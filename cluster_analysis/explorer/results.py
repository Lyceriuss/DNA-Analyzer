"""A person's results as one file: every dataset row the explorer has for them, so a result can be kept, moved to
another computer, or opened in the web app on a phone (docs/architecture/production.md, Phase 0). No DNA file and no
genotype file goes in, only the interpreted rows the page shows, which do include the person's genotypes at the
variants it discusses: the file is as private as the DNA file and stays with its owner.

    python -m cluster_analysis.explorer results export --person ID [--out FILE]
    python -m cluster_analysis.explorer results import FILE [--as ID]
    python -m cluster_analysis.explorer results list

An imported person is kept in data/output/imported/ and merged into the datasets on every export, next to the
people analysed here.
"""
import datetime
import gzip
import json
import os
import re

from genome import build as gbuild

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASETS = os.path.join(ROOT, gbuild.EXPLORER, "datasets")
IMPORTED = os.path.join(ROOT, "data", "output", "imported" + gbuild.SUFFIX)
FORMAT = "dna-analyzer-results"
VERSION = 1
SUFFIX = ".dnaresults.gz"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


def _knowledge():
    try:
        from cluster_analysis import knowledge
        k = knowledge.installed()
        return k and k.get("version")
    except Exception:
        return None


def collect(pid, datasets=DATASETS):
    """{dataset: [rows]} for one person, from the exported datasets."""
    out = {}
    for n in sorted(os.listdir(datasets)):
        if not n.endswith(".json") or n == "bundle.json":
            continue
        with open(os.path.join(datasets, n), encoding="utf-8") as f:
            rows = json.load(f)
        if not isinstance(rows, list):
            continue
        mine = [r for r in rows if isinstance(r, dict) and r.get("person") == pid]
        if mine:
            out[n[:-5]] = mine
    return out


def export(pid, out=None, datasets=DATASETS):
    with open(os.path.join(datasets, "profiles.json"), encoding="utf-8") as f:
        prof = next((p for p in json.load(f) if p["id"] == pid), None)
    if not prof:
        raise SystemExit(f"{pid}: no such profile in the datasets (python -m cluster_analysis.explorer export first)")
    rows = collect(pid, datasets)
    doc = {"format": FORMAT, "version": VERSION, "created": datetime.datetime.now().isoformat(timespec="seconds"),
           "build": gbuild.BUILD,
           "knowledge": _knowledge(), "profile": prof, "datasets": rows}
    out = out or os.path.join(ROOT, "data", "output", f"{pid}{SUFFIX}")
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{out}: {pid}, {sum(len(r) for r in rows.values()):,} rows in {len(rows)} datasets "
          f"({os.path.getsize(out) / 1e6:.1f} MB)")
    return out


def read(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("format") != FORMAT:
        raise ValueError("not a results file")
    if doc.get("version", 0) > VERSION:
        raise ValueError(f"a results file of version {doc['version']}; this app reads up to {VERSION}: update the app")
    if doc.get("build") != gbuild.BUILD:
        raise ValueError(f"results made on {doc.get('build')}; this app runs on {gbuild.BUILD}")
    if not ID_RE.match(str((doc.get("profile") or {}).get("id", ""))):
        raise ValueError("the results file has no valid person id")
    return doc


def import_(path, as_id=None, taken=()):
    """Keeps the file under data/output/imported/<id>; with as_id the person is renamed (an id already in use)."""
    doc = read(path)
    old = doc["profile"]["id"]
    pid = as_id or old
    if not ID_RE.match(pid):
        raise ValueError("A name can have letters, digits, _ and -, up to 32 characters.")
    if pid in taken:
        raise ValueError(f"There is already a profile named {pid}.")
    if pid != old:
        doc["profile"]["id"] = pid
        doc["datasets"] = {n: [{**r, "person": pid} for r in rows] for n, rows in doc["datasets"].items()}
    doc["imported"] = datetime.datetime.now().isoformat(timespec="seconds")
    os.makedirs(IMPORTED, exist_ok=True)
    with gzip.open(os.path.join(IMPORTED, pid + SUFFIX), "wt", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{pid} imported ({sum(len(r) for r in doc['datasets'].values()):,} rows); export to show them")
    return pid


def imported():
    """The imported people's documents."""
    if not os.path.isdir(IMPORTED):
        return []
    out = []
    for n in sorted(os.listdir(IMPORTED)):
        if n.endswith(SUFFIX):
            try:
                out.append(read(os.path.join(IMPORTED, n)))
            except (OSError, ValueError) as e:
                print(f"   [!] {n}: {e}")
    return out


def merge(merged, local_ids):
    """Adds the imported people's rows to the datasets export.py is about to write. A person analysed on this
    machine wins over an imported one of the same id."""
    for doc in imported():
        pid = doc["profile"]["id"]
        if pid in local_ids:
            print(f"   [!] {pid}: analysed here as well; the imported copy is not shown")
            continue
        for name, rows in doc["datasets"].items():
            if name == "profiles":
                continue
            merged.setdefault(name, []).extend(rows)
        merged.setdefault("profiles", []).append({**{k: doc["profile"].get(k) for k in ("id", "sex")},
                                                  "imported": doc.get("imported", "")[:10],
                                                  **({"lite": True} if doc["profile"].get("lite") else {})})
        print(f"   {pid}: imported results merged ({doc.get('created', '')[:10]})")


def main(a):
    if a.action == "export":
        if not a.person:
            raise SystemExit("results export needs --person ID")
        export(a.person, a.out)
    elif a.action == "import":
        if not a.file:
            raise SystemExit("results import needs FILE")
        with open(os.path.join(DATASETS, "profiles.json"), encoding="utf-8") as f:
            taken = {p["id"] for p in json.load(f) if not p.get("imported")}
        try:
            import_(a.file, a.as_id, taken)
        except ValueError as e:
            raise SystemExit(f"{a.file}: {e}")
    else:
        for d in imported():
            p = d["profile"]
            print(f"{p['id']:24} {p.get('sex') or '':7} created {d.get('created', '')[:10]}, imported {d.get('imported', '')[:10]}"
                  f"{', measured variants only' if p.get('lite') else ''}")
