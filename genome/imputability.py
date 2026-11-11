"""Imputability map: how reliably a MyHeritage chip customer's genotype can be known at every variant of the panel.

    python -m genome.imputability run 22             # one chromosome (test)
    python -m genome.imputability run                # chr1-22, then the summary
    python -m genome.imputability summary            # per-site files -> calibration and gene tables

Method. HOLDOUT European founders of the 1000 Genomes high-coverage panel are taken out of the panel; their genotypes
are cut down to the positions a MyHeritage chip reads (the measured positions in the profiles' imputed files, which
are the chip's, the same for everyone), imputed with Beagle against the panel without them, and compared with their
sequenced genotypes at every site:

  r2      squared correlation between the true allele count and Beagle's dosage, across the held-out people
  conc    share of held-out genotypes called right (the most likely genotype against the truth)
  carriers, found   held-out people who carry the alternative allele, and how many of them the imputation calls a carrier
  dr2     Beagle's own estimate of r2 at the site (it exists for rare sites too, where the held-out people rarely carry)

Per chromosome on D: (<panel folder>/imputability/): the reduced reference (bref3, deleted after use), the chip-only
target, the truth, and chr<N>.sites.tsv.gz with one row per site. Every step skips work already done, writes to a
.part file first, and stops when C: or D: runs low (genome/panel_sites.check_space).
"""
import argparse
import gzip
import json
import os
import random
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from genome import impute, panel_sites
from genome.pgs_reference import PANEL, eur_founders

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(PANEL, "imputability")
HOLDOUT = 100
CHROMS = [str(c) for c in range(1, 23)]
PROFILES = ("XY", "XX")
BREF3 = os.path.join(impute.REF, "bref3.jar")


def holdout():
    """The held-out people: HOLDOUT European founders, drawn with a fixed seed so every run uses the same ones."""
    return sorted(random.Random(20261111).sample(eur_founders(), HOLDOUT))


def chip_positions(chrom):
    """GRCh38 positions the MyHeritage chip reads on a chromosome: the measured rows of the profiles' imputed files.
    One pass over both files caches every chromosome (chip_chr<N>.txt)."""
    path = os.path.join(WORK, f"chip_chr{chrom}.txt")
    if not os.path.exists(path):
        by = {c: set() for c in CHROMS}
        for p in PROFILES:
            f = os.path.join(ROOT, "data", "output", "imputation", p, "1kgp_hc", f"MyHeritage_raw_dna_data_{p}.imputed.csv")
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "measured" not in line:
                        continue
                    x = line.rstrip("\n").replace('"', "").split(",")
                    if len(x) >= 8 and x[7] == "measured" and x[1] in by and x[2].isdigit():
                        by[x[1]].add(int(x[2]))
        for c, s in by.items():
            out = os.path.join(WORK, f"chip_chr{c}.txt")
            with open(out + ".part", "w") as fh:
                fh.write("\n".join(map(str, sorted(s))) + "\n")
            os.replace(out + ".part", out)
    return {int(x) for x in open(path) if x.strip()}


def split(chrom, held):
    """One pass over the raw chromosome: the panel without the held-out people (VCF, for bref3), their chip-only
    target (VCF, unphased like a chip), and their truth at every biallelic SNP or indel."""
    ref_vcf, target, truth = (os.path.join(WORK, f"chr{chrom}.{n}") for n in ("ref.vcf.gz", "target.vcf.gz", "truth.tsv.gz"))
    if all(os.path.exists(f) for f in (truth, target)) and (os.path.exists(ref_vcf) or os.path.exists(bref(chrom))):
        return ref_vcf, target, truth
    panel_sites.check_space(PANEL)
    chip = chip_positions(chrom)
    raw = os.path.join(PANEL, "raw", panel_sites.raw_file(PANEL, chrom))
    with gzip.open(raw, "rb") as f, gzip.open(ref_vcf + ".part", "wb", compresslevel=1) as r, \
            gzip.open(target + ".part", "wb", compresslevel=1) as t, gzip.open(truth + ".part", "wt", compresslevel=1) as u:
        keep = out = None
        for line in f:
            if line[:2] == b"##":
                r.write(line); t.write(line)
                continue
            if line[:1] == b"#":
                head = line.rstrip(b"\n").split(b"\t")
                names = [h.decode() for h in head]
                out = [names.index(s) for s in held]
                drop = set(out)
                keep = [i for i in range(len(head)) if i not in drop]
                r.write(b"\t".join(head[i] for i in keep) + b"\n")
                t.write(b"\t".join(head[:9] + [head[i] for i in out]) + b"\n")
                u.write("pos\tref\talt\t" + "\t".join(held) + "\n")
                continue
            p = line.rstrip(b"\n").split(b"\t")
            r.write(b"\t".join(p[i] for i in keep) + b"\n")
            gts = [p[i][:3] for i in out]
            if b"," not in p[4]:
                u.write(f"{int(p[1])}\t{p[3].decode()}\t{p[4].decode()}\t" + "\t".join(g.decode() for g in gts) + "\n")
                if int(p[1]) in chip and len(p[3]) == 1 and len(p[4]) == 1:
                    # A chip reads genotypes, not haplotypes: unphased
                    t.write(b"\t".join(p[:8] + [b"GT"] + [g.replace(b"|", b"/") for g in gts]) + b"\n")
    for f in (ref_vcf, target, truth):
        os.replace(f + ".part", f)
    return ref_vcf, target, truth


