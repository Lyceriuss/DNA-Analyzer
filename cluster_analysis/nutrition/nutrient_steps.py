"""Where in a nutrient's conversion a person's variants act, and how.

For each nutrient's Reactome pathways: the steps in order (binding, transport across a membrane, conversion by an
enzyme, use), each with where in the cell it happens, the proteins that do it and where in the body those proteins
are mostly made (Human Protein Atlas). Each variant of the nutrient's findings is then pinned to a step when it acts
on one of the step's genes, and given its mechanism:

  protein     the variant changes the protein's amino acid sequence (Ensembl VEP, canonical transcript): V264M ...
  expression  the variant changes how much of a step gene is made (GTEx v8 eQTL), in a named tissue
  in_gene     the variant lies in a step gene, but no protein change or expression effect is known
  outside     the variant acts outside the conversion steps (lipid transport, blood group genes ...)

Public identifiers only are sent to Reactome, Ensembl, GTEx and the Protein Atlas; genotypes stay local.
"""
import gzip
import re
from collections import defaultdict

from cluster_analysis import sources
from cluster_analysis.evidence.function_evidence import gtex_eqtl, vep_amino_acids
from cluster_analysis.lifecycle.gene_trace import genes_for_accessions
from cluster_analysis.lifecycle.lifecycle import _get, event, links_between, pathway_events

GTF = "data/reference/ensembl_grch37_genes.gtf.gz"
# Genes renamed since GRCh37's annotation and GTEx v8, which still use the old symbol
OLD_NAME = {"MMUT": "MUT", "CBLIF": "GIF", "PRXL2B": "FAM213B"}
EQTL_REACH = 1_000_000            # look for an expression effect on a step gene within 1 Mb of the variant
PROTEIN = {"missense_variant", "stop_gained", "stop_lost", "start_lost", "frameshift_variant", "inframe_deletion",
           "inframe_insertion", "splice_donor_variant", "splice_acceptor_variant"}
AA3 = {"A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys", "Q": "Gln", "E": "Glu", "G": "Gly", "H": "His",
       "I": "Ile", "L": "Leu", "K": "Lys", "M": "Met", "F": "Phe", "P": "Pro", "S": "Ser", "T": "Thr", "W": "Trp",
       "Y": "Tyr", "V": "Val", "*": "stop"}


def ordered(events):
    """Steps in the order the pathway runs: a step comes after the steps it follows (Reactome's preceding events, or
    a molecule one step hands the next); ties keep Reactome's listing order."""
    n = len(events)
    after = defaultdict(set)
    for i in range(n):
        for j in range(n):
            if i != j and links_between(events[i], events[j]):
                after[j].add(i)
    done, out = set(), []
    while len(out) < n:
        ready = [j for j in range(n) if j not in done and after[j] <= done]
        j = ready[0] if ready else min(j for j in range(n) if j not in done)  # a cycle: take the earliest listed
        done.add(j)
        out.append(events[j])
    return out


def molecule_events(pathway_id, molecules):
    """The pathway's reactions that take in or give out one of the molecules, common ions included (Mg2+ is a
    "currency" molecule elsewhere, so pathway_events leaves out reactions that only move it)."""
    rows = sources._cached("lc_contained", pathway_id, lambda: _get(f"/data/pathway/{pathway_id}/containedEvents") or [])
    out = []
    for r in rows:
        e = event(r["dbId"] if isinstance(r, dict) else r)
        if not e["schemaClass"] or "Pathway" in e["schemaClass"]:
            continue
        io = [x for x in e.get("all_io", []) if x["base"] in molecules]
        if not io:
            continue
        side = lambda s: [{"base": x["base"], "compartment": x["compartment"], "pe": f'{x["base"]} [{x["compartment"]}]'}
                          for x in io if x["side"] == s]
        e = dict(e, inputs=side("in"), outputs=side("out"),
                 transport={x["compartment"] for x in io if x["side"] == "in"} != {x["compartment"] for x in io if x["side"] == "out"})
        out.append(e)
    return out


