# cluster_analysis/api_check/server.py
"""
Temporary local API checker: shows the raw answer every research API gives for one gene.

    python cluster_analysis/api_check/server.py        then open http://localhost:8765

The server fetches on the page's behalf (OmniPath and KEGG send no CORS headers, so a
browser page cannot call them directly), times each call and keeps answers in memory.
Only public identifiers (gene symbols, rsIDs) are sent.
"""
import json
import os
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))  # repo root, for the cached Ensembl lookups
PORT = 8765
TRAITS_PATH = os.path.join(HERE, "..", "..", "config", "snp_traits.json")

# What each source is, whether it knows direction, and its terms of use
SOURCES = {
    "mygene":   {"name": "MyGene.info", "directional": False, "license": "Open (aggregates NCBI, Ensembl, etc.)",
                 "what": "Gene summary, aliases, IDs, GO terms, pathway memberships (Reactome, KEGG, WikiPathways)."},
    "uniprot":  {"name": "UniProt", "directional": True, "license": "CC BY 4.0",
                 "what": "Protein function, catalysed reactions with physiological direction, cofactors, regulation, pathway, location, disease."},
    "rhea":     {"name": "Rhea", "directional": True, "license": "CC BY 4.0",
                 "what": "Reactions as ChEBI molecules. Shared molecules link enzymes into chains (upstream producer, downstream consumer)."},
    "reactome": {"name": "Reactome", "directional": True, "license": "CC BY 4.0",
                 "what": "Curated reaction steps and the pathways that contain them, in biological order."},
    "omnipath": {"name": "OmniPath", "directional": True, "license": "Mixed per resource (filter with license=commercial)",
                 "what": "Directed, signed protein interactions: who activates or inhibits this gene, and what it acts on."},
    "string":   {"name": "STRING", "directional": False, "license": "CC BY 4.0",
                 "what": "Interaction partners with confidence scores (co-expression, experiments, text mining). No direction."},
    "kegg":     {"name": "KEGG", "directional": True, "license": "Free for academic use only; commercial use needs a licence",
                 "what": "Pathway maps, orthology, network elements and disease links."},
    "ensembl":  {"name": "Ensembl", "directional": False, "license": "Open",
                 "what": "Gene location, biotype and transcripts (GRCh38)."},
    "vep":      {"name": "Ensembl VEP", "directional": False, "license": "Open",
                 "what": "For the gene's library SNPs: alleles, consequence, amino-acid change, population frequencies."},
    "gwas":     {"name": "GWAS Catalog", "directional": False, "license": "Open (EMBL-EBI terms)",
                 "what": "For the gene's library SNPs: traits and lab measurements linked in genome-wide studies, with effect allele."},
    "protvar":  {"name": "UniProt variants", "directional": True, "license": "CC BY 4.0",
                 "what": "For the gene's library SNPs: the protein change, curated effect or disease, and SIFT/PolyPhen predictions."},
    "mavedb":   {"name": "MaveDB", "directional": True, "license": "CC0 / CC BY per dataset",
                 "what": "Deep mutational scans: lab-measured function score for each protein change, often under several conditions."},
    "gtex":     {"name": "GTEx eQTL", "directional": True, "license": "Open (dbGaP summary data)",
                 "what": "For the gene's library SNPs: whether the allele raises or lowers expression (NES), per tissue and per gene."},
    "clinpgx":  {"name": "ClinPGx (PharmGKB)", "directional": True, "license": "CC BY-SA 4.0",
                 "what": "For the gene's library SNPs: genotype-level drug and metabolism effects with an evidence level."},
}

_cache = {}


def library_rsids(gene):
    with open(TRAITS_PATH, encoding="utf-8") as f:
        traits = json.load(f)
    g = gene.upper()
    return [r for r, i in traits.items() if i["gene"].upper().split(" ")[0].split("(")[0] == g]


