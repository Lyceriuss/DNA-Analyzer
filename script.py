import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# --- CONFIGURATION ---
MODEL_CHECKER = "gemini-2.5-flash"
TRAITS_FILE = "config/snp_traits.json"         # Ground Truth (Scores/Gene/Description)
CONTENT_FILE = "config/deep_dive_content.json" # Narrative Layer
REWRITE_LIST_FILE = "config/rewrite_needed.json"
LOG_FILE = "audit_results.log"

class DeepDiveAuditor:
    def __init__(self):
        self.client = genai.Client()

    def verify_factuality(self, rsid, trait_data, content_data):
        """
        Audits the narrative against ground truth biochemical scores.
        """
        start_time = time.time()
        
        # Safe extraction of the two narrative perspectives
        risk_narrative = content_data.get('data_risk', {}).get('mechanisms', {}).get('how', 'MISSING')
        strength_narrative = content_data.get('data_strength', {}).get('mechanisms', {}).get('how', 'MISSING')

        instruction = f"""
        ACT AS: Senior Bioinformatician. 
        TASK: Compare the NARRATIVE against the GROUND TRUTH.

        GROUND TRUTH:
        - Gene: {trait_data.get('gene')}
        - Score Logic: {json.dumps(trait_data.get('scores'))}
        - Description: {trait_data.get('description')}
        (Scores < 5 = Bottleneck/Impaired | Scores > 5 = Advantage/Robust)

        NARRATIVE PERSPECTIVES:
        1. RISK: {risk_narrative}
        2. STRENGTH: {strength_narrative}

        AUDIT RULES:
        - LOGIC: Does 'data_risk' describe the bottleneck associated with the low scores?
        - LOGIC: Does 'data_strength' describe the advantage associated with the high scores?
        - FACT: Is the gene's biochemical role (catalysis, substrate, etc.) accurate?
        - SCHEMA: Status is FAIL if either 'how' section is missing or generic.

        OUTPUT JSON:
        {{
            "status": "PASS or FAIL",
            "summary": "One sentence factual verification of the logic."
        }}
        """

        try:
            if risk_narrative == 'MISSING' or strength_narrative == 'MISSING':
                return {"status": "FAIL", "summary": "Incomplete dual-perspective architecture."}, {"total": 0}

            response = self.client.models.generate_content(
                model=MODEL_CHECKER,
                contents=f"Audit {rsid}",
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    temperature=0.0 # Strict fact-checking
                )
            )
            
            parsed = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
            stats = {"total": response.usage_metadata.total_token_count}
            return parsed, stats
            
        except Exception as e:
            return {"status": "ERROR", "summary": str(e)}, {"total": 0}

def run_integrity_audit():
    auditor = DeepDiveAuditor()
    
    # Load with UTF-8 to prevent Windows encoding crashes
    with open(TRAITS_FILE, 'r', encoding='utf-8') as f:
        traits = json.load(f)
    with open(CONTENT_FILE, 'r', encoding='utf-8') as f:
        content = json.load(f)

    rewrite_list = []
    
    print(f"🚀 Starting Fact-Check Audit (Architecture: FUT8/ZEB2 Dual-Path)...")

    for rsid, narrative in content.items():
        if rsid not in traits:
            continue

        result, stats = auditor.verify_factuality(rsid, traits[rsid], narrative)
        
        status = result.get('status', 'FAIL')
        summary = result.get('summary', 'No summary.')
        tokens = stats.get('total', 0)

        # Terminal Visualization
        icon = "✅" if status == "PASS" else "❌"
        print(f"{icon} {rsid:12} | {tokens:4} t | {status:5} | {summary[:70]}...")

        # Log to file for deep review
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] {rsid} | {tokens} tokens | {status} | {summary}\n")

        if status != 'PASS':
            rewrite_list.append(rsid)

    # Save the 'To-Do' list
    with open(REWRITE_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(rewrite_list, f, indent=4)

    print(f"\n🏁 Audit Complete. Flagged {len(rewrite_list)} for rewrite.")

if __name__ == "__main__":
    run_integrity_audit()