"""Ask and the Inheritance tab: what a child of two profiles could inherit, for the items a question names.

The child is worked out on this machine from the two profiles picked in Ask (one XX, one XY). Its results go to the
model only with Restricted mode off (settings.share_results), like every other result, and even then as the
interpreted result and nothing under it:

  trait predictions   the child's band and ranges ("Top 17% · taller"), each parent's band, how many of the study's
                      variants are settled, left to chance or unread; the study and the trait's definition
  conditions          the gene, the conditions and their modes (HPO), which parent carries a reviewed pathogenic
                      variant, and the child's odds
  single-gene traits  the gene, the mode, which parent carries the variant, the child's odds
  drug genes          each parent's metaboliser type and the child's types with their odds

Never: an rsID, a genotype or allele letter, a star allele, a profile id or name (the parents are "the XX parent" and
"the XY parent"), or any item the question didn't name. With Restricted mode on the model gets the public part only
(which traits, conditions and genes exist, their definitions and studies) and the person sees the result.

trait_model is a public tool: the GWAS Catalog study and EFO definition behind a trait's prediction, from the
person-free models file (inheritance/predict.py), never from a pair's results.
"""
import gzip
import json
import os
import re

from cluster_analysis.agent import providers

ITEMS = 8           # items per call, all kinds together
PER_PHRASE = 3      # trait predictions per phrase
_MODELS = {}


def _j(v):
    if isinstance(v, str) and v[:1] in "[{":
        try:
            return json.loads(v)
        except ValueError:
            return v
    if v in ("None", "", None):
        return None
    return v


