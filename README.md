# DNA-Analyzer

An in-house tool that turns a consumer raw-DNA export (MyHeritage / 23andMe-style CSV) into a multi-page, illustrated PDF report. The report covers ~230 curated SNPs (each validated against Ensembl and the GWAS Catalog) across ten health domains, with actionable health advice for each result. It can be produced in English or Swedish, and it can optionally compare the subject with one or two relatives.

A core design goal is that each SNP result fits on **one PDF page**: its genotype spectrum, mechanism, insight, evidence and confidence panel.

## Quick start

```bash
pip install -r requirements.txt   # installed into the global Python, no venv

# put one or more raw DNA CSVs in data/input/
python main.py
```

`main.py` is interactive. It asks you to:

1. pick the report language (English / Swedish),
2. pick the primary profile from `data/input/*.csv`,
3. optionally add up to two relatives (Mom / Dad / a custom label).

Output goes to `data/output/<file>_<Language>_Report.pdf`, together with the intermediate chart PNGs.

`data/input/` and `data/output/` are git-ignored. **Never commit raw DNA files or anything derived from them.**

Run the tests with `python -m unittest discover tests`. Check content consistency with `python injectors-authenticators/validate.py`.

On Windows, set `PYTHONIOENCODING=utf-8` if the console crashes when it prints emoji.

## What the report contains

| Section | Source |
|---|---|
| 4-page introduction (GoF/LoF, upstream/downstream, etc.) | `config/ui_labels.json` → `introduction_education` |
| Dashboard: per-domain positive/baseline/negative counts and a polar chart | computed from `snp_traits.json` scores |
| Key active traits: increased and decreased function tables | `snp_traits.json` |
| Section 3, Strengths: one deep-dive page per strength SNP, then a summary | `deep_dive_content.json` + `evidence_db.json` |
| Section 4, Risks: one deep-dive page per risk SNP, then a summary | same |
| Heritage (optional): donut chart and per-relative match tables | `src/inheritance.py` |

## Repository layout

```
main.py                   Interactive entry point; builds the whole PDF
src/                      Analysis pipeline and PDF rendering (see docs/ARCHITECTURE.md)
config/                   The knowledge base: traits, narratives, evidence, UI labels (see docs/DATA_MODEL.md)
config/backup/            Backup of entries changed by the 2026-11 library corrections
assets/                   Images used by reference-PDF tooling
cluster_analysis/         Research-API clients, functional modules, library validation
injectors-authenticators/ Content tooling: LLM translation/generation/audit, injectors, validators
tests/                    Unit tests (python -m unittest discover tests)
```

The tooling scripts are described in [docs/CONTENT_TOOLING.md](docs/CONTENT_TOOLING.md).

## Imputation

`src/impute.py` fills in the ~28 million common and rare variants the raw file doesn't contain. It runs locally with Beagle 5.5 and the 1000 Genomes phase 3 panel, so the genome never leaves the machine. It needs Java 11+ and the reference files fetched by `scripts/fetch_imputation_reference.sh` (about 5 GB).

```bash
python -m src.impute data/input/MyHeritage_raw_dna_data_XY.csv --validate 10   # accuracy check -> calibration.json
python -m src.impute data/input/MyHeritage_raw_dna_data_XY.csv                 # impute, then grade every call
```

Every imputed call gets a confidence tier, measured on the person's own file. The validation run hides 1 in 10 of their measured SNPs, re-imputes them, and records how often calls like each one came back right. "Like it" means the same allele frequency band, the same genotype-probability band, and the same direction (carrier or not).
- **high:** ≥ 98% right.
- **medium:** ≥ 90% right.
- **low**, **untested**: below that, or too few test SNPs to tell.
- **not_excluded:** a "doesn't carry it" call in a band where imputation misses too many real carriers, which applies to rare variants. It means "not detected", never "not a carrier".

The loaders (`src/loader.py`) pick tiers by use. Single-SNP conclusions (the library, drug response, pathogenic variants) take measured and high calls; theme statistics also take medium. The output goes to `data/output/imputation/<person>/`, which git ignores like all genotype data.

## Requirements

- Python 3.10+
- Runtime: `pandas`, `numpy`, `plotly`, `kaleido` (static PNG export), `fpdf` (PyFPDF 1.7.x)
- Tooling only: `google-genai`, `python-dotenv`, `requests`, `networkx`, and a `GOOGLE_API_KEY` in `.env` for the LLM scripts.

## Further reading

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): data flow, scoring, matching, and report assembly
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md): schemas for every file in `config/`
- [docs/CONTENT_TOOLING.md](docs/CONTENT_TOOLING.md): the LLM, audit and injection scripts
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md): known bugs, risks and the improvement backlog
