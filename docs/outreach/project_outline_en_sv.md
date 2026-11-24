Project outline: a personal genome explorer from consumer DNA data
=================================================================

Source text for DNA-Analyzer_project_outline_en.pdf and _sv.pdf.

ENGLISH
-------

1. Input
- A MyHeritage raw data CSV, about 585,000 genotyped SNPs, delivered on GRCh37.
- Two profiles so far (one male, one female), both with consent.
- Personal data stays on the local machine. The code is in a public GitHub repository without genotypes or per-person results.

2. Pipeline (everything runs on GRCh38)
- Lift-over: the raw file is lifted to GRCh38 with the UCSC chain file (pyliftover). 272 of 584,898 calls drop out.
- Imputation: Beagle 5.5 against the 1000 Genomes high-coverage panel (NYGC, 3,202 samples, GRCh38) in bref3 format. chrX is split at the pseudoautosomal boundaries so male haploid calls are handled correctly.
- Site list: 73.5 million variants with rsIDs from Ensembl dbSNP and European allele frequencies from the panel.
- Calibration: about 57,700 of the person's own measured SNPs are hidden, re-imputed and compared. Every call is tagged measured, high (GP >= 0.98) or medium (GP 0.90-0.98).
- Variant interpretation: consequence and amino-acid change from Ensembl VEP, expression effects from GTEx eQTLs. Each gene gets a call: less active, more active, typical function, changed in an unclear direction, or carries a trait-linked variant.
- Disease variants: checked against ClinVar (pathogenic, likely pathogenic, risk factor), with review status.

3. Coverage and confidence (per person; the two profiles are nearly identical)
- Measured SNPs: 584,600.
- Imputed at high confidence: 5.3 million, 99.5% correct in validation.
- Imputed at medium confidence: 0.32 million, 91% correct.
- Confidently called in total: about 6.2 million variants, 98.9% correct overall.
- Rare variants not detected but not excluded: 56 million. These are never reported as a negative.
- Carrier sensitivity: 98% for common variants, 87-89% for uncommon ones. Rare variants have too few data points for a reliable figure, so "does not carry" for a rare variant always reads "not detected, but not excluded".
- Gene coverage: 19,470 of 20,121 protein-coding genes (97%) have at least one confident call; 17,750 (88%) have at least one directly measured SNP.
- Calling a gene is not interpreting it: of the roughly 3,100 genes in the themes, 1,905 get typical function, 190 less active, 155 more active and 27 changed in an unclear direction; 843 have no variant with a known effect. The changed calls rest mainly on GTEx expression data, a few on curated, predicted or protein-truncating variants.

4. Analyses (tabs in an interactive explorer)
- Medicines: 12 pharmacogenes with a metaboliser phenotype (CYP2C19, CYP2C9, CYP2D6, CYP3A4/5, TPMT, NUDT15, DPYD, UGT1A1, CYP2B6, SLCO1B1, NAT2), and 4,198 ClinPGx (PharmGKB) clinical annotations at evidence levels 1A-3 for 777 drugs.
- Nutrition: 15 nutrients with intake targets from the Nordic Nutrition Recommendations 2023. Each blood marker gets a genetic score (a PGS Catalog score, or the lead variants of one large GWAS Catalog study) placed as a percentile among 1000 Genomes Europeans. Each finding has an evidence grade from A+ to C. The nutrient's Reactome pathways are shown step by step, with the person's variants pinned to the step they act on.
- Biomarkers: 11 common lab tests (lipids, glucose, CRP, liver, kidney, thyroid, hormones), same method.
- Themes (gene clusters): cancer and the life of a cell (1,716 genes), female fertility (712), male fertility (763), fitness (1,170). Genes come from Open Targets (genetic evidence) and Gene Ontology via QuickGO, with UniProt and GTEx as filters. Protein interactions from STRING, pathways from Reactome.
- Fitness: 5 polygenic measures (grip strength, lean mass, heart-rate response to exercise, creatine kinase, coffee intake), and the 33 SNPs that consumer fitness DNA tests report, each graded by what large sources support (GWAS Catalog, ClinVar, ClinPGx), with a count of sport papers from Europe PMC.
- Each result has a short plain-language text on what it means in practice. For each score, the variants in the person's favour and against them are shown side by side.

