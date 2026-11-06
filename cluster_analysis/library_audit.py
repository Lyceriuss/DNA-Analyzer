# cluster_analysis/library_audit.py
"""
Checks every SNP in the library (config/snp_traits.json, written with an LLM) against evidence:

  * function: what the library's wording claims for the less common genotype (more / less active), against the
    evidence call (evidence_call.py: CPIC, MaveDB, UniProt, a truncating change, SIFT/PolyPhen, GTEx);
  * trait: whether the GWAS Catalog has any genome-wide significant association for the SNP at all;
  * scoring: whether the genotype most Europeans carry is scored as a risk (4 or lower), which an LLM easily does
    and which makes a common, ordinary genotype look like a problem.

    python -m cluster_analysis.library_audit

Writes docs/LIBRARY_AUDIT.md (for review, one row per SNP with the verdict and a suggested action) and
cluster_analysis/library_audit.json. Library and public reference data only: no one's genotypes.
Nothing in the library is changed here; corrections are made after review.
"""
import csv
import io
import json
import os
import re
import zipfile
from collections import Counter, defaultdict

from cluster_analysis import sources
from cluster_analysis.evidence_call import BASIS_TEXT, evidence_call, load_evidence
from cluster_analysis.gene_trace import NORMAL_WORDS, direction

TRAITS_PATH = "config/snp_traits.json"
GWAS_ZIP = "data/reference/gwas_associations_ontology.zip"
OUT_MD = "docs/LIBRARY_AUDIT.md"
OUT_JSON = os.path.join(os.path.dirname(__file__), "library_audit.json")
COMPLEMENT = str.maketrans("ACGT", "TGCA")
SEVERITY = {"contradicts": 0, "unsupported": 1, "common genotype scored as risk": 2, "function claim unsupported": 3,
            "agrees": 4, "no function claim": 5}


def gwas_hits(rsids):
    """{rsid: [(p, trait)]} for genome-wide significant GWAS Catalog associations, strongest first."""
    out = defaultdict(dict)
    with zipfile.ZipFile(GWAS_ZIP) as z:
        name = next(n for n in z.namelist() if n.endswith((".tsv", ".txt")))
        for row in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace"), delimiter="\t"):
            hits = [rs for rs in re.findall(r"rs\d+", row.get("SNPS", "")) if rs in rsids]
            if not hits:
                continue
            try:
                p = float(row.get("P-VALUE") or 1)
            except ValueError:
                continue
            if p > 5e-8:
                continue
            trait = row.get("MAPPED_TRAIT") or row.get("DISEASE/TRAIT") or ""
            for rs in hits:
                out[rs][trait] = min(p, out[rs].get(trait, 1))
    return {rs: sorted(((p, t) for t, p in d.items()), key=lambda x: x[0]) for rs, d in out.items()}


def oriented(text_by_gt, alleles):
    """Library genotype keys turned onto the VEP (forward) strand and sorted."""
    out = {}
    for k, v in text_by_gt.items():
        g = k if set(k) <= set(alleles) else k.translate(COMPLEMENT)
        out["".join(sorted(g))] = v
    return out


