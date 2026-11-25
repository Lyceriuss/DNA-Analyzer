"""The prediction engine: effect sizes from the GWAS Catalog, strand alignment, and where parents and child sit on a
trait's genetic score. No reference file or DNA file is read."""
import math
import unittest

from cluster_analysis.inheritance import predict as pr


def model(variants):
    return {"id": "T", "trait": "t", "variants": variants}


def v(rsid, freq, w, allele="A", ref="G", alt="A"):
    return {"rsid": rsid, "freq": freq, "w": w, "allele": allele, "ref": ref, "alt": alt, "gene": "", "p": 1e-10}


def call(gt, tier="measured"):
    return {"genotype": gt, "tier": tier}


class TestEffect(unittest.TestCase):
    def test_beta_and_odds_ratio(self):
        self.assertEqual(pr.effect(0.03, "[0.02-0.04] unit increase"), (0.03, "beta"))
        self.assertEqual(pr.effect(0.03, "[0.02-0.04] unit decrease"), (-0.03, "beta"))
        w, kind = pr.effect(1.2, "[1.1-1.3]")
        self.assertAlmostEqual(w, math.log(1.2))
        self.assertEqual(kind, "odds ratio")
        self.assertEqual(pr.effect(0.8, "[0.7-0.9]"), (None, None))   # neither signed nor an odds ratio above 1

    def test_align(self):
        self.assertEqual(pr.align("A", ("G", "A", 0.3)), ("A", 0.3, "G", "A"))
        self.assertEqual(pr.align("T", ("G", "A", 0.3)), ("A", 0.3, "G", "A"))          # the other strand
        self.assertEqual(pr.align("G", ("G", "A", 0.3)), ("G", 0.7, "G", "A"))
        self.assertIsNone(pr.align("A", ("A", "T", 0.3)))                             # palindromic, no frequency
        self.assertEqual(pr.align("T", ("A", "T", 0.2), raf=0.21)[0], "T")            # the frequency settles it
        self.assertIsNone(pr.align("T", ("A", "T", 0.45), raf=0.45))                  # too close to one half


class TestTerms(unittest.TestCase):
    def test_term_keys_match_across_spellings(self):
        # The GWAS Catalog writes URIs, EFO's file writes efo:EFO_... and MONDO:...
        self.assertEqual(pr.term_key("http://www.ebi.ac.uk/efo/EFO_0011015"), pr.term_key("efo:EFO_0011015"))
        self.assertEqual(pr.term_key("http://purl.obolibrary.org/obo/MONDO_0005146"), pr.term_key("MONDO:0005146"))


class TestPredict(unittest.TestCase):
    def test_child_sits_between_its_parents(self):
        vs = [v(f"rs{i}", 0.5, 1.0) for i in range(20)]
        xx = {f"rs{i}": call("AA") for i in range(20)}   # two effect copies everywhere: far above average
        xy = {f"rs{i}": call("GG") for i in range(20)}   # none: far below
        r = pr.predict(model(vs), xx, xy)
        self.assertGreater(r["XX_pct"], 99)
        self.assertLess(r["XY_pct"], 1)
        self.assertAlmostEqual(r["child_z"], 0.0, places=6)   # every child gets one copy at every variant
        self.assertAlmostEqual(r["child_sd"], 0.0, places=6)  # and nothing is left to chance
        self.assertEqual(r["used_both"], 20)

    def test_two_heterozygous_parents_spread_like_the_population(self):
        # f = 0.5 and both parents AG: each child is a fresh draw, so its spread equals the population's
        vs = [v(f"rs{i}", 0.5, 1.0) for i in range(10)]
        xx = {f"rs{i}": call("AG") for i in range(10)}
        r = pr.predict(model(vs), xx, dict(xx))
        self.assertAlmostEqual(r["child_z"], 0.0, places=6)
        self.assertAlmostEqual(r["child_sd"], 1.0, places=6)
        self.assertLess(r["child_lo"], 15)
        self.assertGreater(r["child_hi"], 85)

    def test_full_range(self):
        # Every gene settled: the child can land in one place only
        vs = [v(f"rs{i}", 0.5, 1.0) for i in range(10)]
        r = pr.predict(model(vs), {f"rs{i}": call("AA") for i in range(10)}, {f"rs{i}": call("GG") for i in range(10)})
        self.assertAlmostEqual(r["child_min"], r["child_max"])
        self.assertAlmostEqual(r["child_min"], r["child_pct"])
        # Coin tosses: the furthest possible places lie beyond the range most children land in
        both = {f"rs{i}": call("AG") for i in range(10)}
        r = pr.predict(model(vs), both, dict(both))
        self.assertLess(r["child_min"], r["child_lo"])
        self.assertGreater(r["child_max"], r["child_hi"])

    def test_person_scores(self):
        m = {**model([v(f"rs{i}", 0.5, 1.0) for i in range(10)]), "category": "c", "study": "s", "pmid": "1", "author": "a",
             "year": "2020", "n": 1, "kind": "beta", "sample": "10,000 European ancestry women"}
        rows = pr.person_scores([m], {f"rs{i}": call("AA") for i in range(10)}, sex="female")
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]["pct"], 99)
        # A trait studied in women only is left out for a man
        self.assertEqual(pr.person_scores([m], {f"rs{i}": call("AA") for i in range(10)}, sex="male"), [])

    def test_missing_call_counts_as_average(self):
        vs = [v("rs1", 0.2, 1.0)]
        r = pr.predict(model(vs), {}, {"rs1": call("GG", tier="not_excluded")})
        self.assertEqual(r["used_XX"], 0)
        self.assertEqual(r["used_XY"], 0)
        self.assertAlmostEqual(r["child_z"], 0.0, places=6)

    def test_unusable_genotypes(self):
        self.assertIsNone(pr.copies(call("AA", tier="low"), v("rs1", 0.2, 1.0)))
        self.assertIsNone(pr.copies(call("CT"), v("rs1", 0.2, 1.0)))   # alleles that aren't the site's
        self.assertEqual(pr.copies(call("AG"), v("rs1", 0.2, 1.0)), 1)

    def test_predictions_need_enough_shared_variants(self):
        vs = [v(f"rs{i}", 0.3, 0.5) for i in range(10)]
        both = {f"rs{i}": call("AG") for i in range(3)}
        self.assertEqual(pr.predictions([model(vs)], both, both), [])
        both = {f"rs{i}": call("AG") for i in range(8)}
        self.assertEqual(len(pr.predictions([{**model(vs), "category": "c", "study": "s", "pmid": "1", "author": "a",
                                               "year": "2020", "n": 1, "kind": "beta"}], both, both)), 1)


if __name__ == "__main__":
    unittest.main()
