# Run with: python -m unittest discover tests
import unittest

from src.impute import calibrate, carries_minor, freq_band, harmonize, is_male, person_of, tier


class TestConfidence(unittest.TestCase):
    def test_minor_allele(self):
        self.assertTrue(carries_minor(1, 0.1))
        self.assertFalse(carries_minor(0, 0.1))
        self.assertFalse(carries_minor(2, 0.9))  # alt is the common allele here: AA-alt means no minor allele
        self.assertTrue(carries_minor(1, 0.9))

    def test_bands(self):
        self.assertEqual(freq_band(0.3), "common")
        self.assertEqual(freq_band(0.97), "uncommon")
        self.assertEqual(freq_band(0.004), "rare")
        self.assertEqual(freq_band(None), "unknown")

    def test_tiers_follow_measured_accuracy(self):
        calls = [(1, 1, 0.999, 0.3)] * 990 + [(0, 1, 0.999, 0.3)] * 10      # common carrier calls: 99% right
        calls += [(1, 1, 0.999, 0.03)] * 93 + [(0, 1, 0.999, 0.03)] * 7 + [(0, 0, 0.999, 0.03)] * 500
        calls += [(1, 0, 0.999, 0.003)] * 60 + [(1, 1, 0.999, 0.003)] * 40   # rare: most real carriers missed
        cal = calibrate(calls, 0.9)
        self.assertEqual(tier(cal, 0.3, 0.999, 1), "high")
        self.assertEqual(tier(cal, 0.03, 0.999, 1), "medium")
        self.assertEqual(tier(cal, 0.03, 0.999, 0), "not_excluded")  # 93 real carriers: too few to trust
        self.assertEqual(tier(cal, 0.003, 0.999, 0), "not_excluded")
        self.assertEqual(tier(cal, 0.003, 0.95, 1), "untested")
        self.assertEqual(tier(None, 0.3, 0.999, 1), "uncalibrated")


class TestHarmonize(unittest.TestCase):
    def test_forward_strand(self):
        self.assertEqual(harmonize("AG", "A", "G"), (0, 1, False))
        self.assertEqual(harmonize("GA", "A", "G"), (1, 0, False))
        self.assertEqual(harmonize("GG", "A", "G"), (1, 1, False))

    def test_complement_fallback(self):
        self.assertEqual(harmonize("TC", "A", "G"), (0, 1, True))

    def test_ambiguous_site_is_never_flipped(self):
        self.assertEqual(harmonize("AA", "A", "T"), (0, 0, False))
        self.assertIsNone(harmonize("GG", "A", "T"))

    def test_mismatch(self):
        self.assertIsNone(harmonize("AC", "A", "G"))


class TestHelpers(unittest.TestCase):
    def test_person(self):
        self.assertEqual(person_of("data/input/MyHeritage_raw_dna_data_XY.csv"), "XY")

    def test_sex_from_x(self):
        hom = [(5_000_000 + i, "rs", "AA") for i in range(200)]
        self.assertTrue(is_male(hom))
        self.assertFalse(is_male(hom[:150] + [(6_000_000 + i, "rs", "AG") for i in range(50)]))
        self.assertTrue(is_male(hom + [(100, "rs", "AG")]))  # PAR heterozygotes are fine


if __name__ == "__main__":
    unittest.main()
