import json
import os
import re

# CONFIG
TRAITS_PATH = "config/snp_traits.json"
DEEP_DIVE_PATH = "config/deep_dive_content.json"
EVIDENCE_PATH = "config/evidence_db.json"

def validate_coverage():
    print("🔍 Starting Gap Analysis...")

    # 1. Load Data
    if not os.path.exists(TRAITS_PATH):
        print("❌ snp_traits.json not found.")
        return
    with open(TRAITS_PATH, 'r', encoding='utf-8') as f:
        traits = json.load(f)

    if not os.path.exists(DEEP_DIVE_PATH):
        print("❌ deep_dive_content.json not found.")
        return
    with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
        content = json.load(f)

    # 2. Analyze Coverage
    total_traits = len(traits)
    covered_traits = 0
    missing_list = []

    print(f"\n{'RSID':<15} | {'GENE':<20} | {'STATUS'}")
    print("-" * 50)

    for rsid, info in traits.items():
        gene_name = info.get('gene', 'Unknown')
        
        if rsid in content:
            # check if content is actually valid (not empty)
            entry = content[rsid]
            has_text = len(entry.get('data_risk', {}).get('mechanisms', {}).get('how', '')) > 5
            
            if has_text:
                covered_traits += 1
                # print(f"{rsid:<15} | {gene_name:<20} | ✅ OK") 
            else:
                missing_list.append((rsid, gene_name))
                print(f"{rsid:<15} | {gene_name:<20} | ⚠️ EMPTY ENTRY")
        else:
            missing_list.append((rsid, gene_name))
            print(f"{rsid:<15} | {gene_name:<20} | ❌ MISSING")

    # 3. Summary
    coverage_pct = (covered_traits / total_traits) * 100
    
    print("-" * 50)
    print(f"📊 COVERAGE REPORT")
    print(f"   Total Traits: {total_traits}")
    print(f"   Covered:      {covered_traits}")
    print(f"   Missing:      {len(missing_list)}")
    print(f"   Coverage:     {coverage_pct:.1f}%")
    
    if missing_list:
        print("\n📝 MISSING GENES (Add these to `final_system_cleanup.py`):")
        unique_missing_genes = sorted(list(set([x[1] for x in missing_list])))
        print(", ".join(unique_missing_genes))

def _gene_tokens(name):
    # "IL1B (Promoter)" -> {"IL1B", "PROMOTER"}; overlap means the files agree on the gene
    return set(re.split(r"[^A-Z0-9-]+", str(name).upper())) - {""}

def check_gene_consistency():
    """Flags RSIDs where snp_traits, deep_dive_content and evidence_db name different genes."""
    print("\n🧬 Gene Consistency Check...")
    with open(TRAITS_PATH, 'r', encoding='utf-8') as f:
        traits = json.load(f)
    with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
        content = json.load(f)
    with open(EVIDENCE_PATH, 'r', encoding='utf-8') as f:
        evidence = json.load(f)

    mismatches = 0
    for rsid, info in traits.items():
        trait_gene = info.get('gene', '')
        others = {}
        if rsid in content:
            entry = content[rsid]
            others['deep_dive'] = (entry.get('data_risk') or {}).get('gene') or (entry.get('data_strength') or {}).get('gene')
        if rsid in evidence:
            others['evidence'] = evidence[rsid].get('variant_identity', {}).get('gene_symbol')

        for source, gene in others.items():
            if gene and not (_gene_tokens(trait_gene) & _gene_tokens(gene)):
                mismatches += 1
                print(f"   ⚠️ {rsid:<12} snp_traits: {trait_gene:<15} {source}: {gene}")

    # Aliases (BCMO1/BCO1, TNF-alpha/TNF...) also show up here; review by hand
    print(f"   {mismatches} mismatches found.")

if __name__ == "__main__":
    validate_coverage()
    check_gene_consistency()