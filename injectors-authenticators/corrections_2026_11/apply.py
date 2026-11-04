# injectors-authenticators/corrections_2026_11/apply.py
"""
Applies the 2026-11 library corrections found by cluster_analysis/validate_library.py.

    python injectors-authenticators/corrections_2026_11/apply.py

Every touched entry is first copied to config/backup/library_corrections_2026-11-04.json,
so any removal or rewrite can be restored by hand. Safe to re-run: applied steps are skipped
and existing backup snapshots are never overwritten.
"""
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import content_en  # noqa: E402
import content_sv  # noqa: E402

FILES = {
    "traits": "config/snp_traits.json",
    "dd": "config/deep_dive_content.json",
    "ev": "config/evidence_db.json",
    "sv_dd": "config/SV_deep_dive_content.json",
    "sv_ev": "config/SV_evidence_db.json",
}
BACKUP_PATH = "config/backup/library_corrections_2026-11-04.json"
VALIDATION_PATH = "cluster_analysis/library_validation.json"

# --- Removals: no established effect for the gene actually at the site, or unfixable ---
REMOVE_REASON = {
    "rs1042713_dupfix": "Suffixed duplicate key; can never match a DNA file (rs1042713 kept)",
    "rs2740574_dupfix": "Suffixed duplicate key; can never match a DNA file (rs2740574 kept)",
    "rs662799_TIER2": "Suffixed duplicate key; can never match a DNA file (rs662799 kept)",
    "rs328_TIER2": "Suffixed duplicate key; can never match a DNA file (rs328 kept)",
    "rs11191548_TIER2": "Suffixed duplicate key; can never match a DNA file (rs11191548 kept)",
    "rs1800790_TIER2": "Suffixed duplicate key; can never match a DNA file (rs1800790 kept)",
    "rs1049434_TIER2": "Suffixed duplicate key naming CKM; can never match a DNA file",
    "rs2070974": "rsID not found in Ensembl/dbSNP",
    "rs57875989": "rsID not found in Ensembl/dbSNP (PER3 VNTR is not a SNP)",
    "rs16835198": "Genotype letters impossible for G/T and their strand cannot be determined",
    "rs13331": "Variant is in DLG4, not OR2M7; retarget candidate rs4481887 has unclear effect direction",
    "rs1805086": "Variant is MSTN K153R, not MYF5; effect direction inconsistent across studies",
    "rs2073711": "Variant is CILP I395T, not COL11A1; disc association not replicated in Europeans",
    "rs2802295": "Variant is in FOXO3, not FOXO1; FOXO3 already covered by rs2802292",
    "rs3758391": "Variant is in SIRT1, not SIRT3; SIRT1 already covered",
    "rs1256049": "Variant is a synonymous ESR2 SNP, not ESR1; weak functional evidence",
    "rs605059": "Variant is HSD17B1 S312G, not ESR2; effect direction unclear",
    "rs9282859": "Variant is in STK11, not HSD17B12; no established effect",
    "rs2071403": "Variant is in TPO, not THRB; effect unclear",
    "rs2052129": "Variant is in AOC1 (DAO), not HDC; DAO now covered by rs10156191",
}
# Remaining wrong-gene entries: the variant sits in an unrelated gene with no
# established health effect, so the narrative cannot be rewritten honestly.
REMOVE_WRONG_GENE = [
    "rs1010151", "rs12594956", "rs12942023", "rs13278062", "rs137852", "rs16906252", "rs1728986",
    "rs17608", "rs17609940", "rs1800252", "rs1805065", "rs2239681", "rs2271683", "rs2285477",
    "rs2289360", "rs2535633", "rs350843", "rs3737965", "rs3741942", "rs4074995", "rs444697",
    "rs479744", "rs521674", "rs5516", "rs6263", "rs6536", "rs676925", "rs699005", "rs7294919",
    "rs8031440", "rs8101881", "rs934078", "rs3123554",
]

