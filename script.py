import json
import os
from fpdf import FPDF

# CONFIG
EVIDENCE_PATH = "config/evidence_db.json"
OUTPUT_DIR = "data/output"
ASSETS_DIR = "assets"
AVATAR_IMG = os.path.join(ASSETS_DIR, "human_body.png") # Place your avatar image here
OUTPUT_PDF = os.path.join(OUTPUT_DIR, "Clinical_Deep_Dive_Reference.pdf")

def clean_text(text):
    if not isinstance(text, str): text = str(text)
    replacements = {"→": "->", "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", "•": "-"}
    for old, new in replacements.items(): text = text.replace(old, new)
    return text.encode('latin-1', 'replace').decode('latin-1')

class DeepDivePDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Arial', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, 'Clinical Gene Reference Library', 0, 0, 'R')
            self.ln(10)

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def add_toc_avatar_page(self, organ_links):
        """Builds a modern, dark, 'Holographic' Table of Contents with a dynamic biometric body map."""
        self.add_page()
        
        # --- 1. SET MODERN DARK BACKGROUND (EVERY PAGE) ---
        self.set_fill_color(10, 20, 35) # Very deep space navy
        self.rect(0, 0, 210, 297, 'F')
        
        self.set_y(20)
        
        # --- 2. SET NEON COLOR PALETTE ---
        NEON_CYAN = (0, 255, 255)
        NEON_MAGENTA = (255, 0, 255)
        self.set_draw_color(*NEON_CYAN) # Default borders
        self.set_line_width(0.7)
        
        self.set_font('Arial', 'B', 24)
        self.set_text_color(*NEON_CYAN) # Title is neon cyan
        self.cell(0, 10, "BIOMETRIC SYSTEM INTERFACE", 0, 1, 'C')
        self.set_font('Arial', 'I', 11)
        self.set_text_color(180) # Subtitle is softer soft gray
        self.cell(0, 8, "Select a system pathway below to visualize its clinical genetic markers.", 0, 1, 'C')
        self.ln(10)

        # 3. Center the Holographic Avatar Image
        img_x = 65
        img_y = 65
        img_w = 80
        img_center_x = img_x + (img_w / 2)
        
        if os.path.exists(AVATAR_IMG):
            # We use alpha=0.9 to make the avatar itself slightly translucent
            self.image(AVATAR_IMG, x=img_x, y=img_y, w=img_w)
        else:
            self.set_fill_color(0, 30, 60) # Dark gray placeholder
            self.rect(img_x, img_y, img_w, 160, 'F')

        # 4. Precision Biometric Map (Fixing Alignment & Clumping)
        anatomy_map = {
            # Head/Neck Group
            "Brain":          {"box_y": 65,  "target_y": 75,  "side": "R"},
            "Eyes":           {"box_y": 80,  "target_y": 78,  "side": "L"},
            "Thyroid":        {"box_y": 95,  "target_y": 95,  "side": "R"},
            "Nervous System": {"box_y": 105, "target_y": 90,  "side": "L"},
            # Chest/Abdomen Group
            "Heart":          {"box_y": 120, "target_y": 110, "side": "L"},
            "Lungs":          {"box_y": 135, "target_y": 118, "side": "R"},
            "Liver":          {"box_y": 150, "target_y": 135, "side": "L"},
            "Stomach":        {"box_y": 150, "target_y": 140, "side": "R"},
            # Pelvis/General Group
            "Kidneys":        {"box_y": 170, "target_y": 150, "side": "L"},
            "Testes":         {"box_y": 190, "target_y": 170, "side": "R"},
            "Reproductive":   {"box_y": 190, "target_y": 170, "side": "R"},
            "General Health": {"box_y": 215, "target_y": 185, "side": "L"},
            "Systemic":       {"box_y": 225, "target_y": 185, "side": "R"}
        }

        # 5. Draw the Clickable floating tags and Glowing Lines
        for organ, link in sorted(organ_links.items()):
            mapping = anatomy_map.get(organ, {"box_y": 240, "target_y": 180, "side": "L"})
            box_y = mapping["box_y"]
            target_y = mapping["target_y"]
            is_left = (mapping["side"] == "L")

            box_width = 45
            box_x = 15 if is_left else 150
            
            # --- Draw the Glowing Connecting Line FIRST ---
            # We set draw color to neon magenta for a few special lines to create depth
            self.set_draw_color(*NEON_CYAN)
            self.set_line_width(0.7)
            
            if is_left:
                line_start_x = box_x + box_width
                self.line(line_start_x, box_y + 4.5, img_center_x - 10, target_y) 
            else:
                line_start_x = box_x
                self.line(line_start_x, box_y + 4.5, img_center_x + 10, target_y)

            # --- Draw the Floating 'Data Display' Box ---
            self.set_xy(box_x, box_y)
            
            # Use semi-translucent fill (very low alpha dark cyan)
            self.set_fill_color(0, 15, 30) # Very subtle fill to differentiate box from background
            
            self.set_draw_color(*NEON_CYAN) # Glowing Cyan border
            self.set_text_color(*NEON_CYAN) # Glowing Cyan text
            
            self.set_font('Arial', 'B', 9) 
            
            # Draw cell: fill=True adds the subtle fill, border=1 adds the glowing border
            self.cell(box_width, 9, clean_text(organ.upper()), border=1, ln=0, align='C', fill=True, link=link)            
    def add_section_title(self, title, link):
        """Draws the chapter header and sets the link destination."""
        self.add_page()
        self.set_link(link) # Anchors the click from Page 1 to here!
        
        self.set_y(120)
        self.set_font('Arial', 'B', 32)
        self.set_text_color(44, 62, 80)
        self.cell(0, 15, clean_text(title.upper()), 0, 1, 'C')
        self.set_draw_color(52, 152, 219)
        self.set_line_width(1)
        self.line(50, self.get_y(), 160, self.get_y())

    def render_gene_page(self, gene_key, data):
        self.add_page()
        
        identity = data.get("variant_identity", {})
        gene_symbol = identity.get("gene_symbol", gene_key)
        rsid = identity.get("rsid", "Unknown")
        common_name = identity.get("common_name", "")
        consensus = data.get("consensus_label", "CLINICAL MARKER")

        # --- HEADER BANNER ---
        self.set_fill_color(44, 62, 80)
        self.rect(10, 15, 190, 25, 'F')
        self.set_xy(15, 20)
        self.set_font('Arial', 'B', 20)
        self.set_text_color(255)
        self.cell(130, 8, clean_text(f"{gene_symbol} ({rsid})"), 0, 0, 'L')
        self.set_font('Arial', 'B', 10)
        self.set_text_color(241, 196, 15)
        self.cell(50, 8, clean_text(consensus), 0, 1, 'R')
        self.set_xy(15, 28)
        self.set_font('Arial', 'I', 11)
        self.set_text_color(200)
        self.cell(0, 6, clean_text(common_name), 0, 1, 'L')
        self.ln(10)

        # --- RESTORED: BIOTYPE & IMPACT ---
        self.set_font('Arial', 'B', 10)
        self.set_text_color(52, 152, 219)
        self.cell(30, 6, "BIOTYPE:", 0, 0)
        self.set_font('Arial', '', 10)
        self.set_text_color(0)
        self.cell(0, 6, clean_text(identity.get('biotype', 'N/A')), 0, 1)

        self.set_font('Arial', 'B', 10)
        self.set_text_color(52, 152, 219)
        self.cell(30, 6, "IMPACT TYPE:", 0, 0)
        self.set_font('Arial', '', 10)
        self.set_text_color(0)
        self.cell(0, 6, clean_text(data.get('impact_type', 'N/A')), 0, 1)
        self.ln(5)

        # --- METABOLIC CONNECTIONS ---
        metabolic = data.get("metabolic_connections", {})
        if metabolic:
            self.set_fill_color(236, 240, 241)
            self.rect(10, self.get_y(), 190, 8, 'F')
            self.set_font('Arial', 'B', 11)
            self.set_text_color(44, 62, 80)
            self.set_xy(12, self.get_y() + 1.5)
            self.cell(0, 5, "METABOLIC PATHWAY", 0, 1)
            self.ln(5)

            upstream = metabolic.get("upstream_requirements", [])
            downstream = metabolic.get("downstream_impacts", [])
            self.set_text_color(0)
            
            if upstream:
                self.set_font('Arial', 'B', 9)
                self.cell(0, 5, "Upstream Requirements (Inputs):", 0, 1)
                self.set_font('Arial', '', 9)
                for req in upstream:
                    self.multi_cell(0, 5, clean_text(f" + {req.get('molecule')} ({req.get('role')}): {req.get('mechanism')}"))
                self.ln(2)

            if downstream:
                self.set_font('Arial', 'B', 9)
                self.cell(0, 5, "Downstream Impacts (Outputs):", 0, 1)
                self.set_font('Arial', '', 9)
                for imp in downstream:
                    self.multi_cell(0, 5, clean_text(f" -> {imp.get('molecule')} ({imp.get('effect')}): {imp.get('consequence')}"))
                self.ln(5)

        # --- RESTORED: EVIDENCE METRICS ---
        metrics = data.get("metrics", {})
        if metrics:
            self.set_font('Arial', 'B', 11)
            self.set_text_color(44, 62, 80)
            self.cell(0, 8, "[ EVIDENCE METRICS ]", 0, 1)
            
            for m_key, m_data in metrics.items():
                title = m_key.replace('_', ' ').title()
                score = m_data.get('score', 0)
                
                self.set_font('Arial', 'B', 9)
                self.set_text_color(0)
                self.cell(45, 5, clean_text(f"{title}:"), 0, 0)
                
                self.set_text_color(39, 174, 96) # Green score
                self.cell(15, 5, clean_text(f"{score}/5"), 0, 0)
                
                self.set_text_color(80)
                self.set_font('Arial', 'I', 9)
                self.multi_cell(0, 5, clean_text(m_data.get('rationale', '')))
            self.ln(5)

        # --- METHODOLOGY AUDIT ---
        audit = data.get("methodology_audit", [])
        if audit:
            if self.get_y() > 200: self.add_page()
            self.set_fill_color(236, 240, 241)
            self.rect(10, self.get_y(), 190, 8, 'F')
            self.set_font('Arial', 'B', 11)
            self.set_text_color(44, 62, 80)
            self.set_xy(12, self.get_y() + 1.5)
            self.cell(0, 5, "CLINICAL EVIDENCE & AUDIT", 0, 1)
            self.ln(5)

            for study in audit:
                if self.get_y() > 240: self.add_page()
                self.set_font('Arial', 'B', 10)
                self.set_text_color(39, 174, 96)
                self.cell(0, 6, clean_text(f"Study: {study.get('study')} | Type: {study.get('type')}"), 0, 1)
                
                self.set_font('Arial', '', 9)
                self.set_text_color(0)
                self.multi_cell(0, 5, clean_text(f"Population: {study.get('population')}"))
                self.multi_cell(0, 5, clean_text(f"Methods: {study.get('methods')}"))
                
                # RESTORED: Score Contribution
                if 'score_contribution' in study:
                    self.set_font('Arial', 'B', 9)
                    self.cell(0, 5, clean_text(f"Contributes to: {study.get('score_contribution')}"), 0, 1)

                self.ln(2)
                self.set_fill_color(250, 250, 250)
                self.set_font('Arial', 'I', 9)
                self.multi_cell(0, 5, clean_text(f"Critique: {study.get('critique', '')}"), border=1, fill=True)
                self.ln(4)

        # --- RESTORED: CITATIONS (PMIDs) ---
        citations = data.get("citations", [])
        if citations:
            self.set_y(-30) # Anchor to bottom of page
            self.set_font('Arial', 'B', 8)
            self.set_text_color(100)
            self.cell(0, 5, "PUBLICATION IDs (PubMed):", 0, 1)
            self.set_font('Arial', '', 8)
            self.multi_cell(0, 4, clean_text(", ".join(citations)))

