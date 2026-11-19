"""The research agent (cluster_analysis/agent): its tools never touch a person's data, its answers are held to what the
tools returned, the local fill reads the right copies, and the loop runs a tool call and a submission end to end
against a stand-in for the API. Tests that need the local index skip when it hasn't been built."""
import builtins
import gzip
import io
import json
import os
import tempfile
import types
import unittest
import zipfile
from unittest import mock

from cluster_analysis.agent import answer, facts, index

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONAL = [os.path.normcase(os.path.join(ROOT, "data", d)) for d in ("input", "output")]
HAS_INDEX = os.path.exists(index.PATH)

PAPER = "In the trained group, power improved by 12% in XX carriers. Other genetic factors may also matter."


def ledger():
    led = facts.Ledger()
    led.variants["rs1815739"] = {"chrom": "11", "pos": 66560624, "ref": "C", "alt": "T", "eur_af": 0.43, "gwas_alleles": []}
    led.ref("PMID:1", "PMID 1", "https://europepmc.org/article/MED/1")
    led.text("PMID:1", PAPER)
    return led


def good_answer():
    return {
        "title": "Training and ACTN3", "summary": "Genes shape training a little.", "scope": "ACTN3 only.",
        "axes": [{"id": "power", "name": "Power", "about": "Fast, explosive work."}],
        "groups": [{"title": "Fibre type", "intro": "Fast fibres.", "variants": [{
            "rsid": "rs1815739", "gene": "ACTN3", "effect_allele": "T", "effect": "Stops alpha-actinin-3 being made.",
            "readings": [{"copies": 0, "text": "Both copies work.", "lean": "power"},
                         {"copies": 1, "text": "One copy works.", "lean": None},
                         {"copies": 2, "text": "Power improved by 12% in a trial of this group.", "lean": None}],
            "strength": "suggestive", "sources": ["PMID:1"],
            "quotes": [{"source": "PMID:1", "text": "power improved by 12% … Other genetic factors may also matter"}]}]}],
        "research": [{"text": "Training works for every genotype.", "sources": ["PMID:1"], "quotes": []}],
        "practice": [{"text": "Lift twice a week.", "sources": ["PMID:1"], "when": None},
                     {"text": "Try more endurance work.", "sources": ["PMID:1"], "when": {"rsid": "rs1815739", "copies": [2]}}],
        "limits": ["One variant explains little."],
    }


class TestValidate(unittest.TestCase):
    def test_good_answer_passes(self):
        self.assertEqual(answer.validate(good_answer(), ledger()), [])

    def test_rejects_what_no_tool_returned(self):
        a = good_answer()
        v = a["groups"][0]["variants"][0]
        v["sources"].append("PMID:999")
        v["quotes"].append({"source": "PMID:1", "text": "power doubled"})
        v["effect_allele"] = "G"
        v["readings"][2]["copies"] = 1
        a["research"][0]["text"] = "Training raised power by 40%."
        a["practice"][1]["when"]["rsid"] = "rs1"
        probs = " | ".join(answer.validate(a, ledger()))
        for expect in ("'PMID:999' was not returned", "the quote 'power doubled'", "neither C nor T", "0, 1 and 2 copies",
                       "the figure '40%'", "not one of the answer's variants"):
            self.assertIn(expect, probs)

    def test_shape_is_checked(self):
        # What an MCP client sent in the first live run: practice items without when, with quotes, copies as a number
        a = good_answer()
        del a["practice"][0]["when"]
        a["practice"][0]["quotes"] = []
        a["practice"][1]["when"]["copies"] = 2
        a["groups"][0]["variants"][0]["readings"] = a["groups"][0]["variants"][0]["readings"][:2]
        probs = " | ".join(answer.validate(a, ledger()))
        for expect in ("practice[0]: missing field when", "practice[0]: unknown field quotes", "when.copies: must be array",
                       "readings: needs 3 to 3 items"):
            self.assertIn(expect, probs)

    def test_needs_the_variant_looked_up(self):
        led = ledger()
        del led.variants["rs1815739"]
        self.assertIn("look the variant up", " ".join(answer.validate(good_answer(), led)))

    def test_other_strand_is_explained(self):
        a = good_answer()
        a["groups"][0]["variants"][0]["effect_allele"] = "A"
        self.assertIn("other strand", " ".join(answer.validate(a, ledger())))


