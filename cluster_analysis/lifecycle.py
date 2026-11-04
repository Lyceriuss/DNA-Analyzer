# cluster_analysis/lifecycle.py
"""
Linear lifecycle of one gene: from the building block, through the steps that convert it,
the gene's own step, where the product goes and who acts on it next, to the point where it is
excreted, made inert, burned for energy or recycled.

    python -m cluster_analysis.lifecycle MTHFR ALDH2 [--dna data/input/X.csv] [--out file.json]

Within the gene's Reactome pathway, steps are ordered by Reactome's "preceding event" links and
by molecules/proteins passed from one step to the next (transport steps included: where the
product goes is part of its life). Beyond the pathway the chain is extended through shared
molecules (ChEBI) until it reaches a building block nothing in the body makes, or an exit.
Public identifiers only are sent to Reactome; the genotype overlay runs offline.
"""
import argparse
import json
import os
import re

from cluster_analysis import sources
from cluster_analysis.gene_trace import (CURRENCY, HUB_LIMIT, COFACTOR_VITAMIN, genes_for_accessions, omnipath,
                                         person_status, summarize, uniprot_entry)

REACTOME = "https://reactome.org/ContentService"
OUTPUT_DIR = "data/output/cluster_analysis"
MAX_PATHWAY_STEPS = 10
MAX_EXTENSION = 4

EXCRETED = re.compile(r"\burea\b|urate|uric acid|creatinine|glucuronide|sulfate|sulphate|hippur|oxalate|bilirubin|"
                      r"mercaptur|\bCO2\b|carbon dioxide|ammonia|NH4|NH3|taurocholate|glycocholate|calcitroic|\bCTA\b", re.I)
CENTRAL = re.compile(r"acetyl-CoA|\bAc-?CoA\b|\bpyruvate|\bPYR\b|succinate|fumarate|2-oxoglutarate|\b2OG\b|\bcitrate|"
                     r"oxaloacetate|\bOAA\b|\bmalate", re.I)


def _get(path):
    return sources._request("GET", f"{REACTOME}{path}", ok_404=True, timeout=90)


def _base(name):
    return re.sub(r"\s*\[[^\]]*\]$", "", name or "").strip()


def _compartment(name):
    m = re.search(r"\[([^\]]*)\]$", name or "")
    return m.group(1) if m else ""


def event(ref):
    """One Reactome reaction with its participants resolved. ref: stId or dbId."""
    def fetch():
        q = _get(f"/data/query/{ref}") or {}
        if not str(q.get("stId", "")).startswith("R-"):
            q = {}  # not a Reactome event (e.g. a protein isoform id): nothing to follow
        parts = (_get(f"/data/participants/{q['stId']}") or []) if q else []
        dbid = lambda x: x["dbId"] if isinstance(x, dict) else x
        return {"stId": q.get("stId"), "dbId": q.get("dbId"), "name": q.get("displayName"), "schemaClass": q.get("schemaClass"),
                "input": [dbid(x) for x in q.get("input") or []], "output": [dbid(x) for x in q.get("output") or []],
                "preceding": [dbid(x) for x in q.get("precedingEvent") or []], "parts": parts}
    raw = sources._cached("lc_event", str(ref), fetch)
    pes = {}
    for p in raw["parts"]:
        refs = p.get("refEntities", [])
        chebi = [e["identifier"] for e in refs if e.get("schemaClass") == "ReferenceMolecule"]
        prots = [e["identifier"] for e in refs if e.get("schemaClass") == "ReferenceGeneProduct"]
        pes[p["peDbId"]] = {"pe": p["peDbId"], "name": p["displayName"], "base": _base(p["displayName"]),
                            "compartment": _compartment(p["displayName"]), "chebi": chebi[0] if len(chebi) == 1 and not prots else None,
                            "proteins": prots, "currency": bool(chebi) and not prots and all(c in CURRENCY for c in chebi)}
    ins = [pes[i] for i in raw["input"] if i in pes]
    outs = [pes[o] for o in raw["output"] if o in pes]
    io = {x["pe"] for x in ins + outs}
    catalysts = sorted({a for pe, p in pes.items() if pe not in io for a in p["proteins"]})
    if not catalysts:
        # Enzymes recorded inside an input complex (e.g. MTRR:MTR:cob(I)alamin) still do the work
        catalysts = sorted({a for x in ins for a in x["proteins"]})
    main = lambda xs: [x for x in xs if not x["currency"]]
    return {"stId": raw["stId"], "dbId": raw["dbId"], "name": raw["name"], "schemaClass": raw["schemaClass"],
            "preceding": raw["preceding"],
            "inputs": main(ins), "outputs": main(outs), "catalysts": catalysts,
            "transport": bool(ins) and {x["base"] for x in main(ins)} == {x["base"] for x in main(outs)}
                         and {x["compartment"] for x in main(ins)} != {x["compartment"] for x in main(outs)}}


