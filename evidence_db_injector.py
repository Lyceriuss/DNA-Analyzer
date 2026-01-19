import json
import os

# CONFIG
EVIDENCE_PATH = "config/evidence_db.json"

# BATCH 2 DATA: FTO, BDNF, VDR
BATCH_ENTRIES = {
    "FTO": {
        "rsid": "rs9939609",
        "metrics": {
            "mechanistic_impact": {
                "score": 5,
                "rationale": "Mechanism recently solved: It acts as a long-range switch for IRX3/IRX5 genes, shifting fat cells from 'burning' to 'storing'.",
                "detail": "For years, FTO was a mystery. We now know the risk variant disrupts a repressor binding site (ARID5B), unlocking the IRX3 and IRX5 genes. This forces adipocytes (fat cells) to store lipids as white fat rather than burning them as heat (thermogenesis). It is a fundamental shift in cellular energy thermodynamics."
            },
            "study_quality": {
                "score": 5,
                "rationale": "The single strongest genetic signal for BMI. Replicated in hundreds of thousands of people globally.",
                "detail": "Since its discovery in 2007, FTO has been replicated in every major GWAS of obesity. The effect is detectable in children as young as 7. The p-values are often the most significant in the entire genome for body weight (e.g., p < 10^-100)."
            },
            "methodology": {
                "score": 5,
                "rationale": "Supported by CRISPR-Cas9 editing studies proving causality, not just association.",
                "detail": "While initial studies were observational (GWAS), recent work (Claussnitzer et al.) used CRISPR to edit the single nucleotide in human cells, reversing the metabolic signature. This moves the methodology score to 5/5 because causal direction was proven in vitro."
            }
        },
        "consensus_label": "GWAS GOLD STANDARD",
        "methodology_audit": [
            {
                "study": "Frayling et al. (2007) - Science",
                "type": "GWAS Discovery",
                "population": "N = 38,759 (Discovery + Replication)",
                "methods": "First major GWAS identifying rs9939609. Correlated genotype with BMI and Type 2 Diabetes risk.",
                "critique": "STRENGTH: The landmark study that defined modern obesity genetics. WEAKNESS: Initially lacked mechanistic explanation (which came later).",
                "score_contribution": "Study Quality (5/5)"
            },
            {
                "study": "Claussnitzer et al. (2015) - NEJM",
                "type": "Mechanistic Editing (CRISPR)",
                "population": "Human Adipocyte Progenitors",
                "methods": "Used CRISPR-Cas9 to switch the T allele to C in human cells. Measured thermogenesis and mitochondrial function.",
                "critique": "STRENGTH: Proved direct causality. Editing one letter restored 'beige' fat burning capabilities. WEAKNESS: In vitro model, but validated in mouse models.",
                "score_contribution": "Mechanistic Impact (5/5)"
            },
            {
                "study": "Kilpeläinen et al. (2011) - PLOS Med",
                "type": "Meta-Analysis (Interaction)",
                "population": "N = 218,000 (Adults)",
                "methods": "Examined if physical activity blunts the FTO effect. Found exercise reduces genetic risk by ~30%.",
                "critique": "STRENGTH: Massive sample size. Proved lifestyle can modulate genetic expression (Epigenetics). WEAKNESS: Self-reported physical activity is often inaccurate.",
                "score_contribution": "Methodology (4/5)"
            }
        ],
        "citations": [
            "PMID:17434869",
            "PMID:26287746",
            "PMID:22069379"
        ]
    },
    "BDNF": {
        "rsid": "rs6265",
        "metrics": {
            "mechanistic_impact": {
                "score": 5,
                "rationale": "The Val66Met variant physically prevents the growth factor from being secreted by neurons.",
                "detail": "The 'Met' substitution interferes with the intracellular trafficking of the BDNF protein. It fails to get sorted into secretory granules, meaning less BDNF is released when neurons fire. This directly reduces synaptic plasticity and hippocampus volume."
            },
            "study_quality": {
                "score": 4,
                "rationale": "Strong neurobiological evidence, but human cognitive studies show variable effect sizes.",
                "detail": "Molecular studies are definitive (5/5). However, associations with 'Depression' or 'Memory' in humans are highly heterogeneous. The effect is real, but it is often drowned out by environmental factors (stress, sleep), making the 'Study Quality' for specific outcomes slightly lower than FTO."
            },
            "methodology": {
                "score": 4,
                "rationale": "Reliance on fMRI and neuropsychological testing, which are less precise than serum biomarkers.",
                "detail": "We cannot easily measure brain BDNF levels in living humans (serum BDNF is a poor proxy). Therefore, most evidence relies on volumetric MRI (hippocampus size) or memory tests, which have higher measurement error."
            }
        },
        "consensus_label": "NEURO-MECHANISTIC",
        "methodology_audit": [
            {
                "study": "Egan et al. (2003) - Cell",
                "type": "Functional Discovery",
                "population": "N = 641 (Humans) + In Vitro Neurons",
                "methods": "Tested memory (Wisconsin Card Sort) and visualized protein secretion in cultured neurons.",
                "critique": "STRENGTH: Elegantly combined human memory scores with cellular proof of secretion defects. WEAKNESS: Human cohort was relatively small by modern standards.",
                "score_contribution": "Mechanistic Impact (5/5)"
            },
            {
                "study": "Frodl et al. (2007) - Arch Gen Psych",
                "type": "MRI Volumetric Study",
                "population": "N = 60 (Depressed) + 60 (Control)",
                "methods": "Measured Hippocampal volume via MRI over 3 years. Met carriers showed greater atrophy.",
                "critique": "STRENGTH: Objective structural measurement of the brain. WEAKNESS: Small sample size (N=120 total) raises risk of replication failure.",
                "score_contribution": "Methodology (4/5)"
            }
        ],
        "citations": [
            "PMID:12553913",
            "PMID:17548744"
        ]
    },
    "VDR": {
        "rsid": "rs2228570",
        "metrics": {
            "mechanistic_impact": {
                "score": 5,
                "rationale": "A start-codon polymorphism that creates a longer or shorter receptor protein (FokI variant).",
                "detail": "This variant (FokI) is located in the start codon (ATG). The 'f' (T) allele shifts the start site, creating a receptor that is 3 amino acids longer. The shorter 'F' (C) version is actually *more* efficient at binding Vitamin D and transcribing genes. This is a structural change in the receptor itself."
            },
            "study_quality": {
                "score": 3,
                "rationale": "Massive conflict in literature regarding cancer/immunity outcomes.",
                "detail": "While the receptor mechanics are known, linking VDR genotypes to outcomes like 'Breast Cancer' or 'Tuberculosis' has produced conflicting meta-analyses. The signal is weak and heavily dependent on the population's baseline Vitamin D levels (Interaction), lowering the consensus score."
            },
            "methodology": {
                "score": 4,
                "rationale": "Transcriptional assays are solid, but clinical trials often fail to control for solar exposure.",
                "detail": "In vitro studies measuring gene transcription rates are solid (4/5). However, human studies often fail because they rely on single-point Vitamin D blood tests or fail to account for latitude/sun exposure, adding noise to the genetic signal."
            }
        },
        "consensus_label": "BIOCHEMICAL FACTOR",
        "methodology_audit": [
            {
                "study": "Whitfield et al. (2001) - Mol Endocrinol",
                "type": "Transcriptional Assay",
                "population": "Cell Lines",
                "methods": "Compared the 'Long' (f) vs 'Short' (F) receptor's ability to drive gene expression using a reporter gene.",
                "critique": "STRENGTH: Proved the Short (F) variant is 1.7x more active transcriptionally. WEAKNESS: In vitro only; doesn't account for whole-body homeostasis.",
                "score_contribution": "Mechanistic Impact (5/5)"
            },
            {
                "study": "Raimondi et al. (2009) - Carcinogenesis",
                "type": "Meta-Analysis (Cancer)",
                "population": "N = 20,000+ (Cases)",
                "methods": "Pooled analysis of VDR variants and cancer risk.",
                "critique": "STRENGTH: Large sample size. WEAKNESS: Found only weak/null associations, highlighting the difficulty of linking this single gene to complex disease without nutrient data.",
                "score_contribution": "Study Quality (3/5)"
            }
        ],
        "citations": [
            "PMID:11435610",
            "PMID:19357199"
        ]
    }
}

def inject_batch_2():
    print("🔬 Injecting BATCH 2 (FTO, BDNF, VDR)...")

    if os.path.exists(EVIDENCE_PATH):
        try:
            with open(EVIDENCE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                db = json.loads(content) if content.strip() else {}
        except json.JSONDecodeError:
            print("⚠️  JSON file corrupted. Starting fresh.")
            db = {}
    else:
        db = {}

    # Update Database
    for gene, data in BATCH_ENTRIES.items():
        db[gene] = data
        print(f"   + Injected {gene} ({data['rsid']})")

    with open(EVIDENCE_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4)

    print("✅ Batch 2 Injection Complete.")

if __name__ == "__main__":
    inject_batch_2()