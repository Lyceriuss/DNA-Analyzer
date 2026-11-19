# Ask: architecture decisions and iterations

A running log of the choices behind the Ask feature (`cluster_analysis/agent/`, the explorer's Ask tab): what was
decided, why, and what changed when testing showed a problem. The newest entries are at the bottom of each section.
For the current design as a whole, see [agent.md](agent.md).

## Goal (set by the user, 2026-11-19)

- Any question about a person's genome is matched, researched and answered. There is no module per question type;
  if a new kind of question needs its own module, the design has failed.
- Study data is always pulled from the APIs and placed in the explorer's cluster analysis, so the answer carries the
  signal of the research rather than its noise.
- The answer is advice for this person, not a list of how common their genotypes are, unless that is the question.
- Saying "we don't know" is fine. When a question asks for more than the data supports, the answer says which part
  it can't answer, then answers the nearest question it can. Example: "Which cancer will I die from?" becomes
  "mortality is unknown; these are the cancer types you are more susceptible to".
- Minimal AI. A quick answer in under a minute, and a deep answer in at most half of the first version's time
  (18.8 minutes). Nowhere near a million tokens per question.

## Decisions

### D1. The model never sees a genotype

Chosen by the user from three options: send readings opt-in, public facts only, or pseudonymised readings.
- The model works only from public facts.
- Personal data enters in exactly one place, `answer.fill`, on this machine.
- What the model writes is conditional text: a reading per copy count (0/1/2), and later per percentile band or per
  metaboliser class. This machine picks the branch that applies.
- Search queries are built only from what the question matched, never from which of the person's results stand out.
  Otherwise the choice of query would reveal the genotype to Europe PMC, Open Targets or Claude.
- `tests/test_agent.py` runs every tool with file access blocked on `data/input` and `data/output`.

### D2. Facts come from sources: the ledger check

- Each run keeps a ledger of what the tools returned.
- `answer.validate` rejects:
  - a source no tool returned
  - a quote that isn't word for word in a returned text
  - a percentage or fold change missing from the texts its sentence cites
  - an effect allele that isn't one of the variant's two alleles
  - a variant missing a reading for 0, 1 or 2 copies
- The model gets the reasons back and corrects the answer.
- **Iteration (first live run):** the check caught the model citing UniProt for ACTN3 without having looked it up.
  The check works as intended.
- **Iteration:** MCP clients don't enforce the tool's schema, so the first live answer arrived malformed (practice
  items without `when`, `limits` as a single string). `answer.shape` now checks the full schema inside `validate`,
  whatever the route.

### D3. Backends: an API key, or your own agent setup

- **API key:** the Messages API, with a hand-written loop (`run.run`). The user's own key.
- **No key:** a headless Claude Code session (`claude -p`) with only the MCP tools, running on the user's Claude plan
  (`run.run_claude_code`). The CLI is found on PATH, through `DNA_CLAUDE_CLI`, or inside the VS Code extension.
- **Any other MCP client:** `python -m cluster_analysis.agent mcp`.
- Not chosen: extracting the Claude Code session's token to call the API directly. That isn't permitted.

### D4. A local index for bulk lookups

- GWAS Catalog, ClinVar and the 1000 Genomes sites live in one SQLite file (`cluster_analysis/cache/agent_index.sqlite`,
  about 470 MB, built once in about 4 minutes).
- Lookups are offline and take milliseconds. Ensembl isn't needed (rest.ensembl.org was down for days).
- **Iteration:** the first live run asked for PPARGC1A rs8192678 and ACE rs4341. They aren't GWAS hits or in ClinVar,
  so they were missing. The index now also takes the ~15,000 variants earlier Ensembl VEP runs had cached
  (`index --vep`). rs4341 still has no record.

### D5. v1 was one long model-driven loop; replaced by match, research, respond

v1 was one conversation in which the model chose every lookup. The first live run, on Claude Code with Opus at high
effort, took:
- 18.8 minutes
- 43 lookups, one after another
- about 740,000 input tokens, mostly cache reads of the growing history

The answer was good, but the cost and wait don't fit. The user asked for a fast shallow view, a deep view in half the
time, enforced parsing logic, weaker models and parallel runs. v2:

1. **Match** (`terms.py`, no AI). A term index of every public item (drugs and classes, cancer types, lab tests,
   nutrients, theme mechanisms and traits, gene symbols), a domain vocabulary for everyday words, and Open Targets
   search for conditions nothing else names.
2. **Kind** (`terms.kind`, rules). The kind of question sets the answer's shape (rank, action, propensity, gene), and
   unanswerable parts (mortality, timing, certainty) get a sentence that says so.
3. **Providers** (`providers.py`). Each existing package (cancer, lab tests, nutrients, fitness, medicines, clusters,
   genes and pathways) plus a generic condition provider (GWAS and ClinVar, read locally) returns uniform cards from
   the person's own results.
4. **Evidence** (`evidence.py`, rules). One Europe PMC search per card topic. Syntheses and trials first; only
   sentences that state an outcome and an effect are kept.
5. **Respond.** A rule-based verdict for the quick view. Small models write only the conditional advice, in
   parallel, for the deep view.

### D6. Matching rules (iterations from the example questions)

| Problem | Fix |
|---|---|
| Fuzzy matching over drug trade names matched nearly anything ("medicine" gave dapsone; one-letter name parts matched) | fuzzy matching only for theme, test and nutrient names, on word parts of 5+ letters |
| "vitamin D" matched folic acid through a trade name | a drug matches only when its name appears in the question as a whole phrase |
| Everyday words ("medicine", "workouts") matched nothing | a domain vocabulary: words per domain, not per question |
| Open Targets search returns nothing for whole sentences | search the leftover content words, after dropping generic words ("genetic", "propensity", "problems") |
| A partial local match ("Thyroid (TSH)") stopped the search for thyroid conditions | partial matches no longer stop the search, and the search runs after an exact-match pass |
| "type 2 diabetes" lost "type", and single words gave noise ("monogenic diabetes") | the whole phrase is searched first; hits are scored by word overlap and how much of the phrase they cover |
| Swedish condition names ("migrän") get nothing, because Open Targets is English-only | in a Swedish question, the explorer's own term list (`i18n_sv_terms`) translates them first; no AI needed |
| A heredoc removed backslashes, leaving a backspace character in a regex | edits to Python files go through the Edit tool or Python scripts, never heredocs (see the memory notes) |

### D7. Study search speed

- Europe PMC with `resultType=core` (abstracts included) takes about 10 seconds per query; `lite` takes 0.2.
- Now: a lite search (25 hits), ranked by study type and citations, then the abstracts of the best 6 in one core
  request by `EXT_ID`, which takes 0.2 seconds. A topic takes 4-18 seconds uncached, mostly two searches when the
  syntheses-only search finds too few. Repeats are cached.

### D8. A plain risk-allele count for conditions without a score

- When no published score covers a condition (thyroid disorders, migraine, type 2 diabetes), the condition provider
  counts the person's risk alleles at the strongest GWAS loci against the European expectation (1000 Genomes
  frequencies) and reports an approximate percentile.
