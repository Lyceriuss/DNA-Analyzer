"""The AI models Ask can run on besides Anthropic's: any provider that speaks the OpenAI-compatible Chat Completions
API with tool calling, by the user's own API key.

    openai      OpenAI                      https://api.openai.com/v1
    gemini      Google Gemini (AI Studio)   https://generativelanguage.googleapis.com/v1beta/openai
    mistral     Mistral                     https://api.mistral.ai/v1
    openrouter  OpenRouter (many models)    https://openrouter.ai/api/v1
    custom      any other compatible server, by its base URL (a self-hosted one too)

Anthropic stays on its own SDK (run.py, converse._engine_api) and Claude Code on its command line; this module covers
the rest. The choice (provider, model, small model, base URL) is in Ask's settings; each provider's key is saved like
the Anthropic one (keystore.py: DPAPI on Windows, mode 600 elsewhere), one file per provider. Plain HTTPS through
urllib: no SDK to install. Model names are never assumed: the user picks from the provider's own /models list.

Two calls: chat(...) runs one step of the tool loop (converse._engine_openai), complete_json(...) one structured
answer for the readings and the question router (interpret._ask, route._ask).
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

PROVIDERS = {
    "openai": {"label": "OpenAI", "company": "OpenAI", "base": "https://api.openai.com/v1", "env": "OPENAI_API_KEY"},
    "gemini": {"label": "Google Gemini", "company": "Google", "base": "https://generativelanguage.googleapis.com/v1beta/openai",
               "env": "GEMINI_API_KEY"},
    "mistral": {"label": "Mistral", "company": "Mistral AI", "base": "https://api.mistral.ai/v1", "env": "MISTRAL_API_KEY"},
    "openrouter": {"label": "OpenRouter", "company": "OpenRouter and the model's maker", "base": "https://openrouter.ai/api/v1",
                   "env": "OPENROUTER_API_KEY"},
    "custom": {"label": "Other (OpenAI-compatible)", "company": "the server at the base URL", "base": None, "env": None},
}
TIMEOUT = 180
RETRIES = 4


def key_file(pid):
    from cluster_analysis.agent import run
    return os.path.join(os.path.dirname(run.KEY_FILE), f"api_key_{pid}")


def api_key(pid):
    p = PROVIDERS.get(pid)
    if not p:
        return None
    if p["env"] and os.environ.get(p["env"]):
        return os.environ[p["env"]]
    from cluster_analysis.agent import keystore
    try:
        return keystore.read(key_file(pid))
    except Exception:
        return None


def save_key(pid, key):
    from cluster_analysis.agent import keystore
    keystore.write(key_file(pid), key)


def forget_key(pid):
    try:
        os.remove(key_file(pid))
    except OSError:
        pass


def base_url(pid, s=None):
    from cluster_analysis.agent import settings
    s = s or settings.get()
    return ((s.get("base_url") if pid == "custom" else None) or PROVIDERS[pid]["base"] or "").rstrip("/")


def active(s=None):
    """The chosen OpenAI-compatible provider when it is ready to use: {id, label, company, base, key, model, small}, else
    None. A custom server may run without a key."""
    from cluster_analysis.agent import settings
    s = s or settings.get()
    pid = s.get("provider")
    if pid not in PROVIDERS or not s.get("model"):
        return None
    key, base = api_key(pid), base_url(pid, s)
    if not base or (pid != "custom" and not key):
        return None
    p = PROVIDERS[pid]
    return {"id": pid, "label": p["label"], "company": p["company"], "base": base, "key": key,
            "model": s["model"], "small": s.get("small_model") or s["model"]}


def _post(url, key, body, timeout=TIMEOUT, method="POST"):
    """JSON over HTTPS, waiting and retrying on 429 and 5xx (the provider's rate limits)."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "DNA-Analyzer"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    last = None
    for i in range(RETRIES + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")[:500]
            last = RuntimeError(f"{e.code} from the model provider: {_message(text)}")
            if e.code in (429, 500, 502, 503, 504) and i < RETRIES:
                wait = e.headers.get("Retry-After")
                time.sleep(min(60, float(wait)) if wait and wait.replace(".", "").isdigit() else 2 ** (i + 1))
                continue
            raise last
        except urllib.error.URLError as e:
            last = RuntimeError(f"Couldn't reach the model provider: {e.reason}")
            if i < RETRIES:
                time.sleep(2 ** (i + 1))
                continue
            raise last
    raise last


def _message(text):
    try:
        d = json.loads(text)
        d = d[0] if isinstance(d, list) and d else d
        e = d.get("error") if isinstance(d, dict) else None
        return (e.get("message") if isinstance(e, dict) else e) or text
    except ValueError:
        return text


def list_models(pid, key=None, base=None):
    """The provider's own model list (GET /models): the ids, sorted."""
    base = (base or base_url(pid)).rstrip("/")
    d = _post(base + "/models", key if key is not None else api_key(pid), None, timeout=30, method="GET")
    ids = [m.get("id") for m in (d.get("data") or d.get("models") or []) if isinstance(m, dict) and m.get("id")]
    return sorted({re.sub(r"^models/", "", i) for i in ids})


def _clean_schema(s):
    """Our tool schemas without the keywords some compatible servers reject (Gemini's: additionalProperties)."""
    if isinstance(s, dict):
        return {k: _clean_schema(v) for k, v in s.items() if k != "additionalProperties"}
    if isinstance(s, list):
        return [_clean_schema(v) for v in s]
    return s


def tool_specs(schemas):
    """tools.schemas() (Anthropic's form) as Chat Completions function tools."""
    return [{"type": "function", "function": {"name": s["name"], "description": s["description"][:1024],
                                              "parameters": _clean_schema(s["input_schema"])}}
            for s in schemas if s.get("input_schema")]


def usage_of(d):
    u = d.get("usage") or {}
    cached = ((u.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0
    return {"input": max(0, (u.get("prompt_tokens") or 0) - cached), "cache_read": cached, "cache_write": 0,
            "output": u.get("completion_tokens") or 0, "usd": 0.0}


def chat(p, messages, tools=None, small=False, max_tokens=8000):
    """One Chat Completions call: (assistant message, usage)."""
    body = {"model": p["small"] if small else p["model"], "messages": messages}
    if tools:
        body |= {"tools": tools, "tool_choice": "auto"}
    if max_tokens:
        body["max_tokens"] = max_tokens
    d = _post(p["base"] + "/chat/completions", p["key"], body)
    ch = (d.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    return {"role": "assistant", "content": msg.get("content") or "", "tool_calls": msg.get("tool_calls") or [],
            "finish": ch.get("finish_reason")}, usage_of(d)


def _json_in(text):
    """The JSON object in a reply (bare, fenced, or with words around it)."""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except ValueError:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a:
            return json.loads(text[a:b + 1])
        raise


def complete_json(prompt, system, schema, small=True, p=None):
    """One structured answer: (object, usage). The schema goes in the instructions (compatible servers differ in what
    structured-output options they accept); the reply is parsed and its required keys checked, once retried."""
    p = p or active()
    if not p:
        raise RuntimeError("No model provider is set up for Ask.")
    sys_text = (system + "\n\nReply with one JSON object only, no other text, matching this JSON schema:\n"
                + json.dumps(schema, ensure_ascii=False))
    messages = [{"role": "system", "content": sys_text}, {"role": "user", "content": prompt}]
    total = None
    for attempt in range(2):
        msg, u = chat(p, messages, small=small, max_tokens=16000)
        total = u if total is None else {k: total.get(k, 0) + u.get(k, 0) for k in u}
        try:
            obj = _json_in(msg["content"])
            missing = [k for k in schema.get("required", []) if k not in obj]
            if not missing:
                return obj, total
            problem = f"missing {', '.join(missing)}"
        except ValueError as e:
            problem = f"not valid JSON ({e})"
        messages += [{"role": "assistant", "content": msg["content"]},
                     {"role": "user", "content": f"That reply was {problem}. Send the JSON object only."}]
    raise RuntimeError(f"The model's reply was {problem}.")
