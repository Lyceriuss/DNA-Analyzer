"""The research tools as a remote MCP server: Streamable HTTP, protected by OAuth 2.1 as the MCP authorization
specification defines it, so an MCP client elsewhere (Claude, an agent framework, another app) can connect over the
network with a proper sign-in.

    python -m cluster_analysis.agent remote                                   # http://127.0.0.1:8765/mcp
    python -m cluster_analysis.agent remote --port 8765 --public-url https://research.example.org

Only the public tools are served (genes, variants, clusters, drugs, papers, pathways, nutrients; tools.PUBLIC): no
personal tool, no view, and no person behind the server, so nothing about anyone's genome can be reached through it.
The personal half of Ask stays on the person's own device (mcp_server.py over stdio).

Two ways to issue tokens:
  built-in   (default) a small authorization server in this process: OAuth 2.1 with PKCE, dynamic client
             registration (RFC 7591), a sign-in page guarded by DNA_OAUTH_PASSWORD (a random one is printed when unset),
             opaque tokens kept in memory (an hour; refresh tokens for 30 days), revocation. For demos and one operator.
  external   DNA_OAUTH_ISSUER and DNA_OAUTH_JWKS_URL (and DNA_OAUTH_AUDIENCE, default the server's /mcp URL): tokens from
             an identity provider (Microsoft Entra ID, Auth0, Amazon Cognito, Keycloak, Google), checked as JWTs against
             its published keys; this server is then a resource server only.

Either way the server publishes its OAuth Protected Resource Metadata (RFC 9728), answers an unauthenticated request with
401 and a WWW-Authenticate header pointing to it, and accepts only tokens with the scope dna.research that were issued
for its own URL (RFC 8707 resource indicators).
"""
import hmac
import html
import os
import secrets
import time
from typing import Literal

from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import (AccessToken, AuthorizationCode, AuthorizationParams, RefreshToken,
                                      construct_redirect_uri)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.mcpserver import MCPServer
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from cluster_analysis.agent import tools

SCOPE = "dna.research"
ACCESS_TTL = 3600
REFRESH_TTL = 30 * 86400
CODE_TTL = 300
PY = {"string": "str", "integer": "int", "array": "list[str]"}

INSTRUCTIONS = """Public genetics research tools from DNA-Analyzer: genes (UniProt function, GWAS signals, ClinVar), \
variants (alleles, European frequency, every genome-wide association, ClinVar, ClinPGx), the explorer's clusters and \
their mechanisms, drugs (dosing guidelines and the effect of every genotype), pathways, nutrients, and papers (Europe \
PMC search, abstracts and open full-text paragraphs, studies reporting results by genotype). No personal data is \
reachable here. Cite the refs the tools return."""


# --- The built-in authorization server -------------------------------------------------------------------------------

class BuiltInAuth:
    """An OAuth 2.1 authorization server in memory (the MCP SDK's OAuthAuthorizationServerProvider): the SDK serves
    /authorize, /token, /register and /revoke and checks PKCE; this keeps the clients, codes and tokens, and sends the
    person to a sign-in page (/login) between /authorize and the client's redirect."""

    def __init__(self, base_url, password):
        self.base = base_url.rstrip("/")
        self.resource = self.base + "/mcp"
        self.password = password
        self.clients, self.pending, self.codes, self.access, self.refresh = {}, {}, {}, {}, {}

    async def get_client(self, client_id):
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull):
        self.clients[client_info.client_id] = client_info

    async def authorize(self, client, params: AuthorizationParams):
        req = secrets.token_urlsafe(24)
        self.pending[req] = (client.client_id, params, time.time() + CODE_TTL)
        return f"{self.base}/login?req={req}"

    def approve(self, req):
        """The sign-in succeeded: an authorization code for the pending request, and where to send the browser."""
        client_id, params, expires = self.pending.pop(req)
        if time.time() > expires:
            raise ValueError("The sign-in took too long; start again from the client.")
        code = secrets.token_urlsafe(32)   # 256 bits
        self.codes[code] = AuthorizationCode(
            code=code, scopes=params.scopes or [SCOPE], expires_at=time.time() + CODE_TTL, client_id=client_id,
            code_challenge=params.code_challenge, redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource or self.resource, subject="operator")
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client, authorization_code):
        c = self.codes.get(authorization_code)
        return c if c and c.client_id == client.client_id and c.expires_at > time.time() else None

    def _issue(self, client_id, scopes, resource, subject):
        now = int(time.time())
        at, rt = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.access[at] = AccessToken(token=at, client_id=client_id, scopes=scopes, expires_at=now + ACCESS_TTL,
                                      resource=resource, subject=subject)
        self.refresh[rt] = RefreshToken(token=rt, client_id=client_id, scopes=scopes, expires_at=now + REFRESH_TTL,
                                        resource=resource, subject=subject)
        return OAuthToken(access_token=at, token_type="Bearer", expires_in=ACCESS_TTL, refresh_token=rt,
                          scope=" ".join(scopes))

    async def exchange_authorization_code(self, client, authorization_code: AuthorizationCode):
        self.codes.pop(authorization_code.code, None)   # single use
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.resource,
                           authorization_code.subject)

    async def load_refresh_token(self, client, refresh_token):
        r = self.refresh.get(refresh_token)
        return r if r and r.client_id == client.client_id and (r.expires_at or 0) > time.time() else None

    async def exchange_refresh_token(self, client, refresh_token: RefreshToken, scopes):
        self.refresh.pop(refresh_token.token, None)      # rotated: each refresh token works once
        return self._issue(client.client_id, scopes or refresh_token.scopes, refresh_token.resource, refresh_token.subject)

    async def load_access_token(self, token):
        a = self.access.get(token)
        if a and (a.expires_at or 0) > time.time():
            return a
        self.access.pop(token, None)
        return None

    async def revoke_token(self, token):
        self.access.pop(getattr(token, "token", token), None)
        self.refresh.pop(getattr(token, "token", token), None)


