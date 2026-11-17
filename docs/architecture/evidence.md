# Gene function calls and the library audit

The library (`cluster_analysis/library/snp_traits.json`, 247 SNPs) was written with an LLM. Its sentences say what a genotype means for a
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

## From the call to positive or negative

The report and the explorer read each genotype as positive or negative for the person in two steps: the evidence call
above says what the genotype does to the gene, and the library entry's `polarity` says whether that is good or bad.
The call is evidence; the polarity is a best-effort reading of the trait.

```mermaid
flowchart TB
    EC["evidence_call()<br/>per library genotype"] --> FN["snp_traits.json → function<br/>GoF / LoF / normal / altered / unknown"]
    OLD["first drafts, 2026-11-07<br/>(library wording, direction of the old ratings)"] --> POL["polarity<br/>{LoF: negative}"]
    HAND["set by hand<br/>(polarity_source: reviewed)"] --> POL
    FN -->|"effect without a polarity"| NONE["reads unclear<br/>(listed by genotype_effects.py)"]
    FN & POL --> OUT["outcome: positive / negative /<br/>neutral / unclear / typical / unknown"]
```

- The first drafts compared the old rating of the genotype carrying the most copies of the effect with the genotype
  carrying none: a gap of 2 or more decided the direction, a smaller one made it neutral. Only the direction was used,
  and the ratings were then removed. New polarities are set by hand.
- Where the library's wording names a function the evidence reverses (it says more active, the protein evidence says
  less), the draft kept the library's view of which function is good and flipped the sign. Where the evidence is tissue
  expression only, neither side was strong enough, and the effect got no polarity: it reads *unclear*.
- Protein evidence is put on the allele that codes the changed residue. GRCh38 sometimes carries the rarer form
  (PTPN22 rs2476601 holds Trp620; UniProt's standard protein has Arg620), so the allele is matched by amino acid, not
  taken to be the genome's alternative allele.
- A lost start codon is not counted as cutting the protein short: translation can restart at a later ATG (VDR FokI
  gives a shorter, more active receptor).

```bash
python -m cluster_analysis.library.genotype_effects           # calls that would change, and effects without a polarity
python -m cluster_analysis.library.genotype_effects --write   # write function / function_basis into the library
```

## Per-gene calls from the person's own variants

The library covers 247 SNPs, so most theme genes (about 3,000 across cancer and fertility) had no call. The library is
being phased out: `gene_calls.py` calls every theme gene from the person's own variants with the same evidence ladder,
and the explorer uses that call wherever it finds an effect or the library has none (CPIC pharmacogene calls stay).

```mermaid
flowchart TB
    G["theme genes<br/>(each theme's person: XY, XX)"] --> UPV["UniProt variation<br/>every missense / stop change<br/>with its dbSNP id and DNA letter"]
    G --> GT["GTEx v8 independent eQTLs<br/>strongest (rank 1, lowest p),<br/>leading in 2+ tissues"]
    DNA["the person's calls<br/>measured or high-confidence imputed"] --> M["match by rsid and DNA letter"]
    UPV --> M
    GT --> M
    M --> P{"carries a protein change<br/>with evidence?"}
    P -->|"MaveDB / UniProt curated /<br/>stop / SIFT+PolyPhen"| PC["GoF / LoF (protein)"]
    P -->|no| E{"eQTL genotype"}
    E -->|"carries the allele that differs<br/>from the common European one"| EC2["more / less expressed"]
    E -->|"usual genotype"| N["typical function"]
    E -->|"not read, but protein<br/>variants were"| N2["typical: no carried change<br/>with known effect"]
```

- Matching is by DNA letter: one rsid can make several protein changes (rs1801133 G>A is A222V, G>C another), and
  only the one the person's allele codes counts.
- A carried change without evidence is named in the gene's text ("also carries D301Y, no known effect") and doesn't
  make a call by itself.
- Writes `data/output/cluster_analysis/gene_calls_<person>.json`; `export_dashboard.py` reads it per theme person.
- `systems.py` groups the calls into body systems for the Biomarkers tab: Reactome's top-level pathways (Disease left
  out, Metabolism split into its children, those with fewer than 15 read genes as "Other metabolism"), and STRING
  high-confidence pairs (≥ 0.7) between changed genes, inside a system and across systems. It shows direction (more or
  less active), not good or bad: the sources don't say which. Writes `profiles/<id>/sys_systems`, `sys_genes`,
  `sys_links`, `sys_bridges`.
- Limits: UniProt lists the changes it has curated or imported, not every missense variant (SLC23A1 V264M is missing),
  and an eQTL from GTEx's mostly European donors is one variant per gene.

## The library audit

```mermaid
flowchart TB
    LIB["snp_traits.json"] --> CLAIM["the wording's claim for the<br/>less common genotype<br/>(more / less active / typical)"]
    LIB --> SC["function + polarity<br/>per genotype"]
    EVC["evidence call for the<br/>minor homozygote"] --> CMP
    CLAIM --> CMP{"compare"}
    GW["GWAS Catalog<br/>direct hits"] --> SUP
    LD["Ensembl LD partners<br/>r² ≥ 0.6"] --> SUP["GWAS support"]
    VEPF["European frequency"] --> COMMON{"common genotype<br/>(≥ 25%) reads negative?"}
    SC --> COMMON
    CMP & SUP & COMMON --> V["verdict"]
    V --> MD["docs/LIBRARY_AUDIT.md"]
    V --> CH["reviewed corrections<br/>docs/LIBRARY_CHANGES.md<br/>+ 'audit' field per entry"]
```

| Verdict | Meaning |
|---|---|
| contradicts | The wording's direction is the opposite of the evidence |
| unsupported | No functional evidence and no genome-wide study, yet the wording claims an effect |
| common genotype reads negative | Most Europeans carry a genotype that reads negative |
| no polarity | The evidence calls a change but nothing says whether it is good or bad |
| function claim unsupported | The trait has GWAS support; the activity wording doesn't |
| agrees / no function claim | Nothing to change |

```bash
python -m cluster_analysis.evidence.function_evidence    # gather (API, cached)
python -m cluster_analysis.library.library_audit        # → docs/LIBRARY_AUDIT.md, library_audit.json
```

The audit never edits the library. Corrections are made after review and listed in `docs/LIBRARY_CHANGES.md`; the
library no longer draws a tab; the Body systems view is built from the gene calls (below).
