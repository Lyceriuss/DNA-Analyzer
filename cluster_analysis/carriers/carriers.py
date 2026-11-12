# cluster_analysis/carriers/carriers.py
"""
Carrier screening from a chip: every ClinVar pathogenic or likely pathogenic variant the person's DNA says something
about, with the chance they carry it.

    python -m cluster_analysis.carriers sites                         # the public reference, once (a few minutes)
    python -m cluster_analysis.carriers person --dna data/input/MyHeritage_raw_dna_data_XY.csv --out-dir DIR

Sources, all read offline except the chip study:
  ClinVar (GRCh38 VCF)     the variants, their gene, condition, review stars and disease IDs (OMIM, Orphanet)
  HPO annotations          inheritance of each disease (phenotype.hpoa), and of each gene's diseases as a fallback
                           (genes_to_disease.txt)
  1000 Genomes site list   European frequency of each variant: the chance of carrying it before any test
  imputability map         how well a chip plus imputation sees each variant (genome/imputability.py)
  Europe PMC               the chip study quoted for very rare chip calls (Weedon et al., BMJ 2021)

The person's own data: Beagle's output (genotype probabilities at every panel site, chip calls included) and, for chip
SNPs the panel doesn't hold, the raw file lifted to GRCh38.

Per variant, the chance of carrying it (at least one copy):
  measured     the chip's call (1 or 0); a carrier call of a variant 1000 Genomes doesn't have, or has at frequency 0
               in Europeans, is flagged for confirmation: such chip calls are mostly false (the study above)
  imputed      1 - P(no copy) from Beagle's genotype probabilities; for a carrier call, at most the share of such
               calls (same frequency band and Beagle certainty) that proved right in the person's own validation
  not carried  the chance it was missed: the European carrier frequency, lowered by the share of real carriers the
               imputation finds at sites like it (the map's sensitivity) where the site is reliable; at sites the map
               calls uncertain or not knowable the test says little, so the population chance stands

Writes car_variants.json (rows for the explorer's Carriers tab) and car_genes.json (one row per gene) to --out-dir.
"""
import argparse
import gzip
import json
import os
import re
from collections import defaultdict

from cluster_analysis import sources
from genome import build as gbuild
from genome import impute
from genome.loader import person_label

REF = gbuild.REF
CLINVAR = gbuild.path("clinvar")
HPOA = os.path.join(REF, "hpo", "phenotype.hpoa")
G2D = os.path.join(REF, "hpo", "genes_to_disease.txt")
MAP = os.path.join(REF, "imputability", "clinvar_variants.json")
SITES_OUT = os.path.join(REF, "carriers", "sites.json")

# HPO's mode-of-inheritance terms (ontology IDs and their HPO labels)
MODES = {"HP:0000007": "AR", "HP:0000006": "AD", "HP:0001419": "XLR", "HP:0001423": "XLD", "HP:0001417": "XL",
         "HP:0001427": "MT", "HP:0001450": "YL"}
CHIP_STUDY = "33589468"  # Weedon et al., BMJ 2021: SNP chips against sequencing for rare pathogenic variants
CARRIER_P, POSSIBLE_P = 0.9, 0.1
CHROMS = [str(c) for c in range(1, 23)] + ["X"]


# --- the public reference ---------------------------------------------------------------------------------------

