import json

def generate_visual_report(json_filepath, gene_key):
    # 1. Load the data
    print(f"Loading database from {json_filepath}...")
    with open(json_filepath, 'r') as f:
        db = json.load(f)
        
    gene_data = db.get(gene_key)
    if not gene_data:
        print("Gene not found in JSON.")
        return

    # 2. Extract Data for Templates
    gene_name = gene_data['variant_identity']['gene_symbol']
    rsid = gene_data['rsid']
    label = gene_data['consensus_label']
    
    # Pathway Nodes
    vis = gene_data['visualization_blueprint']
    left_node = vis['components']['left_node']
    right_node = vis['components']['right_node']
    
    # State Variables (Normal vs Risk)
    normal = vis['states']['reference_allele']
    risk = vis['states']['risk_allele']
    
    # Clinical Rationale (to show when variant is active)
    clinical_detail = gene_data['metrics']['mechanistic_impact']['detail']

    # 3. Build the HTML String
    print(f"Building Interactive HTML for {gene_name}...")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{gene_name} Analysis Report</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #111827; color: white; display: flex; flex-direction: column; align-items: center; padding: 2rem; }}
            .header-box {{ text-align: center; margin-bottom: 2rem; border-bottom: 1px solid #374151; padding-bottom: 1rem; width: 100%; max-width: 900px; }}
            .label {{ background: #3B82F6; padding: 0.2rem 0.6rem; border-radius: 0.25rem; font-size: 0.8rem; font-weight: bold; letter-spacing: 1px;}}
            
            .dashboard {{ display: flex; align-items: center; justify-content: center; gap: 2rem; margin-top: 1rem; width: 100%; max-width: 900px; }}
            .cycle {{ background: #1F2937; padding: 1.5rem; border-radius: 0.5rem; border: 1px solid #374151; width: 30%; text-align: center; }}
            
            /* Dynamic Enzyme Node */
            .enzyme {{ background: {normal['node_color']}; padding: 2rem 1rem; border-radius: 50%; width: 140px; height: 140px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-weight: bold; text-align: center; transition: all 0.5s ease; border: 4px solid rgba(255,255,255,0.2); z-index: 10; }}
            .enzyme.variant {{ background: {risk['node_color']}; box-shadow: 0 0 20px rgba(245, 158, 11, 0.6); }}
            
            /* Flow Animations */
            .flow-container {{ position: relative; width: 120px; height: 4px; background: #374151; overflow: hidden; }}
            .particle {{ position: absolute; top: 0; left: 0; width: 20px; height: 4px; border-radius: 2px; }}
            .particle-fast {{ background: {normal['node_color']}; animation: moveRight 0.8s linear infinite; }}
            .particle-slow {{ background: {risk['node_color']}; animation: moveRight 3.5s linear infinite; }}

            @keyframes moveRight {{ 0% {{ transform: translateX(-20px); }} 100% {{ transform: translateX(120px); }} }}
            
            /* Controls and Info */
            button {{ background: #374151; color: white; border: 1px solid #4B5563; padding: 1rem 2rem; border-radius: 0.5rem; font-size: 1.1rem; cursor: pointer; font-weight: bold; transition: background 0.2s; margin-top: 2rem;}}
            button:hover {{ background: #4B5563; }}
            .active-btn {{ background: {risk['node_color']} !important; border-color: transparent; color: #000; }}
            
            .info-box {{ margin-top: 2rem; background: #1F2937; padding: 1.5rem; border-radius: 0.5rem; border-left: 4px solid {risk['node_color']}; max-width: 850px; display: none; }}
        </style>
    </head>
    <body>

        <div class="header-box">
            <h1>{gene_name} Insight: <span class="label">{label}</span></h1>
            <p style="color: #9CA3AF;">Variant Identity: {rsid} | Systems: {", ".join(gene_data['affected_systems'])}</p>
        </div>

        <button id="toggleBtn">Simulate {risk['genotype_example']} Genotype (Risk Allele)</button>

        <div class="dashboard">
            <div class="cycle">
                <h3>{left_node['title']}</h3>
                <p style="color: #9CA3AF; font-size: 0.875rem;">{left_node['subtitle']}</p>
            </div>

            <div class="flow-container"><div id="inflow" class="particle particle-fast"></div></div>

            <div id="protein-node" class="enzyme">
                {gene_name}
                <span id="enzyme-status" style="font-size: 0.75rem; font-weight: normal; margin-top: 5px;">{normal['node_label']}</span>
            </div>

            <div class="flow-container"><div id="outflow" class="particle particle-fast"></div></div>

            <div class="cycle">
                <h3>{right_node['title']}</h3>
                <p style="color: #9CA3AF; font-size: 0.875rem;">{right_node['subtitle']}</p>
            </div>
        </div>

        <div id="clinical-info" class="info-box">
            <h3 style="margin-top:0; color: {risk['node_color']};">{risk['clinical_badge']}</h3>
            <p style="line-height: 1.6; color: #D1D5DB;">{clinical_detail}</p>
        </div>

        <script>
            let isVariantActive = false;
            const btn = document.getElementById('toggleBtn');
            const node = document.getElementById('protein-node');
            const statusText = document.getElementById('enzyme-status');
            const inflow = document.getElementById('inflow');
            const outflow = document.getElementById('outflow');
            const infoBox = document.getElementById('clinical-info');

            btn.addEventListener('click', () => {{
                isVariantActive = !isVariantActive;
                if (isVariantActive) {{
                    node.classList.add('variant');
                    statusText.innerText = "{risk['node_label']}";
                    inflow.className = "particle particle-slow";
                    outflow.className = "particle particle-slow";
                    infoBox.style.display = "block";
                    btn.classList.add('active-btn');
                    btn.innerText = "Revert to {normal['genotype_example']} Genotype (Reference)";
                }} else {{
                    node.classList.remove('variant');
                    statusText.innerText = "{normal['node_label']}";
                    inflow.className = "particle particle-fast";
                    outflow.className = "particle particle-fast";
                    infoBox.style.display = "none";
                    btn.classList.remove('active-btn');
                    btn.innerText = "Simulate {risk['genotype_example']} Genotype (Risk Allele)";
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    # 4. Save to disk
    output_filename = f"{gene_key}_dashboard.html"
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"Success! Rendered visualization to {output_filename}")

if __name__ == "__main__":
    # Make sure your JSON file is named 'mthfr_database.json' and is in the same folder
    generate_visual_report('mthfr_database.json', 'MTHFR_1298')