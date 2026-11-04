import json
import csv
import os
import glob

JSON_FILE = "config/snp_traits.json"
INPUT_DIR = os.path.join("data", "input")

def check_all_mismatches():
    # 1. Load the JSON database
    try:
        with open(JSON_FILE, 'r') as f:
            snp_db = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Could not find {JSON_FILE}")
        return

    # Store mismatches cleanly: {rsid: {"csv_variants": set(), "json_allows": list()}}
    global_mismatches = {}
    files_checked = 0
    total_snps_cross_referenced = 0

    # 2. Find all CSV files in the input directory
    search_pattern = os.path.join(INPUT_DIR, "*.csv")
    csv_files = glob.glob(search_pattern)

    if not csv_files:
        print(f"❌ Error: No CSV files found in {INPUT_DIR}")
        return

    print(f"🚀 Scanning {len(csv_files)} DNA files...\n")

    # 3. Loop through every file
    for file_path in csv_files:
        files_checked += 1
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                # Skip empty rows, comments, or headers
                if not row or row[0].startswith('#') or row[0].upper() == 'RSID':
                    continue
                
                if len(row) >= 4:
                    rsid = row[0].strip('"')
                    csv_variant = row[3].strip('"').replace('-', '') 
                    
                    # 4. Check for Match
                    if rsid in snp_db:
                        total_snps_cross_referenced += 1
                        allowed_variants = list(snp_db[rsid].get('variants', {}).keys())
                        
                        # Check forward and reverse string (e.g., GA vs AG)
                        if csv_variant not in allowed_variants and csv_variant[::-1] not in allowed_variants:
                            if rsid not in global_mismatches:
                                global_mismatches[rsid] = {
                                    "csv_variants": set(),
                                    "json_allows": allowed_variants
                                }
                            global_mismatches[rsid]["csv_variants"].add(csv_variant)

    # 5. Output Aggregated Results
    print(f"📊 Batch Scan Complete")
    print(f"📁 Processed {files_checked} files.")
    print(f"🧬 Cross-referenced {total_snps_cross_referenced} total SNP occurrences.")
    
    if not global_mismatches:
        print(f"\n✅ PERFECT MATCH! All CSV variants across all files exist in the JSON.")
    else:
        print(f"\n⚠️ Found {len(global_mismatches)} unique RSID mismatches across all files:\n")
        for rsid, data in global_mismatches.items():
            # Convert set to sorted list for clean printing
            found_variants = sorted(list(data["csv_variants"]))
            print(f"  RSID: {rsid}")
            print(f"    CSV Variants Found : {found_variants}")
            print(f"    JSON Currently Allows: {data['json_allows']}")
            print("-" * 40)

if __name__ == "__main__":
    check_all_mismatches()