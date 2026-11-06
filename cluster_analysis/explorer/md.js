  // Medicines: drug genes (star alleles and CPIC types) and every ClinPGx drug annotation with the person's own reading
  const MD_LEVELS = { guideline: ['1A', '1B'], strong: ['1A', '1B', '2A', '2B'], all: ['1A', '1B', '2A', '2B', '3'] };
  const MD_STATUS = { typical: 'Typical response', differs: 'Differs from typical', not_excluded: 'Not detected, not excluded', unclear: 'Unclear' };
  const MD_CATS = ['Dosage', 'Efficacy', 'Toxicity', 'Metabolism/PK'];
  const mdMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const mdParams = () => {
    const p = dash.params();
    return { q: p.md_q || '', lv: p.md_lv || 'strong', cat: p.md_cat || 'all', diff: p.md_diff === true || p.md_diff === 'true', gene: p.md_gene || '' };
  };
  const mdWho = (rows) => (rows.find((r) => r.person) || {}).person || 'XY';
  let mdShown = 40;
  const mdSet = (p) => { mdShown = 40; dash.setParams(p); };

  // One entry per medicine: its annotations under the current filters, the most notable first
  const mdGroups = (drugs, f) => {
    const levels = MD_LEVELS[f.lv] || MD_LEVELS.strong;
    const q = f.q.trim().toLowerCase();
    const by = new Map();
    for (const d of drugs) {
      if (!levels.includes(d.level)) continue;
      if (f.cat !== 'all' && !d.category.split(';').includes(f.cat)) continue;
      if (f.gene && d.gene.split(';')[0] !== f.gene) continue;
      if (q && !d.drug.toLowerCase().includes(q) && !d.gene.toLowerCase().includes(q) && !(d.condition || '').toLowerCase().includes(q)) continue;
      if (!by.has(d.drug)) by.set(d.drug, []);
      by.get(d.drug).push(d);
    }
    const rank = { differs: 0, not_excluded: 1, unclear: 2, typical: 3 };
    const lvl = (l) => MD_LEVELS.all.indexOf(l);
    const groups = [...by.entries()].map(([drug, anns]) => {
      anns.sort((a, b) => rank[a.status] - rank[b.status] || lvl(a.level) - lvl(b.level));
      const status = anns[0].status;
      return { drug, anns, status, best: Math.min(...anns.map((a) => lvl(a.level))) };
    }).filter((g) => !f.diff || g.status === 'differs');
    return groups.sort((a, b) => rank[a.status] - rank[b.status] || a.best - b.best || a.drug.localeCompare(b.drug));
  };

  dash.draw('md-summary', (el) => {
    const r = gx.rows('med_genes', 'med_drugs');
    if (!r) { if (gx.failed('med_genes', 'med_drugs')) gx.failLine(el); return; }
    const [genes, drugs] = r;
    el.replaceChildren();
    const who = mdWho(genes);
    const guide = drugs.filter((d) => MD_LEVELS.guideline.includes(d.level));
    const differs = [...new Set(guide.filter((d) => d.status === 'differs').map((d) => d.drug))].sort();
    const typical = new Set(guide.map((d) => d.drug)).size - differs.length;
    const odd = genes.filter((g) => g.alleles && !g.typical);
    mdMake(el, 'h3', null, `${who} and medicines`);
    mdMake(el, 'p', null, `Guideline-grade evidence covers ${typical + differs.length} medicines. For ${differs.length} of them ${who} ` +
      `differs from the typical case; for the rest ${who} is expected to respond as most people do. ` +
      (odd.length ? `The drug genes behind most of the differences: ${odd.map((g) => `${g.gene} ${g.alleles} (${g.phenotype.split(' (')[0].toLowerCase()})`).join(', ')}.` : ''));
    mdMake(el, 'span', 'gx-label', `Guideline-grade medicines where ${who} differs`);
    const pills = mdMake(el, 'div', 'md-pills');
    for (const drug of differs) {
      const b = mdMake(pills, 'button', 'md-pill', drug.replace(/;/g, ', '));
      b.type = 'button';
      b.addEventListener('click', () => { mdSet({ md_q: drug.split(';').pop(), md_lv: 'all', md_cat: 'all', md_gene: '' }); document.getElementById('med-drugs').scrollIntoView({ behavior: 'smooth' }); });
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
      const names = [...new Set(drugs.filter((d) => d.gene.split(';')[0] === g.gene && MD_LEVELS.guideline.includes(d.level)).map((d) => d.drug.split(';').pop()))];
      if (names.length) mdMake(b, 'span', 'md-gene-drugs', names.slice(0, 6).join(', ') + (names.length > 6 ? ` +${names.length - 6}` : ''));
      const snps = JSON.parse(g.snps || '[]');
      b.title = [g.note, ...snps.map((s) => `${s.allele} ${s.rsid}: ${s.genotype} (${s.copies} ${s.copies === 1 ? 'copy' : 'copies'} of ${s.variant}; ${s.confidence})`)]
        .filter(Boolean).join('\n');
      b.addEventListener('click', () => mdSet({ md_gene: f.gene === g.gene ? '' : g.gene, md_q: '', md_lv: 'all' }));
    }
  });

  dash.draw('md-controls', (el) => {
    const r = gx.rows('med_drugs');
    if (!r) return;
    const f = mdParams();
    if (!el.dataset.built) {
      el.dataset.built = '1';
      const q = mdMake(el, 'input', 'md-search');
      q.type = 'search'; q.placeholder = 'Search a medicine, gene or condition'; q.setAttribute('aria-label', 'Search medicines');
      let t;
      q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => mdSet({ md_q: q.value }), 250); });
      const lv = mdMake(el, 'select', 'md-select'); lv.setAttribute('aria-label', 'Evidence');
      for (const [v, label] of [['guideline', 'Guideline-grade (1A–1B)'], ['strong', 'Strong evidence (1–2)'], ['all', 'All, with weaker (3)']]) {
        const o = mdMake(lv, 'option', null, label); o.value = v;
      }
      lv.addEventListener('change', () => mdSet({ md_lv: lv.value }));
      const cat = mdMake(el, 'select', 'md-select'); cat.setAttribute('aria-label', 'Kind of effect');
      for (const [v, label] of [['all', 'Every kind of effect'], ...MD_CATS.map((c) => [c, c === 'Metabolism/PK' ? 'Metabolism' : c])]) {
        const o = mdMake(cat, 'option', null, label); o.value = v;
      }
      cat.addEventListener('change', () => mdSet({ md_cat: cat.value }));
      const lab = mdMake(el, 'label', 'md-check');
      const cb = mdMake(lab, 'input'); cb.type = 'checkbox';
      lab.append('Only where XY differs');
      cb.addEventListener('change', () => mdSet({ md_diff: cb.checked }));
      el._md = { q, lv, cat, cb };
    }
    const c = el._md;
    if (document.activeElement !== c.q) c.q.value = f.q;
    c.lv.value = f.lv; c.cat.value = f.cat; c.cb.checked = f.diff;
  });

  dash.draw('md-list', (el) => {
    const r = gx.rows('med_drugs', 'med_genes');
    if (!r) { if (gx.failed('med_drugs', 'med_genes')) gx.failLine(el); return; }
    const [drugs, genes] = r;
    const f = mdParams();
    const who = mdWho(genes);
    const groups = mdGroups(drugs, f);
    el.replaceChildren();
    const n = groups.filter((g) => g.status === 'differs').length;
    mdMake(el, 'p', 'gx-note', `${groups.length} medicines${f.gene ? ` with ${f.gene} evidence` : ''}${f.q ? ` matching "${f.q}"` : ''}; ` +
      `${who} differs from the typical case for ${n}.` + (f.gene || f.q ? ' ' : ''));
    if (f.gene || f.q) {
      const clear = mdMake(el, 'button', 'lc-btn', 'Show all medicines');
      clear.type = 'button';
      clear.addEventListener('click', () => mdSet({ md_gene: '', md_q: '', md_lv: 'strong' }));
    }
    for (const g of groups.slice(0, mdShown)) {
      const box = mdMake(el, 'div', 'md-drug');
      const head = mdMake(box, 'div', 'md-drug-head');
      mdMake(head, 'span', 'md-drug-name', g.drug.replace(/;/g, ', '));
      mdMake(head, 'span', 'md-status md-' + g.status, MD_STATUS[g.status]);
      for (const a of g.anns.slice(0, 4)) {
        const d = mdMake(box, 'div', 'md-ann md-' + a.status);
        const meta = mdMake(d, 'div', 'md-ann-meta');
        mdMake(meta, 'span', 'md-level', a.level);
        mdMake(meta, 'span', null, `${a.gene} · ${a.category.replace(/;/g, ', ').replace('Metabolism/PK', 'metabolism').toLowerCase()}`);
        mdMake(meta, 'span', 'md-gt', a.genotype.startsWith(a.gene) ? a.genotype : `${a.variant} ${a.genotype}`);
        if (a.confidence === 'high') mdMake(meta, 'span', 'th-imp th-imp-high', 'imputed, high confidence');
        if (a.phenotype) mdMake(meta, 'span', null, a.phenotype);
        const t = mdMake(d, 'div', null, a.text + ' ');
        const link = mdMake(t, 'a', null, 'ClinPGx');
        link.href = a.url; link.target = '_blank'; link.rel = 'noopener';
      }
      if (g.anns.length > 4) mdMake(box, 'p', 'gx-note', `+${g.anns.length - 4} more annotations for this medicine.`);
    }
    if (groups.length > mdShown) {
      const more = mdMake(el, 'button', 'lc-btn md-more', `Show ${Math.min(40, groups.length - mdShown)} more`);
      more.type = 'button';
      more.addEventListener('click', () => { mdShown += 40; dash.setParams({ md_more: mdShown }); });
    }
  });
