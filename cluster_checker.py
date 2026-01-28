import json
import os
import pandas as pd

EVIDENCE_PATH = "config/evidence_db.json"

# Defining the specific genes researchers look for in these 3 primary endotypes
ENDOTYPES = {
    "Lipid Partitioning Cluster": [
        "PNPLA3", "LPL", "PPARG", "APOA5", "FADS1", "ANGPTL3", "FABP4", "PLIN1"
    ],
    "Insulin-Glycemic Cluster": [
        "TCF7L2", "SLC2A2", "KCNJ11", "GCK", "MTNR1B", "SLC30A8", "IGF2BP2", "IRS1"
    ],
    "Neuroendocrine (Hunger) Cluster": [
        "MC4R", "FTO", "FOXO1", "BDNF", "LEPR", "POMC", "SH2B1", "PCSK1"
    ],
    "Hypertrophy & Power Cluster": [
        "ACTN3", "MSTN", "ACE", "IGF1", "CKM", "AMPD1", "TRHR", "VDR",
        "IL6",       # Post-exercise inflammation/recovery
        "COL5A1",    # Tendon durability and stiffness
        "PPARGC1A"   # Mitochondrial biogenesis/aerobic capacity
    ],
    "Longevity & DNA Repair Hub": [
        "TP53",      # Guardian of the genome (rs1042523)
        "FOXO3",     # The "Longevity Gene"
        "SIRT1",     # Sirtuin 1 - metabolic aging
        "TERT"       # Telomerase reverse transcriptase
    ]
}



# Primary research SNPs for your missing endotype genes
MISSING_GENES = {
    "ANGPTL3": "rs12130333",  # Key regulator of triglycerides
    # "FABP4":   "rs1054135",   # Adipocyte fatty acid-binding protein - Not found in the CSV
    "IGF2BP2": "rs4402960",   # Strongest link to insulin secretion
    "POMC":    "rs1042522",   # Pro-opiomelanocortin (Hunger/Satiety)
    "SH2B1":   "rs7498665",    # Link to leptin sensitivity
    "ACTN3": "rs1815739", # The R577X 'Sprint' variant
    "MSTN":  "rs1805065", # Myostatin (GDF-8) regulator
    "ACE":   "rs4646994", # Power/Endurance Indel (or proxy rs4341)
    "VDR":   "rs1544410"  ,# BsmI variant linked to muscle strength
    "CKM": "rs8111989",       # Muscle Creatine Kinase (Energy)
    "AMPD1": "rs17602729",    # Muscle Fatigue Threshold
    "IL6": "rs1800795",       # Post-exercise Inflammation
    "PPARGC1A": "rs8192678",  # Mitochondrial Growth
    "COL5A1": "rs12722",       # Tendon/Ligament Durability
    "MSTN": "rs1805065", 
    "IGF1": "rs6214",
    "TRHR": "rs7832552",
    "TERT": "rs2736098"
}

PROXIES = {
    "ACTN3_Proxy": "rs16832327",
    "MSTN_Proxy": "rs11681628",
    "ACE_Proxy_1": "rs4341",
    "ACE_Proxy_2": "rs4343"
}

CSV_PATH = "data/input/MyHeritage_raw_dna_data_GA.csv"

def check_proxies():
    if not os.path.exists(CSV_PATH): return
    df = pd.read_csv(CSV_PATH, comment='#', low_memory=False, names=['RSID', 'CHROM', 'POS', 'RESULT'])
    
    for label, rsid in PROXIES.items():
        match = df[df['RSID'] == rsid]
        if not match.empty:
            print(f"✅ PROXY FOUND: {label} ({rsid}) | Result: {match.iloc[0]['RESULT']}")
        else:
            print(f"❌ PROXY MISSING: {label} ({rsid})")
            
def check_coverage():
    if not os.path.exists(EVIDENCE_PATH):
        print("❌ evidence_db.json not found.")
        return

    with open(EVIDENCE_PATH, 'r', encoding='utf-8') as f:
        db = json.load(f)

    # Extract all genes currently in your evidence database
    current_genes = set()
    for entry in db.values():
        gene = entry.get("variant_identity", {}).get("gene_symbol")
        if gene:
            current_genes.add(gene.upper())

    print("📊 --- OBESITY ENDOTYPE COVERAGE AUDIT --- 📊\n")

    for cluster, target_genes in ENDOTYPES.items():
        found = [g for g in target_genes if g in current_genes]
        missing = [g for g in target_genes if g not in current_genes]
        
        coverage_pct = (len(found) / len(target_genes)) * 100
        
        print(f"🔹 {cluster}")
        print(f"   Coverage: {len(found)}/{len(target_genes)} ({coverage_pct:.1f}%)")
        print(f"   ✅ Found: {', '.join(found) if found else 'None'}")
        print(f"   ❌ Missing: {', '.join(missing) if missing else 'None'}")
        print("-" * 40)
        
        

def check_file():
    if not os.path.exists(CSV_PATH):
        print(f"❌ File not found at {CSV_PATH}")
        return

    print(f"🔍 Searching {os.path.basename(CSV_PATH)} for missing markers...")
    
    # MyHeritage files use commas and skip comment lines starting with #
    try:
        # Load the file, skipping comments
        df = pd.read_csv(CSV_PATH, comment='#', low_memory=False, names=['RSID', 'CHROM', 'POS', 'RESULT'])
        
        found_count = 0
        for gene, rsid in MISSING_GENES.items():
            match = df[df['RSID'] == rsid]
            if not match.empty:
                result = match.iloc[0]['RESULT']
                print(f"✅ FOUND: {gene} ({rsid}) | Your Genotype: {result}")
                found_count += 1
            else:
                print(f"❌ MISSING: {gene} ({rsid})")
        
        print(f"\n📊 Summary: Found {found_count}/{len(MISSING_GENES)} missing markers.")
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")

if __name__ == "__main__":
    check_coverage()
    check_proxies()
    check_file()
    