# cluster_analysis/validate_library.py
"""
Validates every rsID in the library against Ensembl (GRCh38) and the GWAS Catalog.

    python -m cluster_analysis.validate_library

Checks per rsID:
  location   is the library gene at (or within 5 kb of) the variant? which file's gene is right?
  alleles    are the genotype letters possible for this SNP, and on which strand?
  genotypes  are all three genotypes listed (otherwise some people get no result)?
  gwas       which genes curators mapped it to, and its strongest traits (for manual review)

Public data only. Writes cluster_analysis/library_validation.md and .json.
"""
import json
import os
import re

from cluster_analysis import sources
from cluster_analysis.build_modules import candidate_symbols

TRAITS_PATH = "config/snp_traits.json"
DEEP_DIVE_PATH = "config/deep_dive_content.json"
EVIDENCE_PATH = "config/evidence_db.json"
OUT_BASE = os.path.join(os.path.dirname(__file__), "library_validation")
COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}
NEAR_WINDOW = 250_000

# A/T and C/G SNPs whose forward-strand orientation was checked by hand against
# Ensembl's per-allele amino acid (or promoter position) and the gene's strand.
STRAND_VERIFIED = {
    "rs1042522": "TP53 P72R: forward G = Pro72, C = Arg72 (2026-11-04)",
    "rs1049434": "SLC16A1 E490D: forward A = Asp490, T = Glu490 (2026-11-04)",
    "rs1799895": "SOD3 R213G: forward C = Arg213, G = Gly213 (2026-11-04)",
    "rs2304672": "PER2 C111G: gene on minus strand, forward C = 111G (2026-11-04)",
    "rs2631367": "SLC22A5 -207G>C: gene on plus strand, forward C = -207C (2026-11-04)",
    "rs523349": "SRD5A2 V89L: forward C = Val89, G = Leu89 (2026-11-04)",
}


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _names(gene_field, resolved):
    """All names a gene field can go by: as written, cleaned candidates, STRING preferred names."""
    if not gene_field:
        return set()
    cands = candidate_symbols(gene_field)
    return {gene_field, *cands, *(resolved[c] for c in cands if c in resolved)}


def check_alleles(variant_keys, alleles):
    letters = {ch for k in variant_keys for ch in k if ch in COMPLEMENT}
    fwd = {a for a in alleles if a in COMPLEMENT}
    rev = {COMPLEMENT[a] for a in fwd}
    on_fwd, on_rev = letters <= fwd, letters <= rev
    # Only an A/T or C/G pair is truly strand-ambiguous; multi-allelic sites (A/C/G/T)
    # merely make other pairs look valid on both strands
    palindromic = letters in ({"A", "T"}, {"C", "G"})
    if palindromic and on_fwd:
        status = "ambiguous"   # strand cannot be told from the letters
    elif on_fwd:
        status = "forward"
    elif on_rev:
        status = "reverse"     # fine: normalizer flips strands
    else:
        status = "mismatch"

    missing = []
    if len(letters) == 2:
        a, b = sorted(letters)
        present = {"".join(sorted(k)) for k in variant_keys}
        missing = [g for g in (a + a, a + b, b + b) if g not in present]
    return {"letters": sorted(letters), "status": status, "missing_genotypes": missing}


