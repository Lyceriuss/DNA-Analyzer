"""Lite mode: a raw file's measured calls moved to the analysis build, without imputation.

    python -m genome.lite data/input/XX.csv

Consumer raw files are GRCh37; the analysis runs on GRCh38 (genome/build.py). Imputation moves the calls as it goes
(genome/impute.py); without it, this does the same move with the same chain file (impute.lift_calls) and writes the
file in the imputed CSV's format, every row "measured", next to where the imputed file would be:
data/output/imputation/<person>/<panel>/MyHeritage_raw_dna_data_<person>.measured.csv. genome/loader.imputed_path
reads it when there is no imputed file, so the whole analysis runs on the measured calls. An imputation made later
takes its place. No Java, panel or large memory: under a minute.
"""
import argparse
import os

from genome import build as gbuild
from genome import impute
from genome.loader import person_label


def out_path(dna):
    person = person_label(dna)
    folder = os.path.join(impute.OUT, person)
    if gbuild.panel_name() != impute.DEFAULT_PANEL:
        folder = os.path.join(folder, gbuild.panel_name())
    return os.path.join(folder, f"MyHeritage_raw_dna_data_{person}.measured.csv")


def write(dna):
    person = person_label(dna)
    calls = impute.read_csv(dna, impute.CHROMS)
    lost = {}
    if gbuild.BUILD != "GRCh37":
        calls, lost = impute.lift_calls(calls)
    path = out_path(dna)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n = 0
    # Under a temporary name until complete (genome/loader.py never reads it): a stopped run leaves no partial file
    with open(path + impute.PARTIAL, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {person}'s measured calls only (lite mode, genome/lite.py), forward strand, {gbuild.BUILD}. No imputation.\n")
        f.write("RSID,CHROMOSOME,POSITION,RESULT,SOURCE,GP,EUR_AF,CONFIDENCE\n")
        for chrom in impute.CHROMS:
            for pos, rsid, gt in calls.get(chrom, []):
                f.write(f'"{rsid}","{chrom}","{pos}","{gt}",measured,,,measured\n')
                n += 1
    impute.publish(path + impute.PARTIAL, path)
    impute.dump_json({"person": person, "source": os.path.basename(dna), "build": gbuild.BUILD, "calls": n,
                      "not_lifted": dict(lost)}, os.path.join(os.path.dirname(path), "lite.json"))
    if lost:
        print(f"{sum(lost.values()):,} calls couldn't be moved to {gbuild.BUILD}: {dict(lost)}")
    print(f"{n:,} measured calls written to {path}")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dna")
    write(ap.parse_args().dna)
