# Cluster analysis

Groups the genes in the library (`config/snp_traits.json`) into **functional modules**, meaning sets of genes whose proteins work together. It then scores a person's results per module. The aim is to see mechanisms rather than isolated SNPs: where several weakened genes sit in the same pathway, and which weakened genes reach into other systems.

## Two steps

```bash
# 1. Library → modules (public data only; run again when snp_traits.json changes)
python -m cluster_analysis.build_modules            # --resolution 2.0 --min-score 400 --no-gwas

# 2. Person → module report (fully offline)
python -m cluster_analysis.overlay data/input/MyHeritage_raw_dna_data_HP.csv
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

## Gene function calls (GoF / LoF)

`gene_trace.function_call` compares a genotype with the **most common European allele** at the SNP (Ensembl VEP frequencies), not with the reference genome or the healthiest genotype. The reference genome carries the rare allele at some SNPs, such as CYP3A4 rs2740574.

| Call | Meaning |
|---|---|
| `normal` | Two copies of the common allele: the SNP leaves the enzyme in its usual form |
| `LoF` / `GoF` | One or two copies (`dose`) of the less common allele, which the library reads as less / more activity |
| `altered` | Carries the less common allele, but the library text gives no direction |
| `unknown` | The genotype doesn't match the SNP's alleles on either strand |

When the library text gives no direction and the less common allele truncates the protein (stop gained, frameshift, splice site), the call is LoF. ACTN3 R577X is an example.

The direction comes from the library text for the less common homozygote against the common homozygote. Clauses that name an activity decide first, so "Reduced GPX4 activity; higher oxidative stress risk" reads as less. Where both alleles are near 50% (COMT, MTRR), "common" is close to arbitrary, and the explorer says so.

```bash
# Lifecycle and gene-function datasets for the explorer, with fresh calls but no new API walks
python -m cluster_analysis.export_dashboard out/bundle.json --lifecycles data/output/cluster_analysis/lifecycles_HP.json \
    --dna data/input/MyHeritage_raw_dna_data_HP.csv
```

Papers and quoted effect sizes come from `literature.py`, run once for the whole library:

```bash
python -m cluster_analysis.literature   # → cluster_analysis/literature.json (public data)
```

For each SNP it lists UniProt's experimental references, then the most cited Europe PMC papers whose title names the gene or variant. It also quotes abstract sentences that put a number on the variant's own activity, expression or level ("53% reduced urate transport rates compared to wild-type"). Older names such as C677T or ALDH2*2 are learned from abstracts that write them next to the rsID. Sentences with association statistics (odds, CI, risk), and sentences that name only other variants, are dropped. 20 of 229 SNPs have such a quote, since most abstracts give no number.

`gene_function.json` adds the function evidence per gene (MaveDB scores, GTEx direction and HP's copies of the effect allele, UniProt, SIFT/PolyPhen, ClinPGx for HP's genotype). It holds personal genotypes, so keep it out of git.

## Caveats

- The network is **gene-level**. A SNP can affect a different gene, or a regulatory region, rather than the protein of the gene it is filed under. The HERC2 SNP, for example, controls OCA2 pigmentation, so its links into DNA repair are not meaningful. The GWAS traits shown next to each SNP are the quickest way to spot this.
- Module labels are generated automatically. "Response to alkaloid" is really the neurotransmitter module. Curated names would help.