# --- Retargets: narrative is right, rsID was wrong. Move to the canonical SNP. ---
RETARGET = {
    "rs6020": {
        "new": "rs1799963",
        "traits": {"variants": {"GG": "Normal prothrombin levels", "AG": "Raised clotting risk (G20210A carrier)",
                                "AA": "High clotting risk (G20210A homozygous, rare)"},
                   "scores": {"GG": 9, "AG": 3, "AA": 1}},
    },
    "rs1254337": {
        "new": "rs734553",
        "traits": {"variants": {"GG": "Lower uric acid tendency", "GT": "Intermediate uric acid",
                                "TT": "Higher uric acid tendency"},
                   "scores": {"GG": 8, "GT": 6, "TT": 4}},
        "ev_text": [("The rs1254337 'G' allele increases the transporter's efficiency and surface expression.",
                     "The rs734553 'T' allele is associated with higher transporter activity and higher serum urate.")],
        "sv_ev_text": [("Allelen 'G' för rs1254337 ökar transportörens effektivitet och ytexpression.",
                        "Allelen 'T' för rs734553 är kopplad till högre transportöraktivitet och högre urat i blodet.")],
        "biotype": ("Intronic Variant", "Intronvariant"),
    },
    "rs17226398": {
        "new": "rs2631367",
        "traits": {"variants": {"GG": "Efficient carnitine uptake", "CG": "Moderately reduced uptake",
                                "CC": "Lower OCTN2 expression (-207C/C)"},
                   "scores": {"GG": 8, "CG": 6, "CC": 4}},
        "ev_text": [("The rs17226398 variant lowers", "The rs2631367 '-207C' promoter variant lowers")],
        "sv_ev_text": [("rs17226398-varianten sänker", "rs2631367-varianten (-207C) sänker")],
    },
    "rs893703": {
        "new": "rs3892097",
        "traits": {"variants": {"CC": "Normal CYP2D6 function at the *4 site", "CT": "One *4 copy: intermediate metabolism",
                                "TT": "Two *4 copies: poor metabolizer"},
                   "scores": {"CC": 7, "CT": 5, "TT": 2},
                   "description": "CYP2D6*4 marker; metabolizes many antidepressants, beta-blockers and painkillers. Deletions/duplications are not measured."},
        "ev_text": [("The rs893703 SNP is a highly effective tag for determining 'Metabolizer Status'.",
                     "The rs3892097 'T' allele marks CYP2D6*4, the most common non-functional allele in Europeans (a splice defect).")],
        "sv_ev_text": [("SNP rs893703 är en mycket effektiv markör för att bestämma 'Metaboliserarstatus'.",
                        "Allelen 'T' för rs3892097 markerar CYP2D6*4, den vanligaste icke-funktionella allelen hos européer (en splitsningsdefekt).")],
        "biotype": ("Splice Acceptor Variant (CYP2D6*4)", "Splitsningsvariant (CYP2D6*4)"),
        "dd_tokens": {"AA": "TT", "AG": "CT", "GA": "TC", "GG": "CC"},
    },
    "rs11185098": {
        "new": "rs10156191",
        "traits": {"gene": "AOC1 (DAO)",
                   "variants": {"CC": "Normal DAO activity", "CT": "Moderately reduced DAO activity",
                                "TT": "Low DAO activity (higher histamine intolerance risk)"},
                   "scores": {"CC": 7, "CT": 5, "TT": 3}},
        "ev_text": [("The rs11185098 variant is a marker for 'Low DAO Activity'.",
                     "The rs10156191 'T' allele (Thr16Met) is associated with lower DAO activity.")],
        "sv_ev_text": [("Varianten rs11185098 är en markör för 'Låg DAO-aktivitet'.",
                        "Allelen 'T' för rs10156191 (Thr16Met) är kopplad till lägre DAO-aktivitet.")],
        "biotype": ("Missense Variant (Thr16Met)", "Missense-variant (Thr16Met)"),
        "gene_symbol": "AOC1",
        "dd_gene": "AOC1 (DAO)",
        "dd_tokens": {"GG": "CC", "GT": "CT", "TG": "TC", "TT": "TT"},
    },
    "rs3774175": {
        "new": "rs1799895",
        "traits": {"variants": {"CC": "Normal vessel-wall anchoring (Arg213)",
                                "CG": "R213G carrier: SOD3 shifts from vessel wall to plasma",
                                "GG": "R213G homozygous (rare): weak vessel-wall protection"},
                   "scores": {"CC": 7, "CG": 4, "GG": 3}},
        "ev_text": [("The rs3774175 'C' allele (Gly213)", "The rs1799895 'G' allele (Gly213)")],
        "sv_ev_text": [("rs3774175 'C'-allelen (Gly213)", "rs1799895 'G'-allelen (Gly213)")],
    },
}

