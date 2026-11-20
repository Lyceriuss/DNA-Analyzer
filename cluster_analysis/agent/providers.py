"""The explorer's packages as providers: each turns the items a question matched into result cards, from the person's
own results on this machine (the explorer's datasets) and public facts.

Every card has the same shape, whatever answered it:
  {"provider", "id", "title", "level", "value", "headline", "rows": [{label, value, note}], "known": [..],
   "unknown": [..], "links": [{tab, params, label}], "topic": public search topic or None, "focus": search focus}
level is how the person stands on it: "high", "raised", "typical", "lowered", "low", "differs" (medicines),
"unknown" (no data). value orders cards for a ranking (a percentile, a count).

topic is set only from what the question matched (a named condition, drug, cancer type, mechanism), never from which of
the person's results stand out, so a study search can't reveal anything about their genome.
"""
import json
import math
import os
import re

from genome import build as gbuild

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASETS = os.path.join(ROOT, gbuild.EXPLORER, "datasets")
_DATA = {}


def rows(name, person):
    """A dataset's rows for one person (or its rows without a person)."""
    path = os.path.join(DATASETS, name + ".json")
    if not os.path.exists(path):
        return []
    stamp = os.path.getmtime(path)
    if _DATA.get(name, (None,))[0] != stamp:
        with open(path, encoding="utf-8") as f:
            _DATA[name] = (stamp, json.load(f))
    data = _DATA[name][1]
    return [r for r in data if not isinstance(r, dict) or r.get("person") in (None, person)]


def _j(x, default=None):
    if isinstance(x, (list, dict)):
        return x
    try:
        return json.loads(x) if x else default
    except (TypeError, ValueError):
        return default


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def band(pct, higher="worse"):
    if pct is None:
        return "unknown"
    lvl = "high" if pct >= 90 else "raised" if pct >= 75 else "low" if pct <= 10 else "lowered" if pct <= 25 else "typical"
    return lvl


def card(provider, ident, title, **kw):
    return {"provider": provider, "id": ident, "title": title, "level": kw.pop("level", "unknown"), "value": kw.pop("value", None),
            "headline": kw.pop("headline", ""), "rows": kw.pop("rows", []), "known": kw.pop("known", []),
            "unknown": kw.pop("unknown", []), "links": kw.pop("links", []), "topic": kw.pop("topic", None),
            "focus": kw.pop("focus", None), **kw}


# --- Scores: cancer types, lab tests, nutrients, fitness ---------------------------------------------------------

def _score_cards(provider, dataset, person, ids, tab, param, topic_of=None):
    out = []
    for t in rows(dataset, person):
        if ids is not None and t["id"] not in ids:
            continue
        for m in _j(t.get("markers"), []):
            sc = m.get("score") or {}
            pct = sc.get("percentile")
            higher = m.get("higher", "worse")
            top = sc.get("top") or []
            moving = [f"{v.get('gene') or v['rsid']} ({v['rsid']}): {v['copies']} of 2 copies of {v['allele']}, which "
                      f"{'raises' if v.get('raises') else 'lowers'} it" for v in top[:4] if v.get("copies")]
            lvl = band(pct)
            good_side = (higher == "better") == (lvl in ("high", "raised"))
            head = ("No genetic score for this." if pct is None else
                    f"The genes put {m['name'] if m['name'][:2].isupper() else m['name'][0].lower() + m['name'][1:]} at the {ordinal(pct)} percentile of Europeans"
                    + (" (the favourable side)." if lvl != "typical" and good_side else " (the unfavourable side)." if lvl != "typical" else ", in the usual range."))
            known = [f"Score from {sc.get('used')} of {sc.get('variants')} variants of a published score." ] if pct is not None else []
            unknown = ["The score covers inherited variants only: diet, weight, smoking, medicines and age move the real level or risk."]
            out.append(card(provider, f"{t['id']}:{m['id']}", m["name"] if m["name"] != t["name"] else t["name"],
                            group=t.get("group") or t["name"], level=lvl, value=pct, higher=higher, headline=head,
                            rows=[{"label": "Percentile", "value": pct}, *[{"label": "Variant", "value": x} for x in moving]],
                            known=known, unknown=unknown,
                            links=[{"tab": tab, "params": {param: t["id"]}, "label": f"Open {t['name']}"}],
                            topic=(topic_of or (lambda t, m: None))(t, m)))
    return out


