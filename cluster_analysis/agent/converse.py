"""An Ask turn: Claude reads the question, works through the explorer's tools, researches what local data doesn't
answer, and explains; this machine adds the person's own results and readings.

    converse.ask(question, person, session_id=None, emit=print)  ->  (session, turn)

1. understand  Claude's first call states its reading and plan (shown at once).
2. tools       public tools return their results to Claude; personal tools put the person's results on their screen
               and give Claude only their shape; views draw the explorer's own views in the answer (tools.py).
3. research    when the local data doesn't answer the question (it rarely does on its own), Claude researches: the
               drug's annotations, the genes and variants, genotype-specific studies, papers it reads.
4. answer      a general explanation, its citations checked against what the tools returned, and follow-ups.
5. readings    on this machine: the readings for the person's own results (categories.py) and for the studies'
               genotype groups (interpret.py), written once for everyone and picked here.

Backends: with an API key, the Messages API in a loop (run.MODEL family); without, Claude Code (claude -p) with the
same tools served by the MCP server (mcp_server.py), which writes the turn's results to a file this reads back.
"""
import json
import os
import re
import subprocess
import sys
import time

from cluster_analysis.agent import categories, interpret, language, morsels, providers, session as sess, tools

ROOT = sess.ROOT
MODEL_API = os.environ.get("DNA_AGENT_CONVERSE_MODEL", "claude-sonnet-5-5")
MODEL_CC = os.environ.get("DNA_AGENT_CONVERSE_CC", "sonnet")
MAX_TURNS = 24

SYSTEM = """You answer a person's question about their own genome with a genome explorer that runs on their computer, \
through tools.

Work in this order:
1. Call understand first: one sentence on what you understood they want (and what a genome can and can't answer \
about it), and a short plan naming the tools you will use.
2. Find what the question refers to (resolve, catalogue; a drug by any name, misspelled or not: paracetamol is \
acetaminophen).
3. Read the person's own results with the my_* tools. {results_rule}
4. Judge whether what is on the person's screen answers the question: each my_* result says what kind of answer it put \
there (screen_has), never its content. When it holds the answer (dosing guidelines, ClinPGx texts for their own \
genotypes, their scores), explain it from the public facts behind it (drug, gene, cluster) and finish: don't research \
further unless the person asks for depth. When it doesn't (no guideline and no annotation, a training or diet question, \
nothing for a named condition), research: research_genotypes on the strongest variants for the question, or the key \
study with read_paper. Use the public tools to learn what the evidence says: drug \
(guidelines and the effect of every genotype), gene, variant, cluster, research_genotypes (studies reporting results \
by genotype for the variants that matter), search_papers and read_paper for depth. Prefer meta-analyses, trials and \
large studies.
5. Answer in text, statistics and graphs. Draw the explorer's views: show_pathway for a gene's pathway (built live \
from Reactome when the explorer lacks it), show_nutrient for a nutrient's uptake and conversion steps with the \
person's variants, show_cluster for a gene's network, show_medicine for a drug, show_papers for a research digest \
(recent_papers for the newest studies on a gene, a muscle group or a topic). Put the key figures in the answer's \
highlights.
6. Finish with answer: highlights first (2-5 key figures, 'label | value | source ref', each figure taken from that \
source's text; effects, risks and sizes, never how common a genotype is), then a short plain explanation for anyone (the app adds the person's own readings and numbers next to \
it), citing the refs the tools returned as [PMID:123] or [ClinPGx:456], and 2-4 follow-up questions. Lead with the \
signal: the strongest finding first, in one or two sentences. No "practical approach" or "what to do" section.

Every link you draw between a result and the question's subject (a food, a type of training, a drug, an exposure) must come from a tool result and be cited: research it (search_papers, recent_papers, research_genotypes, read_paper) or leave it out. Never fill in from general knowledge; the answer cites its sources.

A follow-up question builds on the conversation so far: use it, don't repeat work you already did. If the person asks \
about a study or item from an earlier answer, read it (read_paper with find=[...] for the full text). No \
disclaimers; say plainly what the evidence can't tell. Keep to about 15 tool calls.
""" + language.RULE


