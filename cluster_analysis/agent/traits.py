"""Ask and the Biomarkers tab's trait scores: where the person's genes place them among Europeans on a GWAS Catalog
trait (inheritance/predict.py person_scores -> the trait_scores dataset), for the traits a question names.

The card for the screen carries the numbers the Ask tab draws (the scale, the genes that push the score). The model
gets, as for every personal tool: with Restricted mode on, only the kind of result shown plus the public facts (the
trait's definition and study); off, the interpreted result ("Top 17% · longer sleep") and the variants behind it.
"""
from cluster_analysis.agent import pair, providers

ITEMS = 6
PER_PHRASE = 2


def _band(p, more, less):
    return pair.band(p, more, less)


def find(person, about):
    rows = [r for r in providers.rows("trait_scores", person) if isinstance(r, dict) and r.get("person") == person]
    out, seen = [], set()
    for phrase in about[:ITEMS]:
        scored = []
        for r in rows:
            f = r.get("featured") if isinstance(r.get("featured"), dict) else pair._j(r.get("featured")) or {}
            f = f if isinstance(f, dict) else {}
            h, rep = pair._hit(phrase, r.get("trait"), f.get("name")), pair._hit(phrase, r.get("reported"))
            if h or rep:
                scored.append((-h, -rep, 0 if f else 1, -(pair._num(r.get("n")) or 0), id(r), r, f))
        if any(x[0] for x in scored):
            scored = [x for x in scored if x[0]]
        if any(x[0] and x[2] == 0 for x in scored):   # a featured trait the phrase names stands alone
            scored = [x for x in scored if x[0] and x[2] == 0]
        for *_, r, f in sorted(scored, key=lambda x: x[:5])[:PER_PHRASE]:
            if r["id"] not in seen and len(out) < ITEMS:
                seen.add(r["id"])
                out.append((r, f))
    return out


def card(r, f):
    pct = pair._num(r.get("pct"))
    more, less = f.get("more") or "higher", f.get("less") or "lower"
    name = f.get("name") or r.get("reported") or r.get("trait")
    top = pair._j(r.get("top")) or []
    top = top if isinstance(top, list) else []
    rows_ = [{"label": f"{v.get('gene') or '?'} ({v.get('rsid')})",
              "value": f"{v.get('copies')} of 2 copies of {v.get('allele')}, which {'raises' if v.get('raises') else 'lowers'} it",
              "note": f"European average {v.get('average')} copies"} for v in top[:8] if v.get("copies") is not None]
    data = {"kind": "trait_score", "name": name, "more": more, "less": less, "pct": pct, "trait": r.get("trait"),
            "definition": r.get("definition"), "pmid": r.get("pmid"), "author": r.get("author"), "year": r.get("year"),
            "n": pair._num(r.get("n")), "used": pair._num(r.get("used")), "variants": pair._num(r.get("variants")),
            "impact": pair.impact_of(r),
            "top": [{"gene": v.get("gene"), "copies": v.get("copies"), "raises": v.get("raises"), "shift": v.get("shift")} for v in top[:8]]}
    return providers.card("trait", r["id"], name, level="differs", value=pct, headline=_band(pct, more, less), rows=rows_, data=data,
                          links=[{"tab": "biomarkers", "params": {}, "label": "Open Biomarkers"}])


def t_my_traits(ctx, about):
    hits = find(ctx["person"], [str(a) for a in about if str(a).strip()])
    cards = [card(r, f) for r, f in hits]
    ctx["cards"] += cards
    for r, _ in hits:
        if r.get("pmid"):
            ctx["ledger"].ref(f"PMID:{r['pmid']}", f"PMID {r['pmid']}: {r.get('author')} {r.get('year')}, GWAS of {r.get('reported') or r.get('trait')}",
                              f"https://europepmc.org/article/MED/{r['pmid']}")
    from cluster_analysis.agent import tools
    out = tools._shape(cards)
    out["public"] = [{"trait": r.get("trait"), "definition": r.get("definition"), "ref": f"PMID:{r['pmid']}" if r.get("pmid") else None,
                      "study": f"{r.get('author')} {r.get('year')}", "impact": pair.impact_of(r)} for r, _ in hits]
    if not hits:
        out["note"] = "No trait score matches; name the trait as usually written (height, sleep duration, LDL cholesterol)."
    return out
