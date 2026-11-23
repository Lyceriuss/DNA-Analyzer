"""The desktop launcher (scripts/launch.py) and the installer script it is installed with (scripts/build_desktop.py),
against a stand-in server: one start, a second start that only opens the browser, --stop."""
import importlib.util
import os
import shutil
import socket
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

FAKE_SERVER = '''import argparse, http.server, json
ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--port", type=int); a = ap.parse_args()
print("stand-in server", flush=True)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        b = json.dumps({"version": "test"}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", a.port), H).serve_forever()
'''


def load_launch():
    spec = importlib.util.spec_from_file_location("launch_under_test", os.path.join(SCRIPTS, "launch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Launcher(unittest.TestCase):
    def setUp(self):
        self.app = tempfile.mkdtemp()
        pkg = os.path.join(self.app, "cluster_analysis", "explorer")
        os.makedirs(pkg)
        for d in (os.path.dirname(pkg), pkg):
            open(os.path.join(d, "__init__.py"), "w").close()
        with open(os.path.join(pkg, "__main__.py"), "w", encoding="utf-8") as f:
            f.write(FAKE_SERVER)
        self.l = load_launch()
        self.l.APP, self.l.DATA = self.app, os.path.join(self.app, "data")
        self.l.LOGS, self.l.STATE = os.path.join(self.l.DATA, "logs"), os.path.join(self.l.DATA, "server.json")
        self.l.PORT = free_port()
        self.l.env = lambda: None             # the test process's environment stays as it is
        self.l.sys.stdout = sys.stdout        # tell() prints instead of a message box
        self.opened = []
        self.browser = self.l.webbrowser.open
        self.l.webbrowser.open = self.opened.append
        self.l.app_browser = lambda: None     # no Edge or Chrome app window from the tests

    def tearDown(self):
        self.l.webbrowser.open = self.browser
        self.l.stop()
        shutil.rmtree(self.app, ignore_errors=True)

    def test_app_window(self):
        launched = []
        popen = self.l.subprocess.Popen
        self.l.app_browser = lambda: "edge.exe"
        self.l.subprocess.Popen = lambda cmd, **kw: launched.append(cmd)
        try:
            self.l.open_page("http://127.0.0.1:1/")
        finally:
            self.l.subprocess.Popen = popen
        self.assertEqual(launched, [["edge.exe", "--app=http://127.0.0.1:1/"]])
        self.assertEqual(self.opened, [])

    def test_start_reuse_stop(self):
        self.assertEqual(self.l.main(["--background"]), 0)
        url = f"http://127.0.0.1:{self.l.PORT}/"
        self.assertEqual(self.opened, [url])
        state = self.l.read_state()
        self.assertEqual(state["port"], self.l.PORT)
        self.assertTrue(self.l.alive(state["pid"]))
        self.assertTrue(os.path.exists(os.path.join(self.l.LOGS, "server.log")))
        # Started again: the browser opens on the running one, nothing new starts
        self.assertEqual(self.l.main([]), 0)
        self.assertEqual(self.opened, [url, url])
        self.assertEqual(self.l.read_state()["pid"], state["pid"])
        # Stopped
        self.l.main(["--stop"])
        for _ in range(40):
            if not self.l.alive(state["pid"]):
                break
            time.sleep(0.25)
        self.assertFalse(self.l.alive(state["pid"]))
        self.assertIsNone(self.l.read_state())

    def test_stale_state_is_ignored(self):
        self.l.write_state(self.l.PORT, 999999)   # no such process
        self.assertIsNone(self.l.running())
        self.assertIsNone(self.l.read_state())

    def test_python_for_the_server(self):
        if os.name != "nt":
            self.skipTest("Windows only")
        real = sys.executable
        sys.executable = r"C:\app\python\pythonw.exe"
        try:
            self.assertEqual(self.l.server_python(), r"C:\app\python\python.exe")
        finally:
            sys.executable = real


class InstallerScript(unittest.TestCase):
    def test_iss(self):
        sys.path.insert(0, SCRIPTS)
        import build_desktop
        out = tempfile.mkdtemp()
        try:
            text = open(build_desktop.write_iss(r"D:\stage\App", out), encoding="utf-8-sig").read()
        finally:
            shutil.rmtree(out, ignore_errors=True)
        self.assertIn(r'Name: "{userdesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"', text)
        self.assertIn(r'IconFilename: "{app}\app.ico"', text)
        self.assertIn(r"SetupIconFile=D:\stage\App\app.ico", text)
        self.assertIn('Name: "desktopicon"; Description: "A desktop shortcut"\n', text)   # checked by default
        self.assertNotIn(r"python\python.exe", text)                                     # no console window
        self.assertIn('Parameters: """{app}\\launch.py"" --stop"', text)
        self.assertNotIn("{{", text.replace("AppId={{", ""))                             # every brace formatted


if __name__ == "__main__":
    unittest.main()
