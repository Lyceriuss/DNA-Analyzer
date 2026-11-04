# cluster_analysis/theme_graph.py
"""
API-built theme graphs, independent of the library: which genes act on a theme, through which mechanism, and how
they connect. A person's DNA file is cross-referenced afterwards, offline.

    python -m cluster_analysis.theme_graph fertility                      # → cluster_analysis/theme_graph_fertility.json
    python -m cluster_analysis.theme_graph fertility --dna data/input/...  # also → data/output/cluster_analysis/theme_<name>_<theme>.json

Genes      Open Targets: a gene joins when its association with any of the theme's diseases or traits scores ≥ 0.5
           overall, or ≥ 0.5 on human genetic evidence. Mouse-only evidence does not count.
Mechanisms Gene Ontology: a gene sits in a mechanism when it has an experimental or curated human annotation (QuickGO)
           to the mechanism's term or any term below it. Genes without one are grouped by their strongest disease.
Links      STRING interactions (confidence ≥ 0.4) between theme genes, and Reactome pathways shared by theme genes.

The DNA cross-reference runs offline against data/reference (Ensembl gene coordinates, ClinVar, GWAS Catalog):
every SNP in the file that falls inside a theme gene, marked with what is known about it. Only theme names, disease
IDs and gene symbols are sent to the APIs, never anything from the DNA file.
"""
import argparse
import csv
import gzip
import io
import json
import os
import re
import zipfile
from collections import defaultdict

from cluster_analysis import sources

OT_API = "https://api.platform.opentargets.org/api/v4/graphql"
QUICKGO = "https://www.ebi.ac.uk/QuickGO/services/annotation/downloadSearch"
REF = "data/reference"
OUTPUT_DIR = "data/output/cluster_analysis"
TRAITS_PATH = "config/snp_traits.json"
# GO evidence by class. Most behaviour and reproduction biology is known from mouse, so annotations carried over from
# orthologs count too, labelled as such; keyword-mapped electronic annotations are left out.
GO_CLASSES = {
    "human experiment": ["ECO:0000269", "ECO:0000314", "ECO:0000315", "ECO:0000316", "ECO:0000353", "ECO:0000270"],
    "curated": ["ECO:0000304", "ECO:0000305"],
    "from orthologs": ["ECO:0000250", "ECO:0000265", "ECO:0000266", "ECO:0000318"],
}
GO_EVIDENCE = ",".join(e for codes in GO_CLASSES.values() for e in codes)
ECO_CLASS = {e: c for c, codes in GO_CLASSES.items() for e in codes}

