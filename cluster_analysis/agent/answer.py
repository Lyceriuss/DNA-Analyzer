"""The agent's answer: a template written without the person, checked against what the tools showed, filled in here.

The model hands in its answer through the submit_answer tool (SCHEMA). validate() rejects it, with the reasons, unless
  - every variant was looked up with variant() and has its two alleles, and the effect allele is one of them;
  - every variant has a reading for 0, 1 and 2 copies;
  - every cited source is one a tool returned in this run;
  - every quote is text a tool returned for that source (read_paper, ClinPGx, ClinVar, UniProt);
  - every percentage or fold change in a text appears in the texts of the sources that text cites.
The model gets the reasons back and fixes the answer. save() stores the checked answer with the variants' alleles
and the cited sources. fill() reads the person's calls for those variants on this machine and picks each variant's
reading: the only step that touches the person's genome, and it makes no network call.
"""
import json
import os
import re
import time
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "output", "agent")
ANSWERS = os.path.join(OUT, "answers")
FILLS = os.path.join(OUT, "fills")
FLIP = str.maketrans("ACGT", "TGCA")
USABLE = ("measured", "high", "medium")

_STR = {"type": "string"}
_SOURCES = {"type": "array", "items": _STR, "minItems": 1,
            "description": "Ref ids exactly as the tools gave them: 'PMID:123', 'GWAS:GCST0001', 'ClinVar:…', 'ClinPGx:…', 'UniProt:GENE', 'Theme:muscle'."}
_QUOTES = {"type": "array", "items": {"type": "object", "properties": {"source": _STR, "text": {
    "type": "string", "description": "Verbatim from that source's text as a tool returned it; join separate parts with ' … '."}},
    "required": ["source", "text"], "additionalProperties": False}}

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "A short title for the answer."},
        "summary": {"type": "string", "description": "2-4 sentences: what genetics can and cannot say about this question, "
                    "for anyone. No genotype: the person's readings are filled in later."},
        "scope": {"type": "string", "description": "How the genes and variants were chosen, and what was left out and why."},
        "axes": {"type": "array", "maxItems": 4, "description": "Optional directions the readings can lean, e.g. power and "
                 "endurance. This machine counts the person's leanings; leave empty if the question has none.",
                 "items": {"type": "object", "properties": {"id": {"type": "string", "pattern": "^[a-z_]{2,20}$"}, "name": _STR,
                                                            "about": _STR},
                           "required": ["id", "name", "about"], "additionalProperties": False}},
        "groups": {"type": "array", "minItems": 1, "maxItems": 8, "items": {
            "type": "object",
            "properties": {
                "title": _STR, "intro": _STR,
                "variants": {"type": "array", "minItems": 1, "maxItems": 12, "items": {
                    "type": "object",
                    "properties": {
                        "rsid": _STR, "gene": _STR,
                        "effect_allele": {"type": "string", "enum": ["A", "C", "G", "T"],
                                          "description": "On the forward strand: one of the two alleles variant() gave."},
                        "effect": {"type": "string", "description": "What the effect allele does, from the sources."},
                        "readings": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
                            "type": "object",
                            "properties": {"copies": {"type": "integer", "enum": [0, 1, 2]},
                                           "text": {"type": "string", "description": "What carrying this many copies means for the question."},
                                           "lean": {"type": ["string", "null"], "description": "An axis id, or null."}},
                            "required": ["copies", "text", "lean"], "additionalProperties": False}},
                        "strength": {"type": "string", "enum": ["established", "suggestive", "weak"],
                                     "description": "established: replicated genome-wide or meta-analysis; suggestive: one large "
                                                    "study or consistent smaller ones; weak: candidate-gene findings that did not replicate."},
                        "sources": _SOURCES, "quotes": _QUOTES},
                    "required": ["rsid", "gene", "effect_allele", "effect", "readings", "strength", "sources", "quotes"],
                    "additionalProperties": False}}},
            "required": ["title", "intro", "variants"], "additionalProperties": False}},
        "research": {"type": "array", "description": "What studies found that applies to anyone (training response, heritability, "
                     "trials), each with its sources.",
                     "items": {"type": "object", "properties": {"text": _STR, "sources": _SOURCES, "quotes": _QUOTES},
                               "required": ["text", "sources", "quotes"], "additionalProperties": False}},
        "practice": {"type": "array", "description": "Practical advice. when=null applies to everyone; when={rsid, copies} only "
                     "to people with that many copies of that answer variant's effect allele.",
                     "items": {"type": "object", "properties": {
                         "text": _STR, "sources": _SOURCES,
                         "when": {"type": ["object", "null"], "properties": {
                             "rsid": _STR, "copies": {"type": "array", "items": {"type": "integer", "enum": [0, 1, 2]}, "minItems": 1}},
                             "required": ["rsid", "copies"], "additionalProperties": False}},
                         "required": ["text", "sources", "when"], "additionalProperties": False}},
        "limits": {"type": "array", "minItems": 1, "items": _STR,
                   "description": "What this cannot tell, and what would (a test, a trial of training, a measurement)."},
    },
    "required": ["title", "summary", "scope", "axes", "groups", "research", "practice", "limits"],
    "additionalProperties": False,
}

