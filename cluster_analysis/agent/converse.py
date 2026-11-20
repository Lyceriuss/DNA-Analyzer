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

from cluster_analysis.agent import categories, cost, interpret, language, morsels, providers, session as sess, tools

ROOT = sess.ROOT
MODEL_API = os.environ.get("DNA_AGENT_CONVERSE_MODEL", "claude-sonnet-5-5")
MODEL_CC = os.environ.get("DNA_AGENT_CONVERSE_CC", "sonnet")
MAX_TURNS = 16
PTC = os.environ.get("DNA_AGENT_PTC") == "1"  # programmatic tool calling on the API backend (prototype)

SYSTEM = """You answer a person's question about their own genome with a genome explorer that runs on their computer, \
through tools.

Work in this order:
1. Call understand first: one sentence on what you understood they want (and what a genome can and can't answer \
about it), the aim of the question, and a short plan naming the tools you will use. Keep the person's own goal: \
"what should I think about to stay lean" asks which strategies work for them, not whether they are at risk of weight \
gain. Never turn a goal into a risk question.
2. Find what the question refers to (resolve, catalogue; a drug by any name, misspelled or not: paracetamol is \
acetaminophen).
3. Read the person's own results with the my_* tools. {results_rule}
4. Judge whether what is on the person's screen answers the question: each my_* result says what kind of answer it put \
there (screen_has), never its content. When it holds the answer (dosing guidelines, ClinPGx texts for their own \
genotypes, their scores), explain it from the public facts behind it (drug, gene, cluster) and finish: don't research \
further unless the person asks for depth. When it doesn't (no guideline and no annotation, a training or diet question, \
nothing for a named condition), research: research_genotypes on the strongest variants for the question, or the key \
study with read_paper. A strategies question (what works, what to do, what to think about, how to reach a goal) is \
never answered by the person's own results alone: their results say which genes matter, the studies say how people \
with those genotypes respond. Look outward for each strategy the question names or the evidence suggests (a diet, \
fasting or meal timing, a type or amount of training, sleep, a nutrient): search_papers for trials, cohorts and \
meta-analyses of the response by genotype (e.g. '(FTO OR MC4R) AND (weight loss OR intervention) AND genotype'), \
research_genotypes on the person's strongest variants with the strategy as the topic, read_paper for the effect \
sizes. Follow the person's notable genes to the strategies their mechanism bears on and research those as well (an \
appetite or satiety gene: fasting, meal timing, protein; a fat-storage or insulin gene: diet composition), keeping \
only what the studies support. That genotype made no difference to a strategy is a finding too: report it. Use the \
public tools to learn \
what the evidence says: drug \
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
it), citing the refs the tools returned as [PMID:123] or [ClinPGx:456], and 2-4 follow-up questions. The summary \
answers the question as asked, in its first sentence: for a strategies question, which strategies the evidence links \
to the person's genotypes and how people with them responded (with the size and the strength of the evidence); \
their propensity comes after, only as context for a strategy. For a risk question, the risk leads. Strategies are \
reported as evidence ("in trials, carriers of … lost more weight on …"), not as instructions.

Cover the question's areas. When it maps to a cluster (muscle, mind, …), list in understand the cluster's \
mechanisms that bear on it as areas (for building muscle: growth on load, protein synthesis, fibre type, tendons, \
regeneration and recovery, inflammation, hormones) and read the person's genes in them (my_cluster with the \
mechanism ids, comma-separated, in one call). Each area where the person carries notable variants gets a finding or \
a strategy: tendons bear on load progression and injury, recovery on how often to train. Tie it together in the \
answer's links: each area and strategy, the person's genes behind it, the refs, and the finding.

When you mention a result of the person's (a score, a gene's type), say why: which of their variants drive it and \
what each does (the result's details list them).

Every link you draw between a result and the question's subject (a food, a type of training, a drug, an exposure) must come from a tool result and be cited: research it (search_papers, recent_papers, research_genotypes, read_paper) or leave it out. Never fill in from general knowledge; the answer cites its sources.

A follow-up question builds on the conversation so far: use it, don't repeat work you already did. If the person asks \
about a study or item from an earlier answer, read it (read_paper with find=[...] for the full text). No \
disclaimers; say plainly what the evidence can't tell. Keep to about 8 lookups (the budget is 10; for a strategies or \
research question, 20); call several tools in one step when they don't depend on each other.
""" + language.RULE + " " + language.RANK_RULE


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


