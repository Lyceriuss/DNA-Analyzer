import json
import os

# CONFIG
TRAITS_PATH = "config/snp_traits.json"
DEEP_DIVE_PATH = "config/deep_dive_content.json"

# TEXTBOOK-GRADE MECHANISMS (Fixed Syntax)
GENE_CONTENT = {
    # 1. VDR (Vitamin D)
    "VDR": {
        "title": "Immune & Calcium Signaling",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "VDR",
            "title": "The 'Silenced' Receptor",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "The Vitamin D Receptor (VDR) is a transcription factor. It enters the nucleus, binds to DNA, and acts as a 'Master Switch' for 900+ genes involved in immunity.",
                "how": "Your receptor has a structural shape that reduces binding affinity. Even with Vitamin D in your blood, the 'key' turns the lock slowly. This leads to weaker transcription of antimicrobial peptides, leaving your immune system slower to react.",
                "yours": "Your Result: Low Transcriptional Activity."
            },
            "action": {
                "title": "Force the Lock",
                "body": "Because your receptor binding is weak, you need higher blood concentrations of Vitamin D to achieve the same gene activation as a normal person. Aim for 60-80 ng/mL."
            }
        },
        "data_strength": {
            "gene": "VDR",
            "title": "The 'Amplified' Signal",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "The Vitamin D Receptor (VDR) forms a complex with the Retinoid-X Receptor (RXR) to bind directly to DNA.",
                "how": "Your receptor is highly sensitive. It creates a robust signal cascade even with moderate Vitamin D levels, resulting in aggressive production of natural antibiotics (cathelicidin).",
                "yours": "Your Result: High Transcriptional Sensitivity."
            },
            "action": {
                "title": "Immune Shield",
                "body": "Your robust VDR signaling provides a powerful baseline defense against respiratory infections."
            }
        }
    },

    # 2. UCP2 (Metabolism) - FIXED SYNTAX HERE
    "UCP2": {
        "title": "Mitochondrial Efficiency",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "UCP2",
            "title": "The 'Thrifty' Mitochondria",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "Mitochondria produce energy by pumping protons across a membrane to spin a turbine. UCP2 is a valve that usually lets protons skip the turbine to generate heat.",
                "how": "Your valve is sealed tight. Your mitochondria trap every single proton to make ATP (energy). While efficient for famine survival, today it means you store excess calories as fat rather than burning them as body heat.",
                "yours": "Your Result: High Storage Efficiency."
            },
            "action": {
                "title": "Cold Activation",
                "body": "You must manually force the valves open. Cold Thermogenesis (Ice Baths) forces the body to activate UCP1/UCP2 to prevent hypothermia, burning fat for heat."
            }
        },
        "data_strength": {
            "gene": "UCP2",
            "title": "The 'Leaky' Reactor",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "UCP2 acts as an 'Uncoupling Protein' in the inner mitochondrial membrane.",
                "how": "Your mitochondria are naturally 'leaky.' Instead of converting 100% of fuel into chemical energy (ATP), your cells allow a significant portion of protons to flow back into the matrix, releasing the energy as pure heat. This raises your Basal Metabolic Rate and protects against obesity.",
                "yours": "Your Result: High Thermogenesis (The Furnace)."
            },
            "action": {
                "title": "Carb Resilience",
                "body": "You can handle caloric surpluses better than most. Your body naturally upregulates heat production after large meals to dissipate the excess energy."
            }
        }
    },

    # 3. IRGM (Gut Health)
    "IRGM": {
        "title": "Gut Autophagy",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "IRGM",
            "title": "The 'Blind' Sentry",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "IRGM orchestrates 'Xenophagy'—the process where cells identify invading bacteria, wrap them in a membrane, and dissolve them.",
                "how": "Your targeting system is faulty. Your gut cells are slower to recognize intracellular pathogens. This allows bacteria to linger inside the gut lining, triggering chronic inflammation.",
                "yours": "Your Result: Impaired Bacterial Clearance."
            },
            "action": {
                "title": "Stimulate Autophagy",
                "body": "Since your baseline autophagy is low, you need lifestyle triggers. Fasting (16h+) and intense exercise are the strongest signals to manually activate the cellular cleanup crew."
            }
        },
        "data_strength": {
            "gene": "IRGM",
            "title": "The 'Iron' Gut",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "IRGM is the sniper of the immune system, specifically hunting intracellular threats in the gut lining.",
                "how": "Your targeting system is aggressive. When a pathogen enters a cell, IRGM instantly tags it for destruction. Your cells rapidly envelop and incinerate the threat, creating a sterile, resilient gut environment.",
                "yours": "Your Result: Rapid Pathogen Clearance."
            },
            "action": {
                "title": "Travel Confidence",
                "body": "You have a robust biological defense against food poisoning and foreign bacteria."
            }
        }
    },

    # 4. MC4R (Appetite)
    "MC4R": {
        "title": "Appetite Regulation",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "MC4R",
            "title": "The 'Silent' Stop Signal",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "MC4R neurons in the hypothalamus receive signals from body fat (Leptin) to tell you 'Stop Eating.'",
                "how": "Your receptor has a 'blunted' response. Even when fat cells signal fullness, the brain only hears a whisper. You require significantly more food to trigger the neural sensation of satisfaction.",
                "yours": "Your Result: Reduced Satiety Signaling."
            },
            "action": {
                "title": "Volume Eating",
                "body": "You cannot rely on calories to feel full; you need physical stretch. Eat massive volumes of low-calorie fiber (greens) to physically stretch the stomach and force the signal."
            }
        },
        "data_strength": {
            "gene": "MC4R",
            "title": "The 'Precision' Appetite",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "MC4R integrates hormonal signals from the gut and fat tissue to regulate energy balance.",
                "how": "Your receptors are highly tuned. As soon as your caloric needs are met, MC4R fires a potent 'Stop' signal. You naturally maintain leanness because overeating feels physically uncomfortable.",
                "yours": "Your Result: High Precision Satiety."
            },
            "action": {
                "title": "Intuitive Eating",
                "body": "Diet rules are unnecessary for you. Your biology is a better calorie counter than any app."
            }
        }
    },

    # 5. F2 (Clotting)
    "F2": {
        "title": "Cardiovascular Clotting",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "F2 (Prothrombin)",
            "title": "The 'Thick' Blood",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "Prothrombin is the precursor to Thrombin, the enzyme that converts liquid blood into a solid fibrin clot.",
                "how": "You carry the G20210A mutation. This causes your liver to overproduce Prothrombin mRNA. You have 'too much glue' circulating in your veins. Your blood coagulates with very little provocation.",
                "yours": "Your Result: Prothrombin Overproduction."
            },
            "action": {
                "title": "Circulation Protocol",
                "body": "Stasis is death. Never sit for more than 2 hours without moving. Hydration is non-negotiable to keep viscosity low."
            }
        },
        "data_strength": {
            "gene": "F2 (Prothrombin)",
            "title": "The 'Optimal' Flow",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "The coagulation cascade balances the need to stop bleeding with the need to keep blood flowing.",
                "how": "Your Prothrombin levels are perfectly regulated. You have the exact right amount of clotting factor to seal a wound instantly, but not enough to trigger random clots during travel.",
                "yours": "Your Result: Optimal Hemodynamics."
            },
            "action": {
                "title": "Vascular Health",
                "body": "You have a natural protection against the clotting risks associated with aging and travel."
            }
        }
    },

    # 6. NOS3 (Nitric Oxide)
    "NOS3": {
        "title": "Blood Flow & Pressure",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "NOS3",
            "title": "The 'Constricted' Vessel",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "NOS3 produces Nitric Oxide (NO), the gas that relaxes blood vessels to lower pressure.",
                "how": "Your production is genetically low. Your vessels tend to stay tight (vasoconstricted). This raises blood pressure and reduces the 'pump' and nutrient delivery during exercise.",
                "yours": "Your Result: Low Nitric Oxide."
            },
            "action": {
                "title": "Nitrate Loading",
                "body": "You need raw materials. Consume beets, arugula, or Citrulline supplements to provide the nitrates your body needs to force those vessels open."
            }
        },
        "data_strength": {
            "gene": "NOS3",
            "title": "The 'Hydraulic' System",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "NOS3 produces Nitric Oxide to dilate blood vessels on demand.",
                "how": "Your blood vessels dilate instantly upon demand. You deliver oxygen and nutrients to muscles efficiently, giving you a natural endurance advantage and excellent blood pressure regulation.",
                "yours": "Your Result: High Nitric Oxide."
            },
            "action": {
                "title": "Endurance Sport",
                "body": "You are built for output. Cycling, running, and high-rep training suit your physiology perfectly."
            }
        }
    }
}

