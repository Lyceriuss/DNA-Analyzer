  // Medicines: drug genes (star alleles and CPIC types), and per medicine its dosing guidance and every ClinPGx finding,
  // each with an evidence grade (A+ guideline-grade ... C a single study or mixed results). Nothing is filtered out by grade.
  const MD_GRADES = ['A+', 'A', 'B', 'C'];
  const MD_GRADE_NOTE = { 'A+': 'guideline-grade', A: 'strong evidence', B: 'moderate evidence', C: 'one study or mixed results' };
  const MD_STATUS = { typical: 'Typical response', differs: 'Differs from typical', not_excluded: 'Not detected, not excluded', unclear: 'Unclear' };
  const MD_RANK = { differs: 0, not_excluded: 1, unclear: 2, typical: 3 };
  const MD_GUIDE_STATUS = { differs: 'differs', no_action: 'typical', typical: 'typical', unclear: 'unclear' };
  const MD_CATS = ['Dosage', 'Efficacy', 'Toxicity', 'Metabolism/PK'];
  const mdMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const mdParams = () => {
    const p = dash.params();
    return { q: p.md_q || '', cat: p.md_cat || 'all', diff: p.md_diff === true || p.md_diff === 'true', gene: p.md_gene || '',
      open: new Set(String(p.md_open || '').split('|').filter(Boolean)) };
  };
  const mdWho = (rows) => (rows.find((r) => r.person) || {}).person || gx.who();
  let mdShown = 40;
  const mdSet = (p) => { mdShown = 40; dash.setParams(p); };
  const mdGradeRank = (g) => { const i = MD_GRADES.indexOf(g); return i < 0 ? MD_GRADES.length : i; };
  const mdTag = (parent, g) => {
    const t = mdMake(parent, 'span', 'md-grade md-grade-' + (g === 'A+' ? 'ap' : String(g).toLowerCase()), g);
    t.title = `Evidence grade ${g}: ${MD_GRADE_NOTE[g] || ''}`;
    return t;
  };
  const mdCompounds = (drug) => drug.split(';').map((x) => x.trim().toLowerCase()).filter(Boolean);

  // Every name a medicine goes by (international and trade names, ATC codes), for search
  let mdNameCache = { rows: null, map: new Map() };
  const mdNames = (rows) => {
    if (mdNameCache.rows !== rows) {
      mdNameCache = { rows, map: new Map(rows.map((r) => [r.drug, { ...r, hay: [r.drug, r.aka, r.classes, r.generic, r.trade, r.atc].join('; ').toLowerCase() }])) };
    }
    return mdNameCache.map;
  };
  // The name the search found a medicine by, when it isn't the ClinPGx name
  const mdFoundAs = (n, q) => {
    if (!q || !n || n.drug.includes(q)) return null;
    for (const field of ['aka', 'generic', 'trade', 'atc', 'classes']) {
      const x = (n[field] || '').split('; ').find((v) => v.toLowerCase().includes(q));
      if (x) return x;
    }
    return null;
  };

  // One entry per medicine (compound or drug class): its guidance and findings, the most notable first
  const mdGroups = (drugs, guidance, names, f) => {
    const q = f.q.trim().toLowerCase();
    const named = (c) => !q || c.includes(q) || (names.get(c) || { hay: '' }).hay.includes(q);
    const by = new Map();
    const group = (c) => { if (!by.has(c)) by.set(c, { drug: c, anns: [], guides: [] }); return by.get(c); };
    for (const d of drugs) {
      if (f.cat !== 'all' && !d.category.split(';').includes(f.cat)) continue;
      if (f.gene && d.gene.split(';')[0] !== f.gene) continue;
      const other = q && (d.gene.toLowerCase().includes(q) || (d.condition || '').toLowerCase().includes(q));
      for (const c of mdCompounds(d.drug)) if (other || named(c)) group(c).anns.push(d);
    }
    for (const g of guidance) {
      if (f.gene && !g.genes.split(';').includes(f.gene)) continue;
      const other = q && g.genes.toLowerCase().includes(q);
      for (const c of mdCompounds(g.drug)) {
        if (!(other || named(c))) continue;
        if (f.cat !== 'all' && !by.has(c)) continue;  // a kind-of-effect filter lists medicines with findings of that kind
        group(c).guides.push(g);
      }
    }
    const groups = [...by.values()].map((g) => {
      g.anns.sort((a, b) => MD_RANK[a.status] - MD_RANK[b.status] || mdGradeRank(a.grade) - mdGradeRank(b.grade));
      const readable = g.guides.filter((x) => x.status !== 'unreadable');
      readable.sort((a, b) => (a.kind === 'guideline' ? 0 : 1) - (b.kind === 'guideline' ? 0 : 1) ||
        (MD_RANK[MD_GUIDE_STATUS[a.status]] ?? 4) - (MD_RANK[MD_GUIDE_STATUS[b.status]] ?? 4) || mdGradeRank(a.grade) - mdGradeRank(b.grade));
      // The medicine's status comes from its strongest evidence; weaker findings that differ are noted beside it
      const items = [...g.anns.map((a) => [a.status, a.grade]), ...readable.map((x) => [MD_GUIDE_STATUS[x.status], x.grade]).filter((x) => x[0])];
      const best = Math.min(...items.map((x) => mdGradeRank(x[1])), MD_GRADES.length);
      const worst = (xs) => xs.map((x) => x[0]).sort((a, b) => MD_RANK[a] - MD_RANK[b])[0];
      const status = worst(items.filter((x) => mdGradeRank(x[1]) === best)) || 'unclear';
      const weaker = status !== 'differs' && items.filter((x) => x[0] === 'differs').map((x) => x[1]).sort((a, b) => mdGradeRank(a) - mdGradeRank(b))[0];
      return { ...g, readable, unreadable: g.guides.length - readable.length, status, weaker, best, foundAs: mdFoundAs(names.get(g.drug), q) };
    }).filter((g) => (g.anns.length || g.readable.length) && (!f.diff || g.status === 'differs' || g.weaker));
    return groups.sort((a, b) => MD_RANK[a.status] - MD_RANK[b.status] || a.best - b.best || !a.weaker - !b.weaker || a.drug.localeCompare(b.drug));
  };

  dash.draw('md-summary', (el) => {
    const r = gx.rows('med_genes', 'med_drugs');
    if (!r) { if (gx.failed('med_genes', 'med_drugs')) gx.failLine(el); return; }
    const [genes, drugs] = r;
    el.replaceChildren();
    const who = mdWho(genes);
    const guide = drugs.filter((d) => d.grade === 'A+' || d.grade === 'A');
    const differs = [...new Set(guide.filter((d) => d.status === 'differs').flatMap((d) => mdCompounds(d.drug)))].sort();
    const all = new Set(guide.flatMap((d) => mdCompounds(d.drug)));
    const odd = genes.filter((g) => g.alleles && !g.typical);
    mdMake(el, 'h3', null, `${who} and medicines`);
    mdMake(el, 'p', null, `Grade A+ and A evidence covers ${all.size} medicines. For ${differs.length} of them ${who} ` +
      `differs from the typical case; for the rest ${who} is expected to respond as most people do. ` +
      (odd.length ? `The drug genes behind most of the differences: ${odd.map((g) => `${g.gene} ${g.alleles} (${g.phenotype.split(' (')[0].toLowerCase()})`).join(', ')}.` : ''));
    mdMake(el, 'span', 'gx-label', `Medicines with grade A+ or A evidence where ${who} differs`);
    const pills = mdMake(el, 'div', 'md-pills');
    for (const drug of differs) {
      const b = mdMake(pills, 'button', 'md-pill', drug);
      b.type = 'button';
      b.addEventListener('click', () => { mdSet({ md_q: drug, md_cat: 'all', md_gene: '' }); document.getElementById('med-drugs').scrollIntoView({ behavior: 'smooth' }); });
    }
  });

  dash.draw('md-genes', (el) => {
    const r = gx.rows('med_genes', 'med_drugs');
    if (!r) { if (gx.failed('med_genes', 'med_drugs')) gx.failLine(el); return; }
    const [genes, drugs] = r;
    const f = mdParams();
    el.replaceChildren();
    for (const g of genes) {
      const b = mdMake(el, 'button', 'md-gene ' + (!g.alleles ? 'md-none' : g.typical ? 'md-typical' : 'md-differs'));
      b.type = 'button';
      b.setAttribute('aria-pressed', String(f.gene === g.gene));
      const head = mdMake(b, 'span');
      mdMake(head, 'span', 'md-gene-name', g.gene);
      if (g.alleles) mdMake(head, 'span', 'md-gene-alleles', g.alleles);
      mdMake(b, 'span', 'md-gene-type', g.phenotype + (g.imputed ? ' · partly imputed' : ''));
      const names = [...new Set(drugs.filter((d) => d.gene.split(';')[0] === g.gene && (d.grade === 'A+' || d.grade === 'A')).flatMap((d) => mdCompounds(d.drug)))];
      if (names.length) mdMake(b, 'span', 'md-gene-drugs', names.slice(0, 6).join(', ') + (names.length > 6 ? ` +${names.length - 6}` : ''));
      const snps = JSON.parse(g.snps || '[]');
      b.title = [g.note, ...snps.map((s) => `${s.allele} ${s.rsid}: ${s.genotype} (${s.copies} ${s.copies === 1 ? 'copy' : 'copies'} of ${s.variant}; ${s.confidence})`)]
        .filter(Boolean).join('\n');
      b.addEventListener('click', () => mdSet({ md_gene: f.gene === g.gene ? '' : g.gene, md_q: '' }));
    }
  });

  // Suggestions while typing: medicines, their international and brand names, and drug classes
  const MD_KIND = { medicine: 'medicine', aka: 'international name', brand: 'brand', class: 'class' };
  const MD_KIND_RANK = { medicine: 0, aka: 1, class: 2, brand: 3 };
  const mdSuggestIndex = (drugs, guidance, names) => {
    const out = [], seen = new Set();
    const add = (label, kind, drug) => {
      const k = kind + '|' + label.toLowerCase() + '|' + drug;
      if (label && !seen.has(k)) { seen.add(k); out.push({ label, low: label.toLowerCase(), kind, drug }); }
    };
    for (const row of [...drugs, ...guidance]) for (const c of mdCompounds(row.drug)) add(c, 'medicine', c);
    for (const n of names) {
      for (const x of (n.aka || '').split('; ')) add(x, 'aka', n.drug);
      for (const x of (n.classes || '').split('; ')) add(x, 'class', x);
      for (const x of (n.trade || '').split('; ')) if (x.length <= 40) add(x, 'brand', n.drug);
    }
    return out;
  };
  const mdSuggest = (index, q) => {
    q = q.trim().toLowerCase();
    if (q.length < 2) return [];
    const scored = [];
    for (const e of index) {
      const at = e.low.indexOf(q);
      if (at < 0) continue;
      const word = at === 0 ? 0 : /[\s(\-/]/.test(e.low[at - 1]) ? 1 : 2;
      scored.push([word, MD_KIND_RANK[e.kind], e.low.length, e]);
    }
    scored.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
    const out = [], seen = new Set();
    for (const [, , , e] of scored) {
      if (seen.has(e.low + '|' + e.drug)) continue;
      seen.add(e.low + '|' + e.drug);
      out.push(e);
      if (out.length >= 8) break;
    }
    return out;
  };

  dash.draw('md-controls', (el) => {
    const r = gx.rows('med_drugs');
    if (!r) return;
    const f = mdParams();
    const all = gx.rows('med_drugs', 'med_guidance', 'med_names');
    if (all && el._md && !el._md.index) el._md.index = mdSuggestIndex(...all);
    if (!el.dataset.built) {
      el.dataset.built = '1';
      const wrap = mdMake(el, 'div', 'md-search-wrap');
      const icon = mdMake(wrap, 'span', 'md-search-icon');
      icon.setAttribute('aria-hidden', 'true');
      icon.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>';
      const q = mdMake(wrap, 'input', 'md-search');
      const list = mdMake(wrap, 'ul', 'md-suggest');
      list.id = 'md-suggest'; list.hidden = true; list.setAttribute('role', 'listbox');
      q.setAttribute('role', 'combobox'); q.setAttribute('aria-controls', 'md-suggest'); q.setAttribute('aria-expanded', 'false');
      q.setAttribute('autocomplete', 'off');
      let items = [], active = -1, t;
      const close = () => { list.hidden = true; q.setAttribute('aria-expanded', 'false'); active = -1; };
      const pick = (e) => { q.value = e.label; close(); clearTimeout(t); mdSet({ md_q: e.label, md_open: '' }); };
      const show = () => {
        items = el._md && el._md.index ? mdSuggest(el._md.index, q.value) : [];
        list.replaceChildren();
        if (!items.length || (items.length === 1 && items[0].low === q.value.trim().toLowerCase())) { close(); return; }
        items.forEach((e, i) => {
          const li = mdMake(list, 'li', 'md-suggest-item' + (i === active ? ' md-active' : ''));
          li.setAttribute('role', 'option'); li.setAttribute('aria-selected', String(i === active));
          mdMake(li, 'span', 'md-suggest-name', e.label);
          mdMake(li, 'span', 'md-suggest-kind', MD_KIND[e.kind]);
          if (e.kind === 'aka' || e.kind === 'brand') mdMake(li, 'span', 'md-suggest-drug', `→ ${e.drug}`);
          li.addEventListener('mousedown', (ev) => { ev.preventDefault(); pick(e); });
        });
        list.hidden = false; q.setAttribute('aria-expanded', 'true');
      };
      q.addEventListener('keydown', (ev) => {
        if (list.hidden || !items.length) return;
        if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') { ev.preventDefault(); active = (active + (ev.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length; show(); }
        else if (ev.key === 'Enter' && active >= 0) { ev.preventDefault(); pick(items[active]); }
        else if (ev.key === 'Escape') close();
      });
      q.addEventListener('blur', close);
      q.addEventListener('focus', show);
      q.addEventListener('input', () => { active = -1; show(); clearTimeout(t); t = setTimeout(() => mdSet({ md_q: q.value, md_open: '' }), 250); });
      q.type = 'search'; q.placeholder = 'Search a medicine by any name, brand or ATC code, or a gene or condition';
      q.setAttribute('aria-label', 'Search medicines');
      const cat = mdMake(el, 'select', 'md-select'); cat.setAttribute('aria-label', 'Kind of effect');
      for (const [v, label] of [['all', 'Every kind of effect'], ...MD_CATS.map((c) => [c, c === 'Metabolism/PK' ? 'Metabolism' : c])]) {
        const o = mdMake(cat, 'option', null, label); o.value = v;
      }
      cat.addEventListener('change', () => mdSet({ md_cat: cat.value }));
      mdMake(el, 'div', 'md-break');  // the other options go on the row below
      const lab = mdMake(el, 'label', 'md-check');
      const cb = mdMake(lab, 'input'); cb.type = 'checkbox';
      lab.append(`Only where ${mdWho(r[0])} differs`);
      cb.addEventListener('change', () => mdSet({ md_diff: cb.checked }));
      const legend = mdMake(el, 'div', 'md-legend');
      mdMake(legend, 'span', null, 'Evidence grade:');
      for (const g of MD_GRADES) { const s = mdMake(legend, 'span', 'md-legend-item'); mdTag(s, g); s.append(MD_GRADE_NOTE[g]); }
      el._md = { q, cat, cb, index: all ? mdSuggestIndex(...all) : null };
    }
    const c = el._md;
    if (document.activeElement !== c.q) c.q.value = f.q;
    c.cat.value = f.cat; c.cb.checked = f.diff;
  });

  // The dose a recommendation states, as one highlighted line: standard (with the amount when it is a plain amount),
  // adjusted (the phrase the guideline uses), or an alternative medicine first
  const mdDose = (parent, dose) => {
    if (!dose) return;
    const amount = dose.dose && /^[≤≥<>]?\s*\d/.test(dose.dose);
    const text = dose.kind === 'avoid' ? 'Use an alternative medicine first'
      : dose.kind === 'adjusted' ? `Adjusted dose: ${dose.dose}`
      : amount ? `Standard dose: ${dose.dose}` : 'Standard dose';
    mdMake(parent, 'div', 'md-dose md-dose-' + dose.kind, text);
  };

  // The studies behind a finding: how many, how many people or samples, the smallest p-value and the reported ratio
  const MD_RATIO = { OR: 'odds ratio', HR: 'hazard ratio', RR: 'relative risk' };
  const mdStudies = (parent, raw) => {
    const st = raw && raw !== 'null' ? JSON.parse(raw) : null;
    if (!st || !st.studies) return;
    const parts = [st.studies === 1 ? '1 study' : `${st.studies} studies`];
    if (st.n) parts.push(`n = ${st.n.toLocaleString('en')}`);
    if (st.p) parts.push(`p ${st.p}`);
    const r = (st.ratios || [])[0];
    if (r) parts.push(`${r.type} ${r.value}` + (r.lo != null && r.hi != null ? ` (95% CI ${r.lo}–${r.hi})` : ''));
    const line = mdMake(parent, 'div', 'md-study', parts.join(' · '));
    line.title = ['n: people or samples studied, summed over the studies (the largest analysis of each).',
      'p: the smallest p-value reported; below 0.05 is the usual bar, and one small study can pass it by chance.',
      ...(st.ratios || []).map((x) => `${x.type} (${MD_RATIO[x.type]}) ${x.value}` + (x.lo != null ? ` [${x.lo}–${x.hi}]` : '') +
        (x.n ? `, n = ${x.n}` : '') + (x.pmid ? `, PMID ${x.pmid}` : '')),
      (st.ratios || []).length ? '1 means no difference; below 1 the outcome is less likely, above 1 more likely, for the genotype the study names.' : '']
      .filter(Boolean).join('\n');
  };

  // One guideline or drug label: what it recommends for the person's type
  const mdGuide = (box, x, who) => {
    const d = mdMake(box, 'div', 'md-ann md-guide md-' + (MD_GUIDE_STATUS[x.status] || 'unclear'));
    const meta = mdMake(d, 'div', 'md-ann-meta');
    mdTag(meta, x.grade);
    mdMake(meta, 'span', 'md-level', x.kind === 'guideline' ? `${x.source} guideline` : `${x.source} drug label`);
    if (x.kind === 'label' && x.testing) mdMake(meta, 'span', null, x.testing);
    if (x.types) mdMake(meta, 'span', 'md-gt', x.types);
    const recs = JSON.parse(x.recs || '[]');
    if (recs.length) {
      for (const rec of recs) {
        mdDose(d, rec.dose);
        const p = mdMake(d, 'div', 'md-rec');
        if (rec.population) mdMake(p, 'span', 'md-rec-for', rec.population.trim() + ': ');
        p.append(rec.recommendation + (rec.strength ? ` (${rec.strength.toLowerCase()} recommendation)` : ''));
        if (rec.implication) mdMake(d, 'div', 'md-rec-why', rec.implication);
      }
    } else if (x.kind === 'guideline' && x.summary) {
      mdMake(d, 'div', null, x.summary);
    } else if (x.kind === 'label') {
      mdMake(d, 'div', null, x.status === 'differs' ? `${who}'s type differs from the typical one, and the label has advice for it: open it for the dose.`
        : `${who} has the typical type for the genes this label names, so its standard dose applies.`);
    }
    const link = mdMake(mdMake(d, 'div', 'md-src'), 'a', null, 'ClinPGx');
    link.href = x.url; link.target = '_blank'; link.rel = 'noopener';
  };

  // One ClinPGx or ClinVar finding: the person's genotype and what it means, the other genotypes, the medicines it names
  const MD_COPIES = ['no copy', 'one copy', 'two copies'];
  const mdFinding = (box, a, who, here) => {
    const d = mdMake(box, 'div', 'md-ann md-' + a.status);
    const meta = mdMake(d, 'div', 'md-ann-meta');
    mdTag(meta, a.grade);
    mdMake(meta, 'span', null, `${a.gene} · ${a.category.replace(/;/g, ', ').replace('Metabolism/PK', 'metabolism').toLowerCase()}`);
    if (a.confidence === 'high') mdMake(meta, 'span', 'th-imp th-imp-high', 'imputed, high confidence');
    mdStudies(d, a.studies);
    const snp = !a.genotype.startsWith(a.gene) && a.level !== 'ClinVar';
    // Your result: the genotype, which allele is the variant, and the effect the study states for it
    const res = mdMake(d, 'div', 'md-result');
    mdMake(res, 'span', 'md-result-label', `${who}:`);
    mdMake(res, 'span', 'md-gt md-gt-' + a.status, snp ? `${a.variant} ${a.genotype}` : a.genotype);
    if (snp && a.variant_allele && a.copies != null) {
      const f = a.freq ? JSON.parse(a.freq) : null;
      const eur = f && f.EUR != null ? ` (${Math.round(f.EUR * 100)}% of alleles in Europeans)` : '';
      mdMake(res, 'span', 'md-copies', `${MD_COPIES[a.copies] || a.copies + ' copies'} of ${a.variant_allele}, the less common allele${eur}`);
    }
    if (a.phenotype) mdMake(res, 'span', 'md-copies', a.phenotype);
    if (a.effect) mdMake(d, 'div', 'md-effect md-effect-' + a.status, `→ ${a.effect}`);
    else mdMake(d, 'div', null, a.text);
    const others = JSON.parse(a.others || '[]').filter((o) => o.effect);
    if (others.length) {
      const o = mdMake(d, 'div', 'md-others');
      mdMake(o, 'span', 'md-others-label', 'Other genotypes:');
      for (const x of others) { const i = mdMake(o, 'span', 'md-other'); mdMake(i, 'span', 'md-gt', x.gt); i.append(' ' + x.effect); }
    }
    // The medicines the study names: this one marked, the others a click away
    const names = mdCompounds(a.drug);
    if (names.length > 1) {
      const tags = mdMake(d, 'div', 'md-compounds');
      for (const c of names) {
        const b = mdMake(tags, 'button', 'md-compound', c);
        b.type = 'button';
        if (c === here) b.setAttribute('aria-current', 'true');
        else b.addEventListener('click', () => mdSet({ md_q: c, md_open: '' }));
      }
    }
    const src = mdMake(d, 'details', 'md-text');
    mdMake(src, 'summary', null, a.level === 'ClinVar' ? 'ClinVar entry' : 'Study text (ClinPGx)');
    if (a.effect) mdMake(src, 'div', null, a.text + ' ');
    const link = mdMake(src, 'a', null, a.level === 'ClinVar' ? 'ClinVar' : 'ClinPGx');
    link.href = a.url; link.target = '_blank'; link.rel = 'noopener';
  };

  dash.draw('md-list', (el) => {
    const r = gx.rows('med_drugs', 'med_genes', 'med_guidance', 'med_names');
    if (!r) { if (gx.failed('med_drugs', 'med_genes', 'med_guidance', 'med_names')) gx.failLine(el); return; }
    const [drugs, genes, guidance, nameRows] = r;
    const f = mdParams();
    const who = mdWho(genes);
    const names = mdNames(nameRows);
    const groups = mdGroups(drugs, guidance, names, f);
    el.replaceChildren();
    const n = groups.filter((g) => g.status === 'differs').length;
    const weak = groups.filter((g) => g.weaker).length;
    mdMake(el, 'p', 'gx-note', `${groups.length} ${groups.length === 1 ? 'medicine' : 'medicines'}${f.gene ? ` with ${f.gene} evidence` : ''}${f.q ? ` matching "${f.q}"` : ''}; ` +
      `${who} differs from the typical case for ${n}.` + (weak ? ` ${weak} more ${weak === 1 ? 'differs' : 'differ'} only on weaker evidence.` : '') + (f.gene || f.q ? ' ' : ''));
    if (f.gene || f.q) {
      const clear = mdMake(el, 'button', 'lc-btn', 'Show all medicines');
      clear.type = 'button';
      clear.addEventListener('click', () => mdSet({ md_gene: '', md_q: '' }));
    }
    const toggle = (drug) => {
      const open = new Set(f.open);
      if (open.has(drug)) open.delete(drug); else open.add(drug);
      dash.setParams({ md_open: [...open].join('|') });
    };
    for (const g of groups.slice(0, mdShown)) {
      const open = f.open.has(g.drug);
      const box = mdMake(el, 'div', 'md-drug' + (g.status === 'differs' ? ' md-drug-differs' : ''));
      const head = mdMake(box, 'div', 'md-drug-head');
      mdMake(head, 'span', 'md-drug-name', g.drug);
      if (g.best < MD_GRADES.length) mdTag(head, MD_GRADES[g.best]);
      mdMake(head, 'span', 'md-status md-' + g.status, MD_STATUS[g.status]);
      if (g.weaker) mdMake(head, 'span', 'md-status md-weaker', `Weaker evidence (${g.weaker}) differs`);
      const n = names.get(g.drug);
      // What it is called in Europe (the WHO name), its class and ATC code, and the name the search found it by
      const aka = [];
      if (n && n.aka) aka.push(`International name: ${n.aka.split('; ').join(', ')}`);
      if (n && n.classes) aka.push(n.classes.split('; ')[0]);
      if (n && n.atc) aka.push(`ATC ${n.atc.split('; ').join(', ')}`);
      if (g.foundAs && !(n && n.aka && n.aka.toLowerCase().includes(g.foundAs.toLowerCase()))) aka.push(`Found as ${g.foundAs}`);
      if (aka.length) {
        const line = mdMake(box, 'div', 'md-aka');
        aka.forEach((x, i) => { if (i) line.append(' · '); mdMake(line, 'span', null, x); });
      }

      mdMake(box, 'div', 'md-sub', 'Dose and guidance');
      if (g.readable.length) {
        for (const x of open ? g.readable : g.readable.slice(0, 2)) mdGuide(box, x, who);
      } else {
        mdMake(box, 'p', 'md-none-note', g.unreadable
          ? `The guidelines and labels for this medicine depend on genes this DNA file can't read (${[...new Set(g.guides.map((x) => x.genes))].join(', ')}).`
          : 'No guideline or drug label bases the dose on genes for this medicine; the findings below are from studies.');
      }
      if (g.anns.length) {
        mdMake(box, 'div', 'md-sub', `Findings for ${who} (${g.anns.length})`);
        for (const a of open ? g.anns : g.anns.slice(0, 4)) mdFinding(box, a, who, g.drug);
      }
      const hidden = (g.readable.length > 2 ? g.readable.length - 2 : 0) + (g.anns.length > 4 ? g.anns.length - 4 : 0);
      if (hidden || open) {
        const b = mdMake(box, 'button', 'lc-btn md-toggle', open ? 'Show fewer' : `Show all (${hidden} more)`);
        b.type = 'button';
        b.addEventListener('click', () => toggle(g.drug));
      }
    }
    if (groups.length > mdShown) {
      const more = mdMake(el, 'button', 'lc-btn md-more', `Show ${Math.min(40, groups.length - mdShown)} more`);
      more.type = 'button';
      more.addEventListener('click', () => { mdShown += 40; dash.setParams({ md_more: mdShown }); });
    }
  });