SCRIPT_RULE = """

The lookups {names} are async functions inside code_execution, not direct tools: each takes one dict and returns a \
JSON string, e.g. json.loads(await gene({{"symbol": "ACTN3"}})). When you need lookups, write one script that runs \
them (asyncio.gather for independent ones), keeps only what bears on the question and prints it compactly: ids, the \
refs (PMID:…, GWAS:…, ClinVar:…) and the figures with the words around them. Only what you print reaches you; refs \
you print can be cited, and a highlight's figure must be in its source's text."""


def system_prompt(share, ptc=False):
    s = SYSTEM.replace("{results_rule}", SHARED if share else BLIND)
    return s + (SCRIPT_RULE.format(names=", ".join(tools.SCRIPTED)) if ptc else "")


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


# What a genotype does to its gene, in the explorer's words (th.js): the call behind the colour of each badge
FN_TEXT = {"LoF": "less active", "GoF": "more active", "altered": "changed, direction unclear", "normal": "typical function",
           "unknown": "no function call"}
FN_RANK = {"LoF": 0, "GoF": 0, "altered": 1, "normal": 2, "variant": 2, "unknown": 3}


def _sites(rsids):
    """Reference and variant alleles per rsID: the agent's index (1000 Genomes), else Ensembl's record (sources.py,
    cached and rate-limited; public variant ids, fetched once for all of a turn's variants)."""
    from cluster_analysis.agent import index
    out = {}
    for rs in rsids:
        s = (index.query("SELECT ref, alt FROM sites WHERE rsid = ?", rs) or [None])[0]
        if s:
            out[rs] = s
    missing = [rs for rs in rsids if rs not in out]
    if missing:
        try:
            from cluster_analysis import sources
            for rs, v in (sources.ensembl_vep(missing) or {}).items():
                al = [a for a in (v.get("alleles") or []) if len(a) == 1]
                af = [a for a in (v.get("eur_af") or {}) if a in al and a != (al or [None])[0]]
                # A site with more alleles: the variant allele is the one with a European frequency
                alt = al[1] if len(al) == 2 else (af[0] if len(af) == 1 else None)
                if al and alt:
                    out[rs] = {"ref": al[0], "alt": alt}
        except Exception:
            pass
    return out


def _carrier(site, gt):
    """Without a function call: how many copies of the variant (alt) allele the genotype holds."""
    from cluster_analysis.agent.answer import copies
    if not site or not gt:
        return None
    n = copies(gt.replace("/", ""), site["alt"], site["ref"], site["alt"])
    if n is None:
        return None
    if n == 0:
        return {"function": "normal", "text": "usual genotype", "basis": "genotype",
                "evidence": f"No copies of the variant allele {site['alt']}."}
    return {"function": "variant", "text": f"{n} {'copy' if n == 1 else 'copies'} of {site['alt']}", "basis": "genotype",
            "evidence": f"{n} {'copy' if n == 1 else 'copies'} of the variant allele {site['alt']}; its effect on the gene isn't measured."}


def _cpic_call(phenotype):
    """A medicine gene's CPIC result as a function call: poor, intermediate, slow or decreased is less active."""
    p = (phenotype or "").lower()
    fn = ("LoF" if re.search(r"poor|intermediate|slow|decreased|reduced|no function|non-expresser", p) else
          "GoF" if re.search(r"rapid|ultra|increased", p) else "normal" if re.search(r"normal|extensive", p) else "unknown")
    return {"function": fn, "text": phenotype or FN_TEXT[fn], "basis": "CPIC"}


