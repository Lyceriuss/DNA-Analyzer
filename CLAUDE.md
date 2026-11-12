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
- Health advice in the outputs is intended; don't add disclaimers.
- Use the global Python; no virtual environments.
- Respect API rate limits and bot checks (`cluster_analysis/sources.py` waits on 429/503).
- Commit or push only when asked.

## Layout

`genome/` reads and imputes DNA files. `cluster_analysis/` holds the analysis, one package per feature (`themes`,
`evidence`, `lifecycle`, `medicines`, `nutrition`, `carriers`), the explorer (`explorer/`) and the old SNP library (`library/`,
being phased out). `main.py`, `src/` and `config/` are the original PDF report. Details:
`cluster_analysis/README.md` and `docs/architecture/`.

## Genome build and disks

The analysis runs on GRCh38 with the 1000 Genomes high-coverage panel (`genome/build.py`, `DNA_BUILD`; GRCh37 for
comparison). The panel and its site list live on D: (`D:\DNA-Analyzer-reference`), outside the repo. Large jobs:
check free space on C: and D: first, never stream bulk data through a Docker container's stdout (Docker logs it into
its virtual disk on C:), write to files on D: instead, and verify outputs against an independent count. Every
reference file is listed in `genome/references.json`; `python -m genome.references status` checks them. Keep the
`source` tier: it is what the built references are rebuilt from.

## The explorer: localhost and the claude.ai artifact

```bash
python -m cluster_analysis.profiles run          # per-profile analysis (slow: API calls, cached)
python -m cluster_analysis.explorer export       # datasets -> data/output/explorer_GRCh38/datasets/
python -m cluster_analysis.explorer serve        # http://127.0.0.1:8000
python -m cluster_analysis.explorer check        # render every tab, profile and language; fails on errors
```

Edit the parts (`explorer/*.js|css|html`) and `explorer/page.html`, never `explorer/index.html`: `build` writes it.

### Publishing the explorer

The artifact is https://claude.ai/artifact/Rsz3RYugnZyvWnixS9168o (Dashboard runtime). Run `check`, then
`python -m cluster_analysis.explorer publish` and read `data/output/explorer_GRCh38/publish/manifest.json`:

1. For each dataset with `"changed": true`: upload its `file` with the Artifact tool (`url` = the artifact,
   `asset: true`, one file per call). Note the returned `/_blob/<id>`.
2. Read the `datasets` collection (ArtifactData `list`) for each document's `version`. In one ArtifactData `batch`:
   `update` `datasets/<name>` with `{"source": {"kind": "file", "name": "<name>.json", "url": "/_blob/<id>"}}` pinned
   with `if_version` (`set` with title and description for a dataset that has no document yet), and, if the page
   changed, `update` `files/index.html` from `file_path` = the manifest's page `file` (pinned to its version).
3. Record what is live: `python -m cluster_analysis.explorer publish --record name=/_blob/<id> ... --page`.

The page document must stay under 262,144 bytes JSON-encoded (`build` checks). The Swedish datasets (`i18n_sv`,
`i18n_sv_terms`) are `[{en, sv}]` rows; `publish` writes them in that form.
