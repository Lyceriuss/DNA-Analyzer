"""Raw DNA files from consumer tests, read into one shape: (rsid, chromosome, position, genotype).

    python -m genome.formats FILE        # which format, how many calls, per chromosome

Formats (all GRCh37, forward strand):
  myheritage  CSV: "RSID","CHROMOSOME","POSITION","RESULT"; genotype as two letters, "--" for no call
  ancestry    AncestryDNA: whitespace-separated rsid, chromosome, position, allele1, allele2 after '#' comments;
              "0" for no call; chromosomes 23 = X, 24 = Y, 25 = X pseudo-autosomal, 26 = mitochondria
  23andme     tab-separated rsid, chromosome, position, genotype after '#' comments; "--" for no call
  imputed     genome/impute.py's output (MyHeritage layout plus SOURCE, GP, EUR_AF, CONFIDENCE): read by
              genome/loader.py, which keeps the confidence column

A file may be zipped (Ancestry delivers AncestryDNA.txt in a .zip) or gzipped. Chromosomes come out as 1-22, X, Y,
MT; genotypes as two upper-case letters, or "--" for no call (one letter for a call on a man's X or Y as some files
write them).
"""
import gzip
import io
import os
import sys
import zipfile
from collections import Counter

CHROM = {"23": "X", "24": "Y", "25": "X", "26": "MT", "M": "MT", "XY": "X", "PAR": "X"}


def open_text(path):
    """A text stream over a plain, gzipped or zipped file (the zip's one .txt/.csv member)."""
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        names = [n for n in z.namelist() if n.lower().endswith((".txt", ".csv", ".tsv")) and not n.startswith("__MACOSX")]
        if len(names) != 1:
            raise SystemExit(f"{os.path.basename(path)}: expected one .txt or .csv inside the zip, found {names or 'none'}")
        return io.TextIOWrapper(z.open(names[0]), encoding="utf-8", errors="replace")
    with open(path, "rb") as f:
        gz = f.read(2) == b"\x1f\x8b"
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if gz else open(path, encoding="utf-8", errors="replace")


def detect(path):
    """myheritage, ancestry, 23andme or imputed, from the comments and the header row."""
    with open_text(path) as f:
        comments = []
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                comments.append(s.lower())
                if s.lower().replace(" ", "").startswith("#rsid\tchromosome\tposition\tgenotype".replace(" ", "")):
                    return "23andme"
                continue
            head = s.replace('"', "").lower()
            if "confidence" in head and "result" in head:
                return "imputed"
            if head.startswith("rsid,chromosome,position,result") or ("," in s and "\t" not in s):
                return "myheritage"
            if head.split()[:5] == ["rsid", "chromosome", "position", "allele1", "allele2"] or any("ancestrydna" in c for c in comments):
                return "ancestry"
            if any("23andme" in c for c in comments) or len(s.split("\t")) == 4:
                return "23andme"
            raise SystemExit(f"{os.path.basename(path)}: not a MyHeritage, AncestryDNA or 23andMe raw data file")
    raise SystemExit(f"{os.path.basename(path)}: empty")


def rows(path):
    """(rsid, chromosome, position or None, genotype) for every call in a raw file."""
    kind = detect(path)
    if kind == "imputed":
        raise ValueError("imputed files are read by genome.loader.iter_calls")
    with open_text(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            p = [x.strip().strip('"') for x in (s.split(",") if kind == "myheritage" else s.split())]
            if p[0].lower() == "rsid":
                continue  # the header row
            if kind == "ancestry":
                if len(p) < 5:
                    continue
                a, b = p[3].upper(), p[4].upper()
                gt = "--" if a in ("0", "-", "") or b in ("0", "-", "") else a + b
            else:
                if len(p) < 4:
                    continue
                gt = p[3].upper()
            chrom = p[1].upper().removeprefix("CHR")
            yield p[0], CHROM.get(chrom, chrom), int(p[2]) if p[2].isdigit() else None, gt


def main():
    path = sys.argv[1]
    kind = detect(path)
    n, by, nocall = 0, Counter(), 0
    for _, c, _, gt in rows(path):
        n += 1
        by[c] += 1
        nocall += "-" in gt
    print(f"{os.path.basename(path)}: {kind}, {n:,} calls ({nocall:,} no-calls)")
    print("  " + ", ".join(f"{c}: {by[c]:,}" for c in sorted(by, key=lambda c: (not c.isdigit(), int(c) if c.isdigit() else c))))


if __name__ == "__main__":
    main()
