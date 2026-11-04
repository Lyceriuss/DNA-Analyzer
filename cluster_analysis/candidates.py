# cluster_analysis/candidates.py
"""
Filters a coverage map (coverage_map.py) down to SNPs worth adding to the library: those with
real evidence of what they do, not merely a mention somewhere. Runs offline on the bulk files.

    python -m cluster_analysis.candidates --name HP

A SNP qualifies (and is not in the library yet) when at least one holds:
  A  protein effect       UniProt humsavar class P, LP or US (not benign)
  B  drug / metabolism    ClinPGx clinical annotation at evidence level 1A, 1B, 2A or 2B
  C  biomarker            GWAS Catalog association p < 5e-8 with a standard lab biomarker

Writes data/output/cluster_analysis/candidates_<name>.tsv and .md.
"""
import argparse
import csv
import io
import os
import re
import zipfile
from collections import defaultdict

import pandas as pd

from cluster_analysis.biomarkers import classify_trait

REF = "data/reference"
OUTPUT_DIR = "data/output/cluster_analysis"
STRONG_PGX = {"1A", "1B", "2A", "2B"}
RS = re.compile(r"rs\d+")


def humsavar(rsids):
    out = {}
    with open(f"{REF}/humsavar.txt", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"^(\S+)\s+(\S+)\s+VAR_\d+\s+(\S+)\s+(\S+)\s+(rs\d+)\s+(.*)$", line.rstrip())
            if m and m.group(5) in rsids and m.group(4) in ("P", "LP", "US"):
                out.setdefault(m.group(5), []).append(
                    {"gene": m.group(1), "change": m.group(3), "class": m.group(4), "disease": m.group(6).strip(" -")})
    return out


def clinpgx(rsids):
    out = defaultdict(list)
    with zipfile.ZipFile(f"{REF}/clinpgx_clinical_annotations.zip") as z:
        with z.open("clinical_annotations.tsv") as f:
            for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t"):
                level = row.get("Level of Evidence", "")
                if level not in STRONG_PGX:
                    continue
                for rs in RS.findall(row.get("Variant/Haplotypes", "")):
                    if rs in rsids:
                        out[rs].append({"level": level, "gene": row.get("Gene", ""), "drugs": row.get("Drug(s)", ""),
                                        "category": row.get("Phenotype Category", "")})
    return out


def gwas_biomarkers(rsids):
    """rsid -> {biomarker: best p}, plus the variant's location type (CONTEXT) and mapped gene."""
    out, context = defaultdict(dict), {}
    with zipfile.ZipFile(f"{REF}/gwas_associations_ontology.zip") as z:
        name = next(n for n in z.namelist() if n.endswith(".tsv"))
        with z.open(name) as f:
            for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t"):
                snps = RS.findall(row.get("SNPS", ""))
                hits = [s for s in snps if s in rsids]
                if not hits:
                    continue
                try:
                    p = float(row.get("P-VALUE") or 1)
                except ValueError:
                    continue
                for s in hits:
                    context.setdefault(s, (row.get("CONTEXT", ""), row.get("MAPPED_GENE", "")))
                if p > 5e-8:
                    continue
                for trait in (row.get("MAPPED_TRAIT") or row.get("DISEASE/TRAIT") or "").split(", "):
                    hit = classify_trait(trait.strip())
                    if hit:
                        for s in hits:
                            out[s][hit[1]] = min(p, out[s].get(hit[1], 1))
    return out, context


def main(name):
    cov = pd.read_csv(os.path.join(OUTPUT_DIR, f"coverage_{name}.tsv"), sep="\t", dtype={"chrom": str})
    pool = cov[~cov["in_library"]]
    rsids = set(pool["rsid"])
    print(f"Scanning {len(rsids):,} SNPs not in the library...")
    uni = humsavar(rsids)
    pgx = clinpgx(rsids)
    bio, context = gwas_biomarkers(rsids)
    print(f"  A protein effect: {len(uni):,}   B strong drug evidence: {len(pgx):,}   C biomarker: {len(bio):,}")

    rows = []
    for r in pool.itertuples(index=False):
        a, b, c = uni.get(r.rsid), pgx.get(r.rsid), bio.get(r.rsid)
        if not (a or b or c):
            continue
        ctx, mapped = context.get(r.rsid, ("", ""))
        gene = r.gene if isinstance(r.gene, str) and r.gene else (a[0]["gene"] if a else (b[0]["gene"] if b else mapped))
        rows.append({
            "rsid": r.rsid, "gene": gene, "chrom": r.chrom, "pos": r.pos,
            "gene_in_reactome": bool(r.gene_in_reactome), "context": ctx,
            "A_protein_effect": "; ".join(f"{x['change']} {x['class']} {x['disease']}" for x in a) if a else "",
            "B_drug_evidence": "; ".join(sorted({f"{x['level']} {x['drugs']}" for x in b})) if b else "",
            "C_biomarkers": "; ".join(f"{k} (p={v:.0e})" for k, v in sorted(c.items(), key=lambda kv: kv[1])) if c else "",
            "n_filters": sum(bool(x) for x in (a, b, c)),
            "best_pgx": min((x["level"] for x in b or []), default=""), "n_biomarkers": len(c or {}),
        })
    out = pd.DataFrame(rows).sort_values(["n_filters", "gene_in_reactome", "n_biomarkers"], ascending=False)
    out.to_csv(os.path.join(OUTPUT_DIR, f"candidates_{name}.tsv"), sep="\t", index=False)

    lifecycle = out[out["gene_in_reactome"]]
    md = [f"# Library candidates ({name})", "",
          f"{len(out):,} SNPs not yet in the library pass at least one evidence filter, in {out['gene'].nunique():,} genes. "
          f"{len(lifecycle):,} of them sit in a Reactome pathway gene, so they can also get a lifecycle.", "",
          "| Filter | SNPs | Genes |", "|---|---|---|",
          f"| A Protein effect (UniProt, not benign) | {(out['A_protein_effect'] != '').sum():,} | {out[out['A_protein_effect'] != '']['gene'].nunique():,} |",
          f"| B Strong drug evidence (ClinPGx 1A–2B) | {(out['B_drug_evidence'] != '').sum():,} | {out[out['B_drug_evidence'] != '']['gene'].nunique():,} |",
          f"| C Biomarker (GWAS p < 5e-8) | {(out['C_biomarkers'] != '').sum():,} | {out[out['C_biomarkers'] != '']['gene'].nunique():,} |",
          f"| Two or more filters | {(out['n_filters'] >= 2).sum():,} | {out[out['n_filters'] >= 2]['gene'].nunique():,} |", "",
          "## Strongest candidates (two or more filters)", "",
          "| SNP | Gene | Pathway | Location | Protein effect | Drug evidence | Biomarkers |", "|---|---|---|---|---|---|---|"]
    for r in out[out["n_filters"] >= 2].head(40).itertuples():
        md.append(f"| {r.rsid} | {r.gene} | {'yes' if r.gene_in_reactome else ''} | {r.context} | {r.A_protein_effect[:70]} | "
                  f"{r.B_drug_evidence[:50]} | {r.C_biomarkers[:70]} |")
    md += ["", "## Biomarkers with the most new candidate SNPs", "", "| Biomarker | New SNPs |", "|---|---|"]
    counts = defaultdict(int)
    for v in bio.values():
        for k in v:
            counts[k] += 1
    md += [f"| {k} | {v} |" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:15]]
    text = "\n".join(md) + "\n"
    open(os.path.join(OUTPUT_DIR, f"candidates_{name}.md"), "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="HP")
    main(ap.parse_args().name)
