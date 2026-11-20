"""Token cost controls in Ask: billing-split usage (agent/cost.py), the lookup budget, the answer check that reports
everything at once and stops retrying, and programmatic tool calling on the API backend (converse.PTC)."""
import types
import unittest
from unittest import mock

from cluster_analysis.agent import converse, cost, tools

NS = types.SimpleNamespace


class TestCost(unittest.TestCase):
    def test_billing_split_and_price(self):
        u = cost.of("claude-sonnet-5-5", NS(input_tokens=1000, cache_read_input_tokens=10000, cache_creation_input_tokens=2000, output_tokens=500))
        self.assertEqual((u["input"], u["cache_read"], u["cache_write"], u["output"]), (1000, 10000, 2000, 500))
        # 1000*2 + 2000*2*1.25 + 10000*0.10 + 500*10, per million
        self.assertAlmostEqual(u["usd"], (2000 + 5000 + 1000 + 5000) / 1e6)
        both = cost.add(u, cost.of("haiku", {"input_tokens": 100, "output_tokens": 10}))
        self.assertEqual(both["input"], 1100)
        self.assertEqual(cost.total_in(both), 13100)
        self.assertEqual(cost.of("unknown-model", {"input_tokens": 5})["usd"], 0.0)


class TestBudget(unittest.TestCase):
    def test_lookups_stop_at_the_budget(self):
        ctx = tools.new_context("P", share=False)
        with mock.patch.object(tools, "t_resolve", lambda ctx, text, kind="any": {"candidates": []}), \
                mock.patch.dict(tools.TOOLS, {"resolve": (tools.PUBLIC, lambda ctx, text, kind="any": {"candidates": []}, *tools.TOOLS["resolve"][2:])}):
            for _ in range(tools.CALL_BUDGET):
                self.assertFalse(tools.call(ctx, "resolve", {"text": "x"})[1])
            text, err = tools.call(ctx, "resolve", {"text": "x"})
        self.assertTrue(err)
        self.assertIn("budget", text)
        # Views, understand and answer aren't lookups
        self.assertFalse(tools.call(ctx, "show_cluster", {"theme": "muscle"})[1])


class TestAnswerRetries(unittest.TestCase):
    def test_all_problems_at_once_then_accepted_without_them(self):
        ctx = tools.new_context("P")
        ctx["ledger"].ref("PMID:1", "PMID 1", "u")
        bad = {"summary": "Shown [PMID:9].", "explanation": "Shown in [PMID:1] and [PMID:2].", "highlights": ["X | OR 9 | PMID:1"]}
        first = tools.call(ctx, "answer", bad)[0]
        self.assertIn("PMID:2", first)
        self.assertIn("Highlights not accepted", first)  # both problems in one rejection
        tools.call(ctx, "answer", bad)
        self.assertIsNone(ctx["answer"])
        self.assertIn('"ok"', tools.call(ctx, "answer", bad)[0])  # the third try is accepted without what didn't hold
        a = ctx["answer"]
        self.assertNotIn("PMID:2", a["explanation"])
        self.assertNotIn("PMID:9", a["summary"])
        self.assertEqual(a["highlights"], [])
        self.assertEqual(set(a["refs"]), {"PMID:1"})

    def test_advice_is_never_accepted(self):
        ctx = tools.new_context("P")
        for _ in range(5):
            text, _ = tools.call(ctx, "answer", {"summary": "Ask your doctor for a test.", "explanation": "x"})
            self.assertIn("clinical advice", text)
        self.assertIsNone(ctx["answer"])


