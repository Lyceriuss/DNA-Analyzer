# injectors-authenticators/additions_2026_11/apply.py
"""
Batch 1 of library additions: the orphan deep dives (narratives with no trait entry).

    python injectors-authenticators/additions_2026_11/apply.py

Each orphan was checked against Ensembl (gene at the site, alleles on the forward strand) and
the GWAS Catalog (effect direction). Six are added as trait entries, nine orphan narratives are
removed (wrong gene, duplicate signal of a SNP already in the library, or rare-disease only), and
APOE rs429358 is re-oriented (its C allele is e4; the library had it reversed).
Everything touched is backed up to config/backup/library_additions_2026-11-04.json. Safe to re-run.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "corrections_2026_11"))
from builders import side, deep_dive, evidence  # noqa: E402

FILES = {"traits": "config/snp_traits.json", "dd": "config/deep_dive_content.json", "ev": "config/evidence_db.json",
         "sv_dd": "config/SV_deep_dive_content.json", "sv_ev": "config/SV_evidence_db.json"}
BACKUP = "config/backup/library_additions_2026-11-04.json"

# Genotype keys are on the forward strand (as in MyHeritage files) and sorted.
ADD_TRAITS = {
    "rs7412": {
        "gene": "APOE", "system": "Lipids / Brain", "trait": "APOE ε2 status (rs7412)",
        "description": "rs7412 T marks the APOE ε2 allele, which lowers LDL cholesterol and Alzheimer's risk. "
                       "ε4 needs rs429358, which MyHeritage does not test.",
        "impact": "High",
        "variants": {"CC": "No ε2 allele (ε3 or ε4)", "CT": "One ε2 allele: lower LDL, lower Alzheimer's risk",
                     "TT": "ε2/ε2: very low LDL, small risk of a remnant-cholesterol disorder"},
        "scores": {"CC": 5, "CT": 7, "TT": 6},
    },
    "rs1801131": {
        "gene": "MTHFR", "system": "Methylation", "trait": "MTHFR A1298C (Glu429Ala)",
        "description": "A1298C mildly lowers MTHFR activity; it matters most together with C677T (rs1801133).",
        "impact": "Medium",
        "variants": {"GG": "Reduced activity (1298 C/C)", "GT": "Mildly reduced activity", "TT": "Typical activity (1298 A/A)"},
        "scores": {"GG": 4, "GT": 5, "TT": 6},
    },
    "rs2228570": {
        "gene": "VDR", "system": "Vitamin D / Immune", "trait": "Vitamin D receptor FokI (receptor length)",
        "description": "FokI changes the VDR start codon: the f allele makes a 3-amino-acid longer, less active receptor.",
        "impact": "Medium",
        "variants": {"GG": "F/F: shorter, more active receptor", "AG": "F/f: intermediate", "AA": "f/f: longer, less active receptor"},
        "scores": {"GG": 6, "AG": 5, "AA": 4},
    },
    "rs11568820": {
        "gene": "VDR", "system": "Vitamin D / Gut", "trait": "Vitamin D receptor Cdx2 (gut expression)",
        "description": "The Cdx2 promoter variant changes how much vitamin D receptor the intestine makes; T (Cdx2 A) makes more.",
        "impact": "Low",
        "variants": {"CC": "Typical intestinal VDR expression", "CT": "Somewhat higher VDR expression",
                     "TT": "Higher intestinal VDR expression"},
        "scores": {"CC": 5, "CT": 6, "TT": 7},
    },
    "rs12255372": {
        "gene": "TCF7L2", "system": "Glucose / Insulin", "trait": "Insulin secretion (TCF7L2, second marker)",
        "description": "The T allele lowers first-phase insulin secretion and raises type 2 diabetes risk (independent of rs7903146 only in part).",
        "impact": "High",
        "variants": {"GG": "Typical insulin secretion", "GT": "Somewhat reduced first-phase insulin",
                     "TT": "Reduced first-phase insulin; higher type 2 diabetes risk"},
        "scores": {"GG": 6, "GT": 5, "TT": 3},
    },
    "rs3025039": {
        "gene": "VEGFA", "system": "Cardiovascular / Muscle", "trait": "VEGF secretion (+936 C>T)",
        "description": "The T allele lowers circulating VEGF, the signal that grows new capillaries.",
        "impact": "Medium",
        "variants": {"CC": "Typical VEGF secretion", "CT": "Lower VEGF secretion", "TT": "Lowest VEGF secretion"},
        "scores": {"CC": 6, "CT": 5, "TT": 4},
    },
}

# Narrative metadata for the six (which genotypes see which side)
GENOTYPE_SIDES = {
    "rs1801131": (["GG"], ["TT"]), "rs2228570": (["AA"], ["GG"]), "rs11568820": (["CC"], ["TT"]),
    "rs12255372": (["TT", "GT"], ["GG"]), "rs3025039": (["TT", "CT"], ["CC"]),
}

# rs429358: C = e4 (Arg112). The library had CC as "APOE2" and scored it best.
FIX_RS429358 = {
    "trait": "APOE ε4 status (rs429358)",
    "description": "rs429358 C marks the APOE ε4 allele (Arg112), the strongest common genetic risk factor for "
                   "late-onset Alzheimer's disease; it also raises LDL cholesterol.",
    "variants": {"TT": "No ε4 allele (ε2 or ε3)", "CT": "One ε4 allele", "CC": "Two ε4 alleles"},
    "scores": {"TT": 7, "CT": 4, "CC": 2},
}

REMOVE = {
    "rs17616434": "Narrative about ALDH2, but the SNP sits in TLR1 (ALDH2*2 is rs671, already in the library)",
    "rs2854464": "Narrative about ACTN3, but the SNP sits in ACVR1B (ACTN3 R577X is rs1815739, already in the library)",
    "rs8111989": "Narrative about VDR, but the SNP is the CKM NcoI variant",
    "rs1143627": "IL1B -31: inherited together with rs16944 (already in the library); direction reported both ways",
    "rs1800796": "IL6 -572: rare in Europeans and inconsistent direction; IL6 -174 (rs1800795) already in the library",
    "rs1800797": "IL6 -597: inherited together with rs1800795 (already in the library)",
    "rs6269": "COMT: the narrative describes rs4680 Val/Met (already in the library), not this haplotype marker",
    "rs731236": "VDR TaqI: silent change inherited together with BsmI (rs1544410, already in the library)",
    "rs1799990": "PRNP M129V: only relevant to prion disease, which is extremely rare",
}

# Narrative text fixes (the VDR orphans shared one generic text that named the wrong variants)
TEXT_FIXES = {
    "rs2228570": [
        ("Your receptor (likely Taq1 or Bsm1 variant) has a shape change that reduces its binding efficiency.",
         "Your FokI variant makes a slightly longer receptor that binds its partners less efficiently."),
        ("Din receptor (troligen en Taq1- eller Bsm1-variant) har en formförändring som minskar dess bindningseffektivitet.",
         "Din FokI-variant ger en något längre receptor som binder sina partner mindre effektivt."),
    ],
    "rs11568820": [
        ("Your receptor (likely Taq1 or Bsm1 variant) has a shape change that reduces its binding efficiency.",
         "Your Cdx2 promoter variant makes less receptor in the gut lining."),
        ("Din receptor (troligen en Taq1- eller Bsm1-variant) har en formförändring som minskar dess bindningseffektivitet.",
         "Din Cdx2-promotorvariant gör att tarmslemhinnan bildar mindre receptor."),
        ("Your receptor is hypersensitive.", "Your Cdx2 variant makes more receptor in the gut lining."),
        ("Din receptor är överkänslig.", "Din Cdx2-variant gör att tarmslemhinnan bildar mer receptor."),
    ],
}

# rs7412: the old narrative described e4, which this SNP cannot detect. Rewritten as the e2 marker.
RS7412_DD = deep_dive([], ["CT", "TT"], data_strength=side(
    "APOE", "The 'Clean-Up' Transporter", "STRENGTH",
    "APOE carries cholesterol and fats between cells, including in the brain.",
    "You carry the ε2 version of APOE (the T allele at rs7412). It hands LDL particles to the liver for clearance more readily, so "
    "your LDL cholesterol runs lower, and ε2 is the APOE version most consistently linked to lower Alzheimer's risk.",
    "Typical APOE (CC).", "Your Result: ε2 carrier.",
    "Keep Triglycerides in Check",
    "ε2 lowers LDL but can let triglyceride-rich remnants linger, especially with high sugar, alcohol or weight gain. Check a full "
    "lipid panel and keep refined carbs moderate.",
    risks=["Lipids: Remnant particles can build up with poor diet (rare type III hyperlipoproteinemia in ε2/ε2)."],
    foods=["Oily Fish", "Fiber", "Limit Refined Carbs"], confidence=4))

RS7412_DD_SV = deep_dive([], ["CT", "TT"], data_strength=side(
    "APOE", "Den Städande Transportören", "STRENGTH",
    "APOE bär kolesterol och fetter mellan celler, även i hjärnan.",
    "Du bär ε2-versionen av APOE (T-allelen vid rs7412). Den lämnar lättare över LDL-partiklar till levern för rensning, så ditt "
    "LDL-kolesterol ligger lägre, och ε2 är den APOE-version som tydligast kopplats till lägre risk för Alzheimers sjukdom.",
    "Typisk APOE (CC).", "Ditt Resultat: ε2-bärare.",
    "Håll Triglyceriderna i Schack",
    "ε2 sänker LDL men kan låta triglyceridrika restpartiklar dröja kvar, särskilt vid mycket socker, alkohol eller viktuppgång. "
    "Ta en full blodfettsprofil och håll raffinerade kolhydrater måttliga.",
    risks=["Blodfetter: Restpartiklar kan ansamlas vid dålig kost (sällsynt typ III-hyperlipoproteinemi vid ε2/ε2)."],
    foods=["Fet fisk", "Fibrer", "Begränsa raffinerade kolhydrater"], confidence=4))

RS7412_EV = evidence(
    "rs7412", "APOE", "The ε2 Marker", "Missense Variant (Arg158Cys)",
    ["Liver", "Brain"], ["Lipid Metabolism", "Nervous System"], "LDL Receptor Binding",
    [("LDL / VLDL remnants", "Cargo", "APOE on the particle surface is the key that lets the liver take up remnants.")],
    [("LDL cholesterol", "Level", "ε2 binds the LDL receptor weakly, which up-regulates the receptor and lowers LDL.")],
    (5, "Changes receptor binding of a central lipid carrier.",
     "APOE has three common forms, ε2, ε3 and ε4, set by two SNPs. rs7412 changes arginine 158 to cysteine; its T allele defines "
     "ε2. The ε2 protein binds the LDL receptor far more weakly than ε3, so liver cells raise their LDL receptor count and clear "
     "LDL faster: each T allele lowers LDL cholesterol substantially. Remnant particles that rely on APOE for clearance can, "
     "however, accumulate, which is why ε2/ε2 people with extra metabolic stress can develop type III hyperlipoproteinemia. "
     "In the brain, ε2 is associated with lower amyloid build-up and the lowest Alzheimer's risk of the three forms."),
    (5, "Among the strongest signals in lipid genetics.",
     "LDL association reaches p = 6e-223 in UK Biobank-scale studies, with matching triglyceride signals; the ε2 link to lower "
     "Alzheimer's risk is replicated across large case-control consortia."),
    (5, "GWAS, receptor-binding assays and cohorts.", "Genome-wide association, LDL-receptor binding assays and long-term cohorts."),
    "LIPID TRANSPORT",
    [("Jacobs et al. (2024) - genome-wide association of lipid levels", "Genome-wide association", "UK Biobank",
      "Genome-wide association of LDL cholesterol.",
      "STRENGTH: Enormous sample and an unambiguous effect allele (T lowers LDL). CRITIQUE: The full APOE type needs rs429358 too, "
      "which MyHeritage files lack, so ε3 and ε4 cannot be told apart from this SNP alone.", "Study Quality (5/5)")],
    ["39414775", "39024449"], "APOE_E2")

RS7412_EV_SV = evidence(
    "rs7412", "APOE", "ε2-Markören", "Missense-variant (Arg158Cys)",
    ["Lever", "Hjärna"], ["Lipidmetabolism", "Nervsystemet"], "Bindning till LDL-receptorn",
    [("LDL- / VLDL-restpartiklar", "Last", "APOE på partikelns yta är nyckeln som låter levern ta upp restpartiklar.")],
    [("LDL-kolesterol", "Nivå", "ε2 binder LDL-receptorn svagt, vilket ökar antalet receptorer och sänker LDL.")],
    (5, "Ändrar receptorbindningen hos en central lipidbärare.",
     "APOE finns i tre vanliga former, ε2, ε3 och ε4, som bestäms av två SNP:er. rs7412 byter arginin 158 mot cystein; dess "
     "T-allel definierar ε2. ε2-proteinet binder LDL-receptorn mycket svagare än ε3, så levercellerna ökar antalet LDL-receptorer "
     "och rensar LDL snabbare: varje T-allel sänker LDL-kolesterolet tydligt. Restpartiklar som är beroende av APOE för att rensas "
     "kan dock ansamlas, vilket är varför personer med ε2/ε2 och extra metabol stress kan utveckla typ III-hyperlipoproteinemi. "
     "I hjärnan är ε2 kopplad till mindre amyloidinlagring och den lägsta Alzheimerrisken av de tre formerna."),
    (5, "Bland de starkaste signalerna inom lipidgenetik.",
     "Kopplingen till LDL når p = 6e-223 i studier i UK Biobank-storlek, med samstämmiga triglyceridsignaler; kopplingen mellan "
     "ε2 och lägre Alzheimerrisk är replikerad i stora fall-kontrollkonsortier."),
    (5, "GWAS, receptorbindningsförsök och kohorter.", "Genomvid associationsstudie, försök med LDL-receptorbindning och långa kohorter."),
    "LIPIDTRANSPORT",
    [("Jacobs et al. (2024) - genomvid associationsstudie av blodfetter", "Genomvid associationsstudie", "UK Biobank",
      "Genomvid association för LDL-kolesterol.",
      "STYRKA: Enormt urval och en entydig effektallel (T sänker LDL). KRITIK: Den fullständiga APOE-typen kräver även rs429358, "
      "som saknas i MyHeritage-filer, så ε3 och ε4 kan inte skiljas åt med enbart denna SNP.", "Studiekvalitet (5/5)")],
    ["39414775", "39024449"], "APOE_E2")


def load(p):
    return json.load(open(p, encoding="utf-8"))


def save(p, data):
    open(p, "wb").write(json.dumps(data, indent=4, ensure_ascii=False).replace("\n", "\r\n").encode("utf-8"))


def walk_replace(obj, a, b):
    if isinstance(obj, dict):
        return {k: walk_replace(v, a, b) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk_replace(v, a, b) for v in obj]
    return obj.replace(a, b) if isinstance(obj, str) else obj


def main():
    db = {k: load(p) for k, p in FILES.items()}
    backup = load(BACKUP) if os.path.exists(BACKUP) else {"removed": {}, "replaced": {}}
    snap = lambda key: copy.deepcopy({n: db[n][key] for n in FILES if key in db[n]})
    done = {"added": 0, "removed": 0, "fixed": 0}

    for rsid, reason in REMOVE.items():
        if any(rsid in db[n] for n in FILES):
            backup["removed"].setdefault(rsid, {"reason": reason, **snap(rsid)})
            for n in FILES:
                db[n].pop(rsid, None)
            done["removed"] += 1

    for rsid, entry in ADD_TRAITS.items():
        backup["replaced"].setdefault(rsid, snap(rsid))
        db["traits"][rsid] = entry
        done["added"] += 1
    for rsid, (risk, strength) in GENOTYPE_SIDES.items():
        for n in ("dd", "sv_dd"):
            db[n][rsid]["risk_genotypes"], db[n][rsid]["strength_genotypes"] = risk, strength
    for rsid, pairs in TEXT_FIXES.items():
        for a, b in pairs:
            for n in ("dd", "sv_dd"):
                db[n][rsid] = walk_replace(db[n][rsid], a, b)
    db["dd"]["rs7412"], db["sv_dd"]["rs7412"] = RS7412_DD, RS7412_DD_SV
    db["ev"]["rs7412"], db["sv_ev"]["rs7412"] = RS7412_EV, RS7412_EV_SV

    if db["traits"]["rs429358"]["scores"].get("CC") != FIX_RS429358["scores"]["CC"]:
        backup["replaced"].setdefault("rs429358", snap("rs429358"))
        db["traits"]["rs429358"].update(FIX_RS429358)
        done["fixed"] += 1
    for n in ("dd", "sv_dd"):
        if "rs429358" in db[n]:
            db[n]["rs429358"]["risk_genotypes"], db[n]["rs429358"]["strength_genotypes"] = ["CC", "CT"], ["TT"]

    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    json.dump(backup, open(BACKUP, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    for n, p in FILES.items():
        save(p, db[n])
    print(" | ".join(f"{k} {v}" for k, v in done.items()), f"| library now {len(db['traits'])} traits")


if __name__ == "__main__":
    main()
