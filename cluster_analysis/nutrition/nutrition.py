"""Nutrition: where a person's genes act on how the body takes up, carries and converts each nutrient.

    python -m cluster_analysis.nutrition.nutrition                                  # XY (imputed file when there is one)
    python -m cluster_analysis.nutrition.nutrition --dna data/input/X.csv --sex women --age "25–50 år" --activity medium

Per nutrient (cluster_analysis/nutrition/nutrients.json maps each one to the sources' identifiers):
  * Genetic level. For each blood marker of the nutrient (25-hydroxyvitamin D, ferritin, homocysteine ...) a score
    from the variants that set it: a PGS Catalog score where one fits, else the genome-wide significant lead
    variants of one GWAS Catalog study (one study, so the weights share a scale). The person's score is placed
    against 1000 Genomes Europeans from the variants' European frequencies: mean = sum(2pw), variance =
    sum(2p(1-p)w^2). The variants are independent (pruned or one per locus), so no LD term is needed. Missing
    variants count at the population mean, and the coverage is reported.
  * Findings, each with an evidence grade:
      A+  ClinVar pathogenic or likely pathogenic, reviewed by an expert panel or a practice guideline (3-4 stars)
      A   ClinVar with criteria from several submitters (2 stars), or a GWAS variant genome-wide significant for
          the nutrient's markers in 2+ publications, all in the same direction
      B   ClinVar with one submitter's criteria, or a GWAS variant from one publication
      C   ClinPGx (PharmGKB) gene x nutrient annotations (level 3: single studies)
  * Mechanism (nutrient_steps.py): the nutrient's Reactome pathways as ordered steps (uptake, transport,
    activation, use), where each happens, and each finding pinned to the step whose gene it acts on, with how:
    a protein change (Ensembl VEP), a change in how much of the gene is made (GTEx), or in the gene, effect unknown.
  * Intake: NNR 2023 RI or AI, and UL, for the person's sex and age (cluster_analysis/nutrition/nnr_2023.json), as context.

Writes to data/output/cluster_analysis/ (personal: keep out of git):
  nut_nutrients.json  one row per nutrient: intake target, the markers' scores, the blood test, counts
  nut_findings.json   one row per finding: grade, gene, variant, the person's genotype, which way it moves the
                      level for them, and its mechanism and step gene
  nut_steps.json      one row per conversion step: pathway, order, name, where in the cell, genes and where in the
                      body they are made
Reference data: python -m cluster_analysis.nutrition.nutrition_reference nnr | pgs (once).
"""
import argparse
import csv
import gzip
import io
import json
import math
import os
import re
import sys
import zipfile
from collections import defaultdict

if not __package__:  # run as a file (python cluster_analysis/nutrition/nutrition.py, an editor's Run button): import from the repo root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from genome import build as gbuild
from genome.loader import imputed_path, iter_calls, person_label

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "nutrients.json")
NNR = os.path.join(HERE, "nnr_2023.json")
REF = "data/reference"
PGS_DIR = f"{REF}/nutrition/pgs"
GWAS = f"{REF}/gwas_associations_ontology.zip"
CLINVAR = gbuild.path("clinvar")
CLINPGX = f"{REF}/clinpgx_clinical_annotations.zip"
REACTOME = f"{REF}/Ensembl2Reactome.txt"
GTF = gbuild.path("gtf")
SITES = gbuild.sites()
OUT = gbuild.OUTPUT
GWS = 5e-8
LOCUS = 500_000                    # one lead variant per 500 kb
MIN_N = 10_000                     # a GWAS study smaller than this doesn't make a score (its findings still show)
SCORE_TIERS = ("measured", "high", "medium")
FINDING_TIERS = ("measured", "high")
FLIP = str.maketrans("ACGT", "TGCA")
STARS = {"practice_guideline": 4, "reviewed_by_expert_panel": 3, "criteria_provided,_multiple_submitters,_no_conflicts": 2,
         "criteria_provided,_single_submitter": 1}