def scientific_overhaul():
    print("🧬 Injecting Textbook-Grade Mechanisms...")
    
    # 1. Load Traits
    if not os.path.exists(TRAITS_PATH):
        print("❌ snp_traits.json not found!")
        return
    with open(TRAITS_PATH, 'r', encoding='utf-8') as f:
        traits = json.load(f)

    # 2. Build Smart Map
    gene_map = {}
    for rsid, info in traits.items():
        raw_name = info.get('gene', '')
        clean_name = raw_name.split('(')[0].strip()
        if clean_name not in gene_map: gene_map[clean_name] = []
        gene_map[clean_name].append(rsid)

    # 3. Load Deep Dives
    if os.path.exists(DEEP_DIVE_PATH):
        with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
            deep_dive_data = json.load(f)
    else:
        deep_dive_data = {}

    # 4. Inject
    count = 0
    for gene_key, content in GENE_CONTENT.items():
        target_rsids = gene_map.get(gene_key, [])
        if target_rsids:
            print(f"   -> Rewriting {gene_key}...")
            for rsid in target_rsids:
                content['data_risk']['gene'] = gene_key
                content['data_strength']['gene'] = gene_key
                deep_dive_data[rsid] = content
                count += 1
        else:
            print(f"⚠️ Gene {gene_key} not found in database.")

    # 5. Save
    with open(DEEP_DIVE_PATH, 'w', encoding='utf-8') as f:
        json.dump(deep_dive_data, f, indent=4)

    print(f"\n✅ Overhaul Complete. Updated {count} entries with deep science.")

if __name__ == "__main__":
    scientific_overhaul()