# cluster_analysis/evidence/gene_calls.py
"""
A call per gene (more active, typical, less active) from the person's own variants, read against public sources.
It replaces the library's per-SNP calls: any gene, any variant the person carries, not only the curated 247 SNPs.

    python -m cluster_analysis.evidence.gene_calls                       # the theme genes, for each theme's person
    python -m cluster_analysis.evidence.gene_calls --person XX           # one theme person only (XX: female fertility genes)
    python -m cluster_analysis.evidence.gene_calls --dna data/input/X.csv --genes MTHFR CYP2C19

For each gene, strongest evidence first (the same order as evidence_call.py):

  protein     every missense or stop variant UniProt lists for the protein (with its dbSNP id), matched to the person's
              calls by the DNA letter that makes the change. A carried change is read by:
                measured    MaveDB deep mutational scan of that exact change          → GoF / LoF / normal
                curated     UniProt's curated effect with a direction                 → GoF / LoF
                truncating  the change is a stop                                      → LoF
                predicted   SIFT and PolyPhen both call it damaging                   → LoF, worded "likely"
  expression  GTEx v8: the gene's strongest independent eQTL (rank 1, lowest p across tissues, leading in 2+ tissues). The allele that differs
              from the common European one raises or lowers expression; the person's copies of it decide. Mixed
              directions across tissues → altered.

A protein change outranks expression (a broken protein is less active whatever its mRNA level). With neither effect,
the gene is "normal" when something was read (the usual genotype at its eQTL, no carried change with evidence),
"unknown" when nothing about it could be read. Only measured or high-confidence imputed calls count.

Public identifiers only are sent to UniProt, MaveDB, GTEx and Ensembl; genotypes stay local.
Writes data/output/cluster_analysis/gene_calls_<person>.json: {gene: call}.
"""
import argparse
import glob
import json
import os
import re
import statistics
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from cluster_analysis import sources
from cluster_analysis.evidence.evidence_call import text_direction
from cluster_analysis.evidence.function_evidence import AA3, FUNCTION_WORDS, mavedb_scores, mavedb_sets, uniprot_variants
from cluster_analysis.lifecycle.gene_trace import uniprot_entry
from genome import build as gbuild
from genome.loader import CONFIDENT, imputed_path, iter_calls, person_label

HERE = os.path.dirname(__file__)
OUT_DIR = gbuild.OUTPUT
EFFECTS = ("GoF", "LoF", "altered")
BASIS_RANK = {"measured": 0, "curated": 1, "truncating": 2, "predicted": 3, "expression": 4}
WORKERS = 3                         # parallel API requests
MIN_TISSUES = 2                     # an expression call needs its eQTL to lead in at least this many tissues
GENOMIC = re.compile(r"g\.\d+([ACGT])>([ACGT])$")


def _gtex(path, params):
    time.sleep(0.15)
    return sources._request("GET", f"https://gtexportal.org/api/v2/{path}", ok_404=True, params=params, timeout=90) or {}


def gtex_top_eqtl(gene):
    """The gene's strongest independent eQTL in GTEx v8: {rsid, ref, alt, tissues: [{tissue, nes, p}]} (NES of alt)."""
    def fetch():
        g = _gtex("reference/gene", {"geneId": gene, "gencodeVersion": "v26", "genomeBuild": "GRCh38/hg38"}).get("data") or []
        gid = next((x["gencodeId"] for x in g if x.get("geneSymbol") == gene), None)
        if not gid:
            return None
        try:
            rows = _gtex("association/independentEqtl", {"gencodeId": gid, "datasetId": "gtex_v8"}).get("data") or []
        except Exception:
            # GTEx answers 500 for some genes (COMT); their full eQTL list works: its strongest variant is the same lead
            # signal, with the tissues where it is significant
            rows = _gtex("association/singleTissueEqtl", {"gencodeId": gid, "datasetId": "gtex_v8", "itemsPerPage": 100000}).get("data") or []
            if rows:
                lead = min(rows, key=lambda r: r["pValue"])["variantId"]
                rows = [dict(r, rank=1) for r in rows if r["variantId"] == lead]
        return [{"rsid": r.get("snpId"), "variant": r["variantId"], "tissue": r["tissueSiteDetailId"], "rank": r.get("rank"),
                 "nes": r["nes"], "p": r["pValue"]} for r in rows]
    rows = [r for r in (sources._cached("gtex_ind_eqtl", gene, fetch) or []) if r.get("rsid") and r.get("rank") == 1]
    if not rows:
        return None
    best = min(rows, key=lambda r: r["p"])
    _, _, ref, alt, _ = best["variant"].split("_")
    if len(ref) != 1 or len(alt) != 1:
        return None
    return {"rsid": best["rsid"], "ref": ref, "alt": alt,
            "tissues": sorted(({"tissue": r["tissue"], "nes": r["nes"], "p": r["p"]} for r in rows if r["rsid"] == best["rsid"]),
                              key=lambda r: r["p"])}


