"""A sealed forecast of a child, checked against the child's own DNA: how good the Inheritance tab's predictions are,
and where their logic is wrong.

    python -m cluster_analysis.inheritance.forecast freeze XX_1 XY_1 --sex female   # before the child is in the app
    python -m cluster_analysis.inheritance.forecast check XX_2 [--forecast FILE]     # once the child is imputed
    python -m cluster_analysis.inheritance.forecast list

freeze writes everything the tab predicts for a child of the pair, from the parents alone, into the pair's folder
(data/output/.../pairs/XX__XY/forecast-<time>.json, personal, kept out of git), with the SHA-256 of its content in
an append-only ledger (pairs/forecasts.json). check refuses a forecast whose content no longer matches its hash, or
that was made after the child's DNA was added, so the test can't be bent after the fact.

What check measures, from the most basic to the most derived:
  1. Mendel: at every variant all three are read, the child's two copies must be one from each parent. A child
     genotype no parent pair can give is an error in one of the three calls (imputation, a chip miscall) or a wrong
     relationship; the rate by call tier shows which calls to trust.
  2. Variant odds: the child's copies against the predicted odds (Mendel over the parents' copies), scored as
     information gained over knowing only European frequencies, and how often a settled variant came out as settled.
  3. Traits: the child's own score against the predicted place. If the logic is right, (actual - predicted) / spread
     follows a standard normal: 80% inside the 80% field, 98% inside the 98% field, mean 0, spread 1. More misses mean
     the fields are too narrow (missing variance: imputation error, unread variants counted as average); fewer, too
     wide.
  4. Single-gene traits and drug types: the child's outcome against its predicted odds.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import statistics

import numpy as np

from cluster_analysis.inheritance import inheritance as ih, predict


Z80, Z98 = 1.2816, 2.3263


def _pair_dir(xx, xy):
    return os.path.join(predict.ROOT, "data", "output", "cluster_analysis_GRCh38", "pairs", f"{xx}__{xy}")


def _ledger():
    return os.path.join(predict.ROOT, "data", "output", "cluster_analysis_GRCh38", "pairs", "forecasts.json")


def _profiles():
    return {p["id"]: p for p in json.load(open(ih.PROFILES, encoding="utf-8"))["profiles"]}


def _rows(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _seal(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def variant_odds(models, xxc, xyc, sex="female"):
    """Per variant read in both parents: the child's odds of 0, 1, 2 effect-allele copies (Mendel, each parent passing
    one of two copies), with the parents' copies and call tiers. On the X (outside the pseudo-autosomal regions) a son
    gets his mother's X only, counted 0 or 2 (predict.moments); a daughter her father's single X for certain."""
    out = {}
    for m in models:
        for v in m["variants"]:
            if v["rsid"] in out:
                continue
            a, b = predict.copies(xxc.get(v["rsid"]), v), predict.copies(xyc.get(v["rsid"]), v)
            if a is None or b is None:
                continue
            qa, qb = a / 2, b / 2
            x = bool(v.get("x"))
            p = [round(1 - qa, 4), 0.0, round(qa, 4)] if x and sex == "male" else \
                [round((1 - qa) * (1 - qb), 4), round(qa * (1 - qb) + qb * (1 - qa), 4), round(qa * qb, 4)]
            out[v["rsid"]] = {"allele": v["allele"], "ref": v["ref"], "alt": v["alt"], "freq": v.get("freq"),
                              "XX": a, "XY": b, "XX_tier": xxc[v["rsid"]]["tier"], "XY_tier": xyc[v["rsid"]]["tier"],
                              "p": p, **({"x": True} if x else {})}
    return out


SIMS = 500
SEED = 20261126


def _space(models, odds, sex):
    """The trait space of the embedding: every model whose variants include some read in both parents (and not studied
    in the other sex only), as a sparse matrix of weight / the model's population spread, over those variants. A
    person's vector is that matrix times (their copies - 2f): unread variants count as the average, as on the page."""
    from scipy import sparse
    keep = "female" if sex == "female" else "male"
    rs = sorted(odds)
    col = {r: i for i, r in enumerate(rs)}
    f = np.array([odds[r]["freq"] or 0.0 for r in rs])
    rows, cols, vals, ids = [], [], [], []
    for m in models:
        st = predict.studied_sex(m.get("sample"))
        if (st and st != keep) or m["trait"] in predict.NOT_A_TRAIT:
            continue
        var = sum(predict.moments(v.get("freq") or 0, bool(v.get("x")) and keep == "male")[1] * v["w"] ** 2 for v in m["variants"])
        hits = [(col[v["rsid"]], v["w"]) for v in m["variants"] if v["rsid"] in col and odds[v["rsid"]]["allele"] == v["allele"]]
        if var <= 0 or len(hits) < 5:
            continue
        sd = math.sqrt(var)
        k = len(ids)
        ids.append(m["id"])
        for c, w in hits:
            rows.append(k); cols.append(c); vals.append(w / sd)
    M = sparse.csr_matrix((vals, (rows, cols)), shape=(len(ids), len(rs)))
    return ids, rs, f, M


