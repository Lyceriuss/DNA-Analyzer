# cluster_analysis/function_evidence.py
"""
Collects measured evidence of how each library SNP changes gene function: direction, size,
mechanism and conditions, from five public sources, and reports coverage.

    python -m cluster_analysis.function_evidence            # all library SNPs
    python -m cluster_analysis.function_evidence rs1801133  # selected SNPs

Evidence tiers (best first):
  1 measured    MaveDB deep mutational scan score for this exact protein change
  1 measured    ClinPGx/PharmGKB clinical annotation (genotype -> drug/metabolism effect, evidence level)
  2 curated     UniProt variant annotation (literature-curated effect or disease)
  3 expression  GTEx eQTL: the allele raises or lowers the gene's expression (NES, per tissue)
  4 predicted   SIFT / PolyPhen damage prediction (whether, not how much or which direction)
  5 unknown

Public identifiers only. Writes cluster_analysis/function_evidence.json and _coverage.md.
"""
import argparse
import csv
import io
import json
import os
import time
from collections import Counter

from cluster_analysis import sources
from cluster_analysis.biomarkers import main_pair
from cluster_analysis.gene_trace import uniprot_entry

HERE = os.path.dirname(__file__)
OUT_JSON = os.path.join(HERE, "function_evidence.json")
OUT_MD = os.path.join(HERE, "function_evidence_coverage.md")
AA3 = {"A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys", "Q": "Gln", "E": "Glu", "G": "Gly", "H": "His", "I": "Ile",
       "L": "Leu", "K": "Lys", "M": "Met", "F": "Phe", "P": "Pro", "S": "Ser", "T": "Thr", "W": "Trp", "Y": "Tyr", "V": "Val", "*": "Ter"}


def _req(method, url, **kw):
    return sources._request(method, url, ok_404=True, **kw)


# --- UniProt variation (EBI Proteins API): protein change, curated effect, predictions ---------

def uniprot_variants(acc):
    return sources._cached("prot_variation", acc, lambda: _req(
        "GET", f"https://www.ebi.ac.uk/proteins/api/variation/{acc}", headers={"Accept": "application/json"}, timeout=120) or {})


def vep_amino_acids(rsids):
    """{rsid: {variant_allele: (ref_aa, alt_aa, position)}} from Ensembl's canonical transcripts."""
    out = {}
    for i in range(0, len(rsids), 150):
        batch = sorted(rsids[i:i + 150])
        rows = sources._cached("vep_canonical", "\n".join(batch), lambda b=batch: sources._request(
            "POST", "https://rest.ensembl.org/vep/human/id", params={"canonical": 1}, json={"ids": b}, timeout=300,
            headers={"Content-Type": "application/json", "Accept": "application/json"}) or [])
        for v in rows:
            for t in v.get("transcript_consequences", []):
                if t.get("canonical") and "/" in (t.get("amino_acids") or ""):
                    ref_aa, alt_aa = t["amino_acids"].split("/")
                    out.setdefault(v["id"], {})[t["variant_allele"]] = (ref_aa, alt_aa, t.get("protein_start"))
    return out


def uniprot_evidence(rsid, acc, alt_aa=None):
    """Protein change, curated effect and predictions. alt_aa keeps only the change the SNP's main
    alternative allele actually makes (UniProt lists every change seen at the position)."""
    feats = [f for f in uniprot_variants(acc).get("features", [])
             if any(x.get("id") == rsid for x in f.get("xrefs", []))]
    if alt_aa:
        feats = [f for f in feats if f.get("alternativeSequence") == alt_aa] or feats
    changes, curated, preds = [], [], []
    for f in feats:
        wt, alt, pos = f.get("wildType"), f.get("alternativeSequence"), f.get("begin")
        if wt and alt and pos and len(wt) == 1 and len(alt) == 1:
            changes.append({"wt": wt, "pos": int(pos), "alt": alt, "hgvs_pro": f"p.{AA3.get(wt, wt)}{pos}{AA3.get(alt, alt)}"})
        curated += [d["value"] for d in f.get("descriptions", []) if d.get("value")]
        curated += [a["name"] for a in f.get("association", []) if a.get("name")]
        preds += [{"tool": p.get("predAlgorithmNameType"), "call": p.get("predictionValType"), "score": p.get("score")}
                  for p in f.get("predictions", []) if p.get("predAlgorithmNameType") in ("SIFT", "PolyPhen")]
    return changes, sorted(set(curated)), preds


# --- MaveDB: measured protein function for the exact change ---------------------------------

