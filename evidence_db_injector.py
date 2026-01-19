import json
import os

# CONFIG
EVIDENCE_PATH = "config/evidence_db.json"

# THE FINAL SCHEMA: V4 SCORING + RSID ANCHOR
NEW_ENTRY = {
    "APOA5": {
        "rsid": "rs662799",
        "metrics": {
            "mechanistic_impact": {
                "score": 5,
                "rationale": "The biological pathway is fully mapped and the effect size is massive.",
                "detail": "APOA5 is physically required for Lipoprotein Lipase (LPL) to bind to fat particles. Without it, the enzyme falls off. This isn't a 'nudge'—it's a structural failure in fat metabolism, raising triglycerides by 20-30%."
            },
            "study_quality": {
                "score": 5,
                "rationale": "Supported by the 'Gold Standard' of genetic research: The Global Lipids Genetics Consortium.",
                "detail": "Replicated in >188,000 participants across diverse ancestries. The P-value is statistical certainty (1 x 10^-100)."
            },
            "methodology": {
                "score": 4,
                "rationale": "The main effect studies use precise genotyping and serum assays (5/5). However, the lifestyle interaction studies often rely on Food Frequency Questionnaires.",
                "detail": "While the genetic link to blood lipids is indisputable (measured via serum assay), the studies linking specific dietary interventions (like Omega-6 intake) rely on self-reported diet data (FFQs), which are prone to user error, pulling the average methodology score down slightly."
            }
        },
        
        "consensus_label": "GWAS GOLD STANDARD",
        
        "methodology_audit": [
            {
                "study": "Willer et al. (2013) - Global Lipids Genetics Consortium",
                "type": "GWAS Meta-Analysis",
                "population": "N = 188,577 (European, East Asian, South Asian, African)",
                "methods": "Aggregated genotype data from ~60 independent cohorts. Fasting serum lipids measured via standard enzymatic assays.",
                "critique": "STRENGTH: Massive sample size eliminates statistical noise. WEAKNESS: GWAS proves correlation, not causation (though P-values were definitive).",
                "score_contribution": "Study Quality (5/5)"
            },
            {
                "study": "Pennacchio et al. (2001) - Science",
                "type": "Functional Transgenic Model",
                "population": "Murine (Mice) + Human Validation Cohort (N=631)",
                "methods": "Created APOA5 knockout mice (deleted gene) and transgenic mice (added human gene) compared triglyceride phenotype.",
                "critique": "STRENGTH: Gold-standard proof of mechanism. Knockout mice had 400% higher TG. WEAKNESS: Human validation cohort was small by modern standards.",
                "score_contribution": "Mechanistic Impact (5/5)"
            },
            {
                "study": "Lai et al. (2006) - J Nutr",
                "type": "Gene-Diet Interaction (Observational)",
                "population": "N = 896 (Boston Puerto Rican Health Study)",
                "methods": "Cross-sectional analysis. Genotyped T-1131C variant (rs662799). Diet assessed via Food Frequency Questionnaire (FFQ).",
                "critique": "WEAKNESS: Relied on self-reported diet (FFQ), which is notoriously unreliable. Interaction effects are difficult to replicate. This lowers the specific 'Methodology' score for the diet advice component.",
                "score_contribution": "Methodology (2/5)"
            }
        ],
        "citations": [
            "PMID:24097068",
            "PMID:11588264",
            "PMID:16702326"
        ]
    }
}

def inject_evidence_final():
    print("🔬 Injecting FINAL APOA5 EVIDENCE (with RSID)...")

    if os.path.exists(EVIDENCE_PATH):
        try:
            with open(EVIDENCE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    db = {}
                else:
                    db = json.loads(content)
        except json.JSONDecodeError:
            print("⚠️  JSON file corrupted or empty. Starting with a fresh database.")
            db = {}
    else:
        db = {}

    # Update
    db.update(NEW_ENTRY)

    with open(EVIDENCE_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4)

    print("✅ Evidence Locker Updated.")
    print(f"   Gene: APOA5")
    print(f"   RSID: {NEW_ENTRY['APOA5']['rsid']} (Linked successfully)")
    print("   Data is now ready for the Report Engine.")

if __name__ == "__main__":
    inject_evidence_final()