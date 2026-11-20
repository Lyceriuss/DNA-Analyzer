"""Written readings for every possible result of a gene or a score, the same for everyone; the person's are picked here.

    categories.ensure("medicines")      # every CPIC gene result (NAT2 poor metabolizer, CYP2B6 intermediate, ...)
    categories.ensure("cancer")         # every cancer type in every band (low ... high)
    categories.reading(card)            # the reading for one result card, picked on this machine

The same idea as interpret.py for study findings (docs/architecture/ask-decisions.md, D14 and D16): the model is never
told whose genome it is or which result they have. It writes, once and for everyone, a reading for every category a
domain has, from public facts only (the CPIC recommendations for that gene result; what a score measures and the
advice tied to it). Writing the whole domain, never one person's categories, keeps the choice from revealing anything.
This machine then picks the reading for the person's own category. A reading may only use the numbers its facts give.
"""
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from cluster_analysis import sources
from cluster_analysis.agent import cost, interpret, language

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG = os.path.join(ROOT, "cluster_analysis")
CPIC = os.path.join(ROOT, "data", "reference", "cpic_recommendations.json")
BANDS = {"low": "in the lowest 10% of Europeans", "lowered": "between the 10th and 25th percentile",
         "typical": "in the usual range (25th to 75th percentile)", "raised": "between the 75th and 90th percentile",
         "high": "in the highest 10% of Europeans"}
BATCH = 16

SYSTEM = ("Each item is a category of result a person can have from their genome, with the public facts about it: "
          "a gene result with the dosing guideline recommendations for it, or a genetic score in a band. Write for "
          "someone in that category, addressed to \"you\":\n"
          "- reading: one or two plain sentences on what this result means for them, using only the facts given.\n"
          "- takeaway: one short sentence on what this result means for their risk, exposure or response (for "
          "medicines: how the drug is handled, and whether the guideline lists a changed dose for this group), or \"\".\n"
          "Keep every dose and number exactly as the facts give it and add none. Plain words, no jargon, no hedging "
          "boilerplate. A usual result should read as reassuring and short.\n" + language.RULE)

SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "string"}, "reading": {"type": "string"}, "takeaway": {"type": "string"}},
    "required": ["id", "reading", "takeaway"], "additionalProperties": False}}}, "required": ["items"], "additionalProperties": False}


def key_id(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:14]


def _path(key):
    return os.path.join(sources.CACHE_DIR, f"agent_cat_{key_id(key)}.json")


def cached(key):
    p = _path(key)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


# --- The categories of each domain, with their public facts ---------------------------------------------------------

def cpic_result(gene, phenotype):
    """The CPIC name of a result as the explorer writes it ("Slow acetylator" -> Poor Metabolizer for NAT2,
    "Normal metaboliser (activity score 2)" -> 2.0 for CYP2C9)."""
    p = (phenotype or "").lower().replace("metaboliser", "metabolizer")
    if gene == "CYP2C9":
        m = re.search(r"activity score (\d(?:\.\d)?)", p)
        return f"{float(m.group(1)):.1f}" if m else None
    p = re.sub(r"\s*\(.*\)$", "", p).strip()
    p = {"slow acetylator": "poor metabolizer", "intermediate acetylator": "intermediate metabolizer",
         "rapid acetylator": "rapid metabolizer"}.get(p, p)
    return p.title()


def medicines():
    """{key: facts} for every single-gene CPIC result: the drugs and what the guideline recommends for that result."""
    if not os.path.exists(CPIC):
        return {}
    with open(CPIC, encoding="utf-8") as f:
        rows = json.load(f)
    by = {}
    for r in rows:
        lk = r.get("lookupkey") or {}
        if len(lk) != 1:
            continue
        gene, result = next(iter(lk.items()))
        if result in ("Indeterminate", "n/a", "No Result"):
            continue
        rec = re.sub(r"\s+", " ", r.get("drugrecommendation") or "").strip()
        if not rec:
            continue
        d = by.setdefault(f"med|{gene}|{result}", {"what": f"{gene}: {result}", "drugs": {}})
        name = (r.get("drug") or {}).get("name")
        if name and name not in d["drugs"] and len(d["drugs"]) < 10:
            d["drugs"][name] = {"recommendation": rec[:320], "strength": r.get("classification"),
                                "implication": ((r.get("implications") or {}).get(gene) or "")[:200]}
    return by


