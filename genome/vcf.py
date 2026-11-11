"""Plain-Python replacements for the few bcftools calls the panel needs, so nothing depends on Docker.

    python -m genome.vcf count FILE.vcf.gz             # records per the tabix index (bcftools index -n)
    python -m genome.vcf count FILE.vcf.gz --scan      # and counted by reading the file, as a check
    python -m genome.vcf split-x [PANEL_DIR]           # chrX in Beagle's three ploidy parts, then bref3

The panel's VCFs are bgzip files, which Python's gzip module reads as ordinary multi-member gzip.
"""
import argparse
import gzip
import os
import struct
import subprocess
import sys

if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PSEUDO_BIN = 37450  # the tabix bin that holds a contig's mapped and unmapped record counts


def indexed_count(path):
    """Records in a bgzipped VCF, from its .tbi index (htslib writes the count per contig into a pseudo-bin).
    None when the index has no counts (written by an old tabix)."""
    with gzip.open(path + ".tbi", "rb") as f:
        d = f.read()
    if d[:4] != b"TBI\x01":
        raise ValueError(f"{path}.tbi: not a tabix index")
    n_ref = struct.unpack_from("<i", d, 4)[0]
    l_nm = struct.unpack_from("<i", d, 32)[0]
    o, total, seen = 36 + l_nm, 0, False
    for _ in range(n_ref):
        n_bin = struct.unpack_from("<i", d, o)[0]
        o += 4
        for _ in range(n_bin):
            b, n_chunk = struct.unpack_from("<Ii", d, o)
            o += 8
            if b == PSEUDO_BIN:
                total += struct.unpack_from("<4Q", d, o)[2]
                seen = True
            o += 16 * n_chunk
        n_intv = struct.unpack_from("<i", d, o)[0]
        o += 4 + 8 * n_intv
    return total if seen else None


def records(path):
    """(header lines, record iterator) of a VCF, as bytes lines."""
    f = gzip.open(path, "rb")
    head = []
    for line in f:
        if line[:1] != b"#":
            def rest(first=line):
                yield first
                yield from f
                f.close()
            return head, rest()
        head.append(line)
    f.close()
    return head, iter(())


def info(field, keys):
    """[value or '.'] of the INFO keys, like bcftools query's %KEY."""
    d = dict(kv.split("=", 1) for kv in field.split(";") if "=" in kv)
    return [d.get(k, ".") for k in keys]


def scan_count(path):
    return sum(1 for _ in records(path)[1])


# --- chrX in three parts ---------------------------------------------------------------------------------------------

def split_x(root, parts=None, jar=None, keep_vcf=False):
    """Cuts the panel's chrX into Beagle's ploidy parts by POS (as bcftools view --regions-overlap pos: a structural
    variant starting in one part stays in it), checks that the parts add up to the index's count, and converts each to
    bref3. Files are written as .part and renamed, and the cut VCFs are deleted afterwards."""
    from genome.impute import PANELS, REF
    parts = parts or PANELS["1kgp_hc"]["x_parts"]
    jar = jar or os.path.join(REF, "bref3.jar")
    bref = os.path.join(root, "bref3")
    todo = [(name, region) for name, region in parts if not os.path.exists(os.path.join(bref, f"{name}.bref3"))]
    if not todo:
        print("chrX parts: all converted")
        return
    n = cut_x(root, parts)
    for name, _ in todo:
        vcf, out = os.path.join(root, f"{name}.vcf.gz"), os.path.join(bref, f"{name}.bref3")
        with open(out + ".part", "wb") as w:
            subprocess.run(["java", "-Xmx10g", "-jar", jar, vcf], stdout=w, check=True)
        os.replace(out + ".part", out)
        print(f"{name}: converted", flush=True)
    if not keep_vcf:
        for name in n:
            os.remove(os.path.join(root, f"{name}.vcf.gz"))


def cut_x(root, parts):
    """Writes <root>/<name>.vcf.gz per part and returns {name: records}."""
    from genome import panel_sites
    panel_sites.check_space(root)
    raw = os.path.join(root, "raw", panel_sites.raw_file(root, "X"))
    bounds = []
    for name, region in parts:
        a, b = region.split(":")[1].split("-")
        bounds.append((name, int(a), int(b)))
    head, recs = records(raw)
    outs = {name: gzip.open(os.path.join(root, f"{name}.vcf.gz.part"), "wb", compresslevel=1) for name, _, _ in bounds}
    n = dict.fromkeys(outs, 0)
    for w in outs.values():
        w.writelines(head)
    for line in recs:
        t1 = line.index(b"\t")
        pos = int(line[t1 + 1:line.index(b"\t", t1 + 1)])
        for name, a, b in bounds:
            if a <= pos <= b:
                outs[name].write(line)
                n[name] += 1
                break
        else:
            raise SystemExit(f"chrX:{pos} falls outside every part")
    for w in outs.values():
        w.close()
    expected = indexed_count(raw)
    if expected is not None and sum(n.values()) != expected:
        raise SystemExit(f"chrX parts hold {sum(n.values()):,} records, the index says {expected:,}")
    for name in n:
        os.replace(os.path.join(root, f"{name}.vcf.gz.part"), os.path.join(root, f"{name}.vcf.gz"))
        print(f"{name}: {n[name]:,} records", flush=True)
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count")
    c.add_argument("files", nargs="+")
    c.add_argument("--scan", action="store_true")
    s = sub.add_parser("split-x")
    s.add_argument("root", nargs="?", default=None)
    s.add_argument("--keep-vcf", action="store_true")
    a = ap.parse_args()
    if a.cmd == "count":
        for f in a.files:
            line = f"{os.path.basename(f)}: {indexed_count(f)} in the index"
            if a.scan:
                line += f", {scan_count(f)} read"
            print(line, flush=True)
    else:
        from genome.impute import panel
        split_x(a.root or os.path.dirname(panel("1kgp_hc")["dir"]), keep_vcf=a.keep_vcf)


if __name__ == "__main__":
    main()