def pathway_steps(pathway_id, pathway_name, molecules=None):
    events = ordered(molecule_events(pathway_id, set(molecules)) if molecules else pathway_events(pathway_id))
    accs = sorted({a for e in events for a in e["catalysts"]})
    symbol = genes_for_accessions(accs) if accs else {}
    steps = []
    for i, e in enumerate(events):
        genes = sorted({symbol.get(a.split("-")[0], a) for a in e["catalysts"]})
        where = sorted({x["compartment"] for x in e["inputs"] + e["outputs"] if x["compartment"]})
        steps.append({"pathway_id": pathway_id, "pathway": pathway_name, "order": i + 1, "step": e["stId"], "name": e["name"],
                      "where": where, "transport": e["transport"], "genes": genes,
                      "inputs": sorted({x["base"] for x in e["inputs"]}), "outputs": sorted({x["base"] for x in e["outputs"]})})
    return steps


def tissues(symbols):
    """{gene: {specificity, tissues}}: where the Human Protein Atlas finds each gene's RNA enriched."""
    out = {}
    for g in sorted(symbols):
        def fetch(g=g):
            rows = sources._request("GET", "https://www.proteinatlas.org/api/search_download.php", ok_404=True, timeout=60,
                                    params={"search": g, "format": "json", "columns": "g,rnats,rnatsm", "compress": "no"}) or []
            row = next((r for r in rows if r.get("Gene") == g), None)
            if not row:
                return None
            nt = row.get("RNA tissue specific nTPM") or {}
            return {"specificity": row.get("RNA tissue specificity"),
                    "tissues": [t for t, _ in sorted(nt.items(), key=lambda kv: -float(kv[1]))]}
        out[g] = sources._cached("hpa_tissue", g, fetch)
    return out


def gene_spans(symbols):
    """{gene: (chrom, start, end)} on GRCh37, from the Ensembl GTF."""
    out = {}
    with gzip.open(GTF, "rt", encoding="utf-8") as f:
        for line in f:
            if line[0] == "#" or "\tgene\t" not in line:
                continue
            p = line.split("\t", 9)
            m = re.search(r'gene_name "([^"]+)"', p[8])
            name = m.group(1) if m else None
            for want in (s for s in symbols if name in (s, OLD_NAME.get(s))):
                out.setdefault(want, (p[0], int(p[3]), int(p[4])))
    return out


def protein_change(aa, gt):
    """('V264M', copies) for the protein-changing allele the person carries most of, from {allele: (ref, alt, pos)}."""
    best = None
    for allele, (ref, alt, pos) in (aa or {}).items():
        copies = gt.count(allele) if gt else None
        if best is None or (copies or 0) > (best[1] or 0):
            best = (f"{ref}{pos}{alt}", copies, allele, f"{AA3.get(ref, ref)}{pos}{AA3.get(alt, alt)}")
    return best


def annotate(findings, steps, where):
    """Adds to each finding: step genes it acts on, its mechanism and the details behind it.
    findings: rows of nutrition.py; steps: {nutrient: [step]}; where: {rsid: (chrom, pos)} on GRCh37."""
    step_genes = {nid: {g for s in st for g in s["genes"]} for nid, st in steps.items()}
    spans = gene_spans(set().union(*step_genes.values()) if step_genes else set())
    rsids = sorted({f["rsid"] for f in findings})
    print(f"Ensembl VEP for {len(rsids)} variants...")
    vep = sources.ensembl_vep(rsids)
    # Amino acids only for the variants VEP says change a protein: the only ones that use them
    aa = vep_amino_acids(sorted(rs for rs in rsids if (vep.get(rs) or {}).get("consequence") in PROTEIN))
    near = lambda rs, genes: [g for g in genes if g in spans and where.get(rs) and where[rs][0] == spans[g][0]
                              and spans[g][1] - EQTL_REACH <= where[rs][1] <= spans[g][2] + EQTL_REACH]
    eqtl_cache = {}
    asked = sum(1 for f in findings if near(f["rsid"], step_genes.get(f["nutrient"], ())))
    print(f"GTEx expression effects for variants near step genes (~{asked} lookups, cached)...")
    for f in findings:
        genes = step_genes.get(f["nutrient"], set())
        v = vep.get(f["rsid"]) or {}
        in_genes = [g for g, d in (v.get("genes") or {}).items() if d == 0 and g in genes]
        f["consequence"] = v.get("consequence")
        f["mechanism"], f["step_gene"], f["detail"] = "outside", None, None
        if in_genes and v.get("consequence") in PROTEIN:
            pc = protein_change(aa.get(f["rsid"]), f.get("genotype"))
            f["mechanism"], f["step_gene"] = "protein", in_genes[0]
            if pc:
                f["detail"] = {"change": pc[0], "long": pc[3], "allele": pc[2], "copies": pc[1]}
            continue
        if near(f["rsid"], genes) and v:
            if f["rsid"] not in eqtl_cache:
                meta, rows = gtex_eqtl(v)
                eqtl_cache[f["rsid"]] = (meta, rows)
            meta, rows = eqtl_cache[f["rsid"]]
            new = {OLD_NAME.get(g, g): g for g in genes}
            hits = sorted((r for r in rows if r["gene"] in genes or r["gene"] in new), key=lambda r: r["p"])
            if hits and meta:
                h = hits[0]
                gene = h["gene"] if h["gene"] in genes else new[h["gene"]]
                # GTEx's effect (NES) is for the alternative allele; turn it into the finding's allele
                allele = f.get("allele") if f.get("allele") in (meta["ref"], meta["alt"]) else meta["alt"]
                nes = h["nes"] if allele == meta["alt"] else -h["nes"]
                f["mechanism"], f["step_gene"] = "expression", gene
                f["detail"] = {"gene": gene, "tissue": h["tissue"].replace("_", " "), "allele": allele,
                               "more": nes > 0, "nes": round(abs(nes), 2), "p": h["p"],
                               "tissues": len({r["tissue"] for r in rows if r["gene"] == h["gene"]})}
                continue
        if in_genes:
            f["mechanism"], f["step_gene"] = "in_gene", in_genes[0]
    return findings


