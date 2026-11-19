"""Understanding the question: a small model maps it onto what the explorer holds, before anything is looked up.

    route.items("What way of working out would suit me best?")  ->  (items, kinds, unknowns, usage)

The model sees the question and a compact catalogue of the explorer (clusters with their mechanisms and phases,
cancer types, lab tests, nutrients, fitness tests, and that medicines, genes and any condition can be asked about).
It returns, in a fixed structure, which of those the question is about, what kind of answer it wants, which parts
can't be known, and English names for conditions, drugs and genes. Only ids from the catalogue are kept; drugs,
genes and conditions are checked against the term index and Open Targets as before (terms.py). No personal data goes
in: only the question, which a deep analysis would send anyway.

Without an API key or Claude Code, terms.match (rules) answers alone. With them, both run and their items are
merged, the model's first.
"""
import glob
import hashlib
import json
import os

from cluster_analysis.agent import terms

PKG = terms.PKG
CACHE = os.path.join(terms.ROOT, "data", "output", "agent", "routes2")

SYSTEM = """You read a person's question about their own genome and say which parts of a genome explorer can answer \
it. Choose ids only from the catalogue; leave a list empty when nothing fits. Think about what the question is really \
after: "what way of working out suits me" is about training (the fitness cluster: muscle fibre type, recovery, \
injury, fuel, and the fitness tests), "will I get fat" about weight and metabolism, "can I drink coffee at night" \
about caffeine. Pick the most relevant few, not everything.
kind: rank (which of several is most or least), action (what to do or avoid, what suits them), propensity (are they \
prone to something), gene (what a named gene does in them).
unknown: the parts the genome can't answer: mortality (what they will die from), timing (at what age), certainty \
(whether they will surely get something).
conditions, drugs, genes: English names as a doctor would write them, only if the question names or clearly implies \
them. terms: 2-5 English search words for the research on this question.
reading: one sentence, addressed to the person, saying what you understood they want and how the explorer will answer \
it; if part of it can't be answered from a genome, say so and say what will be answered instead.
plan: 2-5 short steps, in order, each naming the part of the explorer or the source it uses and why (e.g. "Read your \
metaboliser types for the drug-processing genes (ClinPGx)", "Match them to the dosing guidelines (CPIC, DPWG)")."""


def catalogue():
    """The explorer's askable items, compact: what the model may choose from."""
    lines = []
    for path in sorted(glob.glob(os.path.join(PKG, "themes", "theme_graph_*.json"))):
        with open(path, encoding="utf-8") as f:
            g = json.load(f)
        mech = "; ".join(f"{m['id']}={m['name']}" for m in g.get("mechanisms") or [])
        phases = "; ".join(f"{o['id']}={o['name']}" for o in g.get("organs") or [])
        lines.append(f"cluster {g['theme']} ({g['name']}{', ' + g['sex'] if g.get('sex') else ''}): mechanisms {mech} | phases {phases}")
    for cfg, label in (("cancers.json", "cancer"), ("labtests.json", "lab"), ("nutrients.json", "nutrient"), ("fitness.json", "fitness")):
        path = os.path.join(PKG, "nutrition", cfg)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            items = d.get("tests") or d.get("nutrients") or []
            lines.append(f"{label} tests: " + "; ".join(f"{t['id']}={t['name']}" for t in items))
    lines.append("domains: drug (any medicine, pharmacogenetic guidance), cancer, lab, nutrient")
    return "\n".join(lines)


def _schema(cat_ids):
    s = lambda: {"type": "array", "items": {"type": "string"}}
    return {"type": "object", "properties": {
        "kind": {"type": "string", "enum": ["rank", "action", "propensity", "gene"]},
        "clusters": s(), "mechanisms": {"type": "array", "items": {"type": "object", "properties": {
            "cluster": {"type": "string"}, "id": {"type": "string"}}, "required": ["cluster", "id"], "additionalProperties": False}},
        "cancer": s(), "lab": s(), "nutrient": s(), "fitness": s(), "domains": s(),
        "drugs": s(), "genes": s(), "conditions": s(), "terms": s(),
        "unknown": {"type": "array", "items": {"type": "string", "enum": ["mortality", "timing", "certainty"]}},
        "reading": {"type": "string"}, "plan": s()},
        "required": ["reading", "plan", "kind", "clusters", "mechanisms", "cancer", "lab", "nutrient", "fitness", "domains",
                     "drugs", "genes", "conditions", "terms", "unknown"], "additionalProperties": False}


