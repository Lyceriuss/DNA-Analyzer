"""The Anthropic API key at rest (cluster_analysis/agent/keystore.py): encrypted on Windows, mode 600 elsewhere, an old
plain-text file migrated, and never sent back to the page, put in a results file, the knowledge bundle or the installer."""
import gzip
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile

from cluster_analysis.agent import keystore, run

KEY = "sk-ant-api03-" + "Xy7_q-" * 12 + "TESTKEY"
WINDOWS = sys.platform == "win32"


class KeyFile(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "agent", "api_key")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def raw(self):
        with open(self.path, "rb") as f:
            return f.read()

    def test_round_trip(self):
        keystore.write(self.path, KEY + "\n")
        self.assertEqual(keystore.read(self.path), KEY)
        if WINDOWS:
            self.assertTrue(self.raw().startswith(keystore.MAGIC))
            self.assertNotIn(KEY.encode(), self.raw())
            self.assertNotIn(KEY[-20:].encode(), self.raw())
        else:
            self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_migrates_plain_text(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(KEY + "\n")
        if not WINDOWS:
            os.chmod(self.path, 0o644)
        self.assertEqual(keystore.read(self.path), KEY)
        if WINDOWS:
            self.assertTrue(self.raw().startswith(keystore.MAGIC))
            self.assertNotIn(KEY.encode(), self.raw())
        else:
            self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(keystore.read(self.path), KEY)   # and reads the same afterwards

    def test_missing_empty_or_altered(self):
        self.assertIsNone(keystore.read(self.path))
        os.makedirs(os.path.dirname(self.path))
        open(self.path, "w").close()
        self.assertIsNone(keystore.read(self.path))
        if WINDOWS:
            with open(self.path, "wb") as f:
                f.write(keystore.MAGIC + b"not a DPAPI blob")
            self.assertIsNone(keystore.read(self.path))

    def test_run_reads_it(self):
        old_file, old_env = run.KEY_FILE, os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            run.KEY_FILE = self.path
            self.assertIsNone(run.api_key())
            run.save_api_key(KEY)
            self.assertEqual(run.api_key(), KEY)
        finally:
            run.KEY_FILE = old_file
            if old_env is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_env


class NeverSentBack(unittest.TestCase):
    """The server takes the key and reports only that one exists."""

    def setUp(self):
        from cluster_analysis.explorer import server
        self.server = server
        self.dir = tempfile.mkdtemp()
        self.old = run.KEY_FILE, server.Agent.key, os.environ.pop("ANTHROPIC_API_KEY", None)
        run.KEY_FILE = os.path.join(self.dir, "api_key")
        self.srv = server.make(self.dir, 0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        run.KEY_FILE, self.server.Agent.key, env = self.old
        if env is not None:
            os.environ["ANTHROPIC_API_KEY"] = env
        shutil.rmtree(self.dir, ignore_errors=True)

    def call(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"X-GX": "1", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8")

    def test_status_says_only_whether(self):
        out = self.call("/api/agent/key", {"key": KEY, "remember": True})
        self.assertNotIn(KEY, out)
        self.assertEqual(keystore.read(run.KEY_FILE), KEY)
        if WINDOWS:
            self.assertNotIn(KEY.encode(), open(run.KEY_FILE, "rb").read())
        status = self.call("/api/agent/status")
        self.assertIs(json.loads(status)["key"], True)
        self.assertNotIn(KEY, status)
        self.assertNotIn(KEY[-20:], status)
        for path in ("/api/setup", "/api/status", "/api/agent/sessions"):
            self.assertNotIn(KEY[-20:], self.call(path), path)
        # A bad key is refused without being echoed
        bad = KEY.replace("sk-ant-", "nope-")
        self.assertNotIn(bad, self.call("/api/agent/key", {"key": bad}))


class LeftOut(unittest.TestCase):
    """The key file lives in data/output/agent: none of the things that leave the machine read that folder."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.agent = os.path.join(self.dir, "data", "output", "agent")
        keystore.write(os.path.join(self.agent, "api_key"), KEY)
        # The plain-text form too, as an older version left it: what would leak if a folder were packed whole
        with open(os.path.join(self.agent, "api_key.old"), "w", encoding="utf-8") as f:
            f.write(KEY)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_results_file(self):
        from cluster_analysis.explorer import results
        ds = os.path.join(self.dir, "datasets")
        os.makedirs(ds)
        with open(os.path.join(ds, "profiles.json"), "w", encoding="utf-8") as f:
            json.dump([{"id": "P1", "sex": "female"}], f)
        with open(os.path.join(ds, "genes.json"), "w", encoding="utf-8") as f:
            json.dump([{"person": "P1", "gene": "MTHFR"}], f)
        out = os.path.join(self.dir, "P1" + results.SUFFIX)
        results.export("P1", out, datasets=ds)
        with gzip.open(out, "rt", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("MTHFR", text)
        self.assertNotIn(KEY[-20:], text)
        self.assertNotIn("api_key", text)

    def test_knowledge_bundle(self):
        from cluster_analysis import knowledge
        cache = os.path.join(self.dir, "cache")
        os.makedirs(cache)
        with open(os.path.join(cache, "mygene_0123456789abcd.json"), "w", encoding="utf-8") as f:
            json.dump({"symbol": "MTHFR"}, f)
        path = knowledge.build(os.path.join(self.dir, "bundle"), cache=cache)
        with zipfile.ZipFile(path) as z:
            self.assertFalse([n for n in z.namelist() if "api_key" in n])
            for n in z.namelist():
                self.assertNotIn(KEY[-20:].encode(), z.read(n), n)

    def test_installer_files(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
        import build_desktop
        files = build_desktop.shipped_files()
        self.assertTrue(files)
        self.assertFalse([f for f in files if "api_key" in os.path.basename(f) or f.startswith("data/")])
        # The installer copies the staged folder without its data folder
        self.assertIn(r'Excludes: "\data\*', build_desktop.ISS)


if __name__ == "__main__":
    unittest.main()
