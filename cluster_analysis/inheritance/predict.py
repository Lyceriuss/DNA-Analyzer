# cluster_analysis/inheritance/predict.py
"""
The prediction engine: where a child of two profiles is likely to sit, trait by trait, among Europeans.

A GWAS gives, for each lead variant of a trait, an effect allele and what each copy of it adds (a beta, or the log of
an odds ratio): the additive model the study itself fits. A trait's genetic score is the sum over its variants of
copies x effect. For each trait in the GWAS Catalog:

  model      one study (the anchor: European, most lead variants with an effect, then the largest), so the effects
             share units; one lead variant per 500 kb; each placed on the forward strand against the 1000 Genomes site
             list with its European frequency. Person-free, built once: data/reference/inheritance/gwas_trait_models.json.gz
  population mean 2fw and variance 2f(1-f)w^2 per variant (f: the effect allele's European frequency)
  a parent   copies of the effect allele from their calls; a variant without a usable call counts as the average 2f
  the child  at each variant a parent passes the effect allele with chance copies/2 (the average f without a call),
             so the child's copies have mean qm + qf and variance qm(1-qm) + qf(1-qf); summed over the variants this
             gives the child's expected score and its spread from which copies are passed on

Each is placed among Europeans as a percentile (a normal approximation of the score's distribution); the child as an
expected percentile and the range 80% of children of the pair would fall in. The score holds only the trait's lead
variants, so it places the genes these studies found, not the trait itself.

    python -m cluster_analysis.inheritance.predict build     # the trait models (once; rebuilt when the Catalog changes)
"""
import collections
import csv
import gzip
import io
import json
import math
import os
import re
import sys
import zipfile

