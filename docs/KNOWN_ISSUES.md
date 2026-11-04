# Known issues & improvement backlog

Snapshot from a review on 2026-11-04. P0 means fix first. Items that have been fixed are listed at the bottom.

## P0: privacy

- **Personal genotypes are in the public git history.** `genomic_audit_report.csv`, `final_genomic_alignment_check.csv` and `final_hardware_alignment.csv` were committed in `8b3ce28`, `129ded7` and `7c86dfb` (and later deleted). They contain real `RSID → genotype` rows from input files. The GitHub repo is public. Deleting a file doesn't remove it from history. Rewrite history (`git filter-repo`) or make the repo private.
- Some scripts hardcode file names that carry initials (`MyHeritage_raw_dna_data_GA.csv`, `..._HP.csv`). Take them from CLI args instead.

## P0: content says the wrong thing

**Library validation (2026-11-04):** `python -m cluster_analysis.validate_library` checked all 282 entries against Ensembl and the GWAS Catalog. It found **73 errors**: 61 entries filed under the wrong gene, 10 with impossible genotype letters, 7 suffixed keys that never match a DNA file, and 2 unknown rsIDs. It also found 37 warnings, including 30 strand-ambiguous A/T and C/G SNPs. In the HP report, 13 of 91 deep dives rest on an erroring entry. See `cluster_analysis/library_validation.md`.

- **Evidence/deep-dive entries describe a different gene than the trait.** `python injectors-authenticators/validate.py` lists them. Aliases such as BCMO1/BCO1, TNF-alpha/TNF and HLA-DQ8/HLA-DQB1 can be ignored. The real conflicts are:

  | RSID | snp_traits | evidence / deep dive |
  |---|---|---|
  | rs444697 | ASMT | CDKN2B-AS1 (9p21 / ANRIL) |
  | rs1042522 | TP53 | POMC (both files; rs1042522 is the well-known TP53 Arg72Pro) |
  | rs7799039 | LEP | PNPLA3 |
  | rs1049434 | COL12A1 | CKM |
  | rs1110400 | SOD1 | MC1R |

- **Narrative and evidence can contradict each other.** CYP1A1 rs1048943 `TT` gets the "Balanced Detoxifier" strength page, while its own research section says the hyper-active variant raises lung-cancer risk in smokers.
- Narratives are written per *direction* (strength/risk), not per genotype. Since 2026-11-04 only scores ≥ 7 / ≤ 4 get a deep dive, and self-references ("Your AG genotype") are rewritten to the reader's genotype at render time. Text that describes a specific allele in other words still needs a content pass.

## P0: correctness

1. **Inheritance logic is conceptually wrong.** A child always receives exactly one allele from each parent. Comparing *whole genotypes* means:
   - child `AG`, mom `AA`, dad `GG` → "Mixed / Recombined", when the actual answer is A from mom and G from dad;
   - child `AA`, mom `AA`, dad `AG` → "Match: Mom", even though one A must have come from dad.
   Rework it per allele: work out which parent could have supplied each allele, and flag Mendelian inconsistencies (useful for spotting sample mix-ups and strand errors). With a single relative, only "consistent / inconsistent" can be stated.
2. **One SNP per gene.** `drop_duplicates(subset=['Gene'])` hides additional SNPs, for example MTHFR rs1801131 when rs1801133 is present. Decide whether that is intended, or group by gene and show both.
3. **Palindromic SNPs (A/T, C/G)**: about 31 traits can't be strand-resolved by complementing. MyHeritage reports the forward strand, so pinning those traits to the forward strand would be safe.
4. **Silent misses.** RSIDs missing from the panel are dropped without a trace. Report the count ("X of 282 not tested").

## P1: one-page layout, remaining

- The deep-dive fitter steps the body font down to 8pt. ASMT (rs444697) needs clipping even at 8pt. Its oversized evidence text also belongs to the wrong gene (see above).
- `main.py` prints a fit summary after each run (`📐 Deep dives: … | shrunk: … | clipped: …`). Shorten those entries at the source.
- The footer is drawn inside the confidence panel area. It is readable, but it would look cleaner placed below the panel.

