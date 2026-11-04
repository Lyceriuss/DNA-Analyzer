# cluster_analysis/overlay.py
"""
Scores one person's DNA file against the library modules. Runs fully offline.

    python -m cluster_analysis.overlay data/input/MyHeritage_raw_dna_data_HP.csv

Writes data/output/cluster_analysis/<name>_clusters.md and .json (git-ignored: personal data).
"""
import argparse
import json
import os

from cluster_analysis.build_modules import MODULES_PATH
from src.analyzer import run_analysis
from src.report_engine import STRENGTH_MIN_SCORE, RISK_MAX_SCORE

TRAITS_PATH = "config/snp_traits.json"
OUTPUT_DIR = "data/output/cluster_analysis"


def classify(score):
    if score <= RISK_MAX_SCORE: return "risk"
    if score >= STRENGTH_MIN_SCORE: return "strength"
    return "neutral"


def overlay(dna_path):
    with open(MODULES_PATH, "r", encoding="utf-8") as f:
        lib = json.load(f)
    df = run_analysis(dna_path, TRAITS_PATH)
    if df.empty:
        raise SystemExit("No traits matched; nothing to overlay.")

    # Person's results per gene (a gene can carry several SNPs; keep each)
    hits = {}
    for _, row in df.iterrows():
        for gene in lib["rsids"].get(row["RSID"], {}).get("genes", []):
            hits.setdefault(gene, []).append({
                "rsid": row["RSID"], "trait": row["Trait"], "genotype": row["Result"],
                "score": row["Score"], "status": classify(row["Score"]),
                "interpretation": row["Interpretation"],
                "gwas": lib["rsids"][row["RSID"]]["gwas"][:3],
            })

    def gene_status(gene):
        # Worst result decides: one strongly reduced SNP outweighs a neutral one
        rows = hits.get(gene, [])
        return min(rows, key=lambda r: r["score"])["status"] if rows else "untested"

    modules = []
    for m in lib["modules"]:
        tested = [g for g in m["genes"] if g in hits]
        risks = [g for g in tested if gene_status(g) == "risk"]
        strengths = [g for g in tested if gene_status(g) == "strength"]
        risk_load = sum(5 - r["score"] for g in risks for r in hits[g] if r["status"] == "risk")
        strength_load = sum(r["score"] - 5 for g in strengths for r in hits[g] if r["status"] == "strength")

        # Two interacting genes that are both reduced: the effects can stack
        compound = [[a, b, s] for a, b, s in m["edges"] if a in risks and b in risks]
        # A reduced gene whose partner is a strength may be partly compensated
        buffered = [[a, b, s] for a, b, s in m["edges"]
                    if {gene_status(a), gene_status(b)} == {"risk", "strength"}]
        modules.append({
            "id": m["id"], "label": m["label"], "size": len(m["genes"]), "tested": len(tested),
            "risks": risks, "strengths": strengths,
            "risk_load": round(risk_load, 1), "strength_load": round(strength_load, 1),
            "net": round(strength_load - risk_load, 1),
            "compound_links": sorted(compound, key=lambda e: -e[2]),
            "buffered_links": sorted(buffered, key=lambda e: -e[2]),
            "enrichment": [e["description"] for e in m["enrichment"][:3]],
        })
    modules.sort(key=lambda m: (-m["risk_load"], m["net"]))

    # Reduced genes that reach into other systems
    labels = {m["id"]: m["label"] for m in lib["modules"]}
    bridges = []
    for g, info in lib["genes"].items():
        if gene_status(g) == "risk" and info.get("bridges_to"):
            bridges.append({"gene": g, "module": info["module"],
                            "reaches": {labels[k]: w for k, w in info["bridges_to"].items()}})
    bridges.sort(key=lambda b: -sum(b["reaches"].values()))

    return {"source_file": os.path.basename(dna_path), "modules": modules,
            "bridges": bridges, "genes": hits, "library": lib["genes"]}


def _first_sentence(text, limit=220):
    s = (text or "").split(". ")[0]
    return (s[:limit] + "...") if len(s) > limit else s + ("." if s else "")


def to_markdown(result):
    lines = [f"# Cluster analysis: {result['source_file']}", "",
             "Modules are groups of genes from the library that work together (STRING interaction network). "
             f"risk = score ≤ {RISK_MAX_SCORE}, strength = score ≥ {STRENGTH_MIN_SCORE}. "
             "Load = summed distance from baseline 5.", "",
             "| Module | Tested | Risks | Strengths | Risk load | Net |", "|---|---|---|---|---|---|"]
    for m in result["modules"]:
        lines.append(f"| {m['id']} {m['label']} | {m['tested']}/{m['size']} | {len(m['risks'])} | "
                     f"{len(m['strengths'])} | {m['risk_load']} | {m['net']:+} |")

    lines += ["", "## Modules with the highest risk load", ""]
    for m in [m for m in result["modules"] if m["risks"]][:5]:
        lines += [f"### {m['id']} {m['label']}", "",
                  f"Shared biology: {'; '.join(m['enrichment']) or 'n/a'}", ""]
        for g in m["risks"]:
            for r in result["genes"][g]:
                if r["status"] != "risk": continue
                gwas = ", ".join(f"{t['trait']} (p={t['p_value']:.0e})" for t in r["gwas"]) or "no GWAS hits"
                lines.append(f"- **{g}** {r['rsid']} {r['genotype']} (score {r['score']:.0f}): {r['interpretation']}  ")
                lines.append(f"  GWAS: {gwas}  ")
                lines.append(f"  {_first_sentence(result['library'].get(g, {}).get('summary'))}")
        if m["compound_links"]:
            pairs = ", ".join(f"{a}–{b} ({s:.2f})" for a, b, s in m["compound_links"][:6])
            lines += ["", f"**Compound links** (both partners reduced, effects may stack): {pairs}"]
        if m["buffered_links"]:
            pairs = ", ".join(f"{a}–{b}" for a, b, _ in m["buffered_links"][:6])
            lines += [f"**Buffered links** (reduced gene next to a strength): {pairs}"]
        lines.append("")

    if result["bridges"]:
        lines += ["## Reduced bridge genes", "",
                  "Reduced genes with strong interactions into other modules: candidates for cross-system effects.", ""]
        for b in result["bridges"][:8]:
            reach = ", ".join(f"{k} ({w})" for k, w in list(b["reaches"].items())[:3])
            lines.append(f"- **{b['gene']}** → {reach}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dna_file")
    args = ap.parse_args()

    result = overlay(args.dna_file)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(args.dna_file))[0]
    md_path = os.path.join(OUTPUT_DIR, f"{name}_clusters.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(result))
    result.pop("library")
    with open(os.path.join(OUTPUT_DIR, f"{name}_clusters.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=float)
    print(f"✅ Wrote {md_path}")
