"""Lite mode (genome/lite.py): the measured file's name, and drug genes whose common variant a chip doesn't read."""
import unittest

from cluster_analysis.medicines import medicines
from genome.loader import person_label

FREQ = {"rs4244285": {"ref": "G", "alt": "A", "EUR": 0.145, "AFR": 0.17, "AMR": 0.10, "EAS": 0.31, "SAS": 0.36},
        "rs28399504": {"ref": "A", "alt": "G", "EUR": 0.001, "AFR": 0.0, "AMR": 0.003, "EAS": 0.001, "SAS": 0.0}}


class TestLite(unittest.TestCase):
    def test_person_label(self):
        self.assertEqual(person_label("x/MyHeritage_raw_dna_data_P1.measured.csv"), "P1")
        self.assertEqual(person_label("MyHeritage_raw_dna_data_P1.imputed.csv"), "P1")

    def test_common_unread_allele_is_not_called_normal(self):
        # *2 (no function, 15% of Europeans) unread: the gene can't be called; *4 (rare) unread: no reason to stop
        got = medicines.unread_common("CYP2C19", ["rs4244285", "rs28399504"], FREQ)
        self.assertEqual([(a, rs) for a, rs, _, _ in got], [("*2", "rs4244285")])
        self.assertEqual(medicines.unread_common("CYP2C19", ["rs28399504"], FREQ), [])
        self.assertEqual(medicines.unread_common("CYP2C19", [], FREQ), [])


if __name__ == "__main__":
    unittest.main()
