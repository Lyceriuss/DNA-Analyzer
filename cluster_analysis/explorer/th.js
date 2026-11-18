  // Theme clusters: picker, XY balance, mechanism map, connection network, gene detail and shared pathways
  const TH_TEXT = { LoF: 'less active', GoF: 'more active', altered: 'changed, direction unclear', normal: 'typical function',
                    variant: 'carries a trait-linked variant' };
  const TH_CLASS = { LoF: 'lof', GoF: 'gof', altered: 'alt', normal: 'norm', variant: 'var', unknown: 'untested' };
  TH_TEXT.unknown = 'no known effect on the gene';
  // Labels come from evidence about the variant (evidence_call.py); the wording follows what kind of evidence it is
  // What the evidence call means for the person (genotype_effects.py): positive / negative from the library's polarity
  const TH_OUTCOME = { positive: 'positive', negative: 'negative', neutral: 'neither good nor bad',
    unclear: 'whether this is good or bad is unclear', typical: 'typical', unknown: 'unknown' };
  const TH_BASIS = { cpic: 'CPIC allele function', measured: 'measured protein function, MaveDB', curated: 'curated protein effect, UniProt',
    truncating: 'the change cuts the protein short', predicted: 'predicted damage, SIFT and PolyPhen', expression: 'gene expression, GTEx',
    none: 'no evidence about function' };
  const thFnText = (g, fn) => g && g.basis === 'expression' && (fn === 'GoF' || fn === 'LoF') ? (fn === 'GoF' ? 'more expressed' : 'less expressed')
    : g && g.basis === 'predicted' && fn === 'LoF' ? 'likely less active' : TH_TEXT[fn];
  const TH_FILL = { LoF: 'var(--color-bad)', GoF: 'var(--gof)', altered: 'var(--color-fg)', normal: 'var(--typical)',
                    variant: 'var(--color-fg-muted)', unknown: 'var(--color-panel)' };
  const thMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  // Library genes carry a function call; API-theme genes outside the library are marked when XY carries a trait-linked allele
  // A gene's call: the library's at its SNP, or gene_calls.py's from the person's own variants (call_source 'api')
  const thCall = (g) => g.genotype || (g.call_source === 'api' && g.function) ? (g.function || 'normal') : g.carried > 0 ? 'variant' : null;
  const thNote = (g) => g && (g.interpretation || g.fn_evidence);
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
  const thFinding = (parent, f, it, who = gx.who()) => {
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
    } else d.append(`${f.rsid} ${f.genotype}: ${it.what}${/[.!?]$/.test(it.what) ? "" : "."}`);
  };

  // The theme on screen: the one picked, or the first when none is (other parts' cards follow it: fitness, cancer risk)
  gx.theme = () => {
    const r = gx.rows('theme_meta');
    const themes = r ? [...new Map(r[0].map((m) => [m.theme, m])).values()].sort((a, b) => a.theme_order - b.theme_order) : [];
    const p = dash.params().theme;
    if (p === 'nutrition') return p;
    return (themes.find((t) => t.theme === p) || themes[0] || {}).theme || p;
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
    // An API theme lists every gene but draws the notable ones: a call with an effect or a library call, a carried finding or a strong disease link
    const shown = (api ? genes.filter((g) => g.notable) : genes).filter(inOrgan);
    const byName = new Map(genes.map((g) => [g.gene, g]));
    // Default selection: the first changed gene, so the panel opens on something XY carries
    const order = (g) => (g.primary === 'disease' ? 4 : 0) + (g.function === 'LoF' || g.function === 'GoF' ? 0 : g.carried > 0 ? 1 : g.genotype ? 2 : 3);
    const fallback = [...shown].sort((a, b) => order(a) - order(b) || (b.carried || 0) - (a.carried || 0) || a.gene.localeCompare(b.gene))[0];
    const gene = byName.get(p.th_gene) || fallback;
    return { themes, theme, facets, genes, shown, byName, gene, api, stats, organs, organ, inOrgan };
  };
  const thPick = (gene) => dash.setParams({ th_gene: gene });
  const thWho = (s) => (s && s.stats && s.stats.person) || gx.who();

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
      // The profile switcher picks the person, so a theme no longer names it
      const b = thMake(el, 'button', 'th-pick', t.theme_name);
      b.type = 'button';
      b.setAttribute('aria-pressed', String(dash.params().theme !== 'nutrition' && t.theme === s.theme.theme));
      b.addEventListener('click', () => dash.setParams({ theme: t.theme, th_gene: null, th_organ: null, th_facet: null }));
    }
    // Nutrition sits among the themes: its own page (nt.html) shows in place of the theme's cards
    const n = thMake(el, 'button', 'th-pick th-pick-nut', 'Nutrition');
    n.type = 'button';
    n.setAttribute('aria-pressed', String(dash.params().theme === 'nutrition'));
    n.addEventListener('click', () => dash.setParams({ theme: 'nutrition', th_gene: null, th_organ: null, th_facet: null }));
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
    thMake(el, 'p', null, `${s.genes.length} library genes act on ${s.theme.theme_name.toLowerCase()}, and ${thWho(s)} has a call at ${typed.length}: ` +
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
        b.title = thNote(g) || (g.carried ? `${thWho(s)} carries ${g.carried} trait-linked ${g.carried === 1 ? 'allele' : 'alleles'}` : `No ${thWho(s)} finding`);
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
    if (!s.gene) { thMake(el, 'p', 'gx-note', 'No genes are drawn for this selection.'); return; }
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
        (n.g.function !== 'normal' && n.g.dose ? ` ×${n.g.dose}` : '') : `Not genotyped in ${thWho(s)}`, thNote(n.g) || '']))
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
    if (!s.gene) { thMake(el, 'p', 'gx-note', 'No genes are drawn for this selection.'); return; }
    const g = s.gene, fn = thCall(g);
    const head = thMake(el, 'div', 'lc-name');
    thMake(head, 'h3', null, g.gene);
    const fnText = fn ? thFnText(g, fn) : null;
    thMake(head, 'span', 'lc-call ' + (fn ? { LoF: 'lof', GoF: 'gof', altered: 'altered', normal: 'norm', variant: 'var', unknown: 'unknown' }[fn] : 'unknown'),
      fn ? fnText[0].toUpperCase() + fnText.slice(1) + (fn !== 'normal' && fn !== 'unknown' && g.dose ? ` ×${g.dose}` : '') : s.api ? `No ${thWho(s)} finding` : 'Not genotyped');
    if (g.genotype || g.call_source === 'api') thMake(el, 'p', null, `Effect on the gene: ${g.fn_evidence || 'no evidence collected'} (${TH_BASIS[g.basis] || TH_BASIS.none}).`);
    if (g.genotype && g.outcome && g.outcome !== 'typical' && g.outcome !== 'unknown') thMake(el, 'p', null, `Effect on ${thWho(s)}: ${TH_OUTCOME[g.outcome] || g.outcome}. Whether a change is good or bad is a best-effort reading of the trait; the change itself comes from the evidence.`);
    if (g.call_source === 'api') thMake(el, 'p', 'gx-note', `Called from ${thWho(s)}'s own variants in the gene: protein changes (UniProt, MaveDB, SIFT/PolyPhen) and the gene's strongest expression variant (GTEx).`);
    else thMake(el, 'p', g.genotype ? 'gx-note' : null, g.genotype ? `Library note for ${g.rsid} ${g.genotype}: ${g.interpretation}. The notes were written with an LLM and are being checked against the evidence; the label above comes from the evidence, not the note.`
      : s.api ? `Not in the library. ${thWho(s)}'s file ${s.stats && (s.stats.by_confidence || {}).high ? 'measures or confidently imputes' : 'measures'} ${g.ev.n_snps || 0} SNPs in or near this gene.` : `${thWho(s)} has no call at this gene's library SNP.`);
    if (g.has_lifecycle) {
      const b = thMake(el, 'button', 'lc-btn', 'Open its pathway');
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

  // The 28-day cycle for the female theme: a schematic of the hormone shapes and the lining, and the person's genes on
  // the days they act. What each phase is comes from Gene Ontology (the fertility views' fd_explain dataset): `go` picks
  // the term, the days place it on the schematic.
  const CYCLE_PHASES = [
    { id: 'menses', name: 'Menstruation', from: 1, to: 5, go: 'GO:0042703' },
    { id: 'follicular', name: 'Follicular phase', from: 1, to: 13, go: 'GO:0001541' },
    { id: 'ovulation', name: 'Ovulation', from: 13, to: 15, go: 'GO:0030728' },
    { id: 'luteal', name: 'Luteal phase', from: 15, to: 28, go: 'GO:0001553' },
  ];
  // Relative hormone levels by day (0–1): the textbook shape of a 28-day cycle, not anyone's measurements
  const CYCLE_HORMONES = [
    { id: 'FSH', pts: [[1, .55], [3, .62], [7, .42], [11, .32], [14, .72], [16, .3], [22, .18], [26, .3], [28, .5]] },
    { id: 'LH', pts: [[1, .2], [10, .22], [12, .32], [13, .7], [14, 1], [15, .42], [17, .2], [28, .18]] },
    { id: 'Estradiol', pts: [[1, .15], [6, .25], [10, .55], [13, .95], [15, .35], [18, .45], [21, .55], [25, .35], [28, .15]] },
    { id: 'Progesterone', pts: [[1, .05], [13, .05], [15, .14], [18, .6], [21, .95], [24, .7], [27, .2], [28, .08]] },
  ];
  const CYCLE_LINING = [[1, .55], [5, .15], [9, .35], [14, .62], [18, .82], [21, .95], [26, .9], [28, .6]];
  // Core cycle genes: the day each does its main work and the phases it acts in (placement only; what a gene does is
  // UniProt's function text, from the fertility views' fd_genes dataset)
  const CYCLE_GENES = {
    GNRH1: { day: 13, phases: ['follicular', 'ovulation'] }, GNRHR: { day: 13, phases: ['follicular', 'ovulation'] }, KISS1R: { day: 13, phases: ['ovulation'] },
    FSHB: { day: 3, phases: ['menses', 'follicular'] }, FSHR: { day: 6, phases: ['follicular'] }, AMH: { day: 4, phases: ['follicular'] },
    AMHR2: { day: 4, phases: ['follicular'] }, GDF9: { day: 8, phases: ['follicular'] }, BMP15: { day: 8, phases: ['follicular'] },
    FOXL2: { day: 7, phases: ['follicular'] }, CYP17A1: { day: 10, phases: ['follicular'] }, CYP19A1: { day: 12, phases: ['follicular', 'luteal'] },
    HSD17B1: { day: 11, phases: ['follicular'] }, ESR1: { day: 12, phases: ['follicular', 'ovulation'] }, ESR2: { day: 10, phases: ['follicular'] },
    LHB: { day: 14, phases: ['ovulation'] }, LHCGR: { day: 14, phases: ['ovulation', 'luteal'] }, PGR: { day: 20, phases: ['ovulation', 'luteal'] },
    PTGS2: { day: 14, phases: ['ovulation', 'menses'] }, STAR: { day: 17, phases: ['luteal'] }, CYP11A1: { day: 17, phases: ['luteal'] },
    HSD3B2: { day: 18, phases: ['luteal'] }, HOXA10: { day: 21, phases: ['luteal'] }, LIF: { day: 21, phases: ['luteal'] },
    OXTR: { day: 2, phases: ['menses'] }, SHBG: { day: 9, phases: ['follicular', 'luteal'] },
  };

  // Other genes are placed by their Gene Ontology mechanism
  const MECH_PHASES = { eggs: ['follicular'], axis: ['follicular', 'ovulation'], hormones: ['follicular', 'luteal'], cycle: ['ovulation', 'luteal'],
                        implantation: ['luteal'], uterus: ['menses'], ovary: ['follicular'] };

  const drawCycle = (parent, s) => {
    const who = thWho(s);
    const sec = thMake(parent, 'div', 'th-cycle');
    thMake(sec, 'h3', null, 'The 28-day cycle');
    thMake(sec, 'p', 'gx-note', `Schematic: the usual shapes of the hormones across a 28-day cycle, not ${who}'s measured levels. Dots mark ` +
      `the day each of ${who}'s changed genes does its main work. Select a phase for how it works and what ${who}'s variants change in it.`);
    const box = thMake(sec, 'div', 'th-cycle-svg');
    // Drawn at the container's own width, 1:1, so it lines up with the phase columns below and follows resizes
    const W = Math.max(320, Math.round(box.clientWidth || 760)), H = 270, L = 34, R = 12, T = 34, CH = 150, LT = T + CH + 18, LH = 40;
    const x = d3.scaleLinear([1, 28], [L, W - R]);
    const y = d3.scaleLinear([0, 1], [T + CH, T + 6]);
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H)
      .attr('role', 'img').attr('aria-label', 'Hormone levels across a typical 28-day cycle, with the genes that act on each day');
    const tip = gx.tip(box);
    const callOf = (name) => { const g = s.byName.get(name); return g ? thCall(g) : null; };
    const fdg = gx.rows('fd_genes'), fdx = gx.rows('fd_explain');
    const fns = new Map(((fdg && fdg[0]) || []).map((f) => [f.gene, f.function]));
    // Gene Ontology's definitions, from the fertility views' Part 1
    const goDef = new Map(((fdx && fdx[0]) || []).flatMap((r) => JSON.parse(r.processes)).map((t) => [t.id, t.definition]));
    for (const p of CYCLE_PHASES) p.what = goDef.get(p.go) || '';
    const effect = (name) => {
      const g = s.byName.get(name), fn = g && thCall(g);
      const lines = [fns.get(name) || ''];
      if (g && g.genotype) lines.push(`${who}: ${g.genotype}, ${TH_TEXT[fn]}${g.dose && fn !== 'normal' ? ` ×${g.dose}` : ''} (${thNote(g)})`);
      else if (g && g.carried) lines.push(`${who} carries ${g.carried} trait-linked ${g.carried === 1 ? 'allele' : 'alleles'} here`);
      else lines.push(`No ${who} call at this gene`);
      return lines.filter(Boolean);
    };

    // Phase bands and the implantation window
    for (const p of CYCLE_PHASES.filter((p) => p.id !== 'follicular')) {
      svg.append('rect').attr('x', x(p.from)).attr('width', x(p.to) - x(p.from)).attr('y', T).attr('height', CH + 18 + LH)
        .attr('class', 'th-cy-band th-cy-' + p.id)
        .on('mousemove', (event) => tip.show(event, `${p.name} · days ${p.from}–${p.to}`, [p.what]))
        .on('mouseleave', () => tip.hide())
        .on('click', () => window.gxFertility && gxFertility.open(p.id));
    }
    svg.append('text').attr('x', (x(19) + x(24)) / 2).attr('y', LT - 4).attr('text-anchor', 'middle').attr('class', 'th-cap').text('implantation window');
    svg.append('rect').attr('x', x(19)).attr('width', x(24) - x(19)).attr('y', LT).attr('height', LH).attr('class', 'th-cy-window')
      .on('mousemove', (event) => tip.show(event, 'Implantation window · days 19–24', [goDef.get('GO:0007566') || ''].filter(Boolean)))
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
      .on('mousemove', (event) => tip.show(event, 'Endometrium', [goDef.get('GO:0042698') || 'Schematic of the lining thickness'].filter(Boolean)))
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
        .attr('aria-label', `${n}: ${effect(n).map((x) => x.replace(/\.$/, '')).join('. ')}.`)
        .on('mousemove', (event) => tip.show(event, `${n} · day ${d}`, effect(n)))
        .on('mouseleave', () => tip.hide())
        .on('click', () => thPick(n));
      g.append('circle').attr('r', 5.5).style('fill', TH_FILL[fn]).style('stroke', 'var(--color-bg)').attr('stroke-width', 1.5);
      g.append('text').attr('x', 8).attr('y', 4).attr('class', 'th-cy-glabel').text(n);
    }

    // One column per phase: what happens, and the person's genes there; each heading opens the phase in depth
    const cols = thMake(sec, 'div', 'th-cycle-cols');
    for (const p of CYCLE_PHASES) {
      const col = thMake(cols, 'div', 'th-cycle-col th-cy-col-' + p.id);
      const open = thMake(col, 'button', 'th-cy-open', `${p.name} · days ${p.from}–${p.to}`);
      open.type = 'button';
      open.addEventListener('click', () => window.gxFertility && gxFertility.open(p.id));
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
        b.addEventListener('mousemove', (event) => tip.show(event, n, CYCLE_GENES[n] ? effect(n) : [fns.get(n) || '', thNote(g) ? `${who}: ${thNote(g)}` : `No ${who} call here`].filter(Boolean)));
        b.addEventListener('mouseleave', () => tip.hide());
        b.addEventListener('click', () => thPick(n));
      }
    }
    const life = thMake(sec, 'button', 'th-cy-open th-cy-life', 'Across a reproductive life: egg reserve, first period and menopause');
    life.type = 'button';
    life.addEventListener('click', () => window.gxFertility && gxFertility.open('ageing'));
  };

  // Body map: where a theme's genes act, shaded by the person's calls. Female (XX) layout: a body outline with brain and
  // pituitary, and a front view of the reproductive organs. Each organ is a button that narrows the page to its genes.
  const XX_SHAPES = {
    brain: { shapes: [{ ellipse: [120, 54, 29, 19] }], label: [178, 42, 'start'], to: [146, 50] },
    pituitary: { shapes: [{ circle: [124, 80, 6] }], label: [178, 94, 'start'], to: [131, 82] },
    tubes: { shapes: [{ stroke: 'M404,166 C372,142 330,128 300,150 C288,160 284,176 290,186' },
                      { stroke: 'M536,166 C568,142 610,128 640,150 C652,160 656,176 650,186' }], label: [470, 92, 'middle'], to: [470, 132],
             // fimbriae: the fringed ends that sweep the egg in from the ovary
             detail: [{ stroke: 'M290,186 L278,196 M290,186 L284,201 M290,186 L292,203 M290,186 L300,198' },
                      { stroke: 'M650,186 L662,196 M650,186 L656,201 M650,186 L648,203 M650,186 L640,198' }] },
    ovaries: { shapes: [{ ellipse: [300, 214, 30, 18, -18] }, { ellipse: [640, 214, 30, 18, 18] }], label: [300, 258, 'middle'], to: [300, 233],
               // follicles: one ripening, a few small ones
               detail: [{ circle: [309, 211, 7] }, { circle: [287, 214, 2.2] }, { circle: [293, 222, 1.8] }, { circle: [284, 206, 1.6] },
                        { circle: [631, 211, 7] }, { circle: [653, 214, 2.2] }, { circle: [647, 222, 1.8] }, { circle: [656, 206, 1.6] }] },
    uterus: { shapes: [{ path: 'M400,172 C400,128 540,128 540,172 C540,232 506,276 490,298 L490,382 L450,382 L450,298 C434,276 400,232 400,172 Z' }],
              label: [566, 300, 'start'], to: [522, 240] },
    endometrium: { shapes: [{ path: 'M426,168 C444,156 496,156 514,168 C504,212 482,246 470,264 C458,246 436,212 426,168 Z' }],
                   label: [566, 362, 'start'], to: [480, 228] },
  };
  // Figures: the right half of a front-view silhouette, top to bottom (neck, shoulder, arm, hand, back up the arm,
  // torso, leg); thFigure mirrors it around x = 120 and smooths it into one outline. The head is a circle on top.
  const XX_BODY = [[131, 90], [132, 110], [150, 118], [166, 126], [175, 142], [179, 180], [183, 226], [187, 268], [189, 298],
                   [185, 311], [179, 303], [175, 268], [171, 226], [167, 186], [162, 158], [158, 184], [152, 214], [156, 242],
                   [166, 272], [170, 298], [166, 332], [160, 372], [154, 412], [150, 428], [130, 428], [128, 390], [124, 350]];
  const thFigure = (half) => d3.line().curve(d3.curveCatmullRomClosed.alpha(0.5))(
    [...half, [120, 336], ...half.slice().reverse().map(([x, y]) => [240 - x, y])]);

  // The clinical path (mind theme): one row per ICD-10 diagnostic group, walked through the four steps a clinician takes.
  // Screening tests, codes and drug classes are public (themes/mind_clinical.json, window.GX_MIND); the genes and the
  // calls are the person's (theme_genes), and the medicines' guidance is the Medicines tab's (med_guidance, med_genes).
  const CL_STEPS = [['Diagnosis', 'ICD-10'], ['1 · Screen', 'Validated test'], ['2 · Genetics', 'Genes tied to it'],
                    ['3 · Mechanisms', 'What those genes do'], ['4 · Medicines', 'Response to treatment']];
  const CL_GUIDE = { differs: 'differs', typical: 'typical', no_action: 'typical', summary: 'no gene-specific advice', unreadable: 'not readable from the file', unclear: 'unclear' };
  const thClinical = (el, s, who) => {
    const MIND = window.GX_MIND;
    const groups = (MIND && MIND.groups) || {};
    const med = gx.rows('med_guidance', 'med_genes');
    const [guides, mgenes] = med || [[], []];
    const phen = new Map(mgenes.map((g) => [g.gene, g.phenotype]));
    const mechName = new Map(s.facets.map((f) => [f.facet, f.facet_name]));
    const conditions = (id) => Object.entries(s.stats.disease_organs || {}).filter(([, o]) => o === id).map(([d]) => d);
    const changed = (g) => ['LoF', 'GoF', 'altered', 'variant'].includes(thCall(g));
    const callRank = { LoF: 0, GoF: 1, altered: 2, variant: 3, normal: 4 };
    const byCall = (a, b) => (callRank[thCall(a)] ?? 5) - (callRank[thCall(b)] ?? 5) || a.gene.localeCompare(b.gene);
    const chip = (parent, g) => {
      const b = thMake(parent, 'button', 'lc-chip th-gene lc-' + (TH_CLASS[thCall(g)] || 'untested'), thLabel(g));
      b.type = 'button';
      b.addEventListener('click', (e) => { e.stopPropagation(); thPick(g.gene); });
    };
    const link = (parent, text, href) => { const a = thMake(parent, 'a', null, text); a.href = href; a.target = '_blank'; a.rel = 'noopener'; return a; };
    // Per group: its genes (joined on one of its conditions), their mechanisms, and its medicines with guidance
    const rows = s.organs.map((o) => {
      const G = groups[o.id] || { icd: [], screens: [], drugs: {}, classes: [] };
      const genes = s.genes.filter((g) => (g.ev.organs || []).includes(o.id)).sort(byCall);
      const mech = new Map();
      for (const g of genes) for (const f of g.fl) if (f !== 'disease') { if (!mech.has(f)) mech.set(f, []); mech.get(f).push(g); }
      const mechs = [...mech.entries()].sort((a, b) => b[1].length - a[1].length);
      const drugs = new Map();
      for (const x of guides) {
        if (x.kind !== 'guideline') continue;
        const d = x.drug.toLowerCase();
        if (!(d in (G.drugs || {}))) continue;
        if (!drugs.has(d)) drugs.set(d, []);
        drugs.get(d).push(x);
      }
      const differs = [...drugs.entries()].filter(([, xs]) => xs.some((x) => x.status === 'differs')).map(([d]) => d);
      return { o, G, genes, mechs, drugs, differs };
    });

    const box = thMake(el, 'div', 'th-cl');
    const head = thMake(box, 'div', 'th-cl-row th-cl-head');
    CL_STEPS.forEach(([t, sub], i) => {
      const c = thMake(head, 'div', 'th-cl-cell');
      thMake(c, 'b', null, t);
      thMake(c, 'span', null, sub);
      if (i) c.classList.add('th-cl-step');
    });
    for (const r of rows) {
      const sel = s.organ && s.organ.id === r.o.id;
      const row = thMake(box, 'div', 'th-cl-row' + (sel ? ' th-cl-on' : ''));
      row.tabIndex = 0;
      row.setAttribute('role', 'button');
      row.setAttribute('aria-expanded', String(!!sel));
      const pick = () => dash.setParams({ th_organ: sel ? null : r.o.id, th_gene: null });
      row.addEventListener('click', pick);
      row.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });
      // Diagnosis
      const d = thMake(row, 'div', 'th-cl-cell');
      thMake(d, 'b', 'th-cl-name', r.o.name);
      const codes = thMake(d, 'div', 'th-cl-codes');
      for (const c of r.G.icd) thMake(codes, 'span', 'th-cl-code', c.category);
      // 1 Screen
      const sc = thMake(row, 'div', 'th-cl-cell');
      for (const t of r.G.screens) thMake(sc, 'div', 'th-cl-test', t.name);
      // 2 Genetics
      const ge = thMake(row, 'div', 'th-cl-cell');
      const nChanged = r.genes.filter(changed).length;
      thMake(ge, 'div', null, `${r.genes.length} genes`);
      if (r.genes.length) {
        thBalance(ge, r.genes, 'no call');
        thMake(ge, 'span', 'gx-note', `${nChanged} changed in ${who}`);
      }
      // 3 Mechanisms
      const me = thMake(row, 'div', 'th-cl-cell');
      if (r.mechs.length) for (const [f, gs] of r.mechs.slice(0, 3)) thMake(me, 'div', 'th-cl-mech', `${mechName.get(f) || f} · ${gs.length}`);
      else thMake(me, 'span', 'gx-note', 'No known mechanism yet');
      // 4 Medicines
      const md = thMake(row, 'div', 'th-cl-cell');
      if (!r.drugs.size) thMake(md, 'span', 'gx-note', 'No pharmacogenetic guideline');
      else {
        thMake(md, 'div', null, r.drugs.size === 1 ? '1 medicine with a guideline' : `${r.drugs.size} medicines with a guideline`);
        if (r.differs.length) thMake(md, 'div', 'th-cl-differs', `${r.differs.length} ${r.differs.length === 1 ? 'differs' : 'differ'} for ${who}: ${r.differs.slice(0, 3).join(', ')}${r.differs.length > 3 ? '…' : ''}`);
        else thMake(md, 'span', 'gx-note', `typical for ${who}`);
      }
      if (sel) thClinicalDetail(box, r, who, { conditions, chip, link, changed, phen, mechName });
    }
    thMake(el, 'p', 'gx-note', 'Sources: ICD-10 codes from NLM Clinical Tables (ICD-10-CM); screening tests from their validation papers ' +
      '(Europe PMC), quoted as written; genes from Open Targets and Gene Ontology; drug classes from the WHO ATC classification ' +
      '(ChEMBL), with the CPIC and DPWG guidelines of the Medicines tab.');
  };
  const thClinicalDetail = (box, r, who, h) => {
    const det = thMake(box, 'div', 'th-cl-detail');
    det.addEventListener('click', (e) => e.stopPropagation());
    thMake(det, 'p', null, r.o.about);
    // Diagnosis: the codes
    const dx = thMake(det, 'section', 'th-cl-sec');
    thMake(dx, 'span', 'gx-label', 'Diagnosis: ICD-10');
    for (const c of r.G.icd) {
      const dd = thMake(dx, 'details', 'th-cl-icd');
      thMake(dd, 'summary', null, `${c.category} · ${c.codes.length} codes`);
      const ul = thMake(dd, 'ul', null);
      for (const [code, title] of c.codes) thMake(ul, 'li', null, `${code} ${title}`);
    }
    // 1 Screen: each test, its validation paper and what it says about scoring
    const sc = thMake(det, 'section', 'th-cl-sec');
    thMake(sc, 'span', 'gx-label', '1 · Screen');
    for (const t of r.G.screens) {
      const d = thMake(sc, 'div', 'th-cl-paper');
      thMake(d, 'b', null, t.name);
      const cite = thMake(d, 'p', 'gx-note');
      h.link(cite, `${t.title}`, t.url);
      thMake(cite, 'span', null, ` ${t.authors || ''} ${t.journal || ''} ${t.year || ''}`);
      for (const q of t.quotes) thMake(d, 'blockquote', 'th-cl-quote', q);
      if (!t.quotes.length) thMake(d, 'p', 'gx-note', 'The abstract gives no cut-off; the paper has the scoring.');
    }
    // 2 Genetics: per condition, the genes joined on it, changed ones first
    const ge = thMake(det, 'section', 'th-cl-sec');
    thMake(ge, 'span', 'gx-label', '2 · Genetics');
    thMake(ge, 'p', 'gx-note', `Genes with human genetic evidence (Open Targets) for the group's conditions. ${who}'s calls colour them: ` +
      'red less active, blue more active, grey a carried trait-linked variant, green typical. Select a gene for its evidence.');
    for (const cond of h.conditions(r.o.id)) {
      const gs = r.genes.filter((g) => (g.ev.joined_by || []).includes(cond));
      if (!gs.length) continue;
      const line = thMake(ge, 'div', 'th-fibre');
      thMake(line, 'span', 'th-fibre-name', `${cond} · ${gs.length}`);
      const chips = thMake(line, 'div', 'th-genes');
      const show = gs.filter(h.changed).slice(0, 12);
      for (const g of show) h.chip(chips, g);
      thMake(chips, 'span', 'gx-note', show.length ? `${gs.filter(h.changed).length} changed of ${gs.length}` : `none changed in ${who}`);
    }
    // 3 Mechanisms: what the group's genes do, with the changed genes in each
    const me = thMake(det, 'section', 'th-cl-sec');
    thMake(me, 'span', 'gx-label', '3 · Mechanisms');
    if (!r.mechs.length) thMake(me, 'p', 'gx-note', 'Gene Ontology places none of these genes in a mechanism of this theme yet.');
    for (const [f, gs] of r.mechs.slice(0, 6)) {
      const line = thMake(me, 'div', 'th-fibre');
      thMake(line, 'span', 'th-fibre-name', `${h.mechName.get(f) || f} · ${gs.length}`);
      const chips = thMake(line, 'div', 'th-genes');
      for (const g of gs.filter(h.changed).slice(0, 10)) h.chip(chips, g);
    }
    // 4 Medicines: the group's drug classes and every guideline for their drugs, those that differ for the person first
    const md = thMake(det, 'section', 'th-cl-sec');
    thMake(md, 'span', 'gx-label', '4 · Medicines');
    thMake(md, 'p', 'gx-note', 'Drug classes (ATC): ' + r.G.classes.map((c) => `${c.atc} ${c.name.charAt(0) + c.name.slice(1).toLowerCase()}`).join(' · '));
    if (!r.drugs.size) thMake(md, 'p', 'gx-note', 'No CPIC or DPWG guideline covers a medicine of these classes.');
    const order = { differs: 0, typical: 1, no_action: 1, unclear: 2, summary: 3, unreadable: 4 };
    const list = [...r.drugs.entries()].sort((a, b) => Math.min(...a[1].map((x) => order[x.status] ?? 5)) - Math.min(...b[1].map((x) => order[x.status] ?? 5)) || a[0].localeCompare(b[0]));
    for (const [drug, xs] of list) {
      const d = thMake(md, 'div', 'th-cl-drug');
      thMake(d, 'b', null, drug);
      for (const x of xs.sort((a, b) => (order[a.status] ?? 5) - (order[b.status] ?? 5))) {
        const p = thMake(d, 'div', 'th-cl-guide th-cl-' + (CL_GUIDE[x.status] === 'differs' ? 'differs' : 'plain'));
        const genes = x.genes.split(';').map((g) => `${g}${h.phen.get(g) ? ` (${h.phen.get(g)})` : ''}`).join(', ');
        thMake(p, 'span', null, `${x.source} · ${genes} · ${CL_GUIDE[x.status] || x.status}`);
        if (x.status === 'differs') {
          let recs = [];
          try { recs = typeof x.recs === 'string' ? JSON.parse(x.recs) : x.recs || []; } catch (e) { recs = []; }
          for (const rc of recs.slice(0, 2)) if (rc.recommendation) thMake(p, 'p', 'th-cl-rec', rc.recommendation);
        }
      }
    }
    if (r.drugs.size) {
      const go = thMake(md, 'button', 'lc-btn', 'Open Medicines');
      go.type = 'button';
      go.addEventListener('click', () => gx.show('medicines'));
    }
  };

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
    const exertion = s.stats.view === 'exertion';
    // Phased: stages in columns over time (the training session, the mind theme's day)
    const phased = exertion || !!(s.stats.phases && s.stats.phases.length);
    const phases = s.stats.phases && s.stats.phases.length ? s.stats.phases : EX_PHASES;
    const SHAPES = cell ? CELL_SHAPES() : phased ? EXERTION_SHAPES(s.organs, phases) : male ? XY_SHAPES : XX_SHAPES;
    const unit = cell || phased ? 'stage' : 'organ';
    const card = el.closest('.gx-card');
    if (card) {
      const h = card.querySelector('h2'), note = card.querySelector('.gx-note');
      if (h) h.textContent = cell ? 'Life of a cell' : exertion ? 'A training session' : s.stats.view_title || 'Body map';
      if (note) note.textContent = cell
        ? 'The stages every cell lives through, and where the theme\'s genes act in them. Cancer starts when a cell slips past the ' +
          'checkpoints, repair, ageing and death. Select a stage to narrow the mechanisms, connections and gene panel to it.'
        : !exertion && s.stats.view_note ? s.stats.view_note
        : exertion
        ? 'Before, during and after exertion: what you bring to a session, what your muscle fibres are built for, and how you ' +
          'recover. Select a stage to narrow the mechanisms, connections and gene panel to it.'
        : 'Where in the body the theme\'s genes act. Each gene is placed by its mechanisms and the conditions it is linked to. ' +
          'Select an organ to narrow the mechanisms, connections and gene panel to it.';
    }
    if (s.stats.view === 'clinical') { thClinical(el, s, who); return; }

    const per = new Map(s.organs.map((o) => [o.id, { o, all: 0, lof: 0, gof: 0, norm: 0, variant: 0, genes: [] }]));
    for (const g of s.genes) {
      for (const id of g.ev.organs || []) {
        const c = per.get(id);
        if (!c) continue;
        c.all += 1;
        const fn = thCall(g);
        if (fn === 'LoF') c.lof += 1; else if (fn === 'GoF') c.gof += 1; else if (fn === 'variant') c.variant += 1; else if (fn === 'normal') c.norm += 1;
        if (g.notable) c.genes.push(g);
      }
    }
    const signal = (c) => c.lof + c.gof + c.variant;
    const maxSig = d3.max([...per.values()], signal) || 1;
    // Bars: every gene with a call, typical function (green) included, on one scale across the stages
    const called = (c) => signal(c) + c.norm;
    const maxCalled = d3.max([...per.values()], called) || 1;
    const hueOf = (c) => c.lof > c.gof ? 'var(--color-bad)' : c.gof > c.lof ? 'var(--gof)' : 'var(--color-fg-muted)';
    const tint = (c) => `color-mix(in srgb, ${hueOf(c)} ${Math.round(18 + 42 * signal(c) / maxSig)}%, var(--color-panel))`;
    const edge = (c) => `color-mix(in srgb, ${hueOf(c)} 75%, var(--color-fg))`;

    const grid = thMake(el, 'div', 'th-body-grid');
    const box = thMake(grid, 'div', 'th-body-svg');
    const info = thMake(grid, 'div', 'th-organ');
    const svg = d3.select(box).append('svg').attr('viewBox', '0 0 760 432').attr('width', '100%')
      .attr('role', 'group').attr('aria-label', `${s.theme.theme_name}: ${unit}s`).classed('th-ex', phased);
    const tip = gx.tip(box);

    const defs = svg.append('defs');
    // Body, the pelvis it zooms from and the panel the organs sit in; the cell map draws its paths instead
    if (cell) drawCellPaths(svg);
    else if (phased) drawExertionFrame(svg, phases);
    else {
    const glow = defs.append('radialGradient').attr('id', 'th-glow');
    glow.append('stop').attr('offset', '0%').style('stop-color', 'var(--color-fg)').style('stop-opacity', 0.16);
    glow.append('stop').attr('offset', '100%').style('stop-color', 'var(--color-fg)').style('stop-opacity', 0);
    svg.append('path').attr('d', 'M140,284 L250,122 L250,416 L140,316 Z').attr('class', 'th-wedge');
    svg.append('rect').attr('x', 250).attr('y', 112).attr('width', 504).attr('height', 314).attr('rx', 22).attr('class', 'th-lens');
    // Two layers, so the head and body read as one figure: outlines below, fills on top hide the seams
    const fig = svg.append('g').attr('class', 'th-figure');
    for (const layer of ['th-fig-line', 'th-fig-fill']) {
      fig.append('path').attr('d', thFigure(male ? XY_BODY : XX_BODY)).attr('class', layer);
      fig.append('circle').attr('cx', 120).attr('cy', 56).attr('r', 37).attr('class', layer);
    }
    svg.append('circle').attr('cx', 120).attr('cy', 300).attr('r', 34).attr('fill', 'url(#th-glow)');
    svg.append('circle').attr('cx', 120).attr('cy', 300).attr('r', 20).attr('class', 'th-focus');
    if (male) {
      for (const cx of XY_CONTEXT) {
        if (cx.ellipse) {
          svg.append('ellipse').attr('cx', cx.ellipse[0]).attr('cy', cx.ellipse[1]).attr('rx', cx.ellipse[2]).attr('ry', cx.ellipse[3]).attr('class', 'th-context');
          svg.append('text').attr('x', cx.ellipse[0]).attr('y', cx.ellipse[1] + 4).attr('text-anchor', 'middle').attr('class', 'th-cap').text(cx.name);
        } else svg.append('path').attr('d', cx.path).attr('class', 'th-context');
      }
    }
    }
    // Bar of a person's calls in an organ: red less active, blue more active, grey a carried trait-linked variant, green typical
    const k = Math.min(6, 96 / maxCalled);
    const miniBar = (x, y, anchor, c) => {
      const parts = [['lof', c.lof], ['gof', c.gof], ['var', c.variant], ['norm', c.norm]].filter(([, n]) => n);
      const w = d3.sum(parts, ([, n]) => n * k) + parts.length - 1;
      let at = anchor === 'start' ? x : anchor === 'end' ? x - w : x - w / 2;
      for (const [cls, n] of parts) {
        svg.append('rect').attr('x', at).attr('y', y).attr('width', n * k).attr('height', 5).attr('rx', 2).attr('class', 'th-m-' + cls);
        at += n * k + 1;
      }
    };

    for (const [id, shape] of Object.entries(SHAPES)) {
      const c = per.get(id);
      if (!c) continue;
      const selected = s.organ && s.organ.id === id;
      // Shading: the organ's colour at the centre, deepening toward the rim
      const grad = defs.append('radialGradient').attr('id', `th-fill-${id}`).attr('cx', '42%').attr('cy', '38%').attr('r', '70%');
      grad.append('stop').attr('offset', '0%').style('stop-color', tint(c));
      grad.append('stop').attr('offset', '100%').style('stop-color', `color-mix(in srgb, ${tint(c)} 78%, var(--color-fg))`);
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
        node.attr('class', 'th-shape' + (sh.cls ? ' ' + sh.cls : '')).style('fill', cell ? tint(c) : `url(#th-fill-${id})`).style('stroke', edge(c));
      }
      // Anatomical detail (follicles, fimbriae, the glans): drawn in the organ's colours, not clickable on its own
      for (const d of shape.detail || []) {
        if (d.circle) g.append('circle').attr('cx', d.circle[0]).attr('cy', d.circle[1]).attr('r', d.circle[2]).attr('class', 'th-anat')
          .style('fill', `color-mix(in srgb, ${tint(c)} 45%, var(--color-panel))`).style('stroke', edge(c));
        else g.append('path').attr('d', d.stroke).attr('class', 'th-anat th-anat-line').style('stroke', id === 'tubes' ? tint(c) : edge(c));
      }
      const [lx, ly, anchor] = shape.label;
      if (shape.to) svg.append('line').attr('x1', shape.to[0]).attr('y1', shape.to[1])
        .attr('x2', anchor === 'start' ? lx - 6 : anchor === 'end' ? lx + 6 : lx).attr('y2', anchor === 'middle' && ly < shape.to[1] ? ly + (cell ? 20 : 30) : ly - 4).attr('class', 'th-leader');
      const t = svg.append('text').attr('x', lx).attr('y', ly).attr('text-anchor', anchor).attr('class', 'th-label' + (selected ? ' is-selected' : ''));
      t.append('tspan').text(c.o.name);
      const sub = svg.append('text').attr('x', lx).attr('y', ly + 15).attr('text-anchor', anchor).attr('class', 'th-cap');
      sub.append('tspan').text(`${c.all} genes`);
      if (c.lof) sub.append('tspan').attr('class', 'th-c-lof').text(` · ▼${c.lof}`);
      if (c.gof) sub.append('tspan').attr('class', 'th-c-gof').text(` · ▲${c.gof}`);
      if (c.variant) sub.append('tspan').text(` · ●${c.variant}`);
      if (!cell) miniBar(lx, ly + 21, anchor, c);
    }

    if (cell) drawCellLetters(svg);
    // Female theme: the 28-day cycle sits under the organs
    if (s.stats.sex === 'XX') drawCycle(el, s);

    // Side panel: the selected organ, or how to read the map
    const o = s.organ;
    if (!o) {
      thMake(info, 'h3', null, `All ${unit}s`);
      thMake(info, 'p', 'gx-note', `▼ less active and ▲ more active are ${who}'s gene calls; ● counts genes where ${who} carries an allele ` +
        `that a GWAS or ClinVar links to one of the theme's conditions. Shading is stronger where more of these gather, red where less-active genes ` +
        `lead and blue where more-active ones do. Select ${cell || phased ? 'a stage' : 'an organ'} to focus the page on it.`);
      if (phased) thMake(info, 'p', 'gx-note', `How to read the list: the number is how many of the stage's genes ${who} carries in a changed form ` +
        `(red, blue or grey); green are genes ${who} carries in their typical form. A high number means the stage has more places where ` +
        `${who}'s genes differ from most people's, not that it works better or worse: the colour mix says which way it leans.`);
      // Muscle: what the fibres are built for, from the person's calls on the fibre and aerobic genes
      if (exertion) {
        thMake(info, 'span', 'gx-label', 'Fibre profile');
        const rank = { LoF: 0, GoF: 1, altered: 2, variant: 3, normal: 4 };
        for (const [mid, label] of [['fast', 'Fast-twitch fibres'], ['slow', 'Slow-twitch fibres'], ['aerobic', 'Aerobic capacity']]) {
          const gs = s.genes.filter((g) => (g.fl || []).includes(mid));
          const called = gs.filter((g) => thCall(g)).sort((a, b) => (rank[thCall(a)] ?? 5) - (rank[thCall(b)] ?? 5));
          const row = thMake(info, 'div', 'th-fibre');
          thMake(row, 'span', 'th-fibre-name', label);
          const chips = thMake(row, 'div', 'th-genes');
          for (const g of called.slice(0, 8)) {
            const b = thMake(chips, 'button', 'lc-chip th-gene lc-' + TH_CLASS[thCall(g)], thLabel(g));
            b.type = 'button';
            b.addEventListener('click', () => thPick(g.gene));
          }
          thMake(chips, 'span', 'gx-note', called.length
            ? (called.length > 8 ? `and ${called.length - 8} more of ${gs.length} genes` : `of ${gs.length} genes`)
            : `${gs.length} genes, none with a call in ${who}`);
        }
      }
      // Ranked rows, one per organ: its name, the bar of the person's calls there, and how many there are
      const list = thMake(info, 'div', 'th-organ-list');
      for (const c of [...per.values()].sort((a, b) => signal(b) - signal(a) || b.all - a.all)) {
        const b = thMake(list, 'button', 'th-organ-row');
        b.type = 'button';
        b.setAttribute('aria-label', `${c.o.name}: ${c.lof} less active, ${c.gof} more active, ${c.variant} with a carried variant, ${c.norm} typical function`);
        thMake(b, 'span', 'th-organ-name', c.o.name);
        const bar = thMake(b, 'span', 'th-mini');
        for (const [cls, n] of [['lof', c.lof], ['gof', c.gof], ['var', c.variant], ['norm', c.norm]]) {
          if (n) thMake(bar, 'span', 'th-mini-' + cls).style.width = `${(100 * n) / maxCalled}%`;
        }
        thMake(b, 'span', 'th-organ-n', String(signal(c)));
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
  // Muscle theme: a training session in three columns (before, during, after), each stage a tile, in the order the theme
  // lists them. Tiles are buttons like the organs on the body maps.
  // Any phased theme (the mind theme's day) uses the same layout, with the columns its stats name.
  const EX_PHASES = [{ id: 'before', name: 'Before' }, { id: 'during', name: 'During' }, { id: 'after', name: 'After' }];
  const EX_LEFT = 14, EX_RIGHT = 746, EX_GAP = 24, EX_TOP = 44, EX_BOTTOM = 426;
  const exCols = (phases) => {
    const w = (EX_RIGHT - EX_LEFT - EX_GAP * (phases.length - 1)) / phases.length;
    return phases.map((p, i) => ({ ...p, x: EX_LEFT + i * (w + EX_GAP), w }));
  };
  const exTile = (x, y, w, h, r = 10) => `M${x + r},${y} h${w - 2 * r} a${r},${r} 0 0 1 ${r},${r} v${h - 2 * r} ` +
    `a${r},${r} 0 0 1 -${r},${r} h-${w - 2 * r} a${r},${r} 0 0 1 -${r},-${r} v-${h - 2 * r} a${r},${r} 0 0 1 ${r},-${r} Z`;
  const EXERTION_SHAPES = (organs, phases) => {
    const out = {};
    for (const { id, x, w } of exCols(phases)) {
      const list = organs.filter((o) => o.phase === id), gap = 8;
      const h = (EX_BOTTOM - EX_TOP - gap * (list.length - 1)) / Math.max(1, list.length);
      list.forEach((o, i) => {
        const y = EX_TOP + i * (h + gap);
        out[o.id] = { shapes: [{ path: exTile(x, y, w, h) }], label: [x + 12, y + Math.min(26, h / 2 - 4), 'start'] };
      });
    }
    return out;
  };
  const drawExertionFrame = (svg, phases) => {
    svg.append('defs').append('marker').attr('id', 'th-ex-arrow').attr('viewBox', '0 0 10 10').attr('refX', 9).attr('refY', 5)
      .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto')
      .append('path').attr('d', 'M0,0 L10,5 L0,10 Z').attr('class', 'th-ex-head');
    const cols = exCols(phases);
    for (const { name, x, w } of cols) {
      svg.append('text').attr('x', x + w / 2).attr('y', 24).attr('text-anchor', 'middle').attr('class', 'th-ex-phase').text(name);
    }
    for (const { x, w } of cols.slice(0, -1)) {
      svg.append('path').attr('d', `M${x + w + 3},20 L${x + w + EX_GAP - 3},20`).attr('class', 'th-ex-flow').attr('marker-end', 'url(#th-ex-arrow)');
    }
  };

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
    penis: { shapes: [{ path: 'M459,224 L459,310 C451,316 450,340 470,346 C490,340 489,316 481,310 L481,224 Z' }],
             detail: [{ stroke: 'M459,312 C464,318 476,318 481,312' }], label: [566, 262, 'start'], to: [484, 268] },
    testes: { shapes: [{ ellipse: [418, 330, 20, 27] }, { ellipse: [522, 330, 20, 27] }], label: [566, 340, 'start'], to: [544, 334] },
    epididymis: { shapes: [{ stroke: 'M402,312 C392,326 394,350 408,358' }, { stroke: 'M538,312 C548,326 546,350 532,358' },
                           { stroke: 'M418,303 C404,262 392,196 420,166 C436,150 452,176 458,196' },
                           { stroke: 'M522,303 C536,262 548,196 520,166 C504,150 488,176 482,196' }],
                  label: [380, 240, 'end'], to: [400, 246] },
  };
  const XY_BODY = [[133, 90], [134, 110], [156, 116], [176, 124], [186, 142], [190, 182], [193, 226], [195, 268], [196, 298],
                   [192, 311], [185, 303], [182, 268], [178, 226], [173, 186], [168, 158], [166, 192], [162, 230], [162, 262],
                   [164, 294], [162, 332], [158, 372], [154, 412], [150, 428], [130, 428], [128, 390], [124, 350]];
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
    const who = thWho(s);
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
        li.append(` ${g.genotype}: ${TH_TEXT[thCall(g)]}${g.dose && g.function !== 'normal' ? ` ×${g.dose}` : ''}. ${thNote(g) || ''}`);
      }
    }
    if (carriers.length) {
      thMake(el, 'p', 'gx-note', `${who} carries trait-linked alleles in ${carriers.length} more ${carriers.length === 1 ? 'gene' : 'genes'} here: ` +
        carriers.sort((a, b) => b.carried - a.carried).slice(0, 12).map((g) => `${g.gene} (${g.carried})`).join(', ') +
        (carriers.length > 12 ? ', …' : '') + '. Select one to see the variants.');
    }
    if (!changed.length && !carriers.length) thMake(el, 'p', 'gx-note', `${who} has no gene call with an effect and no carried trait-linked allele in this mechanism's genes.`);

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

  // Muscle theme: the SNPs consumer fitness tests report, grouped by topic, each with its evidence grade (from the GWAS
  // Catalog, ClinVar and ClinPGx), what it changes (Ensembl VEP), the person's copies, and how many sport papers name it
  const SPORT_GRADE = { A: 'replicated in genome-wide studies, ClinVar, or ClinPGx level 1–2', B: 'one genome-wide study, or a change that cuts the protein short',
                        C: 'candidate-gene studies only: no genome-wide study, ClinVar or ClinPGx finding' };
  const SPORT_CHANGE = { stop_gained: 'Stops the protein early', frameshift_variant: 'Shifts the protein\'s reading frame', missense_variant: 'Changes one amino acid',
    synonymous_variant: 'Same amino acid: a silent change', '5_prime_UTR_variant': 'In the start of the gene\'s message, before the protein',
    '3_prime_UTR_variant': 'In the end of the gene\'s message, after the protein', intron_variant: 'Inside an intron, between the protein-coding parts',
    downstream_gene_variant: 'Just after the gene', upstream_gene_variant: 'Just before the gene', NMD_transcript_variant: 'In the gene',
    splice_region_variant: 'Near a splice site' };
  const thJ = (s) => { try { return s ? JSON.parse(s) : null; } catch (e) { return null; } };
  dash.draw('th-sport', (el) => {
    const card = el.closest('.gx-card');
    if (card) card.classList.toggle('th-off', dash.params().theme !== 'muscle');
    if (dash.params().theme !== 'muscle') return;
    const r = gx.rows('sport_snps');
    if (!r) { if (gx.failed('sport_snps')) gx.failLine(el); return; }
    const [rows] = r;
    el.replaceChildren();
    if (!rows.length) return;
    const who = rows[0].person || gx.who();
    thMake(el, 'h2', null, 'The popular sport genes');
    const n = (g) => rows.filter((x) => x.grade === g).length;
    thMake(el, 'p', 'gx-note', `The ${rows.length} SNPs that consumer fitness DNA tests report. Most come from small candidate-gene studies of athletes; ` +
      `the grade says what larger sources back: ${n('A')} have replicated genome-wide or clinical evidence (A), ${n('B')} some (B), and ${n('C')} rest on ` +
      `candidate-gene studies alone (C). The genome-wide traits are what each variant is proven to move, which is often not what the tests sell it for.`);
    // The grades as a legend, each with its count
    const legend = thMake(el, 'div', 'th-sp-legend');
    for (const gr of ['A', 'B', 'C']) {
      const item = thMake(legend, 'span', 'th-sp-legend-item');
      thMake(item, 'span', 'md-grade md-grade-' + gr.toLowerCase(), gr);
      thMake(item, 'span', null, `${n(gr)} · ${SPORT_GRADE[gr]}`);
    }
    const marked = rows.filter((x) => x.meaning).length;
    if (marked) thMake(el, 'p', 'gx-note', `★ marks the ${marked} where ${who}'s copies matter in practice; those rows are open. Select any row for its genome-wide, ClinVar and ClinPGx findings.`);
    const num = (v) => (v == null || v === '' ? null : Number(v));
    const dots = (k) => (k == null ? '' : '●'.repeat(k) + '○'.repeat(2 - k));
    const topics = [...new Map(rows.map((x) => [x.topic, x])).values()].sort((a, b) => a.topic_order - b.topic_order);
    for (const t of topics) {
      const list = rows.filter((x) => x.topic === t.topic)
        .sort((a, b) => a.grade.localeCompare(b.grade) || (b.meaning ? 1 : 0) - (a.meaning ? 1 : 0) || num(b.papers) - num(a.papers));
      const sec = thMake(el, 'section', 'th-sp-topic');
      const h = thMake(sec, 'h3', null, t.topic_name);
      thMake(h, 'span', 'th-sp-count', ` · ${list.length}`);
      const table = thMake(sec, 'div', 'th-sp-table');
      const head = thMake(table, 'div', 'th-sp-row th-sp-head');
      for (const c of ['Grade', 'Gene and SNP', 'What it changes', `${who}'s copies`, 'In Europeans', 'Evidence', 'Papers']) thMake(head, 'span', null, c);
      for (const s of list) {
        const copies = s.confidence === 'not_excluded' ? null : num(s.alt_copies);
        const det = thMake(table, 'details', 'th-sp-item' + (s.meaning ? ' th-sp-marked' : ''));
        if (s.meaning) det.open = true;
        const row = thMake(det, 'summary', 'th-sp-row');
        // Grade
        const gc = thMake(row, 'span', 'th-sp-grade');
        const g = thMake(gc, 'span', 'md-grade md-grade-' + s.grade.toLowerCase(), s.grade);
        g.title = `Evidence grade ${s.grade}: ${SPORT_GRADE[s.grade]}`;
        if (s.meaning) thMake(gc, 'span', 'th-sp-star', '★');
        // Gene and SNP
        const gn = thMake(row, 'span', 'th-sp-gene');
        const gb = thMake(gn, 'button', 'lc-link', s.gene);
        gb.type = 'button';
        gb.addEventListener('click', (e) => { e.preventDefault(); thPick(s.gene); });
        thMake(gn, 'span', 'nt-sub', s.rsid);
        // What it changes
        const ch = thMake(row, 'span', 'th-sp-change');
        thMake(ch, 'span', null, SPORT_CHANGE[s.consequence] || 'Near the gene');
        if (s.amino_acids) thMake(ch, 'span', 'nt-sub', s.amino_acids.replace('/', ' → ').replace('*', 'stop'));
        // The person's copies of the variant allele
        const cp = thMake(row, 'span', 'th-sp-copies');
        if (s.confidence === 'not_excluded') thMake(cp, 'span', 'nt-sub', 'not detected, too rare to rule out');
        else if (!s.genotype) thMake(cp, 'span', 'nt-sub', 'not read');
        else {
          const line = thMake(cp, 'span', 'th-sp-gt');
          thMake(line, 'b', null, s.genotype);
          if (copies != null) {
            const d = thMake(line, 'span', 'th-sp-dots', dots(copies));
            d.title = copies === 0 ? `${who} does not carry ${s.alt}` : copies === 1 ? `${who} carries one copy of ${s.alt}` : `${who} carries two copies of ${s.alt}`;
            thMake(line, 'span', 'nt-sub', `${s.alt} ×${copies}`);
          }
          if (s.confidence === 'high' || s.confidence === 'medium') thMake(cp, 'span', 'th-imp th-imp-' + s.confidence, `imputed, ${s.confidence} confidence`);
        }
        // How common the variant allele is
        const af = num(s.eur_af);
        const fq = thMake(row, 'span', 'th-sp-af');
        if (af != null) {
          thMake(fq, 'span', null, `${s.alt} ${Math.round(100 * af)}%`);
          const bar = thMake(fq, 'span', 'th-sp-afbar');
          thMake(bar, 'span', null).style.width = `${Math.round(100 * af)}%`;
        } else thMake(fq, 'span', 'nt-sub', '–');
        // Which larger sources back it
        const gw = thJ(s.gwas) || [], cv = thJ(s.clinvar) || [];
        // ClinPGx: levels 1A-2B, and caffeine at any level; a level-3 single study of an unrelated drug says nothing about sport
        const px = (thJ(s.clinpgx) || []).filter((x) => x.effect && (x.level !== '3' || /caffeine/i.test(x.chemicals))).sort((a, b) => a.level.localeCompare(b.level));
        const ev = thMake(row, 'span', 'th-sp-ev');
        if (gw.length) thMake(ev, 'span', 'th-sp-tag', num(s.gwas_pubs) === 1 ? 'GWAS · 1 study' : `GWAS · ${s.gwas_pubs} studies`);
        if (cv.length) thMake(ev, 'span', 'th-sp-tag', 'ClinVar');
        if (px.length) thMake(ev, 'span', 'th-sp-tag', `ClinPGx ${px[0].level}`);
        if (!gw.length && !cv.length && !px.length) thMake(ev, 'span', 'nt-sub', 'candidate-gene studies only');
        // Sport papers
        const pa = thMake(row, 'span', 'th-sp-papers');
        const a = thMake(pa, 'a', 'nt-src', String(s.papers));
        a.href = s.papers_url; a.target = '_blank'; a.rel = 'noopener';
        a.title = 'Sport or exercise papers that name this SNP (Europe PMC)';
        a.addEventListener('click', (e) => e.stopPropagation());

        // Opened: what it means for the person, then each source's finding
        const body = thMake(det, 'div', 'th-sp-body');
        if (s.meaning) { const w = thMake(body, 'div', 'th-sport-mean'); thMake(w, 'b', null, `For ${who}:`); thMake(w, 'span', null, ' '); thMake(w, 'span', null, s.meaning); }
        if (gw.length) {
          // Each trait its own node: the trait names translate through the terms dictionary
          const p = thMake(body, 'div', 'th-sp-src');
          thMake(p, 'b', null, num(s.gwas_pubs) === 1 ? 'Genome-wide, 1 publication' : `Genome-wide, ${s.gwas_pubs} publications`);
          const ul = thMake(p, 'ul', null);
          for (const x of gw.slice(0, 5)) {
            const li = thMake(ul, 'li', null);
            thMake(li, 'span', null, x.trait);
            if (x.allele) thMake(li, 'span', 'nt-sub', x.copies != null ? ` (${x.allele}, ${who} ×${x.copies})` : ` (${x.allele})`);
          }
          if (num(s.gwas_traits) > 5) thMake(p, 'span', 'nt-sub', `and ${num(s.gwas_traits) - 5} more traits`);
        }
        for (const c of cv) {
          // ClinVar joins every submitted condition with |: the first three, and how many more
          const conds = [...new Set(c.condition.replace(/_/g, ' ').split('|').map((x) => x.trim()).filter((x) => x && !/^not (provided|specified)$/i.test(x)))];
          const p = thMake(body, 'div', 'th-sp-src');
          thMake(p, 'b', null, 'ClinVar');
          thMake(p, 'span', null, `${c.significance.replace(/_/g, ' ').split('|')[0]}, ${conds.slice(0, 3).join('; ')}` + (conds.length > 3 ? `; and ${conds.length - 3} more` : ''));
        }
        if (px.length) {
          const p = thMake(body, 'div', 'th-sp-src');
          thMake(p, 'b', null, `ClinPGx, level ${px[0].level}`);
          thMake(p, 'span', null, `${px[0].chemicals}: ${who} may ${px[0].effect}` + (px.length > 1 ? `; and ${px.length - 1} more` : ''));
        }
        if (!gw.length && !cv.length && !px.length) thMake(body, 'p', 'nt-sub', 'No genome-wide study, ClinVar entry or ClinPGx finding: the evidence is candidate-gene studies of athletes.');
      }
    }
  });

  // Fitness theme: what the results mean in practice. Each score in a sentence for the person's band (fitness.json),
  // then the sport genes that matter in practice for their copies (sport_snps.json). The cards below hold the evidence.
  const thBand = (p) => p <= 5 ? 'Very low' : p <= 20 ? 'Low' : p < 40 ? 'Below average' : p <= 60 ? 'Average' : p < 80 ? 'Above average' : p < 95 ? 'High' : 'Very high';
  const thPos = (p) => p > 40 && p <= 60 ? 'middle' : p <= 50 ? `lowest ${Math.max(1, p)}%` : `highest ${Math.max(1, 100 - p)}%`;
  // Lowering the risk (cancer theme): the European Code Against Cancer's recommendations for the avoidable causes IARC
  // links to the theme's cancers (themes/cancer_prevention.json, window.GX_PREVENTION), the same for everyone
  dash.draw('th-prevention', (el) => {
    const card = el.closest('.gx-card'), on = gx.theme() === 'cancer';
    if (card) card.classList.toggle('th-off', !on);
    el.replaceChildren();
    const PV = window.GX_PREVENTION;
    if (!on || !PV) return;
    const make = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
    const by = new Map();
    for (const c of Object.values(PV.cancers)) for (const r of c.recommendations) {
      if (!by.has(r.n)) by.set(r.n, []);
      by.get(r.n).push(c.name);
    }
    make(el, 'h2', null, 'Lowering the risk');
    make(el, 'p', 'gx-note', 'The European Code Against Cancer (IARC/WHO, 5th edition): its recommendations for the avoidable causes that IARC classifies with sufficient evidence for the cancers of this theme, quoted as written. The same for everyone: genes shift the starting point, these lower it from there.');
    const grid = make(el, 'div', 'th-prev-grid');
    const recs = PV.recommendations.filter((r) => by.has(r.n)).sort((a, b) => by.get(b.n).length - by.get(a.n).length || a.n - b.n);
    for (const r of recs) {
      const d = make(grid, 'div', 'th-prev');
      make(d, 'b', null, r.topic);
      make(d, 'p', null, [r.text, ...(r.items || [])].filter(Boolean).join(' '));
      const chips = make(d, 'div', 'th-prev-chips');
      for (const nm of by.get(r.n)) make(chips, 'span', 'th-prev-chip', nm);
    }
    const none = Object.values(PV.cancers).filter((c) => !c.recommendations.length).map((c) => c.name);
    if (none.length) make(el, 'p', 'gx-note', `No avoidable cause with sufficient evidence is known for: ${none.join(', ')}.`);
    const src = make(el, 'p', 'gx-note');
    const a1 = make(src, 'a', null, 'European Code Against Cancer'); a1.href = PV.sources.ecac.en; a1.target = '_blank'; a1.rel = 'noopener';
    make(src, 'span', null, ' · ');
    const a2 = make(src, 'a', null, 'IARC: cancers by cause'); a2.href = PV.sources.iarc; a2.target = '_blank'; a2.rel = 'noopener';
  });

  dash.draw('th-fit-summary', (el) => {
    const card = el.closest('.gx-card'), on = dash.params().theme === 'muscle';
    if (card) card.classList.toggle('th-off', !on);
    if (!on) return;
    const r = gx.rows('fit_tests', 'sport_snps');
    if (!r) { if (gx.failed('fit_tests', 'sport_snps')) gx.failLine(el); return; }
    const [tests, snps] = r;
    el.replaceChildren();
    const who = (tests[0] || snps[0] || {}).person || gx.who();
    thMake(el, 'h2', null, `What it means for ${who}`);
    thMake(el, 'p', 'gx-note', 'Genes set the starting point; training, food and sleep decide how far you move from it. Each line reads one result in plain words. ' +
      'The cards below hold the evidence: the training session, the scores and the popular sport genes.');
    const list = thMake(el, 'div', 'th-mean-list');
    const row = (tone, title, tag, text) => {
      const d = thMake(list, 'div', 'th-mean th-mean-' + tone);
      const h = thMake(d, 'div', 'th-mean-head');
      thMake(h, 'b', null, title);
      if (tag) thMake(h, 'span', 'th-mean-tag', tag);
      thMake(d, 'div', null, text);
    };
    for (const t of tests) {
      for (const m of thJ(t.markers) || []) {
        if (!m.score || !m.meaning) continue;
        // Leaning low below the 40th percentile, high above the 60th: the same lines as the band words
        const p = m.score.percentile, band = p < 40 ? 'low' : p > 60 ? 'high' : 'typical';
        const tone = band === 'typical' || m.higher === 'neutral' ? 'even' : (band === 'high') === (m.higher === 'better') ? 'good' : 'bad';
        row(tone, m.name, `${thBand(p)} · ${thPos(p)}`, m.meaning[band]);
      }
    }
    // The genes: those whose copies carry a practical meaning, strongest evidence first; a carrier of a disease variant is flagged
    const watch = new Set(['rs1800562', 'rs17602729']);
    for (const s of snps.filter((x) => x.meaning).sort((a, b) => a.grade.localeCompare(b.grade) || a.topic_order - b.topic_order)) {
      row(watch.has(s.rsid) && s.alt_copies > 0 ? 'watch' : 'even', `${s.gene} ${s.genotype}`, s.topic_name, s.meaning);
    }
  });
