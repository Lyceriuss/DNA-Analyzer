# Run with: python -m unittest discover tests
import unittest

from src.normalizer import resolve_genotype, normalize_variant_keys
from src.report_engine import personalize_genotype


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


class TestPersonalizeGenotype(unittest.TestCase):
    def test_rewrites_self_reference(self):
        text = "Your AG genotype indicates reduced enzyme activity."
        self.assertEqual(personalize_genotype(text, "GG"), "Your GG genotype indicates reduced enzyme activity.")

    def test_rewrites_label_in_parentheses(self):
        self.assertEqual(personalize_genotype("You carry the 'Empath' variant (GG).", "AG"),
                         "You carry the 'Empath' variant (AG).")

    def test_swedish(self):
        self.assertEqual(personalize_genotype("Din AG-genotyp indikerar", "GG"), "Din GG-genotyp indikerar")

    def test_leaves_other_genes_alone(self):
        text = "In a high-power athlete (like your ACE GG profile), and the 'AA' baseline."
        self.assertEqual(personalize_genotype(text, "TT"), text)


if __name__ == "__main__":
    unittest.main()
