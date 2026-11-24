"""How big an imputation pack would be: the panel positions the analysis reads (an rsID list, e.g. a trace of every
step's reads) plus a chip layout's positions, counted against the 1000 Genomes high-coverage site list.
    python scripts/spike/pack_size.py RSIDS.json CHIP_IMPUTED_CSV [SITES_VCF_GZ]
RSIDS.json: a JSON list of rsIDs. CHIP_IMPUTED_CSV: an imputed CSV whose measured rows give the chip's GRCh38
positions (a public sample's, e.g. HG00096). Prints counts only: no genotype is read."""
import gzip, json, sys
from collections import Counter

rsids = set(json.load(open(sys.argv[1])))
chip = set()
for line in open(sys.argv[2], encoding="utf-8"):
    if line[0] == "#" or line.startswith("RSID"):
        continue
    p = line.split(",", 5)
    if p[4] == "measured":
        chip.add((p[1].strip('"'), int(p[2].strip('"'))))
sites = sys.argv[3] if len(sys.argv) > 3 else r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38\sites.vcf.gz"
n = snv = 0
hit_rs, hit_chip, both = set(), set(), 0
by_maf = Counter()
with gzip.open(sites, "rt") as f:
    for line in f:
        if line[0] == "#":
            continue
        c = line.split("\t", 8)
        n += 1
        if len(c[3]) != 1 or len(c[4]) != 1:
            continue
        snv += 1
        key = (c[0].replace("chr", ""), int(c[1]))
        r = c[2] in rsids
        k = key in chip
        if r:
            hit_rs.add(c[2])
        if k:
            hit_chip.add(key)
        if r or k:
            both += 1
            af = next((float(x[3:]) for x in c[7].split(";") if x.startswith("AF=")), 0.0)
            m = min(af, 1 - af)
            by_maf["<0.1%" if m < .001 else "0.1-1%" if m < .01 else "1-5%" if m < .05 else ">=5%"] += 1
print(f"panel sites {n:,}, biallelic SNVs {snv:,}")
print(f"analysis rsIDs {len(rsids):,}: in the panel {len(hit_rs):,}")
print(f"chip positions {len(chip):,}: in the panel {len(hit_chip):,}")
print(f"pack positions (union) {both:,}; by minor-allele frequency {dict(by_maf)}")
