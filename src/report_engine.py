import json
import os
from fpdf import FPDF

# CONFIG
DEEP_DIVE_PATH = "config/deep_dive_content.json"

def clean_text(text):
    """Sanitizes text to prevent PDF encoding errors."""
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        "→": "->", "’": "'", "‘": "'", "“": '"', "”": '"', 
        "–": "-", "—": "-", "…": "...", "•": "-", "►": ">>",
        "✨": "+"  # <--- FIX: Replaces the emoji with a safe character
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Force Latin-1 encoding (standard for FPDF)
    return text.encode('latin-1', 'replace').decode('latin-1')

class ReportEngine:
    def __init__(self):
        self.deep_dive_data = self._load_deep_dive_data()

    def _load_deep_dive_data(self):
        if not os.path.exists(DEEP_DIVE_PATH):
            return {}
        try:
            with open(DEEP_DIVE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def get_content_for_rsid(self, rsid, score):
        if rsid not in self.deep_dive_data:
            return None
        entry = self.deep_dive_data[rsid]
        
        # Determine Badge Type
        if score < 5:
            content = entry.get('data_risk')
            badge = "RISK"
        elif score > 5:
            content = entry.get('data_strength')
            badge = "SUPERPOWER"
        else:
            return None # Skip baseline
            
        if not content: return None

        return {
            "title": content.get('title', 'Genetic Insight'),
            "gene": content.get('gene', 'Unknown'),
            "badge_type": badge,
            "mechanism": content.get('mechanisms', {}),
            "action": content.get('action', {}),
            "confidence": content.get('confidence', 3)
        }

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18)
        self.set_fill_color(44, 62, 80) # Dark Blue
        self.rect(0, 0, self.w, 20, 'F')
        self.set_y(6)
        self.set_text_color(255)
        self.cell(0, 10, 'Personalized Genetic Trait Report', 0, 1, 'C')
        self.ln(15)

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

    def draw_table(self, df, col_widths, highlight_net=False):
        # Header
        self.set_font('Arial', 'B', 8)
        self.set_fill_color(52, 152, 219)
        self.set_text_color(255)
        headers = df.columns
        for i, col in enumerate(headers):
            self.cell(col_widths[i], 8, clean_text(col), 0, 0, 'C', 1)
        self.ln()

        # Rows
        self.set_font('Arial', '', 8)
        for idx, row in df.iterrows():
            self.set_fill_color(245, 245, 245)
            fill = (idx % 2 == 1)
            
            for i, val in enumerate(row):
                txt = clean_text(str(val))
                self.set_text_color(0)
                
                # Highlight Impact
                if headers[i] == "Impact":
                    self.set_font('Arial', 'B', 8)
                    if txt == "High": self.set_text_color(231, 76, 60)
                    elif txt == "Medium": self.set_text_color(243, 156, 18)
                else:
                    self.set_font('Arial', '', 8)
                
                # Highlight Net Score
                if highlight_net and headers[i] == "Net":
                    try:
                        v = float(val)
                        if v > 0: self.set_text_color(39, 174, 96)
                        elif v < 0: self.set_text_color(231, 76, 60)
                    except: pass

                if len(txt) > 60: txt = txt[:57] + "..."
                self.cell(col_widths[i], 7, txt, 0, 0, 'C', fill)
            self.ln()

    def draw_confidence_score(self, rating, x, y):
        self.set_xy(x, y)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(150)
        self.cell(0, 5, clean_text("SCIENTIFIC CONFIDENCE:"), 0, 1)
        
        self.set_xy(x, y + 5)
        self.set_font('Arial', 'B', 14)
        self.set_text_color(255, 165, 0)
        self.cell(0, 6, f"{rating}/5  {'+'*int(rating)}", 0, 1)

    def draw_genotype_spectrum(self, user_gt, score_map, variant_map):
        self.ln(5)
        self.set_font('Arial', 'B', 10)
        self.set_text_color(44, 62, 80)
        self.cell(0, 8, "Genotype Possibilities (Best to Worst):", 0, 1)
        
        sorted_gts = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
        
        for gt, score in sorted_gts:
            desc = variant_map.get(gt, "")
            
            # Colors
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
            self.cell(15, 8, gt, 1, 0, 'C', 1) 
            
            self.set_text_color(0)
            self.set_font('Arial', '' if not is_user else 'B', 9)
            
            marker = "  <-- YOUR GENOTYPE" if is_user else ""
            self.cell(0, 8, clean_text(f"  {desc}{marker}"), 0, 1)

    def add_strength_summary_page(self, strength_df):
        self.add_page()
        self.chapter_title("3. Other Genetic Strengths (Executive Summary)")
        self.ln(2)
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, clean_text("While these traits did not trigger a deep dive, they represent significant genetic advantages. You carry the OPTIMAL or ENHANCED variants for these genes."))
        self.ln(5)
        
        for _, row in strength_df.iterrows():
            self.set_fill_color(240, 255, 240) # Very Light Green
            self.rect(10, self.get_y(), 190, 18, 'F')
            
            self.set_font('Arial', 'B', 11)
            self.set_text_color(39, 174, 96)
            self.cell(40, 8, clean_text(f"{row['Gene']} ({row['Result']})"), 0, 0)
            
            self.set_font('Arial', 'I', 9)
            self.set_text_color(100)
            self.cell(0, 8, clean_text(f"  Domain: {row['Domain']}"), 0, 1)
            
            # Logic to rebrand "Normal" -> "Optimal"
            desc = row['Interpretation']
            if row['Score'] >= 8 and "Normal" in desc:
                desc = desc.replace("Normal", "Optimal")
                desc = f"+ {desc}" # Safe character
            
            self.set_font('Arial', '', 10)
            self.set_text_color(0)
            self.set_xy(12, self.get_y())
            self.cell(0, 8, clean_text(desc), 0, 1)
            
            self.ln(4)
            if self.get_y() > 260: self.add_page()

    def add_deep_dive_page(self, genotype, data, score_map, variant_map):
        self.add_page()
        self.chapter_title(f"Deep Dive: {data['title']}")
        
        # Info
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

        # Badge
        is_risk = (data['badge_type'] == "RISK")
        badge_color = (231, 76, 60) if is_risk else (46, 204, 113)
        self.set_xy(140, self.get_y() - 25)
        self.set_fill_color(*badge_color)
        self.set_text_color(255)
        self.set_font('Arial', 'B', 10)
        self.cell(50, 8, clean_text(f" {data['badge_type']} "), 0, 1, 'C', 1)
        self.ln(10)

        # Spectrum
        if score_map and variant_map:
            self.draw_genotype_spectrum(genotype, score_map, variant_map)
            self.ln(5)

        # Mechanism
        self.set_text_color(44, 62, 80)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 8, "[ THE BIOLOGICAL MECHANISM ]", 0, 1)
        self.set_font('Arial', '', 10)
        self.set_text_color(20)
        self.multi_cell(0, 5, clean_text(data['mechanism'].get('what', '')))
        self.ln(2)
        self.multi_cell(0, 5, clean_text(data['mechanism'].get('how', '')))
        self.ln(5)

        # Action
        start_y = self.get_y()
        self.set_fill_color(235, 250, 235) 
        self.rect(10, start_y, 190, 45, 'F')
        self.set_xy(15, start_y + 5)
        self.set_text_color(0, 100, 0)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 8, clean_text(f"INSIGHT: {data['action'].get('title', 'Action Plan')}"), 0, 1)
        self.set_x(15)
        self.set_text_color(0)
        self.set_font('Arial', '', 10)
        self.multi_cell(130, 5, clean_text(data['action'].get('body', '')))
        
        # Confidence
        self.draw_confidence_score(data.get('confidence', 3), 150, start_y + 15)
        self.ln(10)