def bref(chrom):
    return os.path.join(WORK, f"chr{chrom}.ref.bref3")


def to_bref3(chrom, ref_vcf):
    out = bref(chrom)
    if not os.path.exists(out):
        panel_sites.check_space(PANEL)
        with open(out + ".part", "wb") as fh:
            r = subprocess.run(["java", "-Xmx10g", "-jar", BREF3, ref_vcf], stdout=fh, stderr=subprocess.PIPE, text=False)
        if r.returncode:
            raise SystemExit(f"bref3 failed on chr{chrom}: {r.stderr.decode()[-500:]}")
        os.replace(out + ".part", out)
    if os.path.exists(ref_vcf):
        os.remove(ref_vcf)  # 30-40 GB over all chromosomes: the bref3 file replaces it
    return out


def beagle(chrom, target, threads, memory):
    prefix = os.path.join(WORK, f"chr{chrom}.imputed")
    if not os.path.exists(prefix + ".vcf.gz"):
        panel_sites.check_space(PANEL)
        cmd = ["java", f"-Xmx{memory}", "-jar", os.path.join(impute.REF, "beagle.jar"), f"gt={target}", f"ref={bref(chrom)}",
               f"map={impute.genetic_map(chrom, impute.panel('1kgp_hc'))}", f"out={prefix}", f"nthreads={threads}", "gp=true"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"Beagle failed on chr{chrom}: {r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return prefix + ".vcf.gz"


def compare(chrom, truth, imputed):
    """One row per site: the held-out people's truth against Beagle's dosage and most likely genotype."""
    out = os.path.join(WORK, f"chr{chrom}.sites.tsv.gz")
    if os.path.exists(out):
        return out
    tf = gzip.open(truth, "rt")
    next(tf)
    t_iter = (l.rstrip("\n").split("\t") for l in tf)
    nxt = next(t_iter, None)
    here, here_pos = {}, -1  # truth rows at the current position, by (ref, alt): several records can share a position
    with gzip.open(imputed, "rt") as f, gzip.open(out + ".part", "wt", compresslevel=6) as w:
        w.write("pos\tref\talt\tchip\taf_holdout\tdr2\tr2\tconc\tcarriers\tfound\n")
        fmt = None
        for line in f:
            if line[0] == "#":
                continue
            p = line.rstrip("\n").split("\t")
            pos, ref, alt = int(p[1]), p[3], p[4]
            if pos != here_pos:
                while nxt is not None and int(nxt[0]) < pos:
                    nxt = next(t_iter, None)
                here, here_pos = {}, pos
                while nxt is not None and int(nxt[0]) == pos:
                    here[(nxt[1], nxt[2])] = nxt
                    nxt = next(t_iter, None)
            cur = here.get((ref, alt))
            if cur is None:
                continue
            info = dict(x.split("=", 1) for x in p[7].split(";") if "=" in x)
            if fmt is None:
                fmt = p[8].split(":")
            ids = fmt.index("DS")
            truth_d = [g.count("1") for g in cur[3:]]
            ds = [float(x.split(":")[ids]) for x in p[9:]]
            gt = [x.split(":")[0] for x in p[9:]]
            n = len(truth_d)
            mt, md = sum(truth_d) / n, sum(ds) / n
            vt = sum((a - mt) ** 2 for a in truth_d)
            vd = sum((b - md) ** 2 for b in ds)
            cov = sum((a - mt) * (b - md) for a, b in zip(truth_d, ds))
            r2 = (cov * cov / (vt * vd)) if vt > 0 and vd > 0 else ""
            called = [g.count("1") for g in gt]
            conc = sum(a == b for a, b in zip(truth_d, called)) / n
            carriers = sum(a > 0 for a in truth_d)
            found = sum(a > 0 and b > 0 for a, b in zip(truth_d, called))
            w.write(f"{pos}\t{ref}\t{alt}\t{0 if 'IMP' in p[7] else 1}\t{mt / 2:.4f}\t{info.get('DR2', '')}\t"
                    f"{'' if r2 == '' else f'{r2:.3f}'}\t{conc:.3f}\t{carriers}\t{found}\n")
    tf.close()
    os.replace(out + ".part", out)
    return out


def run_chrom(chrom, threads, memory):
    os.makedirs(WORK, exist_ok=True)
    held = holdout()
    ref_vcf, target, truth = split(chrom, held)
    print(f"chr{chrom}: split", flush=True)
    to_bref3(chrom, ref_vcf)
    print(f"chr{chrom}: bref3", flush=True)
    imputed = beagle(chrom, target, threads, memory)
    print(f"chr{chrom}: imputed", flush=True)
    sites = compare(chrom, truth, imputed)
    # Keep only the per-site results: the reduced reference, target, truth and Beagle's output are for this run only
    for f in (bref(chrom), target, truth, imputed, imputed[:-len(".vcf.gz")] + ".log"):
        if os.path.exists(f):
            os.remove(f)
    print(f"chr{chrom}: compared -> {sites}", flush=True)
    return chrom


def below_normal():
    """Windows: run this process (and the Java it starts) at below-normal priority, so a long run leaves the PC usable."""
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)


