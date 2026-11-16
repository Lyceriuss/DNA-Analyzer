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

  // Whether a genetic score points to the less favourable side (as in nt.js: below the 20th or above the 80th percentile)
  const inUnfav = (rows) => (rows || []).filter((n) => {
    let ms = []; try { ms = JSON.parse(n.markers || '[]') || []; } catch (e) { /* no markers */ }
    return ms.some((m) => m.score && m.higher !== 'neutral' && (m.score.percentile <= 20 || m.score.percentile >= 80)
      && (m.score.percentile <= 20) === (m.higher === 'better'));
  });
  const inList = (el, items) => inMake(el, 'ul', 'in-list').append(...items.map((x) => { const li = document.createElement('li'); li.textContent = x; return li; }));
  const inOpen = (parent, tab, label) => {
    const b = inMake(parent, 'button', null, inT('Open {}', label));
    b.type = 'button';
    b.addEventListener('click', () => { if (!inLocked()) gx.show(tab); });
    return b;
  };
  // Small line icons for the groups of research databases (24×24, stroke in the current colour)
  const IN_ICONS = {
    reading: 'M7 3c0 6 10 6 10 12s-10 6-10 6M17 3c0 6-10 6-10 12s10 6 10 6M8 7h8M8 17h8M9.5 12h5',
    health: 'M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M12 7.5a4.5 4.5 0 1 0 0 9a4.5 4.5 0 1 0 0-9M12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2',
    body: 'M6 6m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0M18 7m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0M12 18m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0M8.3 7l7.2.2M7.3 8.3l3.6 7.4M16.8 9.2l-3.6 6.5',
    advice: 'M4.6 13.4l8.8-8.8a4.2 4.2 0 0 1 6 6l-8.8 8.8a4.2 4.2 0 0 1-6-6zM9 9l6 6',
    nutrition: 'M5 19c0-8 6-14 15-14c0 9-6 15-14 15M5 19l8-8',
    reference: 'M4 5.5C6.5 4 9.5 4 12 6c2.5-2 5.5-2 8-.5V19c-2.5-1.5-5.5-1.5-8 .5c-2.5-2-5.5-2-8-.5zM12 6v13.5',
  };
  const inIcon = (parent, id) => {
    const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('class', 'in-icon'); svg.setAttribute('aria-hidden', 'true');
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', IN_ICONS[id] || IN_ICONS.reference);
    svg.appendChild(p); parent.appendChild(svg);
    return svg;
  };

  // A database's own logo (runtime/logos, sources.json), on a light tile so it reads in both themes; its initials if none
  const inLogo = (parent, d) => {
    const t = inMake(parent, 'span', 'in-logo');
    if (d.logo) { const i = inMake(t, 'img'); i.src = 'logos/' + d.logo; i.alt = ''; i.loading = 'lazy'; i.onload = () => i.classList.toggle('in-logo-wide', i.naturalWidth > 1.6 * i.naturalHeight); }
    else inMake(t, 'span', 'in-logo-txt', d.name.split(/\s+/).map((w) => w[0]).join('').slice(0, 4).toUpperCase()).setAttribute('data-i18n-skip', '');
    return t;
  };
  const TAB_NAMES = { clusters: 'Clusters', medicines: 'Medicines', nutrition: 'Nutrition', biomarkers: 'Biomarkers' };

  // The steps: how it works (and what imputation is), the research behind it, what it gives, the file, reading it
  const IN_STEPS = [
    { title: 'How it works', draw: (el, c) => {
      const p = c.p || {}, g = c.g || {}, v = p.validation || {};
      // The pipeline as a picture: three stages inside this computer, the research databases coming in from outside
      const wrap = inMake(el, 'div', 'in-pipe');
      // The research databases (sources.json, the Sources tab), not the count of reference files
      const src = inMake(wrap, 'button', 'in-src');
      src.type = 'button';
      src.addEventListener('click', () => { if (!inLocked()) gx.show('sources'); });
      inMake(src, 'div', 'in-src-big', inN(((window.GX_SOURCES || {}).databases || []).length));
      inMake(src, 'div', 'in-src-name', 'Public research databases');
      inMake(src, 'small', null, 'Downloaded once, read by gene and variant. Listed under Sources.');
      inMake(wrap, 'div', 'in-pipe-in', '→');
      const box = inMake(wrap, 'div', 'in-box');
      inMake(box, 'div', 'in-box-label', 'This computer');
      const row = inMake(box, 'div', 'in-stages');
      const stage = (n, name, big, small) => {
        const s = inMake(row, 'div', 'in-stage');
        inMake(s, 'span', 'in-stage-n', String(n));
        inMake(s, 'div', 'in-stage-name', name);
        inMake(s, 'div', 'in-stage-big', big);
        inMake(s, 'small', null, small);
      };
      const fmt = { myheritage: 'MyHeritage', ancestry: 'AncestryDNA', '23andme': '23andMe' }[p.format] || p.format;
      stage(1, 'Read', inN(p.measured), fmt ? inT('SNPs measured in {}\'s {} file: single positions where people\'s DNA differs by one letter', c.who, fmt) : inT('SNPs measured in {}\'s file: single positions where people\'s DNA differs by one letter', c.who));
      // Confident calls only: most filled-in positions are rare variants called "not detected, not excluded", which add nothing
      const conf = p.tiers ? (p.tiers.high || 0) + (p.tiers.medium || 0) : null;
      stage(2, 'After imputation', conf ? inMillions(conf) : '—', inT('confident calls added by imputation, {} of the tested ones right', inPct(v.right, 1)));
      const tg = inCount('theme_genes');
      stage(3, 'Results', inN(inDistinct(tg, 'gene')), 'genes read against the research, each finding with an evidence grade');
      inText(el, 'Genetic data is sensitive health data under the GDPR, so the analysis runs where the DNA file is stored: on this computer. Nothing is sent anywhere, and deleting the DNA file and the results folder removes everything.');
      // What imputation is, boxed apart from the pipeline above
      const sec = inMake(el, 'section', 'in-section');
      inMake(sec, 'h3', 'in-h3', 'What is imputation?');
      const t = p.tiers || {};
      inText(sec, inT('DNA is inherited in long stretches, and distant relatives share them without knowing it. Imputation compares the measured positions with the full genomes of {} volunteers in the 1000 Genomes Project, finds the people who share each stretch, and reads the positions in between from them.', inN(g.panel_people)));
      if (conf && p.measured) inBars(sec, 'Calls before and after imputation', [
        { label: 'Measured by the chip', value: p.measured, cls: 'in-c-fg' },
        { label: 'Confident calls added by imputation', value: conf, cls: 'in-c-ok' }]);
      inText(sec, inT('To check the guesses, every tenth measured position was hidden from {}\'s file, imputed as if it had never been read, and compared with the real answer.', c.who));
      inFacts(sec, [[inPct(v.right, 1), 'of the confident guesses were right']]);
      inStack(sec, inT('{}\'s imputed calls by confidence', c.who), [
        { label: 'High', value: t.high, cls: 'in-c-ok' }, { label: 'Medium', value: t.medium, cls: 'in-c-ok2' },
        { label: 'Low', value: t.low, cls: 'in-c-warn' }, { label: 'Untested', value: t.untested, cls: 'in-c-fg' }]);
      inText(sec, 'Only high-confidence calls are used for conclusions from a single variant, and each is marked "imputed".');
      // The rare positions imputation can't tell about: not calls, so not in the chart; said once, plainly
      if (t.not_excluded) inText(sec, inT('At {} rare positions imputation can\'t tell whether {} carries the variant: it misses too many real carriers there. Those positions aren\'t used; a rare variant that matters (a drug gene, a disease variant) is shown as "not detected, not excluded".', inMillions(t.not_excluded), c.who));
    } },
    { title: 'Read against research', draw: (el, c) => {
      const S = window.GX_SOURCES || { groups: [], databases: [] }, byId = new Map(S.databases.map((d) => [d.id, d]));
      const head = inMake(el, 'div', 'in-lead');
      inMake(head, 'p', 'in-text', inT('Every fact in the explorer comes from one of {} public research databases, each run by a university or a public research institute. Here is what we take from each, and what we use it for:', S.databases.length));
      if (!inLocked()) {
        const all = inMake(head, 'button', 'in-link', inT('All {} under Sources', S.databases.length));
        all.type = 'button';
        all.addEventListener('click', () => gx.show('sources'));
      }
      // Per group, a card per database: its logo, how we get its data, what we take and what we use it for
      const HOW = { bulk: 'Downloaded once', 'API, saved': 'Downloaded once', 'bulk + API': 'Downloaded, and looked up by gene or variant', API: 'Looked up by gene or variant' };
      for (const g of S.groups) {
        const block = inMake(el, 'section', 'in-srcgroup in-grp-' + g.id);
        const h = inMake(block, 'div', 'in-group-head');
        inIcon(h, g.id);
        inMake(h, 'h4', null, g.title);
        const grid = inMake(block, 'div', 'in-srccards');
        for (const id of g.ids) {
          const d = byId.get(id);
          if (!d) continue;
          const card = inMake(grid, 'a', 'in-srccard');
          card.href = d.url; card.target = '_blank'; card.rel = 'noopener';
          const top = inMake(card, 'div', 'in-srccard-top');
          inLogo(top, d);
          const nm = inMake(top, 'div', 'in-srccard-name');
          inMake(nm, 'b', null, d.name).setAttribute('data-i18n-skip', '');
          inMake(nm, 'span', 'in-how', HOW[d.access] || d.access);
          const take = inMake(card, 'p', 'in-take');
          inMake(take, 'span', 'in-tag', 'We take');
          inMake(take, 'span', null, d.takes);
          const use = inMake(card, 'p', 'in-take');
          inMake(use, 'span', 'in-tag', 'We use it to');
          inMake(use, 'span', null, d.use);
        }
      }

      // What the person got from them: every finding by evidence grade
      const grades = ['A+', 'A', 'B', 'C'], cls = (g) => (g === 'A+' ? 'ap' : g.toLowerCase()), n = Object.fromEntries(grades.map((g) => [g, 0]));
      for (const id of ['med_drugs', 'nut_findings', 'lab_findings', 'fit_findings']) for (const r of inCount(id) || []) if (r.grade in n) n[r.grade]++;
      const total = grades.reduce((s, g) => s + n[g], 0);
      const sec = inMake(el, 'section', 'in-section');
      inMake(sec, 'h3', 'in-h3 in-h3-grade', 'How strong is each finding?');
      inText(sec, 'Every finding carries an evidence grade, so a single small study never reads like an expert guideline:');
      const tiles = inMake(sec, 'div', 'in-grades');
      const NOTE = { 'A+': 'Guideline-grade, or expert-reviewed (ClinVar 3–4 stars)', A: 'Replicated, or ClinVar 2 stars', B: 'One publication, or ClinVar 1 star', C: 'A single study' };
      for (const g of grades) {
        const t = inMake(tiles, 'div', 'in-gtile in-g-' + cls(g));
        const top = inMake(t, 'div', 'in-gtile-top');
        inMake(top, 'span', 'md-grade md-grade-' + cls(g), g);
        if (total) inMake(top, 'span', 'in-gtile-pct', inPct(n[g] / total));
        inMake(t, 'div', 'in-big', inN(n[g]));
        inMake(t, 'small', null, NOTE[g]);
      }
      if (total) {
        const bar = inMake(sec, 'div', 'in-gbar');
        bar.setAttribute('role', 'img');
        bar.setAttribute('aria-label', grades.map((g) => `${g}: ${n[g]}`).join(', '));
        for (const g of grades) {
          if (!n[g]) continue;
          const seg = inMake(bar, 'span', 'in-g-' + cls(g));
          seg.style.width = `${(n[g] / total) * 100}%`;
          if (n[g] / total >= 0.08) inMake(seg, 'i', null, g);
        }
        inText(sec, inT('{} findings for {} in Medicines, Nutrition, Biomarkers and training, by grade. The tabs show the grade next to every finding, strongest first.', inN(total), c.who));
      }
      // A grade is how much evidence there is, not how much a finding matters
      const note = inMake(sec, 'div', 'in-gnote');
      const path = inMake(note, 'div', 'in-gpath');
      // In the tiles' order (A+ first); the arrows point the way evidence grows, from C to A+
      for (const g of ['A+', 'A', 'B', 'C']) {
        if (g !== 'A+') inMake(path, 'span', 'in-gpath-arrow', '←');
        inMake(path, 'span', 'md-grade md-grade-' + (g === 'A+' ? 'ap' : g.toLowerCase()), g);
      }
      inMake(note, 'p', null, 'A grade measures how much evidence there is, not how much a finding matters. A single study can find something with a large effect, and every A+ guideline started as one C-grade study that others went on to repeat. The C findings are where tomorrow\'s guidelines come from: worth reading, with that in mind.');
    } },
    { title: 'What your DNA can do for you', draw: (el, c) => {
      inText(el, inT('One example of what the explorer reads from {}\'s own variants: cancer, from the medicines that need a different dose to the cancers the genes lean toward.', c.who));
      const tg = inCount('theme_genes'), tm = inCount('theme_meta'), mgd = inCount('med_guidance'), names = inCount('med_names');
      const mg = inCount('med_genes');
      const nn = inCount('nut_nutrients'), ft = inCount('fit_tests'), sp = inCount('sport_snps');
      const facetName = new Map((tm || []).map((r) => [`${r.theme}|${r.facet}`, r.facet_name]));
      const changed = (theme) => (tg || []).filter((r) => r.theme === theme && ['LoF', 'GoF', 'altered'].includes(r.function));
      // The mechanisms with the most changed genes, with a few of the genes (evidence about the variant itself first)
      const byFacet = (theme, rows) => {
        const m = new Map();
        for (const r of rows) {
          let fs = []; try { fs = JSON.parse(r.facets || '[]'); } catch (e) { /* none */ }
          for (const f of fs) if (f !== 'disease') { if (!m.has(f)) m.set(f, []); m.get(f).push(r); }
        }
        const rank = (r) => { const i = ['measured', 'curated', 'truncating', 'predicted'].indexOf(r.basis); return i < 0 ? 9 : i; };
        return [...m.entries()].sort((a, b) => b[1].length - a[1].length).slice(0, 4)
          .map(([f, rs]) => inT('{}: {} genes ({})', facetName.get(`${theme}|${f}`) || f, rs.length, [...rs].sort((a, b) => rank(a) - rank(b)).slice(0, 3).map((r) => r.gene).join(', ')));
      };
      const area = (title, lead, items) => {
        const a = inMake(el, 'div', 'in-area');
        inMake(a, 'h3', null, title);
        if (lead) inMake(a, 'p', null, lead);
        if (items && items.length) inList(a, items);
      };

      // Cancer: the genes oncologists test before treatment. A gene counts when a CPIC or DPWG guideline gives a readable
      // verdict for a cancer medicine (ATC L01/L02); per gene the person's type, every variant read and how sure the
      // call is, the cancer medicines and the guideline's verdict, and the drug labels that name the gene
      const atc = new Map((names || []).map((n) => [n.drug, String(n.atc || '')]));
      const isOnc = (drug) => /\bL0[12]/.test(atc.get(drug) || '');
      const readable = ['typical', 'differs', 'no_action'];
      const oncRows = (mgd || []).filter((g) => isOnc(g.drug));
      const genesOf = (r) => String(r.genes || '').split(';').filter(Boolean);
      const testGenes = [...new Set(oncRows.filter((r) => r.kind === 'guideline' && ['CPIC', 'DPWG'].includes(r.source) && readable.includes(r.status)).flatMap(genesOf))];
      const mgBy = new Map((mg || []).map((g) => [g.gene, g]));
      const cancer = inMake(el, 'div', 'in-area in-cancer');
      inMake(cancer, 'h3', null, 'Cancer: the genes tested before treatment');
      inMake(cancer, 'p', null, inT('Before chemotherapy and some hormone and targeted treatments, oncologists test a few genes that decide how the body clears the medicine: a slow clearer can get a toxic dose from a standard one. Here is what {}\'s DNA says for each:', c.who));
      const cards = inMake(cancer, 'div', 'in-ccards');
      const CONF = { measured: ['Measured', 'ok'], high: ['Imputed, high confidence', 'ok'], medium: ['Imputed, medium confidence', 'warn'], not_excluded: ['Not detected, can\'t be ruled out', 'bad'] };
      // Most decisive genes first: an unusual type, then a variant that can't be ruled out
      const order = (gene) => { const m = mgBy.get(gene) || {}; let s = []; try { s = JSON.parse(m.snps || '[]'); } catch (e) { /* none */ }
        return (m.typical === true || String(m.typical) === 'True' ? 2 : 0) + (s.some((x) => x.confidence === 'not_excluded') ? 0 : 1); };
      for (const gene of testGenes.filter((g) => mgBy.has(g)).sort((a, b) => order(a) - order(b) || a.localeCompare(b))) {
        const m = mgBy.get(gene);
        let snps = []; try { snps = JSON.parse(m.snps || '[]'); } catch (e) { /* none */ }
        const usual = m.typical === true || String(m.typical) === 'True', open = snps.filter((x) => x.confidence === 'not_excluded');
        const card = inMake(cards, 'div', 'in-ccard ' + (!usual ? 'in-ccard-alt' : open.length ? 'in-ccard-open' : 'in-ccard-ok'));
        const head = inMake(card, 'div', 'in-ccard-head');
        inMake(head, 'b', 'in-ccard-gene', gene).setAttribute('data-i18n-skip', '');
        inMake(head, 'span', 'in-ccard-type', `${m.alleles} · ${String(m.phenotype || '').replace(/\s*\(.*\)$/, '')}`);
        const drugs = [...new Set(oncRows.filter((r) => genesOf(r).includes(gene)).map((r) => r.drug))].sort();
        const dl = inMake(card, 'div', 'in-ccard-drugs');
        inMake(dl, 'span', 'in-tag', 'Cancer medicines');
        inMake(dl, 'span', null, drugs.join(', '));
        const vt = inMake(card, 'div', 'in-ccard-snps');
        inMake(vt, 'span', 'in-tag', 'Variants read');
        for (const x of snps) {
          const row = inMake(vt, 'div', 'in-snp');
          inMake(row, 'code', null, x.rsid);
          inMake(row, 'span', 'in-snp-allele', x.allele);
          inMake(row, 'b', null, x.genotype || '–');
          const [label, cls] = CONF[x.confidence] || [x.confidence, 'fg'];
          inMake(row, 'span', 'in-conf in-conf-' + cls, label);
        }
        // The verdict: CPIC first, then DPWG, on the medicines it covers
        const gl = oncRows.filter((r) => r.kind === 'guideline' && genesOf(r).includes(gene) && readable.includes(r.status));
        const best = gl.find((r) => r.source === 'CPIC') || gl[0];
        let rec = ''; try { rec = (JSON.parse(best.recs || '[]')[0] || {}).recommendation || ''; } catch (e) { /* none */ }
        rec = (rec.match(/^.*?\.(?=\s+[A-Z]|$)/) || [rec])[0];  // the verdict is the first sentence; the Medicines tab has the rest
        const v = inMake(card, 'div', 'in-ccard-verdict');
        inMake(v, 'span', 'in-tag', inT('Guideline ({})', best.source));
        inMake(v, 'span', null, rec);
        const labels = oncRows.filter((r) => r.kind === 'label' && r.status === 'differs' && genesOf(r).includes(gene));
        if (labels.length) inMake(card, 'div', 'in-ccard-note', inT('Drug labels ({}) name {}\'s type for: {}.', [...new Set(labels.map((r) => r.source))].join(', '), c.who, [...new Set(labels.map((r) => r.drug))].sort().join(', ')));
        if (open.length) inMake(card, 'div', 'in-ccard-warn', inT('{} of the {} variants guidelines test for are too rare for a chip to rule out ({}). Test {} before these medicines.', open.length, snps.length, open.map((x) => x.allele).join(', '), gene));
      }
      // Which cancers the genes lean toward: one polygenic score per cancer (cancers.json), highest risk first. Green is a
      // lower risk than most (higher is worse, so the marker sits at 100 - percentile, as in the Clusters cards)
      const risks = (inCount('can_tests') || []).map((t) => {
        let ms = []; try { ms = JSON.parse(t.markers || '[]') || []; } catch (e) { /* none */ }
        const m = ms.find((x) => x.score);
        return m ? { name: t.name, p: m.score.percentile, pgs: (m.source || {}).study || m.pgs_ref || '' } : null;
      }).filter(Boolean).sort((a, b) => b.p - a.p);
      if (risks.length) {
        // Each cancer in words and as a count out of 100 Europeans; the bar keeps the orange-to-green scale (green: lower
        // risk than most), with the average marked
        const band = (p) => p >= 95 ? ['Much higher than most', 'hi'] : p >= 80 ? ['Higher than most', 'hi'] : p >= 60 ? ['Somewhat higher', 'mid']
          : p > 40 ? ['Average', 'avg'] : p > 20 ? ['Somewhat lower', 'mid'] : p > 5 ? ['Lower than most', 'lo'] : ['Much lower than most', 'lo'];
        const rk = inMake(cancer, 'div', 'in-risk');
        inMake(rk, 'h4', null, inT('Which cancers {}\'s genes lean toward', c.who));
        inMake(rk, 'p', 'in-risk-lead', inT('For each cancer, how many of the risk variants large studies found {} carries, compared with 525 Europeans:', c.who));
        for (const r of risks) {
          const [word, cls] = band(r.p);
          const row = inMake(rk, 'div', 'in-risk-row in-band-' + cls);
          inMake(row, 'b', null, r.name);
          const bar = inMake(row, 'div', 'nt-bar in-risk-bar');
          inMake(bar, 'span', 'in-risk-avg');
          inMake(bar, 'i').style.left = `${100 - r.p}%`;
          const v = inMake(row, 'div', 'in-risk-verdict');
          inMake(v, 'b', null, word);
          inMake(v, 'span', null, r.p >= 50 ? inT('higher than {} of 100 Europeans', r.p) : inT('lower than {} of 100 Europeans', 100 - r.p));
        }
        const axis = inMake(rk, 'div', 'in-risk-row in-risk-axis');
        inMake(axis, 'span');
        const ax = inMake(axis, 'div', 'in-risk-axis-labels');
        inMake(ax, 'span', null, '← Higher risk than most');
        inMake(ax, 'span', null, 'Average');
        inMake(ax, 'span', null, 'Lower risk than most →');
        inMake(rk, 'p', 'in-ccard-note', 'The common variants behind these bars each nudge risk a little; together they shift it modestly. The large inherited risks come from rare variants (BRCA1, BRCA2, the Lynch syndrome genes) that a chip mostly can\'t see. A cancer far to the left is a reason to start screening on time, not a diagnosis.');
      }
      const cg = changed('cancer');
      const shown = testGenes.filter((g) => mgBy.has(g));
      // What this gives and what it can't tell: the same for everyone (general counts, no message built from one
      // person's results), and what lowers the risk: the European Code Against Cancer's recommendations for the avoidable
      // causes IARC links to the theme's cancers (themes/cancer_prevention.json, window.GX_PREVENTION)
      const cst = (() => { const r = (tm || []).find((x) => x.theme === 'cancer' && x.stats); try { return r ? JSON.parse(r.stats) : {}; } catch (e) { return {}; } })();
      const reach = cst.chip_reach || {};
      const PV = window.GX_PREVENTION || { recommendations: [], cancers: {} };
      const nMech = new Set((tm || []).filter((r) => r.theme === 'cancer' && r.facet && r.facet !== 'disease').map((r) => r.facet)).size;
      const nCancers = Object.keys(PV.cancers).length;
      const lim = inMake(cancer, 'div', 'in-canlim');
      const can = inMake(lim, 'div', 'in-canlim-col in-canlim-can');
      inMake(can, 'h4', null, 'What this gives');
      const cannot = inMake(lim, 'div', 'in-canlim-col in-canlim-cant');
      inMake(cannot, 'h4', null, 'What it can\'t tell');
      const item = (col, head, text) => { const d = inMake(col, 'div', 'in-canlim-item'); inMake(d, 'b', null, head); if (text) inMake(d, 'p', null, text); return d; };
      if (cst.n_genes) item(can, 'A broad read of the cancer genes', inT('{} genes research links to cancer, grouped by the {} stages of a cell\'s life they act on (repair, checkpoints, clearing toxins and more).', inN(cst.n_genes), nMech));
      item(can, 'Safer dosing', inT('The {} genes that decide how cancer medicines are cleared, read before any treatment starts, so a standard dose that would be toxic can be adjusted in time.', shown.length));
      if (nCancers) item(can, 'Screening at the right time', inT('A genetic risk ranking for {} cancer types, so screening can start on time for the ones that stand out.', nCancers));
      // What lowers the risk, in one line: the full list is in the cancer theme (th.js, th-prevention)
      const nRecs = new Set(Object.values(PV.cancers).flatMap((c) => c.recommendations.map((r) => r.n))).size;
      if (nRecs) item(can, 'Reduce cancer trigger exposure', inT('{} of the European Code Against Cancer\'s recommendations cover the known, avoidable causes of these cancers, such as smoking, alcohol and too much sun. The cancer theme lists them, with the cancers each one lowers.', nRecs));
      item(cannot, 'Rare high-risk mutations (BRCA1, BRCA2, Lynch syndrome)', 'The genes above are read through common variation, which a DNA test reads well. The large inherited risks come from rare single mutations, each carried by very few people, and finding them takes clinical-grade sequencing of the genes themselves.');
      item(cannot, 'Some drug-gene variants', 'A few of the variants dosing guidelines test for are too rare for a chip to rule out; the cards above mark them in orange.');
      item(cannot, 'What a tumour will do', 'How fast a cancer grows and which treatment it responds to are written in the tumour\'s own DNA, read from a biopsy. Inherited DNA only shifts the chance of getting it.');
      item(cannot, 'Exact risk', 'The bars rank common variants among Europeans; they don\'t give a lifetime risk, and they are less accurate for other ancestries. Family history counts as much and isn\'t in the DNA file.');

      // This is the overview: the cancer theme in Clusters goes gene by gene
      const more = inMake(cancer, 'div', 'in-deeper');
      const txt = inMake(more, 'div');
      inMake(txt, 'h4', null, 'This is the overview. The cancer theme goes deeper.');
      inMake(txt, 'p', null, inT('Under Clusters, the cancer theme follows a cell through its life (resting, copying its DNA, checkpoints, repair, programmed death) and shows each of {} cancer genes where it acts, which of {}\'s variants change it and the evidence behind each call. It also lists the disease variants checked, and the variants behind every bar above.', inN(cg.length), c.who));
      if (!inLocked()) {
        const b = inMake(more, 'button', 'in-next', 'Open the cancer theme');
        b.type = 'button';
        b.addEventListener('click', () => { dash.setParams({ theme: 'cancer' }); gx.show('clusters'); });
      }
    } },
    { title: 'Inside a gene: its pathway', draw: (el, c) => {
      inMake(el, 'p', 'in-lc-lead', 'Your body runs on thousands of processes, each a link in a chain where one protein hands its product to the next. Your DNA sets how well each link works, like a dial turned a little up or down. Those settings are how humans adapted to different foods, climates and threats, and the same setting can be a strength in one situation and a weakness in another. Knowing yours, down to the single step, shows where to lean on your strengths and where to support your weaknesses: for a longer, healthier and fuller life.');
      // A teaching example, the same for everyone (no one's genotype): the alcohol chain. The two enzymes are the one
      // choice made here; the molecules come from Reactome's reactions, what the enzymes are for from UniProt
      const lg = inCount('lifecycle_genes') || [], ls = inCount('lifecycle_steps') || [];
      const EX = ['ADH1B', 'ALDH2'];
      const focal = (g) => ls.find((r) => r.gene === g && String(r.role) === '1' && r.section === 'focal');
      const gene = (g) => lg.find((r) => r.gene === g && String(r.role) === '1') || {};
      // "ethanol + NAD+ => acetaldehyde + NADH + H+": the first molecule on each side
      const sides = (rx) => { const m = String(rx || '').split(/\s*=>\s*/); return m.length === 2 ? m.map((x) => x.split(/\s+\+\s+/)[0].replace(/\s*\[.*\]$/, '').trim()) : null; };
      const s1 = sides((focal(EX[0]) || {}).reaction), s2 = sides((focal(EX[1]) || {}).reaction);
      if (s1 && s2) {
        const mols = [s1[0], s1[1], s2[1]];
        const box = inMake(el, 'div', 'in-lc');
        inMake(box, 'span', 'in-tag', 'An example: the alcohol chain');
        inMake(box, 'h3', 'in-lc-title', inT('{} → {} → {}', mols[0], mols[1], mols[2]));
        inMake(box, 'p', 'in-lc-path', inT('Two enzymes, two steps: {} turns {} into {}, then {} turns {} into {}. Change how well one of them works and the middle of the chain changes.', EX[0], mols[0], mols[1], EX[1], mols[1], mols[2]));
        // The same chain three ways; the middle molecule's level is what changes
        // One beer through the chain: grams from its volume, strength and ethanol's density, hours from the whole body's
        // rate (PubChem: a constant amount per hour, whatever the dose)
        let eth = {}; try { eth = JSON.parse(((inCount('intro_stats') || []).find((r) => r.kind === 'example') || {}).ethanol || '{}'); } catch (e) { /* none */ }
        if (eth.rate && eth.density) {
          // The time scales with body weight: PubChem's per-kilo rate (mg per kg per hour), or the 70 kg figure without it
          const ML = 500, ABV = 5, grams = ML * ABV / 100 * eth.density;
          const perKg = eth.rate.mg_per_kg_hour ? eth.rate.mg_per_kg_hour / 1000 : eth.rate.g_per_hour / eth.rate.weight_kg;
          const timeFor = (kg) => grams / (perKg * kg);
          const fmtT = (h) => { const hh = Math.floor(h), mm = Math.round((h - hh) * 60); return mm === 60 ? inT('{} h {} min', hh + 1, 0) : inT('{} h {} min', hh, mm); };
          const bw = inMake(box, 'div', 'in-beer');
          const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
          svg.setAttribute('viewBox', '0 0 80 120'); svg.setAttribute('class', 'in-beer-glass'); svg.setAttribute('aria-hidden', 'true');
          svg.innerHTML = '<path d="M14 22 L66 22 L60 112 Q59 116 55 116 L25 116 Q21 116 20 112 Z" class="g"/>' +
            '<path d="M17 40 L63 40 L59 110 Q58 113 55 113 L25 113 Q22 113 21 110 Z" class="b"/>' +
            '<path d="M12 22 Q16 8 30 12 Q38 2 50 10 Q64 6 68 22 Z" class="f"/>' +
            '<circle cx="32" cy="70" r="2" class="u"/><circle cx="44" cy="88" r="1.6" class="u"/><circle cx="50" cy="60" r="1.4" class="u"/>';
          bw.appendChild(svg);
          const info = inMake(bw, 'div', 'in-beer-info');
          inMake(info, 'span', 'in-tag', 'One beer through the chain');
          inMake(info, 'b', 'in-beer-big', inT('{} ml at {}%: {} g of alcohol', ML, ABV, grams.toFixed(1)));
          inMake(info, 'p', null, inT('The liver turns about {} mg of alcohol into acetate per kilo of body weight per hour, a constant amount whatever was drunk.', Math.round(perKg * 1000)));
          // The weight slider
          const wl = inMake(info, 'label', 'in-beer-w');
          inMake(wl, 'span', null, 'Body weight');
          const range = inMake(wl, 'input');
          range.type = 'range'; range.min = 40; range.max = 120; range.step = 1; range.value = Math.round(eth.rate.weight_kg || 70);
          const wv = inMake(wl, 'b', 'in-beer-wv');
          const tline = inMake(info, 'p', 'in-beer-time');
          // A timeline of those hours, on a fixed 0 to 8 h scale so the weights compare
          const SCALE = 8;
          const tl = inMake(info, 'div', 'in-beer-tl');
          const track = inMake(tl, 'div', 'in-beer-track');
          inMake(track, 'i', 'in-beer-left');
          const ticks = inMake(tl, 'div', 'in-beer-ticks');
          for (let h = 0; h <= SCALE; h += 2) { const t = inMake(ticks, 'span', null, inT('{} h', h)); t.style.left = `${(h / SCALE) * 100}%`; }
          const during = [];   // the panels' lines, filled in below and updated with the slider
          box._beerDuring = during;
          const update = () => {
            const kg = +range.value, h = timeFor(kg);
            wv.textContent = `${kg} kg`;
            tline.textContent = inT('One beer takes about {} to pass through the chain.', fmtT(h));
            track.style.setProperty('--end', `${Math.min(100, (h / SCALE) * 100)}%`);
            for (const [node, tpl] of during) node.textContent = inT(tpl, fmtT(h));
          };
          range.addEventListener('input', update);
          box._beerUpdate = update;
          // Measured: the time doesn't depend on these genes (blood ethanol unaffected by ADH1B or ALDH2)
          let both = []; try { both = JSON.parse(((inCount('intro_stats') || []).find((r) => r.kind === 'example') || {}).measured || '[]').filter((m) => m.about === 'both'); } catch (e) { /* none */ }
          for (const m of both) {
            const q = inMake(info, 'p', 'in-beer-same');
            inMake(q, 'span', null, inT('The same for every form of these genes: measured in people, “{}”', m.finding));
            const a = inMake(q, 'a', 'in-lc-src', ` ${m.study}`); a.href = `https://pubmed.ncbi.nlm.nih.gov/${m.pmid}/`; a.target = '_blank'; a.rel = 'noopener';
          }
          const s2 = inMake(info, 'a', 'in-lc-src', 'PubChem, ethanol: metabolism and density');
          s2.href = eth.url; s2.target = '_blank'; s2.rel = 'noopener';
        }
        // The buildup, measured (Chen 2021's full text, read at export): shown in the slow form's panel
        let bu = null; try { bu = JSON.parse(((inCount('intro_stats') || []).find((r) => r.kind === 'example') || {}).buildup || 'null'); } catch (e) { /* none */ }
        const panels = inMake(box, 'div', 'in-lc-panels');
        // The variants' numbers: GWAS Catalog odds per copy and UniProt's notes, read at export (intro.py, the same for everyone)
        let exData = []; try { exData = JSON.parse(((inCount('intro_stats') || []).find((r) => r.kind === 'example') || {}).example || '[]'); } catch (e) { /* none */ }
        const exOf = (g) => exData.find((x) => x.gene === g);
        const NOISE = /^AMED|ALDH2-related|cancer|carcinoma|nitroglycerin/i;
        const caseFix = (t) => (t === t.toUpperCase() ? t.charAt(0) + t.slice(1).toLowerCase() : t);
        const fmtN = (v) => (v == null ? '—' : String(v));
        const src = (parent, text, pmid) => { const a = inMake(parent, 'a', 'in-lc-src', text); if (pmid) { a.href = `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`; a.target = '_blank'; a.rel = 'noopener'; } return a; };
        const effect = (d, e) => {
          const n = inMake(d, 'div', 'in-lc-num');
          inMake(n, 'b', null, e.or != null ? `×${e.or}` : inT('p = {}', e.p));
          inMake(n, 'span', null, e.or != null ? inT('odds of {} per copy', e.trait.toLowerCase()) : inT('linked to {}', e.trait.toLowerCase()));
          const size = (e.sample.match(/^[\d,]+ [^,]*?(?:individuals|cases)/) || [e.sample.slice(0, 50)])[0];
          src(n, `${e.author} ${e.year} · ${size}`, e.pmid);
        };
        // How fast: the measured speeds (UniProt), drawn as two bars; what the buildup does (MedGen); one GWAS effect
        const numbers = (d, g) => {
          const x = exOf(g);
          if (!x) return;
          inMake(d, 'span', 'in-tag', inT('{} {} ({})', g, x.variant, x.rsid));
          if (x.speed && x.speed.typical && x.speed.variant) {
            const sp = x.speed, ratio = Math.round(sp.variant.value / sp.typical.value);
            const k = inMake(d, 'div', 'in-lc-speed');
            const head = inMake(k, 'div', 'in-lc-num');
            inMake(head, 'b', null, `×${ratio}`);
            inMake(head, 'span', null, inT('faster: {} per minute, per mg of enzyme (Vmax)', sp.substrate));
            for (const [lab, v, cls] of [[inT('{} (typical)', sp.typical_allele), sp.typical, 'norm'], [inT('{} (this form)', sp.variant_allele), sp.variant, 'gof']]) {
              const row = inMake(k, 'div', 'in-lc-bar-row');
              inMake(row, 'span', null, lab);
              const bar = inMake(row, 'div', 'in-lc-bar');
              inMake(bar, 'i', 'in-lc-bar-' + cls).style.width = `${Math.max(2, (v.value / sp.variant.value) * 100)}%`;
              inMake(row, 'span', 'in-lc-bar-v', `${fmtN(v.value)} ${v.unit.replace('umol', 'µmol')}`);
            }
            src(k, 'UniProt, measured kinetics');
          }
          if (x.medgen && x.medgen.definition) {
            // MedGen's effects, without what doesn't belong to drinking (nitroglycerin), each in plain words
            const m = inMake(d, 'div', 'in-lc-effects');
            inMake(m, 'span', 'in-tag', 'What the buildup does (MedGen)');
            const sent = x.medgen.definition.split(/(?<=\.)\s/).find((t) => /results in/i.test(t)) || '';
            const list = (sent.match(/results in (.*?)(?:, as well as|\.$)/) || [])[1] || '';
            const PLAIN = [[/flushing/i, 'Flushing: the face and neck turn red and warm after a drink'],
                           [/toxicity/i, 'Acute alcohol toxicity: feeling poisoned by less alcohol than others'],
                           [/hangover/i, 'Hangovers: worse after-effects the next day']];
            for (const part of list.split(/,\s*(?:and\s+)?|\s+and\s+/).filter(Boolean)) {
              const pl = PLAIN.find(([rx]) => rx.test(part));
              const row = inMake(m, 'div', 'in-lc-eff');
              inMake(row, 'b', null, pl ? pl[1].split(':')[0] : part);
              if (pl) inMake(row, 'span', null, pl[1].split(': ')[1]);
            }
          }
          for (const e of x.effects) effect(d, e);
          const notes = x.uniprot.filter((t) => !NOISE.test(t)).map(caseFix).slice(0, 3);
          if (notes.length) { const t = inMake(d, 'div', 'in-lc-notes'); inMake(t, 'span', 'in-tag', 'UniProt'); for (const nt of notes) inMake(t, 'span', 'in-lc-note', nt); }
        };
        const panel = (title, cls, calls, level, text, gene) => {
          const d = inMake(panels, 'div', 'in-lc-panel in-lc-p-' + cls);
          inMake(d, 'b', 'in-lc-ptitle', title);
          const ch = inMake(d, 'div', 'in-lc-mini');
          const mol = (m, lvl) => { const x = inMake(ch, 'span', 'in-lc-m' + (lvl ? ' in-lc-m-' + lvl : ''), m); return x; };
          const FORM = { norm: 'wild-type', lof: 'slow form', gof: 'fast form' };
          const enz = (g, k) => { inMake(ch, 'span', 'in-lc-ar', '→'); const c = inMake(ch, 'span', 'lc-chip in-lc-form lc-' + k); inMake(c, 'b', null, g); inMake(c, 'small', null, FORM[k]); inMake(ch, 'span', 'in-lc-ar', '→'); };
          mol(mols[0]); enz(EX[0], calls[0]); mol(mols[1], level); enz(EX[1], calls[1]); mol(mols[2]);
          inMake(d, 'p', null, text);
          if (gene) numbers(d, gene);
        };
        panel('Wild-type (typical)', 'norm', ['norm', 'norm'], 'low', inT('Both enzymes work as in most people: {} is cleared about as fast as it is made.', mols[1]));
        // What controlled studies measured, in their abstracts' words (Europe PMC, read at export)
        let measuredRows = []; try { measuredRows = JSON.parse(((inCount('intro_stats') || []).find((r) => r.kind === 'example') || {}).measured || '[]'); } catch (e) { /* none */ }
        const studies = (gene) => {
          const rows = measuredRows.filter((m) => m.about === gene);
          if (!rows.length) return;
          const d = inMake(panels.lastElementChild, 'div', 'in-lc-measured');
          inMake(d, 'span', 'in-tag', 'Measured in people, after a dose like one beer');
          for (const m of rows) {
            inMake(d, 'p', null, `“${m.finding.charAt(0).toUpperCase() + m.finding.slice(1)}”`);
            src(d, `${m.study} · PMID ${m.pmid}`, m.pmid);
          }
        };
        const duringLine = (tpl) => { if (!box._beerDuring) return; const n = inMake(panels.lastElementChild, 'p', 'in-lc-during'); box._beerDuring.push([n, tpl]); };
        duringLine('For the {} the beer takes, acetaldehyde stays low.');
        {
          const tp = panels.lastElementChild, a1 = exOf(EX[0]), a2 = exOf(EX[1]);
          if (a1 && a1.speed && a1.speed.typical) { const n = inMake(tp, 'div', 'in-lc-num'); inMake(n, 'b', null, fmtN(a1.speed.typical.value)); inMake(n, 'span', null, inT('µmol of {} made by {} per minute, per mg of enzyme (Vmax)', mols[1], EX[0])); src(n, inT('{}, UniProt', a1.speed.typical_allele)); }
          if (a2 && a2.affinity) { const n = inMake(tp, 'div', 'in-lc-num'); inMake(n, 'b', null, `${a2.affinity.value} ${a2.affinity.unit.replace('uM', 'µM')}`); inMake(n, 'span', null, inT('{} grabs {} at this tiny concentration (Km): it clears it as soon as it appears', EX[1], mols[1])); src(n, 'UniProt'); }
        }
        panel(inT('{} less active (LoF)', EX[1]), 'lof', ['norm', 'lof'], 'high', inT('The second step slows: {} is made as before but cleared slowly, so it builds up.', mols[1]), EX[1]);
        if (bu) {
          const d = panels.lastElementChild, wt = bu.acetaldehyde.gof;
          const cite = (n) => { const sa = inMake(n, 'a', 'in-lc-src', inT('{} · {} g/kg, about one beer', bu.study, bu.dose_g_per_kg)); sa.href = `https://europepmc.org/article/PMC/${bu.pmcid}`; sa.target = '_blank'; sa.rel = 'noopener'; };
          let n = inMake(d, 'div', 'in-lc-num');
          inMake(n, 'b', null, `${bu.acetaldehyde.lof} µM`);
          inMake(n, 'span', null, Array.isArray(wt) ? inT('peak {} in the blood after one beer, against {} to {} µM with wild-type {}', mols[1], wt[0], wt[1], EX[1]) : inT('peak {} in the blood after one beer', mols[1]));
          cite(n);
          n = inMake(d, 'div', 'in-lc-num');
          inMake(n, 'b', null, `+${bu.heart.lof}%`);
          inMake(n, 'span', null, inT('heart rate 25 minutes after, against no change with wild-type {}', EX[1]));
          cite(n);
        }
        studies(EX[1]);
        panel(inT('{} more active (GoF)', EX[0]), 'gof', ['gof', 'norm'], 'low', inT('The first enzyme is far faster in the lab, yet in people the blood {} measures the same as typical. Carriers still drink less and are protected; why is not known yet.', mols[1]), EX[0]);
        studies(EX[0]);
        duringLine('For the {} the beer takes, blood acetaldehyde stays as in the typical form.');
        if (box._beerUpdate) box._beerUpdate();
        // Why we have them: UniProt's own words
        const why = inMake(box, 'div', 'in-lc-why');
        for (const g of EX) {
          const t = gene(g).protein_function;
          if (!t) continue;
          const d = inMake(why, 'div', 'in-lc-quote');
          inMake(d, 'span', 'in-tag', inT('Why we have {} (UniProt)', g));
          const sentences = t.split(/(?<=\.)\s/).filter((x) => /ethanol|alcohols|formaldehyde/i.test(x) && !/DOPAL|dopamine|esterase/.test(x)).slice(0, 2);
          inMake(d, 'p', null, (sentences.length ? sentences : [t.split(/(?<=\.)\s/)[0]]).join(' ').replace(/\.?$/, '.'));
        }
      }
      // A frontier: what is known is the pieces; how they add up is what the person puzzles together
      const fr = inMake(el, 'div', 'in-frontier');
      inMake(fr, 'h3', null, 'A new frontier');
      inMake(fr, 'p', null, 'Research maps one protein and one step at a time. How a slower step plays out in a whole body, alongside every other variant, is mostly unknown.');
      inMake(fr, 'p', null, 'Where the data exist, the explorer lays out the pieces: the chain, the person\'s variants in it, what each step needs, where it happens and the papers behind it.');
      inMake(fr, 'p', null, 'It gives you the data, not every answer. Some insights won\'t come from a paper but from people who learn which steps run differently in them and how that affects them in their everyday lives.');
      const more = inMake(el, 'div', 'in-deeper');
      const txt = inMake(more, 'div');
      inMake(txt, 'h4', null, 'Gene pathway');
      inMake(txt, 'p', null, 'In this tab every gene with a pathway is drawn step by step from Reactome: what each step takes in and gives out, the enzymes and how the person\'s variants change them, what the steps need, what switches the gene on or off, and the papers behind each finding.');
      if (!inLocked()) {
        const b = inMake(more, 'button', 'in-next', 'Open the Gene pathway tab');
        b.type = 'button';
        b.addEventListener('click', () => { dash.setParams({ lc_gene: 'ALDH2', lc_role: 1 }); gx.show('lifecycle'); });
      }
    } },
    { title: 'How to read the results', draw: (el, c) => {
      inText(el, 'Where a result is a level compared with other people, it is drawn on a bar from orange to green. Green is always on the right, the favourable side, whichever way the level runs: for LDL cholesterol lower is better, for HDL higher is better, and both bars put the better end on the right.');
      inMake(inMake(inMake(el, 'div', 'in-sample'), 'div', 'nt-bar'), 'i').style.left = '72%';
      inText(el, 'Where neither direction is better (TSH, testosterone), the bar is grey with green in the middle: the typical range is the favourable spot.');
      inMake(inMake(inMake(el, 'div', 'in-sample'), 'div', 'nt-bar nt-even'), 'i').style.left = '50%';
      inText(el, 'The marker shows where the genes put the person among Europeans. It is a starting point set by the genes, not a measured value: the lab test measures the real one, and lifestyle moves it.');
      inList(el, [
        'Medicines: every medicine with a guideline, a drug label or a study finding for the person\'s genes, with the dosing advice that applies.',
        'Nutrition: per nutrient, how the genes move its level in the blood and which steps of its uptake and conversion they touch.',
        'Biomarkers: common lab tests read through the genes, and which shifts are real and which only move the test.',
        'Clusters: health themes (cancer, fertility, muscle), gene by gene, with body maps and networks.',
        'Gene pathway and Profile: one gene\'s chemical journey, and the genes grouped into systems that work together.',
      ]);
    } },
    { title: 'Where to start', draw: (el, c) => {
      inText(el, 'Start with what can change a decision: the medicines where the dosing advice differs, the cancer and fertility genes with a changed function, then the nutrients and lab values marked in orange. Each tab starts with a short note on what it shows and where its facts come from.');
      if (!inLocked()) {
        const nav = inMake(el, 'div', 'in-nav');
        for (const t of ['medicines', 'nutrition', 'biomarkers', 'clusters']) inOpen(nav, t, TAB_NAMES[t]);
      }
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
