# cluster_analysis/evidence_call.py
"""
A library SNP's effect on its gene, decided by evidence about the variant instead of the library's wording.

The library (config/snp_traits.json) says what a genotype means for a trait; its sentences were written with an LLM and
are not evidence of how much the gene works. This module reads function_evidence.json (MaveDB, UniProt, GTEx,
SIFT/PolyPhen, gathered by function_evidence.py) and the CPIC allele functions, and decides, strongest evidence first:

  cpic        CPIC allele function (pharmacogenes: CYP2C19*2 no function ...)      → GoF / LoF / normal
  measured    MaveDB deep mutational scan of this protein change, against wild type → GoF / LoF / normal
  curated     UniProt's curated effect of the change ("55% of wild type activity")   → GoF / LoF
  truncating  the allele people carry stops the protein early (stop, frameshift)     → LoF
  curated     a curated effect without a direction                                   → altered
  predicted   SIFT (not low confidence) and PolyPhen both call the change damaging   → LoF, worded "likely"
  expression  GTEx: the allele raises or lowers the gene's expression                → GoF / LoF, worded "more/less expressed"
  none        nothing about function                                                 → unknown ("no known effect")

Protein evidence is relative to the standard protein: the person's copies of the changed allele carry the effect (COMT
Met is the low-activity allele, however common). Expression effects are relative to the genotype most Europeans carry,
since both alleles are natural there. Coding evidence outranks expression: a change that breaks
the protein (NAT2*6, NQO1*2) is less active whatever its mRNA level does.
"""
import json
import os
import re
import statistics

HERE = os.path.dirname(__file__)
EVIDENCE_PATH = os.path.join(HERE, "function_evidence.json")
COMPLEMENT = str.maketrans("ACGT", "TGCA")
TRUNCATING = {"stop_gained", "frameshift_variant", "splice_donor_variant", "splice_acceptor_variant", "start_lost"}

BASIS_TEXT = {"cpic": "CPIC allele function", "measured": "measured protein function (MaveDB)",
              "curated": "curated protein effect (UniProt)", "truncating": "the change cuts the protein short",
              "predicted": "predicted damage (SIFT and PolyPhen)", "expression": "gene expression (GTEx)",
              "none": "no evidence about the gene's function"}

FUNCTION_PART = (r"activit|function|expression|stabil|thermolab|binding|transport|efficien|catalytic|degradation|"
                 r"wild[- ]type|affinity|clearance|uptake|secretion|signal")
UP = r"increas|enhanc|higher|gain|elevat|more active|fold increase|stimulat"
DOWN = r"decreas|reduc|lower|\blow\b|loss|impair|abolish|deficien|inactiv|less active|unstable|instab|thermolabile|null|defect|diminish"


def load_evidence():
    if not os.path.exists(EVIDENCE_PATH):
        return {}
    return {r["rsid"]: r for r in json.load(open(EVIDENCE_PATH, encoding="utf-8"))}


def text_direction(texts):
    """+1, -1, 0 (both or neither) from curated effect sentences; a percentage of wild type below 100 reads as reduced."""
    up = down = False
    # Only the parts about function count: "low enzyme activity" does, "may increase the tendency to develop high blood
    # pressure" (a disease) doesn't
    parts = [p for t in texts for p in re.split(r"[;,]", t) if re.search(FUNCTION_PART, p, re.I)]
    for t in parts:
        low = t.lower()
        for pct in re.findall(r"(\d+(?:\.\d+)?)\s*%\s*of (?:the )?wild[- ]type", low):
            if float(pct) < 90:
                down = True
            elif float(pct) > 110:
                up = True
        if re.search(UP, low):
            up = True
        if re.search(DOWN, low):
            down = True
    return 1 if up and not down else -1 if down and not up else 0


def _alleles(vep):
    """(reference, main alternative, common European allele) from a VEP record."""
    alleles = vep["alleles"]
    af = dict(vep.get("eur_af") or {})
    af.setdefault(alleles[0], max(0.0, 1 - sum(f for a, f in af.items() if a != alleles[0])))
    alts = [a for a in alleles[1:] if len(a) == 1]
    alt = max(alts, key=lambda a: af.get(a, 0)) if alts else None
    common = max(alleles, key=lambda a: af.get(a, 0))
    return alleles[0], alt, common, af


def _star(rsid):
    from cluster_analysis.medicines import STAR
    for gene, defs in STAR.items():
        for name, rs, alt, fn in defs:
            if rs == rsid:
                return gene, name, alt, fn
    return None


