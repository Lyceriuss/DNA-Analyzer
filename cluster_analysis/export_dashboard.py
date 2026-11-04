# cluster_analysis/export_dashboard.py
"""
Bundles public library data (modules, module links, genes, SNPs, biomarkers) into one JSON
for dashboards and the future interactive interface. Contains no personal data.

    python -m cluster_analysis.export_dashboard out/library_bundle.json [--person overlay.json]

--person embeds an overlay result (use only synthetic or consented data in anything you share).
"""
import argparse
import json
import os
from collections import defaultdict

from cluster_analysis.biomarkers import BIOMARKERS_PATH
from cluster_analysis.build_modules import MODULES_PATH

TRAITS_PATH = "config/snp_traits.json"
NAMES_PATH = os.path.join(os.path.dirname(__file__), "module_names.json")


def first_sentence(text, limit=200):
    s = (text or "").split(". ")[0]
    return (s[:limit] + "...") if len(s) > limit else s + ("." if s else "")


def bundle():
    lib = json.load(open(MODULES_PATH, encoding="utf-8"))
    bio = json.load(open(BIOMARKERS_PATH, encoding="utf-8"))["biomarkers"]
    traits = json.load(open(TRAITS_PATH, encoding="utf-8"))
    names = json.load(open(NAMES_PATH, encoding="utf-8"))

    # Symmetric module-to-module weight from bridge genes
    links = defaultdict(float)
    for g, info in lib["genes"].items():
        for other, w in (info.get("bridges_to") or {}).items():
            if info.get("module"):
                links[tuple(sorted((info["module"], other)))] += w

    return {
        "meta": {"built": lib["meta"]["built"], "n_snps": len(traits), "n_genes": len(lib["genes"]),
                 "n_modules": len(lib["modules"]), "n_biomarkers": len(bio),
                 "sources": lib["meta"]["sources"] + ["Ensembl GRCh38 (alleles, frequencies)"]},
        "modules": [{"id": m["id"], "name": names.get(m["label"], m["label"]), "label": m["label"],
                     "size": len(m["genes"]), "genes": m["genes"],
                     "hubs": m["hubs"], "enrichment": [e["description"] for e in m["enrichment"][:4]]}
                    for m in lib["modules"]],
        "module_links": [{"a": a, "b": b, "w": round(w, 2)} for (a, b), w in sorted(links.items(), key=lambda x: -x[1])],
        "genes": {g: {"module": i.get("module"), "name": i.get("name", ""), "summary": first_sentence(i.get("summary")),
                      "bridges_to": i.get("bridges_to", {})} for g, i in lib["genes"].items()},
        "snps": {r: {"genes": d["genes"], "trait": traits.get(r, {}).get("trait", ""),
                     "gwas": [t["trait"] for t in d["gwas"][:3]]} for r, d in lib["rsids"].items()},
        "biomarkers": [{k: b[k] for k in ("biomarker", "panel", "n_snps", "modules")} |
                       {"snps": [{k: s[k] for k in ("rsid", "genes", "modules", "effect_allele", "direction", "strand",
                                                    "eaf_eur", "p_value", "pubmed_id", "first_author")} for s in b["snps"]]}
                       for b in bio],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--person")
    args = ap.parse_args()
    data = bundle()
    if args.person:
        p = json.load(open(args.person, encoding="utf-8"))
        data["person"] = {k: p[k] for k in ("source_file", "modules", "bridges", "biomarker_tilts")}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✅ Wrote {args.out} ({len(json.dumps(data)) // 1024} KB)")
