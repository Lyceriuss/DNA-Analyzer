# From dev to production

Where the explorer stands, what it needs before other people can run it, and the ways to get it to them. Written
2026-11-20. It builds on the product decision of 2026-11-12: people run it themselves, on their own DNA file, on
their own machine. There is no hosted service and no accounts. [migration.md](migration.md) covers the earlier plan
for a hosted service.

## Where it stands

| Part | Today | In someone else's hands |
|---|---|---|
| Code | Python 3.10, the global interpreter, run from a clone | needs a pinned, packaged environment |
| Python packages | `requirements.txt` lists 6; the agent also imports `anthropic` and `mcp` | an incomplete list breaks a fresh install |
| Java | Beagle 5.5 for imputation, with a 12 GB heap by default (the pipeline scales it to the machine) | many laptops have 8-16 GB of RAM |
| Imputation references | 14.3 GB: the 1000 Genomes panel (12.7 GB) and its site list (1.5 GB) | one-time download, plus disk |
| Analysis references | about 0.8 GB: GWAS Catalog, ClinVar, ClinPGx, CPIC, Reactome, UniProt, GTEx, PGS scores | one-time download |
| Rebuild sources | 45 GB (raw panel, dbSNP), GRCh37 extras | for us only; never shipped |
| Lookup cache | `cluster_analysis/cache`: every API answer the analysis has fetched on this machine, 8.9 GB in 47,000 files here | a new user starts empty: hours of API calls on a first run, and the app can't start offline |
| Paths | the panel on `D:\DNA-Analyzer-reference`, moved with `DNA_PANEL_ROOT` and `DNA_PANEL_DIR_1KGP_HC`; the cache with `DNA_CACHE_DIR` | the panel and the cache are configurable; `data/` is still under the code folder |
| Adding a person | browser dialog, then check, register, impute (~15 min), analyse, rebuild; resumable | works as is |
| Explorer | static site and a local server on 127.0.0.1 | works as is |
| Ask | the user's own API key, or a Claude Code login (found through the VS Code extension) | API key only, in practice |
| Profiles | developer profiles (XX, XY, XX_1, XY_1) and HG00096, a public 1000 Genomes sample | an empty start, with HG00096 as a demo |

## What production needs, whatever the packaging

1. **A complete, pinned environment.** Pin the Python packages with versions (add `anthropic` and `mcp`), the Python
   version, and a Java runtime. Use a lock file built from a clean install, not from this machine.
2. **One data folder.** Put every path (references, cache, input, output) under one configurable root, with no drive
   letters. That includes the hard-coded panel path in `genome/impute.py`.
3. **A references downloader.** The manifest (`genome/references.json`) already records where each file comes from
   (`source`, `get`). Add a `fetch` command for the analysis and imputation tiers, with resume, checksums (the
   `lock` and `verify` commands exist) and a progress bar in the page. Check each source's licence for
   redistribution before hosting a bundle of our own. ClinPGx, ChEMBL and others ask for attribution, some under
   share-alike terms. Downloading from the original sources avoids redistributing.
