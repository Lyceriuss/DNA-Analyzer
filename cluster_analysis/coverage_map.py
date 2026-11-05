# cluster_analysis/coverage_map.py
"""
How much of a DNA file do the research sources know about? Matches every SNP in the file,
offline, against bulk downloads: no per-SNP API requests, nothing from the file leaves the machine.

    python -m cluster_analysis.coverage_map data/input/MyHeritage_raw_dna_data_XY.csv

Reference files in data/reference/ (download once, see docs):
  gwas_associations_ontology.zip   GWAS Catalog, all associations (ontology-annotated)
  humsavar.txt                     UniProt curated human variants
  clinpgx_variants.zip             ClinPGx/PharmGKB variants
  clinpgx_clinical_annotations.zip ClinPGx/PharmGKB clinical annotations
  clinvar_grch37.vcf.gz            ClinVar (GRCh37, same build as MyHeritage files)
  ensembl_grch37_genes.gtf.gz      Ensembl gene coordinates (GRCh37)
  Ensembl2Reactome.txt             Reactome pathways per Ensembl gene

Writes data/output/cluster_analysis/coverage_<name>.tsv (one row per SNP, yes/no per source)
and coverage_<name>.md (summary, plus candidate SNPs to grow the library).
"""
import argparse
import bisect
import csv
import gzip
import io
import json
import os
import re
import zipfile
from collections import Counter, defaultdict

import pandas as pd

REF = "data/reference"
OUTPUT_DIR = "data/output/cluster_analysis"
RS = re.compile(r"rs\d+")


def rsids_in_zip(path, column_hint=None):
    """All rsIDs mentioned in the tabular files of a zip (optionally only in columns matching a hint)."""
    found = set()
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.endswith((".tsv", ".txt", ".csv")):
                continue
            with z.open(name) as f:
                reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t")
                header = next(reader, [])
                cols = [i for i, h in enumerate(header) if not column_hint or re.search(column_hint, h, re.I)] or range(len(header))
                for row in reader:
                    for i in cols:
                        if i < len(row) and "rs" in row[i]:
                            found.update(RS.findall(row[i]))
    return found


