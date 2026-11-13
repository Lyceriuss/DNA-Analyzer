def map_system_to_domain(system_name: str) -> str:
    s = str(system_name).lower()

    # 1. Longevity & Cell Health
    if any(k in s for k in ["repair", "longevity", "telom", "cell", "brca", "cancer", "tumor", "sirt", "foxo", "klotho", "dna", "vision", "eye", "macular"]):
        return "Longevity & Cell Health"

    # 2. Metabolism & Weight (Excludes Glucose/Insulin)
    if any(k in s for k in ["weight", "fat", "lipid", "cholesterol", "adip", "metabolic", "obesity", "liver", "appetite", "starch", "craving", "mitochondria"]):
        return "Metabolism & Weight"

    # 3. Cardiovascular
    if any(k in s for k in ["cardio", "heart", "blood pressure", "vascular", "circulation", "stroke", "hypertension", "clot", "thromb", "salt", "vaso"]):
        return "Cardiovascular Health"

    # 4. Hormones & Endocrine
    if any(k in s for k in ["hormone", "estrogen", "thyroid", "testosterone", "endocrine", "fertility", "cortisol", "reproductive", "androgen"]):
        return "Hormones & Endocrine"

    # 5. Detox & Pharma
    if any(k in s for k in ["detox", "cyp", "gst", "oxidat", "drug", "caffeine", "alcohol", "nicotine", "pharma", "anesthesia", "statin"]):
        return "Detox & Pharma"

    # 6. Immune & Gut
    if any(k in s for k in ["immune", "inflam", "autoimmune", "gut", "digest", "allergy", "celiac", "histamine", "crohn", "ibd", "lactose"]):
        return "Immune & Gut Health"

    # 7. Brain & Mood
    if any(k in s for k in ["brain", "neuro", "dopamine", "serotonin", "stress", "sleep", "mood", "cognition", "memory", "gaba", "pain", "mental", "addiction", "circadian"]):
        return "Brain & Mood"

    # 8. Glucose & Insulin (This was missing/merged in your snippet)
    if any(k in s for k in ["insulin", "glucose", "pancreas", "sugar", "diabetes", "glycation", "tcf7l2"]):
        return "Glucose & Insulin"

    # 9. Vitamins & Methylation
    if any(k in s for k in ["vitamin", "mineral", "iron", "b12", "folate", "methylation", "homocysteine", "mthfr", "zinc", "magnesium"]):
        return "Vitamins & Methylation"

    # 10. Musculoskeletal & Skin
    if any(k in s for k in ["muscle", "collagen", "strength", "skin", "hair", "bone", "joint", "tendon", "injury", "appearance", "sensory"]):
        return "Musculoskeletal & Skin"

    return "Other"