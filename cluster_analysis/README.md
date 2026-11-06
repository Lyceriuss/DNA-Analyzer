# Cluster analysis

Groups the genes in the library (`config/snp_traits.json`) into **functional modules**, meaning sets of genes whose proteins work together. It then scores a person's results per module. The aim is to see mechanisms rather than isolated SNPs: where several weakened genes sit in the same pathway, and which weakened genes reach into other systems.

## Two steps

```bash
# 1. Library → modules (public data only; run again when snp_traits.json changes)
python -m cluster_analysis.build_modules            # --resolution 2.0 --min-score 400 --no-gwas

# 2. Person → module report (fully offline)
python -m cluster_analysis.overlay data/input/MyHeritage_raw_dna_data_XY.csv
```

| Output | Contains | In git? |
|---|---|---|
| `cluster_analysis/modules.json` | Modules, enrichment, gene summaries, bridge genes, GWAS traits per rsID | yes (no personal data) |
| `cluster_analysis/cache/` | Raw API responses, so re-runs don't hit the APIs again | no |
| `data/output/cluster_analysis/<name>_clusters.md` / `.json` | One person's module scores | no (personal) |

## Library validation

```bash
python -m cluster_analysis.validate_library   # → cluster_analysis/library_validation.md / .json
```

This checks every rsID in `snp_traits.json` against Ensembl (GRCh38) and the GWAS Catalog:

| Check | Error when | Warning when |
|---|---|---|
| Location | the library gene is not within 250 kb of the variant, or the deep-dive/evidence file names another gene | the gene is nearby but not at the site, or the SNP is in a gene desert |
| Alleles | the genotype letters are impossible for the SNP on either strand | an A/T or C/G SNP, where the strand can't be told and scores may be inverted |
| Genotypes | — | a genotype is missing, so carriers get no result |
| Keys | the key has a suffix (`rs328_TIER2`), so it can never match a DNA file | — |

GWAS mapped genes and top traits are listed alongside for manual review. Run it again after any library edit.

## Privacy rule

Only **public identifiers** (gene symbols, rsIDs) are sent to the APIs, and always for the *whole library*, never for a subset that depends on a person. Genotypes and per-person results never leave the machine: `overlay.py` makes no network calls.

## Data sources

