"""The quick Ask pipeline (cluster_analysis/agent: terms, providers, quick): matching without a model, the kind of
question, the verdict's order (what can't be known first), and the privacy rule that a study search is only ever about
what the question named."""
import unittest
from unittest import mock

from cluster_analysis.agent import quick, terms


def match(q):
    return terms.match(q, search=False)


class TestMatch(unittest.TestCase):
    def test_domains_and_names(self):
        ids = lambda q: {(i["type"], i["id"]) for i in match(q) if i["score"] >= 1.5}
        self.assertIn(("domain", "drug"), ids("What medicine should I be careful with taking?"))
        self.assertIn(("theme", "muscle"), ids("What workouts will work the best for me?"))
        self.assertIn(("nutrient", "vitamin_d"), ids("Should I take vitamin D?"))
        self.assertIn(("gene", "ACTN3"), ids("How does ACTN3 affect me?"))

    def test_drugs_need_their_name(self):
        # "vitamin D" is a trade name somewhere, but not a drug's own name in the question
        self.assertFalse([i for i in match("Should I take vitamin D?") if i["type"] == "drug" and i["id"] == "folic acid"])

    def test_partial_words(self):
        self.assertTrue([i for i in match("Do I have a genetic propensity for thyroid problems?") if i["type"] == "lab"])

    def test_condition_search_takes_the_phrase(self):
        seen = []

        def fake(text, limit=8):
            seen.append(text)
            return [{"id": "MONDO_0005148", "name": "type 2 diabetes mellitus"}, {"id": "MONDO_X", "name": "monogenic diabetes"}]
        with mock.patch.object(terms, "ot_diseases", fake):
            m = terms.match("Am I at risk of type 2 diabetes?")
        self.assertEqual(seen[0], "type 2 diabetes")
        self.assertEqual(m[0]["label"], "type 2 diabetes mellitus")


class TestRoute(unittest.TestCase):
    """The model's reading of the question (agent/route.py): only what exists in the explorer is kept."""

    def test_keeps_only_catalogue_ids(self):
        from cluster_analysis.agent import route
        intent = {"kind": "action", "clusters": ["muscle", "made_up"], "mechanisms": [{"cluster": "muscle", "id": "fast"}, {"cluster": "muscle", "id": "nope"}],
                  "cancer": [], "lab": [], "nutrient": ["vitamin_d", "unicorn"], "fitness": [], "domains": ["drug", "astrology"],
                  "drugs": [], "genes": [], "conditions": [], "terms": ["training"], "unknown": ["mortality"]}
        items = route.to_items(intent)
        got = {(i["type"], i["id"]) for i in items}
        self.assertIn(("theme", "muscle"), got)
        self.assertIn(("theme", "fast"), got)
        self.assertIn(("nutrient", "vitamin_d"), got)
        self.assertIn(("domain", "drug"), got)
        self.assertFalse({("theme", "made_up"), ("theme", "nope"), ("nutrient", "unicorn"), ("domain", "astrology")} & got)

    def test_without_a_model_nothing_is_answered(self):
        """No rule-based fallback: without the model there is no answer, and the rules never add their own matches."""
        from cluster_analysis.agent import route, run
        with mock.patch.object(run, "backend", lambda: None):
            with self.assertRaises(route.NotUnderstood):
                route.items("What workouts will work best for me?")
        intent = {"kind": "action", "reading": "r", "plan": [], "clusters": [], "mechanisms": [], "cancer": [], "lab": [], "nutrient": [],
                  "fitness": [], "domains": ["drug"], "drugs": [], "genes": [], "conditions": [], "terms": [], "unknown": []}
        with mock.patch.object(run, "backend", lambda: "claude-code"), \
                mock.patch.object(route, "understand", lambda q: (intent, {"input": 0, "output": 0})):
            items, *_ = route.items("What is my response to paracetamol and to training?")
        self.assertEqual({i["type"] for i in items}, {"domain"})  # "training" adds nothing the model didn't choose


class TestCategories(unittest.TestCase):
    """Readings per category (agent/categories.py): whole domains are written, the person's category is picked here."""

    def test_cpic_names(self):
        from cluster_analysis.agent import categories as c
        self.assertEqual(c.cpic_result("NAT2", "Slow acetylator"), "Poor Metabolizer")
        self.assertEqual(c.cpic_result("CYP2B6", "Intermediate metaboliser"), "Intermediate Metabolizer")
        self.assertEqual(c.cpic_result("CYP2C9", "Normal metaboliser (activity score 2)"), "2.0")
        self.assertEqual(c.cpic_result("CYP3A5", "Poor metaboliser (non-expresser, the usual type in Europeans)"), "Poor Metabolizer")

    def test_a_domain_is_written_whole(self):
        """ensure() sends every category of the domain, so the choice of categories says nothing about a person."""
        from cluster_analysis.agent import categories as c
        sent = []
        uni = {f"score|cancer|x:{b}|{b}": {"what": b} for b in c.BANDS}
        with mock.patch.object(c, "cached", lambda k: None), \
                mock.patch.object(c, "_batch", lambda items: sent.extend(k for k, _ in items) or {"input": 0, "output": 0}):
            c.ensure(universe=uni)
        self.assertEqual(sorted(sent), sorted(uni))

    def test_key_of_reads_the_persons_own_result(self):
        from cluster_analysis.agent import categories as c, providers
        card = {"provider": "medicines", "gene": "NAT2", "level": "differs", "id": "NAT2", "title": "NAT2"}
        with mock.patch.object(providers, "rows", lambda name, person: [{"gene": "NAT2", "phenotype": "Slow acetylator"}]):
            self.assertEqual(c.key_of(card, "P"), "med|NAT2|Poor Metabolizer")
        self.assertEqual(c.key_of({"provider": "cancer", "id": "lung:pgs1", "level": "high", "title": "Lung"}, "P"), "score|cancer|lung:pgs1|high")


