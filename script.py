import json
import os

# --- PATHS (Based on your script) ---
EVIDENCE_PATH = "config/evidence_db.json"

# --- THRESHOLDS ---
THRESHOLDS = {
    "mechanistic_detail": 250,
    "study_detail": 150,
    "critique": 380
}

VALID_ORGANS = {
    "Brain", "Eyes", "Thyroid", "Heart", "Lungs", "Liver", "Stomach", 
    "Pancreas", "Spleen", "Kidneys", "Intestines", "Bladder", 
    "Ovaries", "Uterus", "Testes", "Prostate", "Skin", "Bones", "Muscles"
}

def audit_database():
    if not os.path.exists(EVIDENCE_PATH):
        print(f"❌ Error: {EVIDENCE_PATH} not found.")
        return

    with open(EVIDENCE_PATH, 'r', encoding='utf-8') as f:
        db = json.load(f)

    print(f"🔍 Starting Audit of {len(db)} entries...\n")
    
    seen_rsids = {}  # To check for duplicate RSIDs
    total_issues = 0

    for key, data in db.items():
        rsid = data.get("rsid", "Unknown")
        issues = []

        # 1. Duplication Check
        if rsid in seen_rsids:
            issues.append(f"DUPLICATE RSID: Also exists as key '{seen_rsids[rsid]}'")
        seen_rsids[rsid] = key

        # 2. Character Limit Checks
        # Mechanistic Detail
        mech_text = data.get("metrics", {}).get("mechanistic_impact", {}).get("detail", "")
        if len(mech_text) < THRESHOLDS["mechanistic_detail"]:
            issues.append(f"SHORT MECHANISTIC: {len(mech_text)}/{THRESHOLDS['mechanistic_detail']}")

        # Study Detail
        study_text = data.get("metrics", {}).get("study_quality", {}).get("detail", "")
        if len(study_text) < THRESHOLDS["study_detail"]:
            issues.append(f"SHORT STUDY: {len(study_text)}/{THRESHOLDS['study_detail']}")

        # Critiques (Methodology Audit)
        audits = data.get("methodology_audit", [])
        for i, audit in enumerate(audits):
            crit_text = audit.get("critique", "")
            if len(crit_text) < THRESHOLDS["critique"]:
                issues.append(f"SHORT CRITIQUE #{i+1}: {len(crit_text)}/{THRESHOLDS['critique']}")

        # 3. Organ Validation
        for organ in data.get("affected_organs", []):
            if organ not in VALID_ORGANS:
                issues.append(f"INVALID ORGAN: '{organ}'")

        # Report findings for this entry
        if issues:
            total_issues += len(issues)
            print(f"🛑 Issues in {key} ({rsid}):")
            for issue in issues:
                print(f"   - {issue}")

    print("-" * 30)
    if total_issues == 0:
        print("✅ AUDIT COMPLETE: No issues found. Database is healthy.")
    else:
        print(f"❌ AUDIT COMPLETE: Found {total_issues} issues.")

if __name__ == "__main__":
    audit_database()