5. Principles
- Facts come from sources: effects, frequencies, pathways and citations are fetched from public databases and bulk files. Hand-curated configs only choose which genes, traits and tests to include.
- The plain-language texts are my own wording and are kept separate from the sourced data.
- Every finding shows its source, its evidence grade and whether the call is measured or imputed.

6. Output
- An interactive web page in English and Swedish, run locally or as a private hosted page. An older PDF report also exists.
- The code is written in Python with help from an AI coding assistant. The scientific content comes from the databases above, not from the AI.

7. Known limitations
- Scores are relative to Europeans only.
- The polygenic scores use clumped lead variants, not LD-aware genome-wide models.
- A genotyping chip cannot replace sequencing when looking for rare disease variants.
- Nothing has been validated clinically.

8. Questions
- Scientific validation: what is needed before showing results to other people, for example comparison against sequenced samples?
- Regulation: does health interpretation of genetic data fall under the EU IVDR or MDR? What does the Swedish Genetic Integrity Act require if the service is offered to others?
- Data handling: what does GDPR require for genetic data (a special category) in storage, consent and hosting, and which secure infrastructures exist?
- Methods: better polygenic score methods, and reference panels beyond European ancestry.



SVENSKA
-------

1. Indata
- MyHeritage-rådata som CSV, ungefär 585 000 genotypade SNP:er, levererad på GRCh37.
- Två profiler hittills (en man, en kvinna), båda med samtycke.
- Personuppgifter ligger bara lokalt. Koden finns i ett publikt GitHub-repo utan genotyper eller resultat per person.

2. Pipeline (allt körs på GRCh38)
- Lift-over: rådatan lyfts till GRCh38 med UCSC:s kedjefil (pyliftover). 272 av 584 898 anrop faller bort.
- Imputering: Beagle 5.5 mot 1000 Genomes high-coverage-panelen (NYGC, 3 202 individer, GRCh38) i bref3-format. chrX delas vid de pseudoautosomala gränserna så att manliga haploida anrop hanteras rätt.
- Platslista: 73,5 miljoner varianter med rsID från Ensembl dbSNP och europeiska allelfrekvenser från panelen.
- Kalibrering: ungefär 57 700 av personens egna uppmätta SNP:er döljs, imputeras om och jämförs. Varje anrop märks uppmätt, hög (GP >= 0,98) eller medel (GP 0,90-0,98).
- Varianttolkning: konsekvens och aminosyraförändring från Ensembl VEP, uttryckseffekter från GTEx eQTL. Varje gen får ett anrop: mindre aktiv, mer aktiv, typisk funktion, förändrad med oklar riktning, eller bär en egenskapskopplad variant.
- Sjukdomsvarianter: kontrolleras mot ClinVar (patogen, troligen patogen, riskfaktor), med granskningsnivå.

3. Täckning och säkerhet (per person; de två profilerna ligger nästan identiskt)
- Uppmätta SNP:er: 584 600.
- Imputerade med hög säkerhet: 5,3 miljoner, 99,5 % rätt vid validering.
- Imputerade med medelhög säkerhet: 0,32 miljoner, 91 % rätt.
- Säkert avlästa totalt: ungefär 6,2 miljoner varianter, 98,9 % rätt sammanvägt.
- Sällsynta varianter som inte påvisats men inte kan uteslutas: 56 miljoner. De redovisas aldrig som ett negativt svar.
- Bärarkänslighet: 98 % för vanliga varianter, 87-89 % för ovanliga. För sällsynta varianter finns för få mätpunkter för en säker siffra, så "bär inte" för en sällsynt variant redovisas alltid som "inte påvisad, men inte utesluten".
- Gentäckning: 19 470 av 20 121 proteinkodande gener (97 %) har minst en säker avläsning; 17 750 (88 %) har minst en direkt uppmätt SNP.
- Avläsning är inte tolkning: av de cirka 3 100 gener som ingår i teman får 1 905 typisk funktion, 190 mindre aktiv, 155 mer aktiv och 27 förändrad med oklar riktning; 843 saknar variant med känd effekt. De förändrade anropen bygger främst på uttrycksdata från GTEx, några få på kurerade, predikterade eller proteinavkortande varianter.

