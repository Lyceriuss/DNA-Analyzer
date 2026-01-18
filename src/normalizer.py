# src/normalizer.py

# Standard complementary base pairing
COMPLEMENT_MAP = {
    "A": "T", "T": "A",
    "C": "G", "G": "C",
    "I": "I", "D": "D"  # Handle Indels/Deletions gracefully if they appear
}

def standardize_genotype(genotype):
    """
    Sorts the genotype string alphabetically.
    'GA' -> 'AG', 'TC' -> 'CT'
    Ensures consistent lookup keys.
    """
    if not genotype or len(genotype) < 1:
        return ""
    return "".join(sorted(genotype))

def get_complement(genotype):
    """
    Returns the complementary strand version of the genotype.
    Example: 'AG' -> 'TC' (A->T, G->C)
    """
    try:
        return "".join([COMPLEMENT_MAP.get(base, base) for base in genotype])
    except Exception:
        return genotype  # Return original if unknown chars encountered

def resolve_genotype(user_genotype, trait_variants):
    """
    The Core Matching Logic.
    
    Args:
        user_genotype (str): The value from the CSV (e.g., "GG")
        trait_variants (dict): The 'variants' dict from snp_traits.json 
                               (e.g., {"CC": "...", "CT": "..."})
                               
    Returns:
        (matched_genotype, was_flipped)
        matched_genotype: The key in the JSON that matches (e.g., "CC")
        was_flipped: Boolean, True if we had to flip strands to find it.
    """
    if not user_genotype or not trait_variants:
        return None, False

    # 1. Clean and Standardize (Sort)
    # If CSV has "GA", we convert to "AG"
    clean_gt = standardize_genotype(user_genotype)
    
    # Check 1: Direct Match (after sorting)
    # Does "AG" exist in the JSON keys?
    if clean_gt in trait_variants:
        return clean_gt, False

    # 2. Strand Flip
    # If "AG" wasn't found, flip it to "TC"
    flipped_gt = get_complement(clean_gt)
    sorted_flipped = standardize_genotype(flipped_gt)
    
    # Check 2: Complement Match
    # Does "TC" exist in the JSON keys?
    if sorted_flipped in trait_variants:
        return sorted_flipped, True

    # 3. No match found
    return None, False