# cluster_analysis/explorer/export.py
"""
Bundles public library data (modules, module links, genes, SNPs, biomarkers) into one JSON
for dashboards and the future interactive interface. Contains no personal data.

    python -m cluster_analysis.explorer.export out/library_bundle.json [--person overlay.json]

--person embeds an overlay result (use only synthetic or consented data in anything you share).
"""
import argparse
import glob
import json
import os
import re
from collections import defaultdict

from cluster_analysis.library.biomarkers import BIOMARKERS_PATH
from cluster_analysis.library.build_modules import MODULES_PATH
from genome import build as gbuild
from genome.loader import imputed_path, person_label

TRAITS_PATH = "cluster_analysis/library/snp_traits.json"
CA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # cluster_analysis/
NAMES_PATH = os.path.join(CA, "library", "module_names.json")


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


EVIDENCE_PATH = os.path.join(CA, "evidence", "function_evidence.json")
LITERATURE_PATH = os.path.join(CA, "evidence", "literature.json")
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
    """Every library genotype at a SNP, from the common homozygote to the less common one: library reading, the
    evidence call (GoF / LoF / normal ...) and what it means for the person (outcome), and, where MaveDB measured the
    protein change, an activity estimate as a share of the common form. The estimate is additive: each allele
    contributes half, the common allele 1 and the variant its measured score."""
    from cluster_analysis.library.analyzer import outcome
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
        fn = (entry.get("function") or {}).get(key, "unknown")
        rows[gt] = {"genotype": gt, "dose": oriented.count(minor), "text": text, "function": fn,
                    "outcome": outcome(fn, entry.get("polarity"))}
    mave = [m["score"] for m in (ev.get("mavedb") or [])]
    for r in rows.values():
        if mave:
            r["capacity"] = [round(((2 - r["dose"]) + r["dose"] * min(mave)) / 2, 2), round(((2 - r["dose"]) + r["dose"] * max(mave)) / 2, 2)]
        elif r["dose"] == 0:
            r["capacity"] = [1.0, 1.0]
    return sorted(rows.values(), key=lambda r: r["dose"])


def protein_text(gene):
    from cluster_analysis.lifecycle.gene_trace import uniprot_text
    t = uniprot_text(gene)
    return {"protein_function": t["function"], "protein_diseases": "; ".join(t["diseases"]), "protein_tissue": t["tissue"]}


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
                "dose": p.get("dose"), "outcome": p.get("outcome")}

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
                "outcome": fp.get("outcome"), "interpretation": fp.get("interpretation"),
                "cofactors": ", ".join(lc.get("cofactors") or []), "vitamins": ", ".join(lc.get("cofactor_vitamins") or []),
                "regulation": lc.get("regulation") or "",
                "regulators": json.dumps([{"gene": r["gene"], "effect": r["effect"], "lib": r["in_library"]}
                                          for r in (lc.get("regulators") or [])]),
                "other_pathways": lc.get("other_pathways", 0),
                # What the protein does, the diseases linked to it and where it is made, in UniProt's words
                **protein_text(lc["gene"])})
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
                         "basis": p.get("basis"), "fn_evidence": p.get("evidence"), "library_function": p.get("library_function"),
                         "common": p.get("common"), "minor": p.get("minor"), "minor_af": p.get("minor_af"),
                         "outcome": p.get("outcome"), "polarity_source": (traits.get(p.get("rsid")) or {}).get("polarity_source"),
                         "interpretation": p.get("interpretation"), "n_snps": p.get("n_snps"),
                         "evidence": json.dumps(evidence_summary(ev, p.get("genotype")) if ev else {}),
                         "ladder": json.dumps(genotype_ladder(p.get("rsid"), p.get("common"), p.get("minor"), traits,
                                                              evidence_summary(ev, p.get("genotype")) if ev else {})),
                         "literature": json.dumps({k: v for k, v in literature.get(p.get("rsid"), {}).items()
                                                   if k in ("papers", "quotes", "hits")})})
    return steps, genes, function


THEMES_PATH = os.path.join(CA, "library", "themes.json")


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
                          "basis": p.get("basis"), "fn_evidence": p.get("evidence"),
                          "minor": p.get("minor"), "interpretation": p.get("interpretation"), "outcome": p.get("outcome"),
                          "has_lifecycle": g in with_lifecycle})
        links += [{"theme": tid, **l} for l in t["links"]]
        pathways += [{"theme": tid, "pathway": x["pathway"], "genes": json.dumps(x["genes"]), "n": len(x["genes"]),
                      "on_theme": x["on_theme"]} for x in t["pathways"]]
    return meta, genes, links, pathways


