# Known issues & improvement backlog

Snapshot from a review on 2026-11-04. P0 means fix first. Items that have been fixed are listed at the bottom.

## P0: privacy

- **Personal genotypes are in the public git history.** `genomic_audit_report.csv`, `final_genomic_alignment_check.csv` and `final_hardware_alignment.csv` were committed in `8b3ce28`, `129ded7` and `7c86dfb` (and later deleted). They contain real `RSID → genotype` rows from input files. The GitHub repo is public. Deleting a file doesn't remove it from history. Rewrite history (`git filter-repo`) or make the repo private.
- Some scripts hardcode file names that carry initials (`MyHeritage_raw_dna_data_GA.csv`, `..._HP.csv`). Take them from CLI args instead.

## P0: content says the wrong thing

**Library validation (2026-11-04):** `python -m cluster_analysis.validate_library` checked all 282 entries against Ensembl and the GWAS Catalog and found 73 errors. They were corrected the same day with `injectors-authenticators/corrections_2026_11/apply.py`:

- 13 entries were rewritten for the gene actually at the site: ATG16L1, SLC2A2, MC1R, MCT1, PER2, CYP3A7*1C, ALPL, CNNM2, MSMB, HSD3B1, SRD5A2, plus the TP53 deep dive and the LEP evidence.
- 6 entries were moved to the correct standard SNP: F2, SLC2A9, SLC22A5, CYP2D6*4, AOC1/DAO, SOD3.
- The FOXO3 allele letters were fixed.
- 53 entries were removed, with each reason recorded in `config/backup/library_corrections_2026-11-04.json`.

Two entries were scored on the wrong strand: **TP53 rs1042522**, and **ATG16L1 rs2241880**, whose scores were inverted.

The library now has **229 traits, 0 errors and 38 warnings**. Remaining work:

- **23 A/T or C/G SNPs** still need their strand checked. TP53 proved these can be silently inverted. Use Ensembl's per-allele amino acids, then add each one to `STRAND_VERIFIED` in `validate_library.py`.
- Some evidence texts in rewritten entries came out 20–30 % shorter than the originals. This is mostly the methodology fields and the LEP evidence.

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
3. **Palindromic SNPs (A/T, C/G)**: 23 traits can't be strand-resolved by complementing and are not yet verified (see `STRAND_VERIFIED` in `cluster_analysis/validate_library.py`).
4. **Silent misses.** RSIDs missing from the panel are dropped without a trace. Report the count ("X of 229 not tested").

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

- Most narrative and evidence text was written or translated by an LLM. The audit (`audit_deep_dives.py`) flagged **120 RSIDs** in `rewrite_needed.json`. Many of those failures are structural (a missing `risks` list), but some are factual: `rs429358` (APOE) was flagged as logically inverted relative to its scores.
- `impact` has 4 non-standard values ("Beneficial", "Altered DHT levels", …). They now sort as Medium.
- **15 orphan deep dives** have narratives but no `snp_traits.json` entry, so they never render: rs1143627, rs11568820, rs12255372, rs17616434, rs1799990, rs1800796, rs1800797, rs1801131 (MTHFR A1298C), rs2228570, rs2854464, rs3025039, rs6269, rs731236 (VDR TaqI), rs7412 (APOE, needed with rs429358 for e2/e3/e4), rs8111989. Add trait entries (and validate them) to activate them. 1 trait has no evidence entry.

## P2: engineering hygiene

- Test coverage is still thin (`tests/` covers only the normalizer and genotype personalisation). Add `domain_mapper` and `inheritance` next.
- Nothing in `requirements.txt` is pinned. `fpdf` is the unmaintained 1.7 line. `fpdf2` adds Unicode TTF fonts, which would remove the Latin-1 `clean_text` downgrade.
- `proxy_handler` is disabled (the call in `analyzer.py` is commented out).
- `domain_mapper` uses substring keywords, and the first match wins ("cell", "dna" and "eye" are broad). A `domain` field in `snp_traits.json` would be explicit.
- Tooling scripts hardcode paths and overwrite config files in place without backups. Add CLI args and write to a temp file before an atomic rename.
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
