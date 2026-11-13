# cluster_analysis/library/genotype_effects.py
"""
Gives every library SNP an evidence-based effect per genotype, and says which effects still lack a reading.

  function   per genotype: GoF | LoF | normal | altered | unknown, from evidence_call.py (CPIC, MaveDB, UniProt,
             a truncating change, SIFT/PolyPhen, GTEx). Library data only, so the PDF report runs offline.
  polarity   per effect: {"LoF": "negative"} means carrying less function is bad for the person; positive is good,
             neutral is neither. Keyed by the effect, so if new evidence flips the effect, the polarity no longer
             applies and the genotype reads as unclear until one is set for the new effect.
  polarity_source   "reviewed" (set by hand), or how a first draft was made on 2026-11-07 when the old 1-10 ratings
             were removed: "library wording" or "library ratings". Polarities are never changed here.

    python -m cluster_analysis.library.genotype_effects            # what would change, and the effects to review
    python -m cluster_analysis.library.genotype_effects --write    # write function / function_basis into the library

A new effect gets no polarity (it reads "unclear") until one is set by hand with "polarity_source": "reviewed".

Reading a genotype is cluster_analysis.library.analyzer.outcome(): GoF/LoF/altered → the polarity of that effect (positive / negative /
neutral, unclear without one); normal → typical; unknown → unknown.
"""
import argparse
import json
from collections import Counter

from cluster_analysis import sources
from cluster_analysis.evidence.evidence_call import evidence_call, load_evidence
from cluster_analysis.lifecycle.gene_trace import direction

TRAITS_PATH = "cluster_analysis/library/snp_traits.json"
EFFECTS = ("GoF", "LoF", "altered")


def calls_for(rsid, entry, ev, vep):
    """(function per genotype, basis, notes) for one library entry."""
    variants = entry.get("variants", {})
    calls = {gt: evidence_call(rsid, gt, ev, vep) for gt in variants}
    function = {gt: c["function"] for gt, c in calls.items()}
    basis = next((c["basis"] for c in calls.values() if c["function"] in EFFECTS), None) or \
        next((c["basis"] for c in calls.values() if c["function"] == "normal"), "none")
    notes = []
    polarity = entry.get("polarity") or {}
    for eff in sorted({f for f in function.values() if f in EFFECTS}):
        top = max((gt for gt in calls if function[gt] == eff), key=lambda gt: calls[gt]["dose"] or 0)
        d = direction(variants.get(top, ""))
        claim = "GoF" if d > 0 else "LoF" if d < 0 else None
        if eff not in polarity:
            notes.append(f"{eff}: no polarity (reads unclear)")
        if claim and eff in ("GoF", "LoF") and claim != eff and entry.get("polarity_source") != "reviewed":
            notes.append(f"wording says {claim}, {calls[top]['basis']} evidence says {eff}")
    return function, basis, notes


def run(write=False):
    traits = json.load(open(TRAITS_PATH, encoding="utf-8"))
    rsids = sorted(rs for rs in traits if rs.startswith("rs"))
    vep = sources.ensembl_vep(rsids)
    evidence = load_evidence()
    tally, review, changed = Counter(), [], []
    for rs, entry in traits.items():
        function, basis, notes = calls_for(rs, entry, evidence.get(rs), vep.get(rs))
        tally.update([f"basis:{basis}"])
        tally.update(f"{k}:{v}" for k, v in (entry.get("polarity") or {}).items())
        if function != entry.get("function") or basis != entry.get("function_basis"):
            changed.append((rs, entry.get("gene"), entry.get("function"), function))
        if notes:
            review.append((rs, entry.get("gene"), "; ".join(notes)))
        if write:
            entry["function"], entry["function_basis"] = function, basis
    for k, v in sorted(tally.items()):
        print(f"{k:28} {v}")
    print(f"\n{len(changed)} calls changed:")
    for r in changed:
        print("  ", *r)
    print(f"\n{len(review)} to review:")
    for r in review:
        print("  ", *r)
    if write and changed:
        json.dump(traits, open(TRAITS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
        print(f"\nWrote {TRAITS_PATH}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    run(ap.parse_args().write)