def scores(domain):
    """{key: facts} for every item of a score domain in every band."""
    cfg = {"cancer": "cancers.json", "lab": "labtests.json", "nutrient": "nutrients.json", "fitness": "fitness.json"}[domain]
    path = os.path.join(PKG, "nutrition", cfg)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    prev = {}
    if domain == "cancer":
        with open(os.path.join(PKG, "themes", "cancer_prevention.json"), encoding="utf-8") as f:
            p = json.load(f)
        recs = {r["n"]: r for r in p.get("recommendations") or []}
        # Risk factors, not instructions: the causes IARC lists with sufficient evidence for each cancer
        prev = {v["name"]: v.get("agents") or [] for v in (p.get("cancers") or {}).values()}
    out = {}
    for t in d.get("tests") or d.get("nutrients") or []:
        for m in t.get("markers", []):
            for band, words in BANDS.items():
                out[f"score|{domain}|{t['id']}:{m['id']}|{band}"] = {
                    "what": f"Genetic score for {m['name']}: {words}", "higher_is": m.get("higher", "worse"),
                    "known_causes_iarc": prev.get(t["name"], []) if domain == "cancer" else [],
                    "note": "The score covers inherited variants only; lifestyle, age and medicines also move the real value or risk."}
    return out


def conditions(label):
    """{key: facts} for one condition (named by the question) in every band of the plain risk-allele count."""
    return {f"cond|{label}|{band}": {"what": f"Count of inherited risk alleles for {label}: {words}",
                                      "note": "An unweighted count of the strongest known variants, not a validated risk score."}
            for band, words in BANDS.items()}


UNIVERSES = {"medicines": medicines, "cancer": lambda: scores("cancer"), "lab": lambda: scores("lab"),
             "nutrient": lambda: scores("nutrient"), "fitness": lambda: scores("fitness")}


# --- Writing them -------------------------------------------------------------------------------------------------

def _batch(items):
    prompt = "Categories (JSON):\n" + json.dumps([{"id": key_id(k), "facts": f} for k, f in items], ensure_ascii=False)
    out, usage = interpret._ask(prompt, SYSTEM, SCHEMA)
    by = {x["id"]: x for x in out.get("items", [])}
    for k, f in items:
        x = by.get(key_id(k))
        if not x:
            continue
        nums = interpret.figures(json.dumps(f, ensure_ascii=False))
        reading = x["reading"] if interpret.figures(x["reading"]) <= nums and not language.advice(x["reading"]) else ""
        take = x["takeaway"] if interpret.figures(x["takeaway"]) <= nums and not language.advice(x["takeaway"]) else ""
        if reading:
            with open(_path(k), "w", encoding="utf-8") as fh:
                json.dump({"key": k, "reading": reading, "takeaway": take}, fh, ensure_ascii=False)
    return usage


def ensure(domain=None, universe=None, emit=lambda ev: None):
    """Writes the readings a domain is missing (all its categories, never a person's selection): tokens used."""
    uni = universe if universe is not None else UNIVERSES[domain]()
    todo = [(k, f) for k, f in uni.items() if cached(k) is None]
    usage = cost.new()
    if not todo:
        return usage
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    emit({"type": "step", "step": "interpret", "sources": ["claude"], "findings": len(todo), "calls": len(batches)})
    with ThreadPoolExecutor(max_workers=4) as pool:
        for u in pool.map(_batch, batches):
            usage = cost.add(usage, u)
            emit({"type": "usage", **usage})
    return usage


def key_of(card, person):
    """The category of a result card, worked out on this machine from the person's own result."""
    from cluster_analysis.agent import providers
    p = card["provider"]
    if p == "medicines" and card.get("gene"):
        phen = next((g["phenotype"] for g in providers.rows("med_genes", person) if g["gene"] == card["gene"]), None)
        res = cpic_result(card["gene"], phen) if phen else None
        return f"med|{card['gene']}|{res}" if res else None
    if p in ("cancer", "lab", "nutrient", "fitness") and card["level"] in BANDS:
        return f"score|{p}|{card['id']}|{card['level']}"
    if p == "condition" and card["level"] in BANDS:
        return f"cond|{card['title']}|{card['level']}"
    return None


def domains_of(cards):
    """The domains (and question-named conditions) the cards come from: what ensure() must cover."""
    out, conds = set(), set()
    for c in cards:
        if c["provider"] == "medicines" and c.get("gene"):
            out.add("medicines")
        elif c["provider"] in ("cancer", "lab", "nutrient", "fitness"):
            out.add(c["provider"])
        elif c["provider"] == "condition" and c["level"] in BANDS:
            conds.add(c["title"])
    return out, conds
