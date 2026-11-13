# Known issues

Open issues for the Gene Cluster Explorer and its pipeline. The PDF report and its issues were removed on 2026-11-13
(see git history).

## P0: privacy

- **Personal genotypes are in the public git history.** `genomic_audit_report.csv`, `final_genomic_alignment_check.csv`
  and `final_hardware_alignment.csv` were committed in `8b3ce28`, `129ded7` and `7c86dfb` (and later deleted). They
  contain real `RSID → genotype` rows from input files. The GitHub repo is public, and deleting a file doesn't remove it
  from history. Rewrite history (`git filter-repo`) or make the repo private.

## P0: the library (`cluster_analysis/library/snp_traits.json`)

- **23 A/T or C/G SNPs** still need their strand checked; TP53 proved these can be silently inverted. Use Ensembl's
  per-allele amino acids, then add each one to `STRAND_VERIFIED` in `validate_library.py`.
- **Silent misses.** Library SNPs missing from the file are dropped without a trace; report the count.

## P1: the explorer

- Tabs throw on a profile whose pipeline hasn't produced every output (nutrition, lab tests, overlay): they should show
  that the data is missing instead.
- The Nutrition tab overflows a phone-width screen.

## P1: nutrition

- The expected shift in blood units (Σ β(copies − 2p), ≈ −0.25 SD) isn't shown next to the percentile.
- No note on cards where a variant moves the test rather than the body (TCN1 and total B12).
- An expression effect is the most significant GTEx tissue, which can be far from where the step runs (testis for a
  liver enzyme). Prefer the tissues the Protein Atlas names for the gene.
- Reactome and UniProt text is English on the Swedish page (source text). UniProt's function text can name roles
  unrelated to the nutrient (CD320 in B-cell responses).
- Calcium has no Reactome steps (Reactome has no dietary calcium uptake). Iodine's steps follow Reactome's order,
  which puts iodide uptake 8th of 11.
- No tolerances yet (lactase persistence, coeliac HLA-DQ2.5, alcohol and caffeine metabolism), and no fertility link
  (folate, choline, iron, DHA for XX).

## P1: medicines

- HLA alleles: only HLA-B\*57:01 is tagged. HLA-B\*58:01, HLA-B\*15:02 and HLA-A\*31:01 have CPIC guidelines but no tag
  yet. G6PD, CACNA1S and MT-RNR1 are read only through single variants, or not at all.

## P2: engineering

- Nothing in `requirements.txt` is pinned.
- Beagle's output depends on its thread count; fix it for reproducible imputation.
- Test coverage is thin (`tests/`).
