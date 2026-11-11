"""The popular sport genes: the SNPs consumer fitness DNA tests report, read in one person, with how strong the evidence
behind each one is.

    python -m cluster_analysis.themes.sport_snps --dna data/input/MyHeritage_raw_dna_data_XY.csv --out-dir <dir>

sport_snps.json only chooses the variants and groups them. Per variant, from the sources:
  * what it changes (Ensembl VEP): the consequence and amino-acid change, and its European frequency;
  * the GWAS Catalog associations at genome-wide significance (p < 5e-8), with the effect allele;
  * ClinVar pathogenic, likely pathogenic or risk-factor records (the local ClinVar file);
  * ClinPGx clinical annotations, levels 1A-3, and the text for the person's genotype;
  * Europe PMC: how many papers name the rsID together with athletes, sport, exercise or training.
Grade, from those (a ClinPGx level 3 annotation is a single study, so it doesn't count):
  A  ClinVar pathogenic or likely pathogenic with review criteria, a genome-wide GWAS association replicated in two or
     more publications, or ClinPGx level 1A-2B
  B  one genome-wide GWAS publication, or a variant that stops or shifts the protein
  C  candidate-gene studies only: none of the above
Writes sport_snps.json (one row per variant, personal: keep out of git).
"""
import argparse
import json
import os
import re
import sys
import urllib.parse

if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cluster_analysis import sources
from genome import build as gbuild
from genome.loader import imputed_path, iter_calls, person_label

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "sport_snps.json")
GENOME_WIDE = 5e-8
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SPORT = "(athlete* OR sport* OR exercise OR training OR \"physical performance\")"
FLIP = str.maketrans("ACGT", "TGCA")
PROTEIN_CHANGE = {"stop_gained", "frameshift_variant", "stop_lost", "start_lost", "splice_donor_variant", "splice_acceptor_variant"}
CLINVAR_STARS = 1
# Ensembl's consequence order, most severe first (the terms these variants can have)
SEVERITY = ["frameshift_variant", "stop_gained", "splice_acceptor_variant", "splice_donor_variant", "stop_lost", "start_lost",
            "inframe_insertion", "inframe_deletion", "missense_variant", "splice_region_variant", "synonymous_variant",
            "5_prime_UTR_variant", "3_prime_UTR_variant", "non_coding_transcript_exon_variant", "intron_variant",
            "NMD_transcript_variant", "non_coding_transcript_variant", "upstream_gene_variant", "downstream_gene_variant",
            "regulatory_region_variant", "intergenic_variant"]
worst = lambda terms: min(terms, key=lambda t: SEVERITY.index(t) if t in SEVERITY else len(SEVERITY)) if terms else None


def papers(rsid):
    """Europe PMC: papers naming the rsID with athletes, sport, exercise or training."""
    def fetch():
        d = sources._request("GET", EUROPE_PMC, params={"query": f'"{rsid}" AND {SPORT}', "format": "json", "pageSize": 1})
        return {"hits": d.get("hitCount", 0)}
    return sources._cached("europepmc_sport", rsid, fetch)["hits"]


def gwas(rsid):
    """Genome-wide associations: [{trait, p, allele, pmid}], strongest per trait, and the publications behind them."""
    best, pubs = {}, set()
    for a in sources._gwas_rows(rsid):
        p = a.get("p_value")
        if p is None or p > GENOME_WIDE:
            continue
        pubs.add(a.get("pubmed_id"))
        allele = ((a.get("snp_effect_allele") or [""])[0] or "").split("-")[-1]
        for t in a.get("efo_traits") or []:
            name = t["efo_trait"]
            if name not in best or p < best[name]["p"]:
                best[name] = {"trait": name, "p": p, "allele": allele if allele in "ACGT" and allele else None, "pmid": a.get("pubmed_id")}
    return sorted(best.values(), key=lambda x: x["p"]), pubs


def copies(gt, allele, alleles):
    """Copies of an allele in a genotype; None when it can't be placed. alleles: the variant's forward-strand alleles
    (Ensembl). The genotype is read on the strand its own letters fit: on a C/G or A/T SNP both strands fit, so only
    the forward strand is used and a C is never read as a flipped G."""
    if not gt or len(gt) != 2 or not allele or not set(gt) <= set("ACGT"):
        return None
    fwd = set(alleles or [])
    if not fwd or set(gt) <= fwd:
        a = allele if allele in fwd or not fwd else allele.translate(FLIP) if allele.translate(FLIP) in fwd else None
        return gt.count(a) if a else None
    flipped = {x.translate(FLIP) for x in fwd}
    if set(gt) <= flipped:
        return gt.count(allele.translate(FLIP)) if allele in fwd else gt.count(allele) if allele in flipped else None
    return None


