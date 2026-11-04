import os
import json


def _sorted(gt):
    return "".join(sorted(gt or ""))


def apply_proxies(dna_data, proxy_map_path="config/proxies.json"):
    """
    Fills library SNPs that are missing from a DNA file using co-inherited proxy SNPs that are present.
    Returns (dna_data, estimated) where estimated maps target rsID -> {proxy, note, note_sv, uncertain}.
    A target the file measures directly is never overwritten.
    """
    estimated = {}
    if not os.path.exists(proxy_map_path):
        return dna_data, estimated

    with open(proxy_map_path, 'r', encoding='utf-8') as f:
        proxy_config = json.load(f)

    for target_rsid, config in proxy_config.items():
        if target_rsid.startswith("_") or target_rsid in dna_data:
            continue
        for proxy_rsid, spec in config["proxies"].items():
            if proxy_rsid not in dna_data:
                continue
            raw = _sorted(dna_data[proxy_rsid])
            translated = spec["map"].get(raw)
            if not translated:
                continue  # unknown proxy genotype (no-call or unexpected allele): do not guess
            pct = f"{spec['concordance_eur']:.0%}"
            note = (config.get("confidence_note") or {}).get(translated) or \
                f"Estimated: this marker matches the measured SNP in {pct} of Europeans"
            note_sv = (config.get("confidence_note_sv") or {}).get(translated) or \
                f"Uppskattad: markören stämmer med den uppmätta SNP:n hos {pct} av européer"

            # A second marker can flag a reassuring result as uncertain
            unc = config.get("uncertain_if")
            uncertain = False
            if unc and translated == unc["when_result"] and unc["allele"] in (dna_data.get(unc["proxy"]) or ""):
                uncertain, note, note_sv = True, unc["note"], unc.get("note_sv", unc["note"])

            dna_data[target_rsid] = translated
            estimated[target_rsid] = {"proxy": proxy_rsid, "uncertain": uncertain,
                                      "note": f"{note} (via {proxy_rsid})", "note_sv": f"{note_sv} (via {proxy_rsid})"}
            print(f"🔄 Estimated {config.get('label', target_rsid)} from {proxy_rsid} ({raw}) -> {translated}"
                  + (" [uncertain]" if uncertain else ""))
            break
    return dna_data, estimated