def mavedb_sets(gene):
    def fetch():
        r = _req("POST", "https://api.mavedb.org/api/v1/score-sets/search", json={"text": gene}, timeout=90) or {}
        rows = r.get("scoreSets", []) if isinstance(r, dict) else r
        keep = []
        for s in rows:
            targets = [t.get("name", "") for t in s.get("targetGenes", [])]
            if any(gene.upper() == t.upper() or t.upper().startswith(gene.upper() + " ") for t in targets):
                keep.append({"urn": s["urn"], "title": s.get("title", ""), "targets": targets})
        return keep
    return sources._cached("mavedb_sets", gene, fetch)


def mavedb_scores(urn):
    def fetch():
        r = sources.requests.get(f"https://api.mavedb.org/api/v1/score-sets/{urn}/scores", timeout=180)
        if not r.ok:
            return {}
        out = {}
        for row in csv.DictReader(io.StringIO(r.text)):
            if row.get("hgvs_pro") not in (None, "NA") and row.get("score") not in (None, "NA"):
                out[row["hgvs_pro"]] = float(row["score"])
        return out
    return sources._cached("mavedb_scores", urn, fetch)


# --- GTEx: expression effect of the allele, per tissue ---------------------------------------

def gtex_eqtl(vep):
    pair = sorted(main_pair(vep))
    ref = vep["alleles"][0]
    alts = [a for a in pair if a != ref]
    if not alts or len(ref) != 1:
        return None, []
    vid = f"chr{vep['chrom']}_{vep['pos']}_{ref}_{alts[0]}_b38"
    def fetch():
        time.sleep(0.2)
        r = _req("GET", "https://gtexportal.org/api/v2/association/singleTissueEqtl",
                 params={"variantId": vid, "datasetId": "gtex_v8"}, timeout=90) or {}
        return [{"gene": x["geneSymbol"], "tissue": x["tissueSiteDetailId"], "nes": x["nes"], "p": x["pValue"]}
                for x in r.get("data", [])]
    return {"variant_id": vid, "alt": alts[0], "ref": ref}, sources._cached("gtex_eqtl", vid, fetch)


# --- ClinPGx / PharmGKB: clinical annotations per genotype ------------------------------------

def clinpgx(rsid):
    def fetch():
        time.sleep(0.5)  # ClinPGx asks for at most 2 requests per second
        r = _req("GET", "https://api.clinpgx.org/v1/data/clinicalAnnotation",
                 params={"location.fingerprint": rsid, "view": "base"}, timeout=90) or {}
        out = []
        for a in r.get("data", []):
            out.append({"level": (a.get("levelOfEvidence") or {}).get("term"),
                        "chemicals": [c.get("name") for c in a.get("relatedChemicals", [])][:3],
                        "genotypes": [{"genotype": p.get("allele"), "phenotype": p.get("phenotype", "")[:300]}
                                      for p in a.get("allelePhenotypes", [])][:4]})
        return out
    return sources._cached("clinpgx_ca", rsid, fetch)


# --- Per SNP ---------------------------------------------------------------------------------

FUNCTION_WORDS = ("activity", "function", "stabil", "thermolabile", "expression", "binding", "transport", "loss", "gain",
                  "decreas", "increas", "reduc", "impair", "abolish", "efficien")


def collect(rsid, genes, vep, aa=None):
    ev = {"rsid": rsid, "genes": genes, "consequence": (vep or {}).get("consequence"), "sources": {}}
    gene = genes[0] if genes else None
    entry = uniprot_entry(gene) if gene else None
    acc = entry["primaryAccession"] if entry else None

    # The amino acid made by the SNP's main alternative allele (the one people actually carry)
    alt_aa = None
    if vep and aa:
        ref = vep["alleles"][0]
        main_alt = next((a for a in sorted(main_pair(vep)) if a != ref), None)
        hit = (aa.get(rsid) or {}).get(main_alt)
        if hit:
            alt_aa = hit[1]
            ev["protein_change"] = f"p.{AA3.get(hit[0], hit[0])}{hit[2]}{AA3.get(hit[1], hit[1])}"

    changes, curated, preds = uniprot_evidence(rsid, acc, alt_aa) if acc else ([], [], [])
    if changes or curated:
        ev["sources"]["uniprot"] = {"protein_changes": [c["hgvs_pro"] for c in changes], "curated": curated[:8]}
    if preds:
        ev["sources"]["predicted"] = preds

    mave = []
    if changes and gene:
        for s in mavedb_sets(gene):
            scores = mavedb_scores(s["urn"])
            for c in changes:
                if c["hgvs_pro"] in scores:
                    mave.append({"set": s["urn"], "conditions": s["title"], "change": c["hgvs_pro"], "score": scores[c["hgvs_pro"]]})
    if mave:
        ev["sources"]["mavedb"] = mave

    if vep:
        vid, rows = gtex_eqtl(vep)
        own = [r for r in rows if r["gene"] in genes]
        if rows:
            best = sorted(own or rows, key=lambda r: r["p"])[:5]
            ev["sources"]["gtex"] = {"variant_id": vid["variant_id"], "effect_allele": vid["alt"],
                                     "own_gene": bool(own), "n_tissues": len(rows),
                                     "other_genes": sorted({r["gene"] for r in rows} - set(genes))[:6], "top": best}

    pgx = clinpgx(rsid)
    if pgx:
        ev["sources"]["clinpgx"] = pgx[:5]

    s = ev["sources"]
    functional_text = [c for c in s.get("uniprot", {}).get("curated", []) if any(w in c.lower() for w in FUNCTION_WORDS)]
    if functional_text:
        s["uniprot"]["functional"] = functional_text
    # Tier = the best evidence about the gene's FUNCTION. Drug associations (ClinPGx) are reported
    # alongside but are not a measure of how much the gene works.
    ev["tier"] = (1 if "mavedb" in s else 2 if functional_text else 3 if "gtex" in s and s["gtex"]["own_gene"]
                  else 4 if "predicted" in s else 5)
    return ev


