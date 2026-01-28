import pandas as pd
import json
import os

# The Comprehensive Hunt List
HUNT_LIST = {
    "CLOCK": "rs1801260",
    "MTNR1B_Sleep": "rs10830963",
    "ASMT": "rs444697",
    "CYP1A2_Caffeine": "rs762551",
    "GSTP1_Detox": "rs1695",
    "SOD2_Antioxidant": "rs4880",
    "COMT_Warrior": "rs4680",
    "BCMO1_VitA": "rs717660",
    "FUT2_B12": "rs601338",
    "SLC23A1_VitC": "rs33972313",
    "NBPF3_B6": "rs4654748",
    "TNF_Alpha": "rs1800629",
    "CRP": "rs1205",
    "SIRT1": "rs12778366",
    "FOXO3_Longevity": "rs2802295",
    "IGF1": "rs6214",           # Circulating IGF-1 levels
    "IGF1R": "rs2229765",       # IGF-1 Receptor sensitivity
    "AR_Genomics": "rs6263",    # Androgen Receptor sensitivity
    "MSTN_Muscle": "rs1805065", # Myostatin (The growth brake)
    "PPARA": "rs4253778",       # Peroxisome proliferator-activated receptor alpha
    "ESR1": "rs2234693" ,        # Estrogen Receptor (Crucial for tendon/bone health)
    "SHBG_Free_T": "rs6259",    # Free Testosterone availability
    "LEP_Leptin": "rs7799039",  # Satiety hormone production
    "ADRB2_FatMobil": "rs1042713", # Fat burning during exercise
    "BDNF_Neuro": "rs6265",     # Neuroplasticity and focus
    "VDR_FokI": "rs2228570",    # Muscle strength variant
    "ALDH2_Alcohol": "rs671"    # The 'Asian Flush' / Alcohol detox gene
}

CSV_PATH = "data/input/MyHeritage_raw_dna_data_GA.csv"
TRAITS_PATH = "config/snp_traits.json"

def perform_sync_audit():
    # 1. Load Library
    if not os.path.exists(TRAITS_PATH):
        print("❌ snp_traits.json not found.")
        return
    with open(TRAITS_PATH, 'r') as f:
        traits_db = json.load(f)

    # 2. Load CSV
    if not os.path.exists(CSV_PATH):
        print("❌ CSV file not found.")
        return
    df = pd.read_csv(CSV_PATH, comment='#', low_memory=False, names=['RSID', 'CHROM', 'POS', 'RESULT'])

    print(f"{'GENE':<15} | {'RSID':<12} | {'IN CSV?':<8} | {'IN LIBRARY?':<12} | {'ACTION'}")
    print("-" * 75)

    for label, rsid in HUNT_LIST.items():
        # Check CSV
        csv_match = df[df['RSID'] == rsid]
        has_csv = not csv_match.empty
        genotype = csv_match.iloc[0]['RESULT'] if has_csv else "N/A"

        # Check Library (checking keys in your snp_traits.json)
        has_library = rsid in traits_db

        # Determine Action
        if has_csv and has_library:
            action = "✅ READY"
        elif has_csv and not has_library:
            action = "⭐ PRIORITY: Add to Library"
        elif not has_csv and has_library:
            action = "⚠️ Library exists, but no user data"
        else:
            action = "❌ Skip (No data/No entry)"

        csv_status = f"YES ({genotype})" if has_csv else "NO"
        lib_status = "YES" if has_library else "NO"
        
        print(f"{label:<15} | {rsid:<12} | {csv_status:<8} | {lib_status:<12} | {action}")

if __name__ == "__main__":
    perform_sync_audit()