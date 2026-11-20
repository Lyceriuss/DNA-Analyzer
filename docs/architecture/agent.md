# The research agent (Ask tab)

`cluster_analysis/agent/` answers a practical question about a person's genome ("What workouts will work best for
me?") with Claude on the Anthropic API, from the same public sources as the other tabs.

## What is sent (addendum, 2026-11-19)

Ask needs a model, and connecting one is the user's own setup: their Anthropic API key, or their Claude Code login.
What that model receives is therefore their decision too, set in the AI corner of the Ask tab
(`agent/settings.py`, `data/output/agent/settings.json`):

| `share_results` | The model receives | The summary |
|---|---|---|
| on (default) | the question; the public research the tools return; and, for the items the question touches, the person's interpreted results: a gene's type ("CYP2C9 \*1/\*1, normal metaboliser"), a score's band and which way is better ("homocysteine: top 10%, higher is worse"), the genotype a finding applies to ("PTGS2 rs20417 CC") | written by the model, weaving the person's results and the evidence together |
| off | the question and public research only; personal tools return just the kind of result shown | assembled on this machine from readings written once for everyone (the blind mode below) |

Never sent, in either mode: the DNA file, raw genotypes outside the items a question touches, the person's name or
profile id. Public tools never read personal data (`tests/test_agent.py`).

Anthropic's handling of API and Claude Code data is set out in its own terms; by default it doesn't train on it. The
EU-law introduction (slide 6) describes the explorer without Ask; this addendum covers Ask.

## The privacy split (the blind mode)

The model never sees a genotype. It researches from public facts only and writes its answer as a **template**: for
each variant it picks, what carrying 0, 1 or 2 copies of the effect allele means for the question. Then the
local server reads the person's calls for those variants and shows the reading that applies. This step makes no
network call.

```mermaid
flowchart LR
  Q[Question] --> A[Claude<br/>Anthropic API]
  A <-->|public ids only| T[Tools<br/>agent/facts.py]
  T --- I[(Local index<br/>GWAS · ClinVar · 1000G)]
  T --- W[UniProt · Europe PMC · ClinPGx<br/>theme graphs]
  A -->|submit_answer| V{Check<br/>answer.validate}
  V -->|problems| A
  V -->|ok| S[(Answer template<br/>data/output/agent/answers)]
  S --> F[Fill on this machine<br/>answer.fill]
  G[(Person's imputed calls)] --> F
  F --> U[Ask tab]
```

What leaves the machine:
- the question;
- the tool calls the model makes: theme ids, gene symbols, rsIDs, trait names and search phrases;
- what the tools return, which is public data.

What never leaves the machine: the DNA file, genotypes, and the per-person results under `data/output`.
`tests/test_agent.py` runs every tool with `open`, `gzip.open` and `zipfile` patched to fail on `data/input` and
`data/output`.

Answer templates don't depend on the person, so one run serves every profile.

## Facts from sources

`answer.validate` checks the answer against a **ledger** of everything the tools returned in the run. If any check
fails, the reasons go back to the model as a tool error and it corrects and resubmits, up to 5 times.

| Check | Rejects |
|---|---|
| Variants | an rsID not looked up with `variant()`, one with no 1000 Genomes alleles, or an effect allele that isn't one of the two (with a hint when it is on the other strand) |
| Readings | anything but exactly one reading each for 0, 1 and 2 copies; a `lean` that isn't one of the answer's axes |
| Sources | a ref id (`PMID:…`, `GWAS:GCST…`, `ClinVar:…`, `ClinPGx:…`, `UniProt:…`, `Theme:…`) no tool returned |
| Quotes | text that is not word for word in what a tool returned for that source (abstracts and full-text paragraphs from `read_paper`, ClinPGx and ClinVar texts, UniProt function text) |
| Figures | a percentage or fold change that is in none of the texts of the sources its sentence cites (GWAS effect sizes are in the ledger too) |
| Advice | a `when` condition on a variant that isn't in the answer |

The system prompt (`run.SYSTEM`) asks the model to hold back:
- Grade each variant established, suggestive or weak.
- Say plainly when genetics can't answer the practical question.
- Give the advice the research supports for everyone.

There are no disclaimers, per the project rule. The `limits` section says what the evidence can't.

## Tools (`agent/facts.py`)

| Tool | Answers from |
|---|---|
| `themes`, `theme_genes` | `themes/theme_graph_*.json`: Gene Ontology mechanisms, Open Targets human genetics |
| `gene` | UniProt function text; GWAS Catalog traits and variants by gene; ClinVar (≥1 star) |
| `variant` | 1000 Genomes alleles and European frequency; every genome-wide GWAS association with effect allele, size and study; ClinVar; ClinPGx genotype texts; `evidence/function_evidence.json`, `evidence/literature.json` |
| `trait_variants` | GWAS Catalog traits matching a phrase, strongest variants first |
| `search_papers`, `read_paper` | Europe PMC: search, abstracts, and the open full-text paragraphs that use the given words |

