import os
import glob
import pandas as pd
from src.analyzer import run_analysis
from src.visualizer import create_polar_chart
from src.report_engine import PDFReport, ReportEngine

# CONFIG
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
TRAITS_FILE = "config/snp_traits.json"

def select_dna_file():
    """Interactive selector for CSV files."""
    csv_files = glob.glob(os.path.join(INPUT_DIR, "*.csv"))
    if not csv_files:
        print("❌ No CSV files found in 'data/input'.")
        return None
    if len(csv_files) == 1:
        return csv_files[0]
    for i, f in enumerate(csv_files):
        print(f"   [{i+1}] {os.path.basename(f)}")
    try:
        choice = int(input(f"\n👉 Select a file (1-{len(csv_files)}): ").strip()) - 1
        return csv_files[choice] if 0 <= choice < len(csv_files) else None
    except:
        return None

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
    dna_file = select_dna_file()
    if not dna_file: return
    
    filename = os.path.basename(dna_file).split('.')[0]
    print(f"🚀 Starting Analysis for: {filename}")

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

# Section 3: Superpowers
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
        
        if content and content['badge_type'] == 'RISK': # (or 'SUPERPOWER')
            # ✅ Always use get_evidence_for_rsid(rsid) here
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

    pdf.output(os.path.join(OUTPUT_DIR, f"{filename}_Report.pdf"))
    print(f"✅ Full Report Generated!")

if __name__ == "__main__":
    main()