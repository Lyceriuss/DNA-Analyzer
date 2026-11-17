"""The Gene Cluster Explorer, on localhost.

    python -m cluster_analysis.explorer export    # datasets for every profile -> data/output/explorer_GRCh38/datasets/
    python -m cluster_analysis.explorer build     # the page (index.html) from its parts
    python -m cluster_analysis.explorer serve     # export if needed, build the site (page, runtime, d3, datasets) and
                                                  # serve it on http://127.0.0.1:8000 (this machine only: the data
                                                  # holds genotypes). No internet needed, no size limit.
    python -m cluster_analysis.explorer check     # render every tab for every profile in English and Swedish in
                                                  # headless Chrome, report script errors

Everything personal stays under data/output/explorer_GRCh38/ (explorer/ for DNA_BUILD=GRCh37; ignored by git).

The old claude.ai artifact (optional; its page is limited to 262,144 bytes):
    python -m cluster_analysis.explorer publish   # the minified page and the datasets that changed since the last
                                                  # publish, in data/output/explorer_GRCh38/publish/ with manifest.json
    python -m cluster_analysis.explorer publish --record lab_tests=/_blob/<id> ... [--page]
                                                  # after the agent's upload: remember what is live
Publishing itself is done by the agent with its Artifact tools.
"""
import argparse
import functools
import hashlib
import http.server
import json
import os
import re
import subprocess
import sys
import threading

from genome import build as gbuild

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, gbuild.EXPLORER)
DATASETS = os.path.join(OUT, "datasets")
SITE = os.path.join(OUT, "site")
PUBLISH = os.path.join(OUT, "publish")
RECORD = os.path.join(OUT, "published.json")
LIFECYCLES = os.path.join(ROOT, gbuild.OUTPUT, "lifecycles_XY_full.json")
ARTIFACT = "https://claude.ai/artifact/Rsz3RYugnZyvWnixS9168o"
TABS = ["home", "clusters", "medicines", "nutrition", "lifecycle", "biomarkers", "profile", "sources"]


def run(*args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True, env=env)


def export(_=None):
    os.makedirs(DATASETS, exist_ok=True)
    run("-m", "cluster_analysis.explorer.export", os.path.join(DATASETS, "bundle.json"), "--lifecycles", LIFECYCLES)


def build(_=None):
    run(os.path.join(HERE, "build.py"))


