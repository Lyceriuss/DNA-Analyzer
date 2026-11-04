# Builders for the 2026-11 library corrections: keep content files readable.


def side(gene, title, badge, what, how, ancestral, yours, act_title, body,
         risks=(), foods=(), confidence=3):
    """One deep-dive perspective (data_risk / data_strength)."""
    return {
        "gene": gene, "title": title, "badge_type": badge,
        "mechanisms": {"what": what, "how": how, "ancestral": ancestral, "yours": yours},
        "risks": list(risks),
        "action": {"title": act_title, "body": body, "foods": list(foods)},
        "confidence": confidence,
    }


def deep_dive(risk_genotypes, strength_genotypes, data_risk=None, data_strength=None):
    entry = {"risk_genotypes": risk_genotypes, "strength_genotypes": strength_genotypes}
    if data_risk: entry["data_risk"] = data_risk
    if data_strength: entry["data_strength"] = data_strength
    return entry


def evidence(rsid, gene, common, biotype, organs, systems, impact, up, down,
             mech, qual, meth, label, audit, citations, name):
    """
    up/down: [(molecule, role|effect, mechanism|consequence)]
    mech/qual/meth: (score, rationale, detail)
    audit: [(study, type, population, methods, critique, score_contribution)]
    citations: only PMIDs returned by the GWAS Catalog API (verified real), never invented.
    """
    metric = lambda m: {"score": m[0], "rationale": m[1], "detail": m[2]}
    return {
        "rsid": rsid,
        "variant_identity": {"gene_symbol": gene, "common_name": common, "rsid": rsid, "biotype": biotype},
        "affected_organs": organs,
        "affected_systems": systems,
        "impact_type": impact,
        "metabolic_connections": {
            "upstream_requirements": [{"molecule": a, "role": b, "mechanism": c} for a, b, c in up],
            "downstream_impacts": [{"molecule": a, "effect": b, "consequence": c} for a, b, c in down],
        },
        "metrics": {"mechanistic_impact": metric(mech), "study_quality": metric(qual), "methodology": metric(meth)},
        "consensus_label": label,
        "methodology_audit": [
            {"study": s, "type": t, "population": p, "methods": m, "critique": c, "score_contribution": sc}
            for s, t, p, m, c, sc in audit
        ],
        "citations": [f"PMID:{c}" for c in citations],
        "name": name,
    }
