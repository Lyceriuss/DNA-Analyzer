#!/usr/bin/env bash
# Downloads what cluster_analysis/medicines.py needs into data/reference (about 10 MB): ClinPGx (PharmGKB) clinical
# annotations and the studies behind them, drug names, guideline annotations (CPIC, DPWG, CPNDS, RNPGx ...) and drug-label annotations (FDA, EMA, PMDA, Health
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
get clinpgx_drugs.zip $D/drugs.zip
get clinpgx_variant_annotations.zip $D/variantAnnotations.zip
# WHO ATC names and classes (ChEMBL, CC BY-SA 3.0): the international name each medicine is sold under in Europe
if [ "$REFRESH" = 1 ] || [ ! -s chembl_atc.json ]; then
  python - <<'PY'
import json, urllib.request
rows, url = [], "https://www.ebi.ac.uk/chembl/api/data/atc_class.json?limit=1000"
while url:
    page = json.load(urllib.request.urlopen(url, timeout=120))
    rows += page["atc"]
    url = page["page_meta"]["next"] and "https://www.ebi.ac.uk" + page["page_meta"]["next"]
json.dump(rows, open("chembl_atc.json", "w", encoding="utf-8"))
print(len(rows), "ATC codes")
PY
fi
get cpic_recommendations.json "https://api.cpicpgx.org/v1/recommendation?select=id,lookupkey,phenotypes,activityscore,allelestatus,implications,drugrecommendation,classification,population,comments,drug(name),guideline(name)"
echo "Done: $(pwd)"
