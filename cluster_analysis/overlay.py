# cluster_analysis/overlay.py
"""
Reads one person's DNA file against the library modules. Runs fully offline.

    python -m cluster_analysis.overlay data/input/MyHeritage_raw_dna_data_XY.csv [--dashboard OUT_DIR]

Writes data/output/cluster_analysis/<name>_clusters.md and .json (git-ignored: personal data); --dashboard also writes
the explorer's Profile datasets (hp_modules, hp_links, hp_bridges, hp_tilts) to OUT_DIR.

A gene reads negative or positive when the evidence says the person's genotype changes it (GoF / LoF / altered) and the
library's polarity says that change is bad or good for them (genotype_effects.py). Typical function and genotypes
without evidence count as neither.
"""
import argparse
import json
import math
import os

from cluster_analysis.biomarkers import BIOMARKERS_PATH
from cluster_analysis.build_modules import MODULES_PATH
from src.analyzer import run_analysis

TRAITS_PATH = "config/snp_traits.json"
OUTPUT_DIR = "data/output/cluster_analysis"
NAMES_PATH = os.path.join(os.path.dirname(__file__), "module_names.json")
MIN_SNPS_FOR_SCORE = 3
# Which reading decides when a gene has several SNPs
STATUS_RANK = {"negative": 0, "positive": 1, "neutral": 2, "unclear": 3, "typical": 4, "unknown": 5}


def biomarker_tilts(user_gt, biomarkers):
    """
    Standardised genetic score per biomarker against European allele frequencies:
        z = sum(sign * (dosage - 2p)) / sqrt(sum(2p(1-p)))
    Equal weight per SNP (GWAS effect sizes use incompatible units). Strand-ambiguous SNPs are skipped.
    """
    tilts = []
    for b in biomarkers:
        contribs, var = [], 0.0
        for s in b["snps"]:
            gt = user_gt.get(s["rsid"])
            if not gt or s["strand"] == "ambiguous" or s["eaf_eur"] is None:
                continue
            p = min(max(s["eaf_eur"], 0.01), 0.99)
            dosage = gt.count(s["effect_allele"])
            sign = 1 if s["direction"] == "+" else -1
            contribs.append({"rsid": s["rsid"], "genes": s["genes"], "modules": s["modules"],
                             "genotype": gt, "effect_allele": s["effect_allele"], "direction": s["direction"],
                             "contribution": round(sign * (dosage - 2 * p), 3)})
            var += 2 * p * (1 - p)
        if not contribs:
            continue
        tilt = {"biomarker": b["biomarker"], "panel": b["panel"], "z": None, "percentile": None,
                "n_snps": len(contribs), "contributions": sorted(contribs, key=lambda c: -abs(c["contribution"]))}
        # One or two SNPs (often rare) make the z-score explode; report direction only
        if len(contribs) >= MIN_SNPS_FOR_SCORE:
            z = sum(c["contribution"] for c in contribs) / math.sqrt(var)
            tilt["z"] = round(z, 2)
            tilt["percentile"] = round(50 * (1 + math.erf(z / math.sqrt(2))))
        tilts.append(tilt)
    return sorted(tilts, key=lambda t: (t["z"] is None, -abs(t["z"] or 0)))


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
                "function": row["Function"], "basis": row["Basis"], "status": row["Outcome"],
                "interpretation": row["Interpretation"],
                "gwas": lib["rsids"][row["RSID"]]["gwas"][:3],
            })

    def gene_status(gene):
        # A negative reading outweighs a positive one, which outweighs no reading
        rows = hits.get(gene, [])
        return min((r["status"] for r in rows), key=lambda s: STATUS_RANK.get(s, 9)) if rows else "untested"

    modules = []
    for m in lib["modules"]:
        tested = [g for g in m["genes"] if g in hits]
        negative = [g for g in tested if gene_status(g) == "negative"]
        positive = [g for g in tested if gene_status(g) == "positive"]

        # Two interacting genes that both read negative: the effects can stack
        compound = [[a, b, s] for a, b, s in m["edges"] if a in negative and b in negative]
        # A negative gene whose partner reads positive may be partly compensated
        buffered = [[a, b, s] for a, b, s in m["edges"]
                    if {gene_status(a), gene_status(b)} == {"negative", "positive"}]
        modules.append({
            "id": m["id"], "label": m["label"], "size": len(m["genes"]), "tested": len(tested),
            "with_evidence": sum(1 for g in tested if gene_status(g) not in ("unknown", "untested")),
            "negative": negative, "positive": positive, "net": len(positive) - len(negative),
            "compound_links": sorted(compound, key=lambda e: -e[2]),
            "buffered_links": sorted(buffered, key=lambda e: -e[2]),
            "enrichment": [e["description"] for e in m["enrichment"][:3]],
        })
    modules.sort(key=lambda m: (-len(m["negative"]), m["net"]))

    # Negative genes that reach into other systems
    labels = {m["id"]: m["label"] for m in lib["modules"]}
    bridges = []
    for g, info in lib["genes"].items():
        if gene_status(g) == "negative" and info.get("bridges_to"):
            bridges.append({"gene": g, "module": info["module"],
                            "reaches": {labels[k]: w for k, w in info["bridges_to"].items()}})
    bridges.sort(key=lambda b: -sum(b["reaches"].values()))

    with open(BIOMARKERS_PATH, "r", encoding="utf-8") as f:
        biomarkers = json.load(f)["biomarkers"]
    tilts = biomarker_tilts(dict(zip(df["RSID"], df["User_Genotype"])), biomarkers)

    return {"source_file": os.path.basename(dna_path), "modules": modules,
            "bridges": bridges, "biomarker_tilts": tilts, "genes": hits, "library": lib["genes"]}