def _ask(question):
    from cluster_analysis.agent import interpret, run
    import subprocess
    cat = catalogue()
    prompt = f"Catalogue:\n{cat}\n\nQuestion: {question}"
    schema = _schema(None)
    if run.backend() == "api":
        import anthropic
        client = anthropic.Anthropic(api_key=run.api_key())
        msg = client.messages.create(model=interpret.MODEL_API, max_tokens=2000, system=SYSTEM,
                                     messages=[{"role": "user", "content": prompt}],
                                     output_config={"format": {"type": "json_schema", "schema": schema}})
        u = msg.usage
        return json.loads(next(b.text for b in msg.content if b.type == "text")), \
            {"input": u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0), "output": u.output_tokens}
    p = subprocess.run([run.claude_cli(), "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(schema), "--tools", "",
                        "--model", interpret.MODEL_CC, "--system-prompt", SYSTEM, "--no-session-persistence"],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    d = json.loads(p.stdout)
    if d.get("is_error") or not d.get("structured_output"):
        raise RuntimeError(str(d.get("result"))[:300])
    u = d.get("usage") or {}
    return d["structured_output"], {"input": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0),
                                    "output": u.get("output_tokens", 0)}


def understand(question):
    """The model's reading of the question (cached per question): (intent, usage)."""
    from cluster_analysis.agent import run
    if not run.backend():
        return None, {"input": 0, "output": 0}
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha1(terms.norm(question).encode("utf-8")).hexdigest()[:16] + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f), {"input": 0, "output": 0, "cached": True}
    intent, usage = _ask(question)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(intent, f, ensure_ascii=False)
    return intent, usage


def to_items(intent):
    """The model's choices as matched items, keeping only what exists in the explorer."""
    idx = terms.index()
    by = {}
    for it in idx:
        by.setdefault((it["type"], it.get("theme"), it["id"]), it)
    out = []

    def add(it, score=2.6):
        out.append({k: v for k, v in it.items() if k != "toks"} | {"score": score, "from": "model"})
    for th in intent.get("clusters") or []:
        it = by.get(("theme", th, th))
        if it:
            add(it)
    for m in intent.get("mechanisms") or []:
        it = by.get(("theme", m.get("cluster"), m.get("id")))
        if it:
            add(it, 2.5)
    for typ in ("cancer", "lab", "nutrient", "fitness"):
        for i in intent.get(typ) or []:
            it = next((x for x in idx if x["type"] == typ and x["id"] == i and "marker" not in x), None)
            if it:
                add(it)
    for d in intent.get("domains") or []:
        if d in ("drug", "cancer", "lab", "nutrient"):
            out.append({"type": "domain", "id": d, "label": d, "score": 2.0, "from": "model"})
    for name in (intent.get("drugs") or []) + (intent.get("genes") or []):
        out += [m | {"from": "model"} for m in terms.match(name, search=False) if m["type"] in ("drug", "gene") and m["score"] >= 2]
    for name in intent.get("conditions") or []:
        out += [m | {"from": "model"} for m in terms.match(name) if m["type"] == "condition"][:2]
    return out


class NotUnderstood(Exception):
    """The question couldn't be read by the model: no answer is given rather than a guess."""


def items(question):
    """(items, kinds, unknowns, usage): the model's reading only. There is no rule-based fallback and no merging with
    word matches (a word like "response" pulled in training mechanisms for a paracetamol question): without the
    model, or when its reading names nothing the explorer holds, NotUnderstood is raised and nothing is answered.
    terms.match is still used to resolve the names the model gives (a drug, a gene, a condition) to the explorer's
    items: that is lookup of what the model chose, not matching of the question."""
    from cluster_analysis.agent import run
    if not run.backend():
        raise NotUnderstood("Ask needs Claude connected (an API key, or Claude Code logged in): without it, no answer is given.")
    try:
        intent, usage = understand(question)
    except Exception as e:
        raise NotUnderstood(f"Claude couldn't read the question ({type(e).__name__}: {str(e)[:200]}).")
    merged = to_items(intent)
    if not merged:
        raise NotUnderstood("Claude read the question, but nothing in the explorer matches what it asks"
                            + (f": {intent.get('reading')}" if intent.get("reading") else "."))
    kinds = [intent["kind"]]
    texts = {k: t for k, _, t in terms.UNKNOWN}
    unknowns = [{"id": u, "text": texts[u]} for u in intent.get("unknown") or [] if u in texts]
    usage["terms"] = intent.get("terms")
    usage["reading"] = intent.get("reading")
    usage["plan"] = intent.get("plan") or []
    return merged, kinds, unknowns, usage
