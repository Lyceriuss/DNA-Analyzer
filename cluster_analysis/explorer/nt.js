  // Nutrition: per nutrient, where the person's genes put its blood level among Europeans, the intake to aim for (NNR 2023),
  // the richest foods (Livsmedelsverket), the blood test, and every finding with an evidence grade.
  // Every text node is one whole template, so the Swedish layer (i18n.js) can swap it. The dashboard runs each script in
  // its own scope, so the helpers it shares with md.js are its own copies here.
  const NT_GRADES = ['A+', 'A', 'B', 'C'];
  const NT_GRADE_NOTE = { 'A+': 'expert-reviewed (ClinVar 3–4 stars)', A: 'replicated, or ClinVar 2 stars', B: 'one publication, or ClinVar 1 star', C: 'a single study (ClinPGx)' };
  const ntMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const ntWho = (rows) => (rows.find((r) => r.person) || {}).person || 'XY';
  const ntRank = (g) => { const i = NT_GRADES.indexOf(g); return i < 0 ? NT_GRADES.length : i; };
  const ntTag = (parent, g) => {
    const t = ntMake(parent, 'span', 'md-grade md-grade-' + (g === 'A+' ? 'ap' : String(g).toLowerCase()), g);
    t.title = `Evidence grade ${g}: ${NT_GRADE_NOTE[g] || ''}`;
    return t;
  };
  const ntJ = (s) => { try { return s ? JSON.parse(s) : null; } catch (e) { return null; } };
  const ntNum = (v) => (v >= 100 ? Math.round(v) : +Number(v).toPrecision(3)).toLocaleString('en');
  const ntUnit = (u) => (u || '').replace('RE/µg', 'µg RE');
  const ntLink = (parent, text, href) => { const a = ntMake(parent, 'a', 'nt-src', text); a.href = href; a.target = '_blank'; a.rel = 'noopener'; return a; };
  let ntAll = false;
  // The first scored marker, and whether its level is on the unfavourable side, the favourable one or neither
  const ntMain = (n) => (ntJ(n.markers) || []).find((m) => m.score);
  const ntSide = (m) => {
    const p = m.score.percentile, side = p <= 20 ? 'low' : p >= 80 ? 'high' : 'typical';
    const bad = side !== 'typical' && m.higher !== 'neutral' && (side === 'low') === (m.higher === 'better');
    return { side, bad, good: side !== 'typical' && m.higher !== 'neutral' && !bad };
  };
  const ntLow = (rows) => rows.filter((n) => (ntJ(n.markers) || []).some((m) => m.score && ntSide(m).bad));
  const ntBar = (parent, m) => {
    const b = ntMake(parent, 'div', 'nt-bar' + (m.higher === 'worse' ? ' nt-flip' : m.higher === 'neutral' ? ' nt-even' : ''));
    const p = m.score.percentile;
    ntMake(b, 'i').style.left = (m.higher === 'worse' ? 100 - p : p) + '%';
    b.title = `Genetic level: higher than ${p}% of Europeans`;
  };
  const ntTarget = (t, short) => !t ? '' : t.min_e == null ? `${t.kind} ${ntNum(t.value)} ${ntUnit(t.unit)} a day`
    : short ? `At least ${ntNum(t.value)} g omega-3 a day`
      : `At least ${ntNum(t.value)} g omega-3 a day (${t.min_e}% of energy at ${t.energy_mj} MJ), ${ntNum(t.ala)} g of it ALA`;
  const ntRead = (who, s) => s.side === 'typical' ? `${who}'s genes point to a typical level.`
    : `${who}'s genes point to a ${s.side === 'low' ? 'lower' : 'higher'} level than most` +
      (s.bad ? ', the unfavourable direction.' : s.good ? ', the favourable direction.' : '.');
  const ntPick = (n) => { ntAll = false; dash.setParams({ nt_n: n.id }); };

  dash.draw('nt-overview', (el) => {
    const r = gx.rows('nut_nutrients');
    if (!r) { if (gx.failed('nut_nutrients')) gx.failLine(el); return; }
    const [rows] = r;
    el.replaceChildren();
    const who = ntWho(rows), low = ntLow(rows), cur = dash.params().nt_n || (low[0] || rows[0]).id;
    ntMake(el, 'h3', null, `${who} and nutrition`);
    if (low.length) {
      ntMake(el, 'p', null, `${who}'s genes point to the unfavourable side for these nutrients. Reach their intake target every day, and check them with a blood test:`);
      const pills = ntMake(el, 'div', 'md-pills');
      for (const n of low) { const b = ntMake(pills, 'button', 'md-pill', n.name); b.type = 'button'; b.addEventListener('click', () => ntPick(n)); }
    } else ntMake(el, 'p', null, `${who}'s genes point to typical levels throughout.`);
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
        ntMake(b, 'small', s.bad ? 'nt-low' : s.good ? 'nt-high' : null, `Percentile ${m.score.percentile}`);
      } else ntMake(b, 'small', null, 'No genetic score');
      ntMake(b, 'small', null, ntTarget(ntJ(n.target), true));
      b.addEventListener('click', () => { ntPick(n); document.getElementById('nt-detail').scrollIntoView({ behavior: 'smooth' }); });
    }
  });

  dash.draw('nt-detail', (el) => {
    const r = gx.rows('nut_nutrients', 'nut_findings', 'nut_genes', 'nut_foods');
    if (!r) { if (gx.failed('nut_nutrients', 'nut_findings', 'nut_genes', 'nut_foods')) gx.failLine(el); return; }
    const [rows, finds, genes, foods] = r;
    el.replaceChildren();
    const who = ntWho(rows);
    const n = rows.find((x) => x.id === dash.params().nt_n) || ntLow(rows)[0] || rows[0];
    const t = ntJ(n.target);
    const head = ntMake(el, 'div', 'nt-head');
    ntMake(head, 'h2', null, n.name);
    if (t) ntMake(head, 'span', 'nt-target', ntTarget(t));
    if (t && t.ul) ntMake(head, 'span', 'nt-sub', (t.ul.applies_to_food ? 'Upper limit {}' : 'Upper limit {} (supplements only)').replace('{}', `${ntNum(t.ul.value)} ${t.ul.unit}`));
    ntMake(el, 'div', 'nt-src', `Nordic Nutrition Recommendations 2023 (Livsmedelsverket), ${n.sex === 'women' ? 'women' : 'men'} ${n.age}.`);
    for (const note of (t && t.notes) || []) ntMake(el, 'div', 'nt-sub', note.text);

    // Genetic level per marker
    const markers = ntJ(n.markers) || [];
    if (markers.length) {
      const box = ntMake(el, 'div', 'nt-block');
      ntMake(box, 'span', 'gx-label', 'Genetic level');
      for (const m of markers) {
        const d = ntMake(box, 'div', 'nt-marker');
        ntMake(d, 'b', null, m.name);
        if (!m.score) { ntMake(d, 'div', 'nt-sub', `No study large enough for a score (${m.studies} publications); the findings below still apply.`); continue; }
        ntBar(d, m);
        const read = ntMake(d, 'div', 'nt-read');
        ntMake(read, 'span', null, `Higher than ${m.score.percentile}% of Europeans.`);
        ntMake(read, 'span', null, ' ');
        ntMake(read, 'span', null, ntRead(who, ntSide(m)));
        const src = m.source, line = ntMake(d, 'div', 'nt-src');
        line.title = src.sample || src.method || '';
        ntMake(line, 'span', null, [src.source, [src.author, src.year].filter(Boolean).join(' '), src.n ? `n = ${src.n.toLocaleString('en')}` : ''].filter(Boolean).join(' · ') + ' · ');
        ntMake(line, 'span', null, `${m.score.used} of ${m.score.variants} variants read`);
        const dr = ntMake(d, 'div', 'nt-drivers');
        for (const x of m.score.top.slice(0, 6)) {
          const up = (x.shift > 0) === (m.higher !== 'worse');
          ntMake(dr, 'span', m.higher === 'neutral' ? null : up ? 'nt-up' : 'nt-down',
            `${x.gene || x.rsid} ${x.copies}×${x.allele} ${x.shift > 0 ? '▲' : '▼'}${Math.abs(x.shift)}`).title =
            (x.raises ? `{}: ${who} has {} of the raising allele {} ({}% of Europeans' alleles); moves the score {} standard deviations`
              : `{}: ${who} has {} of the lowering allele {} ({}% of Europeans' alleles); moves the score {} standard deviations`)
              .replace('{}', x.rsid).replace('{}', x.copies).replace('{}', x.allele).replace('{}', Math.round(x.freq * 100)).replace('{}', x.shift);
        }
      }
    }

    // Foods
    const fl = foods.filter((f) => f.nutrient === n.id);
    const fb = ntMake(el, 'div', 'nt-block');
    ntMake(fb, 'span', 'gx-label', 'Richest foods');
    if (!fl.length) ntMake(fb, 'p', 'nt-sub', "Livsmedelsverket's food database has no values for this nutrient.");
    else {
      const tb = ntMake(ntMake(fb, 'div', 'gx-table-box'), 'table', 'gx-table nt-foods');
      const hr = ntMake(ntMake(tb, 'thead'), 'tr');
      for (const h of ['Food', n.id === 'omega_3' ? 'EPA + DHA per 100 g' : 'Per 100 g', 'Of the target', 'kcal']) ntMake(hr, 'th', null, h);
      const body = ntMake(tb, 'tbody');
      for (const f of fl) {
        const tr = ntMake(body, 'tr');
        const td = ntMake(tr, 'td', null, f.food);
        td.title = [f.food_en, f.group, ...Object.entries(ntJ(f.extra) || {}).map(([k, v]) => `${k}: ${v}`)].filter(Boolean).join(' · ');
        if (f.over_ul) ntMake(td, 'span', 'nt-ul', 'Over the upper limit').title = '100 g holds more than the upper intake level: an occasional food, not a daily one';
        ntMake(tr, 'td', null, `${ntNum(f.amount)} ${ntUnit(f.unit)}`);
        ntMake(tr, 'td', null, f.share != null ? `${f.share}%` : '');
        ntMake(tr, 'td', null, f.kcal != null ? String(Math.round(f.kcal)) : '');
      }
      ntMake(fb, 'div', 'nt-src', 'Livsmedelsverket, Livsmedelsdatabasen (CC BY 4.0). Mixed dishes, sweets, spices and supplements are left out.');
    }

    if (n.test) {
      const tb = ntMake(el, 'div', 'nt-block nt-test');
      ntMake(tb, 'b', null, `Blood test: ${n.test}`);
      ntMake(tb, 'div', 'nt-sub', 'Genes tilt the level; the test shows where it actually is.');
    }

    // Findings, strongest evidence first; a variant found for two markers (omega-3 and DHA) is listed once, naming both
    const byRs = new Map();
    for (const f of finds.filter((x) => x.nutrient === n.id)) {
      const k = f.rsid + (f.allele || '') + f.kind, o = byRs.get(k);
      if (!o) byRs.set(k, { ...f, markers: f.marker_name ? [f.marker_name] : [] });
      else if (f.marker_name && !o.markers.includes(f.marker_name)) {
        o.markers.push(f.marker_name);
        if (ntRank(f.grade) < ntRank(o.grade)) o.grade = f.grade;
      }
    }
    const mine = [...byRs.values()].sort((a, b) => ntRank(a.grade) - ntRank(b.grade) || (b.copies || 0) - (a.copies || 0) || (b.beta || 0) - (a.beta || 0));
    const fx = ntMake(el, 'div', 'nt-block');
    ntMake(fx, 'span', 'gx-label', `Findings (${mine.length})`);
    for (const f of ntAll ? mine : mine.slice(0, 12)) {
      const d = ntMake(fx, 'div', 'nt-find');
      ntTag(d, f.grade);
      const top = ntMake(d, 'div');
      ntMake(top, 'span', null, `${f.gene || ''} ${f.rsid} · ${who}: ${f.genotype || '–'}`);
      if (f.confidence === 'high') ntMake(top, 'span', 'th-imp th-imp-high', 'imputed, high confidence');
      if (f.kind === 'GWAS') {
        const e = ntMake(d, 'div');
        for (const name of f.markers) ntMake(e, 'div', null, (f.direction === 'raises' ? '{} raises: {}' : '{} lowers: {}').replace('{}', f.allele).replace('{}', name));
        if (f.copies != null) ntMake(e, 'div', 'nt-sub', (f.copies === 1 ? `${who} has 1 copy` : `${who} has {} copies`).replace('{}', f.copies));
        const p = f.p ? f.p.toExponential(0) : '< 1e-300';
        ntLink(d, (f.publications === 1 ? '{} · 1 publication · p {}' : f.against ? '{} · {} publications ({} disagree) · p {}' : '{} · {} publications · p {}')
          .replace('{}', f.study).replace('{}', f.publications === 1 ? p : f.publications).replace('{}', f.against || p).replace('{}', p), `https://pubmed.ncbi.nlm.nih.gov/${f.pmid}/`);
      } else {
        ntMake(d, 'div', null, f.kind === 'ClinVar' ? `ClinVar: ${f.text} (${f.copies}×${f.allele})` : `${f.chemical}: ${f.effect || f.text || '–'}`);
        if (f.url) ntLink(d, 'ClinPGx', f.url);
      }
    }
    if (mine.length > 12) {
      const b = ntMake(fx, 'button', 'md-pill', ntAll ? 'Show fewer' : `Show all (${mine.length - 12} more)`);
      b.type = 'button';
      b.addEventListener('click', () => { ntAll = !ntAll; dash.setParams({ nt_all: ntAll }); });
    }

    // Genes of the nutrient's Reactome pathways; the ones with findings stand out
    const gl = genes.filter((g) => g.nutrient === n.id);
    if (gl.length) {
      const gb = ntMake(el, 'div', 'nt-block');
      ntMake(gb, 'span', 'gx-label', 'Pathway genes (Reactome)');
      for (const p of [...new Set(gl.map((g) => g.pathway))]) {
        ntMake(gb, 'div', 'nt-sub', p);
        const c = ntMake(gb, 'div', 'nt-genes');
        for (const g of gl.filter((x) => x.pathway === p)) {
          const s = ntMake(c, 'span', 'nt-gene' + (g.findings ? ' nt-hit' : ''), g.gene);
          if (g.findings) s.title = `${g.findings} findings, best grade ${g.best}`;
        }
      }
    }
  });
