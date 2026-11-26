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



class PairTest(unittest.TestCase):
    """Ask's my_child: a child's results reach the model only with Restricted mode off (share_results), never as a
    genotype, an rsID, a star allele or a profile id, and for the XX and XY picked in Ask. The rows are made up."""
    P = {"pair": "PA__PB", "xx": "PA", "xy": "PB"}
    ROWS = {
        "inh_meta": [{**P, "featured": json.dumps([{"id": "T1", "name": "Height", "more": "taller", "less": "shorter"}])}],
        "inh_predictions": [{**P, "id": "T1", "trait": "body height", "reported": "Height", "pmid": "9", "author": "A", "year": "2020",
                             "n": "1000", "sample": "1,000 people", "variants": "40", "definition": "The height of an organism.",
                             "child_pct": "76.2", "child_lo": "40", "child_hi": "95", "child_lo98": "10", "child_hi98": "99.5",
                             "XX_pct": "80", "XY_pct": "30", "push_XX": "0.4", "push_XY": "-0.2", "n_settled": "10", "n_chance": "20",
                             "n_unread": "10", "top": json.dumps([{"rsid": "rs7777777", "allele": "C", "XX": 2, "XY": 1}])}],
        "inh_conditions": [{**P, "gene": "GENE1", "conditions": json.dumps([{"id": "OMIM:1", "name": "Condition one", "modes": ["AR"]}]),
                            "clinvar_names": "[]", "modes": '["AR"]', "on_x": "False", "XX_copies": "1", "XY_copies": "1",
                            "variants": json.dumps([{"rsid": "rs8888888", "XX": {"genotype": "AG"}}]),
                            "outcomes": json.dumps({"AR": {"child": {"affected": 0.25, "carrier": 0.5}}}), "confidence": "0.95"}],
        "inh_traits": [], "inh_drugs": [{**P, "gene": "CYP2C19", "XX_alleles": "*1/*2", "XX_type": "Intermediate metaboliser",
                                         "XY_alleles": "*1/*1", "XY_type": "Normal metaboliser",
                                         "types": json.dumps([{"type": "Normal metaboliser", "p": 0.5}, {"type": "Intermediate metaboliser", "p": 0.5}])}],
    }

    def run_tool(self, share, person="PB", picked=None):
        from cluster_analysis.agent import providers, tools
        with mock.patch.object(providers, "rows", lambda name, person: self.ROWS.get(name, [])):
            ctx = tools.new_context(person, share=share)
            ctx["pair"] = picked
            text, err = tools.call(ctx, "my_child", {"about": ["height", "condition one", "CYP2C19"]})
        self.assertFalse(err, text)
        return json.loads(text), ctx

    def assert_no_leak(self, text):
        for bad in ("PA", "PB", "rs7777777", "rs8888888", "AG", "*1/*2", "*1/*1"):
            self.assertNotIn(bad, text.replace("PA__PB", "?"), bad)

    def test_restricted_mode_sends_public_part_only(self):
        for picked in (None, {"xx": "PA", "xy": "PB"}):
            out, ctx = self.run_tool(False, picked=picked)
            self.assertNotIn("results", out)
            self.assertNotIn("Top", json.dumps(out))
            self.assertEqual(out["found"], 3)
            self.assertEqual(len(ctx["cards"]), 3)   # the person still sees them
            self.assert_no_leak(json.dumps(out))

    def test_shared_is_interpreted_only(self):
        out, ctx = self.run_tool(True)
        text = json.dumps(out, ensure_ascii=False)
        self.assert_no_leak(text)
        res = {r["item"]: r for r in out["results"]}
        self.assertEqual(res["body height"]["child"], "Top 24% · taller")
        self.assertEqual(res["body height"]["the XY parent"], "Bottom 30% · shorter")
        self.assertEqual(res["GENE1"]["child_outcomes"]["AR"]["child"]["affected"], 0.25)
        self.assertEqual(res["CYP2C19"]["child_types"][0], {"type": "Normal metaboliser", "odds": 0.5})
        self.assertEqual(out["asker_is"], "the XY parent")
        self.assertIn("PMID:9", ctx["ledger"].refs)

    def test_picked_pair(self):
        # Asked from a third profile with the pair picked: found, and the asker is neither parent
        out, _ = self.run_tool(True, person="PC", picked={"xx": "PA", "xy": "PB"})
        self.assertEqual(out["found"], 3)
        self.assertEqual(out["asker_is"], "neither parent")
        self.assert_no_leak(json.dumps(out, ensure_ascii=False))
        # A pick the explorer has no results for falls back to the asker's own pair; none at all is an error
        out, _ = self.run_tool(True, person="PB", picked={"xx": "PZ", "xy": "PB"})
        self.assertEqual(out["found"], 3)
        from cluster_analysis.agent import providers, tools
        with mock.patch.object(providers, "rows", lambda name, person: self.ROWS.get(name, [])):
            self.assertTrue(tools.call(tools.new_context("PC", share=True), "my_child", {"about": ["height"]})[1])

    def test_names_only_what_was_asked(self):
        from cluster_analysis.agent import pair
        with mock.patch.object(pair.providers, "rows", lambda name, person: self.ROWS.get(name, [])):
            self.assertEqual([k for k, _ in pair.find(self.P, ["CYP2C19"])], ["drug"])
            self.assertEqual(pair.find(self.P, ["eye colour"]), [])

    def test_trait_model_reads_no_personal_data(self):
        from cluster_analysis.agent import pair, tools
        from cluster_analysis.inheritance import predict
        if not os.path.exists(predict.MODELS):
            self.skipTest("the trait models aren't built")
        pair._MODELS.clear()
        ctx = tools.new_context("PB")   # reads Ask's settings, before the guard
        opened, guards = TestPrivacy.guard(self)
        for g in guards:
            g.start()
        try:
            text, err = tools.call(ctx, "trait_model", {"trait": "height"})
        finally:
            for g in guards:
                g.stop()
        self.assertFalse(err, text)
        self.assertIn('"definition"', text)
        self.assertTrue(opened)

    def test_generic_share_skips_pair_cards(self):
        from cluster_analysis.agent import tools
        self.assertEqual(tools.interpreted([c for c in [{"pair": True}] if not c.get("pair")]), [])



