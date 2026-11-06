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
from collections import Counter, defaultdict

from src.loader import imputed_path, iter_calls, person_label

REF = "data/reference/clinpgx_clinical_annotations.zip"
GUIDELINES = "data/reference/clinpgx_guidelines.zip"      # scripts/fetch_pgx_reference.sh
LABELS = "data/reference/clinpgx_drug_labels.zip"
CPIC_RECS = "data/reference/cpic_recommendations.json"
CLINVAR = "data/reference/clinvar_grch37.vcf.gz"
SITES = "data/reference/imputation/sites.vcf.gz"
FREQ_CACHE = "data/reference/imputation/pgx_pop_freqs.json"
POPS = ("AFR", "AMR", "EAS", "EUR", "SAS")                 # 1000 Genomes superpopulations
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


def site_freqs(where):
    """{rsid: {ref, alt, AFR, AMR, EAS, EUR, SAS}} (alt allele frequency per 1000 Genomes superpopulation) for the
    SNPs at the given GRCh37 positions, looked up once in the site list and cached."""
    known = json.load(open(FREQ_CACHE)) if os.path.exists(FREQ_CACHE) else {}
    todo = {f"{c}\t{p}": rs for rs, (c, p) in where.items() if rs not in known and p}
    if todo and os.path.exists(SITES):
        print(f"Looking up allele frequencies across ancestries for {len(todo)} SNPs (once)...")
        with gzip.open(SITES, "rt") as f:
            for line in f:
                if line[0] == "#":
                    continue
                p = line.split("\t", 8)
                rs = todo.get(f"{p[0]}\t{p[1]}")
                if not rs or len(p[3]) != 1 or len(p[4]) != 1:
                    continue
                af = dict(re.findall(r"(?:^|;)(AFR|AMR|EAS|EUR|SAS)_AF=([\d.e-]+)", p[7]))
                if len(af) == len(POPS):
                    known[rs] = {"ref": p[3], "alt": p[4], **{k: float(v) for k, v in af.items()}}
        for rs in todo.values():
            known.setdefault(rs, None)
        json.dump(known, open(FREQ_CACHE, "w"))
    return {rs: f for rs, f in known.items() if f}


def allele_freq(site, allele):
    """{population: frequency of allele} from a site_freqs entry; the complement is tried for the other strand."""
    if not site:
        return None
    for a in (allele, allele.translate(FLIP)):
        if a == site["alt"]:
            return {p: round(site[p], 4) for p in POPS}
        if a == site["ref"]:
            return {p: round(1 - site[p], 4) for p in POPS}
    return None


def major_alleles(freqs):
    """{rsid: the allele most Europeans carry}; the typical genotype is two copies of it."""
    return {rs: f["alt"] if f["EUR"] > 0.5 else f["ref"] for rs, f in freqs.items()}


