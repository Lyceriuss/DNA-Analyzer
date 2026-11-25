# cluster_analysis/inheritance/inheritance.py
"""
Inheritance: what a child of an XX and an XY profile could inherit, as odds.

At every position each parent passes one of their two copies, each with a chance of one half (a man's single X goes to
every daughter and to no son). For a variant both parents have a call at, the child's genotype odds are exact; how far
they can be trusted is how far the parents' calls can. Three parts:

  conditions  ClinVar pathogenic and likely pathogenic variants (reviewed, not conflicting) that either parent carries,
              grouped by gene, with the mode of inheritance HPO gives the condition: autosomal recessive or dominant,
              X-linked. Recessive: a child is affected when it gets a variant copy from both parents.
  traits      The single-gene traits traits.json chooses, with the variant allele from ClinVar and the mode from HPO
              where HPO gives one; the others show the child's genotype odds only.
  drugs       The drug genes: each parent passes one of their two star alleles, and CPIC's rules turn the child's pair
              into a metaboliser type (medicines.py writes them to med_diplotypes.json).

Confidence of a parent's call: an imputed call carries the share of such calls (frequency band, GP band, carrier or
not) that were right in that person's own check (genome/impute.py, calibration.json); a measured call carries the
chip's accuracy from Weedon et al., BMJ 2021 (traits.json): above 99% for common variants, 16% for very rare ones.

    python -m cluster_analysis.inheritance                      # every XX x XY pair in profiles.json
    python -m cluster_analysis.inheritance --pair XX_1 XY_1
    python -m cluster_analysis.inheritance --person XX_1         # every pair with XX_1 (profiles.py run, the pipeline)

Writes data/output/cluster_analysis_<build>/pairs/<XX>__<XY>/inh_meta, inh_conditions, inh_traits, inh_drugs (.json):
the parents' genotypes are in them, so they stay in data/output like every personal result.
"""
import argparse
import collections
import gzip
import itertools
import json
import os
import re

from genome import build as gbuild
from genome import impute
from genome.loader import imputed_path

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(os.path.dirname(HERE))
TRAITS = os.path.join(HERE, "traits.json")
PROFILES = os.path.join(os.path.dirname(HERE), "profiles.json")
HPO = os.path.join(ROOT, "data", "reference", "hpo", "phenotype.hpoa")
# ClinVar's per-submission report: which condition each submitter classified a variant pathogenic for
SUBMISSIONS = os.path.join(ROOT, "data", "reference", "clinvar", "submission_summary.txt.gz")
SUBMISSIONS_INDEX = os.path.join(ROOT, "data", "reference", "clinvar", "pathogenic_conditions.json.gz")
PAIRS_DIR = os.path.join(gbuild.OUTPUT, "pairs")
PROFILE_DIR = os.path.join(gbuild.OUTPUT, "profiles")

# HPO's mode-of-inheritance terms
MODES = {"HP:0000007": "AR", "HP:0000006": "AD", "HP:0001419": "XLR", "HP:0001423": "XLD", "HP:0001417": "XL",
         "HP:0001427": "MT"}
CONFIDENT = ("measured", "high", "medium")
# ClinVar review statuses that carry an assertion of criteria (one star and up)
REVIEWED = re.compile(r"^(?!no_assertion).*(criteria_provided|reviewed_by_expert_panel|practice_guideline)")
PATHOGENIC = re.compile(r"(^|[^_a-z])(likely_)?pathogenic", re.I)


# --- Mendel ------------------------------------------------------------------------------------------------------

def passes(copies, haploid=False):
    """Chance a parent passes a variant copy: half per copy of two; a single X (haploid) always passes what it holds."""
    if copies is None:
        return None
    return float(min(copies, 1)) if haploid else min(copies, 2) / 2


def child_copies(pm, pf):
    """[P(0), P(1), P(2)] variant copies in a child whose mother passes one with chance pm and father with pf."""
    if pm is None or pf is None:
        return None
    return [(1 - pm) * (1 - pf), pm * (1 - pf) + pf * (1 - pm), pm * pf]


def odds(xx_copies, xy_copies, on_x=False):
    """The child's variant copies: {"child": [p0, p1, p2]} on an autosome; on X {"son": [p0, p1], "daughter": [...]}:
    a son's one X comes from his mother, a daughter gets her mother's passed X and her father's only X."""
    pm = passes(xx_copies)
    if not on_x:
        return {"child": child_copies(pm, passes(xy_copies))}
    son = None if pm is None else [1 - pm, pm]
    return {"son": son, "daughter": child_copies(pm, passes(xy_copies, haploid=True))}


