import json
import os
import re
import pandas as pd
from src.loader import load_dna_file
from src.normalizer import resolve_genotype
from src.proxy_handler import apply_proxies

# --- CONFIG PATHS ---
PROXIES_PATH = "config/proxies.json"
MUSCLE_LOGIC = "config/muscle_logic_gates_db.json"
TRAITS_DB_PATH = "config/evidence_db.json"
CSV_PATH = "data/input/MyHeritage_raw_dna_data_GA.csv"

def evaluate_condition(logic_str, normalized_dna):
    """Evaluates logic strings against normalized DNA data."""
    # Find all rsXXXX == 'YY' patterns in the logic string
    patterns = re.findall(r"(rs\d+) == '([ACGTDI]+)'", logic_str)
    
    evaluated_str = logic_str
    for rsid, target_gt in patterns:
        user_val = normalized_dna.get(rsid, "MISSING")
        # Direct comparison after standardization
        match = (user_val == target_gt)
        evaluated_str = evaluated_str.replace(f"{rsid} == '{target_gt}'", str(match))
    
    evaluated_str = evaluated_str.replace("AND", "and").replace("OR", "or")
    
    try:
        return eval(evaluated_str, {"__builtins__": None}, {})
    except Exception as e:
        print(f"⚠️ Logic error in [{logic_str}]: {e}")
        return False

def run_integrated_pipeline(dna_path, logic_path, proxies_path, traits_path):
    # 1. Load DNA
    dna_raw = load_dna_file(dna_path)
    if not dna_raw: return

    # 2. Load Support Files
    if not os.path.exists(logic_path) or not os.path.exists(traits_path):
        print("❌ Error: Missing configuration files.")
        return

    with open(logic_path, 'r') as f: logic_gates = json.load(f)
    with open(traits_path, 'r') as f: traits_db = json.load(f)

    # 3. Apply Proxies (Pass the path string to avoid the Type Error)
    dna_patched = apply_proxies(dna_raw, proxies_path)

    # 4. Normalize DNA for Logic Gates
    normalized_dna = {}
    for rsid, user_gt in dna_patched.items():
        if rsid in traits_db:
            # Resolve strand flips and sort genotypes
            matched_gt, _ = resolve_genotype(user_gt, traits_db[rsid]['variants'])
            if matched_gt:
                normalized_dna[rsid] = matched_gt
        else:
            # Basic normalization for SNPs not in evidence_db
            normalized_dna[rsid] = "".join(sorted(user_gt.replace("/", "").replace(" ", "")))

    print("\n🏁 --- GENOMIC PIPELINE AUDIT: ACTIVE CONSTRAINTS --- 🏁\n")

    for station_id, categories in logic_gates.items():
        print(f"📍 {station_id.replace('_', ' ').title()}")
        found_active = False
        
        for category, rules in categories.items():
            for rule_id, rule_data in rules.items():
                if evaluate_condition(rule_data['logic'], normalized_dna):
                    print(f"  ✅ [TRIGGERED]: {rule_id.replace('_', ' ').upper()}")
                    print(f"     👉 Instruction: {rule_data['instruction']}")
                    found_active = True
        
        if not found_active:
            print("  ⚪ No hardware constraints triggered.")
        print("-" * 60)

if __name__ == "__main__":
    run_integrated_pipeline(CSV_PATH, MUSCLE_LOGIC, PROXIES_PATH, TRAITS_DB_PATH)