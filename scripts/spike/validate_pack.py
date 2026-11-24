"""The imputation pack against the full panel, genome-wide: HG00096 (a 1000 Genomes sample, public) left out of the
reference, imputed from its chip positions with Beagle on the full panel and on the pack (build_pack.py), both
scored against its own panel genotypes at the pack's positions (which hold every position the analysis reads).
    python scripts/spike/validate_pack.py [CHROM ...]       # default: every chromosome the pack has, 1-22
Writes D:/DNA-Analyzer-build/pack/validate/. Public data only."""
import gzip, json, os, subprocess, sys, time
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACK = os.environ.get("DNA_PACK_DIR", r"D:\DNA-Analyzer-build\pack")
OUT = os.path.join(PACK, "validate")
FULL = r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38\bref3\chr{c}.bref3"
MAP = os.path.join(ROOT, "data", "reference", "imputation", "plink.chrchr{c}.GRCh38.map")
JAR = os.path.join(ROOT, "data", "reference", "imputation", "beagle.jar")
CSV = os.path.join(ROOT, "data", "output", "imputation", "HG00096", "1kgp_hc", "MyHeritage_raw_dna_data_HG00096.imputed.csv")
SAMPLE = "HG00096"
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "exclude.txt"), "w").write(SAMPLE + "\n")

chip = {}
for line in open(CSV, encoding="utf-8"):
    if line[0] == "#" or line.startswith("RSID"):
        continue
    p = line.rstrip("\n").replace('"', "").split(",")
    if p[4] == "measured" and len(p[3]) == 2:
        chip[(p[1], int(p[2]))] = p[3]


def truth_and_target(c):
    """HG00096's panel genotypes at the pack's positions (the truth), and its chip calls as an unphased VCF."""
    truth, alleles, sites_af = {}, {}, {}
    tgt = os.path.join(OUT, f"target.chr{c}.vcf")
    with gzip.open(os.path.join(PACK, f"chr{c}.vcf.gz"), "rt") as f, open(tgt, "w") as tv:
        tv.write("##fileformat=VCFv4.2\n##FORMAT=<ID=GT,Number=1,Type=String,Description=\"Genotype\">\n"
                 "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tTARGET\n")
        si = None
        for line in f:
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                si = line.rstrip("\n").split("\t").index(SAMPLE)
                continue
            p = line.rstrip("\n").split("\t")
            pos, ref, alt = int(p[1]), p[3], p[4]
            gt = p[si].split(":")[0]
            truth[pos] = int(gt[0]) + int(gt[2])
            alleles[pos] = (ref, alt)
            g = chip.get((c, pos))
            if g and set(g) <= {ref, alt}:
                n = g.count(alt)
                tv.write(f"{p[0]}\t{pos}\t.\t{ref}\t{alt}\t.\tPASS\t.\tGT\t{('0/0', '0/1', '1/1')[n]}\n")
    return truth, alleles, tgt


def beagle(c, ref, tgt, tag):
    out = os.path.join(OUT, f"{tag}.chr{c}")
    if not os.path.exists(out + ".vcf.gz"):
        subprocess.run(["java", "-Xmx12g", "-jar", JAR, f"gt={tgt}", f"ref={ref}", f"map={MAP.format(c=c)}", f"out={out}",
                        f"excludesamples={os.path.join(OUT, 'exclude.txt')}", "nthreads=6", "gp=true"],
                       check=True, capture_output=True)
    ds = {}
    with gzip.open(out + ".vcf.gz", "rt") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.rstrip("\n").split("\t")
            fmt, v = p[8].split(":"), p[9].split(":")
            ds[(int(p[1]), p[3], p[4])] = float(v[fmt.index("DS")]) if "DS" in fmt else sum(int(x) for x in v[0].replace("|", "/").split("/"))
    return ds


chroms = sys.argv[1:] or [str(i) for i in range(1, 23) if os.path.exists(os.path.join(PACK, f"chr{i}.vcf.gz"))]
rows = {"full": [], "pack": []}
for c in chroms:
    t0 = time.time()
    truth, alleles, tgt = truth_and_target(c)
    pack_ref = os.path.join(PACK, f"chr{c}.bref3")
    pack_ref = pack_ref if os.path.exists(pack_ref) else os.path.join(PACK, f"chr{c}.vcf.gz")
    for tag, ref in (("full", FULL.format(c=c)), ("pack", pack_ref)):
        ds = beagle(c, ref, tgt, tag)
        for pos, t in truth.items():
            d = ds.get((pos, *alleles[pos]))
            if d is not None:
                rows[tag].append((t, d))
    print(f"chr{c}: {len(truth):,} pack positions, {round(time.time() - t0)} s", flush=True)

summary = {}
for tag, r in rows.items():
    a = np.array(r)
    t, d = a[:, 0], a[:, 1]
    summary[tag] = {"positions": len(a), "exact": round(float((np.rint(d) == t).mean()), 4),
                    "r2": round(float(np.corrcoef(d, t)[0, 1] ** 2), 4),
                    "non-ref found": round(float(((np.rint(d) > 0) & (t > 0)).sum() / max(1, (t > 0).sum())), 4)}
print(json.dumps(summary, indent=1))
json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