# --- Tokens from an external identity provider -----------------------------------------------------------------------

class JwtVerifier:
    """Checks bearer tokens issued by an identity provider: a JWT signed with one of the keys at its JWKS URL, from its
    issuer, for this server's audience, unexpired, with the dna.research scope."""

    def __init__(self, issuer, jwks_url, audience):
        import jwt
        self.jwt, self.issuer, self.audience = jwt, issuer, audience
        self.keys = jwt.PyJWKClient(jwks_url)

    async def verify_token(self, token):
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            c = self.jwt.decode(token, key, algorithms=["RS256", "ES256", "PS256"], audience=self.audience,
                                issuer=self.issuer)
        except Exception:
            return None
        scopes = (c.get("scope") or c.get("scp") or "")
        scopes = scopes.split() if isinstance(scopes, str) else list(scopes)
        aud = c.get("aud")
        return AccessToken(token=token, client_id=c.get("azp") or c.get("client_id") or c.get("appid") or "external",
                           scopes=scopes, expires_at=c.get("exp"), subject=c.get("sub"),
                           resource=self.audience if (aud == self.audience or (isinstance(aud, list) and self.audience in aud)) else None,
                           claims={"iss": c.get("iss")})


# --- The server -------------------------------------------------------------------------------------------------------

LOGIN = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in to DNA-Analyzer research tools</title><style>
body{{font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;background:#f7f7f5;color:#1d2430;display:grid;place-items:center;min-height:100vh;margin:0}}
main{{background:#fff;border:1px solid #d5dbe3;border-radius:14px;padding:28px 30px;max-width:380px;width:calc(100% - 32px)}}
h1{{font-size:19px;margin:0 0 6px}} p{{color:#5b6472;margin:0 0 16px}} label{{display:grid;gap:6px;font-size:13px;color:#5b6472}}
input{{font:inherit;padding:9px 11px;border:1px solid #d5dbe3;border-radius:8px}} button{{margin-top:16px;width:100%;font:inherit;
padding:9px;border:0;border-radius:999px;background:#0f766e;color:#fff;cursor:pointer}} .bad{{color:#b42318}}
</style></head><body><main><h1>DNA-Analyzer research tools</h1>
<p><b>{client}</b> asks to use the public research tools (scope dna.research). No personal data is reachable through them.</p>
{error}<form method="post"><input type="hidden" name="req" value="{req}"><label>Operator password
<input type="password" name="password" autocomplete="current-password" autofocus required></label>
<button type="submit">Sign in and allow</button></form></main></body></html>"""


def _register_public(server):
    """Each public tool as a typed MCP tool; every call gets a fresh context (its own lookup budget and ledger)."""
    for name, (kind, _fn, schema, desc) in tools.TOOLS.items():
        if kind != tools.PUBLIC:
            continue
        params, names = [], []
        for k, spec in sorted(schema["properties"].items(), key=lambda kv: kv[0] not in schema["required"]):
            t = f"Literal[{', '.join(map(repr, spec['enum']))}]" if spec.get("enum") else PY[spec["type"]]
            params.append(f"{k}: {t}" if k in schema["required"] else f"{k}: {t} | None = None")
            names.append(k)
        src = (f"def {name}({', '.join(params)}):\n"
               f"    args = {{k: v for k, v in dict({', '.join(f'{n}={n}' for n in names)}).items() if v is not None}}\n"
               f"    text, err = tools.call(tools.new_context(None, share=False), {name!r}, args)\n"
               f"    return ('NOT ACCEPTED: ' + text) if err else text\n")
        ns = {"tools": tools, "Literal": Literal}
        exec(src, ns)
        server.add_tool(ns[name], name=name, description=desc)


def build(public_url, password=None, env=None):
    """(the MCP server, the built-in auth or None). public_url is where clients reach this server (no trailing /mcp)."""
    env = os.environ if env is None else env
    base = public_url.rstrip("/")
    resource = base + "/mcp"
    issuer = env.get("DNA_OAUTH_ISSUER")
    if issuer:
        verifier = JwtVerifier(issuer, env["DNA_OAUTH_JWKS_URL"], env.get("DNA_OAUTH_AUDIENCE") or resource)
        settings = AuthSettings(issuer_url=AnyHttpUrl(issuer), resource_server_url=AnyHttpUrl(resource),
                                required_scopes=[SCOPE], validate_token_resource=True)
        server = MCPServer("dna-research", instructions=INSTRUCTIONS, token_verifier=verifier, auth=settings)
        auth = None
    else:
        auth = BuiltInAuth(base, password)
        settings = AuthSettings(issuer_url=AnyHttpUrl(base), resource_server_url=AnyHttpUrl(resource),
                                required_scopes=[SCOPE], validate_token_resource=True,
                                client_registration_options=ClientRegistrationOptions(enabled=True, valid_scopes=[SCOPE],
                                                                                      default_scopes=[SCOPE]),
                                revocation_options=RevocationOptions(enabled=True))
        server = MCPServer("dna-research", instructions=INSTRUCTIONS, auth_server_provider=auth, auth=settings)

        @server.custom_route("/login", methods=["GET", "POST"])
        async def login(request: Request) -> Response:
            if request.method == "GET":
                req = request.query_params.get("req", "")
                return _login_page(auth, req)
            form = await request.form()
            req, pw = str(form.get("req", "")), str(form.get("password", ""))
            if req not in auth.pending:
                return HTMLResponse("This sign-in request is unknown or has expired; start again from the client.", 400)
            if not hmac.compare_digest(pw.encode(), auth.password.encode()):
                return _login_page(auth, req, "That password isn't right.", 401)
            try:
                return RedirectResponse(auth.approve(req), status_code=302)
            except ValueError as e:
                return HTMLResponse(html.escape(str(e)), 400)
    _register_public(server)
    return server, auth


def _login_page(auth, req, error="", status=200):
    pending = auth.pending.get(req)
    if not pending:
        return HTMLResponse("This sign-in request is unknown or has expired; start again from the client.", 400)
    client = auth.clients.get(pending[0])
    name = (client.client_name if client and client.client_name else pending[0])
    return HTMLResponse(LOGIN.format(client=html.escape(name), req=html.escape(req),
                                     error=f'<p class="bad">{html.escape(error)}</p>' if error else ""), status)


def main(host="127.0.0.1", port=8765, public_url=None):
    import uvicorn
    public_url = public_url or f"http://{host}:{port}"
    password = os.environ.get("DNA_OAUTH_PASSWORD")
    if not os.environ.get("DNA_OAUTH_ISSUER") and not password:
        password = secrets.token_urlsafe(12)
        print(f"Operator password for the sign-in page (set DNA_OAUTH_PASSWORD to choose one): {password}", flush=True)
    server, _ = build(public_url, password)
    app = server.streamable_http_app(host=host)
    mode = "external identity provider " + os.environ["DNA_OAUTH_ISSUER"] if os.environ.get("DNA_OAUTH_ISSUER") else "built-in sign-in"
    print(f"DNA-Analyzer research tools over MCP: {public_url.rstrip('/')}/mcp (OAuth 2.1, {mode})", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")
