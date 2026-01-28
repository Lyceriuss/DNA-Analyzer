import json
import os
from collections import Counter

EVIDENCE_PATH = "config/evidence_db.json"

def analyze_connections():
    if not os.path.exists(EVIDENCE_PATH):
        print("❌ Database not found.")
        return

    with open(EVIDENCE_PATH, 'r', encoding='utf-8') as f:
        db = json.load(f)

    organ_map = {}
    molecule_map = {}
    gene_to_rsid = {}

    for key, data in db.items():
        gene = data.get("variant_identity", {}).get("gene_symbol", "Unknown")
        organs = data.get("affected_organs", [])
        
        # 1. Map Organ Influence
        for organ in organs:
            if organ not in organ_map:
                organ_map[organ] = []
            organ_map[organ].append(gene)

        # 2. Map Molecule Overlaps (Upstream/Downstream)
        connections = data.get("metabolic_connections", {})
        all_mols = connections.get("upstream_requirements", []) + connections.get("downstream_impacts", [])
        
        for mol_data in all_mols:
            mol_name = mol_data.get("molecule", "Unknown").title()
            if mol_name not in molecule_map:
                molecule_map[mol_name] = []
            molecule_map[mol_name].append(gene)

    # --- REPORTING ---
    print("📊 --- SYSTEMIC CONNECTIVITY REPORT --- 📊\n")

    # Top 3 "Multi-System" Genes
    gene_counts = Counter([g for genes in organ_map.values() for g in genes])
    print("🧬 MASTER REGULATORS (Genes affecting most organs):")
    for gene, count in gene_counts.most_common(5):
        print(f"   - {gene}: Influences {count} organs")

    print("\n🫀 ORGAN VULNERABILITY (Highest genetic density):")
    sorted_organs = sorted(organ_map.items(), key=lambda x: len(x[1]), reverse=True)
    for organ, genes in sorted_organs[:5]:
        print(f"   - {organ}: {len(set(genes))} genes ({', '.join(list(set(genes))[:5])}...)")

    print("\n🧪 METABOLIC HUBS (Molecules with highest overlap):")
    sorted_mols = sorted(molecule_map.items(), key=lambda x: len(x[1]), reverse=True)
    for mol, genes in sorted_mols[:8]:
        if len(set(genes)) > 1:
            print(f"   - {mol}: Influenced by {len(set(genes))} genes ({', '.join(list(set(genes)))})")

if __name__ == "__main__":
    analyze_connections()