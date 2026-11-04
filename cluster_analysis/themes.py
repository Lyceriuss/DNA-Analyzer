# cluster_analysis/themes.py
"""
Theme clusters: every library gene with data that bears on a health theme (cancer, fertility, muscle growth),
grouped by the mechanism through which it acts, with the interactions and pathways that connect them.

    python -m cluster_analysis.themes        # → cluster_analysis/themes.json (public data, no genotypes)

A theme is a set of facets (mechanisms). A gene joins a facet when its annotations match the facet's patterns:
  GO        Gene Ontology biological processes (MyGene.info)
  Reactome  Reactome pathways (MyGene.info)
  UniProt   the curated function and disease text
  GWAS      genome-wide significant traits of the gene's library SNPs
  Library   the library's own trait and system text
Broad facets (inflammation, oxidative stress, energy) also need a direct link to the theme in UniProt, the
gene summary or GWAS, so that every antioxidant gene does not land in "cancer". Each membership keeps the
matching terms as evidence. Connections are STRING interactions (confidence ≥ 0.4) between theme genes, and
pathways are Reactome pathways shared by two or more theme genes.
"""
import json
import os
import re

from cluster_analysis import sources
from cluster_analysis.gene_trace import uniprot_entry

MODULES_PATH = os.path.join(os.path.dirname(__file__), "modules.json")
TRAITS_PATH = "config/snp_traits.json"
OUT_PATH = os.path.join(os.path.dirname(__file__), "themes.json")

