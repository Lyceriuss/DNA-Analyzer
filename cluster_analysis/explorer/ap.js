  // The app itself (explorer/server.py Lifetime, /api/delete, /api/delete-all, /api/quit): an App menu in the header to
  // delete a person, delete everything or quit, and the window's check-ins that let the desktop app stop by itself
  // once no window is open. Only with the local server: a page opened from disk has no API and shows none of it.
  (() => {
    const box = document.getElementById('gx-app');
    if (!box) return;
    const make = (p, tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; p.appendChild(e); return e; };
    const fill = (tpl, ...v) => { let i = 0; return tpl.replace(/\{\}/g, () => String(v[i++])); };
    const post = async (path, body, keepalive) => {
      const r = await fetch('/api/' + path, { method: 'POST', keepalive: !!keepalive, cache: 'no-store',
                                             headers: { 'X-GX': '1', 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || fill('The server answered {}.', r.status));
      return j;
    };
    const page = Math.random().toString(36).slice(2, 12);
    let life = null, misses = 0, stopped = false, dialog = null;

    // --- Check-ins: every 20 s while open, goodbye on close. Two missed check-ins in a row: the app has stopped
    const ping = async () => {
      if (stopped) return;
      try { life = await post('ping', { page }); misses = 0; if (!box.firstChild) menuButton(); }
      catch (e) { if (life && ++misses >= 2) gone(); }
    };
    window.addEventListener('pagehide', () => { if (!stopped) post('bye', { page }, true).catch(() => {}); });
    window.addEventListener('pageshow', (e) => { if (e.persisted) ping(); });
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') ping(); });
    setInterval(ping, 20000);
    ping();

    // A page whose app has stopped (quit, or stopped by itself after the window was hidden): it says so, once
    const gone = (quit) => {
      if (stopped) return;
      stopped = true;
      box.replaceChildren();
      if (dialog && dialog.open) dialog.close();
      const bar = make(document.body, 'div', 'gx-app-gone');
      bar.setAttribute('role', 'alert');
      make(bar, 'b', null, quit ? 'DNA-Analyzer has stopped.' : 'DNA-Analyzer is no longer running.');
      make(bar, 'span', null, quit ? 'You can close this window.' : 'Start it again from its icon on the desktop or in the Start menu; this window then works again.');
      if (!quit) {
        const t = setInterval(async () => {   // started again (same address): carry on where this window was
          try { await post('ping', { page }); clearInterval(t); location.reload(); } catch (e) { /* still stopped */ }
        }, 5000);
      }
    };

    // --- The App menu
    const menuButton = () => {
      box.replaceChildren();
      const b = make(box, 'button', 'gx-app-btn', 'App');
      b.type = 'button';
      b.setAttribute('aria-haspopup', 'dialog');
      b.addEventListener('click', () => open('menu'));
    };
    const shownPeople = () => { const p = window.dash && dash.data('profiles'); return p && p.status === 'ok' ? p.data.map((x) => x.id) : []; };
    const open = (view, arg) => {
      if (!dialog) {
        dialog = make(document.querySelector('.gx') || document.body, 'dialog', 'gx-add-dialog gx-app-dialog');
        dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });
      }
      dialog.replaceChildren();
      const head = (title, sub) => {
        const h = make(dialog, 'div', 'gx-add-head');
        const t = make(h, 'div');
        make(t, 'h2', null, title);
        if (sub) make(t, 'p', 'gx-note', sub);
        const x = make(h, 'button', 'gx-add-x', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Close');
        x.addEventListener('click', () => dialog.close());
      };
      const status = () => { const s = make(dialog, 'p', 'gx-app-status'); s.setAttribute('role', 'status'); return s; };
      const row = () => make(dialog, 'div', 'gx-app-row');
      const button = (parent, text, cls, fn) => { const b = make(parent, 'button', cls, text); b.type = 'button'; b.addEventListener('click', fn); return b; };

      if (view === 'menu') {
        head('App', 'Everything stays on this computer.');
        const who = window.gx && gx.who && gx.who();
        const list = make(dialog, 'div', 'gx-app-menu');
        const item = (title, text, fn, bad) => {
          const b = button(list, '', 'gx-app-item' + (bad ? ' is-bad' : ''), fn);
          make(b, 'b', null, title); make(b, 'span', null, text);
        };
        if (who && shownPeople().includes(who)) {
          item(fill('Delete {}…', who), fill('{}\'s DNA file, imputation, results and Ask readings. The others stay.', who), () => open('delete', who), true);
        }
        item('Delete everything…', 'Every person, their files and results, the Ask history and the saved API key. The public research data stays.', () => open('all'), true);
        item('Quit', life && life.autostop
          ? 'Stops the app now. It also stops by itself a couple of minutes after its last window is closed.'
          : 'Stops the app now.', () => open('quit'));
      }

      if (view === 'delete') {
        head(fill('Delete {}?', arg), 'This can\'t be undone. Save their results first if you want to keep them.');
        const ul = make(dialog, 'ul', 'gx-app-list');
        for (const t of ['The DNA file and its imputation', 'Every result for them, in every tab', 'Their readings in the Ask tab'])
          make(ul, 'li', null, t);
        const r = row(), s = status();
        button(r, 'Cancel', 'gx-add-btn', () => dialog.close());
        const go = button(r, fill('Delete {}', arg), 'gx-app-danger', async () => {
          go.disabled = true; s.textContent = 'Deleting…';
          try {
            await post('delete', { id: arg });
            try { if (localStorage.getItem('gx-person') === arg) localStorage.removeItem('gx-person'); } catch (e) { /* no storage */ }
            s.textContent = fill('{} was deleted. The page reloads when the explorer has been rebuilt without them.', arg);
            waitUntil((ids) => !ids.includes(arg));
          } catch (e) { s.textContent = e.message; go.disabled = false; }
        });
      }

      if (view === 'all') {
        head('Delete everything?', 'This can\'t be undone. The app goes back to how it was installed.');
        const ul = make(dialog, 'ul', 'gx-app-list');
        for (const t of ['Every person: their DNA files, imputations and results', 'Every opened results file', 'The Ask tab\'s questions, answers and saved API key',
                         'The research lookups made for someone\'s questions']) make(ul, 'li', null, t);
        make(dialog, 'p', 'gx-note', 'The public research data and reference files stay, so adding someone again needs no download.');
        const lab = make(dialog, 'label', 'gx-app-type');
        make(lab, 'span', null, 'Type DELETE to confirm');
        const inp = make(lab, 'input'); inp.type = 'text'; inp.autocomplete = 'off'; inp.spellcheck = false;
        const r = row(), s = status();
        button(r, 'Cancel', 'gx-add-btn', () => dialog.close());
        const go = button(r, 'Delete everything', 'gx-app-danger', async () => {
          go.disabled = true; s.textContent = 'Deleting…';
          try {
            await post('delete-all', { confirm: 'delete everything' });
            try { localStorage.removeItem('gx-person'); } catch (e) { /* no storage */ }
            s.textContent = 'Everything was deleted. The page reloads in a moment.';
            waitUntil((ids) => ids.length === 0);
          } catch (e) { s.textContent = e.message; go.disabled = false; }
        });
        go.disabled = true;
        inp.addEventListener('input', () => { go.disabled = inp.value.trim().toUpperCase() !== 'DELETE'; });
        setTimeout(() => inp.focus(), 0);
      }

      if (view === 'quit') {
        head('Quit DNA-Analyzer?');
        const working = life && life.working;
        make(dialog, 'p', null, working
          ? 'Something is still working: a person being added or a question being researched. Quitting stops it; a person\'s run carries on from where it was with Resume, next time.'
          : 'The app stops. Start it again from its icon on the desktop or in the Start menu.');
        const r = row(), s = status();
        button(r, 'Cancel', 'gx-add-btn', () => dialog.close());
        const go = button(r, 'Quit', working ? 'gx-app-danger' : 'gx-app-go', async () => {
          go.disabled = true;
          try { await post('quit'); gone(true); setTimeout(() => window.close(), 300); }
          catch (e) { s.textContent = e.message; go.disabled = false; }
        });
      }
      if (!dialog.open) dialog.showModal();
    };
    // After a delete: reload once the rebuilt page no longer lists them
    const waitUntil = (ok) => {
      const t = setInterval(async () => {
        try {
          const p = await (await fetch('data/profiles.json', { cache: 'no-store' })).json();
          if (ok(p.map((x) => x.id))) { clearInterval(t); location.reload(); }
        } catch (e) { /* still rebuilding */ }
      }, 3000);
    };
  })();
