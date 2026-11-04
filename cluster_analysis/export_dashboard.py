# cluster_analysis/export_dashboard.py
"""
Bundles public library data (modules, module links, genes, SNPs, biomarkers) into one JSON
for dashboards and the future interactive interface. Contains no personal data.

    python -m cluster_analysis.export_dashboard out/library_bundle.json [--person overlay.json]

--person embeds an overlay result (use only synthetic or consented data in anything you share).
"""
import argparse
import glob
import json
import os
import re
from collections import defaultdict

from cluster_analysis.biomarkers import BIOMARKERS_PATH
from cluster_analysis.build_modules import MODULES_PATH

TRAITS_PATH = "config/snp_traits.json"
NAMES_PATH = os.path.join(os.path.dirname(__file__), "module_names.json")


def first_sentence(text, limit=200):
    s = (text or "").split(". ")[0]
    return (s[:limit] + "...") if len(s) > limit else s + ("." if s else "")


def bundle():
    lib = json.load(open(MODULES_PATH, encoding="utf-8"))
    bio = json.load(open(BIOMARKERS_PATH, encoding="utf-8"))["biomarkers"]
    traits = json.load(open(TRAITS_PATH, encoding="utf-8"))
    names = json.load(open(NAMES_PATH, encoding="utf-8"))

    # Symmetric module-to-module weight from bridge genes
    links = defaultdict(float)
    for g, info in lib["genes"].items():
        for other, w in (info.get("bridges_to") or {}).items():
            if info.get("module"):
                links[tuple(sorted((info["module"], other)))] += w

    return {
        "meta": {"built": lib["meta"]["built"], "n_snps": len(traits), "n_genes": len(lib["genes"]),
                 "n_modules": len(lib["modules"]), "n_biomarkers": len(bio),
                 "sources": lib["meta"]["sources"] + ["Ensembl GRCh38 (alleles, frequencies)"]},
        "modules": [{"id": m["id"], "name": names.get(m["label"], m["label"]), "label": m["label"],
                     "size": len(m["genes"]), "genes": m["genes"],
                     "hubs": m["hubs"], "enrichment": [e["description"] for e in m["enrichment"][:4]]}
                    for m in lib["modules"]],
        "module_links": [{"a": a, "b": b, "w": round(w, 2)} for (a, b), w in sorted(links.items(), key=lambda x: -x[1])],
        "genes": {g: {"module": i.get("module"), "name": i.get("name", ""), "summary": first_sentence(i.get("summary")),
                      "bridges_to": i.get("bridges_to", {})} for g, i in lib["genes"].items()},
        "snps": {r: {"genes": d["genes"], "trait": traits.get(r, {}).get("trait", ""),
                     "gwas": [t["trait"] for t in d["gwas"][:3]]} for r, d in lib["rsids"].items()},
        "biomarkers": [{k: b[k] for k in ("biomarker", "panel", "n_snps", "modules")} |
                       {"snps": [{k: s[k] for k in ("rsid", "genes", "modules", "effect_allele", "direction", "strand",
                                                    "eaf_eur", "p_value", "pubmed_id", "first_author")} for s in b["snps"]]}
                       for b in bio],
    }


EVIDENCE_PATH = os.path.join(os.path.dirname(__file__), "function_evidence.json")
LITERATURE_PATH = os.path.join(os.path.dirname(__file__), "literature.json")
TIER_NAMES = {1: "Measured protein function (MaveDB)", 2: "Curated functional effect (UniProt)",
              3: "Expression effect (GTEx)", 4: "Predicted damage only (SIFT/PolyPhen)", 5: "No functional evidence"}
CLINPGX_LEVEL = {"1A": 0, "1B": 1, "2A": 2, "2B": 3, "3": 4, "4": 5}


def _copies(genotype, allele, alleles):
    """Copies of a forward-strand allele in a genotype, flipping the genotype's strand when needed."""
    if not genotype or not allele:
        return None
    gt = genotype if set(genotype) <= set(alleles) else genotype.translate(str.maketrans("ACGT", "TGCA"))
    return gt.count(allele)


