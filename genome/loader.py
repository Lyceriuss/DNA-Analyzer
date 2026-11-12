# genome/loader.py
import os
import re

# Imputed files (genome/impute.py) grade every call. Single-SNP conclusions (the library, drug response, pathogenic
# variants) only take calls that are measured or imputed at high confidence.
CONFIDENT = ("measured", "high")


def person_label(path):
    """XY from data/input/MyHeritage_raw_dna_data_XY.csv, and from its imputed version too; otherwise the file's name
    without its extensions (data/input/XX.txt.zip -> XX)."""
    name = re.sub(r"^MyHeritage_raw_dna_data_", "", os.path.basename(path or ""))
    return re.sub(r"(\.imputed)?(\.(csv|txt|tsv))?(\.(gz|zip))?$", "", name, flags=re.I)


def imputed_path(path):
    """The imputed version of a raw data file (genome/impute.py) on the build in genome/build.py, or the file itself
    when it hasn't been imputed (GRCh37 only: a raw MyHeritage file is GRCh37, so on GRCh38 it must be imputed)."""
    from genome import build as gbuild
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    person = person_label(path)
    folder = os.path.join(root, "data", "output", "imputation", person)
    if gbuild.panel_name() != "1kg_phase3":
        folder = os.path.join(folder, gbuild.panel_name())
    p = os.path.join(folder, f"MyHeritage_raw_dna_data_{person}.imputed.csv")
    if path and os.path.exists(p):
        return p
    if path and gbuild.BUILD != "GRCh37":
        raise SystemExit(f"{person} has no {gbuild.BUILD} imputation yet: python -m genome.impute {path} --panel {gbuild.panel_name()}")
    return path


def read_calls(filepath, rsids=None, confidence=CONFIDENT):
    """Stream a DNA raw data file: {rsid: (genotype, chrom, pos, confidence)}.

    Reads MyHeritage, AncestryDNA and 23andMe files (genome/formats.py) and the imputed CSVs written by
    genome/impute.py, whose CONFIDENCE column says how far each call can be trusted. Files without that column are
    all "measured". rsids limits the result to those SNPs (an imputed file holds ~28 million); confidence limits it
    to those tiers (None keeps every call). When an rsID appears twice, the last row wins.
    """
    return {rsid: (gt, chrom, pos, tier) for rsid, chrom, pos, gt, tier in iter_calls(filepath, rsids, confidence)}


def iter_calls(filepath, rsids=None, confidence=CONFIDENT):
    """(rsid, chrom, pos, genotype, confidence) per row of a DNA raw data file; see read_calls."""
    from genome import formats
    if formats.detect(filepath) != "imputed":  # a test's own file: every call is measured
        if confidence is not None and "measured" not in confidence:
            return
        for rsid, chrom, pos, gt in formats.rows(filepath):
            if rsids is None or rsid in rsids:
                yield rsid, chrom, pos, gt, "measured"
        return
    cols = None
    with open(filepath, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[0] == "#" or not line.strip():
                continue
            sep = "\t" if "\t" in line else ","
            if rsids is not None and cols is not None and line[:line.find(sep)].strip().strip('"') not in rsids:
                continue  # cheap skip before splitting the whole row
            p = [x.strip().strip('"') for x in line.rstrip("\r\n").split(sep)]
            if cols is None and p[0].upper() in ("RSID", "# RSID"):
                cols = {c.upper(): i for i, c in enumerate(p)}
                continue
            if cols is None:  # no header: rsid, chromosome, position, genotype
                cols = {"RSID": 0, "CHROMOSOME": 1, "POSITION": 2, "RESULT": 3}
            rsid = p[cols["RSID"]]
            if rsids is not None and rsid not in rsids:
                continue
            tier = p[cols["CONFIDENCE"]] if "CONFIDENCE" in cols and len(p) > cols["CONFIDENCE"] else "measured"
            if confidence is not None and tier not in confidence:
                continue
            res = cols.get("RESULT", cols.get("GENOTYPE", 3))
            if len(p) <= res or not p[res]:
                continue
            pos = p[cols["POSITION"]] if "POSITION" in cols and len(p) > cols["POSITION"] else ""
            yield rsid, p[cols["CHROMOSOME"]] if "CHROMOSOME" in cols else "", int(pos) if pos.isdigit() else None, p[res], tier


def load_dna_file(filepath, rsids=None, confidence=CONFIDENT):
    """
    Loads a DNA raw data file (CSV/TXT) and returns a dictionary mapping RSID -> Genotype.
    Handles MyHeritage, AncestryDNA and 23andMe files and imputed files (see read_calls); pass rsids to read only those SNPs.
    """
    if not os.path.exists(filepath):
        print(f"❌ Error: File not found at {filepath}")
        return {}
    try:
        calls = read_calls(filepath, rsids, confidence)
    except Exception as e:
        print(f"❌ Critical Error loading file: {e}")
        return {}
    if not calls:
        print(f"❌ Error: no genotypes read from {os.path.basename(filepath)} (expected RSID and RESULT columns)")
        return {}
    print(f"✅ Successfully loaded {len(calls)} SNPs from {os.path.basename(filepath)}")
    return {rsid: c[0] for rsid, c in calls.items()}
