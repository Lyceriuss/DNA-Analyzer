"""The numbers behind the explorer's introduction (the Home tab): the intro_stats dataset.

    python -m cluster_analysis.explorer.intro                # print the rows (export writes them as intro_stats.json)

One row for the method, the same for everyone (person null):
  panel_people, holdout       the 1000 Genomes reference panel and the people held out to measure imputation
  map_sites                   genome-wide sites by class (chip, reliable, uncertain, not_knowable), genome/imputability.py
  map_by_frequency            per frequency band: sites measured, mean r2 and carrier sensitivity (all DR2 bins together)
  clinvar                     ClinVar pathogenic variants by what a chip can see (genes.json totals)
  references                  reference files in genome/references.json
One row per person:
  source, format              the raw file and its maker (genome/formats.py)
  measured, per_chrom         calls in the raw file, per chromosome
  matched, not_lifted         of them, those at 1000 Genomes sites, and those that couldn't be moved to GRCh38
  imputed, kept               calls imputation made, and those kept (GP >= the run's min_gp)
  tiers                       kept calls by confidence tier (genome/impute.py)
  validation                  hidden chip SNPs re-imputed: how many, and the share right among confident guesses

Whether the introduction is mandatory is settings.json (intro_required), not data.
"""
import json
import re
import os

from genome import build as gbuild

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SETTINGS = os.path.join(HERE, "settings.json")


def settings():
    return json.load(open(SETTINGS, encoding="utf-8"))


def _load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None


def general():
    imp = os.path.join(gbuild.REF, "imputability")
    meta = _load(os.path.join(imp, "summary.json")) or {}
    by = {}
    for c in meta.get("calibration", []):
        b = by.setdefault(tuple(c["maf_bin"]), {"sites": 0, "r2": 0.0, "sens_w": 0.0, "sens_n": 0})
        b["sites"] += c["sites"]
        b["r2"] += c["r2"] * c["sites"]
        if c.get("sensitivity") is not None:
            b["sens_w"] += c["sensitivity"] * c["sites"]
            b["sens_n"] += c["sites"]
    bands = [{"from": lo, "to": min(hi, 0.5), "sites": b["sites"], "r2": round(b["r2"] / b["sites"], 3),
              "sensitivity": round(b["sens_w"] / b["sens_n"], 3) if b["sens_n"] else None}
             for (lo, hi), b in sorted(by.items())]
    genes = _load(os.path.join(imp, "genes.json")) or []
    keys = ("pathogenic", "chip", "reliable", "uncertain", "not_knowable", "not_in_panel", "not_mapped")
    refs = _load(os.path.join(ROOT, "genome", "references.json")) or {"references": []}
    from genome.impute import panel
    return {"person": None, "kind": "general", "panel_people": panel(gbuild.panel_name()).get("samples"),
            "holdout": meta.get("holdout"), "map_sites": meta.get("sites"), "map_by_frequency": bands,
            "clinvar": {k: sum(g.get(k, 0) for g in genes) for k in keys} if genes else None,
            "references": len(refs["references"])}


def person(p):
    from genome import formats
    from genome.impute import OUT, DEFAULT_PANEL
    from genome.loader import person_label
    pid, name = p["id"], gbuild.panel_name()
    folder = os.path.join(OUT, person_label(p["dna"]))
    folder = folder if name == DEFAULT_PANEL else os.path.join(folder, name)
    s = _load(os.path.join(folder, "summary.json")) or {}
    cal = _load(os.path.join(folder, "calibration.json")) or {}
    chroms = s.get("chroms", {})
    # Confident guesses (GP at or above the run's threshold) among the hidden chip SNPs: the share that were right
    cells = cal.get("cells", {}).values()
    n, right = sum(c["n"] for c in cells), sum(c["right"] for c in cells)
    try:
        fmt = formats.detect(p["dna"])
    except (SystemExit, OSError):
        fmt = None
    return {"person": pid, "kind": "person", "sex": p.get("sex"), "source": os.path.basename(p["dna"]), "format": fmt,
            "measured": s.get("totals", {}).get("calls"), "per_chrom": {c: v.get("calls") for c, v in chroms.items()},
            "matched": sum(v.get("matched", 0) for v in chroms.values()) or None,
            "not_lifted": sum((s.get("not_lifted") or {}).values()), "imputed": s.get("totals", {}).get("imputed"),
            "kept": s.get("totals", {}).get("imputed_kept"), "min_gp": s.get("min_gp"), "tiers": s.get("tiers"),
            "validation": {"hidden": cal.get("hidden"), "confident": n, "right": round(right / n, 4) if n else None},
            "example_gt": json.dumps(genotypes_at(p["dna"], [r for c in CLUSTER.values() for r in c["variants"]])),
            # the slide's worked example is this profile (data/input/intro_example.json): no separate marker for it
            "is_example": pid == (_load(os.path.join(ROOT, "data", "input", "intro_example.json")) or {}).get("profile")}


# The introduction's teaching example: the alcohol chain, ADH1B then ALDH2, one well-studied variant each, shown as
# chemistry: how fast each form works (UniProt's measured kinetics), what the buildup does (MedGen's definition of the
# condition) and one GWAS Catalog effect. The choices here are the variants, which kinetics rows (allele, substrate) and
# which association to show; every number and sentence is read from the sources.
EXAMPLE = [
    {"gene": "ADH1B", "rsid": "rs1229984", "call": "GoF", "acc": "P00325",
     # Vmax toward ethanol at the higher NAD+ concentration, typical (*1) and fast (*2) forms
     "speed": {"substrate": "ethanol", "condition": "2.4 mM", "typical": "ADH1B*1", "variant": "ADH1B*2"},
     "picks": [("Alcohol use disorder", "Kember RL", "T")]},
    {"gene": "ALDH2", "rsid": "rs671", "call": "LoF", "acc": "P05091",
     "affinity": "acetaldehyde", "medgen": "Alcohol sensitivity, acute", "picks": []},
]


