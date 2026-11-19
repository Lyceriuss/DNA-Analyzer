"""The quick answer: match, research, respond, with no language model.

    python -m cluster_analysis.agent quick "Which cancer will I most likely die from?" --person XY

1. match   terms.match: the items the question names (drugs, cancers, tests, nutrients, clusters, genes, conditions)
2. kind    terms.kind: the shape of answer wanted (rank, action, propensity, gene) and what it asks that can't be known
3. cards   providers: the person's own results for each matched item, read on this machine
4. studies evidence.studies for the cards whose topic came from the question, in parallel
5. verdict rules over the cards: what can't be known first, then the answer to the nearest question that can be

Each step reports through emit(event), so the Ask tab can show it and light up the sources in use.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, wait

from cluster_analysis.agent import evidence, providers, terms

ROOT = providers.ROOT
STUDY_BUDGET = 4  # seconds the quick answer waits for study searches
_BACKGROUND = ThreadPoolExecutor(max_workers=6)
LEVEL_WORD = {"high": "high", "raised": "raised", "typical": "typical", "lowered": "lowered", "low": "low",
              "differs": "calls for attention", "unknown": "unknown"}
# Which public sources each step draws on (the Ask tab lights them up)
SOURCES = {"match": ["opentargets"], "cancer": ["pgs", "iarc", "ecac"], "lab": ["pgs", "gwas", "loinc", "medlineplus"],
           "nutrient": ["pgs", "gwas", "nnr"], "fitness": ["gwas", "pgs"], "medicines": ["clinpgx", "cpic", "chembl"],
           "theme": ["go", "opentargets", "string", "reactome"], "gene": ["uniprot", "gwas", "clinvar", "reactome"],
           "condition": ["gwas", "clinvar", "1000g"], "studies": ["europepmc"], "findings": ["europepmc", "1000g"]}


def _sex(person):
    with open(os.path.join(ROOT, "cluster_analysis", "profiles.json"), encoding="utf-8") as f:
        p = next((x for x in json.load(f)["profiles"] if x["id"] == person), {})
    return p.get("sex")


def plan(items, person, words=()):
    """[(provider, kwargs)] for the matched items: each provider once, with the ids it was asked about."""
    strong = [i for i in items if i["score"] >= 0.8]
    if strong:
        top = strong[0]["score"]
        strong = [i for i in strong if i["score"] >= min(top - 1.3, 1.5)]
    typ = lambda *t: [i for i in strong if i["type"] in t]
    domains = {i["id"] for i in typ("domain")}
    jobs = []
    drugs = [i["id"] for i in typ("drug")]
    if drugs or "drug" in domains or typ("drug_class"):
        jobs.append(("medicines", {"ids": set(drugs) if drugs else None}))
    themes = typ("theme")
    cancer_named = [i["id"] for i in typ("cancer")]
    if cancer_named or "cancer" in domains or any(t["theme"] == "cancer" for t in themes):
        jobs.append(("cancers", {"ids": set(cancer_named) if cancer_named else None}))
    for prov, t in (("labs", "lab"), ("nutrients", "nutrient"), ("fitness", "fitness")):
        named = [i["id"] for i in typ(t)]
        if named or (t in domains and t != "fitness"):
            jobs.append((prov, {"ids": set(named) if named else None}))
    sex = _sex(person)
    seen, studied = set(), set()
    for t in themes:
        th = t["theme"]
        if th == "fertility":
            th = "fertility_female" if sex == "female" else "fertility_male"
        if th == "cancer":
            continue  # the cancer types answer for the cluster
        key = (th, t["id"] if t.get("level") in ("mechanism", "phase", "trait") else None)
        if key in seen:
            continue
        seen.add(key)
        if len([j for j in jobs if j[0] == "themes"]) >= 2:
            continue
        jobs.append(("themes", {"theme": th, "mechanism": key[1], "level": t.get("level")}))
        if th not in studied:
            studied.add(th)
            jobs.append(("findings", {"theme": th, "words": words}))
        if th == "muscle" and not any(j[0] == "fitness" for j in jobs):
            jobs.append(("fitness", {"ids": None}))
    for g in typ("gene"):
        jobs.append(("gene", {"symbol": g["id"]}))
    conds = typ("condition")[:4]
    if conds:
        jobs.append(("condition", {"items": conds}))
    return jobs


def verdict(kinds, unknowns, cards):
    """The answer in a few sentences, by rule: what can't be known first, then the nearest question that can be."""
    out = [u["text"] for u in unknowns]
    lead = kinds[0]
    scored = [c for c in cards if c["value"] is not None and c["provider"] in ("cancer", "lab", "nutrient", "fitness", "condition")]
    if lead == "rank" and scored:
        ranked = sorted(scored, key=lambda c: -c["value"])
        top = [f"{c['title']} ({providers.ordinal(c['value'])} percentile)" for c in ranked[:3]]
        out.append("Ranked by your genes, the highest are " + ", ".join(top) + ".")
        low = ranked[-1]
        out.append(f"The lowest is {low['title']} ({providers.ordinal(low['value'])} percentile).")
    meds = [c for c in cards if c["provider"] == "medicines"]
    act = [c for c in meds if c["level"] == "differs"]
    if meds:
        if act and act[0].get("drugs"):
            drugs = sorted({d for c in act for d in c["drugs"]})
            out.append(f"{len(drugs)} medicines need a changed dose or choice with your genes, through {len(act)} gene"
                       f"{'s' if len(act) != 1 else ''}: " + "; ".join(f"{c['gene']} ({', '.join(c['drugs'][:4])}"
                       + ("…" if len(c["drugs"]) > 4 else "") + ")" for c in act[:6]) + ".")
        elif act:
            out += [c["headline"] for c in act]
        else:
            out += [c["headline"] for c in meds[:3]]
        unread = next((c for c in meds if c["id"] == "unreadable"), None)
        if unread:
            out.append(unread["headline"])
    # Scores outside a ranking: the ones off the usual range, by side, then how many are usual
    if lead != "rank" and scored:
        side = lambda c: (c.get("higher") == "better") == (c["level"] in ("high", "raised"))
        off = [c for c in scored if c["level"] not in ("typical", "unknown")]
        fav = [c for c in off if side(c)]
        unf = [c for c in off if not side(c)]
        pct = lambda c: f"{c['title'][0].lower() + c['title'][1:] if not c['title'][:2].isupper() else c['title']} ({providers.ordinal(c['value'])})"
        if unf:
            out.append("On the unfavourable side: " + ", ".join(pct(c) for c in unf[:5]) + ".")
        if fav:
            out.append("On the favourable side: " + ", ".join(pct(c) for c in fav[:5]) + ".")
        usual = len(scored) - len(off)
        if usual:
            out.append(f"{usual} other score{'s are' if usual != 1 else ' is'} in the usual range."
                       if off else f"All {usual} scores are in the usual range.")
    for c in cards:
        if c["provider"] == "gene" and c["headline"] and len(out) < 8:
            out.append(c["headline"])
        if c["provider"] == "condition" and c["level"] == "unknown" and len(out) < 8:
            out.append(c["headline"])
    if not cards:
        out.append("Nothing in the explorer's data or the research databases matched this question.")
    return out


