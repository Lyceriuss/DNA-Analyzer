# Imputation and confidence tiers

`src/impute.py` fills in the SNPs MyHeritage didn't report, by comparing the person's measured SNPs with the
haplotypes of the 2,504 people in 1000 Genomes. It takes a file from ~600k SNPs to ~28 million calls. Each new call
gets a confidence tier, so later steps can decide which calls to trust.

## Pipeline

```mermaid
flowchart TB
    CSV["data/input/MyHeritage_raw_dna_data_XY.csv"] --> H["harmonize<br/>match each SNP to a 1000 Genomes site,<br/>flip strand where needed"]
    SITES["sites.vcf.gz<br/>1000 Genomes site list"] --> H
    H --> VCF["target VCF per chromosome"]
    VCF --> B["Beagle 5.5<br/>1000 Genomes phase 3 panel (bref3)<br/>GRCh37 genetic maps"]
    B --> OUT["imputed VCF<br/>genotype + probability (GP)"]
    OUT --> F["finalize<br/>keep GP ≥ 0.9, add EUR_AF,<br/>assign a tier"]
    CAL["calibration table<br/>from --validate"] --> F
    F --> IMP["data/output/imputation/XY/<br/>…XY.imputed.csv (1.8 GB)"]
```

```bash
bash scripts/fetch_imputation_reference.sh                      # Beagle, panels, maps, site list (~5 GB)
python -m src.impute data/input/MyHeritage_raw_dna_data_XY.csv     # impute, then finalize
python -m src.impute data/input/... --validate 10                 # hide every 10th measured SNP and score the guesses
```

Output columns: `RSID, CHROMOSOME, POSITION, RESULT, SOURCE, GP, EUR_AF, CONFIDENCE`.

## How the tiers are measured

`--validate` hides every tenth measured SNP (~58k for XY), imputes them and compares each guess with the real call.
Accuracy is counted per **allele-frequency band** (how common the variant is) and per **GP band** (Beagle's own
certainty). With one person, Beagle's DR2 quality score is 0 at homozygous sites, so GP is used instead.

```mermaid
flowchart LR
    M["Measured SNPs"] --> HIDE["Hide 1 in 10"]
    HIDE --> RUN["Impute"]
    RUN --> CMP["Compare guess with truth"]
    CMP --> TAB["Accuracy per<br/>frequency band × GP band"]
    CMP --> SENS["Sensitivity per frequency band:<br/>of real carriers, how many<br/>were called carriers"]
    TAB & SENS --> TIERS["Tier rules"]
```

## Tiers

```mermaid
flowchart TB
    C{"Call"} -->|"in the MyHeritage file"| MEAS["measured"]
    C -->|"imputed"| N{"≥ 100 validated calls<br/>in its band?"}
    N -->|no| UNT["untested"]
    N -->|yes| ACC{"measured accuracy<br/>in its band"}
    ACC -->|"≥ 98%"| HIGH["high"]
    ACC -->|"≥ 90%"| MED["medium"]
    ACC -->|"< 90%"| LOW["low"]
    HIGH & MED --> RARE{"'Doesn't carry it'<br/>in a band where < 90% of<br/>real carriers were found?"}
    RARE -->|yes| NE["not_excluded"]
    RARE -->|no| KEEP["keeps its tier"]
```

| Tier | Meaning | Used for |
|---|---|---|
| measured | Reported by MyHeritage | Everything |
| high | ≥ 98% correct in validation | Everything, marked "imputed" |
| medium | ≥ 90% correct | Theme findings (GWAS, ClinVar non-pathogenic), not single-SNP conclusions |
| low | < 90% | Counted, not used |
| untested | Fewer than 100 validation calls in its band | Counted, not used |
| not_excluded | "Doesn't carry it" for a rare variant imputation often misses | Shown as "not detected, not excluded" |

`src/loader.py` applies the policy: `CONFIDENT = ("measured", "high")` is the default for single-SNP conclusions
(library, medicines, pathogenic carrier status). `theme_graph.py` uses `FINDING_TIERS = measured, high, medium` for
findings and `CARRIED_TIERS = measured, high` for pathogenic variants.

## Reading the file

```mermaid
sequenceDiagram
    participant Caller as theme_graph / medicines / analyzer
    participant L as src/loader.py
    participant F as imputed CSV
    Caller->>L: iter_calls(path, rsids, confidence)
    loop each line
        L->>F: read line
        L->>L: skip cheaply if the rsID isn't wanted
        L->>L: skip if the tier isn't wanted
        L-->>Caller: (rsid, chrom, pos, genotype, tier)
    end
```

`imputed_path()` swaps a raw file for its imputed version when one exists, so every command takes the raw path and
uses the imputed file automatically (`--measured-only` turns that off).
