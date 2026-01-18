import json
import os

# CONFIG
TRAITS_PATH = "config/snp_traits.json"
DEEP_DIVE_PATH = "config/deep_dive_content.json"

# CRITICAL RISK CONTENT (Fixed Structure)
GENE_CONTENT = {
    # 1. APOE (The Alzheimer's / Lipid Gene)
    "APOE": {
        "risk_genotypes": ["CC", "CT", "TC"], 
        "strength_genotypes": ["TT"], 
        "data_risk": {  # <--- FIXED: Now nested properly
            "gene": "APOE",
            "title": "Lipid & Brain Metabolism",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "APOE transports cholesterol and fats in the bloodstream and clears amyloid plaque from the brain.",
                "how": "You carry a variant associated with the APOE4 allele. Your body is inefficient at recycling cholesterol and clearing brain inflammation. Saturated fats tend to spike your inflammation markers significantly more than average.",
                "yours": "Your Result: Reduced Clearance (E4 Pattern)."
            },
            "action": {
                "title": "Strict Lipid Management",
                "body": "This is the most diet-responsive gene. You must aggressively limit saturated fats (butter, fatty beef, coconut oil) and prioritize Omega-3s (DHA) to protect the brain.",
                "foods": ["Salmon (DHA)", "Olive Oil", "Avoid Butter/Coconut"]
            },
            "confidence": 5
        },
        "data_strength": {
            "gene": "APOE",
            "title": "The Longevity Variant",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "APOE transports cholesterol and fats.",
                "how": "You likely carry the APOE2 or neutral APOE3 variant. Your lipid handling is robust, and you have a genetically lower baseline risk for neurodegeneration.",
                "yours": "Your Result: Efficient Clearance."
            },
            "action": {
                "title": "Metabolic Freedom",
                "body": "You have more flexibility with dietary fats, though a balanced diet is still recommended."
            },
            "confidence": 5
        }
    },

    # 2. ALDH2 (The Alcohol Flush Gene)
    "ALDH2": {
        "risk_genotypes": ["AA", "AG"],
        "strength_genotypes": ["GG"],
        "data_risk": { # <--- FIXED: Now nested properly
            "gene": "ALDH2",
            "title": "Toxin Filtration (Acetaldehyde)",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "ALDH2 is the liver enzyme responsible for breaking down Acetaldehyde, a toxic byproduct of alcohol and exhaust fumes.",
                "how": "Your enzyme is structurally broken (The 'Asian Flush' variant). When you drink alcohol, toxic Acetaldehyde accumulates immediately, causing DNA damage and inflammation 10-100x faster than in others.",
                "yours": "Your Result: Zero/Low Efficiency."
            },
            "action": {
                "title": "Zero Tolerance",
                "body": "Alcohol is essentially a carcinogen for your genotype. The 'flush' is a toxicity alarm. If you must drink, stick to clear spirits and take NAC (N-Acetyl Cysteine) beforehand to support glutathione.",
                "foods": ["NAC Supplement", "Cruciferous Veggies", "Limit Alcohol"]
            },
            "confidence": 5
        },
        "data_strength": {
            "gene": "ALDH2",
            "title": "The Iron Liver",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "ALDH2 breaks down Acetaldehyde.",
                "how": "Your enzyme functions at peak efficiency. You rapidly convert toxins into harmless acetate, preventing hangover symptoms and immediate DNA damage.",
                "yours": "Your Result: High Efficiency."
            },
            "action": {
                "title": "Social Advantage",
                "body": "You can process social drinking with minimal biological cost, though moderation is always key."
            },
            "confidence": 5
        }
    }
}

def inject_critical_risks():
    print("🚀 Starting Critical Risk Injection...")
    
    # 1. Load Traits to find correct RSIDs
    if not os.path.exists(TRAITS_PATH):
        print("❌ snp_traits.json not found!")
        return
    
    with open(TRAITS_PATH, 'r', encoding='utf-8') as f:
        traits = json.load(f)

    # 2. Map Gene Names to RSIDs (Smart Lookup)
    gene_map = {}
    for rsid, info in traits.items():
        # Handle "APOE (rs429358)" -> "APOE"
        raw_name = info.get('gene', '')
        clean_name = raw_name.split('(')[0].strip()
        
        if clean_name not in gene_map: gene_map[clean_name] = []
        gene_map[clean_name].append(rsid)

    # 3. Load Deep Dive Data
    if os.path.exists(DEEP_DIVE_PATH):
        with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
            deep_dive_data = json.load(f)
    else:
        deep_dive_data = {}

    # 4. Inject
    count = 0
    for gene_key, content in GENE_CONTENT.items():
        target_rsids = gene_map.get(gene_key, [])
        
        if target_rsids:
            print(f"✅ Found {gene_key} at {target_rsids}. Injecting...")
            for rsid in target_rsids:
                # Safe to set now because structure matches expectation
                content['data_risk']['gene'] = gene_key
                content['data_strength']['gene'] = gene_key
                
                deep_dive_data[rsid] = content
                count += 1
        else:
            print(f"⚠️ Warning: Could not find RSID for {gene_key} in your traits file.")

    # 5. Save
    with open(DEEP_DIVE_PATH, 'w', encoding='utf-8') as f:
        json.dump(deep_dive_data, f, indent=4)

    print(f"\n🎉 Success! Injected {count} critical risk stories.")

if __name__ == "__main__":
    inject_critical_risks()