def cancers(person, ids=None, **_):
    """Each cancer type's score, with what lowers that cancer: the European Code Against Cancer's recommendations
    for the causes IARC lists for it (themes/cancer_prevention.json)."""
    prev, recs = {}, {}
    path = os.path.join(ROOT, "cluster_analysis", "themes", "cancer_prevention.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        prev = {v["name"]: v for v in (d.get("cancers") or {}).values()}
        recs = {r["n"]: r for r in d.get("recommendations") or []}
    names = {t["id"]: t["name"] for t in rows("can_tests", person)}
    out = _score_cards("cancer", "can_tests", person, ids, "clusters", "can_n",
                       topic_of=lambda t, m: t["name"].lower())
    for c in out:
        p = prev.get(names.get(c["id"].split(":")[0]))
        # Risk factors, not instructions: the causes IARC lists with sufficient evidence
        causes = (p or {}).get("agents") or []
        c["advice"] = [{"label": "Known cause (IARC)", "value": a, "note": "sufficient evidence"} for a in causes[:8]]
        if not causes and p:
            c["unknown"].append("IARC lists no avoidable cause with sufficient evidence for this cancer.")
        c["focus"] = "polygenic risk OR screening OR prevention"
    return out


def labs(person, ids=None, **_):
    out = _score_cards("lab", "lab_tests", person, ids, "biomarkers", "lb_n", topic_of=lambda t, m: m["name"])
    for c in out:
        c["focus"] = "genetic OR genotype OR polygenic"
    return out


def nutrients(person, ids=None, **_):
    out = _score_cards("nutrient", "nut_nutrients", person, ids, "nutrition", "nt_n", topic_of=lambda t, m: t["name"])
    for c in out:
        c["focus"] = "supplementation OR intake OR genotype"
    return out


def fitness(person, ids=None, **_):
    out = _score_cards("fitness", "fit_tests", person, ids, "clusters", "fit_n", topic_of=lambda t, m: m["name"])
    for c in out:
        c["focus"] = "training OR exercise OR genotype"
    return out


# --- Medicines ---------------------------------------------------------------------------------------------------

def medicines(person, ids=None, **_):
    """Named drugs: a card per drug with the guidance for the person's genes. No drug named ("which medicines should
    I be careful with"): a card per gene whose result changes guidance, with every drug it affects and what to do,
    so the answer reads by cause (one gene's result and the drugs it affects) rather than as a list of drugs."""
    guid = rows("med_guidance", person)
    phen = {g["gene"]: g for g in rows("med_genes", person)}
    grade = {"A+": 5, "A": 4, "B": 3, "C": 2, "D": 1}

    def recs_of(g):
        """What to do: the guideline's recommendation for the person's type, else the label's or guideline's summary."""
        rs = [r["recommendation"] for r in _j(g.get("recs"), []) if r.get("recommendation")]
        if not rs and g.get("summary"):
            rs = [re.split(r"(?<=[.!?])\s+", g["summary"].strip())[0]]
        return rs

    if ids is not None:
        out = []
        for drug in sorted(ids):
            # A guideline can cover several drugs ("celecoxib;flurbiprofen;ibuprofen;lornoxicam")
            gs = [g for g in guid if drug in [d.strip() for d in g["drug"].split(";")]]
            act = [g for g in gs if g["status"] == "differs"]
            unread = [g for g in gs if g["status"] == "unreadable"]
            genes = sorted({x.strip() for g in (act or gs) for x in re.split(r"[;,]", g.get("genes") or "") if x.strip()})
            lvl = "differs" if act else "typical" if any(g["status"] == "typical" for g in gs) else "unknown"
            head = (f"Your genes call for a change with {drug} ({', '.join(genes)})." if act else
                    f"With {drug}, the guidance for your genes is the standard one." if lvl == "typical" else
                    f"There is no pharmacogenetic guidance for {drug}, or your file can't read the genes it depends on.")
            unread_genes = sorted({x.strip() for g in unread for x in re.split(r"[;,]", g.get("genes") or "") if x.strip()})
            out.append(card("medicines", drug, drug, level=lvl, value=10 if act else 0, headline=head, unread_genes=unread_genes, genes=genes,
                            rows=[{"label": g.get("source") or g["kind"], "value": r, "note": g.get("types")}
                                  for g in (act or gs)[:3] for r in recs_of(g)[:1]],
                            known=[f"{x}: {phen[x]['alleles']}, {phen[x]['phenotype']}" for x in genes if x in phen],
                            unknown=(["Part of the guidance depends on genes or gene copies a genotyping chip can't read."] if unread else []),
                            links=[{"tab": "medicines", "params": {"md_drug": drug}, "label": f"Open {drug}"}],
                            topic=drug, focus="pharmacogenetic OR genotype"))
        return out
    by_gene = {}
    for g in guid:
        if g["status"] != "differs":
            continue
        genes = [x.strip() for x in re.split(r"[;,]", g.get("genes") or "") if x.strip()]
        # Guidance on several genes belongs to the ones whose result isn't the usual type, not to a gene with the usual
        # result
        odd = [x for x in genes if not (phen.get(x) or {}).get("typical")]
        for x in odd or genes:
            by_gene.setdefault(x, []).append(g)
    out = []
    for gene_, gs in by_gene.items():
        drugs = {}
        for g in sorted(gs, key=lambda g: -grade.get(g.get("grade"), 0)):
            d = drugs.setdefault(g["drug"], {"grade": g.get("grade"), "recs": []})
            for r in recs_of(g)[:1]:
                if r not in d["recs"]:
                    d["recs"].append(f"{g.get('source') or g['kind']}: {r}")
        p = phen.get(gene_)
        best = max(grade.get(d["grade"], 0) for d in drugs.values())
        out.append(card("medicines", gene_, f"{gene_}" + (f": {p['phenotype']}" if p else ""), level="differs",
                        value=best * 10 + len(drugs),
                        headline=f"Your {gene_}" + (f" ({p['alleles']}, {p['phenotype'].lower()})" if p else "")
                                 + f" changes the guidance for {len(drugs)} medicine{'s' if len(drugs) != 1 else ''}: "
                                 + ", ".join(list(drugs)[:8]) + ("…" if len(drugs) > 8 else "") + ".",
                        rows=_drug_rows(drugs),
                        drugs=list(drugs), gene=gene_,
                        known=[f"{len(drugs)} drugs with CPIC, DPWG or drug-label guidance that depends on {gene_}."],
                        unknown=([p["note"]] if p and p.get("note") else []),
                        links=[{"tab": "medicines", "params": {"md_gene": gene_}, "label": f"Open {gene_} in Medicines"}],
                        topic=None))
    unread = sorted({d.strip() for g in guid if g["status"] == "unreadable" for d in g["drug"].split(";") if d.strip()})
    if unread:
        out.append(card("medicines", "unreadable", "Not readable from this file", level="unknown", value=0,
                        headline=f"For {len(unread)} medicines the guidance depends on genes a genotyping chip can't read "
                                 "reliably (gene copies, deletions, HLA types), so these results are unknown.",
                        rows=[{"label": "Among them", "value": ", ".join(unread[:12]) + (f" and {len(unread) - 12} more" if len(unread) > 12 else "")}],
                        unknown=["Only a dedicated pharmacogenetic test reads these genes with certainty."]))
    return out


def _drug_rows(drugs):
    """A row per drug with an instruction to act on; drugs whose guidance gives none here (only an allele name, as some
    labels do) are counted in a last row that points to the Medicines tab."""
    rows_, rest = [], 0
    for d, v in drugs.items():
        rec = next((r for r in v["recs"] if len(r.split()) >= 6), None)
        if rec and len(rows_) < 6:
            rows_.append({"label": d, "value": rec, "note": v["grade"]})
        else:
            rest += 1
    if rest:
        rows_.append({"label": f"{rest} more", "value": "Open the gene in Medicines for their guidance."})
    return rows_


# --- Clusters, genes and pathways --------------------------------------------------------------------------------

def _graph(theme):
    path = os.path.join(ROOT, "cluster_analysis", "themes", f"theme_graph_{theme}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def themes(person, theme=None, mechanism=None, level=None, **_):
    """Where in a cluster the person's variants change genes: per mechanism, how many genes and which have the
    strongest evidence (the explorer's own tables first, then experiments, then Open Targets genetics). One mechanism
    or trait when the question named one, else the whole cluster."""
    g = _graph(theme)
    names = {m["id"]: m["name"] for m in g.get("mechanisms") or []} | {o["id"]: o["name"] for o in g.get("organs") or []}
    mine = [r for r in rows("theme_genes", person) if r["theme"] == theme]
    graded = {r["gene"]: r for r in rows("sport_snps", person)} if theme == "muscle" else {}
    by = {}
    for r in mine:
        ev = _j(r.get("evidence"), {}) or {}
        mechs = list((ev.get("mechanisms") or {}).keys()) or ([r["primary"]] if r.get("primary") not in (None, "disease") else [])
        if level == "trait" and mechanism and mechanism not in (ev.get("diseases") or {}):
            continue
        if level in ("mechanism", "phase") and mechanism and mechanism not in mechs and mechanism not in (ev.get("organs") or []):
            continue
        if r.get("function") not in ("LoF", "GoF", "altered") and not r.get("interpretation"):
            continue
        strength = 3 if r["gene"] in graded else 2 if any(v.get("evidence") == "human experiment" for v in (ev.get("mechanisms") or {}).values()) \
            else 1 + min(1, max([d.get("genetic") or 0 for d in (ev.get("diseases") or {}).values()] or [0]))
        for m in mechs or ["other"]:
            by.setdefault(m, []).append((strength, r))
    rows_ = []
    for m, rs in sorted(by.items(), key=lambda kv: -sum(s for s, _ in kv[1])):
        rs.sort(key=lambda x: -x[0])
        rows_.append({"label": names.get(m, "Genetics only (no mechanism placed)" if m == "other" else m),
                      "value": f"{len(rs)} gene{'s' if len(rs) != 1 else ''} changed",
                      "note": ", ".join(f"{r['gene']} ({'less' if r.get('function') == 'LoF' else 'more' if r.get('function') == 'GoF' else 'changed'})"
                                        for _, r in rs[:4])})
    n = len({r["gene"] for rs in by.values() for _, r in rs})
    name = g.get("name", theme)
    scope = names.get(mechanism, mechanism) if mechanism else None
    top = [x["label"] for x in rows_[:3] if not x["label"].startswith("Genetics only")]
    out = [card("theme", f"{theme}:{mechanism or ''}", name + (f": {scope}" if scope else ""),
                level="differs" if n else "typical", value=n,
                headline=(f"In the {name} cluster your variants change {n} genes, most of them in " + ", ".join(top).lower() + "."
                          if n and top else f"Your variants change {n} genes in the {name} cluster." if n else
                          f"None of your variants is known to change a gene in the {name} cluster" + (f" ({scope})" if scope else "") + "."),
                rows=rows_[:8], theme=theme, mechanism=mechanism,
                unknown=["Most of these changes are small: they show where your genes lean, not what you will notice."],
                links=[{"tab": "clusters", "params": {"theme": theme, **({"th_organ": mechanism} if mechanism else {})}, "label": f"Open the {name} cluster"}],
                topic=scope.lower() if scope else None)]
    if graded and not mechanism:
        good = [r for r in graded.values() if r.get("grade") in ("A", "B") and r.get("meaning")]
        out.append(card("theme", f"{theme}:graded", f"{name}: variants with practical meaning", level="differs" if good else "unknown",
                        value=len(good), headline=f"{len(good)} of the well-known {name.lower()} variants have a practical meaning for your genotype.",
                        rows=[{"label": f"{r['gene']} {r['rsid']} ({r.get('topic_name')})", "value": r["meaning"], "note": r.get("grade")}
                              for r in sorted(good, key=lambda r: (r.get("grade"), r.get("topic_order") or 0))[:8]],
                        unknown=["Grades: A, replicated genome-wide or a clinical guideline; B, one large study or a protein change."],
                        links=[{"tab": "clusters", "params": {"theme": theme}, "label": "Open the variant tables"}]))
    return out


def gene(person, symbol=None, **_):
    from cluster_analysis.agent import facts
    pub = facts.gene(facts.Ledger(), symbol, limit=6)
    mine = [r for r in rows("theme_genes", person) if r["gene"] == symbol]
    life = [r for r in rows("lifecycle_genes", person) if r["gene"] == symbol]
    sport = [r for r in rows("sport_snps", person) if r["gene"] == symbol]
    meds = [r for r in rows("med_genes", person) if r["gene"] == symbol]
    r_ = []
    for r in mine[:4]:
        r_.append({"label": f"In the {r['theme']} cluster", "value": r.get("interpretation") or r.get("function") or "typical",
                   "note": f"{r.get('rsid') or ''} {r.get('genotype') or ''}".strip()})
    for r in sport:
        r_.append({"label": f"{r['rsid']} ({r.get('topic_name')})", "value": r.get("meaning") or r.get("genotype"), "note": r.get("grade")})
    for r in meds:
        r_.append({"label": "Drug response", "value": f"{r['alleles']}: {r['phenotype']}"})
    for r in life[:3]:
        r_.append({"label": f"Pathway: {r['pathway']}", "value": r.get("interpretation") or r.get("function") or "", "note": r.get("top_pathway")})
    protein = (pub.get("protein") or {}).get("function")
    known = ([f"What the protein does (UniProt): {protein[:400]}"] if protein else []) + \
            [f"Strongest GWAS traits: " + ", ".join(t["trait"] for t in pub.get("gwas_traits", [])[:6])] if pub.get("gwas_traits") else []
    calls = [r for r in mine if r.get("function") in ("LoF", "GoF", "altered")]
    return [card("gene", symbol, symbol, level="differs" if calls or sport or meds else "typical" if mine else "unknown",
                 headline=(f"Your variants change how {symbol} works." if calls else
                           f"Your {symbol} reads as typical." if mine else f"{symbol} isn't in the explorer's clusters for this profile."),
                 rows=r_, known=known,
                 unknown=[] if mine or sport or meds else ["None of the explorer's clusters, tables or pathways covers this gene yet."],
                 links=([{"tab": "lifecycle", "params": {"lc_gene": symbol}, "label": f"{symbol} pathway"}] if life else []) +
                       [{"tab": "clusters", "params": {"theme": r["theme"], "th_gene": symbol}, "label": f"{symbol} in {r['theme']}"} for r in mine[:2]],
                 topic=symbol, focus="variant OR polymorphism OR genotype")]


# --- What studies found for the person's own genotypes ------------------------------------------------------------

def findings(person, theme=None, words=(), **_):
    """The study sentences that name the person's own genotype group, for the cluster's well-known variants
    (agent/morsels.py: researched once for everyone and cached; the uncached ones are researched in the background).
    The person's genotypes are read here: the explorer's variant table, else their file."""
    from cluster_analysis.agent import index, morsels
    have, todo = morsels.cached(theme)
    if todo:
        morsels.prefetch(theme)
    table = {r["rsid"]: r for r in rows("sport_snps", person)} if theme == "muscle" else {}
    need = [rs for rs in have if rs not in table]
    if need:
        from cluster_analysis.agent.answer import person_file
        from genome.loader import read_calls
        calls = read_calls(person_file(person), set(need), confidence=("measured", "high", "medium"))
        for rs in need:
            site = (index.query("SELECT ref, alt FROM sites WHERE rsid = ?", rs) or [{}])[0]
            gt = (calls.get(rs) or (None,))[0]
            if gt and site:
                table[rs] = {"rsid": rs, "genotype": gt, "ref": site["ref"], "alt": site["alt"], "amino_acids": None}
    want = [w.lower() for w in words if len(w) >= 4]
    hits = []
    for rs, found in have.items():
        r = table.get(rs)
        if not r or not r.get("genotype"):
            continue
        for m in morsels.apply(found, r["genotype"], r.get("ref"), r.get("alt"), r.get("amino_acids"))[:3]:
            on = sum(1 for w in want if w in m["sentence"].lower())
            hits.append({**m, "genotype": r["genotype"], "ref": r.get("ref"), "alt": r.get("alt"), "amino": r.get("amino_acids"),
                         "score": m["score"] + 1.5 * on})
    hits.sort(key=lambda m: -m["score"])
    best, genes = [], set()
    for m in hits:
        if m["gene"] in genes:
            continue
        genes.add(m["gene"])
        best.append(m)
    g = _graph(theme)
    return [card("findings", f"{theme}:findings", f"Studies on your genotypes ({g.get('name', theme)})",
                 level="differs" if best else "unknown", value=len(best),
                 headline=(f"Studies report results for your own genotype at {len(best)} of the cluster's well-known variants."
                           if best else "No study sentence names your genotype group for this cluster's variants yet."),
                 rows=[{"label": f"{m['gene']} {m['rsid']} · yours {m['genotype']}", "value": m["sentence"],
                        "note": f"{m['type']}, {m['year']}"} for m in best[:10]],
                 findings=best[:10], pending=len(todo), theme=theme,
                 unknown=[f"{len(todo)} of the cluster's {len(todo) + len(have)} variants are still being researched: ask again in a few minutes."]
                         if todo else [],
                 links=[{"tab": "clusters", "params": {"theme": theme}, "label": f"Open the {g.get('name', theme)} cluster"}])]


# --- Any condition: GWAS and ClinVar, read on this machine ----------------------------------------------------------

def condition(person, items=(), **_):
    """For conditions no score covers: the strongest genome-wide associations, how many of their risk alleles the
    person carries against the European average, and any pathogenic ClinVar variant they carry in the genes behind
    it. The person's calls are read here, offline."""
    from cluster_analysis.agent import index
    from cluster_analysis.agent.answer import person_file
    from genome.loader import read_calls
    out = []
    for it in items:
        ids = it.get("traits") or [it["id"]]
        q = " OR ".join("trait_uri LIKE ?" for _ in ids)
        gw = index.query(f"SELECT g.rsid, g.allele, g.p, g.size, g.ci, g.trait, g.pmid, g.study, g.mapped, s.ref, s.alt, s.eur_af "
                         f"FROM gwas g JOIN sites s ON s.rsid = g.rsid WHERE ({q}) ORDER BY g.p LIMIT 3000",
                         *[f"%{i}%" for i in ids])
        best = {}
        for r in gw:
            if r["allele"] in (r["ref"], r["alt"]) and r["eur_af"] is not None and r["rsid"] not in best:
                best[r["rsid"]] = r
        loci = list(best.values())[:200]
        out.append({"item": it, "loci": loci})
    rsids = {l["rsid"] for o in out for l in o["loci"]}
    calls = read_calls(person_file(person), rsids, confidence=("measured", "high", "medium")) if rsids else {}
    cards = []
    for o in out:
        it, loci = o["item"], o["loci"]
        carried = exp = var = 0.0
        top = []
        n = 0
        for l in loci:
            gt = (calls.get(l["rsid"]) or (None,))[0]
            if not gt or len(gt) != 2 or not set(gt) <= {l["ref"], l["alt"]}:
                continue
            ci = (l["ci"] or "").lower()
            risk = l["allele"]
            # An odds ratio below 1, or a beta that decreases, means the reported allele protects
            if (l["size"] is not None and l["size"] < 1 and "increase" not in ci and "decrease" not in ci) or "decrease" in ci:
                risk = l["alt"] if risk == l["ref"] else l["ref"]
            f = l["eur_af"] if risk == l["alt"] else 1 - l["eur_af"]
            c = gt.count(risk)
            carried += c
            exp += 2 * f
            var += 2 * f * (1 - f)
            n += 1
            if len(top) < 6:
                top.append({"label": f"{(l['mapped'] or '').split(',')[0].strip() or l['rsid']} ({l['rsid']})",
                            "value": f"{c} of 2 risk copies", "note": f"p {l['p']:.0e}, PMID {l['pmid']}"})
        if not loci:
            cards.append(card("condition", it["id"], it["label"], level="unknown",
                              headline=f"No genome-wide association study in the GWAS Catalog reports variants for {it['label']}.",
                              unknown=["With no known variants there is nothing to read in the genome for this condition."],
                              topic=it["label"], focus="genetic OR heritability"))
            continue
        z = (carried - exp) / math.sqrt(var) if var else 0.0
        pct = round(100 * 0.5 * (1 + math.erf(z / math.sqrt(2))))
        lvl = band(pct)
        cards.append(card("condition", it["id"], it["label"], level=lvl, value=pct, higher="worse",
                          headline=f"You carry {int(carried)} risk alleles at the {n} strongest known {it['label']} variants; "
                                   f"the European average is {exp:.0f}, which puts you near the {ordinal(pct)} percentile.",
                          rows=top,
                          known=[f"{len(loci)} genome-wide significant variants in the GWAS Catalog; {n} read in your file."],
                          unknown=["This is a plain count of risk alleles, not a validated risk score: each variant is weighted the same, "
                                   "and most of the inheritance of common conditions lies in variants not found yet.",
                                   "It says nothing about whether the condition is present now."],
                          topic=it["label"], focus="genetic OR polygenic OR heritability"))
    return cards
