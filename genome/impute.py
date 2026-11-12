"""Genotype imputation for a MyHeritage CSV, run locally with Beagle 5.5 and the 1000 Genomes phase 3 panel.

The file's ~585k SNPs are matched to the panel, and Beagle fills in every other panel variant from the haplotypes
they share with the panel's 2,504 people. Nothing leaves the machine.

    python -m genome.impute data/input/MyHeritage_raw_dna_data_XY.csv              # impute 1-22 and X, then --finalize
    python -m genome.impute data/input/MyHeritage_raw_dna_data_XY.csv --chroms 22   # one chromosome, for a quick test
    python -m genome.impute data/input/MyHeritage_raw_dna_data_XY.csv --validate 10 # measure accuracy -> calibration.json
    python -m genome.impute data/input/MyHeritage_raw_dna_data_XY.csv --calibrate   # rebuild calibration.json (no Beagle)
    python -m genome.impute data/input/MyHeritage_raw_dna_data_XY.csv --finalize    # rebuild the CSV (no Beagle)

Confidence. Every imputed call is judged by how often calls like it come back right when some of the person's own
measured SNPs are hidden and re-imputed (--validate). "Like it" means the same band of European allele frequency
(common >= 5%, uncommon 1-5%, rare < 1%), the same band of genotype probability (GP >= 0.99, 0.95, 0.90) and the same
direction: a call that carries the minor allele can be a false alarm, a call that doesn't can be false reassurance.

  measured      from the file itself
  high          calls like it were right >= 98% of the time
  medium        >= 90%
  low           < 90%
  untested      too few hidden SNPs like it to measure (treat as low)
  not_excluded  a "doesn't carry it" call in a band where imputation found < 90% of the real carriers: it means
                "not detected", never "not a carrier"

Needs Java 11+ and the reference files in data/reference/imputation (beagle.jar, plink.GRCh37.map.zip,
panel/chr*.1kg.phase3.v5a.b37.bref3, sites.vcf.gz); scripts/fetch_imputation_reference.sh downloads them.

Writes to data/output/imputation/<person>/:
  chr*.vcf.gz                                   Beagle's output (GT, DS, GP)
  MyHeritage_raw_dna_data_<person>.imputed.csv  measured calls plus imputed ones with GP >= --min-gp, in the
                                                MyHeritage layout plus SOURCE, GP, EUR_AF and CONFIDENCE columns,
                                                so any tool that takes a --dna CSV can read it
  validation_calls.tsv.gz, calibration.json     the hidden SNPs and the accuracy table built from them
  summary.json                                  counts per chromosome and per confidence tier
"""
import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "data", "reference", "imputation")
OUT = os.path.join(ROOT, "data", "output", "imputation")
CHROMS = [str(c) for c in range(1, 23)] + ["X"]
ORDER = {c: i for i, c in enumerate(CHROMS)}
COMP = str.maketrans("ACGT", "TGCA")
# Reference panels. A panel's files can live anywhere (the high-coverage panel is 15+ GB, on another disk): set
# DNA_PANEL_DIR_<NAME> to move one. `par` are chrX's pseudo-autosomal bounds on the panel's build: a man is diploid
# only outside (par[0], par[1]).
PANELS = {
    "1kg_phase3": {
        "label": "1000 Genomes phase 3 v5a (GRCh37)", "build": "GRCh37", "samples": 2504,
        "dir": os.path.join(REF, "panel"), "file": "chr{c}.1kg.phase3.v5a.b37.bref3", "contig": "{c}",
        "map_zip": "plink.GRCh37.map.zip", "map": "plink.chr{c}.GRCh37.map", "par": (2699520, 154931043),
    },
    "1kgp_hc": {
        "label": "1000 Genomes high coverage, 3,202 samples (GRCh38)", "build": "GRCh38", "samples": 3202,
        "dir": r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38\bref3", "file": "chr{c}.bref3", "contig": "chr{c}",
        "map_zip": "plink.GRCh38.map.zip", "map": "chr_in_chrom_field/plink.chrchr{c}.GRCh38.map",
        "par": (2781479, 155701383),
        # Men are diploid in the PARs and haploid between them, and Beagle wants one ploidy per sample per file, so
        # chrX is converted and imputed in three parts (scripts/fetch_1kgp_hc_panel.sh)
        "x_parts": [("chrX_par1", "chrX:1-2781479"), ("chrX", "chrX:2781480-155701382"),
                    ("chrX_par2", "chrX:155701383-156040895")],
    },
}
DEFAULT_PANEL = "1kg_phase3"
PAR = PANELS[DEFAULT_PANEL]["par"]  # GRCh37, the build of consumer raw files


