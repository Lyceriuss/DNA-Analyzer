"""Matching a question to what the explorer holds: no module per question, one index of every public item.

    from cluster_analysis.agent import terms
    terms.match("Which medicines should I be careful with?")

The index is built from public files only (the configs in git and the theme graphs), so matching sends nothing
anywhere:
  drug       every drug with pharmacogenetic guidance or annotation, by name, generic name, trade name and class
  cancer     the cancer types scored by PGS (nutrition/cancers.json)
  lab        the lab tests and their markers (nutrition/labtests.json)
  nutrient   the nutrients and their blood tests (nutrition/nutrients.json)
  fitness    the fitness tests (nutrition/fitness.json, when present)
  theme      the clusters (themes/theme_graph_*.json): the theme, its phases, mechanisms and traits
  gene       gene symbols of the themes, medicines and pathways
Items carry their ontology ids (EFO, MONDO) where the configs give them, so a condition the index doesn't name can
still be reached: Open Targets search turns the question's words into disease ids, and those ids are looked up in
the configs, the theme graphs and the GWAS index.

kind() reads what sort of answer the question wants (a ranking, actions, a propensity, a gene's role) and which parts
it asks for that the data cannot give (mortality, timing), so the answer can say so first.
"""
import glob
import json
import os
import re

from cluster_analysis import sources

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
OT_API = "https://api.platform.opentargets.org/api/v4/graphql"
STOP = set("""a an the and or of in on to for with by from at as is are be been am do does did have has had i me my mine
we our you your it its this that these those which what who whom how why when where will would should could can may might
must shall there their them they he she his her about into than then so if not no yes any some most more less least much
many very really just only also get got make take use give tell know want need like am best good bad well vad vilken vilka
hur jag mig min mitt mina är har kan ska skulle bör och eller av för med på till om att det den de en ett som inte""".split())


def norm(text):
    t = (text or "").lower().replace("’", "'")
    t = re.sub(r"'s\b", "", t)
    t = re.sub(r"[^\w\s\-/]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def words(text):
    return [w for w in re.split(r"[\s\-/]+", norm(text)) if w]


def stem(w):
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf) and not w.endswith("ss"):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


# --- The index -------------------------------------------------------------------------------------------------

_INDEX = None


def _add(index, name, item):
    toks = [stem(w) for w in words(name) if w not in STOP]
    if toks:
        index.append({"name": name, "toks": toks, **item})


