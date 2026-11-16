"""What lowers the risk of each cancer of the cancer theme: the avoidable causes IARC classifies with sufficient evidence,
and the European Code Against Cancer's advice for them, in English and Swedish.

    python -m cluster_analysis.themes.cancer_prevention      # -> cluster_analysis/themes/cancer_prevention.json

Two sources, both fetched, neither written here:
  IARC Monographs, "List of classifications by cancer sites with sufficient or limited evidence in humans" (PDF):
      per cancer site, the agents with sufficient evidence in humans.
  European Code Against Cancer, 5th edition (IARC/WHO): the 14 recommendations for individuals, from its English and
      Swedish pages.
The only choice made here is AGENTS: which IARC agent a recommendation is about (tobacco smoking -> the smoking
recommendation). A cancer whose avoidable causes no recommendation covers gets none, said as such (prostate has no agent
with sufficient evidence at all).
"""
import html
import io
import json
import os
import re

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cancer_prevention.json")
IARC_PDF = "https://monographs.iarc.who.int/wp-content/uploads/2019/07/Classifications_by_cancer_site.pdf"
ECAC = {"en": "https://cancer-code-europe.iarc.who.int/", "sv": "https://cancer-code-europe.iarc.who.int/sv/startsida/"}
H = {"User-Agent": "Mozilla/5.0 (DNA-Analyzer; research; github.com/Lyceriuss/DNA-Analyzer)"}

# The cancers of theme_graph_cancer.json and their IARC sites
SITES = {"breast carcinoma": ["Breast"], "prostate carcinoma": ["Prostate"], "colorectal cancer": ["Colon", "Rectum"],
         "lung carcinoma": ["Lung"], "cutaneous melanoma": ["Skin (melanoma)"], "ovarian cancer": ["Ovary"],
         "exocrine pancreatic carcinoma": ["Pancreas"], "basal cell carcinoma": ["Skin (malignant non-melanoma)"],
         "urinary bladder carcinoma": ["Urinary bladder"], "renal cell carcinoma": ["Kidney"]}
# The choice: which IARC agents (their names in the list, as written there) each ECAC5 recommendation (its topic heading)
# is about. Only avoidable causes; the rest of IARC's list (drugs, infections, radiation in medicine) isn't matched here
AGENTS = [
    (["Tobacco smoking", "Tobacco, smokeless"], "Smoking"),
    (["Tobacco smoke, secondhand"], "Exposure to other people"),
    (["Alcoholic beverages"], "Alcohol"),
    (["Solar radiation", "Ultraviolet-emitting tanning devices"], "Sun exposure"),
    (["Radon-222"], "Indoor radon"),
    (["Processed meat (consumption of)"], "Diet"),
    (["Outdoor air pollution", "Particulate matter in outdoor air pollution", "Diesel engine exhaust"], "Air pollution"),
    (["Estrogen–progestogen menopausal therapy", "Estrogen therapy, postmenopausal"], "Hormone replacement"),
    (["Asbestos (all forms)", "Painter (occupational exposure as a)", "Firefighter (occupational exposure as a)",
      "Rubber manufacturing industry", "Aluminium production", "Coal-tar distillation", "Welding fumes", "Silica dust, crystalline",
      "Trichloroethylene"], "Cancer-causing factors at work"),
]


def get(url, **kw):
    r = requests.get(url, headers=H, timeout=60, **kw)
    r.raise_for_status()
    return r


