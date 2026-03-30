import pandas as pd
import json
import os

# --- PATHS ---
TRAITS_PATH = "config/snp_traits.json"
CSV_PATH = "data/input/MyHeritage_raw_dna_data_GA.csv"

def run_final_health_check():
    # 1. Load DNA
    try:
        raw_df = pd.read_csv(CSV_PATH, comment='#', sep=None, engine='python', dtype=str)
        raw_df.columns = [c.upper().strip() for c in raw_df.columns]
        dna_data = pd.Series(raw_df.RESULT.str.strip().values, index=raw_df.RSID.str.strip()).to_dict()
    except Exception:
        print("❌ Could not load CSV.")
        return

    # 2. Load JSON
    with open(TRAITS_PATH, 'r') as f:
        traits_db = json.load(f)

    def normalize(gt):
        return "".join(sorted(str(gt).replace("/", "").replace(" ", "")))

    failures = []
    
    print(f"🏁 Checking {len(traits_db)} markers for full hardware compatibility...")

    for rsid, info in traits_db.items():
        if rsid not in dna_data:
            continue

        user_val = normalize(dna_data[rsid])
        json_keys = [normalize(k) for k in info['variants'].keys()]
        
        if user_val not in json_keys:
            failures.append({
                "RSID": rsid,
                "CSV": user_val,
                "JSON": json_keys
            })

    if not failures:
        print("\n✅ PERFECT ALIGNMENT: Every letter in your DNA file matches your Trait Database.")
        print("You can now generate your Character String (A-Z) with 100% confidence.")
    else:
        print(f"\n❌ FOUND {len(failures)} REMAINING MISMATCHES.")
        print("These likely have structural errors (e.g. your DNA says 'G' but the SNP is 'A/C').")
        print(pd.DataFrame(failures))

if __name__ == "__main__":
    run_final_health_check()