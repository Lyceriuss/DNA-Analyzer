"""The research databases are listed once, in cluster_analysis/explorer/sources.json: the Sources tab and the
introduction's count are built from it. These tests keep it, docs/architecture/sources.md and genome/references.json
in step."""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read() if parts[-1].endswith(".md") else json.load(f)


class TestSourcesCatalog(unittest.TestCase):
    def setUp(self):
        self.cat = load("cluster_analysis", "explorer", "sources.json")
        self.refs = {r["name"]: r for r in load("genome", "references.json")["references"]}
        self.doc = load("docs", "architecture", "sources.md")

    def test_every_database_is_documented(self):
        for d in self.cat["databases"]:
            self.assertIn(f"[{d['name']}]({d['url']})", self.doc, f"{d['name']} is missing from sources.md")
        self.assertIn(f"The {len(self.cat['databases'])} research databases", self.doc)

    def test_refs_exist(self):
        for item in self.cat["databases"] + self.cat["tools"]:
            for r in item.get("refs", []):
                self.assertIn(r, self.refs, f"{item['name']}: {r} is not in references.json")

    def test_every_downloaded_reference_has_a_source(self):
        used = {r for item in self.cat["databases"] + self.cat["tools"] for r in item.get("refs", [])}
        for name, r in self.refs.items():
            if r["tier"] in ("impute", "analyse") and r.get("kind") != "built":
                self.assertIn(name, used, f"{name} (references.json) is not credited to a database or tool")

    def test_every_database_in_exactly_one_group(self):
        grouped = [i for g in self.cat["groups"] for i in g["ids"]]
        self.assertEqual(sorted(grouped), sorted(d["id"] for d in self.cat["databases"]))
        for g in self.cat["groups"]:
            self.assertTrue(g.get("sv"), f"{g['id']} lacks Swedish")

    def test_take_use_and_logo(self):
        logos = os.path.join(ROOT, "cluster_analysis", "explorer", "runtime", "logos")
        for d in self.cat["databases"]:
            for k in ("takes", "use", "takes_sv", "use_sv"):
                self.assertTrue(d.get(k), f"{d['name']} has no {k}")
            if d.get("logo"):
                self.assertTrue(os.path.exists(os.path.join(logos, d["logo"])), f"{d['logo']} is missing")
                self.assertTrue(d.get("logo_from"), f"{d['name']}: where the logo came from")

    def test_every_text_has_swedish(self):
        for item in self.cat["databases"] + self.cat["tools"] + self.cat["glossary"]:
            self.assertTrue(item.get("sv"), f"{item.get('name') or item.get('term')} has no Swedish")


if __name__ == "__main__":
    unittest.main()
