"""The reference files the pipeline needs, from genome/references.json: are they all there, and are they intact?

    python -m genome.references status                 # present, counts, sizes, free space; exit 1 if a run would fail
    python -m genome.references lock [--tier T ...]    # checksum the files into data/reference/references.lock.json
    python -m genome.references verify [--tier T ...]  # check the panel against 1000 Genomes' MD5 manifest and
                                                       # everything else against the lock file

The manifest is in git (sources, versions, how each file is made); the lock file is local, next to the files it
describes. A report can name the lock it ran with, so it can be rerun on exactly the same references.
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "genome", "references.json")
LOCK = os.path.join(ROOT, "data", "reference", "references.lock.json")
PANEL = os.environ.get("DNA_PANEL_ROOT", r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38")
ROOTS = {"ref": os.path.join(ROOT, "data", "reference"), "panel": PANEL,
         "ensembl": os.environ.get("DNA_ENSEMBL_DIR", os.path.join(os.path.dirname(PANEL), "ensembl_grch38"))}
TIERS = ("impute", "analyse", "built", "source", "grch37")
NEEDS = {"imputing a person": ("impute",), "analysing": ("impute", "analyse"),
         "rebuilding the built references": ("source",), "the GRCh37 comparison": ("grch37",)}


def entries():
    return json.load(open(MANIFEST, encoding="utf-8"))["references"]


def files(e):
    pattern = e["path"].format(**ROOTS)
    return sorted(f for f in glob.glob(pattern) if not f.endswith(".part"))


def state(e):
    fs = files(e)
    want = e.get("count", 1)
    return ("ok" if len(fs) >= want else "partial" if fs else "missing"), fs, want


def gb(n):
    return f"{n / 1e9:.1f} GB" if n >= 1e8 else f"{n / 1e6:.1f} MB"


def status():
    by = {}
    print(f"{'':2}{'reference':24}{'tier':9}{'files':>9}{'size':>10}  version")
    for e in entries():
        s, fs, want = state(e)
        by.setdefault(e["tier"], []).append(s)
        mark = {"ok": "  ", "partial": "! ", "missing": "x "}[s]
        size = sum(os.path.getsize(f) for f in fs)
        print(f"{mark}{e['name']:24}{e['tier']:9}{f'{len(fs)}/{want}':>9}{gb(size):>10}  {e.get('version', '')[:70]}")
        if s != "ok":
            print(f"{'':35}-> {e['get']}")
    print()
    bad = False
    for what, tiers in NEEDS.items():
        ok = all(s == "ok" for t in tiers for s in by.get(t, []))
        print(f"  {'ready' if ok else 'NOT ready':10} for {what}")
        bad |= not ok and "impute" in tiers
    for drive in sorted({os.path.splitdrive(p)[0].upper() + "\\" for p in ROOTS.values()} | {"C:\\"}):
        if os.path.exists(drive):
            print(f"  {drive} {shutil.disk_usage(drive).free / 1e9:.0f} GB free")
    if os.path.exists(LOCK):
        print(f"  lock: {os.path.relpath(LOCK, ROOT)} ({json.load(open(LOCK))['written']})")
    else:
        print("  no lock file yet: python -m genome.references lock")
    return 1 if bad else 0


def digest(path, algo="sha256"):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while block := f.read(1 << 23):
            h.update(block)
    return h.hexdigest()


def chosen(tiers):
    return [e for e in entries() if not tiers or e["tier"] in tiers]


def lock(tiers):
    old = json.load(open(LOCK)) if os.path.exists(LOCK) else {"files": {}}
    out = dict(old["files"])
    for e in chosen(tiers):
        for f in files(e):
            key = os.path.normpath(f)
            st = os.stat(f)
            prev = out.get(key)
            if prev and prev["size"] == st.st_size and prev["mtime"] == int(st.st_mtime):
                continue  # unchanged since it was hashed
            t = time.time()
            out[key] = {"reference": e["name"], "size": st.st_size, "mtime": int(st.st_mtime), "sha256": digest(f)}
            print(f"{e['name']}: {os.path.basename(f)} ({gb(st.st_size)}, {time.time() - t:.0f}s)", flush=True)
    tmp = LOCK + ".part"
    json.dump({"written": time.strftime("%Y-%m-%d %H:%M"), "manifest": os.path.relpath(MANIFEST, ROOT),
               "files": out}, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, LOCK)
    print(f"{len(out)} files in {LOCK}")


def md5_manifest(path):
    """{file name: md5} from 1000 Genomes' manifest (name, md5 per line)."""
    out = {}
    for line in open(path):
        p = line.split()
        if len(p) >= 2:
            out[p[0]] = p[1]
    return out


def verify(tiers):
    lk = json.load(open(LOCK))["files"] if os.path.exists(LOCK) else {}
    bad = unchecked = 0
    for e in chosen(tiers):
        official = md5_manifest(e["md5"].format(**ROOTS)) if e.get("md5") else {}
        for f in files(e):
            name = os.path.basename(f)
            if name in official:
                ok, how = digest(f, "md5") == official[name], "md5, 1000 Genomes manifest"
            elif os.path.normpath(f) in lk:
                ok, how = digest(f) == lk[os.path.normpath(f)]["sha256"], "sha256, lock"
            else:
                unchecked += 1
                continue
            bad += not ok
            print(f"{'ok ' if ok else 'BAD'} {e['name']}: {name} ({how})", flush=True)
    print(f"{bad} damaged, {unchecked} not in the lock file" + (" (run lock first)" if unchecked else ""))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("status", "lock", "verify"))
    ap.add_argument("--tier", action="append", choices=TIERS)
    a = ap.parse_args()
    if a.command == "status":
        sys.exit(status())
    if a.command == "lock":
        lock(a.tier)
    else:
        sys.exit(verify(a.tier))


if __name__ == "__main__":
    main()