- It is labelled as an unweighted count, not a validated score.
- The direction comes from the odds ratio or the beta's direction text.
- Next: use a PGS Catalog score where one exists, through the existing scoring code (`nutrition.score`).

### D9. Quick answer: no model at all

- `quick.run` does match, kind, providers in parallel, studies in parallel, then a rule-based verdict
  (`python -m cluster_analysis.agent quick "…" --person <profile>`).
- Measured on a test profile on 2026-11-19, using no tokens:

| Question | Uncached | Studies cached |
|---|---|---|
| "Which cancer will I most likely die from?" | 27 s | 0.6 s |
| "What medicine should I be careful with taking?" | – | 0.6 s (no searches: the guidelines are the evidence) |
| "Do I have a genetic propensity for thyroid problems?" | 38 s, including the local GWAS read | 7 s |
| "How does ACTN3 affect me?" | 12 s | – |
| "What workouts will work the best for me?" | 28 s | 1 s |

### D10. Signal over noise (iterations on the example answers)

| Seen | Changed to |
|---|---|
| Medicines: one card per drug, dozens of them | one card per gene whose result changes guidance (for example a NAT2 result affecting hydralazine and isoniazid), each with the instruction per drug; drugs the chip can't settle are summarised in one card ("a pharmacogenetic test settles them") |
| Guidance on two genes credited to a gene with the usual result | guidance on several genes belongs to the genes whose result isn't the usual type |
| Drug labels showed "See the guideline" | the label's or guideline's summary sentence when there is no per-type recommendation |
| Verdict: one sentence per score | scores sorted into favourable, unfavourable and "N others in the usual range" |
| Fitness cluster: "200 of 1,170 genes changed" plus a gene list | grouped by mechanism, strongest evidence first: the explorer's graded tables, then experiments, then Open Targets genetics. The theme's graded variants with a practical meaning (sport SNPs) become their own card |
| Cancer cards without advice | the European Code Against Cancer's recommendations for the causes IARC lists for that cancer; when IARC lists none, the card says there is no specific prevention to give |
| Studies off topic (lung-cancer paper for basal cell carcinoma) | a paper must name every word of the topic; Europe PMC's relevance order counts in the ranking; sentences starting "Background" or "Methods" are dropped |
| Studies not about what was asked (a radioactive-iodine trial for "propensity") | the search focus follows the kind of question (propensity or rank: prevention, screening, risk factors; action: trials, guidelines); a paper must touch the focus |
| Ordinals like "92th"; "tsh" in lower case | proper ordinals; names keep their capitals |

### D11. Privacy rule for searches, tested

Cards built from the person's results (medicines in general, a cluster's changed genes) carry no search topic. A
search runs only for what the question named: a drug, a condition, a cancer type, a mechanism.
`tests/test_ask_quick.py` checks it.

### D12. The tab runs the quick answer first; AI only when the rule says so (2026-11-19)

- **The problem the user saw:** the Ask tab still ran the v1 deep agent for "What medicines should I watch out
  for?", a question the explorer's data answers with no model.
