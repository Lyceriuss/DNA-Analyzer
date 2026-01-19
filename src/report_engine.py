import json
import os
from fpdf import FPDF
import math

# CONFIG
DEEP_DIVE_PATH = "config/deep_dive_content.json"
EVIDENCE_PATH = "config/evidence_db.json"

def clean_text(text):
    """Sanitizes text to prevent PDF encoding errors."""
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        "→": "->", "’": "'", "‘": "'", "“": '"', "”": '"', 
        "–": "-", "—": "-", "…": "...", "•": "-", "►": ">>",
        "✨": "+" 
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode('latin-1', 'replace').decode('latin-1')

class ReportEngine:
    def __init__(self):
        self.deep_dive_data = self._load_json(DEEP_DIVE_PATH)
        self.evidence_db = self._load_json(EVIDENCE_PATH)

    def _load_json(self, path):
        if not os.path.exists(path): return {}
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}

    def get_content_for_rsid(self, rsid, score):
        if rsid not in self.deep_dive_data: return None
        entry = self.deep_dive_data[rsid]
        
        if score < 5:
            content = entry.get('data_risk')
            badge = "RISK"
        elif score > 5:
            content = entry.get('data_strength')
            badge = "SUPERPOWER"
        else: return None 
            
        if not content: return None

        return {
            "title": content.get('title', 'Genetic Insight'),
            "gene": content.get('gene', 'Unknown'),
            "badge_type": badge,
            "mechanism": content.get('mechanisms', {}),
            "action": content.get('action', {}),
            "confidence": content.get('confidence', 3)
        }

    def get_evidence_for_gene(self, gene_name):
        """Fetches the deep evidence object for a specific gene."""
        if not gene_name: return None
        clean_name = gene_name.split('(')[0].strip()
        return self.evidence_db.get(clean_name, None)

