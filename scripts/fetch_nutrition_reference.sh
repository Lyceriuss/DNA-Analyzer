#!/usr/bin/env bash
# Downloads what cluster_analysis/nutrition.py needs into data/reference/nutrition (about 8 MB):
#   * Livsmedelsverket's summary of the Nordic Nutrition Recommendations 2023 (and its errata), parsed into
#     cluster_analysis/nnr_2023.json (kept in git; rebuild it only when Livsmedelsverket revises the summary)
#   * Livsmedelsverket's food database (API, CC BY 4.0), ~5,200 calls, a few minutes
#   * the PGS Catalog scoring files named in cluster_analysis/nutrients.json (harmonised, GRCh37)
# The GWAS Catalog, ClinVar, ClinPGx, Reactome, the Ensembl GTF and the 1000 Genomes site list come with the theme,
# medicines and imputation references. Needs: pip install pdfplumber. Pass --refresh to download again.
set -e
cd "$(dirname "$0")/.."
mkdir -p data/reference/nutrition
get() { if [ "$REFRESH" = 1 ] || [ ! -s "$1" ]; then curl -sfLo "$1.part" "$2" && mv "$1.part" "$1"; fi; }
[ "$1" = --refresh ] && REFRESH=1
L=https://www.livsmedelsverket.se/globalassets/publikationsdatabas/broschyrer-foldrar
get data/reference/nutrition/snr_2023.pdf $L/slutleverans_nordiska-naringsrekommendationer-2023.pdf
get data/reference/nutrition/snr_errata_2025-09.pdf $L/errata-referensvarden-for-energi-och-naringsamnen-september-2025.pdf
python -m cluster_analysis.nutrition_reference nnr
if [ "$REFRESH" = 1 ] || [ ! -s data/reference/nutrition/livsmedel.json ]; then
  python -m cluster_analysis.nutrition_reference foods
fi
python -m cluster_analysis.nutrition_reference pgs
echo "Done"