class TraitsTest(unittest.TestCase):
    """Ask's my_traits: the person's GWAS trait scores. Restricted mode on, the model gets the public part only (no
    band, no variant); off, the band in words. The screen card carries the numbers the tab draws. The row is made up."""
    ROW = {"person": "PB", "id": "T1", "trait": "body height", "reported": "Height", "pmid": "9", "author": "A", "year": "2020",
           "n": 1000, "pct": 76.2, "used": 40, "variants": 40, "definition": "The height of an organism.",
           "featured": {"name": "Height", "more": "taller", "less": "shorter"},
           "top": [{"rsid": "rs7777777", "gene": "GENE9", "allele": "C", "raises": True, "copies": 2, "average": 0.5, "shift": 0.3}]}

    def run_tool(self, share):
        from cluster_analysis.agent import providers, tools
        with mock.patch.object(providers, "rows", lambda name, person: [self.ROW] if name == "trait_scores" else []):
            ctx = tools.new_context("PB", share=share)
            text, err = tools.call(ctx, "my_traits", {"about": ["height"]})
        self.assertFalse(err, text)
        return text, ctx

    def test_restricted(self):
        text, ctx = self.run_tool(False)
        for bad in ("Top 24", "rs7777777", "GENE9", "76"):
            self.assertNotIn(bad, text)
        self.assertIn("The height of an organism.", text)
        self.assertEqual(ctx["cards"][0]["data"]["pct"], 76.2)      # drawn on the screen
        self.assertEqual(ctx["cards"][0]["headline"], "Top 24% · taller")

    def test_open(self):
        text, _ = self.run_tool(True)
        self.assertIn("Top 24% · taller", json.loads(text)["results"][0]["summary"])


class DocumentedTest(unittest.TestCase):
    def test_every_tool_is_documented(self):
        """Sources and documentation and the Ask tab show each tool from ask_tools.json: every tool needs its entry
        (abbreviation, name, description), every entry a tool, and no two share an abbreviation."""
        from cluster_analysis.agent import tools
        d = json.load(open(os.path.join(ROOT, "cluster_analysis", "explorer", "ask_tools.json"), encoding="utf-8"))
        described = set(d["tools"])
        self.assertEqual(sorted(set(tools.TOOLS) - described), [], "tools without an entry in ask_tools.json")
        self.assertEqual(sorted(described - set(tools.TOOLS)), [], "ask_tools.json describes tools Ask no longer has")
        abbrs = [t["abbr"] for t in d["tools"].values()] + [x["abbr"] for x in d["drawn"]]
        self.assertEqual(len(abbrs), len(set(abbrs)), "two share an abbreviation")
        for t in d["tools"].values():
            self.assertTrue(t["label"] and t["what"] and 2 <= len(t["abbr"]) <= 3)


class FunctionCallsTest(unittest.TestCase):
    """my_genes_by_function: one row per gene, reviewed protein changes first, then two copies, then more tissues; the
    model gets counts only in Restricted mode. Made-up rows."""
    ROWS = [{"person": "PB", "theme": "muscle", "gene": "EXPR1", "function": "GoF", "basis": "expression", "dose": "2", "rsid": "rs1", "genotype": "AA",
             "fn_evidence": "A raises EXPR1 expression in 12 tissues"},
            {"person": "PB", "theme": "cancer", "gene": "EXPR1", "function": "GoF", "basis": "expression", "dose": "2", "rsid": "rs1", "genotype": "AA",
             "fn_evidence": "A raises EXPR1 expression in 12 tissues"},
            {"person": "PB", "theme": "muscle", "gene": "CUR1", "function": "GoF", "basis": "curated", "dose": "1", "rsid": "rs2", "genotype": "AG",
             "fn_evidence": "p.Ile57Val: increased kinase activity"},
            {"person": "PB", "theme": "muscle", "gene": "LOF1", "function": "LoF", "basis": "curated", "dose": "1", "rsid": "rs3", "genotype": "AG"}]

    def test_order_and_privacy(self):
        from cluster_analysis.agent import functions, providers, tools
        with mock.patch.object(providers, "rows", lambda name, person: self.ROWS if name == "theme_genes" else []):
            ctx = tools.new_context("PB", share=False)
            text, err = tools.call(ctx, "my_genes_by_function", {"function": "gain of function"})
        self.assertFalse(err, text)
        genes = ctx["cards"][0]["data"]["genes"]
        self.assertEqual([g["gene"] for g in genes], ["CUR1", "EXPR1"])          # reviewed first; LoF left out
        self.assertEqual(genes[1]["themes"], ["cancer", "muscle"])                # one row per gene, clusters merged
        for bad in ("rs1", "rs2", "EXPR1", "CUR1", "AA", "AG"):
            self.assertNotIn(bad, text)                                            # Restricted mode: counts only

if __name__ == "__main__":
    unittest.main()