def protein_variants(gene):
    """UniProt's single-residue changes with a dbSNP id: [{rsid, ref, alt (DNA, forward strand), change, curated, preds,
    stop}]. One rsid can make several changes (one per DNA letter); each is kept with its letter."""
    entry = uniprot_entry(gene)
    if not entry:
        return []
    out = []
    for f in uniprot_variants(entry["primaryAccession"]).get("features", []):
        if f.get("type") != "VARIANT":
            continue
        wt, alt_aa, pos = f.get("wildType"), f.get("alternativeSequence"), f.get("begin")
        rs = next((x["id"] for x in f.get("xrefs", []) if str(x.get("id", "")).startswith("rs")), None)
        if not (rs and wt and alt_aa and pos and len(wt) == 1 and len(alt_aa) == 1):
            continue
        for loc in f.get("genomicLocation") or []:
            m = GENOMIC.search(loc)
            if not m:
                continue
            curated = [d["value"] for d in f.get("descriptions") or [] if d.get("value")]
            curated += [a["name"] for a in f.get("association") or [] if a.get("name")]
            out.append({"rsid": rs, "ref": m.group(1), "alt": m.group(2), "stop": alt_aa == "*",
                        "change": f"p.{AA3.get(wt, wt)}{pos}{AA3.get(alt_aa, alt_aa)}", "short": f"{wt}{pos}{alt_aa}",
                        "curated": [c for c in curated if any(w in c.lower() for w in FUNCTION_WORDS)],
                        "preds": {p.get("predAlgorithmNameType"): p.get("predictionValType") for p in f.get("predictions") or []
                                  if p.get("predAlgorithmNameType") in ("SIFT", "PolyPhen")}})
    return out


def read_protein_change(gene, v):
    """(sign, basis, detail) for one carried change, or None without evidence about it."""
    mave = []
    for s in mavedb_sets(gene):
        sc = mavedb_scores(s["urn"]).get(v["change"])
        if isinstance(sc, (int, float)):
            mave.append(sc)
    if mave:
        med = statistics.median(mave)
        ratio = med / 100 if med > 10 else med
        sign = -1 if ratio < 0.8 else 1 if ratio > 1.25 else 0
        return sign, "measured", f"{v['change']}: {ratio:.0%} of wild-type function in MaveDB assays (median of {len(mave)})"
    d = text_direction(v["curated"]) if v["curated"] else 0
    if d:
        return d, "curated", f"{v['change']}: {'; '.join(v['curated'])[:220]}"
    if v["stop"]:
        return -1, "truncating", f"{v['change']}: a stop, the protein is cut short"
    if v["preds"].get("SIFT") == "deleterious" and v["preds"].get("PolyPhen") in ("probably damaging", "possibly damaging"):
        return -1, "predicted", f"{v['change']}: SIFT {v['preds']['SIFT']}, PolyPhen {v['preds']['PolyPhen']}"
    return None


