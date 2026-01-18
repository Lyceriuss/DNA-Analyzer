import json
import os
import glob
from src.loader import load_dna_file
from src.normalizer import resolve_genotype

# CONFIG
TRAITS_FILE = "config/snp_traits.json"
INPUT_DIR = "data/input"

def run_test():
    # 1. Auto-detect the first CSV file found
    csv_files = glob.glob(os.path.join(INPUT_DIR, "*.csv"))
    if not csv_files:
        print(f"❌ No CSV files found in {INPUT_DIR}")
        return
    
    # Pick the first one for testing
    dna_file = csv_files[0]
    print(f"--- STEP 1: LOADING {os.path.basename(dna_file)} ---")
    
    dna_data = load_dna_file(dna_file)
    if not dna_data:
        return

    # 2. Load Traits
    print("\n--- STEP 2: LOADING KNOWLEDGE BASE ---")
    if not os.path.exists(TRAITS_FILE):
        print(f"❌ Error: {TRAITS_FILE} not found. Please create it!")
        return
        
    with open(TRAITS_FILE, 'r', encoding='utf-8') as f:
        traits = json.load(f)
    print(f"✅ Loaded {len(traits)} traits.")

    # 3. Test Normalization
    print("\n--- STEP 3: TESTING NORMALIZER ---")
    matches = 0
    flips = 0
    
    # Test a few known RSIDs
    test_rsids = ["rs1801133", "rs4680", "rs1800562", "rs662"]
    
    print(f"{'RSID':<12} {'USER GT':<10} {'STATUS'}")
    print("-" * 40)

    for rsid in test_rsids:
        if rsid in traits and rsid in dna_data:
            user_gt = dna_data[rsid]
            json_variants = traits[rsid]['variants']
            resolved_gt, flipped = resolve_genotype(user_gt, json_variants)
            
            status = f"✅ MATCH ({resolved_gt})"
            if flipped:
                status += " [FLIPPED]"
                flips += 1
            matches += 1
            print(f"{rsid:<12} {user_gt:<10} {status}")
        else:
            print(f"{rsid:<12} {'--':<10} Not in file")

    print("-" * 40)
    if flips > 0:
        print(f"🎉 SUCCESS! Normalizer fixed {flips} strand mismatches.")
    else:
        print("Run complete. (No flips needed for these specific SNPs).")

if __name__ == "__main__":
    run_test()