def _json(*parts):
    path = os.path.join(PKG, *parts)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def index():
    """[{name, toks, type, id, ...}] over every public item (built once per process)."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    idx = []
    for cfg, typ in (("cancers.json", "cancer"), ("labtests.json", "lab"), ("nutrients.json", "nutrient"), ("fitness.json", "fitness")):
        d = _json("nutrition", cfg)
        for t in (d or {}).get("tests") or (d or {}).get("nutrients") or []:
            ids = [x for m in t.get("markers", []) for x in m.get("traits", [])] + ([t["disease"]] if t.get("disease") else [])
            item = {"type": typ, "id": t["id"], "label": t["name"], "traits": ids}
            _add(idx, t["name"], item)
            if t.get("sv"):
                _add(idx, t["sv"], item)
            for m in t.get("markers", []):
                _add(idx, m.get("name", ""), {**item, "marker": m["id"]})
    for path in sorted(glob.glob(os.path.join(PKG, "themes", "theme_graph_*.json"))):
        with open(path, encoding="utf-8") as f:
            g = json.load(f)
        th = g["theme"]
        base = {"type": "theme", "theme": th, "label": g["name"], "sex": g.get("sex")}
        _add(idx, g["name"], {**base, "id": th, "level": "theme"})
        for o in g.get("organs") or []:
            _add(idx, o["name"], {**base, "id": o["id"], "level": "phase", "label": f"{g['name']}: {o['name']}"})
        for m in g.get("mechanisms") or []:
            _add(idx, m["name"], {**base, "id": m["id"], "level": "mechanism", "label": f"{g['name']}: {m['name']}"})
        for efo, name in (g.get("diseases") or {}).items():
            _add(idx, name, {**base, "id": name, "level": "trait", "label": f"{g['name']}: {name}",
                             "traits": (g.get("disease_ids") or {}).get(efo, [efo])})
    genes = set()
    for path in sorted(glob.glob(os.path.join(PKG, "themes", "theme_graph_*.json"))):
        with open(path, encoding="utf-8") as f:
            genes |= {s for s in json.load(f)["genes"] if re.fullmatch(r"[A-Z][A-Z0-9\-]{1,9}", s)}
    for s in sorted(genes):
        idx.append({"name": s, "toks": [s.lower()], "type": "gene", "id": s, "label": s, "exact": True})
    for r in _med_names():
        item = {"type": "drug", "id": r["drug"], "label": r["drug"]}
        for name in [r["drug"]] + [x for k in ("generic", "trade") for x in (r.get(k) or "").split(";")]:
            if name.strip():
                _add(idx, name.strip(), item)
        for c in (r.get("classes") or "").split(";"):
            if c.strip():
                _add(idx, c.strip(), {"type": "drug_class", "id": c.strip(), "label": c.strip()})
    _INDEX = idx
    return idx


def _med_names():
    """Drug names, generic and trade names and classes: public (ClinPGx, ChEMBL ATC), kept in the medicines dataset."""
    from genome import build as gbuild
    path = os.path.join(ROOT, gbuild.EXPLORER, "datasets", "med_names.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --- Matching --------------------------------------------------------------------------------------------------

# Everyday words for what each part of the explorer covers: a word list per domain, not per question
DOMAINS = {
    ("domain", "drug"): "medicine medicines medication medications drug drugs pill pills tablet tablets prescription prescriptions "
                        "painkiller painkillers dose doses läkemedel medicin mediciner tablett tabletter",
    ("domain", "cancer"): "cancer cancers tumour tumor tumours tumors carcinoma malignancy cancern tumör",
    ("domain", "lab"): "lab labs blood test tests level levels biomarker biomarkers blodprov prov värden",
    ("domain", "nutrient"): "vitamin vitamins mineral minerals diet food foods nutrition nutrient nutrients supplement supplements "
                            "eat eating kost mat vitaminer mineraler kosttillskott äta",
    ("theme", "muscle"): "workout workouts training train exercise exercises sport sports fitness gym run running strength "
                         "endurance muscle muscles recovery injury injuries träning träna motion styrka uthållighet muskler",
    ("theme", "mind"): "mood sleep depression anxiety psychology psychological mental stress adhd sömn humör ångest psykisk",
    ("theme", "fertility"): "fertility fertile pregnancy pregnant conceive conceiving baby infertility fertilitet gravid graviditet",
    ("theme", "cancer"): "cancer cancers",
}
# Words that say what kind of answer is wanted, not what it is about: never searched as conditions
GENERIC = set("""genetic genetically genes gene genome dna propensity predisposition predisposed susceptible susceptibility
risk risks chance chances problem problems issue issues condition conditions disease diseases disorder disorders health
healthy likely likelihood prone tendency careful caution safe safety avoid affect affects effect effects mean means
work works suit suits help helps good better worse high low higher lower thing things body die dying taking take takes
death life long often anlag risk problem sjukdom sjukdomar påverkar betyder""".split())


_SV = None


def _sv_terms():
    """{Swedish name: English name} for the short disease and trait names in explorer/i18n_sv_terms.json."""
    global _SV
    if _SV is None:
        path = os.path.join(PKG, "explorer", "i18n_sv_terms.json")
        d = _json("explorer", "i18n_sv_terms.json") or {}
        _SV = {norm(sv): en for en, sv in d.items() if len(words(sv)) <= 4 and len(norm(sv)) >= 4 and norm(sv) != norm(en)}
    return _SV


def _domain_index():
    out = {}
    for key, ws in DOMAINS.items():
        for w in ws.split():
            out.setdefault(stem(w), set()).add(key)
    return out


def match(question, limit=40, search=True):
    """The items a question names: [{type, id, label, score, ...}], best first.
      3    a gene symbol written as such (ACTN3)
      2+   every word of an item's name is in the question ("vitamin D", "clopidogrel", "prostate cancer")
      1.5  a domain word ("medicine" -> the medicines, "workouts" -> the Fitness cluster)
      1    a theme, test or nutrient name sharing a long word part with the question ("thyroid" ~ "thyroid hormone")
      0.9  an Open Targets disease found for a word nothing else matched ("thyroid" -> thyroid gland disorder)"""
    qw = [w for w in words(question) if w not in STOP]
    q = [stem(w) for w in qw]
    qset = set(q)
    symbols = set(re.findall(r"\b[A-Z][A-Z0-9\-]{1,9}\b", question))
    found, used, partial = {}, set(), set()
    qnorm = norm(question)

    def keep(it, score, toks):
        key = (it["type"], it.get("theme"), it["id"], it.get("marker"))
        if score > found.get(key, {}).get("score", 0):
            found[key] = {k: v for k, v in it.items() if k != "toks"} | {"score": round(score, 2)}
        if score >= 1.5:
            used.update(toks)

    # Pass 1: names written in full, gene symbols, domain words
    for it in index():
        toks = it["toks"]
        if it.get("exact"):
            if it["name"] in symbols and len(it["name"]) >= 3:
                keep(it, 3.0, [it["name"].lower()])
            continue
        if any(len(x) >= 3 for x in toks) and all(x in qset for x in toks):
            # A drug must be named as written ("vitamin D" is not a trade name of folic acid's)
            if it["type"] in ("drug", "drug_class") and f" {norm(it['name'])} " not in f" {qnorm} ":
                continue
            keep(it, 2.0 + 0.2 * len(toks), toks)
    for w in q:
        for typ, ident in _domain_index().get(w, ()):
            if typ == "domain":
                keep({"type": "domain", "id": ident, "label": ident}, 1.5, [w])
            else:
                keep({"type": "theme", "theme": ident, "id": ident, "level": "theme", "label": ident}, 1.5, [w])
    # Pass 2: long word parts the first pass left over ("thyroid" ~ "Thyroid (TSH)", "cholesterol" ~ "LDL cholesterol")
    free = [w for w in q if w not in used and w not in GENERIC and len(w) >= 5]
    for it in index():
        if it["type"] not in ("theme", "lab", "nutrient", "cancer", "fitness") or it.get("exact"):
            continue
        toks = it["toks"]
        hit = {x for x in toks for w in free if len(x) >= 5 and (x.startswith(w) or w.startswith(x))}
        if hit and len(hit) * 2 >= len(toks):
            keep(it, 1.0 + 0.4 * len(hit) / len(toks), [])
    # Pass 3: Open Targets for the conditions the words name, the whole phrase first ("type 2 diabetes")
    if search:
        rest = [w for w, s in zip(qw, q) if s not in used and s not in GENERIC and w not in GENERIC and (len(w) >= 4 or w.isdigit())]
        content = [w for w in rest if not w.isdigit()]
        phrases = ([" ".join(rest)] if len(content) > 1 else []) + content[:4]
        # A Swedish question: its condition names through the explorer's own term list ("migrän" -> migraine disorder)
        swedish = bool(set(words(question)) & {"jag", "har", "för", "är", "och", "att", "mig", "min", "vilken", "vilka", "hur", "bör"})
        sv = [en for s, en in _sv_terms().items() if f" {s} " in f" {qnorm} "] if swedish else []
        cond = {}
        for ph in sv + phrases:
            want = set(words(ph))
            # A hit found by one word of a longer phrase counts for that share of the phrase only
            cover = 1.0 if ph in sv else min(1.0, len([w for w in want if not w.isdigit()]) / max(1, len(content)))
            for h in ot_diseases(ph, limit=8):
                name = set(words(h["name"]))
                overlap = len(want & name) / len(want)
                if overlap >= 0.5 and any(w[:5] in h["name"].lower() for w in want if not w.isdigit()):
                    s = 0.5 + 0.4 * overlap * cover - 0.02 * len(name - want)
                    if s > cond.get(h["id"], (0,))[0]:
                        cond[h["id"]] = (s, h, ph)
        best = sorted(cond.values(), key=lambda x: -x[0])[:5]
        for s, h, ph in best:
            if s >= best[0][0] - 0.15:
                keep({"type": "condition", "id": h["id"], "label": h["name"], "word": ph, "traits": [h["id"]]}, round(s, 2), [])
    out = sorted(found.values(), key=lambda x: (-x["score"], x["type"], x["label"]))
    return out[:limit]


def ot_diseases(text, limit=8):
    """Open Targets search for one term: [{id, name}] of diseases and traits (public, cached)."""
    text = text.strip()
    if not text:
        return []
    q = "query($q: String!) { search(queryString: $q, entityNames: [\"disease\"], page: {index: 0, size: %d}) { hits { id name } } }" % limit

    def fetch():
        r = sources._request("POST", OT_API, json={"query": q, "variables": {"q": text}}, timeout=30)
        return [{"id": h["id"], "name": h["name"]} for h in ((r or {}).get("data", {}).get("search", {}).get("hits") or [])]
    try:
        return sources._cached("agent_ot_search", f"{text}|{limit}", fetch)
    except Exception:
        return []


# --- The kind of question --------------------------------------------------------------------------------------

KINDS = [
    ("rank", r"\b(which|what)\b.*\b(most|least|highest|lowest|biggest|greatest|top|likeliest|likely)\b|\bvilk(en|et|a)\b.*\b(mest|minst|störst|högst|troligast)\b|\brank"),
    ("action", r"\b(should|avoid|careful|caution|best|safe|work(s)? (best|for)|how (to|should|can|do)|tips?|advice|recommend|bör|undvika|försiktig|bäst|råd|hur ska|hur kan)\b"),
    ("propensity", r"\b(do i have|am i|risk|propens\w*|predispos\w*|suscept\w*|chance|likel\w*|prone|tendency|genetic(ally)?|anlag|benägen\w*|risk)\b"),
    ("gene", r"\b(gene|genen|genes)\b.*\b(affect|do|mean|role|påverka|betyder)\b|\bwhat does\b.*\b[A-Z][A-Z0-9]{2,}\b"),
]
UNKNOWN = [
    ("mortality", r"\b(die|dying|death|mortality|fatal|kill|dö|döden|dödlighet|dödlig)\b",
     "Genetics doesn't tell what anyone will die from: that depends on how common and how deadly each disease is, on age, "
     "on lifestyle and on screening, and the explorer has no mortality data. What it can tell is which ones the genes make more likely."),
    ("timing", r"\b(when will|at what age|how old|hur gammal|när kommer)\b",
     "Genetics doesn't give an age at which something happens; it can tell whether the genes make it more or less likely."),
    ("certainty", r"\b(will i (get|have|develop)|kommer jag (få|att få))\b",
     "No genotype makes a common disease certain or rules it out; the genes shift the likelihood, and that is what is shown."),
]


def kind(question, items):
    """(kinds, unknowns): the answer shapes the question wants, first one leading, and the parts it asks for that the
    data can't give, each with the sentence that says so."""
    q = question.lower()
    kinds = [k for k, pat in KINDS if re.search(pat, q if k != "gene" else question, re.I)]
    if any(i["type"] == "gene" for i in items) and "gene" not in kinds:
        kinds.append("gene")
    if not kinds:
        kinds = ["propensity"]
    # A ranking over one named thing is a propensity question about it
    if kinds[0] == "rank" and len({(i["type"], i["id"]) for i in items if i["score"] >= 2}) == 1 and not re.search(r"\b(types?|kinds?|which|vilk)", q):
        kinds = kinds[1:] or ["propensity"]
    # "Which gene matters most" asks for the genes' effects, not a ranking of scores
    if kinds[0] == "rank" and re.search(r"\b(genes?|genen|gener|variants?)\b", q):
        kinds[0] = "action"
    unknowns = [{"id": k, "text": text} for k, pat, text in UNKNOWN if re.search(pat, q)]
    return kinds, unknowns
