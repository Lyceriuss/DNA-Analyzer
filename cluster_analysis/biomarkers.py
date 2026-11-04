# cluster_analysis/biomarkers.py
"""
Links library SNPs and modules to measurable biomarkers (standard lab tests) via the GWAS Catalog.

    python -m cluster_analysis.biomarkers

For every library rsID, the strongest genome-wide significant association (p < 5e-8) with each
biomarker is kept, with its effect allele aligned to the forward strand (Ensembl alleles) and a
direction (+ raises, - lowers). Public data only; writes cluster_analysis/biomarkers.json.
Person-level "genetic tilt" is computed offline in overlay.py.
"""
import json
import os
import re
from collections import defaultdict

from cluster_analysis import sources
from cluster_analysis.build_modules import MODULES_PATH
from cluster_analysis.validate_library import STRAND_VERIFIED, COMPLEMENT

BIOMARKERS_PATH = os.path.join(os.path.dirname(__file__), "biomarkers.json")
GENOME_WIDE = 5e-8

# Standard lab tests and the GWAS Catalog (EFO) trait names that measure them
CATALOG = [
    # panel,          biomarker,             EFO trait regex
    ("Lipids",        "Triglycerides",       r"^triglyceride measurement$"),
    ("Lipids",        "LDL cholesterol",     r"^low density lipoprotein cholesterol measurement$"),
    ("Lipids",        "HDL cholesterol",     r"^high density lipoprotein cholesterol measurement$"),
    ("Lipids",        "Total cholesterol",   r"^total cholesterol measurement$"),
    ("Lipids",        "ApoB",                r"^apolipoprotein B measurement$"),
    ("Lipids",        "Lp(a)",               r"lipoprotein\(a\)|lipoprotein a measurement"),
    ("Glucose",       "HbA1c",               r"^HbA1c measurement$"),
    ("Glucose",       "Fasting glucose",     r"^glucose measurement$|^blood glucose amount$|fasting blood glucose"),
    ("Glucose",       "Insulin",             r"^insulin measurement$|fasting blood insulin"),
    ("Inflammation",  "CRP",                 r"^c-reactive protein measurement$"),
    ("Inflammation",  "White cell count",    r"^leukocyte count$|^white blood cell count$"),
    ("Liver",         "ALT",                 r"alanine aminotransferase"),
    ("Liver",         "AST",                 r"aspartate aminotransferase"),
    ("Liver",         "GGT",                 r"gamma-glutamyl"),
    ("Liver",         "Bilirubin",           r"^bilirubin measurement$|total bilirubin"),
    ("Liver",         "Alkaline phosphatase", r"^alkaline phosphatase measurement$"),
    ("Liver",         "Albumin",             r"^serum albumin amount$|^albumin measurement$"),
    ("Kidney",        "Creatinine",          r"^serum creatinine amount$|^creatinine measurement$"),
    ("Kidney",        "Urea",                r"^blood urea nitrogen amount$"),
    ("Kidney",        "Uric acid",           r"^uric acid measurement$|^urate measurement$"),
    ("Kidney",        "eGFR",                r"glomerular filtration rate"),
    ("Vitamins",      "Vitamin D",           r"^amount of vitamin D$|vitamin D measurement|25-hydroxyvitamin D"),
    ("Vitamins",      "Vitamin B12",         r"vitamin B12|cobalamin"),
    ("Vitamins",      "Folate",              r"^folate measurement$|amount of folic acid"),
    ("Vitamins",      "Homocysteine",        r"^homocysteine measurement$"),
    ("Vitamins",      "Vitamin B6",          r"vitamin B6"),
    ("Blood & iron",  "Ferritin",            r"^ferritin measurement$"),
    ("Blood & iron",  "Serum iron",          r"^serum iron amount$|^iron biomarker measurement$"),
    ("Blood & iron",  "Transferrin saturation", r"transferrin saturation"),
    ("Blood & iron",  "Hemoglobin",          r"^hemoglobin measurement$"),
    ("Blood & iron",  "Platelets",           r"^platelet count$"),
    ("Hormones",      "SHBG",                r"^sex hormone-binding globulin measurement$"),
    ("Hormones",      "Testosterone",        r"^testosterone measurement$|^total testosterone measurement$"),
    ("Hormones",      "DHEA-S",              r"dehydroepiandrosterone sulfate|^DHEA"),
    ("Hormones",      "Estradiol",           r"^estradiol measurement$"),
    ("Thyroid",       "TSH",                 r"thyroid stimulating hormone|thyrotropin"),
    ("Thyroid",       "Free T4",             r"^free thyroxine|^thyroxine amount$|^amount of thyroxine$"),
    ("Blood pressure", "Systolic BP",        r"^systolic blood pressure$"),
    ("Blood pressure", "Diastolic BP",       r"^diastolic blood pressure$"),
    ("Body",          "BMI",                 r"^body mass index$"),
    ("Body",          "Waist-hip ratio",     r"^waist-hip ratio$"),
]
_COMPILED = [(panel, name, re.compile(rx, re.I)) for panel, name, rx in CATALOG]


def classify_trait(efo_trait):
    for panel, name, rx in _COMPILED:
        if rx.search(efo_trait):
            return panel, name
    return None