def evidence_call(rsid, genotype, ev, vep):
    """{function, basis, detail, dose, effect_allele} for a person's genotype at a library SNP."""
    out = {"function": "unknown", "basis": "none", "detail": None, "dose": None, "effect_allele": None}
    if not genotype or not vep:
        return out
    ref, alt, common, af = _alleles(vep)
    gt = genotype if set(genotype) <= set(vep["alleles"]) else genotype.translate(COMPLEMENT)
    if not set(gt) <= set(vep["alleles"]) or not alt:
        return out
    ev = ev or {"sources": {}}
    s = ev.get("sources", {})

    def call(effect_allele, sign, basis, detail):
        """sign: the effect of effect_allele (+1 more, -1 less, 0 changed). Protein evidence is relative to the standard
        protein, so the person's copies of the changed allele carry it. Expression is relative to the common genotype,
        since both alleles are natural there."""
        if basis == "expression" and effect_allele == common:
            sign, effect_allele = -sign, next((a for a in (alt, ref) if a != common), alt)
        dose = gt.count(effect_allele)
        fn = "normal" if dose == 0 else {1: "GoF", -1: "LoF"}.get(sign, "altered")
        out.update(function=fn, basis=basis, detail=detail, dose=dose, effect_allele=effect_allele)
        return out

    star = _star(rsid)
    if star:
        gene, name, a, fn = star
        sign = -1 if fn in ("No function", "Decreased function", "Slow") else 1 if fn == "Increased function" else 0
        return call(a, sign, "cpic", f"{gene}{name} ({a}) is a {fn.lower()} allele by CPIC")

    if s.get("mavedb"):
        scores = [m["score"] for m in s["mavedb"] if isinstance(m.get("score"), (int, float))]
        if scores:
            med = statistics.median(scores)
            ratio = med / 100 if med > 10 else med  # sets score wild type as 100 or as 1
            sign = -1 if ratio < 0.8 else 1 if ratio > 1.25 else 0
            change = s["mavedb"][0]["change"]
            if sign == 0:
                out.update(basis="measured", detail=f"{change} works about as well as the common form in MaveDB assays "
                                                     f"(median {ratio:.0%} of wild type)", dose=sum(1 for a in gt if a != common))
                out["function"] = "normal"
                return out
            return call(alt, sign, "measured", f"{change}: {ratio:.0%} of wild-type function in MaveDB assays (median of {len(scores)})")

    # Curated text with a clear direction first, then a stop in the allele people carry, then curated text without one.
    # LPL S447X is a stop near the protein's end that raises activity: the curated direction wins there.
    functional = s.get("uniprot", {}).get("functional") or []
    sign = text_direction(functional) if functional else 0
    change = (s.get("uniprot", {}).get("protein_changes") or [""])[0]
    if functional and sign:
        return call(alt, sign, "curated", f"{change + ': ' if change else ''}{'; '.join(functional)[:220]}")
    stops = TRUNCATING & set((vep.get("allele_consequences") or {}).get(alt, []))
    if stops:
        return call(alt, -1, "truncating", f"{change + ': ' if change else ''}{sorted(stops)[0].replace('_', ' ')}, the protein is cut short")
    if functional:
        return call(alt, 0, "curated", f"{change + ': ' if change else ''}{'; '.join(functional)[:220]}")

    preds = {p["tool"]: p["call"] for p in s.get("predicted", [])}
    if preds.get("SIFT") == "deleterious" and preds.get("PolyPhen") in ("probably damaging", "possibly damaging"):
        return call(alt, -1, "predicted", f"SIFT {preds['SIFT']}, PolyPhen {preds['PolyPhen']}")

    g = s.get("gtex")
    if g and g.get("own_gene"):
        rows = [r for r in g["top"] if r["gene"] in ev.get("genes", [])] or g["top"]
        signs = {1 if r["nes"] > 0 else -1 for r in rows}
        tissues = ", ".join(r["tissue"].replace("_", " ") for r in rows[:3])
        if len(signs) == 1:
            sign = signs.pop()
            return call(g["effect_allele"], sign, "expression",
                        f"{g['effect_allele']} {'raises' if sign > 0 else 'lowers'} {rows[0]['gene']} expression in "
                        f"{g['n_tissues']} tissues (strongest: {tissues})")
        return call(g["effect_allele"], 0, "expression", f"{g['effect_allele']} raises {rows[0]['gene']} expression in some "
                                                         f"tissues and lowers it in others ({tissues})")
    out["dose"] = sum(1 for a in gt if a != common)
    out["detail"] = ("SIFT and PolyPhen call the change harmless; " if preds else "") + \
        "no measured, curated or expression evidence that this SNP changes the gene"
    return out
