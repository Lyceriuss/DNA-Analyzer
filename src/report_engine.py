import json
import os
from fpdf import FPDF
import math

# CONFIG
DEEP_DIVE_PATH = "config/deep_dive_content.json"
EVIDENCE_PATH = "config/evidence_db.json"
UI_LABELS_PATH = "config/ui_labels.json" # New config for modularity


LANGUAGE_CONFIG = {
    "English": {"prefix": "", "flag": "🇬🇧"},
    "Swedish": {"prefix": "SV_", "flag": "🇸🇪"},
    "German":  {"prefix": "DE_", "flag": "🇩🇪"}
}

# --- EXTERNAL LABEL LOADER ---
# We load this at the module level so main.py can still import PDF_LABELS
def load_ui_labels():
    if os.path.exists(UI_LABELS_PATH):
        try:
            with open(UI_LABELS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"English": {}, "Swedish": {}}

# Keep this name so main.py's "from src.report_engine import PDF_LABELS" still works
PDF_LABELS = load_ui_labels()

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
    try:
        return text.encode('latin-1', 'replace').decode('latin-1')
    except:
        return text.encode('ascii', 'replace').decode('ascii')

class ReportEngine:
    def __init__(self, language="English"):
        self.language = language
        
        # 1. Modular Label Loading (Merge English base with selected language)
        # This ensures if you forget a key in Swedish, it falls back to English instead of breaking.
        eng_base = PDF_LABELS.get("English", {})
        selected = PDF_LABELS.get(language, {})
        self.labels = {**eng_base, **selected}
        
        # 2. Map-Driven Path Logic (No more if/else booleans)
        # We grab the config for the language, defaulting to English if not found
        lang_cfg = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["English"])
        prefix = lang_cfg["prefix"]
        
        # Build paths dynamically using f-strings
        # This renders: "config/SV_deep_dive_content.json" for Swedish
        self.deep_dive_path = f"config/{prefix}deep_dive_content.json"
        self.evidence_path = f"config/{prefix}evidence_db.json"

        print(f"[*] ReportEngine: Loading {language} resources (Prefix: '{prefix}')...")
        self.deep_dive_data = self._load_json(self.deep_dive_path)
        self.evidence_db = self._load_json(self.evidence_path)

    def _load_json(self, path):
        if not os.path.exists(path):
            print(f"    [!] Warning: {path} not found. Falling back to empty data.")
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"    [!] Error loading {path}: {e}")
            return {}
        
    def get_evidence_for_rsid(self, rsid):
        """
        Scans evidence_db.json for the entry matching the rsid.
        """
        if not rsid: return None
        # Check if the RSID is the key (common in translated files)
        if rsid in self.evidence_db:
            return self.evidence_db[rsid]
        # Scan if it's a list-style dictionary
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
    def __init__(self, orientation='P', unit='mm', format='A4', labels=None):
        super().__init__(orientation, unit, format)
        # We catch the labels injected from main.py
        self.labels = labels if labels else {}

    def header(self):
        if self.page_no() > 1:
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128, 128, 128)
            # Pull header text from injected labels
            header_txt = self.labels.get('header_tag', 'Personalized Genetic Trait Report')
            self.cell(0, 10, clean_text(header_txt), 0, 0, 'R')
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150)
        # Localize "Page" if the key exists
        page_lbl = self.labels.get('footer_page', 'Page')
        self.cell(0, 10, f'{page_lbl} {self.page_no()}', 0, 0, 'C')

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
                
                # Check for localized Impact/Påverkan headers
                if headers[i] in ["Impact", "Påverkan"]:
                    self.set_font('Arial', 'B', 8)
                    if txt in ["High", "Hög"]: self.set_text_color(231, 76, 60)
                    elif txt in ["Medium", "Medel"]: self.set_text_color(243, 156, 18)
                else: self.set_font('Arial', '', 8)
                
                # Check for localized Net/Netto headers
                if highlight_net and headers[i] in ["Net", "Netto"]:
                    try:
                        if float(val) > 0: self.set_text_color(39, 174, 96)
                        elif float(val) < 0: self.set_text_color(231, 76, 60)
                    except: pass

                if len(txt) > 60: txt = txt[:57] + "..."
                self.cell(col_widths[i], 7, txt, 0, 0, 'C', fill)
            self.ln()

    def draw_genotype_spectrum(self, user_gt, score_map, variant_map):
        self.ln(-3)
        self.set_font('Arial', 'B', 10)
        self.set_text_color(44, 62, 80)
        # Pull localized spectrum title
        
        spectrum_txt = self.labels.get('genotype_spectrum_title', "Genotype Possibilities (Best to Worst):")
        self.cell(0, 8, clean_text(spectrum_txt), 0, 1)
        
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
            # Pull localized marker
            marker_lbl = self.labels.get('user_genotype_marker', "  <-- YOUR GENOTYPE")
            marker = marker_lbl if is_user else ""
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
        self.ln(4) 
        
        # HEADER
        self.set_font('Arial', 'B', 12)
        self.set_text_color(44, 62, 80) 
        val_header = self.labels.get('research_validation_header', "[ RESEARCH & VALIDATION ]")
        self.cell(0, 8, clean_text(val_header), 0, 1, 'L')
        self.ln(-2)
        
        # CONTENT
        self.set_draw_color(52, 152, 219) 
        self.set_line_width(0.8)
        
        # 1. MECHANISTIC
        if 'detail' in mech:
            self.line(12, self.get_y(), 12, self.get_y() + 5) 
            self.set_x(15)
            self.set_font('Arial', 'B', 10) 
            self.set_text_color(44, 62, 80)
            mech_lbl = self.labels.get('mech_context_label', "MECHANISTIC CONTEXT:")
            self.cell(0, 5, clean_text(mech_lbl), 0, 1)
            
            self.ln(2) 
            self.set_x(15)
            self.set_font('Arial', '', 10) 
            self.set_text_color(0, 0, 0)
            self.multi_cell(180, 5, clean_text(mech['detail'])) 
            self.ln(4) 

        # 2. STUDY QUALITY
        if 'detail' in qual and self.get_y() < 220:
            self.line(12, self.get_y(), 12, self.get_y() + 5)
            self.set_x(15)
            self.set_font('Arial', 'B', 10)
            self.set_text_color(44, 62, 80)
            qual_lbl = self.labels.get('study_quality_header_label', "STUDY QUALITY & CONSENSUS:")
            self.cell(0, 5, clean_text(qual_lbl), 0, 1)

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
                    "mechanistic_impact": {"score": 3, "detail": "N/A"},
                    "study_quality": {"score": 2, "detail": "N/A"},
                    "methodology": {"score": 3, "detail": "N/A"}
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
        self.set_y(-45)
        self.set_fill_color(248, 250, 252)
        self.set_draw_color(220, 220, 220)
        self.rect(10, self.get_y(), 190, 40, 'DF')
        
        start_y = self.get_y() + 4
        self.set_xy(15, start_y)

        # --- COL 1: SCORE ---
        self.set_font('Arial', 'B', 8)
        self.set_text_color(100) 
        conf_lbl = self.labels.get('confidence_score_label', "CONFIDENCE SCORE")
        self.cell(28, 4, clean_text(conf_lbl), 0, 1, 'L')
        
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
        breakdown_lbl = self.labels.get('metric_breakdown_label', "METRIC BREAKDOWN")
        self.cell(30, 4, clean_text(breakdown_lbl), 0, 1, 'L')
        
        def draw_metric_row(label_key, score, y_offset, default_txt):
            self.set_xy(col2_x, start_y + 8 + y_offset)
            self.set_font('Arial', 'B', 7)
            self.set_text_color(0, 0, 0)
            row_label = self.labels.get(label_key, default_txt)
            self.cell(25, 4, clean_text(row_label), 0, 0, 'L')
            self.draw_segment_bar(self.get_x(), self.get_y() + 1, score)

        draw_metric_row('label_mechanism', mech['score'], 0, "MECHANISM (3x)")
        draw_metric_row('label_quality', qual['score'], 6, "STUDY QUALITY")
        draw_metric_row('label_methodology', meth['score'], 12, "METHODOLOGY")
        # --- COL 3: AUDIT ---
        col3_x = 120
        self.set_xy(col3_x, start_y)
        self.set_font('Arial', 'B', 8)
        self.set_text_color(0, 0, 0)
        audit_lbl = self.labels.get('methodology_audit_label', "METHODOLOGY AUDIT")
        self.cell(0, 4, clean_text(audit_lbl), 0, 1, 'L')
        
        self.set_xy(col3_x, start_y + 6)
        self.set_font('Arial', '', 8)
        self.set_text_color(0, 0, 0)
        fallback = self.labels.get('audit_fallback_text', 'No detailed audit available.')
        detail_text = clean_text(meth.get('detail', fallback))
        self.multi_cell(80, 3.5, detail_text, 0, 'L')

    def add_strength_summary_page(self, strength_df):
        self.add_page()
        title = self.labels.get('strength_summary_title', "3. Other Genetic Strengths (Executive Summary)")
        self.chapter_title(title)
        self.ln(2)
        self.set_font('Arial', '', 10)
        intro = self.labels.get('strength_summary_intro', "While these traits did not trigger a deep dive, they represent significant genetic advantages.")
        self.multi_cell(0, 5, clean_text(intro))
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
        title = self.labels.get('risk_summary_title', "4. Other Genetic Risks (Executive Summary)")
        self.chapter_title(title)
        self.ln(2)
        self.set_font('Arial', '', 10)
        intro = self.labels.get('risk_summary_intro', "These traits did not trigger a detailed deep dive, but they represent areas of potential vulnerability.")
        self.multi_cell(0, 5, clean_text(intro))
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
        prefix = self.labels.get('deep_dive_prefix', "Deep Dive:")
        self.chapter_title(f"{prefix} {data['title']}")
        
        self.set_fill_color(240, 244, 248) 
        self.rect(10, self.get_y(), 190, 25, 'F')
        self.set_xy(15, self.get_y() + 5)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(0)
        gene_label = self.labels.get('gene_label_text', 'Gene:')
        self.cell(0, 8, clean_text(f"{gene_label} {data['gene']}"), 0, 1)
        self.set_font('Arial', '', 10)
        self.set_text_color(80)
        res_lbl = self.labels.get('your_result_label', "Your Result:")
        self.cell(4, 6, clean_text(f"{res_lbl} {genotype}"), 0, 1)
        self.ln(15)

        is_risk = (data['badge_type'] == "RISK")
        badge_color = (231, 76, 60) if is_risk else (46, 204, 113)
        # Pull localized badge text
        badge_txt = self.labels.get('risk_badge_text', 'RISK') if is_risk else self.labels.get('superpower_badge_text', 'SUPERPOWER')
        
        self.set_xy(140, self.get_y() - 25)
        self.set_fill_color(*badge_color)
        self.set_text_color(255)
        self.set_font('Arial', 'B', 10)
        self.cell(50, 8, clean_text(f" {badge_txt} "), 0, 1, 'C', 1)
        self.ln(10)

        if score_map and variant_map:
            self.draw_genotype_spectrum(genotype, score_map, variant_map)
            self.ln(5)

        self.set_text_color(44, 62, 80)
        self.set_font('Arial', 'B', 12)
        mech_header = self.labels.get('biological_mechanism_header', "[ THE BIOLOGICAL MECHANISM ]")
        self.cell(0, 8, clean_text(mech_header), 0, 1)
        self.set_font('Arial', '', 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 5, clean_text(data['mechanism'].get('what', '')))
        self.ln(1)
        self.multi_cell(0, 5, clean_text(data['mechanism'].get('how', '')))
        self.ln(5)

        start_y = self.get_y()
        ins_prefix = self.labels.get('insight_prefix', "INSIGHT")
        title_txt = f"{ins_prefix}: {data['action'].get('title', 'Action Plan')}"
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
        
    def _truncate(self, text, length):
        """Helper to keep table cells from overflowing the PDF margins."""
        if not isinstance(text, str): text = str(text)
        return text[:length-3] + "..." if len(text) > length else text

    def add_inheritance_page(self, inheritance_df, parent1_name="Parent 1", parent2_name="Parent 2", two_parents=True, chart_path=None):
        self.add_page()
        title = self.labels.get('inheritance_title', "Family Trait Inheritance Breakdown")
        self.chapter_title(title)
        self.ln(2)
        
        self.set_font('Arial', '', 10)
        desc = self.labels.get('inheritance_desc', "This section visualizes where your active genetic traits originated.")
        self.multi_cell(0, 5, clean_text(desc))
        self.ln(5)

        # 1. Place the Donut Chart
        if chart_path and os.path.exists(chart_path):
            self.image(chart_path, x=25, w=160)
            self.ln(5)

        # 2. Helper function to draw mini-tables
        def draw_relative_table(df_subset, relative_name, relative_color):
            if df_subset.empty: return
            
            self.set_font('Arial', 'B', 12)
            self.set_text_color(*relative_color)
            lbl_prefix = self.labels.get('inherited_from_label', "Traits Inherited Exclusively From")
            self.cell(0, 8, clean_text(f"{lbl_prefix} {relative_name}"), 0, 1, 'L')
            
            self.set_font('Arial', 'B', 9)
            self.set_fill_color(*relative_color)
            self.set_text_color(255)
            
            col_widths = [20, 55, 25, 25, 65]
            # Pull localized heritage headers
            headers = self.labels.get('cols_heritage', ["Gene", "Trait", "Your Result", f"{relative_name} Result", "Impact Summary"])
            
            for i, header in enumerate(headers):
                self.cell(col_widths[i], 8, clean_text(header), 0, 0, 'C', 1)
            self.ln()

            self.set_font('Arial', '', 8)
            display_df = df_subset.head(15)
            
            for idx, row in display_df.iterrows():
                if self.get_y() > 270:
                    self.add_page()
                    
                self.set_fill_color(245, 245, 245)
                fill = (idx % 2 == 1)
                self.set_text_color(0)
                
                c_score = row.get('Child_Score', 5)
                gene_txt = self._truncate(str(row.get('Gene', '')), 12)
                trait_txt = self._truncate(str(row.get('Trait', '')), 35)
                interp_txt = self._truncate(str(row.get('Interpretation', '')), 45)
                
                c_res = str(row.get('Child_Result', 'N/A'))
                p_res = str(row.get(f'{relative_name}_Result', 'N/A'))

                self.cell(col_widths[0], 7, clean_text(gene_txt), 0, 0, 'C', fill)
                self.cell(col_widths[1], 7, clean_text(trait_txt), 0, 0, 'C', fill)
                
                if c_score >= 7: self.set_text_color(39, 174, 96) 
                elif c_score <= 4: self.set_text_color(231, 76, 60) 
                else: self.set_text_color(0)
                
                self.set_font('Arial', 'B', 8)
                self.cell(col_widths[2], 7, clean_text(c_res), 0, 0, 'C', fill)
                
                self.set_text_color(0)
                self.set_font('Arial', '', 8)
                self.cell(col_widths[3], 7, clean_text(p_res), 0, 0, 'C', fill)
                self.cell(col_widths[4], 7, clean_text(interp_txt), 0, 0, 'C', fill)
                self.ln()
                
            self.ln(8)

        p1_df = inheritance_df[inheritance_df['Inheritance_Source'] == f"Match: {parent1_name}"]
        draw_relative_table(p1_df, parent1_name, (231, 76, 60))

        if two_parents:
            if self.get_y() > 220: 
                self.add_page()
                
            p2_df = inheritance_df[inheritance_df['Inheritance_Source'] == f"Match: {parent2_name}"]
            draw_relative_table(p2_df, parent2_name, (52, 152, 219))