TIER_NAMES = {1: "measured protein function (MaveDB)", 2: "curated functional effect (UniProt)",
              3: "expression effect on the gene (GTEx)", 4: "predicted damage only (SIFT/PolyPhen)", 5: "no functional evidence"}


def coverage_md(results):
    n = len(results)
    has = lambda k: sum(1 for r in results if k in r["sources"])
    tiers = Counter(r["tier"] for r in results)
    lines = ["# Function evidence coverage", "",
             f"{n} library SNPs checked against MaveDB, ClinPGx, UniProt, GTEx and SIFT/PolyPhen.", "",
             "| Source | SNPs with data | Share | What it tells us |", "|---|---|---|---|",
             f"| MaveDB | {has('mavedb')} | {has('mavedb') / n:.0%} | Measured protein function for this exact change |",
             f"| ClinPGx | {has('clinpgx')} | {has('clinpgx') / n:.0%} | Genotype → drug or metabolism effect, with evidence level |",
             f"| UniProt | {has('uniprot')} | {has('uniprot') / n:.0%} | Protein change and curated effect or disease |",
             f"| GTEx | {has('gtex')} | {has('gtex') / n:.0%} | Expression up or down, per tissue "
             f"({sum(1 for r in results if 'gtex' in r['sources'] and r['sources']['gtex']['own_gene'])} for the library gene itself) |",
             f"| SIFT/PolyPhen | {has('predicted')} | {has('predicted') / n:.0%} | Predicted damage only |", "",
             "## Best evidence about function, per SNP", "",
             "Drug associations (ClinPGx) are not counted here: they say a genotype changes a drug's effect, "
             "not how much the gene works.", "", "| Tier | SNPs |", "|---|---|"]
    lines += [f"| {t} {TIER_NAMES[t]} | {tiers.get(t, 0)} |" for t in sorted(TIER_NAMES)]
    lines += ["", f"{sum(1 for r in results if 'clinpgx' in r['sources'] and r['tier'] >= 3)} SNPs without curated or "
              "measured function do have a ClinPGx drug association."]
    lines += ["", "## Examples of measured evidence", ""]
    for r in [r for r in results if "mavedb" in r["sources"]][:8]:
        m = r["sources"]["mavedb"]
        lines.append(f"- **{r['rsid']} {'/'.join(r['genes'])}** {m[0]['change']}: " +
                     "; ".join(f"{x['score']:.2f} ({x['conditions'][:60]})" for x in m[:6]))
    lines += ["", "## Examples of curated functional effects", ""]
    for r in [r for r in results if r["tier"] == 2][:10]:
        lines.append(f"- **{r['rsid']} {'/'.join(r['genes'])}** {r.get('protein_change', '')}: "
                     + "; ".join(r["sources"]["uniprot"]["functional"][:3]))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rsids", nargs="*")
    args = ap.parse_args()
    lib = json.load(open(os.path.join(HERE, "modules.json"), encoding="utf-8"))
    rsids = args.rsids or sorted(lib["rsids"])
    vep = sources.ensembl_vep(sorted(lib["rsids"]))
    aa = vep_amino_acids(sorted(lib["rsids"]))
    results = []
    for i, r in enumerate(rsids, 1):
        try:
            results.append(collect(r, lib["rsids"][r]["genes"], vep.get(r), aa))
        except Exception as e:  # one SNP's API failure should not stop the run
            results.append({"rsid": r, "genes": lib["rsids"][r]["genes"], "sources": {}, "tier": 5,
                            "error": f"{type(e).__name__}: {str(e)[:160]}"})
        if i % 20 == 0:
            print(f"  {i}/{len(rsids)}", flush=True)
    if not args.rsids:
        json.dump(results, open(OUT_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        open(OUT_MD, "w", encoding="utf-8").write(coverage_md(results))
        print(coverage_md(results))
    else:
        print(json.dumps(results, indent=1, ensure_ascii=False)[:6000])
