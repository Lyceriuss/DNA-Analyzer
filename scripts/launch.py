"""Starts DNA-Analyzer on this computer and opens it in the browser; the desktop app's launcher
(scripts/build_desktop.py copies it into the program folder).

    pythonw launch.py            the shortcuts: no window; the server runs in the background
    python launch.py             Troubleshoot (console).cmd / start.sh: the server runs in this console until it is closed (Ctrl+C)
    python launch.py --stop      stops a running server (the "Stop" shortcut, the uninstaller and an update)

Already running (data/server.json names its port and process, and the port answers as this app): the browser opens
on it, nothing else starts. The page opens in an app window of Edge or Chrome (no address bar, its own taskbar entry
and title); DNA_BROWSER=default opens a normal browser tab instead. Otherwise the server starts on port 8470 (or a free one if that is taken; DNA_PORT sets
it), and the browser opens when it answers. Its output, and the launcher's own errors, go to data/logs/.

The one-time setup (unpacking the knowledge bundle the installer brought) is done by the server itself on its first
start (cluster_analysis/knowledge.ensure_included); on later starts that is a version comparison, nothing more.
"""
import json
import os
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
# The program folder: this one, or its parent when run from the repository's scripts/
APP = HERE if os.path.isdir(os.path.join(HERE, "cluster_analysis")) else os.path.dirname(HERE)
DATA = os.path.join(APP, "data")
LOGS = os.path.join(DATA, "logs")
STATE = os.path.join(DATA, "server.json")
PORT = 8470
WINDOWS = os.name == "nt"
NO_WINDOW = 0x08000000   # CREATE_NO_WINDOW