def panel(name=DEFAULT_PANEL):
    """A panel's settings, its directory taken from DNA_PANEL_DIR_<NAME> when that is set."""
    p = dict(PANELS[name], name=name)
    p["dir"] = os.environ.get(f"DNA_PANEL_DIR_{name.upper()}", p["dir"])
    # The site list (positions, alleles, rsIDs, population frequencies) sits next to the panel's folder
    p["sites"] = os.path.normpath(os.path.join(p["dir"], "..", "sites.vcf.gz"))
    return p
EUR_AF = re.compile(r"(?:^|;)EUR_AF=([\d.e-]+)(?:;|$)")

HIGH, MEDIUM = 0.98, 0.90   # accuracy needed for the tiers
MIN_SENSITIVITY = 0.90      # share of real carriers a band must find before its "doesn't carry it" calls count
MIN_N = 100                 # hidden SNPs a cell needs before its accuracy is trusted


def person_of(path):
    from genome.loader import person_label
    return person_label(path)


def read_csv(path, chroms):
    """{chrom: [(pos, rsid, genotype)]} for 2-letter ACGT calls, from any raw file genome/formats.py reads."""
    from genome import formats
    out = {c: [] for c in chroms}
    for rsid, chrom, pos, gt in formats.rows(path):
        if chrom in out and pos is not None and len(gt) == 2 and set(gt) <= set("ACGT"):
            out[chrom].append((pos, rsid, gt))
    for rows in out.values():
        rows.sort()
    return out


def is_male(x_rows, par=PAR):
    """Men have one X, so outside the PAR their X calls are (almost) all homozygous."""
    body = [g for pos, _, g in x_rows if par[0] < pos < par[1]]
    return bool(body) and sum(g[0] != g[1] for g in body) / len(body) < 0.01


def panel_sites(wanted, cache, path=None):
    """{(chrom, pos): [(ref, alt, id)]} of 1000 Genomes biallelic SNVs at the wanted positions.

    Streams the panel's site list once and caches the matches."""
    path = path or panel()["sites"]
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(path):  # rebuilt with the site list
        sites = {}
        with gzip.open(cache, "rt") as f:
            for line in f:
                c, pos, ref, alt, vid = line.rstrip("\n").split("\t")
                sites.setdefault((c, int(pos)), []).append((ref, alt, vid))
        return sites
    keys = {f"{c}\t{p}" for c, p in wanted}
    sites = {}
    print("Reading the 1000 Genomes site list (once; takes a few minutes)...")
    with gzip.open(path, "rt") as f, gzip.open(cache, "wt") as out:
        for line in f:
            if line[0] == "#":
                continue
            c, pos, vid, ref, alt = line.split("\t", 5)[:5]
            if f"{c}\t{pos}" not in keys or len(ref) != 1 or len(alt) != 1:
                continue
            sites.setdefault((c, int(pos)), []).append((ref, alt, vid))
            out.write(f"{c}\t{pos}\t{ref}\t{alt}\t{vid}\n")
    return sites


class Freqs:
    """European allele frequencies of the panel's SNVs, read in step with position-sorted files.

    at() must be called in file order: chromosomes 1-22 then X, positions ascending within each. ids holds the rsIDs
    the site list gives for the last position asked about (the high-coverage panel's own IDs are chrom:pos:ref:alt)."""

    def __init__(self, path=None):
        self.path = path or panel()["sites"]
        self.it = self._read()
        self.cur = next(self.it, None)
        self.last = (None, None, {})
        self.ids = {}

    def _read(self):
        with gzip.open(self.path, "rt") as f:
            for line in f:
                if line[0] == "#":
                    continue
                p = line.split("\t", 8)
                if len(p[3]) == 1 and len(p[4]) == 1 and p[0] in ORDER:
                    yield ORDER[p[0]], int(p[1]), p[3], p[4], p[7], p[2]

    def at(self, chrom, pos):
        """{(ref, alt): EUR allele frequency of alt} at chrom:pos."""
        if self.last[:2] == (chrom, pos):
            return self.last[2]
        o = ORDER[chrom]
        while self.cur and (self.cur[0], self.cur[1]) < (o, pos):
            self.cur = next(self.it, None)
        found, self.ids = {}, {}
        while self.cur and self.cur[0] == o and self.cur[1] == pos:
            m = EUR_AF.search(self.cur[4])
            found[(self.cur[2], self.cur[3])] = float(m.group(1)) if m else None
            if self.cur[5].startswith("rs"):
                self.ids[(self.cur[2], self.cur[3])] = self.cur[5]
            self.cur = next(self.it, None)
        self.last = (chrom, pos, found)
        return found


