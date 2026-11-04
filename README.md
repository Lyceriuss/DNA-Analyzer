# DNA-Analyzer

An in-house tool that turns a consumer raw-DNA export (MyHeritage / 23andMe-style CSV) into a multi-page, illustrated PDF report. The report covers ~280 curated SNPs across ten health domains, with actionable health advice for each result. It can be produced in English or Swedish, and it can optionally compare the subject with one or two relatives.

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
config/backup/            Hand-made snapshots of older config versions
assets/                   Images used by reference-PDF tooling
injectors-authenticators/ One-off maintenance, validation and injection scripts
agent_flow.py             LLM translation pipeline (Gemini): EN → SV evidence DB
agent_flow_deepdive.py    LLM generation of new evidence entries
script.py                 LLM fact-check audit of deep-dive narratives → rewrite_needed.json
evidence_db_injector.py   Validates and merges new evidence entries
CSV_SNP_compare.py        Finds genotypes in input CSVs that the traits DB can't match
```

The tooling scripts are described in [docs/CONTENT_TOOLING.md](docs/CONTENT_TOOLING.md).

## Requirements

- Python 3.10+
- Runtime: `pandas`, `numpy`, `plotly`, `kaleido` (static PNG export), `fpdf` (PyFPDF 1.7.x)
- Tooling only: `google-genai`, `python-dotenv`, `requests`, and a `GOOGLE_API_KEY` in `.env`. These packages are **not** in `requirements.txt` yet.

## Further reading

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): data flow, scoring, matching, and report assembly
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md): schemas for every file in `config/`
- [docs/CONTENT_TOOLING.md](docs/CONTENT_TOOLING.md): the LLM, audit and injection scripts
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md): known bugs, risks and the improvement backlog