def audit():
    traits = json.load(open(TRAITS_PATH, encoding="utf-8"))
    rsids = sorted(rs for rs in traits if rs.startswith("rs"))
    vep = sources.ensembl_vep(rsids)
    evidence = load_evidence()
    # The GWAS Catalog lists each study's lead SNP; a library SNP inherited with a lead SNP is supported through it
    # (TCF7L2 rs12255372 through rs7903146)
    direct = gwas_hits(set(rsids))
    partners = {rs: sources.ensembl_ld(rs) for rs in rsids if rs not in direct}
    proxy = gwas_hits({p for ps in partners.values() for p in ps})
    gwas, via = dict(direct), {}
    for rs, ps in partners.items():
        # Every partner's associations, strongest p per trait; "via" names the partner behind the strongest one
        best = {}
        for partner in (p for p in ps if p in proxy):
            for pval, trait in proxy[partner]:
                if trait not in best or pval < best[trait][0]:
                    best[trait] = (pval, partner)
        if best:
            gwas[rs] = sorted((pval, trait) for trait, (pval, _) in best.items())
            lead = min(best.values())[1]
            via[rs] = (lead, ps[lead])
    rows = []
    for rs in rsids:
        t = traits[rs]
        v = vep.get(rs)
        row = {"rsid": rs, "gene": t.get("gene"), "trait": t.get("trait"), "scores": t.get("scores", {}),
               "gwas": [{"trait": tr, "p": p} for p, tr in gwas.get(rs, [])[:4]], "n_gwas": len(gwas.get(rs, [])),
               "gwas_via": {"rsid": via[rs][0], "r2": round(via[rs][1], 2)} if rs in via else None}
        if not v:
            row.update(verdict="unsupported", action="Ensembl doesn't know this rsID: check the ID.", flags=["unknown rsID"])
            rows.append(row)
            continue
        af = dict(v.get("eur_af") or {})
        alleles = v["alleles"]
        af.setdefault(alleles[0], max(0.0, 1 - sum(f for a, f in af.items() if a != alleles[0])))
        common = max(alleles, key=lambda a: af.get(a, 0))
        minor = max((a for a in alleles if a != common and len(a) == 1), key=lambda a: af.get(a, 0), default=None)
        texts = oriented(t.get("variants", {}), alleles)
        scores = oriented(t.get("scores", {}), alleles)
        hom_common, hom_minor = common * 2, (minor or "") * 2
        lib_text = texts.get("".join(sorted(hom_minor)), "")
        claim = direction(lib_text)
        lib_claim = "GoF" if claim and claim > 0 else "LoF" if claim and claim < 0 else \
            "normal" if re.search(NORMAL_WORDS, lib_text, re.I) else None
        ev = evidence_call(rs, hom_minor, evidence.get(rs), v) if minor else {"function": "unknown", "basis": "none", "detail": None}
        # The evidence call for the minor homozygote, as a direction of the minor allele
        ev_dir = ev["function"] if ev["function"] in ("GoF", "LoF", "altered") else "normal" if ev["function"] == "normal" else None
        p_common = af.get(common, 0)
        flags = []
        common_score = scores.get(hom_common)
        if common_score is not None and common_score <= 4 and p_common ** 2 >= 0.25:
            flags.append(f"{hom_common} ({p_common ** 2:.0%} of Europeans) scored {common_score:g}")
        extreme = any(s <= 3 or s >= 8 for s in scores.values())

        if lib_claim in ("GoF", "LoF") and ev_dir in ("GoF", "LoF") and lib_claim != ev_dir:
            verdict = "contradicts"
            action = (f"The wording makes {hom_minor} {'more' if lib_claim == 'GoF' else 'less'} active; the evidence says "
                      f"{'more' if ev_dir == 'GoF' else 'less'}"
                      f"{' (expression only: a protein change can still win)' if ev['basis'] == 'expression' else ''}. Rewrite the genotype texts.")
        elif lib_claim in ("GoF", "LoF") and ev_dir == "normal" and ev["basis"] in ("cpic", "measured"):
            verdict = "contradicts"
            action = f"The wording claims an effect; {BASIS_TEXT[ev['basis']]} finds typical function. Rewrite as typical."
        elif ev["basis"] == "none" and not row["n_gwas"] and (claim or extreme):
            verdict = "unsupported"
            action = ("No functional evidence and no genome-wide GWAS hit. Scores are neutral (5); the wording still claims an effect."
                      if set(scores.values()) == {5} else
                      "No functional evidence and no genome-wide GWAS hit: neutralise the scores (5) or drop the SNP.")
        elif flags:
            verdict = "common genotype scored as risk"
            action = "Most people carry this genotype: score it 5 unless a study shows harm against the other genotypes."
        elif claim and ev["basis"] == "none":
            verdict = "function claim unsupported"
            action = "Keep the trait wording (GWAS supports the SNP), drop words about activity."
        elif claim:
            verdict = "agrees"
            action = ""
        else:
            verdict = "no function claim"
            action = ""
        if flags and verdict != "common genotype scored as risk":
            action += " Also: the common genotype is scored as a risk."
        row.update(common=common, minor=minor, minor_af=round(af.get(minor, 0), 3) if minor else None,
                   consequence=v.get("consequence"), library_text=lib_text, library_claim=lib_claim,
                   evidence_function=ev["function"], evidence_basis=ev["basis"], evidence=ev["detail"],
                   flags=flags, verdict=verdict, action=action.strip())
        rows.append(row)
    rows.sort(key=lambda r: (SEVERITY[r["verdict"]], r["gene"] or "", r["rsid"]))
    return rows


