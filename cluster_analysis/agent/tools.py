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

from cluster_analysis.agent import evidence, facts, language, morsels, providers, terms

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
    return facts.gene(ctx["ledger"], symbol, limit=10)


def t_variant(ctx, rsid):
    return facts.variant(ctx["ledger"], rsid, limit=15)


def t_cluster(ctx, theme, mechanism=None, trait=None, limit=25):
    if not mechanism and not trait:
        return facts.themes(ctx["ledger"], theme)
    return facts.theme_genes(ctx["ledger"], theme, mechanism, trait, limit)


def t_trait_variants(ctx, trait):
    return facts.trait_variants(ctx["ledger"], trait, limit=20)


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
        gts = [{"genotype": t["genotype"], "text": re.split(r"(?<=\.)\s", t["text"])[0][:220]} for t in full]
        ann.append({"ref": rid, "gene": r["Gene"], "variant": r["Variant/Haplotypes"], "level": r["Level of Evidence"],
                    "category": r["Phenotype Category"], "phenotype": r.get("Phenotype(s)"), "genotypes": gts})
    ann.sort(key=lambda a: a["level"])
    cpic = []
    path = os.path.join(providers.ROOT, "data", "reference", "cpic_recommendations.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cpic = sorted({r["guideline"]["name"] for r in json.load(f) if (r.get("drug") or {}).get("name") == drug})
    return {"drug": drug, "asked_as": name, "guidelines": cpic, "annotations": ann[:15], "annotation_total": len(ann),
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
            "condition": "the person's risk-allele count for the condition", "medicines": "the person's medicine results"}
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


def t_recent_papers(ctx, query, since_year=2023, limit=8):
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

def t_understand(ctx, reading, plan):
    ctx["understood"] = {"reading": reading, "plan": plan}
    return {"ok": True, "next": "Run the plan with the tools."}


def t_answer(ctx, explanation, followups=None, highlights=None, summary=None):
    """The general explanation, for anyone: every [PMID:…] or [ClinPGx:…] it cites must be one a tool returned."""
    if not (summary or "").strip():
        return {"error": "Write the summary first: 2-4 sentences that weave together what the person's results and the "
                         "evidence mean for their question."}
    said = language.advice(explanation + " " + summary)
    if said:
        return {"error": "This gives clinical advice (" + "; ".join(said[:5]) + "). Rephrase in risk and evidence: what the "
                         "genotype means for risk, exposure or response, and guidelines as facts about the guideline."}
    cited = set(re.findall(r"\[((?:PMID|ClinPGx|GWAS|ClinVar|UniProt):[^\]\s]+)\]", explanation))
    missing = sorted(c for c in cited if c not in ctx["ledger"].refs)
    if missing:
        return {"error": f"These citations were not returned by any tool in this conversation: {', '.join(missing)}. "
                         "Cite only refs the tools gave, or remove them."}
    # Highlights: the answer's key figures as tiles, each tied to a source whose text gives the figure
    from cluster_analysis.agent import interpret
    tiles, bad = [], []
    for h in (highlights or [])[:6]:
        parts = [x.strip() for x in str(h).split("|")]
        if len(parts) != 3:
            bad.append(f"{h!r}: write it as 'label | value | source ref'")
            continue
        label, value, src = parts
        # The person's own result as the source (sharing on): its figures must be in their results from this turn
        if src.lower() in ("yours", "your result", "your results"):
            if not ctx.get("share"):
                bad.append(f"{label}: the person's results are not shared with you, so they can't be a highlight")
                continue
            # The result the label names (its words in the result's title), and only that result's figures
            want = {w for w in re.findall(r"[a-z0-9]{3,}", label.lower())} - {"genetic", "score", "your", "baseline", "result", "level", "blood"}
            match = [c for c in interpreted(ctx["cards"]) if want & set(re.findall(r"[a-z0-9]{3,}", (c["result"] or "").lower()))]
            mine = set().union(*[interpret.figures(json.dumps(c, ensure_ascii=False)) for c in match]) if match else set()
            if not match:
                bad.append(f"{label}: no result of the person's matches this label; name it as the result is named")
                continue
            if not interpret.figures(value) <= mine:
                bad.append(f"{label}: the figure {value!r} is not in the person's {match[0]['result']} result")
                continue
            if language.advice(label + " " + value):
                bad.append(f"{label}: clinical advice")
                continue
            tiles.append({"label": label, "value": value, "source": "yours"})
            continue
        if src not in ctx["ledger"].refs:
            bad.append(f"{label}: {src} was not returned by a tool")
            continue
        pool = interpret.figures(" ".join(ctx["ledger"].texts.get(src, [])))
        if not interpret.figures(value) <= pool:
            bad.append(f"{label}: the figure {value!r} is not in {src}'s text")
            continue
        if language.advice(label + " " + value):
            bad.append(f"{label}: clinical advice")
            continue
        tiles.append({"label": label, "value": value, "source": src})
        cited.add(src)
    if bad:
        return {"error": "Highlights not accepted: " + "; ".join(bad)}
    cited |= set(re.findall(r"\[((?:PMID|ClinPGx|GWAS|ClinVar|UniProt|Reactome):[^\]\s]+)\]", summary))
    missing = sorted(c for c in cited if c not in ctx["ledger"].refs)
    if missing:
        return {"error": f"These citations were not returned by any tool: {', '.join(missing)}."}
    ctx["answer"] = {"summary": summary.strip(), "explanation": explanation, "followups": (followups or [])[:4], "highlights": tiles,
                     "refs": {c: ctx["ledger"].refs[c] for c in sorted(cited)}}
    return {"ok": True}


TOOLS = {
    "understand": (CONTROL, t_understand, *_s("Call this FIRST: your reading of the question and your plan, shown to the person before you work.",
                                               reading=S("One sentence to the person: what you understood they want, and what a genome can and can't answer about it."),
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
                                                   limit=I("max papers, default 8", optional=True))),
    "my_nutrient": (PERSONAL, t_my_nutrient, *_s("Read the person's genetic baseline for a nutrient and their variants at its steps. They see it; you get its shape.", name=S("nutrient name"))),
    "show_nutrient": (VIEW, t_show_nutrient, *_s("Draw the nutrient's uptake and conversion steps in the answer, with the person's variants marked at each step.", name=S("nutrient name"))),
    "show_papers": (VIEW, t_show_papers, *_s("Show a research digest in the answer: the papers (from recent_papers, search_papers or read_paper) with their key findings.",
                                             pmids=A("PubMed ids"), title=S("heading, e.g. Latest research on ACTN3", optional=True))),
    "my_medicine": (PERSONAL, t_my_medicine, *_s("Read the person's own results for one drug (guidelines and ClinPGx annotations for their genotypes). They see the result; you get its shape.", name=S("drug name"))),
    "my_medicines": (PERSONAL, t_my_medicines, *_s("Read the person's medicine overview: every gene whose result changes dosing guidance. They see it; you get its shape.")),
    "my_scores": (PERSONAL, t_my_scores, *_s("Read the person's genetic scores in a domain (cancer, lab, nutrient, fitness), all or some ids.",
                                             domain=S("domain", enum=["cancer", "lab", "nutrient", "fitness"]), ids=A("ids from the catalogue", optional=True))),
    "my_cluster": (PERSONAL, t_my_cluster, *_s("Read the person's genes in a cluster (or one mechanism) and the study findings for their genotypes.",
                                               theme=S("theme id"), mechanism=S("mechanism id", optional=True))),
    "my_gene": (PERSONAL, t_my_gene, *_s("Read the person's result for one gene across the clusters, tables and pathways.", symbol=S("HGNC symbol"))),
    "my_condition": (PERSONAL, t_my_condition, *_s("Read the person's inherited risk for a condition (GWAS risk alleles, ClinVar).", name=S("condition in English"))),
    "show_cluster": (VIEW, t_show_cluster, *_s("Draw the cluster around a gene (its network neighbours in the theme, coloured by the person's results) or a mechanism, in the answer.",
                                               theme=S("theme id"), gene=S("HGNC symbol", optional=True), mechanism=S("mechanism id", optional=True))),
    "show_pathway": (VIEW, t_show_pathway, *_s("Draw a gene's pathway (its Reactome steps, inputs and outputs) in the answer.", gene=S("HGNC symbol"))),
    "show_medicine": (VIEW, t_show_medicine, *_s("Show the explorer's medicine view for a drug in the answer.", name=S("drug name"))),
    "answer": (CONTROL, t_answer, *_s("Finish: the summary (2-4 sentences weaving the person's results and the evidence into what they mean for the question), highlights, then the supporting explanation, citing refs the tools returned as [PMID:123] or [ClinPGx:…], and 2-4 follow-up questions.",
                                      summary=S("2-4 sentences, the narrative: what the person's results together mean for their question, the strongest signal first, in risk language."),
                                      explanation=S("The supporting detail, plain words, 3-8 sentences."), followups=A("follow-up questions", optional=True),
                                      highlights=A("2-5 key figures as 'label | value | source'; the value is a short figure (e.g. 'OR 0.71', '80th percentile'). The source is a ref a tool returned (its text must give the figure), or 'yours' for the person's own result (its figure must be in their results), e.g. 'ACTN3 T allele and power | OR 0.71 | PMID:41009985', 'LDL cholesterol score | 80th percentile | yours'", optional=True))),
}

KIND = {name: spec[0] for name, spec in TOOLS.items()}


def schemas():
    return [{"name": n, "description": d, "input_schema": schema} for n, (_, _, schema, d) in TOOLS.items()]


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
        out.append({"result": c["title"], "kind": c["provider"], "level": c["level"],
                    "percentile": c["value"] if c["provider"] in ("cancer", "lab", "nutrient", "fitness", "condition") else None,
                    "higher_is": c.get("higher"), "summary": c.get("headline"),
                    "details": [{k: r.get(k) for k in ("label", "value", "note") if r.get(k)} for r in (c.get("rows") or [])[:8]],
                    "unknown": (c.get("unknown") or [None])[0]})
    return out


def call(ctx, name, args):
    """Runs a tool: (text for the model, is_error)."""
    if name not in TOOLS:
        return f"No tool {name!r}.", True
    kind, fn, schema, _ = TOOLS[name]
    args = {k: v for k, v in (args or {}).items() if k in schema["properties"]}
    missing = [k for k in schema["required"] if k not in args]
    if missing:
        return f"Missing {', '.join(missing)}.", True
    before = len(ctx["cards"])
    try:
        out = fn(ctx, **args)
    except Exception as e:
        return f"{name} failed: {type(e).__name__}: {str(e)[:300]}", True
    # Sharing on: a personal tool also gives the model the interpreted results it just put on the screen
    if kind == PERSONAL and ctx.get("share") and isinstance(out, dict):
        out = {**out, "results": interpreted(ctx["cards"][before:]),
               "note": "The person's interpreted results for this item, shared so you can weave them into the summary."}
    err = isinstance(out, dict) and "error" in out and len(out) <= 2
    return facts.clip(out), err