The bulk lookups use `cluster_analysis/cache/agent_index.sqlite`, which is built from:
- `gwas_associations_ontology.zip`
- ClinVar
- the panel site list on D:

Build it once with `python -m cluster_analysis.agent index`: about 4 minutes, 470 MB, ignored by git. The sites also
include the ~15,000 variants that earlier Ensembl VEP runs cached (popular candidate-gene variants such as PPARGC1A
rs8192678 that are neither GWAS hits nor in ClinVar); `index --vep` adds them to an existing index. Lookups that
need the network (UniProt, Europe PMC) are cached in `cluster_analysis/cache` like the other packages' lookups.
Ensembl isn't used, so the agent keeps working when rest.ensembl.org is down.

## The loop (`agent/run.py`)

- **API:** the Messages API, streamed, with a hand-written loop rather than the SDK's beta tool runner. Hand-writing
  it lets the loop record every tool result in the ledger, report each step to the tab, and send the check's
  reasons back as a tool error.
- **Model:** `claude-opus-5-5` with adaptive thinking (summaries are shown live) at effort `high`. Override with
  `DNA_AGENT_MODEL` and `DNA_AGENT_EFFORT`.
- **Caching:** automatic prompt caching (top-level `cache_control`), since the system prompt and tools are the same
  every turn.
- **Refusals:** server-side fallbacks (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) reroute a
  request a safety classifier declines.
- **Tools:** several run at once. Inputs are checked against each tool's schema before it runs, because eager input
  streaming means the API doesn't validate them.
- **Limits:** 40 turns. A note goes in when 6 are left.
- **Logs:** `data/output/agent/runs/<id>.jsonl` holds every step. It contains no personal data, only the question,
  the tool calls and the model's text.

**The key:** the loop takes it from `ANTHROPIC_API_KEY`, or from `data/output/agent/api_key`, which the Ask tab
writes when "remember" is ticked. Otherwise the server keeps it in memory.

## Two backends

`run.ask()` picks the backend (`DNA_AGENT_BACKEND` forces one):

| Backend | When | How |
|---|---|---|
| `api` | an API key is set (`ANTHROPIC_API_KEY`, the Ask tab, or `data/output/agent/api_key`) | the loop below, on the Messages API, billed to the key; with `DNA_AGENT_PTC=1` the bulky lookups run inside Claude's code execution as a script (programmatic tool calling, a prototype: ask-decisions.md D25) |
| `claude-code` | no key, and the Claude Code CLI is found (`claude` on PATH, `DNA_CLAUDE_CLI`, or the VS Code extension's copy) | `run.run_claude_code` starts a headless `claude -p` with this system prompt, no built-in tools, and only the MCP tools (`--strict-mcp-config`, `--permission-mode dontAsk`); it runs on the user's Claude plan, counting toward its usage limits, and needs no key |

In both, the MCP server's or the loop's `submit_answer` runs the same check. MCP clients don't enforce the answer
schema, so `answer.shape` checks it as part of `validate`. Other agent setups (Claude Desktop, other MCP clients) use
the MCP server the same way.

## Where it runs

- **Ask tab:** `explorer serve`, with the routes under `/api/agent/*` in `explorer/server.py`; the page parts are
  `explorer/ask.*`. One question runs at a time, and the page polls the steps. Saved answers are listed, filled in
  for the selected profile, and linked as `#ask=<id>`.
- **CLI:** `python -m cluster_analysis.agent ask "QUESTION" --person <profile>`, and `fill`, `list`.
- **MCP:** `python -m cluster_analysis.agent mcp`, which serves the same tools plus `submit_answer` over stdio. For
  Claude Code, run `claude mcp add dna-research -- python -m cluster_analysis.agent mcp` from the repo root. The
  client's model then does the research, and `submit_answer` checks and saves the answer for the Ask tab.

## Files

| Path | In git | Holds |
|---|---|---|
| `cluster_analysis/agent/*.py` | yes | the package |
| `cluster_analysis/cache/agent_index.sqlite` | no | the public index |
| `data/output/agent/answers/` | no | answer templates (no genotypes, but the user's questions) |
| `data/output/agent/fills/` | no | per-person readings (personal) |
| `data/output/agent/runs/` | no | step logs |
| `data/output/agent/api_key` | no | the remembered key |