- **The tab now:**
  - The question bar always starts the quick answer (`POST /api/agent/quick`, a job whose steps the tab polls).
  - `quick.needs_deep` decides whether AI could add anything:
    - **complete:** the data carries the answer itself (guideline instructions, a ranking of scores, a standing on a
      named score or condition, a gene's role).
    - **deep recommended:** the question asks what to do and the cards have no advice of their own (training,
      diet), or nothing matched.
  - The deep analysis is a button. It's the main action when recommended, and a quiet "anyway" otherwise, always
    with the rule's reason next to it.
- **Tokens shown:**
  - A quick answer says "No AI · 0 tokens · N s".
  - A deep run shows its tokens live: the API loop reports usage per turn, and Claude Code per message (each message
    id counted once).
- **Layout:**
  - The AI connection is a chip in the bar's corner ("AI: Claude Code"), opening the key field.
  - The explainers about what leaves the machine are gone.
  - A strip of the Sources tab's databases (logos from `sources.json`) pulses green while a step reads them and stays
    outlined once used. The ids come from `quick.SOURCES`; Claude lights up only in the deep pass.
- **Cards:** each card shows its level (Act on this, High, Usual, Unknown, …), the headline, rows, "What lowers it",
  "What we don't know", the research, and buttons that open the explorer's own tab for that item.
- **Measured:** the medicines question through the server took 0.1-0.7 s with 0 tokens, and `needs_deep` said
  complete.
- **Iteration:** the drug rows showed "See the guideline" or bare allele codes. Only rows with an instruction (6+
  words) are shown, and the rest are counted ("N more: open the gene in Medicines").

### D13. The answer leads with what studies found for the person's own genotypes (2026-11-19)

**User feedback on the first quick answer:** it didn't contextualise anything and cluttered the screen with numbers
that weren't useful. They want a centred summary of specific findings, ideally a percentage ("people with this gene
responded 25% better to this training"), and a bigger, square source box. They also doubted the "0 tokens";
`grep` confirms no model call anywhere in the quick path.

The new core, `agent/morsels.py`:
- **What gets researched:** every well-known variant of the matched cluster. That's the whole public list (the sport
  SNPs for Fitness, otherwise the library variants in the cluster's genes), never chosen by the person's genotypes.
- **The search:** Europe PMC for the variant or gene with genotype words and the cluster's field words. Papers that
  name the gene in the title rank higher; narrative reviews rank low (they rarely report genotype groups). The best
  15 abstracts are read.
- **What a finding is:** a sentence that names a genotype group (CT, XX, "T allele", carriers), states an effect, and
  uses the field's outcome words (training, strength, injury, recovery, …). Numbers (%, fold, OR, HR, SMD) rank
  first; the "95%" of a confidence interval doesn't count as one.
- **Dropped as noise:**
  - how common a genotype is (distribution, frequency, "the majority … was AT (69.2%)")
  - methods sentences
  - sentences about another gene or variant (the "CC genotype of IL-6", "VEGFA rs699947")
- **Caching:** results are cached per variant, the same for everyone. A cluster is researched once in the background
  (Fitness: 33 variants, ~4 minutes), and the quick answer uses what's cached, saying how many are still pending.
- **Applying it to the person** (`morsels.apply`, locally): the person's genotype becomes the labels papers use. That
  includes protein letters from Ensembl's amino acids, so an ACTN3 rs1815739 TT genotype reads as XX, "X allele" and "T allele".
  Only findings that name the person's own group are kept, one per gene, numbers first.

The tab now shows:
- a centred "Based on <profile>'s DNA" with one finding per gene: the gene, the person's genotype, the number, the quoted
  sentence, the study type, year and title
- then the score lines and "No AI · 0 tokens · N s"
- the explorer's result cards folded under "Details"
- the sources as a square grid of logo tiles beside the answer, sticky, green while read, outlined once used

**Measured:** "which muscle mass gene has the most impact on my training?" took 0.4-1.3 s with 0 tokens. The findings it
led with are public study results by genotype group: CYP1A2 (lifting velocity +4-12% after caffeine in AA, 3-9% in AC),
ACTN3 (T allele and power, OR 0.71, meta-analysis), ADORA2A, SLC16A1 and AGT.

**Other changes:**
- Studies for the cards get an 8-second budget. Late ones are left out of that answer and keep caching.
- "Which gene matters most" no longer ranks scores.
- A cluster's graded-variants card appears once.

**Still a quote, not advice:** the summary quotes what studies found; it doesn't yet say "so train like this". Next is
a small model as a parser of public sentences: per finding, which genotype group it is about, the intervention, the
outcome and the effect, in plain words. That's cached per sentence, the same for everyone, and never sees the person.

### D14. The summary is written by a small model, without the model knowing whose genome it is (2026-11-19)

**The user's request:** the findings were right, but the main result should be a written summary ("Based on your
DNA, you're highly receptive to caffeine…") with the single findings pushed down, all on one page.

**The conflict with D1:** a model that writes "your CT on ADORA2A…" has to be told which findings apply, and that
reveals the genotypes. The solution, `agent/interpret.py`:

1. **Read every finding, once, for everyone.** Haiku reads ALL of a cluster's findings, never a person's selection,
   batched 18 per call with each paper's title as context. For each genotype group a sentence names, it returns a
   self-contained reading ("In a study of … caffeine …, if you are AC, your mean velocity increased by 3%-9% …") and a
   takeaway for that group ("Caffeine before lifting may help your bar speed, though likely less than for AA"), or ""
   when none follows.
2. **Check against the sentence.** A group's label must be written in the sentence, and every figure in a reading or
   takeaway must be one the sentence gives. Digits inside names (CYP1A2, ADORA2A, rs ids, 1RM) don't count as
   figures.
3. **Cache.** Readings are kept per sentence in `cluster_analysis/cache/agent_interp_*.json`: public, the same for
   everyone.
4. **Assemble locally.** `interpret.summary` picks, for each finding that applies to the person, the reading for
   their own group ("C allele carriers" for a CT) and puts the takeaways first. The words come from the model; the
   choice is made on this machine.

**Backends:**
- with an API key: `claude-haiku-5-5`, structured output (`output_config.format`)
- without one: `claude -p --model haiku --json-schema …`, read from `structured_output`

**Tab:**
- The quick answer shows at once. The server then writes or reuses the summary in the same job, and the tab polls the
  partial result.
- On top: "Based on <profile>'s DNA", one paragraph per finding with the takeaway in bold and a numbered link to its study.
- A token line: "Written by … · N tokens, once for this cluster and reused for everyone", or "earlier, reused · 0
  tokens now".
- Then "The studies behind it" folded, the score lines, the deep-analysis button, and the details folded.
- It fits one screen.

**Measured:**
- The first read of the Fitness cluster (50 sentences, 71 group readings, 24 with a takeaway) took 70 s and about
  60k Haiku tokens (22k in, 38k out). It's once, for every person and every later fitness question.
- After that, an answer takes 0.6 s with 0 tokens.

**Iterations:**
- Readings lacked context: CYP1A2's sentence doesn't name caffeine, its title does, so titles are now sent.
- Takeaways were empty: a single takeaway per sentence came back empty, so each group gets its own; then the number
  check rejected gene names with digits, so `figures()` now ignores names.

**Checked against the user's example:**
- The user's example said an ADORA2A CT genotype means "somewhat higher testosterone".
- The study says TT carriers had higher testosterone than C-allele carriers, so a CT is in the lower group.
- The reading says so ("if you are a C allele carrier, your testosterone and growth hormone levels were significantly
  lower than those of TT carriers").

### D15. A small model reads the question first; the rules are the fallback (2026-11-19)

**What the user saw:** "What way of working out would suit me best?" matched nothing. The rules know "workout",
"training" and "exercise", but not "working out". The user's point: understanding a question needs a model; a word
lookup isn't enough.

**`agent/route.py`:**
- Haiku gets the question and a compact catalogue of the explorer (each cluster with its mechanisms and phases, the
  cancer types, lab tests, nutrients, fitness tests, and the domains), about 6.7k tokens.
- It returns a fixed structure:
  - kind (rank, action, propensity, gene)
  - the clusters and mechanisms the question is really about
  - the tests and nutrients
  - drugs, genes and conditions in English
  - the unknowable parts
  - 2-5 English search terms
- Only catalogue ids are kept; drugs, genes and conditions go through the term index and Open Targets as before.
- The model's items come first, then the rules' items; the kind and the unknowns come from the model.
- The search terms feed the findings ranking.
- No personal data: only the question, which a deep analysis sends anyway.
- Cached per question under `data/output/agent/routes/`; the question is the user's own, so not in the public cache.
- Without an API key or Claude Code, or if the call fails, the rules answer alone and the answer says so.

**Measured** (Claude Code, Haiku): about 8 s and ~7.8k tokens per new question, 0 tokens when repeated.

| Question | The model's reading |
|---|---|
| "What way of working out would suit me best?" | Fitness: fast-twitch power, slow-twitch endurance, aerobic capacity, growth on load, response to training, the strength test |
| "Can I drink coffee in the evening?" | Psychology: adenosine and caffeine, circadian clock, sleep disorders; the caffeine test |
| "Will I get fat easily?" | Fitness: fat burning, glucose burning; blood sugar, TSH; obesity |

**The answer's token line** says how the question was read: "Question read by Claude · N tokens", "read earlier · 0
tokens now", or "matched by rules (no AI connected)".

**Through the server:** the question that failed now answers in about 10 s, and the card study budget was cut from
8 to 4 s since the written summary doesn't depend on it.

### D16. The comprehension is shown first; every answer type gets a written summary (2026-11-19)

**User feedback:** "You cannot make a logic that works for every single use case." The model's understanding has to
be visible before the work starts. The medicine answer was still a rule-built sentence.

**The comprehension, visible:**
- `route.py` now also returns:
  - **reading:** one sentence to the person on what was understood and how it will be answered, including what can't
    be (for the cancer question: "it cannot say which cancer will kill you … a genome shows predisposition, not
    destiny")
  - **plan:** 2-5 steps naming the part of the explorer or the source each uses, and why
- `quick.run` emits it as an `understood` event before any provider runs.
- The tab shows it at once as "How the question was read", with the token cost, and ticks the plan's steps when the
  answer arrives.
- The route cache moved to `routes2/`, since the old entries had no reading or plan.

**Summaries for answers built from the person's own results.** The user chose readings per category over sending
derived results or rule-built text. `agent/categories.py`:

| Domain | Categories (public facts) |
|---|---|
| Medicines | every single-gene CPIC result, 73 in all (NAT2 Poor Metabolizer, CYP2B6 Intermediate, …), each with the drugs and CPIC's recommendation and implication for that result |
| Scores (cancer, lab, nutrient, fitness) | every item in 5 bands (low, lowered, usual, raised, high), with what higher means and, for cancers, the European Code recommendations against that cancer's causes |
| Conditions the question names | the plain risk-allele count, in 5 bands |

- The model writes a reading and a takeaway per category, and the numbers are checked against the facts.
- **Always the whole domain**, never the person's categories, so the choice reveals nothing.
  `tests/test_ask_quick.py` checks that `ensure` sends every category.
- `key_of(card, person)` works out the person's category locally (`cpic_result` maps "Slow acetylator" to CPIC's NAT2
  "Poor Metabolizer", "activity score 2" to CYP2C9 "2.0").
- The server writes missing readings in the same job as the quick answer. The summary puts the study findings first
  for cluster questions and the person's own results first otherwise. A usual result is shown only when little else
  stands out.

**Measured, once for everyone, on Claude Code with Haiku:**

| Domain | Tokens | Time |
|---|---|---|
| Medicines, 73 categories | 46k in, 17k out | 34 s |
| Cancer, 50 categories | 29k in, 12k out | 22 s, within the answer |

After that, reuse costs 0 tokens.

**Example readings** (written for every person in the category, before D22 changed the wording):
- **NAT2 poor metabolizer:** "Tell your doctor or pharmacist … The guideline starts treatment at a total daily dose of
  40 to 75 mg …"
- **Lung cancer, highest band:** "Do not smoke … check radon levels …"

**Fixes along the way:** a long prompt broke the Windows command-line limit, so the prompt now goes to `claude -p` on
stdin. `interpret._ask` takes its prompt and schema as arguments rather than through swapped globals, which wasn't
safe with two jobs at once.

### D17. No answer without the model; how "What is my response to paracetamol?" failed (2026-11-19)

**The trace.** The model's reading was right: the drug domain plus paracetamol, with the reading "how your body
handles paracetamol (acetaminophen) …". The answer still failed:
1. **Rule matches were merged in after the model.** The word "response" matched the Fitness mechanisms "Cortisol
   response" and "Response to training" and four Open Targets conditions ("inflammatory response", "PARP inhibitor
   response", …). Each became a job, and the Fitness findings filled the summary.
2. **The medicine provider looks only at guidelines (CPIC, DPWG, labels).** Paracetamol has none, so it answered "no
   guidance, or your file can't read the genes". It ignored the ClinPGx clinical annotations the explorer holds for the
   person (public ClinPGx records on UGT1A, PLCG1 and a Stevens-Johnson risk variant, each with a text per genotype).
   These are level 3, but they are the answer.
3. **The model's plan is shown but not executed.** It said "read your metaboliser types for the genes that process
   paracetamol"; the code ran its own fixed jobs by item type.
4. **The unknown sentence** for "certainty" is written for diseases ("no genotype makes a common disease certain")
   and was shown for a drug.

**Decided (the user):** no fallback that doesn't rely on the model. `route.items` raises `NotUnderstood` when there is
no backend, when the model call fails, or when its reading names nothing in the explorer, and the tab shows that
instead of an answer. The rules no longer add matches. `terms.match` remains only to resolve the names the model
gives (a drug, a gene, a condition). Tested in `tests/test_ask_quick.py`.

**Under discussion:** the resolution and execution architecture (a local hybrid index, the plan as typed tool calls,
every provider exposing all its data, a golden question set). See the next entries.

### D18. Ask becomes a conversation in which Claude works through the explorer's tools (2026-11-19)

**The user's priorities:**
1. Understand the question first.
2. Take whatever local data there is, but don't stop there unless it answers the question (it rarely does).
3. Allow in-depth follow-ups, on a study for example, like a session.

They also want tools that work with the explorer's features ("show me the cluster for a gene").

**`agent/tools.py`, one registry of 21 tools,** served to the API loop and over MCP (`mcp_server.py`):

| Kind | Tools | What the model gets back |
|---|---|---|
| public | catalogue, resolve, gene, variant, cluster, trait_variants, drug (guidelines plus every ClinPGx annotation with its per-genotype text), research_genotypes, search_papers, read_paper | the full result |
| personal | my_medicine, my_medicines, my_scores, my_cluster, my_gene, my_condition | only the result's kinds; the screen gets the result. No titles ("NAT2: Slow acetylator" is a result), no counts of what stood out |
| view | show_cluster, show_pathway, show_medicine | "shown"; the tab draws the view |
| control | understand (the reading and plan, first), answer | answer checks that every [PMID:…]/[ClinPGx:…] cited is one a tool returned |

**`agent/converse.py`, one turn:**
1. **Engines:** with an API key, the Messages API in a loop (`claude-sonnet-5-5`, effort medium). Without one,
   `claude -p --model sonnet` with the MCP tools. The MCP process shares the turn through `DNA_TURN_FILE`: the
   person, the ledger, the cards, the views, the answer.
2. **Readings afterwards, on this machine:**
   - categories for the person's own results (D16)
   - ClinPGx's own text for the person's genotype for each drug annotation
   - genotype-group readings for the research findings (D14), all of them written, the person's picked
3. **Prompt rules:** call understand first; resolve names (paracetamol is acetaminophen); read the person's results;
   research at least once unless the person only asked to be shown something; views when they help; finish with a
   cited answer and follow-ups.

**`agent/session.py`:**
- Turns are kept in `data/output/agent/sessions/<id>.json`.
- A follow-up's `context()` holds the earlier questions, readings, plans, tool calls with their public arguments, and
  the model's own explanations and follow-ups. It holds no card, reading or screen content
  (`tests/test_ask_converse.py`).
- The public ledger carries over, so later turns can cite earlier papers.
- `#ask=<session id>` reopens a conversation.

**The tab:**
- One article per turn:
  - the question
  - "How the question was read": the reading, the plan, and each tool step tagged research, yours or view
  - the views
  - the explanation, with citations as links
  - "For <profile>", the picked readings
  - the person's results folded
  - token and time line
  - follow-up chips
- The bar becomes "Follow up", with "New" to start over.
- The source grid lights by tool.
- The cluster view is generated in the answer: the gene's 16 strongest STRING partners in the theme (`theme_links`),
  coloured by the person's call for each gene (`theme_genes`), drawn with d3.

**Measured on Claude Code (Sonnet), on a test profile:**

| Turn | Time | Tokens in | What happened |
|---|---|---|---|
| "What is my response to paracetamol?" | 18 s | 43k | resolved acetaminophen, read the person's annotations, read the public drug genetics (no guideline; 35 ClinPGx annotations on UGT1A, SULT1A, PLCG1); a cited explanation of glucuronidation, sulfation and angioedema, and of what the genotype can't tell (dose, alcohol and liver health matter more) |
| Follow-up "Show me the cluster for UGT1A1" | 94 s | 46k | gene, my_gene, show_cluster (cancer theme), research_genotypes; the genotype research was uncached, hence the time |
| Follow-up "Tell me more about the study on liver failure after an overdose" | 24 s | 48k | resolved from the conversation alone to Court et al. 2013; search_papers, research_genotypes, read_paper; explained the design (liver tissue plus a patient comparison), the variants (rs8330, rs1042640, rs10929303 as one signal) and what it can't tell |

### D19. Claude learns what kind of answer is on the person's screen, so it can stop (2026-11-19)

**The user's point:** for "What is my response to paracetamol?" the answer already exists in the Medicines data, so
the slow genotype-study search shouldn't have started.

**What the data holds:** `med_drugs` has the ClinPGx annotations on acetaminophen for each person. Each carries:
- the person's genotype
- ClinPGx's sentence for that genotype
- a short effect
- the status (differs, usual, not excluded)
- the level and its papers

`my_medicine` put them on screen, and the "For <profile>" readings use them.

**Why it went on anyway:**
- The model can't see these rows (D1).
- D18's rule, "research at least once", forced a genotype-study search.

**Change:**
- Every `my_*` result now says `screen_has`: what kind of answer it put on screen, never its content. For example
  "ClinPGx's text for the person's own genotype at each annotated variant", "dosing-guideline recommendations for
  the person's own gene results", "the person's genetic score per cancer type with … prevention advice", or "nothing
  that answers it".
- The prompt says: when the screen holds the answer, explain it from the public facts behind it and finish. Research
  only when it doesn't, or when the person asks for depth.
- Disclosure: only whether an answer of that kind exists, which for medicines is nearly always.

### D20. The "For <profile>" box: one coloured row per finding (2026-11-19)

**User feedback:** the readings were good, but the box gave no clear overview of which gene result the person has.

**Change:**
- **Rows:** each reading is a row, with chips for the gene, each variant with the person's genotype, and the
  evidence level ("level 3 · single studies"); the effect in bold; the source's sentence beneath in muted text.
- **Colour by direction:** `converse.direction` sorts each finding into favourable (decreased risk, better or
  increased response), worth attention (increased risk, toxicity, failure, poor response) or good to know (activity
  or expression changes). Counts of each sit at the top; attention rows come first.
- **Merging:** the same effect in one gene family at several variants is one row (UGT1A rs1042640, rs8330 and
  rs10929303, inherited together).
- **Credit:** the footer names the actual author: "ClinPGx's own texts for your genotypes", "readings written once for
  everyone by Claude", or both.

### D21. The person's gene results lead the "For <profile>" box (2026-11-19)

**User feedback** on "How well does my body handle ibuprofen?": "I'm not seeing my genotype here and what expression
I have." Their tab still ran the old script (hard reload); the stored turn did hold the genotypes. Three real gaps:

| Gap | Fix |
|---|---|
| Guidelines name several drugs in one entry ("celecoxib;flurbiprofen;ibuprofen;lornoxicam"), so the named-drug lookup missed the person's CPIC CYP2C9 guidance and the card said "unknown" | match a drug within multi-drug entries (`providers.medicines`); the card keeps the genes its guidelines use (`genes`, `unread_genes`) |
| The person's CYP2C9 result (their alleles and activity type), the result that matters for NSAIDs at CPIC level 1A, appeared only inside a ClinPGx sentence | a gene-result row per guideline gene: the alleles, the activity as the "expression", the written category reading, favourable or attention by whether it's the usual type; genes the chip can't read (CYP2C8) get a row saying so. These rows lead the box, and a star-allele annotation repeating them is dropped |
| "Decreased pain relief" was sorted as neutral | `direction` also counts decreased or reduced relief, response, efficacy or effect as worth attention |

The explanation renderer now turns inline lists (": - **A** … - B") into lists, and bold that holds a star allele
(`**CYP2C8 *3 …**`) renders as bold.

### D22. Risk and evidence, never clinical advice (2026-11-19)

**The user's rule:** clinical advice ("see a doctor", "ask for lab tests") is prohibited; answers speak in risk. It
replaces the CLAUDE.md line "Health advice in the outputs is intended" (CLAUDE.md and the memory note are updated).

`agent/language.py`:
- **RULE**, which goes into every prompt that writes text for the person (the conversation, the category readings,
  the study readings): what a genotype means for a risk, an exposure, a level or a response, and how strong the
  evidence is. Never "see a doctor", "ask for a test", "tell your doctor or pharmacist", a dose or drug instruction,
  "you should", "consider", "avoid" or "make sure". A guideline is reported as a fact about the guideline, prevention
  as risk factors.
- **`advice()`**, a pattern check that enforces it:
  - `answer` sends an advising explanation back to be rephrased, like an unreturned citation
  - category and study readings that advise are not kept
  - an advising takeaway is blanked

**Rule-built texts:**
- Cancer cards show "Known cause (IARC)" risk factors instead of the European Code's instructions ("Do not smoke"),
  and the cancer category facts carry IARC's causes in place of the Code's texts.
- "A pharmacogenetic test settles it" becomes "so this result is unknown".
- "A test or a doctor's assessment does" is gone.

**Cache:** all 298 cached readings (written under the old "practical action" wording, 59 with advice phrasing) were
cleared and are rewritten on next use. The medicine domain was rewritten at once: 73 readings, 83k tokens in and 32k
out, 43 s, 0 with advice. For example NAT2: "Higher levels may mean a stronger effect and more side effects … The CPIC
guideline gives a starting dose of 40 to 75 mg total daily for this group".

**Not covered yet:** the other tabs' curated texts can still read as advice (the sport-SNP meanings such as "longer
warm-ups … help", the European Code recommendations in the Cancer cluster), and so can conversations saved before
the rule.

### D23. Answers in text, statistics and graphs; the signal first; the latest research (2026-11-19)

**User feedback on a vitamin D answer:** very little signal; the Nutrition module's vitamin D data should be used;
answers should carry assets ("part text, part statistics, part graph"); a gene such as ADRB2 should get its pathway
"imported or constructed"; and the LLM should be able to pull up the latest research on a gene or muscle group. The
same answer also still advised ("Test first", "Re-test after 2-3 months", "800-2000 IU … a common, low-risk
choice"), past D22's check.

**New tools:**

| Tool | Kind | What it does |
|---|---|---|
| `pathway(gene)` | public | uses the explorer's Gene pathway steps when it maps the gene well (6 steps or more); otherwise builds the pathway live from Reactome: UniProt accession, the protein's reactions, each reaction's inputs and outputs (ADRB2: 3 explorer steps, so 14 live). The steps go into the ledger as Reactome refs |
| `nutrient(name)` | public | the Nutrition module's tests and its uptake and conversion steps with the genes at each (vitamin D: 19 steps) |
| `my_nutrient(name)` | personal | the person's baseline and their variants at each step, on screen only |
| `recent_papers(query, since_year)` | public | Europe PMC newest first, each paper with the sentences that carry its finding (`evidence.pick`) |
| `show_pathway`, `show_nutrient`, `show_papers` | view | the pathway view carries its steps |

**`answer` takes `highlights`:** 'label | value | source', where the value's numbers must be in that source's text and
the label may not advise. They are shown as tiles beside the person's own number tiles (score percentiles from their
cards).

**The tab:**
- Order: highlight tiles and the person's tiles, then the explanation, then the views, then "For <profile>".
- Pathways and nutrients are drawn as numbered flows: steps with inputs and outputs, a nutrient's genes as chips, the
  person's variant on each with ↑ or ↓ for raising or lowering the blood level.
- The research digest shows the type, date and journal, the title linked, the key sentences, and "Ask about this
  study".

**The stricter advice check** (`language.advice`), sentence by sentence:
- sentences that start as an instruction ("Test first.", "- Avoid …", "Re-test …")
- doses not attributed to a guideline or a study ("800–2000 IU"); "a trial gave 2000 IU daily" passes
- verdicts ("is reasonable", "clearly indicated", "a common, low-risk choice", "practical approach")

Every advice line of the reported answer is caught; its factual lines pass. The prompt now asks for the signal first,
no "practical approach" or "what to do" section, and highlights that are effects, risks and sizes, never how common a
genotype is.

**Measured** (Claude Code, Sonnet, on a test profile):

| Question | Time | Tokens in | Views | What happened |
|---|---|---|---|---|
| "Should I take vitamin D based on my genes?" | 152 s (genotype research uncached) | 51k | nutrient flow | the person's variants marked on their steps; highlights such as "25(OH)D rise did not vary by GC isoform" (RCT) |
| "How does ADRB2 look in my genome? Show me its pathway." | 37 s | 88k | ADRB2 pathway, 14 steps, Reactome live | the answer was sent back 3 times by the checks before passing |
| "Pull up the latest research on hamstring injury genetics." | 90 s | 58k | 5 papers, 2025-2026 | led with the 2026 systematic review's verdict that genetic evidence is insufficient for injury prediction |

### D24. The summary weaves the person's results: interpreted results go to the model the user connects (2026-11-19)

**User feedback** on "What kind of food should I eat?": individually correct cards with no narrative, "which the LLM
needs to do". The summary and contextualisation have to be consistent across all questions: a presentable explanation,
then the sources it rests on.

**Decided with the user:** a woven narrative needs a model that knows the results. Connecting a model is the user's
own setup (their API key, their Claude Code login), so what it receives is their choice; a handful of interpreted
results doesn't identify anyone; an addendum states it.

**`agent/settings.py`, `share_results`** (on by default; the switch is in the tab's AI corner):
- **On:** every personal tool also returns `interpreted(cards)` for what it just showed: each result's title, kind,
  level, percentile, which way is better, its summary line and up to 8 detail rows (genotype, effect). Only the items
  the question touches; never the DNA file. A follow-up's context includes the earlier summaries.
- **Off:** the blind mode of D1, D14 and D16.

**What is sent**, written down in:
- `docs/architecture/agent.md`, "What is sent (addendum)"
- `cluster_analysis/README.md`
- the CLAUDE.md rule
- the Sources tab's entry for Claude

**`answer` requires `summary`:** 2-4 sentences weaving the person's results and the evidence, the strongest signal
first, in risk language. The advice check covers it.

**Highlights may use 'yours' as the source** when sharing is on. The figure must be in the person's result that the
label names (the label's words in that result's title); a made-up "42nd percentile" is rejected even though 42 occurs
somewhere else in their results.

**The tab, one structure for every question:**
1. how the question was read
2. "Based on <profile>'s DNA", the summary
3. the key figures: highlights plus the person's number tiles
4. "For <profile>", the evidence rows
5. "The evidence in more detail", the explanation
6. the views
7. "Sources (N)", every cited ref plus the sources behind the person's rows
8. the token and time line, which says whether interpreted results were shared

**Fixes along the way:**

| Problem | Fix |
|---|---|
| A turn ended without `answer`; the food question showed only cards | a turn that ends without one gets a second pass with the calls made so far; the turn file carries the whole turn, so it continues |
| Over MCP a rejection reached the model only as "Error executing tool answer", so it couldn't fix it: the first food run took 6 attempts, 196k tokens and 187 s | the reasons are returned as the result ("NOT ACCEPTED: …"). The rerun took 2 attempts, 87k tokens and 27 s |
| Score cards were coloured without regard to which way is better (a high HDL score marked worth attention) | `_score_direction` uses `higher` |
| The explanation said "I did not look up studies … the food links are general nutrition knowledge" | the prompt requires every link from a result to the question's subject to come from a cited tool result: research it or leave it out |

## Open

- The hybrid resolution index (D17 proposal): exact hash maps for ids, character trigrams for typos, local embeddings
  for meaning, with the model choosing among real candidates. `resolve` today is the term index plus Open Targets.
- A golden set of ~50 questions with expected tools and entities, run after every change.
- The old single-shot quick answer (`quick.py`, `/api/agent/quick`) and the v1 deep agent (`run.py`) are still in
  the code but no longer used by the tab; remove them once the conversation has been used for a while.
- The tab's new texts are English only.

- Study relevance for measurement names ("heart-rate recovery after exercise" found a Prader-Willi review): search
  the trait with the question's own words, or leave measurement cards to the deep pass.
- A PGS Catalog score for conditions that have one, in place of the plain allele count (D8).
- The deep pass is still v1 (one long model loop). Next: per-card writers in parallel on a small model, fed the cards
  and their extracted study sentences, writing only advice. That would cut tokens from ~740k to a few thousand per
  card.
- The quick answer's own texts (verdicts, headlines) and the written readings are English only; the tab's labels are
  in Swedish. Readings could be written in both languages in the same call.
- Only Fitness has a curated variant list for findings; other clusters fall back to the library variants in their
  genes. Each cluster's first question triggers its research (minutes) and its reading (one small-model pass).
- Medicine categories come from CPIC only: DPWG and drug-label guidance (in the person's `med_guidance`) have no
  categories yet, so genes like VKORC1, G6PD and HLA-B get no written reading.
- The plan's steps are ticked together at the end; they could follow the providers one by one.
- Readings are still long ("In a study of …"); a second, shorter field could serve the summary while the long one
  stays under the study.
- Embedding the explorer's views (cluster graph, pathway) inside the cards; for now the cards link to their tabs.

- The deep pass: per-card writers in parallel (Haiku or Sonnet, through the API or `claude -p`), conditional
  templates, and the ledger check per card.
- The UI: a question bar; the key as a corner chip; the Sources strip pulsing green per source in use; results drawn
  with the existing views (cluster graph, pathway, medicine cards, score bars); no security explainers.
- Ranking study relevance: genetic-focus terms should weigh more ("resistance training" returned general sarcopenia
  trials).
