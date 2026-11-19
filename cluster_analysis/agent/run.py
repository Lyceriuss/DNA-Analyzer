"""The agent loop: a question in, a checked answer template out, on Claude through the Anthropic API.

    python -m cluster_analysis.agent ask "What workouts suit me best?" [--lang sv] [--person XY]

The key comes from ANTHROPIC_API_KEY, or the file data/output/agent/api_key (written by the explorer's Ask tab when
"remember" is ticked). Only the question and the public facts the tools return are sent: the person's genome is read
after the run, on this machine (answer.fill).

Each step is reported through emit(event) (the Ask tab shows them live) and kept in data/output/agent/runs/<id>.jsonl.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from cluster_analysis.agent import answer, facts

MODEL = os.environ.get("DNA_AGENT_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("DNA_AGENT_EFFORT", "high")
MAX_TURNS = 40
MAX_SUBMITS = 5
RUNS = os.path.join(answer.OUT, "runs")
KEY_FILE = os.path.join(answer.OUT, "api_key")
LANGS = {"en": "English", "sv": "Swedish"}

SYSTEM = """You research questions about how a person's genome bears on their training, diet, health and medicines, for \
a genome explorer that runs on the person's own computer.

You never see the person's DNA. You work only from public research, through the tools, and write your answer as a \
template: for each variant you choose, what carrying 0, 1 or 2 copies of its effect allele means for the question. \
The explorer then reads the person's genotypes on their machine and shows the reading that applies. So write every \
reading so it is true and useful for whoever has that many copies, and never guess what this person carries.

How to work:
- Orient first. themes() and theme_genes() give the explorer's curated genes for a topic (Gene Ontology mechanisms, \
Open Targets genetics); gene() gives a gene's role, strongest GWAS variants and ClinVar records; trait_variants() finds \
GWAS traits by name. Several calls can go out at once.
- Choose variants that matter for the question: replicated genome-wide hits for the relevant traits, and the well-known \
variants people ask about (graded honestly, even when the evidence turned out weak). Look up every one with variant(): \
it gives the two alleles on the forward strand, which the answer needs. Usually 4-15 variants are enough.
- Research the question itself, not only the genes: intervention and training-response studies, meta-analyses, \
heritability, trials that tested genotype-guided advice. search_papers() then read_paper(), with find=[...] to get the \
full-text paragraphs that report effect sizes.
- Then hand in the answer with submit_answer. If the check finds problems, fix exactly those and submit again.

What counts as a fact: only what a tool returned. Cite sources by the ref ids the tools gave ("PMID:…", "GWAS:…", \
"ClinVar:…", "ClinPGx:…", "UniProt:…", "Theme:…"). Quote word for word from text a tool returned (abstracts, \
full-text paragraphs, ClinPGx and ClinVar texts). Any percentage or fold change you write must appear in the texts of \
the sources that sentence cites.

Restraint: say what the evidence supports and no more. Single common variants usually shift a trait a little; many \
popular fitness and diet variants come from candidate-gene studies that did not replicate, and genotype-guided advice \
has rarely been tested against ordinary advice. Grade each variant (established, suggestive, weak) and say plainly in \
the summary and limits when genetics cannot answer the practical question, then give the advice the research supports \
for everyone (practice items with when=null). A reading for a variant with little effect should say so. The explorer \
gives health advice by design: no disclaimers, the limits section says what the evidence cannot.