def uniprot_accession(gene):
    r = requests.get("https://rest.uniprot.org/uniprotkb/search", timeout=30, params={
        "query": f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true", "fields": "accession", "format": "json", "size": 1})
    res = r.json().get("results", [])
    return res[0]["primaryAccession"] if res else None


def entrez_id(gene):
    r = requests.get("https://mygene.info/v3/query", timeout=30,
                     params={"q": f"symbol:{gene}", "species": "human", "fields": "entrezgene", "size": 1})
    hits = r.json().get("hits", [])
    return hits[0].get("entrezgene") if hits else None


def build_requests(source, gene):
    """Returns a list of (label, url, kind) to call for this source; kind is json or text."""
    q = urllib.parse.quote
    if source == "mygene":
        return [("query", f"https://mygene.info/v3/query?q=symbol:{q(gene)}&species=human&size=1"
                 "&fields=symbol,name,alias,summary,entrezgene,ensembl.gene,uniprot.Swiss-Prot,go.BP,go.MF,pathway,genomic_pos", "json")]
    if source == "uniprot":
        return [("entry", "https://rest.uniprot.org/uniprotkb/search?format=json&size=1&query="
                 + q(f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true")
                 + "&fields=accession,gene_names,protein_name,cc_function,cc_catalytic_activity,cc_cofactor,cc_pathway,"
                   "cc_activity_regulation,cc_subcellular_location,cc_disease,cc_tissue_specificity", "json")]
    if source == "rhea":
        acc = uniprot_accession(gene)
        return [("reactions", f"https://www.rhea-db.org/rhea?query=uniprot:{acc}&columns=rhea-id,equation,chebi-id,ec,uniprot"
                 "&format=tsv&limit=50", "text")] if acc else []
    if source == "reactome":
        acc = uniprot_accession(gene)
        return [("reactions", f"https://reactome.org/ContentService/data/mapping/UniProt/{acc}/reactions?species=9606", "json"),
                ("pathways", f"https://reactome.org/ContentService/data/mapping/UniProt/{acc}/pathways?species=9606", "json")] if acc else []
    if source == "omnipath":
        return [("interactions", f"https://omnipathdb.org/interactions?partners={q(gene)}&genesymbols=1"
                 "&fields=sources,references,type,curation_effort&format=json", "json")]
    if source == "string":
        return [("partners", f"https://string-db.org/api/json/interaction_partners?identifiers={q(gene)}&species=9606&limit=15", "json")]
    if source == "kegg":
        eid = entrez_id(gene)
        return [("gene", f"https://rest.kegg.jp/get/hsa:{eid}", "text")] if eid else []
    if source == "ensembl":
        return [("lookup", f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{q(gene)}?content-type=application/json", "json")]
    if source == "vep":
        # The batch (POST) endpoint answers far faster than one GET per rsID
        rsids = library_rsids(gene)[:5]
        return [("library SNPs", "https://rest.ensembl.org/vep/human/id?canonical=1", "post:" + json.dumps({"ids": rsids}))] if rsids else []
    if source == "gwas":
        return [(r, f"https://www.ebi.ac.uk/gwas/rest/api/v2/associations?rs_id={r}&size=20", "json")
                for r in library_rsids(gene)[:3]]
    if source == "protvar":
        acc = uniprot_accession(gene)
        return [("variants", f"https://www.ebi.ac.uk/proteins/api/variation/{acc}", "json")] if acc else []
    if source == "mavedb":
        return [("score sets", "https://api.mavedb.org/api/v1/score-sets/search", "post:" + json.dumps({"text": gene}))]
    if source == "gtex":
        from cluster_analysis import sources as S
        from cluster_analysis.biomarkers import main_pair
        out = []
        for r in library_rsids(gene)[:3]:
            v = S.ensembl_vep([r]).get(r)
            if not v:
                continue
            ref = v["alleles"][0]
            alt = next((a for a in sorted(main_pair(v)) if a != ref), None)
            if alt:
                vid = f"chr{v['chrom']}_{v['pos']}_{ref}_{alt}_b38"
                out.append((f"{r} ({vid})", f"https://gtexportal.org/api/v2/association/singleTissueEqtl?variantId={vid}&datasetId=gtex_v8", "json"))
        return out
    if source == "clinpgx":
        return [(r, f"https://api.clinpgx.org/v1/data/clinicalAnnotation?location.fingerprint={r}&view=base", "json")
                for r in library_rsids(gene)[:3]]
    raise KeyError(source)


def trim(source, gene, body):
    """Keeps very large raw answers readable: only the variants that are library SNPs."""
    if source == "protvar" and isinstance(body, dict):
        rs = set(library_rsids(gene))
        feats = [f for f in body.get("features", []) if any(x.get("id") in rs for x in f.get("xrefs", []))]
        return {"accession": body.get("accession"), "note": f"{len(body.get('features', []))} variants in total; "
                f"showing the {len(feats)} that are library SNPs", "features": feats}
    return body


def fetch(source, gene):
    key = (source, gene.upper())
    if key in _cache:
        return {**_cache[key], "cached": True}
    out = {"source": source, **SOURCES[source], "gene": gene, "calls": []}
    t0 = time.time()
    try:
        calls = build_requests(source, gene)
        if not calls:
            out["note"] = "Nothing to call (no UniProt/Entrez ID found, or no library SNP for this gene)."
        for label, url, kind in calls:
            t = time.time()
            try:
                if kind.startswith("post:"):
                    r = requests.post(url, data=kind[5:], timeout=120,
                                      headers={"Content-Type": "application/json", "Accept": "application/json"})
                    kind = "json"
                else:
                    r = requests.get(url, timeout=90 if "ensembl" in url else 45,
                                     headers={"Accept": "application/json" if kind == "json" else "*/*"})
                body = trim(source, gene, r.json() if kind == "json" and r.ok else r.text)
                out["calls"].append({"label": label, "url": url, "status": r.status_code,
                                     "ms": round((time.time() - t) * 1000), "bytes": len(r.content), "body": body})
            except Exception as e:  # noqa: BLE001 - show any failure on the page
                out["calls"].append({"label": label, "url": url, "status": "error", "ms": round((time.time() - t) * 1000),
                                     "bytes": 0, "body": f"{type(e).__name__}: {e}"})
    except Exception as e:  # noqa: BLE001
        out["note"] = f"{type(e).__name__}: {e}"
    out["total_ms"] = round((time.time() - t0) * 1000)
    _cache[key] = out
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if url.path == "/sources":
            return self._send(200, json.dumps(SOURCES), "application/json")
        if url.path == "/genes":
            with open(TRAITS_PATH, encoding="utf-8") as f:
                genes = sorted({i["gene"].split(" ")[0].split("(")[0] for i in json.load(f).values()})
            return self._send(200, json.dumps(genes), "application/json")
        if url.path.startswith("/api/"):
            source = url.path[5:]
            gene = urllib.parse.parse_qs(url.query).get("gene", [""])[0].strip()
            if source not in SOURCES or not gene.replace("-", "").isalnum():
                return self._send(400, json.dumps({"error": "unknown source or bad gene symbol"}), "application/json")
            return self._send(200, json.dumps(fetch(source, gene), ensure_ascii=False), "application/json")
        self._send(404, "not found", "text/plain")

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    print(f"API checker on http://localhost:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
