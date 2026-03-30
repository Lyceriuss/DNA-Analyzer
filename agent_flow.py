import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL_TRANSLATE = "gemini-2.5-flash-lite"
INPUT_FILE = "config/evidence_db2.json"
OUTPUT_FILE = "config/SV_evidence_db2.json"

# --- STATIC TRANSLATION MAP ---
# This ensures these technical labels NEVER change.
STATIC_LABELS = {
    "Swedish": {
        "Mechanistic Impact": "Mekanisk påverkan",
        "Study Quality": "Studiekvalitet",
        "Methodology": "Metodik"
    },
    "German": {
        "Mechanistic Impact": "Mechanistischer Einfluss",
        "Study Quality": "Studienqualität",
        "Methodology": "Methodik"
    }
}

class GeneticPipeline:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    def enforce_static_labels(self, data, lang):
        """Force replaces specific fields with our 'Gold Standard' translations."""
        mapping = STATIC_LABELS.get(lang, {})
        
        if "methodology_audit" in data:
            for audit in data["methodology_audit"]:
                orig_val = audit.get("score_contribution", "")
                for en_label, lang_label in mapping.items():
                    if en_label in orig_val:
                        # Replaces "Mechanistic Impact (4/5)" with "Mekanisk påverkan (4/5)"
                        audit["score_contribution"] = orig_val.replace(en_label, lang_label)
        return data

    def translate_with_telemetry(self, data, target_lang, is_retry=False):
        # 1. PRICING CONSTANTS (2026 Gemini 2.5 Flash-Lite rates)
        PRICE_IN_1M = 0.10
        PRICE_OUT_1M = 0.40

        # 2. INITIALIZE STATS
        stats = {
            "p_tokens": 0, "r_tokens": 0, "t_tokens": 0,
            "total": 0, "cost_usd": 0.0, "latency": 0
        }
        
        token_limit = 8192
        instruction = (
            f"You are a professional medical translator specialized in functional genomics. "
            f"Translate this JSON data into {target_lang} according to these strict requirements:\n\n"
            "1. STRUCTURAL INTEGRITY: Keep all JSON keys, RSIDs, Gene Symbols, and PMID numbers EXACTLY as they are. Do not translate them.\n"
            "2. MANDATORY TRANSLATION: Every string value (rationale, detail, critique, mechanism, etc.) MUST be translated. No section may remain in English.\n"
            f"3. LINGUISTIC RULES: All sentences must follow {target_lang} grammar and syntax. "
            "If a specific medical noun has no equivalent, keep ONLY that noun in English within the translated sentence.\n"
            "4. NO TRUNCATION: Maintain the exact same technical depth, clinical tone, and length as the source. Do not summarize.\n"
            "5. OUTPUT: Return ONLY the valid JSON object. No preamble or notes."
        )
                
        start_time = time.time()
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_TRANSLATE,
                contents=json.dumps(data),
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=token_limit
                )
            )
            
            # 3. NONE-SAFE METADATA EXTRACTION
            meta = response.usage_metadata
            # Using 'or 0' to prevent the NoneType error we saw earlier
            p_tokens = meta.prompt_token_count or 0
            r_tokens = meta.candidates_token_count or 0
            t_tokens = getattr(meta, 'thoughts_token_count', 0) or 0
            # Ensure we use the API's reported total
            total_tokens = meta.total_token_count or (p_tokens + r_tokens + t_tokens)
            
            # 4. COST CALCULATION
            # Using LaTeX for clarity: 
            # $Cost = \frac{Input}{10^6} \times 0.10 + \frac{Output + Thinking}{10^6} \times 0.40$
            in_cost = (p_tokens / 1_000_000) * PRICE_IN_1M
            out_cost = ((r_tokens + t_tokens) / 1_000_000) * PRICE_OUT_1M
            total_cost_usd = in_cost + out_cost

            # Update stats object
            stats.update({
                "p_tokens": p_tokens,
                "r_tokens": r_tokens,
                "t_tokens": t_tokens,
                "total": total_tokens, 
                "cost_usd": round(total_cost_usd, 6),
                "latency": round(time.time() - start_time, 2)
            })

            # Check if we actually got text back before parsing
            if not response.text:
                raise ValueError("Empty response from API (likely safety filter)")

            try:
                translated_json = json.loads(response.text)
                return self.enforce_static_labels(translated_json, target_lang), stats
            except json.JSONDecodeError:
                if not is_retry:
                    print(f"    [!] JSON Malformed for {data.get('rsid')}. Retrying...")
                    return self.translate_with_telemetry(data, target_lang, is_retry=True)
                else:
                    print(f"    [!] Failed to parse JSON for {data.get('rsid')} after retry.")
                    return data, stats

        except Exception as e:
            # Now handles the NoneType + int error gracefully
            print(f"    [!] Error on {data.get('rsid')}: {e}")
            return data, stats

def run_batch(batch_size=1):
    pipeline = GeneticPipeline()

    # 1. Load Input Data
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        input_data = json.load(f)

    # 2. Load Existing Output (if it exists)
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try:
                output_data = json.load(f)
            except json.JSONDecodeError:
                output_data = {}
    else:
        output_data = {}

    # --- NEW: SWEDISH AUDITOR LOGIC ---
    def is_actually_swedish(entry):
            if not isinstance(entry, dict): 
                return False
            
            # Convert the whole dictionary to a string to check every single value at once
            # ensure_ascii=False is key so we don't see '\u00e4' instead of 'ä'
            full_text = json.dumps(entry, ensure_ascii=False).lower()

            # The "Nordic Fingerprint"
            swedish_markers = ['ä', 'å', 'ö']
            
            return any(marker in full_text for marker in swedish_markers)

    # 3. Smart Filter: Identify RSIDs that are missing OR still in English
    pending_rsids = []
    for rsid in input_data:
        if rsid not in output_data or not is_actually_swedish(output_data[rsid]):
            pending_rsids.append(rsid)
    
    if not pending_rsids:
        print("[✔] Audit Complete: All entries are translated and verified as Swedish.")
        return

    to_process = pending_rsids[:batch_size]
    # This will now include the entries that previously failed (503s)
    print(f"[*] Audit found {len(pending_rsids)} items needing translation. Processing {len(to_process)}.")

    for rsid in to_process:
        print(f"--- RSID: {rsid} ---")
        time.sleep(1.5)  # Breather to prevent 503 errors
        
        try:
            translated, stats = pipeline.translate_with_telemetry(input_data[rsid], "Swedish")
            
            # --- THE SAFETY CHECK ---
            # Only save if the API actually returned a translation, not the original data fallback
            if is_actually_swedish(translated):
                output_data[rsid] = translated
                
                print(f"    Tokens: {stats['p_tokens']} In / {stats['r_tokens']} Out (Total: {stats['total']})")
                print(f"    Cost:   ${stats['cost_usd']:.6f} | Time: {stats['latency']}s")
                
                # 4. Immediate Write-Back
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=4, ensure_ascii=False)
                print(f"    [✔] Saved to {OUTPUT_FILE}")
            else:
                print(f"    [!] Skipping {rsid}: API returned English or invalid data. Will retry next run.")

        except Exception as e:
            print(f"    [!] Critical Error on {rsid}: {e}")
            break

# --- TEST RUN ---
# Try 1, then 2, then 4 as you mentioned
run_batch(batch_size=15)