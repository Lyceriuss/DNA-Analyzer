"""Female fertility in depth: each phase of the cycle, and a whole reproductive life, read for one person.

    python -m cluster_analysis.themes.fertility_deep --dna data/input/X.csv --out-dir <dir>

fertility_deep.json only chooses: per phase the chain of genes it runs on, the variants and the studies that measured
them in women, and the GWAS studies whose lead variants are read. Everything else comes from the sources:
  * what each gene does: UniProt's function text (reviewed human entry);
  * which DNA letter carries which form of a variant (Ser680, Asn680 ...): Ensembl VEP's amino acids per allele, and
    its European frequency;
  * what a study found in women: the sentences of its Europe PMC abstract that the choices point at, and the numbers
    in them (FSH by genotype, cycle length in days ...), read with the choices' patterns;
  * GWAS: the genome-wide significant lead variants (p < 5e-8, one per 500 kb) of the chosen study in the GWAS
    Catalog, scored for the person against Europeans like the nutrition module does (mean sum(2pw), variance
    sum(2p(1-p)w^2), p from Ensembl's European frequency); for odds-ratio studies also the person's odds against an
    average European, exp(score - mean);
  * premature ovarian insufficiency: ClinVar's pathogenic and likely pathogenic records for ovarian insufficiency,
    failure or dysgenesis (the local ClinVar file), which of them the person's file can check, and MedGen's definition.
Writes fd_phases.json (one row per phase, personal: keep out of git) and fd_genes.json (UniProt functions, public).
"""
import argparse
import csv
import gzip
import html
import io
import json
import math
import os
import re
import sys
import zipfile

if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cluster_analysis import sources
from genome import build as gbuild
from genome.loader import imputed_path, iter_calls

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CONFIG = os.path.join(HERE, "fertility_deep.json")
GWAS_ZIP = os.path.join(ROOT, "data", "reference", "gwas_associations.zip")
GWS = 5e-8
LOCUS = 500_000
SCORE_TIERS = ("measured", "high", "medium")
CHECK_TIERS = ("measured", "high")
FLIP = str.maketrans("ACGT", "TGCA")
STARS = {"practice_guideline": 4, "reviewed_by_expert_panel": 3, "criteria_provided,_multiple_submitters,_no_conflicts": 2,
         "criteria_provided,_single_submitter": 1}


# --- sources ----------------------------------------------------------------------------------------------------------