# --- Summary ---------------------------------------------------------------------------------------------------------

MAF_BINS = [0, 0.001, 0.005, 0.01, 0.05, 0.2, 0.51]
DR2_BINS = [0, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 1.01]
MIN_CARRIERS = 3      # a site's own r2 counts only when at least this many held-out people carry the allele
RELIABLE, UNCERTAIN = 0.8, 0.5
SUMMARY = os.path.join(ROOT, "data", "reference", "imputability")


def _bin(x, edges):
    for i in range(len(edges) - 1):
        if edges[i] <= x < edges[i + 1]:
            return i
    return len(edges) - 2


def sites(chroms=CHROMS):
    """(chrom, pos, ref, alt, chip, maf, dr2, r2 or None, carriers, found) for every compared site."""
    for c in chroms:
        f = os.path.join(WORK, f"chr{c}.sites.tsv.gz")
        if not os.path.exists(f):
            continue
        with gzip.open(f, "rt") as fh:
            next(fh)
            for line in fh:
                p = line.rstrip("\n").split("\t")
                af = float(p[4])
                yield (c, int(p[0]), p[1], p[2], p[3] == "1", min(af, 1 - af), float(p[5]) if p[5] else 0.0,
                       float(p[6]) if p[6] else None, int(p[8]), int(p[9]))


def calibrate(chroms=CHROMS):
    """Per (frequency bin, Beagle DR2 bin): mean measured r2 and carrier sensitivity over the sites where enough
    held-out people carry the allele. This is what a site with too few carriers is judged by."""
    acc = {}
    for c, pos, ref, alt, chip, maf, dr2, r2, carriers, found in sites(chroms):
        if chip or r2 is None or carriers < MIN_CARRIERS:
            continue
        k = (_bin(maf, MAF_BINS), _bin(dr2, DR2_BINS))
        a = acc.setdefault(k, [0, 0.0, 0, 0])
        a[0] += 1; a[1] += r2; a[2] += carriers; a[3] += found
    return {k: {"sites": a[0], "r2": round(a[1] / a[0], 3), "sensitivity": round(a[3] / a[2], 3)} for k, a in acc.items()}


def reliability(chip, maf, dr2, r2, carriers, cal):
    """chip, reliable, uncertain or not_knowable, and the r2 it rests on (measured, else calibrated)."""
    if chip:
        return "chip", 1.0
    if r2 is not None and carriers >= MIN_CARRIERS:
        est = r2
    else:
        # The calibration of the nearest bin that has data: same DR2 bin, the closest frequency bin above
        mb, db = _bin(maf, MAF_BINS), _bin(dr2, DR2_BINS)
        est = next((cal[(m, db)]["r2"] for m in range(mb, len(MAF_BINS) - 1) if (m, db) in cal), dr2)
        est = min(est, dr2) if dr2 < 0.3 else est  # Beagle's own doubt is never overruled upward
    return ("reliable" if est >= RELIABLE else "uncertain" if est >= UNCERTAIN else "not_knowable"), round(est, 3)


