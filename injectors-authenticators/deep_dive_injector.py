import json
import os

# CONFIG
DEEP_DIVE_PATH = "config/deep_dive_content.json"
TRAITS_PATH = "config/snp_traits.json"

# THE FINAL 6 (Textbook Depth)
FINISH_CONTENT = {
    # --- SENSORY & APPEARANCE ---
    "HERC2": {
        "title": "Pigmentation Switch",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "HERC2",
            "title": "The 'Blue' Switch",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "HERC2 acts as a regulatory switch for the OCA2 gene. It determines whether the pigment factories in your iris produce brown melanin or remain switched off (blue).",
                "how": "You carry the recessive 'Blue' variant. Your HERC2 gene turns off OCA2 expression in the eye. You produce almost no melanin in the iris. While aesthetically unique, this lack of pigment means your eyes lack the natural sunglasses that brown-eyed people have. You are significantly more sensitive to glare and retinal UV damage.",
                "yours": "Your Result: Melanin Switch OFF (Blue/Green)."
            },
            "action": { "title": "Retinal Shielding", "body": "You cannot filter blue light effectively. You need polarized sunglasses outdoors and blue-light blocking glasses for computer work to prevent macular strain." }
        },
        "data_strength": {
            "gene": "HERC2",
            "title": "The 'Melanin' Shield",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "Active HERC2 signaling keeps the melanin factories running, providing a natural shield against radiation.",
                "how": "Your HERC2 switch is ON. It drives robust expression of OCA2, filling your iris with dense melanin (Brown eyes). This pigment absorbs scattered light and UV radiation, giving you superior visual acuity in bright environments and a lower risk of macular degeneration.",
                "yours": "Your Result: Melanin Switch ON (Brown)."
            },
            "action": { "title": "Visual Endurance", "body": "Your eyes are built for bright sunlight. You likely suffer less from glare and eye fatigue than your light-eyed peers." }
        }
    },
    "OR6A2": {
        "title": "Aldehyde Perception",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "OR6A2",
            "title": "The 'soap' Taster",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "Olfactory Receptor 6A2 is a chemosensor in the nose specifically tuned to detect aldehydes—organic compounds found in soap, bugs, and cilantro (Coriandrum sativum).",
                "how": "Your receptor has a structural mutation that hyper-binds to (E)-2-decenal, the specific aldehyde in cilantro. Instead of tasting 'fresh' or 'herbal,' your brain interprets the signal as 'soap' or 'dirt.' This is not picky eating; it is a genetic chemosensory divergent perception.",
                "yours": "Your Result: Hyper-Sensitive to Aldehydes."
            },
            "action": { "title": "Avoidance", "body": "There is no 'cure' for this receptor binding. Avoid cilantro. Interestingly, crushing the herb accelerates the breakdown of these aldehydes, sometimes making it tolerable in pesto or cooked sauces." }
        },
        "data_strength": {
            "gene": "OR6A2",
            "title": "The 'Herbal' Palate",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "Standard receptor affinity allows for the detection of complex herbal notes without chemical distortion.",
                "how": "Your receptors bind aldehydes normally. You perceive cilantro as fresh, citrusy, and herbal. You are able to enjoy a wider range of culinary flavors without the interference of the 'soapy' artifact that plagues others.",
                "yours": "Your Result: Normal Perception."
            },
            "action": { "title": "Culinary Range", "body": "Your palate is versatile. Use fresh herbs liberally to increase the polyphenol content of your diet." }
        }
    },
    "OR2M7": {
        "title": "Pungent Perception",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "OR2M7",
            "title": "The 'Strong' Nose",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "OR2M7 is another olfactory receptor linked to the perception of strong, pungent odors, often interacting with the same pathway as the cilantro-soap gene.",
                "how": "Your variant is linked to heightened sensitivity to specific volatile organic compounds. You may be 'hyperosmic'—having a sense of smell that is too acute for comfort. Strong perfumes, gasoline, or certain spices may trigger headaches or nausea because your brain receives an amplified signal.",
                "yours": "Your Result: Hyper-Acute Smell."
            },
            "action": { "title": "Scent Free", "body": "Your home environment should be fragrance-free. Use un-scented laundry detergents to prevent chronic low-level neural irritation." }
        },
        "data_strength": {
            "gene": "OR2M7",
            "title": "The 'Balanced' Nose",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "Balanced olfactory signaling allows for the detection of danger signals (smoke/rot) without overwhelming the nervous system.",
                "how": "Your olfactory threshold is standard. You can smell dinner cooking or a gas leak, but you aren't incapacitated by someone wearing too much cologne in an elevator. Your sensory processing filter is working correctly.",
                "yours": "Your Result: Normal Sensitivity."
            },
            "action": { "title": "Adaptability", "body": "You can function well in varied environments without being distracted by background odors." }
        }
    },

    # --- STRUCTURE & IMMUNITY ---
    "COL18A1": {
        "title": "Vascular Structure",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "COL18A1",
            "title": "The 'Eye' Integrity",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "Type XVIII Collagen is unique because it contains 'Endostatin,' a potent inhibitor of new blood vessel growth. It is critical for maintaining the structure of the eye.",
                "how": "Your variant is associated with reduced structural integrity in the basement membranes of the eye. This is a risk factor for myopia (nearsightedness) and potentially issues with retinal vessel overgrowth. Your eyes may physically elongate faster during childhood, blurring distance vision.",
                "yours": "Your Result: Reduced Membrane Stability."
            },
            "action": { "title": "Visual Hygiene", "body": "You must practice the '20-20-20' rule. Every 20 minutes, look at something 20 feet away. Your eye structure is malleable and needs breaks from close-up screen tension." }
        },
        "data_strength": {
            "gene": "COL18A1",
            "title": "The 'Stable' Eye",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "Robust Type XVIII Collagen ensures the eye maintains its spherical shape and regulates angiogenesis properly.",
                "how": "Your basement membranes are tough. Your eyes resist the elongation that causes nearsightedness. You likely have better baseline visual acuity and a lower risk of neovascular eye diseases later in life.",
                "yours": "Your Result: High Structural Stability."
            },
            "action": { "title": "20/20 Potential", "body": "Your eyes are structurally sound. Protect them from UV light to maintain this advantage." }
        }
    },
    "FUT8": {
        "title": "Protein Glycosylation",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "FUT8",
            "title": "The 'Immune' Signal",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "Fucosyltransferase 8 adds a specific sugar molecule (fucose) to proteins, a process called 'Core Fucosylation.' This acts like a shipping label, telling growth factor receptors and immune antibodies how to function.",
                "how": "Your enzyme activity is altered. This affects how your immune cells (IgG antibodies) bind to their targets. It can lead to a 'hyper-reactive' immune state or altered sensitivity to growth factors like TGF-beta. This is often linked to higher susceptibility to autoimmune flares or tissue fibrosis.",
                "yours": "Your Result: Altered Protein Tagging."
            },
            "action": { "title": "Inflammation Control", "body": "Since your protein 'tags' are different, your immune system is more prone to confusion. An anti-inflammatory diet (Autoimmune Protocol - AIP) can help reduce the noise in the system." }
        },
        "data_strength": {
            "gene": "FUT8",
            "title": "The 'Precision' Signal",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "Proper core fucosylation ensures that receptors (like EGFR) and antibodies function with maximum efficiency.",
                "how": "Your FUT8 enzyme tags proteins correctly. Your growth factor signaling is balanced—neither too weak nor too aggressive. Your immune antibodies bind to viruses tightly but release healthy tissue. This is a marker of deep cellular communication health.",
                "yours": "Your Result: Optimal Protein Tagging."
            },
            "action": { "title": "Cellular Health", "body": "Your cells talk to each other clearly. Maintain this with a low-sugar diet, as excess sugar can interfere with glycosylation processes." }
        }
    },
    "ZEB2": {
        "title": "Neural Development",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "ZEB2",
            "title": "The 'Sensitive' Wire",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "ZEB2 is a transcription factor that orchestrates the development of the nervous system and the migration of neural crest cells.",
                "how": "Your variant is linked to heightened neural sensitivity. While not pathological, you likely have a lower threshold for pain perception and sensory input. Your nervous system is 'tuned high.' You may find tags on clothes irritating or loud noises overwhelming faster than others.",
                "yours": "Your Result: High Sensory Gain."
            },
            "action": { "title": "Nervous System Regulation", "body": "You need 'Sensory Dieting.' Limit exposure to chaotic environments. Weighted blankets and deep pressure therapy can help calm your hyper-tuned nervous system." }
        },
        "data_strength": {
            "gene": "ZEB2",
            "title": "The 'Robust' Wire",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "Optimal ZEB2 signaling creates a robust, insulated nervous system.",
                "how": "Your neural development is solid. You have a high threshold for pain and sensory overload. You can function effectively in chaotic, loud, or physically uncomfortable environments without your nervous system getting fried.",
                "yours": "Your Result: High Sensory Threshold."
            },
            "action": { "title": "Grind Capacity", "body": "You are built to endure. You can handle physical and sensory stress that would exhaust a more sensitive person." }
        }
    }
}

