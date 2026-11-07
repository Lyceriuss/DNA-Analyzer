# Content tooling

These tools build and check the knowledge base in `config/`. None of them run when a report is generated. Run them from
the repo root.

| Command | What it does | Writes? |
|---|---|---|
| `python -m cluster_analysis.validate_library` | Checks every entry against Ensembl and the GWAS Catalog: gene at the site, possible alleles, strand | `cluster_analysis/library_validation.*` |
| `python -m cluster_analysis.genotype_effects` | Evidence call (GoF / LoF / normal / altered / unknown) per genotype; lists effects without a polarity | `--write`: `function`, `function_basis` in `snp_traits.json` |
| `python -m cluster_analysis.library_audit` | Compares each entry's wording with the evidence and flags contradictions and common genotypes that read negative | `docs/LIBRARY_AUDIT.md`, `cluster_analysis/library_audit.json` |
| `python -m cluster_analysis.coverage_map FILE` | Which SNPs in a DNA file the research sources know about (offline, bulk files) | `data/output/` |
| `python -m cluster_analysis.candidates --name XY` | SNPs worth adding to the library: protein effect, drug annotation or biomarker association | `data/output/` |
| `python scripts/library_coverage.py` | Traits without a deep dive or evidence entry, and gene names that differ across the three files | no |

The LLM-era scripts (generation, translation, the LLM audit, injectors and one-off fixers in `injectors-authenticators/`)
were removed on 2026-11-07. They are in git history up to commit `71d7068`.

## Adding or changing an entry

1. Add the genotype texts in `snp_traits.json` (sorted keys).
2. Run `python -m cluster_analysis.validate_library` and fix every error.
3. Run `python -m cluster_analysis.genotype_effects --write` for the evidence calls. Set the `polarity` for each effect
   it lists by hand, with `"polarity_source": "reviewed"`.
4. Write `data_risk` / `data_strength` in `deep_dive_content.json` and the evidence entry in `evidence_db.json`, plus
   their Swedish versions (`SV_*.json`).
5. Run `python -m cluster_analysis.library_audit` and `python scripts/library_coverage.py`.
6. Generate a report in both languages and read through it.