def direction(assoc):
    """'+' if the effect allele raises the measurement, '-' if it lowers it, None if unknown."""
    beta = str(assoc.get("beta") or "")
    if "increase" in beta: return "+"
    if "decrease" in beta: return "-"
    try:
        orv = float(assoc.get("or_value"))
        return "+" if orv > 1 else "-" if orv < 1 else None
    except (TypeError, ValueError):
        return None


def main_pair(vep):
    """Reference allele plus the most common alternative in Europeans (Ensembl lists every
    allele ever seen, so G/A/C/T would make any letter look valid on both strands)."""
    ref, alts = vep["alleles"][0], vep["alleles"][1:]
    eur = vep.get("eur_af") or {}
    alt = max(alts, key=lambda a: eur.get(a) or 0) if alts else None
    return {ref, alt} - {None}


def align_allele(allele, vep, rsid):
    """Returns (forward_allele, status). status: ok | flipped | ambiguous | mismatch."""
    if allele not in COMPLEMENT:
        return None, "mismatch"
    pair = main_pair(vep)
    if pair in ({"A", "T"}, {"C", "G"}) and rsid not in STRAND_VERIFIED:
        return allele, "ambiguous"  # A/T or C/G SNP: reported strand cannot be confirmed
    if allele in pair:
        return allele, "ok"
    if COMPLEMENT[allele] in pair:
        return COMPLEMENT[allele], "flipped"
    return None, "mismatch"


def effect_allele_frequency(allele, vep):
    """EUR frequency of the effect allele (Ensembl reports alt alleles; ref = 1 - sum of alts)."""
    eur = vep.get("eur_af") or {}
    if allele in eur and eur[allele] is not None:
        return eur[allele]
    if vep["alleles"] and allele == vep["alleles"][0] and eur:
        return max(0.0, 1.0 - sum(f for f in eur.values() if f))
    return None


def build():
    lib = json.load(open(MODULES_PATH, encoding="utf-8"))
    rsids = sorted(lib["rsids"])
    vep = sources.ensembl_vep(rsids)
    gene_module = {g: info.get("module") for g, info in lib["genes"].items()}

    links = defaultdict(dict)  # biomarker -> rsid -> best association
    skipped = defaultdict(int)
    for rsid in rsids:
        v = vep.get(rsid)
        if not v:
            continue
        for a in sources._gwas_rows(rsid):
            if a["p_value"] > GENOME_WIDE:
                continue
            for t in a.get("efo_traits") or []:
                hit = classify_trait(t["efo_trait"])
                if not hit:
                    continue
                panel, name = hit
                reported = (a.get("snp_effect_allele") or [""])[0].split("-")[-1]
                d = direction(a)
                fwd, status = align_allele(reported, v, rsid)
                if d is None or fwd is None:
                    skipped["no allele/direction"] += 1
                    continue
                best = links[name].get(rsid)
                if best and best["p_value"] <= a["p_value"]:
                    continue
                genes = lib["rsids"][rsid]["genes"]
                links[name][rsid] = {
                    "rsid": rsid, "genes": genes,
                    "modules": sorted({gene_module.get(g) for g in genes if gene_module.get(g)}),
                    "panel": panel, "effect_allele": fwd, "direction": d, "strand": status,
                    "eaf_eur": effect_allele_frequency(fwd, v),
                    "p_value": a["p_value"], "beta": a.get("beta"), "or": a.get("or_value"),
                    "efo_trait": t["efo_trait"], "pubmed_id": a.get("pubmed_id"),
                    "first_author": a.get("first_author"),
                }

    panels = {name: panel for panel, name, _ in CATALOG}
    biomarkers = []
    for name, by_rsid in links.items():
        snps = sorted(by_rsid.values(), key=lambda x: x["p_value"])
        modules = defaultdict(int)
        for s in snps:
            for m in s["modules"]:
                modules[m] += 1
        biomarkers.append({"biomarker": name, "panel": panels[name], "n_snps": len(snps),
                           "modules": dict(sorted(modules.items(), key=lambda x: -x[1])), "snps": snps})
    biomarkers.sort(key=lambda b: (-b["n_snps"], b["biomarker"]))

    out = {
        "meta": {"source": "GWAS Catalog v2 + Ensembl GRCh38 alleles", "p_threshold": GENOME_WIDE,
                 "note": "Effect alleles are on the forward strand. 'ambiguous' A/T or C/G SNPs are excluded from person tilts."},
        "biomarkers": biomarkers,
    }
    with open(BIOMARKERS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    linked = {s["rsid"] for b in biomarkers for s in b["snps"]}
    print(f"✅ {len(biomarkers)} biomarkers linked to {len(linked)} library SNPs -> {BIOMARKERS_PATH}")
    for b in biomarkers[:15]:
        amb = sum(s["strand"] == "ambiguous" for s in b["snps"])
        print(f"   {b['panel']:<14} {b['biomarker']:<20} {b['n_snps']:>2} SNPs  modules {list(b['modules'])[:4]}"
              + (f"  ({amb} strand-ambiguous)" if amb else ""))


if __name__ == "__main__":
    build()