def call_gene(gene, pv, eq, calls, vep):
    """One gene's call from its protein variants (pv), its top eQTL (eq), the person's calls {rsid: (gt, tier)} and
    VEP records (European frequencies) for the eQTL SNPs."""
    out = {"function": "unknown", "basis": "none", "detail": None, "rsid": None, "genotype": None, "dose": None,
           "variants": [], "n_read": 0}
    read = {v["rsid"] for v in pv if v["rsid"] in calls}
    found = []
    for v in pv:
        if v["rsid"] not in calls:
            continue
        gt = calls[v["rsid"]][0]
        copies = gt.count(v["alt"])
        if not copies:
            continue
        ev = read_protein_change(gene, v)
        item = {"rsid": v["rsid"], "change": v["short"], "copies": copies, "genotype": gt}
        if ev:
            sign, basis, detail = ev
            item.update(function="normal" if sign == 0 else {1: "GoF", -1: "LoF"}[sign], basis=basis, detail=detail)
        else:
            item.update(function="unknown", basis="none", detail=f"{v['change']}: no measured, curated or predicted effect")
        found.append(item)
    out["variants"] = found[:12]
    effects = [x for x in found if x["function"] in ("GoF", "LoF")]
    if effects:
        top = min(BASIS_RANK[x["basis"]] for x in effects)
        best = [x for x in effects if BASIS_RANK[x["basis"]] == top]
        fn = best[0]["function"] if len({x["function"] for x in best}) == 1 else "altered"
        b = best[0]
        out.update(function=fn, basis=b["basis"], detail="; ".join(x["detail"] for x in best[:3]), rsid=b["rsid"],
                   genotype=b["genotype"], dose=b["copies"], n_read=len(read))
        return out
    measured_normal = [x for x in found if x["function"] == "normal"]

    unknown = [x for x in found if x["function"] == "unknown"]
    note = ("; also carries " + ", ".join(x["change"] for x in unknown[:3]) + " (no known effect)") if unknown else ""
    # An eQTL that leads in a single tissue is too narrow to call the gene from
    if eq and eq["rsid"] in calls and len(eq["tissues"]) >= MIN_TISSUES:
        read.add(eq["rsid"])
        gt = calls[eq["rsid"]][0]
        v = vep.get(eq["rsid"]) or {}
        af = dict(v.get("eur_af") or {})
        alt_f = af.get(eq["alt"])
        if alt_f is not None and set(gt) <= {eq["ref"], eq["alt"]}:
            common = eq["alt"] if alt_f > 0.5 else eq["ref"]
            other = eq["ref"] if common == eq["alt"] else eq["alt"]
            # NES is for the alternative allele; turn it into the effect of the allele that differs from the common one
            signs = {(1 if t["nes"] > 0 else -1) * (1 if other == eq["alt"] else -1) for t in eq["tissues"]}
            dose = gt.count(other)
            tissues = ", ".join(t["tissue"].replace("_", " ") for t in eq["tissues"][:3])
            out.update(rsid=eq["rsid"], genotype=gt, dose=dose, basis="expression", n_read=len(read))
            if dose == 0:
                out.update(function="normal", detail=f"The usual genotype ({gt}) at {gene}'s strongest expression variant "
                                                      f"{eq['rsid']} (GTEx, {len(eq['tissues'])} tissues)")
            elif len(signs) == 1:
                s = signs.pop()
                out.update(function="GoF" if s > 0 else "LoF",
                           detail=f"{other} {'raises' if s > 0 else 'lowers'} {gene} expression in {len(eq['tissues'])} tissues "
                                  f"(strongest: {tissues}); {dose} cop{'y' if dose == 1 else 'ies'}")
            else:
                out.update(function="altered", detail=f"{other} raises {gene} expression in some tissues and lowers it in "
                                                       f"others ({tissues}); {dose} cop{'y' if dose == 1 else 'ies'}")
            if measured_normal and out["function"] == "normal":
                out.update(basis="measured", detail=measured_normal[0]["detail"])
            out["detail"] += note
            return out
    if measured_normal:
        b = measured_normal[0]
        out.update(function="normal", basis="measured", detail=b["detail"] + note, rsid=b["rsid"], genotype=b["genotype"],
                   dose=b["copies"], n_read=len(read))
    elif read:
        out.update(function="normal", basis="none", n_read=len(read),
                   detail=f"No carried protein change with known effect among {len(read)} known variants read in {gene}" + note)
    return out


