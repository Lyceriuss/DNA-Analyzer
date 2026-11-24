"""A chip-like raw file for a public 1000 Genomes sample, to test the pipeline on someone new with nobody's private data.

    python -m genome.sample_person HG00096 --layout data/input/MyHeritage_raw_dna_data_XY.csv --out data/input/HG00096.csv

The layout file gives the chip's content: which rsIDs at which GRCh37 positions (its genotypes are not used). Each
position is lifted to GRCh38 (UCSC chain), the sample's genotype read from the high-coverage panel's raw VCFs, and
written back on GRCh37's forward strand in MyHeritage's CSV layout. Positions the panel has no SNV for read "--", as a
chip's no-calls do. A man's X outside the PARs is one allele in the panel; it is written twice, as chips write it.

The sample is part of the reference panel, so its imputation is better than a real customer's would be: use it to test
that the pipeline runs (formats, offline lookups, the explorer), not to measure accuracy.

Reads every raw panel VCF once (32 GB), one process per chromosome.
"""
import argparse
import gzip
import io
import os
import time
from multiprocessing import Pool

from genome import formats, panel_sites
from genome.impute import COMP, REF

PANEL = os.environ.get("DNA_PANEL_ROOT", r"D:\DNA-Analyzer-reference\1kGP_high_coverage_GRCh38")
CHROMS = [str(c) for c in range(1, 23)] + ["X"]


MANIFEST_CHROM = {"XY": "X", "0": None, "Y": None, "MT": None}   # Y and MT are left out, as panel_sites does


def manifest_rows(path):
    """(name, chrom, GRCh37 pos) per locus of an Illumina manifest CSV (GSA, OmniExpress ...; zipped or not), the
    [Assay] section's Name, Chr and MapInfo, one per position. The Name is an rsID or a chr:pos name, as the chip
    companies write them."""
    import zipfile
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        f = io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace")
    else:
        f = open(path, encoding="utf-8", errors="replace")
    seen = set()
    with f:
        for line in f:
            if line.startswith("[Assay]"):
                break
        cols = f.readline().rstrip("\r\n").split(",")
        ni, ci, pi, bi = cols.index("Name"), cols.index("Chr"), cols.index("MapInfo"), cols.index("GenomeBuild")
        for line in f:
            if line.startswith("[Controls]"):
                break
            p = line.rstrip("\r\n").split(",")
            if len(p) <= pi or p[bi] != "37" or not p[pi].isdigit():
                continue
            chrom = MANIFEST_CHROM.get(p[ci], p[ci])
            if chrom is None or (chrom, p[pi]) in seen:
                continue
            seen.add((chrom, p[pi]))
            yield p[ni], chrom, int(p[pi])


def layout(path):
    """{chrom: [(GRCh37 pos, rsid, GRCh38 pos or None, strand)]} for the layout file's calls: a raw chip file, or an
    Illumina manifest CSV (manifest_rows)."""
    from pyliftover import LiftOver
    lo = LiftOver(os.path.join(REF, "hg19ToHg38.over.chain.gz"))
    out = {c: [] for c in CHROMS}
    src = manifest_rows(path) if "manifest" in os.path.basename(path).lower() else ((r, c, p) for r, c, p, _ in formats.rows(path))
    for rsid, chrom, pos in src:
        if chrom not in out or pos is None:
            continue
        hits = lo.convert_coordinate(f"chr{chrom}", pos - 1)
        ok = len(hits) == 1 and hits[0][0] == f"chr{chrom}"
        out[chrom].append((pos, rsid, hits[0][1] + 1 if ok else None, hits[0][2] if ok else None))
    return out


