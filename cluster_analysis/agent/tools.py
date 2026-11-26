"""The tools Claude works through in an Ask conversation: one registry for the API loop and the MCP server.

Three kinds, by what goes back to the model:
  public    research facts the same for everyone (genes, variants, clusters, drugs, papers): the full result.
  personal  the person's own results (their medicines, scores, cluster genes, conditions): the result goes to the
            person's screen only; the model gets back the result's public shape (what kinds of data exist for the
            item, how many), never a genotype or a value. The model can judge whether local data covers the
            question without seeing it.
  view      a view of the explorer drawn in the answer (a cluster graph around a gene, a pathway, a medicine):
            recorded for the screen; the model gets "shown".
Plus understand (the reading and plan, shown first) and answer (the general explanation, checked against what the
public tools returned, and follow-up questions).

Every call is appended to the turn's record (session.py), which the server streams to the tab.
"""
import json
import os
import re

from cluster_analysis.agent import evidence, facts, functions, language, morsels, pair, providers, terms, traits

PUBLIC, PERSONAL, VIEW, CONTROL = "public", "personal", "view", "control"


def _s(desc, **props):
    req = [k for k, v in props.items() if not v.pop("optional", False)]
    return {"type": "object", "properties": props, "required": req, "additionalProperties": False}, desc


S = lambda d, **k: {"type": "string", "description": d, **k}
I = lambda d, **k: {"type": "integer", "description": d, **k}
A = lambda d, **k: {"type": "array", "items": {"type": "string"}, "description": d, **k}


# --- Public tools ---------------------------------------------------------------------------------------------------

def t_catalogue(ctx):
    from cluster_analysis.agent import route
    return {"catalogue": route.catalogue()}


def t_resolve(ctx, text, kind="any"):
    """Candidates in the explorer for a name as the person wrote it (typos and other languages included)."""
    out = []
    for m in terms.match(text, search=(kind in ("any", "condition")))[:12]:
        if kind == "any" or m["type"] == kind or (kind == "drug" and m["type"] == "drug_class"):
            out.append({k: m.get(k) for k in ("type", "id", "label", "theme", "level", "score")})
    return {"text": text, "candidates": out}


def t_gene(ctx, symbol):
    return facts.gene(ctx["ledger"], symbol, limit=8)


def t_variant(ctx, rsid):
    return facts.variant(ctx["ledger"], rsid, limit=10)


def t_cluster(ctx, theme, mechanism=None, trait=None, limit=15):
    if not mechanism and not trait:
        return facts.themes(ctx["ledger"], theme)
    return facts.theme_genes(ctx["ledger"], theme, mechanism, trait, limit)


def t_trait_variants(ctx, trait):
    return facts.trait_variants(ctx["ledger"], trait, limit=12)


def t_search_papers(ctx, query, limit=8):
    return facts.search_papers(ctx["ledger"], query, limit)


def t_read_paper(ctx, pmid, find=None):
    return facts.read_paper(ctx["ledger"], pmid, find)


_PGX = None


def _pgx():
    global _PGX
    if _PGX is None:
        from cluster_analysis.medicines.medicines import load_annotations
        rows, texts = load_annotations(("1A", "1B", "2A", "2B", "3", "4"))
        _PGX = (rows, texts)
    return _PGX


def _drug_name(name):
    """The explorer's name of a drug: exact names, generic and trade names (paracetamol -> acetaminophen)."""
    n = terms.norm(name)
    for it in terms.index():
        if it["type"] == "drug" and terms.norm(it["name"]) == n:
            return it["id"]
    hits = [m for m in terms.match(name, search=False) if m["type"] == "drug"]
    return hits[0]["id"] if hits else name.lower()


