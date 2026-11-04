import json
import os
import pandas as pd
from src.loader import load_dna_file
from src.normalizer import resolve_genotype, normalize_variant_keys
from src.domain_mapper import map_system_to_domain
from src.proxy_handler import apply_proxies

def run_analysis(dna_filepath, traits_filepath):
    # 1. Load DNA
    dna_data = load_dna_file(dna_filepath)
    if not dna_data: return pd.DataFrame() 
    
   # dna_data = apply_proxies(dna_data)
    
    # 2. Load Traits
    try:
        with open(traits_filepath, 'r', encoding='utf-8') as f:
            traits_db = json.load(f)
    except Exception as e:
        print(f"❌ Error loading traits JSON: {e}")
        return pd.DataFrame()

    results = []
    
    # 3. Analyze
    print("🔍 Analyzing Genotypes...")
    for rsid, info in traits_db.items():
        if rsid not in dna_data: continue

        user_gt = dna_data[rsid]

        # Normalize both sides: the user genotype is sorted inside resolve_genotype,
        # so the JSON keys must be sorted too ("GA" in the DB would never match otherwise)
        variants = normalize_variant_keys(info['variants'])
        scores = normalize_variant_keys(info['scores'])
        matched_gt, _ = resolve_genotype(user_gt, variants)

        if matched_gt:
            score = scores.get(matched_gt, 5)
            impact = info.get('impact', 'Medium')
            interpretation = variants.get(matched_gt, "Unknown")
            
            results.append({
                "RSID": rsid,
                "Gene": info.get('gene', 'Unknown'),
                "System": info.get('system', 'Other'),
                "Domain": map_system_to_domain(info.get('system', '')),
                "Trait": info.get('trait', 'Unknown'),
                "Impact": impact,
                "Result": matched_gt,      
                "User_Genotype": user_gt,
                "Score": float(score),
                "Interpretation": interpretation,
                # "carrier" / "rare_variant" entries are reported on their own page, not scored
                "Category": info.get("category", "trait"),
                # --- NEW: Preserve Context for the Report ---
                "Score_Map": scores,      # { "CC": 9, "CT": 5, "TT": 2 }
                "Variant_Map": variants   # { "CC": "Good", "TT": "Bad" }
            })

    # 4. Create DataFrame
    df = pd.DataFrame(results)
    
    if not df.empty:
        impact_map = {"High": 0, "Medium": 1, "Low": 2}
        df['_impact_rank'] = df['Impact'].map(impact_map).fillna(1)
        df['_score_dist'] = abs(df['Score'] - 5)
        
        df = df.sort_values(
            by=['Domain', '_impact_rank', '_score_dist'], 
            ascending=[True, True, False]
        )
        df = df.drop(columns=['_impact_rank', '_score_dist'])
        
        print(f"✅ Analysis Complete: {len(df)} active traits found.")
        
    return df