def genotypes(job):
    """{GRCh38 pos: two letters on GRCh38's forward strand} for one sample on one chromosome."""
    chrom, sample, wanted = job
    path = os.path.join(PANEL, "raw", panel_sites.raw_file(PANEL, chrom))
    want = {str(p).encode() for p in wanted}
    out, t = {}, time.time()
    with io.BufferedReader(gzip.open(path, "rb"), buffer_size=1 << 22) as f:
        col = None
        for line in f:
            if line[:1] == b"#":
                if line.startswith(b"#CHROM"):
                    col = line.rstrip(b"\n").split(b"\t").index(sample.encode())
                continue
            pos = line.split(b"\t", 2)[1]
            if pos not in want:
                continue
            p = line.split(b"\t", col + 1)
            ref, alt = p[3].decode(), p[4].decode()
            if len(ref) != 1 or len(alt) != 1:
                continue  # chips read SNVs
            gt = p[col].split(b"\t")[0].strip().decode().replace("/", "|").split("|")
            if any(a not in ("0", "1") for a in gt):
                continue
            letters = "".join((ref, alt)[int(a)] for a in gt)
            letters = letters * 2 if len(letters) == 1 else letters
            # Several records can share a position (one per alternative allele): keep the one the sample carries
            if int(pos) not in out or alt in letters:
                out[int(pos)] = letters
    print(f"  chr{chrom}: {len(out):,} of {len(wanted):,} positions ({time.time() - t:.0f}s)", flush=True)
    return chrom, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sample", help="1000 Genomes sample ID, e.g. HG00096")
    ap.add_argument("--layout", required=True, help="a raw chip file whose rsIDs and positions to use, or an Illumina "
                    "manifest CSV (zipped or not; a file name with 'manifest' in it)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--format", choices=("myheritage", "23andme", "ancestry"), default="myheritage",
                    help="the raw file's format (genome/formats.py)")
    ap.add_argument("--processes", type=int, default=6)
    a = ap.parse_args()
    print("Lifting the layout to GRCh38 ...", flush=True)
    lay = layout(a.layout)
    jobs = sorted(((c, a.sample, {p38 for _, _, p38, _ in rows if p38}) for c, rows in lay.items()),
                  key=lambda j: -len(j[2]))
    print(f"Reading {a.sample} from the raw panel, {a.processes} processes ...", flush=True)
    with Pool(a.processes) as pool:
        got = dict(pool.imap_unordered(genotypes, jobs))
    n = called = 0
    tmp = a.out + ".part"
    src = os.path.basename(a.layout)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        if a.format == "23andme":
            # 23andMe's download: comment lines, a commented header, tab-separated, "--" for no call
            f.write(f"# Test file in 23andMe's raw data format: 1000 Genomes sample {a.sample} (public), at the positions\n"
                    f"# of {src}. Made by genome/sample_person.py; not a 23andMe file. GRCh37, forward strand.\n"
                    "# rsid\tchromosome\tposition\tgenotype\n")
        elif a.format == "ancestry":
            # AncestryDNA's download: comment lines, a header row, tab-separated alleles, 0 for no call, X as 23
            f.write(f"#Test file in AncestryDNA's raw data format: 1000 Genomes sample {a.sample} (public), at the\n"
                    f"#positions of {src}. Made by genome/sample_person.py; not an AncestryDNA file. GRCh37, forward strand.\n"
                    "rsid\tchromosome\tposition\tallele1\tallele2\n")
        else:
            f.write(f"# Test file: 1000 Genomes sample {a.sample} (public), at the positions of {src}.\n")
            f.write("# Made by genome/sample_person.py; GRCh37, forward strand.\n")
            f.write('RSID,CHROMOSOME,POSITION,RESULT\n')
        for c in CHROMS:
            for pos, rsid, p38, strand in lay[c]:
                gt = got.get(c, {}).get(p38) if p38 else None
                if gt and strand == "-":
                    gt = gt.translate(COMP)
                n += 1
                called += bool(gt)
                if a.format == "23andme":
                    f.write(f"{rsid}\t{c}\t{pos}\t{gt or '--'}\n")
                elif a.format == "ancestry":
                    a1, a2 = (gt[0], gt[1]) if gt else ("0", "0")
                    f.write(f"{rsid}\t{'23' if c == 'X' else c}\t{pos}\t{a1}\t{a2}\n")
                else:
                    f.write(f'"{rsid}","{c}","{pos}","{gt or "--"}"\n')
    os.replace(tmp, a.out)
    print(f"Wrote {a.out}: {n:,} positions, {called:,} called ({called / n:.1%})")


if __name__ == "__main__":
    main()