def _score_direction(c):
    """A result card's direction: a guideline change needs attention; a score is favourable or not by which way is
    better for it (HDL high: favourable; LDL high: attention); a score without a better side is information."""
    if c["provider"] == "medicines":
        return "bad" if c["level"] == "differs" else "info"
    up, down = c["level"] in ("high", "raised"), c["level"] in ("low", "lowered")
    if not (up or down) or c.get("higher") not in ("better", "worse"):
        return "info"
    return "good" if (up and c["higher"] == "better") or (down and c["higher"] == "worse") else "bad"


def direction(text):
    """Whether a finding reads favourable for the person (good), needs attention (bad) or is information (info)."""
    t = (text or "").lower()
    if re.search(r"(decreased|reduced|lower)(?:, but not absent,)? (risk|chance) (of|for)|protect|(better|increased|greater) response|less toxicity", t):
        return "good"
    if re.search(r"(increased|higher|greater) (risk|chance|severity) (of|for)|toxicity|adverse|hypersensitivity|poor response|"
                 r"(decreased|reduced|less|lower) (pain relief|relief|response|efficacy|effect)|"
                 r"decreased (response|efficacy)|failure", t):
        return "bad"
    return "info"


SHARED = ("They go to the person's screen, and you also get them as interpreted results (a gene's type, a score's band "
          "and which way is better, the genotype a finding applies to): weave them into the summary.")
BLIND = ("You never see their values: the results go to their screen and you get back only what kind of result was "
         "shown. Never ask for or guess their genotypes; write the summary so it holds for anyone.")


def system_prompt(share):
    return SYSTEM.replace("{results_rule}", SHARED if share else BLIND)


def _research_for_person(person, findings):
    """The research findings that name the person's own genotype group, read on this machine."""
    from cluster_analysis.agent import index
    from cluster_analysis.agent.answer import person_file
    from genome.loader import read_calls
    by = {}
    for m in findings:
        by.setdefault(m["rsid"], []).append(m)
    if not by:
        return []
    calls = read_calls(person_file(person), set(by), confidence=("measured", "high", "medium"))
    sport = {r["rsid"]: r for r in providers.rows("sport_snps", person)}
    out = []
    for rs, ms in by.items():
        gt = (calls.get(rs) or (None,))[0]
        site = (index.query("SELECT ref, alt FROM sites WHERE rsid = ?", rs) or [{}])[0]
        if not gt or not site:
            continue
        amino = (sport.get(rs) or {}).get("amino_acids")
        for m in morsels.apply(ms, gt, site.get("ref"), site.get("alt"), amino)[:2]:
            out.append({"gene": m["gene"], "rsid": rs, "genotype": gt, "yours": m["yours"], "ref": site.get("ref"), "alt": site.get("alt"),
                        "amino": amino, "sentence": m["sentence"], "numbers": m["numbers"], "type": m["type"], "year": m["year"],
                        "title": m["title"], "url": m["url"]})
    return out


