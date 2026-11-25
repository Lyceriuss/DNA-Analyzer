# cluster_analysis/profiles.py
"""
Profiles: one person each, with their own analysis. The explorer switches between them.

    python -m cluster_analysis.profiles check                 # sex from each DNA file, against profiles.json
    python -m cluster_analysis.profiles run                   # every step for every profile
    python -m cluster_analysis.profiles run --person XX --steps themes,genes

Steps, per profile (outputs in data/output/cluster_analysis/profiles/<id>/ unless noted):
  themes     theme_graph.py cross-reference for each theme that applies to the profile's sex
             (-> data/output/cluster_analysis/theme_<id>_<theme>.json)
  genes      gene_calls.py for the profile's theme genes (-> data/output/cluster_analysis/gene_calls_<id>.json)
  medicines  medicines.py  -> med_genes, med_drugs, med_guidance, med_names
  nutrition  nutrition.py with the profile's sex -> nut_nutrients, nut_findings, nut_steps
  labtests   nutrition.py with labtests.json (Biomarkers tab) -> lab_tests, lab_findings, lab_steps
  fitness    nutrition.py with fitness.json (muscle theme scores) -> fit_tests, fit_findings, fit_steps; and
             themes/sport_snps.py (the popular sport genes) -> sport_snps
  cancers    nutrition.py with cancers.json (cancer theme: polygenic risk per cancer) -> can_tests, can_findings, can_steps
  inheritance  inheritance/ for each pair of this profile with one of the other sex (Inheritance tab)
             -> data/output/cluster_analysis/pairs/<XX>__<XY>/inh_*

explorer/export.py then builds every dataset for every profile, each row tagged with `person`.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

from genome import build as gbuild
from genome.loader import iter_calls

HERE = os.path.dirname(__file__)
PATH = os.path.join(HERE, "profiles.json")
PROFILE_DIR = f"{gbuild.OUTPUT}/profiles"
STEPS = ("themes", "genes", "medicines", "nutrition", "labtests", "fitness", "cancers", "inheritance")
THEME_SEX = {"XX": "female", "XY": "male"}   # theme_graph.py marks a theme's body layout as XX or XY


RUNS = os.path.join(os.path.dirname(HERE), "data", "output", "pipeline")   # cluster_analysis/pipeline.py's run records
# The people a pipeline run is analysing and exporting right now (comma-separated ids): listed by load() although
# their run hasn't finished
RUNNING_ENV = "DNA_PROFILE_RUNNING"


def finished(p):
    """Whether a person's run finished: no `pending` mark in profiles.json (pipeline.register sets it, the end of the
    run removes it) and no run record that isn't done. People added by hand have neither: finished."""
    if p.get("pending"):
        return False
    path = os.path.join(RUNS, p["id"] + ".json")
    if not os.path.exists(path):
        return True
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("state") == "done"
    except (OSError, ValueError):
        return False


def load(unfinished=False):
    """The people in profiles.json whose run finished (see finished), plus the one a running pipeline names in
    DNA_PROFILE_RUNNING. unfinished=True: everyone listed, however far their run got."""
    rows = json.load(open(PATH, encoding="utf-8"))["profiles"]
    if unfinished:
        return rows
    running = set(filter(None, os.environ.get(RUNNING_ENV, "").split(",")))
    return [p for p in rows if p["id"] in running or finished(p)]


def get(pid):
    return next((p for p in load(unfinished=True) if p["id"] == pid), None)


def applies(theme_sex, sex):
    """Whether a theme is for this sex: themes without a sex are for everyone, fertility themes for theirs."""
    return not theme_sex or THEME_SEX.get(theme_sex, theme_sex) == sex


def theme_graphs():
    return [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(HERE, "themes", "theme_graph_*.json")))]


def out_dir(pid):
    d = os.path.join(PROFILE_DIR, pid)
    os.makedirs(d, exist_ok=True)
    return d


# PAR1 and PAR2: X positions shared with Y, heterozygous in men too. On GRCh37, the build of the raw MyHeritage file
# x_heterozygosity reads, whatever build the analysis runs on.
PAR = gbuild.par("GRCh37")


