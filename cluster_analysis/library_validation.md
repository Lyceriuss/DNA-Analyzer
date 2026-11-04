# Library validation

282 rsIDs checked against Ensembl (GRCh38) and the GWAS Catalog: **73 errors**, 37 warnings, 172 ok.

Regenerate with `python -m cluster_analysis.validate_library`.

## Errors (73)

Wrong gene, impossible alleles, or unknown rsID. Results for these SNPs are unreliable.

| rsID | Library gene | Trait | Site (GRCh38) | Genes at site | GWAS top traits | Issues |
|---|---|---|---|---|---|---|
| rs1010151 | GLO1 | Advanced Glycation End product (AGE) Risk | chr7:115970339 (intron_variant) | TFEC | – | GLO1 is not within 250 kb; variant is at TFEC<br>genotype letters ['A', 'C'] are impossible for alleles G/A |
| rs1042522 | TP53 | p53 damage response efficiency | chr17:7676154 (missense_variant) | TP53 | sex hormone-binding globulin measurement; testosterone measurement; HbA1c measurement | deep_dive names POMC, but the site is TP53<br>evidence names POMC, but the site is TP53<br>A/T or C/G SNP (G/A/C/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1042713_dupfix | ADRB2 | Adrenaline-driven fat release | chr5:148826877 (missense_variant) | ADRB2 | creatine kinase measurement | key has a suffix, so it can never match a DNA file; duplicates rs1042713 (ADRB2) |
| rs1047303 | HSD17B3 | Testosterone synthesis (androstenedione → testosterone) | chr1:119514623 (missense_variant) | HSD3B1 | – | HSD17B3 is not within 250 kb; variant is at HSD3B1 |
| rs1049434 | COL12A1 | Soft-tissue injury susceptibility | chr1:112913924 (missense_variant) | SLC16A1, SLC16A1-AS1 | – | COL12A1 is not within 250 kb; variant is at SLC16A1, SLC16A1-AS1<br>A/T or C/G SNP (A/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1049434_TIER2 | CKM | Phosphocreatine recycling speed | chr1:112913924 (missense_variant) | SLC16A1, SLC16A1-AS1 | – | key has a suffix, so it can never match a DNA file; duplicates rs1049434 (COL12A1)<br>CKM is not within 250 kb; variant is at SLC16A1, SLC16A1-AS1 |
| rs10993994 | MSRA | Optimism & Resilience | chr10:46046326 (5_prime_UTR_variant) | MSMB | beta-microseminoprotein measurement; protein measurement; prostate carcinoma | MSRA is not within 250 kb; variant is at MSMB |
| rs1110400 | SOD1 | UV-induced oxidative damage resilience | chr16:89919722 (missense_variant) | TUBB3, MC1R | hair color; Abnormal skin pigmentation | SOD1 is not within 250 kb; variant is at TUBB3, MC1R |
| rs11185098 | DAO | Histamine degradation (DAO enzyme) | chr1:103778727 (intergenic_variant) | – | – | DAO is not within 250 kb; variant is at AMY1C, AMY1B, AMY1A |
| rs11191548 | DRD1 | Dopamine receptor D1 activity | chr10:103086421 (3_prime_UTR_variant) | NT5C2, CNNM2 | systolic blood pressure; smoking status measurement; essential hypertension | DRD1 is not within 250 kb; variant is at NT5C2, CNNM2 |
| rs11191548_TIER2 | DRD1 | Renal sodium handling via dopamine system | chr10:103086421 (3_prime_UTR_variant) | NT5C2, CNNM2 | systolic blood pressure; smoking status measurement; essential hypertension | key has a suffix, so it can never match a DNA file; duplicates rs11191548 (DRD1)<br>DRD1 is not within 250 kb; variant is at NT5C2, CNNM2 |
| rs1254337 | GLUT9 (SLC2A9) | Uric acid transport (metabolic inflammation) | chr14:60453807 (intron_variant) | C14orf39 | age at menarche | GLUT9 (SLC2A9) is not within 250 kb; variant is at C14orf39<br>A/T or C/G SNP (A/G/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1256049 | ESR1 | Estrogen receptor signaling modulation | chr14:64257333 (synonymous_variant) | ESR2 | – | ESR1 is not within 250 kb; variant is at ESR2 |
| rs12594956 | PPARGC1A | Mitochondrial biogenesis | chr15:50329637 (intron_variant) | GABPB1 | – | PPARGC1A is not within 250 kb; variant is at GABPB1 |
| rs12942023 | FUT8 | Congener Processing (Whiskey/Wine Tolerance) | chr17:69616976 (intron_variant) | LINC01483 | – | FUT8 is not within 250 kb; variant is at LINC01483 |
| rs13278062 | SIRT1 | Cellular repair efficiency (SIRT1 expression) | chr8:23225458 (splice_region_variant) | TNFRSF10A, TNFRSF10A-DT | tumor necrosis factor receptor superfamily member 10A amount; amount of tumor necrosis factor receptor superfamily member 10A (human) in cerebrospinal fluid; age-related macular degeneration | SIRT1 is not within 250 kb; variant is at TNFRSF10A, TNFRSF10A-DT |
| rs13331 | OR2M7 | Asparagus Urine Odor Detection | chr17:7190147 (3_prime_UTR_variant) | DLG4 | amount of fatty acid-binding protein, intestinal in blood; heel bone mineral density | OR2M7 is not within 250 kb; variant is at DLG4 |
| rs137852 | COL5A2 | Tendon stiffness and ligament structure | chr22:50004852 (intron_variant) | IL17REL | – | COL5A2 is not within 250 kb; variant is at IL17REL<br>genotype letters ['C', 'T'] are impossible for alleles AAAAAAAAAAA/AAAAAAAAAA/AAAAAAAAAAAA/AAAAAAAAAAAAA/AAAAAAAAAAAAAA/AAAAAAAAAAAAAAA/AAAAAAAAAAAAAAAA/AAAAAAAAAAAAAAAAAA/AAAAAAAAAAAAAAAAAAAAAA |
| rs16835198 | FNDC5 | Irisin release & mitochondrial remodeling | chr1:32861080 (downstream_gene_variant) | FNDC5, S100PBP | – | genotype letters ['A', 'G'] are impossible for alleles G/T |
| rs16906252 | MMP12 | Lung Elasticity & COPD Risk | chr10:129467281 (splice_donor_region_variant) | MGMT | amount of methylated-DNA--protein-cysteine methyltransferase (human) in blood; gene methylation measurement | MMP12 is not within 250 kb; variant is at MGMT |
| rs17226398 | SLC22A5 | Carnitine absorption (fat oxidation) | chr4:61996223 (intron_variant) | ADGRL3 | – | SLC22A5 is not within 250 kb; variant is at ADGRL3<br>genotype letters ['C', 'T'] are impossible for alleles G/C |
| rs1728986 | TNXB | Tenascin-X structure (joint laxity marker) | chr4:98585324 (intron_variant) | TSPAN5 | – | TNXB is not within 250 kb; variant is at TSPAN5<br>genotype letters ['C', 'T'] are impossible for alleles T/G |
| rs17608 | SERPINA1 | Alpha-1 Antitrypsin Deficiency | chr19:39735006 (missense_variant) | CLC | eosinophil count | SERPINA1 is not within 250 kb; variant is at CLC |
| rs17609940 | IGF1R | IGF-1 receptor sensitivity | chr6:35067023 (intron_variant) | ANKS1A | vaginal microbiome measurement; coronary artery disorder | IGF1R is not within 250 kb; variant is at ANKS1A<br>A/T or C/G SNP (G/A/C): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs1800252 | COL2A1 | Cartilage durability and joint surface quality | chr7:94428336 (synonymous_variant) | COL1A2 | – | COL2A1 is not within 250 kb; variant is at COL1A2 |
| rs1800790_TIER2 | FGB | Fibrinogen level (clotting / inflammation) | chr4:154562556 (upstream_gene_variant) | FGB | – | key has a suffix, so it can never match a DNA file; duplicates rs1800790 (FGB) |
| rs1805065 | ACTN2 | Muscle fiber structural stability | chr16:55669586 (missense_variant) | SLC6A2 | – | ACTN2 is not within 250 kb; variant is at SLC6A2 |
| rs1805086 | MYF5 | Satellite cell activation (muscle growth) | chr2:190060351 (missense_variant) | MSTN, AKAP19 | – | MYF5 is not within 250 kb; variant is at MSTN, AKAP19 |
| rs2052129 | HDC | Histamine production rate | chr7:150851884 (intron_variant) | AOC1 | – | HDC is not within 250 kb; variant is at AOC1 |
| rs2070974 | TYR | Melanin synthesis efficiency | – () | – | – | rsID not found in Ensembl (retired, or never existed) |
| rs2071403 | THRB | Thyroid receptor responsiveness | chr2:1413472 (5_prime_UTR_variant) | TPO | blood immunoglobulin amount | THRB is not within 250 kb; variant is at TPO |
| rs2073711 | COL11A1 | Collagen cross-link strength | chr15:65201874 (missense_variant) | CILP | – | COL11A1 is not within 250 kb; variant is at CILP |
| rs2239681 | NDUFB6 | Electron transport chain efficiency | chr11:2146751 (non_coding_transcript_exon_variant) | IGF2-AS, IGF2 | hemoglobin measurement | NDUFB6 is not within 250 kb; variant is at IGF2-AS, IGF2 |
| rs2241880 | NOD2 | Inflammatory response to gut bacteria | chr2:233274722 (missense_variant) | ATG16L1, SCARNA5 | Crohn disease | NOD2 is not within 250 kb; variant is at ATG16L1, SCARNA5 |
| rs2271683 | ELN | Elastin fiber elasticity | chr2:189009011 (missense_variant) | COL3A1 | – | ELN is not within 250 kb; variant is at COL3A1 |
| rs2285477 | COX7A1 | Complex IV oxidative phosphorylation output | chr17:10638198 (missense_variant) | MYHAS, MYH3 | – | COX7A1 is not within 250 kb; variant is at MYHAS, MYH3 |
| rs2289360 | COL6A5 | Collagen VI microfibril strength | chr2:27079297 (intron_variant) | EMILIN1 | – | COL6A5 is not within 250 kb; variant is at EMILIN1 |
| rs2304672 | NR1D1 | Sleep timing & metabolic rhythm | chr2:238277948 (5_prime_UTR_variant) | PER2 | – | NR1D1 is not within 250 kb; variant is at PER2<br>genotype letters ['C', 'T'] are impossible for alleles G/C |
| rs2535633 | ELOVL2 | Epigenetic aging rate | chr3:52825614 (intron_variant) | ITIH4, ITIH4-AS1 | body mass index | ELOVL2 is not within 250 kb; variant is at ITIH4, ITIH4-AS1<br>A/T or C/G SNP (C/G): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs2740574_dupfix | CYP3A4 | Secondary CYP3A4 metabolic rate | chr7:99784473 (upstream_gene_variant) | CYP3A4 | – | key has a suffix, so it can never match a DNA file; duplicates rs2740574 (CYP3A4) |
| rs2802292 | FOXO3 | Cellular stress resistance & Longevity | chr6:108587315 (intron_variant) | FOXO3 | platelet component distribution width | genotype letters ['C', 'T'] are impossible for alleles G/T |
| rs2802295 | FOXO1 | Oxidative stress resilience & glucose aging | chr6:108605293 (intron_variant) | FOXO3 | body mass index; cerebral cortex area attribute; brain attribute | FOXO1 is not within 250 kb; variant is at FOXO3 |
| rs3123554 | SHBG | SHBG binding affinity | chr1:23869911 (upstream_gene_variant) | CNR2, FUCA1 | – | SHBG is not within 250 kb; variant is at CNR2, FUCA1 |
| rs328_TIER2 | LPL | LPL enzyme efficiency (fat clearance) | chr8:19962213 (stop_gained) | LPL | triglycerides in chylomicrons and extremely large VLDL measurement; phospholipids in chylomicrons and extremely large VLDL measurement; concentration of chylomicrons and extremely large VLDL particles measurement | key has a suffix, so it can never match a DNA file; duplicates rs328 (LPL)<br>A/T or C/G SNP (C/A/G): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs350843 | FOXO3 | Stress resistance & longevity | chr19:4177334 (intron_variant) | CREB3L3, SIRT6 | – | FOXO3 is not within 250 kb; variant is at CREB3L3, SIRT6<br>genotype letters ['C', 'G'] are impossible for alleles A/C |
| rs3737965 | COL18A1 | Collagen XVIII integrity | chr1:11806394 (5_prime_UTR_variant) | CLCN6, MTHFR | – | COL18A1 is not within 250 kb; variant is at CLCN6, MTHFR |
| rs3741942 | NDUFS2 | ETC efficiency & ROS leakage | chr12:3283033 (missense_variant) | TSPAN9 | – | NDUFS2 is not within 250 kb; variant is at TSPAN9 |
| rs3758391 | SIRT3 | Mitochondrial stress resistance | chr10:67883584 (upstream_gene_variant) | SIRT1 | – | SIRT3 is not within 250 kb; variant is at SIRT1 |
| rs3774175 | SOD3 | Extracellular Antioxidant Capacity / Collagen Protection | chr3:10358582 (intron_variant) | ATP2B2 | – | SOD3 is not within 250 kb; variant is at ATP2B2 |
| rs4074995 | MYH7 | Type I fiber development | chr5:177370342 (intron_variant) | RGS14 | nephrolithiasis; hemoglobin measurement; high density lipoprotein cholesterol measurement | MYH7 is not within 250 kb; variant is at RGS14 |
| rs444697 | ASMT | Melatonin Synthesis Efficiency | chr6:33607232 (intron_variant) | – | psoriasis | ASMT is not within 250 kb; variant is at ITPR3, BAK1, UQCC2 |
| rs45446698 | CYP3A5 | Steroid hormone and drug metabolism speed | chr7:99735325 (intron_variant) | CYP3A7, ZSCAN25 | epiandrosterone sulfate measurement; androsterone sulfate measurement; 5alpha-androstan-3beta,17beta-diol disulfate measurement | CYP3A5 is 55 kb away, not at the site (regulatory/LD association; check the mechanism text)<br>genotype letters ['C', 'T'] are impossible for alleles T/G |
| rs4654748 | LMNA | Nuclear membrane stability | chr1:21459575 (intron_variant) | NBPF3, PFN1P10 | alkaline phosphatase measurement; glycerol-3-phosphate measurement; vitamin B6 measurement | LMNA is not within 250 kb; variant is at NBPF3, PFN1P10 |
| rs479744 | PLOD1 | Collagen cross-linking and stability | chr6:108698829 (intergenic_variant) | – | brain volume; reaction time measurement | PLOD1 is not within 250 kb; variant is at FOXO3, ARMC2, AFG1L |
| rs521674 | ADRA2B | Emotional Memory (Flashbulb Memories) | chr10:111075832 (upstream_gene_variant) | ADRA2A | – | ADRA2B is not within 250 kb; variant is at ADRA2A<br>genotype letters ['A', 'G'] are impossible for alleles T/A |
| rs523349 | SRD5A1 | DHT conversion (5-alpha reductase type 1) | chr2:31580636 (missense_variant) | SRD5A2 | triglyceride measurement | SRD5A1 is not within 250 kb; variant is at SRD5A2<br>A/T or C/G SNP (G/A/C/T): confirm the scores are written on the forward strand, otherwise results are silently inverted |
| rs5516 | F5 | Factor V Leiden clotting tendency | chr19:50820217 (missense_variant) | KLK1, TMEM277P | – | F5 is not within 250 kb; variant is at KLK1, TMEM277P |
| rs57875989 | PER3 | Circadian rhythm type | – () | – | – | rsID not found in Ensembl (retired, or never existed) |
| rs6020 | F2 | Thrombophilia (Factor II Prothrombin) | chr1:169549874 (missense_variant) | F5 | – | F2 is not within 250 kb; variant is at F5 |
| rs605059 | ESR2 | Estrogen receptor beta sensitivity | chr17:42554888 (missense_variant) | HSD17B1, HSD17B1-AS1 | – | ESR2 is not within 250 kb; variant is at HSD17B1, HSD17B1-AS1 |
| rs6263 | AR (Androgen Receptor) | Androgen Receptor Density/Sensitivity | chr7:50528202 (missense_variant) | DDC, DDC-AS1 | – | AR (Androgen Receptor) is not within 250 kb; variant is at DDC, DDC-AS1 |
| rs6536 | TRPM6 | Magnesium absorption | chr6:130839736 (3_prime_UTR_variant) | EPB41L2, SMLR1 | – | TRPM6 is not within 250 kb; variant is at EPB41L2, SMLR1 |
| rs662799_TIER2 | APOA5 | Triglyceride clearance variability | chr11:116792991 (5_prime_UTR_variant) | ZPR1, APOA5 | triglyceride measurement; high density lipoprotein cholesterol measurement; metabolic syndrome | key has a suffix, so it can never match a DNA file; duplicates rs662799 (APOA5) |
| rs676925 | MMP1 | Collagen degradation rate | chr11:118894979 (3_prime_UTR_variant) | CXCR5, BCL9L | – | MMP1 is not within 250 kb; variant is at CXCR5, BCL9L |
| rs699005 | COL1A1 | Tendon strength, flexibility, and injury risk | chr1:32780201 (synonymous_variant) | YARS1 | – | COL1A1 is not within 250 kb; variant is at YARS1 |
| rs7294919 | CNTNAP2 | Neuromuscular coordination | chr12:116889787 (intron_variant) | – | hippocampal volume; brain volume | CNTNAP2 is not within 250 kb; variant is at HRK, FBXW8, RNFT2 |
| rs7799039 | LEP (Leptin) | Leptin Production & Satiety Signaling | chr7:128238730 (intron_variant) | LEP | – | evidence names PNPLA3, but the site is LEP (Leptin) |
| rs8031440 | ACAN | Aggrecan production (shock absorption) | chr15:67191641 (3_prime_UTR_variant) | SMAD3 | – | ACAN is not within 250 kb; variant is at SMAD3 |
| rs8101881 | TFAM | Mitochondrial DNA replication & maintenance | chr19:32873722 (upstream_gene_variant) | SLC7A9, CEP89 | homocitrulline measurement; X-24736 measurement; urinary metabolite measurement | TFAM is not within 250 kb; variant is at SLC7A9, CEP89 |
| rs8192675 | SLC2A4 | GLUT4 glucose uptake in muscle cells | chr3:171007094 (intron_variant) | SLC2A2 | amount of hepatocyte growth factor receptor (human) in blood; type 2 diabetes mellitus; trait in response to thiazide | SLC2A4 is not within 250 kb; variant is at SLC2A2 |
| rs893703 | CYP2D6 | CYP2D6 metabolic speed | chr3:139531807 (intron_variant) | RBP1, COPB2-DT | – | CYP2D6 is not within 250 kb; variant is at RBP1, COPB2-DT |
| rs9282859 | HSD17B12 | Estradiol levels & associated risk | chr19:1221294 (stop_gained) | STK11 | – | HSD17B12 is not within 250 kb; variant is at STK11 |
| rs934078 | DIO2 | T4 → T3 conversion efficiency (secondary site) | chr12:114622198 (intron_variant) | – | – | DIO2 is not within 250 kb; variant is at TBX3, TBX5 |

## Warnings (37)

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
| forward | 223 |
| ambiguous | 30 |
| reverse | 17 |
| mismatch | 10 |
| n/a | 2 |