class Calls:
    """The person's function calls: per variant (the explorer's gene_function data), per gene (its most telling call
    there or in the clusters), and per medicine gene (the CPIC phenotype)."""

    def __init__(self, person):
        self.rs, self.gene, self.sites = {}, {}, {}
        for r in providers.rows("gene_function", person) + providers.rows("theme_genes", person):
            if not isinstance(r, dict) or not r.get("gene"):
                continue
            c = {"function": r.get("function") or "unknown", "basis": r.get("basis"), "evidence": (r.get("fn_evidence") or "")[:220]}
            c["text"] = FN_TEXT.get(c["function"], c["function"])
            if r.get("rsid") and r["rsid"] not in self.rs:
                self.rs[r["rsid"]] = c
            if FN_RANK.get(c["function"], 3) < FN_RANK.get(self.gene.get(r["gene"], {}).get("function"), 9):
                self.gene[r["gene"]] = c
        self.cpic = {g["gene"]: _cpic_call(g.get("phenotype")) for g in providers.rows("med_genes", person)}

    def of(self, gene, variant=None, gt=None):
        g = (gene or "").split(";")[0]
        if variant and str(variant).startswith("rs"):
            known = self.rs.get(variant)
            if known and known["function"] != "unknown":
                return known
            return _carrier(self.sites.get(variant), gt) or known or {"function": "unknown", "text": "no function call for this variant"}
        if variant and "*" in str(variant) and g in self.cpic:
            return self.cpic[g]
        return self.cpic.get(g) or self.gene.get(g) or {"function": "unknown", "text": FN_TEXT["unknown"]}


def attach_calls(person, rows, answer=None):
    """Each finding row gets the call for each of its variants (or its gene); the answer's web gets one per gene."""
    calls = Calls(person)
    wanted = {v for x in rows for v in (x.get("variants") or ([x["rsid"]] if x.get("rsid") else [])) if str(v).startswith("rs")}
    calls.sites = _sites(sorted(v for v in wanted if (calls.rs.get(v) or {}).get("function", "unknown") == "unknown"))
    for x in rows:
        if x.get("source") == "score":
            continue
        vs = x.get("variants") or ([x["rsid"]] if x.get("rsid") else [])
        gts = x.get("genotypes") or ([x["genotype"]] if x.get("genotype") else [])
        if x.get("source") == "CPIC guideline":
            x["calls"] = [calls.cpic.get(x.get("gene")) or _cpic_call(x.get("effect"))]
        else:
            x["calls"] = ([calls.of(x.get("gene"), v, gts[i] if i < len(gts) else None) for i, v in enumerate(vs)] if vs
                          else [calls.of(x.get("gene"))])
    if answer and answer.get("links"):
        names = {g for l in answer["links"] for g in l["genes"]}
        answer["calls"] = {n: calls.of(None, n)["function"] if n.startswith("rs") else calls.of(n)["function"] for n in names}


HERO_RANK = {"LoF": 0, "GoF": 0, "altered": 1, "variant": 1.5, "normal": 2, "unknown": 3}


def genotype_hero(person, question, answer, written):
    """The key genes of a turn (named in the question, then the web's, then the findings'), each with the person's
    headline genotype and its call (a medicine gene's star alleles and CPIC result; else its most telling variant), and
    the gene's other variants. On this machine, for the person's screen; never sent to the model."""
    calls = Calls(person)
    gf = {}
    for r in providers.rows("gene_function", person):
        if isinstance(r, dict) and r.get("gene") and r.get("rsid") and r.get("genotype"):
            gf.setdefault(r["gene"], []).append(r)
    med = {g["gene"]: g for g in providers.rows("med_genes", person)}
    rows = [x for x in written or [] if x.get("source") != "score"]
    known = set(gf) | set(med) | {(x.get("gene") or "").split(";")[0] for x in rows}
    order = []

    def add(g):
        if g in known and g not in order:
            order.append(g)
    for g in re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", question or ""):
        add(g)
    for link in (answer or {}).get("links") or []:
        for g in link.get("genes") or []:
            add(g)
    for x in rows:
        add((x.get("gene") or "").split(";")[0])
    order = order[:4]
    need = {r["rsid"] for g in order for r in gf.get(g, []) if (calls.rs.get(r["rsid"]) or {}).get("function", "unknown") == "unknown"}
    calls.sites = _sites(sorted(need)) if need else {}
    out = []
    for g in order:
        vs = [{"variant": r["rsid"], "genotype": r["genotype"], **calls.of(g, r["rsid"], r["genotype"])} for r in gf.get(g, [])]
        for x in rows:
            if (x.get("gene") or "").split(";")[0] != g:
                continue
            gts, cs = x.get("genotypes") or [], x.get("calls") or []
            for i, v in enumerate(x.get("variants") or []):
                if str(v).startswith("rs") and v not in {y["variant"] for y in vs}:
                    gt = gts[i] if i < len(gts) else None
                    vs.append({"variant": v, "genotype": gt, **((cs[i] if i < len(cs) else None) or calls.of(g, v, gt))})
        if g in med:
            main = {"label": med[g]["alleles"], "variant": None, **_cpic_call(med[g]["phenotype"])}
        elif vs:
            best = sorted(vs, key=lambda v: HERO_RANK.get(v.get("function"), 3))[0]
            main = {"label": best["genotype"], **{k: best.get(k) for k in ("variant", "function", "text", "basis", "evidence")}}
        else:
            continue
        out.append({"gene": g, "main": main, "variants": [v for v in vs if v["variant"] != main.get("variant")][:6]})
    return out