def build(dna):
    rows, texts = load_annotations(LEVELS)
    rs_wanted = {r["Variant/Haplotypes"] for r in rows if re.fullmatch(r"rs\d+", r["Variant/Haplotypes"])}
    rs_wanted |= {rsid for defs in STAR.values() for _, rsid, _, _ in defs}
    rs_wanted |= {rs for rs, _ in HLA_TAGS.values()} | set(SNP_GENES.values())
    clinvar = clinvar_drug_response()
    rs_wanted |= set(clinvar)
    calls, where = {}, {}
    for rsid, chrom, pos, gt, tier in iter_calls(dna, rs_wanted, confidence=None):
        where[rsid] = (chrom, pos)  # every tier: the frequencies don't depend on the call
        if tier in ("measured", "high", "not_excluded"):
            calls[rsid] = (gt, tier)
    freqs = site_freqs(where)
    major = major_alleles(freqs)

    genes = []
    star = {}
    for gene in STAR:
        # How common each defining allele is in the five 1000 Genomes ancestries
        across = [{"allele": name, "rsid": rsid, "variant": alt, "function": fn, "freq": allele_freq(freqs.get(rsid), alt)}
                  for name, rsid, alt, fn in STAR[gene]]
        across = json.dumps([a for a in across if a["freq"]])
        d = diplotype(gene, calls)
        if not d:
            genes.append({"gene": gene, "alleles": None, "phenotype": "Not readable from this file", "snps": "[]",
                          "note": CAVEATS.get(gene), "typical": None, "ancestry": across})
            continue
        alleles, pheno, snps, note, missing = d
        star[gene] = alleles
        typical = pheno.startswith(("Normal", "Rapid acetylator")) or gene == "CYP3A5" and pheno.startswith("Poor")
        genes.append({"gene": gene, "alleles": "/".join(alleles), "phenotype": pheno, "snps": json.dumps(snps),
                      "note": " ".join(x for x in (note, CAVEATS.get(gene),
                                                    f"Not read: {', '.join(missing)}." if missing else None) if x),
                      "typical": typical, "imputed": any(s["confidence"] == "high" for s in snps), "ancestry": across})

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
            drugs.append({**base, "genotype": m["Genotype/Allele"], "confidence": conf, "status": status,
                          "text": m["Annotation Text"], "freq": minor_freq(freqs.get(var), major.get(var))})
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

    # ClinVar's drug-response classifications: each names a variant allele and the response it bears on
    for rsid, entries in clinvar.items():
        c = calls.get(rsid)
        if not c:
            continue
        gt, conf = c
        for e in entries:
            if len(e["alt"]) != 1:
                continue
            n = gt.count(e["alt"])
            if conf == "not_excluded":
                status = "not_excluded"
            elif rsid in major:
                status = "typical" if sort_gt(gt) == major[rsid] * 2 else "differs"
            else:
                status = "differs" if n else "typical"
            drugs.append({"id": f"clinvar:{e['id']}", "drug": e["drug"], "gene": e["gene"], "variant": rsid,
                          "level": "ClinVar", "expert": e["expert"], "category": "ClinVar drug response",
                          "condition": e["condition"], "url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{e['id']}/",
                          "pmids": 0, "genotype": gt, "confidence": conf, "status": status,
                          "text": f"ClinVar classes {e['ref']}>{e['alt']} in {e['gene']} as bearing on {e['condition']} "
                                  f"({e['review']}). {{who}} carries {n} {'copy' if n == 1 else 'copies'} of {e['alt']}.",
                          "freq": allele_freq(freqs.get(rsid), e["alt"]) and json.dumps(
                              {"allele": e["alt"], **allele_freq(freqs.get(rsid), e["alt"])})})

    guidance = build_guidance(person_types(genes, star, calls, major))
    return genes, drugs, guidance


def minor_freq(site, major_allele):
    """JSON {allele, AFR..SAS} for the allele fewer Europeans carry, or None."""
    if not site or not major_allele:
        return None
    other = site["alt"] if major_allele == site["ref"] else site["ref"]
    return json.dumps({"allele": other, **allele_freq(site, other)})


