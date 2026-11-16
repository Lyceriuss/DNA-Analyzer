# Gene Cluster Explorer

The interactive explorer, served on this machine at http://127.0.0.1:8000. It needs no internet and has no page size
limit. (It was first published as a claude.ai Dashboard artifact, https://claude.ai/artifact/Rsz3RYugnZyvWnixS9168o,
which is no longer updated; see the end of this page.)

## Running it

```bash
python -m cluster_analysis.explorer serve     # export if needed, build the site, serve it on http://127.0.0.1:8000
python -m cluster_analysis.explorer check     # every tab x profile x language in headless Chrome; fails on script errors
python -m cluster_analysis.explorer export    # refresh the datasets (data/output/explorer_GRCh38/datasets/; explorer/ for DNA_BUILD=GRCh37) after a pipeline run
```

`serve` writes the site to `data/output/explorer_GRCh38/site/` (page, runtime, d3, datasets) and answers on 127.0.0.1
only: the datasets hold genotypes. Run `export` after a pipeline run so the site picks up the new results.

## Building

`page.html` is the page's shell (header, tab sections, shared helpers) with an include marker where each part goes.
`build.py` assembles it into `index.html`, the complete page. **Edit the parts and
`page.html`, never `index.html`**, then rebuild:

```bash
python cluster_analysis/explorer/build.py                  # index.html
python cluster_analysis/explorer/build.py --standalone DATASET_DIR data/output/explorer_site
python -m http.server -d data/output/explorer_site 8000   # the same page, self-hosted, on http://localhost:8000
```

`--standalone` writes the page as a static site with its own runtime (`runtime/dash.js`, `runtime/tokens.css`) and a
local copy of d3 (`runtime/d3.min.js`, 7.9.0, ISC licence), and copies the datasets from an export folder (`python -m cluster_analysis.explorer export`) next to it. Those datasets hold
genotypes: keep the site under `data/output` (ignored by git) and don't serve it beyond your own machine. Why and
where this is heading: [docs/architecture/migration.md](../../docs/architecture/migration.md).

| File | Part |
|---|---|
| `page.html` | The shell: header (language and profile switches), tab sections, shared helpers (`gx.*`) |
| `build.py` | Assembles the page; minifies the published copy; writes the standalone site |
| `runtime/dash.js`, `runtime/tokens.css` | The standalone runtime and design tokens (claude.ai provides both on the artifact) |
| `runtime/d3.min.js` | d3 7.9.0, so the page draws without internet |

