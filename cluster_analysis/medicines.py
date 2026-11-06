"""Medicines: how a person's genome bears on drug response, from ClinPGx (PharmGKB) clinical annotations.

    python -m cluster_analysis.medicines                               # XY (imputed file when there is one)
    python -m cluster_analysis.medicines --dna data/input/X.csv --out-dir out/

Two kinds of annotation:
  * Star alleles (CYP2C19*2, SLCO1B1*5 ...). The guideline-grade annotations (CPIC, level 1A) are written per allele.
    A small caller below names the person's two alleles in the core drug genes from each allele's defining SNPs,
    and the CPIC rules turn them into a phenotype (poor, intermediate, normal, rapid or ultrarapid metaboliser ...).
  * Single SNPs (rs...). ClinPGx gives a sentence per genotype; the person's own sentence is shown.

Only calls that are measured or imputed at high confidence count (src/loader.py). A rare variant that imputation
can't rule out reads "not detected, not excluded".

Writes med_genes.json (one row per drug gene: alleles, phenotype, the SNPs behind them) and med_drugs.json (one row
per annotation: drug, gene, level, category, the person's genotype or alleles, ClinPGx's text for them, and whether
the person is the typical case) for the explorer's Medicines tab. Both hold the person's genotypes: keep them out of git.
"""
import argparse
import csv
import gzip
import io
import json
import os
import re
import zipfile
from collections import defaultdict

from src.loader import imputed_path, iter_calls, person_label

REF = "data/reference/clinpgx_clinical_annotations.zip"
LEVELS = ("1A", "1B", "2A", "2B", "3")
FLIP = str.maketrans("ACGT", "TGCA")

# Star alleles from their defining SNPs, alleles on the GRCh37 forward strand (checked against 1000 Genomes).
# value: CPIC activity value or function class used by the phenotype rules below.
STAR = {
    "CYP2C19": [("*2", "rs4244285", "A", "No function"), ("*3", "rs4986893", "A", "No function"),
                ("*4", "rs28399504", "G", "No function"), ("*8", "rs41291556", "C", "No function"),
                ("*17", "rs12248560", "T", "Increased function")],
    "CYP2C9": [("*2", "rs1799853", "T", "Decreased function"), ("*3", "rs1057910", "C", "No function"),
               ("*5", "rs28371686", "G", "No function"), ("*8", "rs7900194", "A", "Decreased function"),
               ("*11", "rs28371685", "T", "Decreased function")],
    "CYP2D6": [("*4", "rs3892097", "T", "No function"), ("*10", "rs1065852", "A", "Decreased function"),
               ("*41", "rs28371725", "T", "Decreased function")],
    "CYP3A5": [("*3", "rs776746", "C", "No function"), ("*6", "rs10264272", "T", "No function")],
    "TPMT": [("*3B", "rs1800460", "T", "No function"), ("*3C", "rs1142345", "C", "No function"),
             ("*2", "rs1800462", "G", "No function")],
    "NUDT15": [("*3", "rs116855232", "T", "No function")],
    "DPYD": [("*2A", "rs3918290", "T", "No function"), ("*13", "rs55886062", "C", "No function"),
             ("c.2846A>T", "rs67376798", "A", "Decreased function"), ("HapB3", "rs75017182", "C", "Decreased function")],
    "UGT1A1": [("*28", "rs887829", "T", "Decreased function"), ("*6", "rs4148323", "A", "Decreased function")],
    "CYP2B6": [("*6", "rs3745274", "T", "Decreased function"), ("*18", "rs28399499", "C", "No function")],
    "SLCO1B1": [("*5", "rs4149056", "C", "No function")],
    "NAT2": [("*5", "rs1801280", "C", "Slow"), ("*6", "rs1799930", "A", "Slow"), ("*7", "rs1799931", "A", "Slow"),
             ("*14", "rs1801279", "A", "Slow")],
    "CYP3A4": [("*22", "rs35599367", "A", "Decreased function")],
}
# What the caller can't see, per gene
CAVEATS = {
    "CYP2D6": "Deletions (*5) and extra copies (*1xN, *2xN) of CYP2D6 can't be read from SNP data, and about 1 in 15 "
              "Europeans has one. The call assumes two copies: a clinical CYP2D6 test settles it.",
    "UGT1A1": "*28 is a TA-repeat in the promoter; rs887829 stands in for it (nearly always inherited together in Europeans).",
    "SLCO1B1": "*5 and *15 (both no function) share rs4149056; they are not told apart here, which doesn't change the phenotype.",
    "DPYD": "Only the four variants CPIC tests for are read. Rarer DPYD variants exist; before fluorouracil or capecitabine, a "
            "clinical DPYD test is the standard.",
    "NAT2": "Acetylator type from the four SNPs that define the slow alleles; one slow allele gives intermediate, two slow.",
    "TPMT": "*3A is *3B and *3C on the same chromosome; when both are present once, *3A is assumed (the usual case).",
}
ACTIVITY = {"No function": 0, "Decreased function": 0.5, "Normal function": 1, "Increased function": 1.5}


