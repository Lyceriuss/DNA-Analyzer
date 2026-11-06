  // Theme clusters: picker, XY balance, mechanism map, connection network, gene detail and shared pathways
  const TH_TEXT = { LoF: 'less active', GoF: 'more active', altered: 'changed, direction unclear', normal: 'typical function',
                    variant: 'carries a trait-linked variant' };
  const TH_CLASS = { LoF: 'lof', GoF: 'gof', altered: 'alt', normal: 'norm', variant: 'var', unknown: 'untested' };
  TH_TEXT.unknown = 'no known effect on the gene';
  // Labels come from evidence about the variant (evidence_call.py); the wording follows what kind of evidence it is
  const TH_BASIS = { cpic: 'CPIC allele function', measured: 'measured protein function, MaveDB', curated: 'curated protein effect, UniProt',
    truncating: 'the change cuts the protein short', predicted: 'predicted damage, SIFT and PolyPhen', expression: 'gene expression, GTEx',
    none: 'no evidence about function' };
  const thFnText = (g, fn) => g && g.basis === 'expression' && (fn === 'GoF' || fn === 'LoF') ? (fn === 'GoF' ? 'more expressed' : 'less expressed')
    : g && g.basis === 'predicted' && fn === 'LoF' ? 'likely less active' : TH_TEXT[fn];
  const TH_FILL = { LoF: 'var(--color-bad)', GoF: 'var(--gof)', altered: 'var(--color-fg)', normal: 'var(--typical)',
                    variant: 'var(--color-fg-muted)', unknown: 'var(--color-panel)' };
  const thMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  // Library genes carry a function call; API-theme genes outside the library are marked when XY carries a trait-linked allele
  const thCall = (g) => g.genotype ? (g.function || 'normal') : g.carried > 0 ? 'variant' : null;
  const thLabel = (g) => g.gene + (g.genotype ? ` ${g.genotype}` : '') + (g.genotype && g.function !== 'normal' && g.dose ? ` ×${g.dose}` : '') +
    (!g.genotype && g.carried > 0 ? ` · ${g.carried}` : '');
  const thPubmed = (parent, id) => {
    if (!id) return;
    const a = thMake(parent, 'a', null, 'PubMed');
    a.href = `https://pubmed.ncbi.nlm.nih.gov/${id}/`; a.target = '_blank'; a.rel = 'noopener';
  };
  const TH_CONF = { high: 'imputed, high confidence', medium: 'imputed, medium confidence' };
  // GWAS effects per copy in plain words. Betas for levels are mostly in standard deviations of the trait.
  const thSize = (it) => {
    if (it.effect == null) return '';
    if (it.kind === 'beta') {
      const b = Math.abs(it.effect);
      return b < 0.05 ? 'a very small shift' : b < 0.15 ? 'a small shift' : b < 0.4 ? 'a moderate shift' : 'a large shift';
    }
    const r = it.effect >= 1 ? it.effect : 1 / it.effect;
    return r < 1.1 ? 'a very small effect' : r < 1.3 ? 'a small effect' : r < 2 ? 'a moderate effect' : 'a large effect';
  };
  const thFinding = (parent, f, it, who = 'XY') => {
    const d = thMake(parent, 'div');
    thMake(d, 'span', 'th-src', it.source);
    if (TH_CONF[f.confidence]) {
      const c = thMake(d, 'span', 'th-imp th-imp-' + f.confidence, TH_CONF[f.confidence]);
      c.title = f.confidence === 'high'
        ? 'Not measured: inferred from the surrounding SNPs. Calls like this were right at least 98% of the time when some of the file\'s own SNPs were hidden and re-imputed.'
        : 'Not measured: inferred from the surrounding SNPs. Calls like this were right 90 to 98% of the time in the check; good for patterns, not for single conclusions.';
    }
    if (it.source === 'GWAS') {
      const known = /^[ACGT]$/.test(it.allele || '');
      const copies = !known ? 'the study did not report which allele' : it.copies == null ? 'strand unclear' : `${it.copies} ${it.copies === 1 ? 'copy' : 'copies'} of ${it.allele}`;
      const size = it.effect != null ? ` (${it.kind === 'beta' ? 'β' : 'OR'} ${d3.format('.3~g')(it.effect)} per copy: ${thSize(it)}; p ${d3.format('.0e')(it.p)})` : '';
      d.append(`${f.rsid} ${f.genotype}: ${copies}. ${known ? it.allele + ' ' : 'The SNP '}${known && it.direction ? it.direction : 'is linked to'} ${known && it.direction && it.kind === 'odds ratio' ? 'the risk of ' : ''}${it.what}${size}. `);
      if (!known && it.related && it.related.length) {
        d.append(`Other studies of this SNP name the allele: ` + it.related.map((k) => `${k.allele} ${k.direction} ${k.trait} (${who} has ${k.copies})`).join('; ') + '. ');
      }
      thPubmed(d, it.pubmed);
    } else if (it.source === 'ClinVar') {
      d.append(`${f.rsid} ${f.genotype}: ${it.what}; ${who} has ${it.copies} ${it.copies === 1 ? 'copy' : 'copies'} of ${it.allele}.`);
    } else d.append(`${f.rsid} ${f.genotype}: ${it.what}.`);
  };

  const thSel = () => {
    const r = gx.rows('theme_meta', 'theme_genes');
    if (!r) return null;
    const [meta, rows] = r;
    const themes = [...new Map(meta.map((m) => [m.theme, m])).values()].sort((a, b) => a.theme_order - b.theme_order);
    const p = dash.params();
    const theme = themes.find((t) => t.theme === p.theme) || themes[0];
    const facets = meta.filter((m) => m.theme === theme.theme).sort((a, b) => a.facet_order - b.facet_order);
    const genes = rows.filter((g) => g.theme === theme.theme).map((g) => ({ ...g, fl: JSON.parse(g.facets), ev: JSON.parse(g.evidence) }));
    const api = theme.source === 'api';
    const stats = api && theme.stats ? JSON.parse(theme.stats) : null;
    // Organ focus (themes with a body map): the page narrows to genes acting in the selected organ
    const organs = (stats && stats.organs) || [];
    const organ = organs.find((o) => o.id === p.th_organ) || null;
    const inOrgan = (g) => !organ || (g.ev.organs || []).includes(organ.id);
    // An API theme lists every gene but draws the notable ones: a library call, a carried finding or a strong disease link
    const shown = (api ? genes.filter((g) => g.notable) : genes).filter(inOrgan);
    const byName = new Map(genes.map((g) => [g.gene, g]));
    // Default selection: the first changed gene, so the panel opens on something XY carries
    const order = (g) => (g.primary === 'disease' ? 4 : 0) + (g.function === 'LoF' || g.function === 'GoF' ? 0 : g.carried > 0 ? 1 : g.genotype ? 2 : 3);
    const fallback = [...shown].sort((a, b) => order(a) - order(b) || (b.carried || 0) - (a.carried || 0) || a.gene.localeCompare(b.gene))[0];
    const gene = byName.get(p.th_gene) || fallback;
    return { themes, theme, facets, genes, shown, byName, gene, api, stats, organs, organ, inOrgan };
  };
  const thPick = (gene) => dash.setParams({ th_gene: gene });
  const thWho = (s) => (s && s.stats && s.stats.person) || 'XY';

  const thBalance = (parent, genes, none = 'not genotyped') => {
    const bar = thMake(parent, 'div', 'th-balance');
    bar.setAttribute('role', 'img');
    const parts = [['GoF', 'gof'], ['normal', 'norm'], ['LoF', 'lof'], ['altered', 'alt'], ['unknown', 'untested'], ['variant', 'var'], [null, 'none']];
    const label = [];
    for (const [fn, cls] of parts) {
      const n = genes.filter((g) => thCall(g) === fn).length;
      if (!n) continue;
      const s = thMake(bar, 'span', 'th-b-' + cls);
      s.style.width = `${(n / genes.length) * 100}%`;
      label.push(`${n} ${fn ? TH_TEXT[fn] : none}`);
    }
    bar.setAttribute('aria-label', label.join(', '));
    return label;
  };

  dash.draw('th-picker', (el) => {
    el.replaceChildren();
    const s = thSel();
    if (!s) { if (gx.failed('theme_meta')) gx.failLine(el); return; }
    for (const t of s.themes) {
      const who = t.stats ? JSON.parse(t.stats).person : null;
      const b = thMake(el, 'button', 'th-pick', t.theme_name + (who ? ` · ${who}` : ''));
      b.type = 'button';
      b.setAttribute('aria-pressed', String(t.theme === s.theme.theme));
      b.addEventListener('click', () => dash.setParams({ theme: t.theme, th_gene: null, th_organ: null, th_facet: null }));
    }
  });

  dash.draw('th-head', (el) => {
    el.replaceChildren();
    const s = thSel();
    if (!s) { if (gx.failed('theme_meta', 'theme_genes')) gx.failLine(el); return; }
    thMake(el, 'h3', null, s.theme.theme_name);
    thMake(el, 'p', 'gx-muted', s.theme.about);
    if (s.api && s.stats) {
      const st = s.stats, fmt = d3.format(','), who = thWho(s);
      const parts = thBalance(el, s.shown);
      const bc = st.by_confidence || {}, imputed = (bc.high || 0) + (bc.medium || 0);
      const snps = imputed
        ? `${who}'s file measures ${fmt(bc.measured || 0)} SNPs inside them, and imputation adds ${fmt(imputed)} more it can call with high or ` +
          `medium confidence (findings from them are marked)`
        : `${who}'s file measures ${fmt(st.n_snps)} SNPs inside them`;
      thMake(el, 'p', null, `${fmt(st.n_genes)} genes act on ${s.theme.theme_name.toLowerCase()}, ${fmt(st.n_mechanism)} of them through a known ` +
        `mechanism. ${snps}, and ${st.n_genes_with_findings} genes have a SNP with something ` +
        `known about it. The ${s.shown.length} drawn here are the notable ones: ${parts.filter((x) => !/not genotyped/.test(x)).join(', ')}.`);
      const carried = st.pathogenic_carried || [], possible = st.pathogenic_possible || [];
      const src = (c) => c.confidence && c.confidence !== 'measured' ? `, imputed ${c.confidence}` : '';
      thMake(el, 'p', carried.length ? 'lc-warn' : 'gx-note', (carried.length
        ? `${who} carries ${carried.length} ClinVar pathogenic ${carried.length === 1 ? 'allele' : 'alleles'}: ` + carried.map((c) => `${c.gene} ${c.rsid} (${c.condition}${src(c)})`).join('; ') + '.'
        : `ClinVar pathogenic variants: ${fmt(st.pathogenic_measured)} in these genes are measured or confidently imputed, and ${who} carries none of them.`) +
        (st.pathogenic_not_excluded ? ` ${fmt(st.pathogenic_not_excluded)} more are too rare for imputation to rule out: not detected, but not excluded.` : ''));
      if (possible.length) thMake(el, 'p', 'gx-note', `Possible, from weaker imputed calls (confirm with a test before acting): ` +
        possible.map((c) => `${c.gene} ${c.rsid} ${c.genotype} (${c.condition}, ${c.confidence})`).join('; ') + '.');
      thMake(el, 'p', 'gx-note', `Genes: ${st.rule}. This theme is built from Open Targets and Gene Ontology, not from the library; ` +
        `${who}'s SNPs are matched offline against ClinVar and the GWAS Catalog.`);
      return;
    }
    const typed = s.genes.filter((g) => g.genotype);
    const parts = thBalance(el, s.genes);
    thMake(el, 'p', null, `${s.genes.length} library genes act on ${s.theme.theme_name.toLowerCase()}, and XY has a call at ${typed.length}: ` +
      parts.filter((x) => !/not genotyped/.test(x)).join(', ') + '.');
    // Where XY's changed genes gather
    const lean = s.facets.map((f) => {
      const gs = s.genes.filter((g) => g.fl.includes(f.facet));
      return { f, lof: gs.filter((g) => g.function === 'LoF'), gof: gs.filter((g) => g.function === 'GoF') };
    });
    const top = (key) => lean.filter((x) => x[key].length).sort((a, b) => b[key].length - a[key].length)[0];
    const lo = top('lof'), hi = top('gof');
    if (lo || hi) {
      const p = thMake(el, 'p', 'gx-note');
      p.textContent = [lo ? `Most less-active genes: ${lo.f.facet_name} (${lo.lof.map((g) => g.gene).join(', ')}).` : null,
        hi ? `Most more-active genes: ${hi.f.facet_name} (${hi.gof.map((g) => g.gene).join(', ')}).` : null].filter(Boolean).join(' ');
    }
  });

  dash.draw('th-facets', (el) => {
    el.replaceChildren();
    const s = thSel();
    if (!s) { if (gx.failed('theme_meta', 'theme_genes')) gx.failLine(el); return; }
    const rank = { LoF: 0, GoF: 1, altered: 2, variant: 3, normal: 4 };
    for (const f of s.facets) {
      const all = s.genes.filter((g) => g.fl.includes(f.facet) && s.inOrgan(g));
      if (s.organ && !all.length) continue;
      const gs = (s.api ? all.filter((g) => g.notable) : all)
        .sort((a, b) => (rank[thCall(a)] ?? 5) - (rank[thCall(b)] ?? 5) || (b.carried || 0) - (a.carried || 0) || a.gene.localeCompare(b.gene));
      const box = thMake(el, 'div', 'th-facet' + (dash.params().th_facet === f.facet ? ' is-open' : ''));
      const open = thMake(thMake(box, 'h3'), 'button', 'th-facet-open', f.facet_name);
      open.type = 'button';
      open.title = 'Open this mechanism in depth';
      open.addEventListener('click', () => thFacetOpen(f.facet));
      thMake(box, 'span', 'th-tag', s.api
        ? `${all.length} ${all.length === 1 ? 'gene' : 'genes'} · ${gs.length} notable`
        : `${gs.length} ${gs.length === 1 ? 'gene' : 'genes'}${f.core ? '' : ' · needs a direct link to the theme'}`);
      if (s.api && f.facet_about) thMake(box, 'p', 'gx-note', f.facet_about);
      if (!gs.length) { thMake(box, 'p', 'gx-note', 'No library gene has evidence for this mechanism yet.'); continue; }
      thBalance(box, gs);
      const chips = thMake(box, 'div', 'th-genes');
      for (const g of gs) {
        const fn = thCall(g);
        const b = thMake(chips, 'button', 'lc-chip th-gene ' + (fn ? 'lc-' + TH_CLASS[fn] : 'lc-untested') + (g.gene === s.gene.gene ? ' is-selected' : ''), thLabel(g));
        b.type = 'button';
        b.title = g.interpretation || (g.carried ? `${thWho(s)} carries ${g.carried} trait-linked ${g.carried === 1 ? 'allele' : 'alleles'}` : `No ${thWho(s)} finding`);
        b.addEventListener('click', () => thPick(g.gene));
      }
      if (s.api && all.length > gs.length) thMake(box, 'span', 'th-tag', `+${all.length - gs.length} more with no ${thWho(s)} finding and a weaker disease link`);
    }
  });

  dash.draw('th-net', (el) => {
    el.replaceChildren();
    const s = thSel();
    const lr = gx.rows('theme_links');
    if (!s || !lr) { if (gx.failed('theme_meta', 'theme_genes', 'theme_links')) gx.failLine(el); return; }
    const W = Math.max(320, el.clientWidth), H = 580;
    let links = lr[0].filter((l) => l.theme === s.theme.theme && s.byName.has(l.a) && s.byName.has(l.b));
    const strong = links.filter((l) => l.score >= 0.7);
    links = strong.length >= s.shown.length / 2 ? strong : links;

    // Mechanism anchors around an ellipse; each gene is pulled towards its main mechanism
    const used = s.facets.filter((f) => s.shown.some((g) => g.primary === f.facet));
    const anchor = new Map(used.map((f, i) => {
      const a = (i / used.length) * 2 * Math.PI - Math.PI / 2;
      return [f.facet, { x: W / 2 + Math.cos(a) * W * 0.33, y: H / 2 + Math.sin(a) * H * 0.34, f }];
    }));
    const nodes = s.shown.map((g) => ({ id: g.gene, g, ...anchor.get(g.primary) }));
    const drawn = new Set(nodes.map((n) => n.id));
    links = links.filter((l) => drawn.has(l.a) && drawn.has(l.b));
    const edges = links.map((l) => ({ source: l.a, target: l.b, score: l.score }));
    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id((d) => d.id).strength(0.04))
      .force('charge', d3.forceManyBody().strength(-70))
      .force('x', d3.forceX((d) => anchor.get(d.g.primary).x).strength(0.3))
      .force('y', d3.forceY((d) => anchor.get(d.g.primary).y).strength(0.3))
      .force('collide', d3.forceCollide(17)).stop();
    for (let i = 0; i < 300; i++) sim.tick();
    for (const n of nodes) { n.x = Math.max(14, Math.min(W - 14, n.x)); n.y = Math.max(14, Math.min(H - 14, n.y)); }

    const sel = s.gene.gene;
    const near = new Set([sel, ...edges.filter((e) => e.source.id === sel || e.target.id === sel).flatMap((e) => [e.source.id, e.target.id])]);
    const svg = d3.select(el).append('svg').attr('width', W).attr('height', H).attr('viewBox', `0 0 ${W} ${H}`)
      .attr('role', 'group').attr('aria-label', `${s.theme.theme_name} genes and their interactions`);
    const tip = gx.tip(el);
    for (const a of anchor.values()) {
      const side = a.x < W * 0.35 ? 'start' : a.x > W * 0.65 ? 'end' : 'middle';
      const lx = side === 'start' ? Math.max(4, a.x - 90) : side === 'end' ? Math.min(W - 4, a.x + 90) : a.x;
      svg.append('text').attr('x', lx).attr('y', a.y < H / 2 ? Math.max(12, a.y - 50) : Math.min(H - 4, a.y + 58)).attr('text-anchor', side)
        .attr('font-size', 11).attr('letter-spacing', '.04em').style('fill', 'var(--color-fg-muted)').text(a.f.facet_name.toUpperCase());
    }
    svg.append('g').selectAll('line').data(edges).join('line')
      .attr('x1', (e) => e.source.x).attr('y1', (e) => e.source.y).attr('x2', (e) => e.target.x).attr('y2', (e) => e.target.y)
      .style('stroke', (e) => (e.source.id === sel || e.target.id === sel) ? 'var(--color-fg)' : 'var(--color-border-line)')
      .attr('stroke-width', (e) => 0.6 + (e.score - 0.4) * 3)
      .attr('stroke-opacity', (e) => (e.source.id === sel || e.target.id === sel) ? 0.9 : 0.45);
    const node = svg.append('g').selectAll('g').data(nodes).join('g').attr('class', 'th-node')
      .attr('transform', (n) => `translate(${n.x},${n.y})`).attr('tabindex', 0).attr('role', 'button')
      .attr('aria-label', (n) => `${n.id}: ${thCall(n.g) ? TH_TEXT[thCall(n.g)] : 'not genotyped'}`)
      .style('opacity', (n) => near.has(n.id) ? 1 : 0.45)
      .on('click', (event, n) => thPick(n.id))
      .on('keydown', (event, n) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); thPick(n.id); } })
      .on('mousemove', (event, n) => tip.show(event, n.id, [n.g.genotype ? `${n.g.rsid} ${n.g.genotype} · ${TH_TEXT[thCall(n.g)]}` +
        (n.g.function !== 'normal' && n.g.dose ? ` ×${n.g.dose}` : '') : `Not genotyped in ${thWho(s)}`, n.g.interpretation || '']))
      .on('mouseleave', () => tip.hide());
    node.append('circle').attr('r', (n) => n.id === sel ? 10 : 7)
      .style('fill', (n) => thCall(n.g) ? TH_FILL[thCall(n.g)] : 'var(--color-panel)')
      .style('stroke', (n) => n.id === sel ? 'var(--color-fg)' : thCall(n.g) ? 'var(--color-bg)' : 'var(--color-fg-muted)')
      .attr('stroke-width', (n) => n.id === sel ? 2.5 : 1.5).attr('stroke-dasharray', (n) => thCall(n.g) ? null : '2 2');
    node.append('text').attr('x', 11).attr('y', 4).attr('font-size', 11)
      .attr('font-weight', (n) => n.id === sel ? 700 : 400).style('fill', 'var(--color-fg)').text((n) => n.id);
  });

  dash.draw('th-detail', (el) => {
    el.replaceChildren();
    const s = thSel();
    const r = gx.rows('theme_links', 'theme_pathways');
    if (!s || !r) { if (gx.failed('theme_meta', 'theme_genes', 'theme_links', 'theme_pathways')) gx.failLine(el); return; }
    const g = s.gene, fn = thCall(g);
    const head = thMake(el, 'div', 'lc-name');
    thMake(head, 'h3', null, g.gene);
    const fnText = fn ? thFnText(g, fn) : null;
    thMake(head, 'span', 'lc-call ' + (fn ? { LoF: 'lof', GoF: 'gof', altered: 'altered', normal: 'norm', variant: 'var', unknown: 'unknown' }[fn] : 'unknown'),
      fn ? fnText[0].toUpperCase() + fnText.slice(1) + (fn !== 'normal' && fn !== 'unknown' && g.dose ? ` ×${g.dose}` : '') : s.api ? `No ${thWho(s)} finding` : 'Not genotyped');
    if (g.genotype) thMake(el, 'p', null, `Effect on the gene: ${g.fn_evidence || 'no evidence collected'} (${TH_BASIS[g.basis] || TH_BASIS.none}).`);
    thMake(el, 'p', g.genotype ? 'gx-note' : null, g.genotype ? `Library note for ${g.rsid} ${g.genotype}: ${g.interpretation} (library rating ${g.score}/10, where 5 is neutral; 4 or lower counts as a risk in the PDF report, 7 or higher as a strength). The notes were written with an LLM and are being checked against the evidence; the label above comes from the evidence, not the note.`
      : s.api ? `Not in the library. ${thWho(s)}'s file ${s.stats && (s.stats.by_confidence || {}).high ? 'measures or confidently imputes' : 'measures'} ${g.ev.n_snps || 0} SNPs in or near this gene.` : 'XY has no call at this gene\'s library SNP.');
    if (g.has_lifecycle) {
      const b = thMake(el, 'button', 'lc-btn', 'Open its lifecycle');
      b.type = 'button';
      b.addEventListener('click', () => { dash.setParams({ lc_gene: g.gene, lc_role: 1 }); gx.show('lifecycle'); });
    }

    if (s.api) {
      // XY's variants first, then why the gene belongs to the theme
      const fs = (g.ev.findings || []).filter((f) => f.items.length);
      thMake(el, 'span', 'gx-label', `${thWho(s)}'s variants with a known effect (${fs.length})`);
      if (fs.length) {
        const fl = thMake(el, 'ul', 'th-why');
        const carriedFirst = [...fs].sort((a, b) => Math.max(...b.items.map((i) => i.copies || 0)) - Math.max(...a.items.map((i) => i.copies || 0)));
        for (const f of carriedFirst.slice(0, 12)) { const li = thMake(fl, 'li'); for (const it of f.items.slice(0, 3)) thFinding(li, f, it, thWho(s)); }
        if (fs.length > 12) thMake(el, 'p', 'gx-note', `+${fs.length - 12} more SNPs with a finding.`);
      } else thMake(el, 'p', 'gx-note', `None of ${thWho(s)}'s SNPs in this gene has a ClinVar, GWAS or library entry for one of the theme's conditions.`);
      thMake(el, 'span', 'gx-label', `Why it is in ${s.theme.theme_name.toLowerCase()}`);
      const why = thMake(el, 'ul', 'th-why');
      for (const f of s.facets) {
        const m = (g.ev.mechanisms || {})[f.facet];
        if (!m) continue;
        const li = thMake(why, 'li');
        thMake(li, 'b', null, f.facet_name + (f.facet === g.primary ? ' (main)' : ''));
        const d = thMake(li, 'div'); thMake(d, 'span', 'th-src', 'GO'); d.append(`${m.terms.join('; ')} (${m.evidence})`);
      }
      const ds = Object.entries(g.ev.diseases || {});
      if (ds.length) {
        const li = thMake(why, 'li');
        thMake(li, 'b', null, 'Disease and trait links (Open Targets)');
        for (const [name, v] of ds) {
          const d = thMake(li, 'div'); thMake(d, 'span', 'th-src', d3.format('.2f')(v.score));
          d.append(`${name}${v.genetic >= 0.2 ? `, human genetics ${d3.format('.2f')(v.genetic)}` : ''} (${v.types.map((t) => t.replace(/_/g, ' ')).join(', ')})`);
        }
      }
    } else {
    thMake(el, 'span', 'gx-label', `Why it is in ${s.theme.theme_name.toLowerCase()}`);
    const ul = thMake(el, 'ul', 'th-why');
    for (const f of s.facets) {
      const ev = g.ev[f.facet];
      if (!ev) continue;
      const li = thMake(ul, 'li');
      thMake(li, 'b', null, f.facet_name + (f.facet === g.primary ? ' (main)' : ''));
      for (const e of ev) { const d = thMake(li, 'div'); thMake(d, 'span', 'th-src', e.source); d.append(e.text); }
    }
    }

    const links = r[0].filter((l) => l.theme === s.theme.theme && (l.a === g.gene || l.b === g.gene))
      .map((l) => ({ other: l.a === g.gene ? l.b : l.a, score: l.score })).filter((l) => s.byName.has(l.other))
      .sort((a, b) => b.score - a.score).slice(0, 14);
    thMake(el, 'span', 'gx-label', 'Interacts with, in this theme');
    if (links.length) {
      const box = thMake(el, 'div', 'th-genes');
      for (const l of links) {
        const o = s.byName.get(l.other), ofn = thCall(o);
        const b = thMake(box, 'button', 'lc-chip th-gene ' + (ofn ? 'lc-' + TH_CLASS[ofn] : 'lc-untested'), `${thLabel(o)} · ${l.score.toFixed(2)}`);
        b.type = 'button';
        b.title = `STRING confidence ${l.score.toFixed(2)}`;
        b.addEventListener('click', () => thPick(o.gene));
      }
    } else thMake(el, 'p', 'gx-note', 'No STRING interaction with the other genes in this theme.');

    const pws = r[1].filter((p) => p.theme === s.theme.theme && JSON.parse(p.genes).includes(g.gene));
    if (pws.length) {
      thMake(el, 'span', 'gx-label', 'Shared pathways');
      const pl = thMake(el, 'ul', 'lc-alts');
      for (const p of pws.slice(0, 8)) thMake(pl, 'li', null, `${p.pathway} (with ${JSON.parse(p.genes).filter((x) => x !== g.gene).join(', ')})`);
    }
  });

  dash.draw('th-pathways', (tbody) => {
    tbody.replaceChildren();
    const s = thSel();
    const r = gx.rows('theme_pathways');
    if (!s || !r) return;
    for (const p of r[0].filter((x) => x.theme === s.theme.theme)) {
      const tr = thMake(tbody, 'tr');
      const td = thMake(tr, 'td', null, p.pathway);
      if (p.on_theme) thMake(td, 'span', 'th-tag', ' · mechanism pathway');
      if (s.api && p.n > JSON.parse(p.genes).length) thMake(td, 'span', 'th-tag', ` · ${p.n} theme genes, notable ones shown`);
      const cell = thMake(tr, 'td');
      const box = thMake(cell, 'div', 'th-genes');
      for (const name of JSON.parse(p.genes)) {
        const g = s.byName.get(name), fn = g && thCall(g);
        const b = thMake(box, 'button', 'lc-chip th-gene ' + (fn ? 'lc-' + TH_CLASS[fn] : 'lc-untested'), g ? thLabel(g) : name);
        b.type = 'button';
        b.addEventListener('click', () => thPick(name));
      }
    }
  });

  // The 28-day cycle for the female theme: textbook hormone shapes, the lining, and the person's genes on the days they act
  const CYCLE_PHASES = [
    { id: 'menses', name: 'Menstruation', from: 1, to: 5,
      what: 'Progesterone has fallen, so the lining sheds. FSH starts rising to recruit a new group of follicles.' },
    { id: 'follicular', name: 'Follicular phase', from: 1, to: 13,
      what: 'FSH grows a group of follicles; one becomes dominant, and its rising estradiol rebuilds the lining.' },
    { id: 'ovulation', name: 'Ovulation', from: 13, to: 15,
      what: 'Peak estradiol flips to positive feedback: an LH surge releases the egg about 24–36 hours later.' },
    { id: 'luteal', name: 'Luteal phase', from: 15, to: 28,
      what: 'The empty follicle becomes the corpus luteum and makes progesterone, which readies the lining; the implantation ' +
            'window is roughly days 19–24. Without a pregnancy, progesterone falls and the cycle restarts.' },
  ];
  // Relative hormone levels by day (0–1): the textbook shape of a 28-day cycle, not anyone's measurements
  const CYCLE_HORMONES = [
    { id: 'FSH', pts: [[1, .55], [3, .62], [7, .42], [11, .32], [14, .72], [16, .3], [22, .18], [26, .3], [28, .5]] },
    { id: 'LH', pts: [[1, .2], [10, .22], [12, .32], [13, .7], [14, 1], [15, .42], [17, .2], [28, .18]] },
    { id: 'Estradiol', pts: [[1, .15], [6, .25], [10, .55], [13, .95], [15, .35], [18, .45], [21, .55], [25, .35], [28, .15]] },
    { id: 'Progesterone', pts: [[1, .05], [13, .05], [15, .14], [18, .6], [21, .95], [24, .7], [27, .2], [28, .08]] },
  ];
  const CYCLE_LINING = [[1, .55], [5, .15], [9, .35], [14, .62], [18, .82], [21, .95], [26, .9], [28, .6]];
  // Core cycle genes: where they act and what a change in them does
  const CYCLE_GENES = {
    GNRH1: { day: 13, phases: ['follicular', 'ovulation'], role: 'GnRH pulses from the hypothalamus drive the whole cycle.',
             LoF: 'Weaker GnRH signalling lowers LH and FSH, which can mean irregular or missed ovulation.' },
    GNRHR: { day: 13, phases: ['follicular', 'ovulation'], role: 'The pituitary receptor that answers GnRH by releasing LH and FSH.',
             LoF: 'A less responsive receptor lowers LH and FSH release; strong loss stops the cycle.' },
    KISS1R: { day: 13, phases: ['ovulation'], role: 'Kisspeptin receptor: switches on GnRH pulses and the LH surge.',
              LoF: 'Weaker kisspeptin signalling can delay puberty and blunt the LH surge.', GoF: 'Stronger signalling is linked to earlier puberty.' },
    FSHB: { day: 3, phases: ['menses', 'follicular'], role: 'FSH beta subunit: FSH recruits and grows the follicles.',
            LoF: 'Less FSH: slower follicle growth and a longer follicular phase.', GoF: 'More FSH: faster follicle recruitment.' },
    FSHR: { day: 6, phases: ['follicular'], role: 'FSH receptor on the granulosa cells that line each follicle.',
            LoF: 'A less responsive receptor needs more FSH to grow follicles; this is linked to a slightly longer follicular phase and higher FSH.',
            GoF: 'A more responsive receptor grows follicles on less FSH.' },
    AMH: { day: 4, phases: ['follicular'], role: 'Made by small follicles; restrains how many are recruited each cycle. Its blood level tracks egg reserve.',
           LoF: 'Less AMH restraint lets follicles be used up faster.', GoF: 'More AMH holds back recruitment; high AMH is common in PCOS.' },
    AMHR2: { day: 4, phases: ['follicular'], role: 'The AMH receptor.', LoF: 'Weaker AMH restraint on follicle recruitment.' },
    GDF9: { day: 8, phases: ['follicular'], role: 'Egg-made signal that drives follicle growth.',
            LoF: 'Weaker signalling slows follicle growth; strong loss causes early ovarian failure.' },
    BMP15: { day: 8, phases: ['follicular'], role: 'Egg-made signal that sets how many follicles mature.',
             LoF: 'Weaker signalling slows follicle growth; strong loss causes early ovarian failure.', GoF: 'Linked in some studies to more than one follicle maturing.' },
    FOXL2: { day: 7, phases: ['follicular'], role: 'Keeps granulosa cells ovarian and paces follicle growth.',
             LoF: 'Faster follicle use; strong loss causes early ovarian failure.' },
    CYP17A1: { day: 10, phases: ['follicular'], role: 'Theca cells make androgens, the raw material for estradiol.',
               LoF: 'Less androgen supply can lower estradiol.', GoF: 'More androgen production is a PCOS feature.' },
    CYP19A1: { day: 12, phases: ['follicular', 'luteal'], role: 'Aromatase: turns androgens into estradiol in the growing follicle.',
               LoF: 'Less estradiol: a slower rise, a later or weaker LH surge and a thinner lining.', GoF: 'More estradiol: a stronger rise and higher estrogen exposure.' },
    HSD17B1: { day: 11, phases: ['follicular'], role: 'Converts estrone into the stronger estradiol.', LoF: 'Lower estradiol at the follicular peak.' },
    ESR1: { day: 12, phases: ['follicular', 'ovulation'], role: 'Estrogen receptor alpha: estradiol builds the lining and, at its peak, triggers the LH surge.',
            LoF: 'A weaker estrogen response: a thinner lining and a less certain surge.', GoF: 'A stronger estrogen response.' },
    ESR2: { day: 10, phases: ['follicular'], role: 'Estrogen receptor beta, important inside the follicle.',
            LoF: 'Weaker signalling can impair follicle maturation and ovulation.', GoF: 'Stronger estrogen signalling in the follicle.' },
    LHB: { day: 14, phases: ['ovulation'], role: 'LH beta subunit: the LH surge triggers ovulation.', LoF: 'A weaker LH surge can delay or prevent ovulation.' },
    LHCGR: { day: 14, phases: ['ovulation', 'luteal'], role: 'LH receptor: answers the surge to release the egg, then keeps the corpus luteum making progesterone.',
             LoF: 'A less responsive receptor can weaken ovulation and the luteal phase: shorter, with less progesterone.',
             GoF: 'A more responsive receptor; LHCGR variants are linked to PCOS in GWAS.' },
    PGR: { day: 20, phases: ['ovulation', 'luteal'], role: 'Progesterone receptor: needed to release the egg and to prepare the lining for implantation.',
           LoF: 'A weaker progesterone response: harder ovulation and a less receptive lining.', GoF: 'A stronger progesterone response: a more receptive lining.' },
    PTGS2: { day: 14, phases: ['ovulation', 'menses'], role: 'COX-2 makes prostaglandins that help the follicle rupture, and that drive menstrual cramps.',
             LoF: 'Less COX-2 can delay follicle rupture, as NSAIDs taken around ovulation can.' },
    STAR: { day: 17, phases: ['luteal'], role: 'Moves cholesterol into mitochondria: the first step of every steroid hormone.',
            LoF: 'Less steroid production overall, progesterone included.' },
    CYP11A1: { day: 17, phases: ['luteal'], role: 'First enzyme of steroid making: cholesterol to pregnenolone.', LoF: 'Less pregnenolone, so less progesterone downstream.' },
    HSD3B2: { day: 18, phases: ['luteal'], role: 'Turns pregnenolone into progesterone in the corpus luteum.', LoF: 'Lower progesterone in the luteal phase.' },
    HOXA10: { day: 21, phases: ['luteal'], role: 'Opens the implantation window in the lining.',
              LoF: 'A less receptive lining; linked to implantation failure and endometriosis.' },
    LIF: { day: 21, phases: ['luteal'], role: 'Signal from the lining that lets the embryo attach.', LoF: 'A less receptive lining at implantation.' },
    OXTR: { day: 2, phases: ['menses'], role: 'Oxytocin receptor in the uterine muscle: contractions at menstruation and birth.',
            LoF: 'Weaker contraction signalling in the uterus.', GoF: 'Stronger contraction signalling in the uterus.' },
    SHBG: { day: 9, phases: ['follicular', 'luteal'], role: 'Carries estradiol and testosterone in the blood; less SHBG means more free hormone.',
            LoF: 'More free testosterone and estradiol; low SHBG is common in PCOS.', GoF: 'Less free hormone.' },
  };
  // Other genes are placed by their Gene Ontology mechanism
  const MECH_PHASES = { eggs: ['follicular'], axis: ['follicular', 'ovulation'], hormones: ['follicular', 'luteal'], cycle: ['ovulation', 'luteal'],
                        implantation: ['luteal'], uterus: ['menses'], ovary: ['follicular'] };

  const drawCycle = (parent, s) => {
    const who = thWho(s);
    const sec = thMake(parent, 'div', 'th-cycle');
    thMake(sec, 'h3', null, 'The 28-day cycle');
    thMake(sec, 'p', 'gx-note', `Typical hormone shapes across a 28-day cycle: textbook curves, not ${who}'s measured levels. Dots mark ` +
      `the day each of ${who}'s changed genes does its main work; hover a dot, a phase or a gene for what it means for the cycle.`);
    const box = thMake(sec, 'div', 'th-cycle-svg');
    // Drawn at the container's own width, 1:1, so it lines up with the phase columns below and follows resizes
    const W = Math.max(320, Math.round(box.clientWidth || 760)), H = 270, L = 34, R = 12, T = 34, CH = 150, LT = T + CH + 18, LH = 40;
    const x = d3.scaleLinear([1, 28], [L, W - R]);
    const y = d3.scaleLinear([0, 1], [T + CH, T + 6]);
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H)
      .attr('role', 'img').attr('aria-label', 'Hormone levels across a typical 28-day cycle, with the genes that act on each day');
    const tip = gx.tip(box);
    const callOf = (name) => { const g = s.byName.get(name); return g ? thCall(g) : null; };
    const effect = (name) => {
      const info = CYCLE_GENES[name] || {}, g = s.byName.get(name), fn = g && thCall(g);
      const lines = [info.role || ''];
      if (g && g.genotype) lines.push(`${who}: ${g.genotype}, ${TH_TEXT[fn]}${g.dose && fn !== 'normal' ? ` ×${g.dose}` : ''} (${g.interpretation})`);
      else if (g && g.carried) lines.push(`${who} carries ${g.carried} trait-linked ${g.carried === 1 ? 'allele' : 'alleles'} here`);
      else lines.push(`No ${who} call at this gene`);
      if (fn === 'LoF' && info.LoF) lines.push('What it can mean: ' + info.LoF);
      if (fn === 'GoF' && info.GoF) lines.push('What it can mean: ' + info.GoF);
      return lines.filter(Boolean);
    };

    // Phase bands and the implantation window
    for (const p of CYCLE_PHASES.filter((p) => p.id !== 'follicular')) {
      svg.append('rect').attr('x', x(p.from)).attr('width', x(p.to) - x(p.from)).attr('y', T).attr('height', CH + 18 + LH)
        .attr('class', 'th-cy-band th-cy-' + p.id)
        .on('mousemove', (event) => tip.show(event, `${p.name} · days ${p.from}–${p.to}`, [p.what]))
        .on('mouseleave', () => tip.hide());
    }
    svg.append('text').attr('x', (x(19) + x(24)) / 2).attr('y', LT - 4).attr('text-anchor', 'middle').attr('class', 'th-cap').text('implantation window');
    svg.append('rect').attr('x', x(19)).attr('width', x(24) - x(19)).attr('y', LT).attr('height', LH).attr('class', 'th-cy-window')
      .on('mousemove', (event) => tip.show(event, 'Implantation window · days 19–24', ['The lining is receptive to an embryo for a few days under progesterone.']))
      .on('mouseleave', () => tip.hide());
    for (const p of CYCLE_PHASES) {
      const mid = p.id === 'follicular' ? x(8) : (x(p.from) + x(p.to)) / 2;
      svg.append('text').attr('x', mid).attr('y', 16).attr('text-anchor', 'middle').attr('class', 'th-cap').text(p.name.toUpperCase());
    }
    svg.append('line').attr('x1', x(1)).attr('x2', x(13)).attr('y1', 22).attr('y2', 22).attr('class', 'th-leader');
    svg.append('line').attr('x1', x(15)).attr('x2', x(28)).attr('y1', 22).attr('y2', 22).attr('class', 'th-leader');

    // Hormone curves
    const line = d3.line().x((d) => x(d[0])).y((d) => y(d[1])).curve(d3.curveMonotoneX);
    CYCLE_HORMONES.forEach((h, i) => {
      const color = dash.colors[i % dash.colors.length];
      svg.append('path').attr('d', line(h.pts)).attr('class', 'th-cy-line').style('stroke', color);
      const peak = h.pts.reduce((a, b) => (b[1] > a[1] ? b : a));
      svg.append('text').attr('x', x(peak[0]) + (h.id === 'LH' ? 8 : 0)).attr('y', y(peak[1]) - 6).attr('text-anchor', h.id === 'LH' ? 'start' : 'middle')
        .attr('class', 'th-cy-hlabel').style('fill', color).text(h.id);
    });
    // The lining
    svg.append('text').attr('x', 4).attr('y', LT + LH / 2 + 4).attr('class', 'th-cap').text('Lining');
    svg.append('path').attr('class', 'th-cy-lining')
      .attr('d', d3.area().x((d) => x(d[0])).y0(LT + LH).y1((d) => LT + LH - d[1] * LH).curve(d3.curveMonotoneX)(CYCLE_LINING))
      .on('mousemove', (event) => tip.show(event, 'Endometrium', ['Sheds at menstruation, rebuilds under estradiol, and matures under progesterone.']))
      .on('mouseleave', () => tip.hide());
    // Day axis
    for (const d of [1, 7, 14, 21, 28]) {
      svg.append('text').attr('x', x(d)).attr('y', H - 4).attr('text-anchor', d === 1 ? 'start' : d === 28 ? 'end' : 'middle').attr('class', 'th-cap').text(`day ${d}`);
    }

    // The person's changed genes on the day they act
    const changed = Object.keys(CYCLE_GENES).filter((n) => ['LoF', 'GoF', 'altered', 'variant'].includes(callOf(n)));
    const lane = new Map();
    for (const n of changed.sort((a, b) => CYCLE_GENES[a].day - CYCLE_GENES[b].day)) {
      const d = CYCLE_GENES[n].day, k = lane.get(d) || 0;
      lane.set(d, k + 1);
      const fn = callOf(n), cx = x(d) + (k % 2 ? 9 : 0) * (k ? 1 : 0), cy = T + 12 + k * 15;
      const g = svg.append('g').attr('class', 'th-cy-gene').attr('transform', `translate(${cx},${cy})`).attr('tabindex', 0).attr('role', 'button')
        .attr('aria-label', `${n}: ${effect(n).join(' ')}`)
        .on('mousemove', (event) => tip.show(event, `${n} · day ${d}`, effect(n)))
        .on('mouseleave', () => tip.hide())
        .on('click', () => thPick(n));
      g.append('circle').attr('r', 5.5).style('fill', TH_FILL[fn]).style('stroke', 'var(--color-bg)').attr('stroke-width', 1.5);
      g.append('text').attr('x', 8).attr('y', 4).attr('class', 'th-cy-glabel').text(n);
    }

    // One column per phase: what happens, and the person's genes there
    const cols = thMake(sec, 'div', 'th-cycle-cols');
    for (const p of CYCLE_PHASES) {
      const col = thMake(cols, 'div', 'th-cycle-col th-cy-col-' + p.id);
      thMake(col, 'b', null, `${p.name} · days ${p.from}–${p.to}`);
      thMake(col, 'p', 'gx-note', p.what);
      const key = Object.keys(CYCLE_GENES).filter((n) => CYCLE_GENES[n].phases.includes(p.id));
      const fromMech = s.shown.filter((g) => !CYCLE_GENES[g.gene] && (g.ev.organs || []).some((o) => o === 'ovaries' || o === 'endometrium' || o === 'uterus' || o === 'pituitary')
        && Object.keys(g.ev.mechanisms || {}).some((m) => (MECH_PHASES[m] || []).includes(p.id))).map((g) => g.gene);
      const chips = thMake(col, 'div', 'th-genes');
      const rank = { GoF: 0, LoF: 1, altered: 2, variant: 3, normal: 4 };
      for (const n of [...key, ...fromMech].sort((a, b) => (rank[callOf(a)] ?? 5) - (rank[callOf(b)] ?? 5))) {
        const g = s.byName.get(n), fn = g && thCall(g);
        const b = thMake(chips, 'button', 'lc-chip th-gene ' + (fn ? 'lc-' + TH_CLASS[fn] : 'lc-untested'), g ? thLabel(g) : n);
        b.type = 'button';
        b.addEventListener('mousemove', (event) => tip.show(event, n, CYCLE_GENES[n] ? effect(n) : [g && g.interpretation ? `${who}: ${g.interpretation}` : `No ${who} call here`]));
        b.addEventListener('mouseleave', () => tip.hide());
        b.addEventListener('click', () => thPick(n));
      }
      const notes = key.filter((n) => ['LoF', 'GoF'].includes(callOf(n)) && CYCLE_GENES[n][callOf(n)]);
      if (notes.length) {
        const ul = thMake(col, 'ul', 'th-why');
        for (const n of notes) {
          const g = s.byName.get(n);
          const li = thMake(ul, 'li');
          thMake(li, 'b', null, `${n} ${TH_TEXT[callOf(n)]}${g.dose ? ` ×${g.dose}` : ''}: `);
          li.append(CYCLE_GENES[n][callOf(n)]);
        }
      }
    }
  };

  // Body map: where a theme's genes act, shaded by the person's calls. Female (XX) layout: a body outline with brain and
  // pituitary, and a front view of the reproductive organs. Each organ is a button that narrows the page to its genes.
  const XX_SHAPES = {
    brain: { shapes: [{ ellipse: [120, 54, 29, 19] }], label: [178, 42, 'start'], to: [146, 50] },
    pituitary: { shapes: [{ circle: [124, 80, 6] }], label: [178, 94, 'start'], to: [131, 82] },
    tubes: { shapes: [{ stroke: 'M404,166 C372,142 330,128 300,150 C288,160 284,176 290,186' },
                      { stroke: 'M536,166 C568,142 610,128 640,150 C652,160 656,176 650,186' }], label: [470, 92, 'middle'], to: [470, 132] },
    ovaries: { shapes: [{ ellipse: [300, 214, 30, 18, -18] }, { ellipse: [640, 214, 30, 18, 18] }], label: [300, 258, 'middle'], to: [300, 233] },
    uterus: { shapes: [{ path: 'M400,172 C400,128 540,128 540,172 C540,232 506,276 490,298 L490,382 L450,382 L450,298 C434,276 400,232 400,172 Z' }],
              label: [566, 300, 'start'], to: [522, 240] },
    endometrium: { shapes: [{ path: 'M426,168 C444,156 496,156 514,168 C504,212 482,246 470,264 C458,246 436,212 426,168 Z' }],
                   label: [566, 362, 'start'], to: [480, 228] },
  };
  const XX_BODY = 'M106,100 L104,114 C72,120 54,136 52,172 L60,262 C64,300 72,330 82,362 L158,362 C168,330 176,300 180,262 ' +
                  'L188,172 C186,136 168,120 136,114 L134,100 Z';

  dash.draw('th-body', (el) => {
    el.replaceChildren();
    const s = thSel();
    if (!s) { if (gx.failed('theme_meta', 'theme_genes')) gx.failLine(el); return; }
    if (!s.organs.length) {
      thMake(el, 'p', 'gx-note', 'This theme has no map yet. The fertility themes have a body map (female XX, male XY) and cancer has the life of a cell.');
      return;
    }
    const who = thWho(s);
    const male = s.stats.sex === 'XY';
    const cell = s.stats.view === 'cell';
    const SHAPES = cell ? CELL_SHAPES() : male ? XY_SHAPES : XX_SHAPES;
    const unit = cell ? 'stage' : 'organ';
    const card = el.closest('.gx-card');
    if (card) {
      const h = card.querySelector('h2'), note = card.querySelector('.gx-note');
      if (h) h.textContent = cell ? 'Life of a cell' : 'Body map';
      if (note) note.textContent = cell
        ? 'The stages every cell lives through, and where the theme\'s genes act in them. Cancer starts when a cell slips past the ' +
          'checkpoints, repair, ageing and death. Select a stage to narrow the mechanisms, connections and gene panel to it.'
        : 'Where in the body the theme\'s genes act. Each gene is placed by its mechanisms and the conditions it is linked to. ' +
          'Select an organ to narrow the mechanisms, connections and gene panel to it.';
    }

    const per = new Map(s.organs.map((o) => [o.id, { o, all: 0, lof: 0, gof: 0, variant: 0, genes: [] }]));
    for (const g of s.genes) {
      for (const id of g.ev.organs || []) {
        const c = per.get(id);
        if (!c) continue;
        c.all += 1;
        const fn = thCall(g);
        if (fn === 'LoF') c.lof += 1; else if (fn === 'GoF') c.gof += 1; else if (fn === 'variant') c.variant += 1;
        if (g.notable) c.genes.push(g);
      }
    }
    const signal = (c) => c.lof + c.gof + c.variant;
    const maxSig = d3.max([...per.values()], signal) || 1;
    const hueOf = (c) => c.lof > c.gof ? 'var(--color-bad)' : c.gof > c.lof ? 'var(--gof)' : 'var(--color-fg-muted)';
    const tint = (c) => `color-mix(in srgb, ${hueOf(c)} ${Math.round(18 + 42 * signal(c) / maxSig)}%, var(--color-panel))`;
    const edge = (c) => `color-mix(in srgb, ${hueOf(c)} 75%, var(--color-fg))`;

    const grid = thMake(el, 'div', 'th-body-grid');
    const box = thMake(grid, 'div', 'th-body-svg');
    const info = thMake(grid, 'div', 'th-organ');
    const svg = d3.select(box).append('svg').attr('viewBox', '0 0 760 432').attr('width', '100%')
      .attr('role', 'group').attr('aria-label', `${s.theme.theme_name}: organs`);
    const tip = gx.tip(box);

    // Body outline and the zoom from the pelvis to the organ view; the cell map draws its paths instead
    if (cell) drawCellPaths(svg);
    else {
    svg.append('circle').attr('cx', 120).attr('cy', 62).attr('r', 40).attr('class', 'th-outline');
    svg.append('path').attr('d', male ? XY_BODY : XX_BODY).attr('class', 'th-outline');
    if (male) {
      for (const cx of XY_CONTEXT) {
        if (cx.ellipse) {
          svg.append('ellipse').attr('cx', cx.ellipse[0]).attr('cy', cx.ellipse[1]).attr('rx', cx.ellipse[2]).attr('ry', cx.ellipse[3]).attr('class', 'th-context');
          svg.append('text').attr('x', cx.ellipse[0]).attr('y', cx.ellipse[1] + 4).attr('text-anchor', 'middle').attr('class', 'th-cap').text(cx.name);
        } else svg.append('path').attr('d', cx.path).attr('class', 'th-context');
      }
    }
    svg.append('rect').attr('x', 94).attr('y', 268).attr('width', 52).attr('height', 50).attr('rx', 6).attr('class', 'th-zoom');
    svg.append('path').attr('d', 'M146,268 L262,120 M146,318 L262,400').attr('class', 'th-zoom');
    svg.append('text').attr('x', 120).attr('y', 398).attr('text-anchor', 'middle').attr('class', 'th-cap').text(`${s.stats.sex || ''} · ${who}`);
    }

    for (const [id, shape] of Object.entries(SHAPES)) {
      const c = per.get(id);
      if (!c) continue;
      const selected = s.organ && s.organ.id === id;
      const g = svg.append('g').attr('class', 'th-organ-hit' + (selected ? ' is-selected' : '')).attr('tabindex', 0).attr('role', 'button')
        .attr('aria-pressed', String(!!selected))
        .attr('aria-label', `${c.o.name}: ${c.all} genes, ${c.lof} less active, ${c.gof} more active, ${c.variant} with carried variants`)
        .on('click', () => dash.setParams({ th_organ: selected ? null : id, th_gene: null }))
        .on('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); dash.setParams({ th_organ: selected ? null : id, th_gene: null }); } })
        .on('mousemove', (event) => tip.show(event, c.o.name, [c.o.about, `${c.all} genes; ${who}: ${c.lof} less active, ${c.gof} more active, ` +
          `${c.variant} with a carried variant`, selected ? `Select again to show all ${unit}s` : `Select to focus the page on this ${unit}`]))
        .on('mouseleave', () => tip.hide());
      for (const sh of shape.shapes) {
        let node;
        if (sh.ellipse) {
          const [cx, cy, rx, ry, rot] = sh.ellipse;
          node = g.append('ellipse').attr('cx', cx).attr('cy', cy).attr('rx', rx).attr('ry', ry)
            .attr('transform', rot ? `rotate(${rot} ${cx} ${cy})` : null);
        } else if (sh.circle) {
          node = g.append('circle').attr('cx', sh.circle[0]).attr('cy', sh.circle[1]).attr('r', sh.circle[2]);
        } else if (sh.stroke) {
          // Tubes are lines: a wide invisible hit area under a coloured stroke
          g.append('path').attr('d', sh.stroke).attr('class', 'th-hit');
          node = g.append('path').attr('d', sh.stroke).attr('class', 'th-tube').style('stroke', tint(c));
          continue;
        } else node = g.append('path').attr('d', sh.path).attr('transform', sh.at ? `translate(${sh.at})` : null);
        node.attr('class', 'th-shape' + (sh.cls ? ' ' + sh.cls : '')).style('fill', tint(c)).style('stroke', edge(c));
      }
      const [lx, ly, anchor] = shape.label;
      if (shape.to) svg.append('line').attr('x1', shape.to[0]).attr('y1', shape.to[1])
        .attr('x2', anchor === 'start' ? lx - 6 : anchor === 'end' ? lx + 6 : lx).attr('y2', anchor === 'middle' && ly < shape.to[1] ? ly + 20 : ly - 4).attr('class', 'th-leader');
      const t = svg.append('text').attr('x', lx).attr('y', ly).attr('text-anchor', anchor).attr('class', 'th-label' + (selected ? ' is-selected' : ''));
      t.append('tspan').text(c.o.name);
      const sub = svg.append('text').attr('x', lx).attr('y', ly + 15).attr('text-anchor', anchor).attr('class', 'th-cap');
      sub.append('tspan').text(`${c.all} genes`);
      if (c.lof) sub.append('tspan').attr('class', 'th-c-lof').text(` · ▼${c.lof}`);
      if (c.gof) sub.append('tspan').attr('class', 'th-c-gof').text(` · ▲${c.gof}`);
      if (c.variant) sub.append('tspan').text(` · ●${c.variant}`);
    }

    if (cell) drawCellLetters(svg);
    // Female theme: the 28-day cycle sits under the organs
    if (s.stats.sex === 'XX') drawCycle(el, s);

    // Side panel: the selected organ, or how to read the map
    const o = s.organ;
    if (!o) {
      thMake(info, 'h3', null, `All ${unit}s`);
      thMake(info, 'p', 'gx-note', `▼ less active and ▲ more active are ${who}'s library calls; ● counts genes where ${who} carries an allele ` +
        `that a GWAS or ClinVar links to one of the theme's conditions. Shading is stronger where more of these gather, red where less-active genes ` +
        `lead and blue where more-active ones do. Select ${cell ? 'a stage' : 'an organ'} to focus the page on it.`);
      const list = thMake(info, 'div', 'th-genes');
      for (const c of [...per.values()].sort((a, b) => signal(b) - signal(a))) {
        const b = thMake(list, 'button', 'lc-chip th-gene', `${c.o.name} · ${signal(c)}`);
        b.type = 'button';
        b.addEventListener('click', () => dash.setParams({ th_organ: c.o.id, th_gene: null }));
      }
      return;
    }
    const c = per.get(o.id);
    thMake(info, 'h3', null, o.name);
    thMake(info, 'p', null, o.about);
    thMake(info, 'p', 'gx-note', `${c.all} genes act here. ${who}: ${c.lof} less active, ${c.gof} more active, ${c.variant} with a carried trait-linked variant.`);
    const mechs = s.facets.filter((f) => f.organ === o.id).map((f) => f.facet_name);
    if (mechs.length) { thMake(info, 'span', 'gx-label', 'Mechanisms'); thMake(info, 'p', null, mechs.join(', ')); }
    const ds = Object.entries(s.stats.disease_organs || {}).filter(([, v]) => v === o.id).map(([k]) => k);
    if (ds.length) { thMake(info, 'span', 'gx-label', 'Conditions'); thMake(info, 'p', null, ds.join(', ')); }
    thMake(info, 'span', 'gx-label', `Notable genes (${c.genes.length})`);
    const chips = thMake(info, 'div', 'th-genes');
    const rank = { LoF: 0, GoF: 1, altered: 2, variant: 3, normal: 4 };
    for (const g of c.genes.sort((a, b) => (rank[thCall(a)] ?? 5) - (rank[thCall(b)] ?? 5) || (b.carried || 0) - (a.carried || 0)).slice(0, 40)) {
      const fn = thCall(g);
      const b = thMake(chips, 'button', 'lc-chip th-gene ' + (fn ? 'lc-' + TH_CLASS[fn] : 'lc-untested'), thLabel(g));
      b.type = 'button';
      b.addEventListener('click', () => thPick(g.gene));
    }
    const all = thMake(info, 'button', 'lc-btn', `Show all ${unit}s`);
    all.type = 'button';
    all.addEventListener('click', () => dash.setParams({ th_organ: null, th_gene: null }));
  });


  // Cancer theme: the life of a cell. The cell cycle is a ring (G1, S, G2, M) with its checkpoint gates; resting, stress,
  // ageing, death and escape sit around it. Each stage is a button that narrows the page, like the organs on the body maps.
  const CELL_C = [300, 214];
  const cellPt = (deg, r) => [CELL_C[0] + r * Math.sin(deg * Math.PI / 180), CELL_C[1] - r * Math.cos(deg * Math.PI / 180)];
  const cellArc = (a, b, r0 = 92, r1 = 128) => ({ path: d3.arc()({ innerRadius: r0, outerRadius: r1, startAngle: a * Math.PI / 180,
    endAngle: b * Math.PI / 180 }), at: CELL_C });
  const CELL_SHAPES = () => ({
    lives: { shapes: [cellArc(200, 340), { ellipse: [78, 214, 76, 34] }], label: [78, 212, 'middle'] },
    birth: { shapes: [cellArc(340, 440), cellArc(440, 490), cellArc(490, 560)], label: [300, 206, 'middle'] },
    checks: { shapes: [cellArc(336, 344, 82, 138), cellArc(486, 494, 82, 138), cellArc(521, 529, 82, 138)],
              label: [206, 46, 'middle'], to: cellPt(340, 138) },
    stress: { shapes: [{ ellipse: [604, 70, 92, 34] }], label: [604, 68, 'middle'] },
    ages: { shapes: [{ ellipse: [640, 214, 92, 34] }], label: [640, 212, 'middle'] },
    dies: { shapes: [{ ellipse: [604, 358, 92, 34] }], label: [604, 356, 'middle'] },
    escape: { shapes: [{ ellipse: [112, 366, 96, 34], cls: 'th-escape' }], label: [112, 364, 'middle'] },
  });
  const drawCellPaths = (svg) => {
    const defs = svg.append('defs');
    defs.append('marker').attr('id', 'th-cell-arrow').attr('viewBox', '0 0 10 10').attr('refX', 9).attr('refY', 5)
      .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto')
      .append('path').attr('d', 'M0,0 L10,5 L0,10 z').style('fill', 'var(--color-fg-muted)');
    const arrow = (d, text, tx, ty, anchor = 'middle', cls = 'th-cell-path') => {
      svg.append('path').attr('d', d).attr('class', cls).attr('marker-end', 'url(#th-cell-arrow)');
      if (text) svg.append('text').attr('x', tx).attr('y', ty).attr('text-anchor', anchor).attr('class', 'th-cap').text(text);
    };
    const [sx, sy] = cellPt(30, 132), [ax, ay] = cellPt(90, 132), [dx, dy] = cellPt(150, 132), [ex, ey] = cellPt(222, 132);
    arrow(`M${sx},${sy} Q470,70 508,72`, 'damage: repair, or stop', 452, 60);
    arrow(`M${ax},${ay} L544,214`, 'wear', 490, 206);
    arrow(`M${dx},${dy} Q470,358 508,358`, 'beyond repair', 452, 374);
    arrow('M640,250 Q646,290 626,322', 'cleared', 650, 290, 'start');
    arrow('M156,202 L170,202', null);
    arrow('M170,226 L156,226', null);
    svg.append('text').attr('x', 160).attr('y', 262).attr('text-anchor', 'middle').attr('class', 'th-cap').text('signals');
    arrow(`M${ex},${ey} Q190,320 168,334`, null, 0, 0, 'middle', 'th-cell-path th-cell-fail');
    svg.append('text').attr('x', 112).attr('y', 418).attr('text-anchor', 'middle').attr('class', 'th-cap')
      .text('when checks, repair and death all fail');
  };
  const drawCellLetters = (svg) => {
    for (const [txt, deg] of [['G1', 270], ['S', 390], ['G2', 465], ['M', 525]]) {
      const [x, y] = cellPt(deg, 110);
      svg.append('text').attr('x', x).attr('y', y + 4).attr('text-anchor', 'middle').attr('class', 'th-cell-phase').text(txt);
    }
    svg.append('text').attr('x', 300).attr('y', 246).attr('text-anchor', 'middle').attr('class', 'th-cap').text('one turn ≈ a day in fast tissue');
  };

  // Mechanism in depth: what it does, what the person carries in it, and every gene behind it
  const XY_SHAPES = {
    brain: { shapes: [{ ellipse: [120, 54, 29, 19] }], label: [178, 42, 'start'], to: [146, 50] },
    pituitary: { shapes: [{ circle: [124, 80, 6] }], label: [178, 94, 'start'], to: [131, 82] },
    prostate: { shapes: [{ ellipse: [470, 205, 28, 18] }, { ellipse: [428, 178, 20, 9, -35] }, { ellipse: [512, 178, 20, 9, 35] }],
                label: [566, 190, 'start'], to: [498, 200] },
    penis: { shapes: [{ path: 'M458,224 L458,318 C458,342 482,342 482,318 L482,224 Z' }], label: [566, 262, 'start'], to: [484, 268] },
    testes: { shapes: [{ ellipse: [418, 330, 20, 27] }, { ellipse: [522, 330, 20, 27] }], label: [566, 340, 'start'], to: [544, 334] },
    epididymis: { shapes: [{ stroke: 'M402,312 C392,326 394,350 408,358' }, { stroke: 'M538,312 C548,326 546,350 532,358' },
                           { stroke: 'M418,303 C404,262 392,196 420,166 C436,150 452,176 458,196' },
                           { stroke: 'M522,303 C536,262 548,196 520,166 C504,150 488,176 482,196' }],
                  label: [380, 240, 'end'], to: [400, 246] },
  };
  const XY_BODY = 'M104,100 L102,114 C62,118 42,134 42,172 L54,262 C58,300 66,330 78,362 L162,362 C174,330 182,300 186,262 ' +
                  'L198,172 C198,134 178,118 138,114 L136,100 Z';
  const XY_CONTEXT = [{ ellipse: [470, 148, 50, 36], name: 'bladder' }, { path: 'M394,304 C382,352 404,374 470,374 C536,374 558,352 546,304' }];

  const thFacetOpen = (id) => {
    dash.setParams({ th_facet: id });
    document.querySelectorAll('#theme-facet').forEach((c) => c.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };

  dash.draw('th-facet', (el) => {
    el.replaceChildren();
    const s = thSel();
    const pr = gx.rows('theme_pathways');
    if (!s || !pr) { if (gx.failed('theme_meta', 'theme_genes', 'theme_pathways')) gx.failLine(el); return; }
    const f = s.facets.find((x) => x.facet === dash.params().th_facet);
    if (!f) { thMake(el, 'p', 'gx-note', 'Select a mechanism box above to open it here: what it does, how it works, what the person carries in it, and every gene behind it.'); return; }
    const who = s.api ? thWho(s) : 'XY';
    const genes = s.genes.filter((g) => g.fl.includes(f.facet));
    const head = thMake(el, 'div', 'lc-name');
    thMake(head, 'h3', null, f.facet_name);
    const organ = (s.organs || []).find((o) => o.id === f.organ);
    if (organ) {
      const b = thMake(head, 'button', 'lc-chip th-gene', organ.name);
      b.type = 'button';
      b.title = 'Show this organ on the body map';
      b.addEventListener('click', () => dash.setParams({ th_organ: organ.id }));
    }
    const close = thMake(head, 'button', 'lc-btn', 'Close');
    close.type = 'button';
    close.addEventListener('click', () => dash.setParams({ th_facet: null }));
    if (f.facet_about) thMake(el, 'p', 'gx-muted', f.facet_about);
    if (f.facet_explain) { thMake(el, 'span', 'gx-label', 'How it works'); thMake(el, 'p', 'th-explain', f.facet_explain); }

    // What the person carries here
    const changed = genes.filter((g) => ['LoF', 'GoF', 'altered'].includes(thCall(g)));
    const carriers = genes.filter((g) => thCall(g) === 'variant');
    thMake(el, 'span', 'gx-label', `What ${who} carries here`);
    const parts = thBalance(el, genes, s.api ? 'without a finding' : 'not genotyped');
    thMake(el, 'p', null, `${genes.length} genes. ${parts.join(', ')}.`);
    if (changed.length) {
      const ul = thMake(el, 'ul', 'th-why');
      for (const g of changed) {
        const li = thMake(ul, 'li');
        const b = thMake(li, 'button', 'lc-link', g.gene);
        b.type = 'button'; b.addEventListener('click', () => thPick(g.gene));
        li.append(` ${g.genotype}: ${TH_TEXT[thCall(g)]}${g.dose && g.function !== 'normal' ? ` ×${g.dose}` : ''}. ${g.interpretation || ''}`);
      }
    }
    if (carriers.length) {
      thMake(el, 'p', 'gx-note', `${who} carries trait-linked alleles in ${carriers.length} more ${carriers.length === 1 ? 'gene' : 'genes'} here: ` +
        carriers.sort((a, b) => b.carried - a.carried).slice(0, 12).map((g) => `${g.gene} (${g.carried})`).join(', ') +
        (carriers.length > 12 ? ', …' : '') + '. Select one to see the variants.');
    }
    if (!changed.length && !carriers.length) thMake(el, 'p', 'gx-note', `${who} has no library call and no carried trait-linked allele in this mechanism's genes.`);

    // Conditions, evidence strength and pathways (API themes)
    if (s.api) {
      const cond = new Map();
      for (const g of genes) for (const [d, v] of Object.entries(g.ev.diseases || {})) if (v.score >= 0.3) cond.set(d, (cond.get(d) || 0) + 1);
      if (cond.size) {
        thMake(el, 'span', 'gx-label', 'Conditions its genes are linked to');
        thMake(el, 'p', null, [...cond].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([d, n]) => `${d} (${n})`).join(', '));
      }
      const evid = d3.rollup(genes.filter((g) => g.ev.mechanisms && g.ev.mechanisms[f.facet]), (v) => v.length, (g) => g.ev.mechanisms[f.facet].evidence);
      if (evid.size) {
        thMake(el, 'span', 'gx-label', 'How we know (Gene Ontology evidence)');
        thMake(el, 'p', null, [...evid].map(([k, n]) => `${n} ${k}`).join(', ') + '.');
      }
    }
    const names = new Set(genes.map((g) => g.gene));
    const pws = pr[0].filter((p) => p.theme === s.theme.theme).map((p) => ({ ...p, hit: JSON.parse(p.genes).filter((x) => names.has(x)) }))
      .filter((p) => p.hit.length >= 2).sort((a, b) => b.on_theme - a.on_theme || b.hit.length - a.hit.length).slice(0, 6);
    if (pws.length) {
      thMake(el, 'span', 'gx-label', 'Pathways it runs through');
      const pl = thMake(el, 'ul', 'lc-alts');
      for (const p of pws) thMake(pl, 'li', null, `${p.pathway} (${p.hit.join(', ')})`);
    }

    // Every gene, the person's changes first
    thMake(el, 'span', 'gx-label', `All ${genes.length} genes`);
    const rank = { LoF: 0, GoF: 1, altered: 2, variant: 3, normal: 4 };
    const sorted = [...genes].sort((a, b) => (rank[thCall(a)] ?? 5) - (rank[thCall(b)] ?? 5) || (b.carried || 0) - (a.carried || 0) ||
      (b.best_score || 0) - (a.best_score || 0) || a.gene.localeCompare(b.gene));
    const table = (rows, parent) => {
      const box = thMake(parent, 'div', 'gx-table-box');
      const t = thMake(box, 'table', 'gx-table');
      const hr = thMake(thMake(t, 'thead'), 'tr');
      for (const h of ['Gene', who, s.api ? 'Carried alleles' : 'Evidence', s.api ? 'Strongest condition link' : '', s.api ? 'GO evidence' : ''].filter(Boolean)) thMake(hr, 'th', null, h);
      const tb = thMake(t, 'tbody');
      for (const g of rows) {
        const tr = thMake(tb, 'tr');
        const td = thMake(tr, 'td');
        const b = thMake(td, 'button', 'lc-link', g.gene);
        b.type = 'button'; b.addEventListener('click', () => thPick(g.gene));
        const fn = thCall(g);
        const c = thMake(tr, 'td', null, fn ? `${g.genotype ? g.genotype + ' · ' : ''}${TH_TEXT[fn]}${g.dose && g.function !== 'normal' ? ` ×${g.dose}` : ''}` : '—');
        if (fn) c.style.boxShadow = `inset 3px 0 0 ${TH_FILL[fn]}`;
        if (s.api) {
          thMake(tr, 'td', null, g.carried ? String(g.carried) : '—');
          const best = Object.entries(g.ev.diseases || {}).sort((a, b) => b[1].score - a[1].score)[0];
          thMake(tr, 'td', null, best ? `${best[0]} (${d3.format('.2f')(best[1].score)})` : '—');
          thMake(tr, 'td', 'gx-muted', (g.ev.mechanisms && g.ev.mechanisms[f.facet]) ? g.ev.mechanisms[f.facet].evidence : 'disease link');
        } else thMake(tr, 'td', 'gx-muted', [...new Set((g.ev[f.facet] || []).map((e) => e.source))].join(', '));
      }
    };
    table(sorted.slice(0, 30), el);
    if (sorted.length > 30) {
      const det = thMake(el, 'details');
      thMake(det, 'summary', 'gx-note', `Show the other ${sorted.length - 30} genes`);
      table(sorted.slice(30), det);
    }
  });