def _num(v):
    v = _j(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pairs():
    """The pairs the explorer has results for: [{"pair", "xx", "xy"}]."""
    return [{"pair": r["pair"], "xx": r["xx"], "xy": r["xy"]} for r in providers.rows("inh_meta", None) if isinstance(r, dict) and r.get("pair")]


def pair_of(person, picked=None):
    """The pair a child question is about: the XX and XY picked in Ask when the explorer has results for them, else
    the person with the first profile of the other sex."""
    ps = pairs()
    if picked:
        hit = next((p for p in ps if p["xx"] == picked.get("xx") and p["xy"] == picked.get("xy")), None)
        if hit:
            return hit
    return next((p for p in ps if person in (p["xx"], p["xy"])), None)


def band(p, more="higher", less="lower"):
    """The exact percentile as 'Top N% · more' or 'Bottom N% · less' (CLAUDE.md)."""
    if p is None:
        return None
    return f"Top {max(1, round(100 - p))}% · {more}" if p >= 50 else f"Bottom {max(1, round(p))}% · {less}"


def _featured():
    meta = next(iter(providers.rows("inh_meta", None)), None) or {}
    return {f["id"]: f for f in (_j(meta.get("featured")) or [])}


def _words(s):
    return set(re.findall(r"[a-z0-9]{3,}", str(s or "").lower()))


def _hit(phrase, *texts):
    """How well a phrase names an item: 3 the whole name, 2 inside a name, 1 all its words in it, 0 none."""
    q = phrase.strip().lower()
    best = 0
    for t in texts:
        t = str(t or "").lower()
        if not t or not q:
            continue
        if q == t:
            return 3
        if q in t:
            best = max(best, 2)
        elif _words(q) and _words(q) <= _words(t):
            best = max(best, 1)
    return best


def find(pair, about):
    """The pair's rows the phrases name: [(kind, row)], at most ITEMS."""
    feat = _featured()
    own = lambda name: [r for r in providers.rows(name, None) if isinstance(r, dict) and r.get("pair") == pair["pair"]]
    out, seen = [], set()

    def add(kind, r, key):
        if (kind, key) not in seen and len(out) < ITEMS:
            seen.add((kind, key))
            out.append((kind, r))

    for phrase in about[:ITEMS]:
        for r in own("inh_drugs"):
            if _hit(phrase, r.get("gene")) == 3:
                add("drug", r, r["gene"])
        for r in own("inh_conditions"):
            names = [c.get("name") for c in _j(r.get("conditions")) or []] + list(_j(r.get("clinvar_names")) or [])
            if _hit(phrase, r.get("gene")) == 3 or max([_hit(phrase, n) for n in names] or [0]) >= 2:
                add("condition", r, r["gene"])
        for r in own("inh_traits"):
            if _hit(phrase, r.get("gene")) == 3 or max(_hit(phrase, r.get("name"), r.get("about"), r.get("omim_name")), 0) >= 1:
                add("trait", r, r["id"])
        # The trait's own name first (EFO, or the featured name), the study's reported name only when nothing else matches
        scored = []
        for r in own("inh_predictions"):
            # one row per trait: a daughter's where a trait has a row per sex (the X), Ask not knowing the child's sex
            if r.get("child_sex") not in (None, "any", "XX"):
                continue
            f = feat.get(r["id"])
            h, rep = _hit(phrase, r.get("trait"), f and f.get("name")), _hit(phrase, r.get("reported"))
            if h or rep:
                scored.append((-h, -rep, 0 if f else 1, -(_num(r.get("n")) or 0), r))
        if any(x[0] for x in scored):
            scored = [x for x in scored if x[0]]
        # A featured trait the phrase names (Height, Sleep length) stands alone: its near relatives are noise
        if any(x[0] and x[2] == 0 for x in scored):
            scored = [x for x in scored if x[0] and x[2] == 0]
        for *_, r in sorted(scored, key=lambda x: x[:4])[:PER_PHRASE]:
            add("prediction", r, r["id"])
    return out


def _who(pair, person):
    return "the XX parent" if person == pair["xx"] else "the XY parent" if person == pair["xy"] else "neither parent"


def _copies(v):
    v = _num(v)
    return "not readable from the file" if v is None else f"{int(v)} of 2 copies"


def impact_of(r):
    """The GWAS impact of a trait's scale, for the model: how much of the differences between people the study's lead
    variants explain, its level (the user's: high 8% and over, modest 3-8%, little under 3%) and its rank among all
    scored traits; or why there is none. Public: a property of the study (inheritance/gwas_impact.py)."""
    v = _num(r.get("impact"))
    if v is None:
        flag = _j(r.get("impact_flag"))
        return {"explains_pct": None, "why_none": flag} if flag else None
    from cluster_analysis.inheritance import gwas_impact
    s = (gwas_impact.summary() or {}).get("all") or {}
    return {"explains_pct": v, "level": "high" if v >= 8 else "modest" if v >= 3 else "little",
            "higher_than_pct_of_traits": _num(r.get("impact_rank")), "median_trait_pct": s.get("median"), "mean_trait_pct": s.get("mean"),
            "what_it_is": "the share of the differences between people that the study's lead variants explain, from their "
                          "strength and the study's size; the rest is weaker variants, environment and chance"}


def _public(kind, r):
    """What exists for the item for everyone: its name, definition and study, nothing about the pair."""
    if kind == "prediction":
        return {"item": r.get("trait"), "kind": "trait prediction (GWAS Catalog)", "category": r.get("category"),
                "definition": _j(r.get("definition")), "study": {"pmid": r.get("pmid"), "author": r.get("author"), "year": r.get("year"),
                                                                 "sample": r.get("sample"), "variants": _j(r.get("variants"))},
                "impact": impact_of(r)}
    if kind == "condition":
        return {"item": r.get("gene"), "kind": "inherited condition (ClinVar, HPO modes)",
                "conditions": [c.get("name") for c in _j(r.get("conditions")) or []], "modes": _j(r.get("modes")), "on_x": _j(r.get("on_x")) is True or r.get("on_x") == "True"}
    if kind == "trait":
        return {"item": r.get("name"), "kind": "single-gene trait (OMIM, HPO modes)", "about": r.get("about"), "gene": r.get("gene"), "modes": _j(r.get("modes"))}
    return {"item": r.get("gene"), "kind": "drug gene (CPIC diplotypes)"}


def _odds(v):
    """The child's odds, or why there are none (a parent's copies unread)."""
    v = _j(v)
    flat = json.dumps(v)
    return "not computable: a parent's copies are not readable from the file" if v is None or "null" in flat else v


def interpreted(kind, r, pair):
    """The pair's result for the item, as words and odds only (see the module's docstring)."""
    out = _public(kind, r)
    if kind == "prediction":
        f = _featured().get(r["id"]) or {}
        more, less = f.get("more") or "higher", f.get("less") or "lower"
        p = lambda k: _num(r.get(k))
        out |= {"child": band(p("child_pct"), more, less),
                "child_middle_80": f"{band(p('child_lo'), more, less)} to {band(p('child_hi'), more, less)}",
                "child_middle_98": f"{band(p('child_lo98'), more, less)} to {band(p('child_hi98'), more, less)}",
                "the XX parent": band(p("XX_pct"), more, less), "the XY parent": band(p("XY_pct"), more, less),
                "pushes": {"the XX parent": p("push_XX"), "the XY parent": p("push_XY")},
                "variants": {"settled": _num(r.get("n_settled")), "left_to_chance": _num(r.get("n_chance")), "unread": _num(r.get("n_unread"))}}
    elif kind == "condition":
        out |= {"the XX parent": _copies(r.get("XX_copies")), "the XY parent": _copies(r.get("XY_copies")),
                "copies_of": "a reviewed pathogenic variant", "child_outcomes": _odds(r.get("outcomes")), "confidence": _num(r.get("confidence"))}
    elif kind == "trait":
        v = (_j(r.get("variants")) or [{}])[0]
        out |= {"the XX parent": _copies(r.get("XX_copies")), "the XY parent": _copies(r.get("XY_copies")),
                "copies_of": f"the variant linked to {v.get('condition') or r.get('omim_name')}".lower(),
                "child_outcomes": _odds(r.get("outcomes")), "confidence": _num(r.get("confidence"))}
    else:
        out |= {"the XX parent": r.get("XX_type"), "the XY parent": r.get("XY_type"),
                "child_types": [{"type": t.get("type"), "odds": t.get("p")} for t in _j(r.get("types")) or []]}
    return out


def card(kind, r, pair):
    """The card for the person's screen (on this machine: it may name the profiles and show the variants)."""
    who = f"Child of {pair['xx']} and {pair['xy']}"
    res = interpreted(kind, r, pair)
    rows_ = [{"label": k, "value": json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)}
             for k, v in res.items() if k not in ("item", "kind", "definition", "study") and v not in (None, [], {})]
    head = res.get("child") or ("; ".join(f"{t['type']} {round(100 * (t['odds'] or 0))}%" for t in res.get("child_types") or [])) or res.get("kind")
    # What the Ask tab draws (the Inheritance tab's scale, odds bars): numbers for the screen, never sent to the model
    data = {"kind": kind, "xx": pair["xx"], "xy": pair["xy"], "name": res["item"]}
    if kind == "prediction":
        f = _featured().get(r["id"]) or {}
        data |= {"impact": impact_of(r), "name": f.get("name") or r.get("reported") or r.get("trait"), "more": f.get("more") or "higher", "less": f.get("less") or "lower",
                 **{k: _num(r.get(k)) for k in ("child_pct", "child_lo", "child_hi", "child_lo98", "child_hi98", "XX_pct", "XY_pct")}}
    elif kind in ("condition", "trait"):
        data |= {"modes": _j(r.get("modes")), "outcomes": _j(r.get("outcomes")), "XX_copies": _num(r.get("XX_copies")),
                 "XY_copies": _num(r.get("XY_copies")), "about": r.get("about"), "gene": r.get("gene"),
                 "conditions": [c.get("name") for c in _j(r.get("conditions")) or []]}
    else:
        data |= {"XX_type": r.get("XX_type"), "XY_type": r.get("XY_type"), "types": _j(r.get("types")) or []}
    return providers.card("inheritance", f"{pair['pair']}:{kind}:{r.get('id') or r.get('gene')}", f"{who}: {res['item']}", level="differs",
                          value=_num(r.get("child_pct")), headline=head, rows=rows_, pair=True, data=data,
                          links=[{"tab": "inheritance", "params": {"ih_xx": pair["xx"], "ih_xy": pair["xy"]}, "label": "Open Inheritance"}])