def t_drug(ctx, name):
    """What is known about a drug's genetics, for everyone: guidelines, and ClinPGx clinical annotations with the
    effect of each genotype (public: ClinPGx writes a text for every genotype)."""
    drug = _drug_name(name)
    rows, texts = _pgx()
    ann = []
    for r in rows:
        if drug not in [d.strip().lower() for d in r["Drug(s)"].split(";")]:
            continue
        rid = ctx["ledger"].ref(f"ClinPGx:{r['Clinical Annotation ID']}", f"ClinPGx {r['Clinical Annotation ID']}: {r['Gene']} {r['Variant/Haplotypes']}, {drug}, level {r['Level of Evidence']}", r["URL"])
        full = [{"genotype": t["Genotype/Allele"], "text": t["Annotation Text"]} for t in texts.get(r["Clinical Annotation ID"], [])]
        for t in full:
            ctx["ledger"].text(rid, t["text"])
        # The model gets each genotype's effect, shortened (the boilerplate after the first sentence dropped)
        gts = [{"genotype": t["genotype"], "text": re.split(r"(?<=\.)\s", t["text"])[0][:180]} for t in full]
        ann.append({"ref": rid, "gene": r["Gene"], "variant": r["Variant/Haplotypes"], "level": r["Level of Evidence"],
                    "category": r["Phenotype Category"], "phenotype": r.get("Phenotype(s)"), "genotypes": gts})
    ann.sort(key=lambda a: a["level"])
    cpic = []
    path = os.path.join(providers.ROOT, "data", "reference", "cpic_recommendations.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cpic = sorted({r["guideline"]["name"] for r in json.load(f) if (r.get("drug") or {}).get("name") == drug})
    return {"drug": drug, "asked_as": name, "guidelines": cpic, "annotations": ann[:10], "annotation_total": len(ann),
            "note": "Levels: 1A/1B guideline-grade, 2A/2B moderate, 3 single studies, 4 case reports."}


def t_research_genotypes(ctx, rsids, topic):
    """Studies that report results by genotype for the given variants on a topic: the sentences naming a genotype
    group with an effect (agent/morsels.py), public and the same for everyone. They are also read for the person,
    on this machine, when the answer is put together."""
    words = [w for w in re.findall(r"[a-z]{4,}", topic.lower())]
    out, found = [], []
    for rs in rsids[:10]:
        gene = (facts.index.query("SELECT gene FROM genes WHERE rsid = ? LIMIT 1", rs) or [{}])[0].get("gene") or ""
        if not gene:
            continue
        fs = morsels.for_variant(rs, gene, theme=None, dom=" OR ".join(words) or None,
                                 topic_re=re.compile("|".join(map(re.escape, words)), re.I) if words else None)
        for m in fs:
            ctx["ledger"].ref(f"PMID:{m['pmid']}", f"PMID {m['pmid']}: {m['title']}", m["url"])
            ctx["ledger"].text(f"PMID:{m['pmid']}", m["sentence"])
        found += fs
        out.append({"rsid": rs, "gene": gene, "findings": [{"pmid": m["pmid"], "sentence": m["sentence"], "groups": m["labels"]} for m in fs[:6]]})
    ctx["findings"] = ctx.get("findings", []) + found
    return {"topic": topic, "variants": out}


# --- Personal tools: the screen gets the result, the model its public shape ----------------------------------------

def _shape(cards):
    """That a personal result was shown, and of which kinds: nothing about its values, its titles (a title such as
    "TPMT: Intermediate metabolizer" is a result) or how many items stood out."""
    what = {"cancer": "the person's genetic score per cancer type with the variants behind it and the known risk factors",
            "lab": "the person's genetic baseline per lab test", "nutrient": "the person's genetic baseline per nutrient",
            "fitness": "the person's genetic score per fitness trait", "theme": "where the person's variants change genes in the cluster",
            "findings": "study sentences that name the person's own genotype group", "gene": "the person's result for the gene",
            "condition": "the person's risk-allele count for the condition", "medicines": "the person's medicine results",
            "inheritance": "what a child of the two picked profiles could inherit for the item, drawn as scales and odds",
            "trait": "where the person's genes place them among Europeans on the GWAS trait, drawn as a scale with the genes behind it",
            "function": "the person's genes called gain or loss of function, with the variant, genotype and evidence behind each call, drawn as a table"}
    has = sorted({what[c["provider"]] for c in cards if c["provider"] in what and c["level"] != "unknown"})
    return {"shown_to_person": True, "kinds": sorted({c["provider"] for c in cards}) or ["none"], "screen_has": has or ["nothing that answers it"],
            "note": "The person's own values are on their screen, not here. What exists publicly for this item comes "
                    "from the public tools (drug, gene, cluster, variant)."}


def t_my_medicine(ctx, name):
    drug = _drug_name(name)
    cards = providers.medicines(ctx["person"], ids={drug})
    mine = [r for r in providers.rows("med_drugs", ctx["person"]) if drug in r["drug"].split(";") or r["drug"] == drug]
    if mine:
        order = {"differs": 0, "not_excluded": 1, "typical": 2}
        rows_ = [{"label": f"{r['gene'] or '?'} {r['variant']} · level {r['level']}", "value": r.get("text") or r.get("effect") or "",
                  "note": f"yours {r['genotype']}", "gene": r.get("gene") or "", "variant": r["variant"], "genotype": r["genotype"],
                  "level": r["level"], "effect": r.get("effect") or "", "status": r.get("status"), "url": r.get("url"),
                  "category": r.get("category")}
                 for r in sorted(mine, key=lambda r: (r["level"], order.get(r.get("status"), 3)))[:12]]
        cards.append(providers.card("medicines", f"{drug}:annotations", f"{drug}: ClinPGx annotations for your genotypes",
                                    level="differs", value=len(mine), headline=f"{len(mine)} clinical annotations read for your genotypes.",
                                    rows=rows_, links=[{"tab": "medicines", "params": {"md_drug": drug}, "label": f"Open {drug}"}]))
    ctx["cards"] += cards
    # What kind of answer is now on the person's screen, never what it says: so the model can judge whether it covers
    # the question (the explorer's Medicines data usually does: ClinPGx writes the effect for every genotype)
    has = []
    if any(c["level"] in ("differs", "typical") and c["provider"] == "medicines" and not str(c["id"]).endswith(":annotations") for c in cards):
        has.append("dosing-guideline recommendations for the person's own gene results")
    if mine:
        has.append("ClinPGx's text for the person's own genotype at each annotated variant, with its evidence level")
    return _shape(cards) | {"drug": drug, "screen_has": has or ["nothing: no guideline or annotation for this drug matched the person's file"]}


def t_my_medicines(ctx):
    cards = providers.medicines(ctx["person"])
    ctx["cards"] += cards
    return _shape(cards)


def t_my_scores(ctx, domain, ids=None):
    fn = {"cancer": providers.cancers, "lab": providers.labs, "nutrient": providers.nutrients, "fitness": providers.fitness}[domain]
    cards = fn(ctx["person"], ids=set(ids) if ids else None)
    ctx["cards"] += cards
    return _shape(cards)


def t_my_cluster(ctx, theme, mechanism=None):
    # Several mechanisms in one call ("tendons,regeneration,hypertrophy"): one card set per mechanism
    mechs = [m.strip() for m in (mechanism or "").split(",") if m.strip()]
    if len(mechs) > 1:
        cards = []
        for m in mechs[:8]:
            cards += providers.themes(ctx["person"], theme=theme, mechanism=m, level="mechanism")
    else:
        cards = providers.themes(ctx["person"], theme=theme, mechanism=mechanism, level="mechanism" if mechanism else "theme")
    cards += providers.findings(ctx["person"], theme=theme, words=ctx.get("words", ()))
    ctx["cards"] += cards
    return _shape(cards)


def t_my_gene(ctx, symbol):
    cards = providers.gene(ctx["person"], symbol=symbol)
    ctx["cards"] += cards
    return _shape(cards)


def t_my_condition(ctx, name):
    hits = [m for m in terms.match(name) if m["type"] == "condition"][:2]
    cards = providers.condition(ctx["person"], items=hits) if hits else []
    ctx["cards"] += cards
    return _shape(cards) | {"public": {"conditions": [h["label"] for h in hits]}}


# --- Views ------------------------------------------------------------------------------------------------------------

def t_show_cluster(ctx, theme, gene=None, mechanism=None):
    ctx["views"].append({"view": "cluster", "theme": theme, "gene": gene, "mechanism": mechanism})
    return {"shown": True}


def t_show_pathway(ctx, gene):
    if gene not in ctx.get("pathways", {}):
        t_pathway(ctx, gene)
    p = ctx["pathways"][gene]
    ctx["views"].append({"view": "pathway", "gene": gene, "steps": p["steps"], "source": p["source"]})
    return {"shown": True, "steps": len(p["steps"])}


def t_show_medicine(ctx, name):
    ctx["views"].append({"view": "medicine", "drug": _drug_name(name)})
    return {"shown": True}


# --- Assets: pathways, nutrients, the latest research ------------------------------------------------------------------

def _pathway_steps(gene):
    """A gene's steps: from the explorer's Gene pathway data when it has the gene, else built live from Reactome
    (UniProt accession -> the protein's reactions -> each reaction's inputs and outputs). Public, cached."""
    rows = [r for r in providers.rows("lifecycle_steps", None) if r.get("gene") == gene]
    if not rows:
        # Any profile's rows: the steps themselves are the same for everyone
        from genome import build as gbuild
        path = os.path.join(providers.DATASETS, "lifecycle_steps.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                seen = set()
                for r in json.load(f):
                    if r.get("gene") == gene and r.get("reaction_id") not in seen:
                        seen.add(r.get("reaction_id"))
                        rows.append(r)
    # The explorer's steps when it maps the gene well; a thin mapping (ADRB2: 3 steps) gives way to Reactome live
    if len(rows) >= 6:
        rows.sort(key=lambda r: (r.get("section") or "", r.get("order") or 0))
        steps = [{"id": r.get("reaction_id"), "name": r.get("reaction"), "inputs": _names(r.get("inputs")),
                  "outputs": _names(r.get("outputs")), "section": r.get("section"), "role": r.get("role")} for r in rows[:16]]
        return steps, "explorer (Reactome)"
    from cluster_analysis.lifecycle import gene_trace as gt
    entry = gt.uniprot_entry(gene) or {}
    acc = entry.get("primaryAccession")
    if not acc:
        return [], None
    steps = []
    for rid in (gt.reactions_for_protein(acc) or [])[:14]:
        r = gt.reaction(rid) or {}
        steps.append({"id": rid, "name": r.get("name"), "inputs": list((r.get("inputs") or {}).values())[:4] if isinstance(r.get("inputs"), dict) else r.get("inputs") or [],
                      "outputs": list((r.get("outputs") or {}).values())[:4] if isinstance(r.get("outputs"), dict) else r.get("outputs") or [],
                      "section": None, "role": None})
    return steps, "Reactome (live)"


def _names(x):
    if isinstance(x, str):
        try:
            x = json.loads(x)
        except ValueError:
            return [x] if x else []
    if isinstance(x, dict):
        return [str(v) for v in x.values()][:4]
    if isinstance(x, list):
        return [str(v.get("name") if isinstance(v, dict) else v) for v in x][:4]
    return []


def t_pathway(ctx, gene):
    steps, src = _pathway_steps(gene)
    for s in steps:
        if s.get("id"):
            ctx["ledger"].ref(f"Reactome:{s['id']}", f"Reactome {s['id']}: {s['name']}", f"https://reactome.org/content/detail/{s['id']}")
    ctx.setdefault("pathways", {})[gene] = {"steps": steps, "source": src}
    return {"gene": gene, "source": src, "steps": steps, "total": len(steps)}


def _nutrient_id(name):
    n = terms.norm(name)
    for it in terms.index():
        if it["type"] == "nutrient" and (terms.norm(it["name"]) == n or it["id"] == name):
            return it["id"]
    hits = [m for m in terms.match(name, search=False) if m["type"] == "nutrient"]
    return hits[0]["id"] if hits else name


def t_nutrient(ctx, name):
    """A nutrient for everyone: its blood tests, the intake target (NNR 2023) and the uptake and conversion steps with
    the genes that act at each."""
    nid = _nutrient_id(name)
    with open(os.path.join(providers.ROOT, "cluster_analysis", "nutrition", "nutrients.json"), encoding="utf-8") as f:
        cfg = next((x for x in json.load(f)["nutrients"] if x["id"] == nid), None)
    path = os.path.join(providers.DATASETS, "nut_steps.json")
    steps = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            steps = sorted([r for r in json.load(f) if r.get("nutrient") == nid], key=lambda r: r.get("order") or 0)
    out = [{"order": s.get("order"), "name": s.get("name"), "genes": (s.get("genes") or "").split(), "where": s.get("where"),
            "step": s.get("step")} for s in steps]
    ctx.setdefault("nutrients", {})[nid] = out
    return {"nutrient": nid, "name": (cfg or {}).get("name"), "markers": [m.get("name") for m in (cfg or {}).get("markers", [])],
            "steps": out}


def t_my_nutrient(ctx, name):
    nid = _nutrient_id(name)
    cards = providers.nutrients(ctx["person"], ids={nid})
    rows_ = [r for r in providers.rows("nut_findings", ctx["person"]) if r.get("nutrient") == nid]
    if rows_:
        best = sorted(rows_, key=lambda r: ({"A+": 0, "A": 1, "B": 2, "C": 3}.get(r.get("grade"), 4), -(abs(r.get("shift") or 0))))[:10]
        cards.append(providers.card("nutrient", f"{nid}:variants", f"{nid}: your variants", level="differs", value=len(best),
                                    rows=[{"label": f"{r['gene']} {r['rsid']}", "value": f"{r['genotype']}: {r['direction']} {r.get('marker_name') or ''}".strip(),
                                           "note": r.get("grade"), "gene": r["gene"], "rsid": r["rsid"], "genotype": r["genotype"],
                                           "direction": r.get("direction"), "step_gene": r.get("step_gene"), "grade": r.get("grade")} for r in best],
                                    headline="", links=[{"tab": "nutrition", "params": {"nt_n": nid}, "label": f"Open {nid} in Nutrition"}]))
    ctx["cards"] += cards
    return _shape(cards) | {"nutrient": nid, "screen_has": ["the person's genetic baseline for the nutrient's blood level and their variants at each step"] if cards else ["nothing"]}


def t_show_nutrient(ctx, name):
    nid = _nutrient_id(name)
    if nid not in ctx.get("nutrients", {}):
        t_nutrient(ctx, nid)
    ctx["views"].append({"view": "nutrient", "nutrient": nid, "steps": ctx["nutrients"][nid]})
    return {"shown": True}


def t_recent_papers(ctx, query, since_year=2023, limit=6):
    """The newest papers on a topic (Europe PMC, newest first, from since_year), each with the sentences that carry its
    finding (evidence.pick: outcomes and effects, not methods)."""
    from cluster_analysis import sources
    import time
    q = f"({query}) AND FIRST_PDATE:[{int(since_year)}-01-01 TO 2100-12-31]"

    def fetch():
        time.sleep(0.2)
        lite = sources._request("GET", evidence.EPMC, params={"query": q, "format": "json", "pageSize": 25, "resultType": "lite",
                                                             "sort": "FIRST_PDATE_D desc"}, timeout=60)
        hits = [r for r in (lite or {}).get("resultList", {}).get("result", []) if r.get("pmid")][:max(1, min(int(limit), 15))]
        if not hits:
            return []
        core = sources._request("GET", evidence.EPMC, params={"query": "(" + " OR ".join(f"EXT_ID:{r['pmid']}" for r in hits) + ") AND SRC:MED",
                                                             "format": "json", "pageSize": len(hits), "resultType": "core"}, timeout=60)
        return [{"pmid": r["pmid"], "title": evidence._clean(r.get("title")), "year": r.get("pubYear"), "date": r.get("firstPublicationDate"),
                 "journal": (r.get("journalInfo") or {}).get("journal", {}).get("medlineAbbreviation"), "cited": int(r.get("citedByCount") or 0),
                 "types": [x.lower() for x in ((r.get("pubTypeList") or {}).get("pubType") or [])], "abstract": evidence._clean(r.get("abstractText"))}
                for r in (core or {}).get("resultList", {}).get("result", []) if r.get("pmid")]
    papers = sources._cached("agent_recent", q + f"|{limit}", fetch)
    papers.sort(key=lambda p: p.get("date") or p.get("year") or "", reverse=True)
    words = [w for w in re.findall(r"[a-z]{4,}", query.lower()) if w not in ("genetic", "genetics", "gene", "genes")]
    out = []
    for p in papers:
        picked = evidence.pick([p], words, limit=1, per_paper=2)
        rid = ctx["ledger"].ref(f"PMID:{p['pmid']}", f"PMID {p['pmid']}: {p['title']}", f"https://europepmc.org/article/MED/{p['pmid']}")
        ctx["ledger"].text(rid, p["abstract"])
        kind = next((t for t in evidence.TYPE_WEIGHT if t in p["types"]), "journal article")
        out.append({"ref": rid, "pmid": p["pmid"], "title": p["title"], "date": p.get("date"), "journal": p.get("journal"), "type": kind,
                    "cited": p["cited"], "key": (picked[0]["sentences"] if picked else [])[:2]})
    ctx.setdefault("papers", {}).update({p["pmid"]: p for p in out})
    return {"query": query, "since": since_year, "papers": out}


def t_show_papers(ctx, pmids, title=None):
    known = ctx.get("papers", {})
    items = [known[p] for p in pmids if p in known]
    for p in pmids:
        if p not in known and f"PMID:{p}" in ctx["ledger"].refs:
            r = ctx["ledger"].refs[f"PMID:{p}"]
            items.append({"pmid": p, "title": r["label"].split(": ", 1)[-1], "type": "", "date": "", "journal": "", "cited": 0,
                          "key": (ctx["ledger"].texts.get(f"PMID:{p}") or [""])[:1]})
    ctx["views"].append({"view": "papers", "title": title or "Research", "items": items})
    return {"shown": True, "papers": len(items)}


# --- Control ----------------------------------------------------------------------------------------------------------

AIMS = ("strategies", "risk", "explain", "research", "other")
OUTWARD = ("search_papers", "research_genotypes", "recent_papers", "read_paper")
MIN_OUTWARD = 2  # outward lookups before a strategies answer is accepted


def _aim(aim):
    """The aim as one of AIMS; a free-text aim (an MCP client may not enforce the enum) is read by its words."""
    a = (aim or "").strip().lower()
    if a in AIMS:
        return a
    for key, pat in (("strategies", r"strateg|what works|to do|how to|approach|stay|keep|improv|reach|avoid|lean|lose|gain"),
                     ("research", r"research|studies|papers|latest"), ("risk", r"risk|prone|propens|chance|likel"),
                     ("explain", r"explain|how does|how do|what is|look")):
        if re.search(pat, a):
            return key
    return "other"


STOP = {"and", "the", "for", "with", "diet", "diets", "intake", "training", "based", "eating", "low", "high"}


def _words(s):
    return {w for w in re.findall(r"[a-z]{4,}", (s or "").lower())} - STOP


def researched(ctx, strategy):
    """Whether an outward lookup this turn was about the strategy: its words in a query, topic or find list."""
    want = _words(strategy) or {w for w in re.findall(r"[a-z]{3,}", strategy.lower())}
    return any(want & _words(json.dumps(a, ensure_ascii=False)) for a in ctx.get("outward_args", []))


def _stems(s):
    """Words cut to five letters, so 'fibre' meets 'fibres' and 'regeneration' meets 'regenerate'."""
    return {w[:5] for w in re.findall(r"[a-z]{3,}", (s or "").lower())} - {w[:5] for w in STOP}


def _area_ids(area):
    """The cluster mechanism ids an area names: by a mechanism's id or name, or by a phase (id or name) and the
    mechanisms in it ('hormones' -> testosterone, gh; 'fibre type' -> fast, slow)."""
    want, ids = _stems(area), set()
    for g in facts._theme_graphs().values():
        for m in g.get("mechanisms") or []:
            if want & (_stems(m["id"]) | _stems(m["name"])):
                ids.add(m["id"])
        for o in g.get("organs") or []:
            if want & (_stems(o["id"]) | _stems(o["name"])):
                ids |= {m["id"] for m in g.get("mechanisms") or [] if m.get("organ") == o["id"]}
    return ids


def covered(ctx, area):
    """Whether a lookup this turn read the area: one of its mechanism ids, or its words, in a lookup's arguments."""
    ids, want = _area_ids(area), _stems(area)
    for a in ctx.get("lookup_args", []):
        read = {x.strip() for x in str(a.get("mechanism") or "").split(",") if x.strip()}
        if ids & read or want & _stems(json.dumps(a, ensure_ascii=False)):
            return True
    return False


def t_understand(ctx, reading, plan, aim="other", strategies=None, areas=None):
    aim = _aim(aim)
    ctx["understood"] = {"reading": reading, "plan": plan, "aim": aim, "strategies": [s for s in (strategies or []) if s.strip()][:6],
                         "areas": [s for s in (areas or []) if s.strip()][:8]}
    nxt = "Run the plan with the tools."
    if aim == "strategies":
        nxt += (" A strategies question needs the studies of how people with the person's genotypes respond: research "
                "outward (search_papers, research_genotypes, read_paper) before answering.")
    return {"ok": True, "next": nxt}


MAX_REJECTIONS = 2  # after this many rejected answers, the next is accepted without what it couldn't support
CITE = r"\[((?:PMID|ClinPGx|GWAS|ClinVar|UniProt|Reactome):[^\]\s]+)\]"


def _highlights(ctx, highlights):
    """The highlight tiles that hold, and the reasons the others don't: each figure must be in its source's text, or
    in the person's own named result ('yours', sharing on)."""
    from cluster_analysis.agent import interpret
    tiles, bad = [], []
    for h in (highlights or [])[:6]:
        parts = [x.strip() for x in str(h).split("|")]
        if len(parts) != 3:
            bad.append(f"{h!r}: write it as 'label | value | source ref'")
            continue
        label, value, src = parts
        if language.advice(label + " " + value):
            bad.append(f"{label}: clinical advice")
            continue
        asked = language.ranks_asked(ctx.get("question"), (ctx.get("understood") or {}).get("aim"))
        rp = language.rank_problems(value, asked) + language.rank_problems(label, asked)
        if src.lower() in ("yours", "your result", "your results") and not asked and re.search(r"\b(top|bottom)\s+\d", value, re.I):
            rp.append("the question doesn't ask where the person ranks")
        if rp:
            bad.append(f"{label}: {rp[0]}")
            continue
        if src.lower() in ("yours", "your result", "your results"):
            if not ctx.get("share"):
                bad.append(f"{label}: the person's results are not shared with you, so they can't be a highlight")
                continue
            # The result the label names (its words in the result's title), and only that result's figures
            want = {w for w in re.findall(r"[a-z0-9]{3,}", label.lower())} - {"genetic", "score", "your", "baseline", "result", "level", "blood"}
            seen = [c for c in ctx["cards"] if not c.get("pair") or ctx.get("pair_shared")]
            match = [c for c in interpreted(seen) if want & set(re.findall(r"[a-z0-9]{3,}", (c["result"] or "").lower()))]
            if not match:
                bad.append(f"{label}: no result of the person's matches this label; name it as the result is named")
                continue
            mine = set().union(*[interpret.figures(json.dumps(c, ensure_ascii=False)) for c in match])
            if not interpret.figures(value) <= mine:
                bad.append(f"{label}: the figure {value!r} is not in the person's {match[0]['result']} result")
                continue
            tiles.append({"label": label, "value": value, "source": "yours"})
            continue
        if src not in ctx["ledger"].refs:
            bad.append(f"{label}: {src} was not returned by a tool")
            continue
        if not interpret.figures(value) <= interpret.figures(" ".join(ctx["ledger"].texts.get(src, []))):
            bad.append(f"{label}: the figure {value!r} is not in {src}'s text")
            continue
        tiles.append({"label": label, "value": value, "source": src})
    return tiles, bad


def _links(ctx, links):
    """The answer's logic web: each link ties an area or strategy to the person's genes, the evidence refs and the
    finding. Genes must come from this turn's tools; refs must be ones a tool returned."""
    known = set(ctx["ledger"].genes) | set(ctx["ledger"].variants)
    for c in ctx["cards"]:
        known |= set(re.findall(r"\b[A-Z][A-Z0-9-]{1,9}\b|\brs\d+\b", json.dumps(c, ensure_ascii=False)))
    web, bad = [], []
    for raw in (links or [])[:12]:
        parts = [x.strip() for x in str(raw).split("|")]
        if len(parts) != 4:
            bad.append(f"{raw!r}: write it as 'area or strategy | genes | refs | finding'")
            continue
        node, genes, refs, finding = parts
        gs = [g for g in re.split(r"[,;\s]+", genes) if g and g.lower() not in ("none", "-", "n/a")
              and not re.fullmatch(r"[ACGT]{1,2}|[ACGT]/[ACGT]|\*\d+/\*\d+", g)]
        rs = [r for r in re.split(r"[,;\s]+", refs) if r and r.lower() not in ("none", "-", "n/a")]
        # A link keeps what holds: a gene or ref no tool returned is left out of it, not the whole link
        unknown = [g for g in gs if g not in known] + [r for r in rs if r not in ctx["ledger"].refs]
        web.append({"node": node, "genes": [g for g in gs if g in known], "refs": [r for r in rs if r in ctx["ledger"].refs],
                     "finding": finding, **({"left_out": unknown} if unknown else {})})
    return web, bad


def t_answer(ctx, explanation, followups=None, highlights=None, summary=None, links=None):
    """The answer: every [PMID:…] or [ClinPGx:…] it cites must be one a tool returned, every highlight figure must be
    in its source, and nothing may read as clinical advice. All problems are reported at once."""
    summary = (summary or "").strip()
    hard, soft = [], []
    if not summary:
        hard.append("Write the summary first: 2-4 sentences that weave together what the person's results and the "
                    "evidence mean for their question.")
    if ((ctx.get("understood") or {}).get("aim") == "strategies" and ctx.get("outward", 0) < MIN_OUTWARD
            and ctx.get("spent", 0) < budget_of(ctx)):
        hard.append("This asks what works for the person, and the answer has no research behind it yet: look outward "
                    "for how people with their genotypes respond to the strategies (search_papers for trials and "
                    "meta-analyses by genotype, research_genotypes with the strategy as the topic, read_paper for the "
                    "sizes), then lead the summary with what that evidence says.")
    if (ctx.get("understood") or {}).get("aim") == "strategies" and ctx.get("spent", 0) < budget_of(ctx):
        todo = [s for s in ctx["understood"].get("strategies") or [] if not researched(ctx, s)]
        if todo:
            hard.append("You listed these strategies but haven't researched them: " + ", ".join(todo) + ". Search each "
                        "(search_papers with the strategy and the person's genes or 'genotype'), then answer; if nothing "
                        "by genotype exists, say so in the answer.")
    u = ctx.get("understood") or {}
    asked = language.ranks_asked(ctx.get("question"), u.get("aim"))
    ranks = language.rank_problems(summary, asked) + language.rank_problems(explanation, asked)
    if ranks:
        hard.append("Ranks: " + "; ".join(dict.fromkeys(ranks)) + ".")
    if ctx.get("spent", 0) < budget_of(ctx):
        unread = [a for a in u.get("areas") or [] if not covered(ctx, a)]
        if unread:
            soft.append("You listed these areas but haven't read them: " + ", ".join(unread) + ". Read each (my_cluster with "
                        "the mechanism ids, comma-separated; gene; search_papers), then answer.")
    web, web_bad = _links(ctx, links)
    nodes = (u.get("areas") or []) + (u.get("strategies") or [])
    if nodes or u.get("aim") in ("strategies", "explain"):
        if not web and not web_bad:
            soft.append("Add links: one per area and strategy, 'area or strategy | the person's genes behind it | refs | "
                        "the finding in a few words', so the answer can be drawn as a web.")
        missing_nodes = [n for n in nodes if not any(_words(n) & _words(w["node"]) for w in web)]
        if web and missing_nodes:
            soft.append("Links missing for: " + ", ".join(missing_nodes) + " (a link may say 'none' for genes or refs, and "
                        "what wasn't found).")
    if web_bad:
        soft.append("Links not accepted: " + "; ".join(web_bad))
    said = language.advice(explanation + " " + summary + " " + " ".join(w["finding"] for w in web))
    if said:
        hard.append("It gives clinical advice (" + "; ".join(said[:5]) + "). Rephrase in risk and evidence: what the "
                    "genotype means for risk, exposure or response, and guidelines as facts about the guideline.")
    cited = set(re.findall(CITE, explanation)) | set(re.findall(CITE, summary))
    missing = sorted(c for c in cited if c not in ctx["ledger"].refs)
    if missing:
        soft.append(f"These citations were not returned by any tool in this conversation: {', '.join(missing)}. "
                    "Cite only refs the tools gave, or remove them.")
    tiles, bad = _highlights(ctx, highlights)
    if bad:
        soft.append("Highlights not accepted: " + "; ".join(bad))
    ctx["rejections"] = ctx.get("rejections", 0) + (1 if hard or soft else 0)
    if hard or (soft and ctx["rejections"] <= MAX_REJECTIONS):
        left = MAX_REJECTIONS - ctx["rejections"] + 1
        return {"error": " ".join(hard + soft) + (f" Fix all of these in one go." if left > 0 else "")}
    dropped = []
    if soft:  # out of retries: keep what holds, drop what the tools didn't support
        for c in missing:
            explanation = explanation.replace(f"[{c}]", "")
            summary = summary.replace(f"[{c}]", "")
        cited -= set(missing)
        dropped = missing + [b.split(":")[0] for b in bad] + [b.split(":")[0] for b in web_bad]
    cited |= {x["source"] for x in tiles if x["source"] != "yours"}
    cited |= {r for w in web for r in w["refs"] if r in ctx["ledger"].refs}
    ctx["answer"] = {"summary": summary, "explanation": explanation, "followups": (followups or [])[:4], "highlights": tiles,
                     "links": web, "refs": {c: ctx["ledger"].refs[c] for c in sorted(cited)}, "dropped": dropped}
    return {"ok": True}

TOOLS = {
    "understand": (CONTROL, t_understand, *_s("Call this FIRST: your reading of the question and your plan, shown to the person before you work.",
                                               reading=S("One sentence to the person: what you understood they want, in their own terms, and what a genome can and can't answer about it."),
                                               aim=S("What they want out of the answer: strategies (what works, what to do or think about, how to reach a goal), "
                                                     "risk (am I prone to, do I have), explain (how a gene, drug or process works for me), research (the studies), other",
                                                     enum=list(AIMS)),
                                               strategies=A("For a strategies question: 3-6 candidate strategies you will research, the ones the person named and the "
                                                            "ones their genes' mechanisms bear on (an appetite gene: fasting or meal timing; an insulin gene: "
                                                            "carbohydrate quality), e.g. 'intermittent fasting', 'endurance training'. Each must be searched before you answer.",
                                                            optional=True),
                                               areas=A("The areas the answer must cover, each read before you answer: for a question on a cluster, its mechanisms "
                                                       "that bear on the question, by id (catalogue), e.g. for building muscle: hypertrophy, synthesis, fast, "
                                                       "tendons, regeneration, inflammation, testosterone. Every area also gets a link in the answer.", optional=True),
                                               plan=A("2-6 steps, each naming the tool or part of the explorer it uses and why."))),
    "catalogue": (PUBLIC, t_catalogue, *_s("The explorer's clusters with their mechanisms, its cancer types, lab tests, nutrients and fitness tests (ids to use).")),
    "resolve": (PUBLIC, t_resolve, *_s("Find what a name refers to in the explorer (a drug by any name, a gene, a test, a condition, a mechanism).",
                                       text=S("The name as written, e.g. paracetamol"),
                                       kind=S("drug, gene, condition, theme or any", optional=True, enum=["any", "drug", "gene", "condition", "theme"]))),
    "gene": (PUBLIC, t_gene, *_s("A gene: protein function (UniProt), the clusters it is in, its strongest GWAS variants and traits, ClinVar.", symbol=S("HGNC symbol"))),
    "variant": (PUBLIC, t_variant, *_s("A variant: alleles, European frequency, every genome-wide association, ClinVar, ClinPGx.", rsid=S("rsID"))),
    "cluster": (PUBLIC, t_cluster, *_s("A cluster (theme): its mechanisms and traits, or the genes of one mechanism or trait.",
                                       theme=S("theme id, e.g. muscle, mind, cancer"), mechanism=S("mechanism id", optional=True),
                                       trait=S("trait name", optional=True), limit=I("max genes", optional=True))),
    "trait_variants": (PUBLIC, t_trait_variants, *_s("GWAS Catalog traits matching a phrase and their strongest variants.", trait=S("trait phrase"))),
    "drug": (PUBLIC, t_drug, *_s("A drug's genetics for everyone: dosing guidelines and ClinPGx clinical annotations with the effect of every genotype. Accepts any name (paracetamol, Tylenol).",
                                 name=S("drug name as written"))),
    "research_genotypes": (PUBLIC, t_research_genotypes, *_s("Studies reporting results by genotype for variants on a topic: the sentences that name a genotype group and an effect. Use it when local data doesn't answer the question.",
                                                             rsids=A("rsIDs to research (from gene, variant, drug or cluster results)"), topic=S("what the question is about, e.g. paracetamol liver toxicity"))),
    "search_papers": (PUBLIC, t_search_papers, *_s("Europe PMC search (all of PubMed and open full texts).", query=S("query, field syntax allowed"), limit=I("max papers", optional=True))),
    "read_paper": (PUBLIC, t_read_paper, *_s("A paper's abstract, and with find=[words] the open full-text paragraphs that use them.", pmid=S("PubMed id"),
                                             find=A("words to find in the full text", optional=True))),
    "pathway": (PUBLIC, t_pathway, *_s("A gene's pathway steps (Reactome reactions with their inputs and outputs), from the explorer's Gene pathway data or built live from Reactome.", gene=S("HGNC symbol"))),
    "nutrient": (PUBLIC, t_nutrient, *_s("A nutrient for everyone: its blood tests and its uptake and conversion steps with the genes acting at each (the explorer's Nutrition module).", name=S("nutrient name, e.g. vitamin D"))),
    "recent_papers": (PUBLIC, t_recent_papers, *_s("The newest papers on a topic, a gene or a muscle group (Europe PMC, newest first), each with the sentences that carry its finding.",
                                                   query=S("topic, e.g. ACTN3 AND training, or hamstring injury genetics"), since_year=I("first year, default 2023", optional=True),
                                                   limit=I("max papers, default 6", optional=True))),
    "trait_model": (PUBLIC, pair.t_trait_model, *_s("The GWAS Catalog study (its people, lead variants) and the EFO definition behind a trait's prediction in the Inheritance tab, and how a child's prediction is made from it. Facts for everyone.",
                                                     trait=S("trait name, e.g. height, LDL cholesterol"))),
    "my_genes_by_function": (PERSONAL, functions.t_my_genes_by_function, *_s("List the person's genes the explorer calls gain of function (GoF), loss of function (LoF) or altered, across the clusters or in one, with the variant and the evidence behind each call (a reviewed protein change, or an expression effect). Use it for 'my GoF genes', 'which genes are less active'.",
                                                                          function=S("GoF, LoF or altered"), theme=S("theme id, e.g. muscle, cancer (optional)", optional=True))),
    "my_traits": (PERSONAL, traits.t_my_traits, *_s("Read where the person's genes place them among Europeans on GWAS Catalog traits the question names (height, sleep duration, LDL cholesterol, chronotype; 2,000+ traits, the Biomarkers tab), drawn as a scale with the genes behind it. They see it; you get the result only with Restricted mode off.",
                                                    about=A("the traits the question names, as written"))),
    "my_child": (PERSONAL, pair.t_my_child, *_s("Read what a child of the two profiles picked in the explorer could inherit, for the traits, conditions and gene symbols the question names (Inheritance tab): the person sees it; you get the child's bands and odds when Restricted mode is off, otherwise the public part.",
                                                about=A("the traits, conditions or gene symbols the question names, as written (e.g. height, cystic fibrosis, CYP2C19)"))),
    "my_nutrient": (PERSONAL, t_my_nutrient, *_s("Read the person's genetic baseline for a nutrient and their variants at its steps. They see it; you get its shape.", name=S("nutrient name"))),
    "show_nutrient": (VIEW, t_show_nutrient, *_s("Draw the nutrient's uptake and conversion steps in the answer, with the person's variants marked at each step.", name=S("nutrient name"))),
    "show_papers": (VIEW, t_show_papers, *_s("Show a research digest in the answer: the papers (from recent_papers, search_papers or read_paper) with their key findings.",
                                             pmids=A("PubMed ids"), title=S("heading, e.g. Latest research on ACTN3", optional=True))),
    "my_medicine": (PERSONAL, t_my_medicine, *_s("Read the person's own results for one drug (guidelines and ClinPGx annotations for their genotypes). They see the result; you get its shape.", name=S("drug name"))),
    "my_medicines": (PERSONAL, t_my_medicines, *_s("Read the person's medicine overview: every gene whose result changes dosing guidance. They see it; you get its shape.")),
    "my_scores": (PERSONAL, t_my_scores, *_s("Read the person's genetic scores in a domain (cancer, lab, nutrient, fitness), all or some ids.",
                                             domain=S("domain", enum=["cancer", "lab", "nutrient", "fitness"]), ids=A("ids from the catalogue", optional=True))),
    "my_cluster": (PERSONAL, t_my_cluster, *_s("Read the person's genes in a cluster, or in one or more of its mechanisms, and the study findings for their genotypes.",
                                               theme=S("theme id"), mechanism=S("mechanism id, or several comma-separated (e.g. tendons,regeneration,hypertrophy)", optional=True))),
    "my_gene": (PERSONAL, t_my_gene, *_s("Read the person's result for one gene across the clusters, tables and pathways.", symbol=S("HGNC symbol"))),
    "my_condition": (PERSONAL, t_my_condition, *_s("Read the person's inherited risk for a condition (GWAS risk alleles, ClinVar).", name=S("condition in English"))),
    "show_cluster": (VIEW, t_show_cluster, *_s("Draw the cluster around a gene (its network neighbours in the theme, coloured by the person's results) or a mechanism, in the answer.",
                                               theme=S("theme id"), gene=S("HGNC symbol", optional=True), mechanism=S("mechanism id", optional=True))),
    "show_pathway": (VIEW, t_show_pathway, *_s("Draw a gene's pathway (its Reactome steps, inputs and outputs) in the answer.", gene=S("HGNC symbol"))),
    "show_medicine": (VIEW, t_show_medicine, *_s("Show the explorer's medicine view for a drug in the answer.", name=S("drug name"))),
    "answer": (CONTROL, t_answer, *_s("Finish: the summary (2-4 sentences weaving the person's results and the evidence into what they mean for the question), highlights, then the supporting explanation, citing refs the tools returned as [PMID:123] or [ClinPGx:…], and 2-4 follow-up questions.",
                                      summary=S("2-4 sentences, the narrative, answering the question as asked in the first sentence: for a strategies question, which strategies the evidence links to the person's genotypes and how people with them responded; their propensity after, only as context. In risk and evidence language."),
                                      explanation=S("The supporting detail, plain words, 3-8 sentences."), followups=A("follow-up questions", optional=True),
                                      links=A("The logic web, one per area and strategy from understand: 'area or strategy | the person's genes behind it "
                                              "(symbols or rsIDs from this turn's tools, or none) | refs (PMID:…, comma-separated, or none) | the finding in a "
                                              "few words', e.g. 'tendons | COL5A1, COL1A1 | PMID:123 | carriers had fewer tendon injuries in one cohort'.", optional=True),
                                      highlights=A("2-5 key figures as 'label | value | source'; the value is a short figure (e.g. 'OR 0.71', '80th percentile'). The source is a ref a tool returned (its text must give the figure), or 'yours' for the person's own result (its figure must be in their results), e.g. 'ACTN3 T allele and power | OR 0.71 | PMID:41009985', 'LDL cholesterol score | 80th percentile | yours'", optional=True))),
}

KIND = {name: spec[0] for name, spec in TOOLS.items()}


# Programmatic tool calling (API backend): these lookups are called from Claude's code, not directly. Their results
# go to the running script, which keeps what matters and prints it; only the printout enters the model's context.
# Personal tools, views, understand and answer stay direct, so what reaches the screen and the checks is unchanged.
CODE_EXECUTION = "code_execution_20260120"
SCRIPTED = ("gene", "variant", "cluster", "trait_variants", "search_papers", "research_genotypes", "recent_papers")


def schemas(ptc=False):
    out = [{"name": n, "description": d, "input_schema": schema} for n, (_, _, schema, d) in TOOLS.items()]
    if ptc:
        for s in out:
            if s["name"] in SCRIPTED:
                s["allowed_callers"] = [CODE_EXECUTION]
        out.insert(0, {"type": CODE_EXECUTION, "name": "code_execution"})
    return out


def new_context(person, session=None, share=None):
    from cluster_analysis.agent import settings
    return {"person": person, "ledger": session.ledger if session else facts.Ledger(), "cards": [], "views": [],
            "findings": [], "understood": None, "answer": None, "words": (),
            "share": settings.get()["share_results"] if share is None else share}


def interpreted(cards):
    """The person's interpreted results, for the model when sharing is on: what each result is (a gene's type, a
    score's band and direction, the genotype behind a finding), never the DNA file and nothing the question didn't
    touch."""
    out = []
    for c in cards:
        score = c["provider"] in ("cancer", "lab", "nutrient", "fitness", "condition") and isinstance(c.get("value"), (int, float))
        out.append({"result": c["title"], "kind": c["provider"], "level": c["level"],
                    "rank": _rank(c) if score else None,
                    "higher_is": c.get("higher"), "summary": _ranked(c.get("headline"), c.get("higher")),
                    "details": [{k: _ranked(r.get(k), c.get("higher")) if isinstance(r.get(k), str) else r.get(k) for k in ("label", "value", "note") if r.get(k)}
                                for r in (c.get("rows") or [])[:10] if (r.get("label") or "").lower() != "percentile"],
                    "unknown": (c.get("unknown") or [None])[0],
                    "studies": [{"gene": m.get("gene"), "rsid": m.get("rsid"), "groups": m.get("labels"), "sentence": (m.get("sentence") or "")[:220],
                                 "ref": f"PMID:{m['pmid']}" if m.get("pmid") else None} for m in (c.get("findings") or [])[:6]] or None})
    return out


def _rank(c):
    """A score's rank for the model: 'bottom 2% of Europeans (the unfavourable end: a higher genetic risk than 98%)'."""
    p, h = round(c["value"]), c.get("higher")
    words = language.rank_words(p, h)
    if h == "worse":
        side = f"a lower genetic risk or level than {100 - p}% of Europeans" if p <= 40 else f"a higher genetic risk or level than {p}% of Europeans"
    elif h == "better":
        side = f"higher than {p}% of Europeans" if p >= 60 else f"lower than {100 - p}% of Europeans"
    else:
        side = None
    if words.startswith("normal"):
        return words
    return f"{words} of Europeans" + (f" ({side})" if side else "")


def _ranked(s, higher=None):
    """'near the 98th percentile' -> 'in the bottom 2%' (a risk): ranks as people read them, top the favourable end."""
    if not s:
        return s
    s = re.sub(r"\b(?:at|near) the (\d{1,3})(?:st|nd|rd|th) percentile", lambda m: "in the " + language.rank_words(int(m.group(1)), higher), s)
    return re.sub(r"\b(?:the )?(\d{1,3})(?:st|nd|rd|th) percentile", lambda m: language.rank_words(int(m.group(1)), higher), s)


def _trace(ctx, name, args, out, error, cards=()):
    """The turn's record of every call for the person's screen: what was asked and what came back, or why it was
    refused. Never sent to the model."""
    ctx.setdefault("trace", []).append({"name": name, "args": args, "ok": not error, "error": error,
                                        "note": None if error else _note(name, out, cards, ctx)})


def _note(name, out, cards, ctx):
    """One line on what a call returned."""
    if name == "understand":
        u = ctx.get("understood") or {}
        return "; ".join(x for x in (f"aim: {u.get('aim')}", ("areas: " + ", ".join(u["areas"])) if u.get("areas") else "",
                                     ("strategies: " + ", ".join(u["strategies"])) if u.get("strategies") else "") if x)
    if name == "answer":
        a = ctx.get("answer") or {}
        return "accepted" + (f"; dropped what the tools didn't support: {', '.join(a['dropped'])}" if a.get("dropped") else "")
    if cards:
        return "on your screen: " + "; ".join(c["title"] for c in cards[:5]) + (f" (+{len(cards) - 5} more)" if len(cards) > 5 else "")
    if isinstance(out, dict):
        if name == "research_genotypes":
            n = sum(len(v.get("findings") or []) for v in out.get("variants") or [])
            return f"{n} study sentences naming a genotype group" if n else "no study reports results by genotype for these"
        bits = [f"{len(v)} {k.replace('_', ' ')}" for k, v in out.items() if isinstance(v, list) and v and k not in ("rsids", "find")]
        titles = [p.get("title") for p in (out.get("papers") or [])[:2] if isinstance(p, dict) and p.get("title")]
        if name == "read_paper":
            return (out.get("title") or "")[:90] + (f" · {len(out.get('paragraphs') or [])} full-text passages" if out.get("paragraphs") else "")
        if not bits:
            filled = [k for k, v in out.items() if v not in (None, "", [], {})]
            return ("returned " + ", ".join(filled[:4])) if filled else "nothing found"
        return " · ".join(bits[:4]) + (": " + "; ".join(t[:70] for t in titles) if titles else "")
    if isinstance(out, list):
        return f"{len(out)} items"
    return None


CALL_BUDGET = 10  # lookups per turn (public and personal tools)
DEEP_BUDGET = 20  # for a strategies or research question, which has to look outward


def budget_of(ctx):
    return DEEP_BUDGET if (ctx.get("understood") or {}).get("aim") in ("strategies", "research") else CALL_BUDGET


def call(ctx, name, args):
    """Runs a tool: (text for the model, is_error)."""
    if name not in TOOLS:
        return f"No tool {name!r}.", True
    kind, fn, schema, _ = TOOLS[name]
    if kind in (PUBLIC, PERSONAL):
        budget = budget_of(ctx)
        ctx["spent"] = ctx.get("spent", 0) + 1
        if ctx["spent"] > budget:
            return (f"The lookup budget for this turn ({budget}) is used. Call answer now with what you have; "
                    "say plainly what the evidence gathered can't tell."), True
        ctx.setdefault("lookup_args", []).append({"tool": name, **args})
        if name in OUTWARD:
            ctx["outward"] = ctx.get("outward", 0) + 1
            ctx.setdefault("outward_args", []).append({k: v for k, v in args.items() if k in ("query", "topic", "find")})
    args = {k: v for k, v in (args or {}).items() if k in schema["properties"]}
    missing = [k for k in schema["required"] if k not in args]
    if missing:
        return f"Missing {', '.join(missing)}.", True
    before = len(ctx["cards"])
    try:
        out = fn(ctx, **args)
    except Exception as e:
        _trace(ctx, name, args, None, f"{name} failed: {type(e).__name__}: {str(e)[:300]}")
        return f"{name} failed: {type(e).__name__}: {str(e)[:300]}", True
    _trace(ctx, name, args, out, out.get("error") if isinstance(out, dict) and "error" in out and len(out) <= 2 else None,
           ctx["cards"][before:])
    # Restricted mode off: a personal tool also gives the model the interpreted results it just put on the screen.
    # A child's results (my_child) are left out here: that tool sends its own, narrower ones
    new = [c for c in ctx["cards"][before:] if not c.get("pair")]
    if kind == PERSONAL and ctx.get("share") and isinstance(out, dict) and new:
        for c in new:
            for m in c.get("findings") or []:
                pmid = m.get("pmid") or (re.search(r"MED/(\d+)|pubmed/(\d+)", m.get("url") or "") or [None, None])[1]
                if pmid:
                    ctx["ledger"].ref(f"PMID:{pmid}", f"PMID {pmid}: {m.get('title') or ''}", m.get("url") or f"https://europepmc.org/article/MED/{pmid}")
                    ctx["ledger"].text(f"PMID:{pmid}", m.get("sentence") or "")
        out = {**out, "results": interpreted(new),
               "note": "The person's interpreted results for this item, shared so you can weave them into the summary."}
    err = isinstance(out, dict) and "error" in out and len(out) <= 2
    return facts.clip(out), err