class TestFill(unittest.TestCase):
    def test_copies(self):
        self.assertEqual(answer.copies("CT", "T", "C", "T"), 1)
        self.assertEqual(answer.copies("TT", "T", "C", "T"), 2)
        self.assertEqual(answer.copies("GA", "T", "C", "T"), 1)    # reverse-strand letters
        self.assertEqual(answer.copies("CC", "C", "C", "G"), 2)    # a C/G site is read on the forward strand only
        self.assertEqual(answer.copies("CG", "G", "C", "G"), 1)
        self.assertIsNone(answer.copies("AT", "T", "C", "T"))

    def test_fill_picks_the_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            dna = os.path.join(tmp, "p.imputed.csv")
            with open(dna, "w") as f:
                f.write("# test\nRSID,CHROMOSOME,POSITION,RESULT,SOURCE,GP,EUR_AF,CONFIDENCE\nrs1815739,11,66560624,TT,imputed,0.99,0.43,high\n")
            with mock.patch.object(answer, "ANSWERS", os.path.join(tmp, "a")), mock.patch.object(answer, "FILLS", os.path.join(tmp, "f")), \
                    mock.patch.object(answer, "person_file", lambda p: dna):
                aid = answer.save("Which training?", good_answer(), ledger(), {"lang": "en"})
                f = answer.fill(aid, "T1")
        r = f["reads"]["rs1815739"]
        self.assertEqual((r["genotype"], r["copies"]), ("TT", 2))
        self.assertIn("12%", r["reading"])
        self.assertEqual([p["applies"] for p in f["practice"]], [True, True])
        self.assertEqual(f["axes"][0]["variants"], [])


class TestPrivacy(unittest.TestCase):
    """No tool may open anything under data/input or data/output: those hold the people's files and results."""

    def guard(self):
        real = {"open": builtins.open, "gzip": gzip.open, "zip": zipfile.ZipFile.__init__, "io": io.open}
        opened = []

        def check(path):
            p = os.path.normcase(os.path.abspath(os.fspath(path))) if isinstance(path, (str, os.PathLike)) else ""
            opened.append(p)
            if any(p.startswith(d) for d in PERSONAL):
                raise AssertionError(f"a tool opened {path}")

        def g_open(path, *a, **k):
            check(path)
            return real["open"](path, *a, **k)

        def g_gzip(path, *a, **k):
            check(path)
            return real["gzip"](path, *a, **k)

        def g_zip(self_, path, *a, **k):
            check(path)
            return real["zip"](self_, path, *a, **k)
        return opened, [mock.patch.object(builtins, "open", g_open), mock.patch.object(io, "open", g_open),
                        mock.patch.object(gzip, "open", g_gzip), mock.patch.object(zipfile.ZipFile, "__init__", g_zip)]

    @unittest.skipUnless(HAS_INDEX, "the agent index isn't built (python -m cluster_analysis.agent index)")
    def test_tools_read_no_personal_data(self):
        canned = {"hitCount": 1, "resultList": {"result": [{"pmid": "1", "title": "T", "pubYear": "2020", "abstractText": PAPER}]}}
        opened, guards = self.guard()
        with mock.patch.object(facts, "_epmc", lambda params, key: canned), \
                mock.patch.object(facts, "_uniprot", lambda g: {"function": "A protein.", "diseases": [], "tissue": ""}):
            for g in guards:
                g.start()
            try:
                led = facts.Ledger()
                calls = [("themes", {}), ("themes", {"theme": "muscle"}), ("theme_genes", {"theme": "muscle", "mechanism": "fast"}),
                         ("gene", {"symbol": "ACTN3"}), ("variant", {"rsid": "rs1815739"}), ("trait_variants", {"trait": "grip strength"}),
                         ("search_papers", {"query": "ACTN3"}), ("read_paper", {"pmid": "1"})]
                for name, args in calls:
                    text, err = facts.call(led, name, args)
                    self.assertFalse(err, f"{name}: {text[:200]}")
                    self.assertNotIn('"person"', text)
            finally:
                for g in guards:
                    g.stop()
        self.assertTrue(opened, "the guard saw no file opened at all")
        self.assertIn("rs1815739", led.variants)
        self.assertEqual(led.variants["rs1815739"]["ref"] + led.variants["rs1815739"]["alt"], "CT")

    def test_inputs_are_checked(self):
        self.assertTrue(facts.call(facts.Ledger(), "variant", {"rsid": 5})[1])
        self.assertTrue(facts.call(facts.Ledger(), "variant", {"rsid": "rs1", "extra": 1})[1])
        self.assertTrue(facts.call(facts.Ledger(), "nope", {})[1])