def _first_sentence(text, limit=220):
    s = (text or "").split(". ")[0]
    return (s[:limit] + "...") if len(s) > limit else s + ("." if s else "")


def to_markdown(result):
    lines = [f"# Cluster analysis: {result['source_file']}", "",
             "Modules are groups of genes from the library that work together (STRING interaction network). "
             "Negative / positive: the evidence says the genotype changes the gene (GoF / LoF) and that change is bad / "
             "good for the person.", "",
             "| Module | Tested | With evidence | Negative | Positive | Net |", "|---|---|---|---|---|---|"]
    for m in result["modules"]:
        lines.append(f"| {m['id']} {m['label']} | {m['tested']}/{m['size']} | {m['with_evidence']} | "
                     f"{len(m['negative'])} | {len(m['positive'])} | {m['net']:+} |")

    lines += ["", "## Modules with the most negative genes", ""]
    for m in [m for m in result["modules"] if m["negative"]][:5]:
        lines += [f"### {m['id']} {m['label']}", "",
                  f"Shared biology: {'; '.join(m['enrichment']) or 'n/a'}", ""]
        for g in m["negative"]:
            for r in result["genes"][g]:
                if r["status"] != "negative": continue
                gwas = ", ".join(f"{t['trait']} (p={t['p_value']:.0e})" for t in r["gwas"]) or "no GWAS hits"
                lines.append(f"- **{g}** {r['rsid']} {r['genotype']} ({r['function']}, {r['basis']}): {r['interpretation']}  ")
                lines.append(f"  GWAS: {gwas}  ")
                lines.append(f"  {_first_sentence(result['library'].get(g, {}).get('summary'))}")
        if m["compound_links"]:
            pairs = ", ".join(f"{a}–{b} ({s:.2f})" for a, b, s in m["compound_links"][:6])
            lines += ["", f"**Compound links** (both partners negative, effects may stack): {pairs}"]
        if m["buffered_links"]:
            pairs = ", ".join(f"{a}–{b}" for a, b, _ in m["buffered_links"][:6])
            lines += [f"**Buffered links** (negative gene next to a positive one): {pairs}"]
        lines.append("")

    if result["bridges"]:
        lines += ["## Negative bridge genes", "",
                  "Genes reading negative with strong interactions into other modules: candidates for cross-system effects.", ""]
        for b in result["bridges"][:8]:
            reach = ", ".join(f"{k} ({w})" for k, w in list(b["reaches"].items())[:3])
            lines.append(f"- **{b['gene']}** → {reach}")

    tilts = [t for t in result["biomarker_tilts"] if t["z"] is not None and abs(t["z"]) >= 1]
    if tilts:
        lines += ["", "## Biomarker tilts (|z| ≥ 1)", "",
                  "Standardised genetic score vs. European allele frequencies (0 = average, equal weight per SNP). "
                  "Suggests which lab values are worth measuring; it does not predict them.", "",
                  "| Biomarker | Panel | z | Percentile | SNPs | Top drivers |", "|---|---|---|---|---|---|"]
        for t in tilts:
            drivers = ", ".join(f"{'/'.join(c['genes'])} ({c['contribution']:+.1f})" for c in t["contributions"][:3])
            lines.append(f"| {t['biomarker']} | {t['panel']} | {t['z']:+.2f} | {t['percentile']} | {t['n_snps']} | {drivers} |")
    return "\n".join(lines) + "\n"


