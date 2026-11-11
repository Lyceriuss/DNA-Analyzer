"""The site list for the 1000 Genomes high-coverage panel: every variant's position, alleles, rsID and population
frequencies, in the layout genome/impute.py reads (the phase 3 sites.vcf.gz layout).

    python -m genome.panel_sites                     # all chromosomes -> <panel folder>/sites.vcf.gz
    python -m genome.panel_sites --chroms 22 --out sites_chr22.vcf.gz

Frequencies come from the panel itself (its INFO fields over the 2,504 unrelated samples: AF_EUR_unrel and the rest),
read straight from the raw VCFs in Python (genome/vcf.py; no Docker). The panel names its variants chrom:pos:ref:alt,
so rsIDs come from Ensembl's GRCh38 variation files (dbSNP), joined on position and alleles:
    <reference>/ensembl_grch38/homo_sapiens-chr<N>.vcf.gz   all of dbSNP for that chromosome, used when present
    <reference>/ensembl_grch38/1000GENOMES-phase_3.vcf.gz     otherwise: the phase 3 variants placed on GRCh38
Both inputs are sorted by position, so they are merged in one pass without holding either in memory.
"""
import argparse
import gzip
import os
import time
from collections import Counter

from genome import vcf
from genome.impute import CHROMS, ORDER, panel

FIELDS = ["AF", "AF_EUR_unrel", "AF_AFR_unrel", "AF_AMR_unrel", "AF_EAS_unrel", "AF_SAS_unrel"]
NAMES = ["AF", "EUR_AF", "AFR_AF", "AMR_AF", "EAS_AF", "SAS_AF"]  # as in the phase 3 site list


def raw_file(root, chrom):
    v2 = ".v2" if chrom == "X" else ""
    return f"1kGP_high_coverage_Illumina.chr{chrom}.filtered.SNV_INDEL_SV_phased_panel{v2}.vcf.gz"


MIN_FREE_GB = {"C:\\": 20, "panel": 50}  # stop, not retry, below these


class DiskLow(Exception):
    pass


def check_space(root):
    """Stops the run when the system drive or the panel's drive runs low: a crash-and-retry loop must not be able to
    fill a disk (Docker once filled C:)."""
    import shutil
    for drive, need in (("C:\\", MIN_FREE_GB["C:\\"]), (os.path.splitdrive(os.path.abspath(root))[0] + "\\", MIN_FREE_GB["panel"])):
        free = shutil.disk_usage(drive).free / 1e9
        if free < need:
            raise DiskLow(f"{drive} has {free:.0f} GB free, below the {need} GB this run keeps free; stopped")


def panel_rows(root, chrom):
    """(pos, ref, alt, [frequencies]) per panel variant, read from the raw VCF."""
    _, recs = vcf.records(os.path.join(root, "raw", raw_file(root, chrom)))
    for line in recs:
        p = line.decode().split("\t", 8)
        yield int(p[1]), p[3], p[4], vcf.info(p[7], FIELDS)


class Ensembl:
    """rsIDs from Ensembl's GRCh38 VCFs, read forward only: at(chrom, pos) must be called in file order."""

    def __init__(self, folder):
        self.folder, self.chrom, self.source, self.cur = folder, None, None, None

    @staticmethod
    def _records(path):
        with gzip.open(path, "rt") as f:
            for line in f:
                if line[0] == "#":
                    continue
                c, pos, rs, ref, alts = line.split("\t", 5)[:5]
                if c in ORDER and rs.startswith("rs"):
                    yield ORDER[c], int(pos), ref, alts.split(","), rs

    def at(self, chrom, pos):
        """{(ref, alt): rsID} at chrom:pos."""
        if chrom != self.chrom:
            self.chrom = chrom
            own = f"homo_sapiens-chr{chrom}.vcf.gz"
            name = own if os.path.exists(os.path.join(self.folder, own)) else "1000GENOMES-phase_3.vcf.gz"
            if name != self.source or name == own:  # the one-file source carries on where it stopped
                self.source, self.it = name, self._records(os.path.join(self.folder, name))
                self.cur = next(self.it, None)
        key = (ORDER[chrom], pos)
        while self.cur and self.cur[:2] < key:
            self.cur = next(self.it, None)
        found = {}
        while self.cur and self.cur[:2] == key:
            for alt in self.cur[3]:
                found.setdefault((self.cur[2], alt), self.cur[4])
            self.cur = next(self.it, None)
        return found


