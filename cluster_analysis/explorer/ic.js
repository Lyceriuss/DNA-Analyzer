  // Predicted vs actual: a child in the app against the forecast its parents' pair sealed before the child was added
  // (cluster_analysis/inheritance/forecast.py check, dataset inh_checks). The Inheritance tab's second view
  // (ih_view=compare), cloned from its first: the same scales, with the child's actual place marked on them.
  const icChecks = (pair) => {
    const d = dash.data('inh_checks');
    return d.status === 'ok' ? d.data.filter((r) => r.pair === pair.key).map((r) => ({ ...r, rep: ihJ(r.report, {}) })) : null;
  };
  const icView = () => (dash.params().ih_view === 'compare' ? 'compare' : 'predict');
  const icPick = (pair) => {
    const cs = icChecks(pair) || [];
    return cs.find((c) => c.child === dash.params().ih_child) || cs[0] || null;
  };
  const IC_Z80 = 1.2816, IC_Z98 = 2.3263;
  // Where the actual place fell: inside the 80 in 100 field, inside the 98, or outside both
  const icFit = (err) => Math.abs(err) <= IC_Z80 ? ['inside the 80% field', 'in80'] : Math.abs(err) <= IC_Z98 ? ['inside the 98% field', 'in98'] : ['outside both fields', 'out'];
  const icPct = (x, d = 1) => `${Math.round(x * 100 * 10 ** d) / 10 ** d}%`;
  const icWhen = (iso) => (iso || '').replace('T', ' at ').slice(0, 19);

  // The switch between the two views, and the page's state for the CSS that shows one or the other
  dash.draw('ih-views', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    const page = document.getElementById('inheritance');
    if (!pair || !pair.xx.length || !pair.xy.length) { if (page) page.dataset.view = 'predict'; return; }
    const checks = icChecks(pair) || [];
    const view = checks.length ? icView() : 'predict';
    if (page) page.dataset.view = view;
    if (!checks.length) return;
    const bar = ihMake(el, 'div', 'ic-views');
    const btn = (label, v, extra) => {
      const b = ihMake(bar, 'button', 'ic-view' + (view === v ? ' is-on' : ''), label);
      b.type = 'button';
      b.addEventListener('click', () => dash.setParams({ ih_view: v === 'predict' ? '' : v, ...(extra || {}) }));
    };
    btn('Prediction', 'predict');
    const P = dash.data('profiles');
    for (const c of checks) {
      const sex = ((P.data || []).find((p) => p.id === c.child) || {}).sex;
      btn(`Predicted vs actual: ${c.child}`, 'compare', { ih_child: c.child, ih_sex: sex === 'male' ? 'XY' : 'XX' });
    }
  });

  // The headline numbers: how well the sealed forecast did, from the most basic test up
  dash.draw('ic-summary', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || icView() !== 'compare') return;
    const c = icPick(pair);
    if (!c) return;
    const r = c.rep;
    const head = ihMake(el, 'div', 'ih-sec-head');
    ihMake(head, 'h3', null, `${c.child}: predicted vs actual`);
    const p = ihMake(head, 'p');
    p.append(`What the Inheritance tab predicted for a child of ${pair.a} and ${pair.b}, sealed on ${icWhen(r.made)}, before ${c.child} was added (${icWhen(r.child_added)}), set against ${c.child}'s own DNA. `);
    ihMake(p, 'span', 'ic-seal', `Seal ${String(r.sha256 || '').slice(0, 12)}…`).title = 'SHA-256 of the forecast: any change to it after it was sealed would show, and the check would refuse it';
    const grid = ihMake(el, 'div', 'ic-scores');
    const card = (big, text, sub, tone) => {
      const k = ihMake(grid, 'div', 'ic-score' + (tone ? ' ic-' + tone : ''));
      ihMake(k, 'span', 'ic-big', big);
      ihMake(k, 'b', null, text);
      if (sub) ihMake(k, 'span', 'ih-sub', sub);
    };
    const m = r.mendel || {}, meas = m['all measured'], imp = m['some imputed'];
    if (meas) card(icPct(1 - meas.error_rate, 2), 'of the measured genotypes are one copy from each parent',
      `${meas.impossible} of ${meas.variants.toLocaleString('en')} can't be: chip miscalls. With imputed calls: ${icPct(1 - (imp ? imp.error_rate : 0), 2)}.`, 'good');
    const v = r.variants || {};
    if (v.settled) card(icPct(v.settled_as_predicted, 2), `of the ${v.settled.toLocaleString('en')} certain variants came out as predicted`,
      'Where both parents carry two identical letters, the child\'s pair has no choice.', v.settled_as_predicted >= 0.999 ? 'good' : 'warn');
    const t = r.traits;
    if (t) {
      card(icPct(t.inside_80), 'of the traits landed inside the 80% field', 'Expected: 80%. More means the fields are a little wide.', Math.abs(t.inside_80 - 0.8) < 0.05 ? 'good' : 'warn');
      card(icPct(t.inside_98), 'inside the 98% field', 'Expected: 98%.', Math.abs(t.inside_98 - 0.98) < 0.02 ? 'good' : 'warn');
      card(String(t.correlation_predicted_actual_pct), `predicted against actual place, across ${t.compared.toLocaleString('en')} traits`, 'r: 1 would be a perfect prediction, 0 none at all. One child also draws her own coin tosses.', null);
    }
    if (v.bits_per_variant_over_frequencies != null) card(`${v.bits_per_variant_over_frequencies} bits`, 'of information per variant from the parents', 'Over knowing only how common each letter is among Europeans.', null);

    // The embedding: the child's whole trait vector against the predicted one, among simulated daughters and strangers
    const e = r.embedding;
    if (e && e.siblings) {
      const box = ihMake(el, 'div', 'ic-embed');
      const eh = ihMake(box, 'div', 'ih-legend-head');
      ihMake(eh, 'b', null, 'The whole picture at once');
      ihMake(eh, 'span', 'ih-sub', `Distance from the predicted child over ${e.traits.toLocaleString('en')} traits; shorter is closer`);
      const lo = 0.45, hi = 1.2, at = (x) => `${Math.max(0, Math.min(100, ((x - lo) / (hi - lo)) * 100))}%`;
      const ax = ihMake(box, 'div', 'ic-embed-axis');
      const band = (q, cls, label) => {
        const b = ihMake(ax, 'span', 'ic-band ' + cls);
        b.style.left = at(q[0]); b.style.width = `calc(${at(q[q.length - 1])} - ${at(q[0])})`;
        const mid = ihMake(ax, 'span', 'ic-band-mid ' + cls); mid.style.left = at(q[4]);
        const l = ihMake(ax, 'span', 'ic-band-label ' + cls, label); l.style.left = at((q[0] + q[q.length - 1]) / 2);
      };
      band(e.siblings.distance, 'ic-sib', `${e.sims} daughters of ${pair.a} and ${pair.b}, drawn by Mendel`);
      band(e.strangers.distance, 'ic-str', `${e.sims} random Europeans`);
      const dot = ihMake(ax, 'span', 'ic-dot'); dot.style.left = at(e.distance); dot.title = `${c.child}: ${e.distance}`;
      const dl = ihMake(ax, 'span', 'ic-dot-label', c.child); dl.style.left = at(e.distance);
      ihMake(box, 'p', 'ih-sub', `${c.child} is ${e.distance} from the prediction: among the simulated daughters (${e.siblings_closer_pct}% of them are closer) and closer than ${e.strangers_closer_pct === '<1' ? 'every' : 100 - e.strangers_closer_pct + '% of the'} simulated stranger${e.strangers_closer_pct === '<1' ? '' : 's'}. ` +
        'The simulated daughters have no call errors and a real file does, so a real child sits toward their far edge.');
    }
  });

  // The familiar traits: the predicted field and place, and where the child actually landed
  const icKey = (parent, pair, child) => {
    const k = ihMake(parent, 'div', 'ak-key-row ic-key');
    for (const [cls, label] of [['sw-xx', pair.a], ['sw-xy', pair.b], ['sw-dot', 'predicted, most likely'], ['sw-range', '80% field'], ['sw-range98', '98% field']]) {
      const it = ihMake(k, 'span', 'ak-key-item'); ihMake(it, 'span', 'ih-legend-swatch ' + cls); ihMake(it, 'span', null, label);
    }
    const it = ihMake(k, 'span', 'ak-key-item'); ihMake(it, 'span', 'ic-swatch-actual'); ihMake(it, 'b', null, `${child}, actual`);
  };
  const icMarkActual = (wrap, pct, child) => {
    const sc = wrap.querySelector('.ih-scale');
    if (!sc) return;
    const m = ihMake(sc, 'span', 'ih-mk ic-mk-actual');
    m.style.left = `${Math.max(0, Math.min(100, pct))}%`;
    m.title = `${child}, actual`;
  };
  const icFitTag = (parent, err) => { const [txt, cls] = icFit(err); return ihMake(parent, 'span', 'ic-fit ic-fit-' + cls, txt); };

  dash.draw('ic-featured', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || icView() !== 'compare') return;
    const c = icPick(pair);
    const preds = ihRows('inh_predictions', pair), meta = (ihRows('inh_meta', pair) || [])[0];
    if (!c || !preds || !meta || !c.rep.traits) return;
    const byPred = new Map(preds.map((r) => [r.id, r]));
    const byAct = new Map((c.rep.traits.rows || []).map((r) => [r.id, r]));
    const kid = ihSex() === 'XX' ? 'female' : 'male';
    const picks = ihJ(meta.featured, []).filter((f) => f.more && (!f.sex || f.sex === kid) && byPred.has(f.id) && byAct.has(f.id));
    if (!picks.length) return;
    const head = ihMake(el, 'div', 'ih-sec-head');
    ihMake(head, 'h3', null, 'Familiar traits');
    ihMake(head, 'p', null, `What the forecast said, and where ${c.child} actually landed.`);
    icKey(el, pair, c.child);
    const grid = ihMake(el, 'div', 'ih-feat');
    for (const f of picks) {
      const pr = byPred.get(f.id), a = byAct.get(f.id), dirs = [f.more, f.less];
      const card = ihMake(grid, 'div', 'ih-fcard ic-fcard');
      const top = ihMake(card, 'div', 'ih-fhead');
      ihMake(top, 'span', 'gx-label', f.name);
      const big = ihMake(top, 'div', 'ih-fbigrow');
      ihMake(big, 'h4', 'ih-fbig', ihBandOf(a.actual_pct)[0]);
      ihMake(big, 'span', 'ih-fdir', ihBandOf(a.actual_pct)[1] > 0 ? f.more : f.less);
      const wrap = ihScale(card, pr, pair, dirs);
      icMarkActual(wrap, a.actual_pct, c.child);
      const line = ihMake(card, 'p', 'ih-fpar');
      line.append(`Predicted: ${ihBand(a.predicted_pct, ...dirs)} · Actual: ${ihBand(a.actual_pct, ...dirs)} `);
      icFitTag(line, a.error_sd);
    }
  });

  // Every trait: sorted by the biggest miss first, so where the logic fails is on top
  let icShown = 40;
  dash.draw('ic-traits', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || icView() !== 'compare') return;
    const c = icPick(pair);
    const preds = ihRows('inh_predictions', pair);
    if (!c || !preds || !c.rep.traits) return;
    const byPred = new Map(preds.map((r) => [r.id, r]));
    const rows = c.rep.traits.rows || [];
    const prm = dash.params();
    const head = ihMake(el, 'div', 'ih-sec-head');
    ihMake(head, 'h3', null, `All ${rows.length.toLocaleString('en')} traits`);
    ihMake(head, 'p', null, 'Each trait\'s predicted field and place, and the actual place. The biggest misses first: they show where the prediction\'s logic fails.');
    const bar = ihMake(el, 'div', 'ih-search');
    const fit = ihMake(bar, 'select', 'md-select');
    for (const [k, l] of [['', 'All traits'], ['out80', 'Outside the 80% field'], ['out98', 'Outside the 98% field']]) { const o = ihMake(fit, 'option', null, l); o.value = k; o.selected = (prm.ic_fit || '') === k; }
    fit.addEventListener('change', () => { icShown = 40; dash.setParams({ ic_fit: fit.value }); });
    const q = ihMake(bar, 'input', 'md-search'); q.type = 'search'; q.placeholder = 'Search a trait'; q.value = prm.ic_q || '';
    let tm; q.addEventListener('input', () => { clearTimeout(tm); tm = setTimeout(() => { icShown = 40; dash.setParams({ ic_q: q.value }); }, 250); });
    const sel = ihMake(bar, 'select', 'md-select');
    for (const [k, l] of [['miss', 'Biggest miss first'], ['impact', 'Highest impact first'], ['name', 'A to Z']]) { const o = ihMake(sel, 'option', null, l); o.value = k; o.selected = (prm.ic_sort || 'miss') === k; }
    sel.addEventListener('change', () => dash.setParams({ ic_sort: sel.value }));
    const needle = (prm.ic_q || '').toLowerCase();
    let list = rows.filter((r) => (!needle || r.trait.toLowerCase().includes(needle)) &&
      (prm.ic_fit === 'out80' ? Math.abs(r.error_sd) > IC_Z80 : prm.ic_fit === 'out98' ? Math.abs(r.error_sd) > IC_Z98 : true));
    const sort = prm.ic_sort || 'miss';
    list = list.slice().sort(sort === 'name' ? (a, b) => a.trait.localeCompare(b.trait)
      : sort === 'impact' ? (a, b) => (b.impact || 0) - (a.impact || 0) : (a, b) => Math.abs(b.error_sd) - Math.abs(a.error_sd));
    ihMake(el, 'p', 'ih-sub', `${list.length.toLocaleString('en')} traits`);
    icKey(el, pair, c.child);
    const box = ihMake(el, 'div', 'ih-plist');
    for (const a of list.slice(0, icShown)) {
      const pr = byPred.get(a.id);
      const row = ihMake(box, 'div', 'ih-prow ic-row');
      const sum = ihMake(row, 'div', 'ic-sum');
      const name = ihMake(sum, 'span', 'ih-pname');
      ihMake(name, 'b', null, a.trait).setAttribute('data-i18n-skip', '');
      ihMake(name, 'span', 'ih-sub', a.category || '');
      const dirs = pr ? ihDirs(pr) : ['higher', 'lower'];
      const wrap = pr ? ihScale(sum, pr, pair) : ihMake(sum, 'span');
      icMarkActual(wrap, a.actual_pct, c.child);
      const num = ihMake(sum, 'span', 'ih-pnum');
      num.append(ihBand(a.actual_pct, ...dirs) + ' ');
      icFitTag(num, a.error_sd);
      ihImpactChip(num, a.impact);
      const err = ihMake(row, 'p', 'ih-sub ic-err');
      err.append(`Predicted ${ihBand(a.predicted_pct, ...dirs)}; off by ${Math.abs(a.error_sd).toFixed(2)} of the prediction's spreads ${a.error_sd > 0 ? 'upwards' : 'downwards'}.`);
    }
    if (list.length > icShown) {
      const b = ihMake(el, 'button', 'md-pill', `Show more (${(list.length - icShown).toLocaleString('en')} left)`);
      b.type = 'button';
      b.addEventListener('click', () => { icShown += 80; dash.setParams({ ic_more: String(icShown) }); });
    }
  });

  // The single-gene traits: the odds the forecast gave, and the outcome
  dash.draw('ic-single', (el) => {
    el.replaceChildren();
    const pair = ihPair();
    if (!pair || icView() !== 'compare') return;
    const c = icPick(pair);
    const sg = (c && c.rep.single_gene) || [];
    if (!sg.length) return;
    const head = ihMake(el, 'div', 'ih-sec-head');
    ihMake(head, 'h3', null, 'Single-gene traits');
    ihMake(head, 'p', null, `The odds the forecast gave each number of copies, and how many ${c.child} has.`);
    const box = ihMake(el, 'div', 'ic-single');
    for (const s of sg) {
      const row = ihMake(box, 'div', 'ic-srow');
      ihMake(row, 'b', null, s.trait);
      const bar = ihMake(row, 'div', 'ic-odds');
      s.predicted_odds.forEach((p, i) => {
        const seg = ihMake(bar, 'span', 'ic-oseg' + (i === s.copies ? ' is-actual' : ''), `${i} cop${i === 1 ? 'y' : 'ies'} · ${Math.round(p * 100)}%`);
        seg.style.flex = String(Math.max(p, 0.08));
      });
      ihMake(row, 'span', 'ih-sub', `${c.child}: ${s.copies} cop${s.copies === 1 ? 'y' : 'ies'}, given ${Math.round((s.odds_of_what_came || 0) * 100)}% odds`);
    }
  });
