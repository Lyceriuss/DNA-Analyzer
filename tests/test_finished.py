"""Unfinished people stay out of sight: a profile is listed only when its run finished (cluster_analysis/profiles.py),
an imputed file is read only when written to the end (genome/loader.py), and the server tells the page whom it
shows (explorer/server.py). Everything here runs on temporary folders with made-up ids, never on anyone's data."""
import json
import os
import tempfile
import time
import unittest
from unittest import mock

from cluster_analysis import profiles
from genome import impute, loader


def put(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestFinished(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runs = os.path.join(self.tmp.name, "pipeline")
        os.makedirs(self.runs)
        self.path = os.path.join(self.tmp.name, "profiles.json")
        rows = [{"id": "HAND", "sex": "male", "dna": "a.csv"},                       # added by hand: no run record
                {"id": "DONE", "sex": "male", "dna": "b.csv", "added": "2026-01-01"},
                {"id": "HALF", "sex": "female", "dna": "c.csv", "added": "2026-01-01", "pending": True},
                {"id": "OLD", "sex": "female", "dna": "d.csv", "added": "2026-01-01"}]  # registered before the mark
        put(self.path, {"about": "", "profiles": rows})
        for pid, state in (("DONE", "done"), ("HALF", "running"), ("OLD", "failed")):
            put(os.path.join(self.runs, pid + ".json"), {"id": pid, "state": state})
        self.patch = mock.patch.multiple(profiles, PATH=self.path, RUNS=self.runs)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_only_finished_people_are_listed(self):
        with mock.patch.dict(os.environ, {profiles.RUNNING_ENV: ""}):
            self.assertEqual([p["id"] for p in profiles.load()], ["HAND", "DONE"])
        self.assertEqual(len(profiles.load(unfinished=True)), 4)
        self.assertEqual(profiles.get("HALF")["sex"], "female")   # a run's own steps still find their person

    def test_the_running_person_is_listed_to_its_own_run(self):
        with mock.patch.dict(os.environ, {profiles.RUNNING_ENV: "HALF"}):
            self.assertEqual([p["id"] for p in profiles.load()], ["HAND", "DONE", "HALF"])

    def test_a_dismissed_run_counts_as_finished(self):
        os.remove(os.path.join(self.runs, "DONE.json"))
        self.assertTrue(profiles.finished({"id": "DONE"}))
        self.assertFalse(profiles.finished({"id": "DONE", "pending": True}))

    def test_pipeline_marks_and_clears_pending(self):
        from cluster_analysis import pipeline
        with mock.patch.object(pipeline, "PROFILES", self.path):
            pipeline.register("NEW", "male", "data/input/NEW.csv", lite=True)
            row = next(p for p in pipeline.profiles() if p["id"] == "NEW")
            self.assertTrue(row["pending"] and row["lite"])
            pipeline.register("NEW", "male", "data/input/NEW.csv", lite=True, pending=False)
            rows = pipeline.profiles()
            self.assertNotIn("pending", rows[-1])
            self.assertEqual([p["id"] for p in rows], ["HAND", "DONE", "HALF", "OLD", "NEW"])
            self.assertFalse(os.path.exists(self.path + ".tmp"))


    def test_serve_exports_again_when_the_page_lists_someone_unfinished(self):
        from cluster_analysis.explorer import __main__ as explorer
        with tempfile.TemporaryDirectory() as d, mock.patch.object(explorer, "DATASETS", d), \
                mock.patch.dict(os.environ, {profiles.RUNNING_ENV: ""}):
            self.assertEqual(explorer.unfinished_shown(), set())              # nothing exported yet
            put(os.path.join(d, "profiles.json"), [{"id": "HAND"}, {"id": "HALF"}, {"id": "OLD"}])
            self.assertEqual(explorer.unfinished_shown(), {"HALF", "OLD"})
            put(os.path.join(d, "profiles.json"), [{"id": "HAND"}, {"id": "DONE"}])
            self.assertEqual(explorer.unfinished_shown(), set())


class TestWholeFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.csv = os.path.join(self.tmp.name, "MyHeritage_raw_dna_data_P.imputed.csv")
        self.summary = os.path.join(self.tmp.name, "summary.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_dump_json_leaves_no_partial(self):
        impute.dump_json({"a": 1}, self.summary)
        self.assertEqual(read(self.summary), {"a": 1})
        self.assertFalse(os.path.exists(self.summary + impute.PARTIAL))

    def test_imputed_file_is_complete_only_with_its_summary(self):
        put(self.csv, "RSID\n")
        self.assertFalse(loader.imputation_complete(self.csv))               # stopped before the summary
        put(self.summary, {"chroms": {}})
        self.assertFalse(loader.imputation_complete(self.csv))               # the summary Beagle's pass writes first
        impute.dump_json({"chroms": {}, "totals": {}}, self.summary)
        self.assertTrue(loader.imputation_complete(self.csv))
        old = time.time() - 3600
        os.utime(self.summary, (old, old))                                    # an earlier run's summary, a newer half file
        self.assertFalse(loader.imputation_complete(self.csv))


class TestShown(unittest.TestCase):
    def test_shown_reads_the_built_page(self):
        from cluster_analysis.explorer import server
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(server, "SITE", d):
                self.assertEqual(server.shown(), [])                          # not built yet: locked
                os.makedirs(os.path.join(d, "data"))
                put(os.path.join(d, "data", "profiles.json"), [])
                self.assertEqual(server.shown(), [])
                put(os.path.join(d, "data", "profiles.json"), [{"id": "P1", "sex": "male"}])
                self.assertEqual(server.shown(), ["P1"])


if __name__ == "__main__":
    unittest.main()
