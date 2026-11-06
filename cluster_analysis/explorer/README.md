# Gene Cluster Explorer (dashboard page)

The interactive explorer published as a private claude.ai Dashboard artifact:
https://claude.ai/artifact/Rsz3RYugnZyvWnixS9168o

`index.html` is the complete page as published. The other files are its parts, the ones edited in this round:

| File | Part |
|---|---|
| `lc.html`, `lc.css`, `lc.js` | Gene lifecycle tab: gene summary, node graph, step details with capacity, evidence and papers |
| `th.html`, `th.css`, `th.js` | Clusters tab: theme picker, body maps, 28-day cycle and the life of a cell, mechanisms and their in-depth view, network, pathways |
| `md.html`, `md.css`, `md.js` | Medicines tab: drug genes (star alleles and CPIC type), and every ClinPGx drug annotation with the person's reading, searchable and filtered by evidence |

The page holds no genotypes. Its data comes from datasets uploaded next to it in the artifact, written by:

```bash
python -m cluster_analysis.theme_graph fertility_female    # XX's cross-reference
python -m cluster_analysis.theme_graph fertility_male      # XY's cross-reference
python -m cluster_analysis.theme_graph cancer              # XY's cross-reference, cell-life stages
python -m cluster_analysis.medicines                       # XY's drug genes and medicines -> med_genes, med_drugs
python -m cluster_analysis.export_dashboard out/bundle.json \
    --lifecycles data/output/cluster_analysis/lifecycles_XY.json --dna data/input/MyHeritage_raw_dna_data_XY.csv
```

That writes `lifecycle_steps`, `lifecycle_genes`, `gene_function`, `theme_meta`, `theme_genes`, `theme_links` and `theme_pathways` next to `out/bundle.json`; `medicines.py` writes `med_genes` and `med_drugs` to `data/output/cluster_analysis/`. These contain XY's and XX's genotypes, so keep them out of git.

Publishing goes through the artifact's database:
- Each dataset file is uploaded as an asset, and its `datasets/<name>` document points at the asset URL.
- The page is the `text` field of the `files/index.html` document.
- Shared filter defaults (theme, gene) are in `dash/params`.

The page runs on the Dashboard runtime (`dash.draw`, `dash.params`, `gx.*` helpers), so it doesn't open as a plain local HTML file.
