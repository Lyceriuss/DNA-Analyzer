"""The imputation pack: the 1000 Genomes high-coverage panel cut to the positions this app needs, so an installed app
can impute with Beagle without the 12 GB panel (docs/architecture/production.md, "Imputation without the 12 GB
panel"). Positions kept:
  chip      the positions a chip layout measures (the measured rows of a public sample's imputed CSV, e.g. HG00096,
            for MyHeritage) and the Illumina manifests in data/reference/chips/download (GSA: 23andMe v5;
            OmniExpress: AncestryDNA v2), lifted from GRCh37
  analysis  the rsIDs the analysis reads (a JSON list: a trace of every step, scratchpad trace_reads.py)
  themes    ClinVar and GWAS Catalog variants inside the theme genes (with the flank theme_graph uses)
  scores    every variant of the genome-wide scores in the fitness and cancer configs (pgs_ref)
Only biallelic SNVs, all 3,202 samples, phased as in the panel.

    python scripts/spike/build_pack.py targets ANALYSIS_RSIDS.json CHIP_IMPUTED_CSV   # -> OUT/targets.json
    python scripts/spike/build_pack.py extract [--jobs 6]                             # -> OUT/chrN.vcf.gz
    python scripts/spike/build_pack.py xsplit                                         # -> OUT/chrX_par1|chrX|chrX_par2.vcf.gz
    python scripts/spike/build_pack.py sites                                          # -> OUT/sites.vcf.gz
    python scripts/spike/build_pack.py bref3                                          # -> OUT/<part>.bref3
    python scripts/spike/build_pack.py install                                        # -> data/reference/imputation/pack
OUT is D:/DNA-Analyzer-build/pack (DNA_PACK_DIR). Reads public reference files only."""
import argparse, glob, gzip, json, os, re, subprocess, sys, time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.environ.get("DNA_PACK_DIR", r"D:\DNA-Analyzer-build\pack")
PANEL = r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38"
RAW = os.path.join(PANEL, "raw", "1kGP_high_coverage_Illumina.chr{c}.filtered.SNV_INDEL_SV_phased_panel.vcf.gz")
CHROMS = [str(i) for i in range(1, 23)] + ["X"]


