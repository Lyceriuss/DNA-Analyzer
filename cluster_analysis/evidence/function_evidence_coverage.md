# Function evidence coverage

229 library SNPs checked against MaveDB, ClinPGx, UniProt, GTEx and SIFT/PolyPhen.

| Source | SNPs with data | Share | What it tells us |
|---|---|---|---|
| MaveDB | 3 | 1% | Measured protein function for this exact change |
| ClinPGx | 109 | 48% | Genotype → drug or metabolism effect, with evidence level |
| UniProt | 111 | 48% | Protein change and curated effect or disease |
| GTEx | 184 | 80% | Expression up or down, per tissue (130 for the library gene itself) |
| SIFT/PolyPhen | 11 | 5% | Predicted damage only |

## Best evidence about function, per SNP

Drug associations (ClinPGx) are not counted here: they say a genotype changes a drug's effect, not how much the gene works.

| Tier | SNPs |
|---|---|
| 1 measured protein function (MaveDB) | 3 |
| 2 curated functional effect (UniProt) | 41 |
| 3 expression effect on the gene (GTEx) | 107 |
| 4 predicted damage only (SIFT/PolyPhen) | 2 |
| 5 no functional evidence | 76 |

83 SNPs without curated or measured function do have a ClinPGx drug association.

## Examples of measured evidence

- **rs1042522 TP53** p.Pro72Arg: 85.90 (Scores from arrayed yeast-based assay of TP53 BAX promoter); 64.10 (Scores from arrayed yeast-based assay of TP53 GADD45 promote); 101.30 (Arrayed yeast-based assay of TP53 h1433snWT promoter); 75.10 (Scores from arrayed yeast-based assay of TP53 MDM2 promoter); 127.30 (Scores from arrayed yeast-based assay of TP53 Noxa promoter); 111.00 (Scores from arrayed yeast-based assay of TP53 p21WAF1 promot)
- **rs1042602 TYR** p.Ser192Tyr: 1.16 (TYR pigmentation-rescue function scores (two biological repl); 0.94 (TYR VAMP-seq abundance scores (two biological replicates))
- **rs1801133 MTHFR** p.Ala222Val: 0.59 (MTHFR at 25ug/ml folate in WT background); 0.38 (MTHFR at 12ug/ml folate in WT background); 0.78 (MTHFR at 200ug/ml folate in WT background); 0.70 (MTHFR at 100ug/ml folate in WT background)

## Examples of curated functional effects

- **rs1048943 CYP1A1** p.Ile462Val: allele CYP1A1*2B and allele CYP1A1*2C; displays 5.7- and 12-fold increase in catalytic efficiency in the formation of 2-hydroxylated estrogens, 17beta-estradiol and estrone respectively
- **rs1049434 SLC16A1** p.Asp490Glu: Ketoacidosis due to monocarboxylate transporter-1 deficiency; Metabolic myopathy due to lactate transporter defect
- **rs1051740 EPHX1** p.Tyr113His: allele EPHX1*3; benign; frequent in the human population; 55% of wild type enzyme activity
- **rs1056836 CYP1B1** p.Leu432Val: allele CYP1B1*3, allele CYP1B1*5, allele CYP1B1*6 and allele CYP1B1*7; 1.6-fold increase in 17beta-estradiol 4-hydroxylation activity but no change in 17beta-estradiol 2-hydroxylation activity; 2-fold reduction in testosterone 6beta-hydroxylation activity and 3-fold reduction in testosterone affinity; 6-fold and 4-fold increase in progesterone 6beta- and 16alpha-hydroxylation activity, respectively and 7-fold reduction in progesterone affinity
- **rs1110400 MC1R** p.Ile155Thr: Increased analgesia from kappa-opioid receptor agonist, female-specific; probable risk factor for developing melanoma; reduced expression at the cell surface
- **rs11209026 IL23R** p.Arg381Gln: Inflammatory bowel disease 17, protection against; Psoriasis, protection against; protective factor against IBD17; protective factor against psoriasis
- **rs1260326 GCKR** p.Leu446Pro: protective factor against diabetes type 2; correlated with high triglyceride levels and low fasting plasma glucose levels; the mutant protein is less efficiently regulated by physiological concentrations of fructose-6 phosphate
- **rs13266634 SLC30A8** p.Arg325Trp: decreased transport reaction kinetics; decreased affinity for zinc ions; decreased zinc ion import into organelle; no effect on protein abundance
- **rs16969968 CHRNA5** p.Asp398Asn: risk factor for lung cancer; decreased calcium permeability and fast desensitization in (CHRNA4:CHRNB2)2:CHRNA5 but not in (CHRNA3:CHRNB4)2:CHRNA5 or (CHRNA3:CHRNB24)2:CHRNA5 AChR; no effect on activation by nicotine
- **rs17822931 ABCC11** p.Gly180Arg: found in individuals with dry earwax and no axillary odor; loss of ATP-dependent cGMP transport activity; loss of DHEAS transport and largely reduced estrone 3-sulfate transport; strong decrease in localization at the plasma membrane; decreased protein expression levels, due to proteasomal degradation; decreased N-glycosylation
