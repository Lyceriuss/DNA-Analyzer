import re
import os

# CONFIG
INPUT_FILE = "MyHeritage_raw_dna_data_HP.csv"
OUTPUT_FILE = "MyHeritage_raw_dna_data_HP_FIXED.csv"

def fix_csv():
    print(f"🔧 Fixing whitespace issues in: {INPUT_FILE}...")
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: File '{INPUT_FILE}' not found in current directory.")
        return

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as infile, \
             open(OUTPUT_FILE, 'w', encoding='utf-8', newline='\n') as outfile:
            
            for line in infile:
                # 1. Preserve Comments/Metadata exactly
                if line.startswith('#'):
                    outfile.write(line)
                    continue
                
                # 2. Skip Empty Lines
                if not line.strip():
                    continue

                # 3. THE FIX: Collapse "   ,   " into ","
                # This turns quoted, spaced garbage into standard CSV format
                clean_line = re.sub(r'\s*,\s*', ',', line.strip())
                
                outfile.write(clean_line + '\n')
                
        print(f"✅ Success! Created clean file: {OUTPUT_FILE}")
        print("👉 You can now select this '_FIXED' file in your main analyzer.")

    except Exception as e:
        print(f"❌ Critical Error: {e}")

if __name__ == "__main__":
    fix_csv()