4. **The knowledge bundle (migration step 4).** Precompute the lookups the analysis makes per gene and variant
   (Open Targets, Ensembl VEP, Europe PMC findings, function evidence) for every variant a supported chip can
   carry. Ship it as a versioned file. This matters most:
   - **Starting at all:** even an empty install looks up public variant data to build the page. Without the cache,
     the desktop build's first start hit Ensembl time-outs and failed.
   - **Speed:** minutes instead of hours on a first run.
   - **Reproducibility:** each report names the data release it used.
   - **Privacy:** already largely designed in. The lookups run over fixed sets (every gene's eQTL variant, the
     library's variants, the theme genes), not over what one person carries, so "a run for anyone fills the cache
     for all" (`evidence/gene_calls.py`). The bundle removes the remaining live calls.
5. **First run.**
   - **Start empty.** Remove the developer profiles from the shipped `profiles.json` and keep HG00096 as a demo.
   - **Explain the steps in the page:** the references download, how to get a raw file from MyHeritage, AncestryDNA
     or 23andMe, then adding a person.
6. **Machine requirements, measured.** The pipeline already measures the machine and estimates times
   (`pipeline machine`). Publish minimums for RAM, disk and time, and refuse to impute where Beagle can't fit.
7. **Ask setup.**
   - **The API key encrypted at rest**, not in a plain file under `data/output`. Done 2026-11-23: DPAPI on
     Windows, mode 600 on Linux (`agent/keystore.py`).
   - **The cost per question shown before the first one.** The token line already shows it after.
   - **Ask stays optional.** The rest of the explorer works without a model.
8. **Security for a local app.** It already binds to 127.0.0.1, checks a header against cross-site requests, and
   limits uploads to 300 MB. Keep it single-user.
9. **Updates.** Version the app and the reference releases separately, re-export the datasets when the app changes,
   and keep a changelog the page can show.
10. **Quality gates.** Run the tests (`python -m unittest discover -s tests`) and `explorer check` in CI on Linux and
    Windows, plus a golden set of Ask questions (see [ask-decisions.md](ask-decisions.md), Open).
11. **Clean-up.** Remove the old claude.ai publish path, the unused v1 agent and quick answer, and the SNP library
    still being phased out.
12. **Legal review before release.** Software that interprets an individual's genetic data can fall under the EU
    rules for medical devices and in-vitro diagnostics, depending on its intended purpose. Genetic data is a special
    category under GDPR. Running locally keeps us from processing anyone's data, but it doesn't settle the
    intended-purpose question. The risk-and-evidence wording (D22) helps; a lawyer should confirm the positioning,
    the terms of use and the licence notices.

## The ways to ship it

| Option | Who it suits | What the user does | For | Against |
|---|---|---|---|---|
| **Docker image** (compose file, data in a volume) | technical users, early testers | install Docker, run one command, open localhost | the same Linux environment everywhere; Java and Beagle inside; easy to update | everyday people don't have Docker; Docker Desktop has licence terms for larger companies; on Windows the WSL2 disk grows and doesn't shrink (we hit this) |
| **Desktop app** (installer per OS, Python and Java bundled, page in a window or the browser) | everyday people | download, install, open | the most familiar path; double-click, no terminal | builds per OS; code signing (an Apple developer account and notarization, a Windows certificate); an auto-updater |
| **Lite mode** (measured chip variants only, no imputation) | everyone, as the default | nothing extra | no 14 GB download, no Java, no 12 GB heap; a first result in minutes | fewer variants: scores and some genes are less complete; full imputation becomes an optional download |
| **pipx or pip package** | developers | `pipx install …`, then run | cheap to do; a clean environment | Java and the references are still separate steps |
| **Browser only** (WebAssembly, the DNA file never leaves the browser) | everyone, later | open a page, pick the file | no install; nothing uploaded | imputation isn't realistic in a browser; needs the knowledge bundle first; a large rewrite of the analysis |
| **Hosted service** (upload, report, data deleted) | everyone | upload | the simplest for users | against the 2026-11-12 decision: we would process other people's genetic data (GDPR special category, EU hosting, security, liability) |

## Recommendation

1. **Make it portable.** Do points 1, 2, 3, 5 and 10 above. This is the base for every option.
2. **Build the knowledge bundle (point 4).** Without it, any packaging still sends a person's variant ids to public
   APIs and takes hours on a first run.
3. **Ship a Docker image to testers.** It finds the setup problems cheaply, on people who can report them.
4. **Build a desktop app for everyone, with lite mode as the default.** Make full imputation an optional download
   for machines that can run it. Lite mode decides whether everyday people can use the app at all: it removes the
   14 GB download, Java and the large memory need.
5. **Get the legal review (point 12)** before a public release.

A hosted service stays a later choice, and only if the decision of 2026-11-12 changes.

## The precomputed lookups (the knowledge bundle)

What the cache holds today, by kind:

| Kind | Examples | Files | Size | Depends on |
|---|---|---|---|---|
| Per protein | UniProt variation records (`prot_variation`), entries and function texts | 8,600 | 6.5 GB | the gene list (theme graphs, library) |
| Per variant | Ensembl VEP records, GTEx eQTLs, GWAS per variant, MaveDB scores | 6,500 | 1.5 GB | fixed variant sets (each gene's eQTL variant, library and curated variants) |
| Per pathway or gene | Reactome events, ancestors and reactions, STRING networks, Open Targets, QuickGO, OmniPath | 17,000 | 0.2 GB | the gene list |
| Literature | Europe PMC searches, full texts, study findings by genotype | 1,100 | 0.13 GB | genes, variants and topics |
| Ask | the research index (GWAS, ClinVar, 1000 Genomes sites), readings written once per category | a few | 0.65 GB | public files; readings are the same for everyone |

**How to build it:** run the lookups over the whole universe once, not per person: every gene in the theme graphs
and the library, every variant a supported chip measures or the panel imputes in those genes. Then compact it.
Measured for the protein records (2026-11-20): 4,218 of the 4,255 cached proteins belong to genes the explorer
still asks about, but the analysis reads only variant features with a dbSNP id and, from them, the change, the
genomic location, curated notes, SIFT and PolyPhen, and experimental PubMed ids. Those fields are 752 MB of the
6.54 GB (11.5%). Keeping only what is read, as a table per kind in one SQLite file, shrinks the bundle by about 88%
before compression. Version it by
build date, refresh it monthly, and let the app download it on first start next to the references.

**How the app uses it:** `sources._cached` already reads the cache before calling an API, so the bundle only has to
be unpacked into the app's cache folder (`DNA_CACHE_DIR`). A lookup missing from it still falls back to the live
API, logged, so gaps can be found and added in the next release.

## Status (2026-11-20)

- **Docker for developers:** `Dockerfile`, `compose.yaml` and `.dockerignore`. The code is mounted live, `data/` and
  the cache stay on the host, the panel is mounted read-only from `DNA_REFERENCE_DIR`, and the port is published on
  127.0.0.1 only (`DNA_BIND_HOST=0.0.0.0` inside). Not built yet: WSL on this machine was hung (`wsl -l` failed,
  `WSLService` stuck stopping), so Docker Desktop's engine couldn't start.
- **Desktop app, Windows:** `scripts/build_desktop.py` builds a 1.32 GB folder (`D:/DNA-Analyzer-build`):
  - the embeddable Python 3.10.11 with the pinned packages (266 MB)
  - a 31 MB Java runtime from jlink, which runs Beagle 5.5
  - the code, unfrozen, so the pipeline's own `python -m` steps work
  - the analysis references (0.98 GB)
  - `launch.py` and `Troubleshoot (console).cmd`
  Tested: the bundle's Python loads only its own code; the launcher builds the page, picks a free port, waits and
  opens it; the pipeline finds Java, the panel and the disks. It starts with no profiles.
- **Found on the way:** a fresh install failed twice. The export needed the Gene pathway file built for one developer
  profile (now optional), and the page build made live API calls (the knowledge bundle). The Home tab still shows the
  developer default "XY" with no one added.

**Next for the desktop app:** the knowledge bundle; a references downloader in the page; a first-run screen; lite
mode; then an installer (Inno Setup or MSIX), code signing, and macOS and Linux builds.

## Plan: installers for Windows and Linux, and a web app for phones (2026-11-20)

People download from our site: an installer for Windows or Linux, or the web app, which also runs on a phone. Both
are wanted. The rule of 2026-11-12 holds for both: the DNA file and the results stay on the person's device.

### One engine, two runtimes

| | Desktop (Windows, Linux) | Web app (any browser, phones included) |
|---|---|---|
| Runs | the Python pipeline and the local server, from the installer | static files from our site; the analysis in the browser |
| Imputation | optional download (panel 14 GB, Java, 8+ GB of RAM) | never: measured variants only (lite mode) |
| Lookups | the full knowledge bundle | the lite pack: only the variants a chip can measure, compacted |
| Ask | the full tool loop, the user's API key | the user's API key, called from the browser (later phase) |
| Results | kept in the app's data folder | kept in the browser (IndexedDB); a results file can come from the desktop |
| Our servers see | the download | the page's files, never a DNA file |

The page is already a static site reading datasets (migration.md), so both runtimes share it. What differs is who
writes the datasets: the Python pipeline on the desktop, a browser engine on the web.

### Phase 0: the shared base (before either ships)

1. **Knowledge bundle**, versioned and compacted (the protein records alone go from 6.5 GB to about 0.75 GB).
2. **Lite pack** cut from it for the web: per chip variant, its genes, the function call, the score weights, the
   ClinPGx texts per genotype and the study findings per genotype group. The aim is tens of MB, fetched once and
   cached; to be measured. The whole pack is fetched, never single variants, so the site can't learn which variants
   a person has.
3. **Lite mode in the pipeline:** an analysis from measured variants only, with the scores marked as based on
   fewer variants. The desktop offers it first, with imputation as an upgrade; the web uses only this.
4. **A results file:** one person's datasets as one versioned file, so a desktop result can be opened on a phone.
5. **The page on a phone:** a responsive pass over every tab. The header now stacks; the tabs and some tables still
   run wider than a 420 px screen. Touch-sized controls, and the views (cluster network, logic web) readable when
   small.
6. **First-run screen**, references and bundle download with progress, and an empty start.

**Done (2026-11-20):**

- **Knowledge bundle:** `python -m cluster_analysis.knowledge build | install | status`. It packs this machine's
  lookup cache as `knowledge-<date>.zip` (+ `.sha256`): the protein records cut to the fields read, Ensembl's batched
  lookups repacked as sorted, deduplicated chunks (no chunk shows which ids were asked together), and Ask's
  model-written readings and search results left out. First build: 9.2 GB of cache, 361 MB packed, 3.3 GB unpacked.
  `install` unpacks into `DNA_CACHE_DIR` and keeps files already there; once a bundle is installed, a lookup it
  lacks is logged to `misses.log` in the cache (`status` lists them) and still fetched live.
  `knowledge fill` first runs the public sample (HG00096) through every step with the current code, so the bundle
  holds every lookup the code makes, not a snapshot of what this machine happened to ask: the first bundle, built
  without it, missed 9 lookup batches in a fresh install's run (Ensembl VEP for eQTL variants added since this
  machine's last gene-calls run, one STRING network). After `fill`, the rebuilt bundle (362 MB packed, 3.3 GB
  unpacked) served a fresh install's whole lite run with no live lookup at all. Lookups a bundle brought (its
  repacked chunks) are folded back in on the next build, not packed twice.
