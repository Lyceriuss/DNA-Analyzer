import json
import os

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
    ]
}

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

if __name__ == "__main__":
    check_coverage()