def embedding(models, odds, sex, sims=SIMS, seed=SEED):
    """The predicted child as one vector over every trait (the expected z), and how far real children of the pair and
    unrelated Europeans fall from it: 500 daughters (or sons) drawn by Mendel from the parents' copies, and 500 people
    drawn from European frequencies (Hardy-Weinberg, no linkage). Distance: root mean square difference over the traits;
    likeness: Pearson r with the predicted vector. Sealed with the forecast, before the child's DNA is read."""
    ids, rs, f, M = _space(models, odds, sex)
    P = np.array([odds[r]["p"] for r in rs])                       # variants x 3: odds of 0, 1, 2 copies
    expect = P @ np.array([0, 1, 2]) - 2 * f
    E = M @ expect                                                   # the predicted child
    rng = np.random.default_rng(seed)

    def draw_child():
        u = rng.random(len(rs))[:, None]
        return (u > np.cumsum(P, axis=1)).sum(axis=1).clip(0, 2)

    def describe(Z):
        d = np.sqrt(((Z - E) ** 2).mean(axis=1))
        r = np.array([np.corrcoef(z, E)[0, 1] for z in Z])
        q = lambda x: [round(float(v), 4) for v in np.percentile(x, [1, 5, 10, 25, 50, 75, 90, 95, 99])]
        return {"distance": q(d), "likeness": q(r)}
    kids = np.array([M @ (draw_child() - 2 * f) for _ in range(sims)])
    # A stranger of the child's sex: two copies at each variant, or on a man's X one copy counted 0 or 2
    hemi = np.array([bool(odds[r].get("x")) and sex == "male" for r in rs])
    strangers = np.array([M @ (np.where(hemi, 2 * rng.binomial(1, f), rng.binomial(2, f)) - 2 * f) for _ in range(sims)])
    return {"traits": ids, "variants": rs, "predicted": [round(float(x), 4) for x in E], "sims": sims, "seed": seed,
            "percentiles": [1, 5, 10, 25, 50, 75, 90, 95, 99],
            "siblings": describe(kids), "strangers": describe(strangers),
            "models_sha256": hashlib.sha256(open(predict.MODELS, "rb").read()).hexdigest()}


