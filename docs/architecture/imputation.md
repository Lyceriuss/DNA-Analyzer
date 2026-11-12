# Imputation and confidence tiers

`genome/impute.py` fills in the SNPs MyHeritage didn't report, by comparing the person's measured SNPs with the
haplotypes of the people in a 1000 Genomes reference panel. Each new call gets a confidence tier, so later steps can
decide which calls to trust.

## Input files

`genome/formats.py` reads MyHeritage (CSV), AncestryDNA (the `.txt`, or the `.zip` Ancestry delivers) and 23andMe
files, gzipped or zipped, into one shape: rsid, chromosome, position, genotype. All three are GRCh37; `impute.py`
stops when fewer than 70% of a file's positions are 1000 Genomes sites, which is what a file on another build looks
like (MyHeritage files match 98.7%). `python -m genome.formats FILE` shows what a file holds.

The AncestryDNA reader is tested on synthetic files (`tests/test_formats.py`) and on a MyHeritage file rewritten in
Ancestry's layout: every call reads the same, and chromosome 22 imputes to byte-identical output.

Beagle's output depends on its thread count (`--threads`): the same file on 6 and 8 threads differed in 1.8% of
chromosome 22's calls, mostly uncertain ones. Keep the thread count fixed where results must be reproducible.

## Panels and genome builds

| Panel | Build | People | Calls kept per person | Where |
|---|---|---|---|---|
| `1kgp_hc`: 1000 Genomes high coverage (30×), the default | GRCh38 | 3,202 | ~62 million | 15 GB of bref3 outside the repo (`DNA_PANEL_DIR_1KGP_HC`) |
| `1kg_phase3`: 1000 Genomes phase 3 | GRCh37 | 2,504 | ~28 million | `data/reference/imputation/panel` |

`genome/build.py` (`DNA_BUILD`, default GRCh38) picks the panel and every reference file that must share its
coordinates: ClinVar, Ensembl genes, the site list, the PGS scoring files. Results go to per-build folders
(`data/output/cluster_analysis_GRCh38`, `data/output/explorer_GRCh38`), so `DNA_BUILD=GRCh37` still reproduces the
earlier analysis for comparison.

On GRCh38, MyHeritage's GRCh37 positions are lifted with UCSC's `hg19ToHg38` chain when the file is read (about 270
of 585,000 calls don't map and are dropped). chrX is imputed in three parts (PAR1, the body, PAR2), because men are
diploid in the pseudo-autosomal regions and haploid between them, and Beagle wants one ploidy per sample per file.
The panel names variants `chrom:pos:ref:alt`; rsIDs and frequencies per superpopulation come from its site list,
built by `genome/panel_sites.py` from the panel itself and Ensembl's GRCh38 dbSNP files (98% of SNPs get an rsID).

```bash
sh scripts/fetch_1kgp_hc_panel.sh "D:/DNA-Analyzer-reference/1kGP_high_coverage_GRCh38"   # download, check, convert
python -m genome.panel_sites                                                                # the site list
python -m genome.build fetch                                                                # GRCh38 ClinVar and genes
python -m genome.references status                                                          # is everything there?
```

None of this needs Docker: the site list, the chrX split and the record counts read the panel's VCFs in Python
(`genome/vcf.py`), and are checked against the panel's index counts.

### Reference files

`genome/references.json` lists every reference file: its source and version, how it is made, and what uses it. It
sorts them into tiers:
- `impute`: needed to impute a person.
- `analyse`: needed to analyse the result.
- `built`: made here from the sources (the PGS reference, the imputability map).
- `source`: the raw panel (32 GB) and dbSNP (13 GB), kept so every built file can be rebuilt without downloading.
- `grch37`: the comparison build.

`python -m genome.references status` shows what is present and whether a run can start. `lock` writes checksums to
`data/reference/references.lock.json`. `verify` checks the raw panel against the 1000 Genomes MD5 manifest, and the
rest against the lock file.

Measured the same way (every 10th SNP hidden), both panels are equally accurate on what a chip can test: 98.9% of
confident calls right, 99.5% at high confidence. The high-coverage panel's gain is coverage (2.2× the calls) and the
build the sources use. Its "doesn't carry it" calls for uncommon variants found 89.5% of real carriers in XY (91% on
phase 3), just below the 90% bar, so those calls read `not_excluded`.

### What a chip can see: the imputability map

`genome/imputability.py` measures, site by site, what a chip plus imputation can recover. It holds out 100 European
founders from the panel, masks them to the chip's positions, imputes them with Beagle against the other 3,102 people
and compares each site with their real genotypes. Each site gets a class from its measured r² (or, where the held-out
people carry fewer than 3 copies of the minor allele, from the calibrated r² of its frequency and DR2 band):

| Class | Sites (chr1–22) |
|---|---|
| chip: measured | 559,703 |
| reliable: r² ≥ 0.8 | 11,347,429 |
| uncertain: r² ≥ 0.5 | 2,465,197 |
| not knowable | 56,319,686 |

```bash
python -m genome.imputability run       # per chromosome, about 7 hours in all; per-site tables on D:
python -m genome.imputability summary   # summary.json, genes.json, clinvar_variants.json in data/reference/imputability
```

`genes.json` counts ClinVar's pathogenic and likely pathogenic variants per gene by class, plus those not in the panel
at all (339,655 of 340,908 on chr1–22) and those on chrX (`not_mapped`; chrX isn't mapped yet). The explorer's
Clusters tab shows it per theme and per gene ("What a chip can see"), so a clean result says how much it rules out.

The rest of this page describes the method; the figures below are from the phase 3 panel.

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
python -m genome.impute data/input/MyHeritage_raw_dna_data_XY.csv     # impute, then finalize
python -m genome.impute data/input/... --validate 10                 # hide every 10th measured SNP and score the guesses
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

`genome/loader.py` applies the policy: `CONFIDENT = ("measured", "high")` is the default for single-SNP conclusions
(library, medicines, pathogenic carrier status). `theme_graph.py` uses `FINDING_TIERS = measured, high, medium` for
findings and `CARRIED_TIERS = measured, high` for pathogenic variants.

## Reading the file

```mermaid
sequenceDiagram
    participant Caller as theme_graph / medicines / analyzer
    participant L as genome/loader.py
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