def lift_calls(calls, chain=None):
    """A MyHeritage file's GRCh37 calls moved to GRCh38 with UCSC's chain file: ({chrom: [(pos, rsid, genotype)]},
    Counter of calls that couldn't be placed). A call is dropped when its position doesn't map, maps to more than one
    place or to another chromosome; a call that lands on the minus strand is complemented, so it stays forward."""
    from pyliftover import LiftOver
    lo = LiftOver(chain or os.path.join(REF, "hg19ToHg38.over.chain.gz"))
    out, lost = {c: [] for c in calls}, Counter()
    for c, rows in calls.items():
        for pos, rsid, gt in rows:
            hits = lo.convert_coordinate(f"chr{c}", pos - 1)
            if not hits:
                lost["unmapped"] += 1
            elif len(hits) > 1:
                lost["ambiguous"] += 1
            elif hits[0][0] != f"chr{c}":
                lost["other chromosome"] += 1
            else:
                out[c].append((hits[0][1] + 1, rsid, gt if hits[0][2] == "+" else gt.translate(COMP)))
    for rows in out.values():
        rows.sort()
    return out, lost


def harmonize(gt, ref, alt):
    """Allele indexes of a forward-strand call against a panel site, or None when it doesn't fit.

    MyHeritage reports the + strand, so a call is first read as is; the complement is a fallback for the odd
    reverse-strand entry, never tried on A/T or C/G sites where it can't be told apart."""
    alleles = {ref: 0, alt: 1}
    if gt[0] in alleles and gt[1] in alleles:
        return alleles[gt[0]], alleles[gt[1]], False
    if {ref, alt} in ({"A", "T"}, {"C", "G"}):
        return None
    f = gt.translate(COMP)
    if f[0] in alleles and f[1] in alleles:
        return alleles[f[0]], alleles[f[1]], True
    return None


# --- confidence -------------------------------------------------------------------------------------------------

def freq_band(af):
    if af is None:
        return "unknown"
    maf = min(af, 1 - af)
    return "common" if maf >= 0.05 else "uncommon" if maf >= 0.01 else "rare"


def gp_band(gp):
    return "0.99" if gp >= 0.99 else "0.95" if gp >= 0.95 else "0.90" if gp >= 0.90 else "below"


def carries_minor(alt_copies, af):
    """Whether a genotype holds the population's minor allele (alt, unless alt is the more common one)."""
    if af is None:
        return alt_copies > 0
    return (alt_copies if af <= 0.5 else 2 - alt_copies) > 0


def tier(cal, af, gp, alt_copies):
    if cal is None:
        return "uncalibrated"
    band, carrier = freq_band(af), carries_minor(alt_copies, af)
    if not carrier:
        sens = cal["sensitivity"].get(band)
        if not sens or sens["n"] < MIN_N or sens["rate"] < MIN_SENSITIVITY:
            return "not_excluded"
    cell = cal["cells"].get(f"{band}|{gp_band(gp)}|{'carrier' if carrier else 'noncarrier'}")
    if not cell or cell["n"] < MIN_N:
        return "untested"
    return "high" if cell["rate"] >= HIGH else "medium" if cell["rate"] >= MEDIUM else "low"


