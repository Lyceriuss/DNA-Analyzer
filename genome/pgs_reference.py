"""Genome-wide polygenic scores placed against 1000 Genomes Europeans.

    python -m genome.pgs_reference fetch PGS002143 PGS002168     # the PGS Catalog scoring files (GRCh38 harmonised)
    python -m genome.pgs_reference build PGS002143 PGS002168     # once: European dosages at their variants (D:)
    python -m genome.pgs_reference score PGS002143 --dna data/input/MyHeritage_raw_dna_data_XY.csv

Genome-wide scores (LDpred2, snpnet, lasso) weight up to a million correlated variants, so the closed-form mean and
variance used for pruned scores (nutrition.score: sum 2pw, sum 2p(1-p)w^2, no LD) does not hold. Instead the score is
computed for every European founder in the 1000 Genomes high-coverage panel (525 people: EUR, no parents in the panel),
and the person is placed by rank among them.

A person's imputed file can call most but not all variants with confidence (measured, high, medium). Both the person
and the 525 reference people are scored on exactly that subset, so a missing variant moves no one.

build reads the raw panel VCFs (raw/ in the panel folder) straight from Python, one pass per chromosome, four at a
time, writing every result to files under the panel folder on D:, and stops when C: or D: runs low.
Output: <panel folder>/pgs_ref/eur_dosage.npz (positions, alleles, and an int8 dosage matrix of the alternative allele)
and one <id>.npz of weights per score.
"""
import argparse
import csv
import gzip
import json
import os
import sys
import urllib.request
from concurrent.futures import ProcessPoolExecutor

import numpy as np

