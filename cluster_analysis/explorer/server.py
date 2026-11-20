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

First run and results files:
    GET  /api/setup             {"knowledge": installed release or null, "source", "job": download progress, "profiles"}
    POST /api/setup/knowledge   installs the knowledge bundle (data/knowledge/*.zip or DNA_KNOWLEDGE_URL) in the background
    GET  /api/results?id=P      P's results file, as a download (explorer/results.py)
    POST /api/results/import[?as=ID]   a results file's bytes -> {"id"}; the datasets are then rebuilt

The Ask tab's research agent (cluster_analysis/agent), one question at a time:
    GET  /api/agent/status      {"key", "backend": "api" | "claude-code" | null, "index", "model", "effort", "running", "answers"}
    POST /api/agent/key         {"key", "remember"}: the Anthropic API key, in memory or (remember) in data/output/agent
    POST /api/agent/ask         {"question", "lang"} -> {"job"}: runs the agent in the background
    GET  /api/agent/events?job=J&after=N   {"events", "next", "done", "answer"}
    POST /api/agent/stop        {"job"}
    POST /api/agent/settings    {"share_results"}: whether interpreted results go to the model (agent/settings.py)
    GET  /api/agent/answer?id=A the saved answer (no personal data)
    GET  /api/agent/fill?id=A&person=P     the answer read for that person, on this machine
"""
import functools
import http.server
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import urllib.parse

from cluster_analysis import pipeline

ROOT = pipeline.ROOT
UPLOADS = os.path.join(pipeline.STATE_DIR, "uploads")
MAX_BYTES = 300 * 1024 * 1024


def busy():
    return next((r["id"] for r in pipeline.status()["runs"] if r["state"] == "running"), None)


class Setup:
    """First run: the knowledge bundle (cluster_analysis/knowledge.py), from a file the installer placed in
    data/knowledge/ or from DNA_KNOWLEDGE_URL, installed in a background thread with its progress."""
    LOCAL = os.path.join(ROOT, "data", "knowledge")
    job = {"state": "idle", "done": 0, "total": 0, "error": None}
    lock = threading.Lock()

    @classmethod
    def source(cls):
        from cluster_analysis import knowledge
        return knowledge.included(cls.LOCAL) or os.environ.get("DNA_KNOWLEDGE_URL") or None

    update = None
    asked = False

    @classmethod
    def check_update(cls):
        """Once per start, in the background: the update feed (DNA_UPDATE_URL), if the app has one."""
        from cluster_analysis import version
        try:
            cls.update = version.check()
        except Exception:
            cls.update = None

    @classmethod
    def status(cls):
        from cluster_analysis import knowledge, version
        if not cls.asked:
            cls.asked = True
            threading.Thread(target=cls.check_update, daemon=True).start()
        k = knowledge.installed()
        src = cls.source()
        return {"knowledge": k and {x: k.get(x) for x in ("version", "installed", "added")},
                "source": src and ("download" if re.match(r"^https?://", src) else "included"),
                "job": dict(cls.job), "profiles": len(pipeline.profiles()), "version": version.VERSION,
                "update": cls.update if cls.update and cls.update.get("newer") else None}

    @classmethod
    def start(cls):
        from cluster_analysis import knowledge
        src = cls.source()
        if not src:
            raise ValueError("No knowledge bundle to install: none was included and DNA_KNOWLEDGE_URL isn't set.")
        with cls.lock:
            if cls.job["state"] == "running":
                return
            cls.job.update(state="running", done=0, total=0, error=None)

        def progress(done, total):
            cls.job.update(done=done, total=total)

        def work():
            try:
                knowledge.install(src, expect_sha256=os.environ.get("DNA_KNOWLEDGE_SHA256"), progress=progress)
                cls.job["state"] = "done"
            except Exception as e:
                cls.job.update(state="failed", error=f"{type(e).__name__}: {e}")
        threading.Thread(target=work, daemon=True).start()


class Agent:
    """The research agent's runs in this server process: the key, the running job and its events."""
    key = None
    jobs = {}       # job id -> {"events": [...], "done", "answer", "stop"}
    running = None
    lock = threading.Lock()

    @classmethod
    def status(cls):
        from cluster_analysis.agent import answer, index, run
        b = "api" if cls.key else run.backend()
        return {"key": bool(cls.key or run.api_key()), "backend": b, "index": os.path.exists(index.PATH),
                "model": run.MODEL if b == "api" else f"Claude Code ({run.CC_MODEL})",
                "effort": run.EFFORT, "running": cls.running, "answers": answer.listing(), "settings": __import__("cluster_analysis.agent.settings", fromlist=["get"]).get()}

    @classmethod
    def ask(cls, question, lang):
        from cluster_analysis.agent import run
        with cls.lock:
            if cls.running:
                raise RuntimeError("A question is being researched; one at a time.")
            job = secrets.token_hex(6)
            state = {"events": [], "done": False, "answer": None, "stop": False}
            cls.jobs[job], cls.running = state, job

        def emit(ev):
            evs = state["events"]
            # Thinking and text arrive in small pieces: kept as one event per stretch
            if ev["type"] in ("thinking", "text") and evs and evs[-1]["type"] == ev["type"] and not evs[-1].get("_sent"):
                evs[-1]["text"] += ev["text"]
            else:
                evs.append(ev)

        def work():
            try:
                state["answer"] = run.ask(question, lang, key=cls.key, emit=emit, stop=lambda: state["stop"])
            finally:
                state["done"] = True
                cls.running = None
        threading.Thread(target=work, daemon=True).start()
        return job

    @classmethod
    def quick(cls, question, person):
        """The quick answer (agent/quick.py, no model) as a job: its steps light up the sources in the tab."""
        from cluster_analysis.agent import quick
        job = secrets.token_hex(6)
        state = {"events": [], "done": False, "answer": None, "quick": None, "stop": False}
        cls.jobs[job] = state

        def work():
            try:
                res = quick.run(question, person, emit=state["events"].append)
                state["quick"] = res  # shown at once; the written summary follows
                write(res)
            except Exception as e:
                state["events"].append({"type": "error", "message": f"{type(e).__name__}: {e}"})
            finally:
                state["done"] = True

        def write(res):
            """The summary in words (agent/interpret.py): the cluster's findings read once by a small model, for
            everyone; the person's readings picked here."""
            from cluster_analysis.agent import categories, interpret, run
            themes = sorted({c["theme"] for c in res["cards"] if c["provider"] == "findings" and c.get("findings")})
            doms, conds = categories.domains_of(res["cards"])
            if not themes and not doms and not conds:
                return
            from cluster_analysis.agent import cost
            usage = cost.new()
            add = lambda u: cost.add(usage, u)
            if run.backend():
                # Whole domains and clusters, never the person's selection: the choice stays on this machine
                for th in themes:
                    usage = add(interpret.cluster(th, emit=state["events"].append))
                for d in sorted(doms):
                    usage = add(categories.ensure(d, emit=state["events"].append))
                for cname in sorted(conds):
                    usage = add(categories.ensure(universe=categories.conditions(cname), emit=state["events"].append))
            # The person's own categories, most notable first (a usual result only when little else stands out)
            order = {"differs": 0, "high": 0, "low": 1, "raised": 1, "lowered": 2, "typical": 3}
            picked = []
            for c in sorted(res["cards"], key=lambda c: order.get(c["level"], 4)):
                k = categories.key_of(c, person)
                x = categories.cached(k) if k else None
                if not x or (c["level"] == "typical" and len(picked) >= 3):
                    continue
                picked.append({"gene": c["title"], "reading": x["reading"], "takeaway": x["takeaway"], "url": None,
                               "link": (c.get("links") or [None])[0], "title": c["title"], "type": c["provider"], "year": ""})
                if len(picked) >= 5:
                    break
            found = interpret.summary(res, person)
            res["written"] = (found + picked) if themes else (picked + found)
            res["written_tokens"] = usage
            res["written_model"] = interpret.MODEL_API if run.backend() == "api" else f"Claude Code ({interpret.MODEL_CC})"
        threading.Thread(target=work, daemon=True).start()
        return job

    @classmethod
    def converse(cls, question, person, session_id=None):
        """An Ask conversation turn (agent/converse.py) as a job; its result is the saved turn."""
        from cluster_analysis.agent import converse
        job = secrets.token_hex(6)
        state = {"events": [], "done": False, "answer": None, "quick": None, "stop": False, "turn": None}
        cls.jobs[job] = state

        def work():
            try:
                s, turn = converse.ask(question, person, session_id, emit=state["events"].append, stop=lambda: state["stop"])
                state["turn"] = {"session": s.id, "index": len(s.turns) - 1, **turn}
            except Exception as e:
                state["events"].append({"type": "error", "message": f"{type(e).__name__}: {e}"})
            finally:
                state["done"] = True
        threading.Thread(target=work, daemon=True).start()
        return job

    @classmethod
    def events(cls, job, after):
        state = cls.jobs.get(job)
        if not state:
            raise KeyError(job)
        evs = state["events"][after:]
        for e in evs:
            e["_sent"] = True
        n = after + len(evs)
        return {"events": [{k: v for k, v in e.items() if k != "_sent"} for e in evs], "next": n,
                "done": state["done"] and n >= len(state["events"]), "answer": state["answer"],
                "quick": state.get("quick"), "turn": state.get("turn") if state["done"] else None}


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
        # The page holds all the code: the browser asks for it again on every load (a 304 when it hasn't changed),
        # so a rebuilt page shows without a hard reload
        elif self.path.split("?")[0] in ("/", "/index.html") or self.path.split("?")[0].endswith((".html", ".js", ".css")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _agent_get(self, url):
        from cluster_analysis.agent import answer
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        try:
            if url.path == "/api/agent/status":
                return self._json(200, Agent.status())
            if url.path == "/api/agent/events":
                return self._json(200, Agent.events(q.get("job", ""), int(q.get("after") or 0)))
            if url.path == "/api/agent/answer":
                return self._json(200, answer.load(q.get("id", "")))
            if url.path == "/api/agent/session":
                from cluster_analysis.agent import session as sess
                s = sess.Session.load(q.get("id", ""))
                from cluster_analysis.agent import converse
                for t in s.turns:  # answers saved before the calls and the headline existed
                    try:
                        if any(x.get("source") != "score" and "calls" not in x for x in t.get("written") or []):
                            converse.attach_calls(s.person, t["written"], t.get("answer"))
                        if "hero" not in t:
                            t["hero"] = converse.genotype_hero(s.person, t.get("question"), t.get("answer"), t.get("written"))
                    except Exception:
                        pass
                return self._json(200, {"id": s.id, "person": s.person, "turns": s.turns})
            if url.path == "/api/agent/sessions":
                from cluster_analysis.agent import session as sess
                return self._json(200, {"sessions": sess.listing()})
            if url.path == "/api/agent/fill":
                return self._json(200, answer.fill(q.get("id", ""), q.get("person", "")))
        except (KeyError, FileNotFoundError):
            return self._json(404, {"error": "Not found."})
        except (ValueError, SystemExit) as e:
            return self._json(400, {"error": str(e)})
        return self._json(404, {"error": "unknown"})

    def _agent_post(self, path, req):
        from cluster_analysis.agent import run
        if path == "/api/agent/key":
            key = str(req.get("key") or "").strip()
            if not re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", key):
                return self._json(400, {"error": "That doesn't look like an Anthropic API key (sk-ant-…)."})
            Agent.key = key
            if req.get("remember"):
                os.makedirs(os.path.dirname(run.KEY_FILE), exist_ok=True)
                with open(run.KEY_FILE, "w", encoding="utf-8") as f:
                    f.write(key)
            return self._json(200, {"ok": True})
        if path == "/api/agent/settings":
            from cluster_analysis.agent import settings
            return self._json(200, settings.set(share_results=req.get("share_results", True)))
        if path == "/api/agent/converse":
            question = str(req.get("question") or "").strip()
            if not 2 <= len(question) <= 2000:
                return self._json(400, {"error": "Ask a question of up to 2,000 characters."})
            person = str(req.get("person") or "")
            if not re.fullmatch(r"[A-Za-z0-9_\-]{1,32}", person):
                return self._json(400, {"error": "Choose a profile."})
            if not run.backend():
                return self._json(400, {"error": "Ask needs Claude connected: an API key, or Claude Code logged in."})
            sid = req.get("session") or None
            return self._json(200, {"job": Agent.converse(question, person, sid)})
        if path == "/api/agent/quick":
            question = str(req.get("question") or "").strip()
            if not 3 <= len(question) <= 2000:
                return self._json(400, {"error": "Ask a question of up to 2,000 characters."})
            person = str(req.get("person") or "")
            if not re.fullmatch(r"[A-Za-z0-9_\-]{1,32}", person):
                return self._json(400, {"error": "Choose a profile."})
            return self._json(200, {"job": Agent.quick(question, person)})
        if path == "/api/agent/ask":
            question = str(req.get("question") or "").strip()
            if not 3 <= len(question) <= 2000:
                return self._json(400, {"error": "Ask a question of up to 2,000 characters."})
            if not (Agent.key or run.backend()):
                return self._json(400, {"error": "Connect an API key, or install Claude Code and log in."})
            try:
                return self._json(200, {"job": Agent.ask(question, req.get("lang") if req.get("lang") in run.LANGS else "en")})
            except RuntimeError as e:
                return self._json(409, {"error": str(e)})
        if path == "/api/agent/stop":
            state = Agent.jobs.get(str(req.get("job")))
            if state:
                state["stop"] = True
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "unknown"})

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path.startswith("/api/agent/"):
            if not self._local():
                return self._json(403, {"error": "local only"})
            return self._agent_get(url)
        if url.path == "/api/setup":
            if not self._local():
                return self._json(403, {"error": "local only"})
            return self._json(200, Setup.status())
        if url.path == "/api/results":
            # One person's results file, as a download (explorer/results.py). GET, so a link can save it; the Host
            # check keeps other sites out, and a cross-site link could only make the browser save it, never read it
            if not self._local():
                return self._json(403, {"error": "local only"})
            from cluster_analysis.explorer import results
            pid = urllib.parse.parse_qs(url.query).get("id", [""])[0]
            if not pipeline.ID_RE.match(pid):
                return self._json(400, {"error": "no such person"})
            path = os.path.join(UPLOADS, f"{pid}{results.SUFFIX}")
            os.makedirs(UPLOADS, exist_ok=True)
            try:
                results.export(pid, path)
            except SystemExit as e:
                return self._json(404, {"error": str(e)})
            data = open(path, "rb").read()
            os.remove(path)
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header("Content-Disposition", f'attachment; filename="{pid}{results.SUFFIX}"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
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
            if url.path == "/api/results/import":
                from cluster_analysis.explorer import results
                data = self._body()
                folder = os.path.join(UPLOADS, secrets.token_hex(8))
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, "results.gz")
                open(path, "wb").write(data)
                try:
                    as_id = urllib.parse.parse_qs(url.query).get("as", [None])[0]
                    try:
                        pid = results.import_(path, as_id, {p["id"] for p in pipeline.profiles()})
                    except (OSError, EOFError, json.JSONDecodeError):
                        raise ValueError("This isn't a results file.")
                finally:
                    import shutil
                    shutil.rmtree(folder, ignore_errors=True)
                if busy():
                    return self._json(200, {"id": pid, "rebuild": False})
                spawn(["rebuild"])
                return self._json(200, {"id": pid, "rebuild": True})
            req = json.loads(self._body() or b"{}")
            if url.path == "/api/setup/knowledge":
                Setup.start()
                return self._json(200, Setup.status())
            if url.path.startswith("/api/agent/"):
                return self._agent_post(url.path, req)
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
                if req.get("lite"):
                    args += ["--lite"]
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
                spawn(["add", src, "--id", pid] + (["--sex", run["sex"]] if run.get("sex") else [])
                      + (["--lite"] if run.get("lite") else []))
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
    # 127.0.0.1 only: the datasets hold genotypes. Inside a container the server must listen on its own network
    # (DNA_BIND_HOST=0.0.0.0), and the container publishes the port on the host's 127.0.0.1 only (compose.yaml)
    return http.server.ThreadingHTTPServer((os.environ.get("DNA_BIND_HOST", "127.0.0.1"), port), handler)
