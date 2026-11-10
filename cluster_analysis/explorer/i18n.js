  // Language: the page is written and drawn in English; with Swedish selected, a layer over the DOM swaps each text,
  // tooltip and placeholder for its Swedish version as it is drawn. The page's wording is explorer/i18n_sv.json (the
  // i18n_sv dataset, [{en, sv}] rows); the library's texts and disease/trait names are explorer/i18n_sv_terms.json (the
  // i18n_sv_terms dataset). Both load like the page's other data. Keys are the English text with {} for values that vary
  // ({0} {1} … in the Swedish to reorder them); a value is translated too when it is itself a key.
  // Other source text (gene names, UniProt, ClinPGx, Reactome, GO, papers) is left as published.
  const I18N = (() => {

    // After a count: Swedish adjectives agree in number ("1 mindre aktiv", "5 mindre aktiva")
    const COUNTED = {
      'mer aktiv': ['mer aktiv', 'mer aktiva'], 'mindre aktiv': ['mindre aktiv', 'mindre aktiva'],
      'mer uttryckt': ['mer uttryckt', 'mer uttryckta'], 'mindre uttryckt': ['mindre uttryckt', 'mindre uttryckta'],
      'förändrad, oklar riktning': ['förändrad, oklar riktning', 'förändrade, oklar riktning'],
      'typisk funktion': ['med typisk funktion', 'med typisk funktion'], 'ingen känd effekt på genen': ['utan känd effekt på genen', 'utan känd effekt på genen'],
      'troligen mindre aktiv': ['troligen mindre aktiv', 'troligen mindre aktiva'],
    };
    let exact = new Map(), pats = [], upper = new Map();
    const build = (dict) => {
      exact = new Map();
      pats = [];
      for (const [en, sv] of Object.entries(dict)) {
        if (!en.includes('{}')) { exact.set(en, sv); continue; }
        const parts = en.split('{}');
        // A generic separator ("{} · {}") translates its values only when they are keys themselves
        pats.push({ parts, sv, weight: parts.join('').length, generic: en === sv, need: parts.filter((x) => x.trim()) });
      }
      pats.sort((a, b) => b.weight - a.weight);  // the most specific template first
      // Labels drawn in capitals ("STARTS") use their key's translation
      upper = new Map([...exact].filter(([en]) => /[a-z]/.test(en)).map(([en, sv]) => [en.toUpperCase(), sv.toUpperCase()]));
      memo.clear();
    };
    // The values of a template in a text, scanning for each fixed part left to right (each value as short as it can be).
    // Linear in the text's length: a regex with several lazy groups can backtrack for minutes on a long paragraph.
    // A fixed part that occurs more than once gives other ways to split ("… (strongest: X) (gene expression, GTEx)" needs
    // the last " ("): up to 4 occurrences per part and 24 splits in all, the first split first.
    const balanced = (v) => {
      let d = 0;
      for (const c of v) { if (c === '(') d++; else if (c === ')' && --d < 0) return false; }
      return d === 0;
    };
    const match = (parts, t) => {
      const last = parts.length - 1;
      if (!t.startsWith(parts[0]) || !t.endsWith(parts[last]) || t.length < parts[0].length + parts[last].length) return [];
      const end = t.length - parts[last].length, out = [];
      const walk = (i, pos, caps) => {
        if (out.length >= 24) return;
        if (i === last) { if (end > pos) out.push([...caps, t.slice(pos, end)]); return; }
        if (!parts[i]) return;
        let j = t.indexOf(parts[i], pos + 1);
        for (let k = 0; j >= 0 && j < end && k < 4; k++, j = t.indexOf(parts[i], j + 1)) walk(i + 1, j + parts[i].length, [...caps, t.slice(pos, j)]);
      };
      walk(1, parts[0].length, []);
      return out;
    };
    // One piece of text: an exact key, else the most specific template. A template's values are translated too
    // (depth 1: exact, template or list), so "Less active ×2" and "{} carries {} trait-linked {}" read in Swedish.
    const one = (t, depth) => {
      const hit = exact.get(t) ?? upper.get(t);  // labels drawn in capitals ("STARTS") use their key's translation
      if (hit != null) return hit;
      // A count before a key ("5 less active"): before the templates, so Swedish agreement applies
      const n0 = t.match(/^([\d,.]+) (.+)$/);
      const k0 = n0 && exact.get(n0[2]);
      if (k0 != null) return n0[1] + ' ' + (COUNTED[k0] ? COUNTED[k0][n0[1] === '1' ? 0 : 1] : k0);
      for (const p of pats) {
        // Cheap checks first: every fixed part must occur, and the separator-only templates are kept to short labels
        if (p.generic && t.length > 160) continue;
        if (!p.need.every((x) => t.includes(x))) continue;
        let best = null, bestScore = -1;
        for (const m of match(p.parts, t)) {
          // A value never spans sentences: if it would, the text is several sentences and is translated one by one
          if (m.some((v) => /[.!?]\s+[A-Z0-9"]/.test(v))) continue;
          // ...nor half a bracket: "a (1), b (2)" is a list, not "{} ({})" with "1), b (2" inside
          if (m.some((v) => !balanced(v))) continue;
          // A separator-only template ("{} ({})") never spans the items of a "; " list either
          if (p.generic && m.some((v) => v.includes('; ') && !exact.has(v.trim()) && !exact.has(v.trim().replace(/\.$/, '')))) continue;
          let i = 0, score = 0;
          const out = p.sv.replace(/\{(\d*)\}/g, (_, n) => {
            const v = m[n === '' ? i++ : +n] ?? '';
            const done = depth > 0 ? value(v, p.generic ? 0 : depth - 1) : (exact.get(v.trim()) ?? v);
            if (done !== v) score++;
            return done;
          });
          if (out !== t && score > bestScore) { best = out; bestScore = score; }
          if (bestScore === m.length) break;
        }
        if (best != null) return best;
      }
      // "1 more active", "Typical function." : a count before a key, or a full stop after one
      const num = t.match(/^([\d,.]+) (.+)$/);
      if (num) {
        const r = exact.get(num[2]) ?? (depth > 0 ? one(num[2], depth - 1) : null);
        if (r != null) return num[1] + ' ' + (COUNTED[r] ? COUNTED[r][num[1] === '1' ? 0 : 1] : r);
      }
      if (/[A-Za-z)]\.$/.test(t)) { const r = exact.get(t.slice(0, -1)) ?? (depth > 0 ? one(t.slice(0, -1), depth - 1) : null); if (r != null) return r + '.'; }
      return null;
    };
    const list = (t, depth, all = false) => {
      for (const sep of ['; ', ', ']) {
        if (!t.includes(sep)) continue;
        // Keys can hold the separator themselves ("2 changed, direction unclear"): neighbours are joined back when together
        // they translate and apart one of them doesn't ("2 changed" is a key, "direction unclear" is not)
        const raw = t.split(sep), parts = [];
        for (let i = 0; i < raw.length; i++) {
          const both = i + 1 < raw.length ? raw[i] + sep + raw[i + 1] : null;
          if (both && (one(raw[i], 0) == null || one(raw[i + 1], 0) == null) && one(both, 0) != null) { parts.push(both); i++; } else parts.push(raw[i]);
        }
        const done = parts.map((x) => one(x, depth));
        if (all ? done.every((x) => x != null) : done.some((x) => x != null)) return parts.map((x, i) => done[i] ?? x).join(sep);
      }
      return null;
    };
    const value = (v, depth) => {
      const t = v.trim();
      if (!t) return v;
      // A list whose every item translates ("1 more active, 5 typical function") beats a template that would span items
      const o = (t.includes(', ') || t.includes('; ') ? list(t, depth, true) : null) ?? one(t, depth) ?? list(t, depth) ?? sentences(t, depth);
      return o == null ? v : v.replace(t, () => o);
    };
    // Several sentences drawn into one node: each is translated on its own
    // Several sentences drawn into one node: the longest run of up to three sentences that a key covers, then the next
    const sentences = (t, depth = 1) => {
      const parts = t.split(/(?<=[.!?])\s+(?=[A-Z0-9"(+·⚠])/);
      if (parts.length < 2) return null;
      const out = [];
      let changed = false;
      for (let i = 0; i < parts.length;) {
        let done = null, n = 1;
        for (let k = Math.min(3, parts.length - i); k >= 1 && done == null; k--) {
          done = one(parts.slice(i, i + k).join(' '), depth) ?? (k === 1 ? list(parts[i], depth) : null);
          n = k;
        }
        out.push(done ?? parts[i]);
        changed ||= done != null;
        i += done == null ? 1 : n;
      }
      return changed ? out.join(' ') : null;
    };
    const line = (s) => {
      const t = s.replace(/\s+/g, ' ').trim();
      if (!t || !/[A-Za-z]/.test(t)) return null;
      // A whole line that is a list translates only when every item does: half-Swedish source lists read worse
      const out = one(t, 1) ?? sentences(t) ?? list(t, 1, true);
      return out == null ? null : (/^\s/.test(s) ? ' ' : '') + out + (/\s$/.test(s) ? ' ' : '');
    };
    // Tooltips put one fact per line. Results are remembered: the same gene names and labels are drawn over and over.
    const memo = new Map();
    const tr = (text) => {
      let out = memo.get(text);
      if (out === undefined) {
        // A paragraph's own line breaks are layout; a tooltip's are one fact per line, so lines only when the whole fails
        out = line(text) ?? (text.trim().includes('\n') ? text.split('\n').map((l) => line(l) ?? l).join('\n') : text);
        if (memo.size > 50000) memo.clear();
        memo.set(text, out);
      }
      return out;
    };

    // English as drawn, kept per node, so switching back restores it and new drawing is picked up
    // Only the explorer's own markup (.gx): the dashboard's interface around it is React-drawn and watches its own text and
    // labels, so translating it would start a tug of war that freezes the page
    const root = () => document.querySelector('.gx');
    const EN = new WeakMap(), SHOWN = new WeakMap(), ATTRS = ['title', 'placeholder', 'aria-label'];
    let lang = 'en', observer = null;
    try { lang = localStorage.getItem('gx-lang') === 'sv' ? 'sv' : 'en'; } catch (e) { /* storage blocked: English */ }
    const skip = (el) => !el || el.nodeName === 'SCRIPT' || el.nodeName === 'STYLE' || (el.closest && el.closest('[data-i18n-skip]'));
    const doText = (n) => {
      if (skip(n.parentNode)) return;
      const cur = n.nodeValue;
      if (!(SHOWN.has(n) && SHOWN.get(n) === cur)) EN.set(n, cur);  // the page wrote new text
      const en = EN.get(n), want = lang === 'sv' ? tr(en) : en;
      if (cur !== want) n.nodeValue = want;
      SHOWN.set(n, want);
    };
    const doAttrs = (el) => {
      if (skip(el)) return;
      for (const a of ATTRS) {
        if (!el.hasAttribute(a)) continue;
        const key = 'i18n' + a.replace('-', ''), cur = el.getAttribute(a);
        if (el.dataset[key + 'Shown'] !== cur) el.dataset[key] = cur;
        const en = el.dataset[key], want = lang === 'sv' ? tr(en) : en;
        if (cur !== want) el.setAttribute(a, want);
        el.dataset[key + 'Shown'] = want;
      }
    };
    const walk = (root) => {
      if (!root.isConnected) return;  // drawn and replaced before the observer saw it
      if (root.nodeType === 3) { doText(root); return; }
      if (root.nodeType !== 1) return;
      doAttrs(root);
      const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
      let n;
      while ((n = w.nextNode())) n.nodeType === 3 ? doText(n) : doAttrs(n);
    };
    const watch = () => {
      if (observer) return;
      observer = new MutationObserver((records) => {
        for (const r of records) {
          if (!r.target.isConnected) continue;
          if (r.type === 'characterData') doText(r.target);
          else if (r.type === 'attributes') doAttrs(r.target);
          else r.addedNodes.forEach(walk);
        }
      });
      if (!root()) return;
      observer.observe(root(), { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    };
    const set = (l) => {
      lang = l === 'sv' ? 'sv' : 'en';
      try { localStorage.setItem('gx-lang', lang); } catch (e) { /* not saved */ }
      if (root()) root().lang = lang;
      document.querySelectorAll('.gx-lang button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.lang === lang)));
      if (root()) walk(root());
      if (lang === 'sv') watch();  // English needs no watching: new text is drawn in English
    };
    // The dictionaries arrive with the page's data, each on its own; text drawn before one arrives is translated then.
    // The page's wording (i18n_sv) wins over a source term (i18n_sv_terms) with the same English.
    const sets = {};
    const load = (name, rows) => {
      if (sets[name] || !rows || !rows.length) return;
      sets[name] = Object.fromEntries(rows.map((r) => [r.en, r.sv]));
      build(Object.assign({}, sets.i18n_sv_terms, sets.i18n_sv));
      if (lang === 'sv' && root()) walk(root());
    };
    return { set, tr, load, get lang() { return lang; } };
  })();

  document.querySelectorAll('.gx-lang button').forEach((b) => b.addEventListener('click', () => I18N.set(b.dataset.lang)));
  I18N.set(I18N.lang);
  if (typeof dash !== 'undefined') {
    dash.draw('i18n-load', () => { const r = gx.rows('i18n_sv'); if (r) I18N.load('i18n_sv', r[0]); });
    dash.draw('i18n-terms', () => { const r = gx.rows('i18n_sv_terms'); if (r) I18N.load('i18n_sv_terms', r[0]); });
  }