Writing: plain words for an interested reader without a biology background, short sentences, concrete and practical. \
Name genes and variants as the sources do. Write all text fields in {language}."""


def api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    if os.path.exists(KEY_FILE):
        return open(KEY_FILE, encoding="utf-8").read().strip() or None
    return None


# --- The other way in: Claude Code on the user's Claude plan, no API key ---------------------------------------------

CC_TOOLS = list(facts.TOOLS) + ["submit_answer"]
CC_MODEL = os.environ.get("DNA_AGENT_CC_MODEL", "opus")


def claude_cli():
    """The Claude Code command line: DNA_CLAUDE_CLI, `claude` on PATH, or the copy inside the VS Code extension."""
    import glob
    import shutil
    found = os.environ.get("DNA_CLAUDE_CLI") or shutil.which("claude")
    if found:
        return found
    exe = "claude.exe" if os.name == "nt" else "claude"
    hits = glob.glob(os.path.join(os.path.expanduser("~"), ".vscode", "extensions", "anthropic.claude-code-*", "resources",
                                  "native-binary", exe))
    return max(hits, key=os.path.getmtime) if hits else None


def backend():
    """'api' with an API key, else 'claude-code' when its command line is there, else None. DNA_AGENT_BACKEND forces one."""
    forced = os.environ.get("DNA_AGENT_BACKEND")
    if forced in ("api", "claude-code"):
        return forced
    return "api" if api_key() else "claude-code" if claude_cli() else None


def run_claude_code(question, lang="en", emit=print, stop=None):
    """The same research through a headless Claude Code session (claude -p) on the user's own Claude plan: the tools come
    from the MCP server (agent/mcp_server.py), whose submit_answer checks and saves the answer. Returns its id or None."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    run_id = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(RUNS, exist_ok=True)
    log = open(os.path.join(RUNS, run_id + ".jsonl"), "w", encoding="utf-8")

    def say(ev):
        ev = {"t": round(time.time(), 2), **ev}
        log.write(json.dumps(ev, ensure_ascii=False) + "\n")
        log.flush()
        emit(ev)

    import sys
    mcp = {"mcpServers": {"dna-research": {"command": sys.executable, "args": ["-m", "cluster_analysis.agent", "mcp"],
                                           "env": {"PYTHONIOENCODING": "utf-8"}}}}
    system = (SYSTEM.replace("{language}", LANGS.get(lang, "English"))
              + f"\n\nThe tools are the dna-research MCP tools. Hand in with submit_answer(question, answer_json, lang=\"{lang}\"): "
                "answer_json is the answer object in the schema its description gives. Stop once it is accepted.")
    cmd = [claude_cli(), "-p", question, "--system-prompt", system, "--output-format", "stream-json", "--verbose",
           "--tools", "", "--mcp-config", json.dumps(mcp), "--strict-mcp-config",
           "--allowedTools", ",".join(f"mcp__dna-research__{t}" for t in CC_TOOLS),
           "--permission-mode", "dontAsk", "--no-session-persistence", "--model", CC_MODEL, "--effort", EFFORT]
    say({"type": "start", "question": question, "model": f"Claude Code ({CC_MODEL})", "lang": lang})
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    names, saved, submits, seen_ids = {}, None, 0, set()
    errlog = open(os.path.join(RUNS, run_id + ".stderr.txt"), "w+", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errlog,
                            text=True, encoding="utf-8", errors="replace",
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    try:
        for line in proc.stdout:
            if stop and stop():
                proc.kill()
                say({"type": "error", "message": "Stopped."})
                return None
            try:
                d = json.loads(line)
            except ValueError:
                continue
            kind = d.get("type")
            if kind == "assistant":
                # Each request's usage, as Claude Code reports it per message: the running total for the tab
                mu = d["message"].get("usage") or {}
                if mu and d["message"].get("id") not in seen_ids:
                    seen_ids.add(d["message"].get("id"))
                    usage["input"] += mu.get("input_tokens", 0)
                    usage["output"] += mu.get("output_tokens", 0)
                    usage["cache_read"] += mu.get("cache_read_input_tokens", 0)
                    usage["cache_write"] += mu.get("cache_creation_input_tokens", 0)
                    say({"type": "usage", **usage})
                for b in d["message"].get("content", []):
                    if b.get("type") == "thinking" and b.get("thinking"):
                        say({"type": "thinking", "text": b["thinking"] + "\n"})
                    elif b.get("type") == "text" and b.get("text"):
                        say({"type": "text", "text": b["text"]})
                    elif b.get("type") == "tool_use":
                        name = b["name"].split("__")[-1]
                        names[b["id"]] = name
                        if name == "submit_answer":
                            say({"type": "tool_start", "name": name})
                        else:
                            say({"type": "tool", "name": name, "input": b.get("input") or {}})
            elif kind == "user":
                for b in d["message"].get("content", []) if isinstance(d["message"].get("content"), list) else []:
                    if b.get("type") != "tool_result":
                        continue
                    name = names.get(b.get("tool_use_id"), "?")
                    c = b.get("content")
                    text = "".join(x.get("text", "") for x in c) if isinstance(c, list) else str(c or "")
                    if name == "submit_answer":
                        submits += 1
                        try:
                            res = json.loads(text)
                        except ValueError:
                            res = {"accepted": False, "problems": [text[:500]]}
                        say({"type": "check", "problems": [] if res.get("accepted") else res.get("problems") or [text[:300]],
                             "attempt": submits})
                        if res.get("accepted"):
                            saved = res.get("id")
                    else:
                        say({"type": "tool_done", "name": name, "ok": not b.get("is_error"), "chars": len(text),
                             "error": text[:300] if b.get("is_error") else None})
            elif kind == "result":
                u = d.get("usage") or {}
                final = {"input": u.get("input_tokens", 0), "output": u.get("output_tokens", 0),
                         "cache_read": u.get("cache_read_input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0)}
                usage = {k: max(usage[k], final[k]) for k in usage}
                if d.get("is_error") and not saved:
                    say({"type": "error", "message": str(d.get("result") or d.get("subtype"))[:500]})
        proc.wait()
        if saved:
            # The MCP server saved it with its own run marker: note which session and model wrote it
            path = os.path.join(answer.ANSWERS, saved + ".json")
            doc = json.load(open(path, encoding="utf-8"))
            doc.update(model=f"Claude Code ({CC_MODEL})", run=run_id, lang=lang)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
            say({"type": "answer", "id": saved, "usage": usage})
            return saved
        errlog.seek(0)
        err = errlog.read().strip()
        say({"type": "error", "message": "No answer was accepted." + (f" {err[:400]}" if err else "")})
        return None
    except Exception as e:
        say({"type": "error", "message": f"{type(e).__name__}: {e}"})
        return None
    finally:
        if proc.poll() is None:
            proc.kill()
        say({"type": "end", "usage": usage})
        log.close()
        errlog.close()


def ask(question, lang="en", key=None, emit=print, stop=None):
    """Runs the agent on whichever backend is available: the API with a key, else Claude Code."""
    if key or backend() == "api":
        return run(question, lang, key=key, emit=emit, stop=stop)
    if backend() == "claude-code":
        return run_claude_code(question, lang, emit=emit, stop=stop)
    emit({"type": "error", "message": "No API key and no Claude Code command line found."})
    return None


def _block_dict(b):
    return b.model_dump(exclude_none=True) if hasattr(b, "model_dump") else b


def run(question, lang="en", key=None, emit=print, stop=None, client=None):
    """Runs the agent on a question; returns the saved answer's id, or None. emit gets each step as a dict; stop() is
    polled between turns (a cancelled run returns None)."""
    import anthropic
    client = client or anthropic.Anthropic(api_key=key or api_key(), max_retries=4)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(RUNS, exist_ok=True)
    log = open(os.path.join(RUNS, run_id + ".jsonl"), "w", encoding="utf-8")

    def say(ev):
        ev = {"t": round(time.time(), 2), **ev}
        log.write(json.dumps(ev, ensure_ascii=False) + "\n")
        log.flush()
        emit(ev)

    led = facts.Ledger()
    tools = facts.schemas() + [answer.TOOL]
    system = SYSTEM.replace("{language}", LANGS.get(lang, "English"))
    messages = [{"role": "user", "content": question}]
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    submits, nudges = 0, 0
    say({"type": "start", "question": question, "model": MODEL, "lang": lang})
    pool = ThreadPoolExecutor(max_workers=4)
    try:
        for turn in range(MAX_TURNS):
            if stop and stop():
                say({"type": "error", "message": "Stopped."})
                return None
            with client.beta.messages.stream(
                model=MODEL, max_tokens=64000, system=system, tools=tools, messages=messages,
                thinking={"type": "adaptive", "display": "summarized"}, output_config={"effort": EFFORT},
                cache_control={"type": "ephemeral"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            ) as stream:
                for ev in stream:
                    kind = getattr(ev, "type", "")
                    if kind == "thinking":
                        say({"type": "thinking", "text": ev.thinking})
                    elif kind == "text":
                        say({"type": "text", "text": ev.text})
                    elif kind == "content_block_start" and getattr(ev.content_block, "type", "") == "tool_use":
                        say({"type": "tool_start", "name": ev.content_block.name})
                msg = stream.get_final_message()
            u = msg.usage
            usage["input"] += u.input_tokens or 0
            usage["output"] += u.output_tokens or 0
            usage["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
            usage["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
            say({"type": "usage", **usage})
            messages.append({"role": "assistant", "content": msg.content})
            uses = [b for b in msg.content if b.type == "tool_use"]
            if msg.stop_reason == "refusal":
                say({"type": "error", "message": "The model declined to answer this question."})
                return None
            if msg.stop_reason == "pause_turn":
                continue
            if msg.stop_reason == "max_tokens" and uses:
                say({"type": "error", "message": "The answer was cut off (max_tokens)."})
                return None
            if not uses:
                nudges += 1
                if nudges > 2:
                    say({"type": "error", "message": "The model stopped without handing in an answer."})
                    return None
                messages.append({"role": "user", "content": "Hand in the answer with the submit_answer tool."})
                continue

            def one(b):
                if b.name == "submit_answer":
                    return b, None
                say({"type": "tool", "name": b.name, "input": b.input})
                text, err = facts.call(led, b.name, b.input)
                say({"type": "tool_done", "name": b.name, "ok": not err, "chars": len(text), "error": text[:300] if err else None})
                return b, (text, err)

            results, saved = [], None
            for b, out in pool.map(one, uses):
                if out is not None:
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": out[0], "is_error": out[1]})
                    continue
                submits += 1
                problems = answer.validate(b.input, led)
                say({"type": "check", "problems": problems, "attempt": submits})
                if not problems:
                    saved = answer.save(question, b.input, led, {"lang": lang, "model": msg.model, "run": run_id})
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": "Accepted."})
                elif submits >= MAX_SUBMITS:
                    say({"type": "error", "message": f"The answer failed the source check {submits} times."})
                    return None
                else:
                    results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                                    "content": "Not accepted. Fix these and submit again:\n- " + "\n- ".join(problems)})
            if saved:
                say({"type": "answer", "id": saved, "usage": usage, "turns": turn + 1})
                return saved
            left = MAX_TURNS - turn - 1
            if left <= 6:
                results.append({"type": "text", "text": f"{left} turns are left: hand in the answer with submit_answer now."})
            messages.append({"role": "user", "content": results})
        say({"type": "error", "message": f"No answer after {MAX_TURNS} turns."})
        return None
    except Exception as e:
        say({"type": "error", "message": f"{type(e).__name__}: {e}"})
        return None
    finally:
        say({"type": "end", "usage": usage})
        pool.shutdown(wait=False)
        log.close()
