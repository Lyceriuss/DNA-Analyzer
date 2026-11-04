# cluster_analysis/gene_trace.py
"""
Traces one gene's upstream and downstream context: the chemical assembly line it sits on,
the cofactors it depends on, and who regulates it, with a person's genotype on every step.

    python -m cluster_analysis.gene_trace ALDH2 [--dna data/input/X.csv] [--depth 2]

Sources: Reactome (directed reactions: inputs -> outputs, catalysts), UniProt (cofactors,
activity regulation), OmniPath (directed, signed regulators). Public identifiers only are sent;
the genotype overlay runs offline. Writes data/output/cluster_analysis/trace_<GENE>.json/.md.
"""
import argparse
import json
import os
import re
from collections import defaultdict

from cluster_analysis import sources
from cluster_analysis.biomarkers import BIOMARKERS_PATH

TRAITS_PATH = "config/snp_traits.json"
OUTPUT_DIR = "data/output/cluster_analysis"
REACTOME = "https://reactome.org/ContentService"

# Carrier molecules that appear in thousands of reactions; linking through them connects everything
CURRENCY = {
    "15378", "15377", "57540", "57945", "58349", "57783", "30616", "456216", "456215", "43474", "33019",
    "16526", "15379", "57287", "57692", "58307", "28938", "29101", "29103", "29108", "18420", "29033",
    "29034", "17996", "456215", "15996", "37565", "58189", "17544", "16474", "16908", "18009", "15846",
}
HUB_LIMIT = 40  # a metabolite in more reactions than this is a hub: keep only library genes through it

COFACTOR_VITAMIN = [
    (r"\bFAD\b|FMN|flavin", "Vitamin B2 (riboflavin)"),
    (r"pyridoxal", "Vitamin B6"),
    (r"cob(?:alamin|\(III\)alamin)|methylcob", "Vitamin B12"),
    (r"thiamine", "Vitamin B1"),
    (r"\bNAD", "Vitamin B3 (niacin)"),
    (r"biotin", "Biotin (B7)"),
    (r"Zn\(2\+\)|zinc", "Zinc"),
    (r"Mg\(2\+\)|magnesium", "Magnesium"),
    (r"Fe\(2\+\)|Fe\(3\+\)|heme|iron", "Iron"),
    (r"Cu\(2\+\)|Cu cation|copper", "Copper"),
    (r"Mn\(2\+\)|manganese", "Manganese"),
    (r"selen", "Selenium"),
    (r"molybd", "Molybdenum"),
]
VITAMIN_BIOMARKER = {"Vitamin B6": "Vitamin B6", "Vitamin B12": "Vitamin B12", "Iron": "Ferritin"}

LOF_WORDS = r"reduced|lower|\blow\b|decreas|slow|impair|poor|weak|loss|deficien|inactiv|\bless\b|sluggish|blunted"
GOF_WORDS = r"increas|higher|\bhigh\b|fast|enhanc|elevat|rapid|\bmore\b|strong|gain|hyper|efficient|optimal"


# --- Reactome -------------------------------------------------------------------------------

def _get(url, ok_404=True):
    return sources._request("GET", url, ok_404=ok_404, timeout=90)


def reactions_for_protein(acc):
    rows = sources._cached("rx_protein", acc, lambda: _get(f"{REACTOME}/data/mapping/UniProt/{acc}/reactions?species=9606") or [])
    return [r["stId"] for r in rows]


def reactions_for_chebi(chebi):
    rows = sources._cached("rx_chebi", chebi, lambda: _get(f"{REACTOME}/data/mapping/ChEBI/{chebi}/reactions?species=9606") or [])
    return [r["stId"] for r in rows]


def reaction(st_id):
    """{id, name, inputs: {chebi: name}, outputs: {chebi: name}, proteins: [UniProt acc]}"""
    def fetch():
        q = _get(f"{REACTOME}/data/query/{st_id}") or {}
        parts = _get(f"{REACTOME}/data/participants/{st_id}") or []
        return {"q": {k: q.get(k) for k in ("displayName", "input", "output")}, "parts": parts}
    raw = sources._cached("rx_detail", st_id, fetch)
    by_pe = {p["peDbId"]: p for p in raw["parts"]}
    pe_id = lambda x: x["dbId"] if isinstance(x, dict) else x

    def molecules(side):
        out = {}
        for x in raw["q"].get(side) or []:
            p = by_pe.get(pe_id(x))
            for e in (p or {}).get("refEntities", []):
                name = re.sub(r"\s*\[.*\]$", "", p["displayName"])
                # Protein-handling steps (CLPXP:substrate...) are not chemistry
                if (e.get("schemaClass") == "ReferenceMolecule" and e["identifier"] not in CURRENCY
                        and ":" not in name and "substrate" not in name.lower()):
                    out[e["identifier"]] = name
        return out

    proteins = sorted({e["identifier"] for p in raw["parts"] for e in p.get("refEntities", [])
                       if e.get("schemaClass") == "ReferenceGeneProduct"})
    return {"id": st_id, "name": raw["q"].get("displayName"), "inputs": molecules("input"),
            "outputs": molecules("output"), "proteins": proteins}