## P1: localisation gaps (Swedish report)

- `ui_labels.json → Swedish` lacks `introduction_education`, so all 4 intro pages print in English.
- These headings are hardcoded in English in `report_engine.py`: "Introduction & Philosophy", "Interpreting Your Genetics (1/3)", "The Factory Floor…", "Upstream & Downstream Effects", "The Vulnerability Cascade", "Embracing Your Blueprint", the `"Domain:"` text in the summary pages, and the `"/ 5.0"` suffix.
- Trait names, interpretations and domain names in the tables stay in English.
- 3 deep dives and 3 evidence entries are not translated yet. German is declared but has no data.

## P1: content quality

- Most narrative and evidence text was written or translated by an LLM. The audit (`script.py`) flagged **120 RSIDs** in `rewrite_needed.json`. Many of those failures are structural (a missing `risks` list), but some are factual: `rs429358` (APOE) was flagged as logically inverted relative to its scores.
- `impact` has 4 non-standard values ("Beneficial", "Altered DHT levels", …). They now sort as Medium.
- 17 deep dives belong to RSIDs that don't exist in `snp_traits.json`, so they are dead content. 8 traits have no evidence entry.

## P2: engineering hygiene

- Test coverage is still thin (`tests/` covers only the normalizer and genotype personalisation). Add `domain_mapper` and `inheritance` next.
- Nothing in `requirements.txt` is pinned. `fpdf` is the unmaintained 1.7 line. `fpdf2` adds Unicode TTF fonts, which would remove the Latin-1 `clean_text` downgrade.
- Dead code: `add_educational_page`, `get_text_height`, and `proxy_handler` (disabled).
- `domain_mapper` uses substring keywords, and the first match wins ("cell", "dna" and "eye" are broad). A `domain` field in `snp_traits.json` would be explicit.
- Tooling scripts run on import, hardcode paths, and overwrite config files in place without backups. Wrap them in `if __name__ == "__main__":`, add CLI args, and write to a temp file before an atomic rename.
- Committed clutter: `bash.exe.stackdump`, `audit_*.log` and `config/backup/` (git already keeps history). Add them to `.gitignore`.
- Bare `except:` clauses hide errors in `report_engine.py`.
- Emoji `print`s crash on a cp1252 Windows console unless `PYTHONIOENCODING=utf-8` is set.
- The interactive-only CLI makes batch runs and testing hard. Add `argparse` (`--input`, `--mom`, `--dad`, `--lang`) and keep the menu as the fallback.
- `main.py` mixes orchestration and layout (the section covers are drawn inline). Move them into `PDFReport` methods.

## Fixed (2026-11-04)

- Unsorted genotype keys in `snp_traits.json` dropped heterozygotes. Keys are now normalised in `analyzer.py`, with unit tests. HP: 189 → 194 matched traits.
- Deep dives were ordered by an alphabetical Impact sort. They now use an explicit rank.
- `main.py` added a duplicate blank "Key Active Traits" page and built `ReportEngine` twice.
- A score of 6 ("Normal") received the strength narrative. Thresholds are now `STRENGTH_MIN_SCORE = 7` and `RISK_MAX_SCORE = 4` in `report_engine.py`.
- Hardcoded genotypes in narratives ("Your AG genotype") are now rewritten to the reader's genotype.
- Deep dives spilled onto a second page, and evidence was silently dropped past y = 225. Layout is now measured first, the font shrinks in steps, and clipping is a last resort. The methodology audit is clipped to the panel box.
- Tables were 190mm wide on a 178mm printable width. Columns now scale to fit, and cell text is cut off with "..." by measured width.
- The footer label key was wrong, so Swedish showed "Page". It now shows "Sida".
- Zebra striping used the DataFrame index.
- Tooling dependencies were added to `requirements.txt`.
- `validate.py` now checks that the gene symbol for each RSID agrees across all three files.