def readings(person, cards, findings, emit):
    """The readings for the person: their own results' categories and the studies' genotype groups. The model writes
    whole domains and every finding (never a selection); this machine picks."""
    from cluster_analysis.agent import run
    usage = cost.new()
    add = lambda u: cost.add(usage, u)
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
    out = picked[:8] + found[:6]
    attach_calls(person, out)
    return out, usage


def _engine_api(prompt, ctx, s, emit, stop):
    import anthropic
    from cluster_analysis.agent import run
    client = anthropic.Anthropic(api_key=run.api_key(), max_retries=4)
    messages = [{"role": "user", "content": prompt}]
    usage = cost.new()
    container = None  # the code execution container, passed back while a script waits on our tools
    for _ in range(MAX_TURNS):
        if stop and stop():
            raise RuntimeError("Stopped.")
        extra = {"container": container} if container else {}
        msg = client.messages.create(model=MODEL_API, max_tokens=8000, system=system_prompt(ctx["share"], PTC), tools=tools.schemas(PTC),
                                     messages=messages, cache_control={"type": "ephemeral"}, output_config={"effort": "medium"}, **extra)
        usage = cost.add(usage, cost.of(MODEL_API, msg.usage))
        emit({"type": "usage", **usage})
        messages.append({"role": "assistant", "content": msg.content})
        if getattr(msg, "container", None):
            container = msg.container.id
        for b in msg.content:
            if b.type == "server_tool_use" and b.name == "code_execution":
                emit({"type": "tool", "name": "script", "input": {}, "kind": "control"})
                ctx.setdefault("calls", []).append({"name": "script", "args": {}, "kind": "control"})
        uses = [b for b in msg.content if b.type == "tool_use"]
        if not uses:
            if msg.stop_reason == "pause_turn":  # a long server-side step: let it continue
                continue
            break
        results = []
        for b in uses:
            via = "script" if getattr(getattr(b, "caller", None), "type", "direct") != "direct" else None
            emit({"type": "tool", "name": b.name, "input": b.input, "kind": tools.KIND.get(b.name), "via": via})
            text, err = tools.call(ctx, b.name, b.input)
            ctx.setdefault("calls", []).append({"name": b.name, "args": b.input, "kind": tools.KIND.get(b.name), "via": via})
            if b.name == "understand" and ctx.get("understood"):
                emit({"type": "understood", "by": "model", **ctx["understood"]})
            if b.name.startswith("show_"):
                emit({"type": "view", **ctx["views"][-1]})
            emit({"type": "tool_done", "name": b.name, "ok": not err, "error": text[:200] if err else None})
            # A script's call takes a plain string (an error is text the script can handle); a direct call can flag it
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": ("Error: " + text) if err and via else text}
                           | ({} if via else {"is_error": err}))
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
                   "answer": ctx.get("answer"), "spent": ctx.get("spent", 0), "rejections": ctx.get("rejections", 0), "outward": ctx.get("outward", 0),
                   "outward_args": ctx.get("outward_args", []), "lookup_args": ctx.get("lookup_args", []), "trace": ctx.get("trace", []),
                   "question": ctx.get("question")}, f)
    mcp = {"mcpServers": {"dna": {"command": sys.executable, "args": ["-m", "cluster_analysis.agent", "mcp"],
                                  "env": {"PYTHONIOENCODING": "utf-8", "DNA_TURN_FILE": turn_file}}}}
    cmd = [run.claude_cli(), "-p", "--output-format", "stream-json", "--verbose", "--tools", "", "--mcp-config", json.dumps(mcp),
           "--strict-mcp-config", "--allowedTools", ",".join(f"mcp__dna__{t}" for t in tools.TOOLS), "--permission-mode", "dontAsk",
           "--no-session-persistence", "--model", MODEL_CC, "--effort", "medium", "--system-prompt", system_prompt(ctx["share"])]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    proc.stdin.write(prompt)
    proc.stdin.close()
    usage, seen, names = cost.new(), set(), {}
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
                    usage = cost.add(usage, cost.of(MODEL_CC, mu))
                    emit({"type": "usage", **usage})
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
    for k in ("cards", "views", "findings", "understood", "answer", "spent", "rejections", "outward", "outward_args", "lookup_args", "trace"):
        if back.get(k) is not None:
            ctx[k] = back[k]
    if back.get("ledger"):
        s.ledger = tools.facts.Ledger.from_json(back["ledger"])
        ctx["ledger"] = s.ledger
    os.remove(turn_file)
    return usage


