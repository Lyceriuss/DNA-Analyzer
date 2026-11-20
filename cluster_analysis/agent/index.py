"""A local index of the bulk research files the agent's tools read, so a lookup takes milliseconds instead of a scan.

    python -m cluster_analysis.agent index        # -> cluster_analysis/cache/agent_index.sqlite (a few minutes, once)

Public data only, built from the files in data/reference and the 1000 Genomes site list (genome/build.py):
  gwas     GWAS Catalog associations at genome-wide significance (p <= 5e-8), one row per SNP, trait and study, with
           the effect allele, odds ratio or beta and its direction, allele frequency, sample and paper.
  genes    the genes the GWAS Catalog maps each SNP to, for lookups by gene.
  clinvar  ClinVar records that say something about a variant's effect (pathogenic, risk factor, drug response,
           protective, association), with the review stars.
  sites    each indexed SNP's position on GRCh38, its two alleles and the European allele frequency (1000 Genomes),
           plus the variants earlier Ensembl VEP runs cached (python -m cluster_analysis.agent.index --vep adds them to
           an existing index).
"""
import csv
import gzip
import io
import os
import re
import sqlite3
import sys
import time
import zipfile

from genome import build as gbuild

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = os.path.join(os.environ.get("DNA_CACHE_DIR") or os.path.join(ROOT, "cluster_analysis", "cache"), "agent_index.sqlite")
GWAS = os.path.join(ROOT, "data", "reference", "gwas_associations_ontology.zip")
GWS = 5e-8
CLINVAR_KEEP = re.compile(r"athogenic|risk_factor|drug_response|protective|association|Affects", re.I)
STARS = {"practice_guideline": 4, "reviewed_by_expert_panel": 3, "criteria_provided,_multiple_submitters,_no_conflicts": 2,
         "criteria_provided,_single_submitter": 1, "criteria_provided,_conflicting_classifications": 1}
VERSION = 1

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE gwas (rsid TEXT, allele TEXT, trait TEXT, trait_uri TEXT, reported TEXT, p REAL, size REAL, ci TEXT,
                   raf REAL, pmid TEXT, author TEXT, year TEXT, journal TEXT, study TEXT, sample TEXT, mapped TEXT,
                   reported_genes TEXT, context TEXT, chrom TEXT, pos INTEGER);
CREATE TABLE genes (gene TEXT, rsid TEXT, PRIMARY KEY (gene, rsid)) WITHOUT ROWID;
CREATE TABLE clinvar (rsid TEXT, gene TEXT, ref TEXT, alt TEXT, significance TEXT, condition TEXT, stars INTEGER,
                      chrom TEXT, pos INTEGER, variation TEXT);