# Controlled studies that measured blood acetaldehyde by genotype after a dose like one beer (0.3 g/kg): the choice is
# the studies; what each found is the sentence of its abstract that says it, read from Europe PMC
MEASURED = [
    {"pmid": "25365528", "about": "ALDH2", "find": r"ALDH2\*1/\*2 heterozygotes[^.]*higher peak levels[^.]*\."},
    {"pmid": "25365528", "about": "ADH1B", "find": r"no significant differences in peak levels and AUCs of blood ethanol, acetaldehyde[^.]*\."},
    {"pmid": "34439848", "about": "both", "find": r"dose-dependent increase of blood ethanol concentration, unaffected by ADH1B or ALDH2"},
]


def europepmc_abstract(pmid):
    from cluster_analysis import sources
    def fetch():
        r = sources._request("GET", "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                             params={"query": f"EXT_ID:{pmid} AND SRC:MED", "format": "json", "resultType": "core"})
        x = (r.get("resultList", {}).get("result") or [{}])[0]
        return {"title": x.get("title"), "authors": x.get("authorString"), "year": x.get("pubYear"),
                "abstract": re.sub(r"<[^>]+>", "", x.get("abstractText") or "")}
    return sources._cached("europepmc_abstract", pmid, fetch)


def measured():
    out = []
    for m in MEASURED:
        a = europepmc_abstract(m["pmid"]) or {}
        hit = re.search(m["find"], a.get("abstract", ""))
        if hit:
            first = (a.get("authors") or "").split(",")[0].strip()
            out.append({"pmid": m["pmid"], "about": m["about"], "finding": hit.group(0).rstrip(".") + ".",
                        "study": f"{first} {a.get('year')}", "title": a.get("title")})
    return out


# The buildup in numbers, from the open full text of Chen 2021 (0.3 g/kg, about one beer for 70 kg): which sentences hold
# the numbers is chosen here; the numbers are read from the text at export. All its groups carried two fast ADH1B copies,
# so its ALDH2*1/*1 group is the ADH1B-fast form; its ADH1B*1/*1 group (typical) is stated only as no significant rise.
BUILDUP = {"pmid": "34439848", "pmcid": "PMC8391449", "dose": 0.3,
           "peak": r"(\d+(?:\.\d+)?) µM vs\. \d+(?:\.\d+)? µM, following the 0\.3 and 0\.5 g/kg",
           "low": r"no significant increase, (\d+)~(\d+) µM, in the ALDH2\*1/\*1",
           "typical": r"no significant increase for the ADH1B\*1/\*1 group regardless of the challenging ethanol dose",
           "heart": r"\d+(?:\.\d+)? ± [\d.]+% and (\d+(?:\.\d+)?) ± [\d.]+% \(mean ± SE\)",
           "heart_none": r"There were no heart rate changes in the ALDH2\*1/\*1 subjects",
           "feel": r"The participants with ALDH2\*2 heterozygote revealed more negative psychological responses than those with ALDH2\*1/\*1 homozygote"}


def europepmc_fulltext(pmcid):
    from cluster_analysis import sources
    def fetch():
        import requests
        r = requests.get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML", timeout=60,
                         headers={"User-Agent": "DNA-Analyzer (research)"})
        r.raise_for_status()
        return {"text": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text)).replace("&lt;", "<").replace("&gt;", ">")}
    return sources._cached("europepmc_fulltext", pmcid, fetch)


def buildup():
    b = BUILDUP
    t = (europepmc_fulltext(b["pmcid"]) or {}).get("text", "")
    a = europepmc_abstract(b["pmid"]) or {}
    peak, low, heart = re.search(b["peak"], t), re.search(b["low"], t), re.search(b["heart"], t)
    if not (peak and low and heart and re.search(b["typical"], t) and re.search(b["heart_none"], t)):
        return None
    feel = re.search(b["feel"], t)
    return {"pmid": b["pmid"], "pmcid": b["pmcid"], "dose_g_per_kg": b["dose"],
            "study": f"{(a.get('authors') or '').split(',')[0].strip()} {a.get('year')}",
            # peak blood acetaldehyde, µM: None = no significant rise
            "acetaldehyde": {"typical": None, "lof": float(peak.group(1)), "gof": [float(low.group(1)), float(low.group(2))]},
            # heart rate change at 25 min, %
            "heart": {"typical": 0, "lof": float(heart.group(1)), "gof": 0},
            "feel": {"lof": feel.group(0) + "." if feel else None}}


