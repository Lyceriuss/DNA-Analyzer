# Gene lifecycles

The Lifecycle tab follows one gene's product through the body: where its building block comes from, the reactions
before and after the gene's own step, the cofactors it needs, who regulates it, and where the product ends up
(excreted, made inert, burned for energy or recycled). The person's genotype is shown on every library enzyme.

## Building a lifecycle

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
    STEPS & RH & OP --> LC["lifecycles_XY.json"]
    CALLS["XY's calls (offline)"] --> OVER["genotype + evidence call<br/>on each library enzyme"]
    LC --> OVER
    OVER --> EXP["export_dashboard.py --lifecycles"]
    EXP --> D1["lifecycle_steps"]
    EXP --> D2["lifecycle_genes"]
    EXP --> D3["gene_function<br/>evidence, genotype ladder, papers"]
```

```bash
python -m cluster_analysis.lifecycle MTHFR ALDH2 --dna data/input/MyHeritage_raw_dna_data_XY.csv --out data/output/cluster_analysis/lifecycles_XY.json
python -m cluster_analysis.gene_trace ALDH2 --dna data/input/MyHeritage_raw_dna_data_XY.csv     # upstream / downstream trace of one gene
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
