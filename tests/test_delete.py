"""Deleting a person and deleting everything (cluster_analysis/pipeline.py remove, remove_all), and when the desktop app
stops by itself (explorer/server.py Lifetime). Everything runs in a temporary folder with made-up people, never on
anyone's data."""
import json
import os
import tempfile
import unittest
from unittest import mock

from cluster_analysis import knowledge, pipeline, sources
from cluster_analysis.explorer import results, server
from cluster_analysis.explorer import __main__ as explorer_main
from genome import build as gbuild
from genome import impute


def put(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if isinstance(text, str) else json.dumps(text))


class TestDelete(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        R = self.root = self.tmp.name
        j = lambda *p: os.path.join(R, *p)
        self.out = j(gbuild.OUTPUT)
        self.paths = dict(ROOT=R, INPUT=j("data", "input"), STATE_DIR=j("data", "output", "pipeline"),
                          PROFILES=j("cluster_analysis", "profiles.json"))
        put(self.paths["PROFILES"], {"about": "", "profiles": [
            {"id": "ANN", "sex": "female", "dna": "data/input/ann_raw_file.csv", "added": "2026-01-01"},
            {"id": "BOB", "sex": "male", "dna": "data/input/BOB.csv", "added": "2026-01-01"}]})
        for pid in ("ANN", "BOB"):
            put(j("data", "output", "imputation", pid, "calls.csv"))
            put(os.path.join(self.out, f"gene_calls_{pid}.json"), {})
            put(os.path.join(self.out, "profiles", pid, "med_genes.json"), [])
            put(j("data", "output", "pipeline", pid + ".json"), {"id": pid, "state": "done", "stages": []})
            put(j("data", "output", "agent", "fills", f"20260101-q__{pid}.json"), {})
            put(j("data", "output", "agent", "sessions", f"s-{pid}.json"), {"id": "s", "person": pid, "turns": []})
        put(j("data", "input", "ann_raw_file.csv")); put(j("data", "input", "BOB.csv"))
        put(j("data", "reference", "imputation", "sites_ANN_1kgp_hc.tsv.gz"))
        put(j("data", "output", "imported", "CAT.dnaresults.gz"))
        put(j("data", "output", "agent", "api_key"), "secret")
        put(j("data", "output", "pipeline", "timings.json"), {})
        self.cache = j("cache")
        put(os.path.join(self.cache, "uniprot_0123456789abcdef.json"), {})        # public: stays
        put(os.path.join(self.cache, "agent_interp_0123456789abcdef.json"), {})   # keyed by a question: goes
        put(os.path.join(self.cache, knowledge.MISSES), "")
        self.datasets = j("datasets")
        put(os.path.join(self.datasets, "profiles.json"), [{"id": "ANN"}, {"id": "BOB"}])
        self.patches = [mock.patch.multiple(pipeline, **self.paths),
                        mock.patch.multiple(impute, OUT=j("data", "output", "imputation"), REF=j("data", "reference", "imputation")),
                        mock.patch.object(results, "IMPORTED", j("data", "output", "imported")),
                        mock.patch.object(sources, "CACHE_DIR", self.cache),
                        mock.patch.object(explorer_main, "DATASETS", self.datasets)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def exists(self, *p):
        return os.path.exists(os.path.join(self.root, *p))

    def ids(self):
        with open(self.paths["PROFILES"], encoding="utf-8") as f:
            return [p["id"] for p in json.load(f)["profiles"]]

    def test_remove_one_person_takes_all_of_theirs_and_nothing_else(self):
        out = pipeline.remove("ANN")
        self.assertTrue(out["rebuild"])
        self.assertEqual(self.ids(), ["BOB"])
        for p in (("data", "input", "ann_raw_file.csv"), ("data", "output", "imputation", "ANN"),
                  ("data", "reference", "imputation", "sites_ANN_1kgp_hc.tsv.gz"),
                  ("data", "output", "agent", "fills", "20260101-q__ANN.json"), ("data", "output", "agent", "sessions", "s-ANN.json"),
                  ("data", "output", "pipeline", "ANN.json")):
            self.assertFalse(self.exists(*p), p)
        self.assertFalse(os.path.exists(os.path.join(self.out, "profiles", "ANN")))
        for p in (("data", "input", "BOB.csv"), ("data", "output", "imputation", "BOB"), ("data", "output", "agent", "api_key"),
                  ("data", "output", "agent", "sessions", "s-BOB.json")):
            self.assertTrue(self.exists(*p), p)

    def test_remove_refuses_a_running_person_and_an_unknown_one(self):
        put(os.path.join(self.paths["STATE_DIR"], "BOB.json"), {"id": "BOB", "state": "running", "pid": os.getpid(), "stages": []})
        with self.assertRaises(ValueError):
            pipeline.remove("BOB")
        with self.assertRaises(ValueError):
            pipeline.remove("NOBODY")

    def test_remove_all_keeps_only_public_data(self):
        out = pipeline.remove_all()
        self.assertEqual(sorted(out["people"]), ["ANN", "BOB", "CAT"])
        self.assertEqual(self.ids(), [])
        self.assertFalse(self.exists("data", "output", "agent"))
        self.assertFalse(self.exists("data", "output", "imported"))
        self.assertFalse(self.exists("data", "input", "ann_raw_file.csv"))
        self.assertFalse(self.exists("data", "input", "BOB.csv"))
        self.assertEqual(os.listdir(self.paths["STATE_DIR"]), ["timings.json"])
        self.assertEqual(os.listdir(self.cache), ["uniprot_0123456789abcdef.json"])


class TestLifetime(unittest.TestCase):
    def setUp(self):
        self.saved = dict(server.Lifetime.pages), server.Lifetime.last
        server.Lifetime.pages.clear()

    def tearDown(self):
        server.Lifetime.pages.clear()
        server.Lifetime.pages.update(self.saved[0])
        server.Lifetime.last = self.saved[1]

    def test_idle_only_when_no_window_and_no_recent_request(self):
        L = server.Lifetime
        L.last = 1000
        L.pages["w1"] = 1000
        self.assertFalse(L.idle(1000 + L.IDLE + 1))            # a window checked in recently
        self.assertTrue(L.idle(1000 + L.SEEN + 1))             # its check-ins stopped (closed without goodbye)
        L.touch("w1"); L.touch("w1", bye=True)                 # a window that said goodbye
        self.assertNotIn("w1", L.pages)
        self.assertFalse(L.idle(L.last + 10))                  # but a request just came
        self.assertTrue(L.idle(L.last + L.IDLE + 1))

    def test_working_keeps_it_running(self):
        with mock.patch.object(server, "busy", return_value="ANN"):
            self.assertTrue(server.Lifetime.working())
        with mock.patch.object(server, "busy", return_value=None), mock.patch.object(server.Agent, "running", None), \
                mock.patch.object(server.Agent, "jobs", {}), mock.patch.object(server.Setup, "job", {"state": "idle"}):
            self.assertFalse(server.Lifetime.working())


if __name__ == "__main__":
    unittest.main()
