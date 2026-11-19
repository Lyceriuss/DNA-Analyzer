"""The agent's tools: public research facts, looked up by theme, gene, variant, trait or paper.

Nothing here reads a person's file or results. Every tool takes only public identifiers (a theme, a gene symbol, an
rsID, a trait name, a search phrase) and answers from public sources:
  themes        the theme graphs of the Clusters tab (themes/theme_graph_*.json: Gene Ontology, Open Targets)
  GWAS Catalog  associations by gene, variant and trait (the local index, agent/index.py)
  ClinVar       what a variant is known to cause (the local index)
  1000 Genomes  the variant's alleles and European frequency (the local index)
  UniProt       what the gene's protein does (REST, cached)
  ClinPGx       genotype-level drug and trait annotations (data/reference)
  Europe PMC    paper search, abstracts and open-access full text (REST, cached)

Each call also writes into a Ledger what it returned (the papers, studies, variants and texts), so the answer can be
checked against it (answer.validate): the model may cite only what a tool gave it and quote only text it was shown.
tests/test_agent.py checks that no tool opens anything under data/input or data/output.
"""
import glob
import html
import json
import os
import re
import time

from cluster_analysis import sources
from cluster_analysis.agent import index

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
MAX_CHARS = 24_000  # one tool result, so a long list can't flood the model's context


class Ledger:
    """What the tools have shown the model in one run: the sources it may cite, the texts it may quote, the variants
    it looked up (with their alleles, which the local fill needs)."""

    def __init__(self):
        self.refs = {}       # ref id -> {"label", "url"}
        self.texts = {}      # ref id -> [text the model was shown]
        self.variants = {}   # rsid -> {"chrom", "pos", "ref", "alt", "eur_af", "gwas_alleles"}
        self.genes = set()

    def ref(self, rid, label, url):
        self.refs.setdefault(rid, {"label": label, "url": url})
        return rid

    def text(self, rid, text):
        if text:
            self.texts.setdefault(rid, []).append(text)

    def to_json(self):
        return {"refs": self.refs, "texts": self.texts, "variants": self.variants, "genes": sorted(self.genes)}

    @classmethod
    def from_json(cls, d):
        led = cls()
        led.refs, led.texts, led.variants, led.genes = d["refs"], d["texts"], d["variants"], set(d["genes"])
        return led


def pmid_ref(led, pmid, title=None, year=None, journal=None):
    title = html.unescape(title) if title else title
    label = f"PMID {pmid}" + (f": {title}" if title else "") + (f" ({journal}, {year})" if journal and year else "")
    return led.ref(f"PMID:{pmid}", label, f"https://europepmc.org/article/MED/{pmid}")


def study_ref(led, row):
    """The study's ref id; its numbers go into the ledger so a figure taken from them can be checked."""
    rid = f"GWAS:{row['study']}"
    led.text(rid, f"{row['rsid']} effect allele {row['allele']} {row['trait']} ({row['reported']}): OR or beta {row['size']} "
                  f"{row['ci'] or ''}, p {row['p']}, allele frequency {row['raf']}, {row['sample']}")
    return led.ref(f"GWAS:{row['study']}", f"GWAS Catalog {row['study']}: {row['author']} {row['year']}, {row['reported']}",
                   f"https://www.ebi.ac.uk/gwas/studies/{row['study']}")


def clip(obj):
    """A tool result as JSON text, cut to MAX_CHARS with a note (lists are shortened first)."""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    if len(text) <= MAX_CHARS:
        return text
    return text[:MAX_CHARS] + ' ... [cut: the result was longer; ask for less, e.g. a lower limit]'


# --- Themes ------------------------------------------------------------------------------------------------------

_THEMES = {}


def _theme_graphs():
    if not _THEMES:
        for path in sorted(glob.glob(os.path.join(PKG, "themes", "theme_graph_*.json"))):
            with open(path, encoding="utf-8") as f:
                g = json.load(f)
            _THEMES[g["theme"]] = g
    return _THEMES


def _theme_id(theme):
    """A theme by id or by its shown name ("Fitness" -> muscle, "Psychology" -> mind)."""
    graphs = _theme_graphs()
    if theme in graphs:
        return theme
    t = (theme or "").strip().lower()
    hits = [k for k, g in graphs.items() if t in (k.lower(), g["name"].lower())]
    return hits[0] if len(hits) == 1 else theme


