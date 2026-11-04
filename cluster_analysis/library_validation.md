# Library validation

229 rsIDs checked against Ensembl (GRCh38) and the GWAS Catalog: **0 errors**, 38 warnings, 191 ok.

Regenerate with `python -m cluster_analysis.validate_library`.

## Warnings (38)

Strand-ambiguous SNPs, missing genotypes, or variants that sit near (not in) the gene.

| rsID | Library gene | Trait | Site (GRCh38) | Genes at site | GWAS top traits | Issues |
|---|---|---|---|---|---|---|
| rs1042714 | ADRB2 | Beta-2 receptor downregulation (Gln27Glu) | chr5:148826910 (stop_gained) | ADRB2 | hematological measurement | A/T or C/G SNP (G/A/C/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs10427255 | ZEB2 | Photic Sneeze Reflex (Sun Sneezing) | chr2:145367955 (intergenic_variant) | – | smoking initiation; social inhibition characteristic; substance abuse | gene desert: no protein-coding gene within 250 kb; ZEB2 is presumably the GWAS locus name, confirm it |
| rs1052133 | OGG1 | Oxidative DNA Damage Repair | chr3:9757089 (missense_variant) | CAMK1, OGG1 | – | A/T or C/G SNP (C/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1056836 | CYP1B1 | Hormone & toxin hydroxylation | chr2:38071060 (missense_variant) | RMDN2, CYP1B1, RMDN2-AS1, CYP1B1-AS1 | – | A/T or C/G SNP (G/A/C): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs10830963 | MTNR1B | Fasting glucose tendency | chr11:92975544 (intron_variant) | MTNR1B | gestational diabetes; glucose measurement; blood glucose amount | A/T or C/G SNP (C/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs11645428 | BCMO1 | Vitamin A conversion (beta-carotene → retinol) | chr16:81225291 (upstream_gene_variant) | PKD1L2 | X-23749 measurement | BCMO1 is 13 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs12130333 | ANGPTL3 | Triglyceride Clearance & Lipid Partitioning | chr1:62726106 (intron_variant) | DOCK7-DT | triglyceride measurement; total cholesterol measurement; low density lipoprotein cholesterol measurement | ANGPTL3 is 118 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs1333049 | CDKN2A/B | Coronary Artery Disease Risk (9p21 locus) | chr9:22125504 (intron_variant) | CDKN2B-AS1 | coronary artery disorder; atherosclerosis; large artery stroke | CDKN2A/B is 116 kb away, not at the site (regulatory/LD association; check the mechanism text)<br>A/T or C/G SNP (G/A/C): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs174537 | FADS1 | Omega-3 & omega-6 fatty acid conversion | chr11:61785208 (non_coding_transcript_exon_variant) | TMEM258, MYRF | amount of Phosphatidylcholine (18:0_20:4) in blood serum; polyunsaturated fatty acids to total fatty acids percentage; triglycerides to total lipids in very small VLDL percentage | FADS1 is 14 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs17653216 | MGAM | Maltase-glucoamylase activity | chr2:56908106 (intergenic_variant) | – | – | gene desert: no protein-coding gene within 250 kb; MGAM is presumably the GWAS locus name, confirm it |
| rs17782313 | MC4R | Weight set point & appetite | chr18:60183864 (intergenic_variant) | – | diet measurement; metabolic syndrome; body mass index | MC4R is 187 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs1799945 | HFE | Iron absorption regulation | chr6:26090951 (missense_variant) | HFE, H2BC4 | mean corpuscular hemoglobin concentration; hemoglobin measurement; reticulocyte amount | A/T or C/G SNP (C/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1800795 | IL6 (Promoter) | Inflammatory reactivity (CRP levels) | chr7:22727026 (5_prime_UTR_variant) | IL6, IL6-AS1, STEAP1B | pulse pressure measurement; systolic blood pressure; serum creatinine amount | A/T or C/G SNP (C/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1801198 | TCN2 | B12 transport in blood | chr22:30615623 (missense_variant) | TCN2 | protein measurement | A/T or C/G SNP (G/A/C): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1801253 | ADRB1 | Exercise Heart Rate Response | chr10:114045297 (missense_variant) | ADRB1 | triglycerides to total lipids in medium HDL percentage; cholesterol to total lipids in medium HDL percentage; triglycerides to total lipids in small HDL percentage | A/T or C/G SNP (G/A/C): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1801272 | CYP2A6 | Nicotine Metabolism Speed | chr19:40848628 (missense_variant) | CYP2A6, EGLN2 | c-reactive protein measurement; amount of carboxypeptidase M (human) in blood; smoking behavior | A/T or C/G SNP (A/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1801282 | PPARG | Insulin sensitivity & fat storage pattern | chr3:12351626 (missense_variant) | PPARG | sex hormone-binding globulin measurement; serum albumin amount; type 2 diabetes mellitus | A/T or C/G SNP (C/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs2010963 | VEGFA (Secretion) | Blood vessel growth (angiogenesis) | chr6:43770613 (5_prime_UTR_variant) | VEGFA | – | A/T or C/G SNP (C/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs2395185 | HLA-DQA1 | Celiac disease susceptibility (HLA-DQ2.5) | chr6:32465390 (intron_variant) | HLA-DRB9 | Hodgkins lymphoma; ulcerative colitis; blood immunoglobulin amount | HLA-DQA1 is 162 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs2943641 | IRS1 | Insulin Resistance & Type 2 Diabetes | chr2:226229029 (intergenic_variant) | – | sex hormone-binding globulin measurement; high density lipoprotein cholesterol measurement; cholesteryl esters in large HDL measurement | gene desert: no protein-coding gene within 250 kb; IRS1 is presumably the GWAS locus name, confirm it |
| rs324981 | NPSR1 | Natural Short Sleeper | chr7:34778501 (missense_variant) | NPSR1, NPSR1-AS1 | – | A/T or C/G SNP (A/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs328 | LPL | Post-meal triglyceride clearance | chr8:19962213 (stop_gained) | LPL | triglycerides in chylomicrons and extremely large VLDL measurement; phospholipids in chylomicrons and extremely large VLDL measurement; concentration of chylomicrons and extremely large VLDL particles measurement | A/T or C/G SNP (C/A/G): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs3813867 | CYP2E1 | Toxin & Solvent Metabolism | chr10:133526101 (intron_variant) | CYP2E1, SCART1 | – | A/T or C/G SNP (G/A/C): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs41423247 | NR3C1 | Cortisol Receptor Sensitivity (BclI) | chr5:143399010 (intron_variant) | NR3C1 | – | A/T or C/G SNP (G/C): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs4253778 | PPARA | Fat metabolism in endurance | chr22:46234737 (intron_variant) | PPARA | – | A/T or C/G SNP (G/C/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs4654748 | ALPL | Vitamin B6 (PLP) blood levels | chr1:21459575 (intron_variant) | NBPF3, PFN1P10 | alkaline phosphatase measurement; glycerol-3-phosphate measurement; vitamin B6 measurement | ALPL is 49 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs4988235 | LCT | Lactase persistence (lactose tolerance) | chr2:135851076 (intron_variant) | MCM6 | lactase-phlorizin hydrolase measurement; blood protein amount; body weight | LCT is 13 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs558972 | GCK | Fasting glucose baseline | chr13:74950693 (intergenic_variant) | – | – | gene desert: no protein-coding gene within 250 kb; GCK is presumably the GWAS locus name, confirm it |
| rs559870 | MMP3 | Collagen remodeling efficiency | chr6:95204044 (intron_variant) | – | – | gene desert: no protein-coding gene within 250 kb; MMP3 is presumably the GWAS locus name, confirm it |
| rs6259 | SHBG | Sex hormone binding globulin level | chr17:7633209 (missense_variant) | SHBG | brain attribute; neuroimaging measurement | A/T or C/G SNP (G/A/C): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs6295 | HTR1A | 5-HT1A autoreceptor sensitivity | chr5:63962738 (intron_variant) | HTR1A | – | A/T or C/G SNP (C/A/G): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs713598 | TAS2R38 | Bitter taste perception | chr7:141973545 (missense_variant) | MGAM, TAS2R38 | sensory perception of bitter taste; taste liking measurement; alcohol consumption characteristic | A/T or C/G SNP (C/A/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs72921001 | OR6A2 | Cilantro Taste (Soapy vs Herb) | chr11:6868417 (intron_variant) | OR10A2 | – | OR6A2 is 68 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs738409 | PNPLA3 | Liver fat accumulation (NAFLD risk) | chr22:43928847 (missense_variant) | PNPLA3 | Abnormality of the liver; liver disorder; metabolic dysfunction-associated steatotic liver disease | A/T or C/G SNP (C/A/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs7454108 | HLA-DQ8 | Celiac Disease Risk (HLA-DQ8) | chr6:32713706 (upstream_gene_variant) | – | anti-neutrophil antibody associated vasculitis; type 2 diabetes mellitus; pemphigus vulgaris | HLA-DQ8 is 45 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs7754840 | CDKAL1 | Insulin release strength | chr6:20661019 (intron_variant) | CDKAL1 | type 2 diabetes mellitus; gestational diabetes; systolic blood pressure | A/T or C/G SNP (G/A/C/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs8007267 | GCH1 | BH4 Synthesis (Natural Pain Relief) | chr14:54912273 (intron_variant) | – | – | GCH1 is 8 kb away, not at the site (regulatory/LD association; check the mechanism text) |
| rs9939609 | FTO | Appetite regulation | chr16:53786615 (intron_variant) | FTO | body mass index; type 2 diabetes mellitus; diastolic blood pressure | A/T or C/G SNP (T/A): confirm the scores are written on the forward strand, otherwise results are silently inverted |

## Strand summary

| Orientation of library genotypes | rsIDs |
|---|---|
| forward | 195 |
| ambiguous | 23 |
| forward (verified) | 6 |
| reverse | 5 |
