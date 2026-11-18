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
    { title: 'Reading a cluster', draw: (el, c) => {
      // The worked example (intro.py): one woman's female fertility theme and genotypes, the same whoever is selected.
      // Without it (an older export), the selected person's own theme is used.
      let exAll = null;
      try { const row = (gx.rows('intro_stats') || [[]])[0].find((x) => x.kind === 'cluster'); exAll = row && row.cluster ? JSON.parse(row.cluster) : null; } catch (e) { /* none */ }
      const EX = exAll && exAll._example;
      const r = EX ? [Object.entries(EX.facets).map(([facet, facet_name]) => ({ theme: EX.theme, theme_name: EX.theme_name, facet, facet_name })),
                      EX.genes.map((x) => ({ ...x, theme: EX.theme })), EX.links.map((x) => ({ ...x, theme: EX.theme }))]
        : gx.rows('theme_meta', 'theme_genes', 'theme_links');
      if (!r) { if (gx.failed('theme_meta', 'theme_genes', 'theme_links')) gx.failLine(el); return; }
      const [meta, genes, links] = r;
      // The labels: "the example" for the worked example, else the person
      const EXW = EX ? 'the example' : c.who, WL = EX ? 'example' : c.who;
      const prof = dash.data('profiles'), sex = prof.status === 'ok' ? ((prof.data.find((p) => p.id === c.who) || {}).sex) : null;
      const themes = [...new Set(meta.map((m) => m.theme))];
      const T = EX ? EX.theme : themes.find((t) => t === (sex === 'female' ? 'fertility_female' : 'fertility_male')) || themes[0];
      const tname = (meta.find((m) => m.theme === T) || {}).theme_name || T;
      const facetName = new Map(meta.filter((m) => m.theme === T).map((m) => [m.facet, m.facet_name]));
      const call = (g) => (g.genotype || (g.call_source === 'api' && g.function) ? (g.function || 'normal') : g.carried > 0 ? 'variant' : null);
      const shown = genes.filter((g) => g.theme === T && g.notable);
      const byName = new Map(shown.map((g) => [g.gene, g]));
      const tl = links.filter((l) => l.theme === T && byName.has(l.a) && byName.has(l.b));
      const partnersOf = (name) => tl.filter((l) => l.a === name || l.b === name).map((l) => ({ g: byName.get(l.a === name ? l.b : l.a), score: l.score }))
        .sort((a, b) => b.score - a.score);
      // The example: a changed gene with the most confident partners
      const cand = shown.filter((g) => ['LoF', 'GoF'].includes(call(g)));
      const sel = EX && byName.has(EX.gene) ? { g: byName.get(EX.gene) }
        : (cand.length ? cand : shown).map((g) => ({ g, n: partnersOf(g.gene).filter((p) => p.score >= 0.7).length })).sort((a, b) => b.n - a.n)[0];
      if (!sel) { inText(el, 'Choose a theme in the Clusters tab to see its network.'); return; }
      const g = sel.g, partners = partnersOf(g.gene).slice(0, 6);
      // A few unlinked genes, one per call, so the colours show
      const used = new Set([g.gene, ...partners.map((p) => p.g.gene)]), extra = [];
      for (const k of ['LoF', 'normal', 'GoF', null]) {
        const x = shown.find((o) => !used.has(o.gene) && call(o) === k && !partnersOf(o.gene).some((p) => p.g.gene === g.gene));
        if (x) { extra.push(x); used.add(x.gene); }
      }
      let ev = {}; try { ev = JSON.parse(g.evidence || '{}'); } catch (e) { /* no evidence */ }

      const deep = (exAll || {})[g.gene] || null;
      // An example without a profile behind it (the most common European genotypes): its call is read from GTEx, as the
      // tab reads expression calls: the copies of the allele that changes expression where GTEx finds it significant
      if (EX && deep && !call(g)) {
        const v = Object.keys(deep.gtex || {})[0], G = v && deep.gtex[v], sig = G ? G.rows.filter((x) => x.significant) : [];
        const n = ((EX.genotypes || {})[v] || '').split('').filter((x) => G && x === G.alt).length;
        if (n && sig.length) Object.assign(g, { rsid: v, genotype: EX.genotypes[v], function: sig[0].nes > 0 ? 'GoF' : 'LoF', basis: 'expression', dose: n });
      }
      inText(el, EX && deep
        ? inT('The Clusters tab draws each health theme as a network of genes. A worked example, the same for every profile: one woman\'s {} theme, where {} is one of the most connected changed genes. What its call means for her, from the measurements and studies behind it:', tname.toLowerCase(), g.gene)
        : deep
        ? inT('The Clusters tab draws each health theme as a network of genes. In {}\'s {} theme, {} is one of the most connected changed genes. What its call means for {}, from the measurements and studies behind it:', c.who, tname.toLowerCase(), g.gene, c.who)
        : inT('The Clusters tab draws each health theme as a network of genes, with a panel describing the gene you select. Here is {}\'s {} theme, with {} selected.', c.who, tname.toLowerCase(), g.gene));
      const grid = inMake(el, 'div', 'in-rc');

      // --- the network, drawn small from the person's own data, with numbered marks
      const left = inMake(grid, 'div', 'in-rc-net');
      inMake(left, 'div', 'in-chart-title', 'Connections');
      const NS = 'http://www.w3.org/2000/svg', W = 540, H = 330;
      const svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('class', 'in-rc-svg'); svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', inT('{} and its interaction partners in the {} theme', g.gene, tname.toLowerCase()));
      left.appendChild(svg);
      const sv = (tag, attrs, text) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; svg.appendChild(e); return e; };
      const nodes = [g, ...partners.map((p) => p.g), ...extra];
      const facets = [...new Set(nodes.map((n) => n.primary))].sort((a, b) => (a === g.primary ? -1 : b === g.primary ? 1 : 0));
      const spots = [[250, 175], [425, 100], [425, 255], [95, 95], [95, 260], [250, 45], [250, 300]];
      const anchor = new Map(facets.map((f, i) => [f, spots[i % spots.length]]));
      // each group's genes evenly round its spot; the selected gene at the centre of its own
      const pos = new Map(), rrOf = new Map();
      for (const f of facets) {
        const [ax, ay] = anchor.get(f), ring = nodes.filter((n) => n.primary === f && n !== g);
        if (f === g.primary) pos.set(g.gene, [ax, ay]);
        const rr = f === g.primary ? 66 : ring.length === 1 ? 0 : 30 + 4 * ring.length;
        rrOf.set(f, rr);
        ring.forEach((n, j) => {
          const a = (f === g.primary ? -Math.PI / 2 + 0.5 : -Math.PI / 4) + (j / ring.length) * 2 * Math.PI;
          pos.set(n.gene, [Math.max(16, Math.min(W - 70, ax + Math.cos(a) * rr)), Math.max(30, Math.min(H - 26, ay + Math.sin(a) * rr * 0.85))]);
        });
      }
      const FILL = { LoF: 'var(--color-bad)', GoF: 'var(--gof)', altered: 'var(--color-fg)', normal: 'var(--typical)', variant: 'var(--color-fg-muted)', unknown: 'var(--color-panel)' };
      const label = new Map();
      for (const f of facets) {
        const [ax, ay] = anchor.get(f), side = f === g.primary || ax < W * 0.35 ? 'start' : ax > W * 0.65 ? 'end' : 'middle';
        const lx = f === g.primary ? Math.max(28, ax - 90) : side === 'start' ? 24 : side === 'end' ? W - 4 : ax;
        const r0 = (rrOf.get(f) || 0) * 0.85;
        const ly = f === g.primary ? ay + r0 + 26 : ay < H / 2 ? Math.max(12, ay - r0 - 16) : Math.min(H - 4, ay + r0 + 24);
        const t = sv('text', { x: lx, y: ly, 'text-anchor': side, class: 'in-rc-facet' }, facetName.get(f) || f);
        label.set(f, t);
      }
      // faint lines between the other genes, strong ones from the selected gene
      for (const l of tl) {
        if (!pos.has(l.a) || !pos.has(l.b) || l.a === g.gene || l.b === g.gene) continue;
        const [x1, y1] = pos.get(l.a), [x2, y2] = pos.get(l.b);
        sv('line', { x1, y1, x2, y2, class: 'in-rc-edge', 'stroke-width': 0.6 + (l.score - 0.4) * 3 });
      }
      const [sx, sy] = pos.get(g.gene);
      for (const p of partners) {
        const [x2, y2] = pos.get(p.g.gene);
        sv('line', { x1: sx, y1: sy, x2, y2, class: 'in-rc-edge is-on', 'stroke-width': 0.6 + (p.score - 0.4) * 3 });
      }
      for (const n of nodes) {
        const [x, y] = pos.get(n.gene), fn = call(n), on = n === g || partners.some((p) => p.g === n);
        const ci = sv('circle', { cx: x, cy: y, r: n === g ? 10 : 7, class: 'in-rc-dot' + (n === g ? ' is-sel' : '') + (fn ? '' : ' is-none') + (on ? '' : ' is-dim') });
        ci.style.fill = fn ? FILL[fn] : 'var(--color-panel)';
        sv('text', { x: x + 12, y: y + 4, class: 'in-rc-name' + (n === g ? ' is-sel' : '') + (on ? '' : ' is-dim') }, n.gene).setAttribute('data-i18n-skip', '');
      }
      // numbered marks: 1 a group's name, 2 a coloured dot, 3 the most confident line, 4 the selected gene
      const mark = (n, x, y) => { sv('circle', { cx: x, cy: y, r: 9, class: 'in-rc-mark' }); sv('text', { x, y: y + 4, 'text-anchor': 'middle', class: 'in-rc-marknum' }, String(n)); };
      // What a mark must keep clear of: every drawn line, every dot and every gene name (names run right of their dots)
      const segs = [...svg.querySelectorAll('line')].map((l) => ['x1', 'y1', 'x2', 'y2'].map((k) => +l.getAttribute(k)));
      const blobs = nodes.flatMap((n) => { const [x, y] = pos.get(n.gene); return [[x, y], [x + 22, y], [x + 40, y]]; });
      // group names too, sampled along their estimated width (10px capitals, about 6.6px a letter)
      for (const t of label.values()) {
        const w = t.textContent.length * 6.6, an = t.getAttribute('text-anchor'), x0 = +t.getAttribute('x'), y0 = +t.getAttribute('y') - 4;
        const left = an === 'end' ? x0 - w : an === 'middle' ? x0 - w / 2 : x0;
        for (let x = left; x <= left + w; x += 10) blobs.push([x, y0]);
      }
      const segDist = (px, py, [x1, y1, x2, y2]) => {
        const dx = x2 - x1, dy = y2 - y1, t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy || 1)));
        return Math.hypot(px - x1 - t * dx, py - y1 - t * dy);
      };
      const placed = [];
      const clear = (x, y) => Math.min(...segs.map((sg) => segDist(x, y, sg)), ...blobs.map(([bx, by]) => Math.hypot(bx - x, by - y) - 4), ...placed.map(([a, b]) => Math.hypot(a - x, b - y)));
      // the nearest spot with at least `room` px clear of everything; the clearest one if none has that much
      const markNear = (n, tx, ty, room = 13) => {
        let best = null;
        for (const r of [16, 20, 24, 28, 34, 40, 48]) for (let k = 0; k < 16; k++) {
          const a = (k / 16) * 2 * Math.PI, x = tx + Math.cos(a) * r, y = ty + Math.sin(a) * r;
          if (x < 10 || x > W - 10 || y < 10 || y > H - 10) continue;
          const cl = clear(x, y), sc = cl >= room ? 100 - r : cl - 60;
          if (!best || sc > best[0]) best = [sc, x, y];
        }
        placed.push([best[1], best[2]]);
        mark(n, best[1], best[2]);
      };
      // 1 just before the selected gene's group name (left-aligned, so the mark holds whatever the language), 2 left of a
      // coloured dot, 3 beside the strongest line
      const lb = label.get(g.primary);
      markNear(1, +lb.getAttribute('x') - 4, +lb.getAttribute('y') - 4, 12);
      const other = extra.find((n) => call(n)) || nodes.find((n) => n !== g && call(n));
      if (other) { const [ox, oy] = pos.get(other.gene); markNear(2, ox, oy); }
      if (partners[0]) {
        const [px, py] = pos.get(partners[0].g.gene), len = Math.hypot(px - sx, py - sy) || 1;
        markNear(3, sx + (px - sx) * 0.6, sy + (py - sy) * 0.6);
      }
      markNear(4, sx, sy);
      const steps = inMake(left, 'ol', 'in-rc-steps');
      const step = (n, text, extraEl) => { const li = inMake(steps, 'li'); inMake(li, 'span', 'in-rc-num', String(n)); const d = inMake(li, 'div'); inMake(d, 'span', null, text); if (extraEl) extraEl(d); };
      step(1, 'Each dot is a gene. It sits in the group of the mechanism it acts through most (Gene Ontology), named in capitals.');
      step(2, inT('Its colour is {}\'s call for the gene, from their own variants:', EXW), (d) => {
        const lg = inMake(d, 'div', 'in-rc-legend');
        const drawn = new Set(nodes.map((n) => call(n) || null));
        for (const [k, t] of [['LoF', 'Less active'], ['altered', 'Changed'], ['GoF', 'More active'], [null, 'No call'], ['normal', 'Typical']].filter(([k]) => drawn.has(k))) {
          const s = inMake(lg, 'span'); const i = inMake(s, 'i', k ? null : 'is-none'); i.style.background = k ? FILL[k] : 'transparent'; s.append(t);
        }
      });
      step(3, 'Lines are protein interactions from STRING: the proteins bind or work together. Thicker lines are more confident.');
      step(4, 'Select a gene: it grows, its partners light up, the rest fade, and the panel beside the network describes it.');
      if (deep) steps.classList.add('is-compact');

      // --- the panel, as the Clusters tab draws it for this gene, block by block
      const answer = inMake(grid, 'div', 'in-rc-panel'), right = deep ? document.createElement('div') : answer;
      inMake(right, 'div', 'in-chart-title', 'Selected gene');
      let num = 4;
      const block = (n, build, text) => {
        const b = inMake(right, 'div', 'in-rc-block');
        inMake(b, 'span', 'in-rc-num', String(++num));
        const m = inMake(b, 'div', 'in-rc-mock'); build(m);
        inMake(b, 'p', 'in-rc-exp', text);
      };
      const fn = call(g), expr = g.basis === 'expression';
      const fnText = { LoF: expr ? 'Less expressed' : 'Less active', GoF: expr ? 'More expressed' : 'More active', normal: 'Typical function', altered: 'Changed, direction unclear', unknown: 'No known effect on the gene', variant: 'Carries a trait-linked variant' }[fn] || 'Not genotyped';
      const BASIS = { cpic: 'CPIC allele function', measured: 'measured protein function, MaveDB', curated: 'curated protein effect, UniProt', truncating: 'the change cuts the protein short', predicted: 'predicted damage, SIFT and PolyPhen', expression: 'gene expression, GTEx', none: 'no evidence about function' };
      block(5, (m) => {
        const h = inMake(m, 'div', 'lc-name'); inMake(h, 'h3', null, g.gene).setAttribute('data-i18n-skip', '');
        inMake(h, 'span', 'lc-call ' + ({ LoF: 'lof', GoF: 'gof', altered: 'altered', normal: 'norm', variant: 'var' }[fn] || 'unknown'), fn && fn !== 'normal' && g.dose ? inT('{} ×{}', fnText, g.dose) : fnText);
      }, 'The call: what the person\'s variant does to the gene, with ×1 or ×2 for one or two copies. Blue is more active or more expressed, red less, green typical.');
      if (g.fn_evidence) block(6, (m) => inMake(m, 'p', null, inT('Effect on the gene: {} ({}).', g.fn_evidence, BASIS[g.basis] || BASIS.none)),
        'What the call rests on: a measured or curated protein change (CPIC, MaveDB, UniProt), a predicted one (SIFT, PolyPhen), or a change in how much of the gene the body\'s tissues make (GTEx).');
      if (g.outcome && !['typical', 'unknown'].includes(g.outcome)) {
        const OUT = { positive: 'positive', negative: 'negative', neutral: 'neither good nor bad', unclear: 'whether this is good or bad is unclear' };
        block(7, (m) => inMake(m, 'p', null, inT('Effect on {}: {}.', c.who, OUT[g.outcome] || g.outcome)),
          'Whether the change is good or bad for the person, where the trait says which way is better. Often it is unclear, and it says so.');
      }
      if (g.call_source !== 'api' && g.genotype) block(8, (m) => inMake(m, 'p', 'gx-note', inT('Library note for {} {}: {}.', g.rsid, g.genotype, g.interpretation)),
        'A note from the old SNP library, which is being phased out. The call above comes from the evidence, not from the note.');
      if (g.has_lifecycle) block(9, (m) => {
        const b = inMake(m, 'button', 'lc-btn', 'Open its pathway'); b.type = 'button';
        b.addEventListener('click', () => { if (!inLocked()) { dash.setParams({ lc_gene: g.gene, lc_role: 1 }); gx.show('lifecycle'); } });
      }, 'Opens the gene in the Gene pathway tab: the chemical steps it takes part in, step by step.');
      const fs = (ev.findings || []).filter((f) => f.items.length);
      if (fs.length) block(10, (m) => {
        inMake(m, 'span', 'gx-label', inT('{}\'s variants with a known effect ({})', c.who, fs.length));
        const ul = inMake(m, 'ul', 'th-why');
        // one of each kind: a GWAS effect carried, an imputed call, a library note
        const pickF = [fs.find((f) => f.items.some((i) => i.source === 'GWAS' && i.copies > 0 && i.effect != null)),
                       fs.find((f) => f.confidence === 'high' || f.confidence === 'medium'), fs.find((f) => f.items.some((i) => i.source === 'Library'))]
          .filter((f, i, a) => f && a.indexOf(f) === i).slice(0, 3);
        for (const f of pickF) {
          const it = f.items.find((i) => i.source === 'GWAS' && i.copies > 0) || f.items[0];
          const d = inMake(inMake(ul, 'li'), 'div');
          inMake(d, 'span', 'th-src', it.source);
          if (f.confidence === 'high' || f.confidence === 'medium') inMake(d, 'span', 'th-imp th-imp-' + f.confidence, f.confidence === 'high' ? 'imputed, high confidence' : 'imputed, medium confidence');
          const known = /^[ACGT]$/.test(it.allele || '');
          if (it.source === 'GWAS' && known && it.copies != null) d.append(inT('{} {}: {} of {}, linked to {}.', f.rsid, f.genotype, it.copies === 1 ? '1 copy' : inT('{} copies', it.copies), it.allele, it.what));
          else d.append(inT('{} {}: {}.', f.rsid, f.genotype, String(it.what).replace(/\.$/, '')));
          if (it.pubmed) { d.append(' '); const a = inMake(d, 'a', null, 'PubMed'); a.href = `https://pubmed.ncbi.nlm.nih.gov/${it.pubmed}/`; a.target = '_blank'; a.rel = 'noopener'; }
        }
      }, 'Every SNP the person has in the gene with a finding: the source (GWAS Catalog, ClinVar or the library), the genotype, how many copies of the allele and the paper. A dashed badge marks a call filled in by imputation and how sure it is; no badge means the chip measured it.');
      block(11, (m) => {
        inMake(m, 'span', 'gx-label', inT('Why it is in {}', tname.toLowerCase()));
        const ul = inMake(m, 'ul', 'th-why');
        const mech = Object.entries(ev.mechanisms || {})[0];
        if (mech) { const d = inMake(inMake(ul, 'li'), 'div'); inMake(d, 'span', 'th-src', 'GO'); d.append(mech[1].terms.slice(0, 2).join('; ')); }
        const dis = Object.entries(ev.diseases || {})[0];
        if (dis) { const d = inMake(inMake(ul, 'li'), 'div'); inMake(d, 'span', 'th-src', d3.format('.2f')(dis[1].score)); d.append(inT('{} (Open Targets)', dis[0])); }
        inMake(m, 'span', 'gx-label', 'Interacts with, in this theme');
        const box = inMake(m, 'div', 'th-genes');
        for (const p of partners.slice(0, 4)) {
          const pf = call(p.g);
          inMake(box, 'span', 'lc-chip th-gene ' + (pf ? 'lc-' + ({ LoF: 'lof', GoF: 'gof', altered: 'alt', normal: 'norm', variant: 'var', unknown: 'untested' }[pf]) : 'lc-untested'), `${p.g.gene} · ${p.score.toFixed(2)}`).setAttribute('data-i18n-skip', '');
        }
      }, 'Why the gene belongs to the theme: its Gene Ontology mechanisms and its strongest Open Targets disease links (0 to 1). Then its STRING partners in the theme with their confidence, the lines of the network.');

      // --- 2. How the genes relate: what each link rests on (STRING's channels, a shared Reactome pathway, OmniPath's
      // direction) and how the two changes combine, from the person's own calls
      let pr = {};
      try { const row = (gx.rows('intro_stats') || [[]])[0].find((x) => x.kind === 'pairs'); pr = row && row.pairs ? JSON.parse(row.pairs) || {} : {}; } catch (e) { /* no table */ }
      const PT = pr.pairs || {}, PW = pr.pathways || [];
      const pairOf = (a, b) => PT[[a, b].sort().join('|')];
      const lcRows = gx.rows('lifecycle_genes'), lcg = lcRows ? lcRows[0] : [];
      const regs = (gene) => { const row = lcg.find((x) => x.gene === gene && x.regulators); try { return row ? JSON.parse(row.regulators) : []; } catch (e) { return []; } };
      const dirOf = (a, b) => {   // OmniPath, as the Gene pathway tab reads it: a regulator of b, or of a
        const ra = regs(b).find((x) => x.gene === a), rb = regs(a).find((x) => x.gene === b);
        const say = (x, r, y) => inT(r.effect === 'activates' ? '{} activates {}' : r.effect === 'inhibits' ? '{} inhibits {}' : '{} regulates {}', x, y);
        return ra ? say(a, ra, b) : rb ? say(b, rb, a) : null;
      };
      const kind = (x, y) => {
        const fx = call(x), fy = call(y);
        if (['LoF', 'GoF'].includes(fx) && ['LoF', 'GoF'].includes(fy)) return fx === fy ? (fx === 'LoF' ? 'Both less' : 'Both more') : 'Mixed';
        return fy === 'normal' ? 'Partner typical' : 'Partner not called';
      };
      const KIND_CLASS = { 'Both less': 'is-lof', 'Both more': 'is-gof', Mixed: 'is-mixed', 'Partner typical': 'is-norm', 'Partner not called': 'is-none' };
      const host = deep ? document.createElement('div') : el;
      const sec2 = inMake(host, 'div', 'in-rc-sec');
      inMake(sec2, 'h3', null, inT('How {} relates to its partners', g.gene));
      inText(sec2, 'A line in the network is a STRING interaction. STRING scores each pair from separate kinds of evidence, and Reactome says whether the two proteins share a pathway. Where both genes are changed in the person, the two changes either point the same way or opposite ways.');
      const tbl = inMake(sec2, 'div', 'in-rc-pairs');
      const head = inMake(tbl, 'div', 'in-rc-prow is-head');
      for (const t of ['Pair', 'How the changes combine', 'Evidence for the link (STRING, 0 to 1)', 'Shared Reactome pathway']) inMake(head, 'span', null, t);
      const CH = [['Experiments', 0], ['Databases', 1], ['Co-expression', 2], ['Text mining', 3]];
      const chip = (p, x) => {
        const f = call(x);
        inMake(p, 'span', 'lc-chip th-gene ' + (f ? 'lc-' + ({ LoF: 'lof', GoF: 'gof', altered: 'alt', normal: 'norm', variant: 'var', unknown: 'untested' }[f]) : 'lc-untested'),
          x.gene + (x.genotype ? ' ' + x.genotype : '')).setAttribute('data-i18n-skip', '');
      };
      const kinds = {};
      for (const p of partners.slice(0, 5)) {
        const row = inMake(tbl, 'div', 'in-rc-prow'), d = pairOf(g.gene, p.g.gene), k = kind(g, p.g);
        kinds[k] = (kinds[k] || 0) + 1;
        const c1 = inMake(row, 'div', 'in-rc-pair'); chip(c1, g); inMake(c1, 'span', 'in-rc-dash', '—'); chip(c1, p.g);
        const dir = dirOf(g.gene, p.g.gene);
        if (dir) inMake(c1, 'small', null, inT('{} (OmniPath)', dir));
        inMake(inMake(row, 'div'), 'span', 'in-rc-kind ' + KIND_CLASS[k], k);
        const ev = inMake(row, 'div', 'in-rc-ch');
        if (d) {
          for (const [t, i] of CH) {
            const r = inMake(ev, 'div', 'in-rc-chrow'); inMake(r, 'span', null, t);
            inMake(inMake(r, 'span', 'in-rc-chbar'), 'i').style.width = `${d[i]}%`;
            inMake(r, 'b', null, (d[i] / 100).toFixed(2));
          }
          inMake(ev, 'small', null, inT('Combined {}', (d[4] / 100).toFixed(2)));
        } else inMake(ev, 'small', null, inT('Combined {}; the channels are kept for pairs of {} or more', p.score.toFixed(2), (pr.min_score || 0.7).toFixed(1)));
        const sp = inMake(row, 'div', 'in-rc-path');
        if (d && d[6].length) { for (const i of d[6]) inMake(sp, 'span', null, PW[i]); if (d[5] > d[6].length) inMake(sp, 'small', null, inT('+{} more shared', d[5] - d[6].length)); }
        else inMake(sp, 'small', null, d ? 'None: they meet through other evidence' : '—');
      }
      // What the pair kinds mean, for the kinds on screen
      const MEAN = { 'Both less': 'Both proteins work less. Linked steps that both slow down point the same way, so the effects can add up.',
                     'Both more': 'Both proteins work more, or are made more. The changes point the same way and can reinforce each other.',
                     Mixed: 'One works more and the other less. The changes point opposite ways and can partly cancel.',
                     'Partner typical': 'Only one of the two is changed: the partner works as usual.',
                     'Partner not called': 'No call for the partner in the person\'s file, so how the two combine is not known.' };
      const lg2 = inMake(sec2, 'div', 'in-rc-kinds');
      for (const k of ['Both less', 'Mixed', 'Both more', 'Partner not called', 'Partner typical'].filter((k) => kinds[k])) {
        const d = inMake(lg2, 'div'); inMake(d, 'span', 'in-rc-kind ' + KIND_CLASS[k], k); inMake(d, 'span', null, MEAN[k]);
      }
      inMake(sec2, 'p', 'gx-note', 'Experiments: the proteins were seen binding or acting together in the lab. Databases: curated pathway and complex databases list them together. Co-expression: their genes are switched on together across tissues. Text mining: papers name them together.');

      // --- 3. What can be gained: where the changes gather, and where to go from there
      const sec3 = inMake(host, 'div', 'in-rc-sec');
      inMake(sec3, 'h3', null, 'What reading it gives');
      const byFacet = new Map();
      for (const x of shown) {
        const f = call(x), b = byFacet.get(x.primary) || { lof: 0, gof: 0, norm: 0, genes: [] };
        if (f === 'LoF') b.lof++; else if (f === 'GoF') b.gof++; else if (f === 'normal') b.norm++;
        if (f === 'LoF' || f === 'GoF') b.genes.push(x);
        byFacet.set(x.primary, b);
      }
      const ranked = [...byFacet.entries()].sort((a, b) => (b[1].lof + b[1].gof) - (a[1].lof + a[1].gof));
      const focus = (ranked.find(([f]) => f !== 'disease') || ranked[0] || [g.primary])[0];
      const fb = byFacet.get(focus) || { genes: [] };
      inText(sec3, inT('Where {}\'s changed genes gather in the {} theme, per mechanism. The busiest one with a known mechanism: {}.', c.who, tname.toLowerCase(), facetName.get(focus) || focus));
      const bars = inMake(sec3, 'div', 'in-rc-facets');
      const max = Math.max(1, ...ranked.map(([, b]) => b.lof + b.gof + b.norm));
      for (const [f, b] of ranked.slice(0, 8)) {
        const r = inMake(bars, 'div', 'in-rc-frow' + (f === focus ? ' is-focus' : ''));
        inMake(r, 'span', null, facetName.get(f) || f);
        const tr = inMake(r, 'span', 'in-rc-ftrack');
        for (const [n, cls] of [[b.lof, 'is-lof'], [b.gof, 'is-gof'], [b.norm, 'is-norm']]) if (n) inMake(tr, 'i', cls).style.width = `${(n / max) * 100}%`;
        inMake(r, 'b', null, inT('{} less · {} more · {} typical', b.lof, b.gof, b.norm));
      }
      const acts = inMake(sec3, 'div', 'in-rc-acts');
      // a. Gene pathway: the changed genes of the mechanism that have one
      const a1 = inMake(acts, 'div', 'in-rc-act');
      inMake(a1, 'b', null, 'Follow the chemistry');
      inMake(a1, 'p', 'gx-note', 'Changed genes of this mechanism with a pathway in the Gene pathway tab, and the Reactome pathway it opens on.');
      const withLc = fb.genes.filter((x) => x.has_lifecycle).slice(0, 5);
      for (const x of withLc) {
        const row = lcg.find((y) => y.gene === x.gene);
        const b = inMake(a1, 'button', 'in-rc-go'); b.type = 'button';
        chip(b, x); if (row) inMake(b, 'span', null, row.pathway);
        b.addEventListener('click', () => { if (!inLocked()) { dash.setParams({ lc_gene: x.gene, lc_role: 1 }); gx.show('lifecycle'); } });
      }
      if (!withLc.length) inMake(a1, 'p', 'gx-note', 'None of them has a Reactome pathway with steps yet.');
      // b. Lab tests and nutrients: findings where a changed gene of the theme moves a marker in the person (copies > 0)
      const a2 = inMake(acts, 'div', 'in-rc-act');
      inMake(a2, 'b', null, 'What a test can show');
      const lr = gx.rows('lab_findings', 'nut_findings', 'lab_tests', 'nut_nutrients');
      const changedHere = new Set(fb.genes.map((x) => x.gene)), changedAll = new Set(shown.filter((x) => ['LoF', 'GoF'].includes(call(x))).map((x) => x.gene));
      const finds = (set) => lr ? [...lr[0].map((x) => ({ ...x, src: 'lab' })), ...lr[1].map((x) => ({ ...x, src: 'nut' }))]
        .filter((x) => (set.has(x.gene) || set.has(x.step_gene)) && x.copies > 0 && x.direction) : [];
      let fl = finds(changedHere), scope = 'mechanism';
      if (!fl.length) { fl = finds(changedAll); scope = 'theme'; }
      inMake(a2, 'p', 'gx-note', scope === 'mechanism'
        ? inT('Lab values and nutrient levels that {}\'s changed genes in this mechanism move, from the GWAS Catalog.', c.who)
        : inT('None for this mechanism; across the whole {} theme, the lab values and nutrient levels {}\'s changed genes move, from the GWAS Catalog.', tname.toLowerCase(), c.who));
      const seen = new Set(), tests = new Map([...(lr ? lr[2] : []), ...(lr ? lr[3] : [])].map((t) => [t.id, t.name]));
      for (const x of fl.sort((a, b) => (a.grade || 'Z').localeCompare(b.grade || 'Z'))) {
        const key = x.marker_name + x.gene;
        if (seen.has(key) || seen.size >= 6) continue;
        seen.add(key);
        const r = inMake(a2, 'div', 'in-rc-find');
        inMake(r, 'span', 'th-src', tests.get(x.nutrient) || x.nutrient);
        r.append(inT('{} {} {}: {} copies of the allele that {} {}.', x.gene, x.rsid, x.genotype, x.copies, x.direction, x.marker_name));
        r.append(' ');
        const a = inMake(r, 'a', null, x.study || 'PubMed'); a.href = `https://pubmed.ncbi.nlm.nih.gov/${x.pmid}/`; a.target = '_blank'; a.rel = 'noopener';
      }
      if (!seen.size) inMake(a2, 'p', 'gx-note', 'No lab value or nutrient level is moved by these genes in the GWAS Catalog findings the tabs read.');
      if (!inLocked()) {
        const nav = inMake(a2, 'div', 'in-rc-nav');
        for (const [t, label] of [['biomarkers', 'Biomarkers'], ['nutrition', 'Nutrition in Clusters']]) { const b = inMake(nav, 'button', 'lc-btn', inT('Open {}', label)); b.type = 'button'; b.addEventListener('click', () => gx.show(t)); }
      }
      // --- The example gene, told for the person (intro.py CLUSTER: GTEx, UniProt, Reactome, studies in women, GWAS)
      if (deep) {
        const D = deep, who = EXW;
        const gt = new Map(EX ? Object.entries(EX.genotypes || {}) : (ev.findings || []).map((f) => [f.rsid, f.genotype]));
        if (g.rsid && g.genotype) gt.set(g.rsid, g.genotype);
        const same = (a, b) => !!a && !!b && a.split('').sort().join('') === b.split('').sort().join('');
        const copies = (rsid, allele) => (gt.get(rsid) || '').split('').filter((x) => x === allele).length;
        const tis = (t) => t.replace(/_/g, ' ').replace('Breast Mammary Tissue', 'Breast');
        const fmtP = (p) => (p == null ? '—' : p < 0.001 ? d3.format('.1e')(p) : d3.format('.2~g')(p));
        const cite = (parent, s) => { const a = inMake(parent, 'a', 'in-cl-cite', s.n ? inT('{}, {} women', s.study, inN(s.n)) : s.study); a.href = `https://pubmed.ncbi.nlm.nih.gov/${s.pmid}/`; a.target = '_blank'; a.rel = 'noopener'; return a; };
        const callG = D.gtex[g.rsid], callAlt = callG && callG.alt;
        const reproductive = (callG ? callG.rows : []).filter((r) => r.tissue !== 'Thyroid' && !r.significant);
        const sigRows = (callG ? callG.rows : []).filter((r) => r.significant);
        const studies = D.studies || [], st = (id) => studies.find((s) => s.id === id);
        const fd = (gx.rows('fd_phases') || [[]])[0];            // the selected person's (their trait scores)
        const fdChains = EX && EX.phases && EX.phases.length ? EX.phases : fd;   // the chains, the same for everyone

        // The answer, top right: each line read from the facts below
        answer.className = 'in-cl-answer';
        inMake(answer, 'div', 'in-chart-title', inT('What {} {} means for {}', g.gene, fnText.toLowerCase(), who));
        if (EX && EX.source !== 'profile') inMake(answer, 'p', 'gx-note', 'The example\'s genotypes are the most common ones among Europeans (1000 Genomes).');
        // The selected person's own calls at the same variants, beside the example (the studies were in women)
        let mineGt = {};
        try { mineGt = JSON.parse((c.p || {}).example_gt || '{}') || {}; } catch (e) { /* none */ }
        const myRs = Object.keys(D.gtex || {}).filter((rs) => mineGt[rs]);
        const pg = (rs) => ((c.p || {}).is_example ? undefined : mineGt[rs]);   // the example's own profile: no second tag
        if (EX && myRs.length && !(c.p || {}).is_example) {
          const m = inMake(answer, 'div', 'in-cl-me');
          inMake(m, 'b', null, inT('{} has:', c.who));
          for (const rs of myRs) inMake(m, 'span', same(mineGt[rs], gt.get(rs)) ? 'is-same' : null, `${rs} ${mineGt[rs]}`).setAttribute('data-i18n-skip', '');
          if (sex !== 'female') inMake(m, 'small', null, 'The studies below were done in women.');
        }
        const ul = inMake(answer, 'ul', 'in-cl-points');
        const point = (cls, head, text) => { const li = inMake(ul, 'li', cls); inMake(li, 'b', null, head); inMake(li, 'span', null, text); };
        if (sigRows.length) point('is-gtex', 'Where it acts', inT('{} copy of {} at {}: {} {} expression in {} (GTEx). In {} it was measured and is not distinguishable from zero.',
          copies(g.rsid, callAlt), callAlt, g.rsid, sigRows[0].nes > 0 ? 'more' : 'less', g.gene, sigRows.map((r) => tis(r.tissue)).join(', '), reproductive.map((r) => tis(r.tissue).toLowerCase()).join(', ')));
        const dose = st('dose');
        if (dose) {
          const mine = dose.groups.find((x) => same(x.label, gt.get(dose.rsid))), top = dose.groups.reduce((a, b) => (b.value > a.value ? b : a));
          if (mine) point(mine === top ? 'is-bad' : 'is-ok', inT('{} {}', dose.name, gt.get(dose.rsid)), inT('{} IU of FSH in IVF, against {} IU for {} ({}).', inN(mine.value), inN(top.value), top.label, dose.study));
        }
        const resp = st('response');
        if (resp) {
          const i = gt.get(resp.rsid) === resp.labels[0] ? 0 : 1, better = resp.rows.filter((r) => r.values[i] > r.values[1 - i]).length;
          point(better ? 'is-ok' : 'is-bad', inT('{} {}', resp.name, gt.get(resp.rsid)), inT('More of {} of {} IVF measures than the other genotypes ({}).', better, resp.rows.length, resp.study));
        }
        const odds = st('odds');
        if (odds) {
          const i = odds.labels.findIndex((l) => same(l, gt.get(odds.rsid)));
          if (i >= 0) point(i === 0 ? 'is-ok' : 'is-bad', inT('{} {}', odds.name, gt.get(odds.rsid)), i === 0
            ? inT('The reference form. Among infertile women with endometriosis, {} turned up at {} times and {} at {} times the odds of {} ({}).', odds.labels[1], odds.outcomes[0].odds[1], odds.labels[2], odds.outcomes[0].odds[2], odds.labels[0], odds.study)
            : inT('Among infertile women with endometriosis, {} turned up at {} times the odds of {} ({}).', odds.labels[i], odds.outcomes[0].odds[i], odds.labels[0], odds.study));
        }
        for (const w of D.gwas || []) {
          const n = copies(w.rsid, w.allele);
          if (n && w.estimate != null && !/unit/.test(w.ci)) point('is-warn', inT('{} {}', w.rsid, gt.get(w.rsid)), inT('{} copy of {}: {} odds ×{} per copy, a small effect ({} {}).', n, w.allele, w.trait.split(' (')[0].toLowerCase(), w.estimate, w.author, w.year));
        }
        const nStudy = studies.map((s) => s.n).filter(Boolean);
        if (nStudy.length) point('is-note', 'How strong', inT('The genotype studies followed {} to {} women; the GWAS effects come from up to {} people.', inN(Math.min(...nStudy)), inN(Math.max(...nStudy)),
          inN(Math.max(...(D.gwas || []).map((w) => +((w.sample.match(/[\d,]+/g) || []).map((x) => +x.replace(/,/g, '')).reduce((a, b) => a + b, 0)))))));
        if (!inLocked()) {
          const nav = inMake(answer, 'div', 'in-rc-nav');
          const go = (label, fn) => { const b = inMake(nav, 'button', 'lc-btn', label); b.type = 'button'; b.addEventListener('click', fn); };
          go('AMH, estradiol and SHBG', () => { dash.setParams({ bm_view: 'lab', lb_n: 'female_hormones' }); gx.show('biomarkers'); });
          if (sigRows.some((r) => r.tissue === 'Thyroid')) go('Thyroid (TSH)', () => { dash.setParams({ bm_view: 'lab', lb_n: 'thyroid' }); gx.show('biomarkers'); });
          if (g.has_lifecycle) go(inT('{} in Gene pathway', g.gene), () => { dash.setParams({ lc_gene: g.gene, lc_role: 1 }); gx.show('lifecycle'); });
          const ph = fdChains.find((p) => (p.chains || '').includes(`"gene": "${g.gene}"`));
          if (ph && T === 'fertility_female' && sex === 'female') go(ph.name, () => { dash.setParams({ theme: T }); gx.show('clusters'); if (window.gxFertility) window.gxFertility.open(ph.phase); });
        }

        // 1. What the call rests on: the variant's measured effect per tissue, beside how much the tissue makes of the gene
        const s1 = inMake(el, 'div', 'in-rc-sec');
        inMake(s1, 'h3', null, inT('1. What "{}" rests on', fnText.toLowerCase()));
        if (callG) {
          inText(s1, inT('GTEx measured how {}\'s expression changes with each copy of {} at {} in donated tissue. {} has {} {}.', g.gene, callAlt, g.rsid, who.charAt(0).toUpperCase() + who.slice(1), copies(g.rsid, callAlt) === 1 ? '1 copy' : inT('{} copies', copies(g.rsid, callAlt)), callAlt));
          const tb = inMake(s1, 'div', 'in-cl-gtex');
          const hd = inMake(tb, 'div', 'in-cl-grow is-head');
          for (const t of ['Tissue', inT('How much {} the tissue makes (median TPM)', g.gene), inT('Effect of each {} (NES)', callAlt), 'p']) inMake(hd, 'span', null, t);
          const maxT = Math.max(1, ...callG.rows.map((r) => r.tpm || 0)), lim = Math.max(0.15, ...callG.rows.map((r) => Math.abs(r.nes || 0))) * 1.15;
          for (const r of [...callG.rows].sort((a, b) => (b.tpm || 0) - (a.tpm || 0))) {
            const row = inMake(tb, 'div', 'in-cl-grow' + (r.significant ? ' is-sig' : ''));
            inMake(row, 'span', null, inT('{} (n = {})', tis(r.tissue), r.n || '—'));
            const tr = inMake(inMake(row, 'span', 'in-cl-tpm'), 'span', 'in-rc-chbar'); inMake(tr, 'i').style.width = `${((r.tpm || 0) / maxT) * 100}%`;
            tr.parentNode.append(d3.format('.1f')(r.tpm || 0));
            const ax = inMake(row, 'span', 'in-cl-nes'); inMake(ax, 'i', 'in-cl-zero');
            const dot = inMake(ax, 'b', r.significant ? 'is-sig' : null); dot.style.left = `${50 + ((r.nes || 0) / lim) * 50}%`;
            dot.title = d3.format('+.3f')(r.nes || 0);
            inMake(row, 'span', 'in-cl-p', r.significant ? inT('{}, significant', fmtP(r.p)) : fmtP(r.p));
          }
          inMake(s1, 'p', 'gx-note', inT('{} is made mostly in {}. A filled dot is an effect GTEx counts as significant; a hollow one was measured but is within chance.', g.gene,
            (callG.top_tpm || []).slice(0, 3).map(([t]) => tis(t).toLowerCase()).join(', ')));
          const vs = inMake(s1, 'div', 'in-cl-vars');
          for (const [rs, v] of Object.entries(D.gtex)) {
            if (!v) continue;
            const sig = v.rows.filter((r) => r.significant).map((r) => tis(r.tissue));
            const d = inMake(vs, 'span', sig.length ? 'is-sig' : null); inMake(d, 'b', null, `${rs} ${gt.get(rs) || '—'}`).setAttribute('data-i18n-skip', '');
            d.append(sig.length ? inT('changes expression in {}', sig.join(', ')) : 'no significant effect in these tissues');
          }
        }

        // 2. The mechanism: estradiol, the receptor, its partners and targets, and the cycle step it feeds
        const s2 = inMake(el, 'div', 'in-rc-sec');
        inMake(s2, 'h3', null, inT('2. What {} does, and with whom', g.gene));
        const rq = inMake(s2, 'q', 'in-cl-quote', D.reactome.summary); rq.setAttribute('data-i18n-skip', '');   // Reactome's own words
        const ra = inMake(s2, 'a', 'in-cl-cite', 'Reactome'); ra.href = `https://reactome.org/content/detail/${D.reactome.id}`; ra.target = '_blank'; ra.rel = 'noopener';
        const chain = inMake(s2, 'div', 'in-cl-chain');
        const node = (label, sub, cls) => { const n = inMake(chain, 'div', 'in-cl-node ' + (cls || '')); inMake(n, 'b', null, label); if (sub) inMake(n, 'small', null, sub); return n; };
        const arrow = () => inMake(chain, 'span', 'in-cl-arrow', '→');
        const fdChain = fdChains.map((p) => { try { return JSON.parse(p.chains || '[]').find((ch) => ch.some((x) => x.gene === g.gene)); } catch (e) { return null; } }).find(Boolean) || [];
        const before = fdChain.slice(0, fdChain.findIndex((x) => x.gene === g.gene)).filter((x) => !x.gene).slice(-1)[0];
        const after = fdChain.slice(fdChain.findIndex((x) => x.gene === g.gene) + 1).filter((x) => !x.gene)[0];
        if (before) { node(before.label, null, 'is-step'); arrow(); }
        const me = node(g.gene, inT('{} · {}', g.genotype ? `${g.rsid} ${g.genotype}` : '', fnText), 'is-' + ({ LoF: 'lof', GoF: 'gof', normal: 'norm' }[fn] || 'none'));
        me.title = D.function;
        arrow();
        const grp = inMake(chain, 'div', 'in-cl-partners');
        for (const p of partners.filter((p) => D.partners[p.g.gene])) {
          const k = kind(g, p.g), d = pairOf(g.gene, p.g.gene);
          const card = inMake(grp, 'div', 'in-cl-pcard');
          const h = inMake(card, 'div'); chip(h, p.g); inMake(h, 'span', 'in-rc-kind ' + KIND_CLASS[k], k);
          inMake(card, 'p', null, D.partners[p.g.gene]).setAttribute('data-i18n-skip', '');   // UniProt's own words
          const dir = dirOf(g.gene, p.g.gene);
          inMake(card, 'small', null, [dir ? inT('{} (OmniPath)', dir) : null, d ? inT('STRING {}: experiments {}, databases {}', (d[4] / 100).toFixed(2), (d[0] / 100).toFixed(2), (d[1] / 100).toFixed(2)) : null,
            d && d[6].length ? inT('shared pathway: {}', PW[d[6][0]]) : null].filter(Boolean).join(' · '));
        }
        if (after) { arrow(); node(after.label, null, 'is-step'); }
        const both = partners.filter((p) => D.partners[p.g.gene] && ['Both more', 'Both less'].includes(kind(g, p.g)));
        if (both.length) {
          const k0 = kind(g, both[0].g), bp = inMake(s2, 'div', 'in-cl-both');
          inMake(bp, 'span', 'in-rc-kind ' + KIND_CLASS[k0], k0);
          inMake(bp, 'b', null, inT('{}, {}', g.gene, both.map((p) => p.g.gene).join(', '))).setAttribute('data-i18n-skip', '');
          inMake(bp, 'span', null, MEAN[k0]);
        }

        // 3. Studies in women, by the person's genotypes
        const s3 = inMake(el, 'div', 'in-rc-sec');
        inMake(s3, 'h3', null, inT('3. Measured in women with {}\'s genotypes', who));
        const cards = inMake(s3, 'div', 'in-cl-studies');
        const card = (s, title) => { const b = inMake(cards, 'div', 'in-cl-study'); inMake(b, 'b', null, title); return b; };
        const quote = (b, s) => { if (s.finding) inMake(b, 'q', null, s.finding.replace(/: [^:]*?(estrogen receptor 1)/, ': … $1')).setAttribute('data-i18n-skip', ''); cite(b, s); };
        if (dose) {
          const b = card(dose, inT('{} {} · {}', dose.name, dose.rsid, dose.measure));
          const max = Math.max(...dose.groups.map((x) => x.value));
          for (const x of dose.groups) {
            const r = inMake(b, 'div', 'in-cl-bar' + (same(x.label, gt.get(dose.rsid)) ? ' is-mine' : ''));
            inMake(r, 'span', null, same(x.label, gt.get(dose.rsid)) ? inT('{} ({})', x.label, WL) : x.label);
            if (EX && same(x.label, pg(dose.rsid))) inMake(r.firstChild, 'em', 'in-cl-you', c.who).setAttribute('data-i18n-skip', '');
            inMake(inMake(r, 'span', 'in-cl-track'), 'i').style.width = `${(x.value / max) * 100}%`;
            inMake(r, 'b', null, inT('{} {}', inN(x.value), dose.unit));
          }
          quote(b, dose);
        }
        if (resp) {
          const mineI = gt.get(resp.rsid) === resp.labels[0] ? 0 : 1;
          const b = card(resp, inT('{} {} · {}', resp.name, resp.rsid, resp.measure));
          const lg = inMake(b, 'div', 'in-rc-legend');
          const youI = pg(resp.rsid) ? (pg(resp.rsid) === resp.labels[0] ? 0 : 1) : -1;
          resp.labels.forEach((l, i) => {
            const s = inMake(lg, 'span'); inMake(s, 'i', i === mineI ? 'is-mine' : 'is-other'); s.append(i === mineI ? inT('{} ({})', l, WL) : l);
            if (EX && i === youI) inMake(s, 'em', 'in-cl-you', c.who).setAttribute('data-i18n-skip', '');
          });
          const max = Math.max(...resp.rows.flatMap((r) => r.values));
          for (const r of resp.rows) {
            const row = inMake(b, 'div', 'in-cl-pair');
            inMake(row, 'span', null, r.measure);
            const bars = inMake(row, 'span', 'in-cl-pbars');
            r.values.forEach((v, i) => { const t = inMake(bars, 'span', 'in-cl-track'); const ii = inMake(t, 'i', i === mineI ? 'is-mine' : 'is-other'); ii.style.width = `${(v / max) * 100}%`; inMake(t, 'em', null, d3.format('~g')(v)); });
            inMake(row, 'small', null, inT('p {}', fmtP(r.p)));
          }
          quote(b, resp);
        }
        if (odds) {
          const mineI = odds.labels.findIndex((l) => same(l, gt.get(odds.rsid))), youI = odds.labels.findIndex((l) => same(l, pg(odds.rsid)));
          const ng = odds.n_groups || [];
          const b = card(odds, inT('{} {} · {}', odds.name, odds.rsid, odds.measure));
          inMake(b, 'p', 'in-cl-explain', ng.length === 3
            ? inT('The study compared {} infertile women with endometriosis and {} women whose IVF had failed with {} fertile women, and counted each form of {} in every group.', ng[0], ng[1], ng[2], odds.rsid)
            : inT('The study compared infertile women with fertile women, and counted each form of {} in every group.', odds.rsid));
          inMake(b, 'p', 'in-cl-explain', inT('An odds ratio compares two forms: 2 means a woman with that form was twice as likely, in odds, to be in the infertile group as a woman with {}. {} is the reference, ×1.', odds.labels[0], odds.labels[0]));
          const TITLE = { 'Endometriosis-related infertility': 'How much more often each form turns up in infertile women with endometriosis, compared with {}',
                          'IVF failure': 'How much more often each form turns up in women whose IVF failed, compared with {}' };
          const max = Math.max(...odds.outcomes.flatMap((o) => o.odds));
          for (const o of odds.outcomes) {
            inMake(b, 'span', 'in-cl-sub', inT(TITLE[o.outcome] || '{}', odds.labels[0]));
            o.odds.forEach((v, i) => {
              const r = inMake(b, 'div', 'in-cl-bar is-wide' + (i === mineI ? ' is-mine' : '') + (i ? ' is-risk' : ''));
              const lab = inMake(r, 'span', null, i === mineI ? inT('{} ({})', odds.labels[i], WL) : odds.labels[i]);
              if (EX && i === youI) inMake(lab, 'em', 'in-cl-you', c.who).setAttribute('data-i18n-skip', '');
              inMake(inMake(r, 'span', 'in-cl-track'), 'i').style.width = `${(v / max) * 100}%`;
              inMake(r, 'b', null, i ? inT('{} times the odds of {} (p {})', v, odds.labels[0], fmtP(o.p[i])) : '×1, the reference');
            });
          }
          quote(b, odds);
        }
        const meta = st('meta');
        if (meta) { const b = card(meta, inT('{} {} · {}', meta.name, meta.rsid, meta.measure)); quote(b, meta); }
        if ((D.gwas || []).length) {
          const b = card(null, 'GWAS Catalog, per copy');
          for (const w of D.gwas) {
            const n = copies(w.rsid, w.allele), r = inMake(b, 'div', 'in-cl-gw');
            inMake(r, 'b', null, `${w.rsid} ${gt.get(w.rsid) || '—'}`).setAttribute('data-i18n-skip', '');
            r.append(/unit/.test(w.ci)
              ? inT('each {} {} {} by {} SD; {} has {}.', w.allele, /decrease/.test(w.ci) ? 'lowers' : 'raises', w.trait.toLowerCase(), d3.format('.3~f')(w.estimate), who, n)
              : inT('each {} multiplies the odds of {} by {}; {} has {}.', w.allele, w.trait.split(' (')[0].toLowerCase(), w.estimate, who, n));
            r.append(' ');
            const a = inMake(r, 'a', 'in-cl-cite', inT('{} {}', w.author, w.year)); a.href = `https://pubmed.ncbi.nlm.nih.gov/${w.pmid}/`; a.target = '_blank'; a.rel = 'noopener';
          }
        }

        // 4. Your turn: the example was one gene's worth; the method, step by step, with the selected person's own starting
        // points (their theme by sex and their most connected changed genes, read from their own Clusters data)
        const s4 = inMake(el, 'div', 'in-rc-sec in-yt');
        inMake(s4, 'h3', null, '4. Your turn: the same reading, on your own genes');
        inText(s4, inT('Everything above is one worked example: the value a single gene and its cluster can yield. {}\'s own networks hold many more genes like it, each waiting to be read the same way. Here is the method, with {}\'s starting points.', c.who, c.who));
        const own = gx.rows('theme_meta', 'theme_genes', 'theme_links');
        let myT = null, myName = null, top = [];
        if (own) {
          const [om, og, ol] = own;
          const ts = [...new Set(om.map((m) => m.theme))];
          myT = ts.find((t) => t === (sex === 'female' ? 'fertility_female' : 'fertility_male')) || ts[0];
          myName = (om.find((m) => m.theme === myT) || {}).theme_name || myT;
          const mine = og.filter((x) => x.theme === myT && x.notable), names = new Set(mine.map((x) => x.gene));
          const deg = new Map();
          for (const l of ol) if (l.theme === myT && l.score >= 0.7 && names.has(l.a) && names.has(l.b)) { deg.set(l.a, (deg.get(l.a) || 0) + 1); deg.set(l.b, (deg.get(l.b) || 0) + 1); }
          top = mine.filter((x) => ['LoF', 'GoF'].includes(call(x))).map((x) => ({ x, n: deg.get(x.gene) || 0 })).filter((t) => t.n).sort((p1, p2) => p2.n - p1.n).slice(0, 5);
        }
        const openGene = (gene) => { if (inLocked()) return; dash.setParams({ theme: myT, th_gene: gene, th_organ: null, th_facet: null }); gx.show('clusters'); };
        const ol2 = inMake(s4, 'ol', 'in-yt-steps');
        const stepY = (n, title, like, body) => {
          const li = inMake(ol2, 'li');
          inMake(li, 'span', 'in-yt-n', String(n));
          const d = inMake(li, 'div');
          const h = inMake(d, 'div', 'in-yt-h'); inMake(h, 'b', null, title); if (like) inMake(h, 'span', 'in-yt-like', inT('as in {} above', like));
          if (body) body(d);
        };
        stepY(1, 'Open your own theme in Clusters', null, (d) => {
          if (myT && !inLocked()) { const bt = inMake(d, 'button', 'lc-btn', inT('Open {}: {}', c.who, myName)); bt.type = 'button'; bt.addEventListener('click', () => openGene(null)); }
        });
        stepY(2, 'Pick your most connected changed genes', null, (d) => {
          if (!top.length) { inMake(d, 'p', 'gx-note', 'No changed gene with high-confidence partners in this theme.'); return; }
          inMake(d, 'p', 'gx-note', inT('{}\'s changed genes with the most high-confidence partners (STRING ≥ 0.7) in the theme. Each opens in Clusters, selected.', c.who));
          const box = inMake(d, 'div', 'in-yt-genes');
          for (const { x, n } of top) {
            const bt = inMake(box, 'button', 'lc-chip th-gene lc-' + ({ LoF: 'lof', GoF: 'gof' }[call(x)]), inT('{} · {} partners', x.gene + (x.genotype ? ' ' + x.genotype : ''), n));
            bt.type = 'button'; bt.addEventListener('click', () => openGene(x.gene));
          }
        });
        stepY(3, 'Read what each call rests on', '1', (d) => inMake(d, 'p', 'gx-note', 'The gene panel\'s "Effect on the gene": which kind of evidence, and in which tissue. An expression change measured only far from where the gene works says little about that organ.'));
        stepY(4, 'Follow the partners and shared pathways', '2', (d) => inMake(d, 'p', 'gx-note', 'The partners under "Interacts with", and "Open its pathway" for the chemical steps. Partners changed the same way can add up; opposite ways can partly cancel.'));
        stepY(5, 'Look for studies measured in people with your genotype', '3', (d) => inMake(d, 'p', 'gx-note', 'Each variant in the panel links its paper. Look for studies that report outcomes per genotype, and note how many people they followed.'));
        stepY(6, 'Check the lab values that would show it', null, (d) => {
          inMake(d, 'p', 'gx-note', 'Where a change should move something measurable, the Biomarkers tab reads those tests through the genes.');
          if (!inLocked()) { const bt = inMake(d, 'button', 'lc-btn', 'Open Biomarkers'); bt.type = 'button'; bt.addEventListener('click', () => { dash.setParams({ bm_view: 'lab' }); gx.show('biomarkers'); }); }
        });
      }
    } },
    { title: 'Your DNA and EU law', draw: (el) => {
      let LAWS = [];
      try { const row = (gx.rows('intro_stats') || [[]])[0].find((x) => x.kind === 'law'); LAWS = JSON.parse(row.law || '[]') || []; } catch (e) { /* none */ }
      const Q = {};
      for (const a of LAWS) for (const q of a.quotes) Q[a.short + ' ' + q.ref] = { ...q, act: a };
      const slug = (k) => 'in-lw-' + k.replace(/[^A-Za-z0-9]+/g, '-');
      // A reference chip: 'IVDR Art. 2(2)|(c)' is IVDR's quoted Art. 2(2), labelled with its point (c); a click shows the quote
      const chip = (parent, spec) => {
        const [key, sub] = spec.split('|'), q = Q[key];
        const b = inMake(parent, q ? 'button' : 'span', 'in-lw-chip', key + (sub || ''));
        b.setAttribute('data-i18n-skip', '');
        if (q) {
          b.type = 'button';
          b.title = q.text.length > 220 ? q.text.slice(0, 220) + '…' : q.text;
          b.addEventListener('click', () => {
            const t = document.getElementById(slug(key));
            if (!t) return;
            t.scrollIntoView({ block: 'center', behavior: 'smooth' });
            t.classList.remove('is-flash'); void t.offsetWidth; t.classList.add('is-flash');
          });
        }
        return b;
      };
      const chips = (parent, specs) => { const w = inMake(parent, 'span', 'in-lw-chips'); for (const s of specs) chip(w, s); return w; };
      const sec = (n, title) => { const s = inMake(el, 'div', 'in-rc-sec in-lw-sec'); inMake(s, 'h3', null, inT('{}. {}', n, title)); return s; };
      inMake(el, 'p', 'in-lw-lead', 'Two EU regulations frame a tool like this one. The GDPR protects genetic data; the IVDR decides when software that reads DNA is a medical device. Below: why the explorer stops where it does, what the two say in their own words, and how the explorer keeps to them.');

      // 1. Why the explorer stops where it does: each thing it could do, the rule that would apply, what it does instead
      const s3 = sec(1, 'Why the explorer stops where it does');
      inMake(s3, 'p', 'gx-note', 'Each of these needs a CE-marked device: a quality system, clinical performance studies and a notified body\'s review, kept up for as long as it is on the market. That is the work of a medical device maker. The explorer stays a research reference instead.');
      const tbl = inMake(s3, 'div', 'in-lw-table');
      for (const t of ['What it could do', 'What the law asks of that', 'What it does instead']) inMake(tbl, 'div', 'in-lw-th', t);
      for (const [could, ask, refs, instead] of [
        ['Tell you your risk of a disease', 'A class C device, reviewed and CE-marked first', ['IVDR Art. 2(2)|(c)', 'IVDR Annex VIII, Rule 3', 'IVDR Art. 5(1)'], 'Shows what studies found for your genotype, with each study\'s size and evidence grade'],
        ['Tell you which medicine or dose suits you', 'A companion diagnostic: class C', ['IVDR Art. 2(2)|(e)', 'IVDR Annex VIII, Rule 3'], 'Shows the published pharmacogenetic guidelines for your genotype, as written'],
        ['Run as a website anyone uploads their DNA to', 'An online device must comply in full; genetic data on a server needs a legal basis', ['IVDR Art. 6(1)', 'GDPR Art. 9(1)'], 'Runs on your own computer only, served on 127.0.0.1; there is no hosted version'],
        ['Read anyone\'s DNA file', 'Their explicit consent', ['GDPR Art. 9(1)', 'GDPR Art. 9(2)(a)'], 'Your own file, or another person\'s with their consent'],
        ['Call its findings a diagnosis or a risk score', 'No claim of a function it doesn\'t have', ['IVDR Art. 7'], 'Says what was measured and by whom: "associated with", "studies found"']]) {
        inMake(tbl, 'div', 'in-lw-td is-could', could);
        const c2 = inMake(tbl, 'div', 'in-lw-td is-ask'); inMake(c2, 'span', null, ask); chips(c2, refs);
        inMake(tbl, 'div', 'in-lw-td is-instead', instead);
      }

      // 2. What the law says, in its own words
      if (LAWS.length) {
        const s2 = sec(2, 'What the law says');
        inMake(s2, 'p', 'gx-note', 'Quoted word for word from the official text in EUR-Lex. Under each quote: what it means for the explorer.');
        const HERE = {
          'GDPR Art. 4(13)': 'A DNA test file is genetic data: it describes one person\'s inherited characteristics.',
          'GDPR Art. 9(1)': 'Genetic data is a special category. Processing it is forbidden unless one of the exceptions in Art. 9(2) applies.',
          'GDPR Art. 9(2)(a)': 'For another person\'s file, their explicit consent is that exception.',
          'GDPR Art. 2(2)(c)': 'Your own file, read by you, for yourself, on your own computer, is a purely personal activity.',
          'GDPR Art. 5(1)(c)': 'Only what a lookup needs leaves the computer: rs numbers and gene names, never genotypes.',
          'GDPR Art. 17(1)': 'A person added by mistake, or no longer wanted, is removed with every file made for them.',
          'IVDR Art. 2(2)': 'Software counts, and so do a predisposition to disease (c) and the response to a treatment (e). This is the definition the explorer stays outside.',
          'IVDR Art. 2(12)': 'The maker\'s stated purpose decides. The explorer\'s: a reference to published research, for your own reading.',
          'IVDR Annex VIII, Rule 3': 'Genetic tests, and tests that decide a medicine, are class C: a notified body reviews them before they reach anyone.',
          'IVDR Art. 5(1)': 'A device must meet the whole regulation before it is used, whether it is sold or given away.',
          'IVDR Art. 6(1)': 'Offering it as an online service counts too.',
          'IVDR Art. 7': 'Words matter: claiming a diagnosis, or functions a tool doesn\'t have, is prohibited. The explorer says "studies found", never "you have".',
          'IVDR Art. 4(1)': 'Genetic tests used in healthcare come with information on what they mean. The explorer is not part of healthcare; every finding links to the study behind it.' };
        const MARK = { 'IVDR Art. 2(2)': /\((?:c|e)\)[^;.]*[;.]/g, 'IVDR Annex VIII, Rule 3': /\((?:f|i)\)[^;]*;/g };
        const grid = inMake(s2, 'div', 'in-lw-acts');
        for (const a of LAWS) {
          const card = inMake(grid, 'div', 'in-lw-act');
          const h = inMake(card, 'div', 'in-lw-act-h');
          inMake(h, 'b', null, a.short).setAttribute('data-i18n-skip', '');
          const link = inMake(h, 'a', 'in-cl-cite', a.act); link.href = a.url; link.target = '_blank'; link.rel = 'noopener'; link.setAttribute('data-i18n-skip', '');
          for (const q of a.quotes) {
            const key = a.short + ' ' + q.ref;
            const r = inMake(card, 'div', 'in-lw-q'); r.id = slug(key);
            inMake(r, 'span', 'in-lw-ref', q.ref).setAttribute('data-i18n-skip', '');
            const body = inMake(r, 'div');
            const qq = inMake(body, 'q'); qq.setAttribute('data-i18n-skip', '');
            const rx = MARK[key];
            if (rx) {
              let at = 0;
              for (const m of q.text.matchAll(rx)) { qq.append(q.text.slice(at, m.index)); inMake(qq, 'mark', null, m[0]); at = m.index + m[0].length; }
              qq.append(q.text.slice(at));
            } else qq.textContent = q.text;
            if (HERE[key]) inMake(body, 'p', 'in-lw-here', HERE[key]);
          }
        }
      }

      // 3. How it keeps to the law: where the data goes, and each measure with its article
      const s4 = sec(LAWS.length ? 3 : 2, 'How the explorer keeps to it');
      const flow = inMake(s4, 'div', 'in-lw-flow');
      const node = (parent, cls, title, lines) => { const n = inMake(parent, 'div', 'in-lw-node ' + (cls || '')); inMake(n, 'b', null, title); for (const l of lines) inMake(n, 'small', null, l); return n; };
      node(flow, 'is-file', 'Your raw DNA file', ['From the DNA test company']);
      inMake(flow, 'span', 'in-lw-arrow', '→');
      const pc = inMake(flow, 'div', 'in-lw-pc');
      inMake(pc, 'div', 'in-lw-pc-label', 'This computer · served on 127.0.0.1 only');
      const inner = inMake(pc, 'div', 'in-lw-inner');
      node(inner, null, 'data/input', ['A copy of the file']);
      inMake(inner, 'span', 'in-lw-arrow', '→');
      node(inner, null, 'Imputation and analysis', ['Beagle and the analysis run here']);
      inMake(inner, 'span', 'in-lw-arrow', '→');
      node(inner, null, 'data/output', ['Results and the explorer\'s datasets']);
      const dbs = ((window.GX_SOURCES || {}).databases || []);
      const out = inMake(flow, 'div', 'in-lw-out');
      const ex = inMake(out, 'div', 'in-lw-exchange');
      inMake(ex, 'span', 'in-lw-up', 'rs numbers, gene names →');
      inMake(ex, 'span', 'in-lw-down', '← published research facts');
      const pub = inMake(out, 'div', 'in-lw-node is-pub');
      inMake(pub, 'b', null, inT('{} public research databases', dbs.length));
      const logos = inMake(pub, 'div', 'in-lw-logos');
      for (const d of dbs.slice(0, 12)) { const t = inLogo(logos, d); t.title = d.name; }
      if (dbs.length > 12) inMake(logos, 'span', 'in-lw-more', inT('+{}', dbs.length - 12));
      const ms = inMake(s4, 'div', 'in-lw-measures');
      for (const [b, t, refs] of [
        ['Your file stays on your computer.', 'The explorer is served on 127.0.0.1 only; its makers receive nothing.', ['GDPR Art. 2(2)(c)', 'IVDR Art. 6(1)']],
        ['Only public identifiers leave.', 'rs numbers and gene names go to the research databases. They say nothing about whose file they came from.', ['GDPR Art. 5(1)(c)']],
        ['Removing a person removes everything.', 'Abandon deletes all an unfinished run made. For a finished person, delete their file in data/input and their files in data/output.', ['GDPR Art. 17(1)']],
        ['Another person\'s file needs their consent.', 'Add a person is for your own file, or for someone who has given explicit consent.', ['GDPR Art. 9(2)(a)']],
        ['It claims no medical purpose.', 'It lays out published research, graded by evidence, and leaves the reading to you.', ['IVDR Art. 2(12)', 'IVDR Art. 7']]]) {
        const m = inMake(ms, 'div', 'in-lw-measure');
        inMake(m, 'span', 'in-lw-tick', '✓');
        const body = inMake(m, 'div');
        inMake(body, 'b', null, b); inMake(body, 'p', null, t); chips(body, refs);
      }
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