def lowest_pathway(st_id):
    chains = sources._cached("lc_ancestors", st_id, lambda: _get(f"/data/event/{st_id}/ancestors") or [])
    for chain in chains:
        for p in chain:
            if p.get("schemaClass") in ("Pathway", "TopLevelPathway"):
                return {"stId": p["stId"], "name": p["displayName"], "top": chain[-1]["displayName"]}
    return None


def pathway_events(pw_id):
    rows = sources._cached("lc_contained", pw_id, lambda: _get(f"/data/pathway/{pw_id}/containedEvents") or [])
    refs = [r["dbId"] if isinstance(r, dict) else r for r in rows]
    evs = [event(r) for r in refs]
    return [e for e in evs if e["schemaClass"] and "Pathway" not in e["schemaClass"] and (e["inputs"] or e["outputs"])]


def chebi_events(chebi):
    rows = sources._cached("rx_chebi", chebi, lambda: _get(f"/data/mapping/ChEBI/{chebi}/reactions?species=9606") or [])
    return [r["stId"] for r in rows]


def norm(name):
    """Bridge molecule forms Reactome keeps apart: folate polyglutamates (THFPG) vs plain (THF), stereo prefixes."""
    n = _base(name).lower()
    n = re.sub(r"^\(\d*[rs]\)-", "", n)
    n = re.sub(r"\s*polyglutamate$|pg$", "", n)
    return n.strip()


def name_events(name):
    """Reactome reactions whose name mentions this molecule (fallback when ChEBI ids differ)."""
    q = norm(name)
    def fetch():
        d = _get(f"/search/query?query={sources.requests.utils.quote(q)}&types=Reaction&species=Homo%20sapiens&cluster=true&rows=25") or {}
        return [e["stId"] for g in d.get("results", []) for e in g.get("entries", [])]
    return sources._cached("lc_name", q, fetch)


# --- Chain building -------------------------------------------------------------------------

def links_between(a, b):
    """True if b follows a: explicit Reactome order, or a hands b an entity."""
    if a["dbId"] in b["preceding"]:
        return True
    return bool({x["pe"] for x in a["outputs"]} & {x["pe"] for x in b["inputs"]})


def step_score(e, library_accs):
    return 2 * len(set(e["catalysts"]) & library_accs) + (1 if e["catalysts"] else 0)


def new_side(e, upstream):
    """Small molecules a step would add to the chain: its inputs going upstream, its outputs going downstream.
    Proteins and complexes are carriers, not new chemistry, so they do not count."""
    return {norm(x["base"]) for x in (e["inputs"] if upstream else e["outputs"]) if x["chebi"]}


