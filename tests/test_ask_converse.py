"""The Ask conversation (agent/tools.py, session.py): personal tools give the model no values, citations must come from
the tools, and a follow-up's context holds nothing from the person's screen."""
import json
import unittest
from unittest import mock

from cluster_analysis.agent import providers, session, tools


CARD = providers.card("medicines", "TPMT", "TPMT: Intermediate metabolizer", level="differs", value=61,
                      headline="Your TPMT (*1/*3A, intermediate metabolizer) changes the guidance for 4 medicines",
                      rows=[{"label": "azathioprine", "value": "Start at 30 to 80% of the usual dose."}])


class TestPersonalTools(unittest.TestCase):
    def test_blind_shape_says_nothing_about_the_result(self):
        ctx = tools.new_context("P", share=False)
        with mock.patch.object(providers, "medicines", lambda person, ids=None: [CARD]):
            text, err = tools.call(ctx, "my_medicines", {})
        self.assertFalse(err)
        for leak in ("TPMT", "metabolizer", "*3A", "azathioprine", "61", "4 medicines"):
            self.assertNotIn(leak, text)
        self.assertEqual(ctx["cards"], [CARD])  # ... while the screen gets the result

    def test_shared_results_are_the_interpreted_ones_for_the_item(self):
        """Sharing on: the model gets the interpreted results the tool showed, nothing else."""
        ctx = tools.new_context("P", share=True)
        with mock.patch.object(providers, "medicines", lambda person, ids=None: [CARD]):
            text, err = tools.call(ctx, "my_medicines", {})
        d = json.loads(text)
        self.assertEqual(d["results"][0]["result"], "TPMT: Intermediate metabolizer")
        self.assertEqual(len(d["results"]), 1)

    def test_views_are_recorded_for_the_screen(self):
        ctx = tools.new_context("P")
        tools.call(ctx, "show_cluster", {"theme": "muscle", "gene": "ACTN3"})
        self.assertEqual(ctx["views"], [{"view": "cluster", "theme": "muscle", "gene": "ACTN3", "mechanism": None}])


class TestAnswer(unittest.TestCase):
    def test_citations_must_come_from_the_tools(self):
        ctx = tools.new_context("P")
        ctx["ledger"].ref("PMID:1", "PMID 1", "u")
        text, err = tools.call(ctx, "answer", {"summary": "S.", "explanation": "Shown in [PMID:1] and [PMID:2]."})
        self.assertIn("PMID:2", text)
        self.assertIsNone(ctx["answer"])
        self.assertIn("summary", tools.call(ctx, "answer", {"explanation": "Shown in [PMID:1]."})[0].lower())
        tools.call(ctx, "answer", {"summary": "Your result points one way [PMID:1].", "explanation": "Shown in [PMID:1].", "followups": ["More?"]})
        self.assertEqual(ctx["answer"]["refs"], {"PMID:1": {"label": "PMID 1", "url": "u"}})


class TestHighlights(unittest.TestCase):
    def test_a_personal_figure_must_be_in_that_result(self):
        """'yours' as a source: the figure must be in the person's result the label names, only when sharing is on."""
        score = providers.card("nutrient", "b12:score", "Vitamin B12", level="high", value=73, headline="73rd percentile")
        ctx = tools.new_context("P", share=True)
        ctx["cards"], ctx["question"] = [score], "Where does my vitamin B12 score rank?"
        def ok(hs):  # each check on its own first attempt (the third rejection is accepted without what failed)
            ctx["rejections"] = 0
            return tools.call(ctx, "answer", {"summary": "S.", "explanation": "E.", "highlights": hs})[0]
        self.assertIn('"ok"', ok(["Vitamin B12 score | top 27% | yours"]))
        self.assertIn("not in the person", ok(["Vitamin B12 score | top 58% | yours"]))
        self.assertIn("no result", ok(["Made up | top 27% | yours"]))
        self.assertIn("top X%", ok(["Vitamin B12 score | 73rd percentile | yours"]))  # ranks read as top/bottom X%
        blind = tools.new_context("P", share=False)
        blind["cards"], blind["question"] = [score], ctx["question"]
        self.assertIn("not shared", tools.call(blind, "answer", {"summary": "S.", "explanation": "E.", "highlights": ["Vitamin B12 | top 27% | yours"]})[0])


