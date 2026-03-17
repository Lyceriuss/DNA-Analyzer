import os
import glob
import pandas as pd
from src.analyzer import run_analysis
from src.visualizer import create_polar_chart, create_heritage_pie_chart
from src.report_engine import PDFReport, ReportEngine
from src.inheritance import analyze_inheritance  # NEW DEPENDENCY

# CONFIG
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
TRAITS_FILE = "config/snp_traits.json"

def select_dna_file(prompt_title, exclude_files=None):
    """
    Robust interactive selector for CSV files with error handling and exclusions.
    """
    if exclude_files is None:
        exclude_files = []
        
    if not os.path.exists(INPUT_DIR):
        print(f"❌ Error: The directory '{INPUT_DIR}' does not exist.")
        return None

    all_csvs = glob.glob(os.path.join(INPUT_DIR, "*.csv"))
    available_files = [f for f in all_csvs if f not in exclude_files]
    
    if not available_files:
        print(f"❌ No available CSV files left in '{INPUT_DIR}' to select.")
        return None

    while True:
        print(f"\n📂 {prompt_title.upper()}")
        for i, f in enumerate(available_files):
            print(f"   [{i+1}] {os.path.basename(f)}")
        print("   [0] Cancel / Skip")
            
        choice_str = input(f"\n👉 Select an option (0-{len(available_files)}): ").strip()
        
        if not choice_str:
            print("⚠️ Please enter a number.")
            continue
            
        if not choice_str.isdigit():
            print("⚠️ Invalid input. Please enter a valid number.")
            continue
            
        choice = int(choice_str)
        
        if choice < 0 or choice > len(available_files):
            print(f"⚠️ Number out of range. Please choose between 0 and {len(available_files)}.")
            continue
            
        if choice == 0:
            return None
            
        selected_file = available_files[choice - 1]
        print(f"✅ Selected: {os.path.basename(selected_file)}")
        return selected_file

def gather_family_profiles():
    """
    Handles the workflow for selecting a primary profile and up to 2 relatives.
    Returns a dictionary with the selected files.
    """
    print("\n🧬 --- PROFILE SELECTION MENU --- 🧬")
    
    selected_profiles = {
        "child": None,
        "parents": []
    }
    exclude_list = []
    
    # 1. Select Primary Profile
    child_file = select_dna_file("Select Primary Profile (Main Subject)")
    if not child_file:
        print("❌ Primary profile selection cancelled. Exiting script.")
        return None
        
    selected_profiles["child"] = child_file
    exclude_list.append(child_file)
    
    # 2. Select Relatives Loop
    print("\n" + "="*35)
    print("👨‍👩‍👧 HERITAGE & FAMILY MODULE (Optional)")
    print("="*35)
    
    while len(selected_profiles["parents"]) < 2:
        num_parents = len(selected_profiles["parents"])
        
        # Display Current State
        print("\n[ CURRENT FAMILY TREE ]")
        print(f"👤 Main: {os.path.basename(selected_profiles['child'])}")
        for p in selected_profiles["parents"]:
            print(f"🧑 {p['label']}: {os.path.basename(p['file'])}")
        print("-" * 25)
        
        # --- BLAZING FAST MENU ---
        print(f"\n👉 Add a family profile? ({num_parents}/2 added)")
        print("   [1] Add Mom")
        print("   [2] Add Dad")
        print("   [3] Add Custom (example: sibling/grandparent)")
        print("   [0] No / Continue to Analysis")
        
        role_choice = input("\nSelect an option (0-3): ").strip()
        
        if role_choice == '0':
            break  
        elif role_choice == '1':
            parent_label = "Mom"
        elif role_choice == '2':
            parent_label = "Dad"
        elif role_choice == '3':
            parent_label = input("Enter custom name (e.g., Sister, Grandpa): ").strip()
            if not parent_label:
                parent_label = f"Relative {num_parents + 1}"
        else:
            print("⚠️ Invalid input. Please type 0, 1, 2, or 3.")
            continue
            
        # Select relative's file
        p_file = select_dna_file(f"Select file for {parent_label.upper()}", exclude_list)
        
        if p_file:
            selected_profiles["parents"].append({
                "label": parent_label,
                "file": p_file
            })
            exclude_list.append(p_file) 
        else:
            print(f"⚠️ Skipped adding {parent_label}.")

    # --- Print Summary ---
    print("\n" + "="*35)
    print("✅ SELECTION COMPLETE")
    print("="*35)
    print(f"👤 Main Subject: {os.path.basename(selected_profiles['child'])}")
    if not selected_profiles['parents']:
        print("👪 Relatives: None selected (Standard Analysis)")
    for p in selected_profiles['parents']:
        print(f"🧑 {p['label']}: {os.path.basename(p['file'])}")
    print("="*35 + "\n")
        
    return selected_profiles