def place(emb, calls, models, sex):
    """The child's own vector in the embedding's space (the same traits, variants and weights as sealed; the child's
    unread variants count as the average), and where it falls among the simulated siblings and strangers."""
    if hashlib.sha256(open(predict.MODELS, "rb").read()).hexdigest() != emb["models_sha256"]:
        raise SystemExit("The trait models changed since the forecast was sealed; the child can't be placed in its space.")
    by = {}
    for m in models:
        for v in m["variants"]:
            by.setdefault(v["rsid"], v)
    odds = {r: {"freq": by[r].get("freq"), "allele": by[r]["allele"], **({"x": True} if by[r].get("x") else {})} for r in emb["variants"]}
    ids, rs, f, M = _space(models, odds, sex)
    keep = {t: i for i, t in enumerate(ids)}
    pairs_ = [(keep[t], e) for t, e in zip(emb["traits"], emb["predicted"]) if t in keep]
    order = [i for i, _ in pairs_]
    E = np.array([e for _, e in pairs_])
    c = []
    for i, r in enumerate(rs):
        n = predict.copies(calls.get(r), by[r])
        c.append(2 * f[i] if n is None else n)
    A = (M @ (np.array(c, dtype=float) - 2 * f))[order]
    d = float(np.sqrt(((A - E) ** 2).mean()))
    r = float(np.corrcoef(A, E)[0, 1])

    def rank(x, qs):
        """The share of the simulated people with a value below x, interpolated between the sealed percentiles
        (below the 1st: under 1; above the 99th: over 99)."""
        ps = emb["percentiles"]
        if x <= qs[0]:
            return "<1"
        if x >= qs[-1]:
            return ">99"
        return round(float(np.interp(x, qs, ps)))
    return {"distance": round(d, 4), "likeness": round(r, 4),
            # distance: lower is closer; the share of simulated daughters and strangers farther away than the child
            "siblings_closer_pct": rank(d, emb["siblings"]["distance"]),
            "strangers_closer_pct": rank(d, emb["strangers"]["distance"]),
            # likeness: the share of simulated daughters and strangers less alike than the child
            "siblings_less_alike_pct": rank(r, emb["siblings"]["likeness"]),
            "strangers_less_alike_pct": rank(r, emb["strangers"]["likeness"]),
            "siblings_range": [emb["siblings"]["distance"][0], emb["siblings"]["distance"][-1]],
            "strangers_range": [emb["strangers"]["distance"][0], emb["strangers"]["distance"][-1]],
            "traits": len(order)}


