"""The summary in words: a small model reads each public finding once, this machine assembles the person's summary.

    interpret.cluster("muscle")                  # every finding of the cluster, read once and cached (no person)
    interpret.summary(quick_result, "XY")        # the person's summary from those readings, on this machine

Privacy (docs/architecture/ask-decisions.md, D1): the model is never told whose genome it is or which findings apply.
It reads ALL of a cluster's findings, the same for everyone, and for each one writes a plain reading per genotype group
the sentence names ("If you carry the C allele: ..."). This machine then picks the readings for the person's own
groups and puts them together. The words come from the model; the choice of words, from the person's genome, never
leaves the machine.

Facts from sources: a reading may only use the numbers its sentence gives (checked), a group label must be written in
the sentence (checked), and a takeaway is kept apart from the finding and must follow from it.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from cluster_analysis import sources
from cluster_analysis.agent import cost, language, morsels

MODEL_API = os.environ.get("DNA_AGENT_SMALL_MODEL", "claude-haiku-5-5")
MODEL_CC = os.environ.get("DNA_AGENT_SMALL_CC", "haiku")
BATCH = 18

SYSTEM = """You turn sentences from research abstracts into plain readings for people with a given genotype. For each sentence, list the genotype groups it names (write each label exactly as it appears in the sentence: "TT", "AC", "C allele carriers", "XX"). For each group write:
- reading: one sentence addressed to "you" that stands on its own: start with what was studied, using the paper title for context (e.g. "With caffeine before lifting, ..."), then what the study found for people in this group, relative to the other group if it compares. Keep the sentence's numbers exactly as written and only for the group they belong to; add no number it doesn't give.
- takeaway: one short sentence on what the finding means for the risk, level or response of people in this group (e.g. "Caffeine is likely to raise your lifting speed less than for AA carriers."), or "" if nothing follows. Never stronger than the study, never an instruction.
Plain words, no jargon, no hedging boilerplate. Use only what the sentence says.""" + "\n" + language.RULE

SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "groups": {"type": "array", "items": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "reading": {"type": "string"}, "takeaway": {"type": "string"},
                               "direction": {"type": "string", "enum": ["better", "worse", "no difference", "unclear"]}},
                "required": ["label", "reading", "takeaway", "direction"], "additionalProperties": False}}},
        "required": ["id", "groups"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False}

NUM = re.compile(r"\d+(?:\.\d+)?")
# Names that carry digits but are not figures: gene symbols (CYP1A2, ADORA2A), variant ids, 1RM
NAMES = re.compile(r"\b(?:[A-Z][A-Za-z]*\d[A-Za-z0-9]*|rs\d+|\d+RM|[A-Z]\d+[A-Z]?)\b")


def figures(text):
    return set(NUM.findall(NAMES.sub(" ", text or "")))


def fid(m):
    return hashlib.sha1((m["pmid"] + "|" + m["sentence"]).encode("utf-8")).hexdigest()[:14]


def _cache_path(i):
    return os.path.join(sources.CACHE_DIR, f"agent_interp_{i}.json")


def cached(i):
    p = _cache_path(i)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def check(item, sentence):
    """Keeps only what the sentence supports: group labels written in it, numbers it gives."""
    s = sentence.lower()
    nums = figures(sentence)
    groups = []
    for g in item.get("groups") or []:
        if g["label"].lower() not in s:
            continue
        if not figures(g["reading"]) <= nums:
            continue
        if language.advice(g["reading"]):
            continue
        if not figures(g.get("takeaway") or "") <= nums or language.advice(g.get("takeaway") or ""):
            g = {**g, "takeaway": ""}
        groups.append(g)
    return {"groups": groups}


def _ask(prompt, system=None, schema=None):
    """One structured call on the small model: (object, usage). The API with a key, else Claude Code."""
    from cluster_analysis.agent import run
    system, schema = system or SYSTEM, schema or SCHEMA
    if run.backend() == "api":
        import anthropic
        client = anthropic.Anthropic(api_key=run.api_key())
        msg = client.messages.create(model=MODEL_API, max_tokens=16000, system=system,
                                     messages=[{"role": "user", "content": prompt}],
                                     output_config={"format": {"type": "json_schema", "schema": schema}})
        text = next(b.text for b in msg.content if b.type == "text")
        return json.loads(text), cost.of(MODEL_API, msg.usage)
    cli = run.claude_cli()
    if not cli:
        raise RuntimeError("No API key and no Claude Code command line.")
    # The prompt goes in on stdin: a long one passes the 32k-character limit of a Windows command line
    p = subprocess.run([cli, "-p", "--output-format", "json", "--json-schema", json.dumps(schema), "--tools", "",
                        "--model", MODEL_CC, "--system-prompt", system, "--no-session-persistence"],
                       input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    d = json.loads(p.stdout)
    if d.get("is_error") or not d.get("structured_output"):
        raise RuntimeError(str(d.get("result"))[:300])
    return d["structured_output"], cost.of(MODEL_CC, d.get("usage") or {})


def _batch(ms):
    prompt = "Sentences (JSON):\n" + json.dumps([{"id": fid(m), "gene": m["gene"], "paper": m["title"], "sentence": m["sentence"]} for m in ms], ensure_ascii=False)
    out, usage = _ask(prompt)
    by = {x["id"]: x for x in out.get("items", [])}
    for m in ms:
        i = fid(m)
        if i in by:
            with open(_cache_path(i), "w", encoding="utf-8") as f:
                json.dump(check(by[i], m["sentence"]), f, ensure_ascii=False)
    return usage


def cluster(theme, emit=lambda ev: None):
    """Reads every finding of a cluster that has no reading yet: the same work for everyone, done once.
    Returns the tokens used ({input, output}; zero when everything was cached)."""
    have, _ = morsels.cached(theme)
    todo = [m for ms in have.values() for m in ms if cached(fid(m)) is None]
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


def _mine(group_label, labels):
    """Whether a group the study names is one the person belongs to ("C allele carriers" for a CT)."""
    g = group_label.lower()
    for x in labels:
        x = x.lower()
        if g == x or re.search(rf"\b{re.escape(x)}\b", g):
            return True
    return False


def summary(result, person):
    """The person's summary from the cached readings: a sentence per finding that applies (one per gene, the
    question's own words and numbers first), each with its takeaway and source. Built on this machine."""
    out = []
    for f in (result.get("summary") or {}).get("findings") or []:
        r = cached(fid({"pmid": f["url"].rsplit("/", 1)[-1], "sentence": f["sentence"]}))
        if not r:
            continue
        labs = morsels.labels(f["genotype"], f.get("ref"), f.get("alt"), f.get("amino")) | set(f.get("yours") or [])
        g = next((g for g in r["groups"] if _mine(g["label"], labs)), None)
        if not g:
            continue
        out.append({"gene": f["gene"], "rsid": f.get("rsid"), "genotype": f["genotype"], "reading": g["reading"], "direction": g["direction"],
                    "takeaway": g.get("takeaway") or "", "type": f["type"], "year": f["year"], "url": f["url"],
                    "title": f["title"], "numbers": f["numbers"]})
    return out
