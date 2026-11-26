# Changelog

What changed in each version and why, newest first. Every iteration adds its entry here (the version is in
`cluster_analysis/version.py`); the design behind each change is in `docs/architecture/`.

## 0.1.15 (2026-11-27)

**GWAS impact: how much each trait's scale says.** Every one of the 2,494 trait models has an impact score: the share
of the differences between people that the study's strongest (lead) variants explain, from each variant's p-value and
the study's size, the same way for every trait (`inheritance/gwas_impact.py`). Levels: high 8% and over, modest 3 to
8%, little under 3%. Over the 2,450 scorable traits the median is 3.34% and the mean 4.16% (half fall between 1.41% and
5.68%); measurements have a median of 3.82%, case-control studies (diseases) 0.32%. 44 studies get no figure (brain-scan
maps, multi-trait MTAG analyses, sums past 50%). Details and caveats: [inheritance.md](architecture/inheritance.md),
"How much a scale says".

- "See the genes" opens with **How much this score says**: the impact with its level, where the trait ranks among all
  traits, the median and average for comparison, and, for the familiar traits, what the study's own paper reports,
  quoted with a link (`inheritance/impact.py`, `impact_picks.json`).
- The Biomarkers trait list sorts by **Highest impact first**.
- The variant counts now say what they are: "193 of the study's 209 strongest variants read", not "of 209 variants".