def build_steps(cfg, pathway_names):
    """{nutrient: [steps]} for the nutrients' Reactome pathways, in the order nutrients.json lists them."""
    out = {}
    for n in cfg:
        rows = []
        for pid in n["reactome"]:
            if pid in pathway_names:
                rows += pathway_steps(pid, pathway_names[pid], n.get("molecules"))
        out[n["id"]] = rows
    return out


# --- Written mechanism: curated text from Reactome and UniProt -----------------------------------

def _clean(text):
    """Source text without markup, citations ("(Fyfe et al. 2004)"), evidence codes or PubMed references."""
    t = re.sub(r"<[^>]+>", "", text or "")
    t = re.sub(r"\s*\{ECO:[^}]*\}", "", t)
    t = re.sub(r"\s*\((?:PubMed:\d+[,; ]*)+\)", "", t)
    t = re.sub(r"\s*\((?:By similarity|Probable)\)", "", t)
    t = re.sub(r"\s*\([^()]*\b(?:19|20)\d{2}[a-z]?\)", "", t)
    t = re.sub(r"\s+", " ", t).replace(" .", ".").strip()
    return re.sub(r"(?<!\.)\.\.(?!\.)", ".", t)


def summary(st_id):
    """Reactome's curated summary of a pathway or reaction."""
    def fetch():
        d = sources._request("GET", f"https://reactome.org/ContentService/data/query/{st_id}", ok_404=True) or {}
        return " ".join(s.get("text", "") for s in d.get("summation", []) if isinstance(s, dict))
    return _clean(sources._cached("re_summary", st_id, fetch))


def protein_function(symbols, limit=420):
    """{gene: {protein, function}}: UniProt's reviewed human entry, its name and the first sentences of its function."""
    out = {}
    for g in sorted(symbols):
        def fetch(g=g):
            d = sources._request("GET", "https://rest.uniprot.org/uniprotkb/search", ok_404=True, params={
                "query": f"gene_exact:{g} AND organism_id:9606 AND reviewed:true", "fields": "cc_function,protein_name",
                "format": "json", "size": 1}) or {}
            r = (d.get("results") or [None])[0]
            if not r:
                return None
            name = ((r.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName", {}).get("value")
            fn = " ".join(t["value"] for c in r.get("comments", []) if c.get("commentType") == "FUNCTION" for t in c.get("texts", []))
            return {"protein": name, "function": fn}
        r = sources._cached("uniprot_fn", g, fetch)
        if not r:
            continue
        text, kept = _clean(r["function"]), ""
        for s in re.split(r"(?<=[a-z0-9)]\.)\s+(?=[A-Z])", text):
            if kept and len(kept) + len(s) > limit:
                break
            kept = (kept + " " + s).strip()
        out[g] = {"protein": r["protein"], "function": kept + ("" if not kept or kept.endswith(".") else ".")}
    return out