def inject_finish_line():
    print("🏁 Injecting FINISH LINE Content (Textbook Depth)...")
    
    if not os.path.exists(TRAITS_PATH):
        print("❌ snp_traits.json not found!")
        return
    with open(TRAITS_PATH, 'r', encoding='utf-8') as f:
        traits = json.load(f)

    if os.path.exists(DEEP_DIVE_PATH):
        with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
            deep_dive_data = json.load(f)
    else:
        deep_dive_data = {}

    # Smart Map
    gene_map = {}
    for rsid, info in traits.items():
        raw_name = info.get('gene', '')
        names_to_map = [raw_name, raw_name.split('(')[0].strip()]
        if '(' in raw_name: names_to_map.append(raw_name.split('(')[1].replace(')', '').strip())
        for n in names_to_map:
            if n not in gene_map: gene_map[n] = []
            gene_map[n].append(rsid)

    # Inject
    count = 0
    for gene_key, content in FINISH_CONTENT.items():
        target_rsids = gene_map.get(gene_key, [])
        if target_rsids:
            print(f"   -> Upgrading {gene_key}...")
            for rsid in target_rsids:
                content['data_risk']['gene'] = gene_key
                content['data_strength']['gene'] = gene_key
                deep_dive_data[rsid] = content
                count += 1
                
                # Verify
                full_text = content['data_risk']['mechanisms']['how'] + content['data_risk']['action']['body'] + content['data_risk']['mechanisms']['what']
                if len(full_text) < 350:
                     print(f"      ⚠️ WARNING: {gene_key} is short")
                else:
                     print(f"      ✅ Verified: {len(full_text)} chars")

    with open(DEEP_DIVE_PATH, 'w', encoding='utf-8') as f:
        json.dump(deep_dive_data, f, indent=4)

    print(f"\n✅ Finish Line Injection Complete. Updated {count} entries.")

if __name__ == "__main__":
    inject_finish_line()