CREATE TABLE sites (rsid TEXT PRIMARY KEY, chrom TEXT, pos INTEGER, ref TEXT, alt TEXT, eur_af REAL);
"""


def _genes(mapped):
    """'ACTN3 - CTSF, KDM2A' -> {'ACTN3', 'CTSF', 'KDM2A'}"""
    return {g.strip() for g in re.split(r"[,;]| - | x ", mapped or "") if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-]*", g.strip() or "-")}


def _float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build():
    started = time.time()
    tmp = PATH + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    positions = {}  # (chrom, pos) -> {rsids}

    print("GWAS Catalog ...")
    n = 0
    with zipfile.ZipFile(GWAS) as z:
        name = next(x for x in z.namelist() if x.endswith((".tsv", ".txt")))
        rows, genes = [], set()
        for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace"), delimiter="\t"):
            p = _float(r["P-VALUE"])
            m = re.fullmatch(r"(rs\d+)-([ACGT?]+)", (r["STRONGEST SNP-RISK ALLELE"] or "").strip())
            if p is None or p > GWS or not m:
                continue
            rsid, allele = m.group(1), m.group(2)
            chrom, pos = r["CHR_ID"], r["CHR_POS"]
            pos = int(pos) if (pos or "").isdigit() else None
            rows.append((rsid, allele if re.fullmatch(r"[ACGT]", allele) else None, r["MAPPED_TRAIT"], r["MAPPED_TRAIT_URI"],
                         r["DISEASE/TRAIT"], p, _float(r["OR or BETA"]), r["95% CI (TEXT)"], _float(r["RISK ALLELE FREQUENCY"]),
                         r["PUBMEDID"], r["FIRST AUTHOR"], (r["DATE"] or "")[:4], r["JOURNAL"], r["STUDY ACCESSION"],
                         r["INITIAL SAMPLE SIZE"], r["MAPPED_GENE"], r["REPORTED GENE(S)"], r["CONTEXT"], chrom, pos))
            for g in _genes(r["MAPPED_GENE"]) | _genes(r["REPORTED GENE(S)"]):
                genes.add((g, rsid))
            if chrom and pos:
                positions.setdefault((chrom, pos), set()).add(rsid)
            n += 1
            if len(rows) >= 50_000:
                db.executemany(f"INSERT INTO gwas VALUES ({','.join('?' * 20)})", rows)
                rows = []
        db.executemany(f"INSERT INTO gwas VALUES ({','.join('?' * 20)})", rows)
        db.executemany("INSERT OR IGNORE INTO genes VALUES (?, ?)", sorted(genes))
    print(f"   {n:,} associations, {len(genes):,} gene-SNP pairs")

    print("ClinVar ...")
    n = 0
    rows = []
    with gzip.open(gbuild.path("clinvar"), "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[0] == "#":
                continue
            p = line.rstrip("\n").split("\t")
            info = dict(x.split("=", 1) for x in p[7].split(";") if "=" in x)
            sig = info.get("CLNSIG", "")
            if "RS" not in info or not CLINVAR_KEEP.search(sig):
                continue
            rsid = "rs" + info["RS"]
            gene = info.get("GENEINFO", "").split("|")[0].split(":")[0]
            rows.append((rsid, gene, p[3], p[4], sig.replace("_", " "), info.get("CLNDN", "").replace("_", " "),
                         STARS.get(info.get("CLNREVSTAT", ""), 0), p[0], int(p[1]), p[2]))
            if len(p[3]) == 1 and len(p[4]) == 1:
                positions.setdefault((p[0], int(p[1])), set()).add(rsid)
            n += 1
    db.executemany("INSERT INTO clinvar VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    print(f"   {n:,} records")

    print("1000 Genomes sites (the longest step) ...")
    found = []
    with gzip.open(gbuild.sites(), "rt") as f:
        for line in f:
            if line[0] == "#":
                continue
            c = line.find("\t")
            chrom = line[:c]
            d = line.find("\t", c + 1)
            key = (chrom[3:] if chrom.startswith("chr") else chrom, int(line[c + 1:d]))
            if key not in positions:
                continue
            p = line.split("\t", 8)
            if len(p[3]) != 1 or len(p[4]) != 1:
                continue
            m = re.search(r"(?:^|;)EUR_AF=([\d.e-]+)", p[7])
            for rsid in positions[key]:
                found.append((rsid, key[0], key[1], p[3], p[4], float(m.group(1)) if m else None))
    db.executemany("INSERT OR REPLACE INTO sites VALUES (?,?,?,?,?,?)", found)
    print(f"   {len(found):,} of {sum(len(v) for v in positions.values()):,} SNPs placed")

    print("Cached Ensembl VEP records ...")
    add_vep(db)
    db.executescript("CREATE INDEX gwas_rsid ON gwas(rsid); CREATE INDEX gwas_trait ON gwas(trait);"
                     "CREATE INDEX genes_rsid ON genes(rsid); CREATE INDEX clinvar_rsid ON clinvar(rsid);"
                     "CREATE INDEX clinvar_gene ON clinvar(gene);")
    db.executemany("INSERT INTO meta VALUES (?, ?)", [("version", str(VERSION)), ("build", gbuild.BUILD),
                                                       ("built", time.strftime("%Y-%m-%d"))])
    db.commit()
    db.close()
    os.replace(tmp, PATH)
    print(f"✅ {PATH} in {time.time() - started:.0f} s")


def add_vep(db):
    """Sites (and gene links) for the variants earlier Ensembl VEP runs cached (sources.ensembl_vep), so popular
    candidate-gene variants that are neither GWAS hits nor in ClinVar (PPARGC1A rs8192678) can be read too. Offline:
    only cached records are used. Sites the 1000 Genomes list already gave are kept."""
    from cluster_analysis import sources
    ids = sorted(sources._vep_index()["ids"])
    vep = sources.ensembl_vep(ids) if ids else {}
    have = {r[0] for r in db.execute("SELECT rsid FROM sites")}
    rows, genes = [], []
    for rs, v in vep.items():
        al = v.get("alleles") or []
        if rs in have or len(al) != 2 or any(len(a) != 1 for a in al):
            continue
        rows.append((rs, v["chrom"], v["pos"], al[0], al[1], (v.get("eur_af") or {}).get(al[1])))
        genes += [(g, rs) for g, dist in (v.get("genes") or {}).items() if dist == 0 and not g.startswith("ENSG")]
    db.executemany("INSERT OR IGNORE INTO sites VALUES (?,?,?,?,?,?)", rows)
    db.executemany("INSERT OR IGNORE INTO genes VALUES (?, ?)", genes)
    db.commit()
    print(f"   {len(rows):,} sites added from cached Ensembl VEP records")


_DB = None


def db():
    """The index, opened read-only; builds it first if it is missing."""
    global _DB
    if _DB is None:
        if not os.path.exists(PATH):
            build()
        _DB = sqlite3.connect(f"file:{PATH}?mode=ro", uri=True, check_same_thread=False)
        _DB.row_factory = sqlite3.Row
    return _DB


def query(sql, *args):
    return [dict(r) for r in db().execute(sql, args).fetchall()]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--vep" in sys.argv:  # only add the cached VEP sites to an existing index
        with sqlite3.connect(PATH) as con:
            add_vep(con)
    else:
        build()
