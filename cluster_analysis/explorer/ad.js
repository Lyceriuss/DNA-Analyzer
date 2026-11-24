  // Add a person: a raw DNA file in, imputed and analysed on this machine, out as a new profile (cluster_analysis/
  // pipeline.py, run by the local server's API in explorer/server.py). Shown only when the page is served by
  // `explorer serve`: a page opened from disk, or the old artifact, has no API and no button.
  (() => {
    const box = document.getElementById('gx-add');
    if (!box) return;
    const make = (p, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; p.appendChild(e); return e; };
    const fill = (tpl, ...v) => { let i = 0; return tpl.replace(/\{\}/g, () => String(v[i++])); };
    const api = async (path, body, raw) => {
      const r = await fetch('/api/' + path, body === undefined ? { cache: 'no-store' } : {
        method: 'POST', headers: { 'X-GX': '1', 'Content-Type': raw ? 'application/octet-stream' : 'application/json' },
        body: raw ? body : JSON.stringify(body),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || `The server answered ${r.status}.`);
      return j;
    };
    // Rough durations until this machine has its own (pipeline.py keeps the last five runs' per stage)
    const TYPICAL = { check: 15, register: 5, impute: 1900, analyse: 900, explorer: 200 };
    const STAGE_TEXT = { check: 'Checking the file', register: 'Adding the person', impute: 'Imputation',
                         analyse: 'Analysis', explorer: 'Loading into the explorer' };
    const STAGE_HELP = { impute: 'Beagle fills in the positions the test didn\'t measure from 3,202 reference genomes, after first measuring how accurate that is for this person.',
                         analyse: 'Themes, gene calls, medicines, nutrition, lab tests, fitness and cancer risk, read against the research databases.',
                         explorer: 'Every tab\'s data written, and the page rebuilt.' };
    const FORMAT = { myheritage: 'MyHeritage', ancestry: 'AncestryDNA', '23andme': '23andMe', imputed: 'Already imputed' };
    let state = { enabled: false, runs: [], typical: {}, busy: null }, dialog = null, view = 'pick', upload = null, timer = null, watching = null;
    const fmtN = (n) => Number(n).toLocaleString('en-US');
    const mins = (s) => (s < 90 ? fill('{} s', Math.max(1, Math.round(s))) : s < 5400 ? fill('{} min', Math.round(s / 60)) : fill('{} h {} min', Math.floor(s / 3600), Math.round((s % 3600) / 60)));
    const typ = (id) => state.typical[id] || TYPICAL[id];
    const remaining = (run) => {
      if (run.eta != null) return Math.max(0, run.eta - (Date.now() - (run._seen || Date.now())) / 1000);
      let s = 0;
      for (const st of run.stages) {
        if (st.state === 'done' || (st.id === 'impute' && run.lite)) continue;
        const t = typ(st.id), part = st.parts ? st.done_parts / st.parts.length : 0;
        if (st.state === 'running' && st.started) {
          const took = (Date.now() - new Date(st.started).getTime()) / 1000;
          s += part > 0.05 ? Math.max(0, took / part - took) : Math.max(t - took, t * 0.1);
        } else s += t;
      }
      return s;
    };
    const current = () => state.runs.find((r) => r.id === watching) || state.runs.find((r) => r.state === 'running') || null;
    // Whether the page shows anyone yet (explorer/server.py "shown"): until a first run finishes, it shows only the
    // first-run screen (fr.js), so the dialog doesn't promise a usable explorer meanwhile
    const usable = () => !state.shown || state.shown.length > 0;
    const meanwhile = (t) => (usable()
      ? fill('Takes about {}. The explorer stays usable meanwhile, and the run carries on if this window is closed.', t)
      : fill('Takes about {}. The explorer opens when it is done, and the run carries on if this window is closed.', t));

    // --- the header: a button, or the run's progress
    const header = () => {
      box.replaceChildren();
      if (!state.enabled) return;
      // The newest run not yet dismissed: running, ready to open, or stopped
      const run = state.runs.find((r) => r.state === 'running') || state.runs[0];
      if (run && run.state === 'running') {
        const b = make(box, 'button', 'gx-add-chip');
        b.type = 'button';
        make(b, 'span', 'gx-add-dot');
        make(b, 'span', null, fill('Adding {} · {}%', run.id, Math.floor(run.progress * 100)));
        const bar = make(b, 'span', 'gx-add-mini'); make(bar, 'i').style.width = `${run.progress * 100}%`;
        b.addEventListener('click', () => open('progress', run.id));
        return;
      }
      if (run && run.state === 'done') {
        const b = make(box, 'button', 'gx-add-chip gx-add-chip-ok', fill('{} is ready: open', run.id));
        b.type = 'button';
        b.addEventListener('click', () => open('progress', run.id));
      }
      if (run && (run.state === 'failed' || run.state === 'cancelled')) {
        const b = make(box, 'button', 'gx-add-chip gx-add-chip-bad', fill(run.state === 'failed' ? 'Adding {} stopped' : 'Adding {} was stopped', run.id));
        b.type = 'button';
        b.addEventListener('click', () => open('progress', run.id));
      }
      const add = make(box, 'button', 'gx-add-btn', '+ Add a person');
      add.type = 'button';
      add.addEventListener('click', () => open('pick'));
    };

    // --- the dialog
    const open = (v, id) => {
      view = v; if (id) watching = id;
      picked = null; drawn = '';
      if (!dialog) {
        dialog = make(document.querySelector('.gx') || document.body, 'dialog', 'gx-add-dialog');
        dialog.addEventListener('close', () => { if (view !== 'progress') { view = 'pick'; upload = null; } });
        dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });
      }
      render();
      if (!dialog.open) dialog.showModal();
      poll();
    };
    const head = (title, sub) => {
      const h = make(dialog, 'div', 'gx-add-head');
      const t = make(h, 'div');
      make(t, 'h2', null, title);
      if (sub) make(t, 'p', 'gx-note', sub);
      const x = make(h, 'button', 'gx-add-x', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Close');
      x.addEventListener('click', () => dialog.close());
    };
    const render = () => {
      if (!dialog) return;
      dialog.replaceChildren();
      dialog.classList.remove('is-wide');
      ({ pick, reading, review, progress }[view] || pick)();
    };

    const pick = () => {
      head('Add a person', 'From the raw data file of a DNA test: MyHeritage, AncestryDNA or 23andMe.');
      const drop = make(dialog, 'label', 'gx-add-drop');
      const input = make(drop, 'input'); input.type = 'file'; input.accept = '.csv,.txt,.tsv,.zip,.gz';
      make(drop, 'span', 'gx-add-drop-icon', '⇪').setAttribute('aria-hidden', 'true');
      make(drop, 'b', null, 'Drop the file here, or choose it');
      make(drop, 'span', 'gx-note', 'The .csv, .txt or .zip the test company lets you download');
      input.addEventListener('change', () => input.files[0] && send(input.files[0]));
      drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('is-over'); });
      drop.addEventListener('dragleave', () => drop.classList.remove('is-over'));
      drop.addEventListener('drop', (e) => { e.preventDefault(); drop.classList.remove('is-over'); if (e.dataTransfer.files[0]) send(e.dataTransfer.files[0]); });
      const how = make(dialog, 'ol', 'gx-add-how');
      for (const [b, t] of [['Read', 'The file is checked: its format, its calls and the sex its X chromosome shows.'],
                            ['Impute (optional)', 'The positions the test didn\'t measure can be filled in from reference genomes, about half an hour. Without it, the measured positions are used and a result is ready in minutes.'],
                            ['Analyse', 'Every tab is worked out for the person and they appear in the profile switcher.']]) {
        const li = make(how, 'li'); make(li, 'b', null, b); make(li, 'span', null, t);
      }
      make(dialog, 'p', 'gx-add-private', 'Everything happens on this computer. The file is copied into the project\'s data folder; only public identifiers such as rs numbers are looked up online, never genotypes.');
      if (state.busy) make(dialog, 'p', 'gx-add-warn', fill('{} is being added right now. One person at a time: the next can start when it is done.', state.busy));
    };

    const send = async (file) => {
      view = 'reading'; upload = { name: file.name, size: file.size }; render();
      try {
        const r = await api('upload?name=' + encodeURIComponent(file.name), file, true);
        upload = { ...upload, token: r.token, info: r.info, id: r.info.suggested_id || '', sex: r.info.sex || '' };
        view = 'review';
      } catch (e) {
        upload = { ...upload, error: e.message };
        view = 'review';
      }
      render();
    };

    const reading = () => {
      head('Add a person');
      const w = make(dialog, 'div', 'gx-add-reading');
      make(w, 'span', 'gx-add-spin').setAttribute('aria-hidden', 'true');
      make(w, 'b', null, fill('Reading {}', upload.name));
      make(w, 'span', 'gx-note', fill('{} MB: counting the calls and reading the X chromosome', (upload.size / 1e6).toFixed(1)));
    };

    // This computer as the imputation sees it, and the time each part of a run takes on it (pipeline.machine, plan)
    const machinePanel = (el) => {
      const m = state.machine, pl = state.plan;
      el.className = 'gx-add-machine';
      if (!m || !pl) { el.remove(); return; }
      const h = make(el, 'div', 'gx-add-mhead');
      make(h, 'b', null, 'This computer');
      make(h, 'span', 'gx-note', m.cpu).setAttribute('data-i18n-skip', '');
      const specs = make(el, 'div', 'gx-add-specs');
      const spec = (label, value) => { const d = make(specs, 'span'); make(d, 'i', null, label); make(d, 'b', null, value); };
      spec('Cores', fill('{} cores · {} threads', m.cores, m.threads));
      spec('Clock', fill('{} GHz', m.ghz));
      spec('Memory', fill('{} GB · {} GB free', Math.round(m.ram_gb), Math.round(m.ram_free_gb)));
      spec('Beagle gets', fill('{} threads · {} GB', m.beagle_threads, m.beagle_heap_gb));
      for (const [drive, d] of Object.entries(m.disks || {})) spec(fill('Disk {}', drive), fill('{} GB free', Math.round(d.free_gb)));
      const parts = [['Accuracy test', pl.validate, 'var(--color-fg-muted)'], ['Imputation', pl.beagle, 'var(--gof)'], ['Writing the calls', pl.write, 'color-mix(in srgb, var(--gof) 45%, var(--color-fg-muted))'],
                     ['Analysis', pl.analyse, 'color-mix(in srgb, var(--color-fg) 70%, transparent)'], ['Loading', pl.explorer + pl.check + pl.register, 'var(--color-fg)']];
      const all = parts.reduce((a, p) => a + p[1], 0) || 1;
      const bar = make(el, 'div', 'gx-add-stack gx-add-plan');
      for (const [t, sec, c] of parts) { const i = make(bar, 'i'); i.style.width = `${sec / all * 100}%`; i.style.background = c; i.title = `${t}: ${mins(sec)}`; }
      const lg = make(el, 'div', 'gx-add-legend');
      for (const [t, sec, c] of parts) { const i = make(lg, 'span'); make(i, 'i').style.background = c; make(i, 'span', null, t); make(i, 'b', null, mins(sec)); }
      make(el, 'p', 'gx-note', pl.basis === 'own'
        ? fill('From this computer\'s own runs ({}). Beagle\'s part scales with the cores it gets; the analysis mostly waits on the research sources\' servers.', pl.runs)
        : 'Scaled from a measured run (i7-7700K, 4 cores at 4.2 GHz): Beagle\'s part by the cores and clock it gets here, the reading and writing by the clock. The estimate corrects itself once the run is under way.');
      for (const w of m.warnings || []) make(el, 'p', 'gx-add-warn', w);
    };

    const review = () => {
      head('Add a person', upload.name);
      const info = upload.info || { problems: [upload.error] };
      const tiles = make(dialog, 'div', 'gx-add-tiles');
      const tile = (label, value, note) => { const t = make(tiles, 'div', 'gx-add-tile'); make(t, 'span', 'gx-label', label); make(t, 'b', null, value); if (note) make(t, 'span', 'gx-note', note); };
      if (info.format) {
        tile('Format', FORMAT[info.format] || info.format);
        tile('Calls', fmtN(info.called || 0), info.calls > info.called ? fill('{} without a call', fmtN(info.calls - info.called)) : null);
        tile('Sex from the DNA', info.sex ? (info.sex === 'female' ? 'Female' : 'Male') : 'Unknown',
             info.x_heterozygosity != null ? fill('X chromosome {}% mixed calls', (info.x_heterozygosity * 100).toFixed(1)) : null);
      }
      const hard = (info.problems || []).filter((p) => !/^No X chromosome/.test(p));
      for (const p of info.problems || []) make(dialog, 'p', hard.includes(p) ? 'gx-add-bad' : 'gx-add-warn', p);
      const form = make(dialog, 'div', 'gx-add-form');
      const nl = make(form, 'label', 'gx-add-field');
      make(nl, 'span', null, 'Name in the explorer');
      const name = make(nl, 'input'); name.value = upload.id || ''; name.maxLength = 32; name.spellcheck = false; name.autocomplete = 'off';
      make(nl, 'span', 'gx-note', 'Letters, digits, _ and -. Shown in the profile switcher; initials or a code keep it private.');
      // Sex is read from the X chromosome (pipeline.inspect); a choice only when the file has too few X calls to tell
      const sl = make(form, info.sex ? 'div' : 'label', 'gx-add-field');
      make(sl, 'span', null, 'Sex');
      let sex;
      if (info.sex) {
        sex = { value: info.sex, addEventListener() {} };
        make(sl, 'b', 'gx-add-fixed', info.sex === 'female' ? 'Female' : 'Male');
        make(sl, 'span', 'gx-note', fill('Read from the DNA: two X chromosomes show mixed calls, one doesn\'t ({}% here). Decides the fertility theme and the nutrient intake group.', (info.x_heterozygosity * 100).toFixed(1)));
      } else {
        sex = make(sl, 'select');
        for (const [v, t] of [['', 'Choose'], ['female', 'Female'], ['male', 'Male']]) { const o = make(sex, 'option', null, t); o.value = v; }
        sex.value = upload.sex || '';
        make(sl, 'span', 'gx-note', 'The file has too few X chromosome calls to read sex from. It decides the fertility theme and the nutrient intake group.');
      }
      // Lite (measured variants only) is the default; imputation only where this computer can run it
      const blocked = (state.imputation || {}).problems || [];
      if (upload.lite === undefined) upload.lite = true;
      const took = (lite) => mins((lite ? ['check', 'register', 'analyse', 'explorer'] : ['check', 'register', 'impute', 'analyse', 'explorer']).reduce((s, k) => s + typ(k), 0));
      const modes = make(dialog, 'div', 'gx-add-modes');
      modes.setAttribute('role', 'radiogroup');
      const machineBox = document.createElement('div');
      let note;
      const mode = (lite, title, text) => {
        const off = !lite && blocked.length;
        const b = make(modes, 'button', 'gx-add-mode' + (upload.lite === lite ? ' is-on' : ''));
        b.type = 'button'; b.disabled = !!off;
        b.setAttribute('role', 'radio'); b.setAttribute('aria-checked', String(upload.lite === lite));
        const h = make(b, 'span', 'gx-add-mode-head'); make(h, 'b', null, title); make(h, 'span', 'gx-add-mode-time', fill('about {}', took(lite)));
        make(b, 'span', 'gx-note', off ? blocked[0] : text);
        b.addEventListener('click', () => {
          upload.lite = lite;
          for (const o of modes.children) { const on = o === b; o.classList.toggle('is-on', on); o.setAttribute('aria-checked', String(on)); }
          machineBox.hidden = lite;
          note.textContent = meanwhile(took(lite));
        });
      };
      mode(true, 'Measured variants', 'The positions the test measured. Ready in minutes, on any computer.');
      mode(false, 'With imputation', 'Fills in the positions between them from 3,202 reference genomes, for fuller scores. Needs Java, the 14 GB reference panel and 8 GB or more of memory.');
      const err = make(dialog, 'p', 'gx-add-bad'); err.hidden = true;
      const foot = make(dialog, 'div', 'gx-add-foot');
      machinePanel(foot.parentNode.insertBefore(machineBox, foot));
      machineBox.hidden = upload.lite;
      note = make(foot, 'span', 'gx-note', meanwhile(took(upload.lite)));
      const back = make(foot, 'button', 'gx-add-ghost', 'Choose another file'); back.type = 'button';
      back.addEventListener('click', () => { view = 'pick'; upload = null; render(); });
      const go = make(foot, 'button', 'gx-add-go', 'Start'); go.type = 'button';
      const valid = () => {
        const id = name.value.trim(), taken = (state.profiles || []).includes(id);
        const ok = /^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$/.test(id) && !taken && sex.value && !hard.length && upload.token && !state.busy;
        go.disabled = !ok;
        err.hidden = !(id && (taken || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$/.test(id)));
        err.textContent = taken ? fill('There is already a profile named {}.', id) : 'A name can have letters, digits, _ and -, up to 32 characters.';
      };
      name.addEventListener('input', () => { upload.id = name.value; valid(); });
      sex.addEventListener('change', () => { upload.sex = sex.value; valid(); });
      valid();
      go.addEventListener('click', async () => {
        go.disabled = true;
        try {
          await api('start', { token: upload.token, id: name.value.trim(), sex: sex.value, lite: !!upload.lite });
          watching = name.value.trim(); upload = null; view = 'progress';
          await refresh(); render();
        } catch (e) { err.hidden = false; err.textContent = e.message; go.disabled = false; }
      });
      setTimeout(() => name.focus(), 0);
    };

    // --- the progress view: the stages on the left, on the right what the chosen stage found (the run's facts, read
    // by pipeline.py from the tools' own output), so the person sees the work being done, not only a bar
    const SVGNS = 'http://www.w3.org/2000/svg';
    const svg = (p, tag, attrs) => { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); p.appendChild(e); return e; };
    const CHR = Array.from({ length: 22 }, (_, i) => String(i + 1)).concat('X');
    const GENOME = 3.1e9;   // letters in one copy of the human genome (GRCh38, about 3.1 billion)
    const STEPS = [['themes', 'Health themes'], ['genes', 'Gene calls'], ['medicines', 'Medicines'],
                   ['nutrition', 'Nutrition'], ['labtests', 'Lab tests'], ['fitness', 'Fitness'], ['cancers', 'Cancer risk']];
    const SOURCES = ['ClinVar', 'GWAS Catalog', 'UniProt', 'GTEx', 'Ensembl VEP', 'Reactome', 'STRING', 'CPIC', 'DPWG', 'Drug labels',
                     'ClinPGx', '1000 Genomes', 'Europe PMC'];
    // Green on the right, as everywhere in the explorer
    const CALLS = [['LoF', 'Less active', 'var(--color-bad)'], ['altered', 'Changed', 'var(--color-fg)'], ['GoF', 'More active', 'var(--gof)'],
                   ['unknown', 'No known effect', 'var(--color-border-line)'], ['normal', 'Typical', 'var(--typical)']];
    const TIERS = [['untested', 'Untested', 'var(--color-fg-muted)'], ['low', 'Low', 'var(--color-warn)'],
                   ['medium', 'Medium', 'color-mix(in srgb, var(--color-ok) 55%, var(--color-warn))'], ['high', 'High', 'var(--color-ok)']];
    const total = (o) => Object.values(o || {}).reduce((s, v) => s + (Array.isArray(v) ? v[0] : v || 0), 0);
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let picked = null, metaNote = null, drawn = '';

    const tilesOf = (el, items) => {
      const tiles = make(el, 'div', 'gx-add-tiles');
      for (const [label, value, note] of items) { const t = make(tiles, 'div', 'gx-add-tile'); make(t, 'span', 'gx-label', label); make(t, 'b', null, value); if (note) make(t, 'span', 'gx-note', note); }
      return tiles;
    };
    // One column per chromosome: a (measured, dark) with b (filled in, blue) on top; the running one outlined
    const chromBars = (el, cols, label) => {
      const w = 24, H = 96, W = cols.length * w;
      const max = Math.max(1, ...cols.map((c) => (c.a || 0) + (c.b || 0)));
      const box = make(el, 'div', 'gx-add-chart');
      const s = svg(box, 'svg', { viewBox: `0 0 ${W} ${H + 16}`, role: 'img', 'aria-label': label });
      cols.forEach((c, i) => {
        const x = i * w + 3, bw = w - 6, ha = (c.a || 0) / max * H, hb = (c.b || 0) / max * H;
        svg(s, 'rect', { x, y: 0, width: bw, height: H, rx: 2, fill: 'var(--color-bg)' });
        if (hb) svg(s, 'rect', { x, y: H - ha - hb, width: bw, height: hb, rx: 2, fill: 'var(--gof)' });
        if (ha) svg(s, 'rect', { x, y: H - ha, width: bw, height: Math.max(ha, 1.5), rx: 1, fill: c.state === 'pending' ? 'var(--color-border-line)' : 'var(--color-fg-muted)' });
        if (c.state === 'running') { const r = svg(s, 'rect', { x: x - 1.5, y: 0, width: bw + 3, height: H, rx: 3, fill: 'none', stroke: 'var(--gof)', 'stroke-width': 2, class: 'gx-add-now' }); }
        const t = svg(s, 'text', { x: x + bw / 2, y: H + 12, 'text-anchor': 'middle', class: 'gx-add-ax' }); t.textContent = c.c;
        svg(svg(s, 'rect', { x: x - 3, y: 0, width: w, height: H + 16, fill: 'transparent' }), 'title', {}).textContent =
          `chr${c.c}: ${fmtN(c.a || 0)}${c.b ? ' + ' + fmtN(c.b) : ''}`;
      });
      return box;
    };
    const legend = (el, items) => {
      const l = make(el, 'div', 'gx-add-legend');
      for (const [text, color, n] of items) { const i = make(l, 'span'); make(i, 'i').style.background = color; make(i, 'span', null, text); if (n != null) make(i, 'b', null, fmtN(n)); }
    };
    const stack = (el, parts) => {
      const all = parts.reduce((s, p) => s + p[2], 0) || 1;
      const bar = make(el, 'div', 'gx-add-stack');
      for (const [, color, n] of parts) if (n) { const i = make(bar, 'i'); i.style.width = `${n / all * 100}%`; i.style.background = color; }
      legend(el, parts.map(([t, c, n]) => [t, c, n]));
    };
    // The idea of imputation in one picture (a drawing, not data): one row of the person's DNA with the chip's
    // positions dark, reference genomes below, a window sliding along them, and the gaps filling in blue
    const illustrate = (el, frac, running) => {
      const N = 50, cw = 11, W = N * cw;
      const box = make(el, 'figure', 'gx-add-illus');
      const s = svg(box, 'svg', { viewBox: `0 0 ${W} 96`, role: 'img', 'aria-label': 'Drawing: the chip\'s positions, reference genomes and the filled-in positions' });
      for (let r = 0; r < 4; r++) {
        let x = 0, k = r * 7 + 3;
        while (x < W) {
          const len = (k * 37 % 9 + 3) * cw;
          svg(s, 'rect', { x, y: 40 + r * 13, width: Math.min(len, W - x) - 1, height: 8, rx: 2, fill: 'var(--color-fg-muted)', opacity: [0.18, 0.32, 0.5, 0.24][(k + r) % 4] });
          x += len; k++;
        }
      }
      for (let i = 0; i < N; i++) {
        const chip = i % 10 === 4, filled = !chip && i / N < frac;
        svg(s, 'rect', { x: i * cw + 1, y: 6, width: cw - 2, height: 22, rx: 2,
                         fill: chip ? 'var(--color-fg)' : filled ? 'var(--gof)' : 'none', stroke: chip || filled ? 'none' : 'var(--color-border-line)' });
      }
      if (running && !reduced) {
        const win = svg(s, 'rect', { x: 0, y: 2, width: cw * 8, height: 92, rx: 4, fill: 'color-mix(in srgb, var(--gof) 10%, transparent)', stroke: 'var(--gof)', 'stroke-width': 1.5 });
        svg(win, 'animate', { attributeName: 'x', values: `0;${W - cw * 8};0`, dur: '9s', repeatCount: 'indefinite' });
      }
      const cap = make(box, 'figcaption');
      legend(cap, [['Measured by the chip', 'var(--color-fg)'], ['Filled in', 'var(--gof)'], ['Not yet known', 'transparent'], ['Reference genomes', 'color-mix(in srgb, var(--color-fg-muted) 40%, transparent)']]);
    };

    const STORY = {
      check(el, run, f) {
        make(el, 'h3', null, 'What the file holds');
        if (!f.called) { make(el, 'p', 'gx-note', 'Reading the file…'); return; }
        tilesOf(el, [['Positions measured', fmtN(f.called)], ['Format', FORMAT[f.format] || f.format],
                     ['Sex from the DNA', f.sex === 'female' ? 'Female' : f.sex === 'male' ? 'Male' : 'Unknown',
                      f.x_heterozygosity != null ? fill('X chromosome {}% mixed calls', (f.x_heterozygosity * 100).toFixed(1)) : null]]);
        make(el, 'h4', null, 'Positions per chromosome');
        chromBars(el, CHR.map((c) => ({ c, a: (f.chromosomes || {})[c] || 0, state: 'done' })), 'Measured positions per chromosome');
        make(el, 'p', 'gx-note', fill('A DNA test reads {} chosen positions out of the 3.1 billion letters in a genome: about one in {}. They are positions where people are known to differ.',
                                      fmtN(f.called), fmtN(Math.round(GENOME / f.called / 100) * 100)));
      },
      register(el, run) {
        make(el, 'h3', null, 'Adding the person');
        const st = run.stages.find((s) => s.id === 'register');
        make(el, 'p', null, st.state === 'done' ? fill('The file was copied to {} and {} was added to the profile list.', st.detail, run.id) : 'Copying the file into the project\'s data folder.');
      },
      impute(el, run, f, st) {
        if (run.lite || f.skipped) {
          make(el, 'h3', null, 'Measured variants only');
          make(el, 'p', 'gx-note', 'This person was added without imputation: every result is read from the positions the test measured. Scores built from many variants use the ones measured, so they can differ from an imputed run. Adding the person again with imputation fills in the rest.');
          return;
        }
        make(el, 'h3', null, 'Filling in the gaps');
        const frac = st.state === 'done' ? 1 : (st.done_parts || 0) / ((st.parts || []).length || 1);
        illustrate(el, frac, st.state === 'running');
        if (f.machine) make(el, 'p', 'gx-add-detail', fill('Beagle on {} threads and {} GB of memory · {}', f.machine.beagle_threads, f.machine.beagle_heap_gb, f.machine.cpu.replace(/\(R\)|\(TM\)|CPU /g, '').replace(/\s+/g, ' ')));
        make(el, 'p', 'gx-note', 'DNA is inherited in long stretches. Beagle lines up each stretch of the measured positions with 3,202 genomes the 1000 Genomes Project sequenced in full, finds the ones that share it, and reads the positions in between from them.');
        // 1. the self-test
        make(el, 'h4', null, '1. A test on itself first');
        const hidden = f.hidden || {};
        if (Object.keys(hidden).length) {
          const grid = make(el, 'div', 'gx-add-acc');
          for (const c of CHR) {
            const h = hidden[c], t = make(grid, 'span', h ? 'is-done' : 'is-pending');
            make(t, 'i', null, c);
            make(t, 'b', null, h ? (h[0] / h[1] * 100).toFixed(1) + '%' : '·');
          }
          const r = Object.values(hidden).reduce((s, v) => [s[0] + v[0], s[1] + v[1]], [0, 0]);
          make(el, 'p', 'gx-note', fill('Every tenth measured position was hidden and imputed back: {} of {} came back right ({}%). That rate gives each filled-in call its confidence.', fmtN(r[0]), fmtN(r[1]), (r[0] / r[1] * 100).toFixed(1)));
        } else if (st.state === 'running' && f.phase === 'sites') {
          make(el, 'p', 'gx-note', 'Matching the file\'s positions to the reference panel first (a few minutes).');
        } else make(el, 'p', 'gx-note', st.state === 'pending' ? 'Every tenth measured position will be hidden and imputed back, to measure how often imputation gets it right for this person.' : 'Measured in an earlier run.');
        // 2. the run itself
        make(el, 'h4', null, '2. Every chromosome filled in');
        const matched = f.matched || {}, kept = f.kept || {};
        const cur = f.current, ci = CHR.indexOf(cur);
        const measured = total(matched), filled = total(kept);
        if (Object.keys(matched).length) {
          const tk = make(el, 'div', 'gx-add-ticker');
          const a = make(tk, 'div'); make(a, 'b', null, fmtN(measured)); make(a, 'span', 'gx-note', 'measured and on the panel');
          make(tk, 'span', 'gx-add-arrow', '→');
          const b = make(tk, 'div', 'is-fill'); make(b, 'b', null, filled ? '+' + fmtN(filled) : '…'); make(b, 'span', 'gx-note', filled ? 'filled in' : 'being filled in');
          if (filled) { const m = make(tk, 'div'); make(m, 'b', null, fill('×{}', Math.round((measured + filled) / measured))); make(m, 'span', 'gx-note', 'as many known positions'); }
          const file = ((run.facts || {}).check || {}).chromosomes || {};
          chromBars(el, CHR.map((c, i) => ({ c, a: matched[c] ? matched[c][0] : file[c] || 0, b: kept[c] || 0,
                                             state: !matched[c] ? 'pending' : f.phase === 'impute' && i === ci ? 'running' : 'done' })),
                    'Measured and filled-in positions per chromosome');
          legend(el, [['Measured', 'var(--color-fg-muted)'], ['Filled in', 'var(--gof)']]);
          if (f.phase === 'write') make(el, 'p', 'gx-add-detail', 'Writing the imputed file with confidence tiers');
        } else make(el, 'p', 'gx-note', 'Beagle then imputes chromosome by chromosome, using all the measured positions.');
        // 3. how sure
        const tiers = f.tiers || {};
        if (tiers.high) {
          make(el, 'h4', null, '3. How sure each call is');
          stack(el, TIERS.map(([k, t, c]) => [t, c, (tiers[k] || [0])[0]]));
          if (tiers.not_excluded) {
            make(el, 'p', 'gx-note', fill('Beagle weighed {} positions in all. At {} of them a rare variant is most likely absent but can\'t be ruled out; those are kept only where ClinVar or ClinPGx list the variant.',
                                          fmtN(total(tiers)), fmtN(tiers.not_excluded[0])));
          }
        }
      },
      analyse(el, run, f, st) {
        make(el, 'h3', null, 'Reading the genome against the research');
        const used = new Set(STEPS.flatMap(([k]) => (f[k] || {}).sources || []));
        const chips = make(el, 'div', 'gx-add-sources');
        for (const n of SOURCES) make(chips, 'span', 'gx-add-src' + (used.has(n) ? ' is-on' : ''), n);
        make(el, 'p', 'gx-note', fill('{} of {} research sources consulted so far. Each lookup sends only public identifiers, such as rs numbers and gene names.', used.size, SOURCES.length));
        const ol = make(el, 'ol', 'gx-add-steps');
        const done = st.steps_done || [];
        for (const [k, label] of STEPS) {
          const s = f[k] || {}, state = done.includes(k) || st.state === 'done' ? 'done' : f.current === k && st.state === 'running' ? 'running' : 'pending';
          const li = make(ol, 'li', 'gx-add-step is-' + state);
          make(li, 'span', 'gx-add-icon', state === 'done' ? '✓' : '').setAttribute('aria-hidden', 'true');
          const d = make(li, 'div');
          make(d, 'b', null, label);
          if (state !== 'pending') stepFacts(d, k, s, run, state);
        }
      },
      explorer(el, run, f, st) {
        make(el, 'h3', null, 'Loading into the explorer');
        if (f.datasets) tilesOf(el, [['Datasets written', fmtN(f.datasets)], ['Rows', fmtN(f.rows)], ['Page', st.state === 'done' ? 'Rebuilt' : '…']]);
        make(el, 'p', 'gx-note', 'Every person\'s results are written as the explorer\'s datasets, and the page is rebuilt so the new person appears in the profile switcher.');
      },
      summary(el, run, F) {
        make(el, 'h3', null, fill('What was done for {}', run.id));
        const c = F.check || {}, im = F.impute || {}, an = F.analyse || {};
        const filled = im.kept ? total(im.kept) : 0;
        const findings = (an.themes?.themes || []).reduce((s, t) => s + (t.findings || 0), 0)
          + ['nutrition', 'labtests', 'fitness', 'cancers'].reduce((s, k) => s + ((an[k] || {}).findings || 0), 0);
        const flow = make(el, 'ol', 'gx-add-flow');
        for (const [label, n, note] of [['Measured by the chip', c.called, FORMAT[c.format] || c.format],
                                        ['Known after imputation', c.called && filled ? (im.matched ? total(im.matched) : c.called) + filled : null, '3,202 reference genomes'],
                                        ['Genes read', an.genes?.genes, an.genes?.calls ? fill('{} with a changed function', fmtN((an.genes.calls.LoF || 0) + (an.genes.calls.GoF || 0) + (an.genes.calls.altered || 0))) : null],
                                        ['Findings from the research', findings || null, null],
                                        ['Drug annotations', an.medicines?.annotations, an.medicines?.differs != null ? fill('{} guidelines where {} differs', an.medicines.differs, run.id) : null]]) {
          if (n == null) continue;
          const li = make(flow, 'li'); make(li, 'b', null, fmtN(n)); make(li, 'span', null, label); if (note) make(li, 'span', 'gx-note', note);
        }
        if (!flow.children.length) { flow.remove(); make(el, 'p', 'gx-note', 'This run was made before the dialog recorded what each stage found.'); return; }
        const used = new Set(STEPS.flatMap(([k]) => (an[k] || {}).sources || []));
        if (used.size) {
          make(el, 'h4', null, 'Sources consulted');
          const chips = make(el, 'div', 'gx-add-sources');
          for (const n of ['1000 Genomes'].concat(SOURCES.filter((s) => s !== '1000 Genomes'))) if (used.has(n) || n === '1000 Genomes') make(chips, 'span', 'gx-add-src is-on', n);
        }
        make(el, 'p', 'gx-note', 'Click a stage on the left to see what it found.');
      },
    };

    const stepFacts = (d, k, s, run, state) => {
      const note = (text) => make(d, 'span', 'gx-note', text);
      if (k === 'themes' && s.themes) {
        const t = s.themes, fd = t.reduce((a, x) => a + (x.findings || 0), 0), gn = t.reduce((a, x) => a + (x.genes || 0), 0);
        note(fill('{} findings in {} genes, across {} themes', fmtN(fd), fmtN(gn), t.length));
        const max = Math.max(1, ...t.map((x) => x.findings || 0));
        const bars = make(d, 'div', 'gx-add-hbars');
        for (const x of t) {
          make(bars, 'span', null, x.name);
          const b = make(bars, 'span', 'gx-add-hbar'); make(b, 'i').style.width = `${(x.findings || 0) / max * 100}%`;
          make(bars, 'b', null, x.findings != null ? fmtN(x.findings) : '…');
        }
      } else if (k === 'genes' && s.calls) {
        note(fill('{} genes read from {} variants', fmtN(s.genes), fmtN(s.variants || 0)));
        stack(d, CALLS.map(([key, t, c]) => [t, c, s.calls[key] || 0]));
      } else if (k === 'genes' && s.genes) {
        note(fill('Reading gene {} of {}', fmtN(s.read || 0), fmtN(s.genes)));
        const pb = make(d, 'span', 'gx-add-partbar'); make(pb, 'i').style.width = `${(s.read || 0) / s.genes * 100}%`;
      } else if (k === 'systems' && s.systems) {
        note(fill('{} changed genes in {} body systems, {} interacting pairs', fmtN(s.changed), s.systems, fmtN(s.pairs)));
      } else if (k === 'medicines' && s.annotations) {
        note(fill('{} drug genes typed, {} drug annotations; {} guidelines where {} differs from the usual', s.drug_genes, fmtN(s.annotations), s.differs, run.id));
        const g = make(d, 'div', 'gx-add-pgx');
        for (const [gene, dip, ph] of s.diplotypes || []) {
          const usual = /^Normal/.test(ph);
          const c = make(g, 'span', usual ? '' : 'is-diff'); make(c, 'b', null, gene); make(c, 'span', null, dip);
          c.title = ph; make(c, 'i', null, ph.replace(/\s*\(.*$/, ''));
        }
      } else if (['nutrition', 'labtests', 'fitness', 'cancers'].includes(k) && s.findings != null) {
        const what = { nutrition: ['{} variants read for {} nutrients: {} findings', s.nutrients], labtests: ['{} variants read for {} lab tests: {} findings', s.tests],
                       fitness: ['{} variants read for {} fitness measures: {} findings', s.tests], cancers: ['{} variants read for {} cancer types: {} findings', s.tests] }[k];
        note(fill(what[0], fmtN(s.variants || 0), what[1] || 0, fmtN(s.findings)));
        if (k === 'fitness' && s.sport_snps) note(fill('and {} sport variants', s.sport_snps));
      } else if (s.variants) {
        note(fill('Reading {} variants', fmtN(s.variants)));
      } else if (state === 'running') note((s.sources || []).length ? fill('Looking up {}', s.sources[s.sources.length - 1]) : 'Starting…');
      if (state === 'running' && (s.sources || []).length && k !== 'medicines') {
        const ch = make(d, 'div', 'gx-add-sources is-small');
        for (const n of s.sources) make(ch, 'span', 'gx-add-src is-on', n);
      }
    };

    const progress = () => {
      const run = current();
      dialog.classList.add('is-wide');
      if (!run) { head('Add a person'); make(dialog, 'p', 'gx-note', 'Starting…'); return; }
      const done = run.state === 'done', failed = run.state === 'failed' || run.state === 'cancelled';
      head(done ? fill('{} is ready', run.id) : failed ? fill('Adding {} stopped', run.id) : fill('Adding {}', run.id), run.source);
      const bar = make(dialog, 'div', 'gx-add-bar' + (failed ? ' is-bad' : done ? ' is-done' : ''));
      make(bar, 'i').style.width = `${(done ? 1 : run.progress) * 100}%`;
      const meta = make(dialog, 'div', 'gx-add-meta');
      make(meta, 'b', null, done ? '100%' : fill('{}%', Math.floor(run.progress * 100)));
      metaNote = make(meta, 'span', 'gx-note');
      timeText(run);
      const F = run.facts || {};
      const auto = done ? 'summary' : (run.stages.find((s) => s.state === 'running' || s.state === 'failed') || run.stages.find((s) => s.state === 'pending') || {}).id;
      const show = picked && (picked !== 'summary' || done) ? picked : auto;
      const body = make(dialog, 'div', 'gx-add-body');
      const list = make(body, 'ol', 'gx-add-stages');
      const item = (id, icon, cls, title, sub, help, part) => {
        const li = make(list, 'li', 'gx-add-stage ' + cls);
        const b = make(li, 'button', null); b.type = 'button';
        if (id === show) b.setAttribute('aria-current', 'true');
        b.addEventListener('click', () => { picked = id; drawn = ''; render(); });
        make(b, 'span', 'gx-add-icon', icon).setAttribute('aria-hidden', 'true');
        const t = make(b, 'div');
        make(t, 'b', null, title);
        if (sub) make(t, 'span', cls === 'is-running' ? 'gx-add-detail' : 'gx-note', sub);
        if (help) make(t, 'span', 'gx-note', help);
        if (part != null) { const pb = make(t, 'span', 'gx-add-partbar'); make(pb, 'i').style.width = `${part * 100}%`; }
      };
      for (const st of run.stages) {
        item(st.id, { done: '✓', running: '', failed: '✕', pending: '' }[st.state] ?? '', 'is-' + st.state, STAGE_TEXT[st.id] || st.label,
             st.state === 'running' ? st.detail : st.state === 'done' && st.detail && st.detail !== 'Done' ? st.detail : null,
             st.state === 'running' ? STAGE_HELP[st.id] : null, st.state === 'running' && st.parts ? st.done_parts / st.parts.length : null);
      }
      if (done) item('summary', '★', 'is-done is-sum', 'What was done', null, null, null);
      const story = make(body, 'section', 'gx-add-story');
      story.setAttribute('aria-live', 'polite');
      if (show === 'summary') STORY.summary(story, run, F);
      else if (STORY[show]) STORY[show](story, run, F[show] || {}, run.stages.find((s) => s.id === show));
      if (failed && run.error) {
        const e = make(dialog, 'div', 'gx-add-error');
        make(e, 'b', null, run.state === 'cancelled' ? 'Stopped on request.' : 'What went wrong');
        if (run.state !== 'cancelled') make(e, 'pre', null, run.error).setAttribute('data-i18n-skip', '');
        make(e, 'span', 'gx-note', fill('The full log is in data/output/pipeline/{}.log.', run.id));
      }
      const foot = make(dialog, 'div', 'gx-add-foot');
      if (done) {
        make(foot, 'span', 'gx-note', 'Every tab now has their results.');
        const go = make(foot, 'button', 'gx-add-go', fill('Open {}', run.id)); go.type = 'button';
        go.addEventListener('click', async () => {
          try { localStorage.setItem('gx-person', run.id); } catch (e) { /* the switcher picks it */ }
          try { await api('dismiss', { id: run.id }); } catch (e) { /* stays listed */ }
          location.hash = ''; location.reload();
        });
      } else if (failed) {
        abandonButton(foot, run);
        const again = make(foot, 'button', 'gx-add-go', 'Carry on from where it stopped'); again.type = 'button';
        again.disabled = !!state.busy;
        again.addEventListener('click', async () => { again.disabled = true; try { await api('resume', { id: run.id }); await refresh(); render(); } catch (e) { alert(e.message); again.disabled = false; } });
      } else {
        make(foot, 'span', 'gx-note', usable() ? 'You can close this window and keep using the explorer; the progress stays in the header.'
          : 'You can close this window; the progress stays in the header, and the explorer opens when the run is done.');
        abandonButton(foot, run);
        const stop = make(foot, 'button', 'gx-add-ghost', 'Pause'); stop.type = 'button';
        stop.addEventListener('click', async () => {
          if (!confirm(fill('Pause adding {}? It carries on later from the stage it reached.', run.id))) return;
          await api('cancel', { id: run.id }).catch(() => {}); await refresh(); render();
        });
        const hide = make(foot, 'button', 'gx-add-go', 'Keep it running in the background'); hide.type = 'button';
        hide.addEventListener('click', () => dialog.close());
      }
    };
    // Abandon: the run stops and everything it made goes (the copied file, the imputation, any results, the profile)
    const abandonButton = (foot, run) => {
      const b = make(foot, 'button', 'gx-add-ghost gx-add-abandon', 'Abandon'); b.type = 'button';
      b.addEventListener('click', async () => {
        if (!confirm(fill('Abandon adding {}? The run stops and everything it made is deleted: the copy of the file, the imputation and any results. The file you chose stays where it was.', run.id))) return;
        b.disabled = true;
        try { await api('abandon', { id: run.id }); watching = null; picked = null; await refresh(); view = 'pick'; render(); }
        catch (e) { alert(e.message); b.disabled = false; }
      });
    };
    const timeText = (run) => {
      if (!metaNote || !run) return;
      const done = run.state === 'done', failed = run.state === 'failed' || run.state === 'cancelled';
      const el = ((run.ended ? new Date(run.ended) : Date.now()) - new Date(run.started)) / 1000;
      metaNote.textContent = done ? fill('Took {}', mins(el)) : failed ? fill('Ran for {}', mins(el)) : fill('{} so far · about {} left', mins(el), mins(remaining(run)));
    };

    // A "+" at the end of the profile switcher opens the dialog too (the switcher is redrawn, so it is put back)
    const plus = () => {
      const set = document.querySelector('.gx-profile-set');
      if (!state.enabled || !set || set.querySelector('.gx-add-plus')) return;
      const b = make(set, 'button', 'gx-add-plus', '+'); b.type = 'button';
      b.title = 'Add a person'; b.setAttribute('aria-label', 'Add a person');
      b.addEventListener('click', () => open('pick'));
    };
    const prof = document.querySelector('.gx-profile');
    if (prof) new MutationObserver(plus).observe(prof, { childList: true });

    // --- polling: fast while something runs or the dialog is open, slow otherwise. The dialog is redrawn only when
    // the run changed (its pictures animate), the elapsed time every poll
    const refresh = async () => {
      try { state = await api('status'); } catch (e) { state = { enabled: false, runs: [] }; }
      for (const r of state.runs || []) r._seen = Date.now();
      header(); plus();
      // The first-run screen (fr.js) shows the run too
      document.dispatchEvent(new CustomEvent('gx-add-status', { detail: state }));
      if (dialog && dialog.open && view === 'progress') {
        const run = current(), key = JSON.stringify(run, (k, v) => (k === 'eta' || k === '_seen' ? undefined : v)) + picked;
        if (key !== drawn) { drawn = key; const top = dialog.scrollTop; render(); dialog.scrollTop = top; } else timeText(run);
      }
    };
    const poll = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => { await refresh(); poll(); }, state.busy || (dialog && dialog.open) ? 2000 : 20000);
    };
    // The first-run card (fr.js) opens the dialog too
    window.gxAdd = { open: () => open('pick'), progress: (id) => open('progress', id), state: () => state };
    refresh().then(() => { if (state.enabled) poll(); });
  })();
