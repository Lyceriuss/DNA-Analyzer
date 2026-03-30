import json
import re

def robust_reorganize(input_file, output_file):
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)

        reorganized_data = {}

        for key, details in data.items():
            # 1. Try to get rsid from the top level
            rsid = details.get("rsid")
            
            # 2. If not found, try looking inside variant_identity
            if not rsid and "variant_identity" in details:
                rsid = details["variant_identity"].get("rsid")
            
            # 3. If still not found, check if the key itself is an RSID
            if not rsid and re.match(r'rs\d+', key.lower()):
                rsid = key
            
            if rsid:
                # Ensure the original name is preserved inside
                if "name" not in details:
                    details["name"] = key
                
                # Normalize the RSID key to lowercase for consistency
                reorganized_data[rsid.lower()] = details
            else:
                print(f"Skipping '{key}': No RSID found in object or key name.")

        with open(output_file, 'w') as f:
            json.dump(reorganized_data, f, indent=4)
        
        print(f"\nSuccess: Processed {len(reorganized_data)} entries.")

    except Exception as e:
        print(f"Error: {e}")

# Run it
robust_reorganize('config\evidence_db.json', 'config\evidence_db2.json')