def walk(start, pool, library_accs, upstream, seen):
    """Linear walk inside the pathway. At each fork take the best step that adds new molecules; a step that
    only leads back to molecules already in the chain closes a cycle, and the walk stops there. Transport
    steps (same molecule, new compartment) are always allowed: where the product goes is part of its life."""
    chain, used, cur, closed = [], {start["dbId"]}, start, None
    for _ in range(MAX_PATHWAY_STEPS):
        cand = [e for e in pool if e["dbId"] not in used and (links_between(e, cur) if upstream else links_between(cur, e))]
        fresh = [e for e in cand if e["transport"] or new_side(e, upstream) - seen]
        if not fresh:
            if cand:
                closed = ", ".join(sorted(new_side(cand[0], upstream) & seen)) or None
            break
        fresh.sort(key=lambda e: -step_score(e, library_accs))
        nxt = fresh[0]
        chain.append({"event": nxt, "alternatives": fresh[1:4]})
        used.add(nxt["dbId"])
        seen |= {norm(x["base"]) for x in nxt["inputs"] + nxt["outputs"]}
        cur = nxt
    return chain, closed


def extend(edge_event, library_accs, upstream, seen):
    """Follow shared molecules beyond the pathway until a building block or an exit."""
    chain, cur = [], edge_event
    for _ in range(MAX_EXTENSION):
        mols = [m for m in (cur["inputs"] if upstream else cur["outputs"]) if m["chebi"]]
        if not mols:
            return chain, ("Starts from a protein or complex" if upstream else "Ends as a protein or complex")
        if upstream and any(m["compartment"] == "extracellular region" for m in mols):
            return chain, "Taken up from the blood: " + ", ".join(m["base"] for m in mols if m["compartment"] == "extracellular region")
        if not upstream:
            for m in mols:
                if EXCRETED.search(m["base"]):
                    return chain, f"Excreted or inert: {m['base']}"
                if CENTRAL.search(m["base"]):
                    return chain, f"Enters central energy metabolism as {m['base']}"
        best, best_mol, hub = None, None, False
        for m in mols:
            ids = chebi_events(m["chebi"])
            if len(ids) > HUB_LIMIT:
                hub, ids = True, []  # too generic to follow by id; the name search below is narrower
            # Same molecule under another form or name (e.g. 5-methyl-THFPG vs 5-methyl-THF)
            ids = list(dict.fromkeys(ids + name_events(m["base"])))
            for st in ids:
                e = event(st)
                if e["dbId"] in (cur["dbId"], edge_event["dbId"]) or not (e["inputs"] or e["outputs"]):
                    continue
                side = e["outputs"] if upstream else e["inputs"]
                if not any(x["chebi"] == m["chebi"] or norm(x["base"]) == norm(m["base"]) for x in side):
                    continue
                if upstream and new_side(e, upstream) and not (new_side(e, upstream) - seen):
                    continue  # would only go back to molecules already in the chain
                # Uptake from blood is a valid start; other moves are not chemical steps
                uptake = upstream and e["transport"] and any(x["compartment"] == "extracellular region" for x in e["inputs"])
                if e["transport"] and not uptake:
                    continue
                # Going upstream, side reactions (a drug releasing ethanol) are not the source of a building
                # block: only follow a producer that is a library gene or an uptake from the blood
                if upstream and not uptake and not (set(e["catalysts"]) & library_accs):
                    continue
                if best is None or step_score(e, library_accs) > step_score(best, library_accs):
                    best, best_mol = e, m
        if best is None:
            names = ", ".join(m["base"] for m in mols)
            if upstream:
                return chain, (f"Starts at {names}, a molecule shared by many pathways" if hub
                               else f"Starts at {names}: no source among the library genes (often diet, circulation or general metabolism)")
            return chain, (f"Joins a hub molecule shared by many pathways: {names}" if hub
                           else f"No further step mapped after {names}")
        chain.append({"event": best, "alternatives": [], "via": best_mol["base"]})
        followed = new_side(best, upstream)
        if not upstream and followed and not (followed - seen):
            return chain, f"Recycled: {', '.join(sorted(followed))} goes back into the cycle"
        seen |= {norm(x["base"]) for x in best["inputs"] + best["outputs"]}
        cur = best
    return chain, "Chain continues beyond this view (step limit reached)"