def diplotype(gene, calls):
    """(alleles, phenotype, snps, note) for a gene from {rsid: (genotype, confidence)}; None when its SNPs are missing."""
    defs = STAR[gene]
    snps, copies, missing = [], {}, []
    for name, rsid, alt, fn in defs:
        c = calls.get(rsid)
        if not c:
            missing.append(rsid)
            continue
        gt, conf = c
        n = gt.count(alt)
        snps.append({"rsid": rsid, "allele": name, "variant": alt, "genotype": gt, "copies": n, "confidence": conf})
        if conf == "not_excluded":
            continue
        copies[name] = n
    if not snps or all(s["confidence"] == "not_excluded" for s in snps):
        return None
    if gene == "TPMT" and copies.get("*3B") and copies.get("*3B") == copies.get("*3C"):
        copies["*3A"] = copies.pop("*3B")
        copies.pop("*3C")
    if gene == "CYP2D6" and copies.get("*4"):  # *4 carries the *10 SNP too
        copies["*10"] = max(0, copies.get("*10", 0) - copies["*4"])
    alleles = [a for a, n in copies.items() for _ in range(n)]
    note = None
    if len(alleles) > 2:
        note = f"{len(alleles)} variant alleles: some must sit on the same chromosome, so the pairing is uncertain."
    alleles = (["*1", "*1"] + alleles)[-2:] if len(alleles) <= 2 else alleles
    fn = {a: f for a, _, _, f in defs}
    fn.update({"*1": "Normal function", "*3A": "No function"})
    funcs = [fn.get(a, "Normal function") for a in alleles]
    return alleles, phenotype(gene, funcs, alleles), snps, note, missing


# CPIC activity values; CYP2D6 counts its decreased alleles differently (*10 is 0.25, *41 is 0.5)
SCORE = {"No function": 0, "Decreased function": 0.5, "Normal function": 1}
CYP2D6_SCORE = {"*4": 0, "*10": 0.25, "*41": 0.5}


def phenotype(gene, funcs, alleles=()):
    """CPIC phenotype from the two alleles' functions."""
    nofn = sum(f == "No function" for f in funcs)
    dec = sum(f == "Decreased function" for f in funcs)
    inc = sum(f == "Increased function" for f in funcs)
    if gene == "CYP2C19":
        if nofn >= 2:
            return "Poor metaboliser"
        if nofn == 1:
            return "Intermediate metaboliser"
        return ("Normal metaboliser", "Rapid metaboliser", "Ultrarapid metaboliser")[min(inc, 2)]
    if gene in ("CYP2C9", "DPYD"):
        score = sum(SCORE.get(f, 1) for f in funcs[:2])
        return f"{'Normal' if score >= 2 else 'Intermediate' if score >= 1 else 'Poor'} metaboliser (activity score {score:g})"
    if gene == "CYP2D6":
        score = sum(CYP2D6_SCORE.get(a, 1) for a in alleles[:2])
        word = "Normal" if score >= 1.25 else "Intermediate" if score > 0 else "Poor"
        return f"{word} metaboliser (activity score {score:g}, assuming two gene copies)"
    if gene == "CYP3A5":
        return ("Poor metaboliser (non-expresser, the usual type in Europeans)", "Intermediate metaboliser",
                "Normal metaboliser (expresser)")[min(len(funcs) - nofn, 2)]
    if gene == "NAT2":
        return ("Rapid acetylator", "Intermediate acetylator", "Slow acetylator")[min(sum(f == "Slow" for f in funcs), 2)]
    if gene == "SLCO1B1":
        return ("Normal function", "Decreased function", "Poor function")[min(nofn, 2)]
    return ("Normal metaboliser", "Intermediate metaboliser", "Poor metaboliser")[min(nofn + dec, 2)]


# HLA types read through a tag SNP that travels with them in Europeans
HLA_TAGS = {"HLA-B*57:01": ("rs2395029", "G")}