def x_heterozygosity(dna):
    """Share of heterozygous calls among measured X SNPs outside the pseudoautosomal regions: about 0 in men (one X),
    clearly above 0 in women."""
    het = n = 0
    for _, chrom, pos, gt, tier in iter_calls(dna, confidence=("measured",)):
        if chrom not in ("X", "23") or pos is None or any(a <= pos <= b for a, b in PAR) or len(gt) != 2 or "-" in gt:
            continue
        n += 1
        het += gt[0] != gt[1]
    return het / n if n else None


def check():
    for p in load(unfinished=True):
        h = x_heterozygosity(p["dna"])
        dna_sex = None if h is None else "female" if h > 0.05 else "male"
        flag = "" if dna_sex in (None, p["sex"]) else f"  <- profiles.json says {p['sex']}"
        print(f"{p['id']}: X heterozygosity {h:.3f} -> {dna_sex}{flag}" if h is not None else f"{p['id']}: no X calls")


def run(pids, steps):
    py = [sys.executable, "-m"]
    # Named people are run however far their run got (the pipeline analyses its person this way); all: the finished
    for p in load(unfinished=bool(pids)):
        if pids and p["id"] not in pids:
            continue
        od = out_dir(p["id"])
        themes = [g["theme"] for g in theme_graphs() if applies(g.get("sex"), p["sex"])]
        cmds = []
        if "themes" in steps:
            cmds += [py + ["cluster_analysis.themes.theme_graph", t, "--dna", p["dna"]] for t in themes]
        if "genes" in steps:
            cmds.append(py + ["cluster_analysis.evidence.gene_calls", "--person", p["id"]])
            if p["sex"] == "female":  # the female fertility views (themes/fertility_deep.py): after the gene calls it reads
                cmds.append(py + ["cluster_analysis.themes.fertility_deep", "--dna", p["dna"], "--out-dir", od])
        if "medicines" in steps:
            cmds.append(py + ["cluster_analysis.medicines.medicines", "--dna", p["dna"], "--out-dir", od])
        if "nutrition" in steps:
            cmds.append(py + ["cluster_analysis.nutrition.nutrition", "--dna", p["dna"], "--out-dir", od,
                              "--sex", "women" if p["sex"] == "female" else "men"])
        if "labtests" in steps:
            cmds.append(py + ["cluster_analysis.nutrition.nutrition", "--config", "cluster_analysis/nutrition/labtests.json", "--prefix", "lab",
                              "--dna", p["dna"], "--out-dir", od, "--sex", "women" if p["sex"] == "female" else "men"])
        if "fitness" in steps:
            cmds.append(py + ["cluster_analysis.nutrition.nutrition", "--config", "cluster_analysis/nutrition/fitness.json", "--prefix", "fit",
                              "--dna", p["dna"], "--out-dir", od, "--sex", "women" if p["sex"] == "female" else "men"])
            cmds.append(py + ["cluster_analysis.themes.sport_snps", "--dna", p["dna"], "--out-dir", od])
        if "cancers" in steps:
            cmds.append(py + ["cluster_analysis.nutrition.nutrition", "--config", "cluster_analysis/nutrition/cancers.json", "--prefix", "can",
                              "--dna", p["dna"], "--out-dir", od, "--sex", "women" if p["sex"] == "female" else "men"])
        if "inheritance" in steps:
            cmds.append(py + ["cluster_analysis.inheritance", "--person", p["id"]])
            # The person's own place on every trait (Biomarkers tab) -> profiles/<id>/trait_scores.json
            cmds.append(py + ["cluster_analysis.inheritance.predict", "person", p["id"]])
        for c in cmds:
            print(f"\n== {p['id']}: {' '.join(c[2:])}", flush=True)
            running = ",".join(filter(None, [os.environ.get(RUNNING_ENV)] + list(pids or [])))
            subprocess.run(c, check=True, env={**os.environ, "PYTHONIOENCODING": "utf-8", RUNNING_ENV: running})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("check", "run"))
    ap.add_argument("--person", nargs="*", help="profile ids (default: all)")
    ap.add_argument("--steps", default=",".join(STEPS), help=f"comma-separated, from {', '.join(STEPS)}")
    a = ap.parse_args()
    if a.command == "check":
        check()
    else:
        run(a.person, [s.strip() for s in a.steps.split(",") if s.strip()])