def load_sources():
    print("Reading reference files...")
    s = {}
    s["gwas"] = rsids_in_zip(f"{REF}/gwas_associations_ontology.zip", r"^SNPS$|SNP_ID_CURRENT|STRONGEST")
    print(f"  GWAS Catalog: {len(s['gwas']):,} rsIDs")
    # humsavar classes: P/LP (likely) disease-causing, US uncertain, LB/B (likely) benign
    s["uniprot"], s["uniprot_effect"] = set(), set()
    with open(f"{REF}/humsavar.txt", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"^\S+\s+\S+\s+VAR_\d+\s+\S+\s+(\S+)\s+(rs\d+)", line)
            if m:
                s["uniprot"].add(m.group(2))
                if m.group(1) in ("P", "LP", "US"):
                    s["uniprot_effect"].add(m.group(2))
    print(f"  UniProt humsavar: {len(s['uniprot']):,} rsIDs ({len(s['uniprot_effect']):,} not classed benign)")
    s["clinpgx"] = rsids_in_zip(f"{REF}/clinpgx_variants.zip") | rsids_in_zip(f"{REF}/clinpgx_clinical_annotations.zip")
    print(f"  ClinPGx: {len(s['clinpgx']):,} rsIDs")
    clinvar = set()
    with gzip.open(f"{REF}/clinvar_grch37.vcf.gz", "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[0] != "#":
                m = re.search(r"[;\t]RS=(\d+)", line)
                if m:
                    clinvar.add("rs" + m.group(1))
    s["clinvar"] = clinvar
    print(f"  ClinVar: {len(s['clinvar']):,} rsIDs")
    return s


def load_genes():
    """Per chromosome: sorted gene intervals (start, end, gene_id, name, biotype) from the GRCh37 GTF."""
    genes = defaultdict(list)
    with gzip.open(f"{REF}/ensembl_grch37_genes.gtf.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.split("\t", 8)
            if p[2] != "gene":
                continue
            attr = dict(re.findall(r'(\w+) "([^"]*)"', p[8]))
            genes[p[0]].append((int(p[3]), int(p[4]), attr.get("gene_id"), attr.get("gene_name"), attr.get("gene_biotype")))
    for c in genes:
        genes[c].sort()
    print(f"  Ensembl GRCh37: {sum(len(v) for v in genes.values()):,} genes")
    return genes


def reactome_genes():
    ids = set()
    with open(f"{REF}/Ensembl2Reactome.txt", encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.split("\t")
            if len(p) >= 6 and p[5].strip() == "Homo sapiens" and p[0].startswith("ENSG"):
                ids.add(p[0])
    print(f"  Reactome: {len(ids):,} human genes in pathways")
    return ids


def gene_at(genes_chr, starts, pos):
    """The gene containing pos (protein-coding preferred), or None."""
    i = bisect.bisect_right(starts, pos)
    hits = []
    for j in range(i - 1, max(-1, i - 400), -1):  # long genes start well before pos
        s, e, gid, name, bt = genes_chr[j]
        if s <= pos <= e:
            hits.append((bt != "protein_coding", e - s, gid, name, bt))
    return min(hits)[2:] if hits else None


def main(dna_path, name):
    df = pd.read_csv(dna_path, comment="#", dtype=str, usecols=[0, 1, 2])
    df.columns = ["rsid", "chrom", "pos"]
    df = df.dropna().drop_duplicates("rsid")
    df["pos"] = df["pos"].astype(int)
    print(f"{len(df):,} SNPs in {os.path.basename(dna_path)}")

    srcs = load_sources()
    genes = load_genes()
    in_reactome = reactome_genes()
    starts = {c: [g[0] for g in v] for c, v in genes.items()}
    lib = json.load(open("cluster_analysis/modules.json", encoding="utf-8"))
    library = set(lib["rsids"])
    evidence = {r["rsid"]: r for r in json.load(open("cluster_analysis/function_evidence.json", encoding="utf-8"))}

    rows = []
    for rsid, chrom, pos in df[["rsid", "chrom", "pos"]].itertuples(index=False):
        g = gene_at(genes.get(chrom, []), starts.get(chrom, []), pos) if chrom in genes else None
        gid, gname, bt = g if g else (None, None, None)
        rows.append({"rsid": rsid, "chrom": chrom, "pos": pos, "gene": gname or "", "gene_id": gid or "",
                     "biotype": bt or "", "in_gene": bool(g), "protein_coding": bt == "protein_coding",
                     "gene_in_reactome": bool(gid and gid in in_reactome),
                     "gwas": rsid in srcs["gwas"], "uniprot": rsid in srcs["uniprot"],
                     "uniprot_not_benign": rsid in srcs["uniprot_effect"],
                     "clinpgx": rsid in srcs["clinpgx"], "clinvar": rsid in srcs["clinvar"],
                     "in_library": rsid in library})
    out = pd.DataFrame(rows)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out.to_csv(os.path.join(OUTPUT_DIR, f"coverage_{name}.tsv"), sep="\t", index=False)

    n = len(out)
    pct = lambda k: f"{out[k].sum():,} ({out[k].mean():.1%})"
    any_snp = out[["gwas", "uniprot", "clinpgx", "clinvar"]].any(axis=1)
    known_fn = out["uniprot"] | out["clinpgx"]
    cand = out[out["gene_in_reactome"] & known_fn & ~out["in_library"]]
    genes_hit = out[out["in_gene"]]["gene"].nunique()
    pc_genes = out[out["protein_coding"]]["gene"].nunique()
    rx_genes = out[out["gene_in_reactome"]]["gene"].nunique()

    md = [f"# Coverage of {os.path.basename(dna_path)}", "",
          f"{n:,} SNPs matched offline against bulk downloads. Nothing was sent to any API.", "",
          "## Where the SNPs sit", "", "| | SNPs | Distinct genes |", "|---|---|---|",
          f"| Inside any gene | {pct('in_gene')} | {genes_hit:,} |",
          f"| Inside a protein-coding gene | {pct('protein_coding')} | {pc_genes:,} |",
          f"| Gene is in a Reactome pathway | {pct('gene_in_reactome')} | {rx_genes:,} |",
          f"| Between genes | {(~out['in_gene']).sum():,} ({(~out['in_gene']).mean():.1%}) | – |", "",
          "## Which sources know the exact SNP", "", "| Source | SNPs known | What it means |", "|---|---|---|",
          f"| GWAS Catalog | {pct('gwas')} | Linked to a trait or measurement in a genome-wide study |",
          f"| ClinVar | {pct('clinvar')} | Reported in clinical genetics (any significance, incl. benign) |",
          f"| UniProt | {pct('uniprot')} | Curated protein-level variant (any class) |",
          f"| UniProt, not benign | {pct('uniprot_not_benign')} | Classed disease-causing or uncertain |",
          f"| ClinPGx | {pct('clinpgx')} | Drug or metabolism annotation |",
          f"| Any of these | {any_snp.sum():,} ({any_snp.mean():.1%}) | |",
          f"| Library (today) | {pct('in_library')} | Scored in the PDF report |", "",
          "## Candidates to grow the library", "",
          f"{len(cand):,} SNPs in {cand['gene'].nunique():,} pathway genes have curated protein-level (UniProt) or drug "
          f"(ClinPGx) knowledge but are not in the library yet.", "",
          "| Gene | Candidate SNPs | UniProt | ClinPGx | GWAS |", "|---|---|---|---|---|"]
    top = cand.groupby("gene").agg(snps=("rsid", "count"), uniprot=("uniprot", "sum"),
                                   clinpgx=("clinpgx", "sum"), gwas=("gwas", "sum")).sort_values("snps", ascending=False)
    md += [f"| {g} | {r.snps} | {r.uniprot} | {r.clinpgx} | {r.gwas} |" for g, r in top.head(25).iterrows()]
    text = "\n".join(md) + "\n"
    open(os.path.join(OUTPUT_DIR, f"coverage_{name}.md"), "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dna_file")
    ap.add_argument("--name")
    a = ap.parse_args()
    main(a.dna_file, a.name or os.path.splitext(os.path.basename(a.dna_file))[0].split("_")[-1])