def readings(person, cards, findings, emit):
    """The readings for the person: their own results' categories and the studies' genotype groups. The model writes
    whole domains and every finding (never a selection); this machine picks."""
    from cluster_analysis.agent import run
    usage = {"input": 0, "output": 0}
    add = lambda u: {k: usage[k] + u[k] for k in usage}
    doms, conds = categories.domains_of(cards)
    if run.backend():
        for d in sorted(doms):
            usage = add(categories.ensure(d, emit=emit))
        for c in sorted(conds):
            usage = add(categories.ensure(universe=categories.conditions(c), emit=emit))
        todo = [m for m in findings if interpret.cached(interpret.fid(m)) is None]
        if todo:
            emit({"type": "step", "step": "interpret", "sources": ["claude"], "findings": len(todo)})
            for i in range(0, len(todo), interpret.BATCH):
                usage = add(interpret._batch(todo[i:i + interpret.BATCH]))
    picked = []
    order = {"differs": 0, "high": 0, "low": 1, "raised": 1, "lowered": 2, "typical": 3}
    for c in sorted(cards, key=lambda c: order.get(c["level"], 4)):
        k = categories.key_of(c, person)
        x = categories.cached(k) if k else None
        if x and not (c["level"] == "typical" and len(picked) >= 3):
            picked.append({"source": "guideline" if c["provider"] == "medicines" else "score", "gene": c["title"],
                           "reading": x["reading"], "takeaway": x["takeaway"], "url": None,
                           "direction": _score_direction(c),
                           "link": (c.get("links") or [None])[0], "title": c["title"], "type": c["provider"], "year": ""})
    # The gene results a named drug's guidelines depend on: the person's alleles and their activity (the "expression"
    # a metabolism gene has), with the written reading for that result; genes a chip can't read, said so
    phen = {g["gene"]: g for g in providers.rows("med_genes", person)}
    gene_rows = []
    for c in cards:
        if c["provider"] != "medicines" or c.get("gene") or str(c.get("id", "")).endswith(":annotations"):
            continue
        for g in c.get("genes") or []:
            p = phen.get(g)
            if not p:
                continue
            k = f"med|{g}|{categories.cpic_result(g, p['phenotype'])}"
            x = categories.cached(k) or {}
            gene_rows.append({"source": "CPIC guideline", "gene": g, "variants": [], "genotypes": [p["alleles"]],
                              "effect": p["phenotype"], "reading": x.get("reading") or c.get("headline", ""),
                              "takeaway": x.get("takeaway", ""), "direction": "good" if p.get("typical") else "bad",
                              "url": None, "link": (c.get("links") or [None])[0], "title": g, "type": "guideline", "year": ""})
        for g in c.get("unread_genes") or []:
            if g not in phen:
                gene_rows.append({"source": "CPIC guideline", "gene": g, "variants": [], "genotypes": ["not read"],
                                  "effect": "Not readable from a genotyping chip",
                                  "reading": f"The guideline also uses {g}, which a genotyping chip can't read reliably, so this result is unknown.",
                                  "takeaway": "", "direction": "info", "url": None, "link": (c.get("links") or [None])[0],
                                  "title": g, "type": "guideline", "year": ""})
    picked = gene_rows + picked
    # ClinPGx annotations for the person's own genotypes: ClinPGx writes a text for every genotype (public), and the
    # person's are picked locally (providers/tools my_medicine), strongest evidence first
    for c in cards:
        if str(c.get("id", "")).endswith(":annotations"):
            merged = {}
            for r in c.get("rows") or []:
                text = re.split(r"(?<=\.)\s+(?:Other genetic|SNP was specified)", r["value"])[0].strip()
                # The same effect in one gene family (UGT1A, UGT1A;UGT1A9) at several variants is one finding
                key = ((r.get("gene") or "").split(";")[0], (r.get("effect") or text).lower())
                # A star-allele annotation of a gene already shown as a gene result says the same again
                if not r.get("effect") and (r.get("gene") or "") in {g["gene"] for g in gene_rows}:
                    continue
                if key in merged:  # the same finding at variants inherited together (rs1042640, rs8330): one row
                    merged[key]["variants"].append(r.get("variant"))
                    merged[key]["genotypes"].append(r.get("genotype"))
                    continue
                merged[key] = {"source": "ClinPGx", "gene": r.get("gene") or "", "variants": [r.get("variant")],
                               "genotypes": [r.get("genotype")], "level": r.get("level"), "effect": r.get("effect") or "",
                               "reading": text, "takeaway": "", "direction": direction(r.get("effect") or text),
                               "status": r.get("status"), "url": r.get("url"), "link": (c.get("links") or [None])[0],
                               "title": f"{r.get('gene')} {r.get('variant')}", "type": "ClinPGx", "year": ""}
            picked += list(merged.values())[:6]
    # Study findings: from the person's own cluster cards and from research done in this turn
    mine = [dict(m, ref=m.get("ref"), alt=m.get("alt")) for c in cards for m in (c.get("findings") or [])]
    mine += _research_for_person(person, findings)
    found = interpret.summary({"summary": {"findings": mine}}, person)
    for f in found:
        f["source"] = "study"
        f["direction"] = {"better": "good", "worse": "bad"}.get(f.get("direction"), "info")
    return picked[:8] + found[:6], usage