def summary(cards):
    """The lead of the answer: what studies found for the person's own genotypes, numbers first, one per gene."""
    out = []
    for c in cards:
        for m in c.get("findings") or []:
            out.append({"gene": m["gene"], "rsid": m["rsid"], "genotype": m["genotype"], "yours": m["yours"],
                        "ref": m.get("ref"), "alt": m.get("alt"), "amino": m.get("amino"),
                        "sentence": m["sentence"], "numbers": m["numbers"], "type": m["type"], "year": m["year"],
                        "title": m["title"], "url": m["url"]})
    out.sort(key=lambda m: (not m["numbers"],))
    pending = sum(c.get("pending") or 0 for c in cards)
    return {"findings": out[:6], "pending": pending}


def needs_deep(kinds, cards):
    """Whether the quick answer is complete, or needs the deep pass (a model writing advice): (bool, reason).
    Complete when the data itself carries the answer: guideline instructions (medicines), a ranking of scores, a
    person's standing on a named score or condition, a gene's role. Deep when the question asks what to do and the
    cards hold only data with no advice of their own (training, diet), or when nothing matched."""
    if not cards:
        return True, "Nothing in the explorer's data matched: the deep pass searches the research for it."
    advice = any(c["provider"] == "medicines" and c["level"] == "differs" for c in cards) or any(c.get("advice") for c in cards) \
        or any(c.get("findings") for c in cards)
    if any(c.get("findings") for c in cards) and kinds[0] == "action":
        return False, "The findings are quoted as the studies wrote them; a deeper analysis would turn them into a plan for you."
    if kinds[0] == "action" and not advice:
        return True, "The data shows where your genes lean, but not what to do about it: the deep pass reads the studies and writes the advice."
    return False, "The explorer's data answers this directly; a deeper analysis would add study summaries, not new facts."


