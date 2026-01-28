import json
import os
import random
from script import NEW_ENTRIES

# --- CONFIGURATION ---
EVIDENCE_DIR = "config"
EVIDENCE_FILE = "evidence_db.json"
EVIDENCE_PATH = os.path.join(EVIDENCE_DIR, EVIDENCE_FILE)

# Guardrail Thresholds
THRESHOLDS = {
    "mechanistic_detail": 250,
    "study_detail": 300,
    "critique": 400
}

# Strict Organ List
VALID_ORGANS = {
    "Brain", "Eyes", "Thyroid", "Heart", "Lungs", "Liver", "Stomach", 
    "Pancreas", "Spleen", "Kidneys", "Intestines", "Bladder", 
    "Ovaries", "Uterus", "Testes", "Prostate", "Skin", "Bones", "Muscles"
}

def inject_batch():
    
    print(f"🔬 Injecting BATCH")
    
    if os.path.exists(EVIDENCE_PATH):
        try:
            with open(EVIDENCE_PATH, 'r') as f: db = json.load(f)
        except: db = {}
    else:
        if not os.path.exists(EVIDENCE_DIR): os.makedirs(EVIDENCE_DIR)
        db = {}

    for key, data in NEW_ENTRIES.items():
        # Validate
        errors = []
        for organ in data.get("affected_organs", []):
            if organ not in VALID_ORGANS: 
                errors.append(f"❌ INVALID ORGAN: '{organ}'")
        
        audits = data.get("methodology_audit", [])
        if not audits:
            errors.append("❌ MISSING AUDIT")
        else:
            for i, audit in enumerate(audits):
                if len(audit.get("critique", "")) < THRESHOLDS["critique"]:
                    errors.append(f"⚠️  WEAK CRITIQUE #{i+1} ({len(audit.get('critique', ''))} chars)")

        if errors:
            print(f"🛑 BLOCKED {key}:")
            for e in errors: print(f"   {e}")
        else:
            db[key] = data
            print(f"   ✨ Injected {key} ({data['rsid']})")

    with open(EVIDENCE_PATH, 'w') as f: json.dump(db, f, indent=4)
    print("✅ Batch Write Complete.")

# --- GAP ANALYSIS ---
def find_next_targets():
    print("\n🔍 GAP ANALYSIS (Checking snp_traits.json)...")
    traits_data = {}
    
    TRAITS_PATHS = ["snp_traits.json", "src/data/snp_traits.json", "config/snp_traits.json"]
    for path in TRAITS_PATHS:
        data = load_json(path)
        if data:
            traits_data = data
            print(f"   ✅ Loaded traits from {path}")
            break
            
    if not traits_data:
        print("   ❌ Could not find snp_traits.json")
        return

    db = load_json(EVIDENCE_PATH)
    existing_rsids = set()
    for k, v in db.items():
        if 'rsid' in v: existing_rsids.add(v['rsid'])
    
    all_traits_rsids = set(traits_data.keys())
    missing_rsids = list(all_traits_rsids - existing_rsids)
    
    print(f"   📊 Coverage: {len(existing_rsids)} / {len(all_traits_rsids)} entries.")
    
    if missing_rsids:
        print("\n🎲 SELECTING 5 NEW TARGETS:")
        random.shuffle(missing_rsids)
        targets = missing_rsids[:5]
        
        for rsid in targets:
            gene = traits_data[rsid].get('gene', 'Unknown')
            trait = traits_data[rsid].get('trait', 'Unknown')
            print(f"   👉 [Target] RSID: {rsid} | Gene: {gene} | Trait: {trait}")

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

if __name__ == "__main__":
    inject_batch()
    find_next_targets()