def write(rows):
    json.dump(rows, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    c = Counter(r["verdict"] for r in rows)
    word = {"GoF": "more active", "LoF": "less active", "normal": "typical", "altered": "changed", "unknown": "no known effect", None: "-"}
    lines = ["# Library audit", "",
             f"Every SNP in `config/snp_traits.json` ({len(rows)}) checked against evidence by `cluster_analysis/library_audit.py`. "
             "The library was written with an LLM; this lists where its wording and scores go beyond, or against, the evidence. "
             "Corrections already made are listed in [LIBRARY_CHANGES.md](LIBRARY_CHANGES.md); what remains here is for review "
             "(expression-only contradictions were kept, since a study of the protein can outweigh GTEx).", "",
             "- **Function**: what the library's text says the less common genotype does, against the evidence call "
             "(CPIC, MaveDB, UniProt, a change that cuts the protein short, SIFT/PolyPhen, GTEx expression).",
             "- **GWAS**: genome-wide significant (p ≤ 5e-8) associations for the SNP in the GWAS Catalog, any trait. The Catalog "
             "lists each study's lead SNP, so a SNP without its own entry is counted through a lead SNP inherited with it "
             "(r² ≥ 0.6 in Europeans, Ensembl).",
             "- **Common risk**: the genotype most Europeans carry scored 4 or lower (a risk in the PDF report).", "",
             "| Verdict | SNPs |", "|---|---|"]
    lines += [f"| {v} | {c[v]} |" for v in SEVERITY if c[v]]
    lines += ["", "| Verdict | SNP | Gene | Trait | Less common genotype: library says | Evidence | GWAS hits | Scores | Action |",
              "|---|---|---|---|---|---|---|---|---|"]
    esc = lambda s: (s or "").replace("|", "/").replace("\n", " ")
    for r in rows:
        hom = (r.get("minor") or "?") * 2
        lib = f"{hom} ({word[r.get('library_claim')]}): {esc(r.get('library_text'))[:90]}"
        ev = f"{word.get(r.get('evidence_function'))} ({esc(BASIS_TEXT.get(r.get('evidence_basis'), ''))}){': ' + esc(r.get('evidence'))[:110] if r.get('evidence') and r.get('evidence_basis') != 'none' else ''}"
        gw = (f"{r['n_gwas']}" + (f" via {r['gwas_via']['rsid']} (r² {r['gwas_via']['r2']})" if r.get("gwas_via") else "") + ": " +
              "; ".join(esc(g['trait'])[:40] for g in r["gwas"][:2])) if r["n_gwas"] else "none"
        sc = ", ".join(f"{k} {v:g}" for k, v in r["scores"].items())
        lines.append(f"| {r['verdict']} | {r['rsid']} | {esc(r['gene'])} | {esc(r['trait'])[:50]} | {lib} | {ev} | {gw} | {sc} | "
                     f"{esc(r.get('action'))}{' Flag: ' + '; '.join(r['flags']) if r.get('flags') else ''} |")
    open(OUT_MD, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    return c


if __name__ == "__main__":
    rows = audit()
    c = write(rows)
    print(f"✅ {len(rows)} library SNPs audited → {OUT_MD}")
    for v in SEVERITY:
        if c[v]:
            print(f"   {v}: {c[v]}")
