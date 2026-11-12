  // Carriers: ClinVar pathogenic variants the person's chip and imputation see, with the chance they carry each
  // (cluster_analysis/carriers). Every text node is one whole template, so the Swedish layer can swap it.
  const crMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const crT = (tpl, ...vals) => vals.reduce((s, v) => s.replace('{}', v), tpl);
  const CR_MODE = { AR: 'recessive', AD: 'dominant', XLR: 'X-linked recessive', XLD: 'X-linked dominant', XL: 'X-linked', MT: 'mitochondrial', YL: 'Y-linked' };
  const CR_HOW = { measured: 'measured on the chip', imputed: 'imputed', 'chip only': 'measured on the chip, not in 1000 Genomes' };
  const crModes = (m) => (m && m.length ? m.map((x) => CR_MODE[x] || x).join(', ') : 'not annotated');
  const crChance = (p) => p >= 0.995 ? 'over 99%' : p >= 0.01 ? `${(p * 100).toFixed(p >= 0.1 ? 0 : 1)}%` : p > 0 ? `1 in ${d3.format(',')(+(1 / p).toPrecision(2))}` : 'none, measured';
  const crDominant = (m) => m.some((x) => x === 'AD' || x === 'XLD');
  // What a found variant means, from its inheritance and the copies the person has
  const crMeaning = (r, who) => {
    const m = r.modes || [];
    if (crDominant(m) && !m.includes('AR')) return 'One copy can cause the condition.';
    if (m.includes('XLR') || m.includes('XL')) return r.haploid ? `On ${who}'s only X: the condition is expected.` : 'Carrier on one X: sons have a 1 in 2 chance of inheriting it.';
    if (m.includes('AR')) return r.copies >= 2 ? 'Two copies: the condition is expected.'
      : `Carrier: one copy alone has no effect. A child is at risk (1 in 4) only if the other parent also carries a variant in ${r.gene}.`;
    return 'Inheritance not annotated.';
  };

  dash.draw('cr-summary', (el) => {
    el.replaceChildren();
    const r = gx.rows('car_variants', 'car_genes', 'car_meta');
    if (!r) { if (gx.failed('car_variants', 'car_genes', 'car_meta')) gx.failLine(el); return; }
    const [vs, gs, [meta]] = r, who = gx.who(), fmt = d3.format(',');
    if (!meta) { crMake(el, 'p', 'gx-note', `No carrier screening for ${who} yet.`); return; }
    const sure = vs.filter((v) => v.status === 'carrier'), maybe = vs.filter((v) => v.status === 'possible');
    const rec = sure.filter((v) => !crDominant(v.modes || []));
    const word = sure.length === 1 ? 'variant' : 'variants';
    crMake(el, 'p', sure.length ? 'cr-big' : null, sure.length
      ? rec.length === sure.length ? crT('{} carries {} pathogenic {}, all in recessive or X-linked genes.', who, sure.length, word)
        : crT('{} carries {} pathogenic {}: {} in recessive or X-linked genes, {} where one copy can cause the condition.', who, sure.length, word, rec.length, sure.length - rec.length)
      : crT('{} carries none of the pathogenic variants a chip can check.', who));
    if (maybe.length) crMake(el, 'p', null, crT('{} more {} possible, from imputed calls a chip sees less well.', maybe.length, maybe.length === 1 ? 'is' : 'are'));
    crMake(el, 'p', 'gx-note', crT('ClinVar lists {} pathogenic or likely pathogenic variants. {}\'s DNA says something about {} of them, in {} genes; the other {} can\'t be seen from a chip, so a clear result here does not rule them out.',
      fmt(meta.variants), who, fmt(meta.checked), fmt(gs.length), fmt(meta.unseen)));
    if (vs.some((v) => v.confirm) && meta.quote) {
      const q = crMake(el, 'p', 'cr-quote');
      crMake(q, 'span', null, 'Variants marked to confirm are very rare, and chip calls of very rare variants are often wrong: ');
      crMake(q, 'q', null, meta.quote);
      crMake(q, 'span', 'gx-muted', ` ${meta.title} ${meta.journal} ${meta.year}, PMID ${meta.pmid}.`);
    }
  });

  dash.draw('cr-found', (el) => {
    el.replaceChildren();
    const r = gx.rows('car_variants', 'car_meta');
    if (!r) { if (gx.failed('car_variants', 'car_meta')) gx.failLine(el); return; }
    const who = gx.who(), order = { carrier: 0, possible: 1 };
    const vs = [...r[0]].sort((a, b) => order[a.status] - order[b.status] || b.chance - a.chance || a.gene.localeCompare(b.gene));
    if (!vs.length) { crMake(el, 'p', 'gx-note', crT('No pathogenic variant found in {}\'s DNA.', who)); return; }
    for (const v of vs) {
      const box = crMake(el, 'div', 'cr-var cr-' + (v.status === 'carrier' ? (crDominant(v.modes || []) ? 'dom' : 'rec') : 'maybe'));
      const head = crMake(box, 'div', 'cr-head');
      crMake(head, 'b', null, v.gene || 'no gene');
      crMake(head, 'span', null, v.condition);
      crMake(head, 'span', 'cr-tag', v.status === 'carrier' ? 'Carrier' : 'Possible');
      if (v.confirm) crMake(head, 'span', 'cr-tag cr-confirm', 'Confirm with a clinical test');
      crMake(box, 'p', null, crMeaning(v, who));
      if ((v.also || []).length) crMake(box, 'p', 'gx-note', crT('ClinVar also lists: {}.', v.also.map((x) => `${x.name} (${crModes(x.modes)})`).join('; ')));
      crMake(box, 'p', 'gx-note', crT('{} {}>{}, {}: {} {}, chance {} carries it {}. ClinVar: {}, {} stars. Inheritance: {}.',
        v.rsid || `chr${v.chrom}:${v.pos}`, v.ref, v.alt, CR_HOW[v.how], v.copies, v.copies === 1 ? 'copy' : 'copies', who, v.confirm ? 'not known: chip calls this rare are often wrong (see above)' : crChance(v.chance),
        v.significance, v.stars, crModes(v.modes)) + (v.how === 'imputed' && v.class !== 'chip' && v.class !== 'reliable' ? ' The chip sees this variant poorly, so treat it as a lead.' : ''));
    }
  });

  dash.draw('cr-genes', (el) => {
    el.replaceChildren();
    const r = gx.rows('car_genes');
    if (!r) { if (gx.failed('car_genes')) gx.failLine(el); return; }
    const gs = r[0].filter((g) => g.checked).sort((a, b) => b.checked - a.checked || a.gene.localeCompare(b.gene));
    const box = crMake(el, 'div', 'gx-table-box cr-genes');
    const t = crMake(box, 'table', 'gx-table');
    const hr = crMake(crMake(t, 'thead'), 'tr');
    for (const h of ['Gene', 'Inheritance', 'Conditions', 'Checked', 'Chance one was missed', "Can't see"]) crMake(hr, 'th', null, h);
    const tb = crMake(t, 'tbody');
    for (const g of gs) {
      const tr = crMake(tb, 'tr');
      crMake(tr, 'td', null, g.gene || '—');
      crMake(tr, 'td', null, crModes(g.modes));
      crMake(tr, 'td', null, g.conditions.join('; ') + (g.n_conditions > 3 ? crT('; and {} more', g.n_conditions - 3) : ''));
      crMake(tr, 'td', null, String(g.checked));
      crMake(tr, 'td', null, crChance(g.missed));
      crMake(tr, 'td', null, d3.format(',')(g.unseen));
    }
  });
