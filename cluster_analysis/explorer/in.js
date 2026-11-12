  // Introduction (Home tab): a walkthrough of what the explorer does and how, one step at a time, with the method's
  // numbers and the selected person's (intro_stats, cluster_analysis/explorer/intro.py). With GX_SETTINGS.intro_required
  // (settings.json) every viewer goes through it once per browser before the other tabs open: Next waits
  // intro_min_seconds on each step and there is no skipping. Every text node is one whole template for the Swedish layer.
  const IN_S = window.GX_SETTINGS || {};
  const inMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const inT = (tpl, ...vals) => vals.reduce((s, v) => s.replace('{}', v), tpl);
  const inN = (n) => (n == null ? '—' : d3.format(',')(n));
  const inPct = (x, d = 0) => (x == null ? '—' : `${(x * 100).toFixed(d)}%`);
  const inMillions = (n) => (n == null ? '—' : `${(n / 1e6).toFixed(1)} million`);
  let inDone = false;
  try { inDone = localStorage.getItem('gx-intro-done') === '1'; } catch (e) { /* storage blocked: shown again next visit */ }
  const inLocked = () => !!IN_S.intro_required && !inDone;
  let inStep = 0, inShownAt = Date.now(), inTimer = null;

  // Shut the other tabs while the introduction is mandatory and not done
  const inShow = gx.show;
  gx.show = (tab) => inShow(inLocked() && tab !== 'home' ? 'home' : tab);
  const inLock = () => {
    document.querySelector('.gx').classList.toggle('gx-locked', inLocked());
    document.querySelectorAll('.gx-tab').forEach((b) => {
      if (b.dataset.tab === 'home') return;
      if (inLocked()) { b.setAttribute('aria-disabled', 'true'); b.title = 'Finish the introduction first'; }
      else { b.removeAttribute('aria-disabled'); b.removeAttribute('title'); }
    });
    if (inLocked()) gx.show('home');
  };
  inLock();
  const inFinish = (tab) => {
    inDone = true;
    try { localStorage.setItem('gx-intro-done', '1'); } catch (e) { /* storage blocked: for this visit only */ }
    inLock();
    gx.show(tab || 'clusters');
  };

  // Charts, drawn as plain elements so their labels are text the Swedish layer translates
  const inChartBox = (parent, title) => { const b = inMake(parent, 'div', 'in-chart'); if (title) inMake(b, 'div', 'in-chart-title', title); return b; };
  const inBars = (parent, title, items, fmt = inN) => {
    const box = inChartBox(parent, title), max = Math.max(...items.map((x) => x.value || 0), 1);
    for (const x of items) {
      const r = inMake(box, 'div', 'in-row');
      inMake(r, 'b', null, x.label);
      inMake(inMake(r, 'div', 'in-track'), 'i', x.cls || 'in-c-fg').style.width = `${((x.value || 0) / (x.max || max)) * 100}%`;
      inMake(r, 'span', null, fmt(x.value));
    }
    return box;
  };
  const inStack = (parent, title, items) => {
    const box = inChartBox(parent, title), total = items.reduce((s, x) => s + (x.value || 0), 0) || 1;
    const bar = inMake(box, 'div', 'in-stack');
    bar.setAttribute('role', 'img');
    bar.setAttribute('aria-label', items.map((x) => `${x.label}: ${inN(x.value)}`).join(', '));
    for (const x of items) if (x.value) inMake(bar, 'span', x.cls).style.width = `${(x.value / total) * 100}%`;
    const lg = inMake(box, 'div', 'in-legend');
    for (const x of items) inMake(lg, 'span', x.cls, `${x.label}: ${inN(x.value)} (${inPct(x.value / total, x.value / total < 0.01 ? 1 : 0)})`);
    return box;
  };
  const inFacts = (parent, facts) => {
    const box = inMake(parent, 'div', 'in-facts');
    for (const [big, small] of facts) { const f = inMake(box, 'div', 'in-fact'); inMake(f, 'div', 'in-big', big); inMake(f, 'small', null, small); }
  };
  const inText = (parent, text) => inMake(parent, 'p', 'in-text', text);

  // The tabs' headline numbers, from the datasets the tabs themselves draw
  const inCount = (id) => { const r = gx.rows(id); return r ? r[0] : null; };
  const inDistinct = (rows, key) => (rows ? new Set(rows.map((r) => r[key])).size : null);

  const IN_STEPS = [
    { title: 'What this is', draw: (el, c) => {
      inText(el, `This explorer reads ${c.who}'s raw DNA file, the file a consumer test such as MyHeritage, AncestryDNA or 23andMe lets you download, and lays it against public research: which genes act on health, what the variants ${c.who} carries do to them, and what that means for medicines, nutrition and lab values.`);
      inText(el, 'Everything runs on this computer. The DNA file and every result stay here; the explorer only reads research databases that were downloaded beforehand, and never sends anyone\'s genotypes anywhere.');
      inText(el, 'The steps that follow explain how the file is read, how the gaps in it are filled, how sure each answer is, where the facts come from, and what each tab shows. Use the switches at the top to change person (Profile) or language (EN, SV).');
    } },
    { title: 'The DNA file', draw: (el, c) => {
      const p = c.p || {}, m = (c.g || {}).map_sites || {};
      const sites = Object.values(m).reduce((s, n) => s + (n || 0), 0);
      inText(el, inT('DNA is a long text of four letters, and people differ from each other at certain positions: the 1000 Genomes reference panel records {} such positions. A consumer DNA test doesn\'t read them all. A chip measures a fixed set of them (SNPs), {} in {}\'s file, and reports the two letters found at each, one from each parent.',
        sites ? inMillions(sites) : '—', inN(p.measured), c.who));
      inFacts(el, [[inN(p.measured), inT('positions measured in {}\'s file', c.who)],
                   [p.format ? { myheritage: 'MyHeritage', ancestry: 'AncestryDNA', '23andme': '23andMe' }[p.format] || p.format : '—', 'file format'],
                   [inN(p.matched), 'of them at positions the reference panel knows']]);
      const chroms = Object.entries(p.per_chrom || {}).sort((a, b) => (a[0] === 'X') - (b[0] === 'X') || +a[0] - +b[0]);
      if (chroms.length) {
        const box = inChartBox(el, 'Measured positions per chromosome');
        const cols = inMake(box, 'div', 'in-cols'), labs = inMake(box, 'div', 'in-cols-lab'), max = Math.max(...chroms.map((x) => x[1] || 0));
        for (const [ch, n] of chroms) {
          const col = inMake(cols, 'div');
          col.title = inT('Chromosome {}: {} positions', ch, inN(n));
          inMake(col, 'i').style.height = `${(n / max) * 100}%`;
          inMake(labs, 'span', null, ch);
        }
      }
      inText(el, 'Larger chromosomes hold more positions. X counts once in men, who have one X; in women, the two X\'s differ like the other chromosomes do.');
    } },
    { title: 'Filling in the gaps: imputation', draw: (el, c) => {
      const p = c.p || {}, g = c.g || {};
      inText(el, inT('DNA is inherited in long stretches, and distant relatives share them without knowing it. Imputation compares the measured positions with the full genomes of {} volunteers in the 1000 Genomes Project, finds the people who share each stretch, and reads the positions in between from them.', inN(g.panel_people)));
      const flow = inMake(el, 'div', 'in-flow');
      inMake(flow, 'span', null, inT('{} measured', inN(p.measured)));
      inMake(flow, 'em', null, '→');
      inMake(flow, 'span', null, inT('compared with {} reference genomes', inN(g.panel_people)));
      inMake(flow, 'em', null, '→');
      inMake(flow, 'span', null, inT('{} positions filled in', inMillions(p.kept)));
      if (p.kept && p.measured) {
        inBars(el, 'Calls before and after imputation', [
          { label: 'Measured by the chip', value: p.measured, cls: 'in-c-fg' },
          { label: 'Filled in by imputation', value: p.kept, cls: 'in-c-ok' }]);
        inText(el, inT('Imputation gives {} {} times more calls than the chip measured. Each comes with a probability: only calls where the best genotype has at least {} probability are kept.', c.who, Math.round(p.kept / p.measured), inPct(p.min_gp)));
      }
    } },
    { title: 'How sure is each call?', draw: (el, c) => {
      const p = c.p || {}, v = p.validation || {}, t = p.tiers || {};
      inText(el, inT('To measure how good the guesses are, every tenth measured position was hidden from {}\'s file, imputed as if it had never been read, and compared with the real answer.', c.who));
      inFacts(el, [[inN(v.hidden), 'positions hidden and re-imputed'], [inPct(v.right, 1), 'of the confident guesses were right']]);
      inStack(el, inT('{}\'s imputed calls by confidence', c.who), [
        { label: 'High', value: t.high, cls: 'in-c-ok' }, { label: 'Medium', value: t.medium, cls: 'in-c-ok2' },
        { label: 'Low', value: t.low, cls: 'in-c-warn' }, { label: 'Untested', value: t.untested, cls: 'in-c-fg' },
        { label: 'Not detected, not excluded', value: t.not_excluded, cls: 'in-c-none' }]);
      inMake(el, 'ul', 'in-list').append(...[
        'High: at least 98% right in the test. Used like a measured call, marked "imputed".',
        'Medium: at least 90% right. Used for theme findings, not for conclusions from one variant.',
        'Low and untested: counted, not used.',
        'Not detected, not excluded: "doesn\'t carry it" for a rare variant, where imputation misses too many real carriers to rule it out. Most imputed calls are of this kind: rare variants nobody can impute well.'
      ].map((x) => { const li = document.createElement('li'); li.textContent = x; return li; }));
    } },
    { title: 'What a chip can and can\'t see', draw: (el, c) => {
      const g = c.g || {}, m = g.map_sites || {}, cv = g.clinvar;
      inText(el, inT('To know where imputation can be trusted for anyone, {} of the reference volunteers were set aside, cut down to the positions a chip reads, imputed from the others, and compared with their real genomes at every one of the panel\'s positions.', inN(g.holdout)));
      inStack(el, 'Every variant position in the reference panel, by how well a chip plus imputation knows it', [
        { label: 'Measured on the chip', value: m.chip, cls: 'in-c-fg' }, { label: 'Imputed reliably', value: m.reliable, cls: 'in-c-ok' },
        { label: 'Uncertain', value: m.uncertain, cls: 'in-c-warn' }, { label: 'Not knowable from a chip', value: m.not_knowable, cls: 'in-c-none' }]);
      const bands = g.map_by_frequency || [];
      if (bands.length) {
        inBars(el, 'Imputation accuracy (r², 1 = perfect) by how common the variant is', bands.map((b) => ({
          label: inT('Variant frequency {}–{}', inPct(b.from), inPct(b.to)), value: b.r2, max: 1, cls: b.r2 >= 0.8 ? 'in-c-ok' : 'in-c-warn' })),
          (x) => (x == null ? '—' : x.toFixed(2)));
      }
      inText(el, 'Common variants are imputed well. The rarer a variant, the fewer reference people share it and the worse the guess; for variants rarer than 1%, the held-out people carry too few copies to measure it at all. Most of the genome\'s variant positions are that rare.');
      if (cv) inText(el, inT('That matters most for disease variants. Of the {} variants ClinVar lists as causing disease, {} are too rare to be in the reference panel at all, and only {} can be read from a chip with confidence. For those, a clear result here says little; a sequencing test reads them directly. The Clusters tab shows this per theme and per gene ("What a chip can see").',
        inN(cv.pathogenic), inN(cv.not_in_panel), inN((cv.chip || 0) + (cv.reliable || 0))));
    } },
    { title: 'Where the facts come from', draw: (el, c) => {
      inText(el, 'Nothing in the explorer is written from memory. Which genes belong to a theme, what a variant does, how strong a finding is and what a guideline recommends all come from public research databases, downloaded and read on this computer:');
      inMake(el, 'ul', 'in-list').append(...[
        'Genes and diseases: Open Targets, Gene Ontology (QuickGO), the GWAS Catalog, ClinVar.',
        'How genes work together: STRING (protein interactions), Reactome (pathways and reactions), OmniPath, Rhea.',
        'What a variant does: Ensembl VEP, UniProt, MaveDB (measured effects), GTEx (gene activity per tissue).',
        'Medicines: ClinPGx (PharmGKB), CPIC and DPWG dosing guidelines, drug labels.',
        'Nutrition and lab values: the PGS Catalog (polygenic scores), Nordic Nutrition Recommendations 2023, the Human Protein Atlas.',
        'Frequencies and imputation: the 1000 Genomes Project.'
      ].map((x) => { const li = document.createElement('li'); li.textContent = x; return li; }));
      if (c.g && c.g.references) inText(el, inT('{} reference files in all, each with its source, version and date (genome/references.json).', c.g.references));
      inText(el, 'Each finding carries an evidence grade, so a single small study never reads like an expert guideline:');
      const gr = inMake(el, 'div', 'in-legend');
      for (const [g, t] of [['A+', 'guideline-grade, or expert-reviewed (ClinVar 3–4 stars)'], ['A', 'replicated, or ClinVar 2 stars'],
                            ['B', 'one publication, or ClinVar 1 star'], ['C', 'a single study']]) {
        const s = inMake(gr, 'div', 'in-grade');
        inMake(s, 'span', 'md-grade md-grade-' + (g === 'A+' ? 'ap' : g.toLowerCase()), g);
        inMake(s, 'span', null, t);
      }
    } },
    { title: 'How to read the results', draw: (el, c) => {
      inText(el, 'Where a result is a level compared with other people, it is drawn on a bar from orange to green. Green is always on the right, the favourable side, whichever way the level runs: for LDL cholesterol lower is better, for HDL higher is better, and both bars put the better end on the right.');
      const s = inMake(el, 'div', 'in-sample');
      const b = inMake(s, 'div', 'nt-bar');
      inMake(b, 'i').style.left = '72%';
      inText(el, 'The marker shows where the genes put the person among Europeans. It is a starting point set by the genes, not a measured value: the lab test measures the real one, and lifestyle moves it.');
      inText(el, 'Calls that come from imputation rather than the chip are marked "imputed", with their confidence. A gene is called more active, less active, changed or typical only from evidence about the variant itself: a measured effect, a curated effect, a change that cuts the protein short, or how the variant changes the gene\'s activity in tissues.');
    } },
    { title: 'Clusters', tab: 'clusters', draw: (el, c) => {
      const tm = inCount('theme_meta'), themes = tm ? [...new Map(tm.map((r) => [r.theme, r.theme_name])).values()] : [];
      inText(el, 'A theme gathers every gene research links to one area of health (cancer and the life of a cell, fertility, muscle and exertion), grouped by the mechanism it acts through: repair, growth signals, hormones, energy. Each gene is then read against the person\'s own variants.');
      if (themes.length) inFacts(el, [[String(themes.length), inT('themes for {}: {}', c.who, themes.join(', '))]]);
      inText(el, 'Body maps show where in the body the genes act, the network shows which genes work together, and selecting a gene lists the person\'s variants in it with what is known about each.');
    } },
    { title: 'Medicines', tab: 'medicines', draw: (el, c) => {
      const mg = inCount('med_genes'), md = inCount('med_drugs');
      inText(el, 'Some genes decide how fast the body clears a medicine. Each drug gene is read as two versions (star alleles), turned into a type with the CPIC rules (poor, intermediate, normal or fast), and every medicine with a guideline, a drug label or a study finding for the person\'s genotype is listed.');
      inText(el, 'The core drug genes that need such a type are read whole. Every other gene with a ClinPGx annotation is read one variant at a time, so findings come from far more genes than the core ones.');
      const mdGenes = md ? new Set(md.flatMap((r) => String(r.gene || '').split(';').filter(Boolean))).size : null;
      if (mg) inFacts(el, [[String(mg.length), 'core drug genes typed'], [String(mg.filter((g) => g.typical !== true && String(g.typical) !== 'True').length), 'of them not the usual type'], [inN(mdGenes), 'genes with a medicine finding'], [inN(inDistinct(md, 'drug')), 'medicines with a finding']]);
      inText(el, 'Search a medicine by any name, brand or ATC code to see the dosing guidance that applies and every finding with the person\'s reading and its evidence grade.');
    } },
    { title: 'Nutrition', tab: 'nutrition', draw: (el, c) => {
      const nn = inCount('nut_nutrients');
      inText(el, 'For each nutrient: how the person\'s variants move its level in the blood, how the body takes it up, carries and converts it (Reactome), which of those steps the person\'s variants touch and how, and the recommended intake (Nordic Nutrition Recommendations 2023).');
      if (nn) inFacts(el, [[String(nn.length), 'nutrients'], [inN(nn.reduce((s, n) => s + (+n.findings || 0), 0)), 'findings in all']]);
    } },
    { title: 'Biomarkers', tab: 'biomarkers', draw: (el, c) => {
      const lt = inCount('lab_tests');
      inText(el, 'Common lab tests read through the genes: where the person\'s genes put each value among Europeans, which genes are known to move it, and whether the person\'s own variants move it. Some only shift the value without the body being affected ("your normal may differ"); others are real and worth following up.');
      if (lt) inFacts(el, [[String(lt.length), 'lab tests']]);
    } },
    { title: 'Gene lifecycle', tab: 'lifecycle', draw: (el, c) => {
      const lg = inCount('lifecycle_genes');
      inText(el, 'One gene at a time: the chemical journey its protein takes part in, step by step from Reactome, what each step needs (cofactors, vitamins), what regulates it, and where the person\'s variants change the gene\'s capacity.');
      if (lg) inFacts(el, [[inN(inDistinct(lg, 'gene')), 'genes with a lifecycle']]);
    } },
    { title: 'Profile', tab: 'profile', draw: (el, c) => {
      const hm = inCount('hp_modules');
      inText(el, 'The genes grouped into functional modules, sets of genes whose proteins work together, with the person\'s results per module: where several weakened genes sit in the same system, and which weakened genes reach into other systems.');
      if (hm) inFacts(el, [[String(hm.length), 'modules']]);
    } },
    { title: 'Ready', draw: (el, c) => {
      inText(el, 'That is the whole process: the chip\'s measured positions, imputation to fill in the rest, a measured confidence for every call, and public research to read them against. Each tab starts with a short note on what it shows and where its facts come from.');
      inText(el, 'This introduction stays under Home, to come back to at any time.');
    } },
  ];

  dash.draw('in-intro', (el) => {
    el.replaceChildren();
    if (inTimer) { clearTimeout(inTimer); inTimer = null; }
    const r = gx.rows('intro_stats');
    if (!r) { if (gx.failed('intro_stats')) gx.failLine(el); return; }
    const who = gx.who(), g = r[0].find((x) => x.kind === 'general'), p = r[0].find((x) => x.kind === 'person' && x.person === who);
    const step = IN_STEPS[inStep];
    const top = inMake(el, 'div', 'in-top');
    inMake(top, 'h2', null, step.title);
    inMake(top, 'span', 'in-count', inT('Step {} of {}', inStep + 1, IN_STEPS.length));
    const prog = inMake(el, 'div', 'in-progress');
    IN_STEPS.forEach((_, i) => inMake(prog, 'span', i <= inStep ? 'on' : null));
    step.draw(el, { who, g, p });

    const nav = inMake(el, 'div', 'in-nav');
    const go = (i) => { inStep = i; inShownAt = Date.now(); dash.draw('in-intro'); el.scrollIntoView({ block: 'start' }); };
    const back = inMake(nav, 'button', null, 'Back');
    back.type = 'button';
    back.disabled = inStep === 0;
    back.addEventListener('click', () => go(inStep - 1));
    const last = inStep === IN_STEPS.length - 1;
    const next = inMake(nav, 'button', 'in-next', last ? 'Open the explorer' : 'Next');
    next.type = 'button';
    next.addEventListener('click', () => (last ? inFinish('clusters') : go(inStep + 1)));
    if (step.tab && !inLocked()) {
      const open = inMake(nav, 'button', null, inT('Open {}', step.title));
      open.type = 'button';
      open.addEventListener('click', () => gx.show(step.tab));
    }
    if (!inLocked() && !last) {
      const skip = inMake(nav, 'button', 'in-skip', 'Skip the introduction');
      skip.type = 'button';
      skip.addEventListener('click', () => inFinish('clusters'));
    }
    // Mandatory: each step stays for intro_min_seconds before Next opens
    const wait = inLocked() ? Math.max(0, (IN_S.intro_min_seconds || 0) * 1000 - (Date.now() - inShownAt)) : 0;
    if (wait > 0) {
      next.disabled = true;
      inTimer = setTimeout(() => { next.disabled = false; inTimer = null; }, wait);
    }
  });
