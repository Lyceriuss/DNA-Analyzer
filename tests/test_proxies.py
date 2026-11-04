# Run with: python -m unittest discover tests
import unittest

from src.proxy_handler import apply_proxies


class TestApoeProxy(unittest.TestCase):
    """rs429358 (APOE e4) is not on MyHeritage panels; it is estimated from rs769449 with rs4420638 as a check."""

    def run_proxy(self, rs769449, rs4420638):
        return apply_proxies({"rs769449": rs769449, "rs4420638": rs4420638})

    def test_marker_allele_means_e4(self):
        dna, est = self.run_proxy("GA", "AG")  # unsorted, as files often are
        self.assertEqual(dna["rs429358"], "CT")
        self.assertFalse(est["rs429358"]["uncertain"])

    def test_both_markers_clear_means_no_e4(self):
        dna, est = self.run_proxy("GG", "AA")
        self.assertEqual(dna["rs429358"], "TT")
        self.assertFalse(est["rs429358"]["uncertain"])

    def test_markers_disagree_is_uncertain(self):
        dna, est = self.run_proxy("GG", "AG")
        self.assertTrue(est["rs429358"]["uncertain"])

    def test_measured_snp_is_never_overwritten(self):
        dna, est = apply_proxies({"rs429358": "CC", "rs769449": "GG", "rs4420638": "AA"})
        self.assertEqual(dna["rs429358"], "CC")
        self.assertNotIn("rs429358", est)

    def test_unknown_proxy_genotype_is_not_guessed(self):
        dna, est = apply_proxies({"rs769449": "--"})
        self.assertNotIn("rs429358", dna)


class TestActn3Proxy(unittest.TestCase):
    def test_rs540874_maps_to_r577x(self):
        dna, _ = apply_proxies({"rs540874": "AA"})
        self.assertEqual(dna["rs1815739"], "TT")


if __name__ == "__main__":
    unittest.main()
