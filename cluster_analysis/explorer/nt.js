  // Nutrition: per nutrient, the steps that take it up, carry it and convert it (Reactome), where each happens, and
  // where the person's variants act on them and how (protein change, expression change). The net effect on the blood
  // level is one summary line per marker. Every text node is one whole template, so the Swedish layer can swap it.
  // The dashboard runs each script in its own scope, so the helpers shared with md.js are its own copies here.
  const NT_GRADES = ['A+', 'A', 'B', 'C'];
  const NT_GRADE_NOTE = { 'A+': 'expert-reviewed (ClinVar 3–4 stars)', A: 'replicated, or ClinVar 2 stars', B: 'one publication, or ClinVar 1 star', C: 'a single study (ClinPGx)' };
  const ntMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const ntWho = (rows) => (rows.find((r) => r.person) || {}).person || gx.who();
  const ntRank = (g) => { const i = NT_GRADES.indexOf(g); return i < 0 ? NT_GRADES.length : i; };
  const ntTag = (parent, g) => { ntMake(parent, 'span', 'md-grade md-grade-' + (g === 'A+' ? 'ap' : String(g).toLowerCase()), g).title = `Evidence grade ${g}: ${NT_GRADE_NOTE[g] || ''}`; };
  const ntJ = (s) => { try { return s ? JSON.parse(s) : null; } catch (e) { return null; } };
  const ntNum = (v) => (v >= 100 ? Math.round(v) : +Number(v).toPrecision(3)).toLocaleString('en');
  const ntT = (tpl, ...vals) => vals.reduce((s, v) => s.replace('{}', v), tpl);
  const ntMain = (n) => (ntJ(n.markers) || []).find((m) => m.score);
  const ntSide = (m) => {
    const p = m.score.percentile, side = p <= 20 ? 'low' : p >= 80 ? 'high' : 'typical';
    const bad = side !== 'typical' && m.higher !== 'neutral' && (side === 'low') === (m.higher === 'better');
    return { side, bad, good: side !== 'typical' && m.higher !== 'neutral' && !bad };
  };
  const ntLow = (rows) => rows.filter((n) => (ntJ(n.markers) || []).some((m) => m.score && ntSide(m).bad));
  // Where a percentile sits, in words: a band, and the lowest or highest share of Europeans it falls in
  const ntBand = (p) => p <= 5 ? 'Very low' : p <= 20 ? 'Low' : p < 40 ? 'Below average' : p <= 60 ? 'Average' : p < 80 ? 'Above average' : p < 95 ? 'High' : 'Very high';
  const ntPos = (p, long) => p > 40 && p <= 60 ? (long ? 'Near the middle among Europeans.' : 'middle')
    : p <= 50 ? ntT(long ? 'In the lowest {}% of Europeans.' : 'lowest {}%', Math.max(1, p)) : ntT(long ? 'In the highest {}% of Europeans.' : 'highest {}%', Math.max(1, 100 - p));
  const ntBar = (parent, m) => {
    const b = ntMake(parent, 'div', 'nt-bar' + (m.higher === 'worse' ? ' nt-flip' : m.higher === 'neutral' ? ' nt-even' : ''));
    const p = m.score.percentile;
    ntMake(b, 'i').style.left = (m.higher === 'worse' ? 100 - p : p) + '%';
    b.title = ntT('Genetic level: {}', ntBand(p).toLowerCase());
  };
  // Why a variant moves the level for the person: which allele they carry or lack, against most Europeans
  const NT_WHY = {
    'lowers raises 0': 'For {}: lowers the level. {} lacks the raising allele.',
    'lowers raises 1': 'For {}: lowers the level. {} has one copy of the raising allele, where most Europeans have two.',
    'lowers lowers 1': 'For {}: lowers the level. {} carries one copy of the lowering allele.',
    'lowers lowers 2': 'For {}: lowers the level. {} carries two copies of the lowering allele.',
    'raises lowers 0': 'For {}: raises the level. {} lacks the lowering allele.',
    'raises lowers 1': 'For {}: raises the level. {} has one copy of the lowering allele, where most Europeans have two.',
    'raises raises 1': 'For {}: raises the level. {} carries one copy of the raising allele.',
    'raises raises 2': 'For {}: raises the level. {} carries two copies of the raising allele.',
  };
  const ntWhy = (f, who) => { const tpl = NT_WHY[`${f.xy} ${f.direction} ${f.copies}`]; return tpl ? ntT(tpl, who, who) : f.xy === 'lowers' ? `For ${who}: lowers the level.` : `For ${who}: raises the level.`; };
  // Source text: the first sentences, the rest behind "More"
  const ntQuote = (parent, text, limit = 260) => {
    const q = ntMake(parent, 'span', 'nt-quote');
    const parts = (text || '').split(/(?<=[a-z0-9)\]]\.)\s+(?=[A-Z])/);
    let short = '';
    for (const x of parts) { if (short && short.length + x.length > limit) break; short = (short + ' ' + x).trim(); }
    q.textContent = short || text || '–';
    if (short && short.length < (text || '').length - 1) {
      const b = ntMake(parent, 'button', 'nt-more', 'More');
      b.type = 'button';
      b.addEventListener('click', () => { const open = b.textContent === 'More' || b.textContent === 'Mer'; q.textContent = open ? text : short; b.textContent = open ? 'Less' : 'More'; });
    }
  };
  // A small version of the lifecycle chain around one step: the step before → the molecule it hands over → this
  // gene's step → the molecule it makes → the step after. Before and after are the nearest steps of the same pathway
  // that make this step's input or take its output (Reactome); without one the card says N/A.
  const ntMols = (x) => (x || '').split('; ').filter(Boolean);
  const ntChain = (parent, s, st, g, fs) => {
    const same = st.filter((x) => x.pathway === s.pathway && x.step !== s.step);
    const ins = ntMols(s.inputs), outs = ntMols(s.outputs);
    const prev = same.filter((x) => x.order < s.order && ntMols(x.outputs).some((m) => ins.includes(m))).pop();
    const next = same.find((x) => x.order > s.order && ntMols(x.inputs).some((m) => outs.includes(m)));
    const c = ntMake(parent, 'div', 'nt-chain');
    const arrow = () => ntMake(c, 'span', 'nt-chain-arrow', '→').setAttribute('aria-hidden', 'true');
    const mol = (names) => { arrow(); if (names.length) { ntMake(c, 'span', 'nt-mol', names.slice(0, 2).join(', ')); arrow(); } };
    const card = (label, x, here) => {
      const d = ntMake(c, 'div', 'nt-card' + (here ? ' nt-card-here' : x ? '' : ' nt-card-na'));
      ntMake(d, 'span', 'nt-card-label', label);
      if (!x) { ntMake(d, 'span', 'nt-card-name', 'N/A'); return; }
      ntMake(d, 'span', 'nt-card-name', x.name);
      const gs = ntMake(d, 'span', 'nt-card-genes');
      for (const gene of x.genes.split(' ').filter(Boolean).slice(0, 4)) {
        const f = here && gene === g ? fs[0] : null;
        ntMake(gs, 'span', 'nt-chip-gene' + (f ? (ntBad(f) === 'bad' ? ' nt-chip-bad' : ' nt-chip-mine') : ''), f && f.genotype ? `${gene} ${f.genotype}` : gene);
      }
    };
    card('Step before', prev);
    mol(prev ? ntMols(prev.outputs).filter((m) => ins.includes(m)) : ins);
    card('This gene', s, true);
    mol(next ? outs.filter((m) => ntMols(next.inputs).includes(m)) : outs);
    card('Step after', next);
  };
  // How common the person's genotype is among Europeans (Hardy-Weinberg from the allele's European frequency)
  const ntRare = (parent, f) => {
    if (f.copies == null || f.allele_freq == null || !f.genotype) return;
    const p = f.allele_freq, q = f.copies === 2 ? p * p : f.copies === 1 ? 2 * p * (1 - p) : (1 - p) * (1 - p);
    const pct = Math.round(q * 100);
    ntMake(parent, 'div', 'nt-sub', q < 0.01 ? ntT('Rare genotype: about 1 in {} Europeans has {}.', ntNum(Math.round(1 / Math.max(q, 1e-7))), f.genotype)
      : ntT(q < 0.05 ? 'Uncommon genotype: about {}% of Europeans have {}.' : q < 0.25 ? 'Fairly common genotype: about {}% of Europeans have {}.'
        : 'Common genotype: about {}% of Europeans have {}.', pct, f.genotype));
  };
  const ntTarget = (t) => !t ? '' : t.min_e == null ? `${t.kind} ${ntNum(t.value)} ${(t.unit || '').replace('RE/µg', 'µg RE')} a day` : `At least ${ntNum(t.value)} g omega-3 a day`;
  // Whether a finding works against the person (their copies move the level the unfavourable way), for it, or neither
  const ntBad = (f) => f.xy === 'carried' ? 'bad' : !f.xy || f.xy === 'typical' || f.higher === 'neutral' ? null
    : (f.xy === 'lowers') === (f.higher === 'better') ? 'bad' : 'good';
  // Genes known to move a test (labtests.json): "your normal may differ" when the gene shifts the value without the body
  // being affected, "worth following up" when the shift is real. Each says whether the person's own variants in the
  // gene move it, and cites the GWAS Catalog study with the strongest association.
  const ntNotes = (parent, notes, finds, who) => {
    if (!notes.length) return;
    const box = ntMake(parent, 'div', 'nt-block');
    ntMake(box, 'span', 'gx-label', 'Genes that move this test');
    for (const note of notes) {
      const fs = finds.filter((f) => (f.gene || '').split(/[\s,;-]+/).includes(note.gene) || f.step_gene === note.gene);
      const moved = fs.filter((f) => f.xy && f.xy !== 'typical');
      const d = ntMake(box, 'div', 'nt-note' + (moved.length ? ' nt-note-on' : ''));
      ntMake(d, 'b', null, note.kind === 'test' ? 'Your normal may differ' : 'Worth following up');
      ntMake(d, 'span', null, ' · ' + note.gene + ': ');
      ntMake(d, 'span', null, note.text);
      ntMake(d, 'div', moved.length ? 'nt-low' : 'nt-sub', moved.length
        ? ntT(moved.length === 1 ? `${who} carries a variant here that moves the level (1 variant).` : `${who} carries variants here that move the level ({} variants).`, moved.length)
        : fs.length ? `${who} has the usual copies at the variants read here.` : `No variant of ${who}'s in this gene is among the findings.`);
      const src = note.source;
      if (src) {
        const a = ntMake(d, 'a', 'nt-src', ntT('{} {} · GWAS Catalog {}', src.author, src.year, src.study));
        a.href = `https://pubmed.ncbi.nlm.nih.gov/${src.pmid}/`; a.target = '_blank'; a.rel = 'noopener';
      }
    }
  };

  // Lab tests read as a lab report: panels of analytes, each with the code it is ordered under (LOINC), the sample, the
  // person's genetic baseline and the genes that move the reading. The clinical side (what the test is, why it is
  // ordered, how to prepare, what results mean) is MedlinePlus's, quoted as written (nutrition/lab_clinical.py → GX_LAB).
  const LB_PANELS = ['Heart and vessels', 'Metabolism', 'Liver and kidneys', 'Blood', 'Hormones'];
  const lbClin = (key) => ((window.GX_LAB || {}).tests || {})[key] || { markers: {} };
  const lbPage = (url) => ((window.GX_LAB || {}).pages || {})[url];
  // Which of a test's genes move the reading for the person: the notes whose gene carries a finding that shifts it
  const lbMoved = (note, finds) => finds.filter((f) => ((f.gene || '').split(/[\s,;-]+/).includes(note.gene) || f.step_gene === note.gene)
    && f.xy && f.xy !== 'typical');
  // The sample code of a marker: the part of the test field ("P-LDL, P-HDL, ...") that names it, else the one in its place
  // when the field lists one per marker
  const lbCode = (n, m, i, count) => {
    const parts = (n.test || '').split(/,\s*/).filter(Boolean);
    const low = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
    const hit = parts.find((p) => low(p).includes(low(m.id)) || low(p).includes(low(m.name)));
    return hit || (parts.length === count ? parts[i] : null);
  };
  const lbLevel = (parent, m) => {
    const c = ntMake(parent, 'span', 'lb-level');
    if (!m || !m.score) { ntMake(c, 'span', 'nt-sub', 'No genetic score'); return; }
    ntBar(c, m);
    const s = ntSide(m), tl = ntMake(c, 'small', s.bad ? 'nt-low' : s.good ? 'nt-high' : 'nt-sub');
    ntMake(tl, 'span', null, ntBand(m.score.percentile));
    ntMake(tl, 'span', null, ' · ');
    ntMake(tl, 'span', null, ntPos(m.score.percentile));
  };
  const lbGenes = (parent, notes, finds, who) => {
    const c = ntMake(parent, 'span', 'lb-genes');
    if (!notes.length) { ntMake(c, 'span', 'nt-sub', '–'); return; }
    for (const note of notes) {
      const on = lbMoved(note, finds).length > 0;
      const g = ntMake(c, 'span', `lb-gene lb-gene-${note.kind}${on ? ' lb-gene-on' : ''}`, note.gene);
      g.title = note.kind === 'test'
        ? (on ? `${note.gene}: ${who}'s variants shift the reading without the body being affected` : `${note.gene} can shift the reading without the body being affected; ${who} has the usual copies`)
        : (on ? `${note.gene}: ${who}'s variants move the level for real` : `${note.gene} moves the level for real; ${who} has the usual copies`);
    }
  };

  const lbReport = (el, rows, finds, nuts, who, cur, pick) => {
    // Every analyte, test by test
    const items = [];
    for (const n of rows) {
      const ms = ntJ(n.markers) || [], clin = lbClin('lab:' + n.id), notes = ntJ(n.notes) || [];
      const fs = finds.filter((f) => f.nutrient === n.id);
      ms.forEach((m, i) => items.push({ n, m, c: clin.markers[m.id] || {}, code: lbCode(n, m, i, ms.length), notes: i === 0 ? notes : [], allNotes: notes, fs, panel: n.group, lab: true }));
    }
    for (const n of nuts) {
      const ms = ntJ(n.markers) || [], clin = lbClin('nut:' + n.id);
      ms.forEach((m) => { if (clin.markers[m.id]) items.push({ n, m, c: clin.markers[m.id], code: null, notes: [], allNotes: [], fs: [], panel: 'Vitamins and minerals', lab: false }); });
    }
    const shifted = rows.filter((n) => (ntJ(n.notes) || []).some((x) => x.kind === 'test' && lbMoved(x, finds.filter((f) => f.nutrient === n.id)).length));
    const real = rows.filter((n) => (ntJ(n.notes) || []).some((x) => x.kind === 'body' && lbMoved(x, finds.filter((f) => f.nutrient === n.id)).length));
    const low = items.filter((x) => x.m.score && ntSide(x.m).bad);
    const panels = [...LB_PANELS, 'Vitamins and minerals'].filter((p) => items.some((x) => x.panel === p));
    ntMake(el, 'p', null, ntT(`{} analytes in {} panels, each with the code it is ordered under (LOINC) and ${who}'s genetic baseline: where ${who}'s genes put the value among Europeans.`, items.length, panels.length));
    const sum = ntMake(el, 'div', 'lb-sum');
    const fact = (cls, label, list, text) => {
      if (!list.length) return;
      const d = ntMake(sum, 'div', 'lb-fact ' + cls);
      ntMake(d, 'b', null, ntT(label, list.length));
      ntMake(d, 'span', 'nt-sub', text);
      const pills = ntMake(d, 'div', 'md-pills');
      for (const x of list) {
        const b = ntMake(pills, 'button', 'md-pill', x.name);
        b.type = 'button';
        b.addEventListener('click', () => {
          if (x.lab === false) { dash.setParams({ nt_n: x.n.id }); gx.show('nutrition'); return; }
          pick(x.n || x); document.getElementById('lb-detail').scrollIntoView({ behavior: 'smooth' });
        });
      }
    };
    fact('lb-fact-test', shifted.length === 1 ? '1 test reads differently' : '{} tests read differently', shifted,
      `${who}'s variants shift the reading without the body being affected: ${who}'s normal may sit outside the usual reference range.`);
    fact('lb-fact-body', real.length === 1 ? '1 test worth following up' : '{} tests worth following up', real,
      `${who}'s variants move the level for real, in genes known to drive it.`);
    fact('lb-fact-low', low.length === 1 ? '1 analyte leans the unfavourable way' : '{} analytes lean the unfavourable way', low.map((x) => ({ ...x, name: x.m.name })),
      `${who}'s genetic baseline is in the lowest or highest fifth of Europeans, on the unfavourable side.`);
    if (!sum.children.length) ntMake(sum, 'p', 'nt-sub', `${who}'s genes point to typical readings throughout.`);
    const leg = ntMake(el, 'div', 'lb-legend');
    ntMake(ntMake(leg, 'span', 'lb-legend-item'), 'span', 'lb-gene lb-gene-test', 'Gene');
    ntMake(leg, 'span', null, 'shifts the reading only: the body is not affected');
    ntMake(ntMake(leg, 'span', 'lb-legend-item'), 'span', 'lb-gene lb-gene-body', 'Gene');
    ntMake(leg, 'span', null, 'moves the level for real');
    ntMake(ntMake(leg, 'span', 'lb-legend-item'), 'span', 'lb-gene lb-gene-body lb-gene-on', 'Gene');
    ntMake(leg, 'span', null, ntT(`bold: ${who}'s own variants move it`));
    for (const p of panels) {
      const sec = ntMake(el, 'section', 'lb-panel');
      const list = items.filter((x) => x.panel === p);
      const h = ntMake(sec, 'h3');
      ntMake(h, 'span', null, p);
      ntMake(h, 'span', 'th-sp-count', ' · ' + list.length);
      if (p === 'Vitamins and minerals') ntMake(sec, 'p', 'nt-sub lb-panel-note', 'The nutrients\' blood tests. Select one to open it under Nutrition, with how the nutrient is taken up and converted.');
      const tab = ntMake(sec, 'div', 'lb-table');
      const hd = ntMake(tab, 'div', 'lb-row lb-head');
      for (const t of ['Analyte', 'Sample', `${who}'s genetic baseline`, 'Genes that move the reading']) ntMake(hd, 'span', null, t);
      for (const x of list) {
        const b = ntMake(tab, 'button', 'lb-row' + (x.lab && x.n.id === cur ? ' lb-on' : ''));
        b.type = 'button';
        const a = ntMake(b, 'span', 'lb-cell');
        ntMake(a, 'b', null, x.m.name);
        if (x.c.loinc) ntMake(a, 'span', 'th-cl-code', 'LOINC ' + x.c.loinc).title = x.c.loinc_name || '';
        const s = ntMake(b, 'span', 'lb-cell');
        if (x.code) ntMake(s, 'span', null, x.code);
        if (x.c.sample) ntMake(s, 'span', 'nt-sub', x.c.sample);
        lbLevel(ntMake(b, 'span', 'lb-cell'), x.m);
        const g = ntMake(b, 'span', 'lb-cell');
        if (x.lab) lbGenes(g, x.notes, x.fs, who);
        else ntMake(g, 'span', 'nt-sub', 'Nutrition →');
        b.addEventListener('click', () => {
          if (!x.lab) { dash.setParams({ nt_n: x.n.id }); gx.show('nutrition'); return; }
          pick(x.n); document.getElementById('lb-detail').scrollIntoView({ behavior: 'smooth' });
        });
      }
    }
  };

  // The clinical path of one test: why it is ordered → before the test → the person's genetic baseline → reading their
  // result → what results mean. The first, second and last are MedlinePlus's words; the middle two are the person's.
  const lbPath = (el, n, finds, who) => {
    const ms = ntJ(n.markers) || [], clin = lbClin('lab:' + n.id), notes = ntJ(n.notes) || [];
    const urls = [...new Set(ms.map((m) => (clin.markers[m.id] || {}).page).filter(Boolean))];
    const pg = lbPage(urls[0]);
    if (pg && pg.what && pg.what.text.length) { const w = ntMake(el, 'p', 'nt-why lb-what'); ntQuote(w, pg.what.text.join(' '), 320); }
    const box = ntMake(el, 'div', 'nt-block');
    ntMake(box, 'span', 'gx-label', 'The clinical path');
    const path = ntMake(box, 'div', 'lb-path');
    const step = (no, title) => { const s = ntMake(path, 'div', 'lb-step'); const h = ntMake(s, 'div', 'lb-step-head'); ntMake(h, 'span', 'lb-step-no', String(no)); ntMake(h, 'b', null, title); return s; };
    // A section's first paragraphs; one that leads into a list ("Anyone age 19 or younger:") goes with the list under
    // "In full", where every paragraph and list item stands as MedlinePlus wrote it
    const paras = (parent, sec, k = 2) => {
      if (!sec) { ntMake(parent, 'p', 'nt-sub', 'MedlinePlus has no page for this test.'); return; }
      const lead = sec.text.filter((t) => !/:\s*$/.test(t));
      lead.slice(0, k).forEach((t) => ntQuote(ntMake(parent, 'p', 'nt-why'), t, 240));
      if (sec.list.length || lead.length > k) {
        const d = ntMake(parent, 'details', 'lb-why');
        ntMake(d, 'summary', null, sec.list.length ? ntT(sec.list.length === 1 ? 'In full (1 listed item)' : 'In full ({} listed items)', sec.list.length) : 'In full');
        for (const t of sec.text) ntMake(d, 'p', 'nt-why nt-quote', t);
        if (sec.list.length) { const ul = ntMake(d, 'ul'); for (const li of sec.list) ntMake(ul, 'li', null, li); }
      }
    };
    const s1 = step(1, 'Why it is ordered');
    paras(s1, pg && pg.used, 1);
    if (pg && pg.why && pg.why.list.length) {
      const d = ntMake(s1, 'details', 'lb-why');
      ntMake(d, 'summary', null, ntT(pg.why.list.length === 1 ? 'When it is ordered (1 reason)' : 'When it is ordered ({} reasons)', pg.why.list.length));
      if (pg.why.text[0]) ntMake(d, 'p', 'nt-why nt-quote', pg.why.text[0]);
      const ul = ntMake(d, 'ul');
      for (const li of pg.why.list) ntMake(ul, 'li', null, li);
    }
    const s2 = step(2, 'Before the test');
    paras(s2, pg && pg.prepare, 2);
    const s3 = step(3, `${who}'s genetic baseline`);
    for (const m of ms) {
      const d = ntMake(s3, 'div', 'lb-base');
      ntMake(d, 'b', null, m.name);
      lbLevel(d, m);
    }
    const s4 = step(4, `Reading ${who}'s result`);
    const moved = notes.map((x) => ({ x, fs: lbMoved(x, finds) })).filter((o) => o.fs.length);
    if (!notes.length) ntMake(s4, 'p', 'nt-why', `No gene is listed as moving this test: read ${who}'s value against the usual reference range.`);
    else if (!moved.length) ntMake(s4, 'p', 'nt-why', `${who} has the usual copies of the genes known to move this test: read the value against the usual reference range.`);
    for (const { x } of moved) {
      const d = ntMake(s4, 'p', 'nt-why ' + (x.kind === 'test' ? 'lb-read-test' : 'lb-read-body'));
      ntMake(d, 'b', null, x.kind === 'test' ? `${who}'s normal may differ` : 'Worth following up');
      ntMake(d, 'span', null, ' · ' + x.gene + ': ');
      ntMake(d, 'span', null, x.text);
    }
    const s5 = step(5, 'What the results mean');
    paras(s5, pg && pg.results, 2);
    // Sources: each marker's LOINC code and the MedlinePlus pages quoted
    const src = ntMake(box, 'div', 'lb-src nt-src');
    for (const m of ms) {
      const c = clin.markers[m.id];
      if (c && c.loinc) ntMake(src, 'span', null, ntT('LOINC {} · {}', c.loinc, c.loinc_name || m.name));
    }
    for (const u of urls) {
      const p = lbPage(u);
      if (!p) continue;
      const a = ntMake(src, 'a', null, ntT('MedlinePlus: {} (in English)', p.title));
      a.href = p.url; a.target = '_blank'; a.rel = 'noopener';
    }
  };

  // One tab drawn from a nutrition.py output: Nutrition (nutrients.json) and Biomarkers (labtests.json)
  const ntTab = (K) => {
  let all = false;
    const pick = (n) => { all = false; dash.setParams({ [K.param]: n.id }); };

    // K.only: the cards show only while it holds (the fitness scores sit in the Clusters page under the muscle theme)
    const off = (el) => { const c = el.closest('.gx-card'), o = !!K.only && !K.only(); if (c) c.classList.toggle('th-off', o); return o; };
    dash.draw(K.over, (el) => {
      if (off(el)) return;
      const r = gx.rows(K.main, K.steps);
      if (!r) { if (gx.failed(K.main, K.steps)) gx.failLine(el); return; }
      const [rows, steps] = r;
      if (!rows.length) { gx.emptyLine(el); return; }
      el.replaceChildren();
      const who = ntWho(rows), low = ntLow(rows), cur = dash.params()[K.param] || (low[0] || rows[0]).id;
      ntMake(el, 'h3', null, K.title(who));
      if (K.lab) {
        const more = gx.rows(K.finds, 'nut_nutrients');
        if (!more) return;
        lbReport(el, rows, more[0], more[1], who, cur, pick);
        return;
      }
      ntMake(el, 'p', null, low.length ? K.low(who)
        : `${who}'s genes point to typical levels throughout.`);
      if (low.length) {
        const pills = ntMake(el, 'div', 'md-pills');
        for (const n of low) { const b = ntMake(pills, 'button', 'md-pill', n.name); b.type = 'button'; b.addEventListener('click', () => pick(n)); }
      }
      const grid = ntMake(el, 'div', 'nt-grid');
      for (const n of rows) {
        const b = ntMake(grid, 'button', 'nt-tile');
        b.type = 'button';
        b.setAttribute('aria-pressed', String(n.id === cur));
        ntMake(b, 'b', null, n.name);
        const m = ntMain(n);
        if (m) {
          ntBar(b, m);
          const s = ntSide(m);
          const tl = ntMake(b, 'small', s.bad ? 'nt-low' : s.good ? 'nt-high' : null);
          ntMake(tl, 'span', null, ntBand(m.score.percentile));
          ntMake(tl, 'span', null, ' · ');
          ntMake(tl, 'span', null, ntPos(m.score.percentile));
        } else ntMake(b, 'small', null, 'No genetic score');
        const k = steps.filter((s) => s.nutrient === n.id).length;
        if (k) ntMake(b, 'small', 'nt-sub', k === 1 ? '1 step found' : ntT('{} steps found', k));
        b.addEventListener('click', () => { pick(n); document.getElementById(K.card).scrollIntoView({ behavior: 'smooth' }); });
      }
    });

    // One variant: what it changes, the person's copies, and which way it moves the level for them
    const ntVariant = (parent, f, who) => {
      const d = ntMake(parent, 'div', 'nt-find' + (ntBad(f) === 'bad' ? ' nt-find-bad' : ntBad(f) === 'good' ? ' nt-find-good' : ''));
      ntTag(d, f.grade);
      const det = ntJ(f.detail) || {};
      const top = ntMake(d, 'div');
      ntMake(top, 'b', null, `${f.step_gene || f.gene || ''} ${det.change || f.rsid}`);
      ntMake(top, 'span', 'nt-sub', ` · ${f.rsid} · ${who}: ${f.genotype || '–'}`);
      if (f.confidence === 'high') ntMake(top, 'span', 'th-imp th-imp-high', 'imputed, high confidence');
      if (f.mechanism === 'protein') {
        ntMake(d, 'div', null, !det.change ? 'Changes the protein.' : ntT(det.copies === 2 ? `Changes the protein: {} ({}). ${who} carries the change on both copies.`
          : det.copies === 1 ? `Changes the protein: {} ({}). ${who} carries the change on one copy.` : det.copies === 0 ? `Changes the protein: {} ({}). ${who} does not carry the change.`
          : 'Changes the protein: {} ({}).', det.long, det.change));
      } else if (f.mechanism === 'expression') {
        ntMake(d, 'div', null, ntT(det.more ? 'The {} allele makes more {} (GTEx: {}, {} tissues).' : 'The {} allele makes less {} (GTEx: {}, {} tissues).',
          det.allele, det.gene, det.tissue, det.tissues));
      } else if (f.mechanism === 'in_gene') ntMake(d, 'div', 'nt-sub', 'In the gene; how it changes the gene is not known.');
      if (f.kind === 'GWAS' || f.kind === 'Score') {
        ntMake(d, 'div', null, ntT(f.direction === 'raises' ? '{} raises: {}' : '{} lowers: {}', f.allele, f.marker_name));
        if (f.xy) ntMake(d, 'div', ntBad(f) === 'bad' ? 'nt-low' : ntBad(f) === 'good' ? 'nt-high' : 'nt-sub',
          f.xy === 'typical' ? `${who} has the usual copies: no shift.` : ntWhy(f, who));
        ntRare(d, f);
        const a = ntMake(d, 'a', 'nt-src', ntT(f.publications === 1 ? '{} · 1 publication' : '{} · {} publications', f.study, f.publications));
        a.href = `https://pubmed.ncbi.nlm.nih.gov/${f.pmid}/`; a.target = '_blank'; a.rel = 'noopener';
      } else ntMake(d, 'div', null, f.kind === 'ClinVar' ? `ClinVar: ${f.text} (${f.copies}×${f.allele})` : `${f.chemical}: ${f.effect || f.text || '–'}`);
    };

    dash.draw(K.detail, (el) => {
      if (off(el)) return;
      const r = gx.rows(K.main, K.finds, K.steps);
      if (!r) { if (gx.failed(K.main, K.finds, K.steps)) gx.failLine(el); return; }
      const [rows, finds, steps] = r;
      if (!rows.length) { gx.emptyLine(el); return; }
      el.replaceChildren();
      const who = ntWho(rows);
      const n = rows.find((x) => x.id === dash.params()[K.param]) || ntLow(rows)[0] || rows[0];
      const t = ntJ(n.target);
      const head = ntMake(el, 'div', 'nt-head');
      ntMake(head, 'h2', null, n.name);
      if (t) ntMake(head, 'span', 'nt-sub', ntT(`Intake target: {} (NNR 2023, ${n.sex === 'women' ? 'women' : 'men'} {})`, ntTarget(t), n.age));
      if (K.lab) {
        if (n.group) ntMake(head, 'span', 'nt-sub', n.group);
        lbPath(el, n, finds.filter((x) => x.nutrient === n.id), who);
      }

      // One variant per locus and marker pair; a variant found for two markers (omega-3 and DHA) is listed once
      const byRs = new Map();
      for (const f of finds.filter((x) => x.nutrient === n.id)) {
        const k = f.rsid + f.kind, o = byRs.get(k);
        if (!o) byRs.set(k, { ...f });
        else if (ntRank(f.grade) < ntRank(o.grade)) byRs.set(k, { ...f });
      }
      const mine = [...byRs.values()].sort((a, b) => (ntBad(a) === 'bad' ? 0 : 1) - (ntBad(b) === 'bad' ? 0 : 1) || ntRank(a.grade) - ntRank(b.grade) || Math.abs(b.shift || 0) - Math.abs(a.shift || 0));
      const st = steps.filter((s) => s.nutrient === n.id).sort((a, b) => a.pathway === b.pathway ? a.order - b.order : 0);
      // Pin each variant to the first step whose genes include its step gene
      const pinned = new Map();
      for (const f of mine) {
        if (!f.step_gene) continue;
        const s = st.find((x) => x.genes.split(' ').includes(f.step_gene));
        if (s) { if (!pinned.has(s.step)) pinned.set(s.step, []); pinned.get(s.step).push(f); }
      }
      const placed = new Set([...pinned.values()].flat());

      // Net effect on the blood level, one line per marker
      const markers = (ntJ(n.markers) || []).filter((m) => m.score);
      if (markers.length) {
        const box = ntMake(el, 'div', 'nt-block');
        ntMake(box, 'span', 'gx-label', K.measured ? 'Net effect on the measure' : 'Net effect on the blood level');
        for (const m of markers) {
          const d = ntMake(box, 'div', 'nt-marker');
          ntMake(d, 'b', null, m.name);
          ntBar(d, m);
          const s = ntSide(m);
          ntMake(d, 'b', s.bad ? 'nt-low' : s.good ? 'nt-high' : null, ntBand(m.score.percentile));
          ntMake(d, 'span', null, ' ');
          ntMake(d, 'span', null, ntPos(m.score.percentile, true));
          if (s.bad || s.good) { ntMake(d, 'span', null, ' '); ntMake(d, 'span', s.bad ? 'nt-low' : 'nt-high', s.bad ? 'The unfavourable direction.' : 'The favourable direction.'); }
          const src = m.source;
          ntMake(d, 'div', 'nt-src', [src.source, [src.author, src.year].filter(Boolean).join(' '), src.n ? `n = ${src.n.toLocaleString('en')}` : ''].filter(Boolean).join(' · ')).title = src.sample || src.method || '';
          // A genome-wide score: its method and the reference it is placed against
          if (src.kind === 'pgs_ref') ntMake(d, 'div', 'nt-src', ntT('{}, {} variants, placed by rank among {} Europeans in 1000 Genomes scored on the same variants',
            src.method, (src.variants || 0).toLocaleString('en'), src.reference));
          // What the score means in practice (fitness.json): below the 40th percentile it leans low, above the 60th high,
          // the same lines as the band words (Below average, Above average)
          const pc = m.score.percentile, mean = m.meaning && m.meaning[pc < 40 ? 'low' : pc > 60 ? 'high' : 'typical'];
          if (mean) { const w = ntMake(d, 'div', 'nt-mean'); ntMake(w, 'b', null, `What it means for ${who}:`); ntMake(w, 'span', null, ' '); ntMake(w, 'span', null, mean); }
        }
      }

      ntNotes(el, ntJ(n.notes) || [], finds.filter((x) => x.nutrient === n.id), who);
      // How the nutrient is taken up and converted, in Reactome's words
      const pws = ntJ(n.pathways) || [];
      if (pws.length) {
        const hb = ntMake(el, 'div', 'nt-block');
        ntMake(hb, 'span', 'gx-label', K.how);
        ntMake(hb, 'div', 'nt-sub', ntT(pws.length === 1 ? '{} steps found, in 1 pathway.' : '{} steps found, in {} pathways.', st.length, pws.length));
        const seen = new Set();
        for (const p of pws) {
          if (p.filtered) {
            // A broad pathway kept only for the steps that move this nutrient: those steps say more than its summary
            for (const x of st.filter((y) => y.pathway_id === p.id)) {
              const w = ntMake(hb, 'p', 'nt-why');
              ntMake(w, 'b', null, x.name + '. ');
              // Reactome opens related steps with the same sentences: show only what is new for each step
              const fresh = (x.summary || '').split(/(?<=[a-z0-9)\]]\.)\s+(?=[A-Z])/).filter((z) => !seen.has(z));
              fresh.forEach((z) => seen.add(z));
              if (fresh.length) ntQuote(w, fresh.join(' '), 200);
            }
            continue;
          }
          const w = ntMake(hb, 'p', 'nt-why');
          ntMake(w, 'b', null, p.name + '. ');
          ntQuote(w, p.summary);
        }
      }

      // Where the person's variants act: the step, the protein and what the variant changes, written out
      const prot = ntJ(n.proteins) || {};
      const pinnedList = mine.filter((f) => placed.has(f));
      if (pinnedList.length) {
        const wb = ntMake(el, 'div', 'nt-block');
        ntMake(wb, 'span', 'gx-label', `Where ${who}'s variants act`);
        // One account per gene: the step it does and what its protein is, then the person's variants in it
        const byGene = new Map();
        for (const f of pinnedList) { if (!byGene.has(f.step_gene)) byGene.set(f.step_gene, []); byGene.get(f.step_gene).push(f); }
        for (const [g, fs] of byGene) {
          const s = st.find((x) => x.genes.split(' ').includes(g));
          const ti = ((ntJ(s.tissues) || {})[g] || {}).tissues;
          const pr = prot[g];
          const box = ntMake(wb, 'div', 'nt-mech' + (fs.some((f) => ntBad(f) === 'bad') ? ' nt-mech-bad' : ''));
          ntMake(box, 'h4', null, g);
          ntChain(box, s, st, g, fs);
          // Read left to right: the step → the protein that does it → what the person's variants change in it
          const row = ntMake(box, 'div', 'nt-mech-row');
          const arrow = () => ntMake(row, 'div', 'nt-mech-arrow', '→').setAttribute('aria-hidden', 'true');
          const w1 = ntMake(ntMake(row, 'div', 'nt-mech-col'), 'p', 'nt-why');
          ntMake(w1, 'b', null, ntT('The step ({} of {}, {}): ', s.order, st.filter((x) => x.pathway === s.pathway).length, s.pathway));
          // The step's name is in the chain above; the text adds Reactome's account of it
          if (s.summary) ntQuote(w1, s.summary); else ntMake(w1, 'span', null, s.name + '.');
          if (pr) {
            arrow();
            const w2 = ntMake(ntMake(row, 'div', 'nt-mech-col'), 'p', 'nt-why');
            ntMake(w2, 'b', null, 'The protein: ');
            ntMake(w2, 'span', null, ti && ti.length ? ntT('{} makes {}, mostly in {}.', g, pr.protein, ti.slice(0, 3).join(', ')) : ntT('{} makes {}.', g, pr.protein));
            if (pr.function) { ntMake(w2, 'span', null, ' '); ntQuote(w2, pr.function, 200); }
          }
          arrow();
          const vc = ntMake(row, 'div', 'nt-mech-col nt-mech-vars');
          ntMake(vc, 'b', 'nt-why-head', ntT(fs.length === 1 ? `${who}'s variant:` : `${who}'s variants ({}):`, fs.length));
          for (const f of fs) ntVariant(vc, f, who);
        }
      }

      // Variants that move the level from outside these steps
      const out = mine.filter((f) => !placed.has(f));
      const ob = out.length ? ntMake(el, 'div', 'nt-block') : null;
      // Lab tests carry only the strongest of thousands of variants (export_dashboard.trim_findings): the true counts are
      // on the test row
      const total = Math.max(n.variants || 0, out.length);
      if (ob) ntMake(ob, 'span', 'gx-label', ntT(st.length ? (K.measured ? 'Outside these steps ({})' : 'Outside the conversion steps ({})') : 'Variants found ({})', total));
      if (ob && st.length) ntMake(ob, 'div', 'nt-sub', K.measured ? 'Genes that move the measure without being part of these steps: other pathways, or a gene whose role is not yet known.'
        : 'Genes that move the blood level without being part of these steps: transport in the blood, other pathways, or a gene not yet known.');
      // Lead with the variants whose copies move the person's level (or that they carry, ClinVar); the ones where they
      // have the usual copies come after, under Show all
      const moving = out.filter((f) => f.xy && f.xy !== 'typical'), quiet = out.filter((f) => !(f.xy && f.xy !== 'typical'));
      const nMoving = Math.max(n.moving || 0, moving.length);
      if (ob && total > out.length) ntMake(ob, 'div', 'nt-sub', ntT(`${who}'s copies move the level for {} of them. The {} strongest are listed.`, nMoving, out.length));
      else if (ob) ntMake(ob, 'div', 'nt-sub', ntT(nMoving === 1 ? `${who}'s copies move the level for 1 of them; the others are under Show all.`
        : `${who}'s copies move the level for {} of them; the others are under Show all.`, nMoving));
      // Both sides of the net score, side by side: the variants that work in the person's favour on the left, those
      // against them on the right (for a value where neither way is better: those that raise it, and those that lower it).
      // The headings carry the true counts; the score is the net of both columns.
      const directional = !!(n.moving_good || n.moving_bad);
      const against = moving.filter((f) => ntBad(f) === 'bad' || (ntBad(f) == null && f.xy === 'lowers'));
      const favour = moving.filter((f) => !against.includes(f));
      let shown = [];
      if (ob && moving.length) {
        ntMake(ob, 'div', 'nt-balance', 'The score above is the net of both columns, each variant weighted by its effect.');
        const cols = ntMake(ob, 'div', 'nt-sides');
        const per = all ? Infinity : 4;
        for (const [list, good, count] of [[favour, true, directional ? n.moving_good : n.moving_up], [against, false, directional ? n.moving_bad : n.moving_down]]) {
          const col = ntMake(cols, 'div', 'nt-side ' + (good ? 'nt-side-good' : 'nt-side-bad'));
          ntMake(col, 'span', 'gx-label', ntT(directional ? (good ? `In ${who}'s favour ({})` : `Against ${who} ({})`) : (good ? 'Raise it ({})' : 'Lower it ({})'),
            Math.max(count || 0, list.length)));
          const take = list.slice(0, per);
          if (!take.length) ntMake(col, 'div', 'nt-sub', 'None among the listed variants.');
          for (const f of take) ntVariant(col, f, who);
          shown = shown.concat(take);
        }
      }
      if (all) { for (const f of quiet) ntVariant(ob, f, who); shown = shown.concat(quiet); }
      if (out.length > shown.length || all) {
        const b = ntMake(ob, 'button', 'md-pill', all ? 'Show fewer' : `Show all (${out.length - shown.length} more)`);
        b.type = 'button';
        b.addEventListener('click', () => { all = !all; dash.setParams({ [K.param + '_all']: all }); });
      }

      if (n.test) {
        const tb = ntMake(el, 'div', 'nt-block nt-sub');
        ntMake(tb, 'span', null, K.measured ? `Measured with: ${n.test}` : `Blood test: ${n.test}`);
      }
    });
  };
  ntTab({ over: 'nt-overview', detail: 'nt-detail', card: 'nt-detail', main: 'nut_nutrients', finds: 'nut_findings', steps: 'nut_steps',
    param: 'nt_n', title: (who) => `${who} and nutrition`, how: 'How it is taken up and converted (Reactome)',
    low: (who) => `${who}'s genes lower these nutrients' blood levels the unfavourable way. Select one to see where in its uptake and conversion the genes act:` });
  ntTab({ over: 'lb-overview', detail: 'lb-detail', card: 'lb-detail', main: 'lab_tests', finds: 'lab_findings', steps: 'lab_steps',
    param: 'lb_n', lab: true, title: (who) => `${who}'s lab tests`, how: 'How it is made and regulated (Reactome)',
    low: (who) => `${who}'s genes move these lab values the unfavourable way. Select one to see which genes act and how:` });
  ntTab({ over: 'fit-overview', detail: 'fit-detail', card: 'fit-detail', main: 'fit_tests', finds: 'fit_findings', steps: 'fit_steps',
    param: 'fit_n', title: (who) => `${who}'s strength and fitness scores`, how: 'How it works in the body (Reactome)', measured: true,
    only: () => (gx.theme ? gx.theme() : dash.params().theme) === 'muscle',
    low: (who) => `${who}'s genes set these the unfavourable way. Select one to see which genes act and how:` });
  // Cancer risk: one polygenic score per cancer (cancers.json), in the Clusters page under the cancer theme
  ntTab({ over: 'can-overview', detail: 'can-detail', card: 'can-detail', main: 'can_tests', finds: 'can_findings', steps: 'can_steps',
    param: 'can_n', title: (who) => `${who}'s genetic risk per cancer`, how: 'How it works in the body (Reactome)', measured: true,
    only: () => (gx.theme ? gx.theme() : dash.params().theme) === 'cancer',
    low: (who) => `${who}'s genes raise the risk of these cancers above most Europeans. Select one to see the variants behind the score:` });
