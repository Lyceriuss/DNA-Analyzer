# The Gene Cluster Explorer

A local web page, served on 127.0.0.1 by `python -m cluster_analysis.explorer serve` (it was first a claude.ai artifact,
no longer updated). The page holds no genotypes itself; it reads the datasets next to it.

## Tabs and their datasets

```mermaid
flowchart LR
    subgraph PAGE["index.html"]
        P["Profile"]
        B["Biomarkers"]
        L["Lifecycle<br/>lc.*"]
        C["Clusters<br/>th.*"]
        M["Medicines<br/>md.*"]
        N["Nutrition<br/>nt.*"]
    end
    HM["hp_modules, hp_links,<br/>hp_bridges, hp_tilts, kpis"] --> P
    BS["biomarker_snps, bio_reach,<br/>module_biomarker"] --> B
    LS["lifecycle_steps"] --> L
    LG["lifecycle_genes"] --> L
    GF["gene_function"] --> L
    GF --> C
    TM["theme_meta"] --> C
    TG["theme_genes"] --> C
    TL["theme_links"] --> C
    TP["theme_pathways"] --> C
    MG["med_genes"] --> M
    MD["med_drugs"] --> M
    MGU["med_guidance"] --> M
    MN["med_names"] --> M
    NN["nut_nutrients, nut_findings,<br/>nut_steps"] --> N
```

## Producing the datasets

```mermaid
flowchart TB
    T1["theme_graph.py fertility_female"] --> X1["theme_XX_fertility_female.json"]
    T2["theme_graph.py fertility_male"] --> X2["theme_XY_fertility_male.json"]
    T3["theme_graph.py cancer"] --> X3["theme_XY_cancer.json"]
    LC["lifecycles_XY_full.json"] --> E
    X1 & X2 & X3 --> E["explorer/export.py out/bundle.json<br/>--lifecycles … --dna …"]
    TH["themes.json (muscle)"] --> E
    EVJ["function_evidence.json,<br/>literature.json"] --> E
    E --> D1["lifecycle_steps, lifecycle_genes,<br/>gene_function"]
    E --> D2["theme_meta, theme_genes,<br/>theme_links, theme_pathways"]
    MP["medicines.py"] --> D3["med_genes, med_drugs,<br/>med_guidance, med_names"]
    NP["nutrition.py"] --> D4["nut_nutrients, nut_findings,<br/>nut_steps"]
```

```bash
python -m cluster_analysis.themes.theme_graph fertility_female
python -m cluster_analysis.themes.theme_graph fertility_male
python -m cluster_analysis.themes.theme_graph cancer
python -m cluster_analysis.medicines.medicines
python -m cluster_analysis.nutrition.nutrition
python -m cluster_analysis.library.overlay data/input/MyHeritage_raw_dna_data_XY.csv --dashboard out   # Profile tab datasets
python -m cluster_analysis.explorer.export out/bundle.json \
    --lifecycles data/output/cluster_analysis/lifecycles_XY_full.json      # every profile; the 207-gene walk
```

Gene rows carry the evidence call (`function`: GoF / LoF / normal / altered / unknown) and what it means for the
person (`outcome`: positive / negative / neutral / unclear / typical / unknown; see
[evidence.md](evidence.md#from-the-call-to-positive-or-negative)). The library's old 1–10 ratings are not shown.

Each dataset is a flat list of rows. Nested data (evidence, SNP lists, frequencies) is stored as a JSON string in a
field and parsed by the page.

## Publishing

```mermaid
sequenceDiagram
    participant Dev as local machine
    participant A as Artifact asset store
    participant DB as Artifact database
    participant P as page
    Dev->>A: upload each changed dataset JSON as an asset
    A-->>Dev: /_blob/<id>
    Dev->>DB: batch: datasets/<name> → {source.url: /_blob/<id>} (pinned with if_version)
    Dev->>DB: files/index.html → {text: page} (when the page changed)
    P->>DB: read datasets/*
    P->>A: fetch each dataset
    P->>P: draw tabs (dash.draw, gx.rows)
```

Only changed datasets need uploading; the others keep their asset. Every write is pinned to the version last read, so
a concurrent change is never overwritten.

## Language (English / Swedish)

The page is drawn in English. A translation layer (`i18n.js`, the page's last script) follows what is drawn and, with
Swedish selected, shows each text in Swedish. The drawing code doesn't change, and English stays the fallback.

```mermaid
flowchart LR
    DRAW["dash.draw<br/>writes English text"] --> MO["MutationObserver<br/>(only while SV is on)"]
    MO --> KEEP["keep the English per node"]
    KEEP --> TR{"translate"}
    TR -->|"exact key"| SV["Swedish text"]
    TR -->|"template with {} values"| SV
    TR -->|"several sentences, a list,<br/>tooltip lines"| PARTS["each part on its own"] --> SV
    TR -->|"no key (source text)"| EN["English as drawn"]
    BTN["EN / SV buttons"] --> SET["walk the page:<br/>show Swedish, or restore English"]
    SET --> LS["localStorage<br/>per viewer"]
```

Two dictionaries arrive with the page's other data; text drawn before one arrives is translated when it does:

| Dataset | File | Holds |
|---|---|---|
| `i18n_sv` | `explorer/i18n_sv.json` (~830 entries) | The page's own wording, with `{}` templates |
| `i18n_sv_terms` | `explorer/i18n_sv_terms.json` (~1,600) | Source terms: the library's traits, systems and genotype readings, module names, disease and trait names from Open Targets, the GWAS Catalog and ClinVar |

`explorer/i18n_terms.py` lists which source terms the datasets and the library contain and which still lack Swedish.
Long source texts stay English: UniProt and ClinPGx/CPIC texts, Reactome and GO names, paper titles. A dosing
recommendation is safer read in its original wording than in a translation.

Templates are matched by scanning for their fixed parts, not with regular expressions: a regex with several open
values can backtrack for minutes on a long paragraph. Results are remembered per text, so the cost is paid once.

## Page parts

`page.html` is the shell and `th.*`, `lc.*`, `md.*`, `nt.*` and `i18n.js` are the parts; `build.py` assembles them into
`index.html` and the minified copy that is published (`build/publish.json`, checked against the artifact's 256 KiB
document limit). Colours are CSS tokens with light and dark values. `build.py --standalone` writes the same page as a
static site with its own runtime (`runtime/dash.js`) and tokens (`runtime/tokens.css`), so it runs without claude.ai;
see [migration.md](migration.md).
