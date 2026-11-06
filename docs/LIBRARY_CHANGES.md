# Library changes

Corrections to `config/snp_traits.json` made after the review of [LIBRARY_AUDIT.md](LIBRARY_AUDIT.md). Each changed entry carries an `audit` field with the reason.

| SNP | Gene | Trait | Scores before | Scores after | Why |
|---|---|---|---|---|---|
| rs1045642 | ABCB1 (MDR1) | Blood-Brain Barrier Pump | GG 9, AG 6, AA 3 | GG 9, AG 6, AA 5 | AA is carried by 27% of Europeans: risk score raised to 5. |
| rs17822931 | ABCC11 | Earwax type & Axillary Osmidrosis | CC 3, CT 5, TC 5, TT 9 | CC 5, CT 5, TC 5, TT 9 | CC is carried by 75% of Europeans: risk score raised to 5. |
| rs4343 | ACE | ACE enzyme expression | AA 7, AG 5, GA 5, GG 4 | AA 7, AG 5, GA 5, GG 5 | GG is carried by 32% of Europeans: risk score raised to 5. |
| rs1501299 | ADIPOQ | Adiponectin level & insulin sensitivity | GG 4, GT 7, TT 9 | GG 5, GT 5, TT 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs553668 | ADRA2A | Adrenaline-Induced Insulin Resistance | AA 7, AG 5, GG 3 | GG 7, AG 5, AA 3 | A is the risk allele (reduced insulin secretion); the library scored the common GG as the risk. |
| rs4994 | ADRB3 | Brown fat activation & weight regulation | GG 7, AG 5, AA 3 | GG 5, AG 5, AA 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs4654748 | ALPL | Vitamin B6 (PLP) blood levels | CC 4, CT 5, TT 7 | CC 5, CT 5, TT 7 | CC is carried by 28% of Europeans: risk score raised to 5. |
| rs12130333 | ANGPTL3 | Triglyceride Clearance & Lipid Partitioning | CC 3, CT 5, TC 5, TT 9 | CC 5, CT 5, TC 5, TT 9 | CC is carried by 66% of Europeans: risk score raised to 5. |
| rs1803274 | BCHE | Anesthesia Sensitivity (Pseudocholinesterase) | TT 8, CT 5, CC 1 | CC 8, CT 6, TT 4 | T is the K variant; the library called the common CC a deficiency with apnea risk. |
| rs16942 | BRCA1 | BRCA1 expression / repair rate | CC 9, CT 6, TT 3 | CC 9, CT 6, TT 5 | TT is carried by 42% of Europeans: risk score raised to 5. |
| rs1799950 | BRCA1 | Homologous recombination repair | CC 9, CT 6, TT 3 | TT 5, CT 5, CC 5 | The library called the 88%-common TT low repair; no evidence for an effect. Neutral scores. |
| rs1761667 | CD36 | Fat Taste Perception (Creamy Craving) | GG 7, GA 5, AG 5, AA 4 | GG 7, GA 5, AG 5, AA 5 | AA is carried by 28% of Europeans: risk score raised to 5. |
| rs1333049 | CDKN2A/B | Coronary Artery Disease Risk (9p21 locus) | CC 9, CG 6, GG 3 | GG 9, CG 6, CC 3 | C is the coronary artery disease risk allele in the GWAS Catalog; the library had it as normal. |
| rs1061170 | CFH | Age-Related Macular Degeneration (AMD) | CC 8, CT 5, TC 5, TT 2 | TT 8, CT 5, CC 2 | C (His402) is the AMD risk allele; the library had it as the normal one. |
| rs1800012 | COL1A1 | Collagen type I stability (bone & tendons) | CC 6, AC 8, AA 9 | CC 5, AC 5, AA 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs12722 | COL5A1 | Tendon stiffness & injury risk | CC 7, CT 6, TC 6, TT 5 | CC 5, CT 5, TC 5, TT 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs1799998 | CYP11B2 | Salt Sensitivity (Aldosterone) | AA 3, AG 6, GG 9 | AA 5, AG 6, GG 9 | AA is carried by 26% of Europeans: risk score raised to 5. |
| rs1048943 | CYP1A1 | Xenobiotic detoxification | TT 7, CT 5, CC 3 | TT 6, CT 5, CC 4 | C (Val462) raises catalytic efficiency 5-12x (UniProt); the library had it as lower activity. |
| rs1801272 | CYP2A6 | Nicotine Metabolism Speed | AA 3, AT 6, TT 9 | AA 5, AT 5, TT 5 | T is CYP2A6*2 (slow); the library called the common AA slow. Neutral scores. |
| rs2740574 | CYP3A4 | Drug metabolism rate | TT 9, CT 6, CC 3 | TT 5, CT 5, CC 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs12785878 | DHCR7 | Vitamin D Synthesis from Sun | GG 7, GT 5, TG 5, TT 3 | GG 7, GT 5, TG 5, TT 5 | TT is carried by 49% of Europeans: risk score raised to 5. |
| rs1800498 | DRD2 | Reward system sensitivity | CC 9, CT 6, TT 3 | CC 9, CT 6, TT 5 | TT is carried by 38% of Europeans: risk score raised to 5. |
| rs1800955 | DRD4 | Novelty Seeking & Impulse Control | CC 7, CT 5, TC 5, TT 3 | CC 7, CT 5, TC 5, TT 5 | TT is carried by 35% of Europeans: risk score raised to 5. |
| rs11615 | ERCC1 | Cisplatin sensitivity / nucleotide repair | GG 9, AG 6, AA 3 | GG 9, AG 6, AA 5 | AA is carried by 39% of Europeans: risk score raised to 5. |
| rs1256031 | ESR2 | Estrogen Receptor Beta Sensitivity | GG 8, GA 6, AA 4 | GG 8, GA 6, AA 5 | AA is carried by 32% of Europeans: risk score raised to 5. |
| rs1054135 | FABP4 (A-FABP) | Fatty Acid Transport & Lipotoxicity Risk | TT 8, TC 5, CC 3 | TT 5, TC 5, CC 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs601338 | FUT2 | Secretor status (major SNP) | AA 6, AG 5, GA 5, GG 3 | GG 6, AG 5, AA 4 | A is the W143X stop (non-secretor); the library had AA as full secretor. |
| rs7041 | GC | Vitamin D transport & availability | AA 9, AC 7, CC 4 | AA 9, AC 7, CC 5 | CC is carried by 34% of Europeans: risk score raised to 5. |
| rs713041 | GPX4 | Lipid Peroxidation Defense | TT 9, TC 6, CC 3 | TT 9, TC 6, CC 5 | CC is carried by 30% of Europeans: risk score raised to 5. |
| rs7454108 | HLA-DQ8 | Celiac Disease Risk (HLA-DQ8) | CC 8, CT 5, TC 5, TT 2 | TT 8, CT 5, CC 2 | C tags HLA-DQ8; the library scored the common TT (no DQ8) as high risk. |
| rs2071749 | HMOX1 | Heme breakdown / oxidative stress resistance | AA 9, AG 7, GG 4 | AA 5, AG 5, GG 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs6295 | HTR1A | 5-HT1A autoreceptor sensitivity | CC 6, CG 5, GG 5 | CC 5, CG 5, GG 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs2229765 | IGF1R | Growth Factor Receptor Sensitivity | AA 9, AG 6, GG 4 | AA 9, AG 6, GG 5 | GG is carried by 33% of Europeans: risk score raised to 5. |
| rs4402960 | IGF2BP2 | First-Phase Insulin Secretion | GG 3, GT 5, TG 5, TT 8 | GG 8, GT 5, TT 3 | T is the type 2 diabetes risk allele; the library had it as protective. |
| rs1946518 | IL18 | IL-18 Inflammatory Levels | TT 7, TG 5, GG 4 | TT 7, TG 5, GG 5 | GG is carried by 33% of Europeans: risk score raised to 5. |
| rs419598 | IL1RN | Inflammation Resolution (IL-1RA) | CC 9, CT 6, TT 3 | CC 9, CT 6, TT 5 | TT is carried by 50% of Europeans: risk score raised to 5. |
| rs1800795 | IL6 (Promoter) | Inflammatory reactivity (CRP levels) | GG 3, GC 6, CC 9 | GG 5, GC 6, CC 9 | GG is carried by 34% of Europeans: risk score raised to 5. |
| rs12203592 | IRF4 | UV sensitivity & pigmentation aging | CC 3, CT 6, TT 9 | CC 7, CT 5, TT 3 | T is the sun-sensitivity and freckling allele; the library had it as darker skin. |
| rs1800588 | LIPC | HDL cholesterol control | CC 3, CT 6, TT 9 | CC 5, CT 6, TT 9 | CC is carried by 63% of Europeans: risk score raised to 5. |
| rs6323 | MAOA | Monoamine Oxidase A Activity | TT 3, TG 5, GG 8 | TT 5, TG 5, GG 8 | TT is carried by 51% of Europeans: risk score raised to 5. |
| rs885479 | MC1R | Melanin type (pheomelanin ratio) | AA 9, AG 6, GG 3 | GG 5, AG 5, AA 5 | The library scored the 87%-common GG as high pheomelanin; Arg163Gln is a weak MC1R variant. Neutral scores. |
| rs559870 | MMP3 | Collagen remodeling efficiency | CC 9, CT 6, TT 3 | CC 5, CT 5, TT 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs1801394 | MTRR | B12 recycling | AA 9, AG 6, GG 3 | AA 9, AG 6, GG 5 | GG is carried by 27% of Europeans: risk score raised to 5. |
| rs35652124 | NFE2L2 (NRF2) | Master Antioxidant Switch (NRF2) | CC 8, CT 6, TC 6, TT 4 | CC 8, CT 6, TC 6, TT 5 | TT is carried by 48% of Europeans: risk score raised to 5. |
| rs41423247 | NR3C1 | Cortisol Receptor Sensitivity (BclI) | CC 7, CG 5, GC 5, GG 3 | CC 7, CG 5, GC 5, GG 5 | GG is carried by 38% of Europeans: risk score raised to 5. |
| rs1052133 | OGG1 | Oxidative DNA Damage Repair | GG 9, GC 6, CC 3 | CC 8, CG 6, GG 4 | G is Cys326, the lower-activity allele; the library had it as efficient. |
| rs72921001 | OR6A2 | Cilantro Taste (Soapy vs Herb) | AA 8, AC 5, CA 5, CC 2 | AA 5, AC 5, CA 5, CC 5 | A taste trait from a single study: neutral scores. |
| rs2268491 | OXTR | Oxytocin Receptor Sensitivity | TT 10, TC 6, CC 3 | TT 5, TC 5, CC 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs7946 | PEMT | Choline synthesis (Liver health) | CC 8, CT 5, TC 5, TT 2 | CC 8, CT 5, TC 5, TT 5 | TT is carried by 50% of Europeans: risk score raised to 5. |
| rs894160 | PLIN1 | Weight Loss Resistance (Perilipin) | TT 7, CT 5, CC 3 | TT 7, CT 5, CC 5 | CC is carried by 48% of Europeans: risk score raised to 5. |
| rs662 | PON1 | Detoxification of oxidized lipids | TT 8, CT 5, CC 3 | TT 5, CT 5, CC 5 | C (Arg192) increases activity (UniProt); the library had it as lower. Heart studies are mixed, so neutral scores. |
| rs8192678 | PPARGC1A (PGC-1α) | Mitochondrial biogenesis rate | CC 8, CT 6, TC 6, TT 4 | CC 5, CT 5, TC 5, TT 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs6259 | SHBG | Sex hormone binding globulin level | CC 7, CG 5, GC 5, GG 3 | GG 5, AG 5, AA 5 | A (Asn327) raises SHBG, and the library's C/G keys didn't match this G/A SNP. Neutral scores. |
| rs12778366 | SIRT1 | Metabolic Aging Clock | CC 8, CT 6, TC 6, TT 4 | CC 8, CT 6, TC 6, TT 5 | TT is carried by 77% of Europeans: risk score raised to 5. |
| rs1051266 | SLC19A1 | Folate Absorption (RFC1 Transporter) | TT 8, CT 5, CC 4 | TT 8, CT 5, CC 5 | CC is carried by 30% of Europeans: risk score raised to 5. |
| rs40184 | SLC6A3 (DAT1) | Dopamine Transporter Density | CC 3, CT 5, TC 5, TT 7 | CC 5, CT 5, TC 5, TT 7 | CC is carried by 27% of Europeans: risk score raised to 5. |
| rs3813034 | SLC6A4 | Serotonin transporter expression | CC 7, AC 5, AA 3 | CC 7, AC 5, AA 5 | AA is carried by 32% of Europeans: risk score raised to 5. |
| rs4880 | SOD2 | Mitochondrial antioxidant defense | AA 3, AG 6, GG 9 | AA 5, AG 6, GG 9 | AA is carried by 28% of Europeans: risk score raised to 5. |
| rs9282858 | SRD5A2 | DHT conversion rate | AA 3, AG 6, GG 9 | GG 5, AG 5, AA 5 | Thr49 increases Vmax (UniProt); the library had it as lower DHT. Neutral scores. |
| rs35874116 | TAS1R2 | Sweet Taste Sensitivity | CC 9, CT 6, TT 3 | CC 5, CT 5, TT 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs713598 | TAS2R38 | Bitter taste perception | CC 3, CG 6, GG 9 | CC 5, CG 6, GG 9 | CC is carried by 33% of Europeans: risk score raised to 5. |
| rs4570625 | TPH2 | Brain Serotonin Synthesis Rate | GG 8, GT 5, TG 5, TT 3 | GG 5, GT 5, TG 5, TT 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs1800592 | UCP1 | Brown fat thermogenesis | AA 3, GA 6, GG 9 | AA 5, GA 5, GG 5 | No functional evidence and no genome-wide study: neutral scores, texts kept as the library's claim. |
| rs2010963 | VEGFA (Secretion) | Blood vessel growth (angiogenesis) | CC 9, CG 6, GG 3 | CC 9, CG 6, GG 5 | GG is carried by 48% of Europeans: risk score raised to 5. |