THEMES = {
    "cancer": {
        "name": "Cancer",
        "about": "Genes that guard the genome, control when cells grow and die, turn chemicals into carcinogens or clear them, "
                 "and shape the hormonal, oxidative and inflammatory setting tumours grow in.",
        "link": r"cancer|carcinom|tumou?r|neoplas|oncogen|leukemi|lymphom|melanom|glioma|adenoma|metasta|malignan",
        "facets": [
            {"id": "repair", "name": "DNA repair and genome stability", "core": True,
             "go": r"DNA repair|double-strand break|mismatch repair|base-excision|nucleotide-excision|"
                   r"genome stability|telomere maintenance|DNA damage checkpoint",
             "reactome": r"DNA Repair|DNA Damage|Telomere|Fanconi Anemia|Homology Directed|Mismatch Repair|Base Excision|Nucleotide Excision",
             "uniprot": r"DNA repair|DNA damage|genome (?:stability|integrity)|double-strand break"},
            {"id": "growth", "name": "Growth signals and cell division", "core": False,
             "go": r"regulation of cell cycle|G1/S transition|mitotic cell cycle|positive regulation of cell population proliferation|"
                   r"regulation of cell growth",
             "reactome": r"Cell Cycle|Signaling by (?:EGFR|ERBB|FGFR|PDGF|RAS|WNT|Hedgehog|NOTCH|TGF)|PIP3 activates AKT|MAPK1/MAPK3",
             "uniprot": r"cell proliferation|cell cycle|oncogen|growth factor"},
            {"id": "death", "name": "Cell death and tumour suppression", "core": False,
             "go": r"apoptotic process|programmed cell death|cellular senescence|negative regulation of cell population proliferation",
             "reactome": r"Apoptosis|TP53|Senescence|Programmed Cell Death",
             "uniprot": r"apoptosis|tumou?r suppressor|senescence"},
            {"id": "carcinogen", "name": "Carcinogen activation and detox", "core": True,
             "go": r"xenobiotic metabolic|xenobiotic catabolic|glutathione metabolic|glutathione derivative|polycyclic|aromatic compound catabolic",
             "reactome": r"Phase I|Phase II|Biological oxidations|Glutathione conjugation|Cytochrome P450|Aflatoxin|xenobiotic",
             "uniprot": r"xenobiotic|carcinogen|detoxif|benzo\[a\]pyrene|polycyclic aromatic"},
            {"id": "hormone", "name": "Hormone-driven growth", "core": False,
             "go": r"estrogen metabolic|androgen metabolic|estrogen receptor signaling|androgen receptor signaling|response to estradiol",
             "reactome": r"Estrogen|ESR-mediated|Androgen",
             "uniprot": r"estrogen|estradiol|androgen|catechol estrogen"},
            {"id": "oxidative", "name": "Oxidative stress", "core": False,
             "go": r"response to oxidative stress|reactive oxygen species|superoxide|hydrogen peroxide|cellular oxidant detoxification",
             "reactome": r"Detoxification of Reactive Oxygen|oxidative stress|NFE2L2|KEAP1",
             "uniprot": r"oxidative stress|reactive oxygen|superoxide|peroxide"},
            {"id": "immune", "name": "Inflammation and immune surveillance", "core": False,
             "go": r"inflammatory response|cytokine-mediated|T cell activation|natural killer|antigen processing",
             "reactome": r"Interleukin|Cytokine Signaling|Inflammasome|TNF signaling",
             "uniprot": r"inflammat|cytokine|immune surveillance"},
            {"id": "methyl", "name": "Folate and DNA building blocks", "core": False,
             "go": r"one-carbon metabolic|folic acid|tetrahydrofolate|methionine metabolic|S-adenosylmethionine|DNA methylation|nucleotide biosynthetic",
             "reactome": r"Metabolism of folate|Methylation|Sulfur amino acid|One carbon",
             "uniprot": r"folate|tetrahydrofolate|methyl donor|DNA methylation"},
        ],
        "gwas_facets": [],
    },
    "fertility": {
        "name": "Fertility",
        "about": "Genes that make and break down sex hormones, carry the signals of the reproductive axis, drive desire, "
                 "run the cycle and gamete production, and support implantation and pregnancy.",
        "link": r"fertil|reproduct|pregnan|ovar|testi[sc]|testosterone|estradiol|estrogen|progesterone|sperm|oocyte|"
                r"menstrua|menopaus|menarche|gonad|placenta|sexual|libido|erectile|androgen",
        "facets": [
            {"id": "make", "name": "Sex hormone production and breakdown", "core": True,
             "go": r"androgen biosynthetic|estrogen biosynthetic|testosterone (?:biosynthetic|metabolic)|progesterone (?:biosynthetic|metabolic)|"
                   r"C21-steroid hormone biosynthetic|estrogen metabolic|androgen metabolic|steroid hormone biosynthetic",
             "reactome": r"Androgen biosynthesis|Estrogen biosynthesis|Pregnenolone biosynthesis|Metabolism of steroid hormones|"
                         r"Glucocorticoid biosynthesis|Mineralocorticoid biosynthesis",
             "uniprot": r"testosterone|estradiol|progesterone|androgen|estrogen|steroidogen|pregnenolone|dihydrotestosterone"},
            {"id": "axis", "name": "Hormone signals and the reproductive axis", "core": True,
             "go": r"gonadotropin|luteinizing|follicle-stimulating|gonadotropin-releasing|prolactin|estrogen receptor signaling|"
                   r"androgen receptor signaling|intracellular steroid hormone receptor signaling",
             "reactome": r"Hormone ligand-binding receptors|Glycoprotein hormones|ESR-mediated signaling|Nuclear Receptor transcription",
             "uniprot": r"gonadotropin|luteinizing|follicle-stimulating|GnRH|prolactin|androgen receptor|estrogen receptor|"
                        r"sex hormone-binding|SHBG"},
            {"id": "drive", "name": "Sexual drive and bonding", "core": True,
             "go": r"sexual behavior|mating behavior|copulation|reproductive behavior|maternal behavior",
             "reactome": r"Oxytocin|Vasopressin",
             "uniprot": r"sexual|libido|mating|oxytocin|pair bonding|social behaviou?r"},
            {"id": "cycle", "name": "Cycle, ovulation and sperm", "core": True,
             "go": r"ovulation|ovarian follicle|oocyte|menstrua|estrous cycle|luteinization|spermatogenesis|sperm|fertilization|"
                   r"meiotic|female gonad|male gonad|gamete generation",
             "reactome": r"Meiosis|Fertilization|Sperm|Acrosome",
             "uniprot": r"spermatogenesis|sperm|oocyte|ovulation|infertility|menstrual|ovarian"},
            {"id": "pregnancy", "name": "Implantation and pregnancy", "core": True,
             "go": r"embryo implantation|placenta|decidualization|parturition|lactation|neural tube",
             "reactome": r"placenta",
             "uniprot": r"pregnancy|placenta|implantation|miscarriage|pregnancy loss|pre-?eclampsia|neural tube"},
            {"id": "support", "name": "Gamete and embryo support (folate, clotting, oxidative stress)", "core": False,
             "go": r"one-carbon metabolic|folic acid|tetrahydrofolate|blood coagulation|response to oxidative stress",
             "reactome": r"Metabolism of folate|Formation of Fibrin|Detoxification of Reactive Oxygen",
             "uniprot": r"folate|thrombophilia|coagulation|oxidative stress"},
        ],
        "gwas_facets": [
            (r"testosterone|estradiol|sex hormone-binding|SHBG|\bprogesterone (?:level|measurement)|DHEA", "make"),
            (r"follicle stimulating|luteinizing|anti-Mullerian|prolactin", "axis"),
            (r"erectile|libido|sexual|number of sexual partners|age at first sexual", "drive"),
            (r"menarche|menopause|infertility|endometriosis|polycystic ovary|sperm|menstrua", "cycle"),
            (r"pre-?eclampsia|miscarriage|preterm|pregnancy loss|number of children", "pregnancy"),
        ],
    },
    "muscle": {
        "name": "Muscle growth",
        "about": "Genes behind the growth hormone and IGF-1 signal, protein synthesis, the supply of amino acids, anabolic "
                 "hormones, muscle fibres, the energy for training, and repair afterwards.",
        "link": r"muscle|muscular|myo(?:genic|cyte|blast|fiber|fibre|statin)|sarcomer|lean (?:body )?mass|grip strength|"
                r"athlet|endurance|sprint|exercise|hypertroph",
        "facets": [
            {"id": "gh", "name": "Growth hormone and IGF-1 axis", "core": True,
             "go": r"growth hormone|insulin-like growth factor|somatotropin",
             "reactome": r"Growth hormone receptor signaling|triggered by IGF1R|Signaling by Type 1 Insulin-like Growth Factor 1 Receptor",
             "uniprot": r"growth hormone|IGF-?1|insulin-like growth factor|somatotropin"},
            {"id": "synthesis", "name": "Protein synthesis (mTOR)", "core": True,
             "go": r"\bTOR signaling|\bTORC1|positive regulation of translation|cellular response to amino acid stimulus|"
                   r"positive regulation of protein synthesis",
             "reactome": r"mTOR|MTOR|Energy dependent regulation of mTOR|Amino acids regulate mTORC1",
             "uniprot": r"\bmTOR|protein synthesis|translation initiation"},
            {"id": "amino", "name": "Amino acid supply", "core": False,
             "go": r"branched-chain amino acid|leucine|glutamine metabolic|creatine|L-amino acid transmembrane|neutral amino acid transport|"
                   r"amino acid import",
             "reactome": r"Amino acid transport|Branched-chain amino acid catabolism|Creatine metabolism|Glutamate and glutamine metabolism",
             "uniprot": r"amino acid transport|leucine|branched-chain|creatine|glutamine"},
            {"id": "anabolic", "name": "Anabolic hormones (testosterone, insulin)", "core": False,
             "go": r"androgen receptor signaling|response to testosterone|androgen biosynthetic|insulin receptor signaling|"
                   r"response to insulin",
             "reactome": r"Androgen biosynthesis|Insulin receptor signalling|Signaling by Insulin receptor",
             "uniprot": r"androgen|testosterone|insulin receptor|anabolic"},
            {"id": "fibre", "name": "Muscle fibres and contraction", "core": True,
             "go": r"skeletal muscle contraction|sarcomere organization|skeletal muscle tissue development|skeletal muscle fiber|myoblast|"
                   r"skeletal muscle cell differentiation|skeletal muscle organ development|skeletal muscle hypertrophy",
             "reactome": r"Striated Muscle Contraction|Myogenesis",
             "uniprot": r"skeletal muscle (?:fib|contraction|mass|function|performance)|sarcomere|myofibril|myogen|fast-twitch"},
            {"id": "regulators", "name": "Brakes and boosters of muscle growth", "core": True,
             "go": r"regulation of skeletal muscle (?:tissue growth|hypertrophy|cell proliferation|fiber development)|"
                   r"negative regulation of muscle|myostatin",
             "reactome": r"myostatin",
             "uniprot": r"myostatin|muscle growth|muscle mass|hypertrophy"},
            {"id": "energy", "name": "Energy for training", "core": False,
             "go": r"mitochondrial biogenesis|fatty acid beta-oxidation|glycolytic process|AMP-activated|oxidative phosphorylation",
             "reactome": r"Mitochondrial biogenesis|Mitochondrial Fatty Acid Beta-Oxidation|AMPK|Glycolysis",
             "uniprot": r"mitochondrial biogenesis|PGC-1|AMPK|endurance|oxidative capacity"},
            {"id": "repair", "name": "Repair and recovery", "core": False,
             "go": r"skeletal muscle tissue regeneration|muscle cell regeneration|response to muscle activity|satellite cell",
             "reactome": r"$^",
             "uniprot": r"regenerat|satellite cell|recovery"},
        ],
        "gwas_facets": [
            (r"lean (?:body )?mass|appendicular|grip strength|muscle", "fibre"),
            (r"insulin-like growth factor|IGF-?1", "gh"),
            (r"testosterone", "anabolic"),
            (r"^(?:leucine|isoleucine|valine|creatine|glutamine) (?:measurement|levels?)", "amino"),
        ],
    },
}


