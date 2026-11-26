"""The Ask report (cluster_analysis/agent/report.py): a saved conversation becomes a PDF that holds the answer and the
whole chain: every tool with its letter logo and the databases it read, the cited sources, and old ordinal
percentiles in the explorer's words. A made-up conversation in a temporary folder; no model is called."""
import io
import os
import tempfile
import unittest
from unittest import mock

from cluster_analysis.agent import report, session as sess


def made_up_turn():
    return {"question": "Which training suits me?", "shared": False, "model": "test-model", "seconds": 12.5,
            "tokens": {"input": 1000, "cache_read": 0, "cache_write": 0, "output": 200, "usd": 0.01},
            "understood": {"reading": "You want training that fits your genes.", "aim": "strategies", "plan": ["read the muscle cluster"]},
            "trace": [{"name": "understand", "args": {"reading": "x"}, "ok": True, "note": "aim: strategies"},
                      {"name": "research_genotypes", "args": {"rsids": ["rs1815739"], "topic": "training"}, "ok": True, "note": "3 study sentences"},
                      {"name": "answer", "args": {}, "ok": False, "error": "Add links"},
                      {"name": "answer", "args": {}, "ok": True, "note": "accepted"}],
            "cards": [{"title": "Grip strength", "headline": "The genes put grip strength at the 45th percentile of Europeans.", "provider": "fitness"}],
            "answer": {"summary": "In trials, carriers responded more [PMID:1].", "explanation": "Detail.",
                       "highlights": [{"label": "Power", "value": "OR 0.71", "source": "PMID:1"}],
                       "links": [{"node": "Power", "genes": ["ACTN3"], "refs": ["PMID:1"], "finding": "stronger response"}],
                       "refs": {"PMID:1": {"label": "PMID 1: A trial", "url": "https://europepmc.org/article/MED/1"}},
                       "followups": ["What about recovery?"]},
            "views": [{"view": "cluster", "theme": "muscle", "auto": True}], "written": []}


class ReportTest(unittest.TestCase):
    def test_pdf_holds_the_chain(self):
        import pdfplumber
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sess, "DIR", d):
            s = sess.Session(person="PB")
            s.turns.append(made_up_turn())
            s.save()
            pdf = report.build(s.id)
            name = report.filename(s.id, 0)
        self.assertTrue(pdf.startswith(b"%PDF"))
        with pdfplumber.open(io.BytesIO(pdf)) as p:
            text = " ".join(page.extract_text() or "" for page in p.pages)
        for want in ("Which training suits me?", "SG", "Studies by genotype", "Europe PMC", "1000 Genomes",
                     "Sent back", "PMID:1", "What about recovery?", "Restricted mode on", "contains personal genetic results"):
            self.assertIn(want, text, want)
        self.assertIn("Bottom 45%", text)                  # the old "45th percentile" in the explorer's words
        self.assertNotIn("45th percentile", text)
        self.assertEqual(name, "Ask-PB-Which-training-suits-me.pdf")

    def test_follow_up_carries_what_came_before(self):
        """A follow-up's PDF holds the earlier questions it builds on, and a long sent-back message is cut, not broken."""
        import pdfplumber
        t2 = made_up_turn()
        t2["question"] = "And recovery?"
        t2["trace"][2]["error"] = "Highlights not accepted: " + "x " * 600     # longer than a table cell takes
        t2["answer"]["explanation"] = "**Recovery** first.\n\nThen more."
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sess, "DIR", d):
            s = sess.Session(person="PB")
            s.turns += [made_up_turn(), t2]
            s.save()
            pdf = report.build(s.id, 1)
            first = report.build(s.id, 0)
        with pdfplumber.open(io.BytesIO(pdf)) as p:
            text = " ".join(page.extract_text() or "" for page in p.pages)
        self.assertIn("Which training suits me?", text)
        self.assertIn("And recovery?", text)
        self.assertIn("A follow-up", text)
        self.assertNotIn("**", text)
        with pdfplumber.open(io.BytesIO(first)) as p:
            self.assertNotIn("And recovery?", " ".join(page.extract_text() or "" for page in p.pages))

    def test_ranked(self):
        self.assertEqual(report.ranked("at the 79th percentile of Europeans"), "in the Top 21% · higher of Europeans")
        self.assertEqual(report.ranked("the 3rd percentile"), "Bottom 3% · lower")


if __name__ == "__main__":
    unittest.main()