class PDFReport(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, 'Personalized Genetic Trait Report', 0, 0, 'R')
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(44, 62, 80)
        self.cell(0, 8, clean_text(title), 0, 1, 'L')
        self.ln(2)

    def get_text_height(self, width, text, font_family, font_style, font_size):
        """Calculates the height a block of text will consume."""
        self.set_font(font_family, font_style, font_size)
        text_w = self.get_string_width(text)
        # Approximate lines needed
        if width == 0: width = 1 # avoid div by zero
        lines = (text_w / width) 
        lines = math.ceil(lines * 1.1) + 1 
        # Height ~ half font size in mm per line is a safe heuristic
        return lines * (font_size * 0.5)

    def draw_table(self, df, col_widths, highlight_net=False):
        self.set_font('Arial', 'B', 8)
        self.set_fill_color(52, 152, 219)
        self.set_text_color(255)
        headers = df.columns
        for i, col in enumerate(headers):
            self.cell(col_widths[i], 8, clean_text(col), 0, 0, 'C', 1)
        self.ln()
        self.set_font('Arial', '', 8)
        for idx, row in df.iterrows():
            self.set_fill_color(245, 245, 245)
            fill = (idx % 2 == 1)
            for i, val in enumerate(row):
                txt = clean_text(str(val))
                self.set_text_color(0)
                
                if headers[i] == "Impact":
                    self.set_font('Arial', 'B', 8)
                    if txt == "High": self.set_text_color(231, 76, 60)
                    elif txt == "Medium": self.set_text_color(243, 156, 18)
                else: self.set_font('Arial', '', 8)
                
                if highlight_net and headers[i] == "Net":
                    try:
                        if float(val) > 0: self.set_text_color(39, 174, 96)
                        elif float(val) < 0: self.set_text_color(231, 76, 60)
                    except: pass

                if len(txt) > 60: txt = txt[:57] + "..."
                self.cell(col_widths[i], 7, txt, 0, 0, 'C', fill)
            self.ln()

    def draw_genotype_spectrum(self, user_gt, score_map, variant_map):
        """Draws the table showing best-to-worst genotypes."""
        self.ln(5)
        self.set_font('Arial', 'B', 10)
        self.set_text_color(44, 62, 80)
        self.cell(0, 8, "Genotype Possibilities (Best to Worst):", 0, 1)
        
        sorted_gts = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
        
        for gt, score in sorted_gts:
            desc = variant_map.get(gt, "")
            # Color Coding based on score
            if score >= 7: r,g,b = 39, 174, 96   # Green
            elif score >= 5: r,g,b = 149, 165, 166 # Grey
            else: r,g,b = 231, 76, 60            # Red
            
            is_user = (gt == user_gt)
            self.set_fill_color(r, g, b)
            
            if is_user:
                self.set_draw_color(0) 
                self.set_line_width(0.5)
            else:
                self.set_draw_color(255)
            
            self.set_font('Arial', 'B', 9)
            self.set_text_color(255)
            self.cell(15, 8, clean_text(gt), 1, 0, 'C', 1) 
            
            self.set_text_color(0)
            self.set_font('Arial', '' if not is_user else 'B', 9)
            marker = "  <-- YOUR GENOTYPE" if is_user else ""
            self.cell(0, 8, clean_text(f"  {desc}{marker}"), 0, 1)

    def draw_body_evidence(self, evidence_data):
        """Draws Mechanism and Study Quality in the body whitespace."""
        if not evidence_data: return

        current_y = self.get_y()
        # Footer starts at -65 (approx 232mm). We need space.
        if current_y > 225: return 

        metrics = evidence_data.get('metrics', {})
        mech = metrics.get('mechanistic_impact', {})
        qual = metrics.get('study_quality', {})
        
        self.ln(5)
        self.set_x(15)
        
        # 1. MECHANISTIC DETAIL
        if 'detail' in mech:
            self.set_font('Arial', 'B', 9)
            self.set_text_color(100)
            self.cell(0, 5, clean_text("MECHANISTIC CONTEXT:"), 0, 1)
            self.set_font('Arial', '', 9)
            self.set_text_color(50)
            self.multi_cell(180, 4, clean_text(mech['detail']))
            self.ln(3)

        # 2. STUDY QUALITY
        if 'detail' in qual and self.get_y() < 220:
            self.set_x(15)
            self.set_font('Arial', 'B', 9)
            self.set_text_color(100)
            self.cell(0, 5, clean_text("STUDY QUALITY & CONSENSUS:"), 0, 1)
            self.set_font('Arial', '', 9)
            self.set_text_color(50)
            self.multi_cell(180, 4, clean_text(qual['detail']))

    def draw_evidence_panel(self, evidence_data):
        """Draws the bottom panel with Score, Bars, and METHODOLOGY."""
        
        if not evidence_data:
            evidence_data = {
                "metrics": {
                    "mechanistic_impact": {"score": 3, "detail": "Mechanism inferred."},
                    "study_quality": {"score": 2, "detail": "Small studies."},
                    "methodology": {"score": 3, "detail": "Standard data."}
                },
                "consensus_label": "PRELIMINARY"
            }

        metrics = evidence_data.get('metrics', {})
        mech = metrics.get('mechanistic_impact', {'score': 3})
        qual = metrics.get('study_quality', {'score': 3})
        meth = metrics.get('methodology', {'score': 3, 'detail': 'N/A'})

        # Algorithm
        raw_sum = (mech['score'] * 3) + qual['score'] + meth['score']
        final_score = raw_sum / 5.0
        if final_score > 5.0: final_score = 5.0

        # Draw Panel
        self.set_y(-65)
        self.set_fill_color(245, 247, 250)
        self.rect(10, self.get_y(), 190, 45, 'F')
        
        start_y = self.get_y() + 5
        self.set_xy(15, start_y)

        # LEFT: SCORE
        self.set_font('Arial', 'B', 10)
        self.set_text_color(100)
        self.cell(40, 5, "CONFIDENCE SCORE", 0, 1, 'L')
        self.set_font('Arial', 'B', 22)
        self.set_text_color(44, 62, 80)
        self.cell(40, 10, f"{final_score:.1f} / 5.0", 0, 1, 'L')
        
        bar_w = 30
        fill_w = (final_score / 5.0) * bar_w
        self.set_fill_color(200, 200, 200)
        self.rect(15, self.get_y()+2, bar_w, 2, 'F')
        self.set_fill_color(39, 174, 96)
        self.rect(15, self.get_y()+2, fill_w, 2, 'F')
        
        # MIDDLE: BARS
        self.set_xy(60, start_y)
        self.set_font('Arial', 'B', 8)
        self.set_text_color(100)
        self.cell(30, 5, "BREAKDOWN", 0, 1, 'L')
        
        def draw_mini_bar(label, score, y_off):
            self.set_xy(60, start_y + 6 + y_off)
            self.set_font('Arial', '', 8)
            self.set_text_color(50)
            self.cell(25, 4, clean_text(label), 0, 0, 'L')
            dots = "O " * int(score) + ". " * (5 - int(score))
            self.set_font('Courier', 'B', 8) 
            self.cell(20, 4, dots, 0, 0, 'L')

        draw_mini_bar("Mechanism (3x)", mech['score'], 0)
        draw_mini_bar("Study Quality", qual['score'], 5)
        draw_mini_bar("Methodology", meth['score'], 10)

        # RIGHT: METHODOLOGY AUDIT
        self.set_xy(110, start_y)
        self.set_font('Arial', 'B', 8)
        self.set_text_color(100)
        self.cell(0, 5, "METHODOLOGY AUDIT", 0, 1, 'L')
        self.set_xy(110, start_y + 6)
        self.set_font('Arial', 'I', 9)
        self.set_text_color(0)
        detail_text = clean_text(meth.get('detail', 'No detailed audit available.'))
        self.multi_cell(85, 4, detail_text, 0, 'L')

    def add_strength_summary_page(self, strength_df):
        self.add_page()
        self.chapter_title("3. Other Genetic Strengths (Executive Summary)")
        self.ln(2)
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, clean_text("While these traits did not trigger a deep dive, they represent significant genetic advantages. You carry the OPTIMAL or ENHANCED variants for these genes."))
        self.ln(5)
        for _, row in strength_df.iterrows():
            self.set_fill_color(240, 255, 240)
            self.rect(10, self.get_y(), 190, 18, 'F')
            self.set_font('Arial', 'B', 11)
            self.set_text_color(39, 174, 96)
            self.cell(40, 8, clean_text(f"{row['Gene']} ({row['Result']})"), 0, 0)
            self.set_font('Arial', 'I', 9)
            self.set_text_color(100)
            self.cell(0, 8, clean_text(f"  Domain: {row['Domain']}"), 0, 1)
            desc = row['Interpretation']
            if row['Score'] >= 8 and "Normal" in desc:
                desc = desc.replace("Normal", "Optimal")
                desc = f"+ {desc}"
            self.set_font('Arial', '', 10)
            self.set_text_color(0)
            self.set_xy(12, self.get_y())
            self.cell(0, 8, clean_text(desc), 0, 1)
            self.ln(4)
            if self.get_y() > 260: self.add_page()

    def add_risk_summary_page(self, risk_df):
        self.add_page()
        self.chapter_title("4. Other Genetic Risks (Executive Summary)")
        self.ln(2)
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, clean_text("These traits did not trigger a detailed deep dive, but they represent areas of potential vulnerability. You carry RISK variants that may require lifestyle management."))
        self.ln(5)
        for _, row in risk_df.iterrows():
            self.set_fill_color(255, 240, 240)
            self.rect(10, self.get_y(), 190, 18, 'F')
            self.set_font('Arial', 'B', 11)
            self.set_text_color(231, 76, 60)
            self.cell(40, 8, clean_text(f"{row['Gene']} ({row['Result']})"), 0, 0)
            self.set_font('Arial', 'I', 9)
            self.set_text_color(100)
            self.cell(0, 8, clean_text(f"  Domain: {row['Domain']}"), 0, 1)
            desc = row['Interpretation']
            self.set_font('Arial', '', 10)
            self.set_text_color(0)
            self.set_xy(12, self.get_y())
            self.cell(0, 8, clean_text(f"! {desc}"), 0, 1)
            self.ln(4)
            if self.get_y() > 260: self.add_page()

    def add_deep_dive_page(self, genotype, data, score_map, variant_map, evidence=None):
        self.add_page()
        self.chapter_title(f"Deep Dive: {data['title']}")
        
        self.set_fill_color(240, 244, 248) 
        self.rect(10, self.get_y(), 190, 25, 'F')
        self.set_xy(15, self.get_y() + 5)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(0)
        self.cell(0, 8, clean_text(f"Gene: {data['gene']}"), 0, 1)
        self.set_font('Arial', '', 10)
        self.set_text_color(80)
        self.cell(0, 6, clean_text(f"Your Result: {genotype}"), 0, 1)
        self.ln(15)

        is_risk = (data['badge_type'] == "RISK")
        badge_color = (231, 76, 60) if is_risk else (46, 204, 113)
        self.set_xy(140, self.get_y() - 25)
        self.set_fill_color(*badge_color)
        self.set_text_color(255)
        self.set_font('Arial', 'B', 10)
        self.cell(50, 8, clean_text(f" {data['badge_type']} "), 0, 1, 'C', 1)
        self.ln(10)

        if score_map and variant_map:
            self.draw_genotype_spectrum(genotype, score_map, variant_map)
            self.ln(5)

        self.set_text_color(44, 62, 80)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 8, "[ THE BIOLOGICAL MECHANISM ]", 0, 1)
        self.set_font('Arial', '', 10)
        self.set_text_color(20)
        self.multi_cell(0, 5, clean_text(data['mechanism'].get('what', '')))
        self.ln(2)
        self.multi_cell(0, 5, clean_text(data['mechanism'].get('how', '')))
        self.ln(5)

        # --- DYNAMIC GREEN BOX ---
        start_y = self.get_y()
        title_txt = f"INSIGHT: {data['action'].get('title', 'Action Plan')}"
        body_txt = data['action'].get('body', '')
        
        # Calculate dynamic height
        # Assuming body text area width is ~180mm (full width w/ padding)
        # Using heuristic calculation to match FPDF text flow
        self.set_font('Arial', '', 10)
        # 180mm width roughly
        lines = math.ceil(self.get_string_width(body_txt) / 180) + 1
        # Base height 8mm (title) + lines * 5mm + padding
        box_height = 10 + (lines * 5) + 5
        if box_height < 25: box_height = 25 

        self.set_fill_color(235, 250, 235) 
        self.rect(10, start_y, 190, box_height, 'F')
        
        self.set_xy(15, start_y + 5)
        self.set_text_color(0, 100, 0)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 8, clean_text(title_txt), 0, 1)
        
        self.set_x(15)
        self.set_text_color(0)
        self.set_font('Arial', '', 10)
        self.multi_cell(180, 5, clean_text(body_txt))
        
        # --- DRAW BODY EVIDENCE (Mech + Quality) ---
        # Move cursor below green box
        self.set_y(start_y + box_height) 
        self.draw_body_evidence(evidence)
        
        # --- DRAW FOOTER PANEL (Score + Methodology) ---
        self.draw_evidence_panel(evidence)