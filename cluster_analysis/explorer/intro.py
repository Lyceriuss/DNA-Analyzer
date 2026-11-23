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
    # Lite mode (genome/lite.py): measured calls only, no imputation summary
    lite = _load(os.path.join(folder, "lite.json")) if not s else None
    if lite:
        s = {"totals": {"calls": lite.get("calls")}, "not_lifted": lite.get("not_lifted")}
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
            # the person's own calls at every example gene's variants ("Reading a cluster" reads the one for their sex)
            "example_gt": json.dumps(genotypes_at(p["dna"], [r for c in CLUSTER.values() for r in c["variants"]])),
            "lite": bool(lite)}


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


# "Reading a cluster" (Home, step 5): what a cluster gene's call means for the person, told for one example gene per
# fertility theme: the slide picks the one of the selected person's theme (their sex) and reads it from their own rows.
# As for the alcohol example, the choices here are the gene, its partners, the variants to look up, the tissues, the
# studies and the regex anchors that find each number in the study's own text; every number and sentence is read from
# GTEx, UniProt, Reactome, Europe PMC and the GWAS Catalog, and an item whose anchor doesn't match is left out.
CLUSTER = {
    "ESR1": {
        "theme": "fertility_female", "people": "women",
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
            {"id": "meta", "kind": "quote", "pmid": "31821471", "rsid": "rs2234693", "name": "PvuII", "measure": "Endometriosis, meta-analysis",
             "sentence": r"(\d+) showed a significant trend towards the lack of an association: [^;]*?estrogen receptor 1 \(ESR1\) rs2234693"},
        ],
        # GWAS Catalog associations of the person's alleles, per copy (trait, first author, the allele the effect is for)
        "gwas": [("rs851982", "Female infertility (idiopathic, defined by coding in electronic health record)", "Venkatesh SS"),
                 ("rs2234693", "Heel bone mineral density", "Morris JA")],
    },
    # FSHB, the FSH beta chain: its promoter variant -211G>T (rs10835638), and the GWAS signal near it in men (rs11031006)
    "FSHB": {
        "theme": "fertility_male", "people": "men",
        "acc": "P01225", "reactome": "R-HSA-375281", "reactome_sentences": [1, 3],
        "partners": {"FSHR": "P23945", "LHCGR": "P22888", "GNRHR": "P30968", "GNRH1": "P01148", "LHB": "P01229"},
        # The path in men, brain to testes: which genes in which order (curated); each label is kept only when its UniProt
        # text holds the backing words (check), and that sentence is shown with it. "measures" are the Grigorova table
        # rows measured along the branch, by FSHB genotype
        "path": [
            [{"gene": "GNRH1", "acc": "P01148", "label": "Brain: GnRH", "check": r"hypothalamic"},
             {"gene": "GNRHR", "acc": "P30968", "check_acc": "P01148", "check_gene": "GNRH1", "label": "Pituitary: GnRH receptor",
              "check": r"pituitary gonadotrope cells"},
             {"gene": "FSHB", "acc": "P01225", "check_acc": "P30968", "check_gene": "GNRHR", "label": "FSH",
              "check": r"follicle-stimulating hormone \(FSH\)"},
             {"gene": "FSHR", "acc": "P23945", "label": "FSH receptor on the Sertoli cells", "check": r"Sertoli"},
             {"gene": None, "acc": "P01225", "check_gene": "FSHB", "label": "Sperm production", "check": r"spermatogenesis",
              "measures": ["FSH", "Inhibin-B", "Total testes volume", "Sperm concentration", "Total sperm count per ejaculate"]}],
            [{"gene": "LHB", "acc": "P01229", "label": "LH", "check": r"luteinizing hormone"},
             {"gene": "LHCGR", "acc": "P22888", "check_acc": "P01229", "check_gene": "LHB", "label": "LH receptor on the Leydig cells",
              "check": r"Leydig"},
             {"gene": None, "acc": "P01229", "check_gene": "LHB", "label": "Testosterone", "check": r"testosterone",
              "measures": ["Total testosterone", "LH"]}],
        ],
        "variants": ["rs10835638", "rs11031006"],
        "tissues": ["Pituitary", "Testis", "Prostate"],
        # Controlled studies in men by -211G>T genotype; what they found is read from their text
        "studies": [
            {"id": "baltic", "kind": "table", "pmid": "21733993", "pmcid": "PMC3298437", "rsid": "rs10835638", "name": "-211G>T",
             "measure": "Reproductive measures in young men, adjusted medians",
             "table": r"Table 2\. Male reproductive parameters in the Baltic young men cohort stratified by the FSHB rs10835638",
             "labels": ["TT", "GT", "GG"], "order": [2, 1, 0], "count": r"No\. of men (\d+) (\d+) (\d+)",
             "rows": ["FSH", "Inhibin-B", "Total testes volume", "Total testosterone", "LH", "Sperm concentration", "Total sperm count per ejaculate"],
             "answer": ["FSH", "Total testes volume"],
             "sentence": r"Serum hormones directly correlated with the T-allele dosage of rs10835638 included FSH .*?nmol/liter\)\.",
             "n": r"n = \d+; GG carriers, n = (\d+); GT carriers, n = (\d+); TT carriers, n = (\d+)"},
            {"id": "danish", "kind": "quote", "pmid": "33236519", "rsid": "rs10835638", "name": "-211G>T",
             "measure": "Testis size and function in men from the general population",
             "sentence": r"The studied polymorphisms have only minor modulating influence on testis size and function in healthy men\.",
             "n": r"A cross-sectional study of (\d+) Danish men"},
            {"id": "sicily", "kind": "quote", "pmid": "28281143", "rsid": "rs10835638", "name": "-211G>T",
             "measure": "Hormones in men with normal or abnormal semen",
             "sentence": r"Decreasing serum levels of FSH and LH were observed across the three FSHB -211 genotype subgroups \(p < [\d.]+ and p < [\d.]+, respectively\)\.",
             "n": r"(\d+) men with abnormal conventional sperm parameters or normozoospermia"},
            {"id": "casecontrol", "kind": "quote", "pmid": "28764642", "rsid": "rs10835638", "name": "-211G>T",
             "measure": "Infertile against fertile men",
             "sentence": r"In the FSHB or FSHR gene single nucleotide polymorphism \(SNP\) evaluation, no statistically-significant difference was found in the frequency of allelic variants or in genotype distribution between cases and controls\.",
             "n": r"case-control study of (\d+) infertile men and (\d+) fertile controls"},
        ],
        "gwas": [("rs10835638", "Follicle stimulating hormone levels in idiopathic male infertility", "Schubert M"),
                 ("rs11031006", "Follicle stimulating hormone levels", "Venkatesh SS")],
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
    import requests
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
        rows, untested = [], []
        for t in sorted(set(tissues) | sig):
            # GTEx tests a variant only in tissues that make enough of the gene; elsewhere it answers 400
            try:
                d = _gtex("association/dyneqtl", {"gencodeId": g, "variantId": v, "tissueSiteDetailId": t, "datasetId": "gtex_v8"})
            except requests.HTTPError:
                untested.append({"tissue": t, "tpm": tpm.get(t)})
                continue
            rows.append({"tissue": t, "nes": d.get("nes"), "p": d.get("pValue"), "significant": t in sig, "tpm": tpm.get(t), "n": size.get(t)})
        _, _, ref, alt, _ = v.split("_")
        return {"variant": v, "ref": ref, "alt": alt, "rows": rows, "untested": untested, "top_tpm": sorted(tpm.items(), key=lambda x: -x[1])[:5]}
    return sources._cached("gtex_tissues", f"{gene}|{rsid}|{','.join(sorted(tissues))}", fetch)


def _study(st):
    a = europepmc_abstract_raw(st["pmid"]) or {}
    t = (europepmc_fulltext(st["pmcid"]) or {}).get("text", "") if st.get("pmcid") else ""
    out = {k: st[k] for k in ("id", "kind", "pmid", "rsid", "name", "measure") if k in st}
    out.update(study=f"{(a.get('authors') or '').split(',')[0].strip()} {a.get('year')}", title=a.get("title"))
    hit = re.search(st["sentence"], a.get("abstract", "")) or re.search(st["sentence"], t)
    out["finding"] = hit.group(0) if hit else None
    if st.get("n"):
        m = re.search(st["n"], a.get("abstract", "")) or re.search(st["n"], t)
        out["n"] = sum(int(x) for x in m.groups()) if m else None
        out["n_groups"] = [int(x) for x in m.groups()] if m else None
    if st.get("kind") == "table":
        # A table of measures by genotype: each row's adjusted median per genotype group, with the additive and the
        # recessive model's P, read from the paper's own table (its columns as the labels say)
        m = re.search(st["table"], t)
        seg = t[m.start():m.start() + 12000] if m else ""
        cnt = re.search(st["count"], seg)
        num = r"(−?[\d.]+)"
        pval = r"([\d.]+) × 10 −(\d+)"
        rows = []
        for name in st["rows"]:
            r = re.search(r"(?<![/\w])" + re.escape(name) + r" \(([^)]+)\) (?:[a-d] )?Mean \( sd \) .*?Adjusted median \(95% CI\) "
                          + r" ".join([num + r" \([^)]*\)"] * 3) + " " + pval + " " + num + " " + pval + " " + num, seg)
            if not r:
                continue
            g = r.groups()
            vals = [float(g[1 + i]) for i in st["order"]]
            rows.append({"measure": name, "unit": g[0], "values": vals, "answer": name in st.get("answer", []),
                         "p_additive": float(f"{g[4]}e-{g[5]}"), "p_recessive": float(f"{g[7]}e-{g[8]}")})
        if not rows:
            return None
        out.update(labels=[st["labels"][i] for i in st["order"]], rows=rows,
                   group_n=[int(cnt.group(1 + i)) for i in st["order"]] if cnt else None)
    elif st["id"] == "dose":
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


# The slide reads the selected person's own genotypes at the example gene (their example_gt) and their own theme rows;
# these sit only in the datasets on their machine. A person without the theme (an older export) gets the example drawn
# from the theme graph with the most common European genotype at each variant (1000 Genomes via Ensembl).
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


def cluster_example(gene):
    """The last-resort example for the gene's theme, the same for everyone: the network from the theme graph that ships
    with the app (the gene, its curated partners and its most confident STRING partners) and the most common European
    genotypes at its variants. The slide uses it only for a person whose own rows lack the theme."""
    from cluster_analysis import profiles as prof
    c = CLUSTER[gene]
    graph = next((x for x in prof.theme_graphs() if x["theme"] == c["theme"]), None)
    if not graph:
        return None
    facets = {m["id"]: m["name"] for m in graph["mechanisms"]}
    facets.setdefault("disease", graph.get("disease_name") or "Disease link, mechanism not yet known")
    out = {"gene": gene, "theme": c["theme"], "theme_name": graph["name"], "facets": facets}
    # The cycle phases' chains (fertility_deep, the same for everyone): where the gene sits in the cycle
    ph = (_load(os.path.join(ROOT, gbuild.EXPLORER, "datasets", "fd_phases.json")) or []) if c["theme"] == "fertility_female" else []
    first = next((r["person"] for r in ph if r.get("person")), None)
    out["phases"] = [{k: r[k] for k in ("phase", "name", "chains")} for r in ph if r.get("person") == first]
    glinks = graph.get("links") or []
    top = sorted((l for l in glinks if gene in (l["a"], l["b"])), key=lambda l: -l["score"])
    names = list(dict.fromkeys([gene] + [p for p in c["partners"] if p in graph["genes"]]
                               + [l["b"] if l["a"] == gene else l["a"] for l in top]))[:10]
    out["genes"] = [{"gene": n, "primary": graph["genes"].get(n, {}).get("primary") or "disease", "notable": True} for n in names]
    keep = set(names)
    out["links"] = [{"a": l["a"], "b": l["b"], "score": l["score"]} for l in glinks if l["a"] in keep and l["b"] in keep]
    gts = {r: eur_common(r) for r in c["variants"]}
    out["genotypes"] = {r: g for r, (g, _) in gts.items() if g}
    out["frequency"] = {r: f for r, (_, f) in gts.items() if f}
    out["source"] = "1000 Genomes Europeans"
    return out


# UniProt's function texts speak of both sexes in one entry. For a man's or a woman's example, the sentences about the
# other sex are left out and those about their own come first; a sentence naming both ("In males, ...; while in females,
# ...") is cut at the clause, marked with an ellipsis. "Follicle-stimulating hormone" is a hormone's name, not a female word.
SEX_WORDS = {
    "male": re.compile(r"\b(males?|men|testi(?:s|cular|es)|Sertoli|Leydig|spermat\w*|sperm|testosterone|androgens?)\b", re.I),
    "female": re.compile(r"\b(females?|women|ovar\w*|granulosa|oocytes?|ovulat\w*|uter\w*|estrous|menstrual|luteal|corpus luteum"
                         r"|pregnan\w*|follicular|follicles?(?!-stimulating))\b", re.I),
}


def uniprot_sentences(acc, kinds=("FUNCTION",)):
    """The entry's sentences, each text closed with a period so one text never runs into the next. A tissue list
    (TISSUE SPECIFICITY) comes as one sentence prefixed "Tissue: "."""
    e = uniprot_full(acc) or {}
    out = []
    for cm in e.get("comments", []):
        if cm.get("commentType") not in kinds:
            continue
        for x in cm.get("texts", []):
            t = re.sub(r"\s*\((?:PubMed:\d+[,; ]*)+\)", "", x["value"]).strip()
            if not t:
                continue
            if cm["commentType"] == "TISSUE SPECIFICITY":
                out.append("Tissue: " + t.rstrip("."))
                continue
            t = t if t.endswith(".") else t + "."
            out += [s.strip() for s in re.split(r"(?<=\.)\s+(?=[A-Z])", t) if s.strip()]
    return out


def tissues_for(sentence, sex):
    """A "Tissue: a, b and c" line cut to the items that aren't the other sex's, marked with an ellipsis when cut."""
    other = "female" if sex == "male" else "male"
    items = [i.strip() for i in re.split(r",\s*|\s+and\s+", sentence[len("Tissue: "):]) if i.strip()]
    keep = [i for i in items if not SEX_WORDS[other].search(i)]
    return "Tissue: " + ", ".join(keep) + (" …" if len(keep) < len(items) else "")


def for_sex(sentences, sex, n=2):
    """Up to n sentences for one sex: its own first, then the neutral ones among the entry's opening sentences (its core
    function); never the other sex's."""
    other = "female" if sex == "male" else "male"
    own, neutral = [], []
    for i, s in enumerate(sentences):
        mine, theirs = SEX_WORDS[sex].search(s), SEX_WORDS[other].search(s)
        if mine and theirs:
            # one clause per sex, joined by "; while in ..." or "; in ...": keep this sex's clause
            parts = [p.strip() for p in re.split(r";\s*(?:while\s+)?(?=in\s+(?:fe)?males\b)", s, flags=re.I)]
            keep = [p for p in parts if SEX_WORDS[sex].search(p) and not SEX_WORDS[other].search(p)]
            if keep:
                c = keep[0].rstrip(".")
                own.append(c + (" …" if c != s.rstrip(".") else "."))
        elif mine:
            own.append(s)
        elif not theirs and i < 2:
            neutral.append(s)
    return " ".join((own + neutral)[:n])


def male_path(spec):
    """The example's path in men (curated: which genes, in which order), each label kept only when its gene's UniProt
    text holds the words that back it; the backing sentence goes with it, verbatim."""
    out = []
    for branch in spec:
        nodes = []
        for node in branch:
            gene, acc, label, check = node["gene"], node["acc"], node["label"], node["check"]
            src_acc = node.get("check_acc", acc)
            sents = uniprot_sentences(src_acc, ("FUNCTION", "TISSUE SPECIFICITY"))
            hit = next((s for s in sents if re.search(check, s, re.I)), None)
            if not hit:
                continue   # no source for the label: left out
            clause = tissues_for(hit, "male") if hit.startswith("Tissue: ") else (for_sex([hit], "male", 1) or hit)
            nodes.append({"gene": gene, "label": label, "source": clause, "source_gene": node.get("check_gene", gene),
                          "measures": node.get("measures", [])})
        out.append(nodes)
    return out


def cluster(people=()):
    """Per example gene: its facts (UniProt, Reactome, GTEx, studies, GWAS) and, under _examples by theme, the fallback
    example. The person's side (their theme rows and example_gt) is read by the slide from their own datasets."""
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
        s0, s1 = c.get("reactome_sentences", [0, 1])
        out[gene] = {"theme": c["theme"], "people": c["people"], "variants": c["variants"],
                     "function": fn(c["acc"]), "partners": {g: fn(a) for g, a in c["partners"].items()},
                     "partners_sex": {sex: {g: for_sex(uniprot_sentences(a), sex) or fn(a) for g, a in c["partners"].items()}
                                      for sex in ("male", "female")},
                     "path": male_path(c["path"]) if c.get("path") else None,
                     "reactome": {"id": c["reactome"], "summary": " ".join(re.split(r"(?<=\.)\s+", reactome_summary(c["reactome"]))[s0:s1])},
                     "gtex": {r: gtex_tissues(gene, r, c["tissues"]) for r in c["variants"]},
                     "studies": [x for x in (_study(st) for st in c["studies"]) if x], "gwas": gw}
    out["_examples"] = {c["theme"]: cluster_example(gene) for gene, c in CLUSTER.items()}
    return out


# The last step of the introduction: the EU rules around working with one's own DNA. The choice here is the acts, the
# articles and the regex anchors; every quoted sentence is read from the official text at export (EUR-Lex, or the EU
# Publications Office's Cellar when EUR-Lex answers with a bot check), cached. An item is a reference and one or more
# anchors (several are joined with " … "); one whose text can't be fetched or matched is left out.
LAW = [
    {"id": "gdpr", "act": "General Data Protection Regulation (EU) 2016/679", "short": "GDPR", "celex": "32016R0679",
     "items": [("Art. 4(13)", r"‘genetic data’ means[^;]*;"),
               ("Art. 9(1)", r"Processing of personal data revealing racial[^.]*\."),
               ("Art. 9(2)(a)", r"\(a\) the data subject has given explicit consent[^;]*;"),
               ("Art. 2(2)(c)", (r"This Regulation does not apply to the processing of personal data: \(a\)", r"\(c\) by a natural person in the course of a purely personal or household activity;")),
               ("Art. 5(1)(c)", r"adequate, relevant and limited to what is necessary in relation to the purposes for which they are processed \(‘data minimisation’\);"),
               ("Art. 17(1)", r"The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay[^:]*:")]},
    {"id": "ivdr", "act": "In Vitro Diagnostic Medical Device Regulation (EU) 2017/746", "short": "IVDR", "celex": "32017R0746",
     "items": [("Art. 2(2)", r"‘ ?in vitro diagnostic medical device’ means any medical device which is.*?\(f\) to define or monitoring therapeutic measures\."),
               ("Art. 2(12)", r"‘intended purpose’ means[^;]*;"),
               ("Annex VIII, Rule 3", (r"Devices are classified as class C if they are intended:", r"\(f\) to be used as companion diagnostics;", r"\(i\) for human genetic testing;")),
               ("Art. 5(1)", r"A device may be placed on the market or put into service only if it complies with this Regulation[^.]*\."),
               ("Art. 6(1)", r"A device offered by means of information society services[^.]*?shall comply with this Regulation\."),
               ("Art. 7", r"In the labelling, instructions for use, making available, putting into service and advertising of devices, it shall be prohibited[^:]*: \(a\)[^;]*; \(b\)[^;]*;"),
               ("Art. 4(1)", r"Member States shall ensure that where a genetic test is used on individuals.*?as appropriate\.")]},
]


def law_text(item):
    """The act's text as plain words, fetched once and cached (public pages; no personal data is sent)."""
    from cluster_analysis import sources
    url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{item['celex']}"
    def fetch():
        import requests
        for u, h in ((url, {"Accept": "text/html"}),
                     (f"http://publications.europa.eu/resource/celex/{item['celex']}", {"Accept": "application/xhtml+xml", "Accept-Language": "eng"})):
            r = requests.get(u, timeout=90, headers={"User-Agent": "Mozilla/5.0 (DNA-Analyzer; research)", **h})
            if r.status_code == 200 and len(r.text) > 50000:   # EUR-Lex's bot check is a short 202 page
                t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text)).replace("&nbsp;", " ").replace("&#160;", " ")
                return {"text": t}
        raise RuntimeError(f"{item['short']}: no text")
    try:
        return (sources._cached("law_text", url, fetch) or {}).get("text", "")
    except Exception:
        return ""