def generate_reference_pdf():
    print("📖 Initializing Clinical Deep Dive Generator...")
    
    if not os.path.exists(EVIDENCE_PATH):
        print(f"❌ Cannot find {EVIDENCE_PATH}")
        return

    # Create assets dir if it doesn't exist to hold your avatar
    if not os.path.exists(ASSETS_DIR): os.makedirs(ASSETS_DIR)
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

    with open(EVIDENCE_PATH, 'r', encoding='utf-8') as f:
        db = json.load(f)

    # 1. Group genes by PRIMARY ORGAN
    organ_groups = {}
    for key, data in db.items():
        organs = data.get("affected_organs", [])
        primary_organ = organs[0] if organs else "Systemic"
        if primary_organ not in organ_groups: organ_groups[primary_organ] = []
        organ_groups[primary_organ].append((key, data))

    # 2. Build PDF and internal links
    pdf = DeepDivePDF('P', 'mm', 'A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Generate link anchors for each organ
    organ_links = {organ: pdf.add_link() for organ in organ_groups.keys()}

    # Page 1: Interactive Avatar Map
    pdf.add_toc_avatar_page(organ_links)

    # Iterate through Organs
    for organ, genes in sorted(organ_groups.items()):
        # Pass the specific link anchor for this chapter
        pdf.add_section_title(f"{organ} System", organ_links[organ])
        
        for gene_key, gene_data in genes:
            pdf.render_gene_page(gene_key, gene_data)

    pdf.output(OUTPUT_PDF)
    print(f"\n✅ Success! PDF saved to {OUTPUT_PDF}")
    if not os.path.exists(AVATAR_IMG):
        print(f"💡 Tip: Place a transparent PNG named 'human_body.png' in the '{ASSETS_DIR}' folder to complete the Avatar map!")

if __name__ == "__main__":
    generate_reference_pdf()