def clinvar():
    """{(chrom, pos, ref, alt): row} for germline ClinVar pathogenic and likely pathogenic variants (no conflicts)."""
    stars = {"practice_guideline": 4, "reviewed_by_expert_panel": 3, "criteria_provided,_multiple_submitters,_no_conflicts": 2,
             "criteria_provided,_single_submitter": 1}
    out = {}
    with gzip.open(CLINVAR, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.rstrip("\n").split("\t", 8)
            if p[0] not in CHROMS:
                continue
            info = dict(x.split("=", 1) for x in p[7].split(";") if "=" in x)
            sig = info.get("CLNSIG", "")
            if not sig.startswith(("Pathogenic", "Likely_pathogenic")) or "onflicting" in sig or info.get("ORIGIN") == "2":
                continue
            # CLNDN and CLNDISDB list the same conditions in the same order: each condition with its OMIM and Orphanet IDs
            groups = [(n.replace("_", " "), [("ORPHA:" + x.split(":", 1)[1]) if x.startswith("Orphanet:") else x
                                             for x in d.split(",") if x.startswith(("OMIM:", "Orphanet:"))])
                      for n, d in zip(info.get("CLNDN", "").split("|"), info.get("CLNDISDB", "").split("|"))
                      if n not in ("not_provided", "not_specified", "")]
            out[(p[0], int(p[1]), p[3], p[4])] = {
                "gene": info.get("GENEINFO", "").split(":")[0], "rsid": "rs" + info["RS"] if "RS" in info else None,
                "significance": sig.split("|")[0].replace("_", " "), "stars": stars.get(info.get("CLNREVSTAT", ""), 0),
                "conditions": groups}
    return out


def inheritance():
    """({disease ID: modes}, {gene: modes of its Mendelian diseases}) from HPO."""
    by_disease = defaultdict(set)
    with open(HPOA, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) > 10 and p[10] == "I" and p[3] in MODES:
                by_disease[p[0]].add(MODES[p[3]])
    by_gene = defaultdict(set)
    with open(G2D, encoding="utf-8") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 4 and p[2] == "MENDELIAN":
                by_gene[p[1]] |= by_disease.get(p[3], set())
    return by_disease, by_gene


def eur_frequencies(wanted):
    """{(chrom, pos, ref, alt): EUR allele frequency} from the panel's site list, for the wanted variants."""
    pos_by_chrom = defaultdict(set)
    for c, pos, _, _ in wanted:
        pos_by_chrom[c].add(str(pos))
        pos_by_chrom["chr" + c].add(str(pos))  # the site list names chromosomes 1 or chr1, depending on its build
    out = {}
    eur = re.compile(r"(?:^|;)EUR_AF=([\d.e-]+)")
    with gzip.open(impute.panel(gbuild.panel_name())["sites"], "rt") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.split("\t", 8)
            if p[1] not in pos_by_chrom.get(p[0], ()):
                continue
            key = (p[0].removeprefix("chr"), int(p[1]), p[3], p[4])
            if key in wanted:
                m = eur.search(p[7])
                out[key] = float(m.group(1)) if m else None
    return out


def chip_study():
    """The chip study's title, citation and the sentences on very rare variants, quoted from its abstract."""
    def fetch():
        return sources._request("GET", "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                                params={"query": f"EXT_ID:{CHIP_STUDY} AND SRC:MED", "format": "json", "resultType": "core"})
    r = sources._cached("europepmc_core", CHIP_STUDY, fetch)["resultList"]["result"][0]
    text = re.sub(r"<[^>]+>", " ", r.get("abstractText", ""))
    quote = [s.strip() for s in re.split(r"(?<=\.)\s+(?=[A-Z])", text) if "positive predictive value was very low" in s]
    return {"pmid": CHIP_STUDY, "title": r["title"], "journal": r["journalInfo"]["journal"]["title"], "year": r["pubYear"],
            "authors": r["authorString"], "quote": quote[0] if quote else None}


def build_sites():
    """The person-independent reference: every variant with its inheritance, frequency and imputability."""
    print("ClinVar ...", flush=True)
    cv = clinvar()
    print(f"  {len(cv):,} pathogenic or likely pathogenic\nHPO inheritance ...", flush=True)
    by_disease, by_gene = inheritance()
    seen = {(v["chrom"], v["pos"], v["ref"], v["alt"]): v for v in json.load(open(MAP, encoding="utf-8"))}
    print("European frequencies from the 1000 Genomes site list (a few minutes) ...", flush=True)
    af = eur_frequencies(set(cv))
    rows = []
    for (c, pos, ref, alt), v in cv.items():
        # ClinVar lists every condition the variant was reported for, in no meaningful order, each with its OMIM and
        # Orphanet IDs. Each condition gets HPO's inheritance; the headline is the first recessive one (what carrier
        # status is about), else the first with any inheritance. The others are kept, with theirs.
        known = []
        for name, ids in v["conditions"]:
            m = set().union(*(by_disease.get(d, set()) for d in ids)) if ids else set()
            if m and name not in (k["name"] for k in known):
                known.append({"name": name, "modes": sorted(m)})
        head = next((k for k in known if {"AR", "XLR"} & set(k["modes"])), known[0] if known else None)
        cond = head["name"] if head else (v["conditions"][0][0] if v["conditions"] else "not named")
        modes, basis = (set(head["modes"]), "condition") if head else (set(), None)
        also = [k for k in known if k is not head][:4]
        if not modes and by_gene.get(v["gene"]):
            modes, basis = by_gene[v["gene"]], "gene"
        m = seen.get((c, pos, ref, alt), {})
        rows.append({"chrom": c, "pos": pos, "ref": ref, "alt": alt, **{k: v[k] for k in ("gene", "rsid", "significance", "stars")}, "condition": cond,
                     "modes": sorted(modes), "modes_from": basis, "also": also, "eur_af": af.get((c, pos, ref, alt)),
                     "in_panel": (c, pos, ref, alt) in af,
                     "class": m.get("class") or ("not_mapped" if c == "X" and (c, pos, ref, alt) in af else None),
                     "r2": m.get("r2"), "sensitivity": m.get("sensitivity")})
    os.makedirs(os.path.dirname(SITES_OUT), exist_ok=True)
    meta = {"clinvar": os.path.basename(CLINVAR), "hpo": open(HPOA, encoding="utf-8").readline().strip(),
            "chip_study": chip_study()}
    tmp = SITES_OUT + ".part"
    json.dump({"meta": meta, "variants": rows}, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, SITES_OUT)
    print(f"Wrote {SITES_OUT}: {len(rows):,} variants, {sum(r['in_panel'] for r in rows):,} in the panel, "
          f"{sum(bool(r['modes']) for r in rows):,} with an inheritance mode")


# --- the person -------------------------------------------------------------------------------------------------

def imputed_folder(person):
    P = impute.panel(gbuild.panel_name())
    return P, os.path.join(impute.OUT, person) if P["name"] == impute.DEFAULT_PANEL else os.path.join(impute.OUT, person, P["name"])


def call_accuracy(person):
    """(af, best GP) -> (share of such carrier calls that were right, frequency band it was measured in), from the
    person's own validation (genome/impute.py --validate: hidden chip SNPs imputed and compared). A band with too few
    hidden carriers borrows the next more common band's, an upper bound for rarer variants."""
    path = os.path.join(imputed_folder(person)[1], "calibration.json")
    cells = json.load(open(path))["cells"] if os.path.exists(path) else {}
    bands = ["rare", "uncommon", "common"]

    def at(af, gp):
        band = impute.freq_band(af)
        for b in bands[bands.index(band) if band in bands else 0:]:
            cell = cells.get(f"{b}|{impute.gp_band(gp)}|carrier")
            if cell and cell["n"] >= impute.MIN_N:
                return cell["rate"], b
        return None, None
    return at


def beagle_calls(person, wanted):
    """{(chrom, pos, ref, alt): (measured?, alt copies, genotype probabilities, ploidy)} from the person's Beagle output."""
    P, folder = imputed_folder(person)
    out = {}
    for c in CHROMS:
        here = {str(pos) for (cc, pos, _, _) in wanted if cc == c}
        if not here:
            continue
        for vcf in impute.outputs(folder, c, P):
            with gzip.open(vcf, "rt") as f:
                for line in f:
                    if line[0] == "#":
                        continue
                    p = line.split("\t", 3)
                    if p[1] not in here:
                        continue
                    _, pos, _, ref, alt, _, _, info, fmt, sample = line.rstrip("\n").split("\t")
                    key = (c, int(pos), ref, alt)
                    if key not in wanted:
                        continue
                    v = dict(zip(fmt.split(":"), sample.split(":")))
                    gt = re.split(r"[|/]", v["GT"])
                    gp = [float(x) for x in v["GP"].split(",")] if "GP" in v else None
                    copies = sum(int(x) for x in gt)
                    out[key] = ("IMP" not in info.split(";"), copies, gp or [float(copies == i) for i in range(len(gt) + 1)], len(gt))
        print(f"  chr{c}: {sum(1 for k in out if k[0] == c):,} variants in the person's imputed calls", flush=True)
    return out


def chip_only_calls(dna, wanted):
    """{(chrom, pos, ref, alt): alt copies} for single-letter variants the raw chip file measures but the panel lacks."""
    raw, _ = impute.lift_calls(impute.read_csv(dna, CHROMS)) if gbuild.BUILD == "GRCh38" else (impute.read_csv(dna, CHROMS), None)
    by_pos = defaultdict(list)
    for k in wanted:
        if len(k[2]) == 1 and len(k[3]) == 1:
            by_pos[(k[0], k[1])].append(k)
    out = {}
    for c, rows in raw.items():
        for pos, _, gt in rows:
            for key in by_pos.get((c, pos), ()):
                ref, alt = key[2], key[3]
                if set(gt) <= {ref, alt}:
                    out[key] = gt.count(alt)
    return out


def carrier_prior(af, haploid):
    """Chance of carrying at least one copy before any test, from the European allele frequency."""
    if af is None:
        return None
    return af if haploid else 1 - (1 - af) ** 2


def missed(prior, sens):
    """Chance of carrying it after a test that found nothing and finds a share sens of real carriers."""
    if prior is None or sens is None:
        return prior
    return prior * (1 - sens) / (prior * (1 - sens) + (1 - prior))


def person(dna, out_dir):
    ref = json.load(open(SITES_OUT, encoding="utf-8"))
    variants = {(v["chrom"], v["pos"], v["ref"], v["alt"]): v for v in ref["variants"]}
    pid = person_label(dna)
    print(f"{pid}: Beagle output ...", flush=True)
    calls = beagle_calls(pid, set(k for k, v in variants.items() if v["in_panel"]))
    print(f"{pid}: chip SNPs the panel lacks ...", flush=True)
    chip = chip_only_calls(dna, set(k for k, v in variants.items() if not v["in_panel"]))
    accuracy = call_accuracy(pid)
    rows, unseen = [], defaultdict(int)
    for key, v in variants.items():
        base = {k: v[k] for k in ("gene", "rsid", "chrom", "pos", "ref", "alt", "significance", "stars", "condition", "modes", "modes_from", "also", "eur_af")}
        cls = v["class"]
        if key in calls:
            measured, copies, gp, ploidy = calls[key]
            prior = carrier_prior(v["eur_af"], ploidy == 1)
            accurate = None
            if measured:
                how, p = "measured", float(copies > 0)
            else:
                how, p = "imputed", round(1 - gp[0], 4)
                if copies > 0:  # a carrier call: no surer than such calls proved in the person's own validation
                    accurate, band = accuracy(v["eur_af"], max(gp))
                    p = min(p, accurate) if accurate is not None else p
        elif key in chip:
            copies, ploidy, how, accurate = chip[key], 2, "chip only", None
            p, prior = float(copies > 0), None
        else:
            unseen[v["gene"]] += 1
            continue
        if copies > 0 and how != "imputed" or how == "imputed" and p >= CARRIER_P and cls in ("chip", "reliable"):
            status = "carrier"
        elif p >= POSSIBLE_P:
            status = "possible"
        else:
            status = "not detected"
        if status == "not detected" and cls not in ("chip", "reliable") and how == "imputed":
            unseen[v["gene"]] += 1  # the test says little here: counted with the variants a chip can't see
            continue
        # Chance of carrying it: the call's own for carriers; for a clear result, the chance it was missed
        if status == "not detected":
            chance = 0.0 if how != "imputed" else max(p, missed(prior, v["sensitivity"]) or 0.0)
        else:
            chance = p
        confirm = status == "carrier" and how != "imputed" and (not v["eur_af"])
        rows.append({**base, "class": cls, "how": how, "copies": copies, "haploid": ploidy == 1, "status": status,
                     "chance": round(chance, 6), "prior": None if prior is None else round(prior, 6),
                     "sensitivity": v["sensitivity"], "r2": v["r2"], "confirm": confirm,
                     "accuracy_band": band if accurate is not None else None})
    genes = defaultdict(lambda: {"checked": 0, "carrier": 0, "possible": 0, "missed": 0.0, "modes": set(), "conditions": set()})
    for r in rows:
        g = genes[r["gene"]]
        g["modes"] |= set(r["modes"])
        g["conditions"].add(r["condition"])
        if r["status"] == "not detected":
            g["checked"] += 1
            g["missed"] = 1 - (1 - g["missed"]) * (1 - r["chance"])
        else:
            g[r["status"]] += 1
    gene_rows = [{"gene": gn, "modes": sorted(g["modes"]), "conditions": sorted(g["conditions"])[:3], "n_conditions": len(g["conditions"]),
                  "checked": g["checked"], "carrier": g["carrier"], "possible": g["possible"], "missed": round(g["missed"], 6),
                  "unseen": unseen.get(gn, 0)} for gn, g in genes.items()]
    found = [r for r in rows if r["status"] != "not detected"]
    # The explorer gets every carrier and possible call, and per gene the checked variants as a count
    os.makedirs(out_dir, exist_ok=True)
    meta = [{"variants": len(variants), "checked": len(rows), "unseen": sum(unseen.values()), **ref["meta"]["chip_study"],
             "hpo": ref["meta"]["hpo"], "clinvar": ref["meta"]["clinvar"]}]
    for name, data in (("car_variants", found), ("car_genes", sorted(gene_rows, key=lambda g: g["gene"])), ("car_meta", meta)):
        json.dump(data, open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    by = defaultdict(int)
    for r in rows:
        by[(r["status"], r["how"])] += 1
    print(f"{pid}: {len(rows):,} variants checked; " + ", ".join(f"{s} ({h}): {n}" for (s, h), n in sorted(by.items())))
    print(f"{pid}: {sum(unseen.values()):,} variants the chip can't see; wrote car_variants, car_genes, car_meta to {out_dir}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("sites", "person"))
    ap.add_argument("--dna")
    ap.add_argument("--out-dir")
    a = ap.parse_args()
    if a.command == "sites":
        build_sites()
    else:
        if not (a.dna and a.out_dir):
            ap.error("person needs --dna and --out-dir")
        person(a.dna, a.out_dir)


if __name__ == "__main__":
    main()
