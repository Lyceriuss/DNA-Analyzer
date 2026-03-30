import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# --- CONFIGURATION FOR DEEP DIVE ---
MODEL_TRANSLATE = "gemini-2.5-flash-lite"
INPUT_FILE = "config/deep_dive_content.json"
OUTPUT_FILE = "config/SV_deep_dive_content.json"

# --- STATIC TRANSLATION MAP ---
# Keeping this for consistency, though Deep Dives have different keys.
STATIC_LABELS = {
    "Swedish": {
        "Mechanistic Impact": "Mekanisk påverkan",
        "Study Quality": "Studiekvalitet",
        "Methodology": "Metodik"
    }
}

class GeneticPipeline:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    def enforce_static_labels(self, data, lang):
        # The Deep Dive structure is different; this function will just pass through 
        # unless you add deep-dive specific static labels here.
        return data

    def translate_with_telemetry(self, data, target_lang, is_retry=False):
        PRICE_IN_1M = 0.10
        PRICE_OUT_1M = 0.40

        stats = {
            "p_tokens": 0, "r_tokens": 0, "t_tokens": 0,
            "total": 0, "cost_usd": 0.0, "latency": 0
        }
        
        token_limit = 8192
        # Updated instructions for the Deep Dive structure (mechanisms, what, yours, action)
        instruction = (
            f"You are a professional medical translator specialized in functional genomics. "
            f"Translate this Deep Dive JSON data into {target_lang} according to these requirements:\n\n"
            "1. STRUCTURAL INTEGRITY: Keep all JSON keys (title, mechanisms, what, how, yours, action, body), RSIDs, and Gene Symbols exactly as they are.\n"
            "2. MANDATORY TRANSLATION: Every string value inside 'what', 'how', 'yours', and 'body' MUST be translated. "
            "Translate titles like 'The Low Energy Cell' into engaging medical Swedish.\n"
            "3. BADGE TYPES: Keep 'badge_type' values like 'RISK' or 'SUPERPOWER' in English unless instructed otherwise.\n"
            "4. NO TRUNCATION: Maintain the clinical tone and depth. Return ONLY valid JSON."
        )
                
        start_time = time.time()
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_TRANSLATE,
                contents=json.dumps(data),
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    temperature=0.1, # Keep it stable
                    max_output_tokens=token_limit
                )
            )
            
            meta = response.usage_metadata
            p_tokens = meta.prompt_token_count or 0
            r_tokens = meta.candidates_token_count or 0
            t_tokens = getattr(meta, 'thoughts_token_count', 0) or 0
            total_tokens = meta.total_token_count or (p_tokens + r_tokens + t_tokens)
            
            in_cost = (p_tokens / 1_000_000) * PRICE_IN_1M
            out_cost = ((r_tokens + t_tokens) / 1_000_000) * PRICE_OUT_1M
            total_cost_usd = in_cost + out_cost

            stats.update({
                "p_tokens": p_tokens, "r_tokens": r_tokens, "t_tokens": t_tokens,
                "total": total_tokens,
                "cost_usd": round(total_cost_usd, 6),
                "latency": round(time.time() - start_time, 2)
            })

            if not response.text:
                raise ValueError("Empty response")

            try:
                translated_json = json.loads(response.text)
                return self.enforce_static_labels(translated_json, target_lang), stats
            except json.JSONDecodeError:
                if not is_retry:
                    return self.translate_with_telemetry(data, target_lang, is_retry=True)
                return None, stats

        except Exception as e:
            print(f"    [!] Error on {data.get('title', 'Unknown')}: {e}")
            return None, stats

def run_batch(batch_size=1):
    pipeline = GeneticPipeline()

    if not os.path.exists(INPUT_FILE):
        print(f"[!] Input file {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        input_data = json.load(f)

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try:
                output_data = json.load(f)
            except:
                output_data = {}
    else:
        output_data = {}

    # --- THE NORDIC FINGERPRINT AUDITOR ---
    def is_actually_swedish(entry):
        if not isinstance(entry, dict): return False
        # Structure-agnostic check: stringify everything and look for äåö
        full_text = json.dumps(entry, ensure_ascii=False).lower()
        return any(marker in full_text for marker in ['ä', 'å', 'ö'])

    # Smart Filter
    pending_rsids = [rsid for rsid in input_data if rsid not in output_data or not is_actually_swedish(output_data[rsid])]
    
    if not pending_rsids:
        print("[✔] Audit Complete: Deep Dive content is fully translated.")
        return

    to_process = pending_rsids[:batch_size]
    print(f"[*] Deep Dive Audit: {len(pending_rsids)} items pending. Processing {len(to_process)}.")

    for rsid in to_process:
        print(f"--- Processing: {rsid} ---")
        time.sleep(2) # Breather for Deep Dive (larger payloads)
        
        translated, stats = pipeline.translate_with_telemetry(input_data[rsid], "Swedish")
        
        if translated and is_actually_swedish(translated):
            output_data[rsid] = translated
            print(f"    Tokens: {stats['p_tokens']} In / {stats['r_tokens']} Out (Total: {stats['total']})")
            print(f"    Cost:   ${stats['cost_usd']:.6f} | Time: {stats['latency']}s")
            
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            print(f"    [✔] Saved to {OUTPUT_FILE}")
        else:
            print(f"    [!] Failed {rsid}. No Swedish detected in output. Skipping.")

if __name__ == "__main__":
    run_batch(batch_size=65) # Deep Dives are larger; start with 5