def load_annotations(levels):
    zf = zipfile.ZipFile(REF)
    rows = [r for r in csv.DictReader(io.TextIOWrapper(zf.open("clinical_annotations.tsv"), encoding="utf-8"), delimiter="\t")
            if r["Level of Evidence"] in levels]
    texts = defaultdict(list)
    for r in csv.DictReader(io.TextIOWrapper(zf.open("clinical_ann_alleles.tsv"), encoding="utf-8"), delimiter="\t"):
        texts[r["Clinical Annotation ID"]].append(r)
    return rows, texts


def sort_gt(gt):
    return "".join(sorted(gt))


def match_genotype(gt, options):
    """The ClinPGx genotype row matching a forward-strand genotype. ClinPGx reports the forward strand too; the
    complement is tried only when the person's alleles share nothing with the annotation's."""
    by = {sort_gt(o["Genotype/Allele"]): o for o in options if re.fullmatch(r"[ACGT]{2}", o["Genotype/Allele"])}
    if sort_gt(gt) in by:
        return by[sort_gt(gt)]
    seen = set("".join(by))
    if by and not set(gt) & seen and not seen <= {"A", "T"} and not seen <= {"C", "G"}:
        return by.get(sort_gt(gt.translate(FLIP)))
    return None


def baseline_genotypes(options):
    """Genotypes the other rows compare against ("... as compared to patients with the TT genotype")."""
    out = set()
    for o in options:
        for m in re.finditer(r"compared to (?:patients|people|individuals|those)?[^.]*?with (?:the )?([ACGT]{2}(?: or [ACGT]{2})?)", o["Annotation Text"]):
            out |= {sort_gt(x) for x in m.group(1).split(" or ")}
    return out


def major_alleles(where):
    """{rsid: the allele most Europeans carry} from the 1000 Genomes site list, cached. The typical genotype is two
    copies of it."""
    cache = "data/reference/imputation/pgx_major_alleles.json"
    known = json.load(open(cache)) if os.path.exists(cache) else {}
    todo = {f"{c}\t{p}": rs for rs, (c, p) in where.items() if rs not in known and p}
    sites = "data/reference/imputation/sites.vcf.gz"
    if todo and os.path.exists(sites):
        print(f"Looking up European allele frequencies for {len(todo)} SNPs (once)...")
        with gzip.open(sites, "rt") as f:
            for line in f:
                if line[0] == "#":
                    continue
                p = line.split("\t", 8)
                rs = todo.get(f"{p[0]}\t{p[1]}")
                if not rs or len(p[3]) != 1 or len(p[4]) != 1:
                    continue
                m = re.search(r"(?:^|;)EUR_AF=([\d.e-]+)", p[7])
                if m:
                    known[rs] = p[4] if float(m.group(1)) > 0.5 else p[3]
        for rs in todo.values():
            known.setdefault(rs, None)
        json.dump(known, open(cache, "w"))
    return {rs: a for rs, a in known.items() if a}


