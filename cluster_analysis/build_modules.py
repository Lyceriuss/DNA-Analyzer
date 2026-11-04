# cluster_analysis/build_modules.py
"""
Builds functional modules ("clusters") from the gene library in config/snp_traits.json.

    python -m cluster_analysis.build_modules [--no-gwas] [--min-score 400] [--resolution 2.0]

Uses public data only (gene symbols + rsIDs), so the output, cluster_analysis/modules.json,
contains no personal data and can be committed. Person-specific scoring is done in overlay.py.
"""
import argparse
import json
import os
import re
from datetime import date

import networkx as nx

from cluster_analysis import sources

TRAITS_PATH = "config/snp_traits.json"
MODULES_PATH = os.path.join(os.path.dirname(__file__), "modules.json")


# Library names that are not gene symbols at all
ALIASES = {"TNF-alpha": "TNF", "HLA-DQ8": "HLA-DQB1"}


def candidate_symbols(gene_field):
    """'IL1B (Promoter)' -> ['IL1B'], 'CDKN2A/B' -> ['CDKN2A', 'CDKN2B'], 'GLUT9 (SLC2A9)' -> ['GLUT9', 'SLC2A9']."""
    if gene_field in ALIASES:
        return [ALIASES[gene_field]]
    head, _, paren = gene_field.partition("(")
    head = head.strip()
    if re.fullmatch(r"[A-Z0-9]+/[A-Z0-9]", head):  # CDKN2A/B
        base = head.split("/")[0]
        return [base, base[:-1] + head[-1]]
    names = [head]
    paren = paren.rstrip(")").strip()
    if re.fullmatch(r"[A-Z0-9-]{2,}", paren):  # an alternative symbol, not "Promoter"/"Flush"
        names.append(paren)
    return names


def resolve_library(traits):
    """Returns {rsid: [STRING preferred symbols]} for every trait in the library."""
    queries = sorted({c for info in traits.values() for c in candidate_symbols(info["gene"])})
    resolved = sources.string_resolve(queries)
    # A batch returns one row per protein, so aliases of an already-queried gene
    # (BCMO1 next to BCO1) go missing. Retry those one by one.
    for q in queries:
        if q not in resolved:
            resolved.update(sources.string_resolve([q]))

    rsid_genes = {}
    for rsid, info in traits.items():
        candidates = candidate_symbols(info["gene"])
        hits = [resolved[c] for c in candidates if c in resolved]
        if not hits:
            # Not a protein in STRING (lncRNA like CDKN2B-AS1, or GPX1). Keep the symbol:
            # it still gets summaries and GWAS data, it just cannot join a module.
            print(f"   [i] {rsid}: '{info['gene']}' not in STRING, kept as unlinked gene")
            hits = candidates[:1]
        if "/" in info["gene"]:
            rsid_genes[rsid] = sorted(set(hits))  # locus spanning two genes
        else:
            rsid_genes[rsid] = hits[:1]           # first resolvable name wins
    return rsid_genes


def build(min_score, resolution, with_gwas):
    with open(TRAITS_PATH, "r", encoding="utf-8") as f:
        traits = json.load(f)

    print("🔎 Resolving gene symbols via STRING...")
    rsid_genes = resolve_library(traits)
    genes = sorted({g for gs in rsid_genes.values() for g in gs})
    print(f"   {len(traits)} traits -> {len(genes)} genes")

    print("🕸️  Fetching interaction network...")
    edges = sources.string_network(genes, required_score=min_score)
    G = nx.Graph()
    G.add_nodes_from(genes)
    for e in edges:
        G.add_edge(e["preferredName_A"], e["preferredName_B"], score=e["score"])
    print(f"   {G.number_of_edges()} interactions (STRING score >= {min_score / 1000})")

    communities = nx.community.louvain_communities(G, weight="score", resolution=resolution, seed=42)
    communities = [set(c) for c in communities]
    # At high resolution Louvain leaves big hubs (IL6: 100+ partners) on their own because they
    # connect to everything. Put each such hub where its interactions are strongest.
    for c in [c for c in communities if len(c) == 1]:
        gene = next(iter(c))
        if G.degree(gene) == 0:
            continue
        ties = {i: sum(G[gene][n]["score"] for n in G[gene] if n in other)
                for i, other in enumerate(communities) if other is not c}
        communities[max(ties, key=ties.get)].add(gene)
        c.clear()
    communities = sorted((sorted(c) for c in communities if c), key=len, reverse=True)

    print("🧪 Enriching modules...")
    modules, gene_module = [], {}
    unlinked = []
    for comm in communities:
        if len(comm) == 1:
            unlinked.extend(comm)
            continue
        module_id = f"M{len(modules) + 1:02d}"
        enrichment = sources.string_enrichment(comm)
        # Label with a biological process when one is enriched; WikiPathways tends to
        # rank disease collections ("ADHD and autism pathways") first
        processes = [e for e in enrichment if e["category"] == "Process"]
        label = (processes or enrichment)[0]["description"] if enrichment else " / ".join(comm)
        sub = G.subgraph(comm)
        modules.append({
            "id": module_id,
            "label": label,
            "genes": comm,
            "hubs": [g for g, _ in sorted(sub.degree(weight="score"), key=lambda x: -x[1])[:3]],
            "enrichment": enrichment,
            "edges": [[a, b, round(d["score"], 3)] for a, b, d in sub.edges(data=True)],
        })
        for g in comm:
            gene_module[g] = module_id
        print(f"   {module_id} ({len(comm):>2} genes) {label}")
    print(f"   {len(unlinked)} genes have no interaction with the rest of the library")

    # Bridge genes: summed interaction weight into modules other than their own
    bridges = {}
    for g in G.nodes:
        own = gene_module.get(g)
        ties = {}
        for n in G[g]:
            m = gene_module.get(n)
            if m and m != own:
                ties[m] = ties.get(m, 0) + G[g][n]["score"]
        strong = {m: round(w, 2) for m, w in sorted(ties.items(), key=lambda x: -x[1]) if w >= 1.5}
        if strong:
            bridges[g] = strong

    print("📚 Fetching gene summaries...")
    info = sources.mygene_info(genes)

    rsids = {}
    if with_gwas:
        print(f"📈 Fetching GWAS associations for {len(traits)} rsIDs (cached after first run)...")
    for i, (rsid, gs) in enumerate(rsid_genes.items(), 1):
        rsids[rsid] = {"genes": gs, "gwas": sources.gwas_traits(rsid) if with_gwas else []}
        if with_gwas and i % 50 == 0:
            print(f"   {i}/{len(traits)}")

    out = {
        "meta": {
            "built": date.today().isoformat(),
            "sources": ["STRING v12 (network, enrichment)", "MyGene.info", "GWAS Catalog v2"],
            "string_min_score": min_score / 1000,
            "louvain_resolution": resolution,
        },
        "modules": modules,
        "unlinked_genes": unlinked,
        "genes": {g: {**info.get(g, {}), "module": gene_module.get(g),
                      "bridges_to": bridges.get(g, {})} for g in genes},
        "rsids": rsids,
    }
    with open(MODULES_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"✅ Wrote {MODULES_PATH}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-score", type=int, default=400, help="STRING confidence 0-1000 (400 = medium)")
    ap.add_argument("--resolution", type=float, default=2.0, help="Louvain resolution; higher = smaller modules")
    ap.add_argument("--no-gwas", action="store_true", help="skip per-rsID GWAS lookups")
    args = ap.parse_args()
    build(args.min_score, args.resolution, not args.no_gwas)
