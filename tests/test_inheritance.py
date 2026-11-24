"""Inheritance: the child's odds from two parents' copies, X-linked inheritance, the modes' outcomes, which ClinVar
conditions a pathogenic classification counts for, and the confidence of a parent's call. No DNA file is read."""
import unittest

from cluster_analysis.inheritance import inheritance as ih


class TestMendel(unittest.TestCase):
    def test_two_carriers(self):
        # AG x AG: 25% AA, 50% AG, 25% GG
        self.assertEqual(ih.odds(1, 1)["child"], [0.25, 0.5, 0.25])

    def test_homozygous_parent_always_passes(self):
        self.assertEqual(ih.odds(2, 0)["child"], [0.0, 1.0, 0.0])
        self.assertEqual(ih.odds(2, 2)["child"], [0.0, 0.0, 1.0])

    def test_unreadable_parent_gives_no_odds(self):
        self.assertIsNone(ih.odds(1, None)["child"])

    def test_x_linked(self):
        # A carrier mother and a father without the variant: half her sons get it, half her daughters carry it
        o = ih.odds(1, 0, on_x=True)
        self.assertEqual(o["son"], [0.5, 0.5])
        self.assertEqual(o["daughter"], [0.5, 0.5, 0.0])
        # A father with it on his only X gives it to every daughter and to no son
        o = ih.odds(0, 1, on_x=True)
        self.assertEqual(o["son"], [1.0, 0.0])
        self.assertEqual(o["daughter"], [0.0, 1.0, 0.0])

    def test_outcomes(self):
        o = ih.odds(1, 1)
        self.assertEqual(ih.outcome("AR", o), {"child": {"affected": 0.25, "carrier": 0.5}})
        self.assertEqual(ih.outcome("AD", o), {"child": {"affected": 0.75}})
        x = ih.outcome("XLR", ih.odds(1, 0, on_x=True))
        self.assertEqual(x["son"]["affected"], 0.5)
        self.assertEqual(x["daughter"], {"affected": 0.0, "carrier": 0.5})


class TestCalls(unittest.TestCase):
    def test_copies_on_a_mans_x(self):
        # A man's X outside the shared regions is written as a pair but holds one copy
        self.assertEqual(ih.copies_of("AA", ["A"], haploid=True), 1)
        self.assertEqual(ih.copies_of("AA", ["A"]), 2)
        self.assertEqual(ih.copies_of("GG", ["A"], haploid=True), 0)

    def test_on_x_outside_par(self):
        par = ((10001, 2781479), (155701383, 156030895))
        self.assertTrue(ih.on_x("X", 50_000_000, par))
        self.assertFalse(ih.on_x("X", 2_000_000, par))
        self.assertFalse(ih.on_x("7", 50_000_000, par))

    def test_chip_accuracy_by_frequency(self):
        common = {"tier": "measured", "af": 0.3, "gp": None}
        very_rare = {"tier": "measured", "af": 0.000001, "gp": None}
        rare = {"tier": "measured", "af": 0.001, "gp": None}
        self.assertEqual(ih.accuracy(common, True, None, None)[0], 0.99)
        self.assertEqual(ih.accuracy(very_rare, True, None, None)[0], 0.16)
        self.assertIsNone(ih.accuracy(rare, True, None, None)[0])
        # Not carrying a rare variant is still read with the chip's common-variant accuracy
        self.assertEqual(ih.accuracy(very_rare, False, None, None)[0], 0.99)

    def test_imputed_accuracy_from_the_persons_check(self):
        cal = {"cells": {"common|0.99|carrier": {"n": 1000, "right": 990, "rate": 0.99}}}
        call = {"tier": "high", "af": 0.3, "gp": 0.995}
        self.assertEqual(ih.accuracy(call, True, cal, None)[0], 0.99)
        self.assertIsNone(ih.accuracy({**call, "gp": 0.91}, True, cal, None)[0])

    def test_unusable_call(self):
        r = ih.read_parent({"genotype": "GG", "tier": "not_excluded", "af": 0.05, "gp": 0.95}, ["A"], False, None)
        self.assertIsNone(r["copies"])


class TestConditions(unittest.TestCase):
    def test_main_conditions_drop_single_gene_wide_listings(self):
        # C282Y: 30 pathogenic submissions for hemochromatosis type 1, one lab's gene-wide list names Alzheimer disease
        entries = [("Hemochromatosis type 1", ["MedGen:C3469186", "OMIM:235200"]),
                   ("Alzheimer disease type 1", ["MedGen:C1863052", "OMIM:104300"]),
                   ("not provided", ["MedGen:C3661900"])]
        counts = {"C3469186": 30, "C1863052": 1, "C3661900": 7}
        kept = ih.main_conditions(entries, counts)
        self.assertEqual([e[0] for e in kept], ["Hemochromatosis type 1"])

    def test_main_conditions_keep_equals(self):
        entries = [("A", ["MedGen:C0000001"]), ("B", ["MedGen:C0000002"])]
        self.assertEqual(len(ih.main_conditions(entries, {"C0000001": 1, "C0000002": 1})), 2)

    def test_review_filter(self):
        self.assertIsNone(ih.REVIEWED.search("no_assertion_criteria_provided"))
        self.assertIsNotNone(ih.REVIEWED.search("criteria_provided,_single_submitter"))
        self.assertIsNotNone(ih.REVIEWED.search("reviewed_by_expert_panel"))


if __name__ == "__main__":
    unittest.main()