# --- Allele fix: FOXO3 rs2802292 is G/T; G is the longevity allele ---
FOXO3 = "rs2802292"
FOXO3_TRAITS = {
    "impact": "High",
    "description": "The G allele is associated with enhanced FOXO3 activity, promoting stress resistance and longevity.",
    "variants": {"TT": "Typical stress resistance", "GT": "Enhanced stress resistance", "GG": "Optimal stress resistance"},
    "scores": {"TT": 6, "GT": 8, "GG": 9},
}


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    text = json.dumps(data, indent=4, ensure_ascii=False).replace("\n", "\r\n")
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def map_strings(obj, fn):
    """Applies fn to every string inside a nested dict/list."""
    if isinstance(obj, dict):
        return {k: map_strings(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [map_strings(v, fn) for v in obj]
    return fn(obj) if isinstance(obj, str) else obj


def rendered_lengths(dd_entry, ev_entry):
    out = {}
    for side in ("data_risk", "data_strength"):
        s = (dd_entry or {}).get(side)
        if s:
            out[f"{side}.what"] = len(s["mechanisms"].get("what", ""))
            out[f"{side}.how"] = len(s["mechanisms"].get("how", ""))
            out[f"{side}.body"] = len(s["action"].get("body", ""))
    for k in ("mechanistic_impact", "study_quality", "methodology"):
        d = ((ev_entry or {}).get("metrics", {}).get(k) or {}).get("detail")
        if d:
            out[f"ev.{k}"] = len(d)
    return out


def main():
    db = {k: load(p) for k, p in FILES.items()}
    validation = {r["rsid"]: r for r in load(VALIDATION_PATH)}
    backup = load(BACKUP_PATH) if os.path.exists(BACKUP_PATH) else {"removed": {}, "replaced": {}}

    def snapshot(key):
        # Deep copy: later steps update trait dicts in place
        return copy.deepcopy({name: db[name].get(key) for name in FILES if key in db[name]})

    counts = {"removed": 0, "retargeted": 0, "rewritten": 0, "allele_fixed": 0}

    # 1. Removals
    removals = dict(REMOVE_REASON)
    for rsid in REMOVE_WRONG_GENE:
        if rsid not in validation:
            continue  # validation was re-run after an earlier apply
        v = validation[rsid]
        site = [g for g in v.get("genes_at_site", {}) if not g.startswith("ENSG")] or \
               [g for g, _ in v.get("nearest_genes", [])[:2]]
        removals[rsid] = (f"Variant is at {', '.join(site) or 'no nearby gene'}, not {v['gene']}; "
                          "no established health effect to rewrite")
    for rsid, reason in removals.items():
        if rsid not in db["traits"]:
            continue  # already removed
        backup["removed"][rsid] = {"reason": reason, **snapshot(rsid)}
        for name in FILES:
            db[name].pop(rsid, None)
        counts["removed"] += 1

    # 2. Retargets (key changes, narrative kept)
    for old, spec in RETARGET.items():
        new = spec["new"]
        if old not in db["traits"]:
            continue  # already retargeted
        assert new not in db["traits"], f"{new} already in library"
        backup["replaced"][old] = {"retargeted_to": new, **snapshot(old)}
        for name in FILES:
            if old not in db[name]:
                continue
            entry = db[name].pop(old)
            pairs = spec.get("ev_text", []) if name == "ev" else spec.get("sv_ev_text", []) if name == "sv_ev" else []
            for a, b in pairs:
                entry = map_strings(entry, lambda s, a=a, b=b: s.replace(a, b))
            if name in ("dd", "sv_dd") and spec.get("dd_tokens"):
                tok = spec["dd_tokens"]
                entry = map_strings(entry, lambda s: re.sub(r"\b(" + "|".join(tok) + r")\b", lambda m: tok[m.group(0)], s))
                if spec.get("dd_gene"):
                    for side in ("data_risk", "data_strength"):
                        if side in entry: entry[side]["gene"] = spec["dd_gene"]
            entry = map_strings(entry, lambda s: s.replace(old, new))
            if name in ("ev", "sv_ev"):
                if spec.get("biotype"):
                    entry["variant_identity"]["biotype"] = spec["biotype"][0 if name == "ev" else 1]
                if spec.get("gene_symbol"):
                    entry["variant_identity"]["gene_symbol"] = spec["gene_symbol"]
            if name == "traits":
                entry.update(spec["traits"])
            db[name][new] = entry
        counts["retargeted"] += 1

    # 3. FOXO3 allele fix: evidence called 'T' the longevity allele and used a non-existent 'C'
    if "TC" in db["traits"][FOXO3]["variants"]:  # not applied yet (swap is not idempotent)
        backup["replaced"][FOXO3] = snapshot(FOXO3)
        db["traits"][FOXO3].update(FOXO3_TRAITS)
        swap = lambda s: s.replace("'T'", "'§G'").replace("'C'", "'T'").replace("'§G'", "'G'")
        for name in ("ev", "sv_ev"):
            db[name][FOXO3] = map_strings(db[name][FOXO3], swap)
        counts["allele_fixed"] += 1

    # 4. Rewrites (idempotent: content is replaced, backup keeps the first snapshot)
    report = []
    rewritten = set(content_en.TRAITS) | set(content_en.DEEP_DIVES) | set(content_en.EVIDENCE)
    for rsid in sorted(rewritten):
        if rsid not in backup["replaced"]:
            backup["replaced"][rsid] = snapshot(rsid)
        counts["rewritten"] += 1
        before = rendered_lengths(db["dd"].get(rsid), db["ev"].get(rsid))
        if rsid in content_en.TRAITS:
            db["traits"][rsid].update(content_en.TRAITS[rsid])
        if rsid in content_en.DEEP_DIVES:
            db["dd"][rsid] = content_en.DEEP_DIVES[rsid]
            db["sv_dd"][rsid] = content_sv.DEEP_DIVES[rsid]
        if rsid in content_en.EVIDENCE:
            db["ev"][rsid] = content_en.EVIDENCE[rsid]
            db["sv_ev"][rsid] = content_sv.EVIDENCE[rsid]
        after = rendered_lengths(db["dd"].get(rsid), db["ev"].get(rsid))
        report.append((rsid, before, after))

    os.makedirs(os.path.dirname(BACKUP_PATH), exist_ok=True)
    with open(BACKUP_PATH, "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)
    for name, path in FILES.items():
        save(path, db[name])

    print(" | ".join(f"{k} {v}" for k, v in counts.items()))
    print(f"Library now has {len(db['traits'])} traits. Backup: {BACKUP_PATH}\n")
    print("Character counts of rendered text (before -> after):")
    for rsid, before, after in report:
        fields = sorted(set(before) | set(after))
        cells = [f"{f.split('.')[-1]} {before.get(f, '-')}->{after.get(f, '-')}" for f in fields]
        print(f"  {rsid:11} " + " | ".join(cells))


if __name__ == "__main__":
    main()