def freeze(xx, xy, sex):
    ps = _profiles()
    if xx not in ps or xy not in ps:
        raise SystemExit("Both parents must be profiles.")
    models = predict.load_models()
    rsids = predict.model_rsids(models)
    xxc, _ = ih.parent_calls(ps[xx]["dna"], rsids)
    xyc, _ = ih.parent_calls(ps[xy]["dna"], rsids)
    d = _pair_dir(xx, xy)
    keep = "female" if sex == "female" else "male"
    traits = []
    for r in _rows(os.path.join(d, "inh_predictions.json")):
        if r.get("child_sex") not in (None, "any", "XX" if sex == "female" else "XY"):
            continue
        studied = r.get("studied_sex")
        if studied and studied not in ("None", keep):
            continue
        traits.append({k: _num(r.get(k)) if k not in ("id", "trait", "reported", "kind", "category") else r.get(k)
                       for k in ("id", "trait", "reported", "kind", "category", "child_z", "child_sd", "child_pct", "child_lo",
                                 "child_hi", "child_lo98", "child_hi98", "XX_pct", "XY_pct", "impact", "variants", "used_both")})
    odds = variant_odds(models, xxc, xyc, sex)
    doc = {"made": datetime.datetime.now().isoformat(timespec="seconds"), "parents": {"XX": xx, "XY": xy}, "child_sex": sex,
           "app": __import__("cluster_analysis.version", fromlist=["VERSION"]).VERSION,
           "embedding": embedding(models, odds, sex),
           "variants": odds, "traits": traits,
           "single_gene": _rows(os.path.join(d, "inh_traits.json")), "drugs": _rows(os.path.join(d, "inh_drugs.json")),
           "conditions": _rows(os.path.join(d, "inh_conditions.json"))}
    seal = _seal(doc)
    stamp = doc["made"].replace(":", "").replace("-", "")
    path = os.path.join(d, f"forecast-{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"sha256": seal, "forecast": doc}, f, ensure_ascii=False)
    led = _rows(_ledger()) or []
    led.append({"file": os.path.relpath(path, predict.ROOT), "sha256": seal, "made": doc["made"], "parents": doc["parents"], "child_sex": sex})
    with open(_ledger(), "w", encoding="utf-8") as f:
        json.dump(led, f, indent=1)
    print(f"✅ forecast sealed: {len(doc['variants']):,} variants, {len(traits):,} traits, {len(doc['single_gene'])} single-gene "
          f"traits, {len(doc['drugs'])} drug genes\n   {path}\n   sha256 {seal}")
    return path


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    if _seal(d["forecast"]) != d["sha256"]:
        raise SystemExit(f"{path}: the content no longer matches its seal; it was changed after it was made.")
    if not any(e["sha256"] == d["sha256"] for e in _rows(_ledger())):
        raise SystemExit(f"{path}: not in the ledger of sealed forecasts.")
    return d["forecast"]


def _latest_for(child):
    ps = _profiles()
    par = ps[child].get("parents") or []
    led = [e for e in _rows(_ledger()) if set(e["parents"].values()) == set(par)] if par else _rows(_ledger())
    if not led:
        raise SystemExit("No sealed forecast for this child's parents: freeze one first.")
    return os.path.join(predict.ROOT, led[-1]["file"])


def check(child, path=None):
    ps = _profiles()
    if child not in ps:
        raise SystemExit(f"{child} isn't a profile yet: add the person first.")
    path = path or _latest_for(child)
    fc = load(path)
    # A fair test: the forecast must be older than the child's DNA in the app
    added = ps[child].get("added")
    if added and added < fc["made"]:
        raise SystemExit(f"The forecast ({fc['made']}) was made after {child} was added ({added}).")
    models = predict.load_models()
    calls, _ = ih.parent_calls(ps[child]["dna"], predict.model_rsids(models))
    rep = {"child": child, "forecast": os.path.basename(path), "made": fc["made"], "parents": fc["parents"],
           "sha256": json.load(open(path, encoding="utf-8"))["sha256"], "child_added": ps[child].get("added"),
           "checked": datetime.datetime.now().isoformat(timespec="seconds")}

    # 1. Mendel, by the child's and parents' call tiers
    mend = {}
    gain, n_info, settled_ok, settled_n = 0.0, 0, 0, 0
    for rsid, v in fc["variants"].items():
        c = predict.copies(calls.get(rsid), v)
        if c is None:
            continue
        key = "all measured" if (v["XX_tier"] == v["XY_tier"] == calls[rsid]["tier"] == "measured") else "some imputed"
        m = mend.setdefault(key, {"variants": 0, "impossible": 0})
        m["variants"] += 1
        p = v["p"][c]
        if p <= 0:
            m["impossible"] += 1
            continue
        # 2. information over the population's frequencies (Hardy-Weinberg)
        f = v.get("freq")
        if f:
            base = [(1 - f) ** 2, 2 * f * (1 - f), f * f][c]
            if base > 0:
                gain += math.log2(p / base)
                n_info += 1
        if max(v["p"]) == 1:
            settled_n += 1
            settled_ok += v["p"][c] == 1
    for m in mend.values():
        m["error_rate"] = round(m["impossible"] / m["variants"], 5) if m["variants"] else None
    rep["mendel"] = mend
    rep["variants"] = {"scored": n_info, "bits_per_variant_over_frequencies": round(gain / n_info, 4) if n_info else None,
                       "settled": settled_n, "settled_as_predicted": round(settled_ok / settled_n, 5) if settled_n else None}

    # 3. Traits: the child's own place against the predicted one
    own = {s["id"]: s for s in predict.person_scores(models, calls, ps[child].get("sex"))}
    errs, pairs_pct, rows = [], [], []
    for t in fc["traits"]:
        s = own.get(t["id"])
        if not s or not t.get("child_sd"):
            continue
        e = (s["z"] - t["child_z"]) / t["child_sd"]
        errs.append(e)
        pairs_pct.append((t["child_pct"], s["pct"]))
        rows.append({"id": t["id"], "trait": t["trait"], "category": t.get("category"), "predicted_pct": t["child_pct"],
                     "actual_pct": s["pct"], "range80": [t["child_lo"], t["child_hi"]], "range98": [t["child_lo98"], t["child_hi98"]],
                     "error_sd": round(e, 2), "impact": t.get("impact")})
    if errs:
        n = len(errs)
        corr = statistics.correlation([a for a, _ in pairs_pct], [b for _, b in pairs_pct]) if n > 2 else None
        rep["traits"] = {"compared": n, "inside_80": round(sum(abs(e) <= Z80 for e in errs) / n, 4),
                         "inside_98": round(sum(abs(e) <= Z98 for e in errs) / n, 4),
                         "error_mean": round(statistics.mean(errs), 3), "error_spread": round(statistics.pstdev(errs), 3),
                         "correlation_predicted_actual_pct": round(corr, 3) if corr is not None else None,
                         "by_impact": {lvl: _cover([r for r in rows if r["impact"] is not None and lo <= r["impact"] < hi])
                                       for lvl, lo, hi in (("high", 8, 1e9), ("modest", 3, 8), ("little", 0, 3))},
                         "worst": sorted(rows, key=lambda r: -abs(r["error_sd"]))[:15], "rows": rows}

    # 4. Single-gene traits: the child's copies at the trait's variant against the predicted odds
    sg = []
    for t in fc["single_gene"]:
        vs = json.loads(t["variants"]) if isinstance(t.get("variants"), str) else t.get("variants") or []
        odds = json.loads(t["odds"]) if isinstance(t.get("odds"), str) else t.get("odds") or {}
        p = (odds or {}).get("child")
        if not vs or not p:
            continue
        v = vs[0]
        call = calls.get(v["rsid"])
        if not call or call.get("tier") not in predict.USABLE:
            continue
        c = ih.copies_of(call["genotype"], [v["allele"]])
        sg.append({"trait": t.get("name"), "copies": c, "predicted_odds": p, "odds_of_what_came": p[c] if c < len(p) else None})
    rep["single_gene"] = sg

    # 5. The embedding: the child's whole trait vector against the sealed prediction, among simulated siblings and strangers
    if fc.get("embedding"):
        rep["embedding"] = place(fc["embedding"], calls, models, fc["child_sex"])
        rep["embedding"] |= {k: fc["embedding"][k] for k in ("percentiles", "siblings", "strangers", "sims")}

    out = os.path.join(os.path.dirname(path), f"check-{child}-{os.path.basename(path)}")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    _print(rep)
    print(f"\n→ {out}")
    return rep


def _cover(rows):
    if not rows:
        return None
    inside = sum(abs(r["error_sd"]) <= Z80 for r in rows) / len(rows)
    return {"traits": len(rows), "inside_80": round(inside, 3)}


def _print(rep):
    print(f"Forecast {rep['forecast']} (made {rep['made']}) for {rep['child']}, child of {rep['parents']['XX']} and {rep['parents']['XY']}")
    for k, m in rep["mendel"].items():
        print(f"  Mendel, {k}: {m['impossible']:,} impossible of {m['variants']:,} ({100 * (m['error_rate'] or 0):.3f}%)")
    v = rep["variants"]
    print(f"  Variant odds: {v['bits_per_variant_over_frequencies']} bits per variant over frequencies ({v['scored']:,} variants); "
          f"settled ones as predicted: {100 * (v['settled_as_predicted'] or 0):.2f}% of {v['settled']:,}")
    t = rep.get("traits")
    if t:
        print(f"  Traits ({t['compared']:,}): inside the 80% field {100 * t['inside_80']:.1f}% (expect 80), inside 98% "
              f"{100 * t['inside_98']:.1f}% (expect 98); error mean {t['error_mean']} (expect 0), spread {t['error_spread']} (expect 1); "
              f"predicted vs actual place r = {t['correlation_predicted_actual_pct']}")
        for lvl, c in t["by_impact"].items():
            if c:
                print(f"    {lvl} impact: {c['traits']} traits, {100 * c['inside_80']:.1f}% inside 80%")
    e = rep.get("embedding")
    if e:
        print(f"  Embedding ({e['traits']:,} traits): distance {e['distance']} (simulated daughters {e['siblings_range'][0]}-{e['siblings_range'][1]}, "
              f"strangers {e['strangers_range'][0]}-{e['strangers_range'][1]}); {e['siblings_closer_pct']}% of simulated daughters are closer, "
              f"{e['strangers_closer_pct']}% of strangers; likeness r = {e['likeness']} ({e['siblings_less_alike_pct']}% of daughters less alike)")
    for s in rep["single_gene"]:
        print(f"  {s['trait']}: {s['copies']} copies; predicted odds {s['predicted_odds']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("xx")
    f.add_argument("xy")
    f.add_argument("--sex", choices=("female", "male"), required=True)
    c = sub.add_parser("check")
    c.add_argument("child")
    c.add_argument("--forecast")
    sub.add_parser("list")
    a = ap.parse_args()
    if a.cmd == "freeze":
        freeze(a.xx, a.xy, a.sex)
    elif a.cmd == "check":
        check(a.child, a.forecast)
    else:
        for e in _rows(_ledger()):
            print(f"{e['made']}  {e['parents']['XX']} × {e['parents']['XY']} ({e['child_sex']})  {e['sha256'][:16]}…  {e['file']}")


if __name__ == "__main__":
    main()
