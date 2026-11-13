# Run with: python -m unittest discover tests
import unittest

from cluster_analysis.library.normalizer import resolve_genotype, normalize_variant_keys


class TestResolveGenotype(unittest.TestCase):
    def test_heterozygote_matches_unsorted_db_key(self):
        # rs1801133 lists only "GA" in snp_traits.json; users report "GA" or "AG"
        variants = normalize_variant_keys({"GG": "optimal", "GA": "reduced", "AA": "low"})
        self.assertEqual(resolve_genotype("GA", variants), ("AG", False))
        self.assertEqual(resolve_genotype("AG", variants), ("AG", False))

    def test_strand_flip(self):
        variants = normalize_variant_keys({"CC": "", "CT": "", "TT": ""})
        self.assertEqual(resolve_genotype("AG", variants), ("CT", True))
        self.assertEqual(resolve_genotype("GG", variants), ("CC", True))

    def test_no_match(self):
        self.assertEqual(resolve_genotype("AT", {"GG": "", "GT": ""}), (None, False))
        self.assertEqual(resolve_genotype("", {"GG": ""}), (None, False))

    def test_normalize_keeps_values(self):
        self.assertEqual(normalize_variant_keys({"TC": 6, "CC": 9}), {"CT": 6, "CC": 9})


if __name__ == "__main__":
    unittest.main()