| Source | Used for | Key |
|---|---|---|
| [STRING v12](https://string-db.org/help/api/) | Symbol resolution, protein–protein interaction network, enrichment (GO / KEGG / Reactome / WikiPathways) | none |
| [MyGene.info](https://docs.mygene.info/) | Gene summaries, Reactome pathway membership | none |
| [GWAS Catalog v2](https://www.ebi.ac.uk/gwas/docs/programmatic-access/) | Trait associations per rsID (strongest p-value per trait) | none |

Tested and usable for later work: Ensembl REST (variant location and consequence), UniProt (protein function), Reactome ContentService.

## How the modules are built

1. Library gene names are cleaned (`IL1B (Promoter)` → `IL1B`, `CDKN2A/B` → both genes) and resolved to official symbols via STRING.
2. STRING returns interactions among the library genes only (confidence ≥ 0.4).
3. Louvain community detection (resolution 2.0, fixed seed) splits the network into modules. Hubs that Louvain leaves on their own (IL6, with 100+ partners) are assigned to the module they are most strongly tied to.
4. Each module is enriched against GO/KEGG/Reactome/WikiPathways and labelled with its top GO biological process.
5. **Bridge genes** are genes with strong interaction weight (≥ 1.5) into modules other than their own.

GPX1 and CDKN2B-AS1 (a non-coding RNA) aren't in STRING. ABCC11 and TRPM6 have no partners in the library. These genes are kept as "unlinked": they still get summaries and GWAS data.

## Reading the overlay

- **Risk load**: summed `5 − score` over the person's risk SNPs (score ≤ 4) in the module.
- **Compound link**: two interacting genes that are both reduced, so their effects may stack.
- **Buffered link**: a reduced gene interacting with a strength gene, so it may be partly compensated.
- **Reduced bridge gene**: a reduced gene that reaches into other modules, a candidate for cross-system effects.

## Theme clusters

```bash
python -m cluster_analysis.themes   # → cluster_analysis/themes.json (public data)
```

A theme (cancer, fertility, muscle growth) gathers every library gene with evidence that it bears on that area of health, grouped by the mechanism it acts through. Cancer, for example, covers DNA repair, growth signals, cell death, carcinogen activation and detox, hormones, oxidative stress, inflammation and folate. A gene joins a mechanism when its Gene Ontology processes, Reactome pathways (ContentService, by UniProt accession), UniProt function or disease text, or the GWAS traits of its library SNPs match that mechanism's patterns in `THEMES`. The matching terms are kept as evidence.

Broad mechanisms (growth signals, cell death, oxidative stress, inflammation, energy) also need a direct link to the theme: its name in the UniProt text, the gene summary, GWAS traits or the library entry. Otherwise every antioxidant or receptor gene would count as a cancer gene. Connections are STRING interactions (confidence ≥ 0.4) between theme genes, and pathways are Reactome pathways shared by two or more of them. Add a theme by adding an entry to `THEMES`. `export_dashboard --lifecycles ... --dna ...` also writes `theme_meta`, `theme_genes`, `theme_links` and `theme_pathways` with the person's calls.

## API-built theme graphs (fertility)

```bash
python -m cluster_analysis.theme_graph fertility_female   # XX's file, from the theme config
python -m cluster_analysis.theme_graph fertility_male     # XY's file
python -m cluster_analysis.theme_graph cancer             # XY's file: the life of a cell
```

These themes don't depend on the library: the categories come from the APIs and the DNA file is matched afterwards.

- **Genes:** Gene Ontology mechanism genes (QuickGO, under the mechanism's GO terms), plus Open Targets genes for the theme's diseases and traits. Open Targets genes need an overall or human-genetic score ≥ 0.5, or ≥ 0.8 genetic for level and timing traits such as testosterone, SHBG and age at menarche. Human-experiment and curated GO annotations always count. Annotations inferred from orthologs count when the gene also has a fertility association, or for behaviour, which is mostly studied in mouse. Each mechanism records its strongest evidence class.
- **Mechanisms (fertility):** desire and sexual behaviour (GO reproductive behavior), sex hormone production, reproductive axis signalling, gonads, gametes, the ovarian cycle, fertilization, and pregnancy. GO itself files reproductive behaviour under reproductive process, so desire and fertility connect through the ontology.
- **Links:** STRING interactions. Shared Reactome pathways come offline from `Ensembl2Reactome.txt`, with theme-specific pathways listed first.
- **Cross-reference (offline):** every SNP of the file within 5 kb of a theme gene is checked against:
  - ClinVar. Pathogenic variants are counted and listed if carried; other entries are kept only when the condition is on-theme.
  - The GWAS Catalog, for the theme's traits and their ontology descendants, keeping the strongest association per trait with its direction and effect size.
  - The library.

  Only theme names, disease IDs and gene symbols go to the APIs.
- **Imputed calls:** when `src/impute.py` has run for the theme's person, the cross-reference reads the imputed file instead of the raw one (`--measured-only` keeps the raw file). Findings use measured, high and medium calls, and each finding records its confidence. A pathogenic variant counts as carried only when measured or imputed at high confidence. Weaker carrier calls are listed as possible, and rare variants imputation can't rule out are counted as not excluded. ClinVar alleles are compared on the forward strand without flipping, because one position often has a benign and a pathogenic change (APC rs2229992: T>C benign, T>G pathogenic). `export_dashboard.py` picks up the imputed file the same way.

Themes can be sex-specific and name their own person. `fertility_female` uses the XX file and places every gene on an organ through its mechanisms (`organ`) and strongly linked conditions (`disease_organs`): brain, hypothalamus–pituitary, ovaries, fallopian tubes, uterus, and endometrium/placenta. The explorer draws these as a body map, and selecting an organ narrows the page to its genes. `fertility_male` uses XY's file (XY) with brain, hypothalamus–pituitary, testes, epididymis and vas deferens, prostate and seminal vesicles, and penis. Together the two fertility themes replace the mixed library theme. Each mechanism has a written explanation (`EXPLAIN`) for the explorer's in-depth view. Erection, accessory-gland and behaviour biology is mostly known from mouse, so those mechanisms accept ortholog-based GO evidence.

`cancer` (XY's file) uses the same mechanism → place link, but its places are the stages of a cell's life instead of organs (`"view": "cell"`): living and resting, copying and dividing, checkpoints, toxins and damage, ageing, death and clearance, and escape. A gene on a stage also needs an Open Targets cancer score ≥ 0.3 (≥ 0.1 for toxin clearance and oxidative stress, whose evidence is mostly older candidate-gene studies), and genes join on a cancer alone only with human genetic evidence ≥ 0.5, since somatic tumour evidence says nothing about a DNA file. It replaces the library-built cancer theme.

`theme_graph_<theme>.json` is public data. `data/output/cluster_analysis/theme_<name>_<theme>.json` holds the person's cross-reference and stays out of git. `export_dashboard` uses an API theme in place of the library theme with the same id. It draws the notable genes: those with a library call, a ClinVar entry, a carried finding in a mechanism gene, or an Open Targets score ≥ 0.8.

## Gene function calls (GoF / LoF)

The library's genotype texts were written with an LLM, so the calls the explorer shows come from evidence about the
variant, not from those texts. `evidence_call.py` reads `function_evidence.json` and decides, strongest evidence first:

| Basis | Evidence | Call |
|---|---|---|
| `cpic` | CPIC allele function (CYP2C19*2 no function, NAT2*6 slow …) | GoF / LoF / normal |
| `measured` | MaveDB scan of the protein change against wild type (below 80% less active, above 125% more) | GoF / LoF / normal |
| `curated` | UniProt's curated effect, read only from the parts about function ("low enzyme activity", "55% of wild type") | GoF / LoF |
| `truncating` | the allele people carry stops the protein early (per allele: a rare stop at the same position doesn't count) | LoF |
| `curated` | a curated effect without a direction | altered |
| `predicted` | SIFT (not low confidence) and PolyPhen both call it damaging | LoF, worded "likely" |
| `expression` | GTEx: the allele raises or lowers the gene's expression, same sign in its strongest tissues | worded "more / less expressed" |
| `none` | nothing | unknown: "no known effect on the gene" |

Protein effects count the person's copies of the changed allele (COMT Met is the low-activity allele however common);
expression effects are relative to the genotype most Europeans carry. Each call keeps `basis` and `evidence` (the
sentence shown in the explorer), and `library_function` keeps the wording-based call below for comparison.

`library_audit.py` checks every library SNP against the same evidence and the GWAS Catalog (counting lead SNPs inherited
with it, r² ≥ 0.6 in Europeans, via Ensembl) and writes `docs/LIBRARY_AUDIT.md` for review: contradictions, claims with
no support, and common genotypes scored as a risk. It changes nothing in the library. Corrections made after review are
listed in `docs/LIBRARY_CHANGES.md`, and each corrected entry in `snp_traits.json` carries an `audit` field with the reason.

```bash
python -m cluster_analysis.library_audit
```

`gene_trace.function_call` (the earlier call, now `library_function`) reports what the library says about the person's own genotype:

| Call | When the library text for the genotype… |
|---|---|
| `LoF` / `GoF` | …names an activity or function going down (reduced, slower, lower clearance) or up (increased, enhanced, higher transport). The first clause that names an activity decides, and within a clause "reduced" wins. |
| `normal` (typical function) | …says normal or typical, or says balanced, intermediate, moderate, efficient or optimal outside risk or trait wording. Two copies of the common allele also count as normal unless the text says otherwise. |
| `LoF` (truncating) | …is silent, and the less common allele truncates the protein (ACTN3 R577X). |
| `altered` | …speaks only of a risk or trait (higher BP, allergy, taster, eye colour), with no function direction. |

"Efficient", "optimal" and "strong" mean typical function, not a gain. The common European allele (Ensembl VEP frequencies) still sets `dose`, the copies of the less common allele, so a heterozygote the library calls "Balanced" is typical function with one copy. Before this rule the call compared alleles with each other. That marked such heterozygotes LoF ×1 and flipped calls where the common allele is the weaker one (BCHE, MTRR, BRCA1, TCF7L2).

```bash
# Lifecycle and gene-function datasets for the explorer, with fresh calls but no new API walks
python -m cluster_analysis.export_dashboard out/bundle.json --lifecycles data/output/cluster_analysis/lifecycles_XY.json \
    --dna data/input/MyHeritage_raw_dna_data_XY.csv
```

Papers and quoted effect sizes come from `literature.py`, run once for the whole library:

```bash
python -m cluster_analysis.literature   # → cluster_analysis/literature.json (public data)
```

For each SNP it lists UniProt's experimental references, then the most cited Europe PMC papers whose title names the gene or variant. It also quotes abstract sentences that put a number on the variant's own activity, expression or level ("53% reduced urate transport rates compared to wild-type"). Older names such as C677T or ALDH2*2 are learned from abstracts that write them next to the rsID. Sentences with association statistics (odds, CI, risk), and sentences that name only other variants, are dropped. 20 of 229 SNPs have such a quote, since most abstracts give no number.

`gene_function.json` adds the function evidence per gene (MaveDB scores, GTEx direction and XY's copies of the effect allele, UniProt, SIFT/PolyPhen, ClinPGx for XY's genotype). It holds personal genotypes, so keep it out of git.

## Caveats

- The network is **gene-level**. A SNP can affect a different gene, or a regulatory region, rather than the protein of the gene it is filed under. The HERC2 SNP, for example, controls OCA2 pigmentation, so its links into DNA repair are not meaningful. The GWAS traits shown next to each SNP are the quickest way to spot this.
- Module labels are generated automatically. "Response to alkaloid" is really the neurotransmitter module. Curated names would help.
