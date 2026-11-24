"""Targeted-imputation spike, step 1 (chr22): from the 1000 Genomes high-coverage panel, keep only
  markers: the positions HG00096's chip file measures (its imputed CSV's measured rows, GRCh38), and
  targets: every 10th other biallelic SNV,
with HG00096 itself left out of the reference; its own panel haplotypes are the truth.
Writes to D:/DNA-Analyzer-build/spike/: panel.npz (pos, ref, alt, marker flag, haplotypes, truth),
ref_reduced.vcf.gz (the reduced panel, for Beagle), target.vcf (HG00096's chip genotypes, unphased), exclude.txt."""
import gzip, os, time
import numpy as np

RAW = r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38\raw\1kGP_high_coverage_Illumina.chr22.filtered.SNV_INDEL_SV_phased_panel.vcf.gz"
CSV = r"c:\Coding\DNA-Analyzer\data\output\imputation\HG00096\1kgp_hc\MyHeritage_raw_dna_data_HG00096.imputed.csv"
OUT = r"D:\DNA-Analyzer-build\spike"
os.makedirs(OUT, exist_ok=True)
SAMPLE = "HG00096"
t0 = time.time()

chip = {}
for line in open(CSV, encoding="utf-8"):
    if line[0] == "#" or line.startswith("RSID"):
        continue
    p = line.rstrip("\n").replace('"', "").split(",")
    if p[1] == "22" and p[4] == "measured" and len(p[3]) == 2:
        chip[int(p[2])] = p[3]
print("chip markers on chr22:", len(chip), flush=True)

pos, ref, alt, mark, haps, truth = [], [], [], [], [], []
samples = None
n_snv = 0
with gzip.open(RAW, "rt") as f, gzip.open(os.path.join(OUT, "ref_reduced.vcf.gz"), "wt", compresslevel=3) as rv:
    for line in f:
        if line.startswith("##"):
            if line.startswith("##fileformat") or line.startswith("##contig=<ID=chr22"):
                rv.write(line)
            continue
        if line.startswith("#CHROM"):
            cols = line.rstrip("\n").split("\t")
            samples = cols[9:]
            si = samples.index(SAMPLE)
            keep = [s for s in samples if s != SAMPLE]
            rv.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n')
            rv.write("\t".join(cols[:9] + keep) + "\n")
            continue
        head = line.split("\t", 5)
        p, r, a = int(head[1]), head[3], head[4]
        if len(r) != 1 or len(a) != 1:
            continue
        n_snv += 1
        is_marker = p in chip
        if not is_marker and n_snv % 10:
            continue
        parts = line.rstrip("\n").split("\t", 9)
        gts, fmt = parts[9], parts[8]
        if fmt != "GT":
            gts = "\t".join(x.split(":")[0] for x in gts.split("\t"))
        b = np.frombuffer(gts.encode(), dtype=np.uint8)
        if len(b) != 4 * len(samples) - 1 or not (b[1::4] == ord("|")).all():
            continue   # missing or unphased: skip the site
        h = np.empty(2 * len(samples), dtype=np.uint8)
        h[0::2], h[1::2] = b[0::4] - 48, b[2::4] - 48
        if h.max() > 1:
            continue
        tr = h[2 * si:2 * si + 2].copy()
        hk = np.delete(h, [2 * si, 2 * si + 1])
        pos.append(p); ref.append(r); alt.append(a); mark.append(is_marker); haps.append(hk); truth.append(tr)
        g = np.empty(len(hk) // 2 * 4 - 1, dtype=np.uint8)
        g[0::4], g[1::4], g[2::4] = hk[0::2] + 48, ord("|"), hk[1::2] + 48
        if len(g) > 3:
            g[3::4] = ord("\t")
        rv.write(f"chr22\t{p}\t22:{p}:{r}:{a}\t{r}\t{a}\t.\tPASS\t.\tGT\t{g.tobytes().decode()}\n")
        if len(pos) % 20000 == 0:
            print(len(pos), "sites kept of", n_snv, "SNVs,", round(time.time() - t0), "s", flush=True)

pos, mark = np.array(pos), np.array(mark)
H, T = np.array(haps), np.array(truth)
np.savez_compressed(os.path.join(OUT, "panel.npz"), pos=pos, ref=np.array(ref), alt=np.array(alt), marker=mark, H=H, truth=T)
# HG00096's chip genotypes as an unphased VCF at the marker sites whose letters match the panel's alleles
with open(os.path.join(OUT, "target.vcf"), "w") as tv:
    tv.write("##fileformat=VCFv4.2\n##contig=<ID=chr22>\n##FORMAT=<ID=GT,Number=1,Type=String,Description=\"Genotype\">\n")
    tv.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tTARGET\n")
    used = 0
    for i in np.where(mark)[0]:
        g = chip[int(pos[i])]
        if set(g) <= {ref[i], alt[i]}:
            tv.write(f"chr22\t{pos[i]}\t22:{pos[i]}:{ref[i]}:{alt[i]}\t{ref[i]}\t{alt[i]}\t.\tPASS\t.\tGT\t{g.count(alt[i]) and ('0/1' if g.count(alt[i]) == 1 else '1/1') or '0/0'}\n")
            used += 1
open(os.path.join(OUT, "exclude.txt"), "w").write(SAMPLE + "\n")
print(f"done: {n_snv} SNVs, {len(pos)} kept ({mark.sum()} markers, {len(pos) - mark.sum()} targets), {used} markers in target.vcf,"
      f" haplotypes {H.shape[1]}, {round(time.time() - t0)} s", flush=True)
