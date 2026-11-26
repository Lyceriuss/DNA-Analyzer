"""How much each familiar trait's score says: what its own study reports about it, quoted, never estimated here.

    python -m cluster_analysis.inheritance.impact          # sweep the featured traits' papers, write the file
    python -m cluster_analysis.inheritance.impact --show   # print what was found per trait

For each trait in featured.json, the study its prediction is built on (the model's PMID) is read: the abstract from Europe
PMC and the open full text (Europe PMC, else NCBI PMC). The sentences that report how much the genetic score or the
variants explain (variance explained, R2, SNP heritability, AUC, how many variants are estimated to affect the trait)
are kept word for word with their place in the paper, and the largest "explains N% of the variance/variation" figure a
prediction sentence gives becomes the headline number. A paper with nothing of the kind says so; nothing is guessed.

The effect sizes in the GWAS Catalog come in mixed units (cm, standard deviations, log odds, "unit"), so a variance
explained can't be computed the same way for every trait from the model itself; the study's own report is the source.

Output: data/reference/inheritance/featured_impact.json, {trait id: {pmid, pmcid, open, explains_pct, h2_snp,
n_variants_estimate, quotes: [{text, where}]}}. Public: the same for everyone (genome/references.json lists it).
"""
import json
import os
import re
import sys
import time

import requests

from cluster_analysis.inheritance import predict

OUT = os.path.join(predict.REF, "inheritance", "featured_impact.json")
UA = {"User-Agent": "DNA-Analyzer (research tool; contact via repository)"}
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"

# A sentence that says how much is explained or inherited
KEEP = re.compile(r"(\d+(?:\.\d+)?\s?%\s*(?:of\s+(?:the\s+)?(?:phenotypic\s+|trait\s+)?(?:variance|variation|variability))"
                  r"|explain\w*\s+(?:up to\s+|about\s+|approximately\s+|~\s?)?\d+(?:\.\d+)?\s?%"
                  r"|\bR\s?2\b|R²|\bAUC\b|area under the (?:receiver|curve)"
                  r"|SNP[- ]?(?:based\s+)?heritabilit|h\s?2\s?SNP|h2SNP|SNP-h2"
                  r"|\d[\d,]*\s+(?:common\s+)?variants\s+(?:were\s+)?(?:estimated|explain|confer|influenc))", re.I)
ABOUT_SCORE = re.compile(r"polygenic|genetic score|risk score|PGS|PRS|PGI|predict", re.I)
PICKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "impact_picks.json")
PCT = re.compile(r"(?:explain\w*\s+(?:up to\s+|about\s+|approximately\s+|~\s?)?(\d+(?:\.\d+)?)\s?%)|(?:(\d+(?:\.\d+)?)\s?%\s*of\s+(?:the\s+)?(?:phenotypic\s+|trait\s+)?(?:variance|variation|variability))", re.I)
H2 = re.compile(r"(?:SNP[- ]?(?:based\s+)?heritabilit\w*|h\s?2\s?SNP|h2SNP)[^.;]{0,60}?(?:=|of|was|is|:)\s*(0?\.\d+|\d+(?:\.\d+)?\s?%)", re.I)
NVAR = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s+(?:common\s+)?variants\s+(?:were\s+)?(?:estimated|explain|confer|influenc)", re.I)


def fetch(url, kind="json", tries=5):
    """GET with waits on 429/503 (the servers' rate limits) and retries on other errors."""
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code in (429, 503):
                ra = r.headers.get("Retry-After") or ""
                time.sleep(min(int(ra) if ra.isdigit() else 20, 120))
                continue
            if r.status_code >= 400:
                return None
            return r.json() if kind == "json" else r.text
        except (requests.RequestException, ValueError):
            time.sleep(3 * (i + 1))
    return None


def text_of(xml):
    xml = re.sub(r"<(xref|sup|ref-list)[^>]*>.*?</\1>", " ", xml or "", flags=re.S)
    t = re.sub(r"<[^>]+>", " ", xml)
    t = re.sub(r"&gt;", ">", re.sub(r"&lt;", "<", re.sub(r"&amp;", "&", t)))
    return re.sub(r"\s+", " ", t).strip()


def sentences(t):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", t) if 30 <= len(s.strip()) <= 600]


def paper(pmid):
    """(abstract, full text or None, pmcid, title)."""
    d = fetch(f"{EPMC}/search?query=EXT_ID:{pmid}%20AND%20SRC:MED&resultType=core&format=json") or {}
    r = ((d.get("resultList") or {}).get("result") or [{}])[0]
    abstract, pmcid = text_of(r.get("abstractText") or ""), r.get("pmcid")
    full = None
    if pmcid:
        full = fetch(f"{EPMC}/{pmcid}/fullTextXML", kind="text")
        if not full or full.lstrip().startswith("{"):
            full = fetch(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmcid.replace('PMC', '')}&retmode=xml", kind="text")
        if full:
            body = re.search(r"<body.*?</body>", full, re.S)
            full = text_of(body.group(0) if body else full)
            time.sleep(0.4)   # NCBI: at most 3 requests a second without a key
    return abstract, full, pmcid, r.get("title")