def lifecycle(gene, status, library_genes, max_roles=3):
    """One lifecycle per pathway the gene works in (its 'roles'), most library-relevant first."""
    entry = uniprot_entry(gene)
    if not entry:
        return {"gene": gene, "error": "No reviewed human UniProt entry"}
    acc = entry["primaryAccession"]
    own_ids = sources._cached("rx_protein", acc, lambda: _get(f"/data/mapping/UniProt/{acc}/reactions?species=9606") or [])
    own = [event(r["stId"]) for r in own_ids]
    own = [e for e in own if e["inputs"] or e["outputs"]]
    if not own:
        return {"gene": gene, "accession": acc, "error": "No Reactome reactions for this protein", "roles": []}

    # Group the gene's own steps by pathway; rank pathways by library genes involved, catalysed steps first
    by_pw = {}
    for e in sorted(own, key=lambda e: acc not in e["catalysts"]):
        pw = lowest_pathway(e["stId"])
        key = pw["stId"] if pw else e["stId"]
        by_pw.setdefault(key, {"pathway": pw, "events": []})["events"].append(e)
    acc_gene_all = {}
    ranked = []
    for key, grp in by_pw.items():
        pool = pathway_events(grp["pathway"]["stId"]) if grp["pathway"] else []
        accs = {a for e in pool + grp["events"] for a in e["catalysts"]}
        acc_gene_all.update(genes_for_accessions(accs | {acc}))
        n_lib = len({acc_gene_all.get(a) for a in accs} & library_genes)
        catalysed = any(acc in e["catalysts"] for e in grp["events"])
        ranked.append((catalysed, n_lib, len(pool), key, grp, pool))
    ranked.sort(key=lambda r: (not r[0], -r[1], -r[2]))

    # Build several candidate roles, then keep those whose chain involves the most library genes
    built = [build_role(gene, acc, grp, pool, status, library_genes) for *_, grp, pool in ranked[:max_roles + 3]]
    in_chain = lambda role: len({g["gene"] for s in role["steps"] for g in s["genes"] if g["in_library"]})
    built.sort(key=lambda role: (-in_chain(role), -len(role["steps"])))
    roles = built[:max_roles]
    return finish(gene, acc, entry, roles, library_genes, other_pathways=len(ranked) - len(roles))


def build_role(gene, acc, grp, pool, status, library_genes):
    focal = grp["events"][0]
    pw = grp["pathway"]
    pool = [e for e in pool if e["dbId"] != focal["dbId"]]
    lib_accs_map = genes_for_accessions({a for e in pool + [focal] for a in e["catalysts"]} | {acc})
    library_accs = {a for a, g in lib_accs_map.items() if g in library_genes}

    seen = {norm(x["base"]) for x in focal["inputs"] + focal["outputs"]}
    up, up_cycle = walk(focal, pool, library_accs, True, seen)
    down, down_cycle = walk(focal, pool, library_accs, False, seen)
    if up_cycle:
        up_ext, start_reason = [], f"Cycle: {up_cycle} is regenerated inside {pw['name'] if pw else 'the pathway'}"
    else:
        up_ext, start_reason = extend((up[-1]["event"] if up else focal), library_accs, True, seen)
    if down_cycle:
        down_ext, end_reason = [], f"Recycled: {down_cycle} goes back into the cycle"
    else:
        down_ext, end_reason = extend((down[-1]["event"] if down else focal), library_accs, False, seen)

    ordered = ([("upstream-extension", s) for s in reversed(up_ext)] + [("pathway", s) for s in reversed(up)]
               + [("focal", {"event": focal, "alternatives": grp["events"][1:4]})]
               + [("pathway", s) for s in down] + [("downstream-extension", s) for s in down_ext])

    all_accs = {a for _, s in ordered for e in [s["event"]] + s["alternatives"] for a in e["catalysts"]}
    acc_gene = genes_for_accessions(all_accs | {acc})
    gstat = lambda g: {"gene": g, "in_library": g in library_genes, "person": summarize(status.get(g))}

    def step(section, s):
        e = s["event"]
        genes = sorted({acc_gene.get(a, a) for a in e["catalysts"]})
        return {"section": section, "reaction": e["name"], "reaction_id": e["stId"], "transport": e["transport"],
                "inputs": [m["base"] for m in e["inputs"]], "outputs": [m["base"] for m in e["outputs"]],
                "compartment_in": sorted({m["compartment"] for m in e["inputs"]}),
                "compartment_out": sorted({m["compartment"] for m in e["outputs"]}),
                "genes": [gstat(g) for g in genes],
                "alternatives": [{"reaction": a["name"], "genes": sorted({acc_gene.get(x, x) for x in a["catalysts"]})}
                                 for a in s["alternatives"]]}

    return {"pathway": pw, "focal_reaction": focal["name"], "start": start_reason, "end": end_reason,
            "steps": [step(sec, s) for sec, s in ordered]}