def clean_domain_names(df):
    replacements = {
        "Metabolism & Weight": "Metabolism",
        "Immune & Gut Health": "Immune & Gut",
        "Longevity & Cell Health": "Longevity",
        "Musculoskeletal & Skin": "Structure",
        "Hormones & Endocrine": "Hormones",
        "Vitamins & Methylation": "Vitamins",
        "Detox & Pharma": "Detox",
        "Cardiovascular Health": "Cardio",
        "Glucose & Insulin": "Glucose",
        "Brain & Mood": "Brain"
    }
    df['Domain'] = df['Domain'].replace(replacements)
    return df

def main():
    # Execute the new robust profile gatherer
    profiles = gather_family_profiles()
    if not profiles or not profiles["child"]:
        return
        
    dna_file = profiles["child"]
    filename = os.path.basename(dna_file).split('.')[0]
    print(f"🚀 Starting Primary Analysis for: {filename}")

    df = run_analysis(dna_file, TRAITS_FILE)
    if df.empty: return

    df = clean_domain_names(df)
    
    # Dashboard Data
    summary = df.groupby("Domain").agg(
        Positive=("Score", lambda x: (x > 5).sum()),
        Negative=("Score", lambda x: (x < 5).sum()),
        Baseline=("Score", lambda x: (x == 5).sum())
    ).reset_index()
    summary["Net"] = summary["Positive"] - summary["Negative"]
    summary = summary.sort_values(by="Net", ascending=False)

    create_polar_chart(summary, os.path.join(OUTPUT_DIR, "polar_chart.png"))

    # Init Engine
    engine = ReportEngine()
    pdf = PDFReport('P', 'mm', 'A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Page 1 & 2 (Summary)
    pdf.add_page()
    pdf.chapter_title("1. Genetic Profile Dashboard")
    pdf.ln(5)
    pdf.draw_table(summary[["Domain", "Positive", "Baseline", "Negative", "Net"]], [70, 25, 25, 25, 25], highlight_net=True)
    if os.path.exists(os.path.join(OUTPUT_DIR, "polar_chart.png")):
        pdf.ln(10)
        pdf.image(os.path.join(OUTPUT_DIR, "polar_chart.png"), x=50, w=110)

    pdf.add_page()
    pdf.chapter_title("2. Key Active Traits")
    unique_df = df.drop_duplicates(subset=['Gene'], keep='first')
    
    inc_df = unique_df[unique_df["Score"] > 5][["Domain", "Trait", "Gene", "Impact", "Result", "Score", "Interpretation"]]
    if not inc_df.empty:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(39, 174, 96)
        pdf.cell(0, 10, f"Increased Function (+): {len(inc_df)} Traits", 0, 1)
        pdf.draw_table(inc_df, [25, 45, 25, 15, 12, 10, 58])

    dec_df = unique_df[unique_df["Score"] < 5][["Domain", "Trait", "Gene", "Impact", "Result", "Score", "Interpretation"]]
    if not dec_df.empty:
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(231, 76, 60)
        pdf.cell(0, 10, f"Decreased Function (-): {len(dec_df)} Traits", 0, 1)
        pdf.draw_table(dec_df, [25, 45, 25, 15, 12, 10, 58])

    # Deep Dives
    print("📘 Generating Deep Dives...")
    prioritized_traits = unique_df.sort_values(by="Impact", ascending=True)
    
    processed_rsids = []
    
    # Section 3: Superpowers
    pdf.add_page()
    pdf.set_fill_color(39, 174, 96)
    pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_y(130)
    pdf.set_font('Arial', 'B', 30)
    pdf.set_text_color(255)
    pdf.cell(0, 20, "SECTION 3:", 0, 1, 'C')
    pdf.cell(0, 20, "YOUR GENETIC SUPERPOWERS", 0, 1, 'C')

    for _, row in prioritized_traits.iterrows():
        rsid = row['RSID']
        score = row['Score']
        
        # 1. GET CONTENT FIRST
        content = engine.get_content_for_rsid(rsid, score)
        
        # 2. NOW CHECK IF CONTENT EXISTS
        if content and content['badge_type'] == 'SUPERPOWER':
            # 3. FETCH EVIDENCE USING RSID
            evidence = engine.get_evidence_for_rsid(rsid)
            
            pdf.add_deep_dive_page(
                row['Result'], 
                content, 
                row['Score_Map'], 
                row['Variant_Map'], 
                evidence=evidence
            )
            processed_rsids.append(rsid)
            
    # --- RESTORED: EXECUTIVE SUMMARY (STRENGTHS) ---
    leftover_strengths = unique_df[
        (unique_df["Score"] >= 7) & 
        (~unique_df["RSID"].isin(processed_rsids))
    ].head(12)
    
    if not leftover_strengths.empty:
        pdf.add_strength_summary_page(leftover_strengths)

    # Section 4: Risks
    pdf.add_page()
    pdf.set_fill_color(231, 76, 60)
    pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_y(130)
    pdf.set_font('Arial', 'B', 30)
    pdf.set_text_color(255)
    pdf.cell(0, 20, "SECTION 4:", 0, 1, 'C')
    pdf.cell(0, 20, "YOUR GENETIC RISKS", 0, 1, 'C')

    for _, row in prioritized_traits.iterrows():
        rsid = row['RSID']
        score = row['Score']
        content = engine.get_content_for_rsid(rsid, score)
        
        if content and content['badge_type'] == 'RISK':
            evidence = engine.get_evidence_for_rsid(rsid)
            pdf.add_deep_dive_page(row['Result'], content, row['Score_Map'], row['Variant_Map'], evidence)
            processed_rsids.append(rsid)

    # --- RESTORED: EXECUTIVE SUMMARY (RISKS) ---
    leftover_risks = unique_df[
        (unique_df["Score"] <= 4) & 
        (~unique_df["RSID"].isin(processed_rsids))
    ].head(12)
    
    if not leftover_risks.empty:
        pdf.add_risk_summary_page(leftover_risks)

# ---------------------------------------------------------
    # INJECT HERITAGE / INHERITANCE MODULE HERE
    # ---------------------------------------------------------
    if profiles["parents"]:
        print("\n🧬 Processing Heritage & Family Data...")
        
        # Analyze first relative
        p1_info = profiles["parents"][0]
        p1_df = run_analysis(p1_info['file'], TRAITS_FILE)
        p1_name = p1_info['label']
        
        # Analyze second relative (if exists)
        p2_df = None
        p2_name = "Relative 2"
        if len(profiles["parents"]) == 2:
            p2_info = profiles["parents"][1]
            p2_df = run_analysis(p2_info['file'], TRAITS_FILE)
            p2_name = p2_info['label']
            
        # Run the inheritance matching logic
        inheritance_df = analyze_inheritance(
            unique_df, 
            p1_df, 
            p2_df, 
            parent1_name=p1_name, 
            parent2_name=p2_name
        )
        
        # --- THIS IS THE PART THAT WAS MISSING! ---
        pie_chart_path = os.path.join(OUTPUT_DIR, "heritage_pie.png")
        create_heritage_pie_chart(inheritance_df, pie_chart_path, p1_name, p2_name)
        
        pdf.add_inheritance_page(
            inheritance_df, 
            parent1_name=p1_name, 
            parent2_name=p2_name, 
            two_parents=(len(profiles["parents"]) == 2),
            chart_path=pie_chart_path
        )

    pdf.output(os.path.join(OUTPUT_DIR, f"{filename}_Report.pdf"))
    print(f"\n✅ Full Report Generated for {filename}!")

if __name__ == "__main__":
    main()