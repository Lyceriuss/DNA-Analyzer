#!/bin/sh
# The 1000 Genomes high-coverage (30x) phased panel: 3,202 samples on GRCh38 (Byrska-Bishop et al. 2022), from EBI's
# public FTP, checked against its MD5 manifest and converted to Beagle's bref3 format for genome/impute.py's
# "1kgp_hc" panel. About 31 GB raw and 15 GB converted, so it goes to a folder of your choice:
#
#     sh scripts/fetch_1kgp_hc_panel.sh "D:/DNA-Analyzer-reference/1kGP_high_coverage_GRCh38"
#
# then point the imputation at DIR/bref3 if that isn't the default (genome/impute.py PANELS):
#     DNA_PANEL_DIR_1KGP_HC=DIR/bref3
#
# Resumes partial downloads (curl -C -) and skips chromosomes already converted. The panel has no singletons, so
# nothing is filtered. Needs curl, md5sum, Java and Python (no Docker); bref3.jar comes from scripts/fetch_imputation_reference.sh.
# The raw files can be deleted once bref3/ is complete and the frequency tables are built from them.
set -e
DIR=${1:?usage: fetch_1kgp_hc_panel.sh DIR}
REPO="$(cd "$(dirname "$0")/.." && pwd)"
JAR="$REPO/data/reference/imputation/bref3.jar"
BASE=https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage/working/20220422_3202_phased_SNV_INDEL_SV
mkdir -p "$DIR/raw" "$DIR/bref3"
cd "$DIR/raw"

# Stop, don't retry, when a drive runs low: a crash-and-retry loop must not be able to fill a disk. GB free to keep:
space() {
  for d in "/c 20" "$DIR 50"; do set -- $d
    free=$(df -BG "$1" | awk 'NR==2 {gsub("G","",$4); print $4}')
    [ "$free" -ge "$2" ] || { echo "stopping: $1 has ${free} GB free, below $2 GB"; exit 1; }
  done
}
space
rm -f "$DIR"/bref3/*.part "$DIR"/chrX*.vcf.gz "$DIR"/chrX*.vcf.gz.part   # leftovers from a run that crashed

name() { [ "$1" = X ] && echo "1kGP_high_coverage_Illumina.chrX.filtered.SNV_INDEL_SV_phased_panel.v2.vcf.gz" \
                      || echo "1kGP_high_coverage_Illumina.chr$1.filtered.SNV_INDEL_SV_phased_panel.vcf.gz"; }
CHROMS="$(seq 1 22) X"

# 1. Download, one file at a time
for f in 20220804_manifest.txt README_1kGP_phased_panel_110722.pdf change_log.txt; do curl -sS -f -C - -o "$f" "$BASE/$f"; done
for c in $CHROMS; do
  f=$(name "$c")
  [ -s "../bref3/chr$c.bref3" ] && continue
  for x in "$f" "$f.tbi"; do
    for try in 1 2 3 4 5; do
      curl -sS -f -C - --retry 3 -o "$x" "$BASE/$x" && break
      echo "retry $try: $x"; sleep 30
    done
  done
  echo "$(date +%H:%M) downloaded chr$c"
done

# 2. Check against the manifest
for c in $CHROMS; do
  f=$(name "$c")
  [ -s "../bref3/chr$c.bref3" ] || awk -v f="$f" '$1 == f {print $2"  "$1}' 20220804_manifest.txt
done > ../md5_todo.txt
[ -s ../md5_todo.txt ] && md5sum -c ../md5_todo.txt
rm -f ../md5_todo.txt

# 3. Convert, two chromosomes at a time
one() {
  out="../bref3/chr$1.bref3"
  [ -s "$out" ] && return
  space
  java -Xmx10g -jar "$JAR" "$(name "$1")" > "$out.part" && mv "$out.part" "$out" && echo "$(date +%H:%M) converted chr$1"
}
for pair in "1 22" "2 21" "3 20" "4 19" "5 18" "6 17" "7 16" "8 15" "9 14" "10 13" "11 12"; do
  for c in $pair; do one "$c" & done; wait
done
# chrX in three parts: men are diploid in the pseudo-autosomal regions and haploid between them, and Beagle needs
# one ploidy per sample per file. genome/vcf.py cuts the regions in Python (bounds from genome/impute.py's x_parts),
# checks the parts add up to the index's record count, converts them and deletes the cut VCFs.
space
(cd "$REPO" && python -m genome.vcf split-x "$DIR")
echo "done: $(ls ../bref3/*.bref3 | wc -l) chromosomes in $DIR/bref3"
