"""Ask and the person's gene function calls: which of their genes the explorer calls gain of function (GoF), loss of
function (LoF) or otherwise altered, across the clusters (the theme_genes dataset) and the Gene pathway genes
(gene_function), with what each call rests on.

What a call rests on matters, so every card says it:
  curated     the variant changes the protein, by a reviewed source (ClinVar, UniProt, lab assays, the library)
  expression  the variant raises (GoF) or lowers (LoF) how much of a normal protein a tissue makes (GTEx eQTLs):
              more or less of the same protein, not a protein that works differently
Curated calls come first, then two copies before one, then the effect seen in more tissues.

The model gets, as for every personal tool: with Restricted mode on, only the kind of result shown and how many;
off, the interpreted calls (gene, call, basis, the variant and genotype behind it).
"""
import re

from cluster_analysis.agent import providers

FUNCTIONS = {"gof": "GoF", "gain": "GoF", "gain of function": "GoF", "lof": "LoF", "loss": "LoF", "loss of function": "LoF",
             "altered": "altered", "changed": "altered"}
BASIS = {"curated": "a reviewed protein change (ClinVar, UniProt, lab assays)",
         "expression": "more or less of the same protein in some tissues (GTEx)"}
LIMIT = 15


def _tissues(text):
    m = re.search(r"in (\d+) tissues?", text or "")
    return int(m.group(1)) if m else 0


def calls(person, function, theme=None):
    """The person's genes with this call, one per gene (its clusters merged), strongest evidence first."""
    by = {}
    for name in ("theme_genes", "gene_function"):
        for r in providers.rows(name, person):
            if not isinstance(r, dict) or r.get("person") != person or r.get("function") != function:
                continue
            if theme and name == "theme_genes" and r.get("theme") != theme:
                continue
            g = by.setdefault(r["gene"], {"gene": r["gene"], "themes": set(), "rsid": r.get("rsid"), "genotype": r.get("genotype"),
                                          "dose": r.get("dose"), "basis": r.get("basis"), "why": r.get("fn_evidence"),
                                          "source": r.get("call_source"), "pathway": False})
            if name == "theme_genes":
                g["themes"].add(r.get("theme"))
            else:
                g["pathway"] = True
            # keep the strongest basis seen for the gene
            if r.get("basis") == "curated" and g["basis"] != "curated":
                g.update(basis="curated", why=r.get("fn_evidence"), rsid=r.get("rsid"), genotype=r.get("genotype"), dose=r.get("dose"))
    out = list(by.values())
    for g in out:
        g["themes"] = sorted(t for t in g["themes"] if t)
        g["tissues"] = _tissues(g["why"])
    out.sort(key=lambda g: (g["basis"] != "curated", -int(float(g["dose"] or 0)), -g["tissues"], g["gene"]))
    return out


def t_my_genes_by_function(ctx, function, theme=None):
    f = FUNCTIONS.get(str(function).strip().lower(), str(function).strip())
    if f not in ("GoF", "LoF", "altered"):
        return {"error": "function is GoF (gain of function), LoF (loss of function) or altered."}
    found = calls(ctx["person"], f, theme)
    cards = []
    if found:
        n_cur = sum(1 for g in found if g["basis"] == "curated")
        cards.append(providers.card("function", f"function:{f}", f"Your {f} genes", level="differs", value=len(found),
                                    headline=f"{len(found)} genes called {f}" + (f" in the {theme} cluster" if theme else " across the clusters") +
                                             f": {n_cur} from a reviewed protein change, {len(found) - n_cur} from expression.",
                                    data={"kind": "function_list", "function": f, "theme": theme, "total": len(found), "curated": n_cur,
                                          "genes": [{k: g[k] for k in ("gene", "themes", "rsid", "genotype", "dose", "basis", "why", "tissues", "pathway")}
                                                    for g in found[:LIMIT]]},
                                    rows=[{"label": f"{g['gene']} ({g['rsid'] or '?'})",
                                           "value": f"{f}, {BASIS.get(g['basis'], g['basis'] or 'basis not recorded')}",
                                           "note": (g["why"] or "")[:160]} for g in found[:LIMIT]],
                                    links=[{"tab": "clusters", "params": {}, "label": "Open the clusters"}]))
    ctx["cards"] += cards
    from cluster_analysis.agent import tools
    out = tools._shape(cards)
    out["public"] = {"what": {"GoF": "gain of function: the variant makes the gene more active, or its protein more abundant or active",
                              "LoF": "loss of function: the variant makes the gene less active, or its protein less abundant or broken",
                              "altered": "changed: the variant changes the protein in a way neither more nor less active"}[f],
                     "bases": BASIS, "counts_only": {"genes": len(found), "curated": sum(1 for g in found if g["basis"] == "curated")}}
    if not found:
        out["note"] = f"No gene of the person's is called {f}" + (f" in the {theme} cluster." if theme else ".")
    return out