def outcome(mode, o):
    """What the copies mean under a mode: shares affected and carrying, per child, son or daughter (None: unknown)."""
    def sh(p, *i):
        return None if p is None else round(sum(p[k] for k in i), 6)
    if "child" in o:
        c = o["child"]
        if mode == "AR":
            return {"child": {"affected": sh(c, 2), "carrier": sh(c, 1)}}
        if mode == "AD":
            return {"child": {"affected": sh(c, 1, 2)}}
        return {"child": {"one or two copies": sh(c, 1, 2)}}
    s, d = o["son"], o["daughter"]
    if mode in ("XLR", "XL"):
        return {"son": {"affected": sh(s, 1)}, "daughter": {"affected": sh(d, 2), "carrier": sh(d, 1)}}
    if mode == "XLD":
        return {"son": {"affected": sh(s, 1)}, "daughter": {"affected": sh(d, 1, 2)}}
    return {"son": {"one copy": sh(s, 1)}, "daughter": {"one or two copies": sh(d, 1, 2)}}


# --- Sources ------------------------------------------------------------------------------------------------------

def hpo_modes(path=HPO):
    """{disease id: sorted modes} and {disease id: name} from HPO's annotations (OMIM:…, Orphanet:…)."""
    modes, names = collections.defaultdict(set), {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line[0] == "#" or line.startswith("database_id"):
                continue
            p = line.rstrip("\n").split("\t")
            did = p[0].replace("ORPHA:", "Orphanet:")
            names[did] = p[1]
            if p[3] in MODES:
                modes[did].add(MODES[p[3]])
    return {k: sorted(v) for k, v in modes.items()}, names


def pathogenic_conditions():
    """{VariationID: {MedGen CUI: n}}: how many reviewed submissions classified the variant (likely) pathogenic for
    each condition. A ClinVar record lists every condition any submitter named, and one lab may classify a variant
    pathogenic for every OMIM entry of its gene: C282Y in HFE has 30 pathogenic submissions for hemochromatosis type 1
    and one each for Alzheimer disease and the porphyrias, from a single lab's gene-wide list. Built once from
    submission_summary.txt.gz into a small index next to it."""
    if os.path.exists(SUBMISSIONS_INDEX) and (not os.path.exists(SUBMISSIONS)
                                              or os.path.getmtime(SUBMISSIONS_INDEX) >= os.path.getmtime(SUBMISSIONS)):
        with gzip.open(SUBMISSIONS_INDEX, "rt", encoding="utf-8") as f:
            return json.load(f)
    if not os.path.exists(SUBMISSIONS):
        return None
    out = collections.defaultdict(collections.Counter)
    with gzip.open(SUBMISSIONS, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.rstrip(chr(10)).split(chr(9))
            if len(p) < 7 or not re.fullmatch(r"(Likely pathogenic|Pathogenic|Pathogenic/Likely pathogenic)", p[1].strip(), re.I):
                continue
            if "no assertion" in p[6].lower() or "no classification" in p[6].lower():
                continue
            for cui in re.findall(r"\b(C\d{7}|CN\d+)\b", p[5]):
                out[p[0]][cui] += 1
    data = {k: dict(v) for k, v in out.items()}
    with gzip.open(SUBMISSIONS_INDEX + ".partial", "wt", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(SUBMISSIONS_INDEX + ".partial", SUBMISSIONS_INDEX)
    return data


def disease_entries(info):
    """ClinVar's conditions on a record, in order: (name, [ids]) per entry of CLNDN and CLNDISDB."""
    names = info.get("CLNDN", "").split("|")
    dbs = info.get("CLNDISDB", "").split("|")
    return [(n.replace("_", " "), re.findall(r"(MedGen:C\d{7}|MedGen:CN\d+|OMIM:\d+|Orphanet:\d+)", d))
            for n, d in zip(names, dbs + [""] * (len(names) - len(dbs)))]


# MedGen concepts that name no condition: "not provided", "not specified", "Inborn genetic diseases", "See cases",
# "Hereditary cancer-predisposing syndrome"
GENERIC = {"C3661900", "CN169374", "C0950123", "CN517202", "C0027672"}


def main_conditions(entries, counts):
    """The record's conditions that pathogenic submissions mainly name: at least half as many submissions as the most
    named one. C282Y keeps hemochromatosis type 1 (30) and drops the single gene-wide listings."""
    def n(e):
        return max((counts.get(i.split(":", 1)[1], 0) for i in e[1] if i.startswith("MedGen:")), default=0)
    named = [(e, n(e)) for e in entries if n(e) and not any(i.split(":", 1)[1] in GENERIC for i in e[1] if i.startswith("MedGen:"))]
    if not named:
        return []
    top = max(k for _, k in named)
    return [e for e, k in named if k * 2 >= top]


def clinvar_records(trait_rsids, pathogenic_for=None):
    """ClinVar GRCh38 records: the reviewed, non-conflicting pathogenic ones, and every record at the traits' rsids."""
    out = collections.defaultdict(list)
    with gzip.open(gbuild.path("clinvar"), "rt", encoding="utf-8") as f:
        for line in f:
            if line[0] == "#":
                continue
            c = line.rstrip("\n").split("\t")
            info = dict(x.split("=", 1) for x in c[7].split(";") if "=" in x)
            if "RS" not in info:
                continue
            rsid = "rs" + info["RS"].split("|")[0]
            sig = info.get("CLNSIG", "")
            condition = (PATHOGENIC.search(sig) and "onflicting" not in sig and "enign" not in sig
                         and REVIEWED.search(info.get("CLNREVSTAT", "")))
            if not condition and rsid not in trait_rsids:
                continue
            entries = disease_entries(info)
            if condition and pathogenic_for is not None:
                # Only the conditions a pathogenic submission names (by MedGen id); none matched: keep them all
                kept = main_conditions(entries, pathogenic_for.get(c[2]) or {})
                entries = kept or entries
            out[rsid].append({"chrom": c[0], "pos": int(c[1]), "ref": c[3], "alt": c[4].split(","), "variation_id": c[2],
                              "significance": sig.replace("_", " "), "review": info.get("CLNREVSTAT", "").replace("_", " "),
                              "conditions": [n for n, _ in entries],
                              "ids": sorted({i for _, ids in entries for i in ids if not i.startswith("MedGen:")}),
                              "gene": info.get("GENEINFO", "").split(":")[0], "pathogenic": bool(condition),
                              "clndn": info.get("CLNDN", "")})
    return out


def parent_calls(dna, rsids):
    """{rsid: {genotype, chrom, pos, tier, gp, af}} from a person's imputed file (every tier: the reader decides)."""
    path = imputed_path(dna)
    calls = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        cols = None
        for line in f:
            if line[0] == "#":
                continue
            p = [x.strip('"') for x in line.rstrip("\r\n").split(",")]
            if cols is None:
                cols = {c.upper(): i for i, c in enumerate(p)}
                continue
            if p[0] not in rsids:
                continue
            g = lambda k: p[cols[k]] if k in cols and len(p) > cols[k] else ""
            calls[p[0]] = {"genotype": g("RESULT"), "chrom": g("CHROMOSOME"), "pos": int(g("POSITION") or 0),
                           "tier": g("CONFIDENCE") or "measured", "gp": float(g("GP")) if g("GP") else None,
                           "af": float(g("EUR_AF")) if g("EUR_AF") else None}
    return calls, path


def calibration(path):
    """The person's imputation check (genome/impute.py writes calibration.json next to the imputed file)."""
    p = os.path.join(os.path.dirname(path), "calibration.json")
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return None


# --- One parent's call --------------------------------------------------------------------------------------------

def copies_of(genotype, alts, haploid=False):
    """Variant copies in a forward-strand genotype (ClinVar and the imputed files share GRCh38's forward strand); a
    man's X outside the shared regions holds one copy, written as a homozygous pair."""
    n = sum(genotype.count(a) for a in alts if len(a) == 1)
    return min(n, 1) if haploid else n


def accuracy(call, carrier, cal, chip):
    """(share right, how it was measured) for one parent's call, or (None, why not)."""
    if call["tier"] == "measured":
        af = call["af"]
        maf = None if af is None else min(af, 1 - af)
        if not carrier or (maf is not None and maf >= 0.01):
            return 0.99, "measured on the chip: above 99% for common variants (chip against sequencing, Weedon 2021)"
        if maf is not None and maf < 0.00001:
            return 0.16, "measured on the chip: only 16% of very rare chip calls were confirmed by sequencing (Weedon 2021)"
        return None, "measured on the chip: a rare variant, and chip calls get less reliable the rarer the variant (Weedon 2021)"
    if not cal or call["gp"] is None:
        return None, "imputed, without an accuracy check"
    key = f"{impute.freq_band(call['af'])}|{impute.gp_band(call['gp'])}|{'carrier' if carrier else 'noncarrier'}"
    cell = cal.get("cells", {}).get(key)
    if not cell:
        return None, "imputed; the check has no such calls"
    return cell["rate"], f"imputed: {cell['rate']:.1%} of {cell['n']:,} such calls were right in the check"


def read_parent(call, alts, haploid, cal):
    """What a parent holds at a variant: copies, genotype, tier and accuracy; copies None when the call can't be used."""
    if not call:
        return {"genotype": None, "copies": None, "tier": "no call", "accuracy": None, "how": "no call at this position"}
    n = copies_of(call["genotype"], alts, haploid)
    usable = call["tier"] in CONFIDENT
    acc, how = accuracy(call, n > 0, cal, None) if usable else (None, {
        "not_excluded": "imputation can't rule out a variant copy here",
        "low": "imputed with low confidence", "untested": "imputed, untested"}.get(call["tier"], call["tier"]))
    return {"genotype": call["genotype"], "copies": n if usable else None, "tier": call["tier"], "accuracy": acc, "how": how}


def combined(*parents):
    """The chance both parents' calls are right, when both have a measured accuracy."""
    accs = [p["accuracy"] for p in parents]
    if any(a is None for a in accs):
        return None
    r = 1.0
    for a in accs:
        r *= a
    return round(r, 4)


def on_x(chrom, pos, par):
    return chrom in ("X", "chrX", "23") and not any(a <= pos <= b for a, b in par)


# --- The three parts ----------------------------------------------------------------------------------------------

def conditions(recs, calls, cals, modes, names, par):
    """Genes where either parent carries a pathogenic variant, with the child's odds per mode."""
    by_gene = collections.defaultdict(list)
    for rsid, rows in recs.items():
        for r in rows:
            if not r["pathogenic"]:
                continue
            x = on_x(r["chrom"], r["pos"], par)
            xx = read_parent(calls["XX"].get(rsid), r["alt"], False, cals["XX"])
            xy = read_parent(calls["XY"].get(rsid), r["alt"], x, cals["XY"])
            if not (xx["copies"] or xy["copies"]):
                continue
            by_gene[r["gene"] or rsid].append({"rsid": rsid, "rec": r, "x": x, "XX": xx, "XY": xy})
    rows = []
    for gene, vs in sorted(by_gene.items()):
        x = any(v["x"] for v in vs)
        # A parent's variant copies in the gene added up: each passes one of two chromosomes, and two different variants
        # in one parent are taken to sit on different chromosomes (which a chip can't tell)
        tot = {}
        for side in ("XX", "XY"):
            cs = [v[side]["copies"] for v in vs]
            tot[side] = None if any(c is None for c in cs) else sum(cs)
        o = odds(tot["XX"], tot["XY"], on_x=x)
        ids = sorted({i for v in vs for i in v["rec"]["ids"]})
        # Each condition with the mode HPO gives it; a condition HPO doesn't annotate keeps ClinVar's name, no mode
        conds = [{"id": i, "name": names[i], "modes": [m for m in modes.get(i, []) if m != "MT"]} for i in ids if i in names]
        if x:
            for c in conds:
                c["modes"] = [m for m in c["modes"] if m.startswith("X")] or c["modes"]
        ms = sorted({m for c in conds for m in c["modes"]})
        clinvar_names = sorted({c for v in vs for c in v["rec"]["conditions"]
                                if c and c not in ("not provided", "not specified", "See cases")})
        rows.append({
            "gene": gene, "on_x": x, "modes": ms, "conditions": conds[:8], "clinvar_names": clinvar_names[:8],
            "by_mode": {m: [c["name"] for c in conds if m in c["modes"]][:4] for m in ms},
            "from_XX": passes(tot["XX"]), "from_XY": passes(tot["XY"], haploid=x),
            "variants": [{"rsid": v["rsid"], "change": f"{v['rec']['ref']}>{','.join(v['rec']['alt'])}",
                          "significance": v["rec"]["significance"], "review": v["rec"]["review"],
                          "XX": v["XX"], "XY": v["XY"]} for v in vs],
            "XX_copies": tot["XX"], "XY_copies": tot["XY"], "odds": o,
            "outcomes": {m: outcome(m, o) for m in (ms or ["none"])},
            "confidence": min((c for c in (combined(v["XX"], v["XY"]) for v in vs) if c is not None), default=None),
        })
    return rows


def coverage(recs, calls):
    """How many pathogenic positions the pair's calls can read: both confident, or not."""
    both = either_unreadable = 0
    for rsid, rows in recs.items():
        if not any(r["pathogenic"] for r in rows):
            continue
        tiers = [calls[s].get(rsid, {}).get("tier") for s in ("XX", "XY")]
        if all(t in CONFIDENT for t in tiers):
            both += 1
        elif any(t is not None for t in tiers):
            either_unreadable += 1
    return {"both_read": both, "not_readable": either_unreadable,
            "pathogenic_records": sum(1 for rows in recs.values() if any(r["pathogenic"] for r in rows))}


def traits(cfg, recs, calls, cals, modes, names, par):
    out = []
    for t in cfg["traits"]:
        pat = re.compile(t["clinvar"], re.I)
        vs = []
        for rsid in t["rsids"]:
            rec = next((r for r in recs.get(rsid, []) if pat.search(r["clndn"])), None)
            if not rec:
                continue
            x = on_x(rec["chrom"], rec["pos"], par)
            alts = [a for a in rec["alt"] if a != "."]
            vs.append({"rsid": rsid, "allele": ",".join(alts), "ref": rec["ref"], "x": x,
                       "condition": next((c for c in rec["conditions"] if pat.search(c.replace(" ", "_"))), rec["conditions"][0]),
                       "XX": read_parent(calls["XX"].get(rsid), alts, False, cals["XX"]),
                       "XY": read_parent(calls["XY"].get(rsid), alts, x, cals["XY"])})
        if not vs:
            continue
        x = any(v["x"] for v in vs)
        tot = {s: (None if any(v[s]["copies"] is None for v in vs) else sum(v[s]["copies"] for v in vs)) for s in ("XX", "XY")}
        ms = [m for m in modes.get(t["omim"], []) if m != "MT"]
        o = odds(tot["XX"], tot["XY"], on_x=x)
        out.append({"id": t["id"], "name": t["name"], "about": t["about"], "gene": t["gene"], "omim": t["omim"],
                    "omim_name": names.get(t["omim"]), "modes": ms, "on_x": x, "variants": vs,
                    "XX_copies": tot["XX"], "XY_copies": tot["XY"], "odds": o,
                    "outcomes": {m: outcome(m, o) for m in ms},
                    "confidence": min((c for c in (combined(v["XX"], v["XY"]) for v in vs) if c is not None), default=None)})
    return out


def drugs(xx_id, xy_id):
    """Each drug gene: the parents' star alleles and the child's type odds by CPIC's rules."""
    def load(pid, name):
        try:
            return json.load(open(os.path.join(PROFILE_DIR, pid, name), encoding="utf-8"))
        except (OSError, ValueError):
            return None
    # The pair table is person-free: any profile's copy will do
    table = next((t for t in (load(pid, "med_diplotypes.json") for pid in [xy_id, xx_id] + sorted(os.listdir(PROFILE_DIR))
                              if os.path.isdir(os.path.join(PROFILE_DIR, pid))) if t), None)
    genes = {s: {r["gene"]: r for r in (load(pid, "med_genes.json") or [])} for s, pid in (("XX", xx_id), ("XY", xy_id))}
    if not table:
        return []
    out = []
    for gene, t in table.items():
        a, b = genes["XX"].get(gene), genes["XY"].get(gene)
        if not a or not b or not a.get("alleles") or not b.get("alleles"):
            continue
        ma, fa = a["alleles"].split("/"), b["alleles"].split("/")
        if len(ma) != 2 or len(fa) != 2:
            continue
        kids = collections.Counter()
        for m, f in itertools.product(ma, fa):
            kids[tuple(sorted((m, f), key=lambda s: (s != "*1", s)))] += 0.25
        rows = []
        for pair, p in kids.items():
            key = f"{pair[0]}/{pair[1]}"
            typ = t["types"].get(key) or t["types"].get(f"{pair[1]}/{pair[0]}")
            rows.append({"alleles": key, "type": typ, "p": p})
        by = collections.Counter()
        for r in rows:
            by[r["type"]] += r["p"]
        conf = lambda r: "measured" if not any(s.get("confidence") not in ("measured",) for s in json.loads(r.get("snps") or "[]")
                                               if s.get("copies")) else "partly imputed"
        out.append({"gene": gene, "XX_alleles": a["alleles"], "XX_type": a["phenotype"], "XY_alleles": b["alleles"],
                    "XY_type": b["phenotype"], "children": sorted(rows, key=lambda r: -r["p"]),
                    "types": [{"type": k, "p": v} for k, v in sorted(by.items(), key=lambda kv: -kv[1])],
                    "functions": {k: v for k, v in t["functions"].items() if k in set(ma + fa)},
                    "XX_calls": conf(a), "XY_calls": conf(b), "XX_note": a.get("note"), "XY_note": b.get("note")})
    return out


# --- A pair --------------------------------------------------------------------------------------------------------

def pairs(person=None):
    """Every XX x XY pair of finished profiles; with person, that person (finished or being added) with each finished
    profile of the other sex."""
    ps = json.load(open(PROFILES, encoding="utf-8"))["profiles"]
    ok = lambda p: not p.get("pending") or p["id"] == person
    xx = [p for p in ps if p.get("sex") == "female" and ok(p)]
    xy = [p for p in ps if p.get("sex") == "male" and ok(p)]
    return [(a, b) for a in xx for b in xy if person is None or person in (a["id"], b["id"])]


def run_pair(a, b, recs, modes, names, cfg, models=()):
    par = gbuild.par()
    from cluster_analysis.inheritance import predict
    rsids = set(recs) | predict.model_rsids(models)
    calls, cals = {}, {}
    for side, p in (("XX", a), ("XY", b)):
        calls[side], path = parent_calls(p["dna"], rsids)
        cals[side] = calibration(path)
    rows = {"inh_predictions": predict.predictions(models, calls["XX"], calls["XY"]),
            "inh_conditions": conditions(recs, calls, cals, modes, names, par),
            "inh_traits": traits(cfg, recs, calls, cals, modes, names, par),
            "inh_drugs": drugs(a["id"], b["id"])}
    meta = {"XX": a["id"], "XY": b["id"], "coverage": coverage(recs, calls),
            "counts": {k: len(v) for k, v in rows.items()}, "chip_accuracy": cfg["chip_accuracy"],
            "hpo_version": hpo_version(), "categories": predict.category_definitions(models),
            "genome": predict.genome_shares(), "featured": predict.featured(), "efo_version": predict.efo_version()}
    out = os.path.join(PAIRS_DIR, f"{a['id']}__{b['id']}")
    os.makedirs(out, exist_ok=True)
    for name, data in list(rows.items()) + [("inh_meta", meta)]:
        with open(os.path.join(out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✅ {a['id']} × {b['id']}: {len(rows['inh_predictions'])} traits predicted, "
          f"{len(rows['inh_conditions'])} genes with a pathogenic variant carried, "
          f"{len(rows['inh_traits'])} traits, {len(rows['inh_drugs'])} drug genes; "
          f"{meta['coverage']['both_read']:,} pathogenic positions read in both → {out}")
    return meta


def hpo_version():
    try:
        with open(HPO, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#version"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pair", nargs=2, metavar=("XX", "XY"), help="one pair (default: every XX x XY in profiles.json)")
    ap.add_argument("--person", help="every pair with this profile (profiles.py run, the pipeline)")
    a = ap.parse_args()
    cfg = json.load(open(TRAITS, encoding="utf-8"))
    ps = {p["id"]: p for p in json.load(open(PROFILES, encoding="utf-8"))["profiles"]}
    todo = [(ps[a.pair[0]], ps[a.pair[1]])] if a.pair else pairs(a.person)
    if not todo:
        print("No XX and XY profile to pair." if not a.person else f"{a.person}: no profile of the other sex to pair with.")
        return
    modes, names = hpo_modes()
    recs = clinvar_records({r for t in cfg["traits"] for r in t["rsids"]}, pathogenic_conditions())
    print(f"ClinVar: {sum(1 for rows in recs.values() if any(r['pathogenic'] for r in rows)):,} reviewed pathogenic positions; "
          f"HPO: {len(modes):,} conditions with a mode")
    from cluster_analysis.inheritance import predict
    models = predict.load_models()
    print(f"GWAS Catalog: {len(models):,} trait models")
    for x, y in todo:
        try:
            run_pair(x, y, recs, modes, names, cfg, models)
        except SystemExit as e:  # a parent without calls on this build yet: the pair waits for them
            print(f"⚠ {x['id']} × {y['id']}: skipped ({e})")


if __name__ == "__main__":
    main()
