import os
import json
import time
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Configuration
MODEL_AUDITOR = "gemini-2.5-flash" 
INPUT_FILE = "config/snp_traits.json"
OUTPUT_FILE = "config/snp_traits.json"
TEST_LIMIT = 5 

class SnpSanitizer:
    def __init__(self):
        self.client = genai.Client()

    def audit_snp(self, rsid, data):
        """
        Performs the clinical audit of a single SNP.
        """
        start_time = time.time()
        
        instruction = f"""
        You are a Senior Bioinformatician. Audit {rsid} (Gene: {data.get('gene')}).
        
        GOAL: The 'variants' letters are verified. DO NOT CHANGE THEM. 
        Ensure 'description', 'trait', and 'scores' are clinically accurate.

        REASONING ARCHETYPES:
        - ARCHETYPE A (Loss of Function - LoF): The variant reduces enzyme speed/stability. 
          Scoring: Wild-Type (High, 9-10) -> Variant (Low, 2-4). (e.g., MTHFR)
        - ARCHETYPE B (Gain of Function - GoF): The variant increases enzyme speed/efficiency. 
          Scoring: Wild-Type (Baseline, 6-7) -> Variant (Optimal, 8-10). (e.g., MTR)
        - ARCHETYPE C (Risk Trade-off): High activity is good for one system but bad for another. 
          Scoring: Use a balanced 5-7 range or prioritize the primary system (e.g., clearance).

        FEW-SHOT EXAMPLES FOR REASONING:
        
        Example 1: rs1801133 (MTHFR) - LoF
        - Input: {{"variants": {{"GG": "...", "AA": "..."}}, "scores": {{"GG": 9, "AA": 2}}}}
        - Reasoning: MTHFR A222V is a classic LoF. AA reduces folate conversion. 9/6/2 is correct.
        - Status: PASS

        Example 2: rs1805087 (MTR) - GoF
        - Input: {{"variants": {{"AA": "...", "GG": "..."}}, "scores": {{"AA": 9, "GG": 3}}}}
        - Reasoning: INCORRECT LOGIC. MTR A2756G is GoF. G allele increases velocity. 
        - Correction: AA (Baseline) should be 6. GG (Fast) should be 9. 
        - Status: FAIL

        10-POINT GUARDRAILS:
        1. TRUST VARIANTS: Never change the letters in 'variants'.
        2. APPLY ARCHETYPES: Determine if {rsid} is LoF or GoF before scoring.
        3. GAIN-OF-FUNCTION SENSITIVITY: If a variant improves clearance/efficiency, it should likely have a HIGHER score.
        4. SCORE ALIGNMENT: 7-10 = Optimal/Fast/Healthy. 1-4 = Impaired/Slow/Risk.
        5. DESCRIPTION ACCURACY: Must reflect current clinical consensus.
        6. BREVITY: Descriptions < 20 words.
        7. RSID/GENE BINDING: Confirm {rsid} is in {data.get('gene')}.
        8. EXACTLY 3 GENOTYPES: HomoRef, Het, HomoVar.
        9. PASS/FAIL: Only PASS if logic AND letters are 100% correct.
        10. JSON ONLY: No markdown.
        
        JSON SCHEMA:
        {{
            "status": "PASS or FAIL",
            "reasoning": "State if this was LoF/GoF and why scores were adjusted.",
            "corrected_entry": {{
                "gene": "...", "system": "...", "trait": "...", "description": "...", "impact": "...",
                "variants": {{ "XX": "...", "XY": "...", "YY": "..." }},
                "scores": {{ "XX": 9, "XY": 6, "YY": 3 }}
            }}
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_AUDITOR,
                contents=f"Audit this JSON data:\n{json.dumps(data)}",
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    temperature=0.0 
                )
            )
            
            raw_text = response.text.strip()
            raw_text = re.sub(r'^```json\s*|```$', '', raw_text, flags=re.MULTILINE)
            parsed = json.loads(raw_text)
            
            meta = response.usage_metadata
            stats = {
                "input_tokens": meta.prompt_token_count,
                "output_tokens": meta.candidates_token_count,
                "total_tokens": meta.total_token_count,
                "latency": round(time.time() - start_time, 2)
            }
            return parsed, stats

        except Exception as e:
            print(f"  🛑 ERROR for {rsid}: {e}")
            return None, None

def run_audit_test():
    sanitizer = SnpSanitizer()
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: Could not find {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r') as f:
        db = json.load(f)

    all_keys = list(db.keys())
    test_keys = all_keys[:TEST_LIMIT]
    
    print(f"🚀 Starting Clinical Logic Audit on {len(test_keys)} SNPs...")
    print("-" * 50)
    
    changes_made = False

    for rsid in test_keys:
        print(f"🔬 Auditing {rsid}...")
        result, stats = sanitizer.audit_snp(rsid, db[rsid])
        
        if result:
            status = result.get("status")
            
            # Print Token Details
            print(f"  Tokens: {stats['total_tokens']} (In: {stats['input_tokens']} | Out: {stats['output_tokens']})")
            print(f"  Latency: {stats['latency']}s")
            
            if status != "PASS":
                print(f"  ⚠️  Status: {status}")
                print(f"  📝 Reason: {result.get('reasoning')}")
                
                old_scores = db[rsid].get('scores')
                new_scores = result['corrected_entry'].get('scores')
                print(f"  📊 Logic Shift: {old_scores} -> {new_scores}")
                
                while True:
                    choice = input(f"  Accept changes for {rsid}? (1=Yes, 2=No): ").strip()
                    if choice == '1':
                        db[rsid] = result['corrected_entry']
                        changes_made = True
                        print(f"  ✅ Accepted.")
                        break
                    elif choice == '2':
                        print(f"  ⏭️  Skipped.")
                        break
            else:
                print("  ✅ Already Optimal.")
        
        print("-" * 50)
        time.sleep(1) 

    if changes_made:
        print("\n💾 Saving updated database...")
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(db, f, indent=4)
        print(f"🎉 Process complete!")
    else:
        print("\n🏁 Audit complete. No changes made.")

if __name__ == "__main__":
    run_audit_test()