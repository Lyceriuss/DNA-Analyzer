import json
import os

# CONFIG
TRAITS_PATH = "config/snp_traits.json"
DEEP_DIVE_PATH = "config/deep_dive_content.json"

# CONTENT DATABASE
GENE_CONTENT = {
    # 1. SLC2A9 (GLUT9) - Uric Acid
    "SLC2A9": {
        "title": "Uric Acid Filtration",
        "badge_type": "RISK",
        "mechanisms": {
            "what": "SLC2A9 transports uric acid out of the blood and into the urine.",
            "how": "Your transporter is lazy. Uric acid stays in your bloodstream longer, crystalizing in joints (Gout) if levels get too high.",
            "yours": "Your Result: Poor Filtration (Gout Risk)."
        },
        "action": {
            "title": "Limit Purines",
            "body": "You must limit high-purine foods (beer, organ meats, shellfish) and stay hydrated to help your kidneys flush the excess."
        },
        "data_strength": {
            "title": "The Gout Shield",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "SLC2A9 transports uric acid out of the blood.",
                "how": "Your transporter works overtime, rapidly flushing uric acid from your system. You are virtually immune to gout caused by diet.",
                "yours": "Your Result: High Filtration Efficiency."
            },
            "action": {
                "title": "Dietary Freedom",
                "body": "You can enjoy rich foods (red meat, seafood) with very little risk of joint inflammation."
            }
        }
    },

    # 2. MYF5 - Muscle Growth
    "MYF5": {
        "title": "Muscle Hypertrophy",
        "badge_type": "RISK",
        "mechanisms": {
            "what": "MYF5 is a key regulator of muscle differentiation and growth.",
            "how": "You have the 'Endurance' profile. Your body resists adding bulk, preferring to stay lean and efficient. Gaining muscle mass requires significant caloric surplus.",
            "yours": "Your Result: 'Hardgainer' Profile."
        },
        "action": {
            "title": "High Volume Training",
            "body": "To trigger growth, you need higher volume and metabolic stress rather than just heavy load."
        },
        "data_strength": {
            "title": "The Builder Gene",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "MYF5 regulates muscle satellite cell activation.",
                "how": "Your body is primed for hypertrophy. When you lift, your satellite cells activate aggressively, adding muscle mass faster than the average person.",
                "yours": "Your Result: High Hypertrophy Potential."
            },
            "action": {
                "title": "Progressive Overload",
                "body": "Your body responds exceptionally well to heavy compound lifts. Feed the machine."
            }
        }
    },

    # 3. IRF4 - Sun Sensitivity
    "IRF4": {
        "title": "Solar Defense (Melanin)",
        "badge_type": "RISK",
        "mechanisms": {
            "what": "IRF4 controls melanin production and response to UV radiation.",
            "how": "You have the 'Celtic' variant. Your skin produces very little melanin and burns instantly. You do not tan; you damage.",
            "yours": "Your Result: High Sun Sensitivity."
        },
        "action": {
            "title": "Strict UV Block",
            "body": "Sunscreen is not optional. You accumulate DNA damage from UV exposure much faster than others."
        },
        "data_strength": {
            "title": "Solar Adaptation",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "IRF4 controls melanin production.",
                "how": "Your skin adapts quickly to UV exposure by producing protective melanin (tanning) rather than burning.",
                "yours": "Your Result: Low Sun Sensitivity."
            },
            "action": {
                "title": "Vitamin D Synthesis",
                "body": "You can safely tolerate moderate sun exposure to optimize Vitamin D levels without immediate burn risk."
            }
        }
    },

    # 4. LRP5 - Bone Density
    "LRP5": {
        "title": "Skeletal Integrity",
        "badge_type": "RISK",
        "mechanisms": {
            "what": "LRP5 signals bone cells to build minerals and density.",
            "how": "Your signaling is weak, leading to lower peak bone mass. This increases the risk of stress fractures and osteoporosis later in life.",
            "yours": "Your Result: Lower Bone Density."
        },
        "action": {
            "title": "Heavy Loading",
            "body": "Bones only get stronger under stress. You need axial loading (Squats/Deadlifts) to manually force bone mineralization."
        },
        "data_strength": {
            "title": "The Unbreakable",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "LRP5 signals bone cells to build density.",
                "how": "Your signaling is hyper-active. You naturally build extremely dense, heavy bones that are highly resistant to fracture.",
                "yours": "Your Result: High Bone Density."
            },
            "action": {
                "title": "Impact Sports",
                "body": "Your skeletal structure is well-suited for high-impact activities (MMA, Rugby, Running)."
            }
        }
    },

    # 5. HFE - Iron Absorption
    "HFE": {
        "title": "Iron Regulation",
        "badge_type": "RISK",
        "mechanisms": {
            "what": "HFE tells the gut when to stop absorbing iron.",
            "how": "Your stop sign is broken (Hemochromatosis Carrier). Your body keeps absorbing iron even when you are full, risking organ damage from iron overload.",
            "yours": "Your Result: Iron Overload Risk."
        },
        "action": {
            "title": "Monitor Ferritin",
            "body": "Donate blood regularly. It is the only way to manually remove excess iron from your system. Avoid iron supplements."
        },
        "data_strength": {
            "title": "Iron Balance",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "HFE tells the gut when to stop absorbing iron.",
                "how": "Your regulator works perfectly. You absorb exactly what you need and block the rest, preventing both anemia and toxicity.",
                "yours": "Your Result: Optimal Regulation."
            },
            "action": {
                "title": "Nutrient Synergy",
                "body": "You don't need to worry about limiting red meat or spinach; your body handles the intake intelligently."
            }
        }
    }
}