class TestKind(unittest.TestCase):
    def test_kinds_and_unknowns(self):
        k, u = terms.kind("Which cancer will I most likely die from?", [])
        self.assertEqual(k[0], "rank")
        self.assertEqual([x["id"] for x in u], ["mortality"])
        self.assertEqual(terms.kind("What medicine should I be careful with?", [])[0][0], "action")
        self.assertEqual(terms.kind("Do I have a propensity for migraine?", [])[0][0], "propensity")


def c(provider, title, level, value, higher="worse"):
    return {"provider": provider, "title": title, "level": level, "value": value, "higher": higher, "headline": f"{title} headline",
            "id": title, "rows": [], "known": [], "unknown": [], "links": []}


class TestVerdict(unittest.TestCase):
    def test_unknown_first_then_ranking(self):
        cards = [c("cancer", "Lung cancer", "high", 88), c("cancer", "Kidney cancer", "typical", 34), c("cancer", "Skin", "raised", 80)]
        v = quick.verdict(["rank"], [{"id": "mortality", "text": "Mortality is unknown."}], cards)
        self.assertEqual(v[0], "Mortality is unknown.")
        self.assertIn("Lung cancer (88th percentile)", v[1])
        self.assertIn("Kidney cancer (34th percentile)", v[2])

    def test_scores_by_side(self):
        cards = [c("lab", "LDL cholesterol", "high", 95), c("lab", "HDL cholesterol", "high", 91, "better"), c("lab", "TSH", "typical", 50)]
        v = " | ".join(quick.verdict(["propensity"], [], cards))
        self.assertIn("unfavourable side: LDL cholesterol (95th)", v)
        self.assertIn("favourable side: HDL cholesterol (91st)", v)
        self.assertIn("1 other score is in the usual range", v)


class TestPrivacy(unittest.TestCase):
    def test_no_study_search_from_the_persons_results(self):
        """Asked about medicines in general, the cards come from the person's results: none may carry a search topic."""
        from cluster_analysis.agent import providers
        guid = [{"drug": "azathioprine", "genes": "TPMT", "status": "differs", "grade": "A", "kind": "guideline", "source": "CPIC",
                 "recs": '[{"recommendation": "Start low."}]', "types": "TPMT *1/*3A", "summary": ""}]
        genes = [{"gene": "TPMT", "alleles": "*1/*3A", "phenotype": "Intermediate metabolizer", "typical": False, "note": ""}]
        with mock.patch.object(providers, "rows", lambda name, person: guid if name == "med_guidance" else genes if name == "med_genes" else []):
            general = providers.medicines("P")
            named = providers.medicines("P", ids={"azathioprine"})
        self.assertTrue(general and all(x["topic"] is None for x in general))
        self.assertEqual(named[0]["topic"], "azathioprine")


class TestFindings(unittest.TestCase):
    """Study sentences that name the person's own genotype group (agent/morsels.py)."""

    def test_labels_include_protein_letters(self):
        from cluster_analysis.agent import morsels
        lab = morsels.labels("TT", "C", "T", "R/*")      # ACTN3 R577X: C is R, T is the stop X
        self.assertTrue({"TT", "XX", "X allele", "T allele"} <= lab)
        self.assertNotIn("RR", lab)
        self.assertIn("RX", morsels.labels("CT", "C", "T", "R/*"))

    def test_apply_keeps_only_the_persons_group(self):
        from cluster_analysis.agent import morsels
        f = [{"sentence": "XX homozygotes gained 20% more strength.", "labels": ["XX"], "numbers": ["20%"], "type": "meta-analysis", "year": "2020"},
             {"sentence": "RR carriers sprinted faster.", "labels": ["RR"], "numbers": [], "type": "journal article", "year": "2020"}]
        got = morsels.apply(f, "TT", "C", "T", "R/*")
        self.assertEqual([m["sentence"] for m in got], ["XX homozygotes gained 20% more strength."])

    def test_frequency_and_other_genes_are_not_findings(self):
        from cluster_analysis.agent import morsels
        papers = [{"pmid": "1", "title": "ACTN3 and training", "year": "2024", "cited": 0, "types": ["journal article"], "abstract":
                   "The genotype distribution was RR 52.6%, RX 30.3% and XX 17.1%. "
                   "However, lower strength values were observed in the GG genotype of IL-6 compared with CC carriers. "
                   "Athletes with the XX genotype had 15% lower sprint power after training than RR athletes."}]
        with mock.patch.object(morsels.evidence, "search", lambda *a, **k: papers):
            got = morsels.for_variant("rs1815739", "ACTN3")
        self.assertEqual([m["sentence"][:18] for m in got], ["Athletes with the "])


if __name__ == "__main__":
    unittest.main()