def evidence_summary(ev, genotype):
    """The function evidence for one SNP, reduced to what a reader needs next to the genotype."""
    src = ev.get("sources", {})
    out = {"tier": ev.get("tier", 5), "tier_name": TIER_NAMES.get(ev.get("tier", 5)), "consequence": ev.get("consequence"),
           "protein_change": ev.get("protein_change")}
    if src.get("mavedb"):
        out["mavedb"] = [{"conditions": m["conditions"], "score": round(m["score"], 3), "change": m["change"]}
                         for m in src["mavedb"]][:8]
    g = src.get("gtex")
    if g and g.get("own_gene"):
        _, _, ref, alt, _ = g["variant_id"].split("_")
        top = g["top"][0] if g.get("top") else None
        out["gtex"] = {"allele": g["effect_allele"], "copies": _copies(genotype, g["effect_allele"], [ref, alt]),
                       "n_tissues": g["n_tissues"], "direction": "raises" if top and top["nes"] > 0 else "lowers",
                       "tissue": top["tissue"].replace("_", " ") if top else None, "nes": top["nes"] if top else None}
    if src.get("uniprot", {}).get("functional"):
        out["uniprot"] = src["uniprot"]["functional"][:4]
    if src.get("predicted"):
        out["predicted"] = [f"{x['tool']}: {x['call']}" for x in src["predicted"]]
    pgx = sorted(src.get("clinpgx") or [], key=lambda x: CLINPGX_LEVEL.get(x["level"], 9))[:3]
    if pgx:
        out["clinpgx"] = [{"level": x["level"], "chemicals": ", ".join(x["chemicals"]),
                           "phenotype": next((y["phenotype"] for y in x["genotypes"] if genotype and y["genotype"] in
                                              {genotype, genotype[::-1]}), None)} for x in pgx]
    return out


def genotype_ladder(rsid, common, minor, traits, ev):
    """Every library genotype at a SNP, from the common homozygote to the less common one: library reading, report
    score and, where MaveDB measured the protein change, an activity estimate as a share of the common form. The
    estimate is additive: each allele contributes half, the common allele 1 and the variant its measured score."""
    entry = traits.get(rsid)
    if not entry or not common or not minor:
        return []
    flip = str.maketrans("ACGT", "TGCA")
    rows = {}
    for key, text in entry["variants"].items():
        gt = "".join(sorted(key))
        oriented = gt if set(gt) <= {common, minor} else gt.translate(flip)
        if not set(oriented) <= {common, minor} or gt in rows:
            continue
        rows[gt] = {"genotype": gt, "dose": oriented.count(minor), "text": text, "score": entry["scores"].get(key)}
    mave = [m["score"] for m in (ev.get("mavedb") or [])]
    for r in rows.values():
        if mave:
            r["capacity"] = [round(((2 - r["dose"]) + r["dose"] * min(mave)) / 2, 2), round(((2 - r["dose"]) + r["dose"] * max(mave)) / 2, 2)]
        elif r["dose"] == 0:
            r["capacity"] = [1.0, 1.0]
    return sorted(rows.values(), key=lambda r: r["dose"])


