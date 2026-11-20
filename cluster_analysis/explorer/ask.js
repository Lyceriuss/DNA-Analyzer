  // Ask: a conversation about the selected person's genome (cluster_analysis/agent/converse.py through the local server,
  // /api/agent/converse). Each turn: Claude's reading and plan first, then its tool calls as they run (public research,
  // the person's own results, views), the explanation with its sources, the readings for the person (picked on this
  // machine), the explorer's views it asked for (a cluster around a gene, a pathway, a medicine) and follow-ups.
  // A follow-up continues the same conversation. Without Claude connected there is no answer.
  (() => {
    const make = (p, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; p.appendChild(e); return e; };
    const fill = (tpl, ...v) => { let i = 0; return tpl.replace(/\{\}/g, () => String(v[i++])); };
    const api = async (path, body) => {
      const r = await fetch('/api/agent/' + path, body === undefined ? { cache: 'no-store' } : {
        method: 'POST', headers: { 'X-GX': '1', 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || fill('The server answered {}.', r.status));
      return j;
    };
    const fmtN = (n) => Number(n || 0).toLocaleString('en-US');
    // Tokens as billed: fresh input, cached input (a cache read costs a fraction of fresh input), output, and the
    // turn's cost on the API (on a Claude Code login it comes out of the plan instead). Older turns: in and out.
    const usd = (u) => (u && u.usd ? (u.usd < 0.01 ? fill('≈ ${}', u.usd.toFixed(4)) : fill('≈ ${}', u.usd.toFixed(3))) : '');
    // Ranks as people read them (the user's rule, 2026-11-20): Top is the favourable end, Bottom the unfavourable one.
    // Higher better: 95 -> Top 5%, 19 -> Bottom 19%. Higher worse (a risk): 3 -> Top 3%, 98 -> Bottom 2%.
    const ORD = (n) => { n = Math.round(n); const s = (n % 100 >= 11 && n % 100 <= 13) ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th'); return n + s; };
    const rankWords = (p, higher) => {
      p = Math.round(p);
      if (p > 40 && p < 60) return 'Normal';
      const high = p >= 60, share = high ? Math.max(100 - p, 1) : Math.max(p, 1);
      if (higher !== 'better' && higher !== 'worse') return fill(high ? 'Highest {}%' : 'Lowest {}%', share);
      return fill(high === (higher === 'better') ? 'Top {}%' : 'Bottom {}%', share);
    };
    const rankSide = (p, higher) => {
      if (p > 40 && p < 60) return fill('baseline ({})', ORD(p));
      if (higher === 'worse') return p <= 40 ? 'lowest genetic risk among Europeans' : 'highest genetic risk among Europeans';
      if (higher === 'better') return p >= 60 ? 'of Europeans, the favourable end' : 'of Europeans, the unfavourable end';
      return 'of Europeans';
    };
    const rankText = (s, higher) => (s || '').replace(/\b(?:at|near) the (\d{1,3})(?:st|nd|rd|th) percentile/g, (m, n) => 'in the ' + rankWords(+n, higher).toLowerCase())
      .replace(/\b(?:the )?(\d{1,3})(?:st|nd|rd|th) percentile/g, (m, n) => rankWords(+n, higher).toLowerCase());
    const tokLine = (u) => {
      u = u || {};
      if (u.cache_read == null) return fill('{} tokens in, {} out', fmtN(u.input), fmtN(u.output));
      const cached = (u.cache_read || 0) + (u.cache_write || 0);
      return [fill('{} new + {} cached tokens in, {} out', fmtN(u.input), fmtN(cached), fmtN(u.output)), usd(u)].filter(Boolean).join(' · ');
    };
    const EXAMPLES = ['What medicines should I watch out for?', 'What is my response to paracetamol?',
                      'Show me the cluster for ACTN3', 'What way of working out would suit me best?'];
    const STRIP = ['opentargets', 'gwas', 'pgs', 'clinvar', '1000g', 'clinpgx', 'cpic', 'chembl', 'uniprot', 'go', 'string',
                   'reactome', 'iarc', 'ecac', 'nnr', 'europepmc'];
    // The sources each tool draws on (the grid lights them up)
    const TOOL_SRC = {
      understand: ['claude'], answer: ['claude'], catalogue: ['opentargets'], resolve: ['opentargets'],
      gene: ['uniprot', 'gwas', 'clinvar'], variant: ['gwas', 'clinvar', '1000g', 'clinpgx'], cluster: ['go', 'opentargets', 'string'],
      trait_variants: ['gwas'], drug: ['clinpgx', 'cpic'], research_genotypes: ['europepmc', '1000g'], search_papers: ['europepmc'],
      read_paper: ['europepmc'], my_medicine: ['clinpgx', 'cpic', 'chembl'], my_medicines: ['clinpgx', 'cpic', 'chembl'],
      my_scores: ['pgs', 'gwas', 'iarc', 'ecac'], my_cluster: ['go', 'opentargets', 'string', 'reactome', 'europepmc'],
      my_gene: ['uniprot', 'reactome', 'gwas'], my_condition: ['gwas', 'clinvar', '1000g'],
      show_cluster: ['string', 'go'], show_pathway: ['reactome'], show_medicine: ['clinpgx'],
      pathway: ['reactome', 'uniprot'], nutrient: ['reactome', 'nnr'], my_nutrient: ['pgs', 'gwas', 'nnr'],
      show_nutrient: ['reactome'], recent_papers: ['europepmc'], show_papers: ['europepmc'],
    };
    const STEP = {
      understand: () => 'Read the question', catalogue: () => 'Looked at what the explorer holds',
      resolve: (i) => fill('Found what “{}” refers to', i.text), gene: (i) => fill('Gene {}: function, clusters, variants', i.symbol),
      variant: (i) => fill('Variant {}', i.rsid), cluster: (i) => fill('Cluster {}{}', i.theme, i.mechanism ? ' · ' + i.mechanism : ''),
      trait_variants: (i) => fill('GWAS traits for “{}”', i.trait), drug: (i) => fill('{}: guidelines and the effect of each genotype', i.name),
      research_genotypes: (i) => fill('Studies by genotype for {} ({})', (i.rsids || []).join(', '), i.topic),
      search_papers: (i) => fill('Searched papers: {}', i.query), read_paper: (i) => fill((i.find && i.find.length) ? 'Read PMID {} (full text)' : 'Read PMID {}', i.pmid),
      my_medicine: (i) => fill('Your results for {}', i.name), my_medicines: () => 'Your medicine results',
      my_scores: (i) => fill('Your {} scores', i.domain), my_cluster: (i) => fill('Your genes in {}{}', i.theme, i.mechanism ? ' · ' + i.mechanism : ''),
      my_gene: (i) => fill('Your {}', i.symbol), my_condition: (i) => fill('Your inherited risk for {}', i.name),
      show_cluster: (i) => fill('Drew the cluster around {}', i.gene || i.mechanism || i.theme), show_pathway: (i) => fill('Showed the {} pathway', i.gene),
      show_medicine: (i) => fill('Showed {}', i.name), answer: () => 'Wrote the explanation',
      pathway: (i) => fill('Built the {} pathway', i.gene), nutrient: (i) => fill('{}: tests and conversion steps', i.name),
      my_nutrient: (i) => fill('Your {} baseline and variants', i.name), show_nutrient: (i) => fill('Drew how {} is converted', i.name),
      recent_papers: (i) => fill('Latest research: {}{}', i.query, i.since_year ? ' (since ' + i.since_year + ')' : ''),
      show_papers: (i) => fill('Showed {} papers', (i.pmids || []).length),
      script: () => 'Wrote a script that runs the lookups and keeps what matters',
    };
    const KIND_TAG = { public: 'research', personal: 'yours', view: 'view', control: '' };
    const KIND_OF = { my_medicine: 'personal', my_medicines: 'personal', my_scores: 'personal', my_cluster: 'personal', my_gene: 'personal',
      my_condition: 'personal', my_nutrient: 'personal', show_cluster: 'view', show_pathway: 'view', show_medicine: 'view', show_nutrient: 'view',
      show_papers: 'view', understand: 'control', answer: 'control', script: 'control' };
    const S = { status: null, offline: false, draft: '', error: null, keyOpen: false, session: null, turns: [],
                live: null, running: false, job: null, lit: new Set(), used: new Set() };
    const redraw = () => dash.draw('ak-main');

    const loadStatus = async () => {
      try { S.status = await api('status'); S.offline = false; } catch (e) { S.status = null; S.offline = true; }
      redraw();
    };
    const ask = async (q) => {
      q = (q || S.draft).trim();
      if (!q || S.running) return;
      S.running = true; S.error = null; S.draft = ''; S.lit = new Set(); S.used = new Set();
      S.live = { question: q, understood: null, steps: [], usage: null, views: [] };
      redraw();
      try {
        const { job } = await api('converse', { question: q, person: gx.who(), session: S.session });
        S.job = job;
        let after = 0;
        for (;;) {
          const r = await api(`events?job=${job}&after=${after}`);
          for (const ev of r.events) {
            if (ev.type === 'start') S.session = ev.session;
            if (ev.type === 'understood') S.live.understood = ev;
            if (ev.type === 'tool') {
              S.live.steps.push({ name: ev.name, input: ev.input, kind: ev.kind, via: ev.via, ok: null });
              S.lit = new Set(TOOL_SRC[ev.name] || []); (TOOL_SRC[ev.name] || []).forEach((x) => S.used.add(x));
            }
            if (ev.type === 'tool_done') { const st = [...S.live.steps].reverse().find((x) => x.name === ev.name && x.ok === null); if (st) { st.ok = ev.ok; st.error = ev.error; } }
            if (ev.type === 'step' && ev.step === 'interpret') { S.live.writing = ev; S.lit = new Set(['claude']); S.used.add('claude'); }
            if (ev.type === 'usage') S.live.usage = ev;
            if (ev.type === 'error') S.error = ev.message;
          }
          after = r.next;
          if (r.done) { if (r.turn) S.turns.push(r.turn); break; }
          redraw();
          await new Promise((res) => setTimeout(res, 500));
        }
      } catch (e) { S.error = e.message; }
      S.running = false; S.live = null; S.lit = new Set();
      redraw();
    };
    const newConversation = () => { S.session = null; S.turns = []; S.error = null; S.used = new Set(); redraw(); };

    // --- the bar: the question (a follow-up once a conversation runs), and the AI connection in the corner
    const bar = (box, who) => {
      const top = make(box, 'div', 'ak-bar');
      const ta = make(top, 'textarea', 'ak-input ak-q');
      ta.rows = 1;
      ta.placeholder = S.turns.length ? 'Ask a follow-up…' : fill('Ask anything about {}\'s genome', who);
      ta.value = S.draft; ta.disabled = S.running;
      ta.addEventListener('input', () => { S.draft = ta.value; });
      ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); } });
      const b = make(top, 'button', 'ak-btn', S.running ? 'Working…' : S.turns.length ? 'Follow up' : 'Ask'); b.type = 'button'; b.disabled = S.running || !S.status.backend;
      b.addEventListener('click', () => ask());
      if (S.turns.length && !S.running) { const n = make(top, 'button', 'ak-btn ak-btn-quiet', 'New'); n.type = 'button'; n.title = 'Start a new conversation'; n.addEventListener('click', newConversation); }
      const m = S.status || {};
      const chip = make(top, 'button', 'gx-chip ak-ai', m.backend === 'api' ? 'AI: API key' : m.backend === 'claude-code' ? 'AI: Claude Code' : 'AI: not connected');
      chip.type = 'button'; chip.addEventListener('click', () => { S.keyOpen = !S.keyOpen; redraw(); });
      if (S.keyOpen || !m.backend) keyBox(box, m);
      if (!S.turns.length && !S.running && m.backend) {
        const ex = make(box, 'div', 'ak-row');
        for (const q of EXAMPLES) { const c = make(ex, 'button', 'gx-chip', q); c.type = 'button'; c.addEventListener('click', () => ask(c.textContent)); }
      }
    };
    const keyBox = (box, m) => {
      const k = make(box, 'div', 'ak-key');
      make(k, 'p', m.backend ? 'ak-off' : 'ak-err', m.backend ? 'Ask runs on your Claude plan through Claude Code; an Anthropic API key runs it on the API instead.'
        : 'Ask needs Claude: an Anthropic API key, or Claude Code installed and logged in. Without it there is no answer.');
      const row = make(k, 'div', 'ak-row');
      const inp = make(row, 'input', 'ak-input'); inp.type = 'password'; inp.placeholder = 'sk-ant-…'; inp.autocomplete = 'off'; inp.style.flex = '1 1 220px';
      const lab = make(row, 'label', 'ak-off'); const cb = make(lab, 'input'); cb.type = 'checkbox'; lab.appendChild(document.createTextNode(' Remember on this machine'));
      const b = make(row, 'button', 'ak-btn ak-btn-quiet', 'Save key'); b.type = 'button';
      b.addEventListener('click', async () => { try { await api('key', { key: inp.value.trim(), remember: cb.checked }); S.keyOpen = false; await loadStatus(); } catch (e) { S.error = e.message; redraw(); } });
      const sh = make(k, 'label', 'ak-off ak-share');
      const scb = make(sh, 'input'); scb.type = 'checkbox'; scb.checked = !!(m.settings || {}).share_results;
      sh.appendChild(document.createTextNode(' Share interpreted results with the model, so the summary can weave them together (the items a question touches: a gene\'s type, a score\'s band, the genotype a finding applies to; never the DNA file)'));
      scb.addEventListener('change', async () => { try { await api('settings', { share_results: scb.checked }); await loadStatus(); } catch (e) { S.error = e.message; redraw(); } });
    };
    const strip = (box) => {
      const dbs = new Map(((window.GX_SOURCES || {}).databases || []).map((d) => [d.id, d]));
      const s = make(box, 'div', 'ak-strip');
      make(s, 'span', 'ak-strip-head', S.running ? 'Reading now' : S.used.size ? 'Sources used' : 'Sources');
      for (const id of [...STRIP, 'claude']) {
        const d = dbs.get(id) || (id === 'claude' ? { name: 'Claude' } : null);
        if (!d) continue;
        const el = make(s, 'span', 'ak-src' + (S.lit.has(id) ? ' ak-src-on' : S.used.has(id) ? ' ak-src-used' : ''));
        el.title = d.name;
        const ic = make(el, 'span', 'ak-src-ic');
        if (d.logo) { const img = make(ic, 'img'); img.src = 'logos/' + d.logo; img.alt = ''; } else ic.textContent = d.name.slice(0, 2);
        make(el, 'span', 'ak-src-name', d.name.replace(/ \(.*\)$/, '').replace(/ Project$| Platform$| Recommendations 2023$/, ''));
      }
    };
    const go = (l) => { if (!l) return; dash.setParams(l.params || {}); gx.show(l.tab); };

    // --- one turn
    const readBox = (box, u, steps, live) => {
      const r = make(box, 'section', 'ak-read-q');
      const h = make(r, 'div', 'ak-read-head');
      make(h, 'span', 'ak-tag', 'How the question was read');
      if (!u) { make(r, 'p', 'ak-off', 'Claude is reading the question…'); }
      else {
        if (u.reading) make(r, 'p', 'ak-reading', u.reading);
        if (u.aim || (u.areas || []).length || (u.strategies || []).length) {
          const row = make(r, 'div', 'ak-chiprow');
          if (u.aim) make(row, 'span', 'ak-lvchip', fill('aim: {}', u.aim));
          for (const a of u.areas || []) make(row, 'span', 'ak-gene-chip ak-area', a);
          for (const s of u.strategies || []) make(row, 'span', 'ak-gene-chip ak-strat', s);
        }
        if ((u.plan || []).length) { const ol = make(r, 'ol', 'ak-plan'); for (const p of u.plan) make(ol, 'li', live ? null : 'ak-done', p); }
      }
      const done = steps.filter((s) => s.name !== 'understand' || s.ok === false);
      if (done.length) {
        const det = make(r, 'details', 'ak-trace');
        if (live) det.open = true;
        const bad = done.filter((s) => s.ok === false).length;
        make(det, 'summary', null, fill('Every step ({}){}', done.length, bad ? fill(' · {} sent back', bad) : ''));
        const ul = make(det, 'ul', 'ak-steps');
        for (const s of done) {
          const li = make(ul, 'li', 'ak-step ' + (s.ok === false ? 'ak-bad' : s.ok === null && live ? 'ak-live' : ''));
          make(li, 'span', 'ak-dot');
          const body = make(li, 'div', 'ak-step-body');
          const head = make(body, 'div', 'ak-step-head');
          if (KIND_TAG[s.kind || KIND_OF[s.name]]) make(head, 'span', 'ak-kind ak-kind-' + (s.kind || KIND_OF[s.name]), KIND_TAG[s.kind || KIND_OF[s.name]]);
          make(head, 'span', null, s.name === 'answer' && s.ok === false ? 'Draft answer sent back' : (STEP[s.name] || (() => s.name))(s.input || {}));
          if (s.via === 'script') make(head, 'span', 'ak-note', ' · in the script');
          if (s.note) make(body, 'span', 'ak-step-note', s.note);
          if (s.ok === false && s.error) make(body, 'span', 'ak-step-note ak-why', s.error);
        }
      }
    };
    // The explanation: paragraphs, bullets and **bold**, citations [PMID:123] as links to their source
    const prose = (box, text, refs) => {
      // A list written inline (": - **A** ... - B ...") becomes lines, so it reads as a list
      text = (text || '').replace(/(:|\.)\s+-\s+(?=\*\*|[A-Z(])/g, '$1\n- ').replace(/\s+-\s+(?=\*\*)/g, '\n- ');
      const blocks = text.split(/\n\s*\n/);
      for (const b of blocks) {
        const lines = b.split('\n').filter((l) => l.trim());
        if (!lines.length) continue;
        const isList = lines.length > 1 && lines.slice(1).every((l) => /^\s*[-*] /.test(l));
        if (isList && !/^\s*[-*] /.test(lines[0])) { const lead = make(box, 'p'); inline(lead, lines.shift(), refs); }
        const host = isList ? make(box, 'ul', 'ak-list') : null;
        for (const l of (isList ? lines : [lines.join(' ')])) {
          const el = isList ? make(host, 'li') : make(box, 'p');
          inline(el, l.replace(/^\s*[-*] /, ''), refs);
        }
      }
    };
    const inline = (el, text, refs) => {
      // Bold may hold a star allele (**CYP2C8 *3 ...**): matched lazily, not by excluding *
      const parts = text.split(/(\*\*.+?\*\*|\[(?:PMID|ClinPGx|GWAS|ClinVar|UniProt):[^\]\s]+\])/);
      for (const p of parts) {
        if (!p) continue;
        const bold = p.match(/^\*\*(.+?)\*\*$/);
        const cite = p.match(/^\[((?:PMID|ClinPGx|GWAS|ClinVar|UniProt):[^\]\s]+)\]$/);
        if (bold) make(el, 'b', null, bold[1]);
        else if (cite) {
          const r = (refs || {})[cite[1]];
          const a = make(el, r && r.url ? 'a' : 'span', 'ak-ref', '[' + cite[1].replace(':', ' ') + ']');
          if (r && r.url) { a.href = r.url; a.target = '_blank'; a.rel = 'noopener'; a.title = r.label; }
        } else el.appendChild(document.createTextNode(p));
      }
    };
    const clusterView = (box, v, who) => {
      const links = dash.data('theme_links'), genes = dash.data('theme_genes');
      const wrap = make(box, 'figure', 'ak-view');
      make(wrap, 'figcaption', 'ak-tag', fill('The {} cluster around {}', v.theme, v.gene || v.mechanism || ''));
      if (links.status !== 'ok' || genes.status !== 'ok') { make(wrap, 'p', 'ak-off', 'Loading the cluster…'); return; }
      const mine = new Map(genes.data.filter((g) => g.person === who && g.theme === v.theme).map((g) => [g.gene, g]));
      const L = links.data.filter((l) => l.theme === v.theme && (!l.person || l.person === who));
      const center = v.gene;
      let near = L.filter((l) => l.a === center || l.b === center).sort((a, b) => b.score - a.score).slice(0, 16);
      if (!near.length) { make(wrap, 'p', 'ak-off', fill('{} has no links in this cluster.', center || '')); return; }
      const ids = new Set([center, ...near.map((l) => (l.a === center ? l.b : l.a))]);
      const edges = L.filter((l) => ids.has(l.a) && ids.has(l.b)).map((l) => ({ source: l.a, target: l.b, w: l.score }));
      const nodes = [...ids].map((id) => ({ id, fn: (mine.get(id) || {}).function }));
      const W = 560, H = 330;
      const sim = d3.forceSimulation(nodes).force('link', d3.forceLink(edges).id((d) => d.id).distance(105).strength((e) => e.w * 0.4))
        .force('charge', d3.forceManyBody().strength(-420)).force('collide', d3.forceCollide(26)).force('center', d3.forceCenter(W / 2, H / 2)).stop();
      for (let i = 0; i < 220; i++) sim.tick();
      nodes.forEach((n) => { n.x = Math.max(30, Math.min(W - 30, n.x)); n.y = Math.max(18, Math.min(H - 18, n.y)); });
      const svg = d3.select(wrap).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('class', 'ak-graph').attr('role', 'img')
        .attr('aria-label', fill('Network of {} and its partners', center));
      svg.append('g').selectAll('line').data(edges).join('line').attr('x1', (e) => e.source.x).attr('y1', (e) => e.source.y)
        .attr('x2', (e) => e.target.x).attr('y2', (e) => e.target.y).attr('stroke', 'var(--color-border-line)').attr('stroke-width', (e) => 0.5 + e.w * 2);
      const col = (f) => (f === 'LoF' ? 'var(--color-bad)' : f === 'GoF' ? 'var(--color-warn)' : f === 'altered' ? 'var(--color-warn)' : 'var(--color-fg-muted)');
      const g = svg.append('g').selectAll('g').data(nodes).join('g').attr('transform', (n) => `translate(${n.x},${n.y})`);
      g.append('circle').attr('r', (n) => (n.id === center ? 11 : 7)).attr('fill', (n) => col(n.fn)).attr('stroke', (n) => (n.id === center ? 'var(--color-fg)' : 'none')).attr('stroke-width', 2);
      g.append('text').attr('y', (n) => (n.id === center ? -15 : -10)).attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', 'var(--color-fg)').text((n) => n.id);
      const key = make(wrap, 'p', 'ak-off', fill('Colour: your result for each gene. Red: less active, amber: more active or changed, grey: typical or not read. Lines: STRING interactions.'));
      const b = make(wrap, 'button', 'gx-chip', fill('Open the {} cluster', v.theme)); b.type = 'button';
      b.addEventListener('click', () => go({ tab: 'clusters', params: { theme: v.theme, th_gene: center } }));
    };
    // A pathway as a flow: each Reactome step in order, its inputs and outputs, built from the explorer's data or live
    const flow = (wrap, steps, chipsFor) => {
      const ol = make(wrap, 'ol', 'ak-flow');
      steps.forEach((s, i) => {
        const li = make(ol, 'li', 'ak-flow-step');
        make(li, 'span', 'ak-flow-n', String(i + 1));
        const body = make(li, 'div', 'ak-flow-body');
        make(body, 'b', null, s.name || '');
        const io = [(s.inputs || []).slice(0, 3).join(', '), (s.outputs || []).slice(0, 3).join(', ')];
        if (io[0] || io[1]) make(body, 'span', 'ak-flow-io', (io[0] || '…') + ' → ' + (io[1] || '…'));
        if (chipsFor) chipsFor(body, s);
      });
    };
    const pathwayView = (box, v, who) => {
      const wrap = make(box, 'figure', 'ak-view');
      make(wrap, 'figcaption', 'ak-tag', fill('The {} pathway · {} steps · {}', v.gene, (v.steps || []).length, v.source || 'Reactome'));
      if ((v.steps || []).length) flow(wrap, v.steps);
      else make(wrap, 'p', 'ak-off', 'Reactome maps no reactions for this gene.');
      const b = make(wrap, 'button', 'gx-chip', fill('Open {} in Gene pathway', v.gene)); b.type = 'button';
      b.addEventListener('click', () => go({ tab: 'lifecycle', params: { lc_gene: v.gene } }));
    };
    // A nutrient's uptake and conversion: each step with the genes acting there, the person's variant marked on each
    const nutrientView = (box, v, who) => {
      const wrap = make(box, 'figure', 'ak-view');
      make(wrap, 'figcaption', 'ak-tag', fill('How {} is taken up and converted · {} steps', v.nutrient.replace(/_/g, ' '), (v.steps || []).length));
      const nf = dash.data('nut_findings');
      const mine = new Map();
      if (nf.status === 'ok') for (const r of nf.data) if (r.person === who && r.nutrient === v.nutrient && !mine.has(r.step_gene || r.gene)) mine.set(r.step_gene || r.gene, r);
      flow(wrap, v.steps || [], (body, s) => {
        if (!(s.genes || []).length) return;
        const row = make(body, 'span', 'ak-flow-genes');
        for (const g of s.genes) {
          const r = mine.get(g);
          const c = make(row, 'span', 'ak-gchip' + (r ? ' ak-gchip-' + (r.direction === 'lowers' ? 'down' : 'up') : ''), g);
          if (r) { c.title = fill('{} {}: {} the blood level', r.rsid, r.genotype, r.direction); make(c, 'b', null, ' ' + r.genotype + (r.direction === 'lowers' ? ' ↓' : ' ↑')); }
        }
      });
      make(wrap, 'p', 'ak-off', fill('Marked: a gene where {}\'s variant raises (↑) or lowers (↓) the blood level, from the Nutrition module.', who));
      const b = make(wrap, 'button', 'gx-chip', 'Open in Nutrition'); b.type = 'button';
      b.addEventListener('click', () => go({ tab: 'nutrition', params: { nt_n: v.nutrient } }));
    };
    // A research digest: the papers, newest or strongest first, each with the sentences that carry its finding
    const papersView = (box, v) => {
      const wrap = make(box, 'figure', 'ak-view');
      make(wrap, 'figcaption', 'ak-tag', v.title || 'Research');
      const ul = make(wrap, 'ul', 'ak-papers');
      for (const p of v.items || []) {
        const li = make(ul, 'li');
        const h = make(li, 'div', 'ak-paper-head');
        if (p.type) make(h, 'span', 'ak-lvchip ak-type', p.type);
        make(h, 'span', 'ak-note', [p.date || '', p.journal || ''].filter(Boolean).join(' · '));
        const a = make(li, 'a', 'ak-paper-title', p.title || ('PMID ' + p.pmid)); a.href = 'https://europepmc.org/article/MED/' + p.pmid; a.target = '_blank'; a.rel = 'noopener';
        for (const s of (p.key || []).slice(0, 2)) make(li, 'blockquote', 'ak-quote', '“' + s + '”');
        const f = make(li, 'button', 'gx-chip', 'Ask about this study'); f.type = 'button';
        f.addEventListener('click', () => ask(fill('Tell me more about PMID {}: {}', p.pmid, p.title || '')));
      }
    };
    // The key figures: the answer's highlights (each tied to its source) and the person's own numbers (from their results)
    const tile = (g, a, h, who) => {
      const r = (a.refs || {})[h.source];
      const tl = make(g, 'div', 'ak-tile');
      make(tl, 'span', 'ak-tile-v' + (h.value.length > 16 ? ' ak-tile-v-long' : ''), h.value);
      make(tl, 'span', 'ak-tile-l', h.label);
      if (h.source === 'yours') tl.classList.add('ak-tile-you');
      const s = make(tl, r && r.url ? 'a' : 'span', 'ak-tile-s', h.source === 'yours' ? fill('{}\'s genes', who) : h.source.replace(':', ' '));
      if (r && r.url) { s.href = r.url; s.target = '_blank'; s.rel = 'noopener'; s.title = r.label; }
    };
    const SCORED = ['cancer', 'lab', 'nutrient', 'fitness', 'condition'];
    const tilesBox = (box, t, who) => {
      const a = t.answer || {};
      const hs = (a.highlights || []).filter((h) => h.source !== 'yours');
      if (!hs.length) return;
      const g = make(box, 'div', 'ak-tiles');
      for (const h of hs) tile(g, a, h, who);
    };
    // The person's scores: context, not the answer. Last, as Top/Bottom X%; folded away unless the question asked
    const scoresBox = (box, t, who) => {
      const a = t.answer || {};
      const nums = (t.cards || []).filter((c) => SCORED.includes(c.provider) && typeof c.value === 'number' && !String(c.id).includes(':variants'));
      const mine = (a.highlights || []).filter((h) => h.source === 'yours');
      const readings = (t.written || []).filter((x) => x.source === 'score');
      if (!nums.length && !mine.length && !readings.length) return;
      const host = make(box, t.ranks_asked ? 'section' : 'details', 'ak-scores');
      if (t.ranks_asked) make(host, 'span', 'ak-tag', fill('{}\'s genetic scores', who));
      else make(host, 'summary', null, fill('{}\'s genetic scores ({}) · context, not the answer', who, nums.length || readings.length));
      if (mine.length) { const g = make(host, 'div', 'ak-tiles'); for (const h of mine) tile(g, a, h, who); }
      const panels = make(host, 'div', 'fd-panels');
      for (const c of nums.slice(0, 8)) scorePanel(panels, c, who);
      if (readings.length) yoursBox(host, readings, who);
    };
    // One score as the explorer draws it in Female fertility: a scale from the unfavourable to the favourable end with
    // the person's dot, Top/Bottom X% (Normal in the middle, with the baseline percentile), and the variants behind it
    const VAR_RE = /^(.+?) \((rs\d+)\): (\d) of 2 copies of (\w+), which (raises|lowers) it/;
    const scorePanel = (parent, c, who) => {
      const higher = c.higher || (c.provider === 'condition' || c.provider === 'cancer' ? 'worse' : null);
      const p = c.value, worse = higher === 'worse', better = higher === 'better';
      const mid = p > 40 && p < 60, good = worse ? p <= 40 : better ? p >= 60 : null;
      const row = make(parent, 'div', 'fd-panel ak-score ak-score-' + (mid || good === null ? 'mid' : good ? 'good' : 'bad'));
      const head = make(row, 'div', 'ak-score-head');
      make(head, 'b', 'ak-score-v', rankWords(p, higher));
      make(head, 'span', null, c.title);
      make(row, 'span', 'ak-note', rankSide(p, higher));
      const scale = make(row, 'div', 'fd-scale' + (worse || better ? ' is-graded' : ''));
      const ends = make(scale, 'div', 'fd-scale-ends');
      make(ends, 'span', null, worse ? 'Higher risk' : 'Lower');
      make(ends, 'span', null, worse ? 'Lower risk' : 'Higher');
      const track = make(scale, 'div', 'fd-track');
      make(track, 'i', 'fd-mid');
      const dot = make(track, 'b', 'fd-dot'); dot.style.left = (worse ? 100 - p : p) + '%';
      dot.title = fill('{}: {}', who, rankWords(p, higher));
      // Why it sits there: the variants listed with the score, coloured by whether they push it the favourable way
      const vars = [];
      for (const r of c.rows || []) {
        const m = String(r.value || '').match(VAR_RE);
        if (m) { if (+m[3] > 0) vars.push({ gene: m[1].split(' - ')[0], rsid: m[2], txt: fill('{} ×{}', m[4], m[3]), good: better || worse ? (m[5] === 'raises') === better : null, raw: r.value }); continue; }
        const k = String(r.value || '').match(/^(\d) of 2 risk copies/);
        const g = String(r.label || '').match(/^(.+?) \((rs\d+)\)/);
        if (k && g && +k[1] > 0) vars.push({ gene: g[1].split(' - ').pop(), rsid: g[2], txt: fill('risk ×{}', k[1]), good: false, raw: r.label + ': ' + r.value });
      }
      if (vars.length) {
        const chips = make(row, 'div', 'fd-tops');
        for (const v of vars.slice(0, 6)) {
          const ch = make(chips, 'span', 'fd-top' + (v.good === true ? ' is-good' : v.good === false ? ' is-bad' : ''));
          make(ch, 'b', null, v.gene); make(ch, 'span', null, v.txt); ch.title = v.raw;
        }
      }
    };
    // The cluster areas the answer read: the person's changed genes in each mechanism, grouped, with their STRING links
    const areasView = (box, v, who) => {
      const links = dash.data('theme_links'), genes = dash.data('theme_genes');
      const wrap = make(box, 'figure', 'ak-view');
      make(wrap, 'figcaption', 'ak-tag', fill('{}\'s genes in the areas read · {} cluster', who, v.theme));
      if (links.status !== 'ok' || genes.status !== 'ok') { make(wrap, 'p', 'ak-off', 'Loading the cluster…'); return; }
      const ids = (v.mechanisms || []).map((m) => m.id);
      const name = new Map((v.mechanisms || []).map((m) => [m.id, m.name]));
      const changed = (g) => ['LoF', 'GoF', 'altered'].includes(g.function) || g.notable;
      const rows = genes.data.filter((g) => g.person === who && g.theme === v.theme && changed(g));
      const nodes = [], seen = new Set();
      for (const id of ids) {
        const inArea = rows.filter((g) => { try { return JSON.parse(g.facets || '[]').includes(id) || g.primary === id; } catch (e) { return g.primary === id; } })
          .sort((a, b) => (b.notable - a.notable) || ((b.best_score || 0) - (a.best_score || 0))).slice(0, 6);
        for (const g of inArea) if (!seen.has(g.gene)) { seen.add(g.gene); nodes.push({ id: g.gene, area: id, fn: g.function, notable: g.notable }); }
      }
      if (!nodes.length) { make(wrap, 'p', 'ak-off', fill('No changed genes of {}\'s in these areas.', who)); return; }
      const inSet = new Set(nodes.map((n) => n.id));
      const edges = links.data.filter((l) => l.theme === v.theme && (!l.person || l.person === who) && inSet.has(l.a) && inSet.has(l.b))
        .map((l) => ({ source: l.a, target: l.b, w: l.score }));
      const W = 620, H = 360, areas = [...new Set(nodes.map((n) => n.area))];
      const cols = Math.min(areas.length, 4), rowsN = Math.ceil(areas.length / cols);
      const center = new Map(areas.map((a, i) => [a, [W * ((i % cols) + 0.5) / cols, H * (Math.floor(i / cols) + 0.5) / rowsN]]));
      const sim = d3.forceSimulation(nodes).force('link', d3.forceLink(edges).id((d) => d.id).distance(60).strength(0.05))
        .force('charge', d3.forceManyBody().strength(-90)).force('collide', d3.forceCollide(24))
        .force('x', d3.forceX((n) => center.get(n.area)[0]).strength(0.35)).force('y', d3.forceY((n) => center.get(n.area)[1]).strength(0.35)).stop();
      for (let i = 0; i < 260; i++) sim.tick();
      nodes.forEach((n) => { n.x = Math.max(30, Math.min(W - 30, n.x)); n.y = Math.max(26, Math.min(H - 14, n.y)); });
      const svg = d3.select(wrap).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('class', 'ak-graph').attr('role', 'img')
        .attr('aria-label', fill('{}\'s changed genes in the areas read, grouped by mechanism', who));
      svg.append('g').selectAll('line').data(edges).join('line').attr('x1', (e) => e.source.x).attr('y1', (e) => e.source.y)
        .attr('x2', (e) => e.target.x).attr('y2', (e) => e.target.y).attr('stroke', 'var(--color-border-line)').attr('stroke-width', (e) => 0.5 + e.w * 1.5);
      for (const a of areas) {
        const pts = nodes.filter((n) => n.area === a), x = d3.mean(pts, (n) => n.x), y = d3.min(pts, (n) => n.y) - 20;
        svg.append('text').attr('x', x).attr('y', Math.max(12, y)).attr('text-anchor', 'middle').attr('class', 'ak-area-label').text(name.get(a) || a);
      }
      const col = (f) => (f === 'LoF' ? 'var(--color-bad)' : f === 'GoF' || f === 'altered' ? 'var(--color-warn)' : 'var(--color-fg-muted)');
      const g = svg.append('g').selectAll('g').data(nodes).join('g').attr('transform', (n) => `translate(${n.x},${n.y})`);
      g.append('circle').attr('r', (n) => (n.notable ? 9 : 6)).attr('fill', (n) => col(n.fn));
      g.append('text').attr('y', -11).attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', 'var(--color-fg)').text((n) => n.id);
      make(wrap, 'p', 'ak-off', fill('Red: less active, amber: more active or changed; larger: notable. Lines: STRING interactions. Up to six genes per area.'));
      const b = make(wrap, 'button', 'gx-chip', fill('Open the {} cluster', v.theme)); b.type = 'button';
      b.addEventListener('click', () => go({ tab: 'clusters', params: { theme: v.theme } }));
    };
    // How it ties together: each area or strategy, the person's genes behind it, the studies, and the finding
    const webBox = (box, t, who) => {
      const links = (t.answer || {}).links || [];
      if (!links.length) return;
      const refs = (t.answer || {}).refs || {};
      const wrap = make(box, 'figure', 'ak-view ak-web');
      make(wrap, 'figcaption', 'ak-tag', 'How it ties together');
      const nodes = links.map((l) => l.node);
      // At most three genes per link in the drawing (the list beneath names them all), so the columns stay readable
      const shown = (l) => l.genes.slice(0, 3);
      const genes = [...new Set(links.flatMap(shown))];
      const studies = [...new Set(links.flatMap((l) => l.refs))];
      const rows = Math.max(nodes.length, genes.length, studies.length, 1);
      const W = 640, H = rows * 30 + 16, X = [8, 300, 470];
      const y = (i, n) => 8 + (i + 0.5) * ((H - 16) / Math.max(n, 1));
      const pos = new Map();
      nodes.forEach((n, i) => pos.set('n:' + i, [X[0], y(i, nodes.length)]));
      genes.forEach((g, i) => pos.set('g:' + g, [X[1], y(i, genes.length)]));
      studies.forEach((s, i) => pos.set('s:' + s, [X[2], y(i, studies.length)]));
      const edges = [];
      links.forEach((l, i) => {
        if (l.genes.length) shown(l).forEach((g) => { edges.push(['n:' + i, 'g:' + g, false]); l.refs.forEach((s) => edges.push(['g:' + g, 's:' + s, false])); });
        else l.refs.forEach((s) => edges.push(['n:' + i, 's:' + s, true]));
      });
      const svg = d3.select(wrap).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('class', 'ak-graph').attr('role', 'img')
        .attr('aria-label', 'Areas and strategies, the genes behind them and the studies');
      const ex = (k, side) => pos.get(k)[0] + (side && k.startsWith('n:') ? 190 : side && k.startsWith('g:') ? 70 : 0);
      svg.append('g').selectAll('path').data(edges).join('path')
        .attr('d', ([a, b]) => { const x1 = ex(a, true), y1 = pos.get(a)[1], x2 = pos.get(b)[0] - 4, y2 = pos.get(b)[1]; const m = (x1 + x2) / 2; return `M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`; })
        .attr('fill', 'none').attr('stroke', 'var(--color-border-line)').attr('stroke-width', 1.5).attr('stroke-dasharray', (e) => (e[2] ? '4 3' : null));
      const label = (k, text, cls, url) => {
        const [x, yy] = pos.get(k);
        const g = svg.append(url ? 'a' : 'g');
        if (url) g.attr('href', url).attr('target', '_blank');
        g.append('text').attr('x', x).attr('y', yy + 4).attr('class', cls).text(text.length > 30 ? text.slice(0, 29) + '…' : text);
      };
      nodes.forEach((n, i) => label('n:' + i, n, 'ak-web-node' + (links[i].genes.length || links[i].refs.length ? '' : ' ak-web-empty')));
      const fnOf = (t.answer || {}).calls || {};
      genes.forEach((g) => label('g:' + g, g, 'ak-web-gene' + (fnOf[g] ? ' ak-fn-' + FN_CLASS[fnOf[g]] : '')));
      studies.forEach((s) => label('s:' + s, s.replace(':', ' '), 'ak-web-ref', (refs[s] || {}).url));
      const ul = make(wrap, 'ul', 'ak-list ak-web-list');
      for (const l of links) {
        const li = make(ul, 'li');
        make(li, 'b', null, l.node + ': ');
        li.appendChild(document.createTextNode(l.finding + ' '));
        if (l.genes.length) make(li, 'span', 'ak-note', fill('({})', l.genes.join(', ')));
      }
      make(wrap, 'p', 'ak-off', fill('Left: what the question needs covered. Middle: {}\'s genes behind it, coloured by {}\'s call (red less active, blue more active, green typical). Right: the studies. Dashed: no gene of {}\'s read for it.', who, who, who));
    };
    // For the person: one row per finding, with the gene and variants, their own genotype and the evidence level as
    // chips, the effect in a word or two, the source's sentence beneath, and an edge coloured by direction
    const DIR = { good: 'Favourable', bad: 'Worth attention', info: 'Good to know' };
    // What a genotype does to its gene, as the Clusters tab colours it: LoF red, GoF blue, typical green
    const FN_CLASS = { LoF: 'lof', GoF: 'gof', altered: 'alt', normal: 'norm', variant: 'var', unknown: 'unk' };
    const FN_SHORT = { LoF: 'LoF', GoF: 'GoF', altered: 'changed', normal: 'normal', variant: 'carrier', unknown: 'no call' };
    // The person's DNA at a glance: one headline card per key gene, the genotype large and glowing in its call's colour
    const HERO_WORD = { LoF: 'Less active', GoF: 'More active', normal: 'Typical', altered: 'Changed', variant: 'Carrier', unknown: 'No call' };
    const heroBox = (box, t, who) => {
      const hs = t.hero || [];
      if (!hs.length) return;
      const sec = make(box, 'section', 'ak-hero');
      make(sec, 'span', 'ak-tag', fill('{}\'s DNA at a glance', who));
      const row = make(sec, 'div', 'ak-hero-row');
      for (const h of hs) {
        const m = h.main || {}, fn = m.function || 'unknown';
        const c = make(row, 'div', 'ak-hero-card ak-fn-' + FN_CLASS[fn]);
        const top = make(c, 'div', 'ak-hero-top');
        make(top, 'span', 'ak-hero-gene', h.gene);
        if (m.variant) make(top, 'span', 'ak-hero-var', m.variant);
        make(c, 'b', 'ak-hero-gt', m.label || '?');
        make(c, 'span', 'ak-hero-call', HERO_WORD[fn]);
        if (m.text && m.text.toLowerCase() !== HERO_WORD[fn].toLowerCase()) make(c, 'span', 'ak-hero-text', m.text);
        c.title = [m.basis ? fill('Call: {} ({})', fn, m.basis) : null, m.evidence].filter(Boolean).join(' — ');
        if ((h.variants || []).length) {
          const more = make(c, 'div', 'ak-hero-more');
          for (const v of h.variants) genoBadge(more, v.genotype, v.variant, v);
        }
      }
    };
    const genoBadge = (parent, gt, variant, call) => {
      const fn = (call && call.function) || 'unknown';
      const b = make(parent, 'span', 'ak-geno ak-fn-' + FN_CLASS[fn]);
      make(b, 'b', null, gt || '?');
      make(b, 'span', 'ak-geno-fn', FN_SHORT[fn] + (call && call.text && call.text !== FN_SHORT[fn] ? ' · ' + call.text : ''));
      if (variant) make(b, 'span', 'ak-geno-v', variant);
      b.title = [call && call.basis ? fill('Call: {} ({})', fn, call.basis) : null, call && call.evidence].filter(Boolean).join(' — ');
    };
    const LEVEL = { '1A': 'guideline', '1B': 'guideline', '2A': 'moderate', '2B': 'moderate', '3': 'single studies', '4': 'case reports' };
    const yoursBox = (box, items, who) => {
      const fy = make(box, 'section', 'ak-yours');
      const head = make(fy, 'div', 'ak-yours-head');
      make(head, 'span', 'ak-tag', fill('For {}', who));
      const counts = { good: 0, bad: 0, info: 0 };
      items.forEach((x) => { counts[x.direction || 'info']++; });
      const legend = make(head, 'span', 'ak-fn-legend');
      for (const [fn, words] of [['LoF', 'less active'], ['GoF', 'more active'], ['normal', 'typical'], ['altered', 'changed'], ['variant', 'carrier, effect not measured']]) {
        const l = make(legend, 'span', 'ak-fn-key ak-fn-' + FN_CLASS[fn]); make(l, 'i'); l.appendChild(document.createTextNode(words));
      }
      const sum = make(head, 'span', 'ak-yours-sum');
      for (const k of ['bad', 'good', 'info']) if (counts[k]) { const c = make(sum, 'span', 'ak-dir ak-dir-' + k, fill('{} {}', counts[k], DIR[k].toLowerCase())); }
      const order = { bad: 0, good: 1, info: 2 };
      // The person's gene results (alleles and activity) first, then the findings, those worth attention first
      const rank = (x) => (x.source === 'CPIC guideline' ? 0 : 10) + (order[x.direction] ?? 2);
      for (const x of [...items].sort((a, b) => rank(a) - rank(b))) {
        const row = make(fy, 'div', 'ak-yrow ak-yrow-' + (x.direction || 'info'));
        const top = make(row, 'div', 'ak-yrow-top');
        if (x.gene) make(top, 'span', 'ak-gene-chip', x.gene.split(';')[0]);
        const vs = x.variants || [];
        const gts = x.genotypes || (x.genotype ? [x.genotype] : []);
        const calls = x.calls || [];
        if (vs.length) vs.forEach((v, j) => genoBadge(top, gts[j], v, calls[j] || calls[0]));
        else if (gts.length) genoBadge(top, gts[0], null, calls[0]);
        if (x.level) make(top, 'span', 'ak-lvchip', fill('level {} · {}', x.level, LEVEL[x.level] || ''));
        else if (x.source === 'study') make(top, 'span', 'ak-lvchip', [x.type, x.year].filter(Boolean).join(', '));
        else if (x.source) make(top, 'span', 'ak-lvchip', x.source);
        make(top, 'span', 'ak-dir ak-dir-' + (x.direction || 'info'), DIR[x.direction || 'info']);
        const main = x.effect ? x.effect[0].toUpperCase() + x.effect.slice(1) : x.takeaway;
        if (main) make(row, 'p', 'ak-yrow-main', main);
        const p = make(row, 'p', 'ak-yrow-text', x.reading + ' ');
        if (x.url) { const l = make(p, 'a', 'ak-ref', x.source === 'ClinPGx' ? 'ClinPGx' : 'study'); l.href = x.url; l.target = '_blank'; l.rel = 'noopener'; l.title = x.title || ''; }
        else if (x.link) { const l = make(p, 'button', 'ak-ref ak-ref-tab', x.link.label); l.type = 'button'; l.addEventListener('click', () => go(x.link)); }
      }
      const srcs = new Set(items.map((x) => x.source));
      make(fy, 'p', 'ak-meta', [srcs.has('ClinPGx') ? 'ClinPGx\'s own texts for your genotypes' : null,
        (srcs.has('guideline') || srcs.has('CPIC guideline') || srcs.has('score') || srcs.has('study')) ? 'readings written once for everyone by Claude' : null]
        .filter(Boolean).join(' · ') + fill(' · picked for {} on this machine', who));
    };
    // One turn, the same structure for every question: how it was read, the summary (the narrative), the key figures,
    // the person's results as the evidence, more detail, the views, and the sources it all rests on
    const turnBox = (box, t, who, i) => {
      const w = make(box, 'article', 'ak-turn');
      make(w, 'h3', 'ak-question', t.question);
      heroBox(w, t, who);
      readBox(w, t.understood, t.trace ? t.trace.map((c) => ({ ...c, input: c.args })) : (t.calls || []).map((c) => ({ ...c, input: c.args, ok: true })), false);
      const a = t.answer || {};
      if (a.summary) {
        const sm = make(w, 'section', 'ak-summary-box');
        make(sm, 'span', 'ak-tag', fill('Based on {}\'s DNA', who));
        prose(sm, a.summary, a.refs);
      } else if (!a.explanation) make(w, 'p', 'ak-err', 'No summary was written for this turn.');
      tilesBox(w, t, who);
      webBox(w, t, who);
      const findings = (t.written || []).filter((x) => x.source !== 'score');
      if (findings.length) yoursBox(w, findings, who);
      if (a.explanation) {
        const det = make(w, 'section', 'ak-explain');
        make(det, 'span', 'ak-tag', 'The evidence in more detail');
        prose(det, a.explanation, a.refs);
      }
      // The views side by side where the screen is wide enough
      const vw = (t.views || []).length ? make(w, 'div', 'ak-views') : null;
      for (const v of t.views || []) {
        if (v.view === 'cluster') clusterView(vw, v, who);
        else if (v.view === 'pathway') pathwayView(vw, v, who);
        else if (v.view === 'nutrient') nutrientView(vw, v, who);
        else if (v.view === 'papers') papersView(vw, v);
        else if (v.view === 'areas') areasView(vw, v, who);
        else if (v.view === 'medicine') { const b = make(vw, 'button', 'gx-chip', fill('Open {} in Medicines', v.drug)); b.type = 'button'; b.addEventListener('click', () => go({ tab: 'medicines', params: { md_drug: v.drug } })); }
      }
      scoresBox(w, t, who);
      // Sources: every ref the answer cites and every source behind the person's results, one list
      const refs = Object.entries(a.refs || {}).map(([id, r]) => ({ id, label: r.label, url: r.url }));
      for (const x of t.written || []) if (x.url && !refs.some((r) => r.url === x.url)) refs.push({ id: x.source || 'ClinPGx', label: x.title || x.gene, url: x.url });
      if (refs.length) {
        const src = make(w, 'section', 'ak-sources');
        make(src, 'span', 'ak-tag', fill('Sources ({})', refs.length));
        const ol = make(src, 'ol', 'ak-refs');
        for (const r of refs) {
          const li = make(ol, 'li');
          make(li, 'span', 'ak-lvchip', r.id.split(':')[0]);
          const x = make(li, r.url ? 'a' : 'span', null, ' ' + (r.label || r.id).replace(/^(PMID|ClinPGx|GWAS|Reactome|ClinVar|UniProt)[ :]\S*:\s*/, '').replace(/<[^>]+>/g, ''));
          if (r.url) { x.href = r.url; x.target = '_blank'; x.rel = 'noopener'; }
        }
      }
      if ((t.cards || []).length) {
        const det = make(w, 'details', 'ak-details'); make(det, 'summary', null, fill('{}\'s results behind it ({})', who, t.cards.length));
        const ul = make(det, 'ul', 'ak-list');
        for (const c of t.cards.slice(0, 14)) { const li = make(ul, 'li'); make(li, 'b', null, c.title + ': '); li.appendChild(document.createTextNode(rankText(c.headline, c.higher))); }
      }
      const tk = t.tokens || {}, wt = t.written_tokens || {};
      make(w, 'p', 'ak-meta', fill('{} · {} s · {}{} · {}', t.model || 'Claude', t.seconds, tokLine(tk),
        (wt.input || wt.output) ? fill(' · readings, written once for everyone: {}', tokLine(wt)) : '',
        t.shared ? 'interpreted results for these items were shared with the model; the DNA file stayed on this machine' : 'your genotypes stayed on this machine'));
      if (i === S.turns.length - 1 && !S.running && (a.followups || []).length) {
        const f = make(w, 'div', 'ak-row ak-follow');
        for (const q of a.followups) { const c = make(f, 'button', 'gx-chip', q); c.type = 'button'; c.addEventListener('click', () => ask(q)); }
      }
    };

    dash.draw('ak-main', (el) => {
      if (dash.data('profiles').status !== 'ok') return;
      const who = gx.who();
      el.replaceChildren();
      if (S.status === null && !S.offline) { make(el, 'p', 'ak-off', 'Connecting to the local server…'); loadStatus(); return; }
      if (S.offline) { make(el, 'p', 'ak-off', 'Asking needs the local server: start the explorer with python -m cluster_analysis.explorer serve and open http://127.0.0.1:8000.'); return; }
      const body = make(el, 'div', 'ak-body');
      const main = make(body, 'div', 'ak-col');
      strip(body);
      S.turns.forEach((t, i) => turnBox(main, t, who, i));
      if (S.live) {
        const w = make(main, 'article', 'ak-turn');
        make(w, 'h3', 'ak-question', S.live.question);
        readBox(w, S.live.understood, S.live.steps, true);
        const u = S.live.usage;
        make(w, 'p', 'ak-meta', S.live.writing ? 'Writing your readings…' : u ? fill('Working · {} so far', tokLine(u)) : 'Working…');
        const st = make(w, 'button', 'ak-btn ak-btn-quiet', 'Stop'); st.type = 'button'; st.addEventListener('click', () => api('stop', { job: S.job }).catch(() => {}));
      }
      if (S.error) make(main, 'p', 'ak-err', S.error);
      bar(main, who);
      if (!S.status.index) make(main, 'p', 'ak-off', 'The research index is not built yet: run python -m cluster_analysis.agent index once (a few minutes).');
    });

    // A link to a conversation: #ask=<session id> reopens it, to read or to follow up
    const m = location.hash.match(/^#ask=(\d{8}-\d{6}-[0-9a-f]{6})/);
    if (m) {
      gx.show('ask');
      api('session?id=' + m[1]).then((s) => { S.session = s.id; S.turns = s.turns.map((t, i) => ({ session: s.id, index: i, ...t })); redraw(); })
        .catch((e) => { S.error = e.message; redraw(); });
      try { history.replaceState(null, '', '#ask=' + m[1]); } catch (e) { /* no link */ }
    }
  })();
