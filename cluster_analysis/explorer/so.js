  // Sources and documentation: the research databases behind the explorer and what Ask can do, from sources.json
  // (window.GX_SOURCES, put in by build.py with each bulk file's version from genome/references.json). Every text node
  // is one whole text, so the Swedish layer swaps it (the build adds sources.json's Swedish to the page's dictionary).
  const SO = window.GX_SOURCES || { databases: [], tools: [], glossary: [] };
  const soMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const SO_TABS = { home: 'Home', clusters: 'Clusters', medicines: 'Medicines', nutrition: 'Clusters: Nutrition', biomarkers: 'Biomarkers', lifecycle: 'Gene pathway', inheritance: 'Inheritance' };
  const SO_ACCESS = { bulk: 'Downloaded file', 'bulk + API': 'Downloaded file and API', API: 'API, cached', 'API, saved': 'API, saved as a file' };
  let soQuery = '';

  const soFilter = (parent, placeholder, redraw) => {
    const f = soMake(parent, 'input', 'so-filter');
    f.type = 'search'; f.placeholder = placeholder; f.value = soQuery;
    f.addEventListener('input', () => { soQuery = f.value; redraw(); });
    return f;
  };
  const soHit = (...texts) => !soQuery || texts.some((t) => String(t || '').toLowerCase().includes(soQuery.toLowerCase()));

  dash.draw('so-dbs', (el) => {
    el.replaceChildren();
    const head = soMake(el, 'div', 'so-head');
    soMake(head, 'h3', null, `${SO.databases.length} research databases`);
    const grid = soMake(el, 'div', 'so-grid');
    const fill = () => {
      grid.replaceChildren();
      const rows = SO.databases.filter((d) => soHit(d.name, d.org, d.what, d.sv));
      if (!rows.length) soMake(grid, 'p', 'so-empty', 'No database matches.');
      for (const d of rows) {
        const c = soMake(grid, 'div', 'so-db');
        const h = soMake(c, 'h4');
        if (d.logo) { const img = soMake(h, 'img', 'so-logo'); img.src = 'logos/' + d.logo; img.alt = ''; img.loading = 'lazy'; }
        h.setAttribute('data-i18n-skip', '');  // a name: never translated ("Open Targets" isn't "Öppna Targets")
        const a = soMake(h, 'a', null, d.name);
        a.href = d.url; a.target = '_blank'; a.rel = 'noopener';
        soMake(c, 'div', 'so-org', d.org).setAttribute('data-i18n-skip', '');
        soMake(c, 'div', 'so-what', d.what);
        if (d.versions && d.versions.length) soMake(c, 'div', 'so-ver', d.versions.join(' · ')).setAttribute('data-i18n-skip', '');
        const m = soMake(c, 'div', 'so-meta');
        soMake(m, 'span', 'so-chip', SO_ACCESS[d.access] || d.access);
        for (const t of d.tabs || []) {
          const b = soMake(m, 'button', 'so-chip so-tab', SO_TABS[t] || t);
          b.type = 'button';
          b.addEventListener('click', () => gx.show(t));
        }
      }
    };
    soFilter(head, 'Search the databases', fill);
    fill();
    const tools = soMake(el, 'div', 'so-tools');
    soMake(tools, 'h3', null, 'Tools');
    for (const t of SO.tools) { const p = soMake(tools, 'p'); soMake(p, 'b', null, t.name); soMake(p, 'span', null, ': '); soMake(p, 'span', null, t.what); if (t.versions && t.versions.length) soMake(p, 'span', 'so-ver', ` (${t.versions.join(', ')})`); }
  });

  // What Ask can do: its tools from the registry (build.py agent_tools), each described here in plain words, grouped
  // by what the person gets: drawings in the answer, their own results, research it looks up. Plus what the Ask tab
  // draws from results on its own. tests/test_agent.py checks every tool has a description here.
  // Ask's tools and what the tab draws on its own: names, abbreviations and descriptions from ask_tools.json, kinds
  // from the tool registry (both through build.py). The abbreviation is each one's letter logo, here and in the Ask tab.
  const soLogo = (parent, abbr, kind) => {
    const l = soMake(parent, 'span', 'so-abbr so-abbr-' + (kind || 'drawn'), abbr);
    l.setAttribute('aria-hidden', 'true');
    return l;
  };
  dash.draw('so-ask', (el) => {
    el.replaceChildren();
    const head = soMake(el, 'div', 'so-head');
    soMake(head, 'h3', null, 'What Ask can show and look up');
    soMake(el, 'p', 'so-what', 'Ask answers through the AI model you connect, but only by calling the explorer\'s own tools: it can\'t draw or look up anything else. The drawings are made on this computer from your results; with Restricted mode on, the model never sees them.');
    const kinds = [['public', 'Looks up research'], ['personal', 'Reads your DNA'], ['view', 'Draws a view'], ['control', 'Steps of every answer']];
    const reg = SO.agent || [];
    const grid = soMake(el, 'div', 'so-ask-grid');
    for (const [kind, title] of kinds) {
      const list = reg.filter((t) => t.kind === kind);
      if (kind === 'view') list.push(...(SO.agent_drawn || []).map((d) => ({ ...d, auto: true })));
      if (!list.length) continue;
      const col = soMake(grid, 'div', 'so-ask-col');
      soMake(col, 'h4', null, title);
      const dl = soMake(col, 'dl', 'so-terms');
      for (const t of list) {
        const d = soMake(dl, 'div', 'so-term so-term-logo');
        soLogo(d, t.abbr, t.auto ? 'drawn' : t.kind);
        const txt = soMake(d, 'div');
        const dt = soMake(txt, 'dt');
        dt.append(t.label);
        soMake(dt, 'span', 'so-abbr-txt', ` · ${t.abbr}`);
        soMake(txt, 'dd', null, (t.what || '') + (t.auto ? ' (drawn by the Ask tab on its own)' : ''));
      }
    }
  });