def _engine_api(prompt, ctx, s, emit, stop):
    import anthropic
    from cluster_analysis.agent import run
    client = anthropic.Anthropic(api_key=run.api_key(), max_retries=4)
    messages = [{"role": "user", "content": prompt}]
    usage = {"input": 0, "output": 0}
    for _ in range(MAX_TURNS):
        if stop and stop():
            raise RuntimeError("Stopped.")
        msg = client.messages.create(model=MODEL_API, max_tokens=8000, system=system_prompt(ctx["share"]), tools=tools.schemas(), messages=messages,
                                     cache_control={"type": "ephemeral"}, output_config={"effort": "medium"})
        u = msg.usage
        usage["input"] += u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
        usage["output"] += u.output_tokens
        emit({"type": "usage", **usage, "cache_read": 0, "cache_write": 0})
        messages.append({"role": "assistant", "content": msg.content})
        uses = [b for b in msg.content if b.type == "tool_use"]
        if not uses:
            break
        results = []
        for b in uses:
            emit({"type": "tool", "name": b.name, "input": b.input, "kind": tools.KIND.get(b.name)})
            text, err = tools.call(ctx, b.name, b.input)
            ctx.setdefault("calls", []).append({"name": b.name, "args": b.input, "kind": tools.KIND.get(b.name)})
            if b.name == "understand" and ctx.get("understood"):
                emit({"type": "understood", "by": "model", **ctx["understood"]})
            if b.name.startswith("show_"):
                emit({"type": "view", **ctx["views"][-1]})
            emit({"type": "tool_done", "name": b.name, "ok": not err, "error": text[:200] if err else None})
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": err})
        messages.append({"role": "user", "content": results})
        if ctx.get("answer"):
            break
    return usage


def _engine_cc(prompt, ctx, s, emit, stop):
    """Claude Code on the person's plan: the tools come from the MCP server, which shares this turn's context
    through a file (the person's results never pass through Claude)."""
    from cluster_analysis.agent import run
    turn_file = os.path.join(sess.DIR, f"{s.id}.turn.json")
    os.makedirs(sess.DIR, exist_ok=True)
    with open(turn_file, "w", encoding="utf-8") as f:
        json.dump({"person": ctx["person"], "share": ctx["share"], "ledger": ctx["ledger"].to_json(), "cards": ctx["cards"],
                   "views": ctx["views"], "findings": ctx.get("findings") or [], "understood": ctx.get("understood"),
                   "answer": ctx.get("answer")}, f)
    mcp = {"mcpServers": {"dna": {"command": sys.executable, "args": ["-m", "cluster_analysis.agent", "mcp"],
                                  "env": {"PYTHONIOENCODING": "utf-8", "DNA_TURN_FILE": turn_file}}}}
    cmd = [run.claude_cli(), "-p", "--output-format", "stream-json", "--verbose", "--tools", "", "--mcp-config", json.dumps(mcp),
           "--strict-mcp-config", "--allowedTools", ",".join(f"mcp__dna__{t}" for t in tools.TOOLS), "--permission-mode", "dontAsk",
           "--no-session-persistence", "--model", MODEL_CC, "--effort", "medium", "--system-prompt", system_prompt(ctx["share"])]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    proc.stdin.write(prompt)
    proc.stdin.close()
    usage, seen, names = {"input": 0, "output": 0}, set(), {}
    try:
        for line in proc.stdout:
            if stop and stop():
                proc.kill()
                raise RuntimeError("Stopped.")
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "assistant":
                m = d["message"]
                mu = m.get("usage") or {}
                if mu and m.get("id") not in seen:
                    seen.add(m.get("id"))
                    usage["input"] += mu.get("input_tokens", 0) + mu.get("cache_read_input_tokens", 0) + mu.get("cache_creation_input_tokens", 0)
                    usage["output"] += mu.get("output_tokens", 0)
                    emit({"type": "usage", **usage, "cache_read": 0, "cache_write": 0})
                for b in m.get("content", []):
                    if b.get("type") == "tool_use":
                        name = b["name"].split("__")[-1]
                        names[b["id"]] = name
                        args = b.get("input") or {}
                        emit({"type": "tool", "name": name, "input": args, "kind": tools.KIND.get(name)})
                        ctx.setdefault("calls", []).append({"name": name, "args": args, "kind": tools.KIND.get(name)})
                        if name == "understand":
                            emit({"type": "understood", "by": "model", "reading": args.get("reading"), "plan": args.get("plan") or []})
                        if name.startswith("show_"):
                            emit({"type": "view", "view": name[5:], **args})
            elif d.get("type") == "user":
                for b in d["message"].get("content", []) if isinstance(d["message"].get("content"), list) else []:
                    if b.get("type") == "tool_result":
                        emit({"type": "tool_done", "name": names.get(b.get("tool_use_id")), "ok": not b.get("is_error"),
                              "error": str(b.get("content"))[:200] if b.get("is_error") else None})
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    with open(turn_file, encoding="utf-8") as f:
        back = json.load(f)
    for k in ("cards", "views", "findings", "understood", "answer"):
        if back.get(k) is not None:
            ctx[k] = back[k]
    if back.get("ledger"):
        s.ledger = tools.facts.Ledger.from_json(back["ledger"])
        ctx["ledger"] = s.ledger
    os.remove(turn_file)
    return usage


