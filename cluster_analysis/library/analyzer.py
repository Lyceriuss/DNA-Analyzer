import json
import os
import pandas as pd
from genome.loader import load_dna_file
from cluster_analysis.library.normalizer import resolve_genotype, normalize_variant_keys
from cluster_analysis.library.domain_mapper import map_system_to_domain
from cluster_analysis.library.proxy_handler import apply_proxies

# What a genotype means for the person, from the library's evidence call (function) and its polarity
OUTCOMES = ("positive", "negative", "neutral", "typical", "unclear", "unknown")
EFFECTS = ("GoF", "LoF", "altered")


def outcome(function, polarity, source=None, drafts=False):
    """positive | negative | neutral | typical | unclear | unknown for one evidence call (see genotype_effects.py).
    Only a polarity reviewed by hand counts: the drafted ones ("library wording", "library ratings") were made from
    the LLM-written library, so they read unclear. drafts=True reads them anyway (the library audit reviews them)."""
    if function == "normal":
        return "typical"
    if function in EFFECTS:
        if source != "reviewed" and not drafts:
            return "unclear"
        return (polarity or {}).get(function, "unclear")
    return "unknown"

def library_rsids(traits_filepath, proxy_map_path="cluster_analysis/library/proxies.json"):
    """The SNPs the analysis reads: the library's, plus the proxies that stand in for missing ones."""
    wanted = set(json.load(open(traits_filepath, encoding="utf-8")))
    if os.path.exists(proxy_map_path):
        for target, config in json.load(open(proxy_map_path, encoding="utf-8")).items():
            if not target.startswith("_"):
                wanted |= set(config["proxies"])
    return wanted


def run_analysis(dna_filepath, traits_filepath):
    # 1. Load DNA (only the SNPs used, so imputed files with millions of rows stay quick)
    try:
        wanted = library_rsids(traits_filepath)
    except Exception:
        wanted = None
    dna_data = load_dna_file(dna_filepath, rsids=wanted)
    if not dna_data: return pd.DataFrame()

    # Library SNPs missing from the file, estimated from co-inherited SNPs (cluster_analysis/library/proxies.json)
    dna_data, estimated = apply_proxies(dna_data)

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
        functions = normalize_variant_keys(info.get('function', {}))
        polarity = info.get('polarity', {})
        matched_gt, _ = resolve_genotype(user_gt, variants)

        if matched_gt:
            function = functions.get(matched_gt, "unknown")
            impact = info.get('impact', 'Medium')
            interpretation = variants.get(matched_gt, "Unknown")
            est = estimated.get(rsid)
            if est and est["uncertain"]:
                function, interpretation = "unknown", est["note"]  # markers disagree: report it, do not read it
            elif est:
                interpretation = f"{interpretation} (estimated)"

            results.append({
                "RSID": rsid,
                "Gene": info.get('gene', 'Unknown'),
                "System": info.get('system', 'Other'),
                "Domain": map_system_to_domain(info.get('system', '')),
                "Trait": info.get('trait', 'Unknown'),
                "Impact": impact,
                "Result": matched_gt,      
                "User_Genotype": user_gt,
                # Evidence call for the gene (GoF / LoF / normal / altered / unknown) and what it means for the person
                "Function": function,
                "Outcome": outcome(function, polarity, info.get("polarity_source")),
                "Basis": info.get('function_basis', 'none'),
                "Interpretation": interpretation,
                # "carrier" / "rare_variant" entries are reported on their own page, not counted
                "Category": info.get("category", "trait"),
                # Set when the genotype was estimated from a co-inherited SNP rather than measured
                "Estimated": est["note"] if est else "",
                "Estimated_SV": est["note_sv"] if est else "",
                # --- NEW: Preserve Context for the Report ---
                "Function_Map": functions,  # { "CC": "normal", "CT": "LoF", "TT": "LoF" }
                "Polarity": polarity,       # { "LoF": "negative" }
                "Variant_Map": variants   # { "CC": "Good", "TT": "Bad" }
            })

    # 4. Create DataFrame
    df = pd.DataFrame(results)
    
    if not df.empty:
        impact_map = {"High": 0, "Medium": 1, "Low": 2}
        df['_impact_rank'] = df['Impact'].map(impact_map).fillna(1)
        # Positive and negative readings first, then the rest
        df['_reading'] = df['Outcome'].map({"negative": 0, "positive": 0, "neutral": 1, "unclear": 1}).fillna(2)
        df = df.sort_values(
            by=['Domain', '_impact_rank', '_reading'],
            ascending=[True, True, True]
        )
        df = df.drop(columns=['_impact_rank', '_reading'])
        
        print(f"✅ Analysis Complete: {len(df)} active traits found.")
        
    return df