def clinvar_drug_response():
    """{rsid: [{id, ref, alt, gene, condition, drug, review, expert}]} for germline ClinVar 'drug response' entries."""
    out = defaultdict(list)
    with gzip.open(CLINVAR, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[0] == "#" or "drug_response" not in line:
                continue
            p = line.rstrip("\n").split("\t")
            info = dict(x.split("=", 1) for x in p[7].split(";") if "=" in x)
            if "drug_response" not in info.get("CLNSIG", "") or "RS" not in info:
                continue
            if not int(info.get("ORIGIN", "1")) & 1:
                continue  # somatic only: about tumours, not the person's own genome
            if p[4] not in ("A", "C", "G", "T"):
                continue
            names = [n.replace("_", " ").strip() for n in info.get("CLNDN", "").split("|") if n not in ("", "not_provided", "not_specified")]
            # One entry can list diseases too (F5 Leiden): the drug part is the name with "response" in it
            drug_names = [n for n in names if re.search(r"response|toxicity", n, re.I)] or names
            condition = "; ".join(drug_names) or "drug response"
            m = re.match(r"(.+?)\s+(?:response|toxicity|sensitivity|resistance|dose|metabolism|hypersensitivity)\b",
                         drug_names[0], re.I) if drug_names else None
            review = info.get("CLNREVSTAT", "").replace("_", " ")
            out["rs" + info["RS"]].append({
                "id": p[2], "ref": p[3], "alt": p[4], "gene": info.get("GENEINFO", "").split(":")[0],
                "condition": condition, "drug": (m.group(1) if m else condition).lower(),
                "review": review, "expert": bool(re.search(r"expert panel|practice guideline", review))})
    return out


# Single-SNP genes the guidelines name by genotype (VKORC1 -1639G>A for warfarin)
SNP_GENES = {"VKORC1": "rs9923231", "ABCG2": "rs2231142"}
CPIC_WORD = {"Poor": "Poor Metabolizer", "Intermediate": "Intermediate Metabolizer", "Normal": "Normal Metabolizer",
             "Rapid": "Rapid Metabolizer", "Ultrarapid": "Ultrarapid Metabolizer"}
ABBR = {"Poor": "PM", "Intermediate": "IM", "Normal": "NM", "Rapid": "RM", "Ultrarapid": "UM"}


def person_types(genes, star, calls, major):
    """{gene: {label, typical, cpic, abbr, score, dip, gt}}: how each guideline gene reads for the person, in the
    vocabularies the guidelines use (CPIC lookup values, DPWG's PM/IM/NM/UM, activity scores, diplotypes)."""
    types = {}
    for g in genes:
        if not g["alleles"]:
            continue
        pheno, word = g["phenotype"], g["phenotype"].split()[0]
        m = re.search(r"activity score ([\d.]+)", pheno)
        score = float(m.group(1)) if m else None
        cpic = CPIC_WORD.get(word)
        if g["gene"] in ("CYP2C9", "DPYD", "CYP2D6") and score is not None:
            cpic = f"{score:.2f}".rstrip("0")
            cpic += "0" if cpic.endswith(".") else ""
        elif g["gene"] == "NAT2":
            cpic = {"Slow": "Poor Metabolizer", "Intermediate": "Intermediate Metabolizer", "Rapid": "Rapid Metabolizer"}[word]
        elif g["gene"] == "SLCO1B1":
            cpic = pheno.split(" (")[0].title()
        abbr = ABBR.get(word) or {"Slow": "PM"}.get(word)
        types[g["gene"]] = {"label": f"{g['gene']} {g['alleles']}: {pheno.split(' (')[0].lower()}", "typical": g["typical"],
                            "cpic": cpic, "abbr": abbr, "score": score, "dip": g["alleles"], "gt": None}
    for var, (rsid, allele) in HLA_TAGS.items():
        c = calls.get(rsid)
        if c and c[1] != "not_excluded":
            carried = bool(c[0].count(allele))
            gene, name = var.split("*")
            types[gene] = {"label": f"{var} {'likely present' if carried else 'not detected'} (tag SNP {rsid})",
                           "typical": not carried, "cpic": f"*{name} {'positive' if carried else 'negative'}",
                           "hla": {name.replace(":", ""): carried}, "abbr": None, "score": None, "dip": None, "gt": None}
    for gene, rsid in SNP_GENES.items():
        c = calls.get(rsid)
        if c and c[1] != "not_excluded":
            cpic = None
            if gene == "ABCG2":  # CPIC reads ABCG2 from rs2231142 alone: each T (Gln141Lys) lowers function
                cpic = ("Normal Function", "Decreased Function", "Poor Function")[c[0].count("T")]
            types[gene] = {"label": f"{gene} {rsid} {c[0]}", "typical": rsid in major and sort_gt(c[0]) == major[rsid] * 2,
                           "cpic": cpic, "abbr": None, "score": None, "dip": None, "gt": sort_gt(c[0])}
    # SLCO1B1 c.521T>C is rs4149056 on the forward strand
    c = calls.get("rs4149056")
    if "SLCO1B1" in types and c:
        types["SLCO1B1"]["gt"] = sort_gt(c[0])
    return types


def _text(html):
    import html as h
    return re.sub(r"\s+", " ", h.unescape(re.sub(r"<[^>]+>", " ", html or ""))).strip()


def dpwg_tables(html):
    """[(phenotype cell, description, recommendation)] from the tables in a DPWG guideline annotation."""
    rows = []
    for table in re.findall(r"<table.*?</table>", html or "", re.S):
        head = [_text(x).lower() for x in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
        rec = next((i for i, h in enumerate(head) if "recommend" in h), len(head) - 1)
        desc = next((i for i, h in enumerate(head) if "descr" in h or "implic" in h), None)
        for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) > rec:
                rows.append((_text(cells[0]), _text(cells[desc]) if desc is not None and desc < len(cells) else "", _text(cells[rec])))
    return rows


def dpwg_matches(cell, default_gene, types):
    """Whether a DPWG table row ("CYP2C19 PM", "Activity Score 1.5", "CYP2C9 *1/*3", "SLCO1B1 521 TC",
    "VKORC1 -1639 AA", "HLA-B*5701") describes the person. None when the row can't be judged."""
    if re.search(r"\bother", cell, re.I):
        return None
    m = re.match(r"([A-Z][A-Z0-9-]+)(?=[\s*]|$)", cell)
    looks_gene = m and (m.group(1) in types or re.fullmatch(r"(?:CYP|HLA|SLCO|UGT|NUDT|TPMT|DPYD|VKORC|ABCG|G6PD|NAT)\S*", m.group(1)))
    gene = m.group(1) if looks_gene else default_gene
    if not gene:
        return None
    rest = cell[len(gene):].strip() if cell.startswith(gene) else cell
    t = types.get(gene)
    if gene == "HLA-B":
        h = re.match(r"\*?(\d\d):?(\d\d)", rest)
        if not h or not t or (h.group(1) + h.group(2)) not in t.get("hla", {}):
            return None
        return t["hla"][h.group(1) + h.group(2)] != bool(re.search(r"negative", rest, re.I))
    if not t:
        return None
    if m2 := re.match(r"(PM|IM|NM|UM|RM)\b", rest):
        return t["abbr"] == m2.group(1)
    if m2 := re.match(r"(?:DPD\s+AS|activity score)\s*([\d.]+)", rest, re.I):
        return t["score"] is not None and abs(t["score"] - float(m2.group(1))) < 1e-9
    if m2 := re.match(r"(\*\w+)\s*/\s*(\*\w+)", rest):
        return t["dip"] is not None and sorted(t["dip"].split("/")) == sorted([m2.group(1), m2.group(2)])
    if gene == "SLCO1B1" and (m2 := re.match(r"521\s*([TC]{2})\b", rest)):
        return t["gt"] == sort_gt(m2.group(1))
    if gene == "VKORC1" and (m2 := re.match(r"(?:-1639|rs9923231)\s*([GA]{2})\b", rest)):
        return t["gt"] == sort_gt(m2.group(1).translate(FLIP))  # gene strand; rs9923231 is reported forward
    if gene == "ABCG2" and (m2 := re.search(r"\(([GT]{2}) genotype", rest)):
        return t["gt"] == sort_gt(m2.group(1))
    if gene == "CYP3A5" and re.search(r"expressor", rest, re.I):
        return t["abbr"] == ("NM" if re.search(r"homozyg", rest, re.I) else "IM")
    return None


def build_guidance(types):
    """One row per guideline (CPIC, DPWG, CPNDS, RNPGx ...) and per drug label (FDA, EMA, PMDA, Health Canada,
    Swissmedic), with what applies to the person's types."""
    recs = json.load(open(CPIC_RECS, encoding="utf-8"))
    cpic = defaultdict(list)
    for r in recs:
        cpic[r["drug"]["name"].lower()].append(r)
    rows = []
    z = zipfile.ZipFile(GUIDELINES)
    for name in z.namelist():
        if not name.endswith(".json"):
            continue
        g = json.loads(z.read(name))["guideline"]
        if g.get("cancerGenome"):
            continue
        drugs = [c["name"].lower() for c in g.get("relatedChemicals", [])]
        gl_genes = [x["symbol"] for x in g.get("relatedGenes", [])]
        text = g["name"] + " " + _text((g.get("summaryMarkdown") or {}).get("html"))
        # HLA genes count only for the HLA types the file can tag (HLA-B*57:01); *15:02, *58:01 ... need HLA typing
        known = [x for x in gl_genes if x in types and
                 (not x.startswith("HLA-") or any(re.search(h[:2] + r":?" + h[2:], text) for h in types[x]["hla"]))]
        row = {"kind": "guideline", "id": g["id"], "source": g["source"], "drug": ";".join(drugs), "genes": ";".join(gl_genes),
               "name": g["name"].replace("Annotation of ", ""), "url": f"https://www.clinpgx.org/guidelineAnnotation/{g['id']}",
               "summary": _text((g.get("summaryMarkdown") or {}).get("html")), "testing": None,
               "types": "; ".join(types[x]["label"] for x in known), "recs": "[]"}
        found, tables = [], False
        if g["source"] == "CPIC":
            def fits(k, v):
                if k.startswith("HLA-") and v == "No Result":
                    return not (k in known and v)  # the guideline's HLA type isn't readable here: CPIC's "no result" row
                return k in known and types[k]["cpic"] == v
            for r in (r for d in drugs for r in cpic.get(d, [])):
                key = r["lookupkey"]
                if not set(key) <= set(gl_genes):
                    continue
                tables = True
                if all(fits(k, v) for k, v in key.items()):
                    found.append({"population": r.get("population"), "recommendation": r["drugrecommendation"],
                                  "implication": "; ".join(f"{k}: {v}" for k, v in (r.get("implications") or {}).items()),
                                  "strength": r.get("classification"), "for": "; ".join(f"{k} {v}" for k, v in key.items())})
        elif g["source"] == "DPWG":
            default = gl_genes[0] if len(gl_genes) == 1 else None
            judged = False
            for cell, desc, rec in dpwg_tables((g.get("textMarkdown") or {}).get("html")):
                tables = True
                hit = dpwg_matches(cell, default, {k: types[k] for k in known})
                judged |= hit is not None
                if hit:
                    found.append({"population": None, "recommendation": rec, "implication": desc, "strength": None, "for": cell})
            if not found and judged:
                found.append({"population": None, "recommendation": "No action: DPWG lists recommendations only for the types "
                              "that need one, and yours isn't among them.", "implication": "", "strength": None, "for": None})
        uniq = list({(f["population"], f["recommendation"]): f for f in found}.values())
        row["recs"] = json.dumps(uniq)
        if not known:
            row["status"] = "unreadable"
        elif not tables:
            row["status"] = "summary"  # no recommendation per type (other bodies, or "no action needed" guidelines)
        elif uniq:
            if all(f["for"] is None for f in uniq) or all(types[x]["typical"] for x in known):
                row["status"] = "typical"
            elif all(re.match(r"\s*(no action|none\b|there is no need|initiate therapy with recommended starting dose\.?\s*$)",
                              f["recommendation"], re.I) for f in uniq):
                row["status"] = "no_action"  # the type differs, but the guideline changes nothing
            else:
                row["status"] = "differs"
        else:
            row["status"] = "unclear"  # the person's type isn't one the guideline names, or a gene is only partly read
        rows.append(row)

    zl = zipfile.ZipFile(LABELS)
    for r in csv.DictReader(io.TextIOWrapper(zl.open("drugLabels.tsv"), encoding="utf-8"), delimiter="\t"):
        if r["Cancer Genome"] or r["Testing Level"] in ("", "No Clinical PGx"):
            continue  # tumour testing, or a label that mentions the gene without clinical consequence
        lb_genes = [x.strip() for x in r["Genes"].split(";") if x.strip()]
        known = [x for x in lb_genes if x in types]
        rows.append({"kind": "label", "id": r["PharmGKB ID"], "source": r["Source"],
                     "drug": ";".join(x.strip().lower() for x in r["Chemicals"].split(";")), "genes": ";".join(lb_genes),
                     "name": r["Name"].replace("Annotation of ", ""), "url": f"https://www.clinpgx.org/labelAnnotation/{r['PharmGKB ID']}",
                     "summary": r["Variants/Haplotypes"], "testing": r["Testing Level"],
                     "types": "; ".join(types[x]["label"] for x in known), "recs": "[]",
                     "status": "unreadable" if not known else "typical" if all(types[x]["typical"] for x in known) else "differs"})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dna", default="data/input/MyHeritage_raw_dna_data_XY.csv")
    ap.add_argument("--measured-only", action="store_true", help="use the raw file even when an imputed one exists")
    ap.add_argument("--out-dir", default="data/output/cluster_analysis")
    args = ap.parse_args()
    dna = args.dna if args.measured_only else imputed_path(args.dna)
    genes, drugs, guidance = build(dna)
    os.makedirs(args.out_dir, exist_ok=True)
    who = person_label(dna)
    for row in genes + drugs + guidance:
        row["person"] = who
        if "text" in row:
            row["text"] = row["text"].replace("{who}", who)
    for name, rows in (("med_genes", genes), ("med_drugs", drugs), ("med_guidance", guidance)):
        with open(os.path.join(args.out_dir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
    differs = [d for d in drugs if d["status"] == "differs" and d["level"] in ("1A", "1B")]
    print(f"✅ {who}: {len(genes)} drug genes, {len(drugs)} drug annotations ({len(differs)} guideline-level where {who} differs "
          f"from the typical case) → {args.out_dir}")
    for g in genes:
        print(f"   {g['gene']:8} {g['alleles'] or '-':14} {g['phenotype']}")
    gl = [g for g in guidance if g["kind"] == "guideline"]
    by = Counter((g["source"], g["status"]) for g in gl)
    print(f"   {len(gl)} guidelines: " + ", ".join(f"{s} {st} {n}" for (s, st), n in sorted(by.items()) if s in ("CPIC", "DPWG")))
    lb = Counter(g["status"] for g in guidance if g["kind"] == "label")
    print(f"   {sum(lb.values())} drug labels: {dict(lb)}; ClinVar drug-response rows: {sum(d['level'] == 'ClinVar' for d in drugs)}")


if __name__ == "__main__":
    main()
