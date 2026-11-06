# Themes and the DNA cross-reference

A theme (cancer and the life of a cell, female fertility, male fertility, muscle growth) is a graph of genes grouped by
mechanism. The graph is built from public data without looking at anyone's DNA; the person's calls are laid over it
afterwards, offline.

## Two kinds of theme

| Theme | Built by | Genes from | Person |
|---|---|---|---|
| Cancer and the life of a cell | `theme_graph.py` | Open Targets + GO | XY |
| Female fertility | `theme_graph.py` | Open Targets + GO | XX |
| Male fertility | `theme_graph.py` | Open Targets + GO | XY |
| Muscle growth | `themes.py` | The library's genes, matched to facets by GO, Reactome, UniProt and GWAS text | XY |

## Building an API theme

```mermaid
flowchart TB
    DEF["THEMES[theme] in theme_graph.py<br/>diseases (MONDO/EFO IDs), mechanisms (GO terms),<br/>organs or cell-life stages, ClinVar terms"]
    DEF --> OT["Open Targets<br/>genes per disease"]
    DEF --> GO["QuickGO<br/>genes per mechanism term (and below)"]
    OT --> J{"score ≥ 0.5 overall<br/>or ≥ 0.5 genetic?<br/>(not mouse-only)"}
    J -->|yes| G["theme gene"]
    GO --> G
    G --> MECH["assign mechanisms<br/>(no GO → grouped by strongest disease)"]
    MECH --> ORG["organs / cell-life stages"]
    G --> ST["STRING links between theme genes"]
    G --> RX["Reactome pathways shared by theme genes"]
    ORG & ST & RX --> OUT["cluster_analysis/theme_graph_&lt;theme&gt;.json<br/>public data, committed"]
```

## Cross-referencing the person

```mermaid
flowchart TB
    G["theme genes"] --> REG["gene regions<br/>(Ensembl GTF, ±5 kb)"]
    CALLS["imputed calls<br/>iter_calls(confidence=None)"] --> IN{"SNP inside a<br/>theme gene?"}
    REG --> IN
    IN -->|yes| SNP["SNP in gene, with tier"]
    SNP --> CV{"ClinVar record?"}
    CV -->|"pathogenic"| PATH["carried / possible / not_excluded<br/>(any disease: carrier status)"]
    CV -->|"risk factor, protective,<br/>drug response, association<br/>on the theme"| FIND["finding"]
    SNP --> GW{"GWAS hit for a<br/>theme trait?"}
    GW -->|yes| GFIND["finding: trait, effect allele,<br/>copies carried, direction, p"]
    GW -->|"allele missing in the study"| REL["related: alleles from<br/>other studies of the SNP"]
    SNP --> LIB{"library SNP?"}
    LIB -->|yes| LFIND["library text for the genotype"]
    PATH & FIND & GFIND & REL & LFIND --> X["data/output/cluster_analysis/<br/>theme_&lt;person&gt;_&lt;theme&gt;.json"]
```

ClinVar alleles are compared forward strand to forward strand, never flipped: one position can hold a benign and a
pathogenic change (APC rs2229992), and flipping would invent a pathogenic allele.

## What a gene's colour means

```mermaid
flowchart TB
    GENE["theme gene"] --> L{"library SNP<br/>with a genotype?"}
    L -->|yes| EC["evidence call<br/>(evidence.md)"]
    EC --> LOF["less active / less expressed"]
    EC --> GOF["more active / more expressed"]
    EC --> ALT["changed, direction unclear"]
    EC --> NORM["typical function (green)"]
    EC --> UNK["no known effect (grey)"]
    L -->|no| C{"carries a GWAS or ClinVar<br/>allele linked to the theme?"}
    C -->|yes| VAR["carries a trait-linked variant (grey)"]
    C -->|no| NONE["no finding (not coloured)"]
```

Two things to keep in mind when reading the colours:

- **Less or more active is not good or bad.** It describes the gene. A less active tumour suppressor is a risk; a less
  active PCSK9 lowers cholesterol. Whether a change helps or harms depends on the gene's role.
- **"Carries a trait-linked variant" is weak information.** The gene is outside the library, and the person carries at
  least one allele that a genome-wide study linked to a theme trait. Each such allele shifts risk by a few percent, many
  are common, and the label doesn't yet say whether the carried allele raises or lowers the trait. The direction is
  stored per finding (`direction`: raises / lowers) but not yet used for the colour.

## Outputs per theme

| Dataset | One row per | Holds genotypes |
|---|---|---|
| `theme_meta` | theme and mechanism | Counts only |
| `theme_genes` | theme and gene | Yes |
| `theme_links` | interacting gene pair | No |
| `theme_pathways` | shared pathway | No |