def themes(led, theme=None):
    """The themes, or one theme's mechanisms and traits."""
    graphs = _theme_graphs()
    theme = _theme_id(theme) if theme else theme
    if not theme:
        return [{"theme": t, "name": g["name"], "sex": g.get("sex"), "about": g.get("about"),
                 "mechanisms": len(g.get("mechanisms") or []), "traits": len(g.get("diseases") or {}), "genes": len(g["genes"])}
                for t, g in graphs.items()]
    g = graphs.get(theme)
    if not g:
        return {"error": f"No theme {theme!r}; the theme ids are {sorted(graphs)} (Fitness is muscle, Psychology is mind)."}
    count = {}
    for gene in g["genes"].values():
        for m in gene.get("mechanisms") or {}:
            count[m] = count.get(m, 0) + 1
    led.ref(f"Theme:{theme}", f"Explorer theme {g['name']} (Gene Ontology, Open Targets)", None)
    return {"theme": theme, "name": g["name"], "about": g.get("about"), "rule": g.get("rule"),
            "phases": [{"id": o["id"], "phase": o.get("phase"), "name": o["name"], "about": o.get("about")} for o in g.get("organs") or []],
            "mechanisms": [{"id": m["id"], "name": m["name"], "about": m.get("about"), "phase": m.get("organ"),
                            "genes": count.get(m["id"], 0)} for m in g.get("mechanisms") or []],
            "traits": sorted(set((g.get("diseases") or {}).values()))}


def theme_genes(led, theme, mechanism=None, trait=None, limit=30):
    """Genes of a theme, in one mechanism or tied to one trait, strongest evidence first."""
    theme = _theme_id(theme)
    g = _theme_graphs().get(theme)
    if not g:
        return {"error": f"No theme {theme!r}; the theme ids are {sorted(_theme_graphs())}."}
    rows = []
    for sym, x in g["genes"].items():
        if re.fullmatch(r"[A-Z]\d[A-Z0-9]{3}\d(?:[A-Z0-9]{4})?", sym):
            continue  # an unnamed UniProt accession
        mech = (x.get("mechanisms") or {}).get(mechanism) if mechanism else None
        dis = (x.get("diseases") or {}).get(trait) if trait else None
        if mechanism and not mech or trait and not dis:
            continue
        rows.append({"gene": sym,
                     "mechanisms": {k: {"terms": v.get("terms", [])[:3], "evidence": v.get("evidence")} for k, v in (x.get("mechanisms") or {}).items()},
                     "traits": {k: {"score": v.get("score"), "genetic": v.get("genetic")} for k, v in (x.get("diseases") or {}).items()},
                     "best_score": x.get("best_score") or 0})
    exp = {"human experiment": 3, "curated": 2, "from orthologs": 1}
    rows.sort(key=lambda r: (-(r["traits"].get(trait, {}).get("genetic") or 0) if trait else 0,
                             -max([exp.get(v["evidence"], 0) for v in r["mechanisms"].values()] or [0]),
                             -r["best_score"], r["gene"]))
    led.ref(f"Theme:{theme}", f"Explorer theme {g['name']} (Gene Ontology, Open Targets)", None)
    for r in rows[:limit]:
        led.genes.add(r["gene"])
    return {"theme": theme, "mechanism": mechanism, "trait": trait, "total": len(rows), "genes": rows[:int(limit)]}


# --- Genes and variants -------------------------------------------------------------------------------------------

def _uniprot(gene):
    from cluster_analysis.lifecycle.gene_trace import uniprot_text
    try:
        return uniprot_text(gene)
    except Exception as e:  # UniProt unreachable: say so rather than fail the run
        return {"function": None, "error": f"UniProt unreachable ({type(e).__name__})"}


