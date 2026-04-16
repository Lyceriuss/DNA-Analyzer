import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# --- CONFIGURATION ---
# Switching to standard flash as it handles deep JSON structural compliance slightly better than lite
MODEL_GENERATE = "gemini-2.5-flash" 
OUTPUT_FILE = "repopulated_entries.json"
TARGET_RSIDS = ["rs7799039", "rs444697", "rs2229765", "rs6214"]

VALID_ORGANS = [
    "Brain", "Eyes", "Thyroid", "Heart", "Lungs", "Liver", "Stomach", 
    "Pancreas", "Spleen", "Kidneys", "Intestines", "Bladder", 
    "Ovaries", "Uterus", "Testes", "Prostate", "Skin", "Bones", "Muscles"
]

class GeneticGenerationPipeline:
    def __init__(self):
        # Initializes using the GOOGLE_API_KEY from your environment
        self.client = genai.Client()

    def generate_with_telemetry(self, rsid, is_retry=False):
        # Pricing for standard Flash (approximate)
        PRICE_IN_1M = 0.075 
        PRICE_OUT_1M = 0.30

        stats = {
            "p_tokens": 0, "r_tokens": 0, "t_tokens": 0,
            "total": 0, "cost_usd": 0.0, "latency": 0
        }
        
        instruction = f"""
        You are an expert molecular geneticist. Generate a highly detailed, deeply researched database entry for the genetic variant: {rsid} in English.
        
        CRITICAL GUARDRAILS:
        
        """
                
        start_time = time.time()
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_GENERATE,
                contents=f"Generate entry for {rsid}",
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    temperature=0.2, # Low temperature for factual consistency
                )
            )
            
            meta = response.usage_metadata
            p_tokens = meta.prompt_token_count or 0
            r_tokens = meta.candidates_token_count or 0
            total_tokens = meta.total_token_count or (p_tokens + r_tokens)
            
            in_cost = (p_tokens / 1_000_000) * PRICE_IN_1M
            out_cost = (r_tokens / 1_000_000) * PRICE_OUT_1M

            stats.update({
                "p_tokens": p_tokens, "r_tokens": r_tokens,
                "total": total_tokens,
                "cost_usd": round(in_cost + out_cost, 6),
                "latency": round(time.time() - start_time, 2)
            })

            if not response.text:
                raise ValueError("Empty response")

            try:
                generated_json = json.loads(response.text)
                return generated_json, stats
            except json.JSONDecodeError:
                if not is_retry:
                    print(f"    [!] JSON Decode failed. Retrying {rsid}...")
                    return self.generate_with_telemetry(rsid, is_retry=True)
                return None, stats

        except Exception as e:
            print(f"    [!] Error generating {rsid}: {e}")
            return None, stats


def passes_guardrails(entry_data, rsid):
    """The new Auditor: Checks lengths and valid organs instead of Swedish characters."""
    try:
        data = entry_data[rsid]
        
        # 1. Check Organs
        for organ in data.get("affected_organs", []):
            if organ not in VALID_ORGANS:
                print(f"    [!] Guardrail failed: Invalid organ '{organ}'")
                return False
                
        # 2. Check Detail Lengths
        metrics = data.get("metrics", {})
        for cat in ["mechanistic_impact", "study_quality", "methodology"]:
            detail = metrics.get(cat, {}).get("detail", "")
            if len(detail) < 300:
                print(f"    [!] Guardrail failed: {cat} detail too short ({len(detail)} chars)")
                return False
                
        # 3. Check Critique Length
        audits = data.get("methodology_audit", [])
        if not audits or len(audits[0].get("critique", "")) < 400:
            print(f"    [!] Guardrail failed: Critique too short")
            return False
            
        return True
    except KeyError:
        print("    [!] Guardrail failed: Malformed JSON structure.")
        return False


def run_generation():
    pipeline = GeneticGenerationPipeline()

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try:
                output_data = json.load(f)
            except:
                output_data = {}
    else:
        output_data = {}

    # Find which of our target RSIDs still need to be generated
    pending_rsids = [rsid for rsid in TARGET_RSIDS if rsid not in output_data]
    
    if not pending_rsids:
        print("[✔] Generation Complete: All target entries exist in the database.")
        return

    print(f"[*] Generation Task: {len(pending_rsids)} items pending.")

    for rsid in pending_rsids:
        print(f"--- Generating: {rsid} ---")
        time.sleep(1) # Slight breather
        
        generated, stats = pipeline.generate_with_telemetry(rsid)
        
        if generated and passes_guardrails(generated, rsid):
            output_data.update(generated)
            print(f"    Tokens: {stats['p_tokens']} In / {stats['r_tokens']} Out (Total: {stats['total']})")
            print(f"    Cost:   ${stats['cost_usd']:.6f} | Time: {stats['latency']}s")
            
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            print(f"    [✔] Saved to {OUTPUT_FILE}")
        else:
            print(f"    [!] Failed to generate a compliant entry for {rsid}. Skipping.")

if __name__ == "__main__":
    run_generation()