# Content tooling

These scripts build and maintain the knowledge base in `config/`. None of them are used when a report is generated. Most of them are one-off scripts: they hardcode paths, and several **overwrite config files in place**. Commit `config/` before running any of them.

All scripts live in `injectors-authenticators/` and must be run from the repo root (`python injectors-authenticators/x.py`). The ones that import `src.*` need `PYTHONPATH=.`. The LLM scripts need `pip install google-genai python-dotenv` and `GOOGLE_API_KEY` in `.env`.

## LLM pipelines

| Script | Model | Reads → Writes | What it does |
|---|---|---|---|
| `translate_evidence.py` | gemini-2.5-flash-lite | `config/evidence_db2.json` → `config/SV_evidence_db2.json` | Translates evidence entries to Swedish in batches of 15 and logs cost and tokens. It treats an entry as "done" when the JSON contains `å/ä/ö`, so re-running it retries entries that were never translated. The input path is a working copy (`*2.json`) that is not in the repo. |
| `generate_evidence.py` | gemini-2.5-flash | `TARGET_RSIDS` → `repopulated_entries.json` | Generates new evidence entries for a hardcoded RSID list. Guardrails: organ vocabulary and minimum text lengths. The system prompt's guardrail section is currently empty. |
| `audit_deep_dives.py` | gemini-2.5-flash | `snp_traits.json` + `deep_dive_content.json` → `config/rewrite_needed.json`, `audit_results.log` | Fact-checks every deep dive's `how` narrative against the trait scores. The FAIL list becomes `rewrite_needed.json`. |

LLM-generated content must pass `python -m cluster_analysis.validate_library` before it is used: the 2026-11 validation found 73 errors in LLM-written entries.

## Other scripts

| Script | Purpose | Writes? |
|---|---|---|
| `evidence_db_injector.py` | Validates new evidence entries (organs, text lengths) and merges them. The `NEW_ENTRIES` import is commented out, so it currently fails with a `NameError`. | **yes** |
| `csv_snp_compare.py` | Lists input genotypes that no trait key accepts (strand or ordering gaps) | no |
| `validate.py` | Gap analysis that compares trait coverage in `snp_traits` with `deep_dive_content` | no |
| `corrections_2026_11/apply.py` | Applies the 2026-11 validation fixes: rewrites, rsID retargets, removals. Content is in `content_en.py` / `content_sv.py`. Safe to re-run. | **yes**, backs up to `config/backup/` |
| `audit_length.py` | Prints the narrative length of each deep dive | no |
| `data_analysis.py` | Organ/molecule/gene connection stats from `evidence_db` | no |
| `DNA_compare.py` | Health check of one hardcoded input CSV against the traits | no |
| `cluster_checker.py` | Evaluates `muscle_logic_gates_db.json` rules for one CSV | no |
| `deep_dive_injector.py` | Merges the hardcoded `FINISH_CONTENT` narratives into `deep_dive_content.json` | **yes** |
| `fixer.py` | Keeps one "priority" RSID per gene and deletes the rest from `snp_traits.json` | **yes, destructive** |
| `SNP_sanitizer_manual.py` | LLM audit and rewrite of `snp_traits.json` entries (`TEST_LIMIT = 5`) | **yes, in place** |
| `fix.py` | Normalises whitespace in one raw DNA CSV, writing a new `_FIXED.csv` | new file |
| `script.py` | Renders `Clinical_Deep_Dive_Reference.pdf` from `evidence_db` (organ avatar layout) | PDF |
| `test_database.py` | Prototype that pulls protein and variant data from the UniProt REST API | no |
| `test_visualization.py` | Prototype HTML dashboard for MTHFR from `mthfr_database.json` | HTML |
| `backup_copypasta.txt` | Scratch content | — |

## Typical content workflow

1. Add or adjust the genotype→score mapping in `snp_traits.json`. Use sorted keys.
2. Write `data_risk` / `data_strength` in `deep_dive_content.json`, by hand or with `deep_dive_injector.py`.
3. Generate or curate the evidence entry, then merge it with `evidence_db_injector.py`.
4. Run `python -m cluster_analysis.validate_library`: gene at the site, possible alleles, strand. Fix every error.
5. Run `audit_deep_dives.py` to fact-check the narrative and review `rewrite_needed.json`.
6. Translate with `translate_evidence.py`. Point `INPUT_FILE`/`OUTPUT_FILE` at the real files, or copy them to `*2.json` first.
7. Run `validate.py` and `csv_snp_compare.py` to check coverage and matching.
8. Generate a report in both languages and read through it.
