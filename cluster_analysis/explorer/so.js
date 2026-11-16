  // Sources and glossary: the research databases behind the explorer and the terms its tabs use, from sources.json
  // (window.GX_SOURCES, put in by build.py with each bulk file's version from genome/references.json). Every text node
  // is one whole text, so the Swedish layer swaps it (the build adds sources.json's Swedish to the page's dictionary).
  const SO = window.GX_SOURCES || { databases: [], tools: [], glossary: [] };
  const soMake = (parent, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; parent.appendChild(e); return e; };
  const SO_TABS = { home: 'Home', clusters: 'Clusters', medicines: 'Medicines', nutrition: 'Nutrition', biomarkers: 'Biomarkers', lifecycle: 'Gene pathway', profile: 'Profile' };
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

  dash.draw('so-glossary', (el) => {
    el.replaceChildren();
    const head = soMake(el, 'div', 'so-head');
    soMake(head, 'h3', null, 'Glossary');
    const dl = soMake(el, 'dl', 'so-terms');
    for (const g of [...SO.glossary].sort((a, b) => a.term.localeCompare(b.term))) {
      const d = soMake(dl, 'div', 'so-term');
      soMake(d, 'dt', null, g.term);
      soMake(d, 'dd', null, g.text);
    }
  });
