# cluster_analysis/sources.py
"""
Thin clients for public research APIs, with an on-disk cache.

Only public identifiers (gene symbols, rsIDs) are ever sent. Never pass genotypes
or anything derived from a person's DNA file to these functions.
"""
import hashlib
import json
import os
import time

import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
STRING_API = "https://string-db.org/api/json"
MYGENE_API = "https://mygene.info/v3/query"
GWAS_API = "https://www.ebi.ac.uk/gwas/rest/api/v2/associations"
ENSEMBL_API = "https://rest.ensembl.org"
CALLER = "dna-analyzer-cluster-analysis"
HUMAN = 9606


def _cached(namespace, key, fetch):
    """Returns the cached JSON for (namespace, key), calling fetch() on a miss."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    path = os.path.join(CACHE_DIR, f"{namespace}_{digest}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    data = fetch()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def _request(method, url, retries=4, ok_404=False, **kwargs):
    """HTTP with retry/backoff: Ensembl and STRING return 429/503 under load."""
    kwargs.setdefault("timeout", 60)
    for attempt in range(retries):
        try:
            r = requests.request(method, url, **kwargs)
            if ok_404 and r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if attempt == retries - 1 or (status and 400 <= status < 500 and status != 429):
                raise  # out of retries, or a bad request that will not succeed on retry
            print(f"   [!] {url.split('?')[0]} failed ({e.__class__.__name__}), retrying...")
            time.sleep(3 * (attempt + 1))


def _post(url, data, timeout=60):
    return _request("POST", url, data=data, timeout=timeout)


# --- STRING: interaction network + functional enrichment ---

def string_resolve(symbols):
    """Maps free-text gene names/aliases to STRING preferred names. Returns {query: preferredName}."""
    key = "\n".join(sorted(symbols))
    def fetch():
        time.sleep(1)  # STRING asks for one call per second
        return _post(f"{STRING_API}/get_string_ids", {
            "identifiers": "\r".join(symbols), "species": HUMAN, "limit": 1,
            "echo_query": 1, "caller_identity": CALLER,
        })
    rows = _cached("string_ids", key, fetch)
    return {row["queryItem"]: row["preferredName"] for row in rows}


def string_network(symbols, required_score=400):
    """Edges among the given genes only. score is STRING combined confidence (0-1)."""
    key = f"{required_score}|" + "\n".join(sorted(symbols))
    def fetch():
        time.sleep(1)
        return _post(f"{STRING_API}/network", {
            "identifiers": "\r".join(symbols), "species": HUMAN,
            "required_score": required_score, "caller_identity": CALLER,
        })
    return _cached("string_network", key, fetch)


def string_enrichment(symbols, categories=("Process", "KEGG", "RCTM", "WikiPathways"), max_terms=5):
    """Top enriched GO processes / pathways shared by a gene set (FDR < 0.05)."""
    if len(symbols) < 2:
        return []
    key = "\n".join(sorted(symbols))
    def fetch():
        time.sleep(1)
        return _post(f"{STRING_API}/enrichment", {
            "identifiers": "\r".join(symbols), "species": HUMAN, "caller_identity": CALLER,
        })
    rows = _cached("string_enrichment", key, fetch)
    rows = [r for r in rows if r["category"] in categories and r["fdr"] < 0.05]
    rows.sort(key=lambda r: (r["fdr"], -r["number_of_genes"]))
    return [{
        "category": r["category"], "term": r["term"], "description": r["description"],
        "genes": r["inputGenes"], "fdr": r["fdr"],
    } for r in rows[:max_terms]]


# --- Ensembl: variant location, alleles and overlapping genes (GRCh38) ---

PRIMARY_CHROMOSOMES = {str(c) for c in range(1, 23)} | {"X", "Y", "MT"}


def ensembl_vep(rsids, batch_size=150):
    """
    Returns {rsid: {chrom, pos, alleles: [forward-strand alleles], consequence,
    genes: {symbol: distance_bp}, eur_af: {allele: freq}}} for the rsIDs Ensembl knows.
    Genes are those overlapping or within 5 kb.
    """
    out = {}
    for i in range(0, len(rsids), batch_size):
        batch = sorted(rsids[i:i + batch_size])
        def fetch():
            return _request("POST", f"{ENSEMBL_API}/vep/human/id", params={"distance": 5000},
                            json={"ids": batch}, timeout=300,
                            headers={"Content-Type": "application/json", "Accept": "application/json"})
        for v in _cached("ensembl_vep", "\n".join(batch), fetch):
            if v["seq_region_name"] not in PRIMARY_CHROMOSOMES or v["id"] in out:
                continue  # skip alt-haplotype contigs (HSCHR...)
            genes, by_allele = {}, {}
            for t in v.get("transcript_consequences", []):
                symbol = t.get("gene_symbol") or t["gene_id"]
                genes[symbol] = min(genes.get(symbol, 10**9), t.get("distance", 0))
                if t.get("variant_allele"):
                    by_allele.setdefault(t["variant_allele"], set()).update(t.get("consequence_terms", []))
            colocated = [c for c in v.get("colocated_variants", []) if c.get("id") == v["id"]]
            freqs = (colocated[0].get("frequencies") or {}) if colocated else {}
            out[v["id"]] = {
                "chrom": v["seq_region_name"], "pos": v["start"],
                "alleles": v["allele_string"].split("/"),
                "consequence": v["most_severe_consequence"],
                # Per alternative allele: one position can hold a common missense change and a rare stop (ADRB2 rs1042714)
                "allele_consequences": {a: sorted(c) for a, c in by_allele.items()},
                "genes": genes,
                "eur_af": {a: f["eur"] for a, f in freqs.items() if "eur" in f},
            }
    return out


def ensembl_ld(rsid, r2=0.6):
    """{partner rsid: r²} for SNPs inherited together with rsid in Europeans (1000 Genomes phase 3, Ensembl, 500 kb)."""
    def fetch():
        return _request("GET", f"{ENSEMBL_API}/ld/human/{rsid}/1000GENOMES:phase_3:EUR", params={"r2": r2}, ok_404=True,
                        headers={"Content-Type": "application/json"}, timeout=120) or []
    rows = _cached("ensembl_ld", f"{rsid}_{r2}", fetch)
    return {x["variation2"]: float(x["r2"]) for x in rows if x.get("variation2", "").startswith("rs")}


def ensembl_genes_near(chrom, pos, window=250_000):
    """Protein-coding genes within `window` bp, nearest first: [(symbol, distance_bp)]."""
    region = f"{chrom}:{max(1, pos - window)}-{pos + window}"
    def fetch():
        time.sleep(0.1)
        return _request("GET", f"{ENSEMBL_API}/overlap/region/human/{region}",
                        params={"feature": "gene", "biotype": "protein_coding"},
                        headers={"Accept": "application/json"})
    genes = []
    for g in _cached("ensembl_near", region, fetch):
        if not g.get("external_name"):
            continue
        dist = 0 if g["start"] <= pos <= g["end"] else min(abs(g["start"] - pos), abs(g["end"] - pos))
        genes.append((g["external_name"], dist))
    return sorted(set(genes), key=lambda x: x[1])


# --- MyGene.info: summaries and pathway membership ---

def mygene_info(symbols):
    """Returns {symbol: {name, summary, reactome: [pathway names]}} for official symbols."""
    key = "\n".join(sorted(symbols))
    def fetch():
        return _post(MYGENE_API, {
            "q": ",".join(symbols), "scopes": "symbol", "species": "human",
            "fields": "symbol,name,summary,pathway.reactome",
        })
    hits = _cached("mygene", key, fetch)
    info = {}
    for h in hits:
        if h.get("notfound") or h["query"] in info:
            continue
        reactome = (h.get("pathway") or {}).get("reactome") or []
        if isinstance(reactome, dict):
            reactome = [reactome]
        info[h["query"]] = {
            "name": h.get("name", ""),
            "summary": h.get("summary", ""),
            "reactome": sorted({p["name"] for p in reactome}),
        }
    return info


# --- GWAS Catalog v2: trait associations per rsID ---

def _gwas_rows(rsid):
    def fetch():
        time.sleep(0.2)
        data = _request("GET", GWAS_API, ok_404=True, params={"rs_id": rsid, "size": 200})
        return (data or {}).get("_embedded", {}).get("associations", [])
    return _cached("gwas", rsid, fetch)


def gwas_mapped_genes(rsid):
    """Genes the GWAS Catalog curators mapped this rsID to, across all its associations."""
    return sorted({g for a in _gwas_rows(rsid) for g in (a.get("mapped_genes") or [])})


def gwas_traits(rsid, max_traits=8):
    """Strongest distinct trait associations for an rsID: [{trait, p_value, effect_allele, pubmed_id}]."""
    rows = _gwas_rows(rsid)

    best = {}
    for a in rows:
        allele = (a.get("snp_effect_allele") or [""])[0]
        for t in a.get("efo_traits") or []:
            trait = t["efo_trait"]
            if trait not in best or a["p_value"] < best[trait]["p_value"]:
                best[trait] = {"trait": trait, "p_value": a["p_value"],
                               "effect_allele": allele, "pubmed_id": a.get("pubmed_id")}
    return sorted(best.values(), key=lambda x: x["p_value"])[:max_traits]