def gene(led, symbol, limit=15):
    """A gene: what its protein does, the themes it sits in, its strongest GWAS variants and traits, its ClinVar
    records."""
    symbol = symbol.strip().upper() if symbol.isascii() else symbol.strip()
    up = _uniprot(symbol)
    if up.get("function"):
        led.ref(f"UniProt:{symbol}", f"UniProt: {symbol}", f"https://www.uniprot.org/uniprotkb?query=gene_exact:{symbol}+AND+organism_id:9606+AND+reviewed:true")
        led.text(f"UniProt:{symbol}", up["function"])
    in_themes = []
    for t, g in _theme_graphs().items():
        x = g["genes"].get(symbol)
        if x:
            in_themes.append({"theme": t, "mechanisms": sorted((x.get("mechanisms") or {})), "traits": sorted((x.get("diseases") or {}))})
    rows = index.query("SELECT g.* FROM gwas g JOIN genes n ON n.rsid = g.rsid WHERE n.gene = ? ORDER BY g.p", symbol)
    traits = {}
    for r in rows:
        t = traits.setdefault(r["trait"], {"trait": r["trait"], "variants": set(), "best_p": r["p"], "studies": set()})
        t["variants"].add(r["rsid"])
        t["studies"].add(r["study"])
    top_traits = sorted(traits.values(), key=lambda t: (-len(t["studies"]), t["best_p"]))[:25]
    seen, top = set(), []
    for r in rows:
        if r["rsid"] in seen:
            continue
        seen.add(r["rsid"])
        top.append({"rsid": r["rsid"], "trait": r["trait"], "p": r["p"], "context": r["context"]})
        if len(top) >= limit:
            break
    cv = index.query("SELECT rsid, significance, condition, stars FROM clinvar WHERE gene = ? AND stars >= 1 ORDER BY stars DESC LIMIT 15", symbol)
    led.genes.add(symbol)
    return {"gene": symbol, "protein": {k: (v[:1500] if isinstance(v, str) else v) for k, v in up.items()},
            "themes": in_themes,
            "gwas_traits": [{"trait": t["trait"], "variants": len(t["variants"]), "studies": len(t["studies"]), "best_p": t["best_p"]} for t in top_traits],
            "gwas_variants": top, "gwas_variant_total": len(seen),
            "clinvar": cv, "next": "variant(rsid) for a variant's alleles, frequencies, effect sizes and papers"}


def _clinpgx(rsid):
    from cluster_analysis.medicines.medicines import load_annotations
    global _PGX
    try:
        _PGX
    except NameError:
        rows, texts = load_annotations(("1A", "1B", "2A", "2B", "3"))
        _PGX = {}
        for r in rows:
            _PGX.setdefault(r["Variant/Haplotypes"], []).append((r, texts.get(r["Clinical Annotation ID"], [])))
    return _PGX.get(rsid, [])


