"""Polygenic risk scores for the cancers of the cancer theme, chosen from the PGS Catalog by a fixed rule.

    python -m cluster_analysis.themes.cancer_scores             # select -> cluster_analysis/nutrition/cancers.json
    python -m genome.pgs_reference build --set cancer <ids>     # the European reference for them (ids printed above)
    python -m cluster_analysis.profiles run --steps cancers     # score each profile (nutrition.py --config cancers.json)

The rule, per cancer of theme_graph_cancer.json (searching every ontology ID the theme maps to it):
  1. a score built from at most 5,000 variants (the risk variants of a GWAS, not a genome-wide score of a million),
  2. developed in people of European ancestry, the ancestry of the reference it is placed against,
  3. with a GRCh38 harmonised scoring file,
  4. then the one evaluated by the most publications in the PGS Catalog, then by the most evaluations, then the largest
     development sample.
No score is chosen by hand: running this again picks the same ones until the Catalog changes.
"""
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
THEME = os.path.join(HERE, "theme_graph_cancer.json")
OUT = os.path.join(os.path.dirname(HERE), "nutrition", "cancers.json")
API = "https://www.pgscatalog.org/rest"
H = {"User-Agent": "DNA-Analyzer (research; github.com/Lyceriuss/DNA-Analyzer)"}
MAX_VARIANTS = 5000
# The sex a score applies to, where the cancer is of one sex's organs
SEX = {"breast carcinoma": "female", "ovarian cancer": "female", "prostate carcinoma": "male"}
SV = {"breast carcinoma": "Bröstcancer", "prostate carcinoma": "Prostatacancer", "colorectal cancer": "Tjock- och ändtarmscancer",
      "lung carcinoma": "Lungcancer", "cutaneous melanoma": "Hudmelanom", "ovarian cancer": "Äggstockscancer",
      "exocrine pancreatic carcinoma": "Bukspottkörtelcancer", "basal cell carcinoma": "Basalcellscancer",
      "urinary bladder carcinoma": "Urinblåsecancer", "renal cell carcinoma": "Njurcancer"}


def get(url):
    for _ in range(5):
        r = requests.get(url, headers=H, timeout=60)
        if r.status_code in (429, 503):
            time.sleep(30)
            continue
        r.raise_for_status()
        time.sleep(0.7)  # the Catalog asks for at most 100 requests a minute
        return r.json()
    r.raise_for_status()


def scores_for(trait_ids):
    out = {}
    for t in trait_ids:
        url = f"{API}/score/search?trait_id={t}&include_children=0&limit=250"
        while url:
            j = get(url)
            for s in j["results"]:
                out[s["id"]] = s
            url = j.get("next")
    return list(out.values())


def eligible(s):
    dev = s.get("samples_variants") or []
    return ((s.get("variants_number") or MAX_VARIANTS + 1) <= MAX_VARIANTS
            and sorted({x.get("ancestry_broad") for x in dev}) == ["European"]
            and bool(((s.get("ftp_harmonized_scoring_files") or {}).get("GRCh38") or {}).get("positions")))


def evaluations(pid):
    res, url = [], f"{API}/performance/search?pgs_id={pid}&limit=250"
    while url:
        j = get(url)
        res += j["results"]
        url = j.get("next")
    return len({(x.get("publication") or {}).get("id") for x in res}), len(res)


def main():
    theme = json.load(open(THEME, encoding="utf-8"))
    tests = []
    for mid, name in theme["diseases"].items():
        if name == "cancer":
            continue
        cands = [s for s in scores_for(theme["disease_ids"].get(mid, [mid])) if eligible(s)]
        ranked = []
        for s in cands:
            pubs, evals = evaluations(s["id"])
            n = sum(x.get("sample_number") or 0 for x in s.get("samples_variants") or [])
            ranked.append((-pubs, -evals, -n, s["id"], s, pubs))
        ranked.sort(key=lambda r: r[:4])
        if not ranked:
            print(f"{name}: no score meets the rule")
            continue
        s, pubs = ranked[0][4], ranked[0][5]
        pub = s.get("publication") or {}
        print(f"{name}: {s['id']} ({s['variants_number']} variants, {pub.get('firstauthor')} {(pub.get('date_publication') or '')[:4]},"
              f" evaluated in {pubs} publications; {len(cands)} candidates)")
        t = {"id": name.split()[0] if name.split()[0] not in ("exocrine", "urinary", "renal", "cutaneous", "basal") else
             {"exocrine": "pancreas", "urinary": "bladder", "renal": "kidney", "cutaneous": "melanoma", "basal": "bcc"}[name.split()[0]],
             "name": s.get("trait_reported") or name.capitalize(), "sv": SV.get(name, name), "group": "Cancer risk", "disease": mid,
             "markers": [{"id": s["id"].lower(), "name": s.get("trait_reported") or name, "traits": [mid], "higher": "worse",
                          "pgs_ref": s["id"]}],
             "selected": {"candidates": len(cands), "evaluating_publications": pubs}}
        if name in SEX:
            t["sex"] = SEX[name]
        tests.append(t)
    data = {"about": "Polygenic risk scores for the cancers of the cancer theme, read by nutrition.py --config cancers.json --prefix can "
                     "(profiles.py run --steps cancers). Written by cluster_analysis/themes/cancer_scores.py from the PGS Catalog by a "
                     "fixed rule (see its docstring); don't edit by hand. Each score is placed by rank among the 1000 Genomes European "
                     "founders (genome/pgs_reference.py, set 'cancer'). higher: worse (a higher score, a higher risk).",
            "tests": tests}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\nWrote {OUT}\nBuild the reference: python -m genome.pgs_reference build --set cancer "
          + " ".join(t["markers"][0]["pgs_ref"] for t in tests))


if __name__ == "__main__":
    main()