def pubchem_ethanol():
    """How fast the whole body clears ethanol, and its density, from PubChem's record for ethanol (CID 702): the
    sentence giving grams per hour for a 70 kg adult, and the density at 20 °C. Cached."""
    from cluster_analysis import sources

    def texts(heading):
        def fetch():
            return sources._request("GET", "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/702/JSON", params={"heading": heading})
        out = []
        def walk(n):
            if isinstance(n, dict):
                for k, v in n.items():
                    if k == "String" and isinstance(v, str):
                        out.append(v)
                    else:
                        walk(v)
            elif isinstance(n, list):
                for v in n:
                    walk(v)
        walk(sources._cached("pubchem_view", f"702|{heading}", fetch))
        return out
    rate = None
    for t in texts("Metabolism/Metabolites"):
        m = re.search(r"about (\d+(?:\.\d+)?) gr?\b[^.]*?per hour in a (\d+)-kg adult(?:, or approximately (\d+) mg/kg per hour)?", t)
        if m:
            sentence = next((x for x in re.split(r"(?<=\.)\s", t) if m.group(0) in x), m.group(0))
            rate = {"g_per_hour": float(m.group(1)), "weight_kg": float(m.group(2)),
                    "mg_per_kg_hour": float(m.group(3)) if m.group(3) else None, "sentence": sentence,
                    "zero_order": "zero-order" in t}
            break
    density = next((float(m.group(1)) for t in texts("Density") for m in [re.match(r"(0\.\d+) g/cu cm", t)] if m), None)
    return {"cid": 702, "url": "https://pubchem.ncbi.nlm.nih.gov/compound/702", "rate": rate, "density": density}


