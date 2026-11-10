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
  overlay    overlay.py    -> hp_modules, hp_links, hp_bridges, hp_tilts (Profile tab)

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
STEPS = ("themes", "genes", "medicines", "nutrition", "labtests", "overlay")
THEME_SEX = {"XX": "female", "XY": "male"}   # theme_graph.py marks a theme's body layout as XX or XY


def load():
    return json.load(open(PATH, encoding="utf-8"))["profiles"]


def get(pid):
    return next((p for p in load() if p["id"] == pid), None)


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
    for p in load():
        h = x_heterozygosity(p["dna"])
        dna_sex = None if h is None else "female" if h > 0.05 else "male"
        flag = "" if dna_sex in (None, p["sex"]) else f"  <- profiles.json says {p['sex']}"
        print(f"{p['id']}: X heterozygosity {h:.3f} -> {dna_sex}{flag}" if h is not None else f"{p['id']}: no X calls")


def run(pids, steps):
    py = [sys.executable, "-m"]
    for p in load():
        if pids and p["id"] not in pids:
            continue
        od = out_dir(p["id"])
        themes = [g["theme"] for g in theme_graphs() if applies(g.get("sex"), p["sex"])]
        cmds = []
        if "themes" in steps:
            cmds += [py + ["cluster_analysis.themes.theme_graph", t, "--dna", p["dna"]] for t in themes]
        if "genes" in steps:
            cmds.append(py + ["cluster_analysis.evidence.gene_calls", "--person", p["id"]])
        if "medicines" in steps:
            cmds.append(py + ["cluster_analysis.medicines.medicines", "--dna", p["dna"], "--out-dir", od])
        if "nutrition" in steps:
            cmds.append(py + ["cluster_analysis.nutrition.nutrition", "--dna", p["dna"], "--out-dir", od,
                              "--sex", "women" if p["sex"] == "female" else "men"])
        if "labtests" in steps:
            cmds.append(py + ["cluster_analysis.nutrition.nutrition", "--config", "cluster_analysis/nutrition/labtests.json", "--prefix", "lab",
                              "--dna", p["dna"], "--out-dir", od, "--sex", "women" if p["sex"] == "female" else "men"])
        if "overlay" in steps:
            cmds.append(py + ["cluster_analysis.library.overlay", p["dna"], "--name", p["id"], "--dashboard", od])
        for c in cmds:
            print(f"\n== {p['id']}: {' '.join(c[2:])}", flush=True)
            subprocess.run(c, check=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})


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