def targets(analysis_json, chip_csv):
    os.chdir(ROOT)
    from cluster_analysis import profiles
    from cluster_analysis.themes import theme_graph as tg
    from genome import build as gbuild
    import numpy as np
    pos = defaultdict(set)      # chrom -> positions
    why = defaultdict(int)
    rsids = set(json.load(open(analysis_json)))
    why["analysis rsIDs asked"] = len(rsids)
    for line in open(chip_csv, encoding="utf-8"):
        if line[0] == "#" or line.startswith("RSID"):
            continue
        p = line.split(",", 5)
        if p[4] == "measured":
            pos[p[1].strip('"')].add(int(p[2].strip('"')))
            why["chip positions"] += 1
    # The other chips: Illumina's public manifests, lifted to GRCh38 (genome/sample_person.layout)
    from genome import sample_person
    for man in sorted(glob.glob(os.path.join(ROOT, "data", "reference", "chips", "download", "*manifest*csv*"))):
        n = 0
        for c, rows in sample_person.layout(man).items():
            for _, _, p38, _ in rows:
                if p38:
                    pos[c].add(p38); n += 1
        why[f"chip {os.path.basename(man)}"] = n
    # The genome-wide scores (pgs_ref arrays: rsIDs)
    for f in glob.glob(os.path.join(PANEL, "pgs_ref", "*.npz")) + glob.glob(os.path.join(PANEL, "pgs_ref", "*", "*.npz")):
        z = np.load(f, allow_pickle=True)
        if "rsid" not in z.files:   # eur_dosage.npz: the reference dosages, no score
            continue
        rsids |= set(z["rsid"].tolist())
        why[f"score {os.path.basename(f)[:-4]}"] = len(z["rsid"])
    # The theme genes' ClinVar and GWAS Catalog variants
    genes = set()
    for g in profiles.theme_graphs():
        genes |= set(g.get("genes", []))
    regions = tg.gene_regions(genes)
    inside = tg.in_regions(regions)
    with gzip.open(gbuild.path("clinvar"), "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[0] == "#":
                continue
            c, p = line.split("\t", 2)[:2]
            c = c.replace("chr", "")
            if inside(c, int(p)):
                pos[c].add(int(p)); why["theme ClinVar"] += 1
    import zipfile, io
    for name in ("gwas_associations.zip",):
        zp = os.path.join(ROOT, "data", "reference", name)
        if not os.path.exists(zp):
            continue
        with zipfile.ZipFile(zp) as z:
            inner = [n for n in z.namelist() if n.endswith((".tsv", ".txt"))][0]
            with z.open(inner) as raw:
                f = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
                head = f.readline().rstrip("\n").split("\t")
                ci, pi = head.index("CHR_ID"), head.index("CHR_POS")
                for line in f:
                    p = line.rstrip("\n").split("\t")
                    if len(p) > pi and p[ci] and p[pi].isdigit() and inside(p[ci], int(p[pi])):
                        pos[p[ci]].add(int(p[pi])); why["theme GWAS"] += 1
    # rsIDs to positions through the panel's site list
    found = 0
    with gzip.open(os.path.join(PANEL, "sites.vcf.gz"), "rt") as f:
        for line in f:
            if line[0] == "#":
                continue
            c = line.split("\t", 5)
            if c[2] in rsids and len(c[3]) == 1 and len(c[4]) == 1:
                pos[c[0].replace("chr", "")].add(int(c[1])); found += 1
    why["rsIDs placed in the panel"] = found
    os.makedirs(OUT, exist_ok=True)
    json.dump({c: sorted(v) for c, v in pos.items()}, open(os.path.join(OUT, "targets.json"), "w"))
    json.dump(dict(why), open(os.path.join(OUT, "targets_why.json"), "w"), indent=1)
    print(json.dumps(dict(why), indent=1))
    print("positions:", sum(len(v) for v in pos.values()))


def extract_one(c):
    want = set(json.load(open(os.path.join(OUT, "targets.json"))).get(c, []))
    src, dst = RAW.format(c=c), os.path.join(OUT, f"chr{c}.vcf.gz")
    if not os.path.exists(src):   # chrX's file is a second version (.v2); it also needs the pipeline's 3-part split
        src = src.replace(".vcf.gz", ".v2.vcf.gz")
    if not os.path.exists(src):
        return c, 0, "no panel file"
    kept, t0 = 0, time.time()
    with gzip.open(src, "rt") as f, gzip.open(dst + ".part", "wt", compresslevel=4) as w:
        for line in f:
            if line[0] == "#":
                w.write(line)
                continue
            h = line.split("\t", 5)
            if len(h[3]) != 1 or len(h[4]) != 1 or int(h[1]) not in want:
                continue
            w.write(line)
            kept += 1
    os.replace(dst + ".part", dst)
    return c, kept, f"{round(time.time() - t0)} s"


def extract(jobs):
    with ProcessPoolExecutor(jobs) as ex:
        for c, kept, msg in ex.map(extract_one, sorted(CHROMS, key=lambda c: -os.path.getsize(RAW.format(c=c)) if os.path.exists(RAW.format(c=c)) else 0)):
            print(f"chr{c}: {kept:,} sites, {msg}", flush=True)


def parts():
    """The pack's files as Beagle reads them: chr1-22, and chrX in genome/impute.py's three ploidy parts."""
    from genome.impute import PANELS
    return [f"chr{c}" for c in CHROMS if c != "X"] + [n for n, _ in PANELS["1kgp_hc"]["x_parts"]]


def xsplit():
    """chrX.vcf.gz cut into the parts by position (men are haploid between the PARs, as the panel writes them)."""
    from genome.impute import PANELS
    bounds = [(n, *map(int, r.split(":")[1].split("-"))) for n, r in PANELS["1kgp_hc"]["x_parts"]]
    src = os.path.join(OUT, "chrX.vcf.gz")
    outs = {n: gzip.open(os.path.join(OUT, f"{n}.vcf.gz.part"), "wt", compresslevel=4) for n, _, _ in bounds}
    cnt = dict.fromkeys(outs, 0)
    with gzip.open(src, "rt") as f:
        for line in f:
            if line[0] == "#":
                for w in outs.values():
                    w.write(line)
                continue
            p = int(line.split("\t", 2)[1])
            n = next(n for n, a, b in bounds if a <= p <= b)
            outs[n].write(line); cnt[n] += 1
    for n, w in outs.items():
        w.close()
        os.replace(os.path.join(OUT, f"{n}.vcf.gz.part"), os.path.join(OUT, f"{n}.vcf.gz"))
    print(cnt)


def sites():
    """The pack's site list: the panel's sites.vcf.gz rows (rsIDs, alleles, population frequencies) at the pack's
    biallelic SNVs, in the same layout, so genome/impute.py reads it as it reads the full one."""
    keep = defaultdict(set)
    for part in parts():
        with gzip.open(os.path.join(OUT, f"{part}.vcf.gz"), "rt") as f:
            for line in f:
                if line[0] != "#":
                    c, p = line.split("\t", 2)[:2]
                    keep[c.replace("chr", "")].add(int(p))
    n = 0
    with gzip.open(os.path.join(PANEL, "sites.vcf.gz"), "rt") as f, gzip.open(os.path.join(OUT, "sites.vcf.gz.part"), "wt") as w:
        for line in f:
            if line[0] == "#":
                w.write(line); continue
            c = line.split("\t", 5)
            if int(c[1]) in keep.get(c[0].replace("chr", ""), ()) and len(c[3]) == 1 and len(c[4]) == 1:
                w.write(line); n += 1
    os.replace(os.path.join(OUT, "sites.vcf.gz.part"), os.path.join(OUT, "sites.vcf.gz"))
    print(f"sites.vcf.gz: {n:,} rows")


def bref3():
    jar = os.path.join(ROOT, "data", "reference", "imputation", "bref3.jar")
    for part in parts():
        src, dst = os.path.join(OUT, f"{part}.vcf.gz"), os.path.join(OUT, f"{part}.bref3")
        if not os.path.exists(src) or (os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src)):
            continue
        with open(dst + ".part", "wb") as out:
            subprocess.run(["java", "-Xmx8g", "-jar", jar, src], stdout=out, check=True)
        os.replace(dst + ".part", dst)
        print(f"{part}.bref3 {os.path.getsize(dst) / 1e6:.1f} MB", flush=True)


def install():
    """The bref3 files and the site list into data/reference/imputation/pack, where genome/impute.py looks when the
    full panel isn't on the machine (and the desktop build ships it)."""
    import shutil
    dst = os.path.join(ROOT, "data", "reference", "imputation", "pack")
    os.makedirs(dst, exist_ok=True)
    total = 0
    for name in [f"{p}.bref3" for p in parts()] + ["sites.vcf.gz"]:
        shutil.copy2(os.path.join(OUT, name), os.path.join(dst, name))
        total += os.path.getsize(os.path.join(dst, name))
    json.dump({"built": time.strftime("%Y-%m-%d"), "why": json.load(open(os.path.join(OUT, "targets_why.json"))),
               "files": len(parts()) + 1, "bytes": total}, open(os.path.join(dst, "pack.json"), "w"), indent=1)
    print(f"installed in {dst}: {total / 1e6:,.0f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=("targets", "extract", "xsplit", "sites", "bref3", "install"))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    if a.step == "targets":
        targets(*a.args)
    elif a.step == "extract":
        extract(a.jobs)
    else:
        {"xsplit": xsplit, "sites": sites, "bref3": bref3, "install": install}[a.step]()