def lifecycle_rows(lifecycles, status=None):
    """Flattens lifecycle.py output into (steps, genes, gene_function) row lists for dashboards.
    Contains genotypes when the lifecycles were built with a DNA file. status ({gene: summarized person call},
    from gene_trace.person_status) replaces the calls stored in the lifecycles, so a new function call
    does not need new API walks."""
    status = status or {}
    traits = json.load(open(TRAITS_PATH, encoding="utf-8"))
    evidence = {e["rsid"]: e for e in json.load(open(EVIDENCE_PATH, encoding="utf-8"))}
    literature = json.load(open(LITERATURE_PATH, encoding="utf-8")) if os.path.exists(LITERATURE_PATH) else {}
    person = lambda g: status.get(g["gene"]) or g.get("person") or {}

    def chip(g):
        p = person(g)
        return {"gene": g["gene"], "lib": g["in_library"], "gt": p.get("genotype"), "fn": p.get("function"),
                "dose": p.get("dose"), "score": p.get("score")}

    steps, genes, seen = [], [], {}
    with_lifecycle = {lc["gene"] for lc in lifecycles if lc.get("roles")}
    for lc in lifecycles:
        for ri, role in enumerate(lc.get("roles") or [], 1):
            fp = status.get(lc["gene"]) or next((g.get("person") for s in role["steps"] for g in s["genes"]
                                                  if g["gene"] == lc["gene"] and g.get("person")), None) or {}
            genes.append({
                "gene": lc["gene"], "role": ri, "pathway": (role.get("pathway") or {}).get("name", "Unmapped"),
                "top_pathway": (role.get("pathway") or {}).get("top", ""), "n_steps": len(role["steps"]),
                "start": role["start"], "end": role["end"], "genotype": fp.get("genotype"), "function": fp.get("function"),
                "score": fp.get("score"), "interpretation": fp.get("interpretation"),
                "cofactors": ", ".join(lc.get("cofactors") or []), "vitamins": ", ".join(lc.get("cofactor_vitamins") or []),
                "regulation": lc.get("regulation") or "",
                "regulators": json.dumps([{"gene": r["gene"], "effect": r["effect"], "lib": r["in_library"]}
                                          for r in (lc.get("regulators") or [])]),
                "other_pathways": lc.get("other_pathways", 0)})
            for i, s in enumerate(role["steps"]):
                for g in s["genes"]:
                    if g["in_library"]:
                        seen[g["gene"]] = g
                steps.append({
                    "gene": lc["gene"], "role": ri, "order": i, "section": s["section"], "reaction": s["reaction"],
                    "reaction_id": s["reaction_id"], "inputs": ", ".join(s["inputs"]), "outputs": ", ".join(s["outputs"]),
                    "transport": s["transport"],
                    "move": (" / ".join(s["compartment_in"]) + " → " + " / ".join(s["compartment_out"])) if s["transport"] else "",
                    "enzymes": json.dumps([chip(g) for g in s["genes"]]),
                    "alternatives": " | ".join(f"{a['reaction']} ({', '.join(a['genes']) or 'no enzyme'})" for a in s["alternatives"])})

    function = []
    for name in sorted(set(seen) | with_lifecycle):
        p = status.get(name) or (seen.get(name) or {}).get("person") or {}
        ev = evidence.get(p.get("rsid"), {}) if p else {}
        function.append({"gene": name, "has_lifecycle": name in with_lifecycle, "rsid": p.get("rsid"),
                         "genotype": p.get("genotype"), "function": p.get("function"), "dose": p.get("dose"),
                         "common": p.get("common"), "minor": p.get("minor"), "minor_af": p.get("minor_af"),
                         "score": p.get("score"), "interpretation": p.get("interpretation"), "n_snps": p.get("n_snps"),
                         "evidence": json.dumps(evidence_summary(ev, p.get("genotype")) if ev else {}),
                         "ladder": json.dumps(genotype_ladder(p.get("rsid"), p.get("common"), p.get("minor"), traits,
                                                              evidence_summary(ev, p.get("genotype")) if ev else {})),
                         "literature": json.dumps({k: v for k, v in literature.get(p.get("rsid"), {}).items()
                                                   if k in ("papers", "quotes", "hits")})})
    return steps, genes, function


THEMES_PATH = os.path.join(os.path.dirname(__file__), "themes.json")


