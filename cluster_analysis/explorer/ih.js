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

  dash.draw('ih-head', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair) return;
    if (!pair.xx.length || !pair.xy.length) { ihMake(el, 'p', 'ih-empty', 'This needs an XX and an XY profile: add a person of the other sex to see what a child of the two could inherit.'); return; }
    const top = ihMake(el, 'div', 'ih-pair');
    ihMake(top, 'h2', null, `${pair.a} × ${pair.b}`).setAttribute('data-i18n-skip', '');
    for (const [label, list, cur, param] of [['XX', pair.xx, pair.a, 'ih_xx'], ['XY', pair.xy, pair.b, 'ih_xy']]) {
      const pick = ihMake(top, 'div', 'ih-pick');
      ihMake(pick, 'span', null, label);
      const set = ihMake(pick, 'div', 'gx-profile-set');
      set.setAttribute('role', 'group'); set.setAttribute('aria-label', label);
      for (const p of list) {
        const b = ihMake(set, 'button', null, p.id);
        b.type = 'button'; b.setAttribute('aria-pressed', String(p.id === cur)); b.setAttribute('data-i18n-skip', '');
        b.addEventListener('click', () => dash.setParams({ [param]: p.id }));
      }
    }
    const meta = (ihRows('inh_meta', pair) || [])[0];
    if (!meta) { ihMake(el, 'p', 'ih-empty', `No inheritance results for ${pair.a} and ${pair.b} yet: python -m cluster_analysis.inheritance --pair ${pair.a} ${pair.b}`); return; }
    const cov = ihJ(meta.coverage, {});
    const counts = ihJ(meta.counts, {});
    const kpis = ihMake(el, 'div', 'ih-kpis');
    for (const [n, label] of [[counts.inh_conditions, 'genes where a parent carries a disease variant'],
      [counts.inh_traits, 'single-gene traits'], [counts.inh_drugs, 'drug genes with a type for the child'],
      [cov.both_read, 'disease positions read in both parents']]) {
      const k = ihMake(kpis, 'div', 'ih-kpi');
      ihMake(k, 'b', null, (n || 0).toLocaleString('en'));
      ihMake(k, 'span', null, label);
    }
    const modes = ihMake(el, 'div', 'ih-modes');
    for (const m of ['AR', 'AD', 'XLR']) { const p = ihMake(modes, 'p'); ihModeTag(p, m); p.append(IH_MODE_WHAT[m]); }
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
    ihMake(head, 'p', null, 'Each parent passes one of their two star alleles, so a child has one of four equally likely pairs; CPIC\'s rules turn each ' +
      'pair into a metaboliser type. Neither form is dominant: both alleles count, which is why one weaker allele gives an intermediate type.');
    if (!rows.length) { ihMake(el, 'p', 'ih-empty', 'No drug gene results for this pair: the Medicines step has to have run for both.'); return; }
    const tbl = ihMake(el, 'table', 'gx-table ih-drugs');
    const hr = ihMake(ihMake(tbl, 'thead'), 'tr');
    for (const h of ['Gene', pair.a, pair.b, 'A child']) ihMake(hr, 'th', null, h);
    const tb = ihMake(tbl, 'tbody');
    const tones = ['t-trait', 't-half', 't-carrier', 't-none'];
    for (const r of rows) {
      const tr = ihMake(tb, 'tr');
      ihMake(tr, 'td', null, r.gene).setAttribute('data-i18n-skip', '');
      for (const [al, ty] of [[r.XX_alleles, r.XX_type], [r.XY_alleles, r.XY_type]]) {
        const td = ihMake(tr, 'td');
        ihMake(td, 'span', 'ih-gt', al).setAttribute('data-i18n-skip', '');
        ihMake(td, 'div', 'ih-sub', ty);
      }
      const td = ihMake(tr, 'td');
      const types = ihJ(r.types, []);
      const bar = ihMake(td, 'div', 'ih-bar');
      types.forEach((t, i) => { const s = ihMake(bar, 'span', 'ih-seg ' + tones[i % tones.length]); s.style.width = (t.p * 100) + '%'; });
      const key = ihMake(td, 'div', 'ih-types');
      types.forEach((t, i) => {
        const k = ihMake(key, 'span');
        ihMake(k, 'i', tones[i % tones.length]).style.cssText = 'display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px';
        ihMake(k, 'span', null, t.type); k.append(` ${ihPct(t.p)}`);
      });
    }
  });