4. Analyser (flikar i en interaktiv utforskare)
- Läkemedel: 12 farmakogener med metaboliserarfenotyp (CYP2C19, CYP2C9, CYP2D6, CYP3A4/5, TPMT, NUDT15, DPYD, UGT1A1, CYP2B6, SLCO1B1, NAT2), och 4 198 kliniska annoteringar från ClinPGx (PharmGKB, evidensnivå 1A-3) för 777 läkemedel.
- Näring: 15 näringsämnen med intagsmål från NNR 2023. Varje blodmarkör får en genetisk poäng (från PGS Catalog, eller ledvarianterna i en stor GWAS Catalog-studie) placerad som percentil bland européer i 1000 Genomes. Varje fynd har en evidensgrad från A+ till C. Näringsämnets Reactome-vägar visas steg för steg, med personens varianter fästa vid steget de verkar i.
- Biomarkörer: 11 vanliga labbprover (blodfetter, glukos, CRP, lever, njure, sköldkörtel, hormoner), samma metod.
- Teman (genkluster): cancer och en cells liv (1 716 gener), kvinnlig fertilitet (712), manlig fertilitet (763), fysisk form (1 170). Generna hämtas från Open Targets (genetiska belägg) och Gene Ontology via QuickGO, med UniProt och GTEx som filter. Proteinkopplingar från STRING, signalvägar från Reactome.
- Fysisk form: 5 polygena mått (greppstyrka, fettfri massa, pulsens svar på träning, kreatinkinas, kaffeintag), och de 33 SNP:er som träningsinriktade DNA-tester rapporterar, var och en graderad efter vad stora källor stöder (GWAS Catalog, ClinVar, ClinPGx), med antal idrottsartiklar från Europe PMC.
- Varje resultat har en kort text i klartext om vad det betyder i praktiken. För varje poäng visas varianterna till personens fördel och emot sida vid sida.

5. Principer
- Fakta kommer från källor: effekter, frekvenser, signalvägar och referenser hämtas från publika databaser och bulkfiler. Handkurerade konfigurationer väljer bara vilka gener, egenskaper och prover som tas med.
- Klartexterna är mina egna formuleringar och hålls åtskilda från källdata.
- Varje fynd visar sin källa, sin evidensgrad och om anropet är uppmätt eller imputerat.

6. Utdata
- En interaktiv webbsida på svenska och engelska, som körs lokalt eller som privat sida. Det finns även en äldre PDF-rapport.
- Koden är skriven i Python med hjälp av en AI-kodassistent. Det vetenskapliga innehållet kommer från databaserna ovan, inte från AI:n.

7. Kända begränsningar
- Poängen är relativa till européer.
- De polygena poängen bygger på klumpade ledvarianter, inte på LD-medvetna genomvida modeller.
- Ett genotypningschip kan inte ersätta sekvensering när man letar efter sällsynta sjukdomsvarianter.
- Ingen klinisk validering har gjorts.

8. Frågor
- Vetenskaplig validering: vad krävs innan resultaten kan visas för andra, till exempel jämförelse mot sekvenserade prover?
- Regelverk: omfattas hälsotolkning av genetiska data av EU:s IVDR eller MDR? Vad kräver lagen om genetisk integritet om tjänsten erbjuds andra?
- Datahantering: vad kräver GDPR för genetiska data, som är en särskild kategori, när det gäller lagring, samtycke och drift? Vilka säkra infrastrukturer finns?
- Metoder: bättre metoder för polygena poäng, och referenspaneler utöver europeisk härkomst.

