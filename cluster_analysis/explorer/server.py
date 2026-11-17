"""The local server behind `explorer serve`: the site's files, plus a small API for adding a person.

Only on 127.0.0.1, and every API call must come from the page itself: the Host header must be this machine and POSTs
carry an X-GX header, which a page on another site can't send without a CORS preflight this server never answers.

    GET  /api/status            {"enabled": true, "runs": [...], "typical": {stage: seconds}, "busy": id or null}
    POST /api/upload?name=F     the file's bytes -> {"token", "info": pipeline.inspect(...)}
    POST /api/start             {"token", "id", "sex"} -> starts cluster_analysis.pipeline add in the background
    POST /api/resume            {"id"}: a failed or stopped run carries on from the stage it reached
    POST /api/cancel            {"id"}: stops the run (and Beagle under it)
    POST /api/dismiss           {"id"}: hides a finished run (the person stays)
    POST /api/abandon           {"id"}: stops an unfinished run if it runs and removes the person with all it made
"""
import functools
import http.server
import json
import os
import re
import secrets
import subprocess
import sys
import urllib.parse

from cluster_analysis import pipeline

ROOT = pipeline.ROOT
UPLOADS = os.path.join(pipeline.STATE_DIR, "uploads")
MAX_BYTES = 300 * 1024 * 1024


def busy():
    return next((r["id"] for r in pipeline.status()["runs"] if r["state"] == "running"), None)


def spawn(args):
    """The pipeline in its own process group, so it outlives a page reload and can be stopped as a whole."""
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    subprocess.Popen([sys.executable, "-m", "cluster_analysis.pipeline", *args], cwd=ROOT, env=env, creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=os.name != "nt")


def kill_tree(pid):
    import psutil
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    for c in p.children(recursive=True) + [p]:
        try:
            c.kill()
        except psutil.NoSuchProcess:
            pass


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    # --- helpers
    def _local(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BYTES:
            raise ValueError("The file is larger than a raw DNA file can be (300 MB).")
        return self.rfile.read(n)

    # --- routes
    def end_headers(self):
        # The datasets change when a person is added: the page must not keep stale copies
        if self.path.startswith("/datasets/") or self.path.endswith(".json"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/api/status":
            if not self._local():
                return self._json(403, {"error": "local only"})
            st = pipeline.status()
            for r in st["runs"]:
                r.pop("src", None)
            return self._json(200, {"enabled": True, **st, "busy": busy(), "profiles": [p["id"] for p in pipeline.profiles()]})
        return super().do_GET()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if not url.path.startswith("/api/") or not self._local() or self.headers.get("X-GX") != "1":
            return self._json(403, {"error": "not allowed"})
        try:
            if url.path == "/api/upload":
                name = urllib.parse.parse_qs(url.query).get("name", ["dna.csv"])[0]
                name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(name))[:80] or "dna.csv"
                data = self._body()
                if not data:
                    return self._json(400, {"error": "The file is empty."})
                token = secrets.token_hex(8)
                folder = os.path.join(UPLOADS, token)
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, name)
                open(path, "wb").write(data)
                try:
                    info = pipeline.inspect(path)
                except Exception as e:  # not a DNA file at all
                    return self._json(200, {"token": token, "info": {"file": name, "problems": [f"The file couldn't be read as a DNA file ({e})."]}})
                return self._json(200, {"token": token, "info": info})
            req = json.loads(self._body() or b"{}")
            pid = str(req.get("id") or "")
            if url.path == "/api/start":
                folder = os.path.join(UPLOADS, re.sub(r"[^0-9a-f]", "", str(req.get("token"))))
                files = os.listdir(folder) if os.path.isdir(folder) else []
                if not files:
                    return self._json(400, {"error": "The uploaded file is gone; choose it again."})
                if not pipeline.ID_RE.match(pid):
                    return self._json(400, {"error": "A name can have letters, digits, _ and -, up to 32 characters."})
                if pid in {p["id"] for p in pipeline.profiles()}:
                    return self._json(400, {"error": f"There is already a profile named {pid}."})
                if busy():
                    return self._json(409, {"error": f"{busy()} is being added; one person at a time."})
                args = ["add", os.path.join(folder, files[0]), "--id", pid]
                if req.get("sex") in ("female", "male"):
                    args += ["--sex", req["sex"]]
                spawn(args)
                return self._json(200, {"ok": True})
            run = pipeline.Run(pid).s if pipeline.ID_RE.match(pid) else None
            if not run:
                return self._json(404, {"error": "No such run."})
            if url.path == "/api/resume":
                if busy():
                    return self._json(409, {"error": f"{busy()} is being added; one person at a time."})
                reg = next((p for p in pipeline.profiles() if p["id"] == pid), None)
                src = os.path.join(ROOT, reg["dna"]) if reg else run.get("src")
                if not src or not os.path.exists(src):
                    return self._json(400, {"error": "The file isn't there any more; start again with the file."})
                spawn(["add", src, "--id", pid] + (["--sex", run["sex"]] if run.get("sex") else []))
                return self._json(200, {"ok": True})
            if url.path == "/api/cancel":
                if run.get("pid"):
                    kill_tree(run["pid"])
                r = pipeline.Run(pid)
                r.s.update(state="cancelled", ended=pipeline.now())
                for st in r.s["stages"]:
                    if st["state"] == "running":
                        st["state"] = "pending"
                r.save()
                return self._json(200, {"ok": True})
            if url.path == "/api/dismiss":
                if run.get("state") != "done":
                    return self._json(409, {"error": "Only a finished run is dismissed; an unfinished one is abandoned."})
                os.remove(pipeline.Run(pid).path)
                return self._json(200, {"ok": True})
            if url.path == "/api/abandon":
                if run.get("state") == "done":
                    return self._json(409, {"error": f"{pid} was added in full."})
                if run.get("state") == "running" and run.get("pid"):
                    kill_tree(run["pid"])
                    r = pipeline.Run(pid)
                    r.s.update(state="cancelled", ended=pipeline.now())
                    r.save()
                out = pipeline.abandon(pid)
                if out["rebuild"]:
                    spawn(["rebuild"])
                return self._json(200, out)
            return self._json(404, {"error": "unknown"})
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})


def make(directory, port):
    handler = functools.partial(Handler, directory=directory)
    # 127.0.0.1 only: the datasets hold genotypes
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