def variant(led, rsid, limit=25):
    """A variant: alleles and European frequency, every genome-wide association with its effect allele and size,
    ClinVar and ClinPGx records, function evidence."""
    rsid = rsid.strip().lower()
    if not re.fullmatch(r"rs\d+", rsid):
        return {"error": "Give an rsID such as rs1815739."}
    site = (index.query("SELECT * FROM sites WHERE rsid = ?", rsid) or [None])[0]
    rows = index.query("SELECT * FROM gwas WHERE rsid = ? ORDER BY p", rsid)
    assoc, seen = [], set()
    for r in rows:
        key = (r["trait"], r["study"])
        if key in seen:
            continue
        seen.add(key)
        ci = (r["ci"] or "").lower()
        assoc.append({"trait": r["trait"], "reported": r["reported"], "effect_allele": r["allele"], "p": r["p"],
                      "or_or_beta": r["size"], "ci": r["ci"] or None,
                      "direction": "increase" if "increase" in ci else "decrease" if "decrease" in ci else None,
                      "allele_freq_in_study": r["raf"], "sample": (r["sample"] or "")[:160], "study": r["study"],
                      "ref": study_ref(led, r), "paper": pmid_ref(led, r["pmid"], None, r["year"], r["journal"]),
                      "author": f"{r['author']} {r['year']}"})
        if len(assoc) >= limit:
            break
    genes = sorted({x["gene"] for x in index.query("SELECT gene FROM genes WHERE rsid = ?", rsid)})
    cv = index.query("SELECT gene, ref, alt, significance, condition, stars, variation FROM clinvar WHERE rsid = ?", rsid)
    for c in cv:
        c["ref_id"] = led.ref(f"ClinVar:{c['variation']}", f"ClinVar {c['variation']}: {c['significance']}, {c['condition']}",
                              f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{c['variation']}/")
        led.text(c["ref_id"], f"{c['significance']}: {c['condition']}")
    pgx = []
    for r, texts in _clinpgx(rsid):
        rid = led.ref(f"ClinPGx:{r['Clinical Annotation ID']}", f"ClinPGx {r['Clinical Annotation ID']} ({r['Drug(s)'] or r.get('Phenotype(s)')}, level {r['Level of Evidence']})", r["URL"])
        gts = [{"genotype": t.get("Genotype/Allele"), "text": t.get("Annotation Text")} for t in texts]
        for t in gts:
            led.text(rid, t["text"])
        pgx.append({"ref": rid, "level": r["Level of Evidence"], "drugs": r["Drug(s)"], "phenotype": r.get("Phenotype(s)"),
                    "genotypes": gts})
    fe = next((x for x in _function_evidence() if x["rsid"] == rsid), None)
    lit = _literature().get(rsid) or {}
    papers = [{"ref": pmid_ref(led, p["pmid"], p.get("title"), p.get("year"), p.get("journal")), "title": p.get("title"),
               "year": p.get("year"), "cited": p.get("cited")} for p in (lit.get("papers") or [])[:8]]
    quotes = []
    for q in lit.get("quotes") or []:
        rid = pmid_ref(led, q["pmid"]) if q.get("pmid") else None
        if rid:
            led.text(rid, q.get("text"))
            quotes.append({"ref": rid, "text": q.get("text")})
    if site or rows:
        led.variants[rsid] = {**(site or {}), "gwas_alleles": sorted({r["allele"] for r in rows if r["allele"]}), "genes": genes}
    if not site and not rows and not cv:
        return {"rsid": rsid, "error": "Not in the local index (GWAS Catalog, ClinVar, 1000 Genomes): no public facts for it here."}
    return {"rsid": rsid, "genes": genes,
            "site": {"chrom": site["chrom"], "pos_grch38": site["pos"], "ref": site["ref"], "alt": site["alt"],
                     "eur_alt_freq": site["eur_af"]} if site else None,
            "note": None if site else "No 1000 Genomes site: alleles unknown, so it cannot go into the answer as a variant.",
            "consequence": next((r["context"] for r in rows if r["context"]), None),
            "gwas": assoc, "gwas_total": len(seen), "clinvar": cv, "clinpgx": pgx,
            "function_evidence": {k: v for k, v in (fe or {}).get("sources", {}).items() if k in ("gtex", "uniprot", "mavedb")} or None,
            "papers": papers, "quotes": quotes}


_FE, _LIT = None, None


def _function_evidence():
    global _FE
    if _FE is None:
        with open(os.path.join(PKG, "evidence", "function_evidence.json"), encoding="utf-8") as f:
            _FE = json.load(f)
    return _FE


def _literature():
    global _LIT
    if _LIT is None:
        with open(os.path.join(PKG, "evidence", "literature.json"), encoding="utf-8") as f:
            _LIT = json.load(f)
    return _LIT


def trait_variants(led, trait, limit=25):
    """The GWAS Catalog's traits matching a phrase, and their strongest variants."""
    like = f"%{trait.strip()}%"
    traits = index.query("SELECT trait, COUNT(DISTINCT rsid) AS variants, COUNT(DISTINCT study) AS studies FROM gwas "
                         "WHERE trait LIKE ? OR reported LIKE ? GROUP BY trait ORDER BY studies DESC LIMIT 15", like, like)
    rows = index.query("SELECT * FROM gwas WHERE trait LIKE ? OR reported LIKE ? ORDER BY p LIMIT 400", like, like)
    out, seen = [], set()
    for r in rows:
        if r["rsid"] in seen:
            continue
        seen.add(r["rsid"])
        out.append({"rsid": r["rsid"], "gene": r["mapped"], "trait": r["trait"], "reported": r["reported"],
                    "effect_allele": r["allele"], "p": r["p"], "or_or_beta": r["size"], "ci": r["ci"] or None,
                    "sample": (r["sample"] or "")[:120], "ref": study_ref(led, r), "paper": pmid_ref(led, r["pmid"])})
        if len(out) >= limit:
            break
    return {"query": trait, "traits": traits, "variants": out}


# --- Papers -------------------------------------------------------------------------------------------------------

def _epmc(params, key):
    def fetch():
        time.sleep(0.3)  # Europe PMC asks for gentle use
        return sources._request("GET", f"{EPMC}/search", params={**params, "format": "json"}, timeout=60)
    return sources._cached("agent_epmc", key, fetch)


def search_papers(led, query, limit=8, sort="relevance"):
    """Europe PMC search: the papers (PubMed ids, titles, years, citations, whether the full text is open)."""
    limit = max(1, min(int(limit), 25))
    params = {"query": query, "pageSize": limit, "resultType": "lite"}
    if sort == "cited":
        params["sort"] = "CITED desc"
    d = _epmc(params, json.dumps(params, sort_keys=True))
    hits = []
    for r in (d or {}).get("resultList", {}).get("result", []):
        if not r.get("pmid"):
            continue
        hits.append({"ref": pmid_ref(led, r["pmid"], r.get("title"), r.get("pubYear"), r.get("journalTitle")),
                     "title": html.unescape(r.get("title") or ""), "authors": (r.get("authorString") or "")[:120], "journal": r.get("journalTitle"),
                     "year": r.get("pubYear"), "cited": r.get("citedByCount"), "open_full_text": r.get("isOpenAccess") == "Y",
                     "types": r.get("pubType")})
    return {"query": query, "total": (d or {}).get("hitCount"), "papers": hits,
            "next": "read_paper(pmid) for the abstract; with find=[words], the full-text paragraphs that use them"}


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text) if s.strip()]