def app_browser():
    """Edge or Chrome, for an app window (--app): Edge comes with Windows 10 and 11. None: the default browser."""
    if os.environ.get("DNA_BROWSER", "").lower() == "default":
        return None
    import shutil
    if WINDOWS:
        roots = [os.environ.get(k) for k in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            for root in filter(None, roots):
                if os.path.exists(os.path.join(root, rel)):
                    return os.path.join(root, rel)
        return None
    return next((p for p in map(shutil.which, ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")) if p), None)


# Shown at once while the server starts (the first start unpacks the research data and builds the page: a minute or
# two): it asks the app every half second and moves to it when it answers. A file, since nothing serves pages yet.
STARTING = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Gene Cluster Explorer</title>
<style>
  html, body {{ height: 100%; margin: 0; }}
  body {{ display: grid; place-items: center; background: #1b1b1b; color: #e8e8e8;
         font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  @media (prefers-color-scheme: light) {{ body {{ background: #f7f7f5; color: #222; }} p {{ color: #555; }} }}
  main {{ text-align: center; max-width: 420px; padding: 0 16px; }}
  h1 {{ font-size: 20px; font-weight: 600; margin: 18px 0 6px; }}
  p {{ margin: 4px 0; color: #aaa; }}
  .ring {{ width: 44px; height: 44px; margin: 0 auto; border-radius: 50%; border: 4px solid rgba(20, 148, 136, .25);
          border-top-color: #149488; animation: spin 1s linear infinite; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  #slow {{ visibility: hidden; }}
</style></head><body><main>
<div class="ring" role="progressbar" aria-label="Starting"></div>
<h1>Starting {name}</h1>
<p>The first start unpacks the research data and prepares the page: a minute or two. Later starts take seconds.</p>
<p id="slow">Still working. If nothing happens, the log is in {logs}.</p>
</main><script>
  const url = {url!r}, t0 = Date.now();
  const tryIt = () => fetch(url + "api/setup", {{ mode: "no-cors", cache: "no-store" }})
    .then(() => location.replace(url))
    .catch(() => {{ if (Date.now() - t0 > 300000) document.getElementById("slow").style.visibility = "visible"; setTimeout(tryIt, 500); }});
  tryIt();
</script></body></html>
"""


def starting_page(url):
    """The "Starting" page for url, written to the data folder; its file:// address."""
    import html
    import pathlib
    os.makedirs(DATA, exist_ok=True)
    p = os.path.join(DATA, "starting.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(STARTING.format(name=html.escape(name()), logs=html.escape(LOGS), url=url))
    return pathlib.Path(p).as_uri()


def open_page(url):
    """The page in its own app window when Edge or Chrome is there, else in the default browser."""
    exe = app_browser()
    if exe:
        try:
            subprocess.Popen([exe, f"--app={url}"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True)
            return
        except OSError as e:
            log(f"app window failed ({e}): opening the default browser")
    webbrowser.open(url)


def name():
    try:
        sys.path.insert(0, APP)
        from cluster_analysis.version import NAME
        return NAME
    except Exception:
        return "DNA-Analyzer"


def log(msg):
    os.makedirs(LOGS, exist_ok=True)
    path = os.path.join(LOGS, "launch.log")
    try:
        if os.path.getsize(path) > 1_000_000:
            os.replace(path, path + ".old")
    except OSError:
        pass
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    if sys.stdout:
        print(msg, flush=True)


def tell(msg, error=False):
    """A message the person sees: the console, or a message box when there is none (the shortcuts)."""
    log(msg)
    if not sys.stdout and WINDOWS:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, name(), 0x10 if error else 0x40)


def env():
    os.environ["PATH"] = os.path.join(APP, "jre", "bin") + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ["PYTHONUNBUFFERED"] = "1"   # the log fills as it happens
    # The app's own lookup cache, in its data folder (the knowledge bundle is installed there)
    os.environ.setdefault("DNA_CACHE_DIR", os.path.join(DATA, "cache"))
    # settings.json: the update feed, and for a test build this machine's panel and cache
    try:
        with open(os.path.join(APP, "settings.json"), encoding="utf-8") as f:
            for k, v in json.load(f).get("env", {}).items():
                os.environ.setdefault(k, v)
    except (OSError, ValueError):
        pass


# --- The running server --------------------------------------------------------------------

def read_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            s = json.load(f)
        return s if isinstance(s.get("port"), int) and isinstance(s.get("pid"), int) else None
    except (OSError, ValueError, AttributeError):
        return None


def write_state(port, pid):
    os.makedirs(DATA, exist_ok=True)
    with open(STATE + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"port": port, "pid": pid, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)
    os.replace(STATE + ".tmp", STATE)


def clear_state(pid=None):
    s = read_state()
    if s and (pid is None or s["pid"] == pid):
        try:
            os.remove(STATE)
        except OSError:
            pass


def alive(pid):
    if WINDOWS:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259   # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def answers(port, timeout=2):
    """True when the port answers as this app (its /api/setup reports a version)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/setup", timeout=timeout) as r:
            return "version" in json.load(r)
    except (OSError, ValueError):
        return False


def free(port):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def pick_port():
    want = int(os.environ.get("DNA_PORT") or PORT)
    if free(want):
        return want
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def running():
    """(port, pid) of this app's server when one runs or is starting, else None (and a stale data/server.json gone)."""
    s = read_state()
    if not s:
        return None
    if alive(s["pid"]):
        if answers(s["port"]):
            return s["port"], s["pid"]
        # Starting: the server builds the page before it listens, so the port may not even be taken yet. Believed
        # only for as long as a first start can take (a stale file whose process id was reused is then ignored)
        try:
            recent = time.time() - os.path.getmtime(STATE) < 3600
        except OSError:
            recent = False
        if recent:
            return s["port"], s["pid"]
    clear_state()
    return None


def stop():
    s = read_state()
    if s and alive(s["pid"]):
        log(f"stopping the server (process {s['pid']})")
        if WINDOWS:
            subprocess.run(["taskkill", "/PID", str(s["pid"]), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
        else:
            import signal
            try:
                os.killpg(s["pid"], signal.SIGTERM)
            except OSError:
                pass
    clear_state()


# --- Starting -----------------------------------------------------------------------------------

def server_python():
    """python.exe, not pythonw.exe: the server's own children (the pipeline, Java) then share its hidden console
    instead of each opening a window."""
    exe = sys.executable
    if WINDOWS and os.path.basename(exe).lower() == "pythonw.exe":
        exe = os.path.join(os.path.dirname(exe), "python.exe")
    return exe


def wait(port, proc, limit=3600):
    """Until the server answers (True), stops (False), or the limit passes (False). The first start unpacks the
    knowledge bundle and builds the page before it listens, which can take minutes."""
    end = time.time() + limit
    while time.time() < end:
        if proc.poll() is not None:
            return False
        if answers(port, timeout=1):
            return True
        time.sleep(0.5)
    return False


def start(background):
    port = pick_port()
    url = f"http://127.0.0.1:{port}/"
    cmd = [server_python(), "-m", "cluster_analysis.explorer", "serve", "--port", str(port)]
    os.makedirs(LOGS, exist_ok=True)
    out = os.path.join(LOGS, "server.log")
    if background:
        if os.path.exists(out):
            os.replace(out, os.path.join(LOGS, "server.previous.log"))
        logf = open(out, "w", encoding="utf-8")
        kw = {"stdout": logf, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
        kw.update({"creationflags": NO_WINDOW} if WINDOWS else {"start_new_session": True})
        # Nothing to close in the background: it stops by itself once no window is open and nothing is working
        # (explorer/server.py Lifetime). The console mode stops when its window is closed.
        kw["env"] = {**os.environ, "DNA_AUTOSTOP": "1"}
    else:
        kw = {}
    log(f"starting the server on {url}")
    proc = subprocess.Popen(cmd, cwd=APP, **kw)
    write_state(port, proc.pid)
    # The window opens now, on the "Starting" page, which moves to the app by itself when it answers
    open_page(starting_page(url))
    if not wait(port, proc):
        if proc.poll() is None:
            proc.kill()
        clear_state(proc.pid)
        tell(f"{name()} stopped while starting (exit code {proc.returncode}). What happened is in {out if background else 'this window'}"
             f"{'' if background else ' and ' + os.path.join(LOGS, 'launch.log')}.", error=True)
        return 1
    if background:
        log(f"running at {url} (process {proc.pid})")
        return 0
    print(f"\n{name()} is running at {url}\nIt runs on this computer only. Close this window to stop it.", flush=True)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    clear_state(proc.pid)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    env()
    if "--stop" in argv:
        stop()
        return 0
    found = running()
    if found:
        port, _ = found
        url = f"http://127.0.0.1:{port}/"
        if answers(port):
            log(f"already running at {url}: opening the browser")
            open_page(url)
        else:   # a second click while the first start is under way: the "Starting" page again (the first may be hidden)
            log(f"already starting at {url}")
            open_page(starting_page(url))
        return 0
    return start(background="--background" in argv or not sys.stdout)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:
        try:
            tell(f"{name()} couldn't start:\n\n{traceback.format_exc()}\n\nThis is also in {os.path.join(LOGS, 'launch.log')}.", error=True)
        except Exception:
            pass
        sys.exit(1)
