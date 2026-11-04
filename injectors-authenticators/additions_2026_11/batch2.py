# injectors-authenticators/additions_2026_11/batch2.py
"""
Batch 2 of library additions: SNPs that passed two or more evidence filters (candidates.py),
checked against Ensembl and the GWAS Catalog, plus a carrier category.

    python injectors-authenticators/additions_2026_11/batch2.py

Added as traits (6): CYP4F2 Val433Met, UGT1A1 -3156G>A, GPT Val452Leu, CUBN Ala2914Val,
ABCB4 Ala934Thr, EPO Asp70Asn. Added as carrier / rare-variant entries (6): CFTR x4, ANO5, KCNQ1.
Not added: DPYD *9A (dosing guidelines class it as normal function), FGFR4 Gly388Arg (prognosis
only), ABCB4 Arg590Gln (very small effect), APOE rs769452 (rare, unclear).
Genotype keys are on the forward strand and sorted. Safe to re-run.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "corrections_2026_11"))
from builders import side, deep_dive, evidence  # noqa: E402

FILES = {"traits": "config/snp_traits.json", "dd": "config/deep_dive_content.json", "ev": "config/evidence_db.json",
         "sv_dd": "config/SV_deep_dive_content.json", "sv_ev": "config/SV_evidence_db.json"}
BACKUP = "config/backup/library_additions_2026-11-04.json"

TRAITS = {
    "rs2108622": {"gene": "CYP4F2", "system": "Vitamins / Drug Metabolism", "trait": "Vitamin K breakdown (CYP4F2 Val433Met)",
                  "description": "The T allele slows vitamin K1 breakdown; carriers need higher warfarin doses (dosing guideline level 1A).",
                  "impact": "Medium",
                  "variants": {"CC": "Typical vitamin K breakdown", "CT": "Slightly slower vitamin K breakdown",
                               "TT": "Slower vitamin K breakdown; higher warfarin dose needed"},
                  "scores": {"CC": 5, "CT": 5, "TT": 4}},
    "rs10929302": {"gene": "UGT1A1", "system": "Liver / Detox", "trait": "Bilirubin clearance (UGT1A1 -3156G>A)",
                   "description": "The A allele lowers UGT1A1 output: higher bilirubin (Gilbert-type) and slower irinotecan clearance.",
                   "impact": "Medium",
                   "variants": {"GG": "Typical bilirubin clearance", "AG": "Somewhat higher bilirubin",
                                "AA": "Higher bilirubin (Gilbert-type); irinotecan caution"},
                   "scores": {"GG": 5, "AG": 5, "AA": 4}},
    "rs147998249": {"gene": "GPT", "system": "Liver / Lab tests", "trait": "ALT liver-test reading (GPT Val452Leu)",
                    "description": "The C allele makes the ALT enzyme read markedly lower in blood tests, which can hide liver strain.",
                    "impact": "Medium",
                    "variants": {"GG": "Typical ALT readings", "CG": "ALT reads markedly lower than liver status",
                                 "CC": "ALT reads very low"},
                    "scores": {"GG": 5, "CG": 4, "CC": 4}},
    "rs45551835": {"gene": "CUBN", "system": "Kidney / Lab tests", "trait": "Urine albumin (CUBN Ala2914Val)",
                   "description": "The A allele raises urine albumin through weaker kidney reabsorption, usually without kidney damage.",
                   "impact": "Low",
                   "variants": {"GG": "Typical urine albumin", "AG": "Higher urine albumin, usually harmless",
                                "AA": "Higher urine albumin"},
                   "scores": {"GG": 5, "AG": 4, "AA": 4}},
    "rs61730509": {"gene": "ABCB4", "system": "Liver / Bile", "trait": "Bile phospholipid pump (ABCB4 Ala934Thr)",
                   "description": "The T allele is linked to higher ALT; ABCB4 protects bile ducts and keeps bile cholesterol dissolved.",
                   "impact": "Medium",
                   "variants": {"CC": "Typical bile protection", "CT": "Weaker bile protection; higher ALT",
                                "TT": "Weaker bile protection"},
                   "scores": {"CC": 5, "CT": 4, "TT": 3}},
    "rs62483572": {"gene": "EPO", "system": "Blood / Oxygen", "trait": "Red blood cell signal (EPO Asp70Asn)",
                   "description": "The A allele is linked to lower haemoglobin and haematocrit in large studies.",
                   "impact": "Medium",
                   "variants": {"GG": "Typical red cell production", "AG": "Lower haemoglobin and haematocrit",
                                "AA": "Lower haemoglobin and haematocrit"},
                   "scores": {"GG": 5, "AG": 4, "AA": 4}},
}

# Carrier entries are never scored (main.py keeps them out of every score) but keep the usual fields
def carrier(gene, variant, ref, alt, condition, condition_sv, inheritance="recessive", category="carrier"):
    het = "".join(sorted(ref + alt))
    return {"gene": gene, "system": "Inherited conditions", "trait": f"Carrier status: {gene} {variant}",
            "description": f"{condition}. Inheritance: {inheritance}.", "impact": "Low", "category": category,
            "variant_name": variant, "reference_genotype": ref * 2, "condition": condition, "condition_sv": condition_sv,
            "inheritance": inheritance,
            "variants": {ref * 2: "Not a carrier", het: "Carrier: one copy", alt * 2: "Two copies"},
            "scores": {ref * 2: 5, het: 5, alt * 2: 5}}


CARRIERS = {
    "rs115545701": carrier("CFTR", "p.Arg74Trp", "C", "T", "Cystic fibrosis / congenital absence of the vas deferens (CBAVD)",
                           "Cystisk fibros / medfödd avsaknad av sädesledare (CBAVD)"),
    "rs35516286": carrier("CFTR", "p.Ile148Thr", "T", "C", "Cystic fibrosis (usually mild or harmless on its own)",
                          "Cystisk fibros (oftast mild eller ofarlig ensam)"),
    "rs1800100": carrier("CFTR", "p.Arg668Cys", "C", "T", "Congenital absence of the vas deferens (CBAVD) and mild CFTR conditions",
                         "Medfödd avsaknad av sädesledare (CBAVD) och milda CFTR-tillstånd"),
    "rs1800111": carrier("CFTR", "p.Leu997Phe", "G", "C", "Congenital absence of the vas deferens (CBAVD) and mild CFTR conditions",
                         "Medfödd avsaknad av sädesledare (CBAVD) och milda CFTR-tillstånd"),
    "rs61910685": carrier("ANO5", "p.Ser796Leu", "C", "T", "Limb-girdle muscular dystrophy type R12",
                          "Limb-girdle muskeldystrofi typ R12"),
    "rs147445322": carrier("KCNQ1", "p.Asp611Asn", "G", "A", "Long QT syndrome type 1 (heart rhythm)",
                           "Långt QT-syndrom typ 1 (hjärtrytm)", inheritance="dominant gene; uncertain significance",
                           category="rare_variant"),
}

DD = {
    "rs2108622": deep_dive(["TT"], ["CC"], data_risk=side(
        "CYP4F2", "The Vitamin K Keeper", "RISK",
        "CYP4F2 breaks down vitamin K1 in the liver, helping set how much vitamin K is available for clotting proteins.",
        "You carry two copies of the Val433Met variant (T allele). Your enzyme clears vitamin K more slowly, so more of it stays "
        "available for clotting. Day to day this is harmless, but people with this genotype need higher doses of the blood thinner warfarin.",
        "Typical Breakdown (CC).", "Your Result: Slower Breakdown (TT).",
        "Tell Your Doctor",
        "If you are ever prescribed warfarin, mention this result: dosing guidelines raise the starting dose for your genotype. "
        "Keep vitamin K intake from leafy greens steady rather than high one week and low the next.",
        risks=["Medication: Higher warfarin dose needed; under-dosing risk if not known."],
        foods=["Steady Leafy Greens", "Fermented Foods (K2)", "Consistent Diet"], confidence=4)),
    "rs10929302": deep_dive(["AA"], ["GG"], data_risk=side(
        "UGT1A1", "The Slow Bilirubin Clearer", "RISK",
        "UGT1A1 attaches a sugar to bilirubin, the yellow breakdown product of red blood cells, so the liver can excrete it.",
        "Your AA genotype lowers UGT1A1 output, so bilirubin runs higher: the pattern behind Gilbert's syndrome. It is harmless and "
        "mildly antioxidant, but fasting, illness or alcohol can tint the eyes yellow, and the cancer drug irinotecan clears more slowly.",
        "Typical Clearance (GG).", "Your Result: Slow Clearance (AA).",
        "Know Your Number",
        "A raised bilirubin on a blood test is likely genetic for you; mention it so it is not mistaken for liver disease. Before "
        "irinotecan chemotherapy, ask about UGT1A1 testing, and avoid long fasts if they leave you tired or yellow.",
        risks=["Lab tests: Raised bilirubin that can be mistaken for liver disease.",
               "Medication: Higher irinotecan toxicity risk."],
        foods=["Regular Meals", "Cruciferous Vegetables", "Hydration"], confidence=4)),
    "rs147998249": deep_dive(["CG", "CC"], ["GG"], data_risk=side(
        "GPT", "The Quiet Liver Alarm", "RISK",
        "GPT is the enzyme measured as ALT in routine blood tests to spot liver damage.",
        "You carry the Val452Leu variant, which makes the ALT enzyme read markedly lower in blood tests. Your liver works normally, "
        "but its alarm signal is turned down: a level that is raised for you may look normal on paper.",
        "Typical Readings (GG).", "Your Result: Low ALT Readings.",
        "Read ALT With Care",
        "Tell your doctor your ALT runs genetically low. Rely more on GGT, AST and ultrasound when checking the liver, especially "
        "with alcohol use, fatty liver risk or medicines that strain the liver.",
        risks=["Lab tests: Liver strain can be missed when ALT is the only marker."],
        foods=["Limit Alcohol", "Coffee", "Leafy Greens"], confidence=4)),
    "rs45551835": deep_dive(["AG", "AA"], ["GG"], data_risk=side(
        "CUBN", "The Leaky Albumin Filter", "RISK",
        "Cubilin helps the kidneys reclaim albumin from urine and helps the gut absorb vitamin B12.",
        "Your variant weakens albumin recovery in the kidney tubules, so a little more albumin appears in urine. Large studies show "
        "this rarely harms kidney function, but urine albumin tests can look raised.",
        "Typical Recovery (GG).", "Your Result: Higher Urine Albumin.",
        "Interpret Urine Tests",
        "If a urine albumin-to-creatinine test comes back mildly raised, mention this result before kidney damage is assumed. "
        "Check vitamin B12 now and then, since cubilin also handles B12 uptake.",
        risks=["Lab tests: Mildly raised urine albumin without kidney disease."],
        foods=["Hydration", "B12 Sources", "Moderate Salt"], confidence=4)),
    "rs61730509": deep_dive(["CT", "TT"], ["CC"], data_risk=side(
        "ABCB4", "The Bile Shield", "RISK",
        "ABCB4 pumps phospholipids into bile, which shields the bile ducts from bile acids and keeps cholesterol dissolved.",
        "Your Ala934Thr variant is linked to higher ALT liver enzyme levels in large studies. Weaker phospholipid output makes bile "
        "harsher and more prone to cholesterol stones, especially under hormonal or weight stress.",
        "Typical Protection (CC).", "Your Result: Weaker Protection.",
        "Protect the Bile Ducts",
        "Keep weight stable and avoid crash diets, which favour gallstones; limit alcohol, and mention this result if liver enzymes "
        "rise or gallstones appear. Pregnancy and oral estrogen can unmask this gene.",
        risks=["Liver: Higher liver enzymes.", "Gallbladder: Higher gallstone tendency."],
        foods=["Steady Weight", "Fiber", "Olive Oil"], confidence=3)),
    "rs62483572": deep_dive(["AG", "AA"], ["GG"], data_risk=side(
        "EPO", "The Red Cell Signal", "RISK",
        "EPO is the kidney hormone that tells the bone marrow to make red blood cells.",
        "Your Asp70Asn variant is linked to lower haemoglobin and haematocrit in large studies, so your blood carries slightly less "
        "oxygen capacity than average.",
        "Typical Signal (GG).", "Your Result: Lower Red Cell Signal.",
        "Feed the Red Cells",
        "Keep iron, B12 and folate sufficient, and check haemoglobin and ferritin yearly. If you train for endurance or spend time "
        "at altitude, expect to adapt a little more slowly.",
        risks=["Blood: Lower haemoglobin and haematocrit.", "Performance: Slightly lower oxygen capacity."],
        foods=["Iron-Rich Foods", "Vitamin C with Meals", "B12 and Folate"], confidence=4)),
}

DD_SV = {
    "rs2108622": deep_dive(["TT"], ["CC"], data_risk=side(
        "CYP4F2", "K-vitaminvakten", "RISK",
        "CYP4F2 bryter ner vitamin K1 i levern och styr hur mycket vitamin K som finns för koagulationsproteinerna.",
        "Du bär två kopior av Val433Met-varianten (T-allelen). Ditt enzym rensar vitamin K långsammare, så mer finns kvar för "
        "koagulationen. I vardagen är det ofarligt, men personer med denna genotyp behöver högre doser av blodförtunnaren warfarin.",
        "Typisk nedbrytning (CC).", "Ditt Resultat: Långsammare nedbrytning (TT).",
        "Berätta för Läkaren",
        "Om du någon gång ordineras warfarin, nämn detta resultat: doseringsriktlinjerna höjer startdosen för din genotyp. Håll "
        "intaget av vitamin K från bladgrönsaker jämnt snarare än högt en vecka och lågt nästa.",
        risks=["Läkemedel: Högre warfarindos behövs; risk för underdosering om det inte är känt."],
        foods=["Jämnt med bladgrönt", "Fermenterad mat (K2)", "Jämn kost"], confidence=4)),
    "rs10929302": deep_dive(["AA"], ["GG"], data_risk=side(
        "UGT1A1", "Den Långsamma Bilirubinrensaren", "RISK",
        "UGT1A1 fäster ett socker vid bilirubin, den gula nedbrytningsprodukten från röda blodkroppar, så att levern kan utsöndra det.",
        "Din AA-genotyp sänker produktionen av UGT1A1, så bilirubinet ligger högre: mönstret bakom Gilberts syndrom. Det är ofarligt "
        "och milt antioxidativt, men fasta, sjukdom eller alkohol kan ge gulaktiga ögonvitor, och cancerläkemedlet irinotekan rensas långsammare.",
        "Typisk rensning (GG).", "Ditt Resultat: Långsam rensning (AA).",
        "Känn Ditt Värde",
        "Ett förhöjt bilirubin i ett blodprov är troligen genetiskt för dig; nämn det så att det inte misstas för leversjukdom. Fråga "
        "om UGT1A1-test före irinotekanbehandling, och undvik långa fastor om de gör dig trött eller gul.",
        risks=["Blodprov: Förhöjt bilirubin som kan misstas för leversjukdom.", "Läkemedel: Högre risk för biverkningar av irinotekan."],
        foods=["Regelbundna måltider", "Korsblommiga grönsaker", "Vätska"], confidence=4)),
    "rs147998249": deep_dive(["CG", "CC"], ["GG"], data_risk=side(
        "GPT", "Leverns Tysta Larm", "RISK",
        "GPT är enzymet som mäts som ALAT i vanliga blodprov för att upptäcka leverskada.",
        "Du bär Val452Leu-varianten, som gör att ALAT mäts tydligt lägre i blodprov. Din lever fungerar normalt, men dess larmsignal "
        "är nedskruvad: ett värde som är förhöjt för dig kan se normalt ut på papperet.",
        "Typiska värden (GG).", "Ditt Resultat: Låga ALAT-värden.",
        "Läs ALAT Varsamt",
        "Berätta för läkaren att ditt ALAT är genetiskt lågt. Lita mer på GT, ASAT och ultraljud när levern kontrolleras, särskilt vid "
        "alkoholbruk, risk för fettlever eller läkemedel som belastar levern.",
        risks=["Blodprov: Leverbelastning kan missas när ALAT är den enda markören."],
        foods=["Begränsa alkohol", "Kaffe", "Bladgrönsaker"], confidence=4)),
    "rs45551835": deep_dive(["AG", "AA"], ["GG"], data_risk=side(
        "CUBN", "Det Läckande Albuminfiltret", "RISK",
        "Kubilin hjälper njurarna att återta albumin från urinen och hjälper tarmen att ta upp vitamin B12.",
        "Din variant försvagar återupptaget av albumin i njurtubuli, så lite mer albumin hamnar i urinen. Stora studier visar att "
        "detta sällan skadar njurfunktionen, men urinprov för albumin kan se förhöjda ut.",
        "Typiskt återupptag (GG).", "Ditt Resultat: Mer albumin i urinen.",
        "Tolka Urinproven",
        "Om ett urinprov för albumin/kreatinin visar ett lätt förhöjt värde, nämn detta resultat innan njurskada antas. Kontrollera "
        "vitamin B12 då och då, eftersom kubilin också sköter upptaget av B12.",
        risks=["Prover: Lätt förhöjt urinalbumin utan njursjukdom."],
        foods=["Vätska", "B12-källor", "Måttligt med salt"], confidence=4)),
    "rs61730509": deep_dive(["CT", "TT"], ["CC"], data_risk=side(
        "ABCB4", "Gallans Sköld", "RISK",
        "ABCB4 pumpar fosfolipider till gallan, vilket skyddar gallgångarna mot gallsyror och håller kolesterolet löst.",
        "Din Ala934Thr-variant är i stora studier kopplad till högre ALAT. Svagare fosfolipidutsöndring gör gallan mer aggressiv och "
        "mer benägen att bilda kolesterolstenar, särskilt vid hormonell belastning eller viktförändring.",
        "Typiskt skydd (CC).", "Ditt Resultat: Svagare skydd.",
        "Skydda Gallgångarna",
        "Håll vikten stabil och undvik snabbdieter, som gynnar gallsten; begränsa alkohol och nämn resultatet om leverprover stiger "
        "eller gallsten uppstår. Graviditet och östrogen i tablettform kan få genen att märkas.",
        risks=["Lever: Högre leverprover.", "Gallblåsa: Ökad benägenhet för gallsten."],
        foods=["Stabil vikt", "Fibrer", "Olivolja"], confidence=3)),
    "rs62483572": deep_dive(["AG", "AA"], ["GG"], data_risk=side(
        "EPO", "De Röda Blodkropparnas Signal", "RISK",
        "EPO är njurhormonet som säger åt benmärgen att bilda röda blodkroppar.",
        "Din Asp70Asn-variant är i stora studier kopplad till lägre hemoglobin och hematokrit, så ditt blod har något lägre "
        "syrebärande kapacitet än genomsnittet.",
        "Typisk signal (GG).", "Ditt Resultat: Svagare signal.",
        "Ge Blodkropparna Byggstenar",
        "Se till att järn, B12 och folat räcker, och kontrollera hemoglobin och ferritin årligen. Om du tränar uthållighet eller "
        "vistas på hög höjd, räkna med att anpassningen går något långsammare.",
        risks=["Blod: Lägre hemoglobin och hematokrit.", "Prestation: Något lägre syrekapacitet."],
        foods=["Järnrik mat", "C-vitamin till maten", "B12 och folat"], confidence=4)),
}


def ev_pair(rsid, gene, common, common_sv, biotype, biotype_sv, organs, organs_sv, mech, mech_sv, qual, qual_sv,
            meth, meth_sv, label, label_sv, study, cites, name):
    """English and Swedish evidence entries with shared structure (connections omitted: not shown in the report)."""
    en = evidence(rsid, gene, common, biotype, organs, [], "", [], [], mech, qual, meth, label,
                  [(study[0], "Genome-wide association", study[1], study[2], study[3], "Study Quality (5/5)")], cites, name)
    sv = evidence(rsid, gene, common_sv, biotype_sv, organs_sv, [], "", [], [], mech_sv, qual_sv, meth_sv, label_sv,
                  [(study[0], "Genomvid associationsstudie", study[1], study[2], study[4], "Studiekvalitet (5/5)")], cites, name)
    return en, sv


EV = {
    "rs2108622": ev_pair(
        "rs2108622", "CYP4F2", "The Vitamin K Keeper", "K-vitaminvakten", "Missense Variant (Val433Met)", "Missense-variant (Val433Met)",
        ["Liver"], ["Lever"],
        (4, "Slower vitamin K hydroxylation.", "CYP4F2 is the liver enzyme that starts the breakdown of vitamin K1 by hydroxylating its "
         "side chain. The rs2108622 T allele (Met433) lowers the amount of active enzyme, so vitamin K is cleared more slowly and more "
         "remains for the gamma-carboxylation of clotting factors. This is why carriers need higher warfarin doses, and the effect is "
         "built into international dosing algorithms. The same enzyme also omega-hydroxylates fatty acids, which explains the strong "
         "metabolomics signals for dicarboxylic acids such as hexadecanedioate."),
        (4, "Långsammare hydroxylering av vitamin K.", "CYP4F2 är leverenzymet som inleder nedbrytningen av vitamin K1 genom att "
         "hydroxylera dess sidokedja. T-allelen för rs2108622 (Met433) sänker mängden aktivt enzym, så vitamin K rensas långsammare och "
         "mer finns kvar för gammakarboxyleringen av koagulationsfaktorer. Därför behöver bärare högre warfarindoser, och effekten finns "
         "inbyggd i internationella doseringsalgoritmer. Samma enzym omega-hydroxylerar också fettsyror, vilket förklarar de starka "
         "metabolomiksignalerna för dikarboxylsyror som hexadekandioat."),
        (5, "Dosing guideline and metabolomics GWAS.", "Included in warfarin dosing guidelines (evidence level 1A) and confirmed by "
         "metabolomics GWAS (p = 3e-108)."),
        (5, "Doseringsriktlinje och metabolomik-GWAS.", "Ingår i doseringsriktlinjer för warfarin (evidensnivå 1A) och bekräftas av "
         "metabolomik-GWAS (p = 3e-108)."),
        (5, "Pharmacogenetic trials and GWAS.", "Warfarin dose studies and metabolite GWAS."),
        (5, "Farmakogenetiska studier och GWAS.", "Studier av warfarindos och GWAS av metaboliter."),
        "DRUG METABOLISM", "LÄKEMEDELSMETABOLISM",
        ("Surendran et al. (2022) - Nature Medicine", "Large plasma metabolomics cohorts", "Genome-wide association of metabolites.",
         "STRENGTH: Very strong, replicated signal with a clear enzyme mechanism. CRITIQUE: Health effects outside warfarin dosing are small.",
         "STYRKA: Mycket stark, replikerad signal med en tydlig enzymmekanism. KRITIK: Hälsoeffekterna utanför warfarindosering är små."),
        ["36357675", "36635386"], "CYP4F2_VITK"),
    "rs10929302": ev_pair(
        "rs10929302", "UGT1A1", "The Bilirubin Clearer", "Bilirubinrensaren", "Promoter Variant (-3156G>A)", "Promotorvariant (-3156G>A)",
        ["Liver"], ["Lever"],
        (5, "Lower UGT1A1 expression.", "UGT1A1 glucuronidates bilirubin, making it water-soluble so the liver can excrete it in bile. "
         "The rs10929302 A allele sits in the phenobarbital-responsive enhancer of the UGT1A1 promoter and lowers transcription; it is "
         "often inherited together with the TA-repeat variant UGT1A1*28. Lower enzyme output raises unconjugated bilirubin, the "
         "Gilbert's syndrome pattern, and slows the inactivation of SN-38, the active metabolite of the chemotherapy drug irinotecan."),
        (5, "Lägre uttryck av UGT1A1.", "UGT1A1 glukuronerar bilirubin så att det blir vattenlösligt och kan utsöndras med gallan. "
         "A-allelen för rs10929302 sitter i den fenobarbitalkänsliga förstärkaren i UGT1A1-promotorn och sänker transkriptionen; den "
         "ärvs ofta tillsammans med TA-repetitionsvarianten UGT1A1*28. Lägre enzymproduktion höjer det okonjugerade bilirubinet, "
         "mönstret vid Gilberts syndrom, och bromsar inaktiveringen av SN-38, den aktiva metaboliten av cytostatikumet irinotekan."),
        (5, "Strongest bilirubin locus.", "The UGT1A1 locus is the strongest bilirubin signal in the genome (p < 1e-300)."),
        (5, "Det starkaste bilirubinlocuset.", "UGT1A1-locuset är den starkaste bilirubinsignalen i genomet (p < 1e-300)."),
        (5, "GWAS and clinical pharmacology.", "Bilirubin GWAS and irinotecan toxicity studies."),
        (5, "GWAS och klinisk farmakologi.", "Bilirubin-GWAS och studier av irinotekantoxicitet."),
        "DETOXIFICATION", "AVGIFTNING",
        ("Sinnott-Armstrong et al. (2021) - Nature Genetics", "UK Biobank", "Genome-wide association of 35 blood and urine biomarkers.",
         "STRENGTH: Enormous sample with an unambiguous effect allele. CRITIQUE: The SNP tags a haplotype; the TA-repeat itself is not measured.",
         "STYRKA: Enormt urval med en entydig effektallel. KRITIK: SNP:n markerar en haplotyp; själva TA-repetitionen mäts inte."),
        ["33462484", "32084209"], "UGT1A1_BILIRUBIN"),
    "rs147998249": ev_pair(
        "rs147998249", "GPT", "The ALT Enzyme", "ALAT-enzymet", "Missense Variant (Val452Leu)", "Missense-variant (Val452Leu)",
        ["Liver", "Muscles"], ["Lever", "Muskler"],
        (4, "Changes the measured enzyme, not liver health.", "GPT encodes alanine aminotransferase 1, the enzyme measured as ALT in "
         "routine liver panels. The rs147998249 C allele (Leu452) is among the strongest common-variant effects on any blood test: "
         "carriers show markedly lower ALT. The effect is on the enzyme itself, its stability or its activity in the assay, not on the "
         "health of the liver, so carriers can have liver strain that ALT under-reports."),
        (4, "Ändrar det uppmätta enzymet, inte leverns hälsa.", "GPT kodar för alaninaminotransferas 1, enzymet som mäts som ALAT i "
         "vanliga leverprover. C-allelen för rs147998249 (Leu452) är bland de starkaste effekterna av en vanlig variant på något "
         "blodprov: bärare har tydligt lägre ALAT. Effekten gäller själva enzymet, dess stabilitet eller aktivitet i analysen, inte "
         "leverns hälsa, så bärare kan ha leverbelastning som ALAT underskattar."),
        (5, "Extremely strong biobank signal.", "ALT association at p < 1e-300 in several biobanks."),
        (5, "Extremt stark biobankssignal.", "Koppling till ALAT med p < 1e-300 i flera biobanker."),
        (4, "Biobank GWAS.", "Biobank-scale GWAS of liver enzymes."),
        (4, "Biobanks-GWAS.", "GWAS av leverenzymer i biobanksskala."),
        "LAB INTERPRETATION", "PROVTOLKNING",
        ("Sinnott-Armstrong et al. (2021) - Nature Genetics", "UK Biobank", "Genome-wide association of 35 blood and urine biomarkers.",
         "STRENGTH: Unambiguous, very large effect. CRITIQUE: Rare (about 0.6% in Europeans); consumer genotypes for rare variants need confirmation.",
         "STYRKA: Entydig och mycket stor effekt. KRITIK: Sällsynt (cirka 0,6 % hos européer); konsumentgenotyper för sällsynta varianter behöver bekräftas."),
        ["33462484", "40436827"], "GPT_ALT"),
    "rs45551835": ev_pair(
        "rs45551835", "CUBN", "The Albumin Receptor", "Albuminreceptorn", "Missense Variant (Ala2914Val)", "Missense-variant (Ala2914Val)",
        ["Kidneys", "Intestines"], ["Njurar", "Tarmar"],
        (4, "Weaker tubular albumin reabsorption.", "Cubilin works with amnionless and megalin to pull filtered albumin back out of urine "
         "in the proximal tubule, and with intrinsic factor to absorb vitamin B12 in the gut. The rs45551835 A allele (Val2914) lies in "
         "the C-terminal part of cubilin and lowers albumin reabsorption, raising the urinary albumin-to-creatinine ratio. Follow-up "
         "work suggests such C-terminal variants cause albuminuria without loss of kidney filtration."),
        (4, "Svagare återupptag av albumin i tubuli.", "Kubilin arbetar med amnionless och megalin för att ta tillbaka filtrerat albumin "
         "från urinen i proximala tubuli, och med intrinsic factor för att ta upp vitamin B12 i tarmen. A-allelen för rs45551835 "
         "(Val2914) ligger i kubilinets C-terminala del och sänker återupptaget av albumin, vilket höjer albumin/kreatinin-kvoten i "
         "urinen. Uppföljande studier tyder på att sådana C-terminala varianter ger albuminuri utan förlust av njurfiltration."),
        (5, "Replicated albuminuria GWAS.", "Urinary albumin-to-creatinine association at p = 3e-126, replicated across consortia."),
        (5, "Replikerad albuminuri-GWAS.", "Koppling till albumin/kreatinin i urin med p = 3e-126, replikerad i flera konsortier."),
        (5, "GWAS and functional follow-up.", "Albuminuria GWAS with kidney function follow-up."),
        (5, "GWAS och funktionell uppföljning.", "Albuminuri-GWAS med uppföljning av njurfunktion."),
        "KIDNEY", "NJURE",
        ("Teumer et al. (2019) - Nature Communications", "CKDGen consortium", "Genome-wide association of urinary albumin.",
         "STRENGTH: Large, replicated signal. CRITIQUE: Raised albumin here may not mean kidney disease, which matters for how it is read.",
         "STYRKA: Stor, replikerad signal. KRITIK: Förhöjt albumin här behöver inte betyda njursjukdom, vilket påverkar hur värdet tolkas."),
        ["31511532", "30220432"], "CUBN_ALBUMIN"),
    "rs61730509": ev_pair(
        "rs61730509", "ABCB4", "The Bile Phospholipid Pump", "Gallans fosfolipidpump", "Missense Variant (Ala934Thr)", "Missense-variant (Ala934Thr)",
        ["Liver"], ["Lever"],
        (4, "Weaker phosphatidylcholine export into bile.", "ABCB4 (MDR3) flips phosphatidylcholine into bile, where it forms mixed "
         "micelles that buffer the detergent action of bile acids and keep cholesterol in solution. Loss of ABCB4 function causes "
         "cholestatic liver disease and low-phospholipid gallstones. The rs61730509 T allele (Thr934) is associated with higher ALT in "
         "a large biobank study, consistent with milder bile-duct stress; its effect on transport has not been measured directly."),
        (4, "Svagare export av fosfatidylkolin till gallan.", "ABCB4 (MDR3) vänder fosfatidylkolin ut i gallan, där det bildar blandade "
         "miceller som dämpar gallsyrornas tvättmedelseffekt och håller kolesterolet löst. Förlust av ABCB4-funktion ger kolestatisk "
         "leversjukdom och gallsten med låg fosfolipidhalt. T-allelen för rs61730509 (Thr934) är kopplad till högre ALAT i en stor "
         "biobanksstudie, i linje med mildare stress på gallgångarna; effekten på transporten har inte mätts direkt."),
        (4, "One large biobank signal.", "ALT association at p = 4e-55 in one large biobank analysis."),
        (4, "En stor biobankssignal.", "Koppling till ALAT med p = 4e-55 i en stor biobanksanalys."),
        (3, "GWAS only for this variant.", "Biobank GWAS; no functional assay of this exact change."),
        (3, "Endast GWAS för denna variant.", "Biobanks-GWAS; ingen funktionell analys av just denna förändring."),
        "BILE AND LIVER", "GALLA OCH LEVER",
        ("Verma et al. (2024) - Science", "Million Veteran Program", "Genome-wide association across hundreds of traits.",
         "STRENGTH: Large sample. CRITIQUE: Rare variant with a single strong study; treat the gallstone link as a reasonable inference.",
         "STYRKA: Stort urval. KRITIK: Sällsynt variant med en enda stark studie; se kopplingen till gallsten som en rimlig slutsats."),
        ["39024449"], "ABCB4_BILE"),
    "rs62483572": ev_pair(
        "rs62483572", "EPO", "The Red Cell Hormone", "Hormonet för röda blodkroppar", "Missense Variant (Asp70Asn)", "Missense-variant (Asp70Asn)",
        ["Kidneys", "Bones"], ["Njurar", "Skelett"],
        (4, "Lower erythropoietin signalling.", "Erythropoietin is made by the kidney when oxygen falls and drives red blood cell "
         "production in the bone marrow. The rs62483572 A allele (Asn70) is associated with lower haemoglobin and haematocrit in "
         "several large blood-cell GWAS, pointing to a weaker hormone signal. UniProt also lists this position in familial "
         "erythrocytosis, which runs the opposite way, so the population data is the more reliable guide here."),
        (4, "Svagare erytropoetinsignal.", "Erytropoetin bildas av njuren när syret sjunker och driver produktionen av röda blodkroppar "
         "i benmärgen. A-allelen för rs62483572 (Asn70) är kopplad till lägre hemoglobin och hematokrit i flera stora GWAS av "
         "blodceller, vilket tyder på en svagare hormonsignal. UniProt listar även denna position vid familjär erytrocytos, som går åt "
         "motsatt håll, så befolkningsdatan är den mer tillförlitliga vägledningen här."),
        (5, "Replicated blood-cell GWAS.", "Haemoglobin association at p = 2e-95, replicated in independent cohorts."),
        (5, "Replikerad blodcells-GWAS.", "Koppling till hemoglobin med p = 2e-95, replikerad i oberoende kohorter."),
        (4, "Blood-cell GWAS.", "Large blood-cell trait GWAS."),
        (4, "Blodcells-GWAS.", "Stora GWAS av blodcellsegenskaper."),
        "BLOOD", "BLOD",
        ("Vuckovic et al. (2020) - Cell", "UK Biobank and INTERVAL", "Genome-wide association of blood cell traits.",
         "STRENGTH: Large, replicated effect on measured blood values. CRITIQUE: Rare variant; the disease annotation points the other way.",
         "STYRKA: Stor, replikerad effekt på uppmätta blodvärden. KRITIK: Sällsynt variant; sjukdomsannoteringen pekar åt motsatt håll."),
        ["32888494", "34226706"], "EPO_RED_CELLS"),
}


def load(p):
    return json.load(open(p, encoding="utf-8"))


def save(p, data):
    open(p, "wb").write(json.dumps(data, indent=4, ensure_ascii=False).replace("\n", "\r\n").encode("utf-8"))


def main():
    db = {k: load(p) for k, p in FILES.items()}
    backup = load(BACKUP) if os.path.exists(BACKUP) else {"removed": {}, "replaced": {}}
    for rsid in list(TRAITS) + list(CARRIERS):
        backup["replaced"].setdefault(rsid, copy.deepcopy({n: db[n][rsid] for n in FILES if rsid in db[n]}))
    db["traits"].update(TRAITS)
    db["traits"].update(CARRIERS)
    for rsid in TRAITS:
        db["dd"][rsid], db["sv_dd"][rsid] = DD[rsid], DD_SV[rsid]
        db["ev"][rsid], db["sv_ev"][rsid] = EV[rsid]
    json.dump(backup, open(BACKUP, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    for n, p in FILES.items():
        save(p, db[n])
    print(f"added {len(TRAITS)} traits and {len(CARRIERS)} carrier entries | library now {len(db['traits'])} entries")


if __name__ == "__main__":
    main()
