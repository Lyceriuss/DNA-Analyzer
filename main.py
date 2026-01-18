import os
import glob
from src.analyzer import run_analysis
from src.visualizer import create_polar_chart
from src.report_engine import PDFReport, ReportEngine

# CONFIG
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
TRAITS_FILE = "config/snp_traits.json"

def main():
    csv_files = glob.glob(os.path.join(INPUT_DIR, "*.csv"))
    if not csv_files:
        print("❌ No CSV files found.")
        return
    
    dna_file = csv_files[0]
    filename = os.path.basename(dna_file).split('.')[0]
    print(f"🚀 Starting Analysis for: {filename}")

    df = run_analysis(dna_file, TRAITS_FILE)
    if df.empty: return

    # Dashboard Data
    summary = df.groupby("Domain").agg(
        Positive=("Score", lambda x: (x > 5).sum()),
        Negative=("Score", lambda x: (x < 5).sum()),
        Baseline=("Score", lambda x: (x == 5).sum())
    ).reset_index()
    summary["Net"] = summary["Positive"] - summary["Negative"]
    summary = summary.sort_values(by="Net", ascending=False)

    polar_path = os.path.join(OUTPUT_DIR, "polar_chart.png")
    create_polar_chart(summary, polar_path)

    engine = ReportEngine()
    pdf = PDFReport('P', 'mm', 'A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- PAGE 1: DASHBOARD ---
    pdf.add_page()
    pdf.chapter_title("1. Genetic Profile Dashboard")
    pdf.ln(5)
    cols = ["Domain", "Positive", "Baseline", "Negative", "Net"]
    widths = [70, 25, 25, 25, 25]
    pdf.draw_table(summary[cols], widths, highlight_net=True)
    if os.path.exists(polar_path):
        pdf.ln(10)
        pdf.image(polar_path, x=50, w=110)

    # --- PAGE 2: KEY TRAITS ---
    pdf.add_page()
    pdf.chapter_title("2. Key Active Traits")
    report_cols = ["Domain", "Trait", "Gene", "Impact", "Result", "Score", "Interpretation"]
    col_widths =  [30,       40,      18,     15,       12,       10,      65] 
    
    inc_df = df[df["Score"] > 5][report_cols]
    if not inc_df.empty:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(39, 174, 96)
        pdf.cell(0, 10, f"Increased Function (+): {len(inc_df)} Traits", 0, 1)
        pdf.draw_table(inc_df, col_widths)

    dec_df = df[df["Score"] < 5][report_cols]
    if not dec_df.empty:
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(231, 76, 60)
        pdf.cell(0, 10, f"Decreased Function (-): {len(dec_df)} Traits", 0, 1)
        pdf.draw_table(dec_df, col_widths)

    # --- PAGE 3: DEEP DIVES ---
    print("📘 Generating Deep Dive Pages...")
    prioritized_traits = df.sort_values(by="Impact", ascending=True) 
    
    processed_rsids = []
    
    for _, row in prioritized_traits.iterrows():
        rsid = row['RSID']
        score = row['Score']
        genotype = row['Result']
        
        score_map = row.get('Score_Map', {})
        variant_map = row.get('Variant_Map', {})
        
        content = engine.get_content_for_rsid(rsid, score)
        
        if content:
            pdf.add_deep_dive_page(genotype, content, score_map, variant_map)
            processed_rsids.append(rsid)
            
    # --- PAGE 4: STRENGTHS SUMMARY ---
    leftover_strengths = df[
        (df["Score"] >= 7) &       # High Score
        (df["Impact"] == "High") & # Important
        (~df["RSID"].isin(processed_rsids))
    ].head(12)
    
    if not leftover_strengths.empty:
        pdf.add_strength_summary_page(leftover_strengths)

    # --- PAGE 5: RISKS SUMMARY (NEW) ---
    leftover_risks = df[
        (df["Score"] <= 4) &       # Low Score (Risk)
        (df["Impact"] == "High") & # Important
        (~df["RSID"].isin(processed_rsids))
    ].head(12)
    
    if not leftover_risks.empty:
        print(f"📕 Generating Risk Summary for {len(leftover_risks)} traits...")
        pdf.add_risk_summary_page(leftover_risks)

    pdf_path = os.path.join(OUTPUT_DIR, f"{filename}_Report.pdf")
    pdf.output(pdf_path)
    print(f"✅ Full Report Generated: {pdf_path}")

if __name__ == "__main__":
    main()