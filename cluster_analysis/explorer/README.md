# Gene Cluster Explorer (dashboard page)

The interactive explorer published as a private claude.ai Dashboard artifact:
https://claude.ai/artifact/Rsz3RYugnZyvWnixS9168o

`index.html` is the complete page as published. The other files are its parts, the ones edited in this round:

| File | Part |
|---|---|
| `lc.html`, `lc.css`, `lc.js` | Gene lifecycle tab: gene summary, node graph, step details with capacity, evidence and papers |
| `th.html`, `th.css`, `th.js` | Clusters tab: theme picker, body maps, 28-day cycle and the life of a cell, mechanisms and their in-depth view, network, pathways |
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
- Source terms have their own dictionary, `i18n_sv_terms.json`: the library's texts (`config/snp_traits.json`), the
  module names (`module_names.json`) and disease/trait names. The page's wording wins when both have a key.
- Other text from the sources stays as published: gene names, UniProt, ClinPGx and CPIC texts, Reactome and GO names,
  paper titles.
- When page wording changes, add its Swedish to `i18n_sv.json` and republish the `i18n_sv` dataset; text without a key
  simply stays English.
- After the library or the theme datasets change, check for new terms and republish `i18n_sv_terms`:

  ```bash
  python cluster_analysis/explorer/i18n_terms.py DATASET_DIR                  # what lacks Swedish
  python cluster_analysis/explorer/i18n_terms.py DATASET_DIR --todo todo.json # the missing terms, to translate
  python cluster_analysis/explorer/i18n_terms.py --publish i18n_sv_terms.json # the dataset's [{en, sv}] rows
  ```
- After editing `i18n.js`, copy it into `index.html`'s last `<script>` block, as with the other parts.
- The dictionaries are loaded by empty `data-draw="i18n-load"` / `"i18n-terms"` spans in the header. Don't give them
  the `hidden` attribute: the Dashboard runtime never runs a draw inside `[hidden]`, so nothing would load (they are
  kept out of sight with the `.gx-i18n` class instead).
- The layer only reads and writes inside `.gx` (the explorer's own markup). The dashboard's interface around the page
  is React-drawn and watches its own text and labels; translating it fights React and froze the page.

The page holds no genotypes. Its data comes from datasets uploaded next to it in the artifact, written by:

```bash
python -m cluster_analysis.theme_graph fertility_female    # XX's cross-reference
python -m cluster_analysis.theme_graph fertility_male      # XY's cross-reference
python -m cluster_analysis.theme_graph cancer              # XY's cross-reference, cell-life stages
python -m cluster_analysis.medicines                       # XY's drug genes and medicines -> med_genes, med_drugs, med_guidance, med_names
python -m cluster_analysis.nutrition                       # XY's nutrients -> nut_nutrients, nut_findings, nut_steps
python -m cluster_analysis.overlay data/input/MyHeritage_raw_dna_data_XY.csv --dashboard out   # Profile: hp_modules, hp_links, hp_bridges, hp_tilts
python -m cluster_analysis.gene_calls                      # per-gene calls from each theme person's own variants -> gene_calls_<person>
python -m cluster_analysis.export_dashboard out/bundle.json \
    --lifecycles data/output/cluster_analysis/lifecycles_XY.json --dna data/input/MyHeritage_raw_dna_data_XY.csv
```

That writes `lifecycle_steps`, `lifecycle_genes`, `gene_function`, `theme_meta`, `theme_genes`, `theme_links` and `theme_pathways` next to `out/bundle.json`; `medicines.py` writes `med_genes`, `med_drugs`, `med_guidance` and `med_names`, and `nutrition.py` writes `nut_nutrients`, `nut_findings` and `nut_steps`, to `data/output/cluster_analysis/`. All but `med_names` and `nut_steps` contain XY's genotypes, and the theme datasets XX's, so keep them out of git.

Publishing goes through the artifact's database:
- Each dataset file is uploaded as an asset, and its `datasets/<name>` document points at the asset URL.
- The page is the `text` field of the `files/index.html` document.
- Shared filter defaults (theme, gene) are in `dash/params`.

The page runs on the Dashboard runtime (`dash.draw`, `dash.params`, `gx.*` helpers), so it doesn't open as a plain local HTML file.

The runtime runs **each `<script>` in its own scope**: a `const` in `md.js` is not visible from `nt.js`. What scripts
share goes on `window` (as `gx` and `I18N` do); anything else a part needs, it defines itself (`nt.js` has its own
`ntMake`, `ntTag` ... rather than borrowing `mdMake`). A local test page that concatenates the scripts hides this:
wrap each script in `(() => { ... })();` when testing. After a publish, the runtime logs a viewer's failures in the
artifact's `data/users/<id>/runs` document (dataset load status per dataset, and script errors such as
`ReferenceError`).