def is_palindromic(a, b):
    return {a, b} in ({"A", "T"}, {"C", "G"})


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def sample_size(text):
    return sum(int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", text or ""))


# --- Sources ----------------------------------------------------------------------------------------------------------

def gwas_rows(trait_ids):
    """GWAS Catalog associations of the given traits at genome-wide significance, one per SNP and study, with the
    effect allele and a signed beta when the study gives one."""
    out = []
    with zipfile.ZipFile(GWAS) as z:
        name = next(n for n in z.namelist() if n.endswith((".tsv", ".txt")))
        for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace"), delimiter="\t"):
            uris = {u.rsplit("/", 1)[-1] for u in (r["MAPPED_TRAIT_URI"] or "").split(",")}
            hit = uris & trait_ids
            if not hit or len(uris) > 1:  # single-trait associations only (not "X, COVID-19")
                continue
            try:
                p = float(r["P-VALUE"] or 1)
            except ValueError:
                continue
            snp = (r["STRONGEST SNP-RISK ALLELE"] or "").strip()
            m = re.fullmatch(r"(rs\d+)-([ACGT])", snp)
            if p > GWS or not m:
                continue
            ci = (r["95% CI (TEXT)"] or "").lower()
            try:
                size = float(r["OR or BETA"])
            except ValueError:
                size = None
            sign = 1 if "increase" in ci else -1 if "decrease" in ci else None
            try:
                raf = float(r["RISK ALLELE FREQUENCY"])
            except ValueError:
                raf = None
            out.append({"trait": hit.pop(), "rsid": m.group(1), "allele": m.group(2), "p": p,
                        "beta": size * sign if size is not None and sign else None, "raf": raf,
                        "study": r["STUDY ACCESSION"], "pmid": r["PUBMEDID"], "author": r["FIRST AUTHOR"],
                        "year": r["DATE"][:4], "sample": r["INITIAL SAMPLE SIZE"], "gene": r["MAPPED_GENE"],
                        "chrom": r["CHR_ID"], "pos38": int(r["CHR_POS"]) if (r["CHR_POS"] or "").isdigit() else None})
    return out


def pgs_rows(pgs_id):
    path = f"{PGS_DIR}/{pgs_id}_{gbuild.pgs_suffix()}.txt.gz"
    meta = json.load(open(f"{PGS_DIR}/{pgs_id}.json", encoding="utf-8"))
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for r in csv.DictReader((l for l in f if not l.startswith("#")), delimiter="\t"):
            rs = r.get("hm_rsID") or r.get("rsID")
            if not rs or not rs.startswith("rs") or not r.get("hm_pos"):
                continue
            rows.append({"rsid": rs, "allele": r["effect_allele"], "other": r.get("other_allele") or r.get("hm_inferOtherAllele"),
                         "weight": float(r["effect_weight"]), "chrom": r["hm_chr"], "pos": int(r["hm_pos"]),
                         "gene": r.get("locus_name") or ""})
    pub = meta.get("publication") or {}
    dev = meta.get("samples_variants") or []
    return rows, {"source": f"PGS Catalog {pgs_id}", "id": pgs_id, "author": pub.get("firstauthor"),
                  "year": (pub.get("date_publication") or "")[:4], "pmid": pub.get("PMID"),
                  "n": sum(x.get("sample_number") or 0 for x in dev), "method": meta.get("method_name"),
                  "variants": meta.get("variants_number")}


def reactome_genes(pathway_ids):
    """{pathway id: (name, [gene symbols])} from Ensembl2Reactome and the Ensembl GTF."""
    ens, names = defaultdict(set), {}
    with open(REACTOME, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) > 3 and p[1] in pathway_ids and p[0].startswith("ENSG"):
                ens[p[1]].add(p[0].split(".")[0])
                names[p[1]] = p[3]
    want = set().union(*ens.values()) if ens else set()
    symbol = {}
    with gzip.open(GTF, "rt", encoding="utf-8") as f:
        for line in f:
            if line[0] == "#" or "\tgene\t" not in line:
                continue
            m = re.search(r'gene_id "([^"]+)".*?gene_name "([^"]+)"', line)
            if m and m.group(1) in want:
                symbol[m.group(1)] = m.group(2)
    return {pid: (names[pid], sorted({symbol[e] for e in ens[pid] if e in symbol})) for pid in ens}


def clinvar_records(genes):
    """ClinVar pathogenic, likely pathogenic and risk-factor records in the given genes:
    [{rsid, gene, ref, alt, significance, condition, stars}]."""
    out = []
    with gzip.open(CLINVAR, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.rstrip("\n").split("\t")
            info = dict(x.split("=", 1) for x in p[7].split(";") if "=" in x)
            gene_info = {g.split(":")[0] for g in info.get("GENEINFO", "").split("|")}
            if not gene_info & genes or "RS" not in info:
                continue
            sig = info.get("CLNSIG", "")
            if not re.search(r"^(Pathogenic|Likely_pathogenic|Pathogenic/Likely_pathogenic|risk_factor)", sig) or "onflicting" in sig:
                continue
            out.append({"rsid": "rs" + info["RS"], "gene": sorted(gene_info & genes)[0], "ref": p[3], "alt": p[4],
                        "significance": sig.replace("_", " "), "condition": info.get("CLNDN", "").replace("_", " "),
                        "stars": STARS.get(info.get("CLNREVSTAT", ""), 0)})
    return out


def clinpgx_rows(chemicals):
    from cluster_analysis.medicines.medicines import load_annotations
    rows, texts = load_annotations(("1A", "1B", "2A", "2B", "3"))
    keep = []
    for r in rows:
        chems = {c.strip().lower() for c in r["Drug(s)"].split(";")}
        hit = chems & chemicals
        if hit and re.fullmatch(r"rs\d+", r["Variant/Haplotypes"]):
            keep.append((hit, r, texts.get(r["Clinical Annotation ID"], [])))
    return keep


def nearest_genes(positions, reach=100_000):
    """{(chrom, pos): symbol} of the protein-coding gene containing each position, else the nearest within reach."""
    by = defaultdict(list)
    with gzip.open(GTF, "rt", encoding="utf-8") as f:
        for line in f:
            if line[0] == "#" or "\tgene\t" not in line or 'gene_biotype "protein_coding"' not in line:
                continue
            p = line.split("\t", 9)
            m = re.search(r'gene_name "([^"]+)"', p[8])
            if m:
                by[p[0]].append((int(p[3]), int(p[4]), m.group(1)))
    out = {}
    for chrom, pos in positions:
        best = min(((0 if s <= pos <= e else min(abs(pos - s), abs(pos - e)), g) for s, e, g in by.get(chrom, [])), default=None)
        if best and best[0] <= reach:
            out[(chrom, pos)] = best[1]
    return out


def panel_sites(positions):
    """{(chrom, pos): (ref, alt, EUR alt frequency)} from the 1000 Genomes site list, for biallelic SNPs."""
    out = {}
    with gzip.open(SITES, "rt") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.split("\t", 8)
            key = (p[0], int(p[1]))
            if key not in positions or len(p[3]) != 1 or len(p[4]) != 1:
                continue
            m = re.search(r"(?:^|;)EUR_AF=([\d.e-]+)", p[7])
            if m:
                out[key] = (p[3], p[4], float(m.group(1)))
    return out


# --- Alignment and scores -------------------------------------------------------------------------------------------

def align(allele, site, raf=None, other=None, trusted=False):
    """The effect allele on the forward strand and its European frequency, or None when it can't be placed.

    PGS harmonised files are on the forward strand already (trusted). GWAS Catalog alleles usually are too; a
    palindromic SNP (A/T, C/G) is only kept when the study's allele frequency settles the strand."""
    if not site:
        return None
    ref, alt, af = site
    pal = is_palindromic(ref, alt)
    if allele in (ref, alt) and (not pal or trusted):
        a = allele
    elif allele.translate(FLIP) in (ref, alt) and not pal:
        a = allele.translate(FLIP)
    elif pal and raf is not None:
        f = af if allele == alt else 1 - af
        if abs(af - 0.5) < 0.1 or abs(f - raf) > 0.15:
            return None
        a = allele
    else:
        return None
    if other and other not in (ref, alt) and other.translate(FLIP) not in (ref, alt):
        return None
    return a, (af if a == alt else 1 - af), ref, alt


def dosage(call, allele, ref, alt):
    gt, tier = call
    if len(gt) != 2 or not set(gt) <= {ref, alt}:
        return None, tier
    return gt.count(allele), tier


def score(variants, calls):
    """Score, z and percentile against Europeans, from aligned variants [{allele, freq, weight, rsid, ref, alt}]."""
    s = mean = var = 0.0
    used, parts = 0, []
    for v in variants:
        w, f = v["weight"], v["freq"]
        mean += 2 * f * w
        var += 2 * f * (1 - f) * w * w
        d, tier = dosage(calls[v["rsid"]], v["allele"], v["ref"], v["alt"]) if v["rsid"] in calls else (None, None)
        if d is not None and tier in SCORE_TIERS:
            s += d * w
            used += 1
            parts.append((w * (d - 2 * f), v, d))
        else:
            s += 2 * f * w
    if var <= 0:
        return None
    sd = math.sqrt(var)
    z = (s - mean) / sd
    # The variants that move the person furthest from the average, in the score's standard deviations
    top = [{"rsid": v["rsid"], "gene": v.get("gene") or "", "allele": v["allele"], "copies": d, "freq": round(v["freq"], 3),
            "raises": v["weight"] > 0, "shift": round(c / sd, 2)} for c, v, d in sorted(parts, key=lambda x: -abs(x[0]))[:8]]
    return {"z": round(z, 2), "percentile": round(100 * phi(z)), "used": used, "variants": len(variants), "top": top}


def clump(rows, key_p="p"):
    """One row per 500 kb: the strongest."""
    kept = []
    for r in sorted(rows, key=lambda r: r[key_p]):
        if r.get("pos38") is None:
            continue
        if all(not (k["chrom"] == r["chrom"] and abs(k["pos38"] - r["pos38"]) < LOCUS) for k in kept):
            kept.append(r)
    return kept


def anchor_study(rows):
    """The study whose lead variants make the score: European, most lead variants with a signed beta, then largest."""
    by = defaultdict(list)
    for r in rows:
        if r["beta"] is not None and sample_size(r["sample"]) >= MIN_N:
            by[r["study"]].append(r)
    if not by:
        return None, []
    best = max(by, key=lambda s: ("European" in by[s][0]["sample"] and not re.search(r"African|Asian|Hispanic|Latin", by[s][0]["sample"]),
                                  len(clump(by[s])), sample_size(by[s][0]["sample"])))
    return best, clump(by[best])


# --- Build ----------------------------------------------------------------------------------------------------------

def target_for(nnr, key, sex, age, activity):
    """{kind, value, unit, ul, notes} for the person's group; n-3 from E% and the reference energy intake."""
    if key == "n-3":
        mj = nnr["energy_mj"][sex][age][activity]
        g = lambda e: round(e / 100 * mj * 1000 / nnr["kj_per_g_fat"], 1)
        fats = nnr["fats_energy_percent"]
        return {"kind": "RI", "value": g(fats["n-3"]["min_e"]), "unit": "g", "min_e": fats["n-3"]["min_e"],
                "ala": g(fats["ALA"]["min_e"]), "energy_mj": mj,
                "notes": [{"applies": "all", "text": fats["n-3"]["quote"]}, {"applies": "all", "text": fats["ALA"]["quote"]}]}
    d = nnr["nutrients"].get(key)
    if not d:
        return None
    notes = [n for n in d.get("notes", []) if n["applies"] in ("all", sex, age)]
    return {"kind": d["kind"], "value": d[sex][age], "unit": d["unit"], "ul": d.get("ul"), "notes": notes}


def build(dna, sex, age, activity, config=CONFIG):
    """config: nutrients.json (the Nutrition tab) or labtests.json (the Biomarkers tab: lab tests in the same shape,
    without intake targets; an entry with "sex" is for that sex only)."""
    data = json.load(open(config, encoding="utf-8"))
    cfg = [n for n in data.get("nutrients") or data.get("tests")
           if not n.get("sex") or n["sex"] == {"men": "male", "women": "female"}.get(sex, sex)]
    for n in cfg:
        for k, v in (("nnr", None), ("clinvar", ""), ("clinpgx", []), ("reactome", []), ("test", ""), ("sv", n["name"])):
            n.setdefault(k, v)
    nnr = json.load(open(NNR, encoding="utf-8"))
    trait_ids = {t for n in cfg for m in n["markers"] for t in m["traits"]}
    print("GWAS Catalog associations...")
    gwas = gwas_rows(trait_ids)
    pgs = {m["pgs"]: pgs_rows(m["pgs"]) for n in cfg for m in n["markers"] if m.get("pgs")}
    print("Reactome pathways...")
    pathways = reactome_genes({p for n in cfg for p in n["reactome"]})
    genes_of = {n["id"]: {g for p in n["reactome"] if p in pathways for g in pathways[p][1]} for n in cfg}
    print("ClinVar...")
    clinvar = [r for r in clinvar_records(set().union(*genes_of.values()))]
    print("ClinPGx...")
    pgx = clinpgx_rows({c for n in cfg for c in n["clinpgx"]})

    rsids = {r["rsid"] for r in gwas} | {r["rsid"] for rows, _ in pgs.values() for r in rows} | \
            {r["rsid"] for r in clinvar} | {r["Variant/Haplotypes"] for _, r, _ in pgx}
    print(f"Reading {len(rsids)} SNPs from {os.path.basename(dna)}...")
    calls, where = {}, {}
    for rsid, chrom, pos, gt, tier in iter_calls(dna, rsids, confidence=None):
        calls[rsid] = (gt, tier)
        where[rsid] = (chrom, pos)
    print("1000 Genomes alleles and European frequencies...")
    sites = panel_sites({(c, p) for c, p in where.values() if p} | {(r["chrom"], r["pos"]) for rows, _ in pgs.values() for r in rows})
    site_of = lambda rs: sites.get(where.get(rs, (None, None)))
    unnamed = {(r["chrom"], r["pos"]) for rows, _ in pgs.values() for r in rows if not r["gene"]}
    if unnamed:
        names = nearest_genes(unnamed)
        for rows, _ in pgs.values():
            for r in rows:
                r["gene"] = r["gene"] or names.get((r["chrom"], r["pos"]), "")

    nutrients, findings = [], []
    for n in cfg:
        target = target_for(nnr, n["nnr"], sex, age, activity) if n["nnr"] else None
        markers = []
        for m in n["markers"]:
            rows = [r for r in gwas if r["trait"] in m["traits"]]
            # The score
            if m.get("pgs"):
                prow, info = pgs[m["pgs"]]
                variants = []
                for r in prow:
                    a = align(r["allele"], sites.get((r["chrom"], r["pos"])), other=r["other"], trusted=True)
                    if a:
                        variants.append({"rsid": r["rsid"], "allele": a[0], "freq": a[1], "ref": a[2], "alt": a[3],
                                         "weight": r["weight"] if a[0] == r["allele"] or a[0] == r["allele"].translate(FLIP) else -r["weight"],
                                         "gene": r["gene"]})
                    else:
                        variants.append(None)
                placed = [v for v in variants if v]
                sc = score(placed, calls)
                if sc:
                    sc["variants"] = len(prow)
                    sc["placed"] = len(placed)
                info = {**info, "kind": "pgs"}
            else:
                study, leads = anchor_study(rows)
                placed = []
                for r in leads:
                    a = align(r["allele"], site_of(r["rsid"]), raf=r["raf"])
                    if a:
                        placed.append({"rsid": r["rsid"], "allele": a[0], "freq": a[1], "ref": a[2], "alt": a[3], "weight": r["beta"],
                                       "gene": r["gene"]})
                sc = score(placed, calls) if len(placed) >= 3 else None
                if sc:
                    sc["variants"] = len(leads)
                    sc["placed"] = len(placed)
                first = leads[0] if leads else {}
                info = {"kind": "gwas", "source": f"GWAS Catalog {study}" if study else None, "id": study,
                        "author": first.get("author"), "year": first.get("year"), "pmid": first.get("pmid"),
                        "n": sample_size(first.get("sample")), "sample": first.get("sample")}
            markers.append({"id": m["id"], "name": m["name"], "higher": m["higher"], "score": sc, "source": info,
                            "studies": len({r["pmid"] for r in rows})})

            # Findings: one lead variant per locus, graded by replication
            by_rs = defaultdict(list)
            for r in rows:
                by_rs[r["rsid"]].append(r)
            leads = clump([min(v, key=lambda r: r["p"]) for v in by_rs.values()])
            for lead in leads:
                rs = lead["rsid"]
                a = align(lead["allele"], site_of(rs), raf=lead["raf"])
                if not a:
                    continue
                allele, freq, ref, alt = a
                # Which way each study says this allele moves the marker
                signs = defaultdict(set)
                for r in by_rs[rs]:
                    if r["beta"] is None:
                        continue
                    ra = align(r["allele"], site_of(rs), raf=r["raf"])
                    if ra:
                        signs[r["pmid"]].add((1 if r["beta"] > 0 else -1) * (1 if ra[0] == allele else -1))
                agree = {pm for pm, s in signs.items() if s == {1}} if lead["beta"] is None or lead["beta"] > 0 else \
                        {pm for pm, s in signs.items() if s == {-1}}
                against = {pm for pm, s in signs.items() if pm not in agree}
                pubs = {r["pmid"] for r in by_rs[rs]}
                grade = "A" if len(agree) >= 2 and not against else "B"
                call = calls.get(rs)
                copies = dosage(call, allele, ref, alt)[0] if call else None
                if lead["beta"] is None and not agree:
                    continue  # no direction known: nothing to tell
                up = (lead["beta"] or (1 if agree else 0)) > 0
                findings.append({
                    "nutrient": n["id"], "marker": m["id"], "marker_name": m["name"], "higher": m["higher"], "kind": "GWAS",
                    "grade": grade, "gene": lead["gene"], "rsid": rs, "genotype": call[0] if call else None,
                    "confidence": call[1] if call else None, "allele": allele, "allele_freq": round(freq, 3),
                    "copies": copies if call and call[1] in FINDING_TIERS else None,
                    "direction": "raises" if up else "lowers", "beta": abs(lead["beta"]) if lead["beta"] is not None else None,
                    "p": lead["p"], "publications": len(pubs), "agree": len(agree), "against": len(against),
                    "pmid": lead["pmid"], "study": f"{lead['author']} {lead['year']}", "text": None})

        # The variants that drive each score, where the findings lack them (a PGS weights variants the GWAS lead list
        # doesn't name: the rare FADS2 variants behind the omega-3 score)
        have = {f["rsid"] for f in findings if f["nutrient"] == n["id"]}
        for mk in markers:
            for t in (mk["score"] or {}).get("top", []):
                if t["rsid"] in have:
                    continue
                have.add(t["rsid"])
                call, src = calls.get(t["rsid"]), mk["source"]
                findings.append({
                    "nutrient": n["id"], "marker": mk["id"], "marker_name": mk["name"], "higher": mk["higher"], "kind": "Score",
                    "grade": "B", "gene": t["gene"], "rsid": t["rsid"], "genotype": call[0] if call else None,
                    "confidence": call[1] if call else None, "allele": t["allele"], "allele_freq": t["freq"], "copies": t["copies"],
                    "direction": "raises" if t["raises"] else "lowers", "beta": None, "p": None, "publications": 1,
                    "agree": 0, "against": 0, "pmid": src.get("pmid"), "study": f"{src.get('author')} {src.get('year')}", "text": None})

        # ClinVar in the nutrient's genes, for its conditions
        cond = re.compile(n["clinvar"], re.I) if n["clinvar"] else None
        merged = {}
        for c in clinvar:
            if c["gene"] not in genes_of[n["id"]] or not cond or not cond.search(c["condition"]):
                continue
            call = calls.get(c["rsid"])
            if not call or call[1] not in FINDING_TIERS:
                continue
            copies = sum(call[0].count(a) for a in c["alt"].split(",") if len(a) == 1)
            if not copies or len(c["ref"]) != 1:
                continue
            k = (c["rsid"], c["alt"])
            if k in merged:
                merged[k]["stars"] = max(merged[k]["stars"], c["stars"])
                continue
            merged[k] = {**c, "genotype": call[0], "confidence": call[1], "copies": copies}
        for c in merged.values():
            findings.append({"nutrient": n["id"], "marker": None, "kind": "ClinVar",
                             "grade": "A+" if c["stars"] >= 3 else "A" if c["stars"] == 2 else "B" if c["stars"] == 1 else "C",
                             "gene": c["gene"], "rsid": c["rsid"], "genotype": c["genotype"], "confidence": c["confidence"],
                             "allele": c["alt"], "copies": c["copies"], "direction": None, "p": None,
                             "text": f"{c['significance']}: {c['condition']}", "stars": c["stars"]})

        # ClinPGx gene x nutrient annotations
        from cluster_analysis.medicines.medicines import match_genotype, effect, LEVEL_GRADE
        for hit, r, opts in pgx:
            if not hit & set(n["clinpgx"]):
                continue
            rs = r["Variant/Haplotypes"]
            call = calls.get(rs)
            if not call or call[1] not in FINDING_TIERS:
                continue
            o = match_genotype(call[0], opts)
            findings.append({"nutrient": n["id"], "marker": None, "kind": "ClinPGx", "grade": LEVEL_GRADE.get(r["Level of Evidence"], "C"),
                             "gene": r["Gene"], "rsid": rs, "genotype": call[0], "confidence": call[1], "allele": None,
                             "copies": None, "direction": None, "p": None, "chemical": r["Drug(s)"],
                             "effect": effect(o["Annotation Text"]) if o else None,
                             "text": o["Annotation Text"] if o else None, "url": r["URL"],
                             "pmids": int(r["PMID Count"] or 0)})

        mine = [f for f in findings if f["nutrient"] == n["id"]]
        # Notes on genes that move a test (labtests.json): each cites the GWAS Catalog study with the strongest
        # association between the gene and one of the test's markers
        traits_n = {t for m in n["markers"] for t in m["traits"]}
        notes = []
        for note in n.get("notes") or []:
            hits = [r for r in gwas if r["trait"] in traits_n and note["gene"] in re.split(r"[\s,;-]+", r["gene"] or "")]
            best = min(hits, key=lambda r: r["p"]) if hits else None
            notes.append({**note, "source": {k: best[k] for k in ("study", "pmid", "author", "year", "p", "rsid")} if best else None})
        nutrients.append({"id": n["id"], "name": n["name"], "sv": n["sv"], "group": n.get("group"),
                          "notes": json.dumps(notes, ensure_ascii=False),
                          "target": json.dumps(target, ensure_ascii=False),
                          "markers": json.dumps(markers, ensure_ascii=False), "test": n["test"] or None,
                          "findings": len(mine), "strong": sum(f["grade"] in ("A+", "A") for f in mine),
                          "genes": len(genes_of[n["id"]])})
    # Which way each GWAS finding moves the level for this person, against the European average:
    # (copies - 2p) of the effect allele, signed by its direction
    for f in findings:
        if f["kind"] in ("GWAS", "Score") and f["copies"] is not None:
            d = (f["copies"] - 2 * f["allele_freq"]) * (1 if f["direction"] == "raises" else -1)
            f["shift"] = round(d, 2)
            f["xy"] = "raises" if d >= 0.5 else "lowers" if d <= -0.5 else "typical"
        elif f["kind"] == "ClinVar":
            f["xy"] = "carried"

    # Mechanism: the conversion steps, and each finding pinned to the step gene it acts on
    print("Conversion steps (Reactome) ...")
    from cluster_analysis.nutrition import nutrient_steps
    steps = nutrient_steps.build_steps(cfg, {pid: name for pid, (name, _) in pathways.items()})
    nutrient_steps.annotate(findings, steps, where)
    tissue = nutrient_steps.tissues({g for st in steps.values() for s in st for g in s["genes"]})
    step_rows = []
    for nid, st in steps.items():
        for s in st:
            step_rows.append({"nutrient": nid, **{k: v for k, v in s.items() if k not in ("where", "genes", "inputs", "outputs")},
                              "where": ", ".join(s["where"]), "genes": " ".join(s["genes"]),
                              "inputs": "; ".join(s["inputs"]), "outputs": "; ".join(s["outputs"]),
                              "tissues": json.dumps({g: tissue.get(g) for g in s["genes"]}, ensure_ascii=False),
                              "summary": nutrient_steps.summary(s["step"])})
    # The mechanism in writing: Reactome's summary of each pathway, UniProt's account of each protein a variant acts on
    print("Pathway summaries (Reactome) and protein functions (UniProt) ...")
    proteins = nutrient_steps.protein_function({f["step_gene"] for f in findings if f.get("step_gene")})
    for row in nutrients:
        cfg_n = next(n for n in cfg if n["id"] == row["id"])
        row["pathways"] = json.dumps([{"id": pid, "name": pathways[pid][0], "summary": nutrient_steps.summary(pid),
                                       "filtered": bool(cfg_n.get("molecules"))}
                                      for pid in cfg_n["reactome"] if pid in pathways
                                      and any(x["pathway_id"] == pid for x in steps[row["id"]])], ensure_ascii=False)
        row["proteins"] = json.dumps({g: proteins[g] for g in sorted({f["step_gene"] for f in findings
                                      if f["nutrient"] == row["id"] and f.get("step_gene")}) if g in proteins}, ensure_ascii=False)
    for f in findings:
        if f.get("detail") is not None:
            f["detail"] = json.dumps(f["detail"], ensure_ascii=False)
    meta = {"person": person_label(dna), "sex": sex, "age": age, "activity": activity, "nnr": nnr["source"]}
    return nutrients, findings, step_rows, meta


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dna", default="data/input/MyHeritage_raw_dna_data_XY.csv")
    ap.add_argument("--sex", choices=("men", "women"), default="men")
    ap.add_argument("--age", default="25–50 år", help="NNR age group: 18–24 år, 25–50 år, 51–70 år, > 70 år")
    ap.add_argument("--activity", choices=("low", "medium", "active"), default="medium",
                    help="NNR physical activity level for energy (PAL 1.4, 1.6, 1.8); sets the omega-3 target in grams")
    ap.add_argument("--out-dir", default=OUT)
    ap.add_argument("--config", default=CONFIG, help="nutrients.json (default) or labtests.json")
    ap.add_argument("--prefix", default="nut", help="dataset name prefix: nut (Nutrition) or lab (Biomarkers)")
    a = ap.parse_args()
    dna = imputed_path(a.dna)
    nutrients, findings, steps, meta = build(dna, a.sex, a.age, a.activity, a.config)
    os.makedirs(a.out_dir, exist_ok=True)
    first = "nut_nutrients" if a.prefix == "nut" else f"{a.prefix}_tests"
    for name, rows in ((first, nutrients), (f"{a.prefix}_findings", findings), (f"{a.prefix}_steps", steps)):
        for r in rows:
            r.setdefault("person", meta["person"])
            if name == first:
                r.update(sex=meta["sex"], age=meta["age"], activity=meta["activity"])
        json.dump(rows, open(f"{a.out_dir}/{name}.json", "w", encoding="utf-8"), ensure_ascii=False)
        print(f"wrote {a.out_dir}/{name}.json: {len(rows)} rows")
    json.dump(meta, open(f"{a.out_dir}/{a.prefix}_meta.json", "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
