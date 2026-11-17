# cluster_analysis/evidence/systems.py
"""
Body systems: the person's gene calls (gene_calls.py) grouped by Reactome's top-level pathways, with STRING interactions
between the changed genes. Feeds the Body systems view of the Biomarkers tab.

    python -m cluster_analysis.evidence.systems --person XY

The rule, not a curated list:
  systems   Reactome's top-level human pathways (those with no parent), Disease left out. Metabolism is split into its
            own children, the large ones on their own and the rest as "Other metabolism", since it holds a third of
            all genes. A gene sits in every system Reactome places it in (Ensembl2Reactome, lowest-level pathways
            rolled up through ReactomePathwaysRelation).
  calls     gene_calls_<person>.json: more active (GoF), less active (LoF) or changed in an unclear direction, each
            with its basis (a measured or curated protein change, a prediction, or expression from GTEx).
  pairs     STRING high-confidence interactions (combined score >= 0.7) between two changed genes of one system.
  reach     a changed gene's interactions with changed genes in other systems, summed per system.

Reactome and the sources behind the calls say whether a gene works more or less, not whether that is good or bad for
the person, so the view shows direction only.

Writes data/output/cluster_analysis/profiles/<id>/sys_systems.json, sys_genes.json, sys_links.json, sys_bridges.json.
"""
import argparse
import gzip
import json
import os
import re
from collections import defaultdict

from cluster_analysis import profiles, sources
from genome import build as gbuild

REF = "data/reference"
DISEASE = "R-HSA-1643685"
METABOLISM = "R-HSA-1430728"
MIN_OWN = 15          # a child of Metabolism with fewer read genes joins "Other metabolism"
STRING_SCORE = 700    # STRING high confidence
CHANGED = ("LoF", "GoF", "altered")


def reactome_systems():
    """Ensembl gene → set of system names."""
    names, parents = {}, defaultdict(set)
    for line in open(f"{REF}/ReactomePathways.txt", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 3 and p[2] == "Homo sapiens":
            names[p[0]] = p[1]
    for line in open(f"{REF}/ReactomePathwaysRelation.txt", encoding="utf-8"):
        a, b = line.split()
        if a.startswith("R-HSA"):
            parents[b].add(a)

    memo = {}

    def roots(pid):
        """The systems a pathway belongs to: its top-level ancestors, or Metabolism's child under Metabolism."""
        if pid in memo:
            return memo[pid]
        out = set()
        for par in parents.get(pid, ()):
            out |= {pid} if par == METABOLISM else roots(par)
        if not parents.get(pid):
            out = {pid}
        memo[pid] = out
        return out

    by_gene = defaultdict(set)
    for line in open(f"{REF}/Ensembl2Reactome.txt", encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 6 and p[5] == "Homo sapiens" and p[1] in names:
            for r in roots(p[1]):
                if r != DISEASE and r != METABOLISM:
                    by_gene[p[0]].add(r)
    return by_gene, names, {k for k, v in parents.items() if METABOLISM in v}


def symbols_to_ensembl(genes):
    ensg = defaultdict(set)
    with gzip.open(gbuild.path("gtf"), "rt", encoding="utf-8") as f:
        for line in f:
            if "\tgene\t" in line:
                m = re.search(r'gene_id "([^"]+)".*?gene_name "([^"]+)"', line)
                if m and m.group(2) in genes:
                    ensg[m.group(2)].add(m.group(1).split(".")[0])
    return ensg


def run(pid):
    calls = json.load(open(os.path.join(gbuild.OUTPUT, f"gene_calls_{pid}.json"), encoding="utf-8"))
    read = {g: c for g, c in calls.items() if c.get("function") != "unknown"}
    by_ensg, names, metab_children = reactome_systems()
    ensg = symbols_to_ensembl(set(read))
    gene_sys = {g: set().union(*(by_ensg.get(e, set()) for e in ensg.get(g, ()))) for g in read}

    # Metabolism's small children join "Other metabolism"
    size = defaultdict(int)
    for g, ss in gene_sys.items():
        for s in ss:
            size[s] += 1
    label = {s: names[s] for s in size}
    for s in size:
        if s in metab_children and size[s] < MIN_OWN:
            label[s] = "Other metabolism"
    members = defaultdict(set)
    for g, ss in gene_sys.items():
        for s in ss:
            members[label[s]].add(g)

    changed = sorted(g for g in read if read[g]["function"] in CHANGED and gene_sys.get(g))
    edges = []
    if changed:
        for e in sources.string_network(changed, required_score=STRING_SCORE):
            a, b = e.get("preferredName_A"), e.get("preferredName_B")
            if a in read and b in read and a != b:
                edges.append((a, b, float(e["score"])))
    seen, uniq = set(), []
    for a, b, s in edges:
        k = tuple(sorted((a, b)))
        if k not in seen:
            seen.add(k)
            uniq.append((k[0], k[1], s))

    systems, genes, links, bridges = [], [], [], []
    for name, gs in sorted(members.items()):
        ch = [g for g in gs if read[g]["function"] in CHANGED]
        by = {f: sorted(g for g in ch if read[g]["function"] == f) for f in CHANGED}
        systems.append({"system": name, "read": len(gs), "lof": len(by["LoF"]), "gof": len(by["GoF"]), "altered": len(by["altered"]),
                        "lof_genes": ", ".join(by["LoF"]), "gof_genes": ", ".join(by["GoF"]), "altered_genes": ", ".join(by["altered"])})
        for g in sorted(ch):
            c = read[g]
            genes.append({"system": name, "gene": g, "function": c["function"], "basis": c.get("basis"), "detail": c.get("detail"),
                          "rsid": c.get("rsid"), "genotype": c.get("genotype")})
        chs = set(ch)
        for a, b, s in uniq:
            if a in chs and b in chs:
                links.append({"system": name, "gene_a": a, "gene_b": b, "fn_a": read[a]["function"], "fn_b": read[b]["function"], "score": s})
        for g in sorted(ch):
            reach = defaultdict(float)
            for a, b, s in uniq:
                other = b if a == g else a if b == g else None
                if not other:
                    continue
                for o in members:
                    if o != name and other in members[o] and other not in gs:
                        reach[o] += s
            if reach:
                top = sorted(reach.items(), key=lambda x: -x[1])[:3]
                bridges.append({"system": name, "gene": g, "function": read[g]["function"],
                                "reaches": json.dumps([{"system": o, "weight": round(w, 2)} for o, w in top], ensure_ascii=False),
                                "total_weight": round(sum(reach.values()), 2)})
    bridges.sort(key=lambda r: -r["total_weight"])

    od = profiles.out_dir(pid)
    for n, rows in (("sys_systems", systems), ("sys_genes", genes), ("sys_links", links), ("sys_bridges", bridges)):
        json.dump(rows, open(os.path.join(od, n + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{pid}: {len(read)} genes read, {len(changed)} changed in a system, {len(systems)} systems, "
          f"{len(uniq)} STRING pairs among changed genes")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--person", nargs="*", help="profile ids (default: every profile with gene calls)")
    a = ap.parse_args()
    for p in a.person or [p["id"] for p in profiles.load()]:
        if os.path.exists(os.path.join(gbuild.OUTPUT, f"gene_calls_{p}.json")):
            run(p)
