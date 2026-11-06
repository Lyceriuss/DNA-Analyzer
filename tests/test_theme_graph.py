# Run with: python -m unittest discover tests
import unittest

from cluster_analysis.theme_graph import clinvar_copies, in_regions


class TestClinvarCopies(unittest.TestCase):
    def test_other_change_at_same_position_is_not_counted(self):
        # APC rs2229992: TC carries the benign T>C, not the pathogenic T>G
        self.assertEqual(clinvar_copies("TC", "T", ["G"]), 0)
        self.assertEqual(clinvar_copies("TC", "T", ["C"]), 1)
        self.assertEqual(clinvar_copies("AA", "G", ["T"]), 0)  # EXT1 rs11546829: G>A benign, G>T pathogenic

    def test_never_flips_strand(self):
        self.assertEqual(clinvar_copies("TC", "A", ["G"]), 0)  # both sides are forward strand

    def test_multi_allelic(self):
        self.assertEqual(clinvar_copies("GT", "G", ["T", "C"]), 1)


class TestRegions(unittest.TestCase):
    def test_lookup(self):
        genes_at = in_regions({"1": [(100, 2000, "LONG"), (500, 600, "A"), (550, 700, "B")]})
        self.assertEqual(sorted(genes_at("1", 560)), ["A", "B", "LONG"])
        self.assertEqual(genes_at("1", 1500), ["LONG"])
        self.assertEqual(genes_at("1", 50), [])
        self.assertEqual(genes_at("2", 560), ())


if __name__ == "__main__":
    unittest.main()