**Inheritance opens like Biomarkers.** Every predicted trait opens with How much this score says (the GWAS impact,
its rank among all traits, and the paper's own figure for a familiar trait); both lists show an impact chip per row and
sort by "Highest impact first".

**Families.** A profile can name its `parents` (profiles.json). A parent and child, or siblings, are never paired as a
couple: the pipeline skips such pairs and both pair pickers (Inheritance, and Ask's Inheritance switch) leave them out.

**Predicted vs actual, in the Inheritance tab.** Once a child in the app has been checked against the forecast its
parents' pair sealed (`forecast check`), the tab gets a switch: Prediction, or Predicted vs actual for that child
(`explorer/ic.js`, cloned from the Inheritance module; dataset `inh_checks`, on this computer only). It shows the
seal and when it was made, scorecards (Mendel, settled variants, fields, correlation, information), the whole-trait
embedding among simulated daughters and strangers, the familiar traits with the predicted fields and the child's
actual place as a gold ring, every trait sorted by the biggest miss (filters: outside the 80% or 98% field), and the
single-gene traits' odds against the outcome.

**Tool groups named by what they read.** Every tool works for the person, so "yours" was the wrong word for one
group: the Ask panel, Sources and documentation and the PDF now say looks up research, reads your DNA, draws a view
(and answer step).

**Ask can list your GoF and LoF genes.** "Show me my GoF genes" used to fail: Ask had no tool for the explorer's
gene function calls. `my_genes_by_function` (GA) lists the person's genes called gain of function, loss of function
or altered, across the clusters or in one, each with its variant, genotype, copies and what the call rests on: a
reviewed protein change (ClinVar, UniProt, lab assays) or an expression effect (more or less of the same protein in
some tissues, GTEx), the reviewed ones first. The Ask tab draws them as a table. Most GoF calls rest on expression,
so the distinction matters. Found on the way: at least one "reviewed" GoF call rests on a note that says the
opposite ("no effect on ... activity"), a classifier issue to look at.

**Ask answers as a PDF.** "Save as PDF" beside every answer, and "Conversation as PDF" for several: a structured
report with the question and how it was read, the answer, key figures, how it ties together, the person's readings,
and the whole chain (every tool called with its letter logo, its arguments, what came back or why it was sent back,
and the databases and APIs it read), then the cited sources and follow-ups. Made on this computer from the saved
conversation; nothing is sent. `agent/report.py`; reportlab added to the app's packages. The tool-to-database map
moved into `explorer/ask_tools.json`, shared by the Ask tab and the PDF. Follow-ups: a question's PDF holds the conversation up to it, each follow-up
marked; a long sent-back message no longer breaks the PDF; the model's bold text and paragraphs come through. Ask's
child, trait and study tools now carry each trait's GWAS impact, so "how much does this matter" gets an answer. Every trait scale
Ask draws (a child's, and the person's own) shows "How much this score says" with its level chip and figure, as in
the Biomarkers and Inheritance tabs; the PDF's results table carries it too.

**The X chromosome in the trait predictions.** The 2,494 trait models used to leave out every X variant. Now X
associations count, a man's single X as 0 or 2 copies, each person ranked against their own sex there, a daughter
getting one X from each parent and a son his mother's only. A trait with X variants gets a prediction for a
daughter and one for a son, so the child-sex switch changes the predictions where biology says it should. Details:
[inheritance.md](architecture/inheritance.md), "The X chromosome in the trait models".

**The first forecast kept as the baseline.** Both sealed forecasts, the ledger and the check against the real
daughter are kept (and archived); the daughter's profile was removed so she can be re-imported once the logic is
fixed, and the new check compared with this one.

**Tools as letter logos.** Each of Ask's tools has an abbreviation, a name and a description in one file
(`explorer/ask_tools.json`), used by both Sources and documentation and the Ask tab, where the source tiles are smaller
and a Tools group lights each logo while the model calls it (blue research, green yours, purple drawn). A test keeps
the file and the tool registry in step, with no abbreviation used twice.

**The release and outreach plan** is in [outreach/TODO.md](outreach/TODO.md) (dated 2026-11-26): the XX_2
check, a public demo with a 1000 Genomes trio, the release work, licence and privacy pages, signing, videos and
funding.

**A sealed forecast, to test the predictions on a real child** (`inheritance/forecast.py`). `freeze` writes everything
the Inheritance tab predicts for a child of a pair, from the parents alone, with a SHA-256 seal in an append-only
ledger; `check` compares it with the child's own DNA once the child is added, and refuses a forecast that was changed
or made after the child joined. It tests, from the most basic up: Mendel (every child genotype one copy from each
parent, error rate by call tier), the variant odds (information over population frequencies; settled variants), the
traits (whether 80% of the child's places fall inside the 80% fields, error mean 0 and spread 1), and the single-gene
traits. Sealed on 2026-11-26 for a daughter of two profiles, then resealed with an **embedding**: the predicted
child as one vector over every trait, beside 500 daughters drawn by Mendel from the parents' genotypes and 500
random Europeans, so check can place the real child among real-looking sisters or among strangers. The first check against a real child (her results private) confirmed the Mendelian parts and
found three flaws in the method, written up in [inheritance.md](architecture/inheritance.md): bell-curve fields for
traits ruled by one rare variant, slightly wide fields, and an embedding baseline without call errors.

**Which scales measure the same thing** (`inheritance/overlap.py`, `{ref}/inheritance/trait_overlap.json`). Every trait
model scored on the 525 European founders of the 1000 Genomes panel, and every two scales correlated (linkage
included). Body mass index moves with childhood body size (r 0.39), waist (0.38), weight (0.36), hip (0.35) and body
fat (0.33). 125 families at r >= 0.6; the joining is single-linkage, which chains the blood lipids into one family of
249 and the protein levels into one of 118, so it needs a stricter rule before the page uses it.

**Familiar traits: 25 more.** Pulse rate, blood pressure, triglycerides, type 2 diabetes, alcohol, Addiction (smoking
initiation), insomnia, migraine, lung function, kidney function, bone density, coronary artery disease, atrial
fibrillation; grip strength and voice-breaking timing for men; waist-hip ratio, first-period timing and menopause for
women; body fat and lean mass in one Body composition card; years of schooling, intelligence, depression, neuroticism
and risk taking. A trait for one sex shows only for that sex (the person, or the child's sex switch);
`featured.json` has `sex` and `group`.

**Ask keeps going.** A question runs on the server: a reload, another window or switching away no longer loses it.
The page reattaches to a running question and replays its steps, reopens each profile's last conversation, lists
earlier ones, and retries a dropped poll. The Ask tab shows a pulsing dot while a question runs and a solid one when an
answer waits.

## 0.1.14 (2026-11-26)

**Ask on other AI models.** Besides Claude Code (login) and Anthropic (API key): OpenAI, Google Gemini, Mistral,
OpenRouter and any OpenAI-compatible server, by the user's own API key (`agent/models.py`). The model is picked from
the provider's own list; keys are saved encrypted on the computer. Gemini by login was left out: Google replaced the
Gemini CLI with Antigravity CLI for free and Google One users on 2026-06-18, and its streaming format isn't documented.

**Restricted mode, on by default.** The switch that decides whether the external model may access the person's
results for the items a question names. On (green): the model gets the question and public research only, and the
answer is general. Off (yellow): interpreted results go to the model, some genotypes included. A folded note above the
question box explains both modes, a child's results and the GDPR points, naming the connected model and its company.

**Ask and Inheritance.** `my_child` reads what a child of the two profiles picked under the Inheritance switch (one XX,
one XY) could inherit, drawn as the Inheritance tab's scales and odds bars; `trait_model` gives the study behind a
trait. `my_traits` reads the person's own GWAS trait scores, drawn as scales with the genes that push them. Neither
sends a genotype, a variant id or a profile id to the model.

**The Ask box.** One composer (question, Restricted mode, Inheritance, the model, Ask), at most 820 px wide; short
suggestions; the placeholder follows the switches.

**Sources and documentation.** The Sources tab, renamed and moved to the right, lists what Ask can show and look up,
from its tool registry (a test keeps the list and the tools in step). The glossary was removed.

## 0.1.13 (2026-11-25)

**Biomarkers redesign.** One person's version of the Inheritance tab: a hero, familiar traits as cards with scales,
"Which cancers XY_1's genes lean toward", all GWAS traits (largest studies first) with the GWAS Catalog's source, and
the blood tests at the bottom.

**Results in words.** Ranks are "Top 24% · taller" or "Bottom 28% · lower LDL cholesterol" from the exact percentile,
never fixed bands or "Nth of 100" (CLAUDE.md). The cancer verdicts and the slide-2 grade bar follow it.