def run(dna, genes):
    genes = sorted(genes)
    print(f"{len(genes)} genes: UniProt variants and GTEx eQTLs (cached after the first run)...", flush=True)
    pv, eq = {}, {}

    def fetch(g):
        try:
            p = protein_variants(g)
        except Exception as e:  # one gene's API failure should not stop the run
            print(f"   [!] UniProt {g}: {type(e).__name__}", flush=True)
            p = []
        # MaveDB for every gene with protein variants, not only those a person carries a change in: the lookups are
        # then the same for everyone, and the analysis of a new person runs offline from the cache
        if p:
            try:
                for s in mavedb_sets(g):
                    mavedb_scores(s["urn"])
            except Exception as e:
                print(f"   [!] MaveDB {g}: {type(e).__name__}", flush=True)
        try:
            q = gtex_top_eqtl(g)
        except Exception as e:
            print(f"   [!] GTEx {g}: {type(e).__name__}", flush=True)
            q = None
        return g, p, q

    # The APIs answer slowly, one gene at a time: a few workers in parallel, each request cached
    with ThreadPoolExecutor(WORKERS) as pool:
        for i, (g, p, q) in enumerate(pool.map(fetch, genes), 1):
            pv[g], eq[g] = p, q
            if i % 100 == 0:
                print(f"   {i}/{len(genes)}", flush=True)
    want = {v["rsid"] for vs in pv.values() for v in vs} | {e["rsid"] for e in eq.values() if e}
    print(f"Reading {len(want):,} variants from {os.path.basename(dna)}...", flush=True)
    calls = {rs: (gt, tier) for rs, _, _, gt, tier in iter_calls(dna, rsids=want, confidence=CONFIDENT) if gt and "-" not in gt}
    # Every gene's eQTL variant, not only those this person has a call at: the lookups are then the same for everyone,
    # and a run for anyone fills the cache for all (no person's variant list goes to Ensembl)
    eq_rs = sorted({e["rsid"] for e in eq.values() if e})
    print(f"Ensembl VEP (European frequencies) for {len(eq_rs):,} eQTL variants...", flush=True)
    vep = sources.ensembl_vep(eq_rs) if eq_rs else {}
    return {g: call_gene(g, pv[g], eq[g], calls, vep) for g in genes}


def theme_people():
    """{dna path: genes}: each profile (profiles.json) with the genes of the themes for its sex."""
    from cluster_analysis import profiles
    out = defaultdict(set)
    graphs = profiles.theme_graphs()
    for p in profiles.load():
        for g in graphs:
            if profiles.applies(g.get("sex"), p["sex"]):
                out[p["dna"]] |= set(g["genes"])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dna")
    ap.add_argument("--genes", nargs="*")
    ap.add_argument("--person", help="only this theme person (XY, XX), with all of their theme genes")
    ap.add_argument("--measured-only", action="store_true", help="use the raw file even when an imputed one exists")
    args = ap.parse_args()
    jobs = {args.dna: set(args.genes or [])} if args.dna else theme_people()
    if args.person:
        jobs = {d: g for d, g in jobs.items() if person_label(d) == args.person}
        if not jobs:
            raise SystemExit(f"No theme names {args.person} as its person")
    for dna, genes in jobs.items():
        if not genes:
            genes = set().union(*theme_people().values())
        path = dna if args.measured_only else imputed_path(dna)
        res = run(path, genes)
        name = person_label(path)
        os.makedirs(OUT_DIR, exist_ok=True)
        out = os.path.join(OUT_DIR, f"gene_calls_{name}.json")
        if args.genes:
            print(json.dumps(res, indent=1, ensure_ascii=False)[:4000])
        else:
            json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            n = defaultdict(int)
            for c in res.values():
                n[c["function"]] += 1
            print(f"Done {name}: {dict(n)} -> {out}")