def abstract(pmid):
    """Europe PMC's record of a paper: title, first author, year and the abstract as plain text. Only real tags are
    removed (a bare "<" in "P < 0.05" is text), and the section headings become line breaks."""
    def fetch():
        r = sources._request("GET", "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                             params={"query": f"EXT_ID:{pmid} AND SRC:MED", "format": "json", "resultType": "core"})
        x = (r.get("resultList", {}).get("result") or [{}])[0]
        return {"title": x.get("title"), "authors": x.get("authorString"), "year": x.get("pubYear"), "journal": (x.get("journalInfo") or {}).get("journal", {}).get("title"),
                "abstract": x.get("abstractText") or ""}
    a = dict(sources._cached("europepmc_abstract_raw", pmid, fetch) or {})
    text = re.sub(r"</?h4>", "\n", a.get("abstract") or "")
    text = re.sub(r"</?(i|b|sup|sub|p|br|em|strong|span|ul|li)\b[^>]*>", "", text)
    a["text"] = html.unescape(text)
    first = (a.get("authors") or "").split(",")[0].strip()
    a["study"] = f"{first} {a.get('year')}".strip()
    return a


def sentence(text, anchor):
    """The whole sentence of text that contains anchor (literal). Sentences end at a full stop followed by a space and
    a capital letter, or at a line break, so decimals ("0.002") and "vs." in the middle stay inside."""
    i = text.find(anchor)
    if i < 0:
        return None
    starts = [m.end() for m in re.finditer(r"(?:\.\s+(?=[A-Z(])|\n)", text) if m.end() <= i]
    start = starts[-1] if starts else 0
    end = re.search(r"\.(?=\s+[A-Z(]|\s*\n|\s*$)|\n", text[i:])
    stop = i + end.end() if end else len(text)
    return re.sub(r"\s+", " ", text[start:stop]).strip()


def primary(results, gene):
    """The UniProt entry whose primary gene name is the gene: an exact gene search also matches synonyms (STAR finds
    guanylyl cyclase C first, whose synonyms include STAR)."""
    name = lambda e: ((e.get("genes") or [{}])[0].get("geneName") or {}).get("value")
    return next((e for e in results if name(e) == gene), {})


def uniprot_function(gene):
    """UniProt's reviewed human entry for a gene: accession, protein name and the first sentences of its function."""
    def fetch():
        r = sources._request("GET", "https://rest.uniprot.org/uniprotkb/search",
                             params={"query": f"(gene_exact:{gene}) AND (organism_id:9606) AND (reviewed:true)",
                                     "fields": "accession,gene_primary,protein_name,cc_function", "format": "json", "size": 10})
        return primary(r.get("results") or [], gene)
    e = sources._cached("uniprot_gene_function2", gene, fetch) or {}
    texts = [t.get("value", "") for c in e.get("comments", []) if c.get("commentType") == "FUNCTION" for t in c.get("texts", [])]
    fn = re.sub(r"\s*\((?:PubMed|By similarity)[^)]*\)", "", " ".join(texts)).strip()
    parts = re.split(r"(?<=\.)\s+(?=[A-Z])", fn)
    name = ((e.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName", {}).get("value")
    return {"gene": gene, "acc": e.get("primaryAccession"), "protein": name, "function": " ".join(parts[:2]) if parts else ""}


def medgen_definition(title):
    """MedGen's definition of the concept titled exactly so (NCBI E-utilities: a title search, then the record whose
    title matches), cached."""
    def fetch():
        e = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        ids = sources._request("GET", f"{e}/esearch.fcgi", params={"db": "medgen", "term": f'"{title}"[Title]', "retmode": "json",
                                                                   "retmax": 10})["esearchresult"]["idlist"]
        if not ids:
            return {}
        res = sources._request("GET", f"{e}/esummary.fcgi", params={"db": "medgen", "id": ",".join(ids), "retmode": "json"})["result"]
        r = next((res[i] for i in ids if (res.get(i) or {}).get("title", "").lower() == title.lower()), None)
        if not r:
            return {}
        d = r.get("definition")
        text = d.get("value", "") if isinstance(d, dict) else str(d or "")
        return {"id": r.get("uid"), "title": r.get("title"), "definition": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()}
    return sources._cached("medgen_title", title, fetch)


def gwas_rows(picks, rsids):
    """The local GWAS Catalog file's rows for the chosen (trait, PubMed id) studies, and every row for the given rsIDs.
    One pass over the file; the selection is cached by what was asked."""
    key = json.dumps([sorted(picks), sorted(rsids), os.path.getmtime(GWAS_ZIP) if os.path.exists(GWAS_ZIP) else 0])

    def fetch():
        if not os.path.exists(GWAS_ZIP):
            return []
        z = zipfile.ZipFile(GWAS_ZIP)
        cols = ("DISEASE/TRAIT", "FIRST AUTHOR", "DATE", "PUBMEDID", "SNPS", "STRONGEST SNP-RISK ALLELE", "RISK ALLELE FREQUENCY",
                "P-VALUE", "OR or BETA", "95% CI (TEXT)", "MAPPED_GENE", "INITIAL SAMPLE SIZE", "CHR_ID", "CHR_POS")
        out = []
        for r in csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace"), delimiter="\t"):
            if (r["DISEASE/TRAIT"], r["PUBMEDID"]) in picks or r["SNPS"] in rsids:
                out.append({c: r.get(c, "") for c in cols})
        return out
    return sources._cached("gwas_fertility_deep", key, fetch)


def clinvar_ovarian(pattern):
    """ClinVar pathogenic and likely pathogenic records (not conflicting) whose condition matches pattern."""
    path = gbuild.path("clinvar")
    key = f"{pattern}|{os.path.getmtime(path) if os.path.exists(path) else 0}"

    def fetch():
        out = []
        rx = re.compile(pattern, re.I)
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line[0] == "#" or not rx.search(line):
                    continue
                p = line.rstrip("\n").split("\t")
                info = dict(x.split("=", 1) for x in p[7].split(";") if "=" in x)
                cond = info.get("CLNDN", "").replace("_", " ")
                sig = info.get("CLNSIG", "")
                if not rx.search(cond) or not re.match(r"(Pathogenic|Likely_pathogenic)", sig) or "onflicting" in sig:
                    continue
                genes = sorted({g.split(":")[0] for g in info.get("GENEINFO", "").split("|") if g})
                out.append({"rsid": "rs" + info["RS"] if "RS" in info else None, "chrom": p[0], "pos": int(p[1]), "ref": p[3], "alt": p[4],
                            "genes": genes, "significance": sig.replace("_", " "), "condition": cond, "stars": STARS.get(info.get("CLNREVSTAT", ""), 0)})
        return out
    return sources._cached("clinvar_ovarian", key, fetch) if os.path.exists(path) else []


# --- reading the person -----------------------------------------------------------------------------------------------

def copies(gt, allele):
    return sum(1 for a in (gt or "") if a == allele) if gt and len(gt) == 2 and "-" not in gt else None


def form_alleles(v, vep):
    """{form letter: forward-strand allele} for a chosen variant: from VEP's amino acids per allele ("S/N" for rs6166 T:
    the reference allele codes S, T codes N), or the config's alleles for a variant outside the protein."""
    rec = vep.get(v["rsid"]) or {}
    if v.get("alleles"):
        return {a: a for a in v["alleles"] if a in rec.get("alleles", v["alleles"])}
    out = {}
    ref = (rec.get("alleles") or [None])[0]
    af = rec.get("eur_af") or {}
    # Two alternative alleles can code the same form (rs1042838 A and G both give Leu660): the common one in Europe
    for alt, aa in sorted((rec.get("allele_amino_acids") or {}).items(), key=lambda x: af.get(x[0], 0)):
        r, a = aa.split("/")
        if a in v["forms"] and r in v["forms"]:
            out[a], out[r] = alt, ref
    return out


def eur_freq(rec, allele):
    af = rec.get("eur_af") or {}
    if allele in af:
        return af[allele]
    if rec.get("alleles") and allele == rec["alleles"][0] and af:
        return round(1 - sum(af.values()), 4)
    return None


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def score_study(rows, vep, calls, chain_genes):
    """Lead variants of one study, aligned to Ensembl's alleles, scored for the person against Europeans."""
    leads = []
    for r in sorted(rows, key=lambda r: float(r["P-VALUE"] or 1)):
        try:
            p = float(r["P-VALUE"])
        except ValueError:
            continue
        m = re.fullmatch(r"(rs\d+)-([ACGT])", (r["STRONGEST SNP-RISK ALLELE"] or "").strip())
        if p > GWS or not m or not (r["CHR_POS"] or "").isdigit():
            continue
        ci = (r["95% CI (TEXT)"] or "").lower()
        try:
            size = float(r["OR or BETA"])
        except ValueError:
            continue
        if "increase" in ci or "decrease" in ci:
            w, kind = size * (1 if "increase" in ci else -1), "beta"
        elif size > 0 and "unit" not in ci:
            w, kind = math.log(size), "or"
        else:
            continue
        chrom, pos = r["CHR_ID"], int(r["CHR_POS"])
        if any(l["chrom"] == chrom and abs(l["pos"] - pos) < LOCUS for l in leads):
            continue
        leads.append({"rsid": m.group(1), "allele": m.group(2), "w": w, "kind": kind, "chrom": chrom, "pos": pos, "p": p,
                      "raf": r["RISK ALLELE FREQUENCY"], "gene": r["MAPPED_GENE"]})
    s = mean = var = 0.0
    used, parts, placed = 0, [], 0
    for l in leads:
        rec = vep.get(l["rsid"]) or {}
        allele = l["allele"]
        if allele not in (rec.get("alleles") or []):
            if allele.translate(FLIP) in (rec.get("alleles") or []):
                allele = allele.translate(FLIP)
            else:
                continue
        f = eur_freq(rec, allele)
        if f is None or not 0 < f < 1:
            continue
        alts = set(rec.get("alleles") or [])
        if alts in ({"A", "T"}, {"C", "G"}):  # palindromic: kept only when the study's frequency agrees with Europe's
            try:
                raf = float(l["raf"])
            except ValueError:
                continue
            if abs(raf - f) > 0.15 or 0.4 < f < 0.6:
                continue
        placed += 1
        mean += 2 * f * l["w"]
        var += 2 * f * (1 - f) * l["w"] ** 2
        gt, tier = calls.get(l["rsid"], (None, None))
        d = copies(gt, allele)
        if d is not None and tier in SCORE_TIERS:
            s += d * l["w"]
            used += 1
            parts.append((l["w"] * (d - 2 * f), l, allele, d, f))
        else:
            s += 2 * f * l["w"]
    if var <= 0 or placed < 3:
        return {"leads": len(leads), "placed": placed, "used": used}
    sd = math.sqrt(var)
    z = (s - mean) / sd
    genes = lambda g: [x.strip() for x in re.split(r"[,;-]", g or "") if x.strip()]
    top = [{"rsid": l["rsid"], "gene": l["gene"], "allele": a, "copies": d, "freq": round(f, 3), "raises": l["w"] > 0,
            "shift": round(c / sd, 2), "chain": bool(set(genes(l["gene"])) & chain_genes)}
           for c, l, a, d, f in sorted(parts, key=lambda x: -abs(x[0]))[:8]]
    kinds = {l["kind"] for l in leads}
    return {"leads": len(leads), "placed": placed, "used": used, "z": round(z, 2), "percentile": round(100 * phi(z)),
            "odds": round(math.exp(s - mean), 2) if kinds == {"or"} else None, "top": top,
            "chain_hits": sorted({g for l in leads for g in genes(l["gene"]) if g in chain_genes})}


# --- build ------------------------------------------------------------------------------------------------------------

def build(dna):
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    phases = cfg["phases"]
    picks = {(g["trait"], g["pmid"]) for ph in phases for g in ph.get("gwas", [])}
    var_rsids = {v["rsid"] for ph in phases for v in ph.get("variants", [])}
    print("GWAS Catalog rows (chosen studies and the chosen variants)...", flush=True)
    rows = gwas_rows(picks, var_rsids)
    clin = {}
    for ph in phases:
        if ph.get("clinvar"):
            print("ClinVar: ovarian insufficiency records...", flush=True)
            clin[ph["id"]] = clinvar_ovarian(ph["clinvar"]["conditions"].replace(" ", "[ _]"))
    lead_rsids = {r["SNPS"] for r in rows if (r["DISEASE/TRAIT"], r["PUBMEDID"]) in picks and re.fullmatch(r"rs\d+", r["SNPS"] or "")}
    clin_rsids = {c["rsid"] for recs in clin.values() for c in recs if c["rsid"]}
    print(f"Ensembl VEP for {len(lead_rsids | var_rsids)} variants...", flush=True)
    vep = sources.ensembl_vep(sorted(lead_rsids | var_rsids))
    want = lead_rsids | var_rsids | clin_rsids
    print(f"Reading {len(want)} SNPs from {os.path.basename(dna)}...", flush=True)
    calls = {rs: (gt, tier) for rs, _, _, gt, tier in iter_calls(dna, want, confidence=None)}

    genes = sorted({c["gene"] for ph in phases for ch in ph["chains"] for c in ch if c.get("gene")})
    print(f"UniProt functions for {len(genes)} genes...", flush=True)
    gene_rows = [uniprot_function(g) for g in genes]

    out = []
    for order, ph in enumerate(phases):
        chain_genes = {c["gene"] for ch in ph["chains"] for c in ch if c.get("gene")}
        cards = []
        for v in ph.get("variants", []):
            rec = vep.get(v["rsid"]) or {}
            fa = form_alleles(v, vep)
            names = v.get("alleles") or v["forms"]
            studied = fa.get(v["studied"])
            other_letter = next((k for k in names if k != v["studied"]), None)
            other = fa.get(other_letter)
            gt, tier = calls.get(v["rsid"], (None, None))
            n = copies(gt, studied) if studied else None
            form = None
            if gt and studied and other and n is not None:
                form = "/".join(names[v["studied"]] if a == studied else names[other_letter] for a in sorted(gt, key=lambda a: a != other))
            studies = []
            for st in v.get("studies", []):
                a = abstract(st["pmid"])
                found = [s for s in (sentence(a["text"], f) for f in st.get("finds", [])) if s]
                nums = []
                for nm in st.get("numbers", []):
                    m = re.search(nm["pattern"], a["text"])
                    if not m:
                        continue
                    item = {k: nm[k] for k in ("id", "name", "unit", "kind") if k in nm}
                    if nm["kind"] == "copies":
                        item["values"] = [float(m.group(i)) for i in (1, 2, 3)]
                    else:
                        item["studied"] = float(m.group(nm["studied"]))
                        if nm.get("typical"):
                            item["typical"] = float(m.group(nm["typical"]))
                        item["copies"] = nm.get("copies")
                    nums.append(item)
                studies.append({"pmid": st["pmid"], "study": a["study"], "title": a.get("title"), "journal": a.get("journal"),
                                "sentences": found, "numbers": nums})
            # The catalog's genome-wide associations of this variant, per copy of the studied form
            assoc = []
            for r in rows:
                if r["SNPS"] != v["rsid"]:
                    continue
                try:
                    p = float(r["P-VALUE"])
                except ValueError:
                    continue
                m = re.fullmatch(r"rs\d+-([ACGT])", (r["STRONGEST SNP-RISK ALLELE"] or "").strip())
                if p > GWS or not m:
                    continue
                ci = (r["95% CI (TEXT)"] or "").lower()
                try:
                    size = float(r["OR or BETA"])
                except ValueError:
                    size = None
                allele = m.group(1) if m.group(1) in (rec.get("alleles") or []) else m.group(1).translate(FLIP)
                same = allele == studied
                eff = None
                if size is not None and ("increase" in ci or "decrease" in ci):
                    beta = size * (1 if "increase" in ci else -1)
                    eff = {"beta": round(beta if same else -beta, 4)}
                elif size is not None and size > 0 and "unit" not in ci:
                    eff = {"or": round(size if same else 1 / size, 2)}
                assoc.append({"trait": r["DISEASE/TRAIT"], "p": r["P-VALUE"], "author": r["FIRST AUTHOR"], "year": r["DATE"][:4],
                              "pmid": r["PUBMEDID"], **(eff or {})})
            seen, uniq = set(), []
            keep = re.compile(cfg.get("card_traits", "."), re.I)
            drop = re.compile(cfg.get("card_traits_not", "$^"), re.I)
            for x in sorted(assoc, key=lambda x: float(x["p"])):
                if x["trait"] not in seen and keep.search(x["trait"]) and not drop.search(x["trait"]):
                    seen.add(x["trait"])
                    uniq.append(x)
            cards.append({"gene": v["gene"], "rsid": v["rsid"], "name": v["name"], "call": v["call"], "effect": v.get("effect"),
                          "studied": names[v["studied"]], "other": names.get(other_letter), "studied_allele": studied, "other_allele": other,
                          "freq": eur_freq(rec, studied) if studied else None, "genotype": gt, "tier": tier, "copies": n, "form": form,
                          "studies": studies, "gwas": uniq[:8]})
        panels = []
        for g in ph.get("gwas", []):
            rs = [r for r in rows if (r["DISEASE/TRAIT"], r["PUBMEDID"]) == (g["trait"], g["pmid"])]
            sc = score_study(rs, vep, calls, chain_genes)
            first = rs[0] if rs else {}
            panels.append({**g, "author": first.get("FIRST AUTHOR"), "year": (first.get("DATE") or "")[:4], "sample": first.get("INITIAL SAMPLE SIZE"),
                           **sc})
        clinvar = None
        if ph.get("clinvar"):
            recs = clin.get(ph["id"], [])
            checkable, carried = [], []
            for c in recs:
                gt, tier = calls.get(c["rsid"], (None, None)) if c["rsid"] else (None, None)
                if gt and tier in CHECK_TIERS and len(c["alt"]) == 1 and len(c["ref"]) == 1:
                    checkable.append(c)
                    if c["alt"] in gt:
                        carried.append({**c, "genotype": gt, "tier": tier})
            definition = next((d for d in (medgen_definition(t) for t in ph["clinvar"]["medgen"]) if d.get("definition")), {})
            by_gene = {}
            for c in recs:
                for gname in c["genes"][:1]:
                    by_gene[gname] = by_gene.get(gname, 0) + 1
            clinvar = {"records": len(recs), "genes": sorted(by_gene.items(), key=lambda x: -x[1]), "checkable": len(checkable),
                       "carried": carried, "medgen": definition}
        out.append({"phase": ph["id"], "order": order, "name": ph["name"], "days": json.dumps(ph.get("days")),
                    "chains": json.dumps(ph["chains"]), "cards": json.dumps(cards, ensure_ascii=False),
                    "gwas": json.dumps(panels, ensure_ascii=False), "clinvar": json.dumps(clinvar, ensure_ascii=False)})
    return out, gene_rows


# --- Part 1: how the cycle works (the same for everyone) ----------------------------------------------------------

REACTOME = "https://reactome.org/ContentService"
GRADE = {"A": 3, "B": 2, "C": 1}


def reactome_reaction(st, cofactors):
    """A Reactome reaction as a step: inputs and outputs (cofactors marked), the catalyst, the genes taking part,
    where it happens and Reactome's summary."""
    r = sources._cached("reactome_query", st, lambda: sources._request("GET", f"{REACTOME}/data/query/{st}")) or {}
    parts = sources._cached("reactome_ref_entities", st,
                            lambda: sources._request("GET", f"{REACTOME}/data/participants/{st}/referenceEntities")) or []

    def ent(e):
        names = e.get("name") or [re.sub(r"\s*\[[^\]]*\]$", "", e.get("displayName", ""))]
        chem = e.get("className") == "Chemical Compound"
        name = names[1] if chem and len(names) > 1 and len(names[0]) <= 10 and re.search(r"[A-Z0-9]{2}", names[0]) else names[0]
        comp = re.search(r"\[([^\]]+)\]$", e.get("displayName", ""))
        return {"name": name, "short": names[0], "compartment": comp.group(1) if comp else None, "chemical": chem,
                "cofactor": names[0] in cofactors or name in cofactors}
    cat = next((c.get("displayName", "") for c in r.get("catalystActivity") or [] if isinstance(c, dict)), "")
    m = re.search(r" of (.+?)(?: \[[^\]]+\])?$", cat)
    summ = next((s.get("text") for s in r.get("summation") or [] if isinstance(s, dict) and s.get("text")), "")
    return {"id": st, "name": r.get("displayName"), "inputs": [ent(e) for e in r.get("input") or [] if isinstance(e, dict)],
            "outputs": [ent(e) for e in r.get("output") or [] if isinstance(e, dict)],
            "enzyme": m.group(1) if m else None, "activity": re.sub(r" of .+$", "", cat) if cat else None,
            "genes": sorted({p["name"][0] for p in parts if p.get("databaseName") == "UniProt" and p.get("name")}),
            "compartments": [c.get("displayName") for c in r.get("compartment") or [] if isinstance(c, dict)],
            "summary": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", summ)).strip(), "kind": "reaction"}


def go_terms(ids):
    """Gene Ontology names and definitions (QuickGO)."""
    def fetch():
        r = sources._request("GET", "https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/" + ",".join(ids))
        return {t["id"]: {"name": t.get("name"), "definition": (t.get("definition") or {}).get("text", "")} for t in r.get("results", [])}
    return sources._cached("quickgo_terms", ",".join(sorted(ids)), fetch)


def go_genes(term):
    """Human genes annotated to a GO process or any term below it, with experimental or curated evidence: QuickGO's bulk
    download, as the themes use it (theme_graph.go_genes, the same cache)."""
    import datetime
    from cluster_analysis.themes.theme_graph import go_genes as theme_go_genes
    day = datetime.date.today().isoformat()
    marker = os.path.join(sources.CACHE_DIR, f"quickgo_failed_{term.replace(':', '')}_{day}")
    if os.path.exists(marker):  # QuickGO failed on this term today: tried again tomorrow
        return []
    from cluster_analysis.themes import theme_graph as tg
    import hashlib
    cached = os.path.join(sources.CACHE_DIR, f"quickgo_genes2_{hashlib.sha1((term + '|' + tg.GO_EVIDENCE).encode()).hexdigest()[:16]}.json")
    try:
        if not os.path.exists(cached):
            # The themes' own request, with a short timeout: QuickGO's download can hang on a term for many minutes
            r = sources.requests.get(tg.QUICKGO, timeout=(10, 45), headers={"Accept": "text/tsv"}, params={
                "goId": term, "goUsage": "descendants", "goUsageRelationships": "is_a,part_of,occurs_in", "taxonId": "9606",
                "geneProductType": "protein", "evidenceCode": tg.GO_EVIDENCE, "evidenceCodeUsage": "descendants", "downloadLimit": 50000,
                "selectedFields": "symbol,goId,goName,evidenceCode", "includeFields": "goName"})
            r.raise_for_status()
            rows = [[x["SYMBOL"], x["GO NAME"], x["ECO ID"]] for x in csv.DictReader(io.StringIO(r.text), delimiter="	")]
            json.dump(rows, open(cached, "w", encoding="utf-8"), ensure_ascii=False)
        return sorted(theme_go_genes(term))
    except Exception as e:
        open(marker, "w").close()
        print(f"   [!] QuickGO genes for {term} unavailable ({type(e).__name__}): the process is shown without its gene list")
        return []


def uniprot_card(gene):
    """UniProt's reviewed human entry: function, where in the cell, which tissues, cofactors."""
    def fetch():
        r = sources._request("GET", "https://rest.uniprot.org/uniprotkb/search",
                             params={"query": f"(gene_exact:{gene}) AND (organism_id:9606) AND (reviewed:true)",
                                     "fields": "accession,gene_primary,protein_name,cc_function,cc_subcellular_location,cc_tissue_specificity,cc_cofactor",
                                     "format": "json", "size": 10})
        return primary(r.get("results") or [], gene)
    e = sources._cached("uniprot_gene_card2", gene, fetch) or {}
    strip = lambda t: re.sub(r"\s*\((?:PubMed|By similarity|Ref\.)[^)]*\)", "", t or "").strip()
    first = lambda t, n: " ".join(re.split(r"(?<=\.)\s+(?=[A-Z])", strip(t))[:n])
    texts = lambda kind: [x.get("value", "") for c in e.get("comments", []) if c.get("commentType") == kind for x in c.get("texts", [])]
    loc = [l["location"]["value"] for c in e.get("comments", []) if c.get("commentType") == "SUBCELLULAR LOCATION"
           for l in c.get("subcellularLocations", []) if l.get("location")]
    cof = [x.get("name") for c in e.get("comments", []) if c.get("commentType") == "COFACTOR" for x in c.get("cofactors", [])]
    name = ((e.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName", {}).get("value")
    return {"gene": gene, "acc": e.get("primaryAccession"), "protein": name, "function": first(" ".join(texts("FUNCTION")), 2),
            "location": sorted(set(loc))[:4], "tissue": first(" ".join(texts("TISSUE SPECIFICITY")), 1), "cofactor": sorted(set(c for c in cof if c))}


def explain(cfg):
    """Part 1: per section its GO processes (definitions), its Reactome steps and the genes drawn, plus the gene cards."""
    cof = set(cfg.get("cofactors", []))
    terms = go_terms(sorted({t for s in cfg["sections"] for t in s["go"]}))
    rows, genes = [], set()
    for order, s in enumerate(cfg["sections"]):
        steps = []
        for rx in s["reactions"]:
            r = reactome_reaction(rx["id"], cof)
            r["cell"] = rx.get("cell")
            steps.append(r)
            genes |= set(r["genes"])
        only = set(s.get("go_defs_only", []))
        procs = [{"id": t, **terms.get(t, {}), "genes": [] if t in only else go_genes(t)} for t in s["go"]]
        genes |= set(s.get("genes", []))
        rows.append({"section": s["id"], "order": order, "name": s["name"], "phase": s.get("phase"),
                     "processes": json.dumps(procs, ensure_ascii=False), "steps": json.dumps(steps, ensure_ascii=False),
                     "genes": json.dumps(s.get("genes", []))})
    print(f"UniProt cards for {len(genes)} genes...", flush=True)
    cards = [uniprot_card(g) for g in sorted(genes)]
    return rows, cards


# --- Part 2: what the person's variants change ---------------------------------------------------------------------

def gtex_eqtls(gene):
    """The gene's independent eQTLs in GTEx v8 per tissue (the same cache as evidence/gene_calls.py)."""
    def fetch():
        g = sources._request("GET", "https://gtexportal.org/api/v2/reference/gene", ok_404=True,
                             params={"geneId": gene, "gencodeVersion": "v26", "genomeBuild": "GRCh38/hg38"}) or {}
        gid = next((x["gencodeId"] for x in g.get("data") or [] if x.get("geneSymbol") == gene), None)
        if not gid:
            return None
        try:
            rows = (sources._request("GET", "https://gtexportal.org/api/v2/association/independentEqtl", ok_404=True,
                                     params={"gencodeId": gid, "datasetId": "gtex_v8"}) or {}).get("data") or []
        except Exception:
            return None
        return [{"rsid": r.get("snpId"), "variant": r["variantId"], "tissue": r["tissueSiteDetailId"], "rank": r.get("rank"),
                 "nes": r["nes"], "p": r["pValue"]} for r in rows]
    return sources._cached("gtex_ind_eqtl", gene, fetch) or []


def gwas_gene_rows(genes, pattern, exclude="$^"):
    """The local GWAS Catalog file's genome-wide significant rows for reproductive traits (pattern) in the given genes."""
    key = json.dumps([sorted(genes), pattern, exclude, os.path.getmtime(GWAS_ZIP) if os.path.exists(GWAS_ZIP) else 0])

    def fetch():
        if not os.path.exists(GWAS_ZIP):
            return []
        rx = re.compile(pattern, re.I)
        drop = re.compile(exclude, re.I)
        z = zipfile.ZipFile(GWAS_ZIP)
        out = []
        for r in csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace"), delimiter="\t"):
            gs = {x.strip() for x in re.split(r"[,;]| - ", r["MAPPED_GENE"] or "") if x.strip()}
            if not gs & genes or not rx.search(r["DISEASE/TRAIT"] or "") or drop.search(r["DISEASE/TRAIT"] or ""):
                continue
            try:
                if float(r["P-VALUE"]) > GWS:
                    continue
            except ValueError:
                continue
            out.append({c: r.get(c, "") for c in ("DISEASE/TRAIT", "FIRST AUTHOR", "DATE", "PUBMEDID", "SNPS", "STRONGEST SNP-RISK ALLELE",
                                                  "P-VALUE", "OR or BETA", "95% CI (TEXT)", "MAPPED_GENE")})
        return out
    return sources._cached("gwas_fertility_genes", key, fetch)


def study_size(card):
    """The measured effect of a studied form, from its numbers: ({text parts}, value for ranking)."""
    out = []
    for s in card["studies"]:
        for n in s["numbers"]:
            if n["kind"] == "pair" and n.get("typical") is not None:
                out.append({"name": n["name"], "value": round(n["studied"] - n["typical"], 2), "unit": n["unit"], "copies": n.get("copies"), "study": s["study"], "pmid": s["pmid"]})
            elif n["kind"] == "copies":
                out.append({"name": n["name"], "value": round(n["values"][card["copies"]] - n["values"][0], 2), "unit": n["unit"],
                            "copies": card["copies"], "study": s["study"], "pmid": s["pmid"]})
            elif n["kind"] == "more":
                out.append({"name": n["name"], "value": n["studied"], "unit": "%", "copies": n.get("copies"), "study": s["study"], "pmid": s["pmid"]})
            elif n["kind"] == "earlier":
                out.append({"name": n["name"], "value": -n["studied"], "unit": n["unit"], "copies": n.get("copies"), "study": s["study"], "pmid": s["pmid"]})
            elif n["kind"] == "odds":
                out.append({"name": n["name"], "value": n["studied"], "unit": "×", "copies": n.get("copies"), "study": s["study"], "pmid": s["pmid"]})
    return out


def impact(cfg, explain_rows, phase_rows, pid, dna):
    """Part 2: every gene of a section (its steps' genes, its chosen genes and the GO process genes) with the person's
    evidence: measured studies in women (A), measured, CPIC or curated protein effects (A/B), genome-wide reproductive
    GWAS hits (B), eQTLs in the cycle's tissues (B), predicted protein effects (C). Sections ranked by the evidence."""
    calls_path = os.path.join(ROOT, gbuild.OUTPUT, f"gene_calls_{pid}.json")
    gcalls = json.load(open(calls_path, encoding="utf-8")) if os.path.exists(calls_path) else {}
    tissues = set(cfg.get("tissues", []))
    sec_genes = {}
    for r in explain_rows:
        steps, procs = json.loads(r["steps"]), json.loads(r["processes"])
        g = {}
        for st in steps:
            for x in st["genes"]:
                g.setdefault(x, set()).add(st["id"])
        for x in json.loads(r["genes"]):
            g.setdefault(x, set())
        for p in procs:
            for x in p["genes"]:
                g.setdefault(x, set()).add(p["id"])
        sec_genes[r["section"]] = g
    allg = set().union(*[set(v) for v in sec_genes.values()])
    print(f"Part 2: {len(allg)} genes; GTEx eQTLs in the cycle's tissues...", flush=True)
    eq = {}
    for g in sorted(allg):
        rows = [x for x in gtex_eqtls(g) if x.get("tissue") in tissues and x.get("rsid") and x.get("rank") == 1]
        if rows:
            eq[g] = rows
    print("GWAS Catalog: reproductive associations in these genes...", flush=True)
    grows = gwas_gene_rows(allg, cfg.get("card_traits", "."), cfg.get("card_traits_not", "$^"))
    want = {x["rsid"] for v in eq.values() for x in v} | {r["SNPS"] for r in grows if re.fullmatch(r"rs\d+", r["SNPS"] or "")}
    print(f"Reading {len(want)} SNPs...", flush=True)
    calls = {rs: (gt, tier) for rs, _, _, gt, tier in iter_calls(dna, want, confidence=None)}
    vep = sources.ensembl_vep(sorted({r["SNPS"] for r in grows if re.fullmatch(r"rs\d+", r["SNPS"] or "")}))
    cards = {}
    for pr in phase_rows:
        for c in json.loads(pr["cards"]):
            if c.get("copies"):
                cards.setdefault(c["gene"], c)

    def evidence(g):
        items = []
        c = cards.get(g)
        if c:
            none = c.get("effect") == "none"   # the study measured the form and found no change
            items.append({"kind": "study", "grade": "A", "rsid": c["rsid"], "copies": c["copies"], "form": c["form"], "studied": c["studied"],
                          "direction": "none" if none else {"LoF": "less", "GoF": "more"}.get(c["call"], "changed"), "sizes": study_size(c),
                          "name": c["name"], "counts": not none, "finding": (c["studies"][0]["sentences"] or [None])[0] if none else None,
                          "pmid": c["studies"][0]["pmid"], "study": c["studies"][0]["study"]})
        gc = gcalls.get(g) or {}
        for v in gc.get("variants") or []:
            if v.get("copies") and v.get("function") in ("LoF", "GoF", "altered"):
                grade = "A" if v.get("basis") in ("measured", "cpic") else "B" if v.get("basis") == "curated" else "C"
                items.append({"kind": "protein", "grade": grade, "rsid": v.get("rsid"), "copies": v["copies"], "change": v.get("change"),
                              "direction": {"LoF": "less", "GoF": "more"}.get(v["function"], "changed"), "basis": v.get("basis"), "detail": v.get("detail")})
        for x in eq.get(g, []):
            parts = x["variant"].split("_")
            if len(parts) < 4 or len(parts[2]) != 1 or len(parts[3]) != 1:
                continue
            gt, tier = calls.get(x["rsid"], (None, None))
            n = copies(gt, parts[3])
            if n and tier in SCORE_TIERS:
                items.append({"kind": "eqtl", "grade": "B", "rsid": x["rsid"], "copies": n, "allele": parts[3], "tissue": x["tissue"],
                              "nes": round(x["nes"], 2), "p": x["p"], "direction": "more" if x["nes"] > 0 else "less"})
        for r in grows:
            gs = {s.strip() for s in re.split(r"[,;]| - ", r["MAPPED_GENE"] or "") if s.strip()}
            if g not in gs:
                continue
            m = re.fullmatch(r"(rs\d+)-([ACGT])", (r["STRONGEST SNP-RISK ALLELE"] or "").strip())
            if not m:
                continue
            rec = vep.get(m.group(1)) or {}
            allele = m.group(2) if m.group(2) in (rec.get("alleles") or [m.group(2)]) else m.group(2).translate(FLIP)
            gt, tier = calls.get(m.group(1), (None, None))
            n = copies(gt, allele)
            if not n or tier not in SCORE_TIERS:
                continue
            ci = (r["95% CI (TEXT)"] or "").lower()
            try:
                size = float(r["OR or BETA"])
            except ValueError:
                size = None
            eff = {}
            if size is not None and ("increase" in ci or "decrease" in ci):
                eff = {"beta": round(size * (1 if "increase" in ci else -1), 4)}
            elif size is not None and size > 0 and "unit" not in ci:
                eff = {"or": round(size, 2)}
            items.append({"kind": "gwas", "grade": "B", "rsid": m.group(1), "copies": n, "allele": allele, "trait": r["DISEASE/TRAIT"],
                          "author": r["FIRST AUTHOR"], "year": r["DATE"][:4], "pmid": r["PUBMEDID"], "p": r["P-VALUE"], **eff,
                          "direction": "raises" if (eff.get("beta", 0) > 0 or eff.get("or", 1) > 1) else "lowers" if eff else "linked"})
        seen, out = set(), []
        for it in sorted(items, key=lambda i: -GRADE[i["grade"]]):
            k = (it["kind"], it.get("rsid"), it.get("tissue"), it.get("trait"))
            if k not in seen:
                seen.add(k)
                out.append(it)
        return out

    ev = {g: evidence(g) for g in sorted(allg)}
    rows = []
    for r in explain_rows:
        g = sec_genes[r["section"]]
        genes = []
        for name in sorted(g):
            items = ev.get(name, [])
            gc = gcalls.get(name) or {}
            on_step = any(s.startswith("R-HSA") for s in g[name]) or name in json.loads(r["genes"])
            counted = [i for i in items if i.get("counts", True)]
            genes.append({"gene": name, "steps": sorted(g[name]), "items": items, "read": gc.get("n_read"), "on_step": on_step,
                          "best": max((i["grade"] for i in counted), key=lambda x: GRADE[x], default=None)})
        hit = [x for x in genes if x["items"]]
        # Strength first (measured 3, associated 2, predicted 1), counted fully for the genes on the section's own steps
        # and at half for genes only Gene Ontology places in its processes
        score = round(sum(GRADE[x["best"]] * (1 if x["on_step"] else 0.5) for x in hit if x["best"]), 1)
        rows.append({"section": r["section"], "order": r["order"], "name": r["name"], "score": score,
                     "best": max((x["best"] for x in hit if x["best"]), key=lambda x: GRADE[x], default=None),
                     "counts": json.dumps({"genes": len(genes), "with_evidence": len(hit),
                                           "read": sum(1 for x in genes if x["read"]), "calls": bool(gcalls)}),
                     "genes": json.dumps(sorted(genes, key=lambda x: (-GRADE.get(x["best"], 0), not x["on_step"], -len(x["items"]), x["gene"])), ensure_ascii=False)})
    rank = sorted(rows, key=lambda x: (-x["score"], x["order"]))
    for i, x in enumerate(rank):
        x["rank"] = i
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dna", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    dna = imputed_path(a.dna)
    from genome.loader import person_label
    phases, genes = build(dna)
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    print("Part 1: Reactome reactions, GO processes, UniProt cards...", flush=True)
    sections, cards = explain(cfg)
    impacts = impact(cfg, sections, phases, person_label(dna), dna)
    have = {g["gene"] for g in genes}
    genes = genes + [c for c in cards if c["gene"] not in have]
    for g in genes:
        g.update({k: v for k, v in next((c for c in cards if c["gene"] == g["gene"]), {}).items() if k in ("location", "tissue", "cofactor")})
    os.makedirs(a.out_dir, exist_ok=True)
    for name, rows in (("fd_phases", phases), ("fd_genes", genes), ("fd_explain", sections), ("fd_impact", impacts)):
        path = os.path.join(a.out_dir, name + ".json")
        json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"wrote {path}: {len(rows)} rows")


if __name__ == "__main__":
    main()
