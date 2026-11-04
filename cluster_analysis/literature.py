# cluster_analysis/literature.py
"""
Research papers per library SNP, with quoted sentences that put a number on its effect.

    python -m cluster_analysis.literature        # → cluster_analysis/literature.json

For each rsID in the library:
  papers   UniProt's experimental references for the protein change (ECO:0000269), then the most cited
           Europe PMC papers that name the SNP (rsID or protein change) with the gene and a function word.
  quotes   Sentences from those abstracts with a number tied to activity, expression or level
           ("homozygotes had approximately 60% of control activity"). They are quoted as written and
           linked to their paper; association statistics (odds ratios, p-values, risk) are left out.

Only public identifiers (rsIDs, genes, protein changes) are sent, for the whole library.
"""
import html
import json
import os
import re

from cluster_analysis import sources
from cluster_analysis.function_evidence import uniprot_variants
from cluster_analysis.gene_trace import uniprot_entry

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EVIDENCE_PATH = os.path.join(os.path.dirname(__file__), "function_evidence.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "literature.json")
AA1 = {"Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
       "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P", "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
       "Ter": "*"}
NUMBER = re.compile(r"\d+(?:\.\d+)?\s?(?:%|-fold|\s?fold|-times)", re.I)
MEASURE = re.compile(r"activit|express|\blevels?\b|stabil|turnover|vmax|\bkm\b|transport|clearance|abundance|half-life", re.I)
# Association statistics never describe the molecular effect; population words only count against a sentence
# that has no clear activity wording
STATS = re.compile(r"\bCI\b|odds|\bOR\s?[=:]|hazard|\bHR\b|mm ?Hg|explained|variance|\brisk\b", re.I)
POPULATION = re.compile(r"prevalen|frequen|population|participants|subjects|\bcases\b|controls\b|cohort|patients|variation in", re.I)
# Wording that ties a number to the variant's own activity, expression or level
_CHANGE = r"(?:lower\w*|higher|reduc\w*|decreas\w*|increas\w*|less|more|greater|residual|remaining)"
_THING = r"(?:activit\w*|express\w*|levels?|concentrations?|abundance|stabilit\w*|turnover|clearance|transport\w*)"
EFFECT = re.compile(rf"(?:%|fold)\s+(?:of\s+(?:the\s+)?(?:control|wild[- ]?type|normal|reference|the common)|"
                    rf"{_CHANGE}\s+(?:in\s+)?(?:\w+\s+){{0,2}}{_THING})|"
                    rf"{_CHANGE}\s+(?:\w+\s+){{0,2}}{_THING}\s+(?:\w+\s+){{0,3}}(?:by|to|of)\s+(?:approximately\s+|about\s+|~|∼)?\d|"
                    rf"{_THING}\s+(?:\w+\s+){{0,3}}(?:by|to)\s+(?:approximately\s+|about\s+|~|∼)?\d+(?:\.\d+)?\s?(?:%|-fold)|"
                    rf"{_THING}[^.;]{{0,30}}\d+(?:\.\d+)?\s?%\s+of\s+(?:the\s+)?(?:control|wild[- ]?type|normal)", re.I)
# The sentence has to be about a variant, not only mention the gene next to another cause
OWN_VARIANT = re.compile(r"allele|variant|mutant|mutation|homozyg|heterozyg|polymorphism", re.I)
OTHER_ID = re.compile(r"\brs\d+\b|\b[A-Z][A-Z0-9]{1,6}\*\d+[A-Z]?\b|\b[A-Z]\d{2,4}[A-Z]\b|\b[A-Z][a-z]{2}\d{1,4}[A-Z][a-z]{2}\b|"
                      r"\b[ACGT]-?\d{2,5}[ACGT]\b")
LEGACY = re.compile(r"(?<![\w*])(?:[ACGT]-?\d{2,5}[ACGT]|-\d{2,4}[ACGT]>[ACGT]|[A-Z][a-z]{2}\d{1,4}[A-Z][a-z]{2}|"
                    r"[A-Z][A-Z0-9]{2,6}\*\d+[A-Z]?)(?!\w)")
SKIP_TITLES = re.compile(r"cDNA|ORFeome|full-length|genome annotation|sequence of the human|sequencing project|"
                         r"mammalian gene collection|DNA sequence and analysis of human chromosome", re.I)
MAX_PAPERS, MAX_QUOTES = 6, 3


def _names(rsid, protein_change):
    """Ways papers name the SNP: rsID, Val158Met and V158M."""
    names = [rsid]
    m = re.match(r"p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})$", protein_change or "")
    if m:
        names.append(f"{m[1]}{m[2]}{m[3]}")
        if m[1] in AA1 and m[3] in AA1:
            names.append(f"{AA1[m[1]]}{m[2]}{AA1[m[3]]}")
    return names


def _paper(x, source):
    j = (x.get("journalInfo") or {}).get("journal") or {}
    return {"pmid": x.get("pmid"), "title": re.sub("<[^>]+>", "", html.unescape(x.get("title") or "")).rstrip("."),
            "year": x.get("pubYear"), "journal": j.get("isoabbreviation") or j.get("title"),
            "cited": x.get("citedByCount", 0), "source": source}


def search(query, size=100, sort="CITED desc"):
    def fetch():
        params = {"query": query, "resultType": "core", "format": "json", "pageSize": size}
        if sort:  # no sort means Europe PMC's relevance ranking
            params["sort"] = sort
        r = sources._request("GET", EPMC, params=params, timeout=120) or {}
        return [{k: x.get(k) for k in ("pmid", "title", "pubYear", "journalInfo", "citedByCount", "abstractText")}
                for x in (r.get("resultList") or {}).get("result", []) if x.get("pmid")]
    return sources._cached("epmc", query + "|" + (sort or "relevance") + "|" + str(size), fetch)


def aliases(rsid, hits, min_count=2):
    """Older names papers write right next to the rsID, as in "C677T (rs1801133)" or "rs671 (ALDH2*2)"."""
    gap = r"[\s(),/:;=-]{0,6}(?:dbSNP(?: ID)?[\s:]*)?"
    near = re.compile(rf"({LEGACY.pattern}){gap}{re.escape(rsid)}(?!\d)|{re.escape(rsid)}(?!\d){gap}({LEGACY.pattern})")
    seen = {}
    for x in hits:
        text = re.sub(r"<[^>]+>", " ", (x.get("title") or "") + " " + (x.get("abstractText") or ""))
        for m in near.finditer(text):
            name = m.group(1) or m.group(2)
            seen[name] = seen.get(name, 0) + 1
    return [n for n, c in sorted(seen.items(), key=lambda kv: -kv[1]) if c >= min_count][:2]


def quotes_from(abstract, names, gene=None):
    """(score, sentence) for sentences that put a number on the variant's effect."""
    text = re.sub(r"<[^>]+>", " ", html.unescape(abstract or ""))
    sentences = re.split(r"(?<=[A-Za-z0-9\)\]%])\.\s+(?=[A-Z])", text)
    variant = re.compile(r"allele|variant|carrier|homozyg|heterozyg|polymorphism|" +
                         "|".join(re.escape(n) for n in names + ([gene] if gene else [])), re.I)
    named = re.compile("|".join(re.escape(n) for n in names), re.I)
    own = {n.lower() for n in names}
    out = []
    for s in sentences:
        if len(s) > 400 or not (NUMBER.search(s) and MEASURE.search(s) and variant.search(s)) or STATS.search(s):
            continue
        if not EFFECT.search(s) or not (named.search(s) or OWN_VARIANT.search(s)):
            continue
        # A sentence that names other variants but not this one is about those variants
        others = {t for t in OTHER_ID.findall(s) if t.lower() not in own}
        if others and not named.search(s):
            continue
        score = 2 * bool(named.search(s)) + bool(re.search(r"activit", s, re.I)) - bool(POPULATION.search(s))
        if True:
            out.append((score, re.sub(r"\s+", " ", s).strip().rstrip(".") + "."))
    return out


def uniprot_pmids(rsid, gene):
    entry = uniprot_entry(gene)
    if not entry:
        return []
    out = []
    for f in uniprot_variants(entry["primaryAccession"]).get("features", []):
        if any(x.get("id") == rsid for x in f.get("xrefs", [])):
            out += [e["source"]["id"] for e in f.get("evidences", [])
                    if e.get("code") == "ECO:0000269" and (e.get("source") or {}).get("name") == "pubmed"]
    return list(dict.fromkeys(out))


def collect(rsid, gene, protein_change):
    names = _names(rsid, protein_change)
    named = " OR ".join(f'"{n}"' for n in names)
    hits = search(f"({named}) AND {gene} AND (activity OR expression OR function OR level)") if gene else search(f'"{rsid}"')
    names += [a for a in aliases(rsid, search(f'"{rsid}"', sort=None) + hits, min_count=2) if a not in names]
    named = " OR ".join(f'"{n}"' for n in names)
    # Relevance-sorted search aimed at measurements of the variant's own activity
    measured = search(f'({named}) AND {gene} AND ("enzyme activity" OR "residual activity" OR "specific activity" OR '
                      f'"catalytic activity" OR "wild-type" OR "wild type" OR "thermolabile" OR "kinetic" OR "in vitro")',
                      sort=None) if gene else []

    exp = uniprot_pmids(rsid, gene) if gene else []
    papers, meta = [], {}
    if exp:
        meta = {x["pmid"]: x for x in search("EXT_ID:(" + " OR ".join(exp[:20]) + ") AND SRC:MED", size=25)}
        papers += [_paper(meta[p], "UniProt experimental") for p in exp if p in meta and not SKIP_TITLES.search(meta[p]["title"] or "")]

    quotes = []
    # UniProt's experimental papers are where measurements are most often reported
    for x in {x["pmid"]: x for x in list(meta.values()) + hits + measured}.values():
        for score, text in quotes_from(x.get("abstractText"), names, gene):
            quotes.append({**_paper(x, "Europe PMC"), "text": text, "score": score})
    by_paper = {}
    for q in sorted(quotes, key=lambda q: (-q["score"], -(q["cited"] or 0))):
        by_paper.setdefault(q["pmid"], q)

    # Reading list: experimental references first, then the most cited papers whose title names the gene or the variant
    in_title = re.compile("|".join(re.escape(n) for n in names + ([gene] if gene else [])), re.I)
    seen = {p["pmid"] for p in papers}
    pool = sorted({x["pmid"]: x for x in hits + measured}.values(), key=lambda x: -(x.get("citedByCount") or 0))
    papers += [_paper(x, "Europe PMC") for x in pool if x["pmid"] not in seen and in_title.search(x.get("title") or "")
               and not SKIP_TITLES.search(x.get("title") or "")][:max(2, MAX_PAPERS - len(papers))]
    return {"names": names, "hits": len(hits), "papers": papers[:MAX_PAPERS + 2],
            "quotes": [{k: v for k, v in q.items() if k != "score"} for q in list(by_paper.values())[:MAX_QUOTES]]}


if __name__ == "__main__":
    evidence = json.load(open(EVIDENCE_PATH, encoding="utf-8"))
    out = {}
    for i, e in enumerate(evidence, 1):
        gene = e["genes"][0] if e.get("genes") else None
        try:
            out[e["rsid"]] = collect(e["rsid"], gene, e.get("protein_change"))
        except Exception as ex:  # one SNP's failure should not lose the others
            out[e["rsid"]] = {"error": f"{type(ex).__name__}: {str(ex)[:200]}", "papers": [], "quotes": []}
        if i % 25 == 0:
            print(f"   {i}/{len(evidence)}", flush=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    n_q = sum(1 for v in out.values() if v.get("quotes"))
    n_p = sum(1 for v in out.values() if v.get("papers"))
    print(f"✅ {len(out)} SNPs: {n_p} with papers, {n_q} with quantified quotes → {OUT_PATH}")
