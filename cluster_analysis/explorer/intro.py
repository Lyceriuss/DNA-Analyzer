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
            "validation": {"hidden": cal.get("hidden"), "confident": n, "right": round(right / n, 4) if n else None}}


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


def rows(people):
    return [general(), {"person": None, "kind": "example", "example": json.dumps(example(), ensure_ascii=False),
                        "ethanol": json.dumps(pubchem_ethanol(), ensure_ascii=False),
                        "measured": json.dumps(measured(), ensure_ascii=False),
                        "buildup": json.dumps(buildup(), ensure_ascii=False)}] + [person(p) for p in people]


if __name__ == "__main__":
    from cluster_analysis import profiles
    print(json.dumps(rows(profiles.load()), indent=1))