def build(dna):
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    snps = cfg["snps"]
    ids = [s["rsid"] for s in snps]
    calls = {rs: (gt, tier) for rs, _, _, gt, tier in iter_calls(dna, set(ids), confidence=None)}
    print("Ensembl VEP ...")
    vep = sources.ensembl_vep(ids)
    print("ClinVar ...")
    from cluster_analysis.nutrition.nutrition import clinvar_records
    clinvar = [r for r in clinvar_records({s["gene"] for s in snps}) if r["rsid"] in set(ids)]
    print("ClinPGx ...")
    from cluster_analysis.medicines.medicines import load_annotations, match_genotype, effect, LEVEL_GRADE
    pgx_rows, pgx_texts = load_annotations(("1A", "1B", "2A", "2B", "3"))
    pgx = [r for r in pgx_rows if r["Variant/Haplotypes"] in set(ids)]
    print("GWAS Catalog and Europe PMC ...")
    rows = []
    for s in snps:
        rs, gene = s["rsid"], s["gene"]
        gt, tier = calls.get(rs, (None, None))
        v = vep.get(rs) or {}
        ref = (v.get("alleles") or [None])[0]
        alts = (v.get("alleles") or [])[1:]
        eur = v.get("eur_af") or {}
        # The changed allele: the alternative allele with a European frequency, else the first
        alt = next((a for a in alts if a in eur), alts[0] if alts else None)
        cons = (v.get("allele_consequences") or {}).get(alt) or ([v["consequence"]] if v.get("consequence") else [])
        assoc, pubs = gwas(rs)
        cv = [{"significance": r["significance"], "condition": r["condition"], "stars": r["stars"]} for r in clinvar if r["rsid"] == rs]
        px = []
        for r in pgx:
            if r["Variant/Haplotypes"] != rs:
                continue
            opts = pgx_texts.get(r["Clinical Annotation ID"], [])
            o = match_genotype(gt, opts) if gt else None
            px.append({"level": r["Level of Evidence"], "chemicals": r["Drug(s)"], "phenotype": r.get("Phenotype(s)") or "",
                       "text": o["Annotation Text"] if o else None, "effect": effect(o["Annotation Text"]) if o else None,
                       "url": r["URL"]})
        n_papers = papers(rs)
        if any(c["stars"] >= CLINVAR_STARS and re.match(r"(Likely_)?[Pp]athogenic", c["significance"]) for c in cv) \
                or len(pubs) >= 2 or any(LEVEL_GRADE.get(p["level"]) in ("A+", "A", "B") and p["level"] != "3" for p in px):
            grade = "A"
        elif pubs or PROTEIN_CHANGE & set(cons):
            grade = "B"
        else:
            grade = "C"
        rows.append({
            "gene": gene, "rsid": rs, "topic": s["topic"], "grade": grade,
            "genotype": gt, "confidence": tier,
            "ref": ref, "alt": alt, "alt_copies": copies(gt, alt, v.get("alleles")) if tier in ("measured", "high", "medium") else None,
            "eur_af": round(eur[alt], 3) if alt in eur else None,
            "consequence": worst(cons),
            "amino_acids": (v.get("allele_amino_acids") or {}).get(alt),
            "gwas": json.dumps([{**a, "copies": copies(gt, a["allele"], v.get("alleles"))} for a in assoc[:6]], ensure_ascii=False),
            "gwas_traits": len(assoc), "gwas_pubs": len(pubs),
            "clinvar": json.dumps(cv, ensure_ascii=False), "clinpgx": json.dumps(px, ensure_ascii=False),
            "papers": n_papers,
            # What the person's copies mean in practice (sport_snps.json), where the list gives it
            "meaning": (s.get("meaning") or {}).get(str(copies(gt, alt, v.get("alleles")))) if tier in ("measured", "high", "medium") else None,
            "papers_url": "https://europepmc.org/search?query=" + urllib.parse.quote(f'"{rs}" AND {SPORT}'),
        })
    topics = {t["id"]: t for t in cfg["topics"]}
    for r in rows:
        r["topic_name"] = topics[r["topic"]]["name"]
        r["topic_order"] = list(topics).index(r["topic"])
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dna", default="data/input/MyHeritage_raw_dna_data_XY.csv")
    ap.add_argument("--out-dir", default=gbuild.OUTPUT)
    a = ap.parse_args()
    dna = imputed_path(a.dna)
    rows = build(dna)
    for r in rows:
        r["person"] = person_label(dna)
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, "sport_snps.json")
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    grades = {g: sum(r["grade"] == g for r in rows) for g in "ABC"}
    print(f"wrote {path}: {len(rows)} variants, grades {grades}, {sum(1 for r in rows if r['genotype'])} with a call")


if __name__ == "__main__":
    main()
