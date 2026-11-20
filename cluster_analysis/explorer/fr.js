  // First run and results files (explorer/server.py: /api/setup, /api/results). Only with the local server: a page
  // opened from disk has no API and shows neither.
  (() => {
    const first = document.getElementById('gx-first'), steps = document.getElementById('fr-steps');
    const files = document.getElementById('gx-files');
    if (!first || !files) return;
    const make = (p, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; p.appendChild(e); return e; };
    const fill = (tpl, ...v) => { let i = 0; return tpl.replace(/\{\}/g, () => String(v[i++])); };
    const post = async (path, body, raw) => {
      const r = await fetch('/api/' + path, { method: 'POST', headers: { 'X-GX': '1', 'Content-Type': raw ? 'application/octet-stream' : 'application/json' },
                                             body: raw ? body : JSON.stringify(body || {}) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || fill('The server answered {}.', r.status));
      return j;
    };
    let setup = null, timer = null, message = null;

    // --- Opening a results file (made by this app on another computer, or kept as a backup)
    const openResults = () => {
      const input = document.createElement('input');
      input.type = 'file'; input.accept = '.gz';
      input.addEventListener('change', async () => {
        const f = input.files[0];
        if (!f) return;
        say(fill('Opening {}…', f.name));
        try {
          const r = await post('results/import', f, true);
          say(fill('{} was opened. The page reloads when the explorer has been rebuilt with them (a minute or two).', r.id));
          waitFor(r.id);
        } catch (e) { say(e.message, true); }
      });
      input.click();
    };
    const waitFor = (id) => {
      const t = setInterval(async () => {
        try {
          const p = await (await fetch('data/profiles.json', { cache: 'no-store' })).json();
          if (p.some((x) => x.id === id)) { clearInterval(t); try { localStorage.setItem('gx-person', id); } catch (e) { /* no storage */ } location.reload(); }
        } catch (e) { /* still rebuilding */ }
      }, 3000);
    };
    const say = (text, bad) => {
      if (!message) { message = make(files, 'span', 'fr-msg'); message.setAttribute('role', 'status'); }
      message.textContent = text;
      message.classList.toggle('is-bad', !!bad);
    };

    // --- The header's results buttons: save the selected person's results, open a results file
    const tools = () => {
      const keep = message;
      files.replaceChildren();
      const who = window.gx && gx.who();
      if (setup.profiles && who) {
        const a = make(files, 'a', 'fr-file', 'Save results');
        a.href = '/api/results?id=' + encodeURIComponent(who);
        a.title = fill('{}\'s results as one file, to keep or to open on another device. It holds genotypes: keep it private.', who);
      }
      const b = make(files, 'button', 'fr-file', 'Open results');
      b.type = 'button';
      b.title = 'A results file saved by this app';
      b.addEventListener('click', openResults);
      if (setup.update && setup.update.url) {
        const u = make(files, 'a', 'fr-file fr-update', fill('Version {} is out', setup.update.latest));
        u.href = setup.update.url; u.target = '_blank'; u.rel = 'noopener';
        u.title = fill('This is version {}. The new installer keeps the people and results already here.', setup.version);
      }
      if (keep) files.appendChild(keep);
    };

    // --- The welcome card, while no one has been added
    const card = () => {
      first.hidden = setup.profiles > 0;
      if (first.hidden) return;
      steps.replaceChildren();
      const step = (done, title) => {
        const li = make(steps, 'li', 'fr-step' + (done ? ' is-done' : ''));
        make(li, 'span', 'fr-mark', done ? '✓' : '').setAttribute('aria-hidden', 'true');
        const body = make(li, 'div');
        make(body, 'b', null, title);
        return body;
      };
      // 1. The knowledge bundle
      const k = setup.knowledge, job = setup.job || {};
      const s1 = step(!!k, 'Research data');
      if (k) make(s1, 'p', 'gx-note', fill('Release {} is installed: the public lookups the analysis needs, so it starts without asking the research sources one by one.', k.version));
      else if (job.state === 'running') {
        const pct = job.total ? Math.round(job.done / job.total * 100) : 0;
        make(s1, 'p', 'gx-note', job.total ? fill('Installing… {}%', pct) : 'Installing…');
        const bar = make(s1, 'div', 'fr-bar'); make(bar, 'i').style.width = pct + '%';
      } else if (setup.source) {
        make(s1, 'p', 'gx-note', setup.source === 'download'
          ? 'The public research data the analysis reads (UniProt, Ensembl, Reactome, Europe PMC and more), downloaded once.'
          : 'The public research data the analysis reads (UniProt, Ensembl, Reactome, Europe PMC and more), included with the app.');
        if (job.state === 'failed') make(s1, 'p', 'fr-bad', job.error);
        const go = make(s1, 'button', 'fr-go', job.state === 'failed' ? 'Try again' : 'Install');
        go.type = 'button';
        go.addEventListener('click', async () => { go.disabled = true; try { setup = await post('setup/knowledge'); } catch (e) { setup.job = { state: 'failed', error: e.message }; } render(); });
      } else make(s1, 'p', 'gx-note', 'Not installed: the first analysis looks each lookup up at the research sources, which can take hours.');
      // 2. The raw file
      const s2 = step(false, 'A raw DNA file');
      make(s2, 'p', 'gx-note', 'MyHeritage, AncestryDNA and 23andMe let their customers download their raw data from the DNA settings of their account: a .csv, .txt or .zip file. That file is what the app reads.');
      // 3. Add the person, or open results made elsewhere
      const s3 = step(false, 'Add a person');
      make(s3, 'p', 'gx-note', 'The file is read on this computer. With only the measured variants a result is ready in minutes.');
      const row = make(s3, 'div', 'fr-row');
      const add = make(row, 'button', 'fr-go', '+ Add a person'); add.type = 'button';
      add.disabled = !window.gxAdd;
      add.addEventListener('click', () => window.gxAdd && window.gxAdd.open());
      const open = make(row, 'button', 'fr-ghost', 'Open a results file'); open.type = 'button';
      open.addEventListener('click', openResults);
    };

    const render = () => {
      tools(); card();
      clearTimeout(timer);
      if (setup.job && setup.job.state === 'running') timer = setTimeout(refresh, 1000);
    };
    const refresh = async () => {
      try {
        const r = await fetch('/api/setup', { cache: 'no-store' });
        if (!r.ok) return;
        setup = await r.json();
      } catch (e) { return; }
      render();
    };
    refresh();
    // The selected person changes the save link
    const prof = document.querySelector('[data-draw="gx-profile"]');
    if (prof) new MutationObserver(() => setup && tools()).observe(prof, { childList: true, subtree: true, attributes: true });
  })();
