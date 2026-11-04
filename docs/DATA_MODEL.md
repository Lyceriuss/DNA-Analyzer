# Data model (`config/`)

All files are UTF-8 JSON keyed by rsID unless noted otherwise. The counts are from 2026-11.

| File | Entries | Used by | Role |
|---|---|---|---|
| `snp_traits.json` | 247 | analyzer (runtime) | **Ground truth**: genotype → score / interpretation |
| `deep_dive_content.json` | 246 | report (EN) | Narrative for strength and risk deep-dive pages |
| `SV_deep_dive_content.json` | 243 | report (SV) | Swedish translation of the above |
| `evidence_db.json` | 231 | report (EN) | Research/evidence panel and confidence metrics |
| `SV_evidence_db.json` | 228 | report (SV) | Swedish translation of the above |
| `ui_labels.json` | 2 langs | report | All PDF chrome strings and the intro text |
| `proxies.json` | 2 | proxy_handler (disabled) | Proxy SNP → target SNP genotype translation |
| `muscle_logic_gates_db.json` | 6 stations | cluster_checker.py | Experimental multi-SNP rule sets |
| `rewrite_needed.json` | 120 (list) | written by `audit_deep_dives.py` | RSIDs whose narrative failed the LLM audit |
| `backup/` | — | — | Manual dated snapshots |

## `snp_traits.json`

```json
"rs1801133": {
  "gene": "MTHFR",
  "system": "Methylation",            // free text → domain via domain_mapper keywords
  "trait": "Folate → active methylfolate conversion",
  "description": "...",
  "impact": "High",                   // High | Medium | Low (a few entries hold other text)
  "variants": { "GG": "Optimal ...", "GA": "...", "AA": "..." },
  "scores":   { "GG": 9, "GA": 6, "AA": 2 }   // 0–10, 5 = baseline; keys must match `variants`
}
```

Rules:
- The `variants` and `scores` keys must be identical (they currently are).
- **Write genotype keys in sorted order** (`AG`, not `GA`), or list both orders. The matcher only sorts the user side.
- Keys are on the strand the matcher should *prefer*. The complement is tried as a fallback.

### Carrier and rare-variant entries

Entries with `"category": "carrier"` (recessive conditions) or `"category": "rare_variant"` (a rare variant of uncertain
significance in a dominant-disease gene) are never scored: `main.py` keeps them out of the dashboard, strengths and risks, and
lists them on a separate **Carrier findings** page, only when the person carries a variant copy.

```json
"rs1800100": {
  "gene": "CFTR", "category": "carrier", "variant_name": "p.Arg668Cys",
  "reference_genotype": "CC",                 // forward strand; anything else = carries the variant
  "condition": "Congenital absence of the vas deferens (CBAVD) and mild CFTR conditions",
  "condition_sv": "Medfödd avsaknad av sädesledare (CBAVD) och milda CFTR-tillstånd",
  "inheritance": "recessive",
  "variants": { "CC": "Not a carrier", "CT": "Carrier: one copy", "TT": "Two copies" },
  "scores":   { "CC": 5, "CT": 5, "TT": 5 }
}
```

The page wording lives in `ui_labels.json` (`carrier_*` keys, English and Swedish).

## `deep_dive_content.json`

```json
"rs35652124": {
  "risk_genotypes":     ["TT", "AA", "TA", "AT"],   // informational; the runtime uses the score instead
  "strength_genotypes": ["CC", "GG"],
  "data_risk": {
    "gene": "NFE2L2",
    "title": "The 'Cellular Shield' & Detox Master",
    "badge_type": "RISK",
    "mechanisms": { "what": "...", "how": "...", "ancestral": "...", "yours": "..." },
    "risks": ["..."],
    "action": { "title": "...", "body": "...", "foods": ["..."] },
    "confidence": 3
  },
  "data_strength": { /* same shape */ }
}
```

The report renders `mechanisms.what`, `mechanisms.how`, `action.title` and `action.body`. The fields `ancestral`, `yours`, `risks` and `foods` exist in the data but are not printed.
17 RSIDs in this file have no matching entry in `snp_traits.json`, so they never render.

## `evidence_db.json`

```json
"rs1801131": {
  "rsid": "rs1801131",
  "variant_identity": { "gene_symbol", "common_name", "rsid", "biotype" },
  "affected_organs":  ["Brain", "Liver"],      // restricted vocabulary, see VALID_ORGANS in the injectors
  "affected_systems": ["..."],
  "impact_type": "...",
  "metabolic_connections": {
    "upstream_requirements": [{ "molecule", "role", "mechanism" }],
    "downstream_impacts":    [{ "molecule", "effect", "consequence" }]
  },
  "metrics": {
    "mechanistic_impact": { "score": 1-5, "rationale", "detail" },
    "study_quality":      { "score": 1-5, "rationale", "detail" },
    "methodology":        { "score": 1-5, "rationale", "detail" }
  },
  "consensus_label": "...",
  "methodology_audit": [{ "study", "type", "population", "methods", "critique", "score_contribution" }],
  "citations": ["PMID ..."],
  "name": "..."
}
```

The report uses `metrics.*.score` (the confidence panel), `mechanistic_impact.detail`, `study_quality.detail` and `methodology.detail`. The organ and connection data feed only the experimental tooling.
1 trait has no evidence entry.

## `ui_labels.json`

```json
{ "English": { "header_tag": "...", "cols_dash": [...], "introduction_education": { "section_1": "...", ... } },
  "Swedish": { ... } }
```

- Column-header arrays (`cols_dash`, `cols_active`, `cols_heritage`) must keep the same length and order as the DataFrame columns in `main.py`.
- `draw_table` colours cells by **header text** (`"Impact"/"Påverkan"`, `"Net"/"Netto"`). A new language must add its words there too.
- Swedish currently lacks `introduction_education`, so the Swedish report's intro pages are in English.

## `proxies.json`

```json
"rs1815739": { "target_gene": "ACTN3", "proxies": { "rs16832327": { "GG": "CC", "GC": "CT", ... } } }
```

## `muscle_logic_gates_db.json`

Groups of named rules whose `logic` is a string such as `"rs7903146 == 'TT'"`. `injectors-authenticators/cluster_checker.py` evaluates them with regex substitution. The main report doesn't use them.
