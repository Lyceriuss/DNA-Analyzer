"""The clinical path of the mind theme: for each ICD-10 diagnostic group, the codes it covers, its validated screening
tests and the medicines of its drug classes, fetched from their sources. The same for everyone.

    python -m cluster_analysis.themes.mind_clinical      # -> cluster_analysis/themes/mind_clinical.json

The choices are in theme_graph.THEMES["mind"]["organs"]: which ICD-10 codes, screening tests (the PubMed id of each
test's validation paper) and ATC classes belong to a group. What they are comes from:
  ICD-10      NLM Clinical Tables (ICD-10-CM): the billable codes under each category, with their titles.
  Screening   Europe PMC: each validation paper's title, authors, journal, year and abstract; the abstract's
              sentences on scores, cut-offs, sensitivity or specificity are quoted as written.
  Medicines   ChEMBL's copy of the WHO ATC classification (data/reference/chembl_atc.json): the drugs in each class.
How a person's genes change the response to those drugs is the Medicines tab's (CPIC and DPWG guidelines, ClinPGx);
the explorer joins the two by drug name.
"""
import json
import os
import re
import time

from cluster_analysis import sources
from cluster_analysis.themes.theme_graph import THEMES

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "mind_clinical.json")
ATC_PATH = "data/reference/chembl_atc.json"
NLM = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
# Abstract sentences that say how the test is scored and how well it works
QUOTE = re.compile(r"cut-?off|cut-?point|score[sd]? (of|≥|>=)|sensitiv|specificit|positive predictive|area under|AUC", re.I)


def icd_codes(category):
    """[(code, title)] of the billable ICD-10-CM codes under a category (F32 -> F32.0 ... F32.9)."""
    def fetch():
        r = sources._request("GET", NLM, params={"sf": "code", "terms": category, "maxList": 200}, timeout=60)
        return [[c, t] for c, t in (r or [0, [], None, []])[3] if c.startswith(category)]
    return sources._cached("nlm_icd10cm", category, fetch)


def paper(pmid):
    """A paper's citation and abstract from Europe PMC."""
    def fetch():
        time.sleep(1)  # Europe PMC answers bursts with empty pages
        r = sources._request("GET", EPMC, params={"query": f"EXT_ID:{pmid} AND SRC:MED", "format": "json",
                                                   "resultType": "core"}, timeout=60) or {}
        hits = (r.get("resultList") or {}).get("result") or []
        if not hits:
            raise RuntimeError(f"Europe PMC has no paper {pmid}")
        h = hits[0]
        return {"pmid": pmid, "title": h.get("title"), "authors": h.get("authorString"), "journal": (h.get("journalInfo") or {})
                .get("journal", {}).get("title") or h.get("journalTitle"), "year": h.get("pubYear"),
                "abstract": re.sub(r"<[^>]+>", "", h.get("abstractText") or ""), "doi": h.get("doi")}
    return sources._cached("europepmc_paper", pmid, fetch)


def quotes(abstract, n=3):
    """The abstract's sentences on scoring and accuracy, as written. Structured abstracts arrive with their headings glued
    to the text ("...achieved.ConclusionsThe ..."): the headings are dropped first."""
    heads = r"Background|Objectives?|Aims?|Purpose|Methods?|Design|Setting|Participants|Measurements|Results|Conclusions?"
    abstract = re.sub(rf"(?<=[.!?:])\s*(?:{heads})(?=[A-Z])", " ", abstract)
    abstract = re.sub(rf"^(?:{heads})(?=[A-Z])", "", abstract)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", abstract)
    return [s.strip() for s in sentences if QUOTE.search(s)][:n]


def main():
    atc = json.load(open(ATC_PATH, encoding="utf-8"))
    out = {"source": {"icd": "https://clinicaltables.nlm.nih.gov/apidoc/icd10cm/v3/doc.html",
                      "papers": "https://europepmc.org", "atc": "https://www.ebi.ac.uk/chembl/"},
           "groups": {}}
    for g in THEMES["mind"]["organs"]:
        codes = {c: icd_codes(c) for c in g["icd"]}
        screens = []
        for s in g["screens"]:
            p = paper(s["pmid"])
            screens.append({"name": s["name"], **{k: p[k] for k in ("pmid", "title", "authors", "journal", "year", "doi")},
                            "quotes": quotes(p["abstract"]),
                            "url": f"https://europepmc.org/article/MED/{s['pmid']}"})
        classes, drugs = {}, {}
        for a in atc:
            for pre in g["atc"]:
                if a["level5"].startswith(pre):
                    level = next(f"level{i}" for i in (5, 4, 3, 2) if a.get(f"level{i}") == pre) if pre != a["level5"] else "level5"
                    classes[pre] = a.get(level + "_description") or a["who_name"]
                    drugs[a["who_name"].lower()] = a["level5"]
        out["groups"][g["id"]] = {"icd": [{"category": c, "codes": v} for c, v in codes.items()], "screens": screens,
                                  "classes": [{"atc": k, "name": v} for k, v in classes.items()],
                                  "drugs": dict(sorted(drugs.items()))}
        print(f"  {g['id']}: {sum(len(v) for v in codes.values())} ICD-10 codes, {len(screens)} screening tests "
              f"({sum(len(s['quotes']) for s in screens)} quotes), {len(drugs)} medicines")
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