def validate():
    traits = _load(TRAITS_PATH)
    deep_dive = _load(DEEP_DIVE_PATH)
    evidence = _load(EVIDENCE_PATH)

    def dd_gene(rsid):
        e = deep_dive.get(rsid) or {}
        return (e.get("data_risk") or {}).get("gene") or (e.get("data_strength") or {}).get("gene")

    def ev_gene(rsid):
        return (evidence.get(rsid) or {}).get("variant_identity", {}).get("gene_symbol")

    # Resolve every gene name used in any of the three files to its official symbol
    all_fields = {g for r in traits for g in (traits[r]["gene"], dd_gene(r), ev_gene(r)) if g}
    queries = sorted({c for g in all_fields for c in candidate_symbols(g)})
    resolved = sources.string_resolve(queries)
    for q in queries:
        if q not in resolved:
            resolved.update(sources.string_resolve([q]))

    # Keys like "rs328_TIER2" never match a DNA file; validate the real rsID behind them
    base_of = {key: re.match(r"rs\d+", key).group(0) for key in traits}
    rsids = sorted(set(base_of.values()))
    print(f"🧬 Looking up {len(rsids)} rsIDs in Ensembl (cached after first run)...")
    vep = sources.ensembl_vep(rsids)

    results = []
    for key in sorted(traits):
        rsid = base_of[key]
        info = traits[key]
        row = {"rsid": key, "gene": info["gene"], "trait": info.get("trait", ""),
               "deep_dive_gene": dd_gene(key), "evidence_gene": ev_gene(key),
               "issues": [], "severity": "ok"}
        if key != rsid:
            dup = f"; duplicates {rsid} ({traits[rsid]['gene']})" if rsid in traits else ""
            row["issues"].append(f"key has a suffix, so it can never match a DNA file{dup}")
            row["severity"] = "error"
        v = vep.get(rsid)
        if not v:
            row["issues"].append("rsID not found in Ensembl (retired, or never existed)")
            row["severity"] = "error"
            results.append(row)
            continue

        row.update({"location": f"chr{v['chrom']}:{v['pos']}", "consequence": v["consequence"],
                    "alleles": v["alleles"], "genes_at_site": v["genes"], "eur_af": v["eur_af"]})

        # --- location ---
        site = {g for g in v["genes"]}
        lib_ok = bool(_names(info["gene"], resolved) & site)
        row["gene_supported"] = {
            "snp_traits": lib_ok,
            "deep_dive": bool(_names(row["deep_dive_gene"], resolved) & site) if row["deep_dive_gene"] else None,
            "evidence": bool(_names(row["evidence_gene"], resolved) & site) if row["evidence_gene"] else None,
        }
        if not lib_ok:
            near = sources.ensembl_genes_near(v["chrom"], v["pos"], NEAR_WINDOW)
            row["nearest_genes"] = near[:5]
            lib_near = [d for g, d in near if g in _names(info["gene"], resolved)]
            if lib_near:
                row["issues"].append(f"{info['gene']} is {lib_near[0] // 1000} kb away, not at the site "
                                     "(regulatory/LD association; check the mechanism text)")
                if row["severity"] == "ok": row["severity"] = "warn"
            elif not near and not [g for g in v["genes"] if not g.startswith("ENSG")]:
                row["issues"].append(f"gene desert: no protein-coding gene within {NEAR_WINDOW // 1000} kb; "
                                     f"{info['gene']} is presumably the GWAS locus name, confirm it")
                if row["severity"] == "ok": row["severity"] = "warn"
            else:
                at = ", ".join(g for g in v["genes"] if not g.startswith("ENSG")) or \
                     ", ".join(g for g, _ in near[:3]) or "no protein-coding gene nearby"
                row["issues"].append(f"{info['gene']} is not within {NEAR_WINDOW // 1000} kb; variant is at {at}")
                row["severity"] = "error"
        for source in ("deep_dive", "evidence"):
            if row["gene_supported"][source] is False and lib_ok:
                row["issues"].append(f"{source} names {row[source + '_gene']}, but the site is {info['gene']}")
                row["severity"] = "error"

        # --- alleles / genotypes ---
        allele = check_alleles(info["variants"].keys(), v["alleles"])
        row["allele_check"] = allele
        if allele["status"] == "mismatch":
            row["issues"].append(f"genotype letters {allele['letters']} are impossible for alleles {'/'.join(v['alleles'])}")
            row["severity"] = "error"
        elif allele["status"] == "ambiguous" and rsid in STRAND_VERIFIED:
            allele["status"] = "forward (verified)"
            row["strand_note"] = STRAND_VERIFIED[rsid]
        elif allele["status"] == "ambiguous":
            row["issues"].append(f"A/T or C/G SNP ({'/'.join(v['alleles'])}): confirm the scores are written on the "
                                 "forward strand, otherwise results are silently inverted")
            if row["severity"] == "ok": row["severity"] = "warn"
        if allele["missing_genotypes"]:
            row["issues"].append(f"no entry for genotype(s) {', '.join(allele['missing_genotypes'])}: "
                                 "people with them get no result")
            if row["severity"] == "ok": row["severity"] = "warn"

        # --- GWAS (for review) ---
        row["gwas_mapped_genes"] = sources.gwas_mapped_genes(rsid)
        row["gwas_top_traits"] = [t["trait"] for t in sources.gwas_traits(rsid, max_traits=4)]
        results.append(row)

    return results


def to_markdown(results):
    errors = [r for r in results if r["severity"] == "error"]
    warns = [r for r in results if r["severity"] == "warn"]
    lines = ["# Library validation", "",
             f"{len(results)} rsIDs checked against Ensembl (GRCh38) and the GWAS Catalog: "
             f"**{len(errors)} errors**, {len(warns)} warnings, "
             f"{len(results) - len(errors) - len(warns)} ok.", "",
             "Regenerate with `python -m cluster_analysis.validate_library`.", ""]

    def section(title, rows, intro):
        if not rows: return
        lines.extend([f"## {title} ({len(rows)})", "", intro, "",
                      "| rsID | Library gene | Trait | Site (GRCh38) | Genes at site | GWAS top traits | Issues |",
                      "|---|---|---|---|---|---|---|"])
        for r in rows:
            site_genes = ", ".join(g for g in r.get("genes_at_site", {}) if not g.startswith("ENSG")) or "–"
            traits = "; ".join(r.get("gwas_top_traits", [])[:3]) or "–"
            lines.append(f"| {r['rsid']} | {r['gene']} | {r['trait']} | {r.get('location', '–')} "
                         f"({r.get('consequence', '')}) | {site_genes} | {traits} | {'<br>'.join(r['issues'])} |")
        lines.append("")

    section("Errors", errors, "Wrong gene, impossible alleles, or unknown rsID. Results for these SNPs are unreliable.")
    section("Warnings", warns, "Strand-ambiguous SNPs, missing genotypes, or variants that sit near (not in) the gene.")

    strands = {}
    for r in results:
        s = r.get("allele_check", {}).get("status", "n/a")
        strands[s] = strands.get(s, 0) + 1
    lines += ["## Strand summary", "",
              "| Orientation of library genotypes | rsIDs |", "|---|---|",
              *[f"| {k} | {v} |" for k, v in sorted(strands.items(), key=lambda x: -x[1])], ""]
    return "\n".join(lines)


if __name__ == "__main__":
    results = validate()
    with open(OUT_BASE + ".json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    with open(OUT_BASE + ".md", "w", encoding="utf-8") as f:
        f.write(to_markdown(results))
    e = sum(r["severity"] == "error" for r in results)
    w = sum(r["severity"] == "warn" for r in results)
    print(f"✅ {len(results)} rsIDs | {e} errors | {w} warnings -> {OUT_BASE}.md")