def iarc_sites():
    """{site: the agents with sufficient evidence in humans, as one text} from the IARC list. A site's row can run over
    a page break (the continued rows have an empty site cell), and agent names wrap over lines: the text is kept whole
    and agents are found in it by name."""
    import pdfplumber
    rows, last = {}, None
    with pdfplumber.open(io.BytesIO(get(IARC_PDF).content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    if not r or len(r) < 2:
                        continue
                    text = re.sub(r"\s+", " ", r[1] or "").strip()
                    site = re.sub(r"\s+", " ", r[0] or "").strip()
                    if site.startswith("List of classifications") or site == "Cancer site":
                        continue  # the header repeated on every page: not a site, and the row before continues after it
                    if site:
                        last = site
                        rows[site] = text
                    elif last and text:
                        rows[last] += " " + text
    return rows


def ecac(lang):
    """[{n, topic, text}] the 14 recommendations, from the page's numbered images, headings and texts."""
    h = get(ECAC[lang]).text
    out = []
    for m in re.finditer(r'/(\d+)-european-code-against-cancer[^"]*\.svg"', h):
        n = int(m.group(1))
        if any(x["n"] == n for x in out):
            continue
        rest = h[m.end():]
        t = re.search(r"<h2[^>]*>(.*?)</h2>", rest, re.S)
        b = re.search(r'data-widget_type="text-editor\.default">(.*?)</div>', rest, re.S)
        if not (t and b):
            continue
        clean = lambda s: html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).replace("​", "").strip()
        items = [clean(x) for x in re.findall(r"<li[^>]*>(.*?)</li>", b.group(1), re.S)]
        text = clean(re.sub(r"<ul.*?</ul>", "", b.group(1), flags=re.S))
        out.append({"n": n, "topic": clean(t.group(1)), "text": text, "items": items})
    return sorted(out, key=lambda x: x["n"])


def main():
    sites = iarc_sites()
    en, sv = ecac("en"), {r["n"]: r for r in ecac("sv")}
    print(f"IARC: {len(sites)} sites; ECAC5: {len(en)} recommendations (en), {len(sv)} (sv)")
    if len(en) != 14 or len(sv) != 14:
        raise SystemExit("the European Code Against Cancer pages didn't give 14 recommendations each: the page layout changed")
    recs = []
    for r in en:
        s = sv[r["n"]]
        recs.append({"n": r["n"], "topic": r["topic"], "topic_sv": s["topic"], "text": r["text"], "text_sv": s["text"],
                     "items": r["items"], "items_sv": s["items"]})
    by_topic = lambda key: next((r for r in recs if r["topic"].lower().startswith(key.lower())), None)
    # Display names (English, Swedish) from the cancer scores, joined through the theme's disease ids
    theme = json.load(open(os.path.join(HERE, "theme_graph_cancer.json"), encoding="utf-8"))
    theme_ids = {name: mid for mid, name in theme["diseases"].items()}
    scored = json.load(open(os.path.join(os.path.dirname(HERE), "nutrition", "cancers.json"), encoding="utf-8"))["tests"]
    cancers = {}
    for cancer, names in SITES.items():
        text = " ".join(sites.get(n, "") for n in names)
        if not any(n in sites for n in names):
            raise SystemExit(f"{cancer}: IARC site {names} not found")
        hit = {}
        for agent_names, topic in AGENTS:
            found = [a for a in agent_names if a in text]
            if found:
                r = by_topic(topic)
                if r is None:
                    raise SystemExit(f"no ECAC5 recommendation starts with {topic!r}")
                hit.setdefault(r["n"], []).extend(found)
        agents = sorted({a for v in hit.values() for a in v})
        shown = next((t for t in scored if t["disease"] == theme_ids.get(cancer)), None)
        cancers[cancer] = {"name": shown["name"] if shown else cancer.capitalize(), "sv": shown["sv"] if shown else cancer,
                           "iarc_sites": names, "agents": agents, "recommendations": [{"n": n, "agents": sorted(v)} for n, v in sorted(hit.items())]}
        print(f"{cancer}: {len(agents)} agents; recommendations {[x['n'] for x in cancers[cancer]['recommendations']]}")
    data = {"about": "Avoidable causes per cancer of the cancer theme (IARC, sufficient evidence in humans) and the European Code "
                     "Against Cancer's advice for them. Written by cluster_analysis/themes/cancer_prevention.py; don't edit by hand.",
            "sources": {"iarc": IARC_PDF, "ecac": ECAC}, "recommendations": recs, "cancers": cancers}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