def calibrate(calls, min_gp):
    """Accuracy table from hidden SNPs: [(truth_alt_copies, imputed_alt_copies, gp, af)]."""
    cells, sens = {}, {}
    for truth, imputed, gp, af in calls:
        band = freq_band(af)
        if gp < min_gp:  # dropped from the CSV, so it neither alarms nor reassures
            continue
        if carries_minor(truth, af):  # a real carrier with a confident call: was it called a carrier?
            s = sens.setdefault(band, {"n": 0, "found": 0})
            s["n"] += 1
            s["found"] += carries_minor(imputed, af)
        key = f"{band}|{gp_band(gp)}|{'carrier' if carries_minor(imputed, af) else 'noncarrier'}"
        c = cells.setdefault(key, {"n": 0, "right": 0})
        c["n"] += 1
        c["right"] += imputed == truth
    for c in cells.values():
        c["rate"] = round(c["right"] / c["n"], 4)
    for s in sens.values():
        s["rate"] = round(s["found"] / s["n"], 4)
    return {"min_gp": min_gp, "thresholds": {"high": HIGH, "medium": MEDIUM, "min_sensitivity": MIN_SENSITIVITY,
                                             "min_n": MIN_N}, "cells": dict(sorted(cells.items())), "sensitivity": sens}


def print_calibration(cal):
    print(f"\n{'frequency':>9} {'GP':>5} {'call':>10} {'right':>8} {'n':>7}   tier")
    for key, c in cal["cells"].items():
        band, gpb, kind = key.split("|")
        t = "untested" if c["n"] < MIN_N else "high" if c["rate"] >= HIGH else "medium" if c["rate"] >= MEDIUM else "low"
        print(f"{band:>9} {gpb:>5} {kind:>10} {c['rate']:8.1%} {c['n']:7,}   {t}")
    print("\nReal carriers with a confident call (GP >= %.2f) that were called carriers:" % cal["min_gp"])
    for band, s in cal["sensitivity"].items():
        ok = s["n"] >= MIN_N and s["rate"] >= MIN_SENSITIVITY
        print(f"{band:>9}: {s['rate']:6.1%} of {s['n']:,}   " + ("'doesn't carry it' calls count" if ok else "-> not_excluded"))


# --- Beagle -----------------------------------------------------------------------------------------------------

def write_target(path, person, chrom, rows, sites, male, mask_every=0, P=None):
    P = P or panel()
    par, contig = P["par"], P["contig"].format(c=chrom)
    stats = {"calls": len(rows), "matched": 0, "flipped": 0, "not_in_panel": 0, "mismatch": 0, "male_x_het": 0}
    masked = {}
    with open(path, "w", newline="\n") as f:
        f.write("##fileformat=VCFv4.2\n##FORMAT=<ID=GT,Number=1,Type=String,Description=\"Genotype\">\n")
        f.write(f"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{person}\n")
        seen = set()
        for pos, rsid, gt in rows:
            options = sites.get((chrom, pos))
            if not options or len(options) > 1:
                stats["not_in_panel"] += 1
                continue
            ref, alt, _ = options[0]
            h = harmonize(gt, ref, alt)
            if h is None:
                stats["mismatch"] += 1
                continue
            a, b, flipped = h
            if pos in seen:
                continue
            seen.add(pos)
            if male and chrom == "X" and par[0] < pos < par[1] and a != b:
                stats["male_x_het"] += 1  # a man can't be heterozygous here; leave it to Beagle
                continue
            stats["matched"] += 1
            stats["flipped"] += flipped
            if mask_every and stats["matched"] % mask_every == 0:
                masked[(pos, ref, alt)] = a + b  # hidden: Beagle imputes it and held_out() compares
                continue
            f.write(f"{contig}\t{pos}\t{rsid}\t{ref}\t{alt}\t.\tPASS\t.\tGT\t{a}/{b}\n")
    return stats, masked


def records(vcf):
    """(pos, id, ref, alt, imputed?, alt copies, best GP) per biallelic SNV in a Beagle output file."""
    with gzip.open(vcf, "rt") as f:
        for line in f:
            if line[0] == "#":
                continue
            _, pos, vid, ref, alt, _, _, info, fmt, sample = line.rstrip("\n").split("\t")
            if len(ref) != 1 or len(alt) != 1:  # indels and multi-allelic sites don't fit the 2-letter layout
                continue
            values = dict(zip(fmt.split(":"), sample.split(":")))
            copies = sum(int(x) for x in re.split(r"[|/]", values["GT"]))
            gp = max(float(x) for x in values["GP"].split(",")) if "GP" in values else 1.0
            yield int(pos), vid, ref, alt, "IMP" in info.split(";"), copies, gp


