"""The gene pathway walks shipped with the app (cluster_analysis/lifecycle/lifecycles.json): built without anyone's DNA,
and complete enough for the introduction's alcohol-chain example (explorer/in.js, step 4)."""
import json
import re
import unittest

from cluster_analysis.lifecycle.lifecycle import LIFECYCLES

PERSONAL = {"person", "genotype", "rsid", "carried", "dose", "interpretation", "outcome", "basis", "evidence", "calls"}


class TestShippedLifecycles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(LIFECYCLES, encoding="utf-8") as f:
            cls.text = f.read()
        cls.data = json.loads(cls.text)

    def test_no_person_data(self):
        def walk(o, path):
            if isinstance(o, dict):
                for k, v in o.items():
                    # The builder leaves "person" null on every enzyme when no DNA file is given
                    if k in PERSONAL:
                        self.assertIsNone(v, f"{path}.{k} holds a person's data")
                    walk(v, f"{path}.{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{path}[{i}]")
        walk(self.data, "")
        self.assertIsNone(re.search(r"\brs\d+\b", self.text), "an rsid in the shipped walks")

    def test_alcohol_chain(self):
        by_gene = {lc["gene"]: lc for lc in self.data}
        for gene, molecule in (("ADH1B", "ethanol"), ("ALDH2", "acetaldehyde")):
            roles = by_gene[gene]["roles"]
            self.assertTrue(roles, gene)
            focal = [s for s in roles[0]["steps"] if s["section"] == "focal"]
            self.assertEqual(len(focal), 1, gene)
            # in.js reads the first molecule on each side of "x + NAD+ => y + NADH + H+"
            self.assertIn("=>", focal[0]["reaction"], gene)
            self.assertTrue(focal[0]["reaction"].startswith(molecule), (gene, focal[0]["reaction"]))
            self.assertIn(gene, [g["gene"] for g in focal[0]["genes"]])


if __name__ == "__main__":
    unittest.main()
