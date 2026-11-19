"""Studies for a finding, filtered by rules: the signal of the research, not its noise.

    evidence.studies("hypothyroidism", focus="genetic risk")  ->  [{pmid, title, year, type, cited, sentences}]

One Europe PMC search per topic (cached), syntheses and trials first. From each abstract only the sentences that state
an outcome and an effect are kept: a number tied to a risk, level or response, or a conclusion. Sentences about how
common something is, about methods, or about what was searched are dropped. Each kept sentence is quoted as written.

Queries are built from public names only (a condition, a drug, a gene, a mechanism), and only for what the question
itself named: never for a list that depends on the person's genotypes (cluster_analysis/README.md, privacy rule).
"""
import html
import json
import math
import re
import time

from cluster_analysis import sources

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
TYPE_WEIGHT = {"meta-analysis": 3.0, "systematic review": 2.6, "randomized controlled trial": 2.6, "clinical trial": 2.0,
               "practice guideline": 2.6, "guideline": 2.4, "review": 1.4, "comparative study": 1.2, "journal article": 1.0}
EFFECT = re.compile(r"\b(\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?-?fold|odds ratio|hazard ratio|relative risk|\bOR\b|\bHR\b|\bRR\b|"
                    r"heritabilit\w*|increas\w*|decreas\w*|reduc\w*|lower\w*|higher|improv\w*|attenuat\w*|protect\w*|"
                    r"associated with|predict\w*|explain\w*|respon\w*)", re.I)
CONCLUSION = re.compile(r"^(in conclusion|conclusions?|these (results|findings|data)|our (results|findings)|overall|"
                        r"taken together|this (study|meta-analysis|review) (shows|suggests|indicates|found|demonstrates))", re.I)
NOISE = re.compile(r"^(background|methods?|design|setting|participants|eligible)\b|\b(we searched|were searched|databases?|pubmed|embase|were included|inclusion criteria|prisma|"
                   r"was performed|were recruited|aim(ed)? (of|to)|objective|this study (aims|aimed)|prevalence|"
                   r"allele frequenc\w*|genotype frequenc\w*|hardy|minor allele|were genotyped|registered|funding)\b", re.I)


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text or "") if 40 <= len(s.strip()) <= 420]


def _clean(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def search(query, size=25, read=6, boost=(), weights=None):
    """Europe PMC papers for a query: a fast search of titles and types (resultType lite), ranked by study type,
    citations and title, then the abstracts of the best few in one request (resultType core, slow when broad). Cached."""
    key = json.dumps({"q": query, "size": size, "read": read, "boost": list(boost), "w": weights}, sort_keys=True)
    tw = weights or TYPE_WEIGHT

    def fetch():
        lite = sources._request("GET", EPMC, params={"query": query, "format": "json", "pageSize": size, "resultType": "lite"}, timeout=60)
        hits = [r for r in (lite or {}).get("resultList", {}).get("result", []) if r.get("pmid")]
        def rank(r):
            types = (r.get("pubType") or "").lower()
            w = max([v for k, v in tw.items() if k in types] or [1.0])
            title = (r.get("title") or "").lower()
            return w + math.log10(1 + int(r.get("citedByCount") or 0)) + (3.0 if any(b.lower() in title for b in boost) else 0)
        # Europe PMC's own relevance order counts too: the first hits are the closest to the query
        pos = {r["pmid"]: i for i, r in enumerate(hits)}
        best = sorted(hits, key=lambda r: rank(r) + 2.0 * (1 - pos[r["pmid"]] / max(1, len(hits))), reverse=True)[:read]
        if not best:
            return []
        q = "(" + " OR ".join(f"EXT_ID:{r['pmid']}" for r in best) + ") AND SRC:MED"
        core = sources._request("GET", EPMC, params={"query": q, "format": "json", "pageSize": len(best), "resultType": "core"}, timeout=60)
        out = []
        for r in (core or {}).get("resultList", {}).get("result", []):
            if not r.get("pmid"):
                continue
            out.append({"pmid": r["pmid"], "title": _clean(r.get("title")), "year": r.get("pubYear"),
                        "journal": (r.get("journalInfo") or {}).get("journal", {}).get("medlineAbbreviation"),
                        "cited": int(r.get("citedByCount") or 0),
                        "types": [t.lower() for t in ((r.get("pubTypeList") or {}).get("pubType") or [])],
                        "abstract": _clean(r.get("abstractText"))})
        return out
    return sources._cached("agent_evidence2", key, fetch)


def pick(papers, terms, limit=3, per_paper=2, topic=(), focus=()):
    """The papers and sentences that carry the signal: [{pmid, title, year, type, cited, sentences, score}]."""
    want = [t.lower() for t in terms if t]
    out = []
    topic = [t.lower() for t in topic if t]
    for p in papers:
        text = (p["title"] + " " + p["abstract"]).lower()
        # Off topic: a paper that doesn't name every word of the topic (a lung paper for basal cell carcinoma)
        if topic and not all(t in text for t in topic):
            continue
        # ... or one that touches none of what the question is after (prevention, screening, the trial asked about)
        if focus and not any(f in text for f in focus):
            continue
        kind = next((t for t in TYPE_WEIGHT if t in p["types"]), "journal article")
        sents = []
        ss = _sentences(p["abstract"])
        for i, s in enumerate(ss):
            if NOISE.search(s):
                continue
            eff = len(EFFECT.findall(s))
            concl = bool(CONCLUSION.search(s)) or i >= len(ss) - 2
            on = sum(1 for t in want if t in s.lower())
            if eff == 0 and not concl:
                continue
            sents.append((eff + 2 * concl + 1.5 * on, s))
        if not sents:
            continue
        sents.sort(key=lambda x: -x[0])
        top = [s for _, s in sents[:per_paper]]
        on_title = sum(1 for t in want if t in p["title"].lower())
        score = TYPE_WEIGHT[kind] + math.log10(1 + p["cited"]) + 0.8 * on_title + 0.3 * sents[0][0]
        out.append({"pmid": p["pmid"], "title": p["title"], "year": p["year"], "journal": p["journal"], "type": kind,
                    "cited": p["cited"], "sentences": top, "score": round(score, 2),
                    "url": f"https://europepmc.org/article/MED/{p['pmid']}"})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def studies(topic, focus=None, limit=3):
    """The strongest studies on a topic, syntheses first: a search restricted to meta-analyses, reviews and trials,
    widened to all papers when that finds too few."""
    core = f'"{topic}"' if " " in topic else topic
    extra = f" AND ({focus})" if focus else ""
    syn = ' AND (PUB_TYPE:"meta-analysis" OR PUB_TYPE:"systematic review" OR PUB_TYPE:"randomized controlled trial" OR PUB_TYPE:"review")'
    papers = search(core + extra + syn)
    if len(papers) < 4:
        papers += [p for p in search(core + extra) if p["pmid"] not in {x["pmid"] for x in papers}]
    terms = re.findall(r"[a-z0-9]{4,}", (topic + " " + (focus or "")).lower().replace(" or ", " ").replace(" and ", " "))
    fwords = [w.strip('"').lower() for w in re.split(r"\s+OR\s+", focus or "") if w.strip()]
    return pick(papers, terms, limit, topic=re.findall(r"[a-z0-9]{3,}", topic.lower()), focus=[w[:7] for w in fwords])
