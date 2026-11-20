"""The knowledge bundle: the public lookups the analysis makes (UniProt, Ensembl, Reactome, Europe PMC, GTEx, ...), cut
to what the code reads and packed as one versioned file, so an install starts without hours of API calls and without
asking public APIs about anything (docs/architecture/production.md, "The precomputed lookups").

    python -m cluster_analysis.knowledge fill                  # every lookup the current code makes, via the public sample
    python -m cluster_analysis.knowledge build [--out DIR]     # from this machine's cache -> knowledge-<date>.zip
    python -m cluster_analysis.knowledge install FILE|URL      # unpacks into the cache (DNA_CACHE_DIR)
    python -m cluster_analysis.knowledge status                # the installed release, and lookups it lacked

The cache's readers are unchanged: the bundle holds cache files under their own names, so `sources._cached` finds
them. A lookup the bundle lacks still goes to the live API, and its namespace and key are logged locally
(misses.log in the cache) so the next release can add it.

Never in the bundle: what a model wrote (Ask's readings) and the results of Ask's own searches, which follow what
someone asked. Batched variant lookups are repacked into sorted chunks, so no chunk shows which ids were asked
together.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.request
import zipfile

from cluster_analysis import sources

FORMAT = 1
MANIFEST = "knowledge.json"   # inside the bundle
INSTALLED = "knowledge_installed.json"   # in the cache, after install
MISSES = "misses.log"
KEYED = re.compile(r"^(.+?)_[0-9a-f]{14,16}\.json$")
# Written by a model, or keyed by what someone asked: stays on the machine that made it
PRIVATE = ("agent_cat", "agent_interp", "agent_recent", "agent_epmc", "agent_epmc_full", "agent_evidence2",
           "agent_ot_search")
# Batched by the ids of one run: repacked as sorted chunks, with their id index rebuilt
BATCHED = {"ensembl_vep": "vep_index.json", "vep_canonical": "vep_canonical_index.json"}
CHUNK = 500
SKIP_NAMES = {INSTALLED, MISSES}


def namespace(name):
    m = KEYED.match(name)
    if m:
        return m.group(1)
    return name.split("_")[0] if "_" in name else name


def private(name):
    return namespace(name) in PRIVATE or name.startswith(tuple(p + "_" for p in PRIVATE))


# --- What each kind keeps --------------------------------------------------------------------

def slim_variation(rec):
    """UniProt variation records: only the features with a dbSNP id, and only the fields read by function_evidence,
    gene_calls, literature and intro (11% of the full record, measured 2026-11-20)."""
    out = []
    for f in (rec or {}).get("features") or []:
        rs = [{"id": x["id"]} for x in f.get("xrefs") or [] if str(x.get("id", "")).startswith("rs")]
        if not rs:
            continue
        g = {"type": f.get("type"), "wildType": f.get("wildType"), "alternativeSequence": f.get("alternativeSequence"),
             "begin": f.get("begin"), "xrefs": rs, "genomicLocation": f.get("genomicLocation"),
             "descriptions": [{"value": d["value"]} for d in f.get("descriptions") or [] if d.get("value")],
             "association": [{"name": a["name"]} for a in f.get("association") or [] if a.get("name")],
             "predictions": [{k: p.get(k) for k in ("predAlgorithmNameType", "predictionValType", "score")}
                             for p in f.get("predictions") or [] if p.get("predAlgorithmNameType") in ("SIFT", "PolyPhen")],
             "evidences": [{"code": e["code"], "source": {"name": "pubmed", "id": e["source"]["id"]}}
                           for e in f.get("evidences") or [] if e.get("code") == "ECO:0000269"
                           and (e.get("source") or {}).get("name") == "pubmed" and e["source"].get("id")]}
        out.append({k: v for k, v in g.items() if v not in (None, [])})
    return {"accession": (rec or {}).get("accession"), "features": out}


SLIM = {"prot_variation": slim_variation}


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# --- Build -----------------------------------------------------------------------------------

def build(out_dir, cache=None):
    cache = cache or sources.CACHE_DIR
    version = datetime.date.today().isoformat()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"knowledge-{version}.zip")
    tmp = path + ".part"
    names = sorted(n for n in os.listdir(cache) if os.path.isfile(os.path.join(cache, n)))
    counts, sizes, left = {}, {}, {}
    batched = {ns: {} for ns in BATCHED}
    started = time.time()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for i, n in enumerate(names):
            if i % 2000 == 0:
                print(f"   {i:,}/{len(names):,} files ({time.time() - started:.0f} s)", flush=True)
            ns = namespace(n)
            if n in SKIP_NAMES or n.endswith((".tmp", ".part", ".lock")) or n in BATCHED.values():
                continue
            if private(n):
                left[ns] = left.get(ns, 0) + 1
                continue
            p = os.path.join(cache, n)
            # A batch of variant records: one of this machine's own (keyed) or a chunk an installed bundle brought
            batch = next((b for b in BATCHED if n.startswith(b + "_") and n.endswith(".json")), None)
            if batch:
                ns = batch
                try:
                    with open(p, encoding="utf-8") as f:
                        data = json.load(f)
                except ValueError:
                    continue
                for v in data if isinstance(data, list) else []:
                    if isinstance(v, dict) and v.get("id"):
                        batched[ns].setdefault(v["id"], v)
                continue
            if ns in SLIM and n.endswith(".json"):
                try:
                    with open(p, encoding="utf-8") as f:
                        body = _dump(SLIM[ns](json.load(f)))
                except ValueError:
                    continue
                z.writestr(n, body)
                size = len(body)
            else:
                z.write(p, n)
                size = os.path.getsize(p)
            counts[ns] = counts.get(ns, 0) + 1
            sizes[ns] = sizes.get(ns, 0) + size
        # Variant batches: sorted chunks under neutral names, with the id index (and the ids Ensembl had no record for)
        for ns, index_name in BATCHED.items():
            recs = batched[ns]
            ids = sorted(recs)
            index = {"files": [], "ids": {}}
            for k in range(0, len(ids), CHUNK):
                fn = f"{ns}_k{k // CHUNK:05d}.json"
                body = _dump([recs[r] for r in ids[k:k + CHUNK]])
                z.writestr(fn, body)
                index["files"].append(fn)
                index["ids"].update({r: fn for r in ids[k:k + CHUNK]})
                sizes[ns] = sizes.get(ns, 0) + len(body)
            try:
                with open(os.path.join(cache, index_name), encoding="utf-8") as f:
                    index["absent"] = sorted(set(json.load(f).get("absent") or ()) - set(ids))
            except (OSError, ValueError):
                pass
            z.writestr(index_name, _dump(index))
            counts[ns] = len(ids)
        manifest = {"format": FORMAT, "version": version, "built": datetime.datetime.now().isoformat(timespec="seconds"),
                    "namespaces": {ns: {"files": counts[ns], "bytes": sizes.get(ns, 0)} for ns in sorted(counts)},
                    "left_out": left, "bytes": sum(sizes.values())}
        z.writestr(MANIFEST, json.dumps(manifest, indent=1))
    os.replace(tmp, path)
    digest = sha256(path)
    with open(path + ".sha256", "w", encoding="utf-8") as f:
        f.write(f"{digest}  {os.path.basename(path)}\n")
    print(f"done: {path}\n   {os.path.getsize(path) / 1e6:,.0f} MB packed, {manifest['bytes'] / 1e6:,.0f} MB unpacked, "
          f"{sum(counts.values()):,} entries in {len(counts)} kinds ({time.time() - started:.0f} s); "
          f"left out: {sum(left.values()):,} private files")
    return path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --- Fill ------------------------------------------------------------------------------------

SAMPLE = "HG00096"   # the public 1000 Genomes sample on a chip layout (genome/sample_person.py)


def fill():
    """Makes every lookup the current code can make, so the bundle isn't a snapshot of what this machine happened to
    ask: the public sample through every analysis step, then the explorer's export. The lookups run over fixed sets
    (every gene's eQTL variant, the theme genes, ...), the same for anyone, so one person's run covers all; the
    sample keeps it to public data. Run before build, after code that asks for more has changed."""
    import subprocess
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for cmd in (["-m", "cluster_analysis.profiles", "run", "--person", SAMPLE], ["-m", "cluster_analysis.explorer", "export"]):
        print("==", " ".join(cmd), flush=True)
        subprocess.run([sys.executable, *cmd], cwd=root, env=env, check=True)


# --- Install ---------------------------------------------------------------------------------

def fetch(url, dest, progress=None):
    """Downloads url to dest, resuming a partial download."""
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    req = urllib.request.Request(url, headers={"User-Agent": sources.CALLER, **({"Range": f"bytes={have}-"} if have else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        if have and r.status != 206:
            have = 0  # the server ignored the range: start over
        total = have + int(r.headers.get("Content-Length") or 0)
        with open(part, "ab" if have else "wb") as f:
            done = have
            for block in iter(lambda: r.read(1 << 20), b""):
                f.write(block)
                done += len(block)
                if progress:
                    progress(done, total)
    os.replace(part, dest)
    return dest


def install(src, cache=None, expect_sha256=None, progress=None):
    """Unpacks a bundle (a path or URL) into the cache. Files already there are kept: they are this machine's own
    lookups, at least as complete as the bundle's. Returns the manifest."""
    cache = cache or sources.CACHE_DIR
    os.makedirs(cache, exist_ok=True)
    path = src
    if re.match(r"^https?://", src):
        path = fetch(src, os.path.join(cache, os.path.basename(src.split("?")[0])), progress)
    if expect_sha256 and sha256(path) != expect_sha256.lower():
        raise ValueError(f"{path}: checksum does not match; delete it and download again")
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read(MANIFEST))
        if manifest.get("format") != FORMAT:
            raise ValueError(f"bundle format {manifest.get('format')}, this app reads {FORMAT}: update the app")
        members = [m for m in z.infolist() if m.filename != MANIFEST and "/" not in m.filename and "\\" not in m.filename
                   and not m.filename.startswith(".")]
        added = 0
        for i, m in enumerate(members):
            dest = os.path.join(cache, m.filename)
            if m.filename in BATCHED.values() and os.path.exists(dest):
                _merge_index(dest, json.loads(z.read(m)))
                continue
            if os.path.exists(dest):
                continue
            with z.open(m) as r, open(dest + ".tmp", "wb") as w:
                shutil.copyfileobj(r, w, 1 << 20)
            os.replace(dest + ".tmp", dest)
            added += 1
            if progress and i % 500 == 0:
                progress(i, len(members))
    with open(os.path.join(cache, INSTALLED), "w", encoding="utf-8") as f:
        json.dump({**manifest, "installed": datetime.datetime.now().isoformat(timespec="seconds"),
                   "file": os.path.basename(path), "added": added}, f, indent=1)
    print(f"knowledge {manifest['version']}: {added:,} lookups added to {cache}")
    return manifest


