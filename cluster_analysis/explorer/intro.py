"""The numbers behind the explorer's introduction (the Home tab): the intro_stats dataset.

    python -m cluster_analysis.explorer.intro                # print the rows (export writes them as intro_stats.json)

One row for the method, the same for everyone (person null):
  panel_people, holdout       the 1000 Genomes reference panel and the people held out to measure imputation
  map_sites                   genome-wide sites by class (chip, reliable, uncertain, not_knowable), genome/imputability.py
  map_by_frequency            per frequency band: sites measured, mean r2 and carrier sensitivity (all DR2 bins together)
  clinvar                     ClinVar pathogenic variants by what a chip can see (genes.json totals)
  references                  reference files in genome/references.json
One row per person:
  source, format              the raw file and its maker (genome/formats.py)
  measured, per_chrom         calls in the raw file, per chromosome
  matched, not_lifted         of them, those at 1000 Genomes sites, and those that couldn't be moved to GRCh38
  imputed, kept               calls imputation made, and those kept (GP >= the run's min_gp)
  tiers                       kept calls by confidence tier (genome/impute.py)
  validation                  hidden chip SNPs re-imputed: how many, and the share right among confident guesses

Whether the introduction is mandatory is settings.json (intro_required), not data.
"""
import json
import os

from genome import build as gbuild

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SETTINGS = os.path.join(HERE, "settings.json")


def settings():
    return json.load(open(SETTINGS, encoding="utf-8"))


def _load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None


def general():
    imp = os.path.join(gbuild.REF, "imputability")
    meta = _load(os.path.join(imp, "summary.json")) or {}
    by = {}
    for c in meta.get("calibration", []):
        b = by.setdefault(tuple(c["maf_bin"]), {"sites": 0, "r2": 0.0, "sens_w": 0.0, "sens_n": 0})
        b["sites"] += c["sites"]
        b["r2"] += c["r2"] * c["sites"]
        if c.get("sensitivity") is not None:
            b["sens_w"] += c["sensitivity"] * c["sites"]
            b["sens_n"] += c["sites"]
    bands = [{"from": lo, "to": min(hi, 0.5), "sites": b["sites"], "r2": round(b["r2"] / b["sites"], 3),
              "sensitivity": round(b["sens_w"] / b["sens_n"], 3) if b["sens_n"] else None}
             for (lo, hi), b in sorted(by.items())]
    genes = _load(os.path.join(imp, "genes.json")) or []
    keys = ("pathogenic", "chip", "reliable", "uncertain", "not_knowable", "not_in_panel", "not_mapped")
    refs = _load(os.path.join(ROOT, "genome", "references.json")) or {"references": []}
    from genome.impute import panel
    return {"person": None, "kind": "general", "panel_people": panel(gbuild.panel_name()).get("samples"),
            "holdout": meta.get("holdout"), "map_sites": meta.get("sites"), "map_by_frequency": bands,
            "clinvar": {k: sum(g.get(k, 0) for g in genes) for k in keys} if genes else None,
            "references": len(refs["references"])}


def person(p):
    from genome import formats
    from genome.impute import OUT, DEFAULT_PANEL
    from genome.loader import person_label
    pid, name = p["id"], gbuild.panel_name()
    folder = os.path.join(OUT, person_label(p["dna"]))
    folder = folder if name == DEFAULT_PANEL else os.path.join(folder, name)
    s = _load(os.path.join(folder, "summary.json")) or {}
    cal = _load(os.path.join(folder, "calibration.json")) or {}
    chroms = s.get("chroms", {})
    # Confident guesses (GP at or above the run's threshold) among the hidden chip SNPs: the share that were right
    cells = cal.get("cells", {}).values()
    n, right = sum(c["n"] for c in cells), sum(c["right"] for c in cells)
    try:
        fmt = formats.detect(p["dna"])
    except (SystemExit, OSError):
        fmt = None
    return {"person": pid, "kind": "person", "sex": p.get("sex"), "source": os.path.basename(p["dna"]), "format": fmt,
            "measured": s.get("totals", {}).get("calls"), "per_chrom": {c: v.get("calls") for c, v in chroms.items()},
            "matched": sum(v.get("matched", 0) for v in chroms.values()) or None,
            "not_lifted": sum((s.get("not_lifted") or {}).values()), "imputed": s.get("totals", {}).get("imputed"),
            "kept": s.get("totals", {}).get("imputed_kept"), "min_gp": s.get("min_gp"), "tiers": s.get("tiers"),
            "validation": {"hidden": cal.get("hidden"), "confident": n, "right": round(right / n, 4) if n else None}}


def rows(people):
    return [general()] + [person(p) for p in people]


if __name__ == "__main__":
    from cluster_analysis import profiles
    print(json.dumps(rows(profiles.load()), indent=1))