def mygene_annotations(symbols):
    """{symbol: {go: [biological processes], reactome: [pathways], summary}} for the whole library."""
    key = "themes|" + "\n".join(sorted(symbols))
    def fetch():
        return sources._post(sources.MYGENE_API, {"q": ",".join(symbols), "scopes": "symbol", "species": "human",
                                                  "fields": "symbol,summary,go.BP.term,pathway.reactome.name"})
    out = {}
    for h in sources._cached("mygene_themes", key, fetch):
        if h.get("notfound") or h["query"] in out:
            continue
        bp = (h.get("go") or {}).get("BP") or []
        reactome = (h.get("pathway") or {}).get("reactome") or []
        out[h["query"]] = {"go": sorted({x["term"] for x in (bp if isinstance(bp, list) else [bp])}),
                           "reactome": sorted({x["name"] for x in (reactome if isinstance(reactome, list) else [reactome])}),
                           "summary": h.get("summary", "")}
    return out


def reactome_pathways(gene):
    """Lowest-level Reactome pathways for a gene's protein (Reactome ContentService, by UniProt accession)."""
    entry = uniprot_entry(gene)
    if not entry:
        return []
    acc = entry["primaryAccession"]
    rows = sources._cached("reactome_acc_pathways", acc, lambda: sources._request(
        "GET", f"https://reactome.org/ContentService/data/mapping/UniProt/{acc}/pathways", params={"species": 9606},
        ok_404=True, timeout=90) or [])
    return sorted({r["displayName"] for r in rows})


