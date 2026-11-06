# Sources

Every external source the cluster analysis uses, what it contributes and how it is reached. APIs receive only public
identifiers; bulk files are downloaded once to `data/reference/` (gitignored) and read offline.

## By layer

```mermaid
flowchart TB
    subgraph L1["1 · Which genes belong to a theme"]
        OT["Open Targets<br/>disease → genes, scores"]
        QG["QuickGO<br/>GO term → genes"]
    end
    subgraph L2["2 · How the genes connect"]
        ST["STRING<br/>protein interactions"]
        RX1["Reactome<br/>shared pathways"]
    end
    subgraph L3["3 · The person's DNA against the theme (offline)"]
        GTF["Ensembl GTF<br/>gene coordinates"]
        CV["ClinVar VCF<br/>pathogenic, drug response"]
        GW["GWAS Catalog<br/>trait associations, alleles, direction"]
    end
    subgraph L4["4 · What a variant does to its gene"]
        VEP["Ensembl VEP<br/>alleles, consequence,<br/>frequency, SIFT/PolyPhen"]
        UP["UniProt variation<br/>curated effects"]
        MV["MaveDB<br/>measured function"]
        GT["GTEx<br/>expression (eQTL)"]
        CP1["ClinPGx API<br/>drug annotations per rsID"]
        LD["Ensembl LD<br/>SNPs inherited together"]
    end
    subgraph L5["5 · A gene's lifecycle"]
        UP2["UniProt<br/>function, cofactors"]
        RH["Rhea<br/>reactions"]
        RX2["Reactome<br/>reaction chains"]
        OP["OmniPath<br/>regulators"]
        EPMC["Europe PMC<br/>papers"]
    end
    subgraph L6["6 · Medicines (offline)"]
        CPA["ClinPGx clinical annotations"]
        CPG["ClinPGx guidelines<br/>CPIC, DPWG, CPNDS, RNPGx …"]
        CPL["ClinPGx drug labels<br/>FDA, EMA, PMDA, HC, Swissmedic"]
        CPR["CPIC recommendations<br/>per metaboliser type"]
        KG["1000 Genomes frequencies<br/>five ancestries"]
    end
    L1 --> L2 --> L3
    L4 --> L3
```

## Table

| Source | Access | Gives us | Used by |
|---|---|---|---|
| Open Targets | GraphQL API | Genes associated with a disease, with overall and genetic scores | `theme_graph.py` |
| QuickGO | REST API | Genes with experimental or curated GO annotations to a mechanism | `theme_graph.py` |
| STRING | REST API | Protein–protein interactions (confidence ≥ 0.4), enrichment | `theme_graph.py`, `themes.py`, `build_modules.py` |
| Reactome | REST API + `Ensembl2Reactome.txt` | Pathways, ordered reactions, inputs and outputs | `theme_graph.py`, `lifecycle.py`, `gene_trace.py` |
| MyGene.info | REST API | Gene summaries, GO and Reactome per gene | `themes.py`, `sources.py` |
| Ensembl GTF (GRCh37) | Bulk file | Gene start and end, to place SNPs in genes | `theme_graph.py` |
| ClinVar (GRCh37) | Bulk VCF | Pathogenic variants, risk factors, drug response | `theme_graph.py`, `medicines.py` |
| GWAS Catalog | Bulk zip (+ REST API per rsID) | Genome-wide significant associations, effect allele, OR/beta and direction | `theme_graph.py`, `library_audit.py`, `biomarkers.py` |
| Ensembl VEP | REST API | Forward-strand alleles, consequence per allele, European frequency, SIFT/PolyPhen | `sources.py`, `function_evidence.py` |
| Ensembl LD | REST API | Partner SNPs (r² ≥ 0.6, Europeans) so a GWAS lead SNP can support a library SNP | `library_audit.py` |
| UniProt | REST API + `humsavar.txt` | Curated variant effects, protein function, cofactors | `function_evidence.py`, `gene_trace.py` |
| MaveDB | REST API | Deep mutational scan scores per protein change | `function_evidence.py` |
| GTEx v8 | REST API | eQTLs: which allele raises or lowers expression, per tissue | `function_evidence.py` |
| Rhea | REST API | Chemical reactions of an enzyme | `gene_trace.py` |
| OmniPath | REST API | Directed, signed regulators of a gene | `gene_trace.py`, `lifecycle.py` |
| Europe PMC | REST API | Papers naming a SNP, quoted effect sizes | `literature.py` |
| ClinPGx (PharmGKB) | Bulk zips + REST API | Clinical annotations, guideline annotations, drug labels | `medicines.py`, `function_evidence.py` |
| CPIC | REST API, saved as JSON | Recommendation per metaboliser type or activity score | `medicines.py` |
| 1000 Genomes | Bulk panel + site list | Imputation; allele frequencies in five ancestries | `src/impute.py`, `medicines.py` |

Downloads: `scripts/fetch_imputation_reference.sh` (imputation) and `scripts/fetch_pgx_reference.sh` (medicines).

## Caching and politeness

```mermaid
sequenceDiagram
    participant M as module
    participant S as sources._cached
    participant D as cluster_analysis/cache/
    participant A as API
    M->>S: namespace, key (gene list or rsID)
    S->>D: look for namespace_sha1(key).json
    alt cached
        D-->>S: JSON
    else not cached
        S->>A: request (retry and back off on 429/503)
        A-->>S: JSON
        S->>D: save
    end
    S-->>M: JSON
```

STRING and ClinPGx ask for at most one or two requests per second; the clients sleep between calls.