def build(dna):
    rows, texts = load_annotations(LEVELS)
    rs_wanted = {r["Variant/Haplotypes"] for r in rows if re.fullmatch(r"rs\d+", r["Variant/Haplotypes"])}
    rs_wanted |= {rsid for defs in STAR.values() for _, rsid, _, _ in defs}
    calls, where = {}, {}
    for rsid, chrom, pos, gt, tier in iter_calls(dna, rs_wanted, confidence=None):
        if tier in ("measured", "high", "not_excluded"):
            calls[rsid] = (gt, tier)
            where[rsid] = (chrom, pos)
    major = major_alleles(where)

    genes = []
    star = {}
    for gene in STAR:
        d = diplotype(gene, calls)
        if not d:
            genes.append({"gene": gene, "alleles": None, "phenotype": "Not readable from this file", "snps": "[]",
                          "note": CAVEATS.get(gene), "typical": None})
            continue
        alleles, pheno, snps, note, missing = d
        star[gene] = alleles
        typical = pheno.startswith(("Normal", "Rapid acetylator")) or gene == "CYP3A5" and pheno.startswith("Poor")
        genes.append({"gene": gene, "alleles": "/".join(alleles), "phenotype": pheno, "snps": json.dumps(snps),
                      "note": " ".join(x for x in (note, CAVEATS.get(gene),
                                                    f"Not read: {', '.join(missing)}." if missing else None) if x),
                      "typical": typical, "imputed": any(s["confidence"] == "high" for s in snps)})

    drugs = []
    for r in rows:
        var, gene = r["Variant/Haplotypes"], r["Gene"]
        opts = texts.get(r["Clinical Annotation ID"], [])
        base = {"id": r["Clinical Annotation ID"], "drug": r["Drug(s)"], "gene": gene, "variant": var,
                "level": r["Level of Evidence"], "category": r["Phenotype Category"], "condition": r["Phenotype(s)"],
                "url": r["URL"], "pmids": int(r["PMID Count"] or 0)}
        if re.fullmatch(r"rs\d+", var):
            c = calls.get(var)
            if not c:
                continue
            gt, conf = c
            if conf == "not_excluded":
                drugs.append({**base, "genotype": gt, "confidence": conf, "status": "not_excluded",
                              "text": "The variant is rare and wasn't measured; imputation found no sign of it but can't rule it out."})
                continue
            m = match_genotype(gt, opts)
            if not m:
                continue
            if re.search(r"unknown response|do(?:es)? not (?:carry|have) a copy|both (?:variants|alleles)[^.]*normal function", m["Annotation Text"], re.I):
                status = "typical"  # the annotation is about carriers of a variant the person doesn't have
            elif var in major:
                status = "typical" if sort_gt(m["Genotype/Allele"]) == major[var] * 2 else "differs"
            else:
                bl = {g for g in baseline_genotypes(opts) if g[0] == g[1]}
                status = "unclear" if len(bl) != 1 else "typical" if sort_gt(m["Genotype/Allele"]) in bl else "differs"
            drugs.append({**base, "genotype": m["Genotype/Allele"], "confidence": conf, "status": status, "text": m["Annotation Text"]})
        elif var in HLA_TAGS:
            rsid, allele = HLA_TAGS[var]
            c = calls.get(rsid)
            if not c or c[1] == "not_excluded":
                continue
            carried = c[0].count(allele)
            hit = next((o for o in opts if o["Genotype/Allele"].startswith("*" + var.split("*")[1])), None)
            if carried and hit:
                drugs.append({**base, "genotype": f"{var} likely present (tag {rsid} {c[0]})", "confidence": c[1],
                              "status": "differs", "text": hit["Annotation Text"]})
            elif not carried:
                drugs.append({**base, "genotype": f"{var} not detected (tag {rsid} {c[0]})", "confidence": c[1], "status": "typical",
                              "text": f"No copy of {var} is indicated by its tag SNP {rsid}, so the raised risk this annotation "
                                      f"describes for carriers doesn't apply. A tag SNP is a stand-in; HLA typing confirms it."})
        else:
            g = gene.split(";")[0]
            if g not in star:
                continue
            alleles = star[g]
            dip = "/".join(alleles)
            by = {o["Genotype/Allele"].replace(g, ""): o for o in opts}
            # The variant allele's text says what the pairing means; *1's text is the generic normal-function one
            variant = [a for a in dict.fromkeys(alleles) if a != "*1" and a in by]
            hits = [by[dip]] if dip in by else [by[a] for a in variant] or ([by["*1"]] if "*1" in by else [])
            if not hits:
                continue
            typical = next((x["typical"] for x in genes if x["gene"] == g), False)
            drugs.append({**base, "genotype": f"{g} {dip}", "confidence": "star", "status": "typical" if typical else "differs",
                          "text": " ".join(h["Annotation Text"] for h in hits),
                          "phenotype": next((x["phenotype"] for x in genes if x["gene"] == g), None)})
    return genes, drugs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dna", default="data/input/MyHeritage_raw_dna_data_XY.csv")
    ap.add_argument("--measured-only", action="store_true", help="use the raw file even when an imputed one exists")
    ap.add_argument("--out-dir", default="data/output/cluster_analysis")
    args = ap.parse_args()
    dna = args.dna if args.measured_only else imputed_path(args.dna)
    genes, drugs = build(dna)
    os.makedirs(args.out_dir, exist_ok=True)
    who = person_label(dna)
    for row in genes + drugs:
        row["person"] = who
    for name, rows in (("med_genes", genes), ("med_drugs", drugs)):
        with open(os.path.join(args.out_dir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
    differs = [d for d in drugs if d["status"] == "differs" and d["level"] in ("1A", "1B")]
    print(f"✅ {who}: {len(genes)} drug genes, {len(drugs)} drug annotations ({len(differs)} guideline-level where {who} differs "
          f"from the typical case) → {args.out_dir}")
    for g in genes:
        print(f"   {g['gene']:8} {g['alleles'] or '-':14} {g['phenotype']}")


if __name__ == "__main__":
    main()
