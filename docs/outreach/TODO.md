# Outreach and release: the to-do list

Started 2026-11-26. The path from the working app on one PC to a public release people can install, keep updated
and hear about, so that attention can turn into resources for a fuller version. Tick items off here and add the date;
the history of what was built is in [../CHANGELOG.md](../CHANGELOG.md).

## Where we start (decided 2026-11-26)

- A free, open-source, consumer tool: people run it on their own computer for themselves and their family, with
  their own consent. Protection comes from the licence's "as is" terms, local-only processing, Restricted mode on by
  default, and honest wording: risk and evidence, never clinical advice, and every scale saying how much it says.
- A commercial product may branch off later, as a separate repository and brand.
- Videos and public demos build reach; reach brings sponsors, grants and contributors.

## 1. Test the predictions on a real child (private)

- [x] Seal a forecast for a daughter of XX_1 and XY_1 before XX_2 is added: variant odds, trait predictions and the
      embedding (2026-11-26 18:28; `inheritance/forecast.py`).
- [x] Add XX_2 with her parents set, so no parent and child are paired as a couple (2026-11-26 18:33).
- [x] `forecast check XX_2` run (2026-11-26 19:30); the method's flaws are written up in
      `docs/architecture/inheritance.md`, without her results. Private: XX_2's results never go public.
- [x] Forecast and check kept as the first baseline (archived 2026-11-26 in
      `data/output/.../forecast_archive/2026-11-26_XX_1__XY_1/`); XX_2 removed from the app (2026-11-26 20:35), her
      original file kept for the re-import.
- [ ] Fix the logic: ~~the X chromosome in the trait models~~ (done 2026-11-26); exact child
      distributions for traits ruled by one rare variant; call errors in the simulated siblings; sex-specific studies
      where the Catalog has them; the check extended to drug types and carrier states; imprinted regions flagged.
- [ ] Reseal a forecast for XX_1 x XY_1 with the fixed logic, re-import and impute XX_2, check, and compare with the
      first baseline. Not blind any more (her results were seen), so fixes must be made on principle, not tuned to
      her misses; the public 1000 Genomes trio is the blind test.
- [x] A comparison view in Inheritance: predicted against actual for a child in the app (2026-11-26; `explorer/ic.js`).

- [ ] Review the curated GoF calls whose evidence note doesn't say gain of function (e.g. a note reading "no
      effect on ... activity"), found 2026-11-26 through Ask's GoF list.

## 2. The public demo family (1000 Genomes trio)

- [ ] Add a real, public parent-child trio from the 1000 Genomes panel (the CEU family: NA12878 and her parents
      NA12891 and NA12892) as demo profiles, from the panel genotypes already on D: (chip positions only, like a
      consumer file).
- [ ] Seal a forecast from the two parents, then reveal the daughter: Mendel check, trait fields, the embedding.
- [ ] Make it reproducible: one command anyone can run on the published data.

## 3. Release: installable and updatable

- [ ] Imputation pack: chrX (men's three-part split), the 23andMe and AncestryDNA chip layouts, the pipeline using
      the pack when the full panel is absent, validated against the full panel. About 1-1.5 days of work.
- [ ] Data packs and updates: the program, imputation pack, references and knowledge bundle versioned separately; a
      feed signed with our own key; in-app download, check, switch and rollback; "Recompute" for profiles built on
      older data. About 1-1.5 days.
- [ ] Release script and a fresh knowledge bundle (the fill runs 3-6 h of rate-limited lookups, overnight). About 0.5 day.
- [ ] Releases built by CI (GitHub Actions) from the public code, not on the development PC.
- [ ] Hosting: GitHub Releases (up to 2 GB per file), the feed beside it.

## 4. Before going public

- [ ] Choose the licence (recommended: Apache-2.0; AGPL-3.0 with a contributor agreement if stopping others' closed
      copies matters more than free signing).
- [ ] A privacy page: what leaves the computer (the user's chosen AI model, the update check) and what never does
      (the DNA file); shown in the installer too.
- [ ] A "what this is and isn't" page, and an issue tracker for reports.
- [ ] Check the data licences for redistribution (attribution: HPO, UniProt, Reactome, STRING; share-alike: ChEMBL,
      ClinPGx; any commercial restrictions, such as OMIM through HPO) and credit every source in the app and README.
- [ ] First releases unsigned, with SHA-256 checksums, to a small circle of testing families.
- [ ] Code signing: apply to SignPath Foundation once CI releases run (free for OSI-licensed projects; publisher shown
      as "SignPath Foundation"; needs a "Code signing policy" page, team roles, MFA, a privacy statement). Fallback:
      Certum's low-cost open-source certificate.

## 5. Videos

Never private DNA on screen except XY_1's (consent recorded in CLAUDE.md); never XX_2's.

- [ ] "What your DNA file actually says" (2-3 min): import, imputation, Biomarkers, impact levels.
- [ ] "We predicted a child from her parents' DNA" (5-8 min): the 1000 Genomes trio, sealed forecast, reveal.
- [ ] "Your data never leaves your computer" (2 min): Restricted mode, what the model sees, the open code.
- [ ] "Ask your genome": an Ask session with its drawings and sources.
- [ ] "Medicines and your genes": CPIC and ClinPGx.

## 6. Turning reach into resources

- [ ] GitHub Sponsors or Open Collective, linked from the README and the videos.
- [ ] Grants for open, privacy-preserving software (e.g. NLnet / NGI in the EU): check their current calls.
- [ ] Before any commercial branch: whether it counts as a medical device (EU IVDR/MDR), the GDPR duties of a
      company, and the data sources' commercial terms, with a specialist.