def dashboard_rows(result):
    """The explorer's Profile datasets: {hp_modules, hp_links, hp_bridges, hp_tilts} row lists."""
    names = json.load(open(NAMES_PATH, encoding="utf-8")) if os.path.exists(NAMES_PATH) else {}
    name = lambda label: names.get(label, label)
    labels = {m["id"]: m["label"] for m in result["modules"]}
    modules = [{"id": m["id"], "name": name(m["label"]), "tested": m["tested"], "size": m["size"],
                "with_evidence": m["with_evidence"], "negative": len(m["negative"]), "positive": len(m["positive"]),
                "net": m["net"], "compound_links": len(m["compound_links"]),
                "negative_genes": ", ".join(sorted(m["negative"])), "positive_genes": ", ".join(sorted(m["positive"]))}
               for m in result["modules"]]
    links = [{"module": m["id"], "module_name": name(m["label"]), "kind": kind, "gene_a": a, "gene_b": b, "string_score": s}
             for m in result["modules"] for kind in ("compound", "buffered") for a, b, s in m[f"{kind}_links"]]
    bridges = [{"gene": b["gene"], "module": b["module"], "module_name": name(labels.get(b["module"], b["module"])),
                "reaches": "; ".join(f"{name(k)} ({w})" for k, w in list(b["reaches"].items())[:3]),
                "total_weight": round(sum(b["reaches"].values()), 2)} for b in result["bridges"]]
    tilts = [{"biomarker": t["biomarker"], "panel": t["panel"], "z": t["z"], "percentile": t["percentile"],
              "n_snps": t["n_snps"],
              "drivers": ", ".join(f"{'/'.join(c['genes'])} ({c['contribution']:+.1f})" for c in t["contributions"][:3])}
             for t in result["biomarker_tilts"] if t["z"] is not None]
    return {"hp_modules": modules, "hp_links": links, "hp_bridges": bridges, "hp_tilts": tilts}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dna_file")
    ap.add_argument("--name", help="output file stem (default: input file name)")
    ap.add_argument("--dashboard", metavar="OUT_DIR", help="also write the explorer's Profile datasets here")
    args = ap.parse_args()

    result = overlay(args.dna_file)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    name = args.name or os.path.splitext(os.path.basename(args.dna_file))[0]
    md_path = os.path.join(OUTPUT_DIR, f"{name}_clusters.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(result))
    if args.dashboard:
        os.makedirs(args.dashboard, exist_ok=True)
        for k, rows in dashboard_rows(result).items():
            json.dump(rows, open(os.path.join(args.dashboard, f"{k}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"✅ Wrote the Profile datasets to {args.dashboard}")
    result.pop("library")
    with open(os.path.join(OUTPUT_DIR, f"{name}_clusters.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=float)
    print(f"✅ Wrote {md_path}")