def run(question, person, emit=lambda ev: None, studies=True):
    t0 = time.time()
    # 1. Understand the question: the model maps it onto the explorer (agent/route.py). Nothing runs without it.
    from cluster_analysis.agent import route, run as runner
    emit({"type": "step", "step": "understand", "sources": ["claude", "opentargets"]})
    try:
        items, kinds, unknowns, read = route.items(question)
    except route.NotUnderstood as e:
        emit({"type": "understood", "by": "none", "error": str(e), "plan": [], "items": [], "tokens": {}})
        return {"question": question, "person": person, "kinds": [], "unknowns": [], "verdict": [], "cards": [], "items": [],
                "seconds": round(time.time() - t0, 1), "tokens": 0, "error": str(e), "summary": {"findings": [], "pending": 0},
                "understood": {"by": "none", "error": str(e), "plan": [], "tokens": {}}, "deep": False, "deep_reason": ""}
    # What was understood, shown before any result: the model's reading and plan (or the rules' matches)
    emit({"type": "understood", "by": "model" if read.get("reading") else "rules", "reading": read.get("reading"),
          "plan": read.get("plan") or [], "kind": kinds[0], "unknowns": [u["text"] for u in unknowns],
          "items": [i["label"] for i in items[:8]], "tokens": {k: read.get(k, 0) for k in ("input", "output")},
          "cached": bool(read.get("cached")), "error": read.get("error")})
    words = [w for w in terms.words(question) if w not in terms.STOP and w not in terms.GENERIC] + list(read.get("terms") or [])
    jobs = plan(items, person, words)
    emit({"type": "matched", "items": [{k: i[k] for k in ("type", "id", "label", "score")} for i in items[:12]], "kinds": kinds})
    cards = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        def one(job):
            name, kw = job
            emit({"type": "step", "step": name, "sources": SOURCES.get({"cancers": "cancer", "labs": "lab", "nutrients": "nutrient", "themes": "theme"}.get(name, name), [])})
            return getattr(providers, name)(person, **kw)
        for got in pool.map(one, jobs):
            cards += got
        if studies:
            # What the studies should be about follows the kind of question: for a propensity, what lowers the risk or
            # catches it early; for an action, the trials of it; for a gene, its variants
            focus = {"propensity": "prevention OR screening OR \"risk factors\" OR modifiable OR lifestyle",
                     "rank": "prevention OR screening OR \"risk factors\"",
                     "action": "trial OR intervention OR guideline OR recommendation"}.get(kinds[0])
            todo = [c for c in cards if c.get("topic")][:8]
            for c in todo:
                if focus and c["provider"] in ("condition", "cancer", "lab", "nutrient", "fitness"):
                    c["focus"] = focus
            if todo:
                emit({"type": "step", "step": "studies", "sources": SOURCES["studies"]})
            # A time budget: what isn't back in time is left out of this answer and keeps caching for the next one
            futs = {_BACKGROUND.submit(_studies, c): c for c in todo}
            done, _ = wait(futs, timeout=STUDY_BUDGET)
            for f in done:
                futs[f]["studies"] = f.result()
            late = len(futs) - len(done)
            if late:
                emit({"type": "step", "step": "studies_late", "sources": [], "late": late})
    # Within a ranking, order by the person's value; otherwise by how much needs attention
    order = {"high": 0, "differs": 0, "raised": 1, "low": 1, "lowered": 2, "typical": 3, "unknown": 4}
    cards.sort(key=lambda c: (order.get(c["level"], 5), -(c["value"] or 0)) if kinds[0] != "rank" else (-(c["value"] or -1),))
    out = {"question": question, "person": person, "kinds": kinds, "unknowns": unknowns,
           "verdict": verdict(kinds, unknowns, cards), "cards": cards,
           "items": [{k: i.get(k) for k in ("type", "id", "label", "score")} for i in items[:12]],
           "seconds": round(time.time() - t0, 1), "tokens": read.get("input", 0) + read.get("output", 0),
           "understood": {"by": "model" if any(i.get("from") == "model" for i in items) else "rules",
                          "reading": read.get("reading"), "plan": read.get("plan") or [],
                          "cached": bool(read.get("cached")), "error": read.get("error"), "tokens": read}}
    out["deep"], out["deep_reason"] = needs_deep(kinds, cards)
    out["summary"] = summary(cards)
    emit({"type": "done", "seconds": out["seconds"]})
    return out


def _studies(c):
    try:
        return evidence.studies(c["topic"], c.get("focus"), limit=2)
    except Exception as e:
        return [{"error": f"{type(e).__name__}"}]
