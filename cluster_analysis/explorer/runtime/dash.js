// Standalone runtime for the Gene Cluster Explorer: the part of claude.ai's Dashboard runtime the page uses, so the same
// page runs as a static site. The page only touches it through window.dash:
//   dash.draw(name, fn)    register a draw; fn(el) runs for every [data-draw=name] element outside a [hidden] section,
//                          again whenever data or params change. dash.draw(name) re-runs one draw now.
//   dash.data(id)          {status: 'loading' | 'ok' | 'error', data}: the dataset data/<id>.json, or a calc's result
//   dash.calc(id, spec)    a derived dataset: spec.fn(...inputs) once every input in spec.inputs is loaded
//   dash.params()          the shared params; dash.setParams(p) merges p and redraws
//   dash.setLink(tab)      the shareable location (#tab)
//   dash.colors            the categorical palette
// Data is fetched once per id on first use (or up front, from the page's data-source attributes) and kept for the visit,
// from data/<id>.json next to the page, or from window.DASH_DATA_URL (a function id -> URL) when a server provides it,
// e.g. window.DASH_DATA_URL = (id) => `/api/people/${person}/datasets/${id}`.
(() => {
  const DATA = new Map();   // id -> {status, data}
  const CALCS = new Map();  // id -> {spec, key, value}
  const DRAWS = new Map();  // name -> fn
  let params = {};
  let started = false, queued = false;

  const fetchData = (id) => {
    if (DATA.has(id) || CALCS.has(id)) return;
    DATA.set(id, { status: 'loading' });
    const url = window.DASH_DATA_URL ? window.DASH_DATA_URL(id) : `data/${encodeURIComponent(id)}.json`;
    fetch(url, { cache: 'no-cache', credentials: 'same-origin' })
      .then((r) => { if (!r.ok) throw new Error(`${id}: HTTP ${r.status}`); return r.json(); })
      .then((rows) => DATA.set(id, { status: 'ok', data: rows }))
      .catch((e) => { console.warn('dash: dataset', e.message); DATA.set(id, { status: 'error' }); })
      .finally(schedule);
  };

  const visible = (el) => !el.closest('[hidden]');

  const runDraw = (name) => {
    const fn = DRAWS.get(name);
    if (!fn) return;
    document.querySelectorAll(`[data-draw="${CSS.escape(name)}"]`).forEach((el) => {
      if (!visible(el)) return;
      try { fn(el); } catch (e) { console.error(`dash: draw ${name}`, e); }
    });
  };

  const runAll = () => { queued = false; for (const name of DRAWS.keys()) runDraw(name); };

  // Many datasets arrive at once on first load: one redraw per frame
  function schedule() {
    if (!started || queued) return;
    queued = true;
    requestAnimationFrame(runAll);
  }

  window.dash = {
    colors: ['#4e79a7', '#f28e2b', '#59a14f', '#b07aa1', '#e15759', '#76b7b2', '#edc948', '#9c755f'],

    data(id) {
      const c = CALCS.get(id);
      if (c) {
        const ins = c.spec.inputs.map((i) => this.data(i));
        if (ins.some((d) => d.status === 'error')) return { status: 'error' };
        if (!ins.every((d) => d.status === 'ok')) return { status: 'loading' };
        // Recompute only when an input's rows changed (rows are replaced, never mutated)
        if (!c.inputs || c.inputs.some((d, i) => d !== ins[i].data)) {
          c.inputs = ins.map((d) => d.data);
          try { c.value = { status: 'ok', data: c.spec.fn(...c.inputs) }; }
          catch (e) { console.error(`dash: calc ${id}`, e); c.value = { status: 'error' }; }
        }
        return c.value;
      }
      if (!DATA.has(id)) fetchData(id);
      return DATA.get(id);
    },

    calc(id, spec) { CALCS.set(id, { spec }); },

    draw(name, fn) {
      if (fn) { DRAWS.set(name, fn); if (started) runDraw(name); return; }
      runDraw(name);
    },

    params() { return params; },

    setParams(p) {
      params = { ...params, ...p };
      for (const k of Object.keys(p)) if (p[k] === null || p[k] === undefined) delete params[k];
      schedule();
    },

    setLink(tab) {
      try { history.replaceState(null, '', `#${tab}`); } catch (e) { /* file:// or sandboxed: no link */ }
    },

    refresh() { schedule(); },

    // Called once the page's own scripts have registered their draws
    start() {
      started = true;
      // Fetch every dataset the page names up front, in parallel
      const ids = new Set();
      document.querySelectorAll('[data-source]').forEach((el) => el.dataset.source.split(/\s+/).forEach((id) => id && ids.add(id)));
      ids.forEach((id) => { if (!CALCS.has(id)) fetchData(id); });
      // A tab section shown or hidden: draw what became visible
      new MutationObserver((ms) => { if (ms.some((m) => m.target.classList && m.target.classList.contains('gx-page'))) schedule(); })
        .observe(document.body, { subtree: true, attributes: true, attributeFilter: ['hidden'] });
      schedule();
    },
  };
})();
