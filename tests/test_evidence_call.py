# Run with: python -m unittest discover tests
import unittest

from cluster_analysis.evidence_call import evidence_call, text_direction

VEP = {"alleles": ["G", "A"], "eur_af": {"A": 0.3}, "allele_consequences": {"A": ["missense_variant"]}}


def ev(**sources):
    return {"genes": ["GENE"], "consequence": "missense_variant", "sources": sources}


class TestTextDirection(unittest.TestCase):
    def test_function_parts_only(self):
        # COMT Val158Met: the activity part decides; the disease part ("increase the tendency") doesn't
        self.assertEqual(text_direction(["associated with low enzyme activity; may increase the tendency to develop high blood pressure"]), -1)
        self.assertEqual(text_direction(["55% of wild type enzyme activity"]), -1)
        self.assertEqual(text_direction(["5.7-fold increase in catalytic efficiency"]), 1)
        self.assertEqual(text_direction(["Inflammatory bowel disease 17, protection against"]), 0)


class TestEvidenceCall(unittest.TestCase):
    def test_no_evidence_is_unknown(self):
        c = evidence_call("rs1", "AA", ev(), VEP)
        self.assertEqual((c["function"], c["basis"]), ("unknown", "none"))

    def test_curated_protein_effect_counts_copies_of_changed_allele(self):
        e = ev(uniprot={"protein_changes": ["p.Val1Met"], "functional": ["reduced enzyme activity"]})
        self.assertEqual(evidence_call("rs1", "GA", e, VEP)["function"], "LoF")
        self.assertEqual(evidence_call("rs1", "GA", e, VEP)["dose"], 1)
        self.assertEqual(evidence_call("rs1", "GG", e, VEP)["function"], "normal")

    def test_stop_only_when_the_carried_allele_is_one(self):
        rare_stop = {**VEP, "alleles": ["G", "A", "T"], "allele_consequences": {"A": ["missense_variant"], "T": ["stop_gained"]}}
        self.assertEqual(evidence_call("rs1", "GA", ev(), rare_stop)["basis"], "none")
        stop = {**VEP, "allele_consequences": {"A": ["stop_gained"]}}
        self.assertEqual(evidence_call("rs1", "AA", ev(), stop)["function"], "LoF")

    def test_expression_is_relative_to_the_common_genotype(self):
        # G (common, 70%) lowers expression, so A carriers are the more expressed ones
        e = ev(gtex={"effect_allele": "G", "own_gene": True, "n_tissues": 3, "top": [{"gene": "GENE", "tissue": "Brain", "nes": -0.5, "p": 1e-9}]})
        self.assertEqual(evidence_call("rs1", "AA", e, VEP)["function"], "GoF")
        self.assertEqual(evidence_call("rs1", "GG", e, VEP)["function"], "normal")

    def test_cpic_allele_function(self):
        vep = {"alleles": ["G", "A"], "eur_af": {"A": 0.15}, "allele_consequences": {}}
        c = evidence_call("rs4244285", "GA", ev(), vep)  # CYP2C19*2
        self.assertEqual((c["function"], c["basis"]), ("LoF", "cpic"))


if __name__ == "__main__":
    unittest.main()