def main():
    P = panel("1kgp_hc")
    root = os.path.dirname(P["dir"])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chroms", default=",".join(CHROMS))
    ap.add_argument("--out", default=P["sites"])
    ap.add_argument("--ensembl", default=os.path.join(os.path.dirname(root), "ensembl_grch38"))
    a = ap.parse_args()
    chroms = [c.strip().upper().replace("CHR", "") for c in a.chroms.split(",")]
    # One finished file per chromosome, so a run that stops resumes where it was
    parts = os.path.join(os.path.dirname(os.path.abspath(a.out)), "sites_parts")
    os.makedirs(parts, exist_ok=True)
    # Leftovers from a run that crashed: removed first, so a retry never stacks another copy
    for f in os.listdir(parts):
        if f.endswith(".part"):
            os.remove(os.path.join(parts, f))
    for chrom in chroms:
        done = os.path.join(parts, f"chr{chrom}.vcf.gz")
        if os.path.exists(done):
            continue
        for attempt in (1, 2, 3):
            check_space(root)  # DiskLow is not caught: low space stops the run
            try:
                one_chrom(root, chrom, Ensembl(a.ensembl), done)
                break
            except (SystemExit, OSError) as e:
                if os.path.exists(done + ".part"):
                    os.remove(done + ".part")
                print(f"chr{chrom}: attempt {attempt} failed ({e}); retrying in a minute", flush=True)
                time.sleep(60)
        else:
            raise SystemExit(f"chr{chrom} failed three times; run again to resume")
    # gzip files can be concatenated: the header, then each chromosome's file as it is
    check_space(root)
    tmp = a.out + ".part"
    with open(tmp, "wb") as out:
        with gzip.open(out, "wt", newline="\n") as head:
            head.write("##fileformat=VCFv4.2\n")
            head.write(f"##source=genome/panel_sites.py: {P['label']}; frequencies over its 2,504 unrelated samples; "
                       "rsIDs from Ensembl GRCh38 (dbSNP)\n")
            for n in NAMES:
                head.write(f'##INFO=<ID={n},Number=A,Type=Float,Description="{n}">\n')
            head.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        for chrom in chroms:
            with open(os.path.join(parts, f"chr{chrom}.vcf.gz"), "rb") as f:
                while block := f.read(1 << 24):
                    out.write(block)
    os.replace(tmp, a.out)
    print(f"{a.out}: chromosomes {', '.join(chroms)}. The per-chromosome files in {parts} can be deleted.")


def one_chrom(root, chrom, ens, done):
    """Writes one chromosome's sites to `done`, checking the row count against the panel's index."""
    t, n = time.time(), Counter()
    with gzip.open(done + ".part", "wt", compresslevel=4, newline="\n") as out:
        for pos, ref, alt, af in panel_rows(root, chrom):
            rs = ens.at(chrom, pos).get((ref, alt))
            n["variants"] += 1
            n["rsid"] += rs is not None
            info = ";".join(f"{k}={v}" for k, v in zip(NAMES, af) if v != ".")
            out.write(f"{chrom}\t{pos}\t{rs or f'{chrom}:{pos}:{ref}:{alt}'}\t{ref}\t{alt}\t.\t.\t{info}\n")
    expected = indexed_records(root, chrom)
    if n["variants"] != expected:
        raise SystemExit(f"chr{chrom}: read {n['variants']:,} variants, the panel's index says {expected:,}")
    os.replace(done + ".part", done)
    print(f"chr{chrom}: {n['variants']:,} variants, {n['rsid']:,} with an rsID ({n['rsid'] / max(n['variants'], 1):.1%}; "
          f"{ens.source}) in {time.time() - t:.0f}s", flush=True)


def indexed_records(root, chrom):
    """The number of variants in a panel file, from its index."""
    return vcf.indexed_count(os.path.join(root, "raw", raw_file(root, chrom)))


if __name__ == "__main__":
    main()