THEMES = {
    "fertility": {
        "name": "Fertility",
        "about": "Desire, the hormones that drive it and the reproductive axis, gonads and gametes, the cycle, fertilization and "
                 "pregnancy. Built from Open Targets disease genetics and Gene Ontology, not from the library.",
        "diseases": {
            "MONDO_0021124": "female infertility", "MONDO_0005372": "male infertility", "MONDO_0005387": "primary ovarian failure",
            "MONDO_0018555": "hypogonadotropic hypogonadism", "MONDO_0002146": "hypogonadism",
            "MONDO_0005362": "erectile dysfunction", "MONDO_0008487": "polycystic ovary syndrome", "MONDO_0005133": "endometriosis",
            "MONDO_0005081": "preeclampsia", "EFO_0004703": "age at menarche", "EFO_0004704": "age at menopause",
            "EFO_0004908": "testosterone level", "EFO_0004696": "SHBG level", "EFO_0004697": "estradiol level",
        },
        # Reactome pathways that are about the theme itself, listed before the generic signalling ones
        "pathway_terms": r"Meiosis|Meiotic|Fertilization|Sperm|Acrosome|Androgen|Estrogen|Pregnenolone|steroid|Glycoprotein hormones|"
                         r"Hormone ligand-binding|ESR-mediated|Ovarian|Gonad|Gonadotropin|Prolactin|Oxytocin|Kisspeptin|Peptide hormone",
        # ClinVar conditions that count as on-theme for risk, association and drug-response entries
        "clinvar_terms": r"infertil|hypogonad|gonad|ovar|sperm|azoosperm|testost|estrogen|estradiol|androgen|pregnan|menstru|"
                         r"puberty|kallmann|aromatase|letrozole|anastrozole|FSH|luteiniz|SHBG|endometrio|pre-?eclampsia|"
                         r"miscarriage|abortion|sex development|disorder of sex",
        # Level and timing traits: large GWAS give many weak locus-to-gene links, so these need a stronger genetic score
        "measurements": ["age at menarche", "age at menopause", "testosterone level", "SHBG level", "estradiol level"],
        # Order matters: a gene's main mechanism is the first one it has
        "mechanisms": [
            {"id": "drive", "name": "Desire and sexual behaviour", "go": ["GO:0019098"], "orthologs": True,
             "about": "Reproductive behaviour: mating, sexual and maternal behaviour."},
            {"id": "hormones", "name": "Sex hormone production", "go": ["GO:0120178", "GO:0006702", "GO:0006703"],
             "about": "Making testosterone, estradiol, progesterone and their precursors."},
            {"id": "axis", "name": "Reproductive axis signalling", "go": ["GO:0032274", "GO:0034698", "GO:0043401", "GO:0032276"],
             "about": "GnRH, LH and FSH release and response, and steroid hormone receptor signalling."},
            {"id": "gonads", "name": "Gonad and sex development", "go": ["GO:0008406", "GO:0007530"],
             "about": "Building testes and ovaries and determining sex."},
            {"id": "gametes", "name": "Sperm and egg production", "go": ["GO:0007276"],
             "about": "Spermatogenesis, oogenesis and meiosis."},
            {"id": "cycle", "name": "Ovarian cycle and ovulation", "go": ["GO:0042698", "GO:0001541"],
             "about": "Follicle development, ovulation and the menstrual cycle."},
            {"id": "fertilization", "name": "Fertilization", "go": ["GO:0009566"],
             "about": "Sperm meeting egg: capacitation, the acrosome reaction and binding."},
            {"id": "pregnancy", "name": "Implantation and pregnancy", "go": ["GO:0007565", "GO:0001890"],
             "about": "Implantation, decidualization, the placenta and birth."},
        ],
    },
}


# --- Open Targets ------------------------------------------------------------------------------------

def _gql(query, variables):
    r = sources._request("POST", OT_API, json={"query": query, "variables": variables}, timeout=180) or {}
    if r.get("errors"):
        raise RuntimeError(r["errors"][0].get("message", "Open Targets error"))
    return r["data"]


def ot_targets(disease_id):
    """Every gene associated with a disease: overall score and per-evidence-type scores."""
    q = """query($id:String!,$i:Int!){disease(efoId:$id){name descendants associatedTargets(page:{index:$i,size:3000}){
           count rows{score target{approvedSymbol} datatypeScores{id score}}}}}"""
    def fetch():
        out, i = {"descendants": [], "rows": []}, 0
        while True:
            d = _gql(q, {"id": disease_id, "i": i})["disease"]
            if not d:
                return out
            out["descendants"] = d.get("descendants") or []
            out["rows"] += [{"gene": r["target"]["approvedSymbol"], "score": r["score"],
                             "types": {x["id"]: x["score"] for x in r["datatypeScores"]}} for r in d["associatedTargets"]["rows"]]
            if len(out["rows"]) >= d["associatedTargets"]["count"]:
                return out
            i += 1
    return sources._cached("ot_targets", disease_id, fetch)


# --- Gene Ontology (QuickGO) -----------------------------------------------------------------------

def go_genes(go_id):
    """{symbol: [(GO term name, evidence class)]} for human genes annotated to a GO term or any term below it."""
    def fetch():
        r = sources.requests.get(QUICKGO, params={"goId": go_id, "goUsage": "descendants", "goUsageRelationships": "is_a,part_of,occurs_in",
                                                 "taxonId": "9606", "geneProductType": "protein", "evidenceCode": GO_EVIDENCE,
                                                 "evidenceCodeUsage": "descendants", "downloadLimit": 50000,
                                                 "selectedFields": "symbol,goId,goName,evidenceCode", "includeFields": "goName"},
                                 headers={"Accept": "text/tsv"}, timeout=300)
        r.raise_for_status()
        return [[x["SYMBOL"], x["GO NAME"], x["ECO ID"]] for x in csv.DictReader(io.StringIO(r.text), delimiter="\t")]
    out = defaultdict(set)
    for sym, name, eco in sources._cached("quickgo_genes2", go_id + "|" + GO_EVIDENCE, fetch):
        out[sym].add((name, ECO_CLASS.get(eco, "other")))
    return out


# --- Build --------------------------------------------------------------------------------------------