def t_my_child(ctx, about):
    """The personal pair tool (tools.TOOLS["my_child"])."""
    person = ctx["person"]
    pair = pair_of(person, ctx.get("pair"))
    if not pair:
        return {"error": "No child results: the explorer needs an XX and an XY profile, picked in Ask."}
    hits = find(pair, [str(a) for a in about if str(a).strip()])
    cards = [card(k, r, pair) for k, r in hits]
    ctx["cards"] += cards
    shared = bool(ctx.get("share"))
    ctx["pair_shared"] = bool(shared)
    for k, r in hits:
        if k == "prediction" and r.get("pmid"):
            ctx["ledger"].ref(f"PMID:{r['pmid']}", f"PMID {r['pmid']}: {r.get('author')} {r.get('year')}, GWAS of {r.get('reported') or r.get('trait')}",
                              f"https://europepmc.org/article/MED/{r['pmid']}")
    out = {"shown_to_person": True, "asker_is": _who(pair, person), "found": len(hits),
           "public": [_public(k, r) for k, r in hits] if not shared else None}
    if not hits:
        out["note"] = "None of these names an item in the pair's results; name traits, conditions or gene symbols as written."
    elif shared:
        out |= {"results": [interpreted(k, r, pair) for k, r in hits],
                "note": "Cite the child's bands, ranges and odds as 'yours' in highlights (they are the pair's results, not a "
                        "paper's figures); cite a study's ref only for what the study reports. Ranks are the share of Europeans on that side of the average; "
                        "child odds are Mendel's rules over both parents' copies. Write them as given."}
    else:
        out["note"] = ("The child's results are on the person's screen, not here (Restricted mode). Explain from the public part.")
    return {k: v for k, v in out.items() if v is not None}