def site():
    if not os.path.exists(os.path.join(DATASETS, "profiles.json")):
        export()
    run(os.path.join(HERE, "build.py"), "--standalone", DATASETS, SITE)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve_dir(directory, port):
    handler = functools.partial(_Quiet, directory=directory)
    # 127.0.0.1 only: the datasets hold genotypes
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve(a):
    site()
    # The site plus the API behind "Add a person" (explorer/server.py)
    from cluster_analysis.explorer import server
    srv = server.make(SITE, a.port)
    print(f"Serving the explorer on http://127.0.0.1:{srv.server_address[1]}/  (Ctrl+C stops)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "chromium"]

COLLECT = """
<script>
  window.__errors = window.__errors || [];
  const _ce = console.error; console.error = (...a) => { window.__errors.push(a.map(String).join(' ')); _ce(...a); };
  const frame = () => new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));
  const settled = async () => {
    for (let i = 0; i < 400; i++) {
      await frame();
      const ids = new Set();
      document.querySelectorAll('[data-source]').forEach((el) => el.dataset.source.split(/\\s+/).forEach((x) => x && ids.add(x)));
      if ([...ids].every((id) => dash.data(id).status !== 'loading')) { await frame(); return; }
    }
  };
  window.addEventListener('load', async () => {
    await settled();
    const people = dash.data('profiles').data.map((p) => p.id), seen = [];
    for (const lang of ['en', 'sv']) {
      document.querySelector(`[data-lang=${lang}]`).click();
      for (const person of people) for (const tab of %s) {
        try { gx.show(tab); dash.setParams({ person }); } catch (e) { window.__errors.push(`${tab} ${person}: ${e.message}`); }
        await settled();
        seen.push(`${lang} ${person} ${tab}: ${[...document.querySelectorAll('.gx-page:not([hidden])')].reduce((n, p) => n + p.innerText.length, 0)} characters`);
      }
    }
    const pre = document.createElement('pre'); pre.id = 'checked';
    pre.textContent = JSON.stringify({ seen, errors: window.__errors });
    document.body.appendChild(pre);
  });
</script>
"""


def check(_=None):
    site()
    chrome = next((c for c in CHROME if os.path.exists(c) or not os.path.isabs(c)), None)
    test = os.path.join(SITE, "_check.html")
    page = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    # Errors are collected from the top of the page, so a part that fails to even parse is caught too
    early = "<script>window.__errors = []; window.addEventListener('error', (e) => window.__errors.push(e.message));</script>"
    page = page.replace("<body>", "<body>" + early, 1)
    open(test, "w", encoding="utf-8").write(page.replace("<script>dash.start();</script>",
                                                         "<script>dash.start();</script>" + COLLECT % json.dumps(TABS)))
    srv = serve_dir(SITE, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        dom = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--virtual-time-budget=2000000000", "--dump-dom",
                              f"http://127.0.0.1:{srv.server_address[1]}/_check.html"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900).stdout
    finally:
        srv.shutdown()
        os.remove(test)
    m = re.search(r'<pre id="checked">(.*?)</pre>', dom, re.S)
    if not m:
        sys.exit("check: the page didn't finish (no result in the rendered page)")
    import html
    res = json.loads(html.unescape(m.group(1)))
    for line in res["seen"]:
        print("  " + line)
    if res["errors"]:
        print("ERRORS:"); [print("  " + e) for e in res["errors"]]
        sys.exit(1)
    print(f"ok: {len(res['seen'])} views, no errors")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def publish(a):
    record = json.load(open(RECORD, encoding="utf-8")) if os.path.exists(RECORD) else {"datasets": {}, "page": None}
    if a.record or a.page:
        manifest = json.load(open(os.path.join(PUBLISH, "manifest.json"), encoding="utf-8"))
        for item in a.record or []:
            name, url = item.split("=", 1)
            d = next(d for d in manifest["datasets"] if d["name"] == name)
            record["datasets"][name] = {"sha256": d["sha256"], "url": url}
        if a.page:
            record["page"] = manifest["page"]["sha256"]
        json.dump(record, open(RECORD, "w", encoding="utf-8"), indent=1)
        print(f"recorded {len(a.record or [])} datasets{' and the page' if a.page else ''} as published")
        return
    if not os.path.exists(os.path.join(DATASETS, "profiles.json")):
        export()
    run(os.path.join(HERE, "build.py"), "--publish")
    os.makedirs(os.path.join(PUBLISH, "datasets"), exist_ok=True)
    for f in os.listdir(os.path.join(PUBLISH, "datasets")):
        os.remove(os.path.join(PUBLISH, "datasets", f))
    # The page's Swedish dictionaries as the [{en, sv}] rows the page reads
    run(os.path.join(HERE, "i18n_terms.py"), "--publish", os.path.join(PUBLISH, "datasets", "i18n_sv.json"), "--page")
    run(os.path.join(HERE, "i18n_terms.py"), "--publish", os.path.join(PUBLISH, "datasets", "i18n_sv_terms.json"))
    import shutil
    for f in sorted(os.listdir(DATASETS)):
        if f.endswith(".json") and f != "bundle.json":
            shutil.copyfile(os.path.join(DATASETS, f), os.path.join(PUBLISH, "datasets", f))
    page = os.path.join(PUBLISH, "page.json")
    shutil.copyfile(os.path.join(HERE, "build", "publish.json"), page)
    sets = []
    for f in sorted(os.listdir(os.path.join(PUBLISH, "datasets"))):
        p = os.path.join(PUBLISH, "datasets", f)
        name, h = f[:-5], sha(p)
        live = record["datasets"].get(name)
        sets.append({"name": name, "file": p, "bytes": os.path.getsize(p), "sha256": h,
                     "changed": not live or live["sha256"] != h, "live_url": live and live["url"]})
    manifest = {"artifact": ARTIFACT, "page": {"file": page, "sha256": sha(page), "changed": record.get("page") != sha(page)},
                "datasets": sets}
    json.dump(manifest, open(os.path.join(PUBLISH, "manifest.json"), "w", encoding="utf-8"), indent=1)
    changed = [d for d in sets if d["changed"]]
    print(f"publish/ ready for {ARTIFACT}")
    print(f"  page: {'changed' if manifest['page']['changed'] else 'unchanged'}")
    print(f"  datasets changed: {len(changed)} of {len(sets)}" + "".join(f"\n    {d['name']} ({d['bytes']:,} bytes)" for d in changed))
    print("  steps: CLAUDE.md, 'Publishing the explorer'")


def main():
    ap = argparse.ArgumentParser(prog="python -m cluster_analysis.explorer", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export").set_defaults(fn=export)
    sub.add_parser("build").set_defaults(fn=build)
    sub.add_parser("site", help="the standalone site (page, runtime, datasets) rebuilt").set_defaults(fn=lambda _: run(os.path.join(HERE, "build.py"), "--standalone", DATASETS, SITE))
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(fn=serve)
    sub.add_parser("check").set_defaults(fn=check)
    p = sub.add_parser("publish")
    p.add_argument("--record", nargs="*", metavar="NAME=URL", help="datasets now live, with their asset URL")
    p.add_argument("--page", action="store_true", help="the page is now live")
    p.set_defaults(fn=publish)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
