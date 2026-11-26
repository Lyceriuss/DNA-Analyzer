"""The impact score of every trait model: how much of the differences between people the study's lead variants
explain, from the GWAS itself, the same way for every trait.

    python -m cluster_analysis.inheritance.gwas_impact          # all models -> data/reference/inheritance/trait_impact.json
    python -m cluster_analysis.inheritance.gwas_impact --check  # beside the figures the familiar traits' papers report
    python -m cluster_analysis.inheritance.gwas_impact --stats  # median, mean, quartiles and levels, overall and by kind

For each lead variant the GWAS Catalog gives its p-value (as -log10 p, PVALUE_MLOG, which doesn't underflow). Its test
statistic chi2 (1 degree of freedom) over the study's sample size N estimates the share of the trait's variance that
variant explains: R2 ~ chi2 / N. The lead variants of a model are one per 500 kb, close to independent, so their R2s
add up. The sum is unit-free, so it compares across traits where the effect sizes don't (the Catalog reports most
effects in an unnamed "unit").

What it is, and isn't:
  - the variance the lead variants explain in the study's own sample: the many variants too weak to reach
    genome-wide significance are left out, so the heritability a full genetic score could reach is higher;
  - an upper side estimate for those variants: the strongest hits of a study overstate their effects a little
    (winner's curse), most for small studies;
  - for a case-control study, on the observed scale of that study's case share, not the population's liability.
N is the study's initial sample (cases plus controls); a variant measured in fewer people gets a smaller chi2, so the
sum leans low there.
"""
import csv
import gzip
import io
import json
import math
import os
import re
import sys
import zipfile

from cluster_analysis.inheritance import predict

OUT = os.path.join(predict.REF, "inheritance", "trait_impact.json")
LN10 = math.log(10)


def chi2_of(mlog):
    """The 1-df chi-square of a two-sided p given as -log10 p; exact through scipy where it can be, else the normal
    tail's asymptotic form solved for z (p below 1e-300)."""
    if mlog <= 0:
        return 0.0
    if mlog < 290:
        from scipy.stats import chi2
        return float(chi2.isf(10 ** -mlog, 1))
    # -ln(p/2) = z^2/2 + ln z + ln sqrt(2 pi), solved by fixed-point iteration
    target = mlog * LN10 - math.log(2)
    z = math.sqrt(2 * target)
    for _ in range(50):
        z = math.sqrt(max(1e-9, 2 * (target - math.log(z) - 0.5 * math.log(2 * math.pi))))
    return z * z


def sample_size(text):
    """The study's people from the Catalog's sample text (cases and controls added)."""
    nums = [int(n.replace(",", "")) for n in re.findall(r"(\d[\d,]*)\s+(?:[A-Za-z-]+\s+){0,6}?(?:individuals|cases|controls|men|women|males|females|participants|people|adults|children|subjects|donors|families|trios)", text or "")]
    return sum(nums) or None


def mlogs(studies):
    """{(study, rsid): -log10 p} for the anchor studies' rows, the strongest when a variant is listed twice."""
    out = {}
    with zipfile.ZipFile(predict.GWAS) as z:
        name = next(n for n in z.namelist() if n.endswith((".tsv", ".txt")))
        for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace"), delimiter="\t"):
            st = r.get("STUDY ACCESSION")
            if st not in studies:
                continue
            m = re.fullmatch(r"(rs\d+)-[ACGT?]", (r["STRONGEST SNP-RISK ALLELE"] or "").strip())
            if not m:
                continue
            try:
                v = float(r.get("PVALUE_MLOG") or "nan")
            except ValueError:
                continue
            if math.isnan(v):
                continue
            k = (st, m.group(1))
            out[k] = max(out.get(k, 0), v)
    return out


