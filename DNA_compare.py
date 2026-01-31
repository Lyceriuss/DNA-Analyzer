import pandas as pd
import json
import os

# --- PATHS ---
TRAITS_PATH = "config/snp_traits.json"
CSV_PATH = "data/input/MyHeritage_raw_dna_data_GA.csv"
REPORT_OUTPUT = "final_hardware_alignment.csv"

def audit_forward_strand(csv_path, traits_path):
    # 1. Load DNA CSV (Forward Strand Build 37 confirmed)
    try:
        raw_df = pd.read_csv(csv_path, comment='#', sep=None, engine='python', dtype=str)
        raw_df.columns = [c.upper().strip() for c in raw_df.columns]
        dna_data = pd.Series(raw_df.RESULT.str.strip().values, index=raw_df.RSID.str.strip()).to_dict()
    except Exception as e:
        print(f"❌ Error parsing CSV: {e}")
        return

    # 2. Load Traits JSON
    with open(traits_path, 'r') as f:
        traits_db = json.load(f)

    def normalize(gt):
        return "".join(sorted(str(gt).replace("/", "").replace(" ", "")))

    alignment_results = []

    print(f"🔬 Aligning {len(traits_db)} traits to Forward Strand Reference...")

    for rsid, info in traits_db.items():
        if rsid not in dna_data:
            continue

        user_raw = dna_data[rsid]
        user_std = normalize(user_raw)
        
        json_variants = info.get("variants", {})
        json_keys = [normalize(k) for k in json_variants.keys()]
        
        # Check if the SNP is Ambiguous (A/T or C/G)
        unique_bases = set("".join(json_keys))
        is_ambiguous = (unique_bases == {"A", "T"}) or (unique_bases == {"C", "G"})

        # LOGIC: Because CSV is Forward, JSON MUST be Forward.
        if user_std in json_keys:
            # Match found. Since it's Forward, we can "trust" ambiguous matches now.
            status = "ALIGNED"
            if is_ambiguous:
                status = "ALIGNED_AMBIGUOUS (Verified Forward)"
        else:
            # If no match, it's either a different allele or a strand mismatch in the JSON
            status = "STRAND_MISMATCH (JSON likely Reverse)"

        if status != "ALIGNED":
            alignment_results.append({
                "RSID": rsid,
                "Gene": info.get("gene", "Unknown"),
                "Trait": info.get("trait", "Unknown"),
                "User_CSV_Value": user_raw,
                "JSON_Expected": list(json_variants.keys()),
                "Status": status,
                "Is_Ambiguous": is_ambiguous
            })

    # 3. Export Report
    if alignment_results:
        report_df = pd.DataFrame(alignment_results)
        report_df.to_csv(REPORT_OUTPUT, index=False)
        print(f"\n✅ Alignment Audit Complete.")
        print(f"📄 Found {len(alignment_results)} discrepancies to fix.")
        print(f"👉 Fix 'STRAND_MISMATCH' by flipping JSON keys to Forward.")
        print(f"💾 Report: {REPORT_OUTPUT}")
    else:
        print("\n✅ Perfect Alignment! All JSON traits match Forward Strand CSV.")

if __name__ == "__main__":
    audit_forward_strand(CSV_PATH, TRAITS_PATH)