def build(theme_id):
    """Theme genes = mechanism genes (Gene Ontology) ∪ disease genes (Open Targets), each with both kinds of evidence."""
    theme = THEMES[theme_id]
    measured = set(theme.get("measurements", ()))
    rank = list(GO_CLASSES) + ["other"]

    # Open Targets: every association ≥ 0.2 is kept as evidence; the stricter rule decides who joins on disease alone
    assoc, by_disease, disease_ids = defaultdict(dict), defaultdict(set), {}
    for did, label in theme["diseases"].items():
        t = ot_targets(did)
        disease_ids[did] = [did] + t["descendants"]
        need = 0.8 if label in measured else 0.5
        for r in t["rows"]:
            genetic = r["types"].get("genetic_association", 0)
            if r["score"] >= 0.2 or genetic >= 0.2:
                assoc[r["gene"]][label] = {"score": round(r["score"], 3), "genetic": round(genetic, 3),
                                           "types": sorted(k for k, v in r["types"].items() if v >= 0.1)}
            if r["score"] >= 0.5 or genetic >= need:
                by_disease[r["gene"]].add(label)

    # Gene Ontology: human or curated annotations always count; ortholog-only ones when the mechanism says so,
    # or when the gene also has a fertility association
    mech = defaultdict(dict)
    for m in theme["mechanisms"]:
        for go_id in m["go"]:
            for sym, terms in go_genes(go_id).items():
                mech[sym].setdefault(m["id"], set()).update(terms)
    genes = {}
    for sym in set(by_disease) | set(mech):
        mechanisms = {}
        for mid, terms in mech.get(sym, {}).items():
            best = min((c for _, c in terms), key=rank.index)
            m = next(x for x in theme["mechanisms"] if x["id"] == mid)
            if best in ("human experiment", "curated") or (best == "from orthologs" and (m.get("orthologs") or assoc.get(sym))):
                mechanisms[mid] = {"terms": sorted({n for n, _ in terms})[:4], "evidence": best}
        if not mechanisms and sym not in by_disease:
            continue
        diseases = assoc.get(sym, {})
        best = max(diseases, key=lambda d: diseases[d]["score"]) if diseases else None
        genes[sym] = {"mechanisms": mechanisms, "diseases": diseases, "joined_by": sorted(by_disease.get(sym, ())),
                      "primary": next((m["id"] for m in theme["mechanisms"] if m["id"] in mechanisms), None),
                      "best_disease": best, "best_score": diseases[best]["score"] if best else 0}
    print(f"   {len(genes)} genes: {sum(1 for g in genes.values() if g['mechanisms'])} with a mechanism, "
          f"{sum(1 for g in genes.values() if g['joined_by'])} on disease evidence")

    # Shared Reactome pathways, offline: GTF symbol → Ensembl gene → lowest-level human pathways
    ensg = {}
    with gzip.open(f"{REF}/ensembl_grch37_genes.gtf.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if "\tgene\t" in line:
                m = re.search(r'gene_id "([^"]+)".*?gene_name "([^"]+)"', line)
                if m and m.group(2) in genes:
                    ensg[m.group(1)] = m.group(2)
    members = defaultdict(set)
    with open(f"{REF}/Ensembl2Reactome.txt", encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 6 and p[5] == "Homo sapiens" and p[0] in ensg:
                members[p[3]].add(ensg[p[0]])
    on_theme = re.compile(theme.get("pathway_terms", "$^"), re.I)
    pathways = sorted(({"pathway": k, "genes": sorted(v), "on_theme": bool(on_theme.search(k))} for k, v in members.items()
                       if len(v) >= 3), key=lambda x: (not x["on_theme"], -len(x["genes"])))[:80]

    symbols = sorted(genes)
    edges = sources.string_network(symbols, required_score=400) if len(symbols) <= 2000 else []
    links = list({tuple(sorted((e["preferredName_A"], e["preferredName_B"]))): {"a": e["preferredName_A"], "b": e["preferredName_B"],
                  "score": e["score"]} for e in edges if e["preferredName_A"] in genes and e["preferredName_B"] in genes}.values())
    return {"theme": theme_id, "name": theme["name"], "about": theme["about"],
            "rule": "Gene Ontology mechanism genes, plus Open Targets genes scoring ≥ 0.5 (≥ 0.8 genetic for level and timing traits)",
            "diseases": theme["diseases"], "disease_ids": disease_ids,
            "mechanisms": [{k: m[k] for k in ("id", "name", "about", "go")} for m in theme["mechanisms"]],
            "genes": dict(sorted(genes.items())), "links": links, "pathways": pathways}


# --- Offline cross-reference with a DNA file ---------------------------------------------------------

def gene_regions(symbols, flank=5000):
    """{chrom: [(start, end, symbol)]} from the Ensembl GRCh37 GTF, with a flank for promoters and nearby regulation."""
    out = defaultdict(list)
    with gzip.open(f"{REF}/ensembl_grch37_genes.gtf.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.split("\t", 9)
            if len(p) < 9 or p[2] != "gene":
                continue
            m = re.search(r'gene_name "([^"]+)"', p[8])
            if m and m.group(1) in symbols:
                out[p[0]].append((int(p[3]) - flank, int(p[4]) + flank, m.group(1)))
    return out


def clinvar_index(rsids):
    """{rsid: [{significance, condition, ref, alt}]} for the given rsIDs from the GRCh37 ClinVar VCF."""
    out = defaultdict(list)
    with gzip.open(f"{REF}/clinvar_grch37.vcf.gz", "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            m = re.search(r"RS=(\d+)", p[7])
            if not m or "rs" + m.group(1) not in rsids:
                continue
            info = dict(x.split("=", 1) for x in p[7].split(";") if "=" in x)
            out["rs" + m.group(1)].append({"significance": info.get("CLNSIG", "").replace("_", " "),
                                           "condition": info.get("CLNDN", "").replace("_", " ").split("|")[0],
                                           "ref": p[3], "alt": p[4]})
    return out


def gwas_index(rsids, trait_ids):
    """{rsid: [{trait, risk_allele, p, pubmed}]} for associations of the given rsIDs with the theme's traits."""
    out = defaultdict(list)
    with zipfile.ZipFile(f"{REF}/gwas_associations_ontology.zip") as z:
        name = next(n for n in z.namelist() if n.endswith((".tsv", ".txt")))
        with z.open(name) as f:
            for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t"):
                uris = {u.rsplit("/", 1)[-1] for u in (row.get("MAPPED_TRAIT_URI") or "").split(",")}
                if not uris & trait_ids:
                    continue
                for rs in re.findall(r"rs\d+", row.get("SNPS", "")):
                    if rs in rsids:
                        risk = (row.get("STRONGEST SNP-RISK ALLELE") or "").split("-")[-1].strip()
                        try:
                            p = float(row.get("P-VALUE") or 1)
                        except ValueError:
                            p = 1.0
                        if p > 5e-8:
                            continue
                        ci = (row.get("95% CI (TEXT)") or "").lower()
                        try:
                            effect = float(row.get("OR or BETA") or "nan")
                        except ValueError:
                            effect = float("nan")
                        # Levels report a beta with "unit increase/decrease"; diseases an odds ratio
                        direction = "raises" if "increase" in ci else "lowers" if "decrease" in ci else \
                            ("raises" if effect > 1 else "lowers" if effect < 1 else None) if effect == effect and effect > 0 else None
                        out[rs].append({"trait": row.get("MAPPED_TRAIT") or row.get("DISEASE/TRAIT"), "study": row.get("DISEASE/TRAIT"),
                                        "risk_allele": risk, "p": p, "pubmed": row.get("PUBMEDID"), "direction": direction,
                                        "effect": effect if effect == effect else None,
                                        "kind": "beta" if "unit" in ci else "odds ratio" if effect == effect else None})
    return out


def load_dna(path):
    """[(rsid, chrom, pos, genotype)] from a MyHeritage CSV."""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith(("#", "RSID", '"RSID')):
                continue
            p = [x.strip().strip('"') for x in line.split(",")]
            if len(p) >= 4 and p[0].startswith("rs") and p[2].isdigit():
                rows.append((p[0], p[1], int(p[2]), p[3]))
    return rows


FLIP = str.maketrans("ACGT", "TGCA")


def cross_reference(graph, dna_path):
    """Every SNP of the file inside a theme gene, with what ClinVar, the GWAS Catalog and the library say about it."""
    traits = json.load(open(TRAITS_PATH, encoding="utf-8"))
    regions = gene_regions(set(graph["genes"]))
    snps = []
    for rsid, chrom, pos, gt in load_dna(dna_path):
        for start, end, sym in regions.get(chrom, ()):
            if start <= pos <= end:
                snps.append({"rsid": rsid, "gene": sym, "genotype": gt, "chrom": chrom, "pos": pos})
    rsids = {s["rsid"] for s in snps}
    trait_ids = {x for ids in graph["disease_ids"].values() for x in ids}
    clinvar, gwas = clinvar_index(rsids), gwas_index(rsids, trait_ids)

    on_theme = re.compile(THEMES[graph["theme"]]["clinvar_terms"], re.I)
    per_gene = defaultdict(lambda: {"n_snps": 0, "findings": []})
    pathogenic = {"measured": 0, "carried": []}
    for s in snps:
        g = per_gene[s["gene"]]
        g["n_snps"] += 1
        gt = s["genotype"]
        found = []
        for c in clinvar.get(s["rsid"], []):
            sig = c["significance"].lower()
            if not re.search(r"pathogenic|risk factor|protective|drug response|association", sig) or "conflicting" in sig:
                continue
            is_path = "pathogenic" in sig and "benign" not in sig
            # Pathogenic variants count whatever the disease (carrier status); the rest only when the condition is on the theme
            if not is_path and not on_theme.search(c["condition"]):
                continue
            alts = c["alt"].split(",")
            copies = sum(gt.count(a) for a in alts if len(a) == 1) if set(gt) <= set(c["ref"] + "".join(alts)) else \
                sum(gt.translate(FLIP).count(a) for a in alts if len(a) == 1)
            if is_path:
                pathogenic["measured"] += 1
                if copies:
                    pathogenic["carried"].append({"gene": s["gene"], "rsid": s["rsid"], "genotype": gt, "condition": c["condition"]})
                else:
                    continue  # a pathogenic variant HP does not carry is counted, not listed
            found.append({"source": "ClinVar", "what": f"{c['significance']}: {c['condition']}", "copies": copies,
                          "allele": ",".join(alts)})
        best = {}
        for a in gwas.get(s["rsid"], []):  # one association per trait: the strongest
            if a["trait"] not in best or a["p"] < best[a["trait"]]["p"]:
                best[a["trait"]] = a
        for a in best.values():
            risk = a["risk_allele"]
            copies = gt.count(risk) if len(risk) == 1 and risk in "ACGT" else None
            found.append({"source": "GWAS", "what": a["trait"], "study": a["study"], "copies": copies, "allele": risk, "p": a["p"],
                          "pubmed": a["pubmed"], "direction": a["direction"], "effect": a["effect"], "kind": a["kind"]})
        if s["rsid"] in traits:
            t = traits[s["rsid"]]
            key = "".join(sorted(gt))
            text = next((v for k, v in t["variants"].items() if "".join(sorted(k)) == key), None)
            found.append({"source": "Library", "what": f"{t.get('trait')}: {text or 'genotype not in library'}", "copies": None})
        if found:
            g["findings"].append({"rsid": s["rsid"], "genotype": gt, "items": found})
    return {"dna_file": os.path.basename(dna_path), "n_snps_in_theme_genes": len(snps), "pathogenic": pathogenic,
            "genes": dict(per_gene)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("theme", choices=sorted(THEMES))
    ap.add_argument("--dna")
    args = ap.parse_args()
    graph = build(args.theme)
    path = os.path.join(os.path.dirname(__file__), f"theme_graph_{args.theme}.json")
    json.dump(graph, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    by_mech = {m["id"]: sum(1 for g in graph["genes"].values() if m["id"] in g["mechanisms"]) for m in graph["mechanisms"]}
    print(f"✅ {graph['name']}: {len(graph['genes'])} genes, {len(graph['links'])} links, "
          f"{sum(1 for g in graph['genes'].values() if not g['mechanisms'])} without a GO mechanism | {by_mech} → {path}")
    if args.dna:
        xref = cross_reference(graph, args.dna)
        name = re.sub(r"^MyHeritage_raw_dna_data_|\.csv$", "", os.path.basename(args.dna))
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out = os.path.join(OUTPUT_DIR, f"theme_{name}_{args.theme}.json")
        json.dump(xref, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n_find = sum(len(g["findings"]) for g in xref["genes"].values())
        print(f"✅ {xref['n_snps_in_theme_genes']} SNPs of the file fall in theme genes; {n_find} have a ClinVar, GWAS or library "
              f"finding, in {sum(1 for g in xref['genes'].values() if g['findings'])} genes → {out}")
