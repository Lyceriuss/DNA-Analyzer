# Gene pathways

The Gene pathway tab follows one gene's product through the body: where its building block comes from, the reactions
before and after the gene's own step, the cofactors it needs, who regulates it, and where the product ends up
(excreted, made inert, burned for energy or recycled). The person's genotype is shown on every library enzyme.

The code keeps its older name: the `cluster_analysis/lifecycle` package, the `lifecycle_*` datasets and the tab id
`lifecycle` all belong to this tab. Only the name users see changed ("Gene lifecycle" became "Gene pathway" on 2026-11-16).

## Building a pathway

```mermaid
flowchart TB
    G["gene symbol"] --> UP["UniProt<br/>accession, function, cofactors,<br/>activity regulation"]
    UP --> RX["Reactome<br/>reactions with this protein<br/>as catalyst"]
    RX --> ORD["order the steps<br/>'preceding event' links,<br/>molecules passed on (ChEBI)"]
    ORD --> EXT{"chain ends at<br/>a building block or an exit?"}
    EXT -->|no| SHARE["extend through shared<br/>molecules beyond the pathway"]
    SHARE --> ORD
    EXT -->|yes| STEPS["ordered steps"]
    UP --> RH["Rhea<br/>reaction equations"]
    G --> OP["OmniPath<br/>directed, signed regulators"]
    STEPS & RH & OP --> LC["lifecycle/lifecycles.json<br/>(shipped, no genotypes)"]
    CALLS["each person's calls (offline)"] --> OVER["genotype + evidence call<br/>on each library enzyme"]
    LC --> OVER
    OVER --> EXP["explorer/export.py --lifecycles"]
    EXP --> D1["lifecycle_steps"]
    EXP --> D2["lifecycle_genes"]
    EXP --> D3["gene_function<br/>evidence, genotype ladder, papers"]
```

The published set covers every library gene that has Reactome reactions (207 genes, ~500 pathway roles). Use the
first word of each library `gene` field as the symbol: the rest is an alias in brackets ("AOC1 (DAO)"), and an
alias on its own can name a different protein (DAO is D-amino acid oxidase). TNF is listed as "TNF-alpha" and needs
its official symbol. Reactome returns 503s under load; rerun the failed genes and merge.

The file is built without a DNA file and committed, so every install has the Gene pathway tab and the introduction's
alcohol-chain example (ADH1B, ALDH2): `explorer/export.py --lifecycles` puts each person's own calls on it.
`tests/test_lifecycles.py` checks it holds no genotype. (Until 2026-11-23 it was built with XY's DNA and lived only
in data/output, so fresh installs had neither.)

```bash
GENES=$(python -c "import json; print(' '.join(sorted({v['gene'].split()[0] for v in json.load(open('cluster_analysis/library/snp_traits.json', encoding='utf-8')).values()})))")
python -m cluster_analysis.lifecycle.lifecycle $GENES TNF --out cluster_analysis/lifecycle/lifecycles.json   # no --dna: the file ships
python -m cluster_analysis.lifecycle.gene_trace ALDH2 --dna data/input/MyHeritage_raw_dna_data_XY.csv     # upstream / downstream trace of one gene
```

## The gene panel

```mermaid
flowchart LR
    GF["gene_function row"] --> E["Effect on the gene<br/>evidence call + basis"]
    GF --> LAD["Genotype ladder<br/>capacity per genotype<br/>where MaveDB measured it"]
    GF --> PGX["Drugs (ClinPGx level)"]
    GF --> PAP["Papers with quoted effect sizes"]
    GF --> NOTE["Library note<br/>(written with an LLM)"]
```

Hub molecules that sit in hundreds of reactions (water, ATP, NAD) are treated as currency and don't link steps;
otherwise every lifecycle would connect to every other.