def held_out(vcf, chrom, masked):
    """[(chrom, pos, ref, alt, truth, imputed, gp)] for the hidden SNPs."""
    return [(chrom, pos, ref, alt, masked[(pos, ref, alt)], copies, gp)
            for pos, _, ref, alt, _, copies, gp in records(vcf) if (pos, ref, alt) in masked]


def remove(path):
    """Delete a temporary file. On Windows a virus scanner can hold a file Beagle just wrote for a moment, so retry,
    and leave it in place rather than stop the run."""
    for wait in (0.5, 1, 2, 4, 8):
        try:
            os.remove(path)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            time.sleep(wait)
    print(f"  (could not delete {os.path.basename(path)}; it is locked by another program, delete it later)")


def genetic_map(chrom, P=None):
    """The genetic map for the panel's build, unpacked next to its zip on first use."""
    P = P or panel()
    member = P["map"].format(c=chrom)
    path = os.path.join(REF, os.path.basename(member))
    if not os.path.exists(path):
        with zipfile.ZipFile(os.path.join(REF, P["map_zip"])) as z:
            with z.open(member) as src, open(path, "wb") as dst:
                dst.write(src.read())
    return path


def parts(chrom, P):
    """[(name, panel file, region)]: the Beagle runs that make up one chromosome, in position order. One, except chrX
    on a panel that splits it at the pseudo-autosomal boundaries. Outputs are <name>.vcf.gz."""
    if chrom == "X" and P.get("x_parts"):
        return [(n, os.path.join(P["dir"], f"{n}.bref3"), region) for n, region in P["x_parts"]]
    return [(f"chr{chrom}", os.path.join(P["dir"], P["file"].format(c=chrom)), None)]


def in_region(target, region):
    """Whether the target VCF has any marker inside chrom:start-end (Beagle stops when a region has none)."""
    start, end = map(int, region.split(":")[1].split("-"))
    with open(target) as f:
        return any(start <= int(l.split("\t", 2)[1]) <= end for l in f if l[0] != "#")


def run_beagle(target, chrom, out_dir, threads, memory, P=None, tag=""):
    """Imputes one chromosome; returns Beagle's output files (<out_dir>/<tag><part>.vcf.gz), in position order."""
    P = P or panel()
    outs = []
    for name, ref, region in parts(chrom, P):
        if not os.path.exists(ref):
            sys.exit(f"No {P['label']} file for {name} at {ref}; set DNA_PANEL_DIR_{P['name'].upper()} to its folder")
        if region and not in_region(target, region):
            continue
        prefix = os.path.join(out_dir, tag + name)
        cmd = ["java", f"-Xmx{memory}", "-jar", os.path.join(REF, "beagle.jar"), f"gt={target}", f"ref={ref}",
               f"map={genetic_map(chrom, P)}", f"out={prefix}", f"nthreads={threads}", "gp=true"]
        if region:
            cmd.append(f"chrom={region}")
        log = subprocess.run(cmd, capture_output=True, text=True)
        if log.returncode != 0:
            sys.exit(f"Beagle failed on {name}:\n{log.stdout[-2000:]}\n{log.stderr[-2000:]}")
        outs.append(prefix + ".vcf.gz")
    return outs


def outputs(out_dir, chrom, P):
    """Beagle's saved output for one chromosome, the parts that exist, in position order."""
    return [f for f in (os.path.join(out_dir, n + ".vcf.gz") for n, _, _ in parts(chrom, P)) if os.path.exists(f)]


# --- steps ------------------------------------------------------------------------------------------------------

def run_validate(args, person, out_dir, calls, sites, male, chroms):
    hidden = []
    for chrom in chroms:
        target = os.path.join(out_dir, f"validate.chr{chrom}.vcf")
        _, masked = write_target(target, person, chrom, calls[chrom], sites, male, args.validate, args.P)
        outs = run_beagle(target, chrom, out_dir, args.threads, args.memory, args.P, tag="validate.")
        rows = [r for vcf in outs for r in held_out(vcf, chrom, masked)]
        for f in [target] + outs + [vcf[:-len(".vcf.gz")] + ".log" for vcf in outs]:
            remove(f)
        hidden += rows
        print(f"chr{chrom}: {sum(r[4] == r[5] for r in rows):,}/{len(rows):,} hidden calls recovered", flush=True)
    with gzip.open(os.path.join(out_dir, "validation_calls.tsv.gz"), "wt") as f:
        f.write("chrom\tpos\tref\talt\ttruth\timputed\tgp\n")
        for r in hidden:
            f.write("\t".join(map(str, r)) + "\n")
    run_calibrate(args, out_dir)