def ask(question, person, session_id=None, emit=lambda ev: None, stop=None):
    from cluster_analysis.agent import run
    if not run.backend():
        raise RuntimeError("Ask needs Claude connected (an API key, or Claude Code logged in).")
    s = sess.Session.load(session_id) if session_id else sess.Session(person=person)
    if s.person != person:
        s = sess.Session(person=person)  # another profile: a new conversation
    t0 = time.time()
    ctx = tools.new_context(person, s)
    ctx["words"] = [w for w in re.findall(r"[a-z]{4,}", question.lower())]
    emit({"type": "start", "session": s.id, "question": question})
    engine = _engine_api if run.backend() == "api" else _engine_cc
    history = s.context(share=ctx["share"])
    prompt = (history + "\n\nNew question: " if history else "") + question
    usage = engine(prompt, ctx, s, emit, stop)
    # A turn ends with an answer: one more pass when the model stopped before writing it
    if not ctx.get("answer") and not (stop and stop()):
        done = "; ".join(f"{c['name']}({json.dumps(c['args'], ensure_ascii=False)})" for c in ctx.get("calls", []) if c["name"] != "understand")
        emit({"type": "step", "step": "finish", "sources": ["claude"]})
        u2 = engine(prompt + f"\n\nYou stopped before calling answer. Tools already called this turn: {done or 'none'}. "
                    "Their results are still available to the answer check. Call more tools only if needed, then call answer "
                    "with the summary.", ctx, s, emit, stop)
        usage = {k: usage[k] + u2[k] for k in usage}
    written, wusage = readings(person, ctx["cards"], ctx.get("findings") or [], emit)
    turn = {"question": question, "shared": ctx["share"], "understood": ctx.get("understood"), "calls": ctx.get("calls", []), "cards": ctx["cards"],
            "views": ctx["views"], "answer": ctx.get("answer"), "written": written, "seconds": round(time.time() - t0, 1),
            "tokens": usage, "written_tokens": wusage, "model": MODEL_API if run.backend() == "api" else f"Claude Code ({MODEL_CC})",
            "followup_refs": None}
    s.turns.append(turn)
    s.save()
    emit({"type": "turn", "session": s.id, "index": len(s.turns) - 1})
    return s, turn