class TestAim(unittest.TestCase):
    """A strategies question (what works for me) must look outward before it is answered, and gets a larger budget."""

    def test_strategies_need_outward_research(self):
        ctx = tools.new_context("P")
        tools.call(ctx, "understand", {"reading": "r", "plan": ["p"], "aim": "strategies"})
        text = tools.call(ctx, "answer", {"summary": "S.", "explanation": "E."})[0]
        self.assertIn("look outward", text)
        stub = (tools.PUBLIC, lambda ctx, query, limit=8: {"papers": []}, *tools.TOOLS["search_papers"][2:])
        with mock.patch.dict(tools.TOOLS, {"search_papers": stub}):
            tools.call(ctx, "search_papers", {"query": "a"})
            tools.call(ctx, "search_papers", {"query": "b"})
        self.assertIn('"ok"', tools.call(ctx, "answer", {"summary": "S.", "explanation": "E.",
                                                         "links": ["training | none | none | no genotype study found"]})[0])

    def test_each_listed_strategy_must_be_researched(self):
        ctx = tools.new_context("P")
        tools.call(ctx, "understand", {"reading": "r", "plan": ["p"], "aim": "strategies",
                                       "strategies": ["intermittent fasting", "endurance training"]})
        stub = (tools.PUBLIC, lambda ctx, query, limit=8: {"papers": []}, *tools.TOOLS["search_papers"][2:])
        with mock.patch.dict(tools.TOOLS, {"search_papers": stub}):
            tools.call(ctx, "search_papers", {"query": "FTO AND endurance exercise"})
            tools.call(ctx, "search_papers", {"query": "FTO AND weight loss"})
            text = tools.call(ctx, "answer", {"summary": "S.", "explanation": "E."})[0]
            self.assertIn("intermittent fasting", text)
            self.assertNotIn("endurance training", text)
            tools.call(ctx, "search_papers", {"query": "MC4R AND fasting"})
        links = ["intermittent fasting | none | none | no trial by genotype", "endurance training | none | none | no trial by genotype"]
        self.assertIn('"ok"', tools.call(ctx, "answer", {"summary": "S.", "explanation": "E.", "links": links})[0])

    def test_areas_must_be_read_and_linked(self):
        ctx = tools.new_context("P")
        ctx["ledger"].ref("PMID:5", "PMID 5", "u")
        ctx["ledger"].genes.add("COL5A1")
        tools.call(ctx, "understand", {"reading": "r", "plan": ["p"], "aim": "explain", "areas": ["tendons", "regeneration"]})
        self.assertIn("haven't read them: tendons, regeneration", tools.call(ctx, "answer", {"summary": "S.", "explanation": "E."})[0])
        stub = (tools.PERSONAL, lambda ctx, theme, mechanism=None: {"shown_to_person": True}, *tools.TOOLS["my_cluster"][2:])
        with mock.patch.dict(tools.TOOLS, {"my_cluster": stub}):
            tools.call(ctx, "my_cluster", {"theme": "muscle", "mechanism": "tendons,regeneration"})
        text = tools.call(ctx, "answer", {"summary": "S.", "explanation": "E.", "links": ["tendons | COL5A1 | PMID:5 | fewer injuries"]})[0]
        self.assertIn("Links missing for: regeneration", text)
        ctx["rejections"] = 0
        ok = tools.call(ctx, "answer", {"summary": "S.", "explanation": "E.",
                                         "links": ["tendons | COL5A1, MADEUP1, CC | PMID:5, PMID:9 | fewer injuries", "regeneration | none | none | nothing found"]})
        self.assertIn('"ok"', ok[0])
        # What no tool returned is left out of the link (a genotype isn't a gene), the link stays
        self.assertEqual(ctx["answer"]["links"][0], {"node": "tendons", "genes": ["COL5A1"], "refs": ["PMID:5"], "finding": "fewer injuries",
                                                     "left_out": ["MADEUP1", "PMID:9"]})
        self.assertIn("PMID:5", ctx["answer"]["refs"])
        # Every call is in the trace, refusals with their reasons
        self.assertEqual([x["name"] for x in ctx["trace"]][:2], ["understand", "answer"])
        self.assertFalse(ctx["trace"][1]["ok"])
        self.assertTrue(ctx["trace"][-1]["ok"])

    def test_other_aims_need_no_research_and_keep_the_budget(self):
        ctx = tools.new_context("P")
        tools.call(ctx, "understand", {"reading": "r", "plan": ["p"], "aim": "risk"})
        self.assertEqual(tools.budget_of(ctx), tools.CALL_BUDGET)
        self.assertIn('"ok"', tools.call(ctx, "answer", {"summary": "S.", "explanation": "E."})[0])
        tools.call(ctx, "understand", {"reading": "r", "plan": ["p"], "aim": "strategies"})
        self.assertEqual(tools.budget_of(ctx), tools.DEEP_BUDGET)


def _msg(content, stop="tool_use", container=None):
    return NS(content=content, stop_reason=stop, container=NS(id=container) if container else None,
              usage=NS(input_tokens=100, cache_read_input_tokens=0, cache_creation_input_tokens=0, output_tokens=20))


class FakeClient:
    """Two responses: a script that calls gene, then a direct answer."""

    def __init__(self):
        self.requests = []
        self.messages = self
        self.replies = [
            _msg([NS(type="server_tool_use", id="srv1", name="code_execution", input={"code": "..."}),
                  NS(type="tool_use", id="tu1", name="gene", input={"symbol": "ACTN3"}, caller=NS(type=tools.CODE_EXECUTION, tool_id="srv1"))],
                 container="cont_1"),
            _msg([NS(type="tool_use", id="tu2", name="answer", input={"summary": "S.", "explanation": "E."}, caller=NS(type="direct"))]),
        ]

    def create(self, **kw):
        self.requests.append(dict(kw, messages=list(kw["messages"])))  # as sent: the loop appends to its list
        return self.replies.pop(0)


class TestProgrammaticCalls(unittest.TestCase):
    def test_schemas_mark_the_scripted_lookups(self):
        s = {x["name"]: x for x in tools.schemas(ptc=True)}
        self.assertEqual(s["code_execution"]["type"], tools.CODE_EXECUTION)
        self.assertEqual(s["gene"]["allowed_callers"], [tools.CODE_EXECUTION])
        for direct in ("answer", "understand", "my_medicine", "show_cluster", "drug"):
            self.assertNotIn("allowed_callers", s[direct])
        self.assertNotIn("code_execution", {x["name"] for x in tools.schemas()})

    def test_the_loop_runs_script_calls_and_keeps_the_container(self):
        fake = FakeClient()
        ctx = tools.new_context("P", share=False)
        with mock.patch("anthropic.Anthropic", lambda **k: fake), mock.patch.object(converse, "PTC", True), \
                mock.patch("cluster_analysis.agent.run.api_key", lambda: "k"), \
                mock.patch.object(tools.facts, "gene", lambda led, symbol, limit=8: {"gene": symbol}):
            usage = converse._engine_api("Q", ctx, None, lambda ev: None, None)
        self.assertNotIn("container", fake.requests[0])
        self.assertEqual(fake.requests[1]["container"], "cont_1")
        result = fake.requests[1]["messages"][-1]["content"]
        self.assertEqual([r["type"] for r in result], ["tool_result"])  # only tool results answer a script's call
        self.assertNotIn("is_error", result[0])
        self.assertEqual([(c["name"], c.get("via")) for c in ctx["calls"]], [("script", None), ("gene", "script"), ("answer", None)])
        self.assertIsNotNone(ctx["answer"])
        self.assertEqual(usage["input"], 200)
        self.assertIn("async functions inside code_execution", fake.requests[0]["system"])


if __name__ == "__main__":
    unittest.main()