# --- Public ----------------------------------------------------------------------------------------------------------

def _models():
    from cluster_analysis.inheritance import predict
    if not os.path.exists(predict.MODELS):
        return []
    stamp = os.path.getmtime(predict.MODELS)
    if _MODELS.get("stamp") != stamp:
        with gzip.open(predict.MODELS, "rt", encoding="utf-8") as f:
            _MODELS.update(stamp=stamp, models=json.load(f)["models"])
    return _MODELS["models"]


def t_trait_model(ctx, trait):
    """The study and definition behind a trait's prediction, for everyone."""
    scored = sorted(((-_hit(trait, m.get("trait"), m.get("reported")), -(_num(m.get("n")) or 0), i) for i, m in enumerate(_models())
                     if _hit(trait, m.get("trait"), m.get("reported"))))[:4]
    from cluster_analysis.inheritance import gwas_impact
    imp = gwas_impact.load()
    out = []
    for *_, i in scored:
        m = _models()[i]
        ref = f"PMID:{m['pmid']}" if m.get("pmid") else None
        if ref:
            ctx["ledger"].ref(ref, f"PMID {m['pmid']}: {m.get('author')} {m.get('year')}, GWAS of {m.get('reported') or m.get('trait')}",
                              f"https://europepmc.org/article/MED/{m['pmid']}")
        out.append({"trait": m.get("trait"), "efo": m.get("id"), "category": m.get("category"), "definition": m.get("definition"),
                    "study": m.get("study"), "ref": ref, "author": m.get("author"), "year": m.get("year"), "sample": m.get("sample"),
                    "variants": len(m.get("variants") or []), "weights": "beta" if m.get("kind") == "beta" else "ln(odds ratio)",
                    "impact": impact_of({"impact": (100 * imp[m["id"]]["r2_lead"]) if m["id"] in imp and not imp[m["id"]].get("flag") else None,
                                         "impact_flag": (imp.get(m["id"]) or {}).get("flag"), "impact_rank": (imp.get(m["id"]) or {}).get("rank_pct")})})
    return {"models": out, "how": ("Each trait uses one large European study (≥10,000 people) from the GWAS Catalog, its lead "
                                   "variants one per 500 kb. A child gets one copy from each parent at every variant (Mendel), "
                                   "the copies add up, and the sum is ranked against Europeans by a normal approximation.")} if out \
        else {"models": [], "note": "No trait model matches; try the trait's usual name (e.g. height, LDL cholesterol)."}
