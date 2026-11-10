"""The genome build the analysis runs on, and the reference files that go with it.

MyHeritage files are GRCh37. genome/impute.py can impute them on the GRCh37 1000 Genomes phase 3 panel or, moving
the calls to GRCh38 first, on the GRCh38 high-coverage panel. Everything after imputation reads positions from the
imputed file, so the gene coordinates, ClinVar, the site list and the PGS files must be on the same build. This module
is the one switch:

    python -m cluster_analysis.profiles run                       # GRCh38, the default
    DNA_BUILD=GRCh37 python -m cluster_analysis.profiles run      # the earlier GRCh37 analysis, for comparison
    python -m genome.build fetch                                  # download the GRCh38 reference files

GRCh38 with the high-coverage panel is the default since 2026-11-10, after its results were compared with GRCh37:
every medicine phenotype the same, twice the imputed variants. GRCh37 output stays in the unsuffixed folders.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "data", "reference")
BUILD = os.environ.get("DNA_BUILD", "GRCh38")

# url: where `fetch` downloads a file that isn't there yet
FILES = {
    "GRCh37": {
        "panel": "1kg_phase3",
        "clinvar": {"path": "clinvar_grch37.vcf.gz",
                    "url": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh37/clinvar.vcf.gz"},
        "gtf": {"path": "ensembl_grch37_genes.gtf.gz",
                "url": "https://ftp.ensembl.org/pub/grch37/release-115/gtf/homo_sapiens/Homo_sapiens.GRCh37.87.gtf.gz"},
        "pgs": "hmPOS_GRCh37",
        # chrX pseudo-autosomal regions (PAR1, PAR2): shared with Y, so heterozygous in men too
        "par": ((60_001, 2_699_520), (154_931_044, 155_260_560)),
    },
    "GRCh38": {
        "panel": "1kgp_hc",
        "clinvar": {"path": "clinvar_grch38.vcf.gz",
                    "url": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"},
        "gtf": {"path": "ensembl_grch38_genes.gtf.gz",
                "url": "https://ftp.ensembl.org/pub/release-115/gtf/homo_sapiens/Homo_sapiens.GRCh38.115.gtf.gz"},
        "pgs": "hmPOS_GRCh38",
        "par": ((10_001, 2_781_479), (155_701_383, 156_030_895)),
    },
}
if BUILD not in FILES:
    sys.exit(f"DNA_BUILD={BUILD}: use one of {', '.join(FILES)}")

# Personal results, kept apart per build so a GRCh38 run doesn't overwrite the GRCh37 one it is compared with
SUFFIX = "" if BUILD == "GRCh37" else f"_{BUILD}"
OUTPUT = f"data/output/cluster_analysis{SUFFIX}"
EXPLORER = f"data/output/explorer{SUFFIX}"


def path(name, build=None):
    """The reference file for this build, e.g. path("clinvar") -> data/reference/clinvar_grch38.vcf.gz."""
    return os.path.join(REF, FILES[build or BUILD][name]["path"])


def panel_name(build=None):
    return FILES[build or BUILD]["panel"]


def sites(build=None):
    """The panel's site list: positions, alleles, rsIDs and frequencies per 1000 Genomes superpopulation."""
    from genome.impute import panel
    return panel(panel_name(build))["sites"]


def pgs_suffix(build=None):
    return FILES[build or BUILD]["pgs"]


def par(build=None):
    return FILES[build or BUILD]["par"]


def cache(name, build=None):
    """A cache file that depends on positions, kept apart per build: pgx_pop_freqs.json -> pgx_pop_freqs_GRCh38.json."""
    b = build or BUILD
    if b == "GRCh37":
        return name
    stem, ext = os.path.splitext(name)
    return f"{stem}_{b}{ext}"


def fetch(build="GRCh38"):
    """Downloads this build's ClinVar and Ensembl gene file when missing (resumable)."""
    for name in ("clinvar", "gtf"):
        f = FILES[build][name]
        dst = os.path.join(REF, f["path"])
        if os.path.exists(dst):
            print(f"{f['path']}: already there")
            continue
        print(f"{f['path']} <- {f['url']}")
        subprocess.run(["curl", "-sS", "-f", "-C", "-", "--retry", "3", "-o", dst + ".part", f["url"]], check=True)
        os.replace(dst + ".part", dst)


if __name__ == "__main__":
    if sys.argv[1:2] == ["fetch"]:
        fetch(sys.argv[2] if len(sys.argv) > 2 else "GRCh38")
    else:
        print(f"build {BUILD}: panel {panel_name()}, sites {sites()}")
        for n in ("clinvar", "gtf"):
            print(f"  {n}: {path(n)}{'' if os.path.exists(path(n)) else '  (missing: python -m genome.build fetch)'}")