if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from genome import panel_sites
from genome.loader import imputed_path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "data", "reference", "pgs_ref")
PANEL = os.environ.get("DNA_PANEL_ROOT", r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38")
WORK = os.path.join(PANEL, "pgs_ref")
POPULATION = os.path.join(REF, "1kgp_3202_samples_ped_population.txt")
POPULATION_URL = ("http://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage/"
                  "20130606_g1k_3202_samples_ped_population.txt")
PGS_FTP = "https://ftp.ebi.ac.uk/pub/databases/spot/pgs/scores/{id}/ScoringFiles/Harmonized/{id}_hmPOS_GRCh38.txt.gz"
PGS_API = "https://www.pgscatalog.org/rest/score/{id}"
CHROMS = [str(c) for c in range(1, 23)]
CONFIDENT = ("measured", "high", "medium")
FLIP = str.maketrans("ACGT", "TGCA")
THREADS = 4


# --- Reference files ------------------------------------------------------------------------------------------------

def fetch(ids):
    os.makedirs(REF, exist_ok=True)
    if not os.path.exists(POPULATION):
        urllib.request.urlretrieve(POPULATION_URL, POPULATION)
    for pid in ids:
        path = os.path.join(REF, f"{pid}_hmPOS_GRCh38.txt.gz")
        if not os.path.exists(path):
            urllib.request.urlretrieve(PGS_FTP.format(id=pid), path)
        meta = os.path.join(REF, f"{pid}.json")
        if not os.path.exists(meta):
            with urllib.request.urlopen(PGS_API.format(id=pid), timeout=60) as r:
                open(meta, "wb").write(r.read())
        print(pid, "ok")


def eur_founders():
    """European samples with no parent in the panel."""
    out = []
    with open(POPULATION, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=" "):
            if r["Superpopulation"] == "EUR" and r["FatherID"] == "0" and r["MotherID"] == "0":
                out.append(r["SampleID"])
    return out


def scoring_rows(pid):
    """[(chrom, pos, effect allele, other allele or '', weight, rsid)] on GRCh38, autosomes, single-base alleles."""
    rows = []
    with gzip.open(os.path.join(REF, f"{pid}_hmPOS_GRCh38.txt.gz"), "rt", encoding="utf-8") as f:
        for r in csv.DictReader((l for l in f if not l.startswith("#")), delimiter="\t"):
            if r.get("hm_chr") not in CHROMS or not (r.get("hm_pos") or "").isdigit():
                continue
            ea, oa = r["effect_allele"], r.get("other_allele") or r.get("hm_inferOtherAllele") or ""
            if len(ea) != 1:
                continue
            rows.append((r["hm_chr"], int(r["hm_pos"]), ea, oa if len(oa) == 1 else "", float(r["effect_weight"]),
                         r.get("hm_rsID") or r.get("rsID") or ""))
    return rows


def meta(pid):
    m = json.load(open(os.path.join(REF, f"{pid}.json"), encoding="utf-8"))
    pub = m.get("publication") or {}
    return {"id": pid, "name": m.get("name"), "trait": m.get("trait_reported"), "method": m.get("method_name"),
            "variants": m.get("variants_number"), "author": pub.get("firstauthor"),
            "year": (pub.get("date_publication") or "")[:4], "pmid": pub.get("PMID"),
            "n": sum(x.get("sample_number") or 0 for x in m.get("samples_variants") or [])}


# --- Build: European dosages from the raw panel ---------------------------------------------------------------------

def extract(chrom, positions, samples):
    """Biallelic SNPs at the positions with the given samples' genotypes, read straight from the raw panel VCF (no
    Docker): one pass over the chromosome, keeping only the wanted lines. Written to a gzipped file on D:, then renamed,
    so an interrupted run leaves no half file that looks finished."""
    out = os.path.join(WORK, f"chr{chrom}.tsv.gz")
    if os.path.exists(out):
        return out
    panel_sites.check_space(PANEL)
    want = set(positions)
    raw = os.path.join(PANEL, "raw", panel_sites.raw_file(PANEL, chrom))
    tmp = out + ".part"
    with gzip.open(raw, "rb") as f, gzip.open(tmp, "wt", compresslevel=1, newline="\n") as w:
        cols = None
        for line in f:
            if line[:2] == b"##":
                continue
            if line[:1] == b"#":
                head = line.rstrip(b"\n").decode().split("\t")
                at = {s: i for i, s in enumerate(head)}
                cols = [at[s] for s in samples]
                continue
            # Position first, cheaply: the second field
            t1 = line.index(b"\t")
            t2 = line.index(b"\t", t1 + 1)
            if int(line[t1 + 1:t2]) not in want:
                continue
            p = line.rstrip(b"\n").split(b"\t")
            ref, alt = p[3], p[4]
            if len(ref) != 1 or len(alt) != 1:
                continue  # SNPs only, biallelic
            gts = [p[c][:3].decode() for c in cols]
            w.write(f"{int(p[1])}\t{ref.decode()}\t{alt.decode()}\t" + "\t".join(gts) + "\n")
    os.replace(tmp, out)
    return out


def build(ids):
    os.makedirs(WORK, exist_ok=True)
    samples = eur_founders()
    with open(os.path.join(WORK, "samples_eur.txt"), "w", newline="\n") as f:
        f.write("\n".join(samples) + "\n")
    scores = {pid: scoring_rows(pid) for pid in ids}
    want = {c: set() for c in CHROMS}
    for rows in scores.values():
        for c, p, *_ in rows:
            want[c].add(p)
    print(f"{len(samples)} European founders; {sum(len(v) for v in want.values()):,} positions for {', '.join(ids)}")
    # One process per chromosome, THREADS at a time (decompression is CPU-bound; more would starve the machine)
    with ProcessPoolExecutor(THREADS) as ex:
        futs = {c: ex.submit(extract, c, want[c], samples) for c in CHROMS}
        for c in CHROMS:
            out = futs[c].result()
            print(f"  chr{c}: {os.path.getsize(out) / 1e6:.0f} MB", flush=True)
    # One dosage matrix for the union of positions: alternative-allele copies per sample
    chrom, pos, ref, alt, dos = [], [], [], [], []
    for c in CHROMS:
        with gzip.open(os.path.join(WORK, f"chr{c}.tsv.gz"), "rt") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                gts = p[3:]
                if len(gts) != len(samples):
                    raise SystemExit(f"chr{c}:{p[0]} has {len(gts)} genotypes, expected {len(samples)}")
                chrom.append(int(c)); pos.append(int(p[0])); ref.append(p[1]); alt.append(p[2])
                dos.append([g.count("1") for g in gts])
        print(f"  read chr{c}: {len(pos):,} variants so far", flush=True)
    dos = np.asarray(dos, dtype=np.int8)
    np.savez_compressed(os.path.join(WORK, "eur_dosage.npz"), chrom=np.asarray(chrom, dtype=np.int8),
                        pos=np.asarray(pos, dtype=np.int64), ref=np.asarray(ref), alt=np.asarray(alt),
                        dosage=dos, samples=np.asarray(samples))
    # A position can hold several biallelic records (a split multi-allelic site): match on the alleles too
    key = {}
    for i, (c, p) in enumerate(zip(chrom, pos)):
        key.setdefault((c, p), []).append(i)
    for pid, rows in scores.items():
        idx, w, rs = [], [], []
        for c, p, ea, oa, wt, rsid in rows:
            hit = None
            for i in key.get((int(c), p), []):
                r, a = ref[i], alt[i]
                if oa and {ea, oa} != {r, a} and {ea.translate(FLIP), oa.translate(FLIP)} != {r, a}:
                    continue  # a different variant at the same position
                if not oa and len(key[(int(c), p)]) > 1:
                    continue  # no other allele to tell the records apart
                e = ea if ea in (r, a) else ea.translate(FLIP) if ea.translate(FLIP) in (r, a) else None
                if e is not None:
                    hit = (i, e)
                    break
            if hit is None:
                continue
            i, e = hit
            a = alt[i]
            # The weight per alternative-allele copy: the effect allele is alt, or ref (one alt copy fewer)
            idx.append(i); w.append(wt if e == a else -wt); rs.append(rsid)
        np.savez_compressed(os.path.join(WORK, f"{pid}.npz"), idx=np.asarray(idx, dtype=np.int64),
                            weight=np.asarray(w, dtype=np.float64), rsid=np.asarray(rs))
        print(f"{pid}: {len(idx):,} of {len(rows):,} variants found in the panel")


# --- Score a person -------------------------------------------------------------------------------------------------

_cache = {}


def _load(pid):
    if "panel" not in _cache:
        _cache["panel"] = dict(np.load(os.path.join(WORK, "eur_dosage.npz")))
    if pid not in _cache:
        _cache[pid] = dict(np.load(os.path.join(WORK, f"{pid}.npz")))
    return _cache["panel"], _cache[pid]


def person_dosage(dna, panel):
    """Alternative-allele copies for every panel position the person's imputed file calls with confidence; -1 elsewhere."""
    key = {}
    for i, (c, p) in enumerate(zip(panel["chrom"], panel["pos"])):
        key.setdefault((int(c), int(p)), []).append(i)
    d = np.full(len(panel["pos"]), -1, dtype=np.int8)
    path = imputed_path(dna)
    with open(path, encoding="utf-8", errors="replace") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").replace('"', "").split(",")
            if len(p) < 8 or p[7] not in CONFIDENT or not p[2].isdigit() or p[1] not in CHROMS:
                continue
            gt = p[3]
            for i in key.get((int(p[1]), int(p[2])), []):
                r, a = panel["ref"][i], panel["alt"][i]
                if len(gt) == 2 and set(gt) <= {r, a}:
                    d[i] = gt.count(a)
    return d


def score(pid, dna, dosage=None):
    """{percentile, z, used, variants, reference, top} for the person, against the 525 European founders."""
    panel, s = _load(pid)
    if dosage is None:  # one pass over the person's file serves every score
        dosage = _cache.get(("dosage", dna))
        if dosage is None:
            dosage = _cache[("dosage", dna)] = person_dosage(dna, panel)
    d = dosage
    idx, w = s["idx"], s["weight"]
    have = d[idx] >= 0
    i, wi = idx[have], w[have]
    ref_scores = panel["dosage"][i].astype(np.float32).T @ wi.astype(np.float32)
    mine = float(d[i].astype(np.float64) @ wi)
    below = float((ref_scores < mine).sum() + 0.5 * (ref_scores == mine).sum())
    pct = 100 * below / len(ref_scores)
    z = (mine - float(ref_scores.mean())) / float(ref_scores.std())
    # The variants that move the person furthest from the reference average, in the reference's standard deviations
    mean_d = panel["dosage"][i].mean(axis=1)
    contrib = (d[i] - mean_d) * wi
    order = np.argsort(-np.abs(contrib))[:8]
    sd = float(ref_scores.std())
    top = [{"rsid": str(s["rsid"][have][k]), "chrom": str(int(panel["chrom"][i[k]])), "pos": int(panel["pos"][i[k]]),
            "allele": str(panel["alt"][i[k]] if wi[k] > 0 else panel["ref"][i[k]]), "copies": int(d[i[k]] if wi[k] > 0 else 2 - d[i[k]]),
            "freq": round(float(mean_d[k] / 2 if wi[k] > 0 else 1 - mean_d[k] / 2), 3), "raises": True,
            "shift": round(float(contrib[k]) / sd, 2)} for k in order]
    return {"percentile": int(round(min(99, max(1, pct)))), "z": round(z, 2), "used": int(have.sum()), "variants": int(len(idx)),
            "placed": int(len(idx)), "reference": int(len(ref_scores)), "top": top}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("fetch", "build", "score"))
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--dna", default="data/input/MyHeritage_raw_dna_data_XY.csv")
    a = ap.parse_args()
    if a.command == "fetch":
        fetch(a.ids)
    elif a.command == "build":
        fetch(a.ids)
        build(a.ids)
    else:
        panel, _ = _load(a.ids[0])
        d = person_dosage(a.dna, panel)
        for pid in a.ids:
            r = score(pid, a.dna, d)
            print(pid, {k: v for k, v in r.items() if k != "top"})


if __name__ == "__main__":
    main()
