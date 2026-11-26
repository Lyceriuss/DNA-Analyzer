"""Ask on an OpenAI-compatible provider (cluster_analysis/agent/models.py): the tool loop against a stand-in server on
localhost (no network, no key), the structured call, the schema clean-up, and which backend is chosen."""
import http.server
import json
import threading
import unittest
from unittest import mock

from cluster_analysis.agent import models, settings


class Fake(http.server.BaseHTTPRequestHandler):
    """Answers /chat/completions: first a tool call, then text; /models lists two. Records every request."""
    seen = []
    replies = []

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Fake.seen.append(("GET", self.path, None, self.headers.get("Authorization")))
        self._send({"data": [{"id": "model-b"}, {"id": "models/model-a"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Fake.seen.append(("POST", self.path, body, self.headers.get("Authorization")))
        self._send(Fake.replies.pop(0))


def tool_call(name, args, cid="call_1"):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}, "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10}}


def text(t):
    return {"choices": [{"message": {"role": "assistant", "content": t}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 5, "prompt_tokens_details": {"cached_tokens": 20}}}


class ModelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        Fake.seen.clear()
        Fake.replies.clear()
        self.s = {"share_results": False, "provider": "custom", "model": "model-a", "small_model": None, "base_url": self.base}
        self.patches = [mock.patch.object(settings, "get", lambda: dict(self.s)),
                        mock.patch.object(models, "api_key", lambda pid: "test-key")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_active_and_backend(self):
        from cluster_analysis.agent import run
        p = models.active()
        self.assertEqual((p["id"], p["model"], p["small"], p["base"]), ("custom", "model-a", "model-a", self.base))
        with mock.patch.dict("os.environ", {}, clear=False):
            self.assertEqual(run.backend(), "openai")
        self.s["model"] = None
        self.assertIsNone(models.active())

    def test_list_models(self):
        self.assertEqual(models.list_models("custom", key="k", base=self.base), ["model-a", "model-b"])
        self.assertEqual(Fake.seen[-1][3], "Bearer k")

    def test_tool_loop(self):
        from cluster_analysis.agent import converse, providers, session as sess, tools
        row = {"person": "PB", "id": "T1", "trait": "body height", "pct": 76.2, "n": 1000, "featured": {"name": "Height", "more": "taller", "less": "shorter"}}
        Fake.replies += [tool_call("my_traits", {"about": ["height"]}), text("Done.")]
        events = []
        with mock.patch.object(providers, "rows", lambda name, person: [row] if name == "trait_scores" else []):
            s = sess.Session(person="PB")
            ctx = tools.new_context("PB", s, share=False)
            usage = converse._engine_openai("How tall am I likely to be?", ctx, s, events.append, None)
        first, second = Fake.seen[0][2], Fake.seen[1][2]
        self.assertEqual(first["model"], "model-a")
        self.assertEqual(first["messages"][0]["role"], "system")
        self.assertNotIn("additionalProperties", json.dumps(first["tools"]))
        self.assertIn("my_traits", [t["function"]["name"] for t in first["tools"]])
        tool_msg = second["messages"][-1]
        self.assertEqual((tool_msg["role"], tool_msg["tool_call_id"]), ("tool", "call_1"))
        self.assertIn("shown_to_person", tool_msg["content"])
        self.assertNotIn("76", tool_msg["content"])          # Restricted mode: the score stays on the screen
        self.assertEqual(len(ctx["cards"]), 1)
        self.assertEqual(usage["output"], 15)
        self.assertEqual(usage["cache_read"], 20)
        self.assertIn("tool_done", [e["type"] for e in events])

    def test_complete_json(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
        Fake.replies += [text("Here you go:\n```json\n{\"b\": 1}\n```"), text("{\"a\": \"yes\"}")]
        obj, usage = models.complete_json("q", "sys", schema)
        self.assertEqual(obj, {"a": "yes"})
        self.assertIn("JSON schema", Fake.seen[0][2]["messages"][0]["content"])
        self.assertIn("missing a", Fake.seen[1][2]["messages"][-1]["content"])

    def test_errors_are_readable(self):
        with mock.patch.object(models, "_post", side_effect=RuntimeError("401 from the model provider: bad key")):
            with self.assertRaises(RuntimeError):
                models.chat(models.active(), [{"role": "user", "content": "x"}])
        self.assertEqual(models._message('{"error": {"message": "Invalid key"}}'), "Invalid key")
        self.assertEqual(models._message('[{"error": {"message": "Quota"}}]'), "Quota")


if __name__ == "__main__":
    unittest.main()
