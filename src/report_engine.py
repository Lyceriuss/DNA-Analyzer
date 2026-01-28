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
        
        
    def get_evidence_for_rsid(self, rsid):
        """
        Scans evidence_db.json for the entry matching the rsid.
        MUST BE INDENTED TO BE PART OF THE CLASS.
        """
        if not rsid: return None
        for key, data in self.evidence_db.items():
            if data.get('rsid') == rsid:
                return data
        return None

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
        self.set_font(font_family, font_style, font_size)
        text_w = self.get_string_width(text)
        if width == 0: width = 1
        lines = math.ceil(text_w / width * 1.1) + 1 
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
        self.ln(5)
        self.set_font('Arial', 'B', 10)
        self.set_text_color(44, 62, 80)
        self.cell(0, 8, "Genotype Possibilities (Best to Worst):", 0, 1)
        
        sorted_gts = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
        
        for gt, score in sorted_gts:
            desc = variant_map.get(gt, "")
            if score >= 7: r,g,b = 39, 174, 96 
            elif score >= 5: r,g,b = 149, 165, 166
            else: r,g,b = 231, 76, 60 
            
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

    def draw_segment_bar(self, x, y, score, max_score=5):
        segment_w = 4
        segment_h = 2.5
        spacing = 1
        
        for i in range(max_score):
            sx = x + (i * (segment_w + spacing))
            sy = y
            if i < int(score):
                self.set_fill_color(52, 152, 219) 
            else:
                self.set_fill_color(220, 220, 220) 
            self.rect(sx, sy, segment_w, segment_h, 'F')

    def draw_body_evidence(self, evidence_data):
        if not evidence_data: return
        current_y = self.get_y()
        if current_y > 225: return 

        metrics = evidence_data.get('metrics', {})
        mech = metrics.get('mechanistic_impact', {})
        qual = metrics.get('study_quality', {})
        
        # Spacer
        self.ln(8) 
        
        # HEADER
        self.set_font('Arial', 'B', 12)
        self.set_text_color(44, 62, 80) 
        self.cell(0, 8, "[ RESEARCH & VALIDATION ]", 0, 1, 'L')
        self.ln(1)
        
        # CONTENT
        self.set_draw_color(52, 152, 219) 
        self.set_line_width(0.8)
        
        # 1. MECHANISTIC
        if 'detail' in mech:
            self.line(12, self.get_y(), 12, self.get_y() + 5) 
            self.set_x(15)
            self.set_font('Arial', 'B', 10) 
            self.set_text_color(44, 62, 80)
            self.cell(0, 5, clean_text("MECHANISTIC CONTEXT:"), 0, 1)
            
            # --- ADDED SPACE BETWEEN TITLE AND TEXT ---
            self.ln(2) 

            self.set_x(15)
            self.set_font('Arial', '', 10) 
            self.set_text_color(0, 0, 0)
            self.multi_cell(180, 5, clean_text(mech['detail'])) 
            
            # Space between blocks
            self.ln(8) 

        # 2. STUDY QUALITY
        if 'detail' in qual and self.get_y() < 220:
            self.line(12, self.get_y(), 12, self.get_y() + 5)
            self.set_x(15)
            self.set_font('Arial', 'B', 10)
            self.set_text_color(44, 62, 80)
            self.cell(0, 5, clean_text("STUDY QUALITY & CONSENSUS:"), 0, 1)

            # --- ADDED SPACE BETWEEN TITLE AND TEXT ---
            self.ln(2) 
            
            self.set_x(15)
            self.set_font('Arial', '', 10)
            self.set_text_color(0, 0, 0)
            self.multi_cell(180, 5, clean_text(qual['detail']))
            
        self.set_line_width(0.2)

    def draw_evidence_panel(self, evidence_data):
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

        raw_sum = (mech['score'] * 3) + qual['score'] + meth['score']
        final_score = raw_sum / 5.0
        if final_score > 5.0: final_score = 5.0

        # Background
        self.set_y(-60)
        self.set_fill_color(248, 250, 252)
        self.set_draw_color(220, 220, 220)
        self.rect(10, self.get_y(), 190, 40, 'DF')
        
        start_y = self.get_y() + 4
        self.set_xy(15, start_y)

        # --- COL 1: SCORE ---
        self.set_font('Arial', 'B', 8)
        self.set_text_color(100) 
        self.cell(40, 4, "CONFIDENCE SCORE", 0, 1, 'L')
        
        # Big Number
        self.set_font('Arial', 'B', 24)
        self.set_text_color(44, 62, 80) 
        big_num = f"{final_score:.1f}"
        big_num_w = self.get_string_width(big_num)
        
        self.set_xy(15, start_y + 6)
        self.cell(big_num_w + 1, 10, big_num, 0, 0, 'L')
        
        # Suffix
        self.set_xy(15 + big_num_w + 1, start_y + 9) 
        self.set_font('Arial', 'B', 13) 
        self.set_text_color(44, 62, 80) 
        self.cell(15, 6, "/ 5.0", 0, 1, 'L')
        
        # --- COL 2: BREAKDOWN ---
        col2_x = 65
        self.set_xy(col2_x, start_y)
        self.set_font('Arial', 'B', 8)
        self.set_text_color(0, 0, 0)
        self.cell(30, 4, "METRIC BREAKDOWN", 0, 1, 'L')
        
        def draw_metric_row(label, score, y_offset):
            self.set_xy(col2_x, start_y + 8 + y_offset)
            self.set_font('Arial', 'B', 7)
            self.set_text_color(0, 0, 0)
            self.cell(25, 4, clean_text(label), 0, 0, 'L')
            self.draw_segment_bar(self.get_x(), self.get_y() + 1, score)

        draw_metric_row("MECHANISM (3x)", mech['score'], 0)
        draw_metric_row("STUDY QUALITY", qual['score'], 6)
        draw_metric_row("METHODOLOGY", meth['score'], 12)

        # --- COL 3: AUDIT ---
        col3_x = 120
        self.set_xy(col3_x, start_y)
        self.set_font('Arial', 'B', 8)
        self.set_text_color(0, 0, 0)
        self.cell(0, 4, "METHODOLOGY AUDIT", 0, 1, 'L')
        
        self.set_xy(col3_x, start_y + 6)
        self.set_font('Arial', '', 8)
        self.set_text_color(0, 0, 0)
        detail_text = clean_text(meth.get('detail', 'No detailed audit available.'))
        self.multi_cell(80, 3.5, detail_text, 0, 'L')

    def add_strength_summary_page(self, strength_df):
        self.add_page()
        self.chapter_title("3. Other Genetic Strengths (Executive Summary)")
        self.ln(2)
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, clean_text("While these traits did not trigger a deep dive, they represent significant genetic advantages."))
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
        self.multi_cell(0, 5, clean_text("These traits did not trigger a detailed deep dive, but they represent areas of potential vulnerability."))
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
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 5, clean_text(data['mechanism'].get('what', '')))
        self.ln(2)
        self.multi_cell(0, 5, clean_text(data['mechanism'].get('how', '')))
        self.ln(5)

        start_y = self.get_y()
        title_txt = f"INSIGHT: {data['action'].get('title', 'Action Plan')}"
        body_txt = data['action'].get('body', '')
        
        self.set_font('Arial', '', 10)
        lines = math.ceil(self.get_string_width(body_txt) / 180) + 1
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
        
        self.set_y(start_y + box_height) 
        self.draw_body_evidence(evidence)
        self.draw_evidence_panel(evidence)