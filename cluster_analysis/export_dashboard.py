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


EVIDENCE_PATH = os.path.join(os.path.dirname(__file__), "function_evidence.json")
TIER_NAMES = {1: "Measured protein function (MaveDB)", 2: "Curated functional effect (UniProt)",
              3: "Expression effect (GTEx)", 4: "Predicted damage only (SIFT/PolyPhen)", 5: "No functional evidence"}
CLINPGX_LEVEL = {"1A": 0, "1B": 1, "2A": 2, "2B": 3, "3": 4, "4": 5}


def _copies(genotype, allele, alleles):
    """Copies of a forward-strand allele in a genotype, flipping the genotype's strand when needed."""
    if not genotype or not allele:
        return None
    gt = genotype if set(genotype) <= set(alleles) else genotype.translate(str.maketrans("ACGT", "TGCA"))
    return gt.count(allele)


def evidence_summary(ev, genotype):
    """The function evidence for one SNP, reduced to what a reader needs next to the genotype."""
    src = ev.get("sources", {})
    out = {"tier": ev.get("tier", 5), "tier_name": TIER_NAMES.get(ev.get("tier", 5)), "consequence": ev.get("consequence"),
           "protein_change": ev.get("protein_change")}
    if src.get("mavedb"):
        out["mavedb"] = [{"conditions": m["conditions"], "score": round(m["score"], 3), "change": m["change"]}
                         for m in src["mavedb"]][:8]
    g = src.get("gtex")
    if g and g.get("own_gene"):
        _, _, ref, alt, _ = g["variant_id"].split("_")
        top = g["top"][0] if g.get("top") else None
        out["gtex"] = {"allele": g["effect_allele"], "copies": _copies(genotype, g["effect_allele"], [ref, alt]),
                       "n_tissues": g["n_tissues"], "direction": "raises" if top and top["nes"] > 0 else "lowers",
                       "tissue": top["tissue"].replace("_", " ") if top else None, "nes": top["nes"] if top else None}
    if src.get("uniprot", {}).get("functional"):
        out["uniprot"] = src["uniprot"]["functional"][:4]
    if src.get("predicted"):
        out["predicted"] = [f"{x['tool']}: {x['call']}" for x in src["predicted"]]
    pgx = sorted(src.get("clinpgx") or [], key=lambda x: CLINPGX_LEVEL.get(x["level"], 9))[:3]
    if pgx:
        out["clinpgx"] = [{"level": x["level"], "chemicals": ", ".join(x["chemicals"]),
                           "phenotype": next((y["phenotype"] for y in x["genotypes"] if genotype and y["genotype"] in
                                              {genotype, genotype[::-1]}), None)} for x in pgx]
    return out


def lifecycle_rows(lifecycles, status=None):
    """Flattens lifecycle.py output into (steps, genes, gene_function) row lists for dashboards.
    Contains genotypes when the lifecycles were built with a DNA file. status ({gene: summarized person call},
    from gene_trace.person_status) replaces the calls stored in the lifecycles, so a new function call
    does not need new API walks."""
    status = status or {}
    evidence = {e["rsid"]: e for e in json.load(open(EVIDENCE_PATH, encoding="utf-8"))}
    person = lambda g: status.get(g["gene"]) or g.get("person") or {}

    def chip(g):
        p = person(g)
        return {"gene": g["gene"], "lib": g["in_library"], "gt": p.get("genotype"), "fn": p.get("function"),
                "dose": p.get("dose"), "score": p.get("score")}

    steps, genes, seen = [], [], {}
    with_lifecycle = {lc["gene"] for lc in lifecycles if lc.get("roles")}
    for lc in lifecycles:
        for ri, role in enumerate(lc.get("roles") or [], 1):
            fp = status.get(lc["gene"]) or next((g.get("person") for s in role["steps"] for g in s["genes"]
                                                  if g["gene"] == lc["gene"] and g.get("person")), None) or {}
            genes.append({
                "gene": lc["gene"], "role": ri, "pathway": (role.get("pathway") or {}).get("name", "Unmapped"),
                "top_pathway": (role.get("pathway") or {}).get("top", ""), "n_steps": len(role["steps"]),
                "start": role["start"], "end": role["end"], "genotype": fp.get("genotype"), "function": fp.get("function"),
                "score": fp.get("score"), "interpretation": fp.get("interpretation"),
                "cofactors": ", ".join(lc.get("cofactors") or []), "vitamins": ", ".join(lc.get("cofactor_vitamins") or []),
                "regulation": lc.get("regulation") or "",
                "regulators": json.dumps([{"gene": r["gene"], "effect": r["effect"], "lib": r["in_library"]}
                                          for r in (lc.get("regulators") or [])]),
                "other_pathways": lc.get("other_pathways", 0)})
            for i, s in enumerate(role["steps"]):
                for g in s["genes"]:
                    if g["in_library"]:
                        seen[g["gene"]] = g
                steps.append({
                    "gene": lc["gene"], "role": ri, "order": i, "section": s["section"], "reaction": s["reaction"],
                    "reaction_id": s["reaction_id"], "inputs": ", ".join(s["inputs"]), "outputs": ", ".join(s["outputs"]),
                    "transport": s["transport"],
                    "move": (" / ".join(s["compartment_in"]) + " → " + " / ".join(s["compartment_out"])) if s["transport"] else "",
                    "enzymes": json.dumps([chip(g) for g in s["genes"]]),
                    "alternatives": " | ".join(f"{a['reaction']} ({', '.join(a['genes']) or 'no enzyme'})" for a in s["alternatives"])})

    function = []
    for name in sorted(set(seen) | with_lifecycle):
        p = status.get(name) or (seen.get(name) or {}).get("person") or {}
        ev = evidence.get(p.get("rsid"), {}) if p else {}
        function.append({"gene": name, "has_lifecycle": name in with_lifecycle, "rsid": p.get("rsid"),
                         "genotype": p.get("genotype"), "function": p.get("function"), "dose": p.get("dose"),
                         "common": p.get("common"), "minor": p.get("minor"), "minor_af": p.get("minor_af"),
                         "score": p.get("score"), "interpretation": p.get("interpretation"), "n_snps": p.get("n_snps"),
                         "evidence": json.dumps(evidence_summary(ev, p.get("genotype")) if ev else {})})
    return steps, genes, function


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--person")
    ap.add_argument("--lifecycles", help="lifecycle.py output: also write lifecycle_steps, lifecycle_genes and "
                                         "gene_function JSON next to out")
    ap.add_argument("--dna", help="with --lifecycles: recompute the genotype calls from this DNA file")
    args = ap.parse_args()
    if args.lifecycles:
        from cluster_analysis.gene_trace import person_status, summarize
        status = {g: summarize(v) for g, v in person_status(args.dna).items()} if args.dna else {}
        tables = lifecycle_rows(json.load(open(args.lifecycles, encoding="utf-8")), status)
        out_dir = os.path.dirname(args.out) or "."
        for name, rows in zip(("lifecycle_steps", "lifecycle_genes", "gene_function"), tables):
            with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
            print(f"✅ Wrote {name}.json ({len(rows)} rows)")
    data = bundle()
    if args.person:
        p = json.load(open(args.person, encoding="utf-8"))
        data["person"] = {k: p[k] for k in ("source_file", "modules", "bridges", "biomarker_tilts")}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✅ Wrote {args.out} ({len(json.dumps(data)) // 1024} KB)")