def read_paper(led, pmid, find=None):
    """A paper's abstract, and (if its full text is open) the paragraphs that use the given words."""
    pmid = re.sub(r"\D", "", str(pmid))
    d = _epmc({"query": f"EXT_ID:{pmid} AND SRC:MED", "resultType": "core"}, f"core:{pmid}")
    res = ((d or {}).get("resultList", {}).get("result") or [None])[0]
    if not res:
        return {"error": f"PMID {pmid} not found in Europe PMC."}
    rid = pmid_ref(led, pmid, res.get("title"), res.get("pubYear"), (res.get("journalInfo") or {}).get("journal", {}).get("medlineAbbreviation"))
    abstract = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", res.get("abstractText") or ""))).strip()
    led.text(rid, abstract)
    out = {"ref": rid, "title": html.unescape(res.get("title") or ""), "authors": (res.get("authorString") or "")[:200], "year": res.get("pubYear"),
           "types": (res.get("pubTypeList") or {}).get("pubType"), "cited": res.get("citedByCount"),
           "mesh": [m.get("descriptorName") for m in ((res.get("meshHeadingList") or {}).get("meshHeading") or [])][:15],
           "abstract": abstract or None}
    words = [w.lower() for w in (find or []) if w and w.strip()]
    pmcid = res.get("pmcid")
    if words and pmcid and res.get("isOpenAccess") == "Y":
        def fetch():
            time.sleep(0.3)
            import requests
            r = requests.get(f"{EPMC}/{pmcid}/fullTextXML", timeout=60)
            return r.text if r.ok else ""
        xml = sources._cached("agent_epmc_full", pmcid, lambda: {"xml": fetch()})["xml"]
        paras = []
        for p in re.findall(r"<p[ >].*?</p>", xml, re.S):
            t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p))).strip()
            t = re.sub(r"\s+([.,;:)\]])", r"\1", re.sub(r"([(\[])\s+", r"\1", t))
            if any(w in t.lower() for w in words):
                paras.append(t)
        chosen, size = [], 0
        for t in paras:
            if size + len(t) > 9000:
                break
            chosen.append(t)
            size += len(t)
            led.text(rid, t)
        out["full_text"] = {"pmcid": pmcid, "matching_paragraphs": len(paras), "paragraphs": chosen}
    elif words:
        out["full_text"] = None
        out["note"] = "The full text is not open in Europe PMC: only the abstract can be quoted."
    return out


# --- The tool list --------------------------------------------------------------------------------------------------