def clinvar_pathogenic():
    """{(chrom, pos, ref, alt): (gene, significance, stars, condition)} for ClinVar pathogenic and likely pathogenic."""
    from genome import build as gbuild
    stars = {"practice_guideline": 4, "reviewed_by_expert_panel": 3, "criteria_provided,_multiple_submitters,_no_conflicts": 2,
             "criteria_provided,_single_submitter": 1}
    out = {}
    with gzip.open(gbuild.path("clinvar"), "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.rstrip("\n").split("\t", 8)
            if p[0] not in CHROMS:
                continue
            info = dict(x.split("=", 1) for x in p[7].split(";") if "=" in x)
            sig = info.get("CLNSIG", "")
            if not sig.startswith(("Pathogenic", "Likely_pathogenic")) or "onflicting" in sig:
                continue
            gene = info.get("GENEINFO", "").split(":")[0]
            out[(p[0], int(p[1]), p[3], p[4])] = (gene, sig, stars.get(info.get("CLNREVSTAT", ""), 0), info.get("CLNDN", "").split("|")[0])
    return out


def summary(chroms=CHROMS):
    os.makedirs(SUMMARY, exist_ok=True)
    done = [c for c in chroms if os.path.exists(os.path.join(WORK, f"chr{c}.sites.tsv.gz"))]
    print(f"Calibrating on {len(done)} chromosomes ...", flush=True)
    cal = calibrate(done)
    print("ClinVar pathogenic variants ...", flush=True)
    cv = clinvar_pathogenic()
    classes = {}
    genes = {}
    per_variant = []
    for c, pos, ref, alt, chip, maf, dr2, r2, carriers, found in sites(done):
        cls, est = reliability(chip, maf, dr2, r2, carriers, cal)
        classes[cls] = classes.get(cls, 0) + 1
        hit = cv.get((c, pos, ref, alt))
        if hit:
            gene, sig, st, cond = hit
            g = genes.setdefault(gene, {"gene": gene, "pathogenic": 0, "chip": 0, "reliable": 0, "uncertain": 0, "not_knowable": 0})
            g["pathogenic"] += 1; g[cls] += 1
            per_variant.append({"chrom": c, "pos": pos, "ref": ref, "alt": alt, "gene": gene, "significance": sig, "stars": st,
                                "condition": cond, "class": cls, "r2": est, "maf": round(maf, 5)})
    # ClinVar pathogenic variants the panel doesn't hold at all: too rare to be in 1000 Genomes, so never imputed
    in_panel = {(v["chrom"], v["pos"], v["ref"], v["alt"]) for v in per_variant}
    for (c, pos, ref, alt), (gene, sig, st, cond) in cv.items():
        if c in done and (c, pos, ref, alt) not in in_panel:
            g = genes.setdefault(gene, {"gene": gene, "pathogenic": 0, "chip": 0, "reliable": 0, "uncertain": 0, "not_knowable": 0})
            g["pathogenic"] += 1; g["not_in_panel"] = g.get("not_in_panel", 0) + 1
    meta = {"holdout": HOLDOUT, "chromosomes": done, "sites": classes, "reliable_r2": RELIABLE, "uncertain_r2": UNCERTAIN,
            "calibration": [{"maf_bin": [MAF_BINS[m], MAF_BINS[m + 1]], "dr2_bin": [DR2_BINS[d], DR2_BINS[d + 1]], **v}
                            for (m, d), v in sorted(cal.items())]}
    json.dump(meta, open(os.path.join(SUMMARY, "summary.json"), "w", encoding="utf-8"), indent=1)
    json.dump(sorted(genes.values(), key=lambda g: g["gene"]), open(os.path.join(SUMMARY, "genes.json"), "w", encoding="utf-8"))
    json.dump(per_variant, open(os.path.join(SUMMARY, "clinvar_variants.json"), "w", encoding="utf-8"))
    print(f"sites by class: {classes}")
    tot = {k: sum(g.get(k, 0) for g in genes.values()) for k in ("pathogenic", "chip", "reliable", "uncertain", "not_knowable", "not_in_panel")}
    print(f"ClinVar pathogenic/likely pathogenic on chr{','.join(done)}: {tot}")
    return meta


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("run", "summary"))
    ap.add_argument("chroms", nargs="*")
    ap.add_argument("--threads", type=int, default=3, help="Beagle threads per chromosome")
    ap.add_argument("--parallel", type=int, default=3, help="chromosomes at a time")
    ap.add_argument("--memory", default="8g", help="Java heap per Beagle run")
    a = ap.parse_args()
    if a.command == "run":
        below_normal()
        todo = [c for c in (a.chroms or CHROMS) if not os.path.exists(os.path.join(WORK, f"chr{c}.sites.tsv.gz"))]
        chip_positions(todo[0]) if todo else None  # the one pass over the profiles' files, before the workers start
        # Largest chromosomes first, PARALLEL at a time: the split is one CPU each, Beagle uses --threads each
        with ProcessPoolExecutor(a.parallel, initializer=below_normal) as ex:
            for c in as_completed([ex.submit(run_chrom, c, a.threads, a.memory) for c in todo]):
                print(f"done chr{c.result()}", flush=True)
        summary()
    else:
        summary(a.chroms or CHROMS)


if __name__ == "__main__":
    main()
