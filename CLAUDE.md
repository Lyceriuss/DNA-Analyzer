# DNA-Analyzer: notes for agents

## Rules

- **The repo is public.** Never commit DNA files, genotypes, per-person results or anything derived from them, not even
  in docs or examples. `data/input`, `data/output`, `data/reference` and `cluster_analysis/cache` are ignored by git;
  keep personal output there.
- **Profiles are named XX and XY** (see `cluster_analysis/profiles.json`), never by initials. Other DNA files in
  `data/input` belong to other people: don't analyse or publish them unless asked.
- **Facts come from sources, not from a language model.** Effects, frequencies, pathways and citations are fetched from
  the APIs and bulk files in `docs/architecture/sources.md` at build time. Curated configs (`nutrients.json`,
  `labtests.json`, theme graphs) only choose which tests, genes or traits to use.
- Outputs speak in risk and evidence, never clinical advice (the user's rule, 2026-11-19): no "see a doctor", "ask for a
  test", dose or drug instructions; guidelines are reported as facts about the guideline, prevention as risk factors.
  No disclaimers either. For Ask, `cluster_analysis/agent/language.py` holds the rule and the check that enforces it.
- **Ask and the model the user connects.** With `share_results` on (the default, `cluster_analysis/agent/settings.py`),
  the interpreted results for the items a question touches go to the user's own model (their API key or Claude Code
  login) so the summary can weave them; never the DNA file. Off, the model sees public facts only. Public tools never
  read personal data (`tests/test_agent.py`); see "What is sent" in `docs/architecture/agent.md`.
- Use the global Python; no virtual environments.
- Respect API rate limits and bot checks (`cluster_analysis/sources.py` waits on 429/503).
- Commit or push only when asked.

## Layout

`genome/` reads and imputes DNA files. `cluster_analysis/` holds the analysis, one package per feature (`themes`,
`evidence`, `lifecycle`, `medicines`, `nutrition`, `agent`), the explorer (`explorer/`) and the old SNP library (`library/`:
`snp_traits.json`, its reader and tools; no tab is drawn from it any more, being phased out). The packages meet only through
files (the person's calls, each package's outputs, the explorer's datasets), so each can be replaced on its own: keep it
that way. The PDF report was removed on 2026-11-13. Details: `cluster_analysis/README.md` and `docs/architecture/`.

## Genome build and disks

The analysis runs on GRCh38 with the 1000 Genomes high-coverage panel (`genome/build.py`, `DNA_BUILD`; GRCh37 for
comparison). The panel and its site list live on D: (`D:\DNA-Analyzer-reference`), outside the repo. Large jobs:
check free space on C: and D: first, never stream bulk data through a Docker container's stdout (Docker logs it into
its virtual disk on C:), write to files on D: instead, and verify outputs against an independent count. Every
reference file is listed in `genome/references.json`; `python -m genome.references status` checks them. Keep the
`source` tier: it is what the built references are rebuilt from.

## The explorer: localhost

```bash
python -m cluster_analysis.profiles run          # per-profile analysis (slow: API calls, cached)
python -m cluster_analysis.explorer export       # datasets -> data/output/explorer_GRCh38/datasets/
python -m cluster_analysis.explorer serve        # http://127.0.0.1:8000, with "Add a person" (cluster_analysis/pipeline.py)
python -m cluster_analysis.explorer check        # render every tab, profile and language; fails on errors
```

Edit the parts (`explorer/*.js|css|html`) and `explorer/page.html`, never `explorer/index.html`: `build` writes it.
The localhost site is the explorer: no page size limit, no internet needed (d3 is in `explorer/runtime/`), served on
127.0.0.1 only because the datasets hold genotypes.

### The old claude.ai artifact

https://claude.ai/artifact/Rsz3RYugnZyvWnixS9168o is no longer updated; publish to it only when asked. Its page is
limited to 262,144 bytes (`build.py --publish` writes the minified copy and checks it), and publishing goes through
`python -m cluster_analysis.explorer publish` and `manifest.json`: upload each changed dataset as an asset, point its
`datasets/<name>` document at the returned `/_blob/<id>` (ArtifactData `batch`, pinned with `if_version`), update
`files/index.html` if the page changed, then `publish --record name=/_blob/<id> ... --page`. The Swedish datasets
(`i18n_sv`, `i18n_sv_terms`) are `[{en, sv}]` rows; `publish` writes them in that form.