def uniprot_text(gene):
    entry = uniprot_entry(gene)
    if not entry:
        return ""
    parts = []
    for c in entry.get("comments", []):
        if c.get("commentType") in ("FUNCTION", "DISEASE"):
            parts += [t.get("value", "") for t in c.get("texts", [])]
            if c.get("disease"):
                parts.append(c["disease"].get("diseaseId", "") + " " + c["disease"].get("description", ""))
    return " ".join(parts)


def _hits(pattern, items, limit=3):
    rx = re.compile(pattern, re.I)
    return [x for x in items if rx.search(x)][:limit]


def _sentence(pattern, text, limit=200):
    m = re.search(rf"[^.]*(?:{pattern})[^.]*\.", text or "", re.I)
    return m.group(0).strip()[:limit] if m else None


def classify(gene, ann, uni, gwas, lib_text):
    """{theme: {facet id: [evidence]}} for one gene."""
    out = {}
    for tid, theme in THEMES.items():
        linked = (re.search(theme["link"], uni, re.I) or re.search(theme["link"], ann.get("summary", ""), re.I)
                  or any(re.search(theme["link"], t, re.I) for t in gwas) or re.search(theme["link"], lib_text, re.I))
        facets = {}
        for f in theme["facets"]:
            ev = [{"source": "GO", "text": t} for t in _hits(f["go"], ann.get("go", []))]
            ev += [{"source": "Reactome", "text": t} for t in _hits(f["reactome"], ann.get("reactome", []))]
            s = _sentence(f["uniprot"], uni)
            if s:
                ev.append({"source": "UniProt", "text": s})
            if ev and (f["core"] or linked):
                facets[f["id"]] = ev
        for pattern, fid in theme.get("gwas_facets", []):
            hits = [t for t in gwas if re.search(pattern, t, re.I)][:3]
            if hits:
                facets.setdefault(fid, []).extend({"source": "GWAS", "text": t} for t in hits)
        if re.search(theme["link"], lib_text, re.I) and facets:
            next(iter(facets.values())).append({"source": "Library", "text": lib_text[:160]})
        if facets:
            out[tid] = facets
    return out