def _merge_index(dest, theirs):
    """A machine with its own variant index keeps it, and learns the bundle's chunks."""
    with open(dest, encoding="utf-8") as f:
        mine = json.load(f)
    for fn in theirs.get("files", []):
        if fn not in mine["files"]:
            mine["files"].append(fn)
    for rs, fn in theirs.get("ids", {}).items():
        mine["ids"].setdefault(rs, fn)
    mine["absent"] = sorted(set(mine.get("absent") or ()) | set(theirs.get("absent") or ()))
    with open(dest + ".tmp", "w", encoding="utf-8") as f:
        json.dump(mine, f)
    os.replace(dest + ".tmp", dest)


INCLUDED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge")


def included(folder=INCLUDED):
    """The newest bundle the installer placed in data/knowledge/, or None."""
    if not os.path.isdir(folder):
        return None
    files = sorted(f for f in os.listdir(folder) if re.match(r"knowledge-[\d-]+\.zip$", f))
    return os.path.join(folder, files[-1]) if files else None


def ensure_included(cache=None):
    """Installs the included bundle when it is newer than the installed one (or none is): before the page is first
    built, which otherwise looks its public data up live."""
    src = included()
    if not src:
        return None
    k = installed(cache)
    version = re.search(r"knowledge-([\d-]+)\.zip$", src).group(1)
    if k and k.get("version", "") >= version:
        return k
    print(f"Installing the research data ({os.path.basename(src)}), once...", flush=True)
    return install(src, cache)


