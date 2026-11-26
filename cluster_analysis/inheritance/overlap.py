"""Which trait scales measure much the same thing: the correlation of every two trait models' scores across real
people, the 525 European founders of the 1000 Genomes high-coverage panel.

    python -m cluster_analysis.inheritance.overlap build    # extract (D:), score, correlate -> trait_overlap.json
    python -m cluster_analysis.inheritance.overlap show EFO_0004340   # the traits whose scales move with BMI's

Two GWAS of related traits (BMI, body weight, obesity, waist) find many of the same genes, so their scales rank people
much alike. Counting shared regions doesn't show it (BMI's 1,048 regions with their neighbours cover half the genome).
Scoring the same real people on both scales does, linkage between nearby variants included: r near 1 means the two
scales say the same thing about a person; near 0, unrelated; negative, opposite (a higher one, a lower other).

The panel's genotypes are read straight from its raw VCFs (genome/pgs_reference.extract), only at the models' variant
positions, into <panel>/pgs_ref/trait_models/ on D: (its own folder: the per-chromosome extracts are cached).
525 people give each r a sampling error of about 0.04, enough for r of 0.3 and up.

Output: data/reference/inheritance/trait_overlap.json, {trait id: [[other id, r], ...]} for |r| >= 0.3, strongest first,
and "families": traits joined where |r| >= FAMILY_R, each family named by its member with the largest study.
"""
import gzip
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from cluster_analysis.inheritance import predict
from genome import pgs_reference as pr

WORK = os.path.join(pr.WORK, "trait_models")
OUT = os.path.join(predict.REF, "inheritance", "trait_overlap.json")
KEEP_R = 0.3      # related scales listed per trait
FAMILY_R = 0.6    # scales joined into one family


def extract_all(models):
    os.makedirs(WORK, exist_ok=True)
    samples = pr.eur_founders()
    want = {c: set() for c in pr.CHROMS}
    for m in models:
        for v in m["variants"]:
            if str(v["chrom"]) in want:
                want[str(v["chrom"])].add(int(v["pos"]))
    print(f"{len(samples)} European founders; {sum(len(v) for v in want.values()):,} positions for {len(models):,} trait models", flush=True)
    with ProcessPoolExecutor(pr.THREADS) as ex:
        futs = {c: ex.submit(pr.extract, c, want[c], samples, WORK) for c in pr.CHROMS}
        for c in pr.CHROMS:
            out = futs[c].result()
            print(f"  chr{c}: {os.path.getsize(out) / 1e6:.1f} MB", flush=True)
    return samples


def dosages(samples):
    """{(chrom, pos): [(ref, alt, alt-allele copies per person)]}."""
    out = {}
    for c in pr.CHROMS:
        with gzip.open(os.path.join(WORK, f"chr{c}.tsv.gz"), "rt") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                gts = p[3:]
                if len(gts) != len(samples):
                    raise SystemExit(f"chr{c}:{p[0]} has {len(gts)} genotypes, expected {len(samples)}")
                out.setdefault((c, int(p[0])), []).append((p[1], p[2], np.fromiter((g.count("1") for g in gts), dtype=np.int8, count=len(gts))))
    return out


def scores(models, dos, n):
    """Each model's score for every person (rows: models with at least half their variants found)."""
    ids, mat = [], []
    for m in models:
        s, found = np.zeros(n), 0
        for v in m["variants"]:
            for ref, alt, d in dos.get((str(v["chrom"]), int(v["pos"])), []):
                if v["allele"] == alt:
                    s += v["w"] * d
                elif v["allele"] == ref:
                    s += v["w"] * (2 - d)
                else:
                    continue
                found += 1
                break
        if found >= max(5, 0.5 * len(m["variants"])) and s.std() > 0:
            ids.append(m["id"])
            mat.append((s - s.mean()) / s.std())
    return ids, np.asarray(mat)


def families(ids, r, size):
    """Traits joined where |r| >= FAMILY_R (single linkage), each family led by its largest study."""
    parent = list(range(len(ids)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    a, b = np.where(np.triu(np.abs(r) >= FAMILY_R, 1))
    for i, j in zip(a, b):
        parent[find(i)] = find(j)
    groups = {}
    for i in range(len(ids)):
        groups.setdefault(find(i), []).append(ids[i])
    out = []
    for members in groups.values():
        if len(members) > 1:
            members.sort(key=lambda t: -size.get(t, 0))
            out.append({"lead": members[0], "members": members})
    return sorted(out, key=lambda f: -len(f["members"]))


def build():
    models = predict.load_models()
    samples = extract_all(models)
    dos = dosages(samples)
    ids, z = scores(models, dos, len(samples))
    r = (z @ z.T) / z.shape[1]
    np.fill_diagonal(r, 0)
    size = {m["id"]: int(float(m.get("n") or 0)) for m in models}
    related = {}
    for i, t in enumerate(ids):
        js = np.where(np.abs(r[i]) >= KEEP_R)[0]
        related[t] = [[ids[j], round(float(r[i, j]), 2)] for j in sorted(js, key=lambda j: -abs(r[i, j]))[:25]]
    fam = families(ids, r, size)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"method": f"Pearson r of the trait models' scores across {len(samples)} 1000 Genomes European founders",
                   "people": len(samples), "scored": len(ids), "keep_r": KEEP_R, "family_r": FAMILY_R,
                   "related": related, "families": fam}, f, separators=(",", ":"))
    print(f"✅ {len(ids):,} of {len(models):,} models scored; {sum(1 for v in related.values() if v):,} with a related scale; "
          f"{len(fam):,} families of 2+ (|r| >= {FAMILY_R}) → {OUT}")


def load():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build()
    elif sys.argv[1:2] == ["show"]:
        d, names = load(), {m["id"]: m.get("reported") or m["trait"] for m in predict.load_models()}
        for tid in sys.argv[2:]:
            print(f"{names.get(tid, tid)}:")
            for other, rv in d.get("related", {}).get(tid, []):
                print(f"  r={rv:+.2f}  {names.get(other, other)}")
    else:
        print(__doc__)
