#!/usr/bin/env bash
# Downloads what cluster_analysis/medicines.py needs into data/reference (about 5 MB): ClinPGx (PharmGKB) clinical
# annotations, guideline annotations (CPIC, DPWG, CPNDS, RNPGx ...) and drug-label annotations (FDA, EMA, PMDA, Health
# Canada, Swissmedic), and the CPIC recommendation table per metaboliser type. Pass --refresh to download again.
# ClinVar and the 1000 Genomes site list come with the theme and imputation references.
set -e
cd "$(dirname "$0")/../data/reference"
get() { if [ "$REFRESH" = 1 ] || [ ! -s "$1" ]; then curl -sfLo "$1.part" "$2" && mv "$1.part" "$1"; fi; }
[ "$1" = --refresh ] && REFRESH=1
D=https://api.clinpgx.org/v1/download/file/data
get clinpgx_clinical_annotations.zip $D/clinicalAnnotations.zip
get clinpgx_guidelines.zip $D/guidelineAnnotations.json.zip
get clinpgx_drug_labels.zip $D/drugLabels.zip
get cpic_recommendations.json "https://api.cpicpgx.org/v1/recommendation?select=id,lookupkey,phenotypes,activityscore,allelestatus,implications,drugrecommendation,classification,population,comments,drug(name),guideline(name)"
echo "Done: $(pwd)"