def build(models=None):
    models = models or predict.load_models()
    ml = mlogs({m["study"] for m in models})
    out = {}
    for m in models:
        n = sample_size(m.get("sample")) or int(float(m.get("n") or 0)) or None
        chis = [chi2_of(ml[(m["study"], v["rsid"])]) for v in m["variants"] if (m["study"], v["rsid"]) in ml]
        if not n or not chis:
            continue
        r2 = sum(chis) / n
        # Where the sum isn't a share of one trait's variance: a study of many measurements filed under one trait
        # (brain-scan "vertex-wise" maps), a multi-trait analysis whose statistics carry more information than its
        # sample (MTAG), or a sum past half the variance, which lead variants of one trait don't reach
        rep = (m.get("reported") or "") + " " + (m.get("sample") or "")
        flag = ("many measurements filed under one trait" if re.search(r"vertex-wise|multivariate|genomic SEM", rep, re.I)
                else "a multi-trait analysis (MTAG), whose statistics carry more than its sample" if re.search(r"\bMTAG\b", rep)
                else "the strongest variants sum past half the variance, so the study's statistics don't fit this sum" if r2 >= 0.5 else None)
        out[m["id"]] = {"r2_lead": round(min(r2, 1.0), 5), "flag": flag, "n": n, "variants": len(m["variants"]), "with_p": len(chis),
                        "case_control": bool(re.search(r"\bcases?\b", m.get("sample") or "")), "study": m["study"], "pmid": m.get("pmid")}
    summary = summarise(out)
    # Each trait's place among all scored traits: the share with a lower impact, in %
    ranked = sorted(v["r2_lead"] for v in out.values() if not v.get("flag"))
    import bisect
    for v in out.values():
        if not v.get("flag"):
            v["rank_pct"] = round(100 * bisect.bisect_left(ranked, v["r2_lead"]) / len(ranked), 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"method": "sum over the lead variants of chi2/N from the GWAS Catalog's PVALUE_MLOG and the study's sample",
                   "summary": summary, "traits": out}, f, separators=(",", ":"))
    print(f"✅ impact for {len(out)} of {len(models)} trait models → {OUT}")
    return out


LEVELS = ((8.0, "high"), (3.0, "modest"), (0.0, "little"))   # the user's levels, 2026-11-26: % of the variance


def level(pct):
    return next(name for floor, name in LEVELS if pct >= floor)


def stats(xs):
    """Median, mean, quartiles and the count per level of impacts given as shares (0-1), in %."""
    import statistics
    xs = sorted(100 * x for x in xs)
    if not xs:
        return None
    q = lambda f: round(xs[min(len(xs) - 1, int(f * len(xs)))], 2)
    counts = {name: 0 for _, name in LEVELS}
    for x in xs:
        counts[level(x)] += 1
    return {"traits": len(xs), "median": round(statistics.median(xs), 2), "mean": round(statistics.mean(xs), 2),
            "p25": q(.25), "p75": q(.75), "p90": q(.9), "levels": counts}


def summarise(out):
    ok = [v for v in out.values() if not v.get("flag")]
    return {"all": stats([v["r2_lead"] for v in ok]),
            "measurements": stats([v["r2_lead"] for v in ok if not v["case_control"]]),
            "case_control": stats([v["r2_lead"] for v in ok if v["case_control"]]),
            "flagged": len(out) - len(ok)}


def summary():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f).get("summary") or {}
    except (OSError, ValueError):
        return {}


def load():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)["traits"]
    except (OSError, ValueError, KeyError):
        return {}


if __name__ == "__main__":
    if "--stats" in sys.argv:
        print(json.dumps(summary(), indent=1))
    elif "--check" in sys.argv:
        from cluster_analysis.inheritance import impact
        imp, rep = load(), impact.load()
        for f in predict.featured(raw=True):
            g, p = imp.get(f["id"], {}), rep.get(f["id"], {})
            paper = f"{p.get('kind')} {p.get('value')}" if p.get("kind") else "-"
            print(f"{f['name']:26} GWAS lead R2 {100 * g.get('r2_lead', 0):6.2f}%  ({g.get('with_p')}/{g.get('variants')} variants, N={g.get('n')}{', case-control' if g.get('case_control') else ''})   paper: {paper}")
    else:
        build()