class TestRanks(unittest.TestCase):
    """Where a score ranks is said only when asked, as top/bottom X% (agent/language.py)."""

    def test_rank_words(self):
        from cluster_analysis.agent import language
        self.assertEqual([language.rank_words(p) for p in (95, 19, 65, 8, 50, 100)],
                         ["top 5%", "bottom 19%", "top 35%", "bottom 8%", "normal (near the European baseline)", "top 1%"])

    def test_top_is_the_favourable_end(self):
        from cluster_analysis.agent import language
        # A risk: low is good (top), high is bad (bottom); no better side: highest/lowest
        self.assertEqual([language.rank_words(p, "worse") for p in (3, 98, 76, 55)], ["top 3%", "bottom 2%", "bottom 24%", "normal (near the European baseline)"])
        self.assertEqual([language.rank_words(p, None) for p in (95, 3)], ["highest 5%", "lowest 3%"])
        risk = providers.card("condition", "ra", "Rheumatoid arthritis", level="high", value=98, higher="worse",
                              headline="You carry 172 risk alleles, which puts you near the 98th percentile.")
        r = tools.interpreted([risk])[0]
        self.assertTrue(r["rank"].startswith("bottom 2% of Europeans"))
        self.assertIn("in the bottom 2%", r["summary"])

    def test_unasked_ranks_are_refused(self):
        ctx = tools.new_context("P", share=True)
        ctx["question"] = "What could help me build muscle?"
        text = tools.call(ctx, "answer", {"summary": "Your lean mass is in the top 5% of Europeans.", "explanation": "E."})[0]
        self.assertIn("doesn't ask where the person ranks", text)
        text = tools.call(ctx, "answer", {"summary": "Lean mass sits at the 95th percentile.", "explanation": "E."})[0]
        self.assertIn("leave ranks out", text)

    def test_interpreted_results_say_top_or_bottom(self):
        card = providers.card("fitness", "grip", "Grip strength", level="lowered", value=19, higher="better",
                              headline="The genes put grip strength at the 19th percentile of Europeans.",
                              rows=[{"label": "Percentile", "value": 19}, {"label": "Variant", "value": "FOXP1 (rs17008201): 1 of 2 copies"}])
        r = tools.interpreted([card])[0]
        self.assertTrue(r["rank"].startswith("bottom 19% of Europeans"))
        self.assertIn("in the bottom 19%", r["summary"])
        self.assertNotIn("percentile", json.dumps(r).lower())
        self.assertEqual(len(r["details"]), 1)


class TestRiskLanguage(unittest.TestCase):
    """Answers speak in risk and evidence, never clinical advice (agent/language.py)."""

    def test_advice_is_caught(self):
        from cluster_analysis.agent import language
        for s in ("Tell your doctor or pharmacist before taking hydralazine.", "Do not smoke.", "Consider asking for a TSH test.",
                  "You should get tested.", "See a doctor if it persists.", "Ask your GP for a blood test.", "Start at 40 mg a day."):
            self.assertTrue(language.advice(s), s)
        for s in ("The CPIC guideline lists a lower starting dose for this group.", "Your risk is raised.",
                  "Tobacco smoking is a known cause of lung cancer.", "Levels are predicted to be higher."):
            self.assertFalse(language.advice(s), s)

    def test_an_advising_answer_is_sent_back(self):
        ctx = tools.new_context("P")
        text, err = tools.call(ctx, "answer", {"summary": "Your risk is a bit raised, so ask your doctor for a test.", "explanation": "x"})
        self.assertIn("clinical advice", text)
        self.assertIsNone(ctx["answer"])


class TestSession(unittest.TestCase):
    def test_follow_up_context_holds_nothing_from_the_screen(self):
        s = session.Session(person="P")
        s.turns.append({"question": "Which medicines?", "understood": {"reading": "You want medicines.", "plan": []},
                        "calls": [{"name": "my_medicines", "args": {}}], "cards": [CARD],
                        "written": [{"reading": "You are a TPMT intermediate metabolizer."}],
                        "answer": {"explanation": "Guidelines exist for some genes.", "followups": ["What about ibuprofen?"]}})
        ctx = s.context(share=False)
        self.assertIn("Which medicines?", ctx)
        self.assertIn("Guidelines exist for some genes.", ctx)
        self.assertIn("my_medicines", ctx)
        for leak in ("TPMT", "intermediate metabolizer", "azathioprine", "*1/*3A"):
            self.assertNotIn(leak, ctx)


if __name__ == "__main__":
    unittest.main()
