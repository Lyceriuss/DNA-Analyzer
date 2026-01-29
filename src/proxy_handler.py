import os
import json

def apply_proxies(dna_data, proxy_map_path="config/proxies.json"):
    if not os.path.exists(proxy_map_path):
        return dna_data

    with open(proxy_map_path, 'r') as f:
        proxy_config = json.load(f)

    for target_rsid, config in proxy_config.items():
            if target_rsid not in dna_data:
                # Look through available proxies for this target
                for proxy_rsid, translation in config["proxies"].items():
                    if proxy_rsid in dna_data:
                        raw_proxy_gt = dna_data[proxy_rsid]
                        
                        # Perform the swap: e.g., GG becomes CC
                        translated_gt = translation.get(raw_proxy_gt, raw_proxy_gt)
                        
                        dna_data[target_rsid] = translated_gt
                        print(f"🔄 Translated Proxy: {proxy_rsid}({raw_proxy_gt}) -> {target_rsid}({translated_gt})")
                        break
    return dna_data