EFFECTS = ("GoF", "LoF", "altered")


GRADES = ["A+", "A", "B", "C"]
KEEP_MOVING, KEEP_QUIET = 40, 10


def _bad(f):
    """As the explorer's ntBad: True when the person's copies move the value the unfavourable way."""
    if f.get("xy") == "carried":
        return True
    if not f.get("xy") or f["xy"] == "typical" or f.get("higher") == "neutral":
        return False
    return (f["xy"] == "lowers") == (f.get("higher") == "better")


def trim_findings(tests, findings):
    """Lab tests read thousands of GWAS variants each (LDL alone has over 2,000 per person) while the tab lists the
    strongest. Kept in full: variants at a pathway step, in a gene the test's notes name, and ClinVar/ClinPGx findings.
    Of the other GWAS variants, per person and test the KEEP_MOVING strongest where the person's copies move the value,
    half from each side (the favourable and the unfavourable way, or up and down for a neutral value) so the list shows
    both sides of the net score, and the KEEP_QUIET strongest where they don't. Each test row gets the true counts:
    variants (distinct variant and kind outside the steps), moving (of those, where the person's copies move the
    value), and of the moving ones good/bad (favourable/unfavourable) and up/down (raise/lower the value)."""
    notes = {(t.get("person"), t["id"]): {n["gene"] for n in json.loads(t.get("notes") or "[]")} for t in tests}
    rank = lambda f: (GRADES.index(f["grade"]) if f.get("grade") in GRADES else 9, -abs(f.get("shift") or 0))
    groups = {}
    for f in findings:
        groups.setdefault((f.get("person"), f["nutrient"]), []).append(f)
    kept, counts = [], {}
    for key, fs in groups.items():
        genes = notes.get(key, set())
        named = lambda f: bool(genes & set(re.split(r"[\s,;-]+", f.get("gene") or ""))) or f.get("step_gene") in genes
        keep = [f for f in fs if f.get("step_gene") or f.get("kind") != "GWAS" or named(f)]
        kept_ids = {id(f) for f in keep}
        rest = [f for f in fs if id(f) not in kept_ids]
        moving = sorted((f for f in rest if f.get("xy") and f["xy"] != "typical"), key=rank)
        quiet = sorted((f for f in rest if not (f.get("xy") and f["xy"] != "typical")), key=rank)
        # Both sides: half the places to each, a side short of its half leaving the rest to the other
        side = lambda f: _bad(f) if f.get("higher") != "neutral" else f["xy"] == "lowers"
        a, b = [f for f in moving if side(f)], [f for f in moving if not side(f)]
        na = min(len(a), max(KEEP_MOVING // 2, KEEP_MOVING - len(b)))
        kept += keep + a[:na] + b[:KEEP_MOVING - na] + quiet[:KEEP_QUIET]
        outside = {(f["rsid"], f.get("kind")): f for f in fs if not f.get("step_gene")}
        mv = [f for f in outside.values() if f.get("xy") and f["xy"] != "typical"]
        counts[key] = (len(outside), len(mv), sum(1 for f in mv if _bad(f)),
                       sum(1 for f in mv if f["xy"] != "carried" and f.get("higher") != "neutral" and not _bad(f)),
                       sum(1 for f in mv if f["xy"] == "raises"), sum(1 for f in mv if f["xy"] == "lowers"))
    for t in tests:
        (t["variants"], t["moving"], t["moving_bad"], t["moving_good"],
         t["moving_up"], t["moving_down"]) = counts.get((t.get("person"), t["id"]), (0, 0, 0, 0, 0, 0))
    return tests, kept


def gene_status(lib, api):
    """One gene's call for the explorer: the per-gene call from the person's own variants (gene_calls.py) when it finds
    an effect or the library has nothing; the library's per-SNP call otherwise (and always for CPIC pharmacogenes)."""
    lib, api = lib or {}, api or {}
    use_api = api.get("function") in EFFECTS and lib.get("basis") != "cpic" or         (not lib.get("genotype") and api.get("function") == "normal")
    if not use_api:
        return lib
    return {"rsid": api.get("rsid"), "genotype": api.get("genotype"), "function": api["function"], "dose": api.get("dose"),
            "basis": api.get("basis"), "evidence": api.get("detail"), "minor": None, "interpretation": None, "outcome": None,
            "source": "api"}


REACH_KEYS = ("pathogenic", "chip", "reliable", "uncertain", "not_knowable", "not_in_panel", "not_mapped")


def chip_reach():
    """{gene: {pathogenic, chip, reliable, uncertain, not_knowable, not_in_panel, not_mapped}}: how many of ClinVar's
    pathogenic variants in each gene a chip plus imputation can see (genome/imputability.py, GRCh38 panel only)."""
    path = os.path.join(gbuild.REF, "imputability", "genes.json")
    if gbuild.BUILD != "GRCh38" or not os.path.exists(path):
        return {}
    return {g["gene"]: {k: g.get(k, 0) for k in REACH_KEYS} for g in json.load(open(path, encoding="utf-8")) if g["gene"]}


def theme_reach(genes, reach, top=5):
    """The chip's reach summed over a theme's genes, and the genes with the most variants a chip can't see."""
    rs = [reach[g] for g in genes if g in reach]
    if not rs:
        return None
    tot = {k: sum(r[k] for r in rs) for k in REACH_KEYS}
    unseen = lambda g: reach[g]["pathogenic"] - reach[g]["chip"] - reach[g]["reliable"]
    tot["unseen_genes"] = [g for g in sorted((g for g in genes if g in reach), key=lambda g: -unseen(g))[:top] if unseen(g) > 0]
    return tot


def api_theme_rows(graph, xref, status, with_lifecycle=(), order=0, person=None, calls=None, reach=None):
    """theme_graph.py output plus a person's cross-reference → the same four theme datasets. Every gene is listed;
    notable ones (a call with an effect, a library call, a finding where the person carries the allele, or an Open
    Targets score ≥ 0.8) are the ones the explorer draws. calls: gene_calls.py output for the person."""
    tid = graph["theme"]
    calls = calls or {}
    reach = reach or {}
    xg = (xref or {}).get("genes", {})
    facets = graph["mechanisms"] + [{"id": "disease", "name": "Disease link, mechanism not yet known",
                                     "about": "Open Targets ties these genes to one of the theme's conditions, but Gene Ontology has no "
                                              "mechanism for them in this theme yet."}]
    with_findings = sum(1 for g in xg.values() if g["findings"])
    stats = {"n_genes": len(graph["genes"]), "n_mechanism": sum(1 for g in graph["genes"].values() if g["mechanisms"]),
             "n_snps": (xref or {}).get("n_snps_in_theme_genes"), "n_genes_with_findings": with_findings,
             "pathogenic_measured": (xref or {}).get("pathogenic", {}).get("measured"),
             "pathogenic_carried": (xref or {}).get("pathogenic", {}).get("carried", []),
             "pathogenic_possible": (xref or {}).get("pathogenic", {}).get("possible", []),
             "pathogenic_not_excluded": (xref or {}).get("pathogenic", {}).get("not_excluded", 0),
             "by_confidence": (xref or {}).get("by_confidence"), "rule": graph["rule"],
             "chip_reach": theme_reach(list(graph["genes"]), reach),
             "person": person, "sex": graph.get("sex"), "organs": graph.get("organs", []),
             "disease_organs": graph.get("disease_organs", {}), "view": graph.get("view"), "phases": graph.get("phases"),
             "view_title": graph.get("view_title"), "view_note": graph.get("view_note")}
    meta = [{"theme": tid, "theme_name": graph["name"], "about": graph["about"], "theme_order": order, "facet": f["id"],
             "facet_name": f["name"], "facet_about": f.get("about"), "organ": f.get("organ"),
             "facet_explain": f.get("explain") or (graph.get("disease_explain") if f["id"] == "disease" else None),
             "core": True, "facet_order": i, "source": "api",
             "stats": json.dumps(stats)} for i, f in enumerate(facets)]
    genes, notable = [], set()
    for sym, g in graph["genes"].items():
        p = gene_status(status.get(sym), calls.get(sym))
        findings = xg.get(sym, {}).get("findings", [])
        carried = sum(1 for f in findings for it in f["items"] if it["source"] in ("GWAS", "ClinVar") and it.get("copies"))
        clinvar = any(it["source"] == "ClinVar" for f in findings for it in f["items"])
        # Genes with a reproductive mechanism are drawn when XY carries a finding; disease-only genes (many of them
        # hormone-level GWAS loci) only with a library call, a ClinVar entry or a very strong disease link
        is_notable = (bool(p.get("genotype")) and p.get("source") != "api") or p.get("function") in EFFECTS or             g["best_score"] >= 0.8 or clinvar or (carried > 0 and bool(g["mechanisms"]))
        if is_notable:
            notable.add(sym)
        top = sorted(g["diseases"].items(), key=lambda kv: -kv[1]["score"])[:5]
        genes.append({"theme": tid, "gene": sym, "primary": g["primary"] or "disease",
                      "facets": json.dumps(list(g["mechanisms"]) or ["disease"]),
                      "evidence": json.dumps({"mechanisms": g["mechanisms"], "diseases": dict(top), "joined_by": g["joined_by"],
                                              "findings": findings, "n_snps": xg.get(sym, {}).get("n_snps", 0),
                                              "organs": g.get("organs", []), "reach": reach.get(sym)}),
                      "rsid": p.get("rsid"), "genotype": p.get("genotype"),
                      "function": p.get("function") if p.get("genotype") or p.get("source") == "api" else None,
                      "basis": p.get("basis"), "fn_evidence": p.get("evidence"), "call_source": p.get("source") or ("library" if p else None),
                      "dose": p.get("dose"), "minor": p.get("minor"), "interpretation": p.get("interpretation"), "outcome": p.get("outcome"),
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
    ap.add_argument("--dna", help="with --lifecycles: only this person (default: every profile in profiles.json)")
    ap.add_argument("--measured-only", action="store_true", help="use the raw files even when imputed ones exist")
    args = ap.parse_args()
    if args.lifecycles:
        from cluster_analysis import profiles as prof
        from cluster_analysis.lifecycle.gene_trace import person_status, summarize
        people = prof.load()
        if args.dna:
            people = [p for p in people if p["id"] == person_label(args.dna)] or [{"id": person_label(args.dna), "sex": None, "dna": args.dna}]
        # A fresh install has no lifecycles yet (they come with the knowledge bundle, docs/architecture/production.md):
        # the Gene pathway tab is then empty, the rest is exported as usual
        lifecycles = json.load(open(args.lifecycles, encoding="utf-8")) if os.path.exists(args.lifecycles) else []
        graphs = prof.theme_graphs()
        reach = chip_reach()
        out_dir = os.path.dirname(args.out) or "."
        merged = {n: [] for n in ("lifecycle_steps", "lifecycle_genes", "gene_function",
                                  "theme_meta", "theme_genes", "theme_links", "theme_pathways")}
        tag = lambda rows, pid: [{**r, "person": pid} for r in rows]
        for p in people:
            pid = p["id"]
            dna = p["dna"] if args.measured_only else imputed_path(p["dna"])  # imputed calls when genome/impute.py has run
            print(f"== {pid} ({os.path.basename(dna)})")
            status = {g: summarize(v) for g, v in person_status(dna).items()}
            lc = lifecycle_rows(lifecycles, status)
            for name, rows in zip(("lifecycle_steps", "lifecycle_genes", "gene_function"), lc):
                merged[name] += tag(rows, pid)
            lifecycle_genes = {r["gene"] for r in lc[1]}
            tables = list(theme_rows(json.load(open(THEMES_PATH, encoding="utf-8")), status, lifecycle_genes))                 if os.path.exists(THEMES_PATH) else [[], [], [], []]
            orders = {r["theme"]: r["theme_order"] for r in tables[0]}
            cpath = os.path.join(gbuild.OUTPUT, f"gene_calls_{pid}.json")
            calls = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else None
            for graph in graphs:
                # Themes for the profile's sex only: female fertility for women, male fertility for men
                if not prof.applies(graph.get("sex"), p.get("sex")):
                    continue
                xpath = os.path.join(gbuild.OUTPUT, f"theme_{pid}_{graph['theme']}.json")
                xref = json.load(open(xpath, encoding="utf-8")) if os.path.exists(xpath) else None
                order = orders.get(graph["theme"], orders.get(graph["theme"].split("_")[0], len(orders)) + 0.5)
                # An API theme replaces the library theme of the same id, and fertility_female/_male replace "fertility"
                tables = [[r for r in t if r["theme"] not in (graph["theme"], graph["theme"].split("_")[0])] for t in tables]
                for t, extra in zip(tables, api_theme_rows(graph, xref, status, lifecycle_genes, order, pid, calls, reach)):
                    t.extend(extra)
            for name, rows in zip(("theme_meta", "theme_genes", "theme_links", "theme_pathways"), tables):
                merged[name] += tag(rows, pid)
        # Medicines, nutrition, lab tests and the body systems, run per profile into data/output/cluster_analysis/profiles/<id>/
        # (profiles.py run): one dataset each, rows tagged with their person. The public ones are taken once.
        for name in ("med_genes", "med_drugs", "med_guidance", "nut_nutrients", "nut_findings", "lab_tests", "lab_findings",
                     "fit_tests", "fit_findings", "sport_snps", "can_tests", "can_findings",
                     "sys_systems", "sys_genes", "sys_links", "sys_bridges", "fd_phases", "fd_impact"):
            merged[name] = []
            for p in people:
                f = os.path.join(prof.PROFILE_DIR, p["id"], name + ".json")
                if os.path.exists(f):
                    merged[name] += tag(json.load(open(f, encoding="utf-8")), p["id"])
        for name in ("med_names", "nut_steps", "lab_steps", "fit_steps", "can_steps", "fd_genes", "fd_explain"):
            f = next((os.path.join(prof.PROFILE_DIR, p["id"], name + ".json") for p in people
                      if os.path.exists(os.path.join(prof.PROFILE_DIR, p["id"], name + ".json"))), None)
            if f:  # public: the same for everyone, so no person (the page would show it to that person only)
                merged[name] = [{k: v for k, v in r.items() if k != "person"} for r in json.load(open(f, encoding="utf-8"))]
        merged.setdefault("fd_genes", [])
        merged.setdefault("fd_explain", [])  # no female profile run yet: the fertility views read an empty set
        merged["lab_tests"], merged["lab_findings"] = trim_findings(merged.get("lab_tests", []), merged.get("lab_findings", []))
        merged["fit_tests"], merged["fit_findings"] = trim_findings(merged.get("fit_tests", []), merged.get("fit_findings", []))
        merged["can_tests"], merged["can_findings"] = trim_findings(merged.get("can_tests", []), merged.get("can_findings", []))
        merged["profiles"] = [{"id": p["id"], "sex": p.get("sex"), **({"lite": True} if p.get("lite") else {})} for p in people]
        # People imported from a results file (explorer/results.py): their rows as they came
        from cluster_analysis.explorer import results
        results.merge(merged, {p["id"] for p in people})
        # The introduction (Home tab): the method's numbers and each person's (cluster_analysis/explorer/intro.py)
        from cluster_analysis.explorer import intro
        merged["intro_stats"] = intro.rows(people)
        for name, rows in merged.items():
            # Empty is still an answer for the datasets the page reads (the cancer scores have no Reactome steps)
            if not rows and name not in ("profiles", "nut_steps", "lab_steps", "fit_steps", "can_steps", "fd_phases", "fd_genes", "fd_explain", "fd_impact"):
                continue
            with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
            print(f"✅ Wrote {name}.json ({len(rows)} rows)")
    data = bundle()
    # The explorer's public reference datasets, flattened from the bundle
    names = {m["id"]: m["name"] for m in data["modules"]}
    public = {
        "modules": [{"id": m["id"], "name": m["name"], "size": m["size"], "hubs": ", ".join(m["hubs"]),
                     "enrichment": "; ".join(m["enrichment"][:3]), "genes": ", ".join(sorted(m["genes"]))} for m in data["modules"]],
        "module_links": [{**l, "a_name": names.get(l["a"], l["a"]), "b_name": names.get(l["b"], l["b"])} for l in data["module_links"]],
        "biomarker_snps": [{"biomarker": b["biomarker"], "panel": b["panel"], "rsid": s["rsid"], "genes": ", ".join(s["genes"]),
                            "module": (s["modules"] or [None])[0], "module_name": names.get((s["modules"] or [None])[0], ""),
                            "effect_allele": s["effect_allele"], "direction": "raises" if s["direction"] == "+" else "lowers",
                            "strand": s["strand"], "eaf_eur": round(s["eaf_eur"], 3) if s["eaf_eur"] is not None else None,
                            "p_value": s["p_value"], "pubmed_id": s["pubmed_id"], "first_author": s["first_author"]}
                           for b in data["biomarkers"] for s in b["snps"]],
    }
    for name, rows in public.items():
        with open(os.path.join(os.path.dirname(args.out) or ".", name + ".json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
    if args.person:
        p = json.load(open(args.person, encoding="utf-8"))
        data["person"] = {k: p[k] for k in ("source_file", "modules", "bridges", "biomarker_tilts")}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✅ Wrote {args.out} ({len(json.dumps(data)) // 1024} KB)")