def run_calibrate(args, out_dir):
    """Attach frequencies to the hidden SNPs and build calibration.json."""
    with gzip.open(os.path.join(out_dir, "validation_calls.tsv.gz"), "rt") as f:
        next(f)
        hidden = [(c, int(p), r, a, int(t), int(i), float(g)) for c, p, r, a, t, i, g in (l.rstrip("\n").split("\t") for l in f)]
    hidden.sort(key=lambda r: (ORDER[r[0]], r[1]))
    print("Looking up allele frequencies...", flush=True)
    freqs = Freqs(args.P["sites"])
    rows = [(t, i, g, freqs.at(c, p).get((r, a))) for c, p, r, a, t, i, g in hidden]
    cal = calibrate(rows, args.min_gp)
    cal["hidden"] = len(rows)
    json.dump(cal, open(os.path.join(out_dir, "calibration.json"), "w"), indent=1)
    print_calibration(cal)


def run_finalize(args, person, out_dir, calls, chroms):
    """Merged CSV with frequencies and confidence tiers, from Beagle's saved output."""
    cal_path = os.path.join(out_dir, "calibration.json")
    cal = json.load(open(cal_path)) if os.path.exists(cal_path) else None
    if cal is None:
        print("No calibration.json yet (run --validate): confidence will read 'uncalibrated'.")
    summary_path = os.path.join(out_dir, "summary.json")
    summary = json.load(open(summary_path)) if os.path.exists(summary_path) else {"chroms": {}}
    summary.update({"person": person, "min_gp": args.min_gp, "calibrated": cal is not None})
    freqs = Freqs(args.P["sites"])
    tiers, carrier_tiers = Counter(), Counter()
    csv = os.path.join(out_dir, f"MyHeritage_raw_dna_data_{person}.imputed.csv")
    with open(csv, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Imputed from {person}'s MyHeritage file with Beagle 5.5 and the {args.P['label']} panel; "
                f"forward strand, {args.P['build']}.\n")
        f.write(f"# Imputed rows have GP >= {args.min_gp}. EUR_AF is the 1000 Genomes European frequency of the alternative allele.\n")
        f.write("# CONFIDENCE: measured, high, medium, low, untested, not_excluded (see genome/impute.py).\n")
        f.write("RSID,CHROMOSOME,POSITION,RESULT,SOURCE,GP,EUR_AF,CONFIDENCE\n")
        for chrom in chroms:
            vcfs = outputs(out_dir, chrom, args.P)
            if not vcfs:
                continue
            measured = {pos: (rsid, gt) for pos, rsid, gt in calls[chrom]}
            rows, kept, imputed = {}, 0, 0
            for pos, vid, ref, alt, imp, copies, gp in (r for vcf in vcfs for r in records(vcf)):
                af = freqs.at(chrom, pos).get((ref, alt))
                if not imp:
                    if pos in measured:
                        rsid, gt = measured[pos]
                        rows[pos] = (rsid, gt, "measured", "", "" if af is None else f"{af:g}", "measured")
                    continue
                imputed += 1
                vid = freqs.ids.get((ref, alt), vid)  # the site list's rsID where the panel has only chrom:pos:ref:alt
                if gp < args.min_gp or not vid.startswith("rs") or pos in measured:
                    continue
                gt = (ref + ref, ref + alt, alt + alt)[copies]
                t = tier(cal, af, gp, copies)
                tiers[t] += 1
                if carries_minor(copies, af):
                    carrier_tiers[t] += 1
                rows[pos] = (vid.split(";")[0], gt, "imputed", f"{gp:.2f}", "" if af is None else f"{af:g}", t)
                kept += 1
            for pos, (rsid, gt) in measured.items():  # measured calls the panel doesn't have
                rows.setdefault(pos, (rsid, gt, "measured", "", "", "measured"))
            for pos in sorted(rows):
                rsid, gt, source, gp, af, t = rows[pos]
                f.write(f'"{rsid}","{chrom}","{pos}","{gt}",{source},{gp},{af},{t}\n')
            s = summary["chroms"].setdefault(chrom, {})
            s.update({"calls": len(calls[chrom]), "imputed": imputed, "imputed_kept": kept})
            print(f"chr{chrom}: {kept:,} imputed calls kept", flush=True)
    summary["tiers"] = dict(tiers)
    summary["carrier_tiers"] = dict(carrier_tiers)
    summary["totals"] = {k: sum(s.get(k, 0) for s in summary["chroms"].values()) for k in ("calls", "imputed", "imputed_kept")}
    json.dump(summary, open(summary_path, "w"), indent=1)
    print(f"\nWrote {csv}\nImputed calls by confidence (all / carrying the minor allele):")
    for t, n in tiers.most_common():
        print(f"{t:>13}: {n:>12,} / {carrier_tiers[t]:,}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dna", help="raw data file from MyHeritage, AncestryDNA or 23andMe (GRCh37; zipped or gzipped is fine)")
    ap.add_argument("--chroms", default=",".join(CHROMS), help="comma-separated, default 1-22 and X")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--memory", default="12g", help="Java heap for Beagle")
    ap.add_argument("--min-gp", type=float, default=0.9, help="probability of the best genotype needed to keep a call")
    from genome import build as gbuild
    ap.add_argument("--panel", choices=list(PANELS), default=gbuild.panel_name(),
                    help="reference panel, by default the one for the build in genome/build.py (DNA_BUILD); output for "
                         f"a panel other than {DEFAULT_PANEL} goes to <person>/<panel>/")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--validate", type=int, default=0, metavar="N",
                      help="hide every Nth measured SNP, re-impute it and build calibration.json (no CSV)")
    mode.add_argument("--calibrate", action="store_true", help="rebuild calibration.json from the last --validate")
    mode.add_argument("--finalize", action="store_true", help="rebuild the CSV from Beagle's saved output")
    args = ap.parse_args()

    chroms = [c.strip().upper().replace("CHR", "") for c in args.chroms.split(",")]
    chroms.sort(key=ORDER.__getitem__)  # frequencies are read in file order
    person = person_of(args.dna)
    args.P = P = panel(args.panel)
    out_dir = os.path.join(OUT, person) if P["name"] == DEFAULT_PANEL else os.path.join(OUT, person, P["name"])
    os.makedirs(out_dir, exist_ok=True)
    if args.calibrate:
        return run_calibrate(args, out_dir)

    calls = read_csv(args.dna, CHROMS)  # all chromosomes, so the site cache covers any later run
    lost = Counter()
    if P["build"] != "GRCh37":  # consumer raw files are GRCh37
        calls, lost = lift_calls(calls)
    if args.finalize:
        return run_finalize(args, person, out_dir, calls, chroms)

    male = is_male(calls["X"], P["par"])
    wanted = {(c, pos) for c, rows in calls.items() for pos, _, _ in rows}
    cache = f"sites_{person}.tsv.gz" if P["name"] == DEFAULT_PANEL else f"sites_{person}_{P['name']}.tsv.gz"
    sites = panel_sites(wanted, os.path.join(REF, cache), P["sites"])
    # A file on another genome build lands on the wrong positions: almost none would match (MyHeritage: 98.7%)
    hit = sum(1 for w in wanted if w in sites) / max(len(wanted), 1)
    if hit < 0.7:
        raise SystemExit(f"Only {hit:.0%} of {os.path.basename(args.dna)}'s positions are 1000 Genomes sites; raw files "
                         "are expected on GRCh37 (build 37). Is this file on another build?")
    if args.validate:
        return run_validate(args, person, out_dir, calls, sites, male, chroms)

    summary = {"person": person, "source": os.path.basename(args.dna), "male": male, "panel": P["label"],
               "build": P["build"], "not_lifted": dict(lost), "chroms": {}}
    if lost:
        print(f"{sum(lost.values()):,} calls couldn't be moved to {P['build']}: {dict(lost)}")
    for chrom in chroms:
        target = os.path.join(out_dir, f"target.chr{chrom}.vcf")
        stats, _ = write_target(target, person, chrom, calls[chrom], sites, male, P=P)
        print(f"chr{chrom}: {stats['matched']:,} of {stats['calls']:,} calls match the panel; imputing...", flush=True)
        run_beagle(target, chrom, out_dir, args.threads, args.memory, P)
        remove(target)
        summary["chroms"][chrom] = stats
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w"), indent=1)
    run_finalize(args, person, out_dir, calls, chroms)


if __name__ == "__main__":
    main()