def complete_inject():
    # 1. Load Traits to Map Genes -> All RSIDs
    if not os.path.exists(TRAITS_PATH):
        print("❌ snp_traits.json not found!")
        return
    
    with open(TRAITS_PATH, 'r', encoding='utf-8') as f:
        traits = json.load(f)

    # 2. Map Gene Name -> LIST of RSIDs
    gene_map = {}
    for rsid, info in traits.items():
        # Clean Name: "SLC2A9 (GLUT9)" -> "SLC2A9"
        raw_name = info.get('gene', '')
        
        # Add exact match
        if raw_name not in gene_map: gene_map[raw_name] = []
        gene_map[raw_name].append(rsid)

        # Add split match (e.g. SLC2A9 from SLC2A9 (GLUT9))
        clean_name = raw_name.split('(')[0].strip()
        if clean_name not in gene_map: gene_map[clean_name] = []
        gene_map[clean_name].append(rsid)
        
        # Add parenthesis match (e.g. GLUT9 from SLC2A9 (GLUT9))
        if '(' in raw_name:
            alt_name = raw_name.split('(')[1].replace(')', '').strip()
            if alt_name not in gene_map: gene_map[alt_name] = []
            gene_map[alt_name].append(rsid)

    # 3. Load Deep Dive File
    if os.path.exists(DEEP_DIVE_PATH):
        with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
            deep_dive_data = json.load(f)
    else:
        deep_dive_data = {}

    # 4. Inject
    injected_count = 0
    for gene_key, content in GENE_CONTENT.items():
        target_rsids = gene_map.get(gene_key, [])
        
        if target_rsids:
            # Deduplicate RSIDs
            target_rsids = list(set(target_rsids))
            print(f"✅ {gene_key}: Injecting into {len(target_rsids)} RSIDs: {target_rsids}")
            for rsid in target_rsids:
                deep_dive_data[rsid] = content
                injected_count += 1
        else:
            print(f"⚠️ Gene '{gene_key}' not found in snp_traits.json (Check spelling?)")

    # 5. Save
    with open(DEEP_DIVE_PATH, 'w', encoding='utf-8') as f:
        json.dump(deep_dive_data, f, indent=4)

    print(f"\n🎉 Done. Updated {injected_count} deep dive entries.")

if __name__ == "__main__":
    complete_inject()