from genome import build as gbuild

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(os.path.dirname(HERE))
REF = os.path.join(ROOT, "data", "reference")
GWAS = os.path.join(REF, "gwas_associations_ontology.zip")
MAPPINGS = os.path.join(REF, "gwas_trait_mappings.tsv")
MODELS = os.path.join(REF, "inheritance", "gwas_trait_models.json.gz")
GWS = 5e-8
LOCUS = 500_000
MIN_N = 10_000          # a study smaller than this doesn't make a model
MIN_VARIANTS = 5        # nor does one with fewer lead variants placed on the forward strand
Z80 = 1.2816            # the middle 80% of a normal distribution
Z98 = 2.3263            # the middle 98%
FLIP = str.maketrans("ACGT", "TGCA")
USABLE = ("measured", "high", "medium")


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def sample_size(text):
    return sum(int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", text or ""))


def european_only(sample):
    return "European" in (sample or "") and not re.search(r"African|Asian|Hispanic|Latin|Japanese|Chinese|Korean", sample or "")


# --- The trait models (person-free) -----------------------------------------------------------------------------------

def effect(size, ci):
    """(weight per copy, kind) from the Catalog's "OR or BETA" and "95% CI (TEXT)": a beta signed by "increase" or
    "decrease", or the log of an odds ratio (the Catalog reports the allele that raises the odds). None otherwise."""
    if size is None:
        return None, None
    ci = (ci or "").lower()
    if "increase" in ci:
        return size, "beta"
    if "decrease" in ci:
        return -size, "beta"
    if size > 1 and "unit" not in ci and size < 50:
        return math.log(size), "odds ratio"
    return None, None


def gwas_rows():
    """Genome-wide significant single-trait associations with an effect allele and a usable effect size."""
    with zipfile.ZipFile(GWAS) as z:
        name = next(n for n in z.namelist() if n.endswith((".tsv", ".txt")))
        for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace"), delimiter="\t"):
            uris = [u.strip() for u in (r["MAPPED_TRAIT_URI"] or "").split(",") if u.strip()]
            if len(uris) != 1:
                continue
            m = re.fullmatch(r"(rs\d+)-([ACGT])", (r["STRONGEST SNP-RISK ALLELE"] or "").strip())
            if not m or r["CHR_ID"] in ("Y", "MT", "") or not (r["CHR_POS"] or "").isdigit():
                continue
            try:
                p = float(r["P-VALUE"] or 1)
                size = float(r["OR or BETA"]) if r["OR or BETA"] else None
            except ValueError:
                continue
            if p > GWS:
                continue
            w, kind = effect(size, r["95% CI (TEXT)"])
            if w is None or w == 0:
                continue
            try:
                raf = float(r["RISK ALLELE FREQUENCY"])
            except ValueError:
                raf = None
            yield {"uri": uris[0], "trait": r["MAPPED_TRAIT"], "rsid": m.group(1), "allele": m.group(2), "p": p, "w": w,
                   "kind": kind, "raf": raf, "study": r["STUDY ACCESSION"], "pmid": r["PUBMEDID"], "author": r["FIRST AUTHOR"],
                   "year": (r["DATE"] or "")[:4], "sample": r["INITIAL SAMPLE SIZE"], "gene": r["MAPPED_GENE"],
                   "chrom": r["CHR_ID"], "pos": int(r["CHR_POS"]), "reported": r["DISEASE/TRAIT"]}


def clump(rows):
    """One row per 500 kb: the strongest."""
    kept = []
    for r in sorted(rows, key=lambda r: r["p"]):
        if all(not (k["chrom"] == r["chrom"] and abs(k["pos"] - r["pos"]) < LOCUS) for k in kept):
            kept.append(r)
    return kept


def anchor(rows):
    """The study whose lead variants make the model: European only, then most lead variants (after clumping), then
    the largest; at least MIN_N people."""
    by = collections.defaultdict(list)
    for r in rows:
        if sample_size(r["sample"]) >= MIN_N:
            by[r["study"]].append(r)
    if not by:
        return None, []
    best = max(by, key=lambda s: (european_only(by[s][0]["sample"]), len(clump(by[s])), sample_size(by[s][0]["sample"])))
    return best, clump(by[best])


def categories():
    """{EFO URI: (the GWAS Catalog's parent category, its URI)}, the most frequent one per trait. The Catalog's trait
    mapping file files every EFO term under one of about fifteen parent terms ("Lipid or lipoprotein measurement",
    "Neurological disorder", "Other measurement" ...)."""
    count = collections.defaultdict(collections.Counter)
    try:
        with open(MAPPINGS, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                count[r["EFO URI"]][(r["Parent term"], r["Parent URI"])] += 1
    except OSError:
        return {}
    return {u: c.most_common(1)[0][0] for u, c in count.items()}


EFO = os.path.join(REF, "efo", "efo.obo")
_EFO = None


def term_key(x):
    """One key for a term however it is written: http://www.ebi.ac.uk/efo/EFO_0011015, efo:EFO_0011015 and
    MONDO:0005146 / .../obo/MONDO_0005146 become EFO_0011015 and MONDO_0005146."""
    x = x.rsplit("/", 1)[-1]
    if x.lower().startswith("efo:"):
        x = x[4:]
    return x.replace(":", "_")


def efo_terms():
    """{term key: {label, definition}} from EFO's release file (it imports the MONDO, HP, GO ... terms it uses)."""
    global _EFO
    if _EFO is None:
        _EFO = {}
        try:
            with open(EFO, encoding="utf-8") as f:
                cur = None
                for line in f:
                    if line.startswith("[Term]"):
                        cur = {}
                    elif cur is not None and line.startswith("id: "):
                        cur["key"] = term_key(line[4:].strip())
                    elif cur is not None and line.startswith("name: "):
                        cur["label"] = line[6:].strip()
                    elif cur is not None and line.startswith("def: "):
                        m = re.match(r'def: "((?:[^"\\]|\\.)*)"', line)
                        cur["definition"] = m.group(1).replace('\\"', '"') if m else None
                    elif not line.strip() and cur:
                        if "key" in cur:
                            _EFO[cur["key"]] = {"label": cur.get("label"), "definition": cur.get("definition")}
                        cur = None
        except OSError:
            pass
    return _EFO


def efo_term(iri):
    return efo_terms().get(term_key(iri), {})


def efo_version():
    try:
        with open(EFO, encoding="utf-8") as f:
            for line in f:
                if line.startswith("data-version:"):
                    return line.split("/releases/")[-1].split("/")[0]
                if line.startswith("[Term]"):
                    break
    except OSError:
        pass
    return None


def define(models, log=print):
    """Each model's EFO definition, added in place."""
    for m in models:
        if "definition" not in m:
            m["definition"] = efo_term(m["uri"]).get("definition")
    log(f"EFO {efo_version()}: {sum(1 for m in models if m.get('definition')):,} of {len(models):,} traits defined")
    return models


def category_definitions(models):
    """{category: {uri, label, definition}} for the categories the models use."""
    out = {}
    for m in models:
        c, u = m["category"], m.get("category_uri")
        if c not in out and u:
            t = efo_term(u)
            out[c] = {"uri": u, "label": t.get("label"), "definition": t.get("definition")}
    return out


def panel_sites(positions):
    """{(chrom, pos): (ref, alt, EUR alt frequency)} for biallelic SNPs, from the 1000 Genomes site list."""
    out = {}
    with gzip.open(gbuild.sites(), "rt") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.split("\t", 8)
            chrom = p[0][3:] if p[0].startswith("chr") else p[0]
            key = (chrom, int(p[1]))
            if key not in positions or len(p[3]) != 1 or len(p[4]) != 1:
                continue
            m = re.search(r"(?:^|;)EUR_AF=([\d.e-]+)", p[7])
            if m:
                out[key] = (p[3], p[4], float(m.group(1)))
    return out


def align(allele, site, raf=None):
    """(effect allele on the forward strand, its European frequency, ref, alt), or None when it can't be placed. A
    palindromic SNP (A/T, C/G) is only kept when the study's allele frequency settles the strand."""
    if not site:
        return None
    ref, alt, af = site
    pal = {ref, alt} in ({"A", "T"}, {"C", "G"})
    if allele in (ref, alt) and not pal:
        a = allele
    elif allele.translate(FLIP) in (ref, alt) and not pal:
        a = allele.translate(FLIP)
    elif pal and raf is not None and allele in (ref, alt):
        f = af if allele == alt else 1 - af
        if abs(af - 0.5) < 0.1 or abs(f - raf) > 0.15:
            return None
        a = allele
    else:
        return None
    f = af if a == alt else 1 - af
    if f <= 0 or f >= 1:
        return None
    return a, f, ref, alt


def build_models(log=print):
    """Every trait with an anchor study of at least MIN_VARIANTS placed lead variants."""
    by_trait = collections.defaultdict(list)
    names = {}
    for r in gwas_rows():
        by_trait[r["uri"]].append(r)
        names[r["uri"]] = r["trait"]
    log(f"GWAS Catalog: {sum(len(v) for v in by_trait.values()):,} associations with an effect, {len(by_trait):,} traits")
    picked = {}
    for uri, rows in by_trait.items():
        study, lead = anchor(rows)
        if study and len(lead) >= MIN_VARIANTS:
            picked[uri] = (study, lead)
    positions = {(r["chrom"], r["pos"]) for _, lead in picked.values() for r in lead}
    log(f"{len(picked):,} traits with an anchor study; placing {len(positions):,} lead variants on the 1000 Genomes sites")
    sites = panel_sites(positions)
    cats = categories()
    models = []
    for uri, (study, lead) in picked.items():
        vs = []
        for r in lead:
            a = align(r["allele"], sites.get((r["chrom"], r["pos"])), r["raf"])
            if not a:
                continue
            allele, f, ref, alt = a
            vs.append({"rsid": r["rsid"], "chrom": r["chrom"], "pos": r["pos"], "allele": allele, "freq": round(f, 5),
                       "ref": ref, "alt": alt, "w": r["w"], "gene": r["gene"], "p": r["p"],
                       **({"x": True} if on_x(r["chrom"], r["pos"]) else {})})
        if len(vs) < MIN_VARIANTS:
            continue
        r0 = lead[0]
        cat, cat_uri = cats.get(uri, ("Other trait", "http://www.ebi.ac.uk/efo/EFO_0000001"))
        models.append({"uri": uri, "id": uri.rsplit("/", 1)[-1], "trait": names[uri], "category": cat, "category_uri": cat_uri,
                       "study": study, "pmid": r0["pmid"], "author": r0["author"], "year": r0["year"],
                       "sample": r0["sample"], "n": sample_size(r0["sample"]), "kind": r0["kind"],
                       "reported": r0["reported"], "variants": vs})
    os.makedirs(os.path.dirname(MODELS), exist_ok=True)
    with gzip.open(MODELS + ".partial", "wt", encoding="utf-8") as f:
        json.dump({"source": os.path.basename(GWAS), "built_from_mtime": os.path.getmtime(GWAS), "models": models}, f,
                  separators=(",", ":"))
    os.replace(MODELS + ".partial", MODELS)
    log(f"✅ {len(models):,} trait models, {sum(len(m['variants']) for m in models):,} variants → {MODELS}")
    return models


def save_models(models):
    with gzip.open(MODELS + ".partial", "wt", encoding="utf-8") as f:
        json.dump({"source": os.path.basename(GWAS), "built_from_mtime": os.path.getmtime(GWAS), "models": models}, f,
                  separators=(",", ":"))
    os.replace(MODELS + ".partial", MODELS)


def load_models():
    """The trait models with their EFO definitions, built when missing or older than the Catalog file."""
    models = None
    if os.path.exists(MODELS):
        with gzip.open(MODELS, "rt", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("built_from_mtime") == os.path.getmtime(GWAS):
            models = data["models"]
    if models is None:
        models = build_models()
    if any("definition" not in m or "category_uri" not in m for m in models):
        cats = categories()
        for m in models:
            m.setdefault("category_uri", cats.get(m["uri"], ("", "http://www.ebi.ac.uk/efo/EFO_0000001"))[1])
        define(models)
        save_models(models)
    return models


# --- A pair ---------------------------------------------------------------------------------------------------------

def on_x(chrom, pos):
    """On the X outside the two pseudo-autosomal regions (those pair with the Y and are inherited like autosomes)."""
    return str(chrom) in ("X", "23") and not any(a <= int(pos) <= b for a, b in gbuild.par())


def moments(f, hemizygous):
    """The population mean and variance of a person's copies at one variant: two copies, each with the European
    frequency f; for a man's X (hemizygous), one copy counted as 0 or 2 (full dosage compensation, a common coding of
    men's X in genome-wide studies, so the study's effect sizes fit it)."""
    return (2 * f, 4 * f * (1 - f)) if hemizygous else (2 * f, 2 * f * (1 - f))


def copies(call, v):
    """Copies of the effect allele in a parent's call, or None when the call can't be used."""
    if not call or call.get("tier") not in USABLE:
        return None
    gt = call.get("genotype") or ""
    if len(gt) != 2 or not set(gt) <= {v["ref"], v["alt"]}:
        return None
    return gt.count(v["allele"])


def predict(model, xx, xy, child_sex="XX"):
    """Where each parent sits and where their child is likely to sit for one trait, as percentiles among Europeans.
    xx, xy: {rsid: call} with genotype and tier. child_sex XX or XY matters on the X only: a daughter gets one X from
    each parent (her father's for certain), a son his mother's only, counted 0 or 2 (moments); each parent and the
    child are ranked against their own sex."""
    mom = {"XX": [0.0, 0.0], "XY": [0.0, 0.0]}   # the population's mean and variance, for women and for men
    mean = var = 0.0
    s = {"XX": 0.0, "XY": 0.0}
    c_mean = c_var = 0.0
    c_min = c_max = 0.0   # the furthest any child could land: every coin toss going the same way
    push = {"XX": 0.0, "XY": 0.0}   # how far each parent's passed copies move the child from the average
    used = {"XX": 0, "XY": 0, "both": 0}
    parts = []
    for v in model["variants"]:
        w, f, x = v["w"], v["freq"], bool(v.get("x"))
        for sx in ("XX", "XY"):
            mu, vv = moments(f, x and sx == "XY")
            mom[sx][0] += mu * w
            mom[sx][1] += vv * w * w
        d = {"XX": copies(xx.get(v["rsid"]), v), "XY": copies(xy.get(v["rsid"]), v)}
        q = {}
        for side in ("XX", "XY"):
            if d[side] is None:
                s[side] += 2 * f * w
                q[side] = f
            else:
                s[side] += d[side] * w
                used[side] += 1
                q[side] = d[side] / 2
        used["both"] += d["XX"] is not None and d["XY"] is not None
        qa, qb = q["XX"], q["XY"]
        if x and child_sex == "XY":
            # A son's X is his mother's: she passes the variant with qa, and he holds it as 0 or 2 (moments)
            c_mean += 2 * qa * w
            c_var += 4 * qa * (1 - qa) * w * w
            push["XX"] += 2 * (qa - f) * w
            lo, hi = (0 if d["XX"] in (None, 0, 1) else 2), (2 if d["XX"] in (None, 1, 2) else 0)
            child_p = [round(1 - qa, 4), 0.0, round(qa, 4)]
            kind = "unread" if d["XX"] is None else "chance" if 0 < qa < 1 else "settled"
            spread, child_mean = 4 * qa * (1 - qa) * w * w, 2 * qa
        else:
            # Two copies, one from each parent (on a daughter's X her father's single X passes for certain: qb is 0 or 1)
            c_mean += (qa + qb) * w
            c_var += (qa * (1 - qa) + qb * (1 - qb)) * w * w
            push["XX"] += (qa - f) * w
            push["XY"] += (qb - f) * w
            # The copies a child could get here: a parent with 0 or 2 passes 0 or 1 for certain, with 1 either; unread, either
            lo = (0 if d["XX"] in (None, 0, 1) else 1) + (0 if d["XY"] in (None, 0, 1) else 1)
            hi = (1 if d["XX"] in (None, 1, 2) else 0) + (1 if d["XY"] in (None, 1, 2) else 0)
            child_p = [round((1 - qa) * (1 - qb), 4), round(qa * (1 - qb) + qb * (1 - qa), 4), round(qa * qb, 4)]
            # settled: both parents carry two identical letters, so the child's pair is certain; chance: a parent
            # carries two different ones (a coin toss); unread: a parent's call can't be used
            kind = "unread" if d["XX"] is None or d["XY"] is None else "chance" if 0 < qa < 1 or 0 < qb < 1 else "settled"
            spread, child_mean = (qa * (1 - qa) + qb * (1 - qb)) * w * w, qa + qb
        c_min += min(lo * w, hi * w)
        c_max += max(lo * w, hi * w)
        parts.append({"rsid": v["rsid"], "gene": v["gene"], "allele": v["allele"],
                      "other": v["alt"] if v["allele"] == v["ref"] else v["ref"], "freq": v["freq"], "raises": w > 0,
                      "average": round(2 * f, 2),  # the copies an average European carries
                      "XX": d["XX"], "XY": d["XY"], "child_mean": round(child_mean, 3), "child_p": child_p, "kind": kind,
                      "spread": spread, "shift": (child_mean - 2 * f) * w, **({"x": True} if x else {})})
    mean, var = mom[child_sex]
    if var <= 0 or mom["XX"][1] <= 0 or mom["XY"][1] <= 0:
        return None
    sd = math.sqrt(var)
    # Each parent against their own sex's population (they differ on the X only)
    z = {k: (s[k] - mom[k][0]) / math.sqrt(mom[k][1]) for k in s}
    cz, csd = (c_mean - mean) / sd, math.sqrt(c_var) / sd
    for p in parts:
        p["shift"] = round(p["shift"] / sd, 3)
    for p in parts:
        p["spread"] = round(p["spread"] / var, 4) if var else 0   # its share of the population's variance
    top = sorted(parts, key=lambda p: -abs(p["shift"]))[:10]
    # The settled genes that move the child most, and the chance genes that widen the field most
    settled = sorted((p for p in parts if p["kind"] == "settled"), key=lambda p: -abs(p["shift"]))[:12]
    chance = sorted((p for p in parts if p["kind"] != "settled"), key=lambda p: -p["spread"])[:12]
    n = collections.Counter(p["kind"] for p in parts)
    pct = lambda x: round(100 * phi(x), 1)
    return {"XX_z": round(z["XX"], 3), "XY_z": round(z["XY"], 3), "child_z": round(cz, 3), "child_sd": round(csd, 3),
            "XX_pct": pct(z["XX"]), "XY_pct": pct(z["XY"]), "child_pct": pct(cz),
            "child_lo": pct(cz - Z80 * csd), "child_hi": pct(cz + Z80 * csd),
            "child_lo98": pct(cz - Z98 * csd), "child_hi98": pct(cz + Z98 * csd),
            "variants": len(model["variants"]), "used_XX": used["XX"], "used_XY": used["XY"], "used_both": used["both"],
            # The child's expected distance from the average, split by the parent whose copies carry it (sums to child_z)
            "push_XX": round(push["XX"] / sd, 3), "push_XY": round(push["XY"] / sd, 3),
            "n_settled": n["settled"], "n_chance": n["chance"], "n_unread": n["unread"],
            "child_min": pct((c_min - mean) / sd), "child_max": pct((c_max - mean) / sd),
            "top": top, "settled": settled, "chance": chance}


# GWAS Catalog terms that are not a person's trait: a GWAS of sex itself
NOT_A_TRAIT = {"biological sex"}

FEMALE = re.compile(r"\b(female|females|women|woman|girls|mothers)\b", re.I)
MALE = re.compile(r"\b(male|males|men|man|boys|fathers)\b", re.I)


def studied_sex(sample):
    """"female" or "male" when the study's sample is one sex only (the Catalog's sample description), else None."""
    f, m = bool(FEMALE.search(sample or "")), bool(MALE.search(sample or ""))
    return "female" if f and not m else "male" if m and not f else None


def predictions(models, xx_calls, xy_calls, min_share=0.5):
    """Every trait whose variants are read in both parents at least min_share of the time."""
    from cluster_analysis.inheritance import gwas_impact
    imp = gwas_impact.load()
    out = []
    for m in models:
        if m["trait"] in NOT_A_TRAIT:
            continue
        on_x_ = any(v.get("x") for v in m["variants"])
        for child in (("XX", "XY") if on_x_ else ("any",)):
            r = predict(m, xx_calls, xy_calls, "XX" if child == "any" else child)
            if not r or r["used_both"] < max(MIN_VARIANTS, min_share * r["variants"]):
                continue
            out.append({"id": m["id"], "uri": m.get("uri"), "trait": m["trait"], "category": m["category"], "study": m["study"],
                        "pmid": m["pmid"], "author": m["author"], "year": m["year"], "n": m["n"], "kind": m["kind"],
                        "reported": m.get("reported"), "definition": m.get("definition"),
                        "studied_sex": studied_sex(m.get("sample")), "sample": m.get("sample"),
                        # which child the row is for: "any" when the trait has no X variants (a son and a daughter alike)
                        "child_sex": child, "x_variants": sum(1 for v in m["variants"] if v.get("x")),
                        # GWAS impact: the share of the differences between people the lead variants explain, in %
                        "impact": round(100 * imp[m["id"]]["r2_lead"], 2) if m["id"] in imp and not imp[m["id"]].get("flag") else None,
                        "impact_flag": (imp.get(m["id"]) or {}).get("flag"), "impact_rank": (imp.get(m["id"]) or {}).get("rank_pct"), **r})
    return out


FEATURED = os.path.join(HERE, "featured.json")


def featured(raw=False):
    """featured.json's traits; unless raw, each with what its study reports about how much the score says
    (impact.py: quoted from the paper, never estimated here)."""
    try:
        fs = json.load(open(FEATURED, encoding="utf-8"))["featured"]
    except (OSError, ValueError, KeyError):
        return []
    if raw:
        return fs
    from cluster_analysis.inheritance import impact
    imp = impact.load()
    return [f | ({"impact": imp[f["id"]]} if f["id"] in imp else {}) for f in fs]


def genome_shares():
    """How much of a child's DNA comes from each parent, by sex of the child, from GRCh38's chromosome lengths
    (Ensembl REST): 22 autosomes from each, the X from the mother, and the X (daughter) or Y (son) from the father;
    the mitochondrial DNA from the mother."""
    from cluster_analysis import sources

    def fetch():
        r = sources._request("GET", "https://rest.ensembl.org/info/assembly/homo_sapiens",
                             headers={"Content-Type": "application/json"}, timeout=60) or {}
        return {x["name"]: x["length"] for x in r.get("top_level_region", []) if x.get("coord_system") == "chromosome"}
    try:
        lengths = sources._cached("ensembl_assembly", "GRCh38", fetch) or {}
    except Exception:
        return None
    auto = sum(lengths.get(str(c), 0) for c in range(1, 23))
    x, y, mt = lengths.get("X"), lengths.get("Y"), lengths.get("MT", 0)
    if not auto or not x or not y:
        return None
    out = {"lengths": {"autosomes": auto, "X": x, "Y": y, "MT": mt}}
    for child, from_father in (("XX", x), ("XY", y)):
        mother, father = auto + x + mt, auto + from_father
        out[child] = {"XX": round(mother / (mother + father), 4), "XY": round(father / (mother + father), 4)}
    return out


def model_rsids(models):
    return {v["rsid"] for m in models for v in m["variants"]}


# --- One person ------------------------------------------------------------------------------------------------------

def person_scores(models, calls, sex=None, min_share=0.5):
    """Where one person's genes place them on every trait, among Europeans (the Biomarkers tab). Traits studied in the
    other sex only are left out; so are traits with fewer than half their variants read."""
    keep = "female" if sex == "female" else "male" if sex == "male" else None
    feat = {f["id"]: f for f in featured()}
    from cluster_analysis.inheritance import gwas_impact
    imp = gwas_impact.load()
    out = []
    for m in models:
        if m["trait"] in NOT_A_TRAIT:
            continue
        studied = studied_sex(m.get("sample"))
        if studied and keep and studied != keep:
            continue
        mean = var = s = 0.0
        used, parts = 0, []
        for v in m["variants"]:
            w, f = v["w"], v["freq"]
            mu, vv = moments(f, bool(v.get("x")) and sex == "male")
            mean += mu * w
            var += vv * w * w
            d = copies(calls.get(v["rsid"]), v)
            s += (2 * f if d is None else d) * w
            used += d is not None
            parts.append({"rsid": v["rsid"], "gene": v["gene"], "allele": v["allele"], "raises": w > 0, "copies": d,
                          "average": round(2 * f, 2), "shift": 0.0 if d is None else (d - 2 * f) * w})
        if var <= 0 or used < max(MIN_VARIANTS, min_share * len(m["variants"])):
            continue
        sd = math.sqrt(var)
        for p in parts:
            p["shift"] = round(p["shift"] / sd, 3)
        z = (s - mean) / sd
        out.append({"id": m["id"], "uri": m.get("uri"), "trait": m["trait"], "category": m["category"], "study": m["study"],
                    "pmid": m["pmid"], "author": m["author"], "year": m["year"], "n": m["n"], "kind": m["kind"],
                    "reported": m.get("reported"), "definition": m.get("definition"), "studied_sex": studied,
                    "z": round(z, 3), "pct": round(100 * phi(z), 1), "used": used, "variants": len(m["variants"]),
                    "impact": round(100 * imp[m["id"]]["r2_lead"], 2) if m["id"] in imp and not imp[m["id"]].get("flag") else None,
                    "impact_flag": (imp.get(m["id"]) or {}).get("flag"), "impact_rank": (imp.get(m["id"]) or {}).get("rank_pct"),
                    "top": sorted(parts, key=lambda p: -abs(p["shift"]))[:10],
                    # A familiar trait (featured.json): its plain name and directions, shown first
                    **({"featured": {**{k: feat[m["id"]].get(k) for k in ("name", "more", "less", "sex", "group", "impact")}, "order": list(feat).index(m["id"])}} if m["id"] in feat else {})})
    return out


def run_people(ids=None):
    """trait_scores.json for each profile (data/output/.../profiles/<id>/): personal, kept out of git."""
    from cluster_analysis.inheritance import inheritance as ih
    ps = json.load(open(ih.PROFILES, encoding="utf-8"))["profiles"]
    models = load_models()
    rsids = model_rsids(models)
    for p in ps:
        if ids and p["id"] not in ids:
            continue
        try:
            calls, _ = ih.parent_calls(p["dna"], rsids)
        except SystemExit as e:  # no calls on this build yet
            print(f"⚠ {p['id']}: skipped ({e})")
            continue
        rows = person_scores(models, calls, p.get("sex"))
        out = os.path.join(ih.PROFILE_DIR, p["id"])
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "trait_scores.json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
        print(f"✅ {p['id']}: {len(rows):,} traits scored → {out}")


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        build_models()
        load_models()   # and their definitions
    elif sys.argv[1:2] == ["person"]:
        run_people(sys.argv[2:] or None)   # python -m cluster_analysis.inheritance.predict person [XY_1 ...]
    else:
        print(__doc__)
