  // Gene lifecycle: gene picker, role switch, gene summary, regulation, node graph, route patterns and step details
  const LC = { key: null, step: null, wrap: true, drawnKey: null, scroll: 0 };
  const FN_TEXT = { LoF: 'Less active (LoF)', GoF: 'More active (GoF)', altered: 'Changed, direction unclear', normal: 'Typical function',
                    unknown: 'Genotype not interpretable' };
  const FN_CLASS = { LoF: 'lof', GoF: 'gof', altered: 'altered', normal: 'norm', unknown: 'unknown' };
  // Blue = more active (GoF), green = typical function, red = less active (LoF)
  const FN_STROKE = { LoF: 'var(--color-bad)', GoF: 'var(--gof)', altered: 'var(--color-fg)', normal: 'var(--typical)',
                      unknown: 'var(--color-fg-muted)' };
  const SECTION = { 'upstream-extension': 'Before the pathway', pathway: 'In the pathway', focal: 'This gene', 'downstream-extension': 'After the pathway' };
  const VERB = /\b(transfers|hydroxylates|oxidi[sz]es|translocates|hydroly[sz]es|deaminates|binds|cleaves|isomeri[sz]es|transports|reduces|transforms|dehydrogenates|condenses|assembles|catalyzes|demethylates|methylates|phosphorylates|ligates|desaturates|monooxygenates|synthesi[sz]es|conjugates|acetylates|glucuronidates|decarboxylates|exports|imports)\b/i;
  const GLOSSARY = {
    THF: 'tetrahydrofolate', THFPG: 'tetrahydrofolate polyglutamate', '5-methyl-THF': '5-methyl-tetrahydrofolate, the circulating folate',
    '5-methyl-THFPG': '5-methyl-tetrahydrofolate polyglutamate', '5,10-methylene-THF': '5,10-methylene-tetrahydrofolate',
    '5,10-methylene-THFPG': '5,10-methylene-tetrahydrofolate polyglutamate', '5,10-methenyl-THFPG': '5,10-methenyl-tetrahydrofolate polyglutamate',
    '10-formyl-THFPG': '10-formyl-tetrahydrofolate polyglutamate', '5-formyl-THFPG': '5-formyl-tetrahydrofolate polyglutamate (folinic acid form)',
    AdoMet: 'S-adenosylmethionine (SAM), the main methyl donor', AdoHcy: 'S-adenosylhomocysteine (SAH)', HCYS: 'homocysteine',
    'L-Met': 'methionine', 'L-Cys': 'cysteine', 'L-Ser': 'serine', Gly: 'glycine', 'L-Ala': 'alanine', 'L-Glu': 'glutamate',
    'L-His': 'histidine', 'L-Cystathionine': 'cystathionine', '2OBUTA': '2-oxobutanoate', NH3: 'ammonia',
    GSH: 'glutathione (reduced)', GSSG: 'glutathione (oxidised)', CysGly: 'cysteinylglycine', gGluCys: 'gamma-glutamylcysteine',
    H2O2: 'hydrogen peroxide', 'O2.-': 'superoxide', NO: 'nitric oxide', CO: 'carbon monoxide',
    EtOH: 'ethanol', CH3CHO: 'acetaldehyde', 'CH3COO-': 'acetate', 'Ac-CoA': 'acetyl-CoA', MeOH: 'methanol', CH2O: 'formaldehyde',
    HCOOH: 'formic acid', '5HT': 'serotonin', '5HIALD': '5-hydroxyindole-acetaldehyde', HIAA: '5-hydroxyindoleacetic acid',
    DA: 'dopamine', DOPAC: '3,4-dihydroxyphenylacetic acid', HVA: 'homovanillic acid', '3MT': '3-methoxytyramine',
    Hist: 'histamine', MeHist: 'N-methylhistamine', VD3: 'vitamin D3 (cholecalciferol)', '25(OH)D': '25-hydroxyvitamin D (calcidiol), the blood test form',
    '1,25(OH)2D': 'calcitriol, the active vitamin D', CHOL: 'cholesterol', '7-dehydroCHOL': '7-dehydrocholesterol, made into vitamin D3 by sunlight',
    DESMOL: 'desmosterol', LAN: 'lanosterol', ZYMOL: 'zymosterol', PREG: 'pregnenolone', '17aHPREG': '17-hydroxypregnenolone',
    P4: 'progesterone', '17aHPROG': '17-hydroxyprogesterone', DHEA: 'dehydroepiandrosterone', ANDST: 'androstenedione',
    TEST: 'testosterone', DHTEST: 'dihydrotestosterone', CORST: 'corticosterone', '11DCORST': '11-deoxycorticosterone',
    '18HCORST': '18-hydroxycorticosterone', ALDO: 'aldosterone', CORT: 'cortisol', COR: 'cortisone', '11DCORT': '11-deoxycortisol',
    BIL: 'bilirubin', BV: 'biliverdin', BMG: 'bilirubin monoglucuronide', BDG: 'bilirubin diglucuronide', APAP: 'paracetamol',
    NAPQI: 'NAPQI, the toxic paracetamol metabolite', atRAL: 'all-trans-retinal', betaC: 'beta-carotene',
    'UDP-GlcA': 'UDP-glucuronic acid', SeMet: 'selenomethionine', Sec: 'selenocysteine', AA: 'arachidonic acid',
    DHA: 'docosahexaenoic acid', '6MP': '6-mercaptopurine', '6MMP': '6-methylmercaptopurine', GTN: 'nitroglycerin',
    'ASA-': 'aspirin (acetylsalicylate)',
  };
  const pctFmt = d3.format('.0%');
  const split = (t) => (t || '').split(', ').filter(Boolean);
  const full = (m) => GLOSSARY[m] ? `${m}: ${GLOSSARY[m]}` : m;
  const actionOf = (x) => { const m = (x.reaction || '').match(VERB); return m ? m[1][0].toUpperCase() + m[1].slice(1).toLowerCase() : x.transport ? 'Moves' : 'Converts'; };
  const pretty = (c) => (c || '').replace(/_variant$/, '').replace(/_/g, ' ');
  const regName = (n) => { const p = n.split('_'); return p.length > 2 ? `${p[0]} complex (+${p.length - 1})` : p.join('–'); };
  const make = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  // GTEx expression for HP's copies of the effect allele, and whether it contradicts the library's activity call
  const exprShift = (f, gt) => {
    const net = (gt.copies || 0) * gt.nes, size = Math.abs(net) < 0.1 ? 'slightly' : Math.abs(net) < 0.4 ? 'moderately' : 'strongly';
    const lead = !gt.copies ? `HP has no ${gt.allele}, so this eQTL leaves HP's ${f.gene} expression at the usual level.`
      : `HP's ${gt.copies === 2 ? 'two copies' : 'copy'} of ${gt.allele} ${size} ${net > 0 ? 'raise' : 'lower'}${gt.copies === 1 ? 's' : ''} how much ` +
        `${f.gene} is made (net ${d3.format('+.2f')(net)}).`;
    const conflict = gt.copies && ((f.function === 'GoF' && net < -0.05) || (f.function === 'LoF' && net > 0.05))
      ? `This disagrees with the library, which reads HP's genotype as ${f.function === 'GoF' ? 'more' : 'less'} active. Less RNA can still ` +
        'mean more protein activity, but the library entry is worth checking against the papers.' : null;
    return { net, lead, conflict };
  };
  const openGene = (gene) => { LC.step = null; dash.setParams({ lc_gene: gene, lc_role: 1 }); };

  const lcSel = () => {
    const r = gx.rows('lifecycle_genes');
    if (!r) return null;
    const genes = r[0];
    const p = dash.params();
    const gene = genes.some((g) => g.gene === p.lc_gene) ? p.lc_gene : genes[0].gene;
    const roles = genes.filter((g) => g.gene === gene).sort((a, b) => a.role - b.role);
    const role = roles.find((g) => g.role === Number(p.lc_role)) || roles[0];
    const key = gene + '|' + role.role;
    if (LC.key !== key) { LC.key = key; LC.step = null; }
    return { genes, gene, roles, role, key };
  };

  let fnCache = { rows: null, map: new Map() };
  const lcFn = () => {
    const r = gx.rows('gene_function');
    if (!r) return new Map();
    if (fnCache.rows !== r[0]) fnCache = { rows: r[0], map: new Map(r[0].map((g) => [g.gene, { ...g, ev: JSON.parse(g.evidence || '{}'), lit: JSON.parse(g.literature || '{}'),
      ladder: JSON.parse(g.ladder || '[]') }])) };
    return fnCache.map;
  };

  const lcSteps = (s) => {
    const st = gx.rows('lifecycle_steps');
    if (!s || !st) return null;
    return st[0].filter((x) => x.gene === s.gene && x.role === s.role.role).sort((a, b) => a.order - b.order)
      .map((x) => ({ ...x, enz: JSON.parse(x.enzymes) }));
  };
  const selectedIndex = (steps) => {
    const i = steps.findIndex((x) => x.order === LC.step);
    if (i >= 0) return i;
    const f = steps.findIndex((x) => x.section === 'focal');
    return f >= 0 ? f : 0;
  };

  // A neighbouring pair of steps where HP's calls could make a molecule build up or run short
  const calledFns = (x) => x.enz.filter((g) => g.lib && (g.fn === 'LoF' || g.fn === 'GoF')).map((g) => g.fn);
  const patternAt = (prev, cur) => {
    const a = calledFns(prev), b = calledFns(cur), m = prev.outputs || 'the product';
    const backup = (x) => x.enz.length > 1 ? ' Other enzymes at that step may make up for it.' : '';
    if (a.includes('GoF') && b.includes('LoF')) return `Possible build-up of ${m}: a more active step feeds a less active one.` + backup(cur);
    if (a.includes('LoF') && b.includes('LoF')) return `Bottleneck around ${m}: two less active steps in a row.` + backup(prev);
    if (a.includes('LoF') && b.length) return `Lower supply of ${m}: a less active step feeds the next one.` + backup(prev);
    return null;
  };

  const chipLabel = (g) => {
    if (!g.lib) return g.gene + ' *';
    if (!g.gt) return g.gene;
    return `${g.gene} ${g.gt}` + (g.fn && g.fn !== 'normal' && g.dose ? ` ×${g.dose}` : '');
  };

  dash.draw('lc-gene', (sel) => {
    const s = lcSel();
    const names = s ? [...new Set(s.genes.map((g) => g.gene))].sort() : [];
    sel.replaceChildren(...names.map((n) => new Option(n, n)));
    if (s) sel.value = s.gene;
    sel.onchange = () => openGene(sel.value);
  });

  dash.draw('lc-roles', (el) => {
    el.replaceChildren();
    const s = lcSel();
    if (!s) return;
    for (const r of s.roles) {
      const b = make(el, 'button', 'lc-role', `${r.pathway} · ${r.n_steps} steps`);
      b.type = 'button';
      b.setAttribute('aria-pressed', String(r.role === s.role.role));
      b.addEventListener('click', () => dash.setParams({ lc_role: r.role }));
    }
  });

  dash.draw('lc-head', (el) => {
    el.replaceChildren();
    const s = lcSel();
    if (!s) { if (gx.failed('lifecycle_genes')) gx.failLine(el); return; }
    const f = lcFn().get(s.gene) || {};
    const ev = f.ev || {};
    const fn = f.genotype ? (f.function || 'unknown') : null;
    const card = el.closest('.gx-card');
    if (card) for (const t of ['gof', 'lof', 'norm']) card.classList.toggle('lc-tone-' + t, FN_CLASS[fn] === t);

    const name = make(el, 'div', 'lc-name');
    make(name, 'h3', null, s.gene);
    if (fn) make(name, 'span', 'lc-call ' + FN_CLASS[fn], FN_TEXT[fn] + (fn !== 'normal' && f.dose ? ` ×${f.dose}` : ''));
    else make(name, 'span', 'lc-call unknown', 'Not genotyped');

    const copies = f.dose === 2 ? 'two copies' : 'one copy';
    let lead;
    if (!f.genotype) lead = "HP's file has no usable call at this gene's library SNP, so its activity in HP is not known.";
    else if (fn === 'unknown') lead = `At ${f.rsid} HP is ${f.genotype}, which could not be matched to the alleles Ensembl lists for this SNP.`;
    else lead = `At ${f.rsid} HP is ${f.genotype}: ` + (f.dose ? `${copies} of the less common ${f.minor} allele. ` : `both copies are the common ${f.common} allele. `) +
      `The library reads this genotype as ${fn === 'LoF' ? 'less active' : fn === 'GoF' ? 'more active' : fn === 'normal' ? 'typical function'
        : 'changed, without saying which way activity goes'} ("${f.interpretation}").`;
    if (f.genotype && f.minor_af >= 0.4) lead += ` Both forms are common in Europeans (${f.minor} ${pctFmt(f.minor_af)}).`;
    make(el, 'p', 'lc-lead', lead);

    if (!f.genotype) return;
    const ul = make(el, 'ul', 'lc-ev');
    const row = (k, v) => { const li = make(ul, 'li'); make(li, 'span', null, k); make(li, 'span', null, v); };
    row('Best evidence', ev.tier_name || 'No functional evidence collected');
    row('Library reading', `${f.interpretation} (report score ${f.score}/10${f.n_snps > 1 ? `, strongest of ${f.n_snps} SNPs` : ''})`);
    if (ev.protein_change || ev.consequence) row('Change', [ev.protein_change, pretty(ev.consequence)].filter(Boolean).join(', '));
    if (ev.mavedb) {
      const sc = ev.mavedb.map((m) => m.score), lo = ev.mavedb.reduce((a, b) => (b.score < a.score ? b : a));
      row('Measured', `${ev.mavedb[0].change} scored ${d3.min(sc)} to ${d3.max(sc)} across ${sc.length} conditions in a deep mutational scan ` +
        `(MaveDB), lowest in "${lo.conditions}". Each study sets its own scale; in most, 1 is the normal protein. ` +
        `HP carries ${f.dose} ${f.dose === 1 ? 'copy' : 'copies'} of the less common allele.`);
    }
    if (ev.gtex) {
      const g = ev.gtex, x = exprShift(f, g);
      row('Expression', `${x.lead} Each ${g.allele} allele ${g.direction} it in ${g.n_tissues} tissues (strongest in ${g.tissue}, ` +
        `effect ${d3.format('+.2f')(g.nes)} per copy on GTEx's normalised scale).` + (x.conflict ? ` ⚠ ${x.conflict}` : ''));
    }
    if (ev.uniprot) row('Curated (UniProt)', ev.uniprot.join('; '));
    if (ev.predicted) row('Predicted', ev.predicted.join(', '));
    const pgx = (ev.clinpgx || []).find((x) => x.phenotype);
    if (pgx) row(`Drugs (ClinPGx ${pgx.level})`, `${pgx.chemicals}: ${pgx.phenotype.length > 260 ? pgx.phenotype.slice(0, 257) + '…' : pgx.phenotype}`);
  });

  dash.draw('lc-context', (el) => {
    el.replaceChildren();
    const s = lcSel();
    if (!s) { if (gx.failed('lifecycle_genes')) gx.failLine(el); return; }
    const r = s.role, fns = lcFn();
    const block = (label) => { const d = make(el, 'div'); make(d, 'span', 'gx-label', label); return d; };

    const pw = block('Pathway');
    make(pw, 'p', null, `${r.pathway}${r.top_pathway && r.top_pathway !== r.pathway ? ' (' + r.top_pathway + ')' : ''}.` +
      (r.other_pathways ? ` ${s.gene} also works in ${r.other_pathways} more pathways not drawn here.` : ''));
    make(pw, 'p', 'gx-muted', `Starts: ${r.start.replace(/^Starts at /, '')}`);
    make(pw, 'p', 'gx-muted', `Ends: ${r.end}`);

    if (r.cofactors) make(block('Needs'), 'p', null, `${r.cofactors}${r.vitamins ? ' → from ' + r.vitamins : ''}`);

    if (r.regulation) {
      const d = block('Feedback');
      const sentences = r.regulation.split(/(?<=\))\.\s+|\.\s+(?=[A-Z])/);
      if (r.regulation.length <= 200) make(d, 'p', null, r.regulation);
      else {
        const det = make(d, 'details');
        make(det, 'summary', null, sentences[0].slice(0, 180) + (sentences[0].length > 180 ? '…' : '') + ` (${sentences.length} notes)`);
        make(det, 'p', null, r.regulation);
      }
    }

    const regs = JSON.parse(r.regulators || '[]');
    if (regs.length) {
      const d = block('Regulated by');
      const box = make(d, 'div', 'lc-regs');
      for (const effect of ['activates', 'inhibits', 'acts on']) {
        const list = regs.filter((x) => x.effect === effect);
        if (!list.length) continue;
        const line = make(box, 'div', 'lc-reg-row');
        make(line, 'span', null, effect === 'acts on' ? 'Acts on it' : effect[0].toUpperCase() + effect.slice(1));
        for (const x of list) {
          const f = fns.get(x.gene);
          const label = regName(x.gene) + (f && f.genotype ? ` ${f.genotype}` : '');
          const chip = f && f.has_lifecycle ? make(line, 'button', 'gx-chip', label) : make(line, 'span', 'gx-chip', label);
          chip.title = x.gene.split('_').join(', ') + (x.lib ? ' (in library)' : '');
          if (f && f.genotype) chip.style.borderColor = FN_STROKE[f.function] || '';
          if (f && f.has_lifecycle) { chip.type = 'button'; chip.addEventListener('click', () => openGene(x.gene)); }
        }
      }
      make(d, 'p', 'gx-note', 'From OmniPath. Genes with a genotype are in the library; select one to open its lifecycle.');
    }
  });

  // Lifecycle as a left-to-right node graph: start, molecule, step, molecule, step, ..., end
  dash.draw('lc-timeline', (el) => {
    const s = lcSel();
    if (LC.drawnKey === (s && s.key)) LC.scroll = el.scrollLeft;
    el.replaceChildren();
    const steps = lcSteps(s);
    if (!s || !steps) { if (gx.failed('lifecycle_steps', 'lifecycle_genes', 'gene_function')) gx.failLine(el); return; }
    if (!steps.length) return;
    const fns = lcFn();
    const sel = selectedIndex(steps);
    const FS = 12, SMALL = 11, LINE = 15, GAP = 36, TOP = 34;

    const svg = d3.select(el).append('svg').attr('role', 'group').attr('aria-label', `Lifecycle of ${s.gene}: ${s.role.pathway}`);
    const probe = svg.append('text').style('visibility', 'hidden');
    const textW = (t, size = FS, weight = 400) => { probe.attr('font-size', size).attr('font-weight', weight).text(t); return probe.node().getComputedTextLength(); };
    const wrap = (t, maxW, maxLines, size = FS, weight = 400) => {
      const lines = []; let cur = '';
      for (const w of String(t || '').split(/\s+/).filter(Boolean)) {
        const test = cur ? cur + ' ' + w : w;
        if (textW(test, size, weight) <= maxW || !cur) cur = test; else { lines.push(cur); cur = w; }
      }
      if (cur) lines.push(cur);
      const out = lines.slice(0, maxLines);
      const fit = (l) => { while (l.length > 1 && textW(l + '…', size, weight) > maxW) l = l.slice(0, -1); return l + '…'; };
      if (lines.length > maxLines) out[maxLines - 1] = fit(out[maxLines - 1]);
      return out.map((l) => textW(l, size, weight) > maxW ? fit(l) : l);
    };

    // 1. Node sequence
    const nodes = [{ type: 'end', tag: 'Starts', text: s.role.start.replace(/^Starts at /, '') }];
    steps.forEach((x, i) => {
      const prev = i > 0 ? steps[i - 1] : null;
      const molText = prev ? (prev.outputs || '?') : (x.inputs || '?');
      nodes.push({ type: 'mol', text: molText, warn: prev ? patternAt(prev, x) : null });
      const carried = new Set(split(molText));
      nodes.push({ type: 'step', x, i, extra: split(x.inputs).filter((m) => !carried.has(m)) });
    });
    nodes.push({ type: 'mol', text: steps[steps.length - 1].outputs || '?' });
    nodes.push({ type: 'end', tag: 'Ends', text: s.role.end });

    // 2. Measure
    for (const n of nodes) {
      if (n.type === 'mol') {
        n.lines = wrap(n.text, 150, 3, FS, 600);
        n.w = Math.round(Math.max(64, d3.max(n.lines, (l) => textW(l, FS, 600)) + 28));
        n.h = n.lines.length * LINE + 18;
      } else if (n.type === 'end') {
        n.w = 170;
        n.lines = wrap(n.text, n.w - 20, 5, SMALL);
        n.h = (n.lines.length + 1) * LINE + 18;
      } else {
        const x = n.x, W = 184, inner = W - 20;
        n.w = W;
        n.parts = [{ kind: 'action', text: actionOf(x) }];
        if (n.extra.length) n.parts.push(...wrap('+ ' + n.extra.join(', '), inner, 2, SMALL).map((t) => ({ kind: 'small', text: t })));
        if (x.transport) n.parts.push(...wrap(x.move, inner, 2, SMALL).map((t) => ({ kind: 'small', text: t })));
        n.chips = [];
        let cx = 0, row = 0;
        const shown = x.enz.slice(0, 6);
        for (const g of shown) {
          const label = chipLabel(g);
          const w = Math.round(Math.min(inner, textW(label, SMALL) + 14));
          if (cx && cx + w > inner) { cx = 0; row += 1; }
          n.chips.push({ g, label, x: cx, row, w });
          cx += w + 4;
        }
        n.more = x.enz.length - shown.length;
        n.noEnzyme = !x.enz.length ? (x.transport ? 'Carrier not listed' : 'No enzyme listed') : null;
        n.chipRows = n.chips.length ? row + 1 : 1;
        n.h = 12 + n.parts.length * LINE + 4 + n.chipRows * 22 + (n.more > 0 ? LINE : 0) + 6;
      }
    }
    probe.remove();

    // 3. Layout: rows that fit the card (wrapped) or one long line, each row with a lane for section labels above
    const wrapped = LC.wrap && el.clientWidth > 320;
    const avail = el.clientWidth - 4;
    const rows = [];
    let cursor = 16, row = [];
    for (const n of nodes) {
      if (wrapped && row.length && cursor + n.w > avail - 8) { rows.push(row); row = []; cursor = 16; }
      n.left = cursor; row.push(n); cursor += n.w + GAP;
    }
    rows.push(row);
    let y0 = 0;
    rows.forEach((r, ri) => {
      r.h = d3.max(r, (n) => n.h);
      r.lane = y0 + TOP;
      r.cy = Math.round(r.lane + 18 + r.h / 2);
      r.bottom = r.cy + r.h / 2;
      for (const n of r) { n.row = ri; n.cy = r.cy; }
      y0 = r.bottom + 18;
    });

    // A route that ends on a molecule it passed earlier is a cycle
    const molNodes = nodes.filter((n) => n.type === 'mol');
    const lastMol = molNodes[molNodes.length - 1];
    const lastSet = split(lastMol.text);
    let loopTo = molNodes.slice(0, -1).find((n) => n.text === lastMol.text);
    let loopMol = loopTo ? lastSet[0] : null;
    if (!loopTo && /^recycled/i.test(s.role.end)) {
      loopTo = molNodes.slice(0, -1).find((n) => split(n.text).some((m) => lastSet.includes(m)));
      loopMol = loopTo ? split(loopTo.text).find((m) => lastSet.includes(m)) : null;
    }
    const loopArc = loopTo && loopTo.row === lastMol.row;
    const W = wrapped ? avail : cursor - GAP + 16;
    const H = rows[rows.length - 1].bottom + (loopArc ? 64 : loopTo ? 30 : 12);
    svg.attr('viewBox', `0 0 ${W} ${H}`).attr('width', W).attr('height', H);
    const tip = gx.tip(el);

    const markerId = 'lc-arrow';
    svg.append('defs').append('marker').attr('id', markerId).attr('viewBox', '0 0 10 10').attr('refX', 9).attr('refY', 5)
      .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto')
      .append('path').attr('d', 'M0,0 L10,5 L0,10 z').style('fill', 'var(--color-fg-muted)');

    // Section brackets over runs of steps from the same part of the route
    const runs = [];
    for (const n of nodes.filter((n) => n.type === 'step')) {
      const last = runs[runs.length - 1];
      if (last && last.section === n.x.section && last.to.row === n.row) last.to = n;
      else runs.push({ section: n.x.section, from: n, to: n, cont: !!last && last.section === n.x.section });
    }
    for (const r of runs) {
      const x0 = r.from.left, x1 = r.to.left + r.to.w, focal = r.section === 'focal', lane = rows[r.from.row].lane;
      const g = svg.append('g');
      g.append('path').attr('d', `M${x0},${lane + 6} V${lane} H${x1} V${lane + 6}`).style('fill', 'none')
        .style('stroke', focal ? 'var(--color-fg)' : 'var(--color-border-line)').attr('stroke-width', focal ? 1.5 : 1);
      g.append('text').attr('x', x0).attr('y', lane - 8).attr('font-size', SMALL).attr('letter-spacing', '.05em')
        .attr('font-weight', focal ? 700 : 400).style('fill', focal ? 'var(--color-fg)' : 'var(--color-fg-muted)')
        .text((SECTION[r.section] || r.section).toUpperCase() + (r.cont ? ' (CONT.)' : ''));
    }

    // 4. Connectors: straight within a row, down and back to the start of the next row
    for (let i = 0; i < nodes.length - 1; i++) {
      const a = nodes[i], b = nodes[i + 1];
      const dashed = (b.type === 'step' && b.x.transport) || (a.type === 'step' && a.x.transport);
      const line = a.row === b.row
        ? `M${a.left + a.w},${a.cy} H${b.left - 2}`
        : `M${a.left + a.w},${a.cy} H${a.left + a.w + 12} V${rows[a.row].bottom + 9} H${b.left - 10} V${b.cy} H${b.left - 2}`;
      svg.append('path').attr('d', line).style('fill', 'none')
        .style('stroke', 'var(--color-fg-muted)').attr('stroke-width', 1.5)
        .attr('stroke-dasharray', dashed ? '5 4' : null).attr('marker-end', `url(#${markerId})`);
    }
    if (loopArc) {
      const x1 = lastMol.left + lastMol.w / 2, y1 = lastMol.cy + lastMol.h / 2, x2 = loopTo.left + loopTo.w / 2, y2 = loopTo.cy + loopTo.h / 2 + 2;
      const yb = rows[lastMol.row].bottom + 44;
      svg.append('path').attr('d', `M${x1},${y1} C${x1},${yb} ${x2},${yb} ${x2},${y2}`).style('fill', 'none')
        .style('stroke', 'var(--color-fg-muted)').attr('stroke-width', 1.5).attr('stroke-dasharray', '6 4').attr('marker-end', `url(#${markerId})`);
      svg.append('text').attr('x', (x1 + x2) / 2).attr('y', yb - 4).attr('text-anchor', 'middle').attr('font-size', SMALL)
        .style('fill', 'var(--color-fg-muted)').text(`↺ ${loopMol} goes back into the route: it is a cycle`);
    } else if (loopTo) {
      // Right-aligned to the molecule so the note never runs past the drawing
      svg.append('text').attr('x', lastMol.left + lastMol.w).attr('y', rows[lastMol.row].bottom + 20).attr('text-anchor', 'end').attr('font-size', SMALL)
        .style('fill', 'var(--color-fg-muted)').text(`↺ ${loopMol} goes back to an earlier step: the route is a cycle`);
    }

    // 5. Nodes
    const stepGroups = [];
    const select = (i) => {
      LC.step = steps[i].order;
      for (const sg of stepGroups) sg.node.classList.toggle('is-selected', sg.i === i);
      dash.draw('lc-detail');
    };
    for (const n of nodes) {
      const g = svg.append('g').attr('transform', `translate(${Math.round(n.left)},${Math.round(n.cy - n.h / 2)})`);
      if (n.type === 'mol') {
        g.append('rect').attr('x', 0.5).attr('y', 0.5).attr('width', n.w - 1).attr('height', n.h - 1).attr('rx', Math.min(n.h / 2, 22))
          .style('fill', 'var(--color-bg)').style('stroke', 'var(--color-border-line)').attr('stroke-width', 1);
        n.lines.forEach((l, i) => g.append('text').attr('x', n.w / 2).attr('y', 9 + LINE * (i + 0.8)).attr('text-anchor', 'middle')
          .attr('font-size', FS).attr('font-weight', 600).style('fill', 'var(--color-fg)').text(l));
        g.on('mousemove', (event) => tip.show(event, 'Molecule', split(n.text).map(full))).on('mouseleave', () => tip.hide());
        if (n.warn) {
          const b = svg.append('g').attr('transform', `translate(${n.left + n.w / 2},${n.cy - n.h / 2 - 13})`).style('cursor', 'help')
            .on('mousemove', (event) => tip.show(event, 'Pattern in HP', [n.warn])).on('mouseleave', () => tip.hide());
          b.append('circle').attr('r', 9).style('fill', 'var(--color-bad)');
          b.append('text').attr('y', 4).attr('text-anchor', 'middle').attr('font-size', FS).attr('font-weight', 700)
            .style('fill', 'var(--color-bg)').text('!');
        }
      } else if (n.type === 'end') {
        g.append('rect').attr('width', n.w).attr('height', n.h).attr('rx', 6).style('fill', 'none')
          .style('stroke', 'var(--color-fg-muted)').attr('stroke-dasharray', '4 3');
        g.append('text').attr('x', 10).attr('y', 9 + LINE * 0.8).attr('font-size', SMALL).attr('letter-spacing', '.05em')
          .style('fill', 'var(--color-fg-muted)').text(n.tag.toUpperCase());
        n.lines.forEach((l, i) => g.append('text').attr('x', 10).attr('y', 9 + LINE * (i + 1.8)).attr('font-size', SMALL)
          .style('fill', 'var(--color-fg)').text(l));
      } else {
        const x = n.x, focal = x.section === 'focal';
        const enzNames = x.enz.map((e) => e.gene).join(', ') || 'no listed enzyme';
        g.attr('class', 'lc-step' + (n.i === sel ? ' is-selected' : '')).attr('tabindex', 0).attr('role', 'button')
          .attr('aria-label', `Step ${n.i + 1} of ${steps.length}, ${SECTION[x.section] || x.section}: ${actionOf(x)} by ${enzNames}`)
          .on('click', () => select(n.i))
          .on('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(n.i); }
            if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
              event.preventDefault();
              const next = stepGroups[n.i + (event.key === 'ArrowRight' ? 1 : -1)];
              if (next) next.node.focus();
            }
          })
          .on('mousemove', (event) => tip.show(event, actionOf(x), [x.reaction, 'Select for details']))
          .on('mouseleave', () => tip.hide());
        stepGroups.push({ i: n.i, node: g.node() });
        // Selection ring sits outside the card, so "selected" and "this gene" can be told apart
        g.append('rect').attr('class', 'lc-sel-ring').attr('x', -6).attr('y', -6).attr('width', n.w + 12).attr('height', n.h + 12).attr('rx', 12);
        g.append('rect').attr('class', 'lc-card' + (focal ? ' is-focal' : '')).attr('x', focal ? 1 : 0.5).attr('y', focal ? 1 : 0.5)
          .attr('width', n.w - (focal ? 2 : 1)).attr('height', n.h - (focal ? 2 : 1)).attr('rx', 8);
        let y = 12;
        for (const p of n.parts) {
          g.append('text').attr('x', 10).attr('y', y + 11).attr('font-size', p.kind === 'action' ? FS : SMALL)
            .attr('font-weight', p.kind === 'action' ? 600 : 400)
            .style('fill', p.kind === 'action' ? 'var(--color-fg)' : 'var(--color-fg-muted)').text(p.text);
          y += LINE;
        }
        y += 4;
        if (n.noEnzyme) g.append('text').attr('x', 10).attr('y', y + 13).attr('font-size', SMALL).style('fill', 'var(--color-fg-muted)').text(n.noEnzyme);
        for (const c of n.chips) {
          const f = fns.get(c.g.gene);
          const opens = f && f.has_lifecycle && c.g.gene !== s.gene;
          const cg = g.append('g').attr('transform', `translate(${10 + c.x},${y + c.row * 22})`).attr('class', opens ? 'lc-enz' : null);
          const called = c.g.lib && c.g.gt && ['LoF', 'GoF', 'normal'].includes(c.g.fn);
          const stroke = !c.g.lib ? 'none' : !c.g.gt ? 'var(--color-fg-muted)' : FN_STROKE[c.g.fn] || FN_STROKE.normal;
          cg.append('rect').attr('width', c.w).attr('height', 18).attr('rx', 9)
            .style('fill', called ? `color-mix(in srgb, ${FN_STROKE[c.g.fn]} 25%, var(--color-bg))` : 'var(--color-bg)')
            .style('stroke', stroke).attr('stroke-width', called ? 2 : 1.5)
            .attr('stroke-dasharray', c.g.lib && !c.g.gt ? '3 2' : c.g.fn === 'altered' ? '1.5 2' : null);
          cg.append('text').attr('x', c.w / 2).attr('y', 13).attr('text-anchor', 'middle').attr('font-size', SMALL)
            .attr('text-decoration', opens ? 'underline' : null)
            .style('fill', !c.g.lib ? 'var(--color-fg-muted)' : 'var(--color-fg)').text(c.label);
          cg.on('mousemove', (event) => {
            event.stopPropagation();
            tip.show(event, c.g.gene, !c.g.lib ? ['Not in the library'] : !f || !f.genotype ? ['In the library, no call in HP'] :
              [`${FN_TEXT[f.function] || ''}${f.function !== 'normal' && f.dose ? ' ×' + f.dose : ''} · ${f.rsid} ${f.genotype}`, f.interpretation,
                opens ? 'Select to open its lifecycle' : ''].filter(Boolean));
          });
          if (opens) cg.on('click', (event) => { event.stopPropagation(); tip.hide(); openGene(c.g.gene); });
        }
        y += n.chipRows * 22;
        if (n.more > 0) g.append('text').attr('x', 10).attr('y', y + 10).attr('font-size', SMALL).style('fill', 'var(--color-fg-muted)').text(`+${n.more} more enzymes`);
      }
    }

    // Open centred on the gene's own step; keep the scroll position while the same chain is redrawn
    if (LC.drawnKey !== s.key) {
      const focalNode = nodes.find((n) => n.type === 'step' && n.x.section === 'focal');
      el.scrollLeft = focalNode ? Math.max(0, focalNode.left + focalNode.w / 2 - el.clientWidth / 2) : 0;
    } else el.scrollLeft = LC.scroll;
    LC.drawnKey = s.key;
  });

  dash.draw('lc-patterns', (el) => {
    el.replaceChildren();
    const s = lcSel();
    const steps = lcSteps(s);
    if (!steps) return;
    const fns = lcFn();
    const lib = new Map();
    for (const x of steps) for (const g of x.enz) if (g.lib) lib.set(g.gene, fns.get(g.gene) || { gene: g.gene });
    const groups = [['GoF', 'More active'], ['normal', 'Typical function'], ['LoF', 'Less active'], ['altered', 'Changed, direction unclear']];
    const p = make(el, 'p');
    make(p, 'b', null, `${lib.size} library ${lib.size === 1 ? 'gene' : 'genes'} on this route. `);
    let first = true;
    for (const [fn, label] of groups) {
      const gs = [...lib.values()].filter((f) => f.genotype && f.function === fn);
      if (!gs.length) continue;
      p.append((first ? '' : ' · ') + label + ': ');
      first = false;
      gs.forEach((f, i) => {
        const t = `${f.gene} ${f.genotype}${fn !== 'normal' && f.dose ? ' ×' + f.dose : ''}`;
        if (f.has_lifecycle && f.gene !== s.gene) { const b = make(p, 'button', 'lc-link', t); b.type = 'button'; b.addEventListener('click', () => openGene(f.gene)); }
        else p.append(t);
        if (i < gs.length - 1) p.append(', ');
      });
    }
    const untyped = [...lib.values()].filter((f) => !f.genotype).map((f) => f.gene);
    if (untyped.length) p.append(`${first ? '' : ' · '}Not genotyped: ${untyped.join(', ')}`);
    const warns = steps.slice(1).map((x, i) => patternAt(steps[i], x)).filter(Boolean);
    if (warns.length) for (const w of warns) make(el, 'p', 'lc-warn', '⚠ ' + w);
    else make(el, 'p', 'gx-muted', 'No build-up or bottleneck pattern between neighbouring steps in HP.');
  });

  dash.draw('lc-detail', (el) => {
    el.replaceChildren();
    const s = lcSel();
    const steps = lcSteps(s);
    if (!steps) { if (gx.failed('lifecycle_steps', 'lifecycle_genes', 'gene_function')) gx.failLine(el); return; }
    if (!steps.length) return;
    const fns = lcFn();
    const i = selectedIndex(steps), x = steps[i];

    make(el, 'h3', null, `Step ${i + 1} of ${steps.length} · ${SECTION[x.section] || x.section} · ${actionOf(x)}`);
    make(el, 'p', 'lc-rx', x.reaction);

    const flow = make(el, 'div', 'lc-flowline');
    const mols = (list) => { for (const m of list) { const c = make(flow, 'span', 'lc-mol', m); if (GLOSSARY[m]) make(c, 'small', null, ' ' + GLOSSARY[m]); } };
    mols(split(x.inputs));
    make(flow, 'span', 'gx-muted', '→');
    mols(split(x.outputs));
    if (x.transport) make(el, 'p', 'gx-note', `Moves between compartments: ${x.move}`);
    const warn = i > 0 ? patternAt(steps[i - 1], x) : null;
    if (warn) make(el, 'p', 'lc-warn', '⚠ ' + warn);

    // One card per library enzyme: HP's call, how big the effect is, and where to read more
    const STEP_TEXT = { LoF: 'less active (LoF)', GoF: 'more active (GoF)', altered: 'changed, direction unclear', normal: 'with typical function',
                        unknown: 'not interpretable' };
    const outside = x.enz.filter((g) => !g.lib).map((g) => g.gene);
    const inLib = x.enz.filter((g) => g.lib);
    const called = inLib.map((g) => fns.get(g.gene)).filter((f) => f && f.genotype);
    const sum = make(el, 'p', 'lc-stepsum');
    sum.textContent = !inLib.length ? 'No library gene works at this step, so HP\'s genotypes say nothing about it.'
      : `In HP: ${called.length ? called.map((f) => `${f.gene} ${STEP_TEXT[f.function] || ''}` +
          (f.function !== 'normal' && f.dose ? ` (${f.dose === 2 ? 'two copies' : 'one copy'})` : '')).join(', ') : 'no library enzyme genotyped'}.` +
        (x.enz.length > 1 ? ` ${x.enz.length} enzymes can do this step, so one changed enzyme may be partly covered by the others.` : '');

    const bar = (parent, cls, lo, hi, min, max, tick) => {
      const track = make(parent, 'div', 'lc-bar ' + cls);
      const pos = (v) => `${((Math.max(min, Math.min(max, v)) - min) / (max - min)) * 100}%`;
      const fill = make(track, 'div', 'lc-bar-fill');
      fill.style.left = pos(Math.min(lo, hi)); fill.style.width = `calc(${pos(Math.max(lo, hi))} - ${pos(Math.min(lo, hi))})`;
      if (tick != null) { const t = make(track, 'div', 'lc-bar-tick'); t.style.left = pos(tick); }
      return track;
    };
    const paperLink = (parent, p) => {
      const a = make(parent, 'a', null, `PMID ${p.pmid}`);
      a.href = `https://pubmed.ncbi.nlm.nih.gov/${p.pmid}/`; a.target = '_blank'; a.rel = 'noopener';
      parent.append(` · ${[p.journal, p.year].filter(Boolean).join(' ')}${p.cited ? ` · cited ${p.cited}` : ''}`);
    };

    for (const g of inLib) {
      const f = fns.get(g.gene);
      const card = make(el, 'div', 'lc-enzcard' + (f && f.genotype && FN_CLASS[f.function] ? ' tone-' + FN_CLASS[f.function] : ''));
      const head = make(card, 'div', 'lc-enzhead');
      make(head, 'b', null, g.gene);
      if (!f || !f.genotype) { make(head, 'span', 'lc-call unknown', 'Not genotyped in HP'); continue; }
      make(head, 'span', 'gx-muted', `${f.rsid} ${f.genotype}`);
      make(head, 'span', 'lc-call ' + FN_CLASS[f.function], FN_TEXT[f.function] + (f.function !== 'normal' && f.dose ? ` ×${f.dose}` : ''));
      if (f.has_lifecycle && g.gene !== s.gene) { const b = make(head, 'button', 'lc-btn', 'Open its lifecycle'); b.type = 'button'; b.addEventListener('click', () => openGene(g.gene)); }
      const ev = f.ev || {}, lit = f.lit || {};
      make(card, 'p', 'gx-note', [`Library: ${f.interpretation}`, ev.protein_change, pretty(ev.consequence)].filter(Boolean).join(' · '));

      // How much
      const how = make(card, 'div', 'lc-how');
      make(how, 'span', 'gx-label', 'How much');
      let any = false;

      // Capacity: where HP sits against the common form (100%) and the other genotypes at this SNP
      const ladder = f.ladder || [];
      const mine = ladder.find((r) => r.genotype === [...f.genotype].sort().join(''));
      if (ladder.length) {
        any = true;
        const row = make(how, 'div', 'lc-howrow');
        make(row, 'span', 'lc-howkey', 'Capacity in HP');
        const body = make(row, 'div');
        const cap = mine && mine.capacity, measured = ladder.some((r) => r.dose > 0 && r.capacity);
        const pctR = (c) => c[0] === c[1] ? pctFmt(c[0]) : `${pctFmt(c[0])}–${pctFmt(c[1])}`;
        if (cap) bar(body, 'cap tone-' + FN_CLASS[f.function], 0, cap[1], 0, 1.25, 1);
        make(body, 'p', null, !f.dose
          ? `${pctFmt(1)} of the common form. HP has the common form, the baseline every measurement of this SNP is compared with` +
            (f.function === 'normal' ? '.' : `; the library still reads it as ${f.function === 'LoF' ? 'less' : 'more'} active.`)
          : cap ? `About ${pctR(cap)} of the common form (${f.dose === 2 ? 'two copies' : 'one copy'} of ${f.minor}).`
          : f.function === 'normal' ? `Typical function in the library's reading, with ${f.dose === 2 ? 'two copies' : 'one copy'} of ${f.minor}. ` +
            'No study gives a size for the difference from the common form.'
          : `${f.function === 'LoF' ? 'Below' : f.function === 'GoF' ? 'Above' : 'Different from'} the common form, with ` +
            `${f.dose === 2 ? 'two copies' : 'one copy'} of ${f.minor}. No activity scan has measured this change, so ` +
            ((lit.quotes || []).length ? 'the size comes from the papers quoted under Reported' : 'there is no measured size yet') +
            (ev.gtex ? '; Expression shows the effect on how much protein is made.' : '.'));
        const tbl = make(body, 'table', 'gx-table lc-ladder');
        const hr = make(make(tbl, 'thead'), 'tr');
        for (const h of ['Genotype', `Copies of ${f.minor}`, measured ? 'Capacity' : null, 'Library reading', 'Score'].filter(Boolean)) make(hr, 'th', null, h);
        const tb = make(tbl, 'tbody');
        for (const r of ladder) {
          const tr = make(tb, 'tr', r === mine ? 'is-hp tone-' + FN_CLASS[f.function] : null);
          make(tr, 'td', null, r.genotype + (r === mine ? ' · HP' : ''));
          make(tr, 'td', null, String(r.dose));
          if (measured) make(tr, 'td', null, r.capacity ? pctR(r.capacity) : '—');
          make(tr, 'td', null, r.text);
          make(tr, 'td', null, r.score != null ? `${r.score}/10` : '—');
        }
        make(body, 'p', 'gx-note', measured
          ? 'Capacity is the measured activity of each allele (MaveDB), added up over both copies; ranges cover the assay conditions.'
          : 'Capacity is relative: the common form is 100% by definition. A size for the other genotypes needs a measurement this SNP lacks.');
      }
      if (ev.mavedb) {
        any = true;
        const sc = ev.mavedb.map((m) => m.score), row = make(how, 'div', 'lc-howrow');
        make(row, 'span', 'lc-howkey', 'Measured activity');
        const body = make(row, 'div');
        bar(body, 'mave', d3.min(sc), d3.max(sc), 0, Math.max(1.25, d3.max(sc)), 1);
        make(body, 'p', 'gx-note', `${ev.mavedb[0].change}: ${d3.min(sc)} to ${d3.max(sc)} across ${sc.length} conditions (MaveDB deep mutational scan; ` +
          `the tick is 1, the normal protein in most studies). HP has ${f.dose} ${f.dose === 1 ? 'copy' : 'copies'} of the less common allele.`);
      }
      if (ev.gtex) {
        any = true;
        const gt = ev.gtex, x = exprShift(f, gt), row = make(how, 'div', 'lc-howrow');
        make(row, 'span', 'lc-howkey', 'Expression');
        const body = make(row, 'div');
        bar(body, 'gtex ' + (x.net > 0.005 ? 'up' : x.net < -0.005 ? 'down' : ''), 0, x.net, -1, 1, 0);
        make(body, 'p', null, x.lead);
        make(body, 'p', 'gx-note', `Each ${gt.allele} allele ${gt.direction} ${g.gene} expression by ${d3.format('.2f')(Math.abs(gt.nes))} ` +
          `(GTEx, strongest in ${gt.tissue}). This is an effect on GTEx's normalised expression scale, not a percentage: ` +
          `0.1 per copy is small, 0.5 large.`);
        if (x.conflict) make(body, 'p', 'lc-warn', '⚠ ' + x.conflict);
      }
      if (lit.quotes && lit.quotes.length) {
        any = true;
        const row = make(how, 'div', 'lc-howrow');
        make(row, 'span', 'lc-howkey', 'Reported');
        const body = make(row, 'div', 'lc-quotes');
        for (const q of lit.quotes) {
          const bq = make(body, 'blockquote', null, q.text);
          paperLink(make(bq, 'cite'), q);
        }
        make(body, 'p', 'gx-note', 'Sentences from abstracts that put a number on the effect, picked automatically. Check the paper: a number may ' +
          'describe a combined genotype or a specific group of people.');
      }
      if (ev.predicted) { any = true; const row = make(how, 'div', 'lc-howrow'); make(row, 'span', 'lc-howkey', 'Predicted'); make(row, 'span', null, ev.predicted.join(', ')); }
      if (!any) make(how, 'p', 'gx-note', 'No measured size found for this SNP. The direction comes from the library' + (ev.uniprot ? ' and UniProt.' : '.'));

      // Research
      if (lit.papers && lit.papers.length) {
        const res = make(card, 'div', 'lc-research');
        make(res, 'span', 'gx-label', 'Research: experimental papers cited by UniProt first, then the most cited');
        const ol = make(res, 'ol');
        for (const p of lit.papers) {
          const li = make(ol, 'li');
          const a = make(li, 'a', null, p.title);
          a.href = `https://pubmed.ncbi.nlm.nih.gov/${p.pmid}/`; a.target = '_blank'; a.rel = 'noopener';
          make(li, 'span', 'gx-muted', ` ${[p.journal, p.year].filter(Boolean).join(' ')}${p.cited ? ` · cited ${p.cited}` : ''}` +
            (p.source === 'UniProt experimental' ? ' · experimental, cited by UniProt' : ''));
        }
      }
    }
    if (outside.length) make(el, 'p', 'gx-note', `Also at this step, not in the library: ${outside.join(', ')}.`);

    const alts = (x.alternatives || '').split(' | ').filter(Boolean);
    make(el, 'span', 'gx-label', 'Other routes at this step');
    if (alts.length) { const ul = make(el, 'ul', 'lc-alts'); for (const a of alts) make(ul, 'li', null, a); }
    else make(el, 'p', 'gx-note', 'None in this pathway.');
    if (x.reaction_id) {
      const a = make(make(el, 'p', 'gx-note'), 'a', null, `Open ${x.reaction_id} in Reactome`);
      a.href = `https://reactome.org/content/detail/${x.reaction_id}`; a.target = '_blank'; a.rel = 'noopener';
    }
  });

  document.querySelectorAll('#lc-wrap').forEach((b) => b.addEventListener('click', () => {
    LC.wrap = !LC.wrap;
    b.setAttribute('aria-pressed', String(LC.wrap));
    dash.draw('lc-timeline');
  }));