TOOLS = {
    "themes": (themes, "List the explorer's themes (Fitness, Cancer, Fertility, Psychology), or with theme=<id> one "
               "theme's phases, mechanisms (with gene counts) and traits. Start here to find the genes that bear on a question.",
               {"theme": {"type": "string", "description": "A theme id from the list, e.g. muscle. Leave out for the list."}}, []),
    "theme_genes": (theme_genes, "The genes of a theme in one mechanism (Gene Ontology) or tied to one trait (Open Targets "
                    "human genetics), strongest evidence first.",
                    {"theme": {"type": "string"}, "mechanism": {"type": "string", "description": "A mechanism id from themes(theme)."},
                     "trait": {"type": "string", "description": "A trait name from themes(theme), e.g. 'VO2max'."},
                     "limit": {"type": "integer", "minimum": 1, "maximum": 80}}, ["theme"]),
    "gene": (gene, "One gene: what its protein does (UniProt), the themes it is in, its strongest genome-wide significant "
             "variants and traits (GWAS Catalog) and its ClinVar records.",
             {"symbol": {"type": "string", "description": "HGNC symbol, e.g. ACTN3."},
              "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, ["symbol"]),
    "variant": (variant, "One variant: its two alleles and European frequency (1000 Genomes), every genome-wide significant "
                "association with effect allele, size and paper (GWAS Catalog), ClinVar and ClinPGx records, function "
                "evidence and papers. Every variant in the answer must have been looked up here.",
                {"rsid": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 60}}, ["rsid"]),
    "trait_variants": (trait_variants, "The GWAS Catalog traits matching a phrase (e.g. 'VO2max', 'grip strength', "
                       "'tendinopathy') with their strongest variants.",
                       {"trait": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 60}}, ["trait"]),
    "search_papers": (search_papers, "Search Europe PMC (all of PubMed plus open full texts). Use field syntax for "
                      "precision, e.g. '(ACTN3 OR rs1815739) AND (training OR exercise) AND PUB_TYPE:\"Meta-Analysis\"'. "
                      "sort=cited for the most cited.",
                      {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 25},
                       "sort": {"type": "string", "enum": ["relevance", "cited"]}}, ["query"]),
    "read_paper": (read_paper, "Read a paper by PubMed id: its abstract, and when find=[words] is given and the full text "
                   "is open, the paragraphs that use those words (results, effect sizes, methods). Quotes in the answer "
                   "must come from text read here or from a ClinPGx or ClinVar record.",
                   {"pmid": {"type": "string"}, "find": {"type": "array", "items": {"type": "string"}, "maxItems": 8}}, ["pmid"]),
}


def schemas():
    """The tools as Messages API tool definitions (eager input streaming: inputs are validated in call())."""
    return [{"name": name, "description": desc, "eager_input_streaming": True,
             "input_schema": {"type": "object", "properties": props, "required": req, "additionalProperties": False}}
            for name, (fn, desc, props, req) in TOOLS.items()]


def check_input(name, args):
    """Problems with a tool call's input against its schema, or []."""
    fn, desc, props, req = TOOLS[name]
    if not isinstance(args, dict):
        return ["the input is not an object"]
    errs = [f"missing {k}" for k in req if k not in args]
    for k, v in args.items():
        spec = props.get(k)
        if spec is None:
            errs.append(f"unknown field {k}")
        elif spec["type"] == "string" and not isinstance(v, str):
            errs.append(f"{k} must be a string")
        elif spec["type"] == "integer" and (not isinstance(v, int) or isinstance(v, bool)):
            errs.append(f"{k} must be an integer")
        elif spec["type"] == "array" and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
            errs.append(f"{k} must be a list of strings")
        elif "enum" in spec and v not in spec["enum"]:
            errs.append(f"{k} must be one of {spec['enum']}")
    return errs


def call(led, name, args):
    """Runs a tool: (result text, is_error)."""
    if name not in TOOLS:
        return f"No tool {name!r}.", True
    errs = check_input(name, args)
    if errs:
        return "Invalid input: " + "; ".join(errs), True
    try:
        out = TOOLS[name][0](led, **args)
    except Exception as e:  # a source that is down or answers oddly: tell the model, keep the run going
        return f"{name} failed: {type(e).__name__}: {str(e)[:300]}", True
    return clip(out), isinstance(out, dict) and "error" in out and len(out) <= 2
