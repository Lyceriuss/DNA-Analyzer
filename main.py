import os
import glob
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
        print("❌ No CSV files found in 'data/input'. Please add your raw DNA data.")
        return None

    if len(csv_files) == 1:
        print(f"📂 Found 1 file: {os.path.basename(csv_files[0])}")
        return csv_files[0]

    print("\n🧬 Found multiple DNA files:")
    for i, f in enumerate(csv_files):
        print(f"   [{i+1}] {os.path.basename(f)}")
    
    while True:
        try:
            choice = input(f"\n👉 Select a file (1-{len(csv_files)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(csv_files):
                return csv_files[idx]
            print("❌ Invalid selection.")
        except ValueError:
            print("❌ Please enter a number.")

def main():
    # 1. Interactive File Selection
    dna_file = select_dna_file()
    if not dna_file: return
    
    filename = os.path.basename(dna_file).split('.')[0]
    print(f"🚀 Starting Analysis for: {filename}")

    # 2. Run Analysis
    df = run_analysis(dna_file, TRAITS_FILE)
    if df.empty: return

    # 3. Create Dashboard Data
    summary = df.groupby("Domain").agg(
        Positive=("Score", lambda x: (x > 5).sum()),
        Negative=("Score", lambda x: (x < 5).sum()),
        Baseline=("Score", lambda x: (x == 5).sum())
    ).reset_index()
    summary["Net"] = summary["Positive"] - summary["Negative"]
    summary = summary.sort_values(by="Net", ascending=False)

    # 4. Generate Visuals (Polar Chart)
    polar_path = os.path.join(OUTPUT_DIR, "polar_chart.png")
    create_polar_chart(summary, polar_path)

    # 5. Initialize Engine
    engine = ReportEngine()
    pdf = PDFReport('P', 'mm', 'A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- PAGE 1: DASHBOARD & POLAR CHART ---
    # This ensures the graphical overview is the very first thing the user sees.
    pdf.add_page()
    pdf.chapter_title("1. Genetic Profile Dashboard")
    pdf.ln(5)
    
    # Draw Summary Table
    cols = ["Domain", "Positive", "Baseline", "Negative", "Net"]
    widths = [70, 25, 25, 25, 25]
    pdf.draw_table(summary[cols], widths, highlight_net=True)
    
    # Draw Polar Chart
    if os.path.exists(polar_path):
        pdf.ln(10)
        # Centered Image
        pdf.image(polar_path, x=50, w=110)

    # --- PAGE 2: KEY TRAITS LIST ---
    pdf.add_page()
    pdf.chapter_title("2. Key Active Traits")
    report_cols = ["Domain", "Trait", "Gene", "Impact", "Result", "Score", "Interpretation"]
    col_widths =  [30,       40,      18,     15,       12,       10,      65] 
    
    inc_df = df[df["Score"] > 5][report_cols]
    if not inc_df.empty:
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(39, 174, 96) # Green
        pdf.cell(0, 10, f"Increased Function (+): {len(inc_df)} Traits", 0, 1)
        pdf.draw_table(inc_df, col_widths)

    dec_df = df[df["Score"] < 5][report_cols]
    if not dec_df.empty:
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(231, 76, 60) # Red
        pdf.cell(0, 10, f"Decreased Function (-): {len(dec_df)} Traits", 0, 1)
        pdf.draw_table(dec_df, col_widths)

    # --- CATEGORIZATION LOGIC ---
    print("📘 Categorizing Deep Dives into Superpowers vs Risks...")
    prioritized_traits = df.sort_values(by="Impact", ascending=True)
    
    superpower_list = []
    risk_list = []
    processed_rsids = []
    
    for _, row in prioritized_traits.iterrows():
        rsid = row['RSID']
        score = row['Score']
        content = engine.get_content_for_rsid(rsid, score)
        
        if content:
            item = {
                "row": row,
                "content": content,
                "score_map": row.get('Score_Map', {}),
                "variant_map": row.get('Variant_Map', {})
            }
            if content['badge_type'] == 'SUPERPOWER':
                superpower_list.append(item)
            else:
                risk_list.append(item)
            processed_rsids.append(rsid)

    # --- SECTION 3: SUPERPOWERS (Green) ---
    if superpower_list:
        pdf.add_page()
        pdf.set_fill_color(39, 174, 96) # Green Brand Color
        pdf.rect(0, 0, 210, 297, 'F')
        pdf.set_xy(0, 130)
        pdf.set_font('Arial', 'B', 30)
        pdf.set_text_color(255)
        pdf.cell(0, 20, "SECTION 3:", 0, 1, 'C')
        pdf.cell(0, 20, "YOUR GENETIC SUPERPOWERS", 0, 1, 'C')
        
        for item in superpower_list:
            pdf.add_deep_dive_page(item['row']['Result'], item['content'], item['score_map'], item['variant_map'])

    # Strengths Executive Summary (Leftovers)
    leftover_strengths = df[
        (df["Score"] >= 7) & (df["Impact"] == "High") & (~df["RSID"].isin(processed_rsids))
    ].head(12)
    if not leftover_strengths.empty:
        pdf.add_strength_summary_page(leftover_strengths)

    # --- SECTION 4: RISKS (Red) ---
    if risk_list:
        pdf.add_page()
        pdf.set_fill_color(231, 76, 60) # Red Brand Color
        pdf.rect(0, 0, 210, 297, 'F')
        pdf.set_xy(0, 130)
        pdf.set_font('Arial', 'B', 30)
        pdf.set_text_color(255)
        pdf.cell(0, 20, "SECTION 4:", 0, 1, 'C')
        pdf.cell(0, 20, "YOUR GENETIC RISKS", 0, 1, 'C')

        for item in risk_list:
            pdf.add_deep_dive_page(item['row']['Result'], item['content'], item['score_map'], item['variant_map'])

    # Risk Executive Summary (Leftovers)
    leftover_risks = df[
        (df["Score"] <= 4) & (df["Impact"] == "High") & (~df["RSID"].isin(processed_rsids))
    ].head(12)
    if not leftover_risks.empty:
        pdf.add_risk_summary_page(leftover_risks)

    # 6. Save
    pdf_path = os.path.join(OUTPUT_DIR, f"{filename}_Report.pdf")
    pdf.output(pdf_path)
    print(f"✅ Full Report Generated: {pdf_path}")

if __name__ == "__main__":
    main()