"""The knowledge bundle (cluster_analysis/knowledge.py) and results files (explorer/results.py), on made-up data."""
import gzip
import json
import os
import shutil
import tempfile
import unittest
import zipfile

from cluster_analysis import knowledge, sources
from cluster_analysis.evidence import function_evidence

FEATURE = {"type": "VARIANT", "wildType": "A", "alternativeSequence": "V", "begin": "222",
           "xrefs": [{"name": "dbSNP", "id": "rs1801133"}, {"name": "gnomAD", "id": "x"}],
           "genomicLocation": ["NC_000001.11:g.11796321G>A"],
           "descriptions": [{"value": "reduced activity", "sources": ["UniProt"]}],
           "association": [{"name": "Thermolabile", "xrefs": []}],
           "predictions": [{"predAlgorithmNameType": "SIFT", "predictionValType": "deleterious", "score": 0.01, "sources": ["x"]},
                           {"predAlgorithmNameType": "CADD", "predictionValType": "x", "score": 3}],
           "evidences": [{"code": "ECO:0000269", "source": {"name": "pubmed", "id": "123", "url": "u"}},
                         {"code": "ECO:0000313", "source": {"name": "pubmed", "id": "999"}}],
           "populationFrequencies": [{"frequency": 0.3}] * 50}
NO_RS = {**FEATURE, "xrefs": [{"name": "gnomAD", "id": "x"}]}


class TestSlim(unittest.TestCase):
    def test_keeps_what_readers_read(self):
        rec = {"accession": "P42898", "features": [FEATURE, NO_RS], "sequence": "M" * 600}
        s = knowledge.slim_variation(rec)
        self.assertEqual(len(s["features"]), 1)   # without a dbSNP id no reader can find it
        f = s["features"][0]
        self.assertEqual(f["xrefs"], [{"id": "rs1801133"}])
        self.assertNotIn("populationFrequencies", f)
        self.assertEqual([p["predAlgorithmNameType"] for p in f["predictions"]], ["SIFT"])
        self.assertEqual([e["source"]["id"] for e in f["evidences"]], ["123"])
        # The readers give the same answer from the slim record as from the full one
        orig = function_evidence.uniprot_variants
        try:
            function_evidence.uniprot_variants = lambda acc: rec
            a = function_evidence.uniprot_evidence("rs1801133", "P42898", "V")
            function_evidence.uniprot_variants = lambda acc: s
            b = function_evidence.uniprot_evidence("rs1801133", "P42898", "V")
        finally:
            function_evidence.uniprot_variants = orig
        self.assertEqual(a, b)


class TestBuildInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cache = os.path.join(self.tmp, "cache")
        os.makedirs(self.cache)

        def put(name, obj):
            with open(os.path.join(self.cache, name), "w", encoding="utf-8") as f:
                json.dump(obj, f)
        put("prot_variation_0123456789abcdef.json", {"accession": "P1", "features": [FEATURE, NO_RS]})
        put("reactome_query_0123456789abcdef.json", {"x": 1})
        put("agent_recent_0123456789abcdef.json", {"q": "what someone asked"})
        put("agent_cat_0123456789abcd.json", {"reading": "a model wrote this"})
        put("ensembl_vep_aaaaaaaaaaaaaaaa.json", [{"id": "rs2", "v": 1}, {"id": "rs1", "v": 1}])
        put("ensembl_vep_bbbbbbbbbbbbbbbb.json", [{"id": "rs1", "v": 1}, {"id": "rs3", "v": 1}])
        put("vep_index.json", {"files": [], "ids": {}, "absent": ["rs9"]})
        self.out = os.path.join(self.tmp, "out")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_leaves_private_out_and_repacks_batches(self):
        path = knowledge.build(self.out, self.cache)
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            m = json.loads(z.read("knowledge.json"))
            chunk = json.loads(z.read("ensembl_vep_k00000.json"))
            index = json.loads(z.read("vep_index.json"))
        self.assertFalse(any(n.startswith("agent_") for n in names))
        self.assertEqual(m["left_out"], {"agent_recent": 1, "agent_cat": 1})
        self.assertNotIn("ensembl_vep_aaaaaaaaaaaaaaaa.json", names)
        self.assertEqual([r["id"] for r in chunk], ["rs1", "rs2", "rs3"])   # sorted, deduplicated
        self.assertEqual(index["absent"], ["rs9"])
        self.assertEqual(index["ids"]["rs3"], "ensembl_vep_k00000.json")

    def test_rebuild_from_a_cache_with_installed_chunks_has_no_duplicates(self):
        first = knowledge.build(self.out, self.cache)
        knowledge.install(first, cache=self.cache)   # the chunks now sit next to this machine's own batches
        again = knowledge.build(os.path.join(self.tmp, "out2"), self.cache)
        with zipfile.ZipFile(again) as z:
            vep = [n for n in z.namelist() if n.startswith("ensembl_vep_")]
            m = json.loads(z.read("knowledge.json"))
        self.assertEqual(vep, ["ensembl_vep_k00000.json"])
        self.assertNotIn("ensembl", m["namespaces"])
        self.assertEqual(m["namespaces"]["ensembl_vep"]["files"], 3)

    def test_install_into_empty_cache_serves_the_readers(self):
        path = knowledge.build(self.out, self.cache)
        fresh = os.path.join(self.tmp, "fresh")
        knowledge.install(path, cache=fresh, expect_sha256=knowledge.sha256(path))
        self.assertIsNotNone(knowledge.installed(fresh))
        old = sources.CACHE_DIR
        sources.CACHE_DIR = fresh
        try:
            def offline(*a):
                raise AssertionError("asked the network")
            recs = sources.by_variant("ensembl_vep", "vep_index.json", ["rs1", "rs3", "rs9"], offline)
            self.assertEqual(sorted(r["id"] for r in recs), ["rs1", "rs3"])   # rs9: known to be absent, not asked
        finally:
            sources.CACHE_DIR = old

    def test_install_keeps_local_files(self):
        path = knowledge.build(self.out, self.cache)
        mine = os.path.join(self.tmp, "mine")
        os.makedirs(mine)
        with open(os.path.join(mine, "reactome_query_0123456789abcdef.json"), "w") as f:
            f.write('{"mine": true}')
        knowledge.install(path, cache=mine)
        with open(os.path.join(mine, "reactome_query_0123456789abcdef.json")) as f:
            self.assertEqual(json.load(f), {"mine": True})

    def test_wrong_checksum_refused(self):
        path = knowledge.build(self.out, self.cache)
        with self.assertRaises(ValueError):
            knowledge.install(path, cache=os.path.join(self.tmp, "x"), expect_sha256="0" * 64)


class TestResultsFile(unittest.TestCase):
    def setUp(self):
        from cluster_analysis.explorer import results
        self.results = results
        self.tmp = tempfile.mkdtemp()
        self.ds = os.path.join(self.tmp, "datasets")
        os.makedirs(self.ds)
        rows = {"profiles": [{"id": "P1", "sex": "female"}, {"id": "P2", "sex": "male"}],
                "theme_genes": [{"person": "P1", "gene": "A"}, {"person": "P2", "gene": "B"}],
                "med_names": [{"drug": "x"}]}
        for n, r in rows.items():
            with open(os.path.join(self.ds, n + ".json"), "w", encoding="utf-8") as f:
                json.dump(r, f)
        self.old = results.IMPORTED
        results.IMPORTED = os.path.join(self.tmp, "imported")

    def tearDown(self):
        self.results.IMPORTED = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_round_trip_and_rename(self):
        r = self.results
        f = r.export("P1", os.path.join(self.tmp, "p1.gz"), self.ds)
        with gzip.open(f, "rt", encoding="utf-8") as g:
            doc = json.load(g)
        self.assertEqual(doc["datasets"], {"theme_genes": [{"person": "P1", "gene": "A"}]})   # only P1, nothing public
        with self.assertRaises(ValueError):
            r.import_(f, taken={"P1"})
        pid = r.import_(f, as_id="P1b", taken={"P1", "P2"})
        merged = {"profiles": [{"id": "P2"}], "theme_genes": []}
        r.merge(merged, {"P2"})
        self.assertEqual(merged["theme_genes"], [{"person": "P1b", "gene": "A"}])
        self.assertEqual([p["id"] for p in merged["profiles"]], ["P2", "P1b"])
        self.assertEqual(pid, "P1b")

    def test_not_a_results_file(self):
        p = os.path.join(self.tmp, "x.gz")
        with gzip.open(p, "wt") as g:
            g.write('{"format": "something else"}')
        with self.assertRaises(ValueError):
            self.results.read(p)


if __name__ == "__main__":
    unittest.main()