# --- UniProt / Rhea / OmniPath --------------------------------------------------------------

def uniprot_entry(gene):
    def fetch():
        r = sources._request("GET", "https://rest.uniprot.org/uniprotkb/search", params={
            "query": f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true", "format": "json", "size": 1,
            "fields": "accession,gene_primary,cc_cofactor,cc_activity_regulation,cc_pathway,cc_catalytic_activity"})
        return (r.get("results") or [None])[0]
    return sources._cached("uniprot_entry2", gene, fetch)


def rhea_sides(rhea_id):
    """Left/right ChEBI ids and names of a Rhea reaction (ChEBI ids come in equation order)."""
    def fetch():
        r = sources.requests.get("https://www.rhea-db.org/rhea", timeout=60, params={
            "query": rhea_id, "columns": "rhea-id,equation,chebi-id", "format": "tsv", "limit": 1})
        rows = [l.split("\t") for l in r.text.strip().split("\n")[1:]]
        return rows[0] if rows else None
    row = sources._cached("rhea_sides", rhea_id, fetch)
    if not row or len(row) < 3 or " = " not in row[1]:
        return None
    left, right = row[1].split(" = ", 1)
    strip = lambda t: re.sub(r"^\d+\s+", "", t.strip())
    lnames, rnames = [strip(t) for t in left.split(" + ")], [strip(t) for t in right.split(" + ")]
    ids = [c.replace("CHEBI:", "") for c in row[2].split(";")]
    if len(ids) != len(lnames) + len(rnames):
        return None  # a name containing " + " broke the split; skip rather than guess
    return {"equation": row[1], "left": dict(zip(ids[:len(lnames)], lnames)), "right": dict(zip(ids[len(lnames):], rnames))}


def oriented(comment):
    """(inputs, outputs, equation) orientations of a UniProt catalytic activity, using its physiological direction."""
    rhea = next((x["id"] for x in comment["reaction"].get("reactionCrossReferences", []) if x["id"].startswith("RHEA:")), None)
    sides = rhea_sides(rhea) if rhea else None
    if not sides:
        return []
    clean = lambda d: {k: v for k, v in d.items() if k not in CURRENCY}
    dirs = {p["directionType"] for p in comment.get("physiologicalReactions", [])}
    l, r = clean(sides["left"]), clean(sides["right"])
    if dirs == {"left-to-right"}:
        return [(l, r, sides["equation"])]
    if dirs == {"right-to-left"}:
        return [(r, l, sides["equation"])]
    return [(l, r, sides["equation"]), (r, l, sides["equation"] + " (reversible)")]


def catalytic(entry):
    return [c for c in (entry or {}).get("comments", []) if c["commentType"] == "CATALYTIC ACTIVITY"]


def enzymes_for_chebi(chebi):
    """Human reviewed enzymes whose catalysed reactions involve this molecule."""
    def fetch():
        r = sources._request("GET", "https://rest.uniprot.org/uniprotkb/search", params={
            "query": f"chebi:{chebi} AND organism_id:9606 AND reviewed:true", "format": "json", "size": 200,
            "fields": "accession,gene_primary,cc_catalytic_activity"})
        return r.get("results", [])
    return sources._cached("enzymes_chebi", chebi, fetch)


