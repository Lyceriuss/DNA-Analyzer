  // Inheritance: what a child of an XX and an XY profile could inherit, as odds (cluster_analysis/inheritance). The
  // datasets hold every XX x XY pair; the pair picker chooses one. Each parent passes one of two copies, each with a
  // chance of one half; the odds are exact for the calls given, and each row says how far those calls can be trusted.
  const ihMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const ihJ = (s, d) => { if (s == null || s === '') return d; if (typeof s !== 'string') return s; try { return JSON.parse(s); } catch (e) { return d; } };
  const ihPct = (p) => p == null ? '–' : `${Math.round(p * 1000) / 10}%`.replace('.0%', '%');
  const IH_MODE = { AR: 'Recessive', AD: 'Dominant', XLR: 'X-linked recessive', XLD: 'X-linked dominant', XL: 'X-linked' };
  const IH_MODE_WHAT = {
    AR: 'A child shows it only with a variant copy from both parents; one copy makes a carrier.',
    AD: 'One variant copy is enough for a child to show it.',
    XLR: 'On the X: a son shows it with his mother\'s copy; a daughter needs a copy from both parents.',
    XLD: 'On the X: one copy is enough, in a son or a daughter.',
  };

  // The pair: the XX and XY chosen in the picker, else the selected profile and the first of the other sex
  const ihPair = () => {
    const P = dash.data('profiles');
    if (P.status !== 'ok') return null;
    const xx = P.data.filter((p) => p.sex === 'female'), xy = P.data.filter((p) => p.sex === 'male');
    const prm = dash.params(), who = gx.who();
    const a = (xx.find((p) => p.id === prm.ih_xx) || xx.find((p) => p.id === who) || xx[0] || {}).id;
    const b = (xy.find((p) => p.id === prm.ih_xy) || xy.find((p) => p.id === who) || xy[0] || {}).id;
    return { xx, xy, a, b, key: `${a}__${b}` };
  };
  const ihRows = (id, pair) => {
    const d = dash.data(id);
    return d.status === 'ok' ? d.data.filter((r) => r.pair === pair.key) : null;
  };
  const ihModeTag = (parent, m) => ihMake(parent, 'span', 'ih-mode ih-mode-' + (IH_MODE[m] ? m : 'none'), IH_MODE[m] || 'Mode not given by a source');

  // One stacked bar of shares with its key beneath: [[label, share, tone]]
  const ihBar = (parent, who, parts) => {
    const row = ihMake(parent, 'div', 'ih-odds-row');
    ihMake(row, 'span', 'ih-odds-who', who);
    const bar = ihMake(row, 'div', 'ih-bar');
    bar.setAttribute('role', 'img');
    bar.setAttribute('aria-label', parts.map(([l, p]) => `${l} ${ihPct(p)}`).join(', '));
    for (const [, p, tone] of parts) if (p > 0) { const s = ihMake(bar, 'span', 'ih-seg ' + tone); s.style.width = (p * 100) + '%'; }
    const key = ihMake(row, 'div', 'ih-key');
    // The label and its share are separate text nodes, so the Swedish layer translates the label on its own
    for (const [l, p, tone] of parts) { const k = ihMake(key, 'span'); ihMake(k, 'i', tone); ihMake(k, 'span', null, l); k.append(` ${ihPct(p)}`); }
  };

  // A parent's call at each variant: genotype, copies and how far the call can be trusted
  const ihParent = (parent, who, vs, side) => {
    const line = ihMake(parent, 'div', 'ih-parent');
    ihMake(line, 'b', null, who);
    for (const v of vs) {
      const c = v[side] || {};
      if (vs.length > 1) ihMake(line, 'span', 'ih-sub', v.rsid);
      ihMake(line, 'span', 'ih-gt', c.genotype || '–');
      ihMake(line, 'span', null, c.copies == null ? 'call not usable' : c.copies === 0 ? 'no variant copy' : c.copies === 1 ? 'one variant copy' : 'two variant copies');
      ihMake(line, 'span', 'ih-how' + (c.accuracy == null && c.copies ? ' ih-warn' : ''), c.how || '');
    }
  };

  // The short form of a call's accuracy for trait cards: "measured" or "imputed 99.3%", the whole sentence on hover
  const ihTag = (parent, c) => {
    const short = c.copies == null ? 'not usable' : c.tier === 'measured' ? (c.accuracy == null ? 'measured, rare' : 'measured')
      : c.accuracy != null ? `imputed ${ihPct(c.accuracy)}` : 'imputed';
    const t = ihMake(parent, 'span', 'ih-tag' + (c.accuracy == null ? ' ih-warn' : ''), short);
    t.title = c.how || '';
  };
  const ihParentShort = (parent, who, vs, side) => {
    const line = ihMake(parent, 'div', 'ih-parent');
    ihMake(line, 'b', null, who);
    const cs = vs.map((v) => v[side] || {});
    ihMake(line, 'span', 'ih-gt', cs.map((c) => c.genotype || '–').join(' · '));
    const n = cs.some((c) => c.copies == null) ? null : cs.reduce((s, c) => s + c.copies, 0);
    ihMake(line, 'span', null, n == null ? 'call not usable' : n === 0 ? 'no variant copy' : n === 1 ? 'one variant copy' : 'two variant copies');
    const worst = cs.find((c) => c.copies == null) || cs.find((c) => c.accuracy == null) || cs.reduce((a, c) => (c.accuracy < a.accuracy ? c : a), cs[0]);
    ihTag(line, worst);
  };

  // The child's sex: XX or XY, chosen in the hero. It decides which parent gives more of the DNA (a son's X is his
  // mother's, his Y his father's), which X-linked outcome shows, and hides traits studied in the other sex only.
  const ihSex = () => (dash.params().ih_sex === 'XY' ? 'XY' : 'XX');
  const ihForSex = (r) => !r.studied_sex || r.studied_sex === (ihSex() === 'XX' ? 'female' : 'male');
  const SVGNS = 'http://www.w3.org/2000/svg';
  const ihSvg = (parent, tag, attrs) => { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); parent.appendChild(e); return e; };

  // A drawn baby (original artwork): round head, sleepy eyes, rosy cheeks, a curl, a onesie with the sex chromosomes
  const ihBaby = (parent, sex) => {
    const svg = ihSvg(parent, 'svg', { viewBox: '0 0 200 230', class: 'ih-baby', role: 'img', 'aria-label': `A child, ${sex}` });
    ihSvg(svg, 'ellipse', { cx: 100, cy: 222, rx: 62, ry: 6, class: 'ih-b-shadow' });
    ihSvg(svg, 'path', { d: 'M48 228 C46 178 64 150 100 150 C136 150 154 178 152 228 Z', class: 'ih-b-suit' });
    ihSvg(svg, 'circle', { cx: 52, cy: 186, r: 14, class: 'ih-b-skin' });
    ihSvg(svg, 'circle', { cx: 148, cy: 186, r: 14, class: 'ih-b-skin' });
    ihSvg(svg, 'circle', { cx: 40, cy: 92, r: 13, class: 'ih-b-skin' });
    ihSvg(svg, 'circle', { cx: 160, cy: 92, r: 13, class: 'ih-b-skin' });
    ihSvg(svg, 'circle', { cx: 100, cy: 90, r: 62, class: 'ih-b-skin' });
    ihSvg(svg, 'path', { d: 'M98 30 C86 22 90 8 102 10 C112 12 112 24 104 26', class: 'ih-b-curl' });
    ihSvg(svg, 'path', { d: 'M70 92 Q79 83 88 92', class: 'ih-b-line' });
    ihSvg(svg, 'path', { d: 'M112 92 Q121 83 130 92', class: 'ih-b-line' });
    ihSvg(svg, 'ellipse', { cx: 66, cy: 110, rx: 11, ry: 7, class: 'ih-b-cheek' });
    ihSvg(svg, 'ellipse', { cx: 134, cy: 110, rx: 11, ry: 7, class: 'ih-b-cheek' });
    ihSvg(svg, 'path', { d: 'M90 116 Q100 126 110 116', class: 'ih-b-line' });
    ihSvg(svg, 'rect', { x: 78, y: 176, width: 44, height: 26, rx: 13, class: 'ih-b-badge' });
    const t = ihSvg(svg, 'text', { x: 100, y: 194, class: 'ih-b-badge-text', 'text-anchor': 'middle' });
    t.textContent = sex;
    return svg;
  };

  // A small "cake": a donut of two shares, each parent's colour, with the labels beside it
  const ihCake = (parent, parts, size = 120, centre) => {
    const box = ihMake(parent, 'div', 'ih-cake');
    const svg = ihSvg(box, 'svg', { viewBox: '0 0 120 120', width: size, height: size, role: 'img',
      'aria-label': parts.map((p) => `${p.label} ${ihPct(p.share)}`).join(', ') });
    const r = 46, c = 2 * Math.PI * r;
    ihSvg(svg, 'circle', { cx: 60, cy: 60, r, class: 'ih-cake-bg' });
    let off = 0;
    for (const p of parts) {
      if (!(p.share > 0)) continue;
      ihSvg(svg, 'circle', { cx: 60, cy: 60, r, class: 'ih-cake-slice ' + p.cls,
        'stroke-dasharray': `${Math.max(0, p.share * c - 2)} ${c}`, 'stroke-dashoffset': -off, transform: 'rotate(-90 60 60)' });
      off += p.share * c;
    }
    if (centre) { const t = ihSvg(svg, 'text', { x: 60, y: 66, 'text-anchor': 'middle', class: 'ih-cake-centre' }); t.textContent = centre; }
    const key = ihMake(box, 'div', 'ih-cake-key');
    for (const p of parts) {
      const k = ihMake(key, 'div');
      ihMake(k, 'i', p.cls);
      const t = ihMake(k, 'div');
      const line = ihMake(t, 'div');
      ihMake(line, 'b', null, p.label).setAttribute('data-i18n-skip', '');
      ihMake(line, 'span', 'ih-cake-pct', ihPct(p.share));
      if (p.note) ihMake(t, 'div', 'ih-sub', p.note);
    }
    return box;
  };

  // The hero: the pair, the child's sex, and how much of the child's DNA each parent gives
  dash.draw('ih-hero', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair) return;
    if (!pair.xx.length || !pair.xy.length) { ihMake(el, 'p', 'ih-empty', 'This needs an XX and an XY profile: add a person of the other sex to see what a child of the two could inherit.'); return; }
    const sex = ihSex();
    const meta = (ihRows('inh_meta', pair) || [])[0];
    const wrap = ihMake(el, 'div', 'ih-hero');
    const left = ihMake(wrap, 'div', 'ih-hero-baby');
    ihBaby(left, sex);
    const seg = ihMake(left, 'div', 'gx-profile-set ih-sexpick');
    seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'The child');
    for (const s of ['XX', 'XY']) {
      const b = ihMake(seg, 'button', null, s);
      b.type = 'button'; b.setAttribute('aria-pressed', String(s === sex)); b.setAttribute('data-i18n-skip', '');
      b.addEventListener('click', () => dash.setParams({ ih_sex: s }));
    }

    const mid = ihMake(wrap, 'div', 'ih-hero-text');
    ihMake(mid, 'span', 'gx-label', 'A child of');
    const h = ihMake(mid, 'h2', 'ih-hero-title');
    h.setAttribute('data-i18n-skip', '');
    ihMake(h, 'span', 'ih-who-xx', pair.a); h.append(' + '); ihMake(h, 'span', 'ih-who-xy', pair.b);
    const picks = ihMake(mid, 'div', 'ih-picks');
    for (const [label, list, cur, param, cls] of [['XX', pair.xx, pair.a, 'ih_xx', 'ih-who-xx'], ['XY', pair.xy, pair.b, 'ih_xy', 'ih-who-xy']]) {
      if (list.length < 2) continue;
      const pick = ihMake(picks, 'div', 'ih-pick');
      ihMake(pick, 'span', cls, label);
      const set = ihMake(pick, 'div', 'gx-profile-set');
      set.setAttribute('role', 'group'); set.setAttribute('aria-label', label);
      for (const p of list) {
        const b = ihMake(set, 'button', null, p.id);
        b.type = 'button'; b.setAttribute('aria-pressed', String(p.id === cur)); b.setAttribute('data-i18n-skip', '');
        b.addEventListener('click', () => dash.setParams({ [param]: p.id }));
      }
    }
    ihMake(mid, 'p', 'ih-hero-lede', sex === 'XX'
      ? 'A daughter gets one half of her DNA from each parent: one copy of every chromosome from her mother and one from her father, including an X from each.'
      : 'A son gets one copy of every chromosome from each parent, except that his X comes from his mother and his much smaller Y from his father.');
    if (!meta) { ihMake(mid, 'p', 'ih-empty', `No inheritance results for ${pair.a} and ${pair.b} yet: python -m cluster_analysis.inheritance --pair ${pair.a} ${pair.b}`); return; }

    const g = ihJ(meta.genome, null);
    const right = ihMake(wrap, 'div', 'ih-hero-cake');
    ihMake(right, 'span', 'gx-label', 'Where the DNA comes from');
    if (g && g[sex]) {
      ihCake(right, [{ label: pair.a, share: g[sex].XX, cls: 'ih-c-xx', note: sex === 'XY' ? 'X and mitochondria too' : 'an X and the mitochondria' },
        { label: pair.b, share: g[sex].XY, cls: 'ih-c-xy', note: sex === 'XY' ? 'the Y' : 'an X' }], 132, sex);
      ihMake(right, 'p', 'ih-src', 'Chromosome lengths: Ensembl, GRCh38.');
    }
  });

  // Results (CLAUDE.md): a short population band and the trait's direction, "Top 25% · taller", never a rank or a
  // sentence. The band and the direction word are keys of their own, so the Swedish layer translates both.
  const ihBandOf = (pct) => pct >= 50 ? [`Top ${Math.max(1, Math.round(100 - pct))}%`, 1] : [`Bottom ${Math.max(1, Math.round(pct))}%`, -1];
  const ihBand = (pct, more, less) => { const [b, d] = ihBandOf(pct); return `${b} · ${d > 0 ? more : less}`; };
  // A trait's two directions: the featured list names them; otherwise higher or lower (risk, for a disease's odds)
  // An age ("age at menarche") is earlier or later, not lower or higher
  const ihAge = (r) => /^age (at|of) /i.test(r.trait || '');
  const ihDirs = (r, f) => f && f.more ? [f.more, f.less] : ihAge(r) ? ['later', 'earlier'] : r.kind === 'odds ratio' ? ['higher risk', 'lower risk'] : ['higher', 'lower'];

  // How the prediction works: one text that starts simple and gets more exact as it goes, the formulas folded away
  dash.draw('ih-explain', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || !pair.xx.length || !pair.xy.length) return;
    const meta = (ihRows('inh_meta', pair) || [])[0] || {};
    ihMake(el, 'h3', 'ih-explain-title', 'How the prediction works');
    const intro = ihMake(el, 'div', 'ih-flow');
    for (const t of [
      'Everyone has two copies of each gene, one from each of their parents. Mendel\'s first law says what happens next: a parent passes on one of their two copies to a child, and which one is a coin toss, each with an even chance, for every gene on its own.',
      'That gives two kinds of gene. Where a parent\'s two copies are the same letter, the toss doesn\'t matter: the child gets that letter for certain. Where they differ, it is 50/50. Whether a version is dominant or recessive changes how the pair a child receives shows, not which copy it gets.',
    ]) ihMake(intro, 'p', null, t);
    // Two small squares: the parents' letters along the edges, the child's possible pairs inside
    const sq = ihMake(el, 'div', 'ih-mendel');
    // Each square reads from the top down: the parents' letters, what each can pass on, every combination, the result
    for (const [title, m, f] of [['Left to chance', ['C', 'T'], ['C', 'T']], ['Settled', ['T', 'T'], ['C', 'C']]]) {
      const c = ihMake(sq, 'div', 'ih-mendel-card');
      ihMake(c, 'b', 'ih-mendel-title', title);
      const parents = ihMake(c, 'div', 'ih-mendel-parents');
      for (const [label, letters, cls] of [['Parent 1', m, 'ih-who-xx'], ['Parent 2', f, 'ih-who-xy']]) {
        const pp = ihMake(parents, 'div', 'ih-mendel-parent');
        ihMake(pp, 'span', 'ih-sub ' + cls, label);
        const ls = ihMake(pp, 'div', 'ih-letters');
        ls.setAttribute('data-i18n-skip', '');
        for (const x of letters) ihMake(ls, 'span', 'ih-letter', x);
        const passes = [...new Set(letters)];
        ihMake(pp, 'span', 'ih-sub', passes.length === 1 ? `always passes ${passes[0]}` : `passes ${passes[0]} or ${passes[1]}, 50/50`);
      }
      const g = ihMake(c, 'div', 'ih-punnett ih-mendel-grid');
      g.setAttribute('data-i18n-skip', '');
      ihMake(g, 'span', 'ih-pa', '');
      for (const x of f) ihMake(g, 'span', 'ih-pa ih-who-xy', x);
      const count = {};
      for (const y of m) {
        ihMake(g, 'span', 'ih-pa ih-who-xx', y);
        for (const x of f) {
          const kid = [y, x].sort().join('');
          count[kid] = (count[kid] || 0) + 1;
          ihMake(g, 'span', 'ih-cell ' + (kid === 'TT' ? 't-trait' : kid === 'CT' ? 't-half' : ''), kid);
        }
      }
      const res = ihMake(c, 'div', 'ih-mendel-result');
      ihMake(res, 'span', 'ih-sub', Object.keys(count).length === 1 ? 'Every child gets' : 'A child gets');
      for (const k of ['CC', 'CT', 'TT']) {
        if (!count[k]) continue;
        const chip = ihMake(res, 'span', 'ih-combo');
        ihMake(chip, 'b', null, k).setAttribute('data-i18n-skip', '');
        chip.append(` ${count[k] * 25}%`);
      }
    }
    const body = ihMake(el, 'div', 'ih-flow');
    for (const t of [
      'Large studies have compared the genes of hundreds of thousands of people with their height, their sleep, their blood values and many other traits. They found small differences in the genes that each push a trait slightly up or down. One on its own does very little; together they add up.',
      `For each trait we take one such study from the GWAS Catalog, a public database of these studies. It lists the gene differences that matter most and how much each one pushes the trait. Adding them up for ${pair.a} and for ${pair.b}, and comparing each total with Europeans in general, shows where each parent's genes place them: in the top or the bottom part, and how far, such as the top 24% for height.`,
      'For a child of the two, many of these genes are settled: both parents carry two identical letters, so the child\'s pair is certain. The rest are coin tosses. The child\'s most likely place adds up the settled genes as they are and each coin toss at its even odds; the blue field is how far the coin tosses could move a child either way, the range 8 in 10 of the couple\'s children would land in. Open a trait to see which genes are settled and which are left to chance.',
      'For traits like these the genes simply add up. A study of 70 traits in 254,679 people found that dominance, one version masking the other, adds almost nothing to how such traits vary (Hivert et al., American Journal of Human Genetics 2021); where it does matter, in single-gene traits and inherited conditions, the sections below use it.',
    ]) ihMake(body, 'p', null, t);
    const tech = ihMake(el, 'details', 'ih-tech');
    ihMake(tech, 'summary', null, 'Technical details');
    for (const t of [
      'Per trait, one anchor study: European, at least 10,000 people, the most lead variants once only the strongest per 500 kb is kept. Effect alleles are placed on the forward strand against the 1000 Genomes high-coverage sites, with their European frequency f; betas, or the log of odds ratios, are the weights w. Population mean Σ2fw, variance Σ2f(1−f)w². A parent passes the effect allele with chance d/2 (f when the call can\'t be used); the child\'s expectation is Σ(q₁+q₂)w with variance Σ[q₁(1−q₁)+q₂(1−q₂)]w², placed with a normal approximation. Bands: top 10% from the 90th percentile, top 25% from the 75th, middle 50% between the 25th and 75th.',
      'Genes that sit close together on a chromosome tend to be passed on together. The prediction treats each variant as passed on by itself; that leaves the most likely place unchanged and makes the field an estimate. Lead variants carry a part of each trait\'s heritability, and for some traits part of a GWAS association runs through the family environment rather than the child\'s own DNA (for educational attainment about half: Okbay et al., Nature Genetics 2022). The score places the variants, not the person.',
    ]) ihMake(tech, 'p', null, t);
  });

  // Where the traits, their groups and their effects come from: the GWAS Catalog, shown with its logo
  const ihSource = (parent, meta) => {
    const src = ihMake(parent, 'div', 'ih-sourcebar');
    const la = ihMake(src, 'a', 'ih-sourcelogo'); la.href = 'https://www.ebi.ac.uk/gwas/'; la.target = '_blank'; la.rel = 'noopener';
    la.setAttribute('aria-label', 'GWAS Catalog');
    const logo = ihMake(la, 'img'); logo.src = 'logos/gwas.ico'; logo.alt = '';
    const st = ihMake(src, 'p');
    st.append('Traits, studies and effects: ');
    const ga = ihMake(st, 'a', null, 'the GWAS Catalog'); ga.href = 'https://www.ebi.ac.uk/gwas/'; ga.target = '_blank'; ga.rel = 'noopener';
    st.append(' (EMBL-EBI and NHGRI). Each trait is a term in ');
    const ea = ihMake(st, 'a', null, 'EFO'); ea.href = 'https://www.ebi.ac.uk/efo/'; ea.target = '_blank'; ea.rel = 'noopener';
    st.append(`${meta.efo_version ? ' ' + meta.efo_version : ''}, which gives its definition; the Catalog's `);
    const ta = ihMake(st, 'a', null, 'trait mapping file'); ta.href = 'https://www.ebi.ac.uk/gwas/docs/file-downloads'; ta.target = '_blank'; ta.rel = 'noopener';
    st.append(' gives the groups. Frequencies: the 1000 Genomes Project. Chromosome lengths: Ensembl.');
    return src;
  };

  // How to read a scale, on a real example: what each mark is and why the children's field can be wide
  const ihLegend = (parent, r, pair, f) => {
    const box = ihMake(parent, 'div', 'ih-legend');
    const head = ihMake(box, 'div', 'ih-legend-head');
    ihMake(head, 'b', null, 'How to read a scale');
    ihMake(head, 'span', 'ih-sub', `Example: ${f.name}`);
    ihScale(box, r, pair, [f.more, f.less]);
    const items = ihMake(box, 'div', 'ih-legend-items');
    const item = (swatch, title, text) => {
      const it = ihMake(items, 'div', 'ih-legend-item');
      ihMake(it, 'span', 'ih-legend-swatch ' + swatch);
      const t = ihMake(it, 'div');
      ihMake(t, 'b', null, title);
      ihMake(t, 'p', null, text);
    };
    item('sw-xx', pair.a, `Where ${pair.a}'s own genes place ${pair.a} among Europeans.`);
    item('sw-xy', pair.b, `Where ${pair.b}'s own genes place ${pair.b}.`);
    item('sw-dot', 'A child, most likely', 'The middle of what the two parents can pass on.');
    item('sw-range98', 'The lighter field', 'Where 98 in 100 of their children would land. A child could only go further if nearly every coin toss went the same way, which is very unlikely.');
    item('sw-range', 'The blue field', 'Where 8 in 10 of their children would land. Each child draws its own mix of the parents\' copies. Where a parent carries two different versions of a gene, which one a child gets is a coin toss, so the more such places, the wider the field: children of the same parents can then differ a lot.');
    return box;
  };

  // One trait on a scale among Europeans: both parents' marks, the child's range and most likely place; the ends and
  // the middle labelled with the trait's directions
  const ihScale = (parent, r, pair, dirs) => {
    const pos = (p) => `${Math.max(0, Math.min(100, p))}%`;
    const wrap = ihMake(parent, 'span', 'ih-scalewrap');
    const scale = ihMake(wrap, 'span', 'ih-scale');
    scale.setAttribute('role', 'img');
    const [more, less] = dirs || ['higher', 'lower'];
    scale.setAttribute('aria-label', `${pair.a}: ${ihBand(r.XX_pct, more, less)}; ${pair.b}: ${ihBand(r.XY_pct, more, less)}; a child: ${ihBand(r.child_pct, more, less)}`);
    ihMake(scale, 'span', 'ih-mid');
    if (r.child_lo98 != null) {
      const outer = ihMake(scale, 'span', 'ih-range98'); outer.style.left = pos(r.child_lo98); outer.style.width = `${Math.max(0.8, r.child_hi98 - r.child_lo98)}%`;
    }
    const rng = ihMake(scale, 'span', 'ih-range'); rng.style.left = pos(r.child_lo); rng.style.width = `${Math.max(0.8, r.child_hi - r.child_lo)}%`;
    ihMake(scale, 'span', 'ih-mk ih-mk-xx').style.left = pos(r.XX_pct);
    ihMake(scale, 'span', 'ih-mk ih-mk-xy').style.left = pos(r.XY_pct);
    ihMake(scale, 'span', 'ih-mk ih-mk-child').style.left = pos(r.child_pct);
    if (dirs) {
      const ax = ihMake(wrap, 'span', 'ih-axis');
      ihMake(ax, 'span', null, less);
      ihMake(ax, 'span', null, 'average');
      ihMake(ax, 'span', null, more);
    }
    return wrap;
  };

  // The genes behind a prediction, in two groups: the settled ones (both parents carry two identical letters, so the
  // child's pair is certain) and the ones left to chance (a parent carries two different letters: a coin toss).
  // The settled ones fix where the child lands; the chance ones are what makes the blue field.
  const ihGenes = (parent, r, pair, dirs) => {
    const [more, less] = dirs || ['higher', 'lower'];
    const gt = (v, n) => n == null ? 'not read' : n === 2 ? v.allele + v.allele : n === 1 ? [v.allele, v.other].sort().join('') : v.other + v.other;
    const box = ihMake(parent, 'div', 'ih-genes');
    const table = (title, note, list) => {
      if (!list.length) return;
      const h = ihMake(box, 'div', 'ih-genes-head');
      ihMake(h, 'b', null, title);
      ihMake(h, 'span', 'ih-sub', note);
      const tbl = ihMake(box, 'table', 'gx-table ih-vtable');
      const hr = ihMake(ihMake(tbl, 'thead'), 'tr');
      for (const c of ['Gene', 'Variant', 'Letter that pushes', pair.a, pair.b, 'A child gets', 'Compared with most Europeans']) ihMake(hr, 'th', null, c);
      const tb = ihMake(tbl, 'tbody');
      for (const v of list) {
        const tr = ihMake(tb, 'tr');
        ihMake(tr, 'td', null, (v.gene || '').split(/[ ,;-]+/).filter(Boolean).slice(0, 2).join(', ') || '–').setAttribute('data-i18n-skip', '');
        ihMake(tr, 'td', 'ih-mono', v.rsid);
        const eff = ihMake(tr, 'td');
        ihMake(eff, 'span', 'ih-gt', v.allele);
        eff.append(' ');
        ihMake(eff, 'span', null, `towards ${v.raises ? more : less}`);
        for (const n of [v.XX, v.XY]) ihMake(tr, 'td', n == null ? 'ih-unread' : 'ih-mono', gt(v, n));
        const kid = ihMake(ihMake(tr, 'td'), 'div', 'ih-combos');
        const cp = v.child_p || [];
        [0, 1, 2].forEach((k) => {
          if (!(cp[k] > 0.0005)) return;
          const c = ihMake(kid, 'span', 'ih-combo');
          ihMake(c, 'b', null, gt(v, k));
          c.append(` ${ihPct(cp[k])}`);
        });
        // The letter's copies in the child (on average, for a coin toss) against an average European's
        const cmp = ihMake(ihMake(tr, 'td'), 'div', 'ih-cmp');
        const fmt = (x) => (Math.round(x * 100) / 100).toString();
        ihMake(cmp, 'span', 'ih-sub', `${fmt(v.child_mean)} ${v.allele} vs ${fmt(v.average ?? 2 * v.freq)}`);
        const way = Math.abs(v.shift) < 0.005 ? null : v.shift > 0 ? more : less;
        ihMake(cmp, 'span', way ? (v.shift > 0 ? 'ih-up' : 'ih-down') : 'ih-sub', way ? `towards ${way}` : 'as most people');
      }
    };
    ihMake(box, 'p', 'ih-sub', 'Everyone carries 0, 1 or 2 copies of each letter. What moves a child is how many it gets compared with most Europeans: where a letter is common, one copy is fewer than most people have, and pushes the other way.');
    table(`Settled: ${r.n_settled} genes`, 'Both parents carry two identical letters here, so the child gets this pair whatever happens. These set where the child lands.',
      ihJ(r.settled, []));
    table(`Left to chance: ${r.n_chance + r.n_unread} genes`, 'A parent carries two different letters here, so which one the child gets is a coin toss. These make the blue field wide or narrow.' +
      (r.n_unread ? ' Where a parent is not read, each letter counts with how common it is among Europeans.' : ''), ihJ(r.chance, []));
    return box;
  };

  // Which parent the child's lean comes from: a cake of the two pushes, each with its direction
  const ihPushCake = (parent, r, pair, size = 92, dirs) => {
    const a = Math.abs(r.push_XX || 0), b = Math.abs(r.push_XY || 0);
    if (a + b < 0.05) { ihMake(parent, 'p', 'ih-sub', 'Neither parent moves the child much: around average.'); return; }
    const [more, less] = dirs || ['higher', 'lower'];
    const dir = (x) => `towards ${x >= 0 ? more : less}`;
    ihCake(parent, [{ label: pair.a, share: a / (a + b), cls: 'ih-c-xx', note: dir(r.push_XX) },
      { label: pair.b, share: b / (a + b), cls: 'ih-c-xy', note: dir(r.push_XY) }], size);
  };

  // The familiar traits first: where a child is most likely to land among Europeans, as a band and a direction
  dash.draw('ih-featured', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || !pair.xx.length || !pair.xy.length) return;
    const rows = ihRows('inh_predictions', pair), meta = (ihRows('inh_meta', pair) || [])[0];
    if (!rows || !meta) return;
    const by = new Map(rows.map((r) => [r.id, r]));
    const picks = ihJ(meta.featured, []).filter((f) => f.more).map((f) => [f, by.get(f.id)]).filter(([, r]) => r && ihForSex(r));
    if (!picks.length) return;
    const head = ihMake(el, 'div', 'ih-sec-head');
    ihMake(head, 'h3', null, 'Familiar traits');
    ihMake(head, 'p', null, `A child of ${pair.a} and ${pair.b}, compared with Europeans.`);
    const ex = picks.find(([f]) => f.id === 'EFO_0008328') || picks[0];
    ihLegend(el, ex[1], pair, ex[0]);
    const grid = ihMake(el, 'div', 'ih-feat');
    for (const [f, r] of picks) {
      const dirs = [f.more, f.less];
      const [band, d] = ihBandOf(r.child_pct);
      const card = ihMake(grid, 'div', 'ih-fcard');
      const top = ihMake(card, 'div', 'ih-fhead');
      ihMake(top, 'span', 'gx-label', f.name);
      const big = ihMake(top, 'div', 'ih-fbigrow');
      ihMake(big, 'h4', 'ih-fbig', band);
      ihMake(big, 'span', 'ih-fdir', d > 0 ? f.more : f.less);
      // What the study measured: its own name for the trait, and EFO's definition
      const meas = ihMake(card, 'p', 'ih-fmeas');
      meas.append('What the study measured: ');
      ihMake(meas, 'b', null, r.reported || r.trait).setAttribute('data-i18n-skip', '');
      if (r.definition) { const dd = ihMake(meas, 'span', 'ih-fdef', ` · ${r.definition.split(/(?<=\.)\s/)[0]}`); dd.setAttribute('data-i18n-skip', ''); }
      ihScale(card, r, pair, dirs);
      const par = ihMake(card, 'p', 'ih-fpar');
      for (const [side, cls, pct] of [[pair.a, 'ih-who-xx', r.XX_pct], [pair.b, 'ih-who-xy', r.XY_pct]]) {
        const s = ihMake(par, 'span');
        ihMake(s, 'b', cls, side).setAttribute('data-i18n-skip', '');
        s.append(': ');
        ihMake(s, 'span', null, ihBand(pct, ...dirs));
      }
      const split = ihMake(card, 'div', 'ih-split');
      const tot = (r.n_settled + r.n_chance + r.n_unread) || 1;
      const sb = ihMake(split, 'div', 'ih-splitbar');
      for (const [n, cls] of [[r.n_settled, 'sp-settled'], [r.n_chance, 'sp-chance'], [r.n_unread, 'sp-unread']]) {
        if (n) ihMake(sb, 'span', cls).style.width = `${(100 * n) / tot}%`;
      }
      const st = ihMake(split, 'span', 'ih-sub');
      st.append(`${tot} genes: `);
      ihMake(st, 'b', 'sp-t-settled', `${r.n_settled} settled`);
      st.append(' · ');
      ihMake(st, 'b', 'sp-t-chance', `${r.n_chance} by chance`);
      if (r.n_unread) st.append(` · ${r.n_unread} not read`);
      const open = ihMake(card, 'details', 'ih-fopen');
      ihMake(open, 'summary', null, 'See the genes and the possible combinations');
      ihGenes(open, r, pair, dirs);
      const foot = ihMake(card, 'div', 'ih-ffoot');
      ihPushCake(foot, r, pair, 76, dirs);
      const src = ihMake(foot, 'p', 'ih-src');
      src.textContent = `${r.author} ${r.year}, ${Number(r.n).toLocaleString('en')} people, ${r.used_both} of ${r.variants} variants read in both parents.`;
      src.setAttribute('data-i18n-skip', '');
    }
  });

  // Predicted traits: for every GWAS trait both parents can be read for, each parent's place among Europeans and the
  // child's expected place with the range 80% of their children would fall in
  let ihShown = 40, ihTyping = false;
  const IH_SORT = { differs: 'Child furthest from average', parents: 'Parents furthest apart', name: 'A to Z' };
  dash.draw('ih-predictions', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || !pair.xx.length || !pair.xy.length) return;
    const rows = ihRows('inh_predictions', pair);
    if (!rows) return;
    const prm = dash.params();
    const head = ihMake(el, 'div', 'ih-sec-head');
    const meta = (ihRows('inh_meta', pair) || [])[0] || {};
    const catDefs = ihJ(meta.categories, {});
    const all = rows;
    const hidden = all.filter((r) => !ihForSex(r)).length;
    const shown = all.filter(ihForSex);
    ihMake(head, 'h3', null, `All ${shown.length.toLocaleString('en')} traits`);
    ihMake(head, 'p', null, 'Every trait in the GWAS Catalog with enough of its variants read in both parents, grouped the way the Catalog groups them. ' +
      'Open a trait for what it measures, how much each parent pushes the child, and the variants behind it.' +
      (hidden ? ` ${hidden} traits studied in ${ihSex() === 'XX' ? 'men' : 'women'} only are left out for ${ihSex() === 'XX' ? 'a daughter' : 'a son'}.` : ''));
    if (!shown.length) { ihMake(el, 'p', 'ih-empty', 'No predictions for this pair yet.'); return; }

    const cats = {};
    for (const r of shown) cats[r.category] = (cats[r.category] || 0) + 1;
    const cat = cats[prm.ih_cat] ? prm.ih_cat : null;
    ihSource(el, meta);
    const controls = ihMake(el, 'div', 'ih-controls');
    const bar = ihMake(controls, 'div', 'ih-search');
    const group = ihMake(bar, 'select', 'md-select');
    group.setAttribute('aria-label', 'Group');
    const og = ihMake(group, 'option', null, `All groups (${shown.length.toLocaleString('en')})`); og.value = '';
    for (const [c, n] of Object.entries(cats).sort((a, b) => b[1] - a[1])) { const o = ihMake(group, 'option', null, `${c} (${n})`); o.value = c; o.selected = c === cat; }
    group.addEventListener('change', () => { ihShown = 40; dash.setParams({ ih_cat: group.value }); });
    // The chosen group: the EFO term the Catalog files its traits under, with EFO's definition
    if (cat && catDefs[cat]) {
      const d = catDefs[cat];
      const p = ihMake(controls, 'p', 'ih-catdef');
      ihMake(p, 'b', null, cat);
      p.append(` · the GWAS Catalog's group for traits under the EFO term "${d.label || ''}"` + (d.definition ? `: ${d.definition}` : '.'));
    }
    const q = ihMake(bar, 'input', 'md-search');
    q.type = 'search'; q.placeholder = 'Search a trait or a gene'; q.value = prm.ih_q || '';
    let t;
    q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { ihShown = 40; ihTyping = true; dash.setParams({ ih_q: q.value }); }, 250); });
    if (ihTyping) { ihTyping = false; q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
    const sel = ihMake(bar, 'select', 'md-select');
    for (const [k, l] of Object.entries(IH_SORT)) { const o = ihMake(sel, 'option', null, l); o.value = k; o.selected = (prm.ih_sort || 'differs') === k; }
    sel.addEventListener('change', () => dash.setParams({ ih_sort: sel.value }));

    const needle = (prm.ih_q || '').toLowerCase();
    let list = shown.filter((r) => (!cat || r.category === cat) &&
      (!needle || r.trait.toLowerCase().includes(needle) || ihJ(r.top, []).some((v) => (v.gene || '').toLowerCase().includes(needle))));
    const sort = prm.ih_sort || 'differs';
    list = list.slice().sort(sort === 'name' ? (a, b) => a.trait.localeCompare(b.trait)
      : sort === 'parents' ? (a, b) => Math.abs(b.XX_z - b.XY_z) - Math.abs(a.XX_z - a.XY_z)
        : (a, b) => Math.abs(b.child_z) - Math.abs(a.child_z));
    ihMake(el, 'p', 'ih-sub', `${list.length.toLocaleString('en')} traits`);

    // The scale: 0 to 100 among Europeans, with the middle marked
    const key = ihMake(el, 'div', 'ih-pkey');
    for (const [cls, label] of [['ih-mk-xx', pair.a], ['ih-mk-xy', pair.b], ['ih-mk-child', 'A child: where 8 in 10 would land, and the most likely place']]) {
      const s = ihMake(key, 'span'); ihMake(s, 'i', 'ih-mk ' + cls); ihMake(s, 'span', null, label);
    }
    const box = ihMake(el, 'div', 'ih-plist');
    const pos = (p) => `${Math.max(0, Math.min(100, p))}%`;
    for (const r of list.slice(0, ihShown)) {
      const row = ihMake(box, 'details', 'ih-prow');
      const sum = ihMake(row, 'summary');
      const name = ihMake(sum, 'span', 'ih-pname');
      ihMake(name, 'b', null, r.trait).setAttribute('data-i18n-skip', '');
      ihMake(name, 'span', 'ih-sub', r.category);
      const dirs = ihDirs(r);
      ihScale(sum, r, pair);
      ihMake(sum, 'span', 'ih-pnum', ihBand(r.child_pct, ...dirs));

      const body = ihMake(row, 'div', 'ih-pbody');
      // What it measures: EFO's definition, and the trait as the study named it
      const what = ihMake(body, 'div', 'ih-what');
      ihMake(what, 'span', 'gx-label', 'What this measures');
      const def = ihMake(what, 'p', null, r.definition || 'EFO gives this term no definition.');
      def.setAttribute('data-i18n-skip', '');
      const rep = ihMake(what, 'p', 'ih-sub');
      rep.append('The study named it: ');
      ihMake(rep, 'i', null, r.reported || r.trait).setAttribute('data-i18n-skip', '');
      rep.append(ihAge(r) ? '. Higher on the scale means later.' : r.kind === 'odds ratio' ? '. Higher on the scale means higher odds of it.' : '. Higher on the scale means more of it.');
      const push = ihMake(body, 'div', 'ih-pushrow');
      ihMake(push, 'span', 'gx-label', 'Who pushes the child where');
      ihPushCake(push, r, pair, 84, dirs);
      const words = ihMake(body, 'p', 'ih-fpar');
      for (const [side, cls, z] of [[pair.a, 'ih-who-xx', r.XX_pct], [pair.b, 'ih-who-xy', r.XY_pct], ['A child', '', r.child_pct]]) {
        const s = ihMake(words, 'span');
        const b = ihMake(s, 'b', cls || null, side);
        if (cls) b.setAttribute('data-i18n-skip', '');
        s.append(': ');
        ihMake(s, 'span', null, ihBand(z, ...dirs));
      }
      const st = ihMake(body, 'p', 'ih-sub');
      st.append(`${r.used_both} of ${r.variants} lead variants read in both parents; the others count as the European average. ` +
        `In the study's own units, a child is expected at ${r.child_z > 0 ? '+' : ''}${r.child_z} standard deviations, 8 in 10 between ${Math.round((r.child_z - 1.2816 * r.child_sd) * 100) / 100} and ${Math.round((r.child_z + 1.2816 * r.child_sd) * 100) / 100}.`);
      const src = ihMake(body, 'p', 'ih-src');
      src.append(`${r.author} ${r.year}, ${Number(r.n).toLocaleString('en')} people, ${r.kind === 'odds ratio' ? 'odds ratios' : 'effect sizes'} from `);
      const a = ihMake(src, 'a', null, r.study); a.href = `https://www.ebi.ac.uk/gwas/studies/${r.study}`; a.target = '_blank'; a.rel = 'noopener';
      src.setAttribute('data-i18n-skip', '');
      ihGenes(body, r, pair, dirs);
    }
    if (list.length > ihShown) {
      const b = ihMake(el, 'button', 'md-pill', `Show more (${(list.length - ihShown).toLocaleString('en')} left)`);
      b.type = 'button';
      b.addEventListener('click', () => { ihShown += 80; dash.setParams({ ih_more: String(ihShown) }); });
    }
  });

  dash.draw('ih-conditions', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || !pair.xx.length || !pair.xy.length) return;
    const rows = ihRows('inh_conditions', pair), meta = (ihRows('inh_meta', pair) || [])[0];
    if (!rows || !meta) return;
    const cov = ihJ(meta.coverage, {}), chip = ihJ(meta.chip_accuracy, {});
    const head = ihMake(el, 'div', 'ih-sec-head');
    ihMake(head, 'h3', null, 'Inherited conditions');
    ihMake(head, 'p', null, `Variants ClinVar classes as pathogenic, reviewed and not conflicting, that ${pair.a} or ${pair.b} carries, grouped by gene. ` +
      'Each condition carries the mode HPO gives it; a condition counts when pathogenic submissions mainly name it.');
    ihMake(head, 'p', null, `${(cov.both_read || 0).toLocaleString('en')} of ClinVar's ${(cov.pathogenic_records || 0).toLocaleString('en')} reviewed disease positions are read in both ` +
      `${pair.a} and ${pair.b}. Most disease variants are too rare for a chip or imputation to read, so the rest are not detected, not excluded.`);
    const list = ihMake(el, 'div', 'ih-list');
    if (!rows.length) ihMake(list, 'p', 'ih-empty', `Neither ${pair.a} nor ${pair.b} carries one of the disease variants their calls can read.`);
    for (const r of rows) {
      const box = ihMake(list, 'div', 'ih-row');
      const h = ihMake(box, 'div', 'ih-row-head');
      ihMake(h, 'b', null, r.gene).setAttribute('data-i18n-skip', '');
      const modes = ihJ(r.modes, []);
      for (const m of modes) ihModeTag(h, m);
      if (!modes.length) ihModeTag(h, null);
      if (r.on_x) ihMake(h, 'span', 'ih-sub', 'X chromosome');
      const byMode = ihJ(r.by_mode, {});
      const conds = ihMake(box, 'div', 'ih-conds');
      // Condition names are HPO's and ClinVar's, kept as written (the term layer would translate them word by word)
      if (modes.length) for (const m of modes) { const d = ihMake(conds, 'div'); ihMake(d, 'span', null, `${IH_MODE[m] || m}: `); ihMake(d, 'b', null, (byMode[m] || []).join('; ')).setAttribute('data-i18n-skip', ''); }
      else ihMake(conds, 'div', null, ihJ(r.clinvar_names, []).join('; ')).setAttribute('data-i18n-skip', '');
      const vs = ihJ(r.variants, []);
      const parents = ihMake(box, 'div', 'ih-parents');
      ihParent(parents, pair.a, vs, 'XX');
      ihParent(parents, pair.b, vs, 'XY');
      const odds = ihMake(box, 'div', 'ih-odds');
      const out = ihJ(r.outcomes, {});
      let shown = false;
      for (const [m, o] of Object.entries(out)) {
        for (const [who, sh] of Object.entries(o)) {
          // On the X, the chosen child only: a son's odds or a daughter's
          if ((who === 'son' && ihSex() === 'XX') || (who === 'daughter' && ihSex() === 'XY')) continue;
          if (sh.affected == null && sh.carrier == null && Object.values(sh).every((v) => v == null)) continue;
          shown = true;
          const label = who === 'child' ? (Object.keys(out).length > 1 ? `${IH_MODE[m] || m}` : 'A child') : who === 'son' ? 'A son' : 'A daughter';
          if (sh.affected != null) {
            const parts = [['Affected', sh.affected, 't-hit']];
            if (sh.carrier != null) parts.push(['Carrier', sh.carrier, 't-carrier']);
            parts.push(['Neither', Math.max(0, 1 - sh.affected - (sh.carrier || 0)), 't-clear']);
            ihBar(odds, label, parts);
          } else {
            const [k, v] = Object.entries(sh)[0];
            ihBar(odds, label, [[k === 'one copy' ? 'One copy' : 'One or two copies', v, 't-carrier'], ['None', 1 - v, 't-clear']]);
          }
        }
      }
      if (!shown) {
        const unreadable = r.XY_copies == null ? pair.b : pair.a;
        const known = r.XY_copies == null ? r.from_XX : r.from_XY;
        const knownWho = r.XY_copies == null ? pair.a : pair.b;
        ihMake(odds, 'p', 'ih-sub', `${unreadable}'s call here can't be used, so the odds of a child being affected can't be worked out. ` +
          `A child gets ${knownWho}'s variant copy with a chance of ${ihPct(known)}.`);
      }
      if (shown) {
        const c = ihMake(box, 'p', 'ih-conf');
        if (r.confidence != null) { c.append('Chance both parents\' calls are right: '); ihMake(c, 'b', null, ihPct(r.confidence)); }
        else c.textContent = 'At least one call has no measured accuracy (see above): read these odds as unconfirmed.';
      }
    }
    if (chip.pmid) {
      const s = ihMake(el, 'p', 'ih-src');
      s.append('Chip accuracy: ');
      const a = ihMake(s, 'a', null, chip.source); a.href = `https://europepmc.org/article/MED/${chip.pmid}`; a.target = '_blank'; a.rel = 'noopener';
      s.append('. HPO annotations ' + (meta.hpo_version || '') + '.');
    }
  });

  // A single-SNP trait's Punnett square: each parent's two alleles along an edge, the child's genotype in each cell
  const ihPunnett = (parent, t, v, pair) => {
    const gt = (s) => (s || '').length === 2 ? [s[0], s[1]] : null;
    const m = gt(v.XX.genotype), f = gt(v.XY.genotype);
    if (!m || !f) return;
    const alt = (v.allele || '').split(',');
    const modes = t.modes;
    const g = ihMake(parent, 'div', 'ih-punnett');
    g.setAttribute('aria-label', `Punnett square for ${t.name}`);
    ihMake(g, 'span', 'ih-pa', '');
    for (const x of f) ihMake(g, 'span', 'ih-pa', `${pair.b}: ${x}`).setAttribute('data-i18n-skip', '');
    for (const y of m) {
      ihMake(g, 'span', 'ih-pa', `${pair.a}: ${y}`).setAttribute('data-i18n-skip', '');
      for (const x of f) {
        const kid = [y, x].sort().join('');
        const n = [y, x].filter((a) => alt.includes(a)).length;
        const shows = modes.includes('AD') ? n >= 1 : modes.includes('AR') ? n === 2 : null;
        const tone = shows == null ? (n === 2 ? 't-trait' : n === 1 ? 't-half' : '') : shows ? 't-trait' : n ? 't-half' : '';
        ihMake(g, 'span', 'ih-cell ' + tone, kid);
      }
    }
  };

  dash.draw('ih-traits', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || !pair.xx.length || !pair.xy.length) return;
    const rows = ihRows('inh_traits', pair);
    if (!rows) return;
    const head = ihMake(el, 'div', 'ih-sec-head');
    ihMake(head, 'h3', null, 'Single-gene traits');
    ihMake(head, 'p', null, 'Traits set by one gene. The variant allele is the one ClinVar records for the trait; dominant or recessive comes from HPO where ' +
      'HPO annotates the trait. Where no source gives a mode, the child\'s genotype odds are shown on their own. Blue cells show the trait (or, without a mode, two copies); pale cells one copy.');
    if (!rows.length) { ihMake(el, 'p', 'ih-empty', 'No trait results for this pair.'); return; }
    const grid = ihMake(el, 'div', 'ih-traits');
    for (const r of rows) {
      const t = { ...r, modes: ihJ(r.modes, []) };
      const vs = ihJ(r.variants, []);
      const card = ihMake(grid, 'div', 'ih-trait');
      const top = ihMake(card, 'div', 'ih-trait-top');
      const tt = ihMake(top, 'div');
      ihMake(tt, 'h4', null, r.name);
      ihMake(tt, 'div', 'ih-sub', r.about);
      const tags = ihMake(top, 'div');
      if (t.modes.length) for (const m of t.modes) ihModeTag(tags, m); else ihModeTag(tags, null);
      if (vs.length > 1) ihMake(card, 'div', 'ih-sub', `${vs.map((v) => v.rsid).join(' · ')}: variant copies counted together`);
      const parents = ihMake(card, 'div', 'ih-parents');
      ihParentShort(parents, pair.a, vs, 'XX');
      ihParentShort(parents, pair.b, vs, 'XY');
      if (vs.length === 1) ihPunnett(card, t, vs[0], pair);
      const o = ihJ(r.odds, {});
      const odds = ihMake(card, 'div', 'ih-odds');
      const c = o.child;
      if (c) {
        const v = vs[0];
        const ref = v.ref, alt = (v.allele || '').split(',')[0];
        const labels = vs.length === 1 && ref && alt && ref.length === 1 && alt.length === 1
          ? [ref + ref, [ref, alt].sort().join(''), alt + alt] : ['No variant copy', 'One copy', 'Two copies'];
        ihBar(odds, 'A child', [[labels[0], c[0], 't-none'], [labels[1], c[1], 't-half'], [labels[2], c[2], 't-trait']]);
        const out = ihJ(r.outcomes, {});
        for (const [m, oo] of Object.entries(out)) {
          const sh = oo.child || {};
          if (sh.affected != null) ihMake(odds, 'p', 'ih-sub', m === 'AR'
            ? `Shows the trait (two copies): ${ihPct(sh.affected)} · carries one copy: ${ihPct(sh.carrier)}`
            : `Shows the trait (one copy is enough): ${ihPct(sh.affected)}`);
        }
      } else ihMake(odds, 'p', 'ih-sub', 'A parent\'s call here can\'t be used, so there are no odds for this trait.');
      const src = ihMake(card, 'div', 'ih-src');
      src.textContent = `ClinVar: ${vs.map((v) => `${v.rsid} ${v.ref}>${v.allele} (${v.condition})`).join('; ')}` +
        (r.omim_name ? ` · HPO: ${r.omim_name}` : ` · ${r.omim}: not annotated with a mode in HPO`);
      src.setAttribute('data-i18n-skip', '');
      if (r.confidence != null) { const cf = ihMake(card, 'p', 'ih-conf'); cf.append('Chance both parents\' calls are right: '); ihMake(cf, 'b', null, ihPct(r.confidence)); }
    }
  });

  dash.draw('ih-drugs', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || !pair.xx.length || !pair.xy.length) return;
    const rows = ihRows('inh_drugs', pair);
    if (!rows) return;
    const head = ihMake(el, 'div', 'ih-sec-head');
    ihMake(head, 'h3', null, 'Drug genes');
    ihMake(head, 'p', null, 'Each star allele is read as less active (LoF), typical or more active (GoF) by its CPIC function. Each parent passes one of ' +
      'their two alleles, so a child has one of four equally likely pairs. A less active allele sets the call even beside a more active one, as in ' +
      'CPIC\'s types; the type under each call is CPIC\'s.');
    if (!rows.length) { ihMake(el, 'p', 'ih-empty', 'No drug gene results for this pair: the Medicines step has to have run for both.'); return; }
    // An allele's direction from its CPIC function; a pair's call: any less active allele makes it LoF (x the number of
    // such alleles), else any more active one GoF, else typical
    const fnDir = (f) => /no function|decreased|slow|poor/i.test(f || '') ? 'LoF' : /increased|rapid/i.test(f || '') ? 'GoF' : 'normal';
    const DIR_TEXT = { LoF: 'Less active (LoF)', GoF: 'More active (GoF)', normal: 'Typical function' };
    const pairCall = (alleles, fns) => {
      const ds = alleles.map((a) => fnDir(fns[a]));
      const nL = ds.filter((d) => d === 'LoF').length, nG = ds.filter((d) => d === 'GoF').length;
      return nL ? ['LoF', nL] : nG ? ['GoF', nG] : ['normal', 0];
    };
    const chips = (parent, alleles, fns) => {
      const box = ihMake(parent, 'span', 'ih-alleles');
      for (const a of alleles) {
        const d = fnDir(fns[a]);
        const c = ihMake(box, 'span', 'ih-allele ih-a-' + d, a);
        c.title = `${a}: ${fns[a] || 'Normal function'}`;
        c.setAttribute('data-i18n-skip', '');
      }
      return box;
    };
    const tbl = ihMake(el, 'table', 'gx-table ih-drugs');
    const hr = ihMake(ihMake(tbl, 'thead'), 'tr');
    for (const h of ['Gene', pair.a, pair.b, 'A child']) ihMake(hr, 'th', null, h);
    const tb = ihMake(tbl, 'tbody');
    for (const r of rows) {
      const fns = ihJ(r.functions, {});
      const tr = ihMake(tb, 'tr');
      ihMake(tr, 'td', null, r.gene).setAttribute('data-i18n-skip', '');
      for (const [al, ty] of [[r.XX_alleles, r.XX_type], [r.XY_alleles, r.XY_type]]) {
        const td = ihMake(tr, 'td');
        const alleles = (al || '').split('/');
        const line = ihMake(td, 'div', 'ih-callline');
        chips(line, alleles, fns);
        const [d, n] = pairCall(alleles, fns);
        ihMake(line, 'span', 'lc-call ' + { LoF: 'lof', GoF: 'gof', normal: 'norm' }[d], DIR_TEXT[d] + (n ? ` ×${n}` : ''));
        ihMake(td, 'div', 'ih-sub', ty);
      }
      // The child: the four pairs grouped by call, LoF to GoF, each with CPIC's type
      const groups = new Map();
      for (const c of ihJ(r.children, [])) {
        const [d, n] = pairCall(c.alleles.split('/'), fns);
        const k = `${d}|${n}|${c.type}`;
        const g = groups.get(k) || { d, n, type: c.type, p: 0, pairs: [] };
        g.p += c.p; g.pairs.push(c.alleles); groups.set(k, g);
      }
      const order = { LoF: 0, normal: 1, GoF: 2 };
      const gs = [...groups.values()].sort((a, b) => order[a.d] - order[b.d] || b.n - a.n);
      const td = ihMake(tr, 'td');
      const bar = ihMake(td, 'div', 'ih-bar');
      bar.setAttribute('role', 'img');
      bar.setAttribute('aria-label', gs.map((g) => `${DIR_TEXT[g.d]}${g.n ? ' ×' + g.n : ''} ${ihPct(g.p)}`).join(', '));
      for (const g of gs) { const s = ihMake(bar, 'span', `ih-seg ih-c-${g.d}${g.d !== 'normal' && g.n > 1 ? '2' : ''}`); s.style.width = (g.p * 100) + '%'; }
      const key = ihMake(td, 'div', 'ih-types');
      for (const g of gs) {
        const k = ihMake(key, 'span', 'ih-type');
        ihMake(k, 'i', `ih-c-${g.d}${g.d !== 'normal' && g.n > 1 ? '2' : ''}`);
        ihMake(k, 'b', null, DIR_TEXT[g.d] + (g.n ? ` ×${g.n}` : ''));
        k.append(` ${ihPct(g.p)}`);
        const sub = ihMake(k, 'span', 'ih-sub', '');
        ihMake(sub, 'span', null, g.type);
        sub.append(` · ${g.pairs.join(', ')}`);
      }
    }
  });