def installed(cache=None):
    try:
        with open(os.path.join(cache or sources.CACHE_DIR, INSTALLED), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def status(cache=None):
    cache = cache or sources.CACHE_DIR
    k = installed(cache)
    print(f"cache: {cache}")
    print(f"knowledge: {k['version']} (installed {k['installed']}, {k['added']:,} lookups added)" if k else
          "knowledge: none installed (lookups go to the live APIs)")
    try:
        with open(os.path.join(cache, MISSES), encoding="utf-8") as f:
            rows = [ln.split("\t") for ln in f.read().splitlines() if ln]
    except OSError:
        rows = []
    if rows:
        by = {}
        for r in rows:
            by[r[1]] = by.get(r[1], 0) + 1
        print(f"lookups the bundle lacked: {len(rows):,} ({', '.join(f'{n} {c}' for n, c in sorted(by.items(), key=lambda x: -x[1])[:8])})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default="D:/DNA-Analyzer-build/knowledge" if os.path.isdir("D:/") else "dist/knowledge")
    b.add_argument("--cache", help="the cache to build from (default: this machine's)")
    i = sub.add_parser("install")
    i.add_argument("src", help="a bundle file or URL")
    i.add_argument("--sha256")
    sub.add_parser("status")
    sub.add_parser("fill", help=f"run the public sample ({SAMPLE}) through every step first, so the cache is complete")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.out, a.cache)
    elif a.cmd == "fill":
        fill()
    elif a.cmd == "install":
        install(a.src, expect_sha256=a.sha256)
    else:
        status()


if __name__ == "__main__":
    sys.exit(main())