def genes_for_accessions(accs):
    """UniProt accession -> gene symbol, cached per accession. Uses the dedicated accessions
    endpoint; long OR queries on /search return 500 errors."""
    accs = sorted({a.split("-")[0] for a in accs if a})  # drop isoform suffixes (P12345-2)
    out, missing = {}, []
    valid = re.compile(r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$")
    for a in [a for a in accs if not valid.match(a)]:
        out[a] = a  # not a UniProt accession: keep the id as its own label
    accs = [a for a in accs if valid.match(a)]
    for a in accs:
        path = os.path.join(sources.CACHE_DIR, f"acc1_{a}.json")
        if os.path.exists(path):
            out[a] = json.load(open(path, encoding="utf-8"))
        else:
            missing.append(a)
    for i in range(0, len(missing), 50):
        chunk = missing[i:i + 50]
        r = sources._request("GET", "https://rest.uniprot.org/uniprotkb/accessions",
                             params={"accessions": ",".join(chunk), "fields": "accession,gene_primary", "format": "json"})
        found = {x["primaryAccession"]: (x.get("genes") or [{}])[0].get("geneName", {}).get("value", x["primaryAccession"])
                 for x in (r or {}).get("results", [])}
        for a in chunk:
            out[a] = found.get(a, a)
            os.makedirs(sources.CACHE_DIR, exist_ok=True)
            json.dump(out[a], open(os.path.join(sources.CACHE_DIR, f"acc1_{a}.json"), "w", encoding="utf-8"))
    return out


def omnipath(gene):
    url = (f"https://omnipathdb.org/interactions?partners={gene}&genesymbols=1"
           "&fields=sources,type,curation_effort&format=json")
    return sources._cached("omnipath", gene, lambda: _get(url) or [])


# --- Person overlay -------------------------------------------------------------------------

def function_call(text):
    """GoF / LoF / normal inferred from the library's interpretation text (marked as inferred)."""
    t = (text or "").lower()
    lof, gof = re.search(LOF_WORDS, t), re.search(GOF_WORDS, t)
    if lof and not gof: return "LoF"
    if gof and not lof: return "GoF"
    return "normal"


def person_status(dna_path):
    from src.analyzer import run_analysis
    from src.report_engine import RISK_MAX_SCORE, STRENGTH_MIN_SCORE
    df = run_analysis(dna_path, TRAITS_PATH)
    lib = json.load(open("cluster_analysis/modules.json", encoding="utf-8"))
    status = defaultdict(list)
    for _, r in df.iterrows():
        for g in lib["rsids"].get(r["RSID"], {}).get("genes", []):
            status[g].append({"rsid": r["RSID"], "genotype": r["Result"], "score": float(r["Score"]),
                              "interpretation": r["Interpretation"], "function": function_call(r["Interpretation"]),
                              "health": "risk" if r["Score"] <= RISK_MAX_SCORE else "strength" if r["Score"] >= STRENGTH_MIN_SCORE else "neutral"})
    return status


def summarize(entries):
    """One call per gene: the SNP furthest from neutral decides."""
    if not entries:
        return None
    e = max(entries, key=lambda x: abs(x["score"] - 5))
    return {**e, "n_snps": len(entries)}


# --- Trace ----------------------------------------------------------------------------------

def trace(gene, status=None, depth=1):
    traits = json.load(open(TRAITS_PATH, encoding="utf-8"))
    library_genes = {g for r in json.load(open("cluster_analysis/modules.json", encoding="utf-8"))["rsids"].values() for g in r["genes"]}
    entry = uniprot_entry(gene)
    if not entry:
        raise SystemExit(f"No reviewed human UniProt entry for {gene}")
    acc = entry["primaryAccession"]
    status = status or {}

    own = [reaction(r) for r in reactions_for_protein(acc)]
    own = [r for r in own if acc in r["proteins"] and (r["inputs"] or r["outputs"])]
    all_accs = {p for r in own for p in r["proteins"]}

    steps = []  # (direction, metabolite, name, reaction)
    hubs = set()
    for r in own:
        for side, direction, want in (("inputs", "upstream", "outputs"), ("outputs", "downstream", "inputs")):
            for chebi, name in r[side].items():
                linked = reactions_for_chebi(chebi)
                if len(linked) > HUB_LIMIT:
                    hubs.add(name)
                for st in linked:
                    if st == r["id"]:
                        continue
                    other = reaction(st)
                    # Transport (same molecule in and out) is not a chemical step
                    if chebi in other[want] and chebi not in other["inputs" if want == "outputs" else "outputs"]:
                        steps.append((direction, chebi, name, other))
                        all_accs.update(other["proteins"])

    acc_gene = genes_for_accessions(all_accs)
    with_status = lambda g: {"gene": g, "in_library": g in library_genes, "person": summarize(status.get(g))}

    links = []
    for direction, chebi, name, other in steps:
        genes = sorted({acc_gene.get(a, a) for a in other["proteins"]} - {gene})
        if name in hubs:
            genes = [g for g in genes if g in library_genes]
        if not genes:
            continue
        links.append({"direction": direction, "metabolite": name, "chebi": chebi, "reaction": other["name"],
                      "reaction_id": other["id"], "source": "Reactome", "genes": [with_status(g) for g in genes]})

    # Second chaining source: UniProt catalytic activities + Rhea sides. Reactome sometimes records
    # one enzyme's product and the next enzyme's substrate as different forms (polyglutamate vs
    # plain folate), which breaks the chain; UniProt/Rhea use one ChEBI id for both.
    own_rx = [o for c in catalytic(entry) for o in oriented(c)]
    uni_reactions = [{"id": None, "name": eq, "inputs": list(i.values()), "outputs": list(o.values())} for i, o, eq in own_rx]
    for ins, outs, _ in own_rx:
        for side, direction in ((ins, "upstream"), (outs, "downstream")):
            for chebi, name in side.items():
                enzymes = enzymes_for_chebi(chebi)
                hub = len(enzymes) > HUB_LIMIT
                if hub:
                    hubs.add(name)
                by_reaction = defaultdict(set)
                for e in enzymes:
                    g = (e.get("genes") or [{}])[0].get("geneName", {}).get("value")
                    if not g or g == gene or (hub and g not in library_genes):
                        continue
                    for c in catalytic(e):
                        for i2, o2, eq in oriented(c):
                            # upstream: enzyme makes our input; downstream: enzyme uses our output
                            if (direction == "upstream" and chebi in o2) or (direction == "downstream" and chebi in i2):
                                by_reaction[eq].add(g)
                for eq, gs in by_reaction.items():
                    links.append({"direction": direction, "metabolite": name, "chebi": chebi, "reaction": eq,
                                  "reaction_id": None, "source": "UniProt/Rhea", "genes": [with_status(g) for g in sorted(gs)]})

    # Cofactors and regulation (UniProt)
    cofactors, regulation = [], None
    for c in entry.get("comments", []):
        if c["commentType"] == "COFACTOR":
            cofactors += [x["name"] for x in c.get("cofactors", [])]
        if c["commentType"] == "ACTIVITY REGULATION":
            regulation = c["texts"][0]["value"]
    vitamins = sorted({v for cf in cofactors for rx, v in COFACTOR_VITAMIN if re.search(rx, cf, re.I)})
    bio = json.load(open(BIOMARKERS_PATH, encoding="utf-8"))["biomarkers"]
    cofactor_genes = {}
    for v in vitamins:
        bm = VITAMIN_BIOMARKER.get(v)
        snps = next((b["snps"] for b in bio if b["biomarker"] == bm), []) if bm else []
        cofactor_genes[v] = [with_status(g) for g in sorted({g for s in snps for g in s["genes"]})]

    regulators = []
    for x in omnipath(gene):
        if not x.get("is_directed"):
            continue
        if x["target_genesymbol"] == gene:
            regulators.append({"direction": "upstream", "gene": x["source_genesymbol"], "effect":
                               "activates" if x["is_stimulation"] else "inhibits" if x["is_inhibition"] else "acts on",
                               "type": x["type"], "sources": x["sources"][:3]})
        elif x["source_genesymbol"] == gene:
            regulators.append({"direction": "downstream", "gene": x["target_genesymbol"], "effect":
                               "activates" if x["is_stimulation"] else "inhibits" if x["is_inhibition"] else "acts on",
                               "type": x["type"], "sources": x["sources"][:3]})
    for r in regulators:
        r.update(with_status(r["gene"]))

    focal = with_status(gene)
    return {"gene": gene, "accession": acc, "focal": focal,
            "library_snps": [r for r, i in traits.items() if i["gene"].split(" ")[0].split("(")[0] == gene],
            "reactions": [{"id": r["id"], "name": r["name"], "inputs": list(r["inputs"].values()),
                           "outputs": list(r["outputs"].values())} for r in own] + uni_reactions,
            "links": links, "hub_metabolites": sorted(hubs),
            "cofactors": cofactors, "cofactor_vitamins": vitamins, "cofactor_genes": cofactor_genes,
            "regulation": regulation, "regulators": regulators,
            "patterns": patterns(focal, links)}


def patterns(focal, links):
    """Chain patterns around the focal gene, from inferred GoF/LoF of each step."""
    out = []
    f = (focal.get("person") or {}).get("function")
    for l in links:
        for g in l["genes"]:
            p = (g.get("person") or {}).get("function")
            if not p or not f:
                continue
            up, down = (g["gene"], focal["gene"]) if l["direction"] == "upstream" else (focal["gene"], g["gene"])
            fu, fd = (p, f) if l["direction"] == "upstream" else (f, p)
            kind = ("pile-up" if fu == "GoF" and fd == "LoF" else
                    "bottleneck" if fu == "LoF" and fd == "LoF" else
                    "starved" if fu == "LoF" and fd in ("normal", "GoF") else
                    "fast flow" if fu == "GoF" and fd == "GoF" else None)
            if kind:
                out.append({"pattern": kind, "upstream": up, "upstream_function": fu, "metabolite": l["metabolite"],
                            "downstream": down, "downstream_function": fd})
    return out


def to_markdown(t):
    def tag(g):
        p = g.get("person")
        if not p:
            return g["gene"] + ("" if g["in_library"] else "*")
        return f"{g['gene']} [{p['function']}, {p['genotype']}, score {p['score']:.0f}]"
    f = t["focal"].get("person")
    lines = [f"# Gene trace: {t['gene']} ({t['accession']})", "",
             f"Your result: {tag(t['focal'])}" + (f": {f['interpretation']}" if f else " (not tested)"), "",
             "GoF/LoF is inferred from the library's interpretation text. * = gene not in the library (no genotype).", "",
             "## Reactions it catalyses"]
    for r in t["reactions"]:
        lines.append(f"- {', '.join(r['inputs']) or '?'} → {', '.join(r['outputs']) or '?'}  ({r['name']})")
    for direction, title in (("upstream", "Upstream: who makes its inputs"), ("downstream", "Downstream: who uses its outputs")):
        rows = [l for l in t["links"] if l["direction"] == direction]
        lines += ["", f"## {title}"]
        by_met = defaultdict(list)
        for l in rows:
            by_met[l["metabolite"]].append(l)
        for met, ls in by_met.items():
            lines.append(f"- **{met}**")
            # Library genes first: those are the steps we can read in a genome
            for l in sorted(ls, key=lambda l: (-sum(g["in_library"] for g in l["genes"]), l["reaction"]))[:8]:
                genes = sorted((tag(g) for g in l["genes"]), key=lambda s: (s.endswith("*"), s))
                lines.append(f"  - {l['reaction']}: {', '.join(genes[:8])}{' …' if len(genes) > 8 else ''}")
            if len(ls) > 8:
                lines.append(f"  - … {len(ls) - 8} more reactions")
        if not rows:
            lines.append("- none found in Reactome")
    if t["hub_metabolites"]:
        lines.append(f"\nHub metabolites (only library genes kept): {', '.join(t['hub_metabolites'])}")
    lines += ["", "## Cofactors and regulation", f"- Cofactors: {', '.join(t['cofactors']) or 'none listed'}"]
    for v, gs in t["cofactor_genes"].items():
        lines.append(f"- {v} supply genes in your library: {', '.join(tag(g) for g in gs) or 'none linked yet'}")
    if t["regulation"]:
        lines.append(f"- Regulation: {t['regulation']}")
    regs = [r for r in t["regulators"] if r["in_library"]] or t["regulators"][:8]
    lines += ["", "## Regulators (OmniPath, directed)"]
    for r in regs[:12]:
        arrow = f"{r['gene']} {r['effect']} {t['gene']}" if r["direction"] == "upstream" else f"{t['gene']} {r['effect']} {r['gene']}"
        lines.append(f"- {arrow} ({r['type']}) {tag(r) if r['in_library'] else ''}")
    lines += ["", "## Chain patterns in your genome"]
    for p in t["patterns"] or [{"pattern": None}]:
        if not p["pattern"]:
            lines.append("- none detected among tested neighbours")
            break
        lines.append(f"- **{p['pattern']}**: {p['upstream']} ({p['upstream_function']}) → {p['metabolite']} → "
                     f"{p['downstream']} ({p['downstream_function']})")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gene")
    ap.add_argument("--dna", default="data/input/MyHeritage_raw_dna_data_HP.csv")
    args = ap.parse_args()
    status = person_status(args.dna) if args.dna else {}
    result = trace(args.gene.upper(), status)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base = os.path.join(OUTPUT_DIR, f"trace_{args.gene.upper()}")
    json.dump(result, open(base + ".json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    md = to_markdown(result)
    open(base + ".md", "w", encoding="utf-8").write(md)
    print(md)
