import json
import os

DEEP_DIVE_PATH = "config/deep_dive_content.json"

def audit_length():
    with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"{'GENE':<10} | {'STATUS':<10} | {'LENGTH'}")
    print("-" * 35)

    for rsid, entry in data.items():
        # Check 'Strength' content primarily (since you cited a strength)
        content = entry.get('data_strength', {})
        mech = content.get('mechanisms', {}).get('how', '')
        insight = content.get('action', {}).get('body', '')
        
        total_len = len(mech) + len(insight)
        gene_name = content.get('gene', 'Unknown')  

        # Threshold based on your TCF7L2 example (~300 chars)
        if total_len < 300:
            print(f"{gene_name:<10} | ❌ SHORT   | {total_len} chars")
        else:
            print(f"{gene_name:<10} | ✅ GOOD    | {total_len} chars")

if __name__ == "__main__":
    audit_length()