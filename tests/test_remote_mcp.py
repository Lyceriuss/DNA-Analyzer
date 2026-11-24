"""The remote MCP server (cluster_analysis/agent/remote.py): OAuth 2.1 end to end against a real server on a free port.
Discovery, dynamic client registration, PKCE, the sign-in page, the token exchange, the MCP session with a bearer token,
and that only public tools are served. No tool is called, so nothing goes to the network."""
import base64
import hashlib
import json
import secrets
import socket
import threading
import time
import unittest
from urllib.parse import parse_qs, urlparse

import httpx
import uvicorn

from cluster_analysis.agent import remote, tools


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class TestRemoteMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.password = "test-" + secrets.token_hex(6)
        server, cls.auth = remote.build(cls.base, cls.password, env={})
        app = server.streamable_http_app(host="127.0.0.1", json_response=True)
        cls.uv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=cls.port, log_level="error"))
        threading.Thread(target=cls.uv.run, daemon=True).start()
        for _ in range(100):
            try:
                httpx.get(cls.base + "/.well-known/oauth-authorization-server", timeout=1)
                break
            except httpx.HTTPError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.uv.should_exit = True

    def mcp(self, token, body, session=None):
        h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
             "MCP-Protocol-Version": "2025-06-18"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        if session:
            h["Mcp-Session-Id"] = session
        return httpx.post(self.base + "/mcp", headers=h, json=body, timeout=10)

    def sign_in(self, password):
        """Register a client, authorize with PKCE, sign in; the redirect the browser would follow."""
        reg = httpx.post(self.base + "/register", json={
            "redirect_uris": ["http://127.0.0.1:9/callback"], "client_name": "Test client",
            "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"], "scope": remote.SCOPE}, timeout=10)
        self.assertEqual(reg.status_code, 201, reg.text)
        client = reg.json()["client_id"]
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        a = httpx.get(self.base + "/authorize", params={
            "response_type": "code", "client_id": client, "redirect_uri": "http://127.0.0.1:9/callback",
            "code_challenge": challenge, "code_challenge_method": "S256", "state": "st-1", "scope": remote.SCOPE,
            "resource": self.base + "/mcp"}, timeout=10)
        self.assertIn(a.status_code, (302, 307), a.text)
        login = a.headers["location"]
        self.assertTrue(login.startswith(self.base + "/login?req="))
        page = httpx.get(login, timeout=10)
        self.assertIn("Test client", page.text)
        req = parse_qs(urlparse(login).query)["req"][0]
        done = httpx.post(self.base + "/login", data={"req": req, "password": password}, timeout=10)
        return client, verifier, done

    def test_unauthenticated_request_points_to_the_metadata(self):
        r = self.mcp(None, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(r.status_code, 401)
        self.assertIn("resource_metadata", r.headers.get("www-authenticate", ""))
        meta = httpx.get(self.base + "/.well-known/oauth-protected-resource/mcp", timeout=10).json()
        self.assertEqual(meta["resource"], self.base + "/mcp")
        self.assertIn(remote.SCOPE, meta.get("scopes_supported", []))
        asm = httpx.get(self.base + "/.well-known/oauth-authorization-server", timeout=10).json()
        self.assertIn("S256", asm["code_challenge_methods_supported"])
        self.assertTrue(asm["registration_endpoint"].endswith("/register"))

    def test_wrong_password_is_refused(self):
        _, _, done = self.sign_in("not-the-password")
        self.assertEqual(done.status_code, 401)

    def test_full_flow_serves_public_tools_only(self):
        client, verifier, done = self.sign_in(self.password)
        self.assertEqual(done.status_code, 302)
        back = parse_qs(urlparse(done.headers["location"]).query)
        self.assertEqual(back["state"], ["st-1"])
        tok = httpx.post(self.base + "/token", data={
            "grant_type": "authorization_code", "code": back["code"][0], "redirect_uri": "http://127.0.0.1:9/callback",
            "client_id": client, "code_verifier": verifier, "resource": self.base + "/mcp"}, timeout=10)
        self.assertEqual(tok.status_code, 200, tok.text)
        token = tok.json()["access_token"]
        # The code is single use
        again = httpx.post(self.base + "/token", data={
            "grant_type": "authorization_code", "code": back["code"][0], "redirect_uri": "http://127.0.0.1:9/callback",
            "client_id": client, "code_verifier": verifier}, timeout=10)
        self.assertNotEqual(again.status_code, 200)
        init = self.mcp(token, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}})
        self.assertEqual(init.status_code, 200, init.text)
        session = init.headers.get("mcp-session-id")
        self.mcp(token, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
        listed = self.mcp(token, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session)
        self.assertEqual(listed.status_code, 200, listed.text)
        names = {t["name"] for t in json.loads(listed.text)["result"]["tools"]}
        public = {n for n, (k, *_) in tools.TOOLS.items() if k == tools.PUBLIC}
        self.assertEqual(names, public)
        self.assertFalse(any(n.startswith(("my_", "show_")) for n in names))
        # A made-up token is refused
        self.assertEqual(self.mcp("forged", {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
