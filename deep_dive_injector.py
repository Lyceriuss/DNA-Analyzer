import json
import os

# CONFIG
DEEP_DIVE_PATH = "config/deep_dive_content.json"
TRAITS_PATH = "config/snp_traits.json"

# THE "HEAVY" CONTENT PACK (Min 400 chars per entry)
UPGRADE_CONTENT = {
    # 1. CACNA1C (Brain Voltage)
    "CACNA1C": {
        "title": "Neuronal Excitability",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "CACNA1C",
            "title": "The 'Live Wire' Circuit",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "CACNA1C encodes the Alpha-1C subunit of the voltage-dependent calcium channel (Cav1.2). This channel acts as the gatekeeper for calcium entry into neurons, which determines how easily a brain cell fires an electrical signal .",
                "how": "You carry the risk variant, which makes these channels 'leaky' and hyper-sensitive to voltage changes. Your neurons fire action potentials too easily. While this facilitates rapid associative thinking (creativity), it lowers the threshold for anxiety and racing thoughts. Your brain struggles to 'turn off' because the electrical potential remains too close to the firing threshold.",
                "yours": "Your Result: Hyper-Excitable Signaling."
            },
            "action": {
                "title": "Chemical Insulation",
                "body": "You need to physically block the influx of calcium to calm the system. Magnesium Threonate is the only form of magnesium that effectively crosses the blood-brain barrier to bind to these channels and dampen the electrical noise. Darkness therapy (reducing light input) also lowers the voltage load on the brain."
            }
        },
        "data_strength": {
            "gene": "CACNA1C",
            "title": "The 'Insulated' Mind",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "CACNA1C regulates the threshold at which neurons fire action potentials in response to stimuli.",
                "how": "Your channels are tightly regulated. Your neurons require a strong, clear signal to fire. This creates a high signal-to-noise ratio in the brain. You are naturally buffered against sensory overload, anxiety, and panic because your biology refuses to react to 'noise.' You maintain cognitive clarity in high-pressure environments where others become overwhelmed.",
                "yours": "Your Result: Stable Neural Signaling."
            },
            "action": {
                "title": "High-Stakes Performance",
                "body": "Your neurobiology is suited for crisis management. Because you do not over-react to stimuli, you can process information logically when the emotional temperature is high. Lean into roles that require 'ice in the veins.'"
            }
        }
    },

    # 2. MTR (Methylation/B12)
    "MTR": {
        "title": "B12 recycling",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "MTR",
            "title": "The 'B12' Bottleneck",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "Methionine Synthase (MTR) is the critical enzyme that recycles Homocysteine back into Methionine. To do this, it requires Vitamin B12 (Methylcobalamin) as a mandatory cofactor to pass the methyl group.",
                "how": "Your enzyme has a weak binding affinity for B12. Even if your blood levels of B12 appear normal, your enzyme struggles to grab it and use it. This halts the methylation cycle, causing inflammatory Homocysteine to pool in the blood while your DNA repair mechanisms starve for Methionine. This often manifests as fatigue and poor stress tolerance.",
                "yours": "Your Result: Reduced B12 Utilization."
            },
            "action": {
                "title": "Methylcobalamin Loading",
                "body": "You cannot use standard Cyanocobalamin (cheap B12). You need pre-methylated B12 (Methylcobalamin) or Adenosylcobalamin. Liquid or sublingual forms are essential to bypass gut absorption issues and flood the enzyme with enough cofactor to force it to work."
            }
        },
        "data_strength": {
            "gene": "MTR",
            "title": "The 'Efficient' Recycler",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "MTR drives the final step of the methylation cycle, regenerating Methionine for protein synthesis and DNA repair.",
                "how": "Your enzyme functions at peak velocity. You scavenge Vitamin B12 efficiently from dietary sources and rapidly convert toxic Homocysteine into useful fuel. This ensures a constant supply of SAMe (the universal methyl donor), providing a robust biochemical foundation for mood stability and cellular repair.",
                "yours": "Your Result: High Enzymatic Efficiency."
            },
            "action": {
                "title": "Metabolic Stability",
                "body": "Your efficient recycling system protects your arteries from inflammation and ensures your neurotransmitters are produced at a steady rate. You likely have high natural energy levels and good recovery from stress."
            }
        }
    },

    # 3. HFE (Iron)
    "HFE": {
        "title": "Iron Homeostasis",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "HFE",
            "title": "The 'Unregulated' Absorption",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "HFE is the sensor protein that detects iron levels in the body and tells the liver to produce Hepcidin, the hormone that blocks iron absorption.",
                "how": "Your sensor is broken (Hemochromatosis variant). Your body thinks it is starving for iron even when it is overloaded. Your gut continues to absorb iron from food unchecked. This excess iron cannot be excreted; it rusts (oxidizes) in your liver, heart, and joints, causing massive oxidative damage and organ failure over decades.",
                "yours": "Your Result: Hyper-Absorption (Iron Overload)."
            },
            "action": {
                "title": "Therapeutic Phlebotomy",
                "body": "Diet changes are not enough. You must physically remove the iron. Regular blood donation (every 8-12 weeks) is the only way to offload the excess. You must also avoid Vitamin C supplements with meals, as Vitamin C increases iron absorption by up to 400%."
            }
        },
        "data_strength": {
            "gene": "HFE",
            "title": "The 'Calibrated' System",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "HFE acts as the master thermostat for iron, ensuring you have enough to carry oxygen but not enough to cause toxicity.",
                "how": "Your HFE gene signals perfectly. When iron stores are sufficient, you produce Hepcidin to block further absorption. When stores drop, you downregulate Hepcidin to absorb more. This tight regulation protects you from both Anemia (low energy) and Hemochromatosis (organ damage).",
                "yours": "Your Result: Optimal Iron Regulation."
            },
            "action": {
                "title": "Nutrient Synergy",
                "body": "You have dietary freedom regarding iron. Your body will take what it needs and discard the rest. Focus on pairing iron with Copper (dark chocolate/liver) to ensure the iron you absorb is properly loaded into red blood cells."
            }
        }
    },

    # 4. TCF7L2 (Insulin)
    "TCF7L2": {
        "title": "Pancreatic Function",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "TCF7L2",
            "title": "The 'Fatigued' Pancreas",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "TCF7L2 regulates the expression of Proinsulin in the beta-cells of the pancreas. It determines the magnitude of the insulin spike after a meal.",
                "how": "You have the high-risk 'T' allele. Your pancreas is slow to react to blood sugar spikes. It produces less insulin in the critical 'first phase' response . Over time, this forces the pancreas to work harder, leading to beta-cell burnout. This is the single strongest genetic predictor for Type 2 Diabetes.",
                "yours": "Your Result: Impaired Insulin Secretion."
            },
            "action": {
                "title": "The Walking Cure",
                "body": "Since your pancreas is slow, you must use your muscles to clear the sugar. A 15-minute walk immediately after eating engages the GLUT4 transporters in your legs, sucking glucose out of the blood without needing high insulin levels. This saves your pancreas from burnout."
            }
        },
        "data_strength": {
            "gene": "TCF7L2",
            "title": "The 'Iron' Pancreas",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "TCF7L2 ensures a rapid and robust release of insulin the moment glucose enters the bloodstream.",
                "how": "Your genotype allows for a sharp, precise insulin response. You clear blood sugar spikes rapidly, preventing the glycation damage that ages skin and organs. Your beta-cells are highly resilient, giving you a massive genetic buffer against metabolic disease even in the modern food environment.",
                "yours": "Your Result: Robust Insulin Secretion."
            },
            "action": {
                "title": "Carb Loading",
                "body": "You are metabolically flexible. You can utilize carbohydrates for high-intensity athletic recovery far more effectively than the average person. Post-workout carbs will be driven directly into muscle tissue rather than lingering in the blood."
            }
        }
    },

    # 5. MC4R (Appetite)
    "MC4R": {
        "title": "Satiety Signaling",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "MC4R",
            "title": "The 'Silent' Stop Signal",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "The Melanocortin 4 Receptor (MC4R) is the primary 'satiety switch' in the hypothalamus of the brain. It receives signals from Leptin (body fat) and Insulin to tell you to stop eating.",
                "how": "Your receptor has a structural bluntness. Even when your stomach is physically full and your fat cells are signaling 'enough,' the MC4R neuron fires weakly. You do not get the 'click' of satisfaction that others feel. This leads to chronic overeating because you are chasing a feeling of fullness that is biochemically muffled.",
                "yours": "Your Result: Reduced Satiety Signaling."
            },
            "action": {
                "title": "Mechanoreceptor Hack",
                "body": "You cannot rely on chemical satiety; you need mechanical satiety. You must trigger the stretch receptors in your stomach. Eat massive volumes of low-calorie density food (leafy greens, huge salads, fibrous veg) to physically stretch the stomach wall and force the brain to register fullness."
            }
        },
        "data_strength": {
            "gene": "MC4R",
            "title": "The 'Precision' Regulator",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "MC4R integrates metabolic signals to tightly regulate energy intake and expenditure.",
                "how": "Your receptor is highly sensitive. As soon as your caloric needs are met, MC4R fires a potent 'Stop' signal that makes food suddenly unappealing. You naturally maintain leanness because overeating feels physically uncomfortable or even nauseating to you. You are naturally protected against obesity.",
                "yours": "Your Result: High Precision Satiety."
            },
            "action": {
                "title": "Intuitive Eating",
                "body": "Diet rules are unnecessary for you. Your biology is a better calorie counter than any app. If you are not hungry, do not eat. Trust your natural aversion to over-stuffing yourself."
            }
        }
    },

    # 6. VDR (Vitamin D)
    "VDR": {
        "title": "Vitamin D Receptor",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "VDR",
            "title": "The 'Silenced' Receptor",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "The Vitamin D Receptor (VDR) is not just a passive dock; it is a nuclear transcription factor. It must bind to Vitamin D, enter the nucleus, and unlock DNA to turn on 900+ genes involved in immunity and bone repair.",
                "how": "Your receptor (likely Taq1 or Bsm1 variant) has a shape change that reduces its binding efficiency. Even with normal Vitamin D levels in your blood, the 'key' turns the lock very slowly. This results in weak gene expression, leaving your immune system sluggish and your bones less able to mineralize.",
                "yours": "Your Result: Low Transcriptional Efficiency."
            },
            "action": {
                "title": "Force the Lock",
                "body": "Standard dosing is not enough. You need to flood the system. You likely need blood levels of 60-80 ng/mL (higher than the standard 30) to achieve the same genetic activation as a normal person. Take Vitamin D3 with K2 and a fatty meal (Avocado) to maximize absorption."
            }
        },
        "data_strength": {
            "gene": "VDR",
            "title": "The 'Amplified' Signal",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "VDR forms a complex with RXR (Retinoid X Receptor) to activate the 'Genome Defense' program.",
                "how": "Your receptor is hypersensitive. It creates a robust signal cascade even with moderate sun exposure. You aggressively produce cathelicidins (natural antibiotics) and absorb calcium efficiently. This gives you a 'Teflon' immune system that repels respiratory viruses and maintains bone density with ease.",
                "yours": "Your Result: High Transcriptional Sensitivity."
            },
            "action": {
                "title": "Immune Shield",
                "body": "Your robust VDR signaling provides a powerful baseline defense. Moderate sun exposure is likely all you need to maintain a super-charged immune response."
            }
        }
    },

    # 7. NOS3 (Nitric Oxide)
    "NOS3": {
        "title": "Endothelial Function",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "NOS3",
            "title": "The 'Constricted' Vessel",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "Endothelial Nitric Oxide Synthase (NOS3) produces the gas Nitric Oxide (NO), which signals the smooth muscle around your arteries to relax and widen (vasodilation).",
                "how": "You produce less enzyme (Glu298Asp variant). Your arteries tend to stay tight and constricted. This raises your baseline blood pressure and limits the delivery of oxygen and nutrients to muscles during exercise. You likely don't get a 'pump' in the gym easily and may have colder hands and feet.",
                "yours": "Your Result: Low Nitric Oxide Production."
            },
            "action": {
                "title": "Nitrate Loading",
                "body": "You must provide the raw materials to force the vessels open. Consume high-nitrate foods like Beets, Arugula, and Spinach. Supplementing with L-Citrulline or Agmatine can also bypass the enzymatic bottleneck to restore blood flow."
            }
        },
        "data_strength": {
            "gene": "NOS3",
            "title": "The 'Hydraulic' System",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "NOS3 maintains the flexibility and responsiveness of the entire vascular system.",
                "how": "Your vessels dilate instantly upon demand. When you exercise or get stressed, your NOS3 enzyme floods the arteries with Nitric Oxide, dropping resistance and delivering massive amounts of oxygen to tissues. This is the genetic signature of elite endurance athletes and those with naturally healthy blood pressure.",
                "yours": "Your Result: High Nitric Oxide Production."
            },
            "action": {
                "title": "Endurance Capacity",
                "body": "You are built for output. Your cardiovascular system is highly efficient. Activities like running, cycling, or high-rep training suit your physiology perfectly."
            }
        }
    },

    # 8. IRGM (Gut Health)
    "IRGM": {
        "title": "Crohn's & Autophagy",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "IRGM",
            "title": "The 'Blind' Sentry",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "IRGM coordinates 'Xenophagy'—a specialized form of autophagy where cells identify invasive bacteria, wrap them in a membrane, and dissolve them with acid.",
                "how": "Your targeting system is faulty. Your gut lining cells struggle to recognize intracellular pathogens (like bad E. Coli). This allows bacteria to survive and replicate *inside* your gut wall, triggering chronic, low-grade inflammation that can eventually lead to Crohn's Disease or IBS.",
                "yours": "Your Result: Impaired Pathogen Clearance."
            },
            "action": {
                "title": "Stimulate Autophagy",
                "body": "Since your baseline autophagy is low, you need strong lifestyle triggers. Intermittent Fasting (16h+) is the most powerful signal to turn on the cleanup crew. Vitamin D is also critical, as it upregulates IRGM expression manually."
            }
        },
        "data_strength": {
            "gene": "IRGM",
            "title": "The 'Iron' Gut",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "IRGM is the sniper of the mucosal immune system, hunting down threats before they can cause inflammation.",
                "how": "Your targeting system is aggressive. When a pathogen touches your gut lining, IRGM instantly tags it for destruction. Your cells envelop and incinerate the threat before it can establish a foothold. You have a 'cast iron' stomach and are highly resistant to food poisoning and gut inflammation.",
                "yours": "Your Result: Rapid Pathogen Clearance."
            },
            "action": {
                "title": "Travel Confidence",
                "body": "You have a robust biological defense against foreign bacteria. Your gut maintains a sterile, healthy barrier with very little effort."
            }
        }
    },

    # 9. CDKN2A (Cellular Aging)
    "CDKN2A": {
        "title": "Tumor Suppression",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "CDKN2A",
            "title": "The 'Weak' Brake",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "CDKN2A produces the p16 protein, which acts as the 'Emergency Brake' for the cell cycle. If a cell has damaged DNA, p16 forces it to stop dividing and enter senescence (retirement).",
                "how": "Your brake pads are worn. Your cells are less sensitive to the 'Stop' signal. This allows cells with DNA mutations to keep dividing rather than stopping. This specific variant is strongly linked to a higher risk of Melanoma because skin cells damaged by UV light fail to arrest their growth.",
                "yours": "Your Result: Reduced Tumor Suppression."
            },
            "action": {
                "title": "UV Vigilance",
                "body": "This is your primary defense against skin cancer. You must be vigilant with sunscreen. Internally, you need to rely on Autophagy (Fasting) to clear out the senescent cells that your CDKN2A gene failed to catch."
            }
        },
        "data_strength": {
            "gene": "CDKN2A",
            "title": "The 'Terminator' Mechanism",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "CDKN2A regulates the G1/S checkpoint of the cell cycle, ensuring only perfect DNA is replicated.",
                "how": "You have a robust surveillance system. Your body aggressively halts the division of any cell showing the slightest sign of instability. This 'Zero Tolerance' policy preserves the genomic integrity of your tissues and provides a powerful shield against cancer and aging.",
                "yours": "Your Result: High Tumor Suppression."
            },
            "action": {
                "title": "Cellular Integrity",
                "body": "Your body is excellent at quality control. Support this system by minimizing oxidative stress (toxins, burnt food) so your surveillance system doesn't get overwhelmed."
            }
        }
    },

    # 10. GLUT9 / SLC2A9 (Uric Acid)
    "SLC2A9": {
        "title": "Uric Acid Transport",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "SLC2A9",
            "title": "The 'Hoarding' Transporter",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "SLC2A9 encodes the GLUT9 transporter, the primary gatekeeper in the kidney that decides whether to pee out Uric Acid or put it back into the blood.",
                "how": "Your transporter is hyper-active. It aggressively reabsorbs uric acid back into the bloodstream. This keeps your serum levels chronically near the saturation point. You are a 'Non-Excretor.' Even small amounts of fructose or purines can spike your levels enough to cause Gout crystals to form.",
                "yours": "Your Result: High Reabsorption Rate."
            },
            "action": {
                "title": "Alkalize & Dilute",
                "body": "Hydration is physics: more water equals lower saturation. You must also limit Fructose (sugar) strictly, as fructose metabolism generates uric acid as a byproduct. Tart Cherry extract is highly effective for your genotype."
            }
        },
        "data_strength": {
            "gene": "SLC2A9",
            "title": "The 'Flush' Phenotype",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "SLC2A9 maintains the balance of Uric Acid, which acts as an antioxidant at normal levels but a toxin at high levels.",
                "how": "Your variant creates a 'loose' gate. Your kidneys dump uric acid into the urine with exceptional efficiency. You maintain naturally low serum urate levels, making you virtually immune to dietary-induced Gout and protecting your blood vessels from urate-induced hypertension.",
                "yours": "Your Result: Rapid Excretion."
            },
            "action": {
                "title": "Dietary Freedom",
                "body": "While others must fear red meat and seafood, your kidneys are efficient enough to clear the purine load. You have a massive biological buffer against inflammation."
            }
        }
    },
    
    # 11. F2 (Clotting)
    "F2": {
        "title": "Coagulation Factors",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "F2",
            "title": "The 'Thick' Blood",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "Prothrombin (Factor II) is the precursor protein that gets cleaved into Thrombin, the enzyme that turns liquid blood into a solid gel (clot).",
                "how": "You carry the G20210A mutation. This is a gain-of-function mutation in the mRNA, causing your liver to overproduce Prothrombin. You have 30% more clotting factor floating in your blood than normal. This turns your blood into 'sludge,' ready to clot at the slightest provocation (like sitting on a plane).",
                "yours": "Your Result: Prothrombin Overproduction."
            },
            "action": {
                "title": "Circulation Protocol",
                "body": "Stasis is death. Never sit for more than 2 hours without moving. You must stay hyper-hydrated to reduce blood viscosity. Avoid Estrogen (birth control/HRT) as it thickens blood further."
            }
        },
        "data_strength": {
            "gene": "F2",
            "title": "The 'Optimal' Flow",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "The coagulation cascade is a delicate balance between bleeding and clotting ",
                "how": "Your Prothrombin levels are perfectly regulated. You have the exact right amount of clotting factor to seal a wound instantly, but not enough to trigger random clots during travel or stress. Your vascular risk profile is baseline optimal.",
                "yours": "Your Result: Optimal Hemodynamics."
            },
            "action": {
                "title": "Vascular Health",
                "body": "You have a natural protection against the clotting risks associated with aging. Maintain this by staying active and hydrated."
            }
        }
    },

    # 12. DRD2 (Dopamine)
    "DRD2": {
        "title": "Reward Circuitry",
        "badge_type": "RISK",
        "data_risk": {
            "gene": "DRD2",
            "title": "The 'Hungry Ghost' Brain",
            "badge_type": "RISK",
            "mechanisms": {
                "what": "The D2 Receptor is the main 'Satisfied' button in the brain. It tells you when you have had enough fun, food, or success.",
                "how": "You have the Taq1A allele (A1). This reduces the density of D2 receptors in your striatum by 30-40%. Life feels 'muted' to you. You need a louder signal (more sugar, more risk, more scrolling) to feel the same level of satisfaction that others feel from a simple walk. This is the genetic basis of addictive behavior.",
                "yours": "Your Result: Low Receptor Density."
            },
            "action": {
                "title": "Dopamine Resensitization",
                "body": "You cannot fill the bucket because it has a hole. You must shrink the bucket. Regular 'Dopamine Fasts' (24h without high-stimulation inputs) force your brain to grow more receptors, restoring your ability to feel joy from simple things."
            }
        },
        "data_strength": {
            "gene": "DRD2",
            "title": "The 'Zen' Architect",
            "badge_type": "SUPERPOWER",
            "mechanisms": {
                "what": "DRD2 determines the 'Reward Prediction Error'—how good something feels compared to what you expected.",
                "how": "You have a high density of D2 receptors. You are easily satisfied. Your brain efficiently processes small wins, allowing you to sustain motivation on long, boring projects without needing constant external validation. You are naturally immune to the 'doom scrolling' loop.",
                "yours": "Your Result: High Receptor Efficiency."
            },
            "action": {
                "title": "Deep Work",
                "body": "You have a rare biological advantage for mastery. You can tolerate the boredom of practice better than 80% of the population. Use this to master difficult skills."
            }
        }
    }
}

