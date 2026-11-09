"""Lists the source terms the page shows that the Swedish switch should cover, and which still lack a translation.

Two kinds of text reach the page from the data rather than from the page's own wording:
- the library's texts (config/snp_traits.json): each entry's trait, system and genotype readings;
- disease and trait names: Open Targets diseases, GWAS Catalog traits and ClinVar conditions in the theme datasets.

Their Swedish lives in explorer/i18n_sv_terms.json ({english: swedish}), published as the i18n_sv_terms dataset next to
i18n_sv (the page's own wording). GWAS traits arrive comma-joined ("breast cancer, COVID-19"), so each part is a term on
its own; the page translates a joined list part by part.

    python cluster_analysis/explorer/i18n_terms.py DATASET_DIR            # report what is missing
    python cluster_analysis/explorer/i18n_terms.py DATASET_DIR --todo F   # write the missing terms to F (a JSON list)
    python cluster_analysis/explorer/i18n_terms.py --publish OUT          # write the [{en, sv}] rows for the dataset
    python cluster_analysis/explorer/i18n_terms.py --publish OUT --page   # the same for the page's wording (i18n_sv)

DATASET_DIR holds the exported datasets (theme_genes.json, theme_meta.json, ...). Only term names are read from them;
nothing about a genotype is written out.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIBRARY = os.path.join(ROOT, "config", "snp_traits.json")
TERMS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n_sv_terms.json")
# ClinVar readings arrive as "<significance>: <condition>"; the significance is page wording (in i18n_sv.json)
CLINVAR_PREFIX = re.compile(r"^(association|protective|risk factor|drug response|pathogenic|likely pathogenic|affects|"
                            r"confers sensitivity|other): ", re.I)


def library_terms():
    lib = json.load(open(LIBRARY, encoding="utf-8"))
    out = set()
    for e in lib.values():
        for f in ("trait", "system"):
            if e.get(f):
                out.add(e[f].strip())
        out.update(t.strip() for t in (e.get("variants") or {}).values() if t)
    return out


def _parts(what):
    """A GWAS/ClinVar 'what' string → its terms (comma-joined traits; a ClinVar significance prefix dropped)."""
    what = CLINVAR_PREFIX.sub("", what.strip())
    if ": " in what:            # a library finding: "<trait>: <reading>", both library terms
        return []
    return [p.strip() for p in what.split(", ") if p.strip()]


def disease_terms(dataset_dir):
    out = set()
    rows = json.load(open(os.path.join(dataset_dir, "theme_genes.json"), encoding="utf-8"))
    for r in rows:
        try:
            ev = json.loads(r.get("evidence") or "{}")
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        out.update((ev.get("diseases") or {}).keys())
        out.update(ev.get("joined_by") or [])
        for f in ev.get("findings") or []:
            for it in f.get("items") or []:
                if it.get("source") in ("GWAS", "ClinVar") and it.get("what"):
                    out.update(_parts(it["what"]))
                for k in it.get("related") or []:      # "Other studies of this SNP name the allele: ..."
                    if k.get("trait"):
                        out.update(_parts(k["trait"]))
    for r in json.load(open(os.path.join(dataset_dir, "theme_meta.json"), encoding="utf-8")):
        for v in r.values():
            if isinstance(v, str) and '"condition"' in v:
                for m in re.finditer(r'"condition":\s*"((?:[^"\\]|\\.)*)"', v):
                    out.add(json.loads('"' + m.group(1) + '"'))
    # The library's module names (cluster_analysis/library/module_names.json) head the Profile and Biomarkers tabs
    names = json.load(open(os.path.join(ROOT, "cluster_analysis", "library", "module_names.json"), encoding="utf-8"))
    out.update(t for k, v in names.items() if not k.startswith("_") for t in (k, v))   # enrichment label and name
    return {t for t in out if re.search(r"[A-Za-z]{3}", t)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset_dir", nargs="?")
    ap.add_argument("--todo")
    ap.add_argument("--publish")
    ap.add_argument("--page", action="store_true", help="with --publish: the page's own wording (i18n_sv.json) instead")
    a = ap.parse_args()
    have = json.load(open(TERMS, encoding="utf-8")) if os.path.exists(TERMS) else {}
    if a.publish and a.page:
        # The page's dictionary keeps every key, also those equal to their Swedish: a separator template such as
        # "{} · {}" translates its values only through such a key
        page = json.load(open(os.path.join(os.path.dirname(TERMS), "i18n_sv.json"), encoding="utf-8"))
        rows = [{"en": en, "sv": sv} for en, sv in page.items() if sv]
        json.dump(rows, open(a.publish, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, separators=(",", ":"))
        print(f"{len(rows)} rows -> {a.publish}")
        return
    if a.publish:
        rows = [{"en": en, "sv": sv} for en, sv in sorted(have.items()) if sv and sv != en]
        json.dump(rows, open(a.publish, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, separators=(",", ":"))
        print(f"{len(rows)} rows -> {a.publish}")
        return
    if not a.dataset_dir:
        ap.error("DATASET_DIR is needed (or --publish)")
    lib, dis = library_terms(), disease_terms(a.dataset_dir)
    page = json.load(open(os.path.join(os.path.dirname(TERMS), "i18n_sv.json"), encoding="utf-8"))
    want = (lib | dis) - set(page)
    missing = sorted(t for t in want if t not in have)
    print(f"library {len(lib)}, diseases and traits {len(dis)}; translated {len(want) - len(missing)} of {len(want)}")
    if a.todo:
        json.dump(missing, open(a.todo, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=0)
        print(f"{len(missing)} missing -> {a.todo}")
    else:
        for t in missing[:40]:
            print("  " + t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