def build():
    lib = json.load(open(MODULES_PATH, encoding="utf-8"))
    traits = json.load(open(TRAITS_PATH, encoding="utf-8"))
    genes = sorted(lib["genes"])
    ann = mygene_annotations(genes)
    for g in genes:
        ann.setdefault(g, {"go": [], "reactome": [], "summary": ""})["reactome"] = reactome_pathways(g)
    gwas = {g: [] for g in genes}
    lib_text = {g: [] for g in genes}
    for rsid, r in lib["rsids"].items():
        for g in r["genes"]:
            if g in gwas:
                gwas[g] += [x["trait"] for x in r.get("gwas", [])]
                t = traits.get(rsid, {})
                lib_text[g].append(f"{t.get('trait', '')} ({t.get('system', '')})")
    edges = sources.string_network(genes, required_score=400)

    themes = {}
    for tid, theme in THEMES.items():
        members = {}
        for g in genes:
            facets = classify(g, ann.get(g, {}), uniprot_text(g), gwas[g], "; ".join(lib_text[g])).get(tid)
            if facets:
                primary = max(facets, key=lambda f: (len(facets[f]), -[x["id"] for x in theme["facets"]].index(f)))
                members[g] = {"facets": facets, "primary": primary,
                              "pathways": [p for p in ann.get(g, {}).get("reactome", [])]}
        links = [{"a": e["preferredName_A"], "b": e["preferredName_B"], "score": e["score"]} for e in edges
                 if e["preferredName_A"] in members and e["preferredName_B"] in members]
        links = list({tuple(sorted((l["a"], l["b"]))): l for l in links}.values())
        shared = {}
        for g, m in members.items():
            for p in m["pathways"]:
                shared.setdefault(p, []).append(g)
        facet_rx = "|".join(f["reactome"] for f in theme["facets"])
        pathways = sorted(([{"pathway": p, "genes": sorted(gs), "on_theme": bool(re.search(facet_rx, p, re.I))}
                            for p, gs in shared.items() if len(gs) >= 2]),
                          key=lambda x: (not x["on_theme"], -len(x["genes"])))[:40]
        for m in members.values():
            del m["pathways"]
        themes[tid] = {"name": theme["name"], "about": theme["about"],
                       "facets": [{"id": f["id"], "name": f["name"], "core": f["core"]} for f in theme["facets"]],
                       "genes": members, "links": links, "pathways": pathways}
    return {"themes": themes, "n_library_genes": len(genes)}


if __name__ == "__main__":
    data = build()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    for tid, t in data["themes"].items():
        by_facet = {f["id"]: sum(1 for m in t["genes"].values() if f["id"] in m["facets"]) for f in t["facets"]}
        print(f"✅ {t['name']}: {len(t['genes'])} genes, {len(t['links'])} links, {len(t['pathways'])} shared pathways | {by_facet}")