def auto_views(ctx):
    """The explorer's views a turn's results call for, added on this machine when the model didn't draw them (no
    tokens): a nutrient's conversion steps, a medicine, and the cluster areas the turn read, as one network per
    cluster grouped by mechanism."""
    have = {(v["view"], v.get("nutrient") or v.get("drug") or v.get("theme")) for v in ctx["views"]}
    areas = {}
    for c in ctx.get("calls", []):
        n, a = c["name"], c.get("args") or {}
        try:
            if n == "my_nutrient" and a.get("name") and ("nutrient", tools._nutrient_id(a["name"])) not in have:
                tools.t_show_nutrient(ctx, a["name"])
                ctx["views"][-1]["auto"] = True
                have.add(("nutrient", ctx["views"][-1]["nutrient"]))
            elif n == "my_medicine" and a.get("name") and ("medicine", tools._drug_name(a["name"])) not in have:
                tools.t_show_medicine(ctx, a["name"])
                ctx["views"][-1]["auto"] = True
                have.add(("medicine", ctx["views"][-1]["drug"]))
            elif n == "my_cluster" and a.get("theme") and a.get("mechanism"):
                ms = areas.setdefault(tools.facts._theme_id(a["theme"]), [])
                for m in str(a["mechanism"]).split(","):
                    for mid in sorted(tools._area_ids(m.strip()) or {m.strip()}):
                        if mid and mid not in ms:
                            ms.append(mid)
        except Exception:
            continue
    for theme, ms in areas.items():
        g = tools.facts._theme_graphs().get(theme) or {}
        names = {m["id"]: m["name"] for m in g.get("mechanisms") or []}
        ms = [m for m in ms if m in names]
        if ms:
            ctx["views"].append({"view": "areas", "theme": theme, "mechanisms": [{"id": m, "name": names[m]} for m in ms[:8]], "auto": True})


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
    ctx["question"] = question
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
        usage = cost.add(usage, u2)
    auto_views(ctx)
    written, wusage = readings(person, ctx["cards"], ctx.get("findings") or [], emit)
    if ctx.get("answer"):
        attach_calls(person, [], ctx["answer"])
    hero = genotype_hero(person, question, ctx.get("answer"), written)
    turn = {"question": question, "shared": ctx["share"], "understood": ctx.get("understood"), "calls": ctx.get("calls", []), "cards": ctx["cards"],
            "views": ctx["views"], "answer": ctx.get("answer"), "written": written, "seconds": round(time.time() - t0, 1),
            "tokens": usage, "written_tokens": wusage, "model": (MODEL_API + (" + scripts" if PTC else "")) if run.backend() == "api" else f"Claude Code ({MODEL_CC})",
            "followup_refs": None, "trace": ctx.get("trace", []), "hero": hero,
            "ranks_asked": language.ranks_asked(question, (ctx.get("understood") or {}).get("aim"))}
    s.turns.append(turn)
    s.save()
    emit({"type": "turn", "session": s.id, "index": len(s.turns) - 1})
    return s, turn