TOOL = {"name": "submit_answer", "eager_input_streaming": True, "input_schema": SCHEMA,
        "description": "Hand in the finished answer. It is checked against what the tools returned in this run; if a check "
                       "fails, the reasons come back and the answer must be corrected and submitted again."}

NUMBER = re.compile(r"(\d+(?:[.,]\d+)?)\s?(?:%|-fold|\s?fold|\s?percent|\s?times\b)", re.I)


def norm(text):
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[‐-―−]", "-", t)
    return re.sub(r"\s+", " ", t).strip()


def _quote_ok(quote, texts):
    pool = [norm(t) for t in texts]
    parts = [p.strip(" .,;") for p in re.split(r"\s*(?:…|\.\.\.)\s*", norm(quote)) if p.strip(" .,;")]
    return bool(parts) and all(any(p in t for t in pool) for p in parts)


def shape(value, schema, where="answer"):
    """Problems with a value against the JSON schema subset SCHEMA uses (an MCP client's answer arrives unchecked)."""
    errs, kind = [], schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    ok = {"object": dict, "array": list, "string": str, "integer": int, "null": type(None)}
    if kind and not any(isinstance(value, ok[k]) and not (k == "integer" and isinstance(value, bool)) for k in kinds):
        return [f"{where}: must be {' or '.join(kinds)}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{where}: must be one of {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and not re.fullmatch(schema["pattern"], value):
        errs.append(f"{where}: must match {schema['pattern']}")
    if isinstance(value, dict) and "properties" in schema:
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{where}: missing field {k}")
        for k, v in value.items():
            if k not in schema["properties"]:
                errs.append(f"{where}: unknown field {k}")
            else:
                errs += shape(v, schema["properties"][k], f"{where}.{k}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 10**9):
            errs.append(f"{where}: needs {schema.get('minItems', 0)} to {schema.get('maxItems', 'any')} items")
        for i, x in enumerate(value):
            errs += shape(x, schema.get("items", {}), f"{where}[{i}]")
    return errs


def validate(ans, led):
    """The reasons the answer can't be shown, or []."""
    errs = []
    errs = shape(ans, SCHEMA)
    if errs:
        return errs[:40]
    axes = {a.get("id") for a in ans.get("axes") or []}
    rsids = set()

    def sources_ok(where, item):
        srcs = item.get("sources") or []
        if not srcs:
            errs.append(f"{where}: cite at least one source")
        for s in srcs:
            if s not in led.refs:
                errs.append(f"{where}: source {s!r} was not returned by any tool in this run")
        for q in item.get("quotes") or []:
            if q.get("source") not in led.refs:
                errs.append(f"{where}: quote source {q.get('source')!r} was not returned by any tool")
            elif not _quote_ok(q.get("text", ""), led.texts.get(q["source"], [])):
                errs.append(f"{where}: the quote {q.get('text', '')[:80]!r} is not in the text the tools returned for "
                            f"{q['source']} (quote word for word, or read the paper with read_paper first)")
        pool = norm(" ".join(t for s in srcs for t in led.texts.get(s, [])) + " "
                    + " ".join(q.get("text", "") for q in item.get("quotes") or []))
        for field in ("text", "effect"):
            for m in NUMBER.finditer(item.get(field) or ""):
                if m.group(1).replace(",", ".") not in pool.replace(",", "."):
                    errs.append(f"{where}: the figure {m.group(0)!r} is not in the texts of the sources it cites; quote "
                                "the source that gives it or leave it out")

    for gi, g in enumerate(ans.get("groups") or []):
        for vi, v in enumerate(g.get("variants") or []):
            where = f"groups[{gi}].variants[{vi}] ({v.get('rsid')})"
            rs = (v.get("rsid") or "").lower()
            site = led.variants.get(rs)
            if not site:
                errs.append(f"{where}: look the variant up with variant() before using it")
            elif not site.get("ref"):
                errs.append(f"{where}: the variant has no 1000 Genomes alleles, so it can't be read from a genome; leave it out")
            elif v.get("effect_allele") not in (site["ref"], site["alt"]):
                hint = " (the study's allele is on the other strand: use its complement)" \
                    if (v.get("effect_allele") or "").translate(FLIP) in (site["ref"], site["alt"]) else ""
                errs.append(f"{where}: effect_allele {v.get('effect_allele')!r} is neither {site['ref']} nor {site['alt']}{hint}")
            if rs in rsids:
                errs.append(f"{where}: the variant appears twice")
            rsids.add(rs)
            copies = sorted(r.get("copies") for r in v.get("readings") or [])
            if copies != [0, 1, 2]:
                errs.append(f"{where}: give one reading each for 0, 1 and 2 copies")
            for r in v.get("readings") or []:
                if r.get("lean") is not None and r["lean"] not in axes:
                    errs.append(f"{where}: lean {r['lean']!r} is not an axis id")
                sources_ok(f"{where} reading {r.get('copies')}", {"text": r.get("text"), "sources": v.get("sources"), "quotes": v.get("quotes")})
            sources_ok(where, v)
    for i, r in enumerate(ans.get("research") or []):
        sources_ok(f"research[{i}]", r)
    for i, p in enumerate(ans.get("practice") or []):
        sources_ok(f"practice[{i}]", p)
        w = p.get("when")
        if w and (w.get("rsid") or "").lower() not in rsids:
            errs.append(f"practice[{i}]: when.rsid {w.get('rsid')!r} is not one of the answer's variants")
    return errs


def save(question, ans, led, meta):
    """Stores a checked answer with the variants' alleles and the sources it cites; returns its id."""
    os.makedirs(ANSWERS, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:40] or "answer"
    aid = time.strftime("%Y%m%d-%H%M%S") + "-" + slug
    cited = set()
    for g in ans["groups"]:
        for v in g["variants"]:
            site = led.variants[v["rsid"].lower()]
            v["rsid"] = v["rsid"].lower()
            v["site"] = {"chrom": site["chrom"], "pos": site["pos"], "ref": site["ref"], "alt": site["alt"], "eur_af": site["eur_af"]}
            v["effect_freq"] = (site["eur_af"] if v["effect_allele"] == site["alt"] else 1 - site["eur_af"]) if site["eur_af"] is not None else None
            cited |= set(v["sources"]) | {q["source"] for q in v["quotes"]}
    for r in ans["research"]:
        cited |= set(r["sources"]) | {q["source"] for q in r["quotes"]}
    for p in ans["practice"]:
        cited |= set(p["sources"])
    doc = {"id": aid, "question": question, "created": time.strftime("%Y-%m-%d %H:%M"), **meta, "answer": ans,
           "refs": {k: led.refs[k] for k in sorted(cited) if k in led.refs}}
    with open(os.path.join(ANSWERS, aid + ".json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return aid


def load(aid):
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[a-z0-9-]*", aid or ""):
        raise ValueError("No such answer.")
    with open(os.path.join(ANSWERS, aid + ".json"), encoding="utf-8") as f:
        return json.load(f)


def listing():
    if not os.path.isdir(ANSWERS):
        return []
    out = []
    for name in sorted(os.listdir(ANSWERS), reverse=True):
        if name.endswith(".json"):
            try:
                d = json.load(open(os.path.join(ANSWERS, name), encoding="utf-8"))
                out.append({"id": d["id"], "question": d["question"], "title": d["answer"]["title"], "created": d["created"],
                            "lang": d.get("lang", "en")})
            except (OSError, ValueError, KeyError):
                continue
    return out


# --- The local fill: the only part that reads the person's genome -----------------------------------------------------

def copies(gt, allele, ref, alt):
    """Copies of the effect allele in a forward-strand genotype; None when the genotype's letters don't fit the site
    (on a C/G or A/T site only the forward reading is used)."""
    if not gt or len(gt) != 2 or allele not in (ref, alt):
        return None
    if set(gt) <= {ref, alt}:
        return gt.count(allele)
    if {ref, alt} != {ref.translate(FLIP), alt.translate(FLIP)} and set(gt) <= {ref.translate(FLIP), alt.translate(FLIP)}:
        return gt.count(allele.translate(FLIP))
    return None


def person_file(person):
    from genome.loader import imputed_path
    with open(os.path.join(ROOT, "cluster_analysis", "profiles.json"), encoding="utf-8") as f:
        prof = next((p for p in json.load(f)["profiles"] if p["id"] == person), None)
    if not prof:
        raise ValueError(f"No profile {person}.")
    return imputed_path(os.path.join(ROOT, prof["dna"]))


def fill(aid, person):
    """The answer read for one person: each variant's genotype, copies and reading, the axes counted, the advice that
    applies. Cached until the person's file changes."""
    from genome.loader import read_calls
    doc = load(aid)
    path = person_file(person)
    stamp = os.path.getmtime(path)
    cache = os.path.join(FILLS, f"{aid}__{person}.json")
    if os.path.exists(cache):
        c = json.load(open(cache, encoding="utf-8"))
        if c.get("stamp") == stamp:
            return c
    variants = [v for g in doc["answer"]["groups"] for v in g["variants"]]
    calls = read_calls(path, {v["rsid"] for v in variants}, confidence=None)
    reads = {}
    for v in variants:
        gt, _, _, tier = calls.get(v["rsid"], (None, None, None, None))
        n = copies(gt, v["effect_allele"], v["site"]["ref"], v["site"]["alt"]) if tier in USABLE else None
        reading = next((r for r in v["readings"] if r["copies"] == n), None)
        reads[v["rsid"]] = {"genotype": gt, "confidence": tier, "copies": n,
                            "reading": reading["text"] if reading else None, "lean": reading["lean"] if reading else None,
                            "why_none": None if reading else "not in the file" if not gt else
                            f"called with {tier} confidence only" if tier not in USABLE else "the genotype doesn't fit the variant's alleles"}
    axes = []
    for a in doc["answer"]["axes"]:
        hits = [rs for rs, r in reads.items() if r["lean"] == a["id"]]
        axes.append({**a, "variants": hits})
    practice = []
    for p in doc["answer"]["practice"]:
        w = p.get("when")
        if not w:
            practice.append({**p, "applies": True})
        else:
            practice.append({**p, "applies": reads.get(w["rsid"].lower(), {}).get("copies") in w["copies"]})
    out = {"answer": aid, "person": person, "stamp": stamp, "reads": reads, "axes": axes, "practice": practice,
           "read": sum(1 for r in reads.values() if r["copies"] is not None), "of": len(reads)}
    os.makedirs(FILLS, exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return out