def gwas_rows(rsids):
    import csv
    import io
    import zipfile
    path = os.path.join(ROOT, "data", "reference", "gwas_associations.zip")
    if not os.path.exists(path):
        return []
    z = zipfile.ZipFile(path)
    return [r for r in csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8"), delimiter="\t") if r.get("SNPS") in rsids]


def uniprot_full(acc):
    from cluster_analysis import sources
    return sources._cached("uniprot_full", acc, lambda: sources._request("GET", f"https://rest.uniprot.org/uniprotkb/{acc}.json"))


def medgen_definition(title):
    """MedGen's definition of a condition (NCBI E-utilities), cached."""
    from cluster_analysis import sources
    def fetch():
        e = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        ids = sources._request("GET", f"{e}/esearch.fcgi", params={"db": "medgen", "term": f'"{title}"', "retmode": "json"})["esearchresult"]["idlist"]
        if not ids:
            return {}
        r = sources._request("GET", f"{e}/esummary.fcgi", params={"db": "medgen", "id": ids[0], "retmode": "json"})["result"][ids[0]]
        d = r.get("definition")
        text = d.get("value", "") if isinstance(d, dict) else str(d or "")
        return {"id": ids[0], "title": r.get("title"), "definition": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()}
    return sources._cached("medgen_definition", title, fetch)


def example():
    """The alcohol example's facts per gene: UniProt's notes on the variant, the speeds (Vmax) or affinity (Km) UniProt
    measured, MedGen's definition of what the buildup does, and the chosen GWAS association, per copy of the allele."""
    import html as htmllib
    from cluster_analysis.evidence.function_evidence import uniprot_variants
    rows_ = gwas_rows({e["rsid"] for e in EXAMPLE})
    out = []
    for e in EXAMPLE:
        # UniProt can list one rsID under several protein changes: the one with notes (the documented form) first. Its
        # notes can sit on the reference residue itself ("="), where UniProt's sequence already carries the variant form
        feats = [f for f in uniprot_variants(e["acc"]).get("features", [])
                 if f.get("type") == "VARIANT" and any(str(x.get("id")) == e["rsid"] for x in f.get("xrefs", []))]
        feats.sort(key=lambda f: -len(f.get("descriptions") or []))
        f = feats[0] if feats else {}
        notes = [d.get("value") for d in f.get("descriptions") or [] if d.get("value")]
        alt = f.get("alternativeSequence")
        variant = (f"{f.get('wildType')}{f.get('begin')}" if alt in (None, "=") else f"{f.get('wildType')}{f.get('begin')}{alt}") if f else ""
        item = {"gene": e["gene"], "rsid": e["rsid"], "call": e["call"], "variant": variant, "uniprot": notes, "effects": []}
        entry = uniprot_full(e["acc"]) or {}
        kin = [c.get("kineticParameters") or {} for c in entry.get("comments", []) if c.get("commentType") == "BIOPHYSICOCHEMICAL PROPERTIES"]
        if e.get("speed"):
            sp = e["speed"]
            def vmax(allele):
                for k in kin:
                    for v in k.get("maximumVelocities", []):
                        en = v.get("enzyme", "")
                        if sp["substrate"] in en and f"allele {allele} " in en + " " and sp["condition"] in en:
                            return {"value": v.get("velocity"), "unit": v.get("unit")}
            item["speed"] = {"typical": vmax(sp["typical"]), "variant": vmax(sp["variant"]), "substrate": sp["substrate"],
                             "typical_allele": sp["typical"], "variant_allele": sp["variant"]}
        if e.get("affinity"):
            km = next(({"value": m.get("constant"), "unit": m.get("unit"), "substrate": m.get("substrate")} for k in kin
                       for m in k.get("michaelisConstants", []) if m.get("substrate", "").startswith(e["affinity"])), None)
            item["affinity"] = km
        if e.get("medgen"):
            item["medgen"] = medgen_definition(e["medgen"])
        for trait, author, allele in e["picks"]:
            hits = [r for r in rows_ if r["SNPS"] == e["rsid"] and r["DISEASE/TRAIT"].strip() == trait and r["FIRST AUTHOR"].startswith(author)]
            hits.sort(key=lambda r: (not r["OR or BETA"], bool(re.search(r"unit|z.score|drinks", r["95% CI (TEXT)"], re.I))))
            if not hits:
                continue
            r = hits[0]
            reported = r["STRONGEST SNP-RISK ALLELE"].split("-")[-1]
            est = float(r["OR or BETA"]) if r["OR or BETA"] else None
            is_or = est is not None and not re.search(r"unit|z.score|drinks", r["95% CI (TEXT)"], re.I)
            per = est if reported == allele else (1 / est if est else None)
            item["effects"].append({"trait": trait, "or": round(per, 2) if is_or and per else None, "p": r["P-VALUE"],
                                    "author": r["FIRST AUTHOR"], "year": r["DATE"][:4], "pmid": r["PUBMEDID"], "sample": r["INITIAL SAMPLE SIZE"]})
        out.append(item)
    return out


# "Reading a cluster" (Home, step 5): what a STRING link between two fertility genes rests on. STRING's own channel
# scores for the pair (experiments, curated databases, co-expression, text mining; read from the STRING network calls
# the themes made, cached in cluster_analysis/cache) and the most specific Reactome pathways the two genes share
# (Ensembl2Reactome, lowest-level pathways). High-confidence pairs only (combined >= 0.7), among the fertility themes'
# genes, so the table stays small.
PAIR_SCORE = 0.7
CHANNELS = (("escore", "experiments"), ("dscore", "databases"), ("ascore", "coexpression"), ("tscore", "textmining"))


def pairs():
    import glob
    from cluster_analysis import sources
    from cluster_analysis.evidence.systems import symbols_to_ensembl
    genes = set()
    for f in glob.glob(os.path.join(ROOT, gbuild.OUTPUT, "theme_*_fertility_*.json")):
        genes |= set((_load(f) or {}).get("genes", {}))
    found = {}
    for f in glob.glob(os.path.join(sources.CACHE_DIR, "string_network_*.json")):
        for r in _load(f) or []:
            a, b = r.get("preferredName_A"), r.get("preferredName_B")
            if r.get("score", 0) >= PAIR_SCORE and a in genes and b in genes:
                found[tuple(sorted((a, b)))] = r
    if not found:
        return None
    # Reactome: each gene's lowest-level pathways; a pair's shared ones, the smallest (most specific) first
    used = {g for k in found for g in k}
    ensg = symbols_to_ensembl(used)
    by_ensg, size, names = {}, {}, {}
    ref = os.path.join(ROOT, "data", "reference")
    for line in open(os.path.join(ref, "ReactomePathways.txt"), encoding="utf-8"):
        x = line.rstrip("\n").split("\t")
        if len(x) >= 3 and x[2] == "Homo sapiens":
            names[x[0]] = x[1]
    for line in open(os.path.join(ref, "Ensembl2Reactome.txt"), encoding="utf-8", errors="replace"):
        x = line.rstrip("\n").split("\t")
        if len(x) >= 6 and x[5] == "Homo sapiens" and x[1] in names:
            by_ensg.setdefault(x[0], set()).add(x[1])
            size[x[1]] = size.get(x[1], 0) + 1
    paths = {g: set().union(*(by_ensg.get(e, set()) for e in ensg.get(g, ()))) for g in used}
    table, index = [], {}
    out = {}
    for (a, b), r in found.items():
        shared = sorted(paths.get(a, set()) & paths.get(b, set()), key=lambda pid: (size.get(pid, 0), pid))
        ids = []
        for pid in shared[:2]:
            if pid not in index:
                index[pid] = len(table)
                table.append(names[pid])
            ids.append(index[pid])
        out[f"{a}|{b}"] = [round(r.get(k, 0) * 100) for k, _ in CHANNELS] + [round(r["score"] * 100), len(shared), ids]
    return {"channels": [n for _, n in CHANNELS], "pairs": out, "pathways": table, "min_score": PAIR_SCORE}


# "Reading a cluster" (Home, step 5): what a cluster gene's call means for the person, told for the example gene the slide
# picks (the changed gene with the most confident partners). As for the alcohol example, the choices here are the gene,
# its partners, the person's variants to look up, the tissues, the studies and the regex anchors that find each number
# in the study's own text; every number and sentence is read from GTEx, UniProt, Reactome, Europe PMC and the GWAS Catalog.
CLUSTER = {
    "ESR1": {
        "acc": "P03372", "reactome": "R-HSA-9018519",
        "partners": {"NCOA1": "Q15788", "ESR2": "Q92731", "PGR": "P06401", "GREB1": "Q4ZG55"},
        "variants": ["rs2234693", "rs9340799", "rs851982", "rs851984"],
        "tissues": ["Uterus", "Ovary", "Vagina", "Breast_Mammary_Tissue", "Pituitary", "Thyroid"],
        # Controlled studies in women, chosen for the person's ESR1 variants; what they found is read from their text
        "studies": [
            {"id": "dose", "pmid": "25526766", "pmcid": "PMC4302593", "rsid": "rs2234693", "name": "PvuII",
             "measure": "Total rFSH dose in IVF", "unit": "IU",
             "groups": r"TT (\d+) IU versus TC (\d+) IU \(p = ([\d.]+)\) and versus CC (\d+) IU",
             "labels": ["TT", "TC", "CC"], "order": [0, 1, 3], "p": 2,
             "sentence": r"The PvuII \(ESR1\) TT and RsaI \(ESR2\) GG genotypes were associated with a longer induction period and higher doses of medication \(p < [\d.]+\)\.",
             "n": r"involving (\d+) infertile women"},
            {"id": "response", "pmid": "25526766", "pmcid": "PMC4302593", "rsid": "rs9340799", "name": "XbaI",
             "measure": "IVF response, median per woman (100 IU a day)", "table": r"Table 4 Association of the XbaI genotypes",
             "rows": ["Follicles", "Mature oocytes", "Embryos", "Good quality embryos"], "labels": ["AA", "AG + GG"],
             "sentence": r"The XbaI \(ESR1\) AA genotype was associated with better COH results, including a larger number of follicles, mature oocytes, embryos, and good quality embryos \(p < [\d.]+\)\.",
             "n": r"involving (\d+) infertile women"},
            {"id": "odds", "pmid": "24427778", "pmcid": "PMC3880708", "rsid": "rs9340799", "name": "XbaI",
             "measure": "Endometriosis and IVF failure, against fertile women",
             "table": r"Endometriosis AA — — AG ([\d.]+) \(([\d.]+)–([\d.]+)\) ([\d.]+) GG ([\d.]+) \(([\d.]+)–([\d.]+)\) ([\d.]+) IVF Failure AA — — AG ([\d.]+) \(([\d.]+)–([\d.]+)\) ([\d.]+) GG ([\d.]+) \(([\d.]+)–([\d.]+)\) ([\d.]+)",
             "outcomes": ["Endometriosis-related infertility", "IVF failure"], "labels": ["AA", "AG", "GG"],
             "sentence": r"After controlling for age, infertile women with ESR1 rs9340799 GG genotype presented 4-fold increased risk of endometriosis \(OR [^)]*\)",
             "n": r"We included (\d+) infertile women with endometriosis, (\d+) infertile women with at least one IVF failure and also (\d+) fertile women"},
            {"id": "meta", "pmid": "31821471", "rsid": "rs2234693", "name": "PvuII", "measure": "Endometriosis, meta-analysis",
             "sentence": r"(\d+) showed a significant trend towards the lack of an association: [^;]*?estrogen receptor 1 \(ESR1\) rs2234693"},
        ],
        # GWAS Catalog associations of the person's alleles, per copy (trait, first author, the allele the effect is for)
        "gwas": [("rs851982", "Female infertility (idiopathic, defined by coding in electronic health record)", "Venkatesh SS"),
                 ("rs2234693", "Heel bone mineral density", "Morris JA")],
    },
}
TAGS = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(\s[^<>]*)?/?>")


def europepmc_abstract_raw(pmid):
    """The abstract with only real tags removed, so "p < 0.05" survives (europepmc_abstract strips from "<" on)."""
    from cluster_analysis import sources
    def fetch():
        r = sources._request("GET", "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                             params={"query": f"EXT_ID:{pmid} AND SRC:MED", "format": "json", "resultType": "core"})
        x = (r.get("resultList", {}).get("result") or [{}])[0]
        return {"title": x.get("title"), "authors": x.get("authorString"), "year": x.get("pubYear"), "abstract": x.get("abstractText") or ""}
    a = sources._cached("europepmc_abstract_tags", pmid, fetch) or {}
    text = TAGS.sub(" ", a.get("abstract") or "").replace("&lt;", "<").replace("&gt;", ">")
    return {**a, "abstract": re.sub(r"\s+", " ", text).strip()}


def gtex_tissues(gene, rsid, tissues):
    """GTEx v8: the variant's effect on the gene's expression (NES of the alternative allele) in each tissue, measured
    whether significant or not, with the tissue's sample size and the gene's median expression there."""
    from cluster_analysis import sources
    from cluster_analysis.evidence.gene_calls import _gtex
    def fetch():
        v = (_gtex("dataset/variant", {"snpId": rsid, "datasetId": "gtex_v8"}).get("data") or [{}])[0].get("variantId")
        g = next((x["gencodeId"] for x in _gtex("reference/gene", {"geneId": gene, "gencodeVersion": "v26", "genomeBuild": "GRCh38/hg38"}).get("data") or []
                  if x.get("geneSymbol") == gene), None)
        if not (v and g):
            return None
        sig = {r["tissueSiteDetailId"] for r in _gtex("association/singleTissueEqtl", {"variantId": v, "datasetId": "gtex_v8"}).get("data") or []
               if r.get("geneSymbol") == gene}
        tpm = {x["tissueSiteDetailId"]: x["median"] for x in _gtex("expression/medianGeneExpression", {"gencodeId": g, "datasetId": "gtex_v8"}).get("data") or []}
        size = {x["tissueSiteDetailId"]: (x.get("eqtlSampleSummary") or {}).get("totalCount") for x in _gtex("dataset/tissueSiteDetail", {"datasetId": "gtex_v8"}).get("data") or []}
        rows = []
        for t in sorted(set(tissues) | sig):
            d = _gtex("association/dyneqtl", {"gencodeId": g, "variantId": v, "tissueSiteDetailId": t, "datasetId": "gtex_v8"})
            rows.append({"tissue": t, "nes": d.get("nes"), "p": d.get("pValue"), "significant": t in sig, "tpm": tpm.get(t), "n": size.get(t)})
        _, _, ref, alt, _ = v.split("_")
        return {"variant": v, "ref": ref, "alt": alt, "rows": rows, "top_tpm": sorted(tpm.items(), key=lambda x: -x[1])[:5]}
    return sources._cached("gtex_tissues", f"{gene}|{rsid}|{','.join(sorted(tissues))}", fetch)


def _study(st):
    a = europepmc_abstract_raw(st["pmid"]) or {}
    t = (europepmc_fulltext(st["pmcid"]) or {}).get("text", "") if st.get("pmcid") else ""
    out = {k: st[k] for k in ("id", "pmid", "rsid", "name", "measure") if k in st}
    out.update(study=f"{(a.get('authors') or '').split(',')[0].strip()} {a.get('year')}", title=a.get("title"))
    hit = re.search(st["sentence"], a.get("abstract", "")) or re.search(st["sentence"], t)
    out["finding"] = hit.group(0) if hit else None
    if st.get("n"):
        m = re.search(st["n"], a.get("abstract", "")) or re.search(st["n"], t)
        out["n"] = sum(int(x) for x in m.groups()) if m else None
        out["n_groups"] = [int(x) for x in m.groups()] if m else None
    if st["id"] == "dose":
        m = re.search(st["groups"], t)
        if not m:
            return None
        out.update(unit=st["unit"], groups=[{"label": l, "value": int(m.group(i + 1))} for l, i in zip(st["labels"], st["order"])], p=float(m.group(st["p"] + 1)))
    elif st["id"] == "response":
        seg = t[t.find(re.search(st["table"], t).group(0)):][:1500] if re.search(st["table"], t) else ""
        rows = []
        for r in st["rows"]:
            m = re.search(re.escape(r) + r" \d+ ([\d,]+) [\d,]+ [\d,]+ \d+ ([\d,]+) [\d,]+ [\d,]+ [\d,.]+ ([\d,]+)", seg)
            if m:
                f = lambda x: float(x.replace(",", "."))
                rows.append({"measure": r, "values": [f(m.group(1)), f(m.group(2))], "p": f(m.group(3))})
        if not rows:
            return None
        out.update(labels=st["labels"], rows=rows)
    elif st["id"] == "odds":
        m = re.search(st["table"], t)
        if not m:
            return None
        v = [float(x) for x in m.groups()]
        out.update(labels=st["labels"], outcomes=[
            {"outcome": st["outcomes"][0], "odds": [1, v[0], v[4]], "ci": [None, v[1:3], v[5:7]], "p": [None, v[3], v[7]]},
            {"outcome": st["outcomes"][1], "odds": [1, v[8], v[12]], "ci": [None, v[9:11], v[13:15]], "p": [None, v[11], v[15]]}])
    elif not out["finding"]:
        return None
    return out


# The slide's example is the same for every profile: one woman's genotypes at the example gene, named only in the local,
# gitignored data/input/intro_example.json ({"profile": id}), so no one's genotypes or id sit in the repo. Without that setting
# (or the profile), the example takes the most common European genotype at each variant (1000 Genomes via Ensembl).
def genotypes_at(dna, rsids):
    """The person's calls at these rsIDs, from their imputed file (or the raw file before imputation)."""
    from genome.loader import imputed_path
    path = imputed_path(dna)
    if not os.path.exists(path):
        path = dna
    want, out = set(rsids), {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[:3] == '"rs' or line[:2] == "rs":
                x = [v.strip('"') for v in line.split(",", 4)]
                if x[0] in want:
                    out[x[0]] = x[3]
                    if len(out) == len(want):
                        break
    return out


def eur_common(rsid):
    """The most common genotype among 1000 Genomes Europeans (Ensembl)."""
    from cluster_analysis import sources
    def fetch():
        r = sources._request("GET", f"https://rest.ensembl.org/variation/human/{rsid}", params={"population_genotypes": 1},
                             headers={"Content-Type": "application/json"}) or {}
        return [x for x in r.get("population_genotypes", []) if x.get("population") == "1000GENOMES:phase_3:EUR"]
    rows = sources._cached("ensembl_pop_genotypes", rsid, fetch) or []
    best = max(rows, key=lambda x: x.get("frequency", 0), default=None)
    return (best["genotype"].replace("|", ""), round(best["frequency"], 3)) if best else (None, None)


def cluster_example(people):
    """The example woman for the slide: her fertility theme rows (as the Clusters tab draws them, from the last export of
    the datasets) and her genotypes at the example gene's variants; the 1000 Genomes fallback without one."""
    from cluster_analysis import profiles as prof
    gene = next(iter(CLUSTER))
    c = CLUSTER[gene]
    graph = next((x for x in prof.theme_graphs() if x["theme"] == "fertility_female"), None)
    if not graph:
        return None
    facets = {m["id"]: m["name"] for m in graph["mechanisms"]}
    facets.setdefault("disease", graph.get("disease_name") or "Disease link, mechanism not yet known")
    rsids = c["variants"]
    pid = (_load(os.path.join(ROOT, "data", "input", "intro_example.json")) or {}).get("profile")
    person = next((x for x in people if x["id"] == pid and x.get("sex") == "female"), None)
    out = {"gene": gene, "theme": "fertility_female", "theme_name": graph["name"], "facets": facets}
    ds = os.path.join(ROOT, gbuild.EXPLORER, "datasets")
    # The cycle phases' chains (fertility_deep, the same for everyone): where the gene sits in the cycle
    ph = _load(os.path.join(ds, "fd_phases.json")) or []
    first = next((r["person"] for r in ph if r.get("person")), None)
    out["phases"] = [{k: r[k] for k in ("phase", "name", "chains")} for r in ph if r.get("person") == first]
    tg = [r for r in (_load(os.path.join(ds, "theme_genes.json")) or []) if person and r.get("person") == person["id"] and r["theme"] == "fertility_female"]
    if person and tg:
        keep = {r["gene"] for r in tg if r.get("notable")}
        out["genes"] = [{k: v for k, v in r.items() if k != "person" and (k != "evidence" or r["gene"] == gene)} for r in tg if r["gene"] in keep]
        out["links"] = [{k: l[k] for k in ("a", "b", "score")} for l in (_load(os.path.join(ds, "theme_links.json")) or [])
                        if l.get("person") == person["id"] and l["theme"] == "fertility_female" and l["a"] in keep and l["b"] in keep]
        out["genotypes"] = genotypes_at(person["dna"], rsids)
        out["source"] = "profile"
    else:
        names = [gene] + list(c["partners"])
        out["genes"] = [{"gene": n, "primary": graph["genes"].get(n, {}).get("primary") or "disease", "notable": True} for n in names]
        pt = (pairs() or {}).get("pairs", {})
        out["links"] = [{"a": a, "b": b, "score": pt[f"{min(a, b)}|{max(a, b)}"][4] / 100} for i, a in enumerate(names) for b in names[i + 1:]
                        if f"{min(a, b)}|{max(a, b)}" in pt]
        gts = {r: eur_common(r) for r in rsids}
        out["genotypes"] = {r: g for r, (g, _) in gts.items() if g}
        out["frequency"] = {r: f for r, (_, f) in gts.items() if f}
        out["source"] = "1000 Genomes Europeans"
    return out


def cluster(people=()):
    out = {}
    from cluster_analysis.nutrition.nutrient_steps import summary as reactome_summary
    rows_ = gwas_rows({r for c in CLUSTER.values() for r, _, _ in c["gwas"]})
    for gene, c in CLUSTER.items():
        def fn(acc):
            e = uniprot_full(acc) or {}
            t = next((x["value"] for cm in e.get("comments", []) if cm.get("commentType") == "FUNCTION" for x in cm.get("texts", [])), "")
            t = re.sub(r"\s*\((?:PubMed:\d+[,; ]*)+\)", "", t)
            return " ".join(re.split(r"(?<=\.)\s+", t)[:2])
        gw = []
        for rsid, trait, author in c["gwas"]:
            hits = [r for r in rows_ if r["SNPS"] == rsid and r["DISEASE/TRAIT"].strip() == trait and r["FIRST AUTHOR"].startswith(author)]
            if hits:
                r = hits[0]
                gw.append({"rsid": rsid, "trait": trait, "allele": r["STRONGEST SNP-RISK ALLELE"].split("-")[-1], "estimate": float(r["OR or BETA"]) if r["OR or BETA"] else None,
                           "ci": r["95% CI (TEXT)"], "p": r["P-VALUE"], "author": r["FIRST AUTHOR"], "year": r["DATE"][:4], "pmid": r["PUBMEDID"], "sample": r["INITIAL SAMPLE SIZE"]})
        out[gene] = {"function": fn(c["acc"]), "partners": {g: fn(a) for g, a in c["partners"].items()},
                     "reactome": {"id": c["reactome"], "summary": " ".join(re.split(r"(?<=\.)\s+", reactome_summary(c["reactome"]))[:1])},
                     "gtex": {r: gtex_tissues(gene, r, c["tissues"]) for r in c["variants"]},
                     "studies": [x for x in (_study(st) for st in c["studies"]) if x], "gwas": gw}
    out["_example"] = cluster_example(people)
    return out


# The last step of the introduction: the rules around working with one's own DNA. The choice here is the acts, the
# articles and the regex anchors; every quoted sentence is read from the official text at export (EUR-Lex for the EU
# acts, riksdagen.se for Swedish law), cached. An item whose text can't be fetched or matched is left out.
LAW = [
    {"id": "gdpr", "level": "EU", "act": "General Data Protection Regulation (EU) 2016/679", "short": "GDPR",
     "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679", "source": "eurlex", "celex": "32016R0679",
     "items": [("Art. 4(13)", r"\(13\) ‘genetic data’[^;]*;"),
               ("Art. 9(1)", r"Processing of personal data revealing racial[^.]*\."),
               ("Art. 9(2)(a)", r"\(a\) the data subject has given explicit consent[^;]*;"),
               ("Art. 2(2)(c)", r"\(c\) by a natural person in the course of a purely personal or household activity;"),
               ("Recital 18", r"\(18\) This Regulation does not apply to the processing of personal data by a natural person in the course of a purely personal or household activity[^.]*\.")]},
    {"id": "mdr", "level": "EU", "act": "Medical Device Regulation (EU) 2017/745", "short": "MDR",
     "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32017R0745", "source": "eurlex", "celex": "32017R0745",
     "items": [("Art. 2(1)", r"\(1\) ‘medical device’ means[^—]*?purposes: — diagnosis, prevention, monitoring, prediction, prognosis, treatment or alleviation of disease,"),
               ("Art. 2(12)", r"\(12\) ‘intended purpose’ means[^;]*;"),
               ("Annex VIII, Rule 11", r"Software intended to provide information which is used to take decisions with diagnosis or therapeutic purposes is classified as class IIa")]},
    {"id": "ivdr", "level": "EU", "act": "In Vitro Diagnostic Medical Device Regulation (EU) 2017/746", "short": "IVDR",
     "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32017R0746", "source": "eurlex", "celex": "32017R0746",
     "items": [("Art. 2(2)", r"\(2\) ‘ ?in vitro diagnostic medical device’ means any medical device which is[^,]*, reagent product, calibrator, control material, kit, instrument, apparatus, piece of equipment, software or system[^:]*:"),
               ("Art. 2(2)(c)", r"\(c\) concerning the predisposition to a medical condition or a disease;")]},
    {"id": "gi", "level": "Sweden", "act": "Lag (2006:351) om genetisk integritet m.m.", "short": "2006:351",
     "url": "https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/lag-2006351-om-genetisk-integritet-mm_sfs-2006-351/",
     "source": "riksdagen", "lang": "sv",
     "items": [("1 kap. 5 §", r"genetisk undersökning: en undersökning inom hälso- och sjukvården eller medicinsk forskning[^,]*,"),
               ("2 kap. 1 §", r"Ingen får utan stöd i lag ställa som villkor för ett avtal[^.]*\. Ingen får utan stöd i lag i samband med ett avtal efterforska eller använda genetisk information om den andre\. Ingen får olovligen bereda sig tillgång till genetisk information om någon annan\."),
               ("2 kap. 2 §", r"I fråga om riskbedömd personförsäkring får .{0,400}?30 prisbasbelopp")]},
]


def law_text(item):
    """The act's text as plain words, fetched once and cached (public pages; no personal data is sent)."""
    from cluster_analysis import sources
    def fetch():
        import requests
        url = item["url"] if item["source"] == "riksdagen" else f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{item['celex']}"
        r = requests.get(url, timeout=90, headers={"User-Agent": "Mozilla/5.0 (DNA-Analyzer; research)"})
        r.raise_for_status()
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text)).replace("&nbsp;", " ").replace("&#160;", " ")
        return {"text": t}
    try:
        return (sources._cached("law_text", item["url"], fetch) or {}).get("text", "")
    except Exception:
        return ""


def law():
    out = []
    for a in LAW:
        t = law_text(a)
        quotes = []
        for ref, rx in a["items"]:
            m = re.search(rx, t)
            if m:
                quotes.append({"ref": ref, "text": re.sub(r"\s+([,;:.])", r"\1", m.group(0)).replace("‘ ", "‘").strip()})
        if quotes:
            out.append({k: a[k] for k in ("id", "level", "act", "short", "url")} | {"lang": a.get("lang", "en"), "quotes": quotes})
    return out


def gwas_limits():
    """From the GWAS Catalog's full association file: how many studies and participants are of European ancestry
    alone, and how large the per-copy odds ratios are (folded to >= 1)."""
    import csv
    import io
    import statistics
    import zipfile
    from cluster_analysis import sources
    path = os.path.join(ROOT, "data", "reference", "gwas_associations.zip")
    if not os.path.exists(path):
        return None
    OTHER = re.compile(r"African|Asian|Hispanic|Latin|Japanese|Chinese|Korean|Indian|Arab|Native|Oceanian|Greater Middle Eastern|"
                       r"Sub-Saharan|Caribbean|Mexican|Brazilian|Pakistani|Bangladeshi|Iranian|Turkish|Filipino|Thai|Vietnamese|"
                       r"Malay|Taiwanese|Singapore|Han|other|multiple|unspecified|NR|not reported", re.I)
    NUM = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)\s+([^\d]*?)(?=,\s*(?:up to\s*)?\d|$)")
    def fetch():
        z = zipfile.ZipFile(path)
        studies, ors = {}, []
        for r in csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8"), delimiter="\t"):
            acc = (r.get("PUBMEDID"), r.get("STUDY"), r.get("INITIAL SAMPLE SIZE"))   # one study (the file has no accession column)
            if acc[0] and acc not in studies:
                eur = other = 0
                for n, desc in NUM.findall(r.get("INITIAL SAMPLE SIZE") or ""):
                    k = int(n.replace(",", ""))
                    if "European" in desc and not OTHER.search(desc):
                        eur += k
                    elif desc.strip():
                        other += k
                studies[acc] = (eur, other)
            ci = r.get("95% CI (TEXT)") or ""
            try:
                v = float(r.get("OR or BETA") or "")
            except ValueError:
                continue
            if v > 0 and not re.search(r"unit|increase|decrease|z.score|SD|%", ci, re.I):
                ors.append(max(v, 1 / v))
        tot_e = sum(e for e, o in studies.values()); tot = sum(e + o for e, o in studies.values())
        only = sum(1 for e, o in studies.values() if e and not o)
        ors.sort()
        return {"studies": len(studies), "european_only_studies": only, "participants": tot, "european_participants": tot_e,
                "odds_ratios": len(ors), "or_median": round(statistics.median(ors), 3) if ors else None,
                "or_below_1_2": sum(1 for x in ors if x < 1.2), "or_below_1_5": sum(1 for x in ors if x < 1.5),
                "file_date": z.getinfo(z.namelist()[0]).date_time[:3]}
    st = os.stat(path)
    return sources._cached("gwas_limits_v2", f"{st.st_size}|{int(st.st_mtime)}", fetch)


def rows(people):
    return [general(), {"person": None, "kind": "example", "example": json.dumps(example(), ensure_ascii=False),
                        "ethanol": json.dumps(pubchem_ethanol(), ensure_ascii=False),
                        "measured": json.dumps(measured(), ensure_ascii=False),
                        "buildup": json.dumps(buildup(), ensure_ascii=False)},
            {"person": None, "kind": "pairs", "pairs": json.dumps(pairs(), ensure_ascii=False, separators=(",", ":"))},
            {"person": None, "kind": "cluster", "cluster": json.dumps(cluster(people), ensure_ascii=False)},
            {"person": None, "kind": "law", "law": json.dumps(law(), ensure_ascii=False), "limits": json.dumps(gwas_limits())}] + \
        [person(p) for p in people]


if __name__ == "__main__":
    from cluster_analysis import profiles
    print(json.dumps(rows(profiles.load()), indent=1))