def final_upgrade():
    print("🚀 Starting Final Science Injection (Min 400 chars)...")
    
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
        # Map Clean Name
        clean_name = raw_name.split('(')[0].strip()
        if clean_name not in gene_map: gene_map[clean_name] = []
        gene_map[clean_name].append(rsid)
        # Map Raw Name (e.g. SLC2A9 (GLUT9))
        if raw_name not in gene_map: gene_map[raw_name] = []
        gene_map[raw_name].append(rsid)
        # Map Alternative Name in Parens (e.g. GLUT9)
        if '(' in raw_name:
            alt = raw_name.split('(')[1].replace(')', '').strip()
            if alt not in gene_map: gene_map[alt] = []
            gene_map[alt].append(rsid)

    # 3. Load Deep Dives
    if os.path.exists(DEEP_DIVE_PATH):
        with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
            deep_dive_data = json.load(f)
    else:
        deep_dive_data = {}

    # 4. Inject
    count = 0
    for gene_key, content in UPGRADE_CONTENT.items():
        target_rsids = gene_map.get(gene_key, [])
        if target_rsids:
            print(f"   -> Overwriting {gene_key}...")
            for rsid in target_rsids:
                # Force Gene Name
                content['data_risk']['gene'] = gene_key
                content['data_strength']['gene'] = gene_key
                deep_dive_data[rsid] = content
                count += 1
        else:
            print(f"⚠️ Gene {gene_key} not found in traits.")

    # 5. Save
    with open(DEEP_DIVE_PATH, 'w', encoding='utf-8') as f:
        json.dump(deep_dive_data, f, indent=4)

    print(f"\n✅ Upgrade Complete. Enhanced {count} entries.")

if __name__ == "__main__":
    final_upgrade()