- **Lite mode:** `pipeline add --lite`, and the first choice in the Add-a-person dialog ("Measured variants",
  with "With imputation" offered only where Java, Beagle and the panel are present). `genome/lite.py` moves the
  measured calls to GRCh38 with the same chain file imputation uses and writes them in the imputed file's format,
  all "measured" (`<person>.measured.csv`, which `loader.imputed_path` reads when there is no imputed file). The
  profile carries `"lite": true`; Home says the person has no imputation.
- **Lite mode's quality,** measured on HG00096 (same file, lite vs imputed, 2026-11-20):

  | | Lite vs imputed |
  |---|---|
  | Lab-test scores (19) | 17% of the variants; median shift 10 percentile points, up to 72; 6 change band (≤20 / middle / ≥80) |
  | Cancer scores (8) | 53% of the variants; median shift 6 points, up to 22; 1 changes band |
  | Drug genes (12) | 11 identical; CYP2C19 read *1/*1 "Normal" because the chip lacks rs4244285 (*2) |

  The CYP2C19 result was wrong, not just less complete, so the medicines caller now refuses to call a gene when a
  defining variant the file doesn't read belongs to an allele that changes function and that 1% or more of any
  ancestry carries (`medicines.unread_common`): "Not determined: a common variant isn't read", with the variant,
  the allele and its frequency, and no guidance treating the gene as typical. On HG00096 lite this covers CYP2C19
  (*2), CYP2C9 (*3), CYP2D6 (*41) and DPYD (HapB3); the imputed run is unchanged. For the web app: drug genes are
  safe to show with this rule; polygenic scores built from a few hundred variants move too much on a chip alone to
  be shown as bands without a "based on N of M variants" mark.
- **Results file:** `python -m cluster_analysis.explorer results export --person ID | import FILE [--as ID] | list`,
  and "Save results" / "Open results" in the page header. One person's rows from every dataset, gzipped (2 MB for
  the HG00096 sample); an import is kept in `data/output/imported_GRCh38/` and merged on every export. Refused when
  made on another genome build.
- **First run:** with no one added, Home opens with a welcome card: the research data (install the bundle from
  `data/knowledge/` or `DNA_KNOWLEDGE_URL`, with progress), where to get a raw file, and Add a person or Open a
  results file.
- **Phones:** measured at 390 px in a frame for every tab: no tab makes the page scroll sideways. The body-map and
  cell drawings now keep a readable size and scroll inside their box; the tabs are finger-sized on touch screens.

### Phase 1: desktop installers

1. **Windows:** the current build (`scripts/build_desktop.py`) wrapped in a per-user installer (Inno Setup or
   MSIX), installed under `%LOCALAPPDATA%`, data kept apart from the program so updates don't touch it, a
   Start-menu entry, an uninstaller that asks whether to delete the data.
2. **Linux:** the same layout with a standalone Python build (python-build-standalone) instead of the Windows
   embeddable one, as an AppImage plus a tarball; a .deb later.
3. **Signing and updates:** a Windows code-signing certificate; checksums and signatures for Linux; an update check
   against our site that downloads a new version and keeps the data folder.
4. **macOS** after these: the same bundle, with notarization.

**Done (2026-11-20):** `python scripts/build_desktop.py --release --installer [--target linux]`, version from
`cluster_analysis/version.py` (0.1.0).

- **Windows:** an Inno Setup installer, `DNA-Analyzer-0.1.0-setup.exe`, 1.0 GB, per-user (no administrator), into
  `%LOCALAPPDATA%\DNA-Analyzer`, with a Start-menu entry. An update replaces the program, the references and the
  bundle; it never touches `data/input`, `data/output`, the cache or the profile list. The uninstaller asks whether
  to delete the people and results (default: keep). Tested: silent install in 96 s; first start unpacks the
  bundle and serves the page in 105 s (25 s after that); the HG00096 sample added in lite mode through the page's
  API, all 8 steps, in 20 minutes with no live lookup; a silent uninstall keeps `data/` and removes the program and
  the Start-menu entry.
- **Linux:** `DNA-Analyzer-0.1.0-linux-x86_64.tar.gz`, 1.17 GB: CPython 3.10.22 from python-build-standalone, the
  packages resolved for manylinux with `uv` (pip reads the dependencies' platform markers for the build machine),
  the Temurin 17 JRE, `start.sh`, and `install.sh`, which installs into `~/.local/share/DNA-Analyzer` with a menu
  entry and keeps the data and the profile list on update. Checked by listing it (executable bits, Linux
  libraries, no personal files); **not yet run on Linux** (WSL is hung on this machine).
- **Only files git doesn't ignore are packed**, so nothing under an ignored path (data/, caches) can reach an
  installer; the release folder was checked for profiles, inputs, outputs and paths to this machine.
- **Updates:** the page asks `DNA_UPDATE_URL` (a small JSON on our site: version, installer URLs, checksums,
  notes) once per start and shows "Version X is out" in the header. No feed exists yet.

**Unfinished runs kept out of sight (2026-11-23).** Testing the installed app showed the site usable with no one
added (a default name and zeros), and a person whose run had stopped shown from a half-written imputed file.
- **The page is locked to its first-run screen** (`explorer/fr.js`, `.gx-locked` in `fr.css`) while the built page
  lists no one: the server's `/api/setup` and `/api/status` report `shown`, the people in the site's
  `data/profiles.json`. Only the welcome steps (research data, "Add a person", "Open a results file") and the run's
  progress show; the page reloads, unlocked, once the first person is in. With someone shown, the explorer stays
  usable while another is added. A page without the server's API (opened from disk) isn't locked.
- **Only finished people are listed.** `pipeline.register` marks a new person `pending` in `profiles.json`, and the
  end of the run removes the mark. `profiles.load()` lists a person only without the mark and without a run record
  (`data/output/pipeline/<id>.json`) that isn't done, so a run registered by an older version counts as unfinished
  too; people added by hand have neither and are listed. A run's own analysis and export see their person through
  `DNA_PROFILE_RUNNING`. `explorer serve` exports again when the datasets list someone unfinished. A stopped run
  shows as stopped, with Resume and Abandon, and a run left "running" by a killed process resumes where it was.
- **Files are written whole or not at all:** the imputed CSV, `summary.json` and `calibration.json`
  (`genome/impute.py`) and the lite CSV (`genome/lite.py`) under a `.partial` name, renamed when complete.
  `genome/loader.imputed_path` takes an imputed CSV only with a `summary.json` holding totals at least as new as it,
  which also rejects a half file an older version wrote in place.

**Using it like an app; the API key encrypted (2026-11-23).** How to use it, in `README.txt` in the program folder
and on the installer's last page: 1. install with the setup.exe; 2. start it from the icon on the desktop or in the
Start menu; 3. the browser opens on the app.
- **Shortcuts:** a desktop shortcut (now ticked by default) and a Start-menu entry, both with the app's icon
  (`app.ico`, drawn by `build_desktop.icon()`, which needs Pillow on the build machine) and run through
  `pythonw.exe`, so no console window. "Stop DNA-Analyzer" in the Start menu stops it; the uninstaller and an
  update stop it first.
- **`launch.py`** (now `scripts/launch.py`, copied into the build): before, every start picked a new free port and
  started another server in a console window (closing it stopped the app). Now `data/server.json` names the running
  server's port and process: started again, it only opens the browser on it. Otherwise the server starts on port 8470
  (a free one if taken; `DNA_PORT`), with its output in `data/logs/server.log` (the launcher's in `launch.log`,
  errors also in a message box), and the browser opens when it answers. `Troubleshoot (console).cmd` and `start.sh` still run it in
  a console until that is closed; the Linux menu entry runs in the background. The one-time setup, unpacking the
  included knowledge bundle (`knowledge.ensure_included`), was already done once and skipped after (a version
  comparison); the page itself is rebuilt from its parts on each start, so an update shows.
- **The API key at rest** (`agent/keystore.py`): on Windows encrypted with DPAPI for the current user (ctypes, no
  new package); on Linux a file only its owner can read (mode 600), protected by file permissions only. A key saved
  as plain text by an earlier version is rewritten encrypted when first read. The server never returns it (the
  status says only whether one is set); it lives under `data/output/agent`, so it is in no results file, no
  knowledge bundle (built from the lookup cache only) and no installer (`data\` is excluded). `tests/test_api_key.py`
  and `tests/test_launch.py`.

**Still open:**
- **Size.** Most of the 1 GB is references already compressed: ClinVar (193 MB), Ensembl2Reactome (183 MB, every
  species: human rows only would be a fraction), the two GWAS Catalog zips (136 MB), the gene annotation (100 MB),
  the imputation map and Beagle (134 MB, only for the imputation upgrade), plus the 361 MB bundle.
- **Signing.** `SIGNTOOL` is passed to Inno Setup when set; it needs a code-signing certificate. Until then Windows
  SmartScreen warns on the download.
- **AppImage.** It mounts read-only, and the app writes next to its code (`data/`, `profiles.json`): it needs one
  configurable data folder (production need 2) first. The tarball installs fine without it.
- **The imputation upgrade** as a download (panel, sites, Beagle) for installs that want it; today a release build
  offers imputation only where the panel is already on disk.
- **Run the Linux tarball** on a Linux machine.

### Phase 2: the web app

1. **Static hosting** on an EU host with a strict Content Security Policy, no third-party scripts or analytics, and
   subresource integrity. Installable as a PWA, and works offline once loaded.
2. **The browser engine,** in a Web Worker, reading the raw file locally. It parses the chip formats, joins the
   measured genotypes with the lite pack, computes the scores, and writes the same datasets the page already reads.
   Two ways to build it:
   - **Pyodide,** running the Python pipeline in the browser: one code base, but tens of MB of runtime, slow on
     phones, and pandas is heavy there.
   - **A small JavaScript engine:** with the interpretation precomputed in the pack, the browser only joins and
     sums. This is lighter and faster on phones.
   Recommended: the JavaScript engine, with the pipeline generating the pack and a shared test set checking that
   both give the same results for the same file.
3. **Storage and deletion.** Results stay in IndexedDB on the device. A "delete everything" button wipes them.
   iOS Safari can clear site storage that hasn't been used for a while unless the app is on the home screen, so the
   page should say so and offer the results file as a backup.
4. **Opening a desktop result on a phone:** import the results file. No pairing or network link to the desktop is
   needed, and nothing goes through our servers.

### Phase 3: Ask on the web and on phones

The model is called from the browser with the user's own key: Anthropic's API allows browser calls when the
request opts in. The tools then have to run in the browser too. The public ones need sources that allow browser
requests; any that don't would need a proxy, which means our servers see the queries. The personal ones read the
local datasets. Until this is built, Ask stays on the desktop, and the web app links to it.

### Open questions

- **Lite mode's quality:** how much do scores and gene calls change without imputation? Measure it on the test
  profiles before choosing what the web app may show.
- **The lite pack's size and refresh rate,** and whether it splits by chip.
- **Legal:** one review covering both the installer and the web app (point 12).
