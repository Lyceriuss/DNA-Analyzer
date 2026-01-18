import json
import os

# CONFIG
TRAITS_PATH = "config/snp_traits.json"
DEEP_DIVE_PATH = "config/deep_dive_content.json"

def fix_metadata():
    print("🔧 Starting Metadata Repair...")

    # 1. Load the Master Database (Source of Truth)
    if not os.path.exists(TRAITS_PATH):
        print("❌ snp_traits.json not found.")
        return
    with open(TRAITS_PATH, 'r', encoding='utf-8') as f:
        traits_db = json.load(f)

    # 2. Load the Broken Stories
    if not os.path.exists(DEEP_DIVE_PATH):
        print("❌ deep_dive_content.json not found.")
        return
    with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
        stories = json.load(f)

    fixed_count = 0

    # 3. Iterate and Patch
    for rsid, entry in stories.items():
        # Lookup the real gene name using the RSID
        if rsid in traits_db:
            raw_gene = traits_db[rsid].get('gene', 'Unknown Gene')
            
            # Clean it up: "DRD2 (Taq1A)" -> "DRD2"
            clean_gene = raw_gene.split('(')[0].strip()
            
            # Patch Risk Data
            if 'data_risk' in entry:
                entry['data_risk']['gene'] = clean_gene
            
            # Patch Strength Data
            if 'data_strength' in entry:
                entry['data_strength']['gene'] = clean_gene
                
            fixed_count += 1
            print(f"   - Fixed {rsid} -> {clean_gene}")
        else:
            print(f"⚠️ Warning: Story exists for {rsid}, but it's not in snp_traits.json")

    # 4. Save
    with open(DEEP_DIVE_PATH, 'w', encoding='utf-8') as f:
        json.dump(stories, f, indent=4)

    print(f"\n✅ Successfully repaired {fixed_count} Deep Dive entries.")

if __name__ == "__main__":
    fix_metadata()