def theme_rows(themes, status, with_lifecycle=()):
    """themes.json plus a person's calls → (meta, genes, links, pathways) rows for the explorer's theme clusters."""
    meta, genes, links, pathways = [], [], [], []
    for order, (tid, t) in enumerate(themes["themes"].items()):
        for fi, f in enumerate(t["facets"]):
            meta.append({"theme": tid, "theme_name": t["name"], "about": t["about"], "theme_order": order,
                         "facet": f["id"], "facet_name": f["name"], "core": f["core"], "facet_order": fi})
        for g, m in t["genes"].items():
            p = status.get(g) or {}
            genes.append({"theme": tid, "gene": g, "primary": m["primary"], "facets": json.dumps(list(m["facets"])),
                          "evidence": json.dumps(m["facets"]), "rsid": p.get("rsid"), "genotype": p.get("genotype"),
                          "function": p.get("function") if p.get("genotype") else None, "dose": p.get("dose"),
                          "minor": p.get("minor"), "interpretation": p.get("interpretation"), "score": p.get("score"),
                          "has_lifecycle": g in with_lifecycle})
        links += [{"theme": tid, **l} for l in t["links"]]
        pathways += [{"theme": tid, "pathway": x["pathway"], "genes": json.dumps(x["genes"]), "n": len(x["genes"]),
                      "on_theme": x["on_theme"]} for x in t["pathways"]]
    return meta, genes, links, pathways