def law():
    out = []
    for a in LAW:
        t = re.sub(r"\( \d+ \) ?", "", law_text(a))   # footnote marks are spaced, "( 23 )"; "Article 1(1)" is not
        quotes = []
        for ref, rx in a["items"]:
            parts = [re.search(x, t) for x in ((rx,) if isinstance(rx, str) else rx)]
            if all(parts):
                text = " … ".join(m.group(0) for m in parts)
                quotes.append({"ref": ref, "text": re.sub(r"\s+([,;:.)])", r"\1", text).replace("‘ ", "‘").replace("( ", "(").strip()})
        if quotes:
            out.append({k: a[k] for k in ("id", "act", "short")} |
                       {"url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{a['celex']}", "quotes": quotes})
    return out


def rows(people):
    return [general(), {"person": None, "kind": "example", "example": json.dumps(example(), ensure_ascii=False),
                        "ethanol": json.dumps(pubchem_ethanol(), ensure_ascii=False),
                        "measured": json.dumps(measured(), ensure_ascii=False),
                        "buildup": json.dumps(buildup(), ensure_ascii=False)},
            {"person": None, "kind": "pairs", "pairs": json.dumps(pairs(), ensure_ascii=False, separators=(",", ":"))},
            {"person": None, "kind": "cluster", "cluster": json.dumps(cluster(people), ensure_ascii=False)},
            {"person": None, "kind": "law", "law": json.dumps(law(), ensure_ascii=False)}] + \
        [person(p) for p in people]


if __name__ == "__main__":
    from cluster_analysis import profiles
    print(json.dumps(rows(profiles.load()), indent=1))