def finish(gene, acc, entry, roles, library_genes, other_pathways):
    cofactors, regulation = [], None
    for c in entry.get("comments", []):
        if c["commentType"] == "COFACTOR":
            cofactors += [x["name"] for x in c.get("cofactors", [])]
        if c["commentType"] == "ACTIVITY REGULATION":
            regulation = c["texts"][0]["value"]
    regulators = [{"gene": x["source_genesymbol"], "effect": "activates" if x["is_stimulation"] else
                   "inhibits" if x["is_inhibition"] else "acts on", "in_library": x["source_genesymbol"] in library_genes}
                  for x in omnipath(gene) if x.get("is_directed") and x["target_genesymbol"] == gene]
    return {"gene": gene, "accession": acc, "roles": roles, "other_pathways": other_pathways,
            "cofactors": cofactors,
            "cofactor_vitamins": sorted({v for cf in cofactors for rx, v in COFACTOR_VITAMIN if re.search(rx, cf, re.I)}),
            "regulation": regulation,
            "regulators": sorted(regulators, key=lambda r: (not r["in_library"], r["gene"]))[:10]}


def to_text(lc):
    if lc.get("error"):
        return f"{lc['gene']}: {lc['error']}"
    tag = lambda g: g["gene"] + (f" [{g['person']['function']} {g['person']['genotype']}]" if g.get("person") else "" if g["in_library"] else "*")
    lines = []
    for i, role in enumerate(lc["roles"], 1):
        lines += [f"=== {lc['gene']} role {i}: {role['pathway']['name'] if role['pathway'] else 'no pathway'}", f"START  {role['start']}"]
        for s in role["steps"]:
            mark = ">>" if s["section"] == "focal" else "  "
            move = " (transport " + "/".join(s["compartment_in"]) + " -> " + "/".join(s["compartment_out"]) + ")" if s["transport"] else ""
            lines.append(f"{mark} {', '.join(s['inputs']) or '?'}  -->  {', '.join(s['outputs']) or '?'}{move}")
            lines.append(f"     by {', '.join(tag(g) for g in s['genes']) or 'no enzyme listed'}   [{s['section']}]")
        lines.append(f"END    {role['end']}\n")
    if lc["cofactor_vitamins"]:
        lines.append(f"Cofactors: {', '.join(lc['cofactors'])} -> {', '.join(lc['cofactor_vitamins'])}")
    if lc["regulation"]:
        lines.append(f"Regulation: {lc['regulation'][:200]}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("genes", nargs="+")
    ap.add_argument("--dna", default="data/input/MyHeritage_raw_dna_data_HP.csv")
    ap.add_argument("--out")
    args = ap.parse_args()
    status = person_status(args.dna) if args.dna else {}
    lib = json.load(open("cluster_analysis/modules.json", encoding="utf-8"))
    library_genes = {g for r in lib["rsids"].values() for g in r["genes"]}
    results = []
    for g in args.genes:
        try:
            lc = lifecycle(g.upper(), status, library_genes)
        except Exception as e:  # one gene's API failure should not lose the others
            lc = {"gene": g.upper(), "error": f"{type(e).__name__}: {str(e)[:200]}", "roles": []}
        results.append(lc)
        print(to_text(lc), "\n", flush=True)
        if args.out:  # save after every gene
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
