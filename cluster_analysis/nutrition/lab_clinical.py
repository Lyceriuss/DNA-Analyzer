"""The clinical side of each lab test: the code it is ordered under, what it measures, why it is ordered, how to prepare
and what the results mean, fetched from their sources. The same for everyone.

    python -m cluster_analysis.nutrition.lab_clinical      # -> cluster_analysis/nutrition/lab_clinical.json

The choices are the "loinc" codes on the markers of labtests.json (the Biomarkers tab) and nutrients.json (the blood
tests of the nutrients). What they are comes from:
  LOINC        NLM Clinical Tables: each code's long common name, which also names the sample (serum or plasma, blood).
  MedlinePlus  MedlinePlus Connect (NLM), asked with the LOINC code: its lab-test page, split into its own sections
               (what the test is, what it is used for, why it is ordered, preparing for it, what the results mean)
               and quoted as written.
"""
import html
import json
import os
import re
import time

from cluster_analysis import sources

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "lab_clinical.json")
CONFIGS = {"lab": os.path.join(HERE, "labtests.json"), "nut": os.path.join(HERE, "nutrients.json")}
LOINC = "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search"
MPLUS = "https://connect.medlineplus.gov/service"
# MedlinePlus lab-test pages use the same questions as headings; each maps to one part of the clinical path
SECTIONS = [("used", re.compile(r"used for", re.I)), ("what", re.compile(r"^what (is|are) ", re.I)),
            ("why", re.compile(r"^why do i need", re.I)), ("prepare", re.compile(r"prepare", re.I)),
            ("results", re.compile(r"results mean", re.I)), ("more", re.compile(r"anything else", re.I))]


def loinc_name(code):
    """The LOINC long common name of a code, or None."""
    def fetch():
        r = sources._request("GET", LOINC, params={"terms": code, "df": "LOINC_NUM,LONG_COMMON_NAME", "maxList": 5}, timeout=60)
        return next((name for num, name in (r or [0, [], None, []])[3] if num == code), None)
    return sources._cached("nlm_loinc", code, fetch)


def medlineplus(code):
    """MedlinePlus Connect's pages for a LOINC code: [{title, url, html}]."""
    def fetch():
        time.sleep(1)
        r = sources._request("GET", MPLUS, params={"mainSearchCriteria.v.cs": "2.16.840.1.113883.6.1",
                                                   "mainSearchCriteria.v.c": code, "knowledgeResponseType": "application/json"},
                             timeout=60)
        return [{"title": e["title"]["_value"], "url": e["link"][0]["href"].split("?")[0],
                 "html": (e.get("summary") or {}).get("_value", "")} for e in (r or {}).get("feed", {}).get("entry", [])]
    return sources._cached("medlineplus_loinc", code, fetch)


def text_of(fragment):
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()
    return re.sub(r"\s+([.,;:)])", r"\1", re.sub(r"\(\s+", "(", text))


def sections(page_html):
    """{section: {"text": [paragraphs], "list": [items]}} of a MedlinePlus lab-test page, in its own words."""
    out = {}
    for head, body in re.findall(r"<h2>(.*?)</h2>(.*?)(?=<h2>|$)", page_html, re.S):
        key = next((k for k, pat in SECTIONS if pat.search(text_of(head))), None)
        if not key or key in out:
            continue
        paras = [text_of(p) for p in re.findall(r"<p>(.*?)</p>", body, re.S)]
        items = [text_of(li) for li in re.findall(r"<li>(.*?)</li>", body, re.S)]
        names = next((p for p in paras if p.lower().startswith("other names")), None)
        # MedlinePlus closes each results section with the same link to its general page on lab tests
        paras = [p for p in paras if not p.startswith("Learn more about laboratory tests")]
        out[key] = {"text": [p for p in paras if p and p is not names], "list": [i for i in items if i]}
        if names:
            out.setdefault("names", names.split(":", 1)[-1].strip())
    return out


def sample(name):
    """The sample a LOINC name says the test is run on."""
    m = re.search(r"\] in ([A-Za-z ]+?)(?: by |$)", name or "")
    return m.group(1).strip() if m else None


def main():
    tests, pages = {}, {}
    for prefix, path in CONFIGS.items():
        cfg = json.load(open(path, encoding="utf-8"))
        for t in cfg.get("tests") or cfg.get("nutrients"):
            markers = {}
            for m in t["markers"]:
                code = m.get("loinc")
                if not code:
                    continue
                name = loinc_name(code)
                if not name:
                    print(f"   [!] LOINC {code} ({m['id']}) not found")
                # The lab-test page (medlineplus.gov/lab-tests/...) over a general health topic page
                found = medlineplus(code) if m.get("medlineplus", True) else []
                page = next((p for p in found if "/lab-tests/" in p["url"]), None)
                if page and page["url"] not in pages:
                    pages[page["url"]] = {"title": page["title"], "url": page["url"], **sections(page["html"])}
                markers[m["id"]] = {"loinc": code, "loinc_name": name, "sample": sample(name),
                                    "page": page["url"] if page else None}
                print(f"   {prefix}:{t['id']}:{m['id']} {code} · {name} · {page['title'] if page else 'no lab-test page'}")
            if markers:
                tests[f"{prefix}:{t['id']}"] = {"markers": markers}
    out = {"source": "LOINC via NLM Clinical Tables; MedlinePlus Connect (U.S. National Library of Medicine)",
           "tests": tests, "pages": pages}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"✅ {OUT}: {sum(len(t['markers']) for t in tests.values())} markers, {len(pages)} MedlinePlus pages")


if __name__ == "__main__":
    main()
