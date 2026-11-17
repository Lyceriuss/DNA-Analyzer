  // Female fertility in depth (cluster_analysis/themes/fertility_deep.py), in two parts. Part 1, how the cycle works:
  // per section the Gene Ontology processes, the Reactome reactions as steps to go through, and the genes at work
  // (UniProt), with two schematics (the axis; the theca and granulosa cells). Part 2, what the selected person's
  // variants change: the sections ranked by the evidence, each gene's evidence linked to its steps, the forms studies
  // measured in women and the GWAS trait panels. Opened from the 28-day cycle (th.js) through fd_sec / fd_part / fd_step.
  const fdMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const fdFill = (tpl, ...v) => { let i = 0; return tpl.replace(/\{\}/g, () => String(v[i++])); };
  const FD_CLASS = { LoF: 'lof', GoF: 'gof', altered: 'alt', normal: 'norm', variant: 'var' };
  const fdNum = (x) => (Math.abs(x) >= 100 ? d3.format(',.0f')(x) : String(x));
  const fdPmid = (parent, pmid, text) => {
    const a = fdMake(parent, 'a', 'fd-cite', text);
    a.href = `https://europepmc.org/article/MED/${pmid}`; a.target = '_blank'; a.rel = 'noopener';
    return a;
  };

  // The cycle in days for the typical form and the studied one: the follicular part shaded, the person's row marked
  const fdTimeline = (parent, card, fol, cyc) => {
    const box = fdMake(parent, 'div', 'fd-timeline');
    // Drawn at the card's own width, 1:1, so the text keeps its size
    const max = Math.max(cyc.typical, cyc.studied) + 1, W = Math.max(300, Math.round(parent.clientWidth || 360)), rowH = 30, L = 118;
    const x = d3.scaleLinear([0, max], [L, W - 44]);
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${W} ${rowH * 2 + 28}`).attr('width', W).attr('height', rowH * 2 + 28).attr('role', 'img')
      .attr('aria-label', fdFill('Cycle length: {} days with {}, {} days with {}', cyc.typical, card.other, cyc.studied, card.studied));
    [[card.other, cyc.typical, fol && fol.typical, 0], [card.studied, cyc.studied, fol && fol.studied, card.copies]].forEach(([name, total, f, copies], i) => {
      const y = 6 + i * rowH, mine = copies === card.copies || (i === 0 && card.copies === 0);
      svg.append('text').attr('x', 0).attr('y', y + 15).attr('class', 'fd-tl-name' + (mine ? ' is-mine' : '')).text(`${name}/${name}`);
      svg.append('rect').attr('x', x(0)).attr('y', y).attr('width', x(total) - x(0)).attr('height', 20).attr('rx', 4).attr('class', 'fd-tl-cycle' + (mine ? ' is-mine' : ''));
      if (f) svg.append('rect').attr('x', x(0)).attr('y', y).attr('width', x(f) - x(0)).attr('height', 20).attr('rx', 4).attr('class', 'fd-tl-fol');
      svg.append('text').attr('x', x(total) + 4).attr('y', y + 15).attr('class', 'fd-tl-val').text(fdFill('{} d', total));
      if (f) svg.append('text').attr('x', x(f) - 4).attr('y', y + 15).attr('text-anchor', 'end').attr('class', 'fd-tl-in').text(fdFill('{} d', f));
    });
    for (let d = 0; d <= max; d += 7) svg.append('text').attr('x', x(d)).attr('y', rowH * 2 + 22).attr('text-anchor', 'middle').attr('class', 'fd-tl-ax').text(fdFill('day {}', d));
    const lg = fdMake(box, 'div', 'fd-legend');
    if (fol) { const a = fdMake(lg, 'span'); fdMake(a, 'i', 'fd-sw fd-sw-fol'); fdMake(a, 'span', null, 'From luteolysis to ovulation'); }
    const b = fdMake(lg, 'span'); fdMake(b, 'i', 'fd-sw fd-sw-cyc'); fdMake(b, 'span', null, 'Whole cycle');
  };

  // A measure by the number of copies of the studied form (0, 1, 2), the person's bar marked
  const fdCopies = (parent, card, n) => {
    const box = fdMake(parent, 'div', 'fd-copies');
    const nm = fdMake(box, 'span', 'fd-num-name');
    fdMake(nm, 'span', null, n.name); fdMake(nm, 'span', 'fd-unit', n.unit);
    const max = Math.max(...n.values);
    n.values.forEach((v, i) => {
      const row = fdMake(box, 'div', 'fd-bar-row' + (i === card.copies ? ' is-mine' : ''));
      fdMake(row, 'span', 'fd-bar-name', [`${card.other}/${card.other}`, `${card.other}/${card.studied}`, `${card.studied}/${card.studied}`][i]);
      const bar = fdMake(row, 'span', 'fd-bar'); fdMake(bar, 'i').style.width = `${(v / max) * 100}%`;
      fdMake(row, 'b', null, fdNum(v));
    });
  };

  const fdCard = (parent, card, ctx) => {
    const c = fdMake(parent, 'article', 'fd-card fd-top-' + (card.copies ? FD_CLASS[card.call] || 'var' : 'norm'));
    const h = fdMake(c, 'div', 'fd-card-head');
    fdMake(h, 'h4', null, card.name);
    fdMake(h, 'span', 'fd-rs', card.rsid);
    const forms = fdMake(c, 'div', 'fd-forms');
    const form = (name, allele, freq, studied) => {
      const f = fdMake(forms, 'span', 'fd-form' + (studied ? ' is-studied' : ''));
      fdMake(f, 'b', null, name);
      fdMake(f, 'span', null, fdFill('{} · {}% of European copies', allele || '?', freq == null ? '?' : Math.round(freq * 100)));
    };
    form(card.other, card.other_allele, card.freq == null ? null : 1 - card.freq, false);
    form(card.studied, card.studied_allele, card.freq, true);
    const me = fdMake(c, 'div', 'fd-me' + (card.copies ? ' is-carrier' : ''));
    if (card.genotype) {
      fdMake(me, 'b', null, card.form || card.genotype);
      fdMake(me, 'span', null, card.tier === 'measured' ? fdFill('{}\'s genotype {}, measured on the chip', ctx.who, card.genotype)
        : fdFill('{}\'s genotype {}, imputed with {} confidence', ctx.who, card.genotype, card.tier));
      fdMake(me, 'span', 'fd-copy', card.copies === 1 ? fdFill('One copy of {}', card.studied) : fdFill('{} copies of {}', card.copies, card.studied));
    } else fdMake(me, 'span', null, fdFill('No call for {} at {}', ctx.who, card.rsid));
    // The numbers, drawn
    const nums = card.studies.flatMap((s) => s.numbers.map((n) => ({ ...n, study: s })));
    const fol = nums.find((n) => n.id === 'follicular_days'), cyc = nums.find((n) => n.id === 'cycle_days');
    if (cyc) {
      fdMake(c, 'span', 'gx-label', fdFill('Measured in women · {}', cyc.study.study));
      fdTimeline(c, card, fol, cyc);
    }
    for (const n of nums) {
      if (n.id === 'follicular_days' || n.id === 'cycle_days') continue;
      if (n.kind === 'copies') { fdMake(c, 'span', 'gx-label', fdFill('Measured in women · {}', n.study.study)); fdCopies(c, card, n); continue; }
      const big = fdMake(c, 'div', 'fd-big');
      const v = n.kind === 'more' ? `+${n.studied}%` : n.kind === 'odds' ? `×${n.studied}` : n.kind === 'earlier' ? fdFill('{} years', n.studied) : fdNum(n.studied);
      fdMake(big, 'b', 'fd-' + (FD_CLASS[card.call] || 'var') + '-text', v);
      const t = fdMake(big, 'span');
      fdMake(t, 'span', null, n.kind === 'earlier' ? fdFill('{}, with {} copies of {}', n.name, n.copies, card.studied) : n.copies ? fdFill('{}, with {} copies of {}', n.name, n.copies, card.studied) : n.name);
      fdMake(t, 'span', 'gx-note', n.study.study);
    }
    // What the studies found, in their words
    const quotes = card.studies.filter((s) => s.sentences.length);
    if (quotes.length) {
      const q = fdMake(c, 'div', 'fd-quotes');
      fdMake(q, 'span', 'gx-label', 'What the studies found');
      for (const s of quotes) {
        const b = fdMake(q, 'blockquote');
        for (const x of s.sentences) fdMake(b, 'p', null, `“${x}”`).setAttribute('data-i18n-skip', '');
        fdPmid(b, s.pmid, `${s.study} · PMID ${s.pmid}`);
      }
    }
    if (card.gwas.length) {
      fdMake(c, 'span', 'gx-label', fdFill('GWAS Catalog, per copy of {}', card.studied));
      const ul = fdMake(c, 'ul', 'fd-gw');
      for (const g of card.gwas) {
        const li = fdMake(ul, 'li');
        fdMake(li, 'span', null, g.trait).setAttribute('data-i18n-skip', '');
        fdMake(li, 'b', null, g.or != null ? `OR ${g.or}` : g.beta != null ? `β ${g.beta > 0 ? '+' : ''}${g.beta}` : '');
        fdPmid(li, g.pmid, `${g.author} ${g.year}`);
      }
    }
  };

  // One GWAS study's lead variants read for the person: where they fall among Europeans. Green on the right: for a
  // condition the right is the lower risk, for an egg-reserve level the higher; neutral measures are not coloured.
  const fdPanel = (parent, p, ctx) => {
    const row = fdMake(parent, 'div', 'fd-panel');
    const head = fdMake(row, 'div', 'fd-panel-head');
    fdMake(head, 'b', null, p.name);
    fdPmid(head, p.pmid, `${p.author} ${p.year} · PMID ${p.pmid}`);
    if (p.percentile == null) {
      fdMake(row, 'p', 'gx-note', p.leads ? fdFill('{} lead variants; too few could be placed on Europe\'s frequencies to score.', p.leads) : 'No genome-wide significant lead variants in this study.');
      return;
    }
    const worse = p.higher === 'worse', better = p.higher === 'better';
    const pos = worse ? 100 - p.percentile : p.percentile;
    const scale = fdMake(row, 'div', 'fd-scale' + (worse || better ? ' is-graded' : ''));
    const lab = fdMake(scale, 'div', 'fd-scale-ends');
    fdMake(lab, 'span', null, worse ? 'Higher risk' : better ? 'Lower' : p.higher === 'later' ? 'Earlier' : 'Lower');
    fdMake(lab, 'span', null, worse ? 'Lower risk' : better ? 'Higher' : p.higher === 'later' ? 'Later' : 'Higher');
    const track = fdMake(scale, 'div', 'fd-track');
    fdMake(track, 'i', 'fd-mid');
    const dot = fdMake(track, 'b', 'fd-dot'); dot.style.left = `${pos}%`;
    const says = fdMake(row, 'p', 'fd-says');
    says.textContent = p.odds != null
      ? fdFill('{}: {} the odds of an average European ({} of {} lead variants read)', ctx.who, `×${p.odds}`, p.used, p.placed)
      : worse ? fdFill('{}: more risk variants than {}% of Europeans ({} of {} lead variants read)', ctx.who, p.percentile, p.used, p.placed)
      : p.higher === 'later' ? fdFill('{}: later than {}% of Europeans ({} of {} lead variants read)', ctx.who, p.percentile, p.used, p.placed)
      : fdFill('{}: higher than {}% of Europeans ({} of {} lead variants read)', ctx.who, p.percentile, p.used, p.placed);
    const top = (p.top || []).filter((t) => t.copies != null).slice(0, 6);
    if (top.length) {
      const chips = fdMake(row, 'div', 'fd-tops');
      for (const t of top) {
        const up = (t.shift > 0) === (p.higher !== 'worse');
        const ch = fdMake(chips, 'span', 'fd-top' + (t.chain ? ' is-chain' : '') + (worse || better ? (up ? ' is-good' : ' is-bad') : ''));
        fdMake(ch, 'b', null, (t.gene || t.rsid).split(/[,;]/)[0]);
        fdMake(ch, 'span', null, `${t.allele} ×${t.copies}`);
        ch.title = fdFill('{} {}: {} copies of {} ({}% of European copies)', t.rsid, t.gene || '', t.copies, t.allele, Math.round(t.freq * 100));
      }
    }
  };

  const FD_PHASE_NAMES = { menses: 'Menstruation', follicular: 'Follicular phase', ovulation: 'Ovulation', luteal: 'Luteal phase and implantation', ageing: 'Across a reproductive life' };
  const FD_GRADE = { A: 'Measured', B: 'Associated', C: 'Predicted' };
  const FD_TISSUE = { Ovary: 'ovary', Uterus: 'uterus', Pituitary: 'pituitary', Brain_Hypothalamus: 'hypothalamus', Vagina: 'vagina' };
  const fdGo = (sec, part, step) => {
    dash.setParams({ fd_sec: sec, fd_part: part, fd_step: step == null ? null : String(step) });
    setTimeout(() => { const c = document.getElementById('fd-view'); if (c) c.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 50);
  };
  const FD_FROM_PHASE = { menses: 'menstruation', follicular: 'follicle', ovulation: 'ovulation', luteal: 'luteal', ageing: 'ageing' };
  window.gxFertility = { open(phase) { fdGo(FD_FROM_PHASE[phase] || phase, 'how', null); } };

  // Schematic of the axis: hypothalamus, pituitary, ovary and uterus, the hormones between them and the feedback.
  // A drawing: the organs and arrows only place the Reactome reactions listed in the sections; each box opens its section.
  const fdAxis = (parent, ctx) => {
    const box = fdMake(parent, 'figure', 'fd-fig');
    const W = 360, H = 330;
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', 'Schematic of the hypothalamus–pituitary–ovary axis');
    svg.append('defs').append('marker').attr('id', 'fd-arr').attr('viewBox', '0 0 10 10').attr('refX', 9).attr('refY', 5).attr('markerWidth', 7).attr('markerHeight', 7)
      .attr('orient', 'auto-start-reverse').append('path').attr('d', 'M0,0 L10,5 L0,10 z').attr('class', 'fd-arrhead');
    const organs = [['Hypothalamus', 'axis', 20, ['KISS1R', 'GNRH1']], ['Pituitary', 'axis', 100, ['GNRHR', 'FSHB', 'LHB']],
                    ['Ovary', 'follicle', 180, ['FSHR', 'LHCGR', 'CYP19A1']], ['Uterus', 'endometrium', 260, ['ESR1', 'PGR']]];
    for (const [name, sec, y, genes] of organs) {
      const g = svg.append('g').attr('class', 'fd-organ' + (ctx.sec === sec ? ' is-on' : '')).attr('tabindex', 0).attr('role', 'button')
        .on('click', () => fdGo(sec, 'how', null));
      g.append('rect').attr('x', 70).attr('y', y).attr('width', 170).attr('height', 50).attr('rx', 10);
      g.append('text').attr('x', 82).attr('y', y + 20).attr('class', 'fd-organ-name').text(name);
      genes.forEach((gn, i) => {
        const has = ctx.has(gn);
        g.append('text').attr('x', 82 + i * 54).attr('y', y + 39).attr('class', 'fd-organ-gene' + (has ? ' is-hit' : '')).text(gn);
      });
    }
    const arrow = (x1, y1, x2, y2, label, cls) => {
      svg.append('line').attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2).attr('class', 'fd-flow ' + (cls || '')).attr('marker-end', 'url(#fd-arr)');
      svg.append('text').attr('x', (x1 + x2) / 2 + 6).attr('y', (y1 + y2) / 2 + 4).attr('class', 'fd-flow-label ' + (cls || '')).text(label);
    };
    arrow(155, 70, 155, 98, 'GnRH pulses');
    arrow(130, 150, 130, 178, 'FSH');
    arrow(180, 150, 180, 178, 'LH');
    arrow(155, 230, 155, 258, 'estradiol, progesterone');
    // feedback from the ovary
    svg.append('path').attr('d', 'M240,200 C300,190 300,80 240,48').attr('class', 'fd-flow fd-neg').attr('marker-end', 'url(#fd-arr)');
    svg.append('text').attr('x', 300).attr('y', 120).attr('class', 'fd-flow-label fd-neg').text('− estradiol,');
    svg.append('text').attr('x', 300).attr('y', 133).attr('class', 'fd-flow-label fd-neg').text('progesterone,');
    svg.append('text').attr('x', 300).attr('y', 146).attr('class', 'fd-flow-label fd-neg').text('inhibin');
    svg.append('path').attr('d', 'M70,200 C20,190 20,90 70,62').attr('class', 'fd-flow fd-pos').attr('marker-end', 'url(#fd-arr)');
    svg.append('text').attr('x', 6).attr('y', 126).attr('class', 'fd-flow-label fd-pos').text('+ estradiol');
    svg.append('text').attr('x', 6).attr('y', 139).attr('class', 'fd-flow-label fd-pos').text('peak');
    fdMake(box, 'figcaption', 'gx-note', 'Schematic. Select an organ for its section; genes outlined in blue have one of the selected person\'s variants with evidence.');
  };

  // Schematic of the two-cell, two-gonadotropin model: a theca cell (LH) next to a granulosa cell (FSH), with the
  // Reactome steroid reactions placed where they happen. Each reaction is a button that opens it in the stepper.
  const FD_CELL_LAYOUT = {
    'R-HSA-391377': ['theca', 60, 22], 'R-HSA-196126': ['theca', 60, 70], 'R-HSA-193054': ['theca', 60, 108], 'R-HSA-193065': ['theca', 60, 138],
    'R-HSA-193101': ['theca', 60, 168], 'R-HSA-193097': ['theca', 60, 206], 'R-HSA-196350': ['theca', 180, 206], 'R-HSA-193052': ['theca', 180, 236],
    'R-HSA-193068': ['theca', 180, 140], 'R-HSA-193070': ['theca', 180, 110], 'R-HSA-193073': ['theca', 180, 80],
    'R-HSA-391378': ['granulosa', 420, 22], 'R-HSA-193060': ['granulosa', 360, 110], 'R-HSA-804969': ['granulosa', 360, 160], 'R-HSA-193143': ['granulosa', 486, 160],
  };
  const fdCells = (parent, ctx, steps, onPick) => {
    const box = fdMake(parent, 'figure', 'fd-fig');
    const W = 620, H = 290;
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', 'Schematic of a theca cell and a granulosa cell with the steroid reactions');
    svg.append('rect').attr('x', 6).attr('y', 6).attr('width', 290).attr('height', H - 12).attr('rx', 24).attr('class', 'fd-cell');
    svg.append('rect').attr('x', 324).attr('y', 6).attr('width', 290).attr('height', H - 12).attr('rx', 24).attr('class', 'fd-cell');
    svg.append('line').attr('x1', 310).attr('x2', 310).attr('y1', 20).attr('y2', H - 20).attr('class', 'fd-basement');
    svg.append('text').attr('x', 20).attr('y', H - 18).attr('class', 'fd-cell-name').text('Theca cell · LH');
    svg.append('text').attr('x', 338).attr('y', H - 18).attr('class', 'fd-cell-name').text('Granulosa cell · FSH');
    svg.append('rect').attr('x', 22).attr('y', 92).attr('width', 116).attr('height', 132).attr('rx', 40).attr('class', 'fd-mito');
    svg.append('text').attr('x', 30).attr('y', 238).attr('class', 'fd-cap').text('mitochondrion');
    svg.append('rect').attr('x', 150).attr('y', 64).attr('width', 132).attr('height', 196).attr('rx', 14).attr('class', 'fd-er');
    svg.append('text').attr('x', 160).attr('y', 274).attr('class', 'fd-cap').text('endoplasmic reticulum');
    svg.append('path').attr('d', 'M282,80 C300,80 330,100 372,110').attr('class', 'fd-flow').attr('marker-end', 'url(#fd-arr2)');
    svg.append('defs').append('marker').attr('id', 'fd-arr2').attr('viewBox', '0 0 10 10').attr('refX', 9).attr('refY', 5).attr('markerWidth', 7).attr('markerHeight', 7)
      .attr('orient', 'auto').append('path').attr('d', 'M0,0 L10,5 L0,10 z').attr('class', 'fd-arrhead');
    svg.append('text').attr('x', 318).attr('y', 96).attr('class', 'fd-flow-label').text('androstenedione');
    svg.append('text').attr('x', 20).attr('y', 30).attr('class', 'fd-cell-name').text('LH → LHCGR');
    svg.append('text').attr('x', 338).attr('y', 30).attr('class', 'fd-cell-name').text('FSH → FSHR');
    svg.append('text').attr('x', 470).attr('y', 230).attr('class', 'fd-flow-label').text('estradiol →');
    steps.forEach((st, i) => {
      const at = FD_CELL_LAYOUT[st.id];
      if (!at) return;
      // Labelled by the catalyst's first protein (Reactome's catalyst name), else a short form of the reaction's name
      const cat = (st.enzyme || '').split(/[:,\s]/)[0];
      const label = cat || (st.name.length > 16 ? st.name.slice(0, 15) + '…' : st.name);
      const hit = st.genes.some((g) => ctx.has(g));
      const g = svg.append('g').attr('class', 'fd-node' + (i === ctx.step ? ' is-on' : '') + (hit ? ' is-hit' : '')).attr('tabindex', 0).attr('role', 'button')
        .attr('transform', `translate(${at[1]},${at[2]})`).on('click', () => onPick(i));
      g.append('rect').attr('x', 0).attr('y', 0).attr('width', 104).attr('height', 24).attr('rx', 12);
      g.append('text').attr('x', 52).attr('y', 16).attr('text-anchor', 'middle').text(label);
      g.append('title').text(st.name);
    });
    fdMake(box, 'figcaption', 'gx-note', 'Schematic of the two-cell, two-gonadotropin model. Each pill is a Reactome reaction placed where Reactome says it happens; select one to step through it below.');
  };

  // One Reactome reaction: substrates → enzyme → products, cofactors, where it happens, and Reactome's summary
  const fdReaction = (parent, st, ctx) => {
    const box = fdMake(parent, 'div', 'fd-rx');
    const flow = fdMake(box, 'div', 'fd-rx-flow');
    const side = (list, cls) => { const d = fdMake(flow, 'div', 'fd-rx-side ' + cls); for (const e of list.filter((x) => !x.cofactor)) { const s = fdMake(d, 'span', 'fd-mol' + (e.chemical ? '' : ' is-protein'), e.name); s.title = e.short; } return d; };
    side(st.inputs, 'is-in');
    fdMake(flow, 'span', 'fd-arrow', '→');
    const enz = fdMake(flow, 'div', 'fd-rx-enz');
    if (st.genes.length) {
      for (const g of st.genes) {
        const c = fdMake(enz, 'button', 'fd-gene ' + (ctx.has(g) ? 'fd-hit' : 'fd-norm'), g); c.type = 'button';
        const fn = ctx.fns.get(g);
        c.addEventListener('mousemove', (event) => ctx.tip.show(event, fn && fn.protein ? `${g} · ${fn.protein}` : g, [fn && fn.function, fn && fn.location && fn.location.length ? fdFill('In the cell: {}', fn.location.join(', ')) : '', fn && fn.cofactor && fn.cofactor.length ? fdFill('Cofactor: {}', fn.cofactor.join(', ')) : ''].filter(Boolean)));
        c.addEventListener('mouseleave', () => ctx.tip.hide());
        c.addEventListener('click', () => fdGo(ctx.sec, 'you', null));
      }
    } else fdMake(enz, 'span', 'gx-note', 'no protein catalyst');
    fdMake(flow, 'span', 'fd-arrow', '→');
    side(st.outputs, 'is-out');
    const meta = fdMake(box, 'div', 'fd-rx-meta');
    const cof = [...st.inputs, ...st.outputs].filter((e) => e.cofactor).map((e) => e.short);
    if (cof.length) { const c = fdMake(meta, 'span', 'fd-tag'); fdMake(c, 'i', null, 'Cofactors'); fdMake(c, 'b', null, [...new Set(cof)].join(' · ')); }
    if (st.compartments.length) { const c = fdMake(meta, 'span', 'fd-tag'); fdMake(c, 'i', null, 'Where'); fdMake(c, 'b', null, st.compartments.join(', ')); }
    if (st.enzyme) { const c = fdMake(meta, 'span', 'fd-tag'); fdMake(c, 'i', null, 'Catalyst'); fdMake(c, 'b', null, st.enzyme); }
    if (st.summary) fdMake(box, 'p', 'fd-rx-sum', st.summary).setAttribute('data-i18n-skip', '');
    const a = fdMake(box, 'a', 'fd-cite', `Reactome ${st.id}`); a.href = `https://reactome.org/content/detail/${st.id}`; a.target = '_blank'; a.rel = 'noopener';
  };

  const fdPartHow = (el, ctx, sec) => {
    const steps = JSON.parse(sec.steps), procs = JSON.parse(sec.processes);
    const figs = fdMake(el, 'div', 'fd-figs');
    fdAxis(figs, ctx);
    const ster = ctx.explain.find((x) => x.section === 'steroids');
    fdCells(figs, { ...ctx, step: sec.section === 'steroids' ? ctx.step : -1 }, ster ? JSON.parse(ster.steps) : [], (i) => fdGo('steroids', 'how', i));
    const tabs = fdMake(el, 'div', 'fd-pick'); tabs.setAttribute('role', 'group'); tabs.setAttribute('aria-label', 'Section');
    for (const s of ctx.explain) {
      const b = fdMake(tabs, 'button', 'fd-pick-btn', s.name); b.type = 'button'; b.setAttribute('aria-pressed', String(s === sec));
      const imp = ctx.impact.find((x) => x.section === s.section);
      if (imp && imp.score) fdMake(b, 'i', 'fd-pick-dot').setAttribute('aria-hidden', 'true');
      b.addEventListener('click', () => fdGo(s.section, 'how', null));
    }
    fdMake(el, 'h3', 'fd-h', sec.name);
    const dl = fdMake(el, 'dl', 'fd-go');
    for (const p of procs) {
      fdMake(dl, 'dt', null, p.name).setAttribute('data-i18n-skip', '');
      const dd = fdMake(dl, 'dd'); fdMake(dd, 'span', null, p.definition).setAttribute('data-i18n-skip', '');
      fdMake(dd, 'span', 'fd-cite', `${p.id} · ${fdFill('{} human genes', p.genes.length)}`);
    }
    if (steps.length) {
      const i = Math.min(Math.max(0, ctx.step), steps.length - 1);
      fdMake(el, 'span', 'gx-label fd-sec', 'Step by step (Reactome)');
      const chain = fdMake(el, 'div', 'fd-chain');
      steps.forEach((st, k) => {
        if (k) fdMake(chain, 'span', 'fd-arrow', '→').setAttribute('aria-hidden', 'true');
        const b = fdMake(chain, 'button', 'fd-step-btn' + (k === i ? ' is-on' : '') + (st.genes.some((g) => ctx.has(g)) ? ' is-hit' : ''), String(k + 1));
        b.type = 'button'; b.title = st.name; b.addEventListener('click', () => fdGo(sec.section, 'how', k));
      });
      const nav = fdMake(el, 'div', 'fd-stepper');
      const prev = fdMake(nav, 'button', 'gx-add-ghost fd-nav', '‹'); prev.type = 'button'; prev.disabled = i === 0;
      prev.addEventListener('click', () => fdGo(sec.section, 'how', i - 1));
      const t = fdMake(nav, 'div', 'fd-step-title');
      fdMake(t, 'span', 'gx-note', fdFill('Step {} of {}', i + 1, steps.length));
      fdMake(t, 'b', null, steps[i].name).setAttribute('data-i18n-skip', '');
      const next = fdMake(nav, 'button', 'gx-add-ghost fd-nav', '›'); next.type = 'button'; next.disabled = i === steps.length - 1;
      next.addEventListener('click', () => fdGo(sec.section, 'how', i + 1));
      fdReaction(el, steps[i], ctx);
    }
    const genes = JSON.parse(sec.genes);
    if (genes.length) {
      fdMake(el, 'span', 'gx-label fd-sec', 'Genes at work (UniProt)');
      const grid = fdMake(el, 'div', 'fd-genecards');
      for (const g of genes) {
        const fn = ctx.fns.get(g) || {};
        const c = fdMake(grid, 'div', 'fd-genecard' + (ctx.has(g) ? ' is-hit' : ''));
        const h = fdMake(c, 'div', 'fd-genecard-head'); fdMake(h, 'b', null, g); if (fn.protein) fdMake(h, 'span', 'gx-note', fn.protein).setAttribute('data-i18n-skip', '');
        if (fn.function) fdMake(c, 'p', null, fn.function).setAttribute('data-i18n-skip', '');
        if (fn.location && fn.location.length) { const l = fdMake(c, 'span', 'fd-tag'); fdMake(l, 'i', null, 'Where'); fdMake(l, 'b', null, fn.location.join(', ')).setAttribute('data-i18n-skip', ''); }
        if (ctx.has(g)) { const b = fdMake(c, 'button', 'th-cy-open', fdFill('What {}\'s variants change here', ctx.who)); b.type = 'button'; b.addEventListener('click', () => fdGo(sec.section, 'you', null)); }
      }
    }
  };

  // One piece of evidence, as a line: grade, what it is, how big, and its source
  const fdItem = (parent, it, ctx) => {
    const li = fdMake(parent, 'li', 'fd-ev fd-ev-' + it.grade);
    fdMake(li, 'span', 'fd-grade', FD_GRADE[it.grade]);
    const d = fdMake(li, 'div');
    const dir = { less: 'less active', more: 'more active', changed: 'changed', raises: 'raises', lowers: 'lowers', linked: 'linked to' }[it.direction] || it.direction;
    if (it.kind === 'study' && it.direction === 'none') {
      fdMake(d, 'b', null, fdFill('{} · {}: measured, no change found', it.name, it.form));
      if (it.finding) fdMake(d, 'span', 'gx-note', `“${it.finding}”`).setAttribute('data-i18n-skip', '');
      fdPmid(d, it.pmid, it.study);
    } else if (it.kind === 'study') {
      fdMake(d, 'b', null, fdFill('{} · {} ({} copies of {})', it.name, it.form, it.copies, it.studied));
      for (const s of it.sizes) {
        const r = fdMake(d, 'span', 'fd-size');
        fdMake(r, 'b', null, `${s.value > 0 && s.unit !== '×' ? '+' : ''}${s.unit === '×' ? '×' : ''}${s.value}${s.unit === '×' ? '' : ' ' + s.unit}`);
        fdMake(r, 'span', null, s.copies ? fdFill('{}, measured with {} copies', s.name, s.copies) : s.name);
        fdPmid(r, s.pmid, s.study);
      }
    } else if (it.kind === 'protein') {
      fdMake(d, 'b', null, fdFill('{} {}: {}', it.rsid || '', it.change || '', dir));
      if (it.detail) fdMake(d, 'span', 'gx-note', it.detail).setAttribute('data-i18n-skip', '');
    } else if (it.kind === 'eqtl') {
      fdMake(d, 'b', null, fdFill('{} {} ×{}: {} expressed in the {}', it.rsid, it.allele, it.copies, it.direction === 'more' ? 'more' : 'less', FD_TISSUE[it.tissue] || it.tissue));
      fdMake(d, 'span', 'gx-note', fdFill('GTEx NES {} per copy', it.nes));
    } else if (it.kind === 'gwas') {
      fdMake(d, 'b', null, fdFill('{} {} ×{}: {} {}', it.rsid, it.allele, it.copies, dir, it.trait));
      const r = fdMake(d, 'span', 'gx-note', it.or != null ? fdFill('OR {} per copy', it.or) : it.beta != null ? fdFill('β {} per copy', it.beta) : '');
      fdPmid(r, it.pmid, ` · ${it.author} ${it.year}`);
    }
  };

  const fdPartYou = (el, ctx, sec) => {
    // The overview: every section ranked by the evidence that the person's variants change it
    fdMake(el, 'span', 'gx-label fd-sec', fdFill('Which processes {}\'s variants change', ctx.who));
    const max = Math.max(1, ...ctx.impact.map((x) => x.score));
    const ov = fdMake(el, 'ol', 'fd-rank');
    for (const imp of [...ctx.impact].sort((a, b) => a.rank - b.rank)) {
      const genes = JSON.parse(imp.genes), counts = JSON.parse(imp.counts);
      const li = fdMake(ov, 'li', 'fd-rank-row' + (imp.section === sec.section ? ' is-on' : ''));
      const b = fdMake(li, 'button', 'fd-rank-btn'); b.type = 'button'; b.addEventListener('click', () => fdGo(imp.section, 'you', null));
      fdMake(b, 'b', null, imp.name);
      const bar = fdMake(b, 'span', 'fd-bar'); fdMake(bar, 'i').style.width = `${(imp.score / max) * 100}%`;
      fdMake(b, 'span', 'gx-note', imp.score ? fdFill('{} of {} genes with evidence', counts.with_evidence, counts.genes) : fdFill('No evidence in {} genes', counts.genes));
      const chips = fdMake(li, 'div', 'fd-tops');
      for (const g of genes.filter((x) => x.best).slice(0, 6)) {
        const it = g.items.find((i) => i.counts !== false) || g.items[0];
        const c = fdMake(chips, 'span', 'fd-top fd-g-' + g.best + ' fd-dir-' + it.direction);
        fdMake(c, 'b', null, g.gene); fdMake(c, 'span', null, { less: '▼', more: '▲', raises: '▲', lowers: '▼' }[it.direction] || '•');
        c.title = FD_GRADE[g.best];
      }
    }
    // The section: its genes with the person's evidence, each linked to its steps in Part 1
    const imp = ctx.impact.find((x) => x.section === sec.section);
    fdMake(el, 'h3', 'fd-h', sec.name);
    const genes = imp ? JSON.parse(imp.genes) : [], counts = imp ? JSON.parse(imp.counts) : {};
    const steps = JSON.parse(sec.steps), procs = JSON.parse(sec.processes);
    const stepName = (id) => { const i = steps.findIndex((s) => s.id === id); if (i >= 0) return [i, steps[i].name]; const p = procs.find((x) => x.id === id); return [null, p ? p.name : id]; };
    const hit = genes.filter((g) => g.items.length);
    if (!hit.length) fdMake(el, 'p', 'fd-empty', counts.calls === false ? fdFill('{}\'s gene calls have not been run yet, so only the measured studies and GWAS are read here.', ctx.who)
      : fdFill('None of {}\'s variants in the {} genes of this section has evidence of a change: they read as the typical form here.', ctx.who, genes.length));
    const list = fdMake(el, 'div', 'fd-hits');
    for (const g of hit) {
      const box = fdMake(list, 'article', 'fd-hit-card fd-g-' + g.best);
      const h = fdMake(box, 'div', 'fd-card-head');
      fdMake(h, 'h4', null, g.gene);
      if (!g.on_step) fdMake(h, 'span', 'fd-go-only', 'Gene Ontology process');
      const fn = ctx.fns.get(g.gene);
      if (fn && fn.protein) fdMake(h, 'span', 'fd-rs', fn.protein).setAttribute('data-i18n-skip', '');
      const links = fdMake(box, 'div', 'fd-steplinks');
      for (const id of g.steps) {
        const [i, name] = stepName(id);
        const a = fdMake(links, 'button', 'fd-steplink', name); a.type = 'button';
        a.setAttribute('data-i18n-skip', '');
        a.addEventListener('click', () => fdGo(sec.section, 'how', i));
      }
      const ul = fdMake(box, 'ul', 'fd-evs');
      for (const it of g.items) fdItem(ul, it, ctx);
    }
    const quiet = genes.filter((g) => !g.items.length);
    if (quiet.length) {
      const q = fdMake(el, 'div', 'fd-quiet');
      fdMake(q, 'span', 'gx-label', fdFill('No variant with evidence ({})', quiet.length));
      const chips = fdMake(q, 'div', 'fd-tops');
      for (const g of quiet.slice(0, 60)) { const c = fdMake(chips, 'span', 'fd-top fd-quiet-chip', g.gene); c.title = g.read ? fdFill('{} variants read', g.read) : 'not read'; }
      if (quiet.length > 60) fdMake(chips, 'span', 'gx-note', fdFill('+{} more', quiet.length - 60));
    }
    // The measured forms and the trait panels of the matching phase
    const ph = ctx.phases.find((p) => p.phase === sec.phase);
    if (ph) {
      if (ph.cards.length) {
        fdMake(el, 'span', 'gx-label fd-sec', 'Forms measured in women');
        const grid = fdMake(el, 'div', 'fd-cards');
        for (const c of [...ph.cards].sort((a, b) => (b.copies || 0) - (a.copies || 0))) fdCard(grid, c, { ...ctx, cards: ph.cards });
      }
      if (ph.clinvar) fdPoi(el, ph.clinvar, ctx);
      if (ph.gwas.length) {
        fdMake(el, 'span', 'gx-label fd-sec', fdFill('{}\'s lead variants for the traits of this phase: {}', ctx.who, FD_PHASE_NAMES[ph.phase] || ph.name));
        const panels = fdMake(el, 'div', 'fd-panels');
        for (const p of ph.gwas) fdPanel(panels, p, ctx);
        fdMake(el, 'p', 'gx-note', 'Each study\'s genome-wide significant lead variants (one per 500 kb), weighted by the study\'s effect sizes and placed against European frequencies. Chips are the variants that move the person most; outlined ones sit in a gene of this section.');
      }
    }
  };

  const fdPoi = (el, cv, ctx) => {
    const box = fdMake(el, 'div', 'fd-poi');
    fdMake(box, 'span', 'gx-label', 'Premature ovarian insufficiency');
    if (cv.medgen && cv.medgen.definition) { fdMake(box, 'p', 'fd-def', cv.medgen.definition).setAttribute('data-i18n-skip', ''); fdMake(box, 'span', 'gx-note', `MedGen · ${cv.medgen.title}`); }
    const tiles = fdMake(box, 'div', 'fd-tiles');
    for (const [n, t, bad] of [[cv.records, 'pathogenic variants in ClinVar'], [cv.genes.length, 'genes they sit in'], [cv.checkable, fdFill('checkable in {}\'s file', ctx.who)], [cv.carried.length, fdFill('carried by {}', ctx.who), true]]) {
      const d = fdMake(tiles, 'div', 'fd-tile' + (bad && n ? ' is-bad' : '')); fdMake(d, 'b', null, fdNum(n)); fdMake(d, 'span', null, t);
    }
    const gs = fdMake(box, 'div', 'fd-tops');
    for (const [g, n] of cv.genes.slice(0, 18)) { const s = fdMake(gs, 'span', 'fd-top'); fdMake(s, 'b', null, g); fdMake(s, 'span', null, `×${n}`); }
    if (cv.carried.length) {
      const ul = fdMake(box, 'ul', 'fd-gw');
      for (const c of cv.carried) { const li = fdMake(ul, 'li'); fdMake(li, 'span', null, `${c.genes[0]} ${c.rsid} ${c.genotype}`); fdMake(li, 'b', null, c.significance); fdMake(li, 'span', 'gx-note', c.condition); }
    }
  };

  dash.draw('fd-view', (el) => {
    el.replaceChildren();
    const card = el.closest('.gx-card');
    const on = gx.theme() === 'fertility_female';
    if (card) card.classList.toggle('th-off', !on);
    if (!on) return;
    const r = gx.rows('fd_phases', 'fd_genes', 'theme_genes', 'fd_explain', 'fd_impact');
    if (!r) { if (gx.failed('fd_phases', 'fd_genes', 'theme_genes', 'fd_explain', 'fd_impact')) gx.failLine(el); return; }
    const [rows, fnRows, tg, explainRows, impactRows] = r;
    if (!explainRows.length) { gx.emptyLine(el); return; }
    const who = gx.who();
    const phases = rows.map((x) => ({ ...x, days: JSON.parse(x.days), chains: JSON.parse(x.chains), cards: JSON.parse(x.cards), gwas: JSON.parse(x.gwas),
                                      clinvar: JSON.parse(x.clinvar) }));
    const explain = [...explainRows].sort((a, b) => a.order - b.order);
    const prm = dash.params();
    const sec = explain.find((s) => s.section === prm.fd_sec) || explain[0];
    const part = prm.fd_part === 'you' ? 'you' : 'how';
    const hits = new Set(impactRows.flatMap((x) => JSON.parse(x.genes).filter((g) => g.items.length).map((g) => g.gene)));
    const ctx = { who, tip: gx.tip(el), sec: sec.section, step: prm.fd_step != null ? Number(prm.fd_step) : 0, explain, impact: impactRows, phases,
                  fns: new Map(fnRows.map((f) => [f.gene, f])), has: (g) => hits.has(g), cards: [],
                  genes: new Map(tg.filter((g) => g.theme === 'fertility_female').map((g) => [g.gene, g])) };
    const parts = fdMake(el, 'div', 'fd-parts'); parts.setAttribute('role', 'group'); parts.setAttribute('aria-label', 'Part');
    for (const [id, num, label] of [['how', '1', 'How the cycle works'], ['you', '2', fdFill('What {}\'s variants change', who)]]) {
      const b = fdMake(parts, 'button', 'fd-part'); b.type = 'button'; b.setAttribute('aria-pressed', String(part === id));
      fdMake(b, 'i', null, num); fdMake(b, 'span', null, label);
      b.addEventListener('click', () => fdGo(sec.section, id, null));
    }
    if (part === 'how') fdPartHow(el, ctx, sec);
    else {
      if (!impactRows.length) { gx.emptyLine(el); return; }
      const tabs = fdMake(el, 'div', 'fd-pick');
      for (const s of explain) { const b = fdMake(tabs, 'button', 'fd-pick-btn', s.name); b.type = 'button'; b.setAttribute('aria-pressed', String(s === sec)); b.addEventListener('click', () => fdGo(s.section, 'you', null)); }
      fdPartYou(el, ctx, sec);
    }
  });