def api_theme_rows(graph, xref, status, with_lifecycle=(), order=0, person=None):
    """theme_graph.py output plus a person's cross-reference → the same four theme datasets. Every gene is listed;
    notable ones (a library call, a finding where the person carries the allele, or an Open Targets score ≥ 0.8)
    are the ones the explorer draws."""
    tid = graph["theme"]
    xg = (xref or {}).get("genes", {})
    facets = graph["mechanisms"] + [{"id": "disease", "name": "Disease link, mechanism not yet known",
                                     "about": "Open Targets ties these genes to a fertility condition, but Gene Ontology has no reproductive "
                                              "mechanism for them yet."}]
    with_findings = sum(1 for g in xg.values() if g["findings"])
    stats = {"n_genes": len(graph["genes"]), "n_mechanism": sum(1 for g in graph["genes"].values() if g["mechanisms"]),
             "n_snps": (xref or {}).get("n_snps_in_theme_genes"), "n_genes_with_findings": with_findings,
             "pathogenic_measured": (xref or {}).get("pathogenic", {}).get("measured"),
             "pathogenic_carried": (xref or {}).get("pathogenic", {}).get("carried", []), "rule": graph["rule"],
             "person": person, "sex": graph.get("sex"), "organs": graph.get("organs", []),
             "disease_organs": graph.get("disease_organs", {})}
    meta = [{"theme": tid, "theme_name": graph["name"], "about": graph["about"], "theme_order": order, "facet": f["id"],
             "facet_name": f["name"], "facet_about": f.get("about"), "organ": f.get("organ"), "core": True, "facet_order": i, "source": "api",
             "stats": json.dumps(stats)} for i, f in enumerate(facets)]
    genes, notable = [], set()
    for sym, g in graph["genes"].items():
        p = status.get(sym) or {}
        findings = xg.get(sym, {}).get("findings", [])
        carried = sum(1 for f in findings for it in f["items"] if it["source"] in ("GWAS", "ClinVar") and it.get("copies"))
        clinvar = any(it["source"] == "ClinVar" for f in findings for it in f["items"])
        # Genes with a reproductive mechanism are drawn when HP carries a finding; disease-only genes (many of them
        # hormone-level GWAS loci) only with a library call, a ClinVar entry or a very strong disease link
        is_notable = bool(p.get("genotype")) or g["best_score"] >= 0.8 or clinvar or (carried > 0 and bool(g["mechanisms"]))
        if is_notable:
            notable.add(sym)
        top = sorted(g["diseases"].items(), key=lambda kv: -kv[1]["score"])[:5]
        genes.append({"theme": tid, "gene": sym, "primary": g["primary"] or "disease",
                      "facets": json.dumps(list(g["mechanisms"]) or ["disease"]),
                      "evidence": json.dumps({"mechanisms": g["mechanisms"], "diseases": dict(top), "joined_by": g["joined_by"],
                                              "findings": findings, "n_snps": xg.get(sym, {}).get("n_snps", 0),
                                              "organs": g.get("organs", [])}),
                      "rsid": p.get("rsid"), "genotype": p.get("genotype"), "function": p.get("function") if p.get("genotype") else None,
                      "dose": p.get("dose"), "minor": p.get("minor"), "interpretation": p.get("interpretation"), "score": p.get("score"),
                      "has_lifecycle": sym in with_lifecycle, "source": "api", "notable": is_notable, "carried": carried,
                      "best_score": g["best_score"]})
    links = [{"theme": tid, **l} for l in graph["links"] if l["a"] in notable and l["b"] in notable]
    pathways = [{"theme": tid, "pathway": x["pathway"], "genes": json.dumps([gn for gn in x["genes"] if gn in notable]),
                 "n": len(x["genes"]), "on_theme": x["on_theme"]} for x in graph["pathways"]]
    return meta, genes, links, [x for x in pathways if json.loads(x["genes"])]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--person")
    ap.add_argument("--lifecycles", help="lifecycle.py output: also write lifecycle_steps, lifecycle_genes and "
                                         "gene_function JSON next to out")
    ap.add_argument("--dna", help="with --lifecycles: recompute the genotype calls from this DNA file")
    args = ap.parse_args()
    if args.lifecycles:
        from cluster_analysis.gene_trace import person_status, summarize
        status = {g: summarize(v) for g, v in person_status(args.dna).items()} if args.dna else {}
        tables = lifecycle_rows(json.load(open(args.lifecycles, encoding="utf-8")), status)
        out_dir = os.path.dirname(args.out) or "."
        for name, rows in zip(("lifecycle_steps", "lifecycle_genes", "gene_function"), tables):
            with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
            print(f"✅ Wrote {name}.json ({len(rows)} rows)")
        if os.path.exists(THEMES_PATH):
            lifecycle_genes = {r["gene"] for r in tables[1]}
            tables = list(theme_rows(json.load(open(THEMES_PATH, encoding="utf-8")), status, lifecycle_genes))
            # API-built themes replace the library-built theme of the same name
            # Each API theme uses its own person when it names one (female fertility: HJ), otherwise --dna
            statuses = {args.dna: status}
            for path in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "theme_graph_*.json"))):
                graph = json.load(open(path, encoding="utf-8"))
                dna = graph.get("person") or args.dna
                if dna not in statuses:
                    statuses[dna] = {g: summarize(v) for g, v in person_status(dna).items()}
                person = re.sub(r"^MyHeritage_raw_dna_data_|\.csv$", "", os.path.basename(dna or ""))
                xpath = os.path.join("data/output/cluster_analysis", f"theme_{person}_{graph['theme']}.json")
                xref = json.load(open(xpath, encoding="utf-8")) if os.path.exists(xpath) else None
                orders = {r["theme"]: r["theme_order"] for r in tables[0]}
                order = orders.get(graph["theme"], orders.get(graph["theme"].split("_")[0], len(orders)) + 0.5)
                tables = [[r for r in t if r["theme"] != graph["theme"]] for t in tables]
                # Lifecycles are built for --dna's person only, so other people's genes do not link to them
                own = lifecycle_genes if dna == args.dna else set()
                for t, extra in zip(tables, api_theme_rows(graph, xref, statuses[dna], own, order, person)):
                    t.extend(extra)
            for name, rows in zip(("theme_meta", "theme_genes", "theme_links", "theme_pathways"), tables):
                with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
                    json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
                print(f"✅ Wrote {name}.json ({len(rows)} rows)")
    data = bundle()
    if args.person:
        p = json.load(open(args.person, encoding="utf-8"))
        data["person"] = {k: p[k] for k in ("source_file", "modules", "bridges", "biomarker_tilts")}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✅ Wrote {args.out} ({len(json.dumps(data)) // 1024} KB)")