def sweep_one(pmid):
    abstract, full, pmcid, title = paper(pmid)
    quotes, seen = [], set()
    for where, t in (("abstract", abstract), ("full text", full)):
        for s in sentences(t or ""):
            if KEEP.search(s) and s not in seen and not re.search(r"\b(?:imputation|INFO|R2\s?[<>]|r\s?2\s?<|LD\b|linkage)", s):
                seen.add(s)
                quotes.append({"text": s, "where": where, "score": bool(ABOUT_SCORE.search(s))})
    # The headline: the largest "explains N%" a sentence about the score's prediction gives
    pcts = [float(a or b) for q in quotes if q["score"] for a, b in PCT.findall(q["text"]) if (a or b)]
    pcts = [p for p in pcts if 0 < p < 100]
    h2s = []
    for q in quotes:
        for v in H2.findall(q["text"]):
            v = v.replace(" ", "")
            x = float(v[:-1]) / 100 if v.endswith("%") else float(v)
            if 0 < x < 1:
                h2s.append(x)
    nvar = [int(n.replace(",", "")) for q in quotes for n in NVAR.findall(q["text"])]
    quotes.sort(key=lambda q: (not q["score"], q["where"] != "abstract"))
    return {"pmid": pmid, "pmcid": pmcid, "title": title, "open": bool(full),
            "explains_pct": max(pcts) if pcts else None, "h2_snp": round(max(h2s), 3) if h2s else None,
            "n_variants_estimate": max(nvar) if nvar else None,
            "quotes": [{"text": q["text"], "where": q["where"]} for q in quotes[:4]],
            "sentences": [{"text": q["text"], "where": q["where"]} for q in quotes[:80]]}


def sweep():
    models = {m["id"]: m for m in predict.load_models()}
    out = {}
    for f in predict.featured(raw=True):
        m = models.get(f["id"])
        if not m or not m.get("pmid"):
            out[f["id"]] = {"pmid": None, "quotes": [], "explains_pct": None, "h2_snp": None, "n_variants_estimate": None, "open": False}
            continue
        print(f"   {f['name']}: PMID {m['pmid']}", flush=True)
        out[f["id"]] = sweep_one(m["pmid"]) | {"variants_used": len(m["variants"])}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"source": "Europe PMC and NCBI PMC (abstracts and open full texts)", "swept": time.strftime("%Y-%m-%d"),
                   "traits": out}, fh, ensure_ascii=False, indent=1)
    print(f"✅ {len(out)} traits → {OUT}")
    return out


def raw():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)["traits"]
    except (OSError, ValueError, KeyError):
        return {}


def picks():
    try:
        with open(PICKS, encoding="utf-8") as f:
            return json.load(f)["picks"]
    except (OSError, ValueError, KeyError):
        return {}


def _find(sents, quote, figure):
    """The paper's sentence that holds the pick's quote and its figure, or None."""
    for q in sents:
        # the figure as written, or with the spaces the full-text XML puts inside numbers ("0 . 167")
        if quote in q["text"] and (figure in q["text"] or figure in re.sub(r"(?<=\d) ?([.,]) ?(?=\d)", r"\1", q["text"])):
            return q
    return None


def load():
    """Per familiar trait: what its study reports about how much the score says, from the pick (impact_picks.json)
    when the paper's own text holds its quote and figure; else kind None (the study reports no such figure, or its
    text isn't open). {pmid, open, kind, value, figure, quote, where, note, variants_estimate}."""
    out = {}
    pk = picks()
    for tid, v in raw().items():
        sents = v.get("sentences") or v.get("quotes") or []
        r = {"pmid": v.get("pmid"), "open": v.get("open"), "kind": None}
        p = pk.get(tid)
        q = _find(sents, p["quote"], p["figure"]) if p else None
        if q:
            x = float(p["figure"].replace(",", ""))
            r |= {"kind": p["kind"], "figure": p["figure"], "quote": q["text"], "where": q["where"], "note": p.get("note"),
                  # a share as a percentage: 0.363 -> 36.3 for heritability written as a fraction
                  "value": round(x * 100, 1) if p["kind"] == "h2" and x < 1 else x}
            ve = p.get("variants_estimate")
            if ve:
                vq = _find(sents, ve["quote"], ve["figure"])
                if vq:
                    r["variants_estimate"] = {"value": int(ve["figure"].replace(",", "")), "quote": vq["text"], "where": vq["where"]}
        elif p:
            print(f"   [!] {tid}: the pick's quote or figure isn't in the paper's text; left out", file=sys.stderr)
        out[tid] = r
    return out


if __name__ == "__main__":
    if "--show" in sys.argv:
        names = {f["id"]: f["name"] for f in predict.featured(raw=True)}
        for k, v in load().items():
            print(f"{names.get(k, k):28} {v.get('kind') or '-':9} {v.get('value') if v.get('kind') else '':>7}  open={v.get('open')}  PMID {v.get('pmid')}")
    else:
        sweep()