def block(**k):
    return types.SimpleNamespace(**k)


class FakeStream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter([])

    def get_final_message(self):
        return self.msg


class FakeClient:
    """Turn 1 looks the variant up; turn 2 submits an answer that cites a source no tool gave; turn 3 fixes it."""

    def __init__(self):
        self.turn, self.seen = 0, []
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(stream=self.stream))

    def stream(self, **kw):
        self.seen.append(kw)
        self.turn += 1
        use = lambda i, name, inp: block(type="tool_use", id=f"t{i}", name=name, input=inp)
        usage = block(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        bad = good_answer()
        bad["research"][0]["sources"] = ["PMID:777"]
        steps = {1: [use(1, "variant", {"rsid": "rs1815739"})], 2: [use(2, "submit_answer", bad)], 3: [use(3, "submit_answer", good_answer())]}
        return FakeStream(block(content=steps[self.turn], stop_reason="tool_use", usage=usage, model="fake"))


class TestLoop(unittest.TestCase):
    @unittest.skipUnless(HAS_INDEX, "the agent index isn't built")
    def test_tool_then_rejected_then_accepted(self):
        from cluster_analysis.agent import run
        events, client = [], FakeClient()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(answer, "ANSWERS", tmp), mock.patch.object(run, "RUNS", tmp):
            # The fake answer cites PMID:1 with a quote: give the ledger that paper the way read_paper would
            real_variant = facts.TOOLS["variant"][0]

            def variant_and_paper(led, rsid, limit=25):
                led.ref("PMID:1", "PMID 1", "u")
                led.text("PMID:1", PAPER)
                return real_variant(led, rsid, limit)
            with mock.patch.dict(facts.TOOLS, {"variant": (variant_and_paper,) + facts.TOOLS["variant"][1:]}):
                aid = run.run("Which training suits me?", client=client, emit=events.append)
            self.assertTrue(aid)
            saved = json.load(open(os.path.join(tmp, aid + ".json"), encoding="utf-8"))
        kinds = [e["type"] for e in events]
        self.assertEqual(kinds[0], "start")
        self.assertIn("tool_done", kinds)
        checks = [e for e in events if e["type"] == "check"]
        self.assertTrue(checks[0]["problems"] and not checks[1]["problems"])
        self.assertEqual(saved["answer"]["groups"][0]["variants"][0]["site"]["ref"], "C")
        # The rejection went back to the model as an error result for the submit_answer call
        results = [b for m in client.seen[-1]["messages"] if m["role"] == "user" and isinstance(m["content"], list)
                   for b in m["content"] if isinstance(b, dict) and b.get("tool_use_id") == "t2"]
        self.assertTrue(results[0]["is_error"] and "PMID:777" in results[0]["content"])


if __name__ == "__main__":
    unittest.main()
