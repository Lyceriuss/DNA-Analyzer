# Cluster analysis architecture

How the gene-cluster side of DNA-Analyzer fits together: from a MyHeritage file, through imputation and public research
data, to the Gene Cluster Explorer. The PDF report has its own page, [../ARCHITECTURE.md](../ARCHITECTURE.md).

| Page | What it covers |
|---|---|
| [imputation.md](imputation.md) | From ~600k measured SNPs to ~28 million calls, and the confidence tiers that say which calls to trust |
| [sources.md](sources.md) | Every external source: what it gives, how we reach it (API or bulk download), and the keys that join them |
| [themes.md](themes.md) | Theme graphs (cancer, fertility, muscle), the DNA cross-reference and what each gene colour means |
| [evidence.md](evidence.md) | Gene function calls from evidence (GoF / LoF), the library audit and its corrections |
| [lifecycles.md](lifecycles.md) | A gene's chemical lifecycle: Reactome steps, cofactors, regulators and papers |
| [medicines.md](medicines.md) | Drug genes, star alleles, ClinPGx annotations, guidelines, drug labels and ClinVar drug response |
| [explorer.md](explorer.md) | The datasets the explorer reads, its tabs, and how a new version is published |

## The whole system

```mermaid
flowchart LR
    subgraph IN["Person (local only)"]
        CSV["MyHeritage CSV<br/>~600k SNPs"]
    end
    subgraph REF["Reference data (downloaded once)"]
        KG["1000 Genomes panel<br/>+ site frequencies"]
        CV["ClinVar VCF"]
        GW["GWAS Catalog"]
        PGX["ClinPGx + CPIC"]
        GTF["Ensembl gene coordinates"]
    end
    subgraph API["Public APIs (gene symbols and rsIDs only)"]
        OT["Open Targets"]
        GO["QuickGO"]
        ST["STRING"]
        RX["Reactome"]
        EV["VEP, UniProt, MaveDB, GTEx"]
        LIT["Europe PMC"]
    end
    LIB["config/snp_traits.json<br/>library, 247 SNPs"]

    CSV --> IMP["src/impute.py<br/>Beagle"]
    KG --> IMP
    IMP --> CALLS["Imputed calls<br/>~28M, with confidence tier"]

    OT & GO & ST & RX --> TG["theme_graph.py<br/>theme graphs"]
    LIB --> FE["function_evidence.py"]
    EV --> FE
    FE --> EC["evidence_call.py<br/>GoF / LoF"]
    RX --> LC["lifecycle.py, gene_trace.py"]
    LIT --> LITPY["literature.py"]

    CALLS --> XR["cross-reference<br/>(offline)"]
    TG --> XR
    CV & GW & GTF --> XR
    CALLS --> MED["medicines.py"]
    PGX & CV --> MED
    CALLS --> EC

    XR & EC & LC & LITPY --> EXP["export_dashboard.py"]
    MED --> DS
    EXP --> DS["Datasets (JSON)"]
    DS --> UI["Gene Cluster Explorer<br/>claude.ai artifact"]
    LIB --> AUD["library_audit.py"]
    EC --> AUD
    GW --> AUD
    AUD --> DOC["docs/LIBRARY_AUDIT.md"]
```

## The privacy boundary

The person's genotypes never leave the machine. Everything that talks to the internet works on public identifiers;
everything that touches a genotype runs offline against local reference files.

```mermaid
flowchart TB
    subgraph ONLINE["Sent to APIs"]
        direction LR
        A1["Gene symbols"] ~~~ A2["rsIDs from the library or the reference data"] ~~~ A3["Disease and GO term IDs"]
    end
    subgraph OFFLINE["Offline only"]
        direction LR
        B1["The DNA file and imputed calls"] ~~~ B2["Cross-reference, star alleles, evidence calls"] ~~~ B3["Datasets with genotypes"]
    end
    ONLINE -- "answers cached in cluster_analysis/cache/" --> OFFLINE
    OFFLINE -. "never" .-> ONLINE
```

- `data/input`, `data/output` and `data/reference` are gitignored. The repo is public, so genotypes and raw files must
  never be committed.
- Datasets with genotypes (`theme_genes`, `gene_function`, `med_*` ...) are published only to the private artifact.
- `sources.py` caches every API answer on disk, so a re-run sends nothing new.

## How the pieces join

Four keys connect every source. A gene symbol links the themes, the library, the lifecycles and the drug genes; an
rsID and its GRCh37 position link a genotype to ClinVar, the GWAS Catalog and ClinPGx.

```mermaid
erDiagram
    GENE ||--o{ SNP : "lies in (Ensembl coordinates)"
    GENE ||--|| PROTEIN : "UniProt accession"
    PROTEIN ||--o{ REACTION : "Reactome, Rhea"
    THEME ||--o{ GENE : "Open Targets, QuickGO"
    SNP ||--o{ GWAS_HIT : "rsID"
    SNP ||--o{ CLINVAR_RECORD : "position + alleles"
    SNP ||--o{ DRUG_ANNOTATION : "rsID or star allele"
    SNP ||--o| LIBRARY_ENTRY : "rsID"
    PERSON_CALL }o--|| SNP : "rsID, GRCh37 forward strand"
```

All positions are GRCh37 and all alleles are on the forward strand, as in the MyHeritage files. Ensembl's REST API
works in GRCh38, so it is only used by rsID, never by position.

## Profiles

| Profile | Whose | Used for |
|---|---|---|
| XY | The user's own DNA | Cancer, male fertility, muscle, lifecycles, medicines |
| XX | Female fertility blueprint | Female fertility |

Other people's files in `data/input` are never published.
