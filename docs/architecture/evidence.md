# Gene function calls and the library audit

The library (`config/snp_traits.json`, 247 SNPs) was written with an LLM. Its sentences say what a genotype means for a
trait, but they are not evidence of what the variant does to the gene. The explorer's labels therefore come from
evidence about the variant, and the library itself is checked against that evidence.

## Gathering evidence

```mermaid
flowchart LR
    LIB["library rsIDs"] --> VEP["Ensembl VEP<br/>alleles, consequence per allele,<br/>European frequency, SIFT/PolyPhen"]
    LIB --> UP["UniProt variation<br/>curated effect text"]
    LIB --> MV["MaveDB<br/>measured score vs wild type"]
    LIB --> GT["GTEx<br/>eQTL direction per tissue"]
    LIB --> CP["ClinPGx<br/>clinical annotations"]
    VEP & UP & MV & GT & CP --> FE["function_evidence.json"]
    LIB --> LIT["Europe PMC + UniProt references"] --> LJ["literature.json<br/>papers, quoted effect sizes"]
```

## The evidence ladder

`evidence_call.py` takes the strongest evidence available for the person's genotype:

```mermaid
flowchart TB
    S(["library SNP + genotype"]) --> C1{"CPIC allele function?<br/>(pharmacogenes)"}
    C1 -->|yes| R1["GoF / LoF / normal · basis cpic"]
    C1 -->|no| C2{"MaveDB score for<br/>this protein change?"}
    C2 -->|yes| R2["GoF / LoF / normal · measured"]
    C2 -->|no| C3{"UniProt effect<br/>with a direction?"}
    C3 -->|yes| R3["GoF / LoF · curated"]
    C3 -->|no| C4{"carried allele stops<br/>the protein early?"}
    C4 -->|yes| R4["LoF · truncating"]
    C4 -->|no| C5{"UniProt effect<br/>without direction?"}
    C5 -->|yes| R5["altered · curated"]
    C5 -->|no| C6{"SIFT 'deleterious' and<br/>PolyPhen damaging?"}
    C6 -->|yes| R6["LoF, 'likely' · predicted"]
    C6 -->|no| C7{"GTEx eQTL, same sign<br/>across top tissues?"}
    C7 -->|yes| R7["more / less expressed · expression"]
    C7 -->|no| R8["no known effect · none"]
```

Details that matter:

- **Protein effects** count copies of the changed allele, relative to the standard protein: COMT Met is the
  low-activity allele however common it is.
- **Expression effects** are relative to the common genotype: if the common allele lowers expression, carriers of the
  other allele are the more expressed ones.
- **Truncation is allele-specific.** A rare third allele that is a stop codon doesn't make a common missense change
  "truncating" (ADRB2 rs1042714).
- **UniProt text** only counts its function parts: in "low enzyme activity; may increase the tendency to develop
  hypertension" the first part decides.

The library's wording-based call is kept as `library_function` for comparison, and the explorer marks the library
sentence as a note written with an LLM.

## The library audit

```mermaid
flowchart TB
    LIB["snp_traits.json"] --> CLAIM["the wording's claim for the<br/>less common genotype<br/>(more / less active / typical)"]
    LIB --> SC["scores per genotype"]
    EVC["evidence call for the<br/>minor homozygote"] --> CMP
    CLAIM --> CMP{"compare"}
    GW["GWAS Catalog<br/>direct hits"] --> SUP
    LD["Ensembl LD partners<br/>r² ≥ 0.6"] --> SUP["GWAS support"]
    VEPF["European frequency"] --> COMMON{"common genotype<br/>(≥ 25%) scored ≤ 4?"}
    SC --> COMMON
    CMP & SUP & COMMON --> V["verdict"]
    V --> MD["docs/LIBRARY_AUDIT.md"]
    V --> CH["reviewed corrections<br/>docs/LIBRARY_CHANGES.md<br/>+ 'audit' field per entry"]
```

| Verdict | Meaning |
|---|---|
| contradicts | The wording's direction is the opposite of the evidence |
| unsupported | No functional evidence and no genome-wide study, yet scored away from neutral |
| common genotype scored as risk | Most Europeans carry the genotype scored ≤ 4 |
| function claim unsupported | The trait has GWAS support; the activity wording doesn't |
| agrees / no function claim | Nothing to change |

```bash
python -m cluster_analysis.function_evidence    # gather (API, cached)
python -m cluster_analysis.library_audit        # → docs/LIBRARY_AUDIT.md, library_audit.json
```

The audit never edits the library. Corrections are made after review and listed in `docs/LIBRARY_CHANGES.md`; the
library also drives the PDF report, so a change there changes the report.
