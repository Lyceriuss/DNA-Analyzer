import json
import os

# CONFIG
TRAITS_PATH = "config/snp_traits.json"

# THE "HIGHLANDER" LIST
# For each gene, we pick the ONE best RSID to represent it.
# Any other RSID mapped to this gene name will be deleted.
PRIORITY_MAP = {
    "ALDH2": "rs671",          # The famous Asian Flush marker
    "IL1B": "rs16944",         # The primary promoter variant
    "VEGFA": "rs2010963",      # The secretion regulator
    "COMT": "rs4680",          # The Val158Met Warrior/Worrier marker
    "IL6": "rs1800795",        # The primary inflammation marker
    "TCF7L2": "rs7903146",     # The primary Diabetes marker
    "MTHFR": "rs1801133",      # C677T (We will keep A1298C separate if needed)
    "VDR": "rs1544410",        # BsmI
    "TNF": "rs1800629",        # TNF-alpha
    "SOD2": "rs4880",          # The mitochondrial marker
    "ACTN3": "rs1815739",      # The Sprinter Gene
    "APOE": "rs429358"         # The Alzheimer's risk marker (part 1 of haplotype)
}

def clean_database():
    print("⚔️  Starting Highlander Deduplication (There Can Be Only One)...")

    if not os.path.exists(TRAITS_PATH):
        print("❌ snp_traits.json not found.")
        return

    with open(TRAITS_PATH, 'r', encoding='utf-8') as f:
        traits = json.load(f)

    # 1. Reverse Map: Group RSIDs by Gene Name
    gene_to_rsids = {}
    for rsid, info in traits.items():
        # Normalize name (remove parenthesis details for grouping)
        gene_base = info.get('gene', '').split('(')[0].strip()
        
        if gene_base not in gene_to_rsids:
            gene_to_rsids[gene_base] = []
        gene_to_rsids[gene_base].append(rsid)

    # 2. Purge Duplicates
    deleted_count = 0
    
    for gene, rsids in gene_to_rsids.items():
        # If we have a priority rule for this gene
        if gene in PRIORITY_MAP:
            target_rsid = PRIORITY_MAP[gene]
            
            # Check if we have multiple entries and one of them is the target
            if len(rsids) > 1 and target_rsid in rsids:
                print(f"   ⚠️  Duplicate found for {gene}: {rsids}")
                
                # Remove everyone EXCEPT the target
                for rs_to_remove in rsids:
                    if rs_to_remove != target_rsid:
                        print(f"      🗑️  Deleting inferior marker: {rs_to_remove}")
                        del traits[rs_to_remove]
                        deleted_count += 1
                        
    # 3. Handle Special Case: MTHFR (Keep both C677T and A1298C, delete others)
    if "MTHFR" in gene_to_rsids:
        allowed = ["rs1801133", "rs1801131"]
        for rs in gene_to_rsids["MTHFR"]:
            if rs not in allowed and rs in traits:
                print(f"      🗑️  Deleting extra MTHFR marker: {rs}")
                del traits[rs]
                deleted_count += 1

    # 4. Save
    with open(TRAITS_PATH, 'w', encoding='utf-8') as f:
        json.dump(traits, f, indent=4)

    print(f"\n✅ Cleanup Complete. Deleted {deleted_count} duplicate entries.")
    print("   Your report will now show only ONE result per gene.")

if __name__ == "__main__":
    clean_database()