| `lc.html`, `lc.css`, `lc.js` | Gene lifecycle tab: gene summary, node graph, step details with capacity, evidence and papers |
| `in.html`, `in.css`, `in.js`, `intro.py` | Home tab: the introduction in six steps (how it works and what imputation is, the research behind it, what the person's DNA can do for them, the DNA file, how to read the results, where to start), with the method's numbers and the selected person's (`intro.py` writes the `intro_stats` dataset) |
| `so.html`, `so.css`, `so.js`, `sources.json` | Sources tab: the research databases (who runs them, what they give, how they are reached, which tabs use them, the version of each bulk file from `genome/references.json`), the tools and a glossary. `sources.json` is the one list of databases: `build.py` puts it in the page as `window.GX_SOURCES` and adds its Swedish to the dictionary; `tests/test_sources_catalog.py` checks it against `docs/architecture/sources.md` and `references.json` |
| `settings.json` | `intro_required`: every viewer goes through the introduction once per browser before the other tabs open (Next waits `intro_min_seconds` per step, no skipping). Off during development; `build.py` puts the settings in the page as `window.GX_SETTINGS` |
| `th.html`, `th.css`, `th.js` | Clusters tab: theme picker, body maps, 28-day cycle and the life of a cell, mechanisms and their in-depth view, network, pathways; per theme and gene, how many ClinVar pathogenic variants a chip can see (`genome/imputability.py`) |
| `md.html`, `md.css`, `md.js` | Medicines tab: drug genes (star alleles and CPIC type), and per medicine (searchable by any name, brand, ATC code or class) its dosing guidance and every finding with the person's reading, each with an evidence grade A+ to C |
| `nt.html`, `nt.css`, `nt.js` | Nutrition tab: per nutrient the net effect on the blood level, then the mechanism in writing: Reactome's account of each pathway, and for each gene a variant is pinned to, the step (Reactome), the protein (UniProt) and what the person's variants change; the intake target as one line |
| `i18n.js` | English / Swedish switch (the EN/SV buttons in the header; the page's last script) |
| `i18n_sv.json` | The Swedish dictionary for the page's own wording, published as the `i18n_sv` dataset (`[{en, sv}]` rows) |
| `i18n_sv_terms.json` | Swedish for source terms: the library's traits, systems and genotype readings, module names, and disease/trait names (Open Targets, GWAS Catalog, ClinVar); published as the `i18n_sv_terms` dataset |
| `i18n_terms.py` | Lists the source terms the page shows and which lack Swedish; writes the `i18n_sv_terms` rows |

### Swedish

The page is written and drawn in English. With SV selected, `i18n.js` watches the page and swaps every text, tooltip,
placeholder and accessible label for its Swedish version as it is drawn; EN restores the English as drawn. The choice
is kept per viewer in the browser (`localStorage`), English when it can't be read.

- Translations live in `i18n_sv.json`, keyed by the English text, and reach the page as the `i18n_sv` dataset (the page
  document has a 256 KB limit, so the dictionary isn't inline). `{}` stands for a value that varies
  ("`{} genes act here`"); `{0}` `{1}` in the Swedish reorder values. A value that is itself a key is translated too
  ("Less active ×2"), counts agree in number ("1 mindre aktiv", "5 mindre aktiva"), and labels drawn in capitals use
  their key's translation.
- Source terms have their own dictionary, `i18n_sv_terms.json`: the library's texts (`cluster_analysis/library/snp_traits.json`), the
  module names (`module_names.json`) and disease/trait names. The page's wording wins when both have a key.
- Other text from the sources stays as published: gene names, UniProt, ClinPGx and CPIC texts, Reactome and GO names,
  paper titles.
- When page wording changes, add its Swedish to `i18n_sv.json` and republish the `i18n_sv` dataset; text without a key
  simply stays English. Publish the rows, never the file itself: `i18n_sv.json` is `{english: swedish}`, the page reads
  `[{en, sv}]` rows and quietly ignores anything else (all page wording then stays English):
  `python cluster_analysis/explorer/i18n_terms.py --publish i18n_sv_rows.json --page`.
- After the library or the theme datasets change, check for new terms and republish `i18n_sv_terms`:

  ```bash
  python cluster_analysis/explorer/i18n_terms.py DATASET_DIR                  # what lacks Swedish
  python cluster_analysis/explorer/i18n_terms.py DATASET_DIR --todo todo.json # the missing terms, to translate
  python cluster_analysis/explorer/i18n_terms.py --publish i18n_sv_terms.json # the dataset's [{en, sv}] rows
  ```
- After editing `i18n.js`, rebuild with `build.py`, as with the other parts.
- The dictionaries are loaded by empty `data-draw="i18n-load"` / `"i18n-terms"` spans in the header. Don't give them
  the `hidden` attribute: the Dashboard runtime never runs a draw inside `[hidden]`, so nothing would load (they are
  kept out of sight with the `.gx-i18n` class instead).
- The layer only reads and writes inside `.gx` (the explorer's own markup). The dashboard's interface around the page
  is React-drawn and watches its own text and labels; translating it fights React and froze the page.

The page holds no genotypes. Its data comes from the datasets next to it (`data/<name>.json`).

## Profiles

Every personal analysis runs per profile (`cluster_analysis/profiles.json`: id, sex, DNA file), and the header's
**Profile** switch picks whose results the page shows. Each personal dataset holds every profile's rows, tagged with
`person`; `gx.rows()` hands a draw only the selected person's rows, so the tabs don't filter themselves. `gx.who()` is
the selected id (the `person` param, remembered in the browser). Themes follow the profile's sex: female fertility
exists only for female profiles, male fertility only for male ones, cancer for everyone. Static texts that name the
person carry `data-who`: their "XY" is rewritten to the selected id, and the Swedish keys are `{}` templates.

```bash
python -m cluster_analysis.profiles check                  # sex from the DNA (X heterozygosity) against profiles.json
python -m cluster_analysis.profiles run                    # per profile: theme cross-references, gene calls, medicines,
                                                           # nutrition (with the profile's sex), Profile tab overlay
python -m cluster_analysis.explorer.export out/bundle.json --lifecycles data/output/cluster_analysis/lifecycles_XY_full.json
```

`profiles run` writes medicines, nutrition and the overlay to `data/output/cluster_analysis/profiles/<id>/`, the theme
cross-references and gene calls to `data/output/cluster_analysis/`. `export_dashboard` then writes every dataset next
to `out/bundle.json` for all profiles at once: `lifecycle_steps`, `lifecycle_genes`, `gene_function`, the four
`theme_*`, `med_genes`, `med_drugs`, `med_guidance`, `nut_nutrients`, `nut_findings`, the four `hp_*` (person-tagged),
`med_names` and `nut_steps` (public), and `profiles` (ids and sex). The lifecycles are walked once; each profile's
calls are laid over them. All but `med_names`, `nut_steps` and `profiles` contain genotypes, so keep them out of git.

## The old claude.ai artifact

No longer updated; publish only when asked (`build.py --publish` writes the minified page and checks it against the
artifact's 262,144-byte document limit; `python -m cluster_analysis.explorer publish` lists what changed, steps in
[CLAUDE.md](../../CLAUDE.md)). Publishing goes through the artifact's database:
- Each dataset file is uploaded as an asset, and its `datasets/<name>` document points at the asset URL.
- The page is the `text` field of the `files/index.html` document: `build/publish.json` as written by `build.py`.
- Shared filter defaults (theme, gene) are in `dash/params`.

On the artifact the page runs on claude.ai's Dashboard runtime (`dash.draw`, `dash.params`, `gx.*` helpers); `build.py
--standalone` gives it its own (`runtime/dash.js`), so it also runs from any web server. It still doesn't open from
`file://`: browsers block `fetch` of the datasets there.

The runtime runs **each `<script>` in its own scope**: a `const` in `md.js` is not visible from `nt.js`. What scripts
share goes on `window` (as `gx` and `I18N` do); anything else a part needs, it defines itself (`nt.js` has its own
`ntMake`, `ntTag` ... rather than borrowing `mdMake`). A local test page that concatenates the scripts hides this:
wrap each script in `(() => { ... })();` when testing. After a publish, the runtime logs a viewer's failures in the
artifact's `data/users/<id>/runs` document (dataset load status per dataset, and script errors such as
`ReferenceError`).
