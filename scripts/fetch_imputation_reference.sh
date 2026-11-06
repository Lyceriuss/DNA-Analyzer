#!/usr/bin/env bash
# Downloads what src/impute.py needs into data/reference/imputation (about 5 GB): Beagle 5.5, the GRCh37 genetic
# maps, the 1000 Genomes phase 3 haplotype panels (one per chromosome, Beagle's bref3 format) and the 1000 Genomes
# site list (allele frequencies). Files already there are skipped.
set -e
cd "$(dirname "$0")/.."
mkdir -p data/reference/imputation/panel
cd data/reference/imputation
B=https://bochet.gcc.biostat.washington.edu/beagle
[ -s beagle.jar ] || curl -sfLo beagle.jar https://faculty.washington.edu/browning/beagle/beagle.27Feb25.75f.jar
[ -s plink.GRCh37.map.zip ] || curl -sfLo plink.GRCh37.map.zip $B/genetic_maps/plink.GRCh37.map.zip
for c in $(seq 1 22) X; do
  f=panel/chr$c.1kg.phase3.v5a.b37.bref3
  if [ ! -s "$f" ]; then
    (curl -sfLo "$f.part" "$B/1000_Genomes_phase3_v5a/b37.bref3/chr$c.1kg.phase3.v5a.b37.bref3" && mv "$f.part" "$f") &
  fi
  [ "$c" = 6 ] || [ "$c" = 12 ] || [ "$c" = 18 ] && wait
done
[ -s sites.vcf.gz ] || curl -sfLo sites.vcf.gz \
  https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.wgs.phase3_shapeit2_mvncall_integrated_v5c.20130502.sites.vcf.gz
wait
echo "Done: $(ls panel/*.bref3 | wc -l) panels in $(pwd)"
