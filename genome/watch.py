"""The variants where "not detected, not excluded" can matter: those ClinVar or ClinPGx list.

genome/impute.py writes an imputed "doesn't carry it" call it can't trust (tier not_excluded: a rare variant, in a band
where imputation misses too many real carriers) only for these. Elsewhere the call says nothing, and leaving it out
keeps the imputed file about a tenth of its size. The list comes from reference files only (genome/references.json):

  ClinVar       every variant with an rsID (disease-causing, risk factor, drug response ...)
  ClinPGx       every rsID in the clinical and variant annotations (the drug genes and their star alleles)

    python -m genome.watch      # how many rsIDs, and whether the drug genes' star-allele SNPs are among them
"""
import csv
import gzip
import io
import os
import re
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLINPGX = [os.path.join(ROOT, "data", "reference", f) for f in ("clinpgx_clinical_annotations.zip", "clinpgx_variant_annotations.zip")]
RS = re.compile(r"\brs\d+\b")
CLINVAR_RS = re.compile(r"(?:^|;)RS=(\d+)")


def clinvar_rsids(path=None):
    from genome import build as gbuild
    out = set()
    with gzip.open(path or gbuild.path("clinvar"), "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            m = CLINVAR_RS.search(line.split("\t", 8)[7])
            if m:
                out.add("rs" + m.group(1))
    return out


def clinpgx_rsids(paths=CLINPGX):
    out = set()
    for path in paths:
        if not os.path.exists(path):
            continue
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith(".tsv"):
                    for line in io.TextIOWrapper(z.open(name), encoding="utf-8"):
                        out.update(RS.findall(line))
    return out


def rsids():
    """Every rsID ClinVar or ClinPGx lists."""
    return clinvar_rsids() | clinpgx_rsids()


if __name__ == "__main__":
    ids = rsids()
    print(f"{len(ids):,} rsIDs listed by ClinVar or ClinPGx")
    try:
        from cluster_analysis.medicines.medicines import STAR, HLA_TAGS, SNP_GENES
        need = {rs for defs in STAR.values() for _, rs, _, _ in defs} | {rs for rs, _ in HLA_TAGS.values()} | set(SNP_GENES.values())
        missing = sorted(need - ids)
        print(f"drug-gene SNPs: {len(need) - len(missing)} of {len(need)} listed" + (f"; missing {missing}" if missing else ""))
    except ImportError:
        pass
