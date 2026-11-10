"""Reference data for the nutrition module, from official sources. Holds no genotypes.

    python -m cluster_analysis.nutrition.nutrition_reference nnr       # NNR 2023 intake values from the Swedish Food Agency's summary
    python -m cluster_analysis.nutrition.nutrition_reference pgs       # PGS Catalog scoring files named in nutrients.json

Sources
  nnr    "Referensvärden för energi och näringsämnen. En sammanfattning av de nordiska näringsrekommendationerna,
         NNR 2023" (Livsmedelsverket, revised June 2025, errata September 2025 applied), tables 7-10 (RI, AI) and 16 (UL).
         scripts/fetch_nutrition_reference.sh downloads the PDF; this parses it into cluster_analysis/nutrition/nnr_2023.json
         (adults; the values are public and carry the citation, so the JSON is kept in git).
  pgs    PGS Catalog harmonised scoring files (on the build in genome/build.py): https://www.pgscatalog.org
"""
import argparse
import gzip
import json
import os
import re
import sys
import time
import urllib.request

from genome import build as gbuild

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = "data/reference/nutrition"
NNR_PDF = f"{OUT}/snr_2023.pdf"
NNR_JSON = os.path.join(HERE, "nnr_2023.json")
NUTRIENTS = os.path.join(HERE, "nutrients.json")
PGS_FTP = "https://ftp.ebi.ac.uk/pub/databases/spot/pgs/scores/{id}/ScoringFiles/Harmonized/{id}_{suffix}.txt.gz"
PGS_API = "https://www.pgscatalog.org/rest/score/{id}"


def _get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


# --- NNR 2023 (Livsmedelsverket's summary) --------------------------------------------------------------------------

ADULT_AGES = ("18–24 år", "25–50 år", "51–70 år", "> 70 år")
# Footnote markers printed against adult cells, which the text extraction glues onto the value ("3306" = 330 + note 6).
# (table, sex, age, column) -> the footnote number; checked against the table's own footnote list below.
FOOTNOTES = {
    (7, "women", "18–24 år", "Folat"): "6", (7, "women", "25–50 år", "Folat"): "6",
    (7, "women", "> 70 år", "Vitamin D"): "8", (7, "men", "> 70 år", "Vitamin D"): "8",
    (9, "women", "18–24 år", "Järn"): "6", (9, "women", "25–50 år", "Järn"): "6", (9, "women", "51–70 år", "Järn"): "7",
}
TABLES = {  # table number: (kind, columns with units, as printed)
    7: ("RI", [("Vitamin A", "µg RE"), ("Vitamin D", "µg"), ("Tiamin", "mg/MJ"), ("Riboflavin", "mg"),
               ("Niacin", "NE/MJ"), ("Vitamin B6", "mg"), ("Folat", "µg"), ("Vitamin C", "mg")]),
    8: ("AI", [("Vitamin E", "mg α-TE"), ("Vitamin K", "µg"), ("Pantotensyra", "mg"), ("Biotin", "µg"),
               ("Vitamin B12", "µg"), ("Kolin", "mg")]),
    9: ("RI", [("Kalcium", "mg"), ("Järn", "mg"), ("Zink", "mg"), ("Koppar", "µg")]),
    10: ("AI", [("Fosfor", "mg"), ("Kalium", "mg"), ("Magnesium", "mg"), ("Jod", "µg"), ("Selen", "µg"),
                ("Fluor", "mg"), ("Mangan", "mg"), ("Molybden", "µg")]),
}
NOTES = {  # the footnotes that bear on adults, verbatim from the PDF (checked to be present in it)
    ("Vitamin D", "all"): "För personer med lite eller ingen solexponering rekommenderas 20 μg per dag.",
    ("Vitamin D", "> 70 år"): "20 µg gäller för åldergruppen 75 år och äldre.",
    ("Järn", "women"): "15 mg för de som menstruerar.",
    ("Järn", "women "): "Vid kraftiga menstruationsblödningar rekommenderas undersökning av järnstatus och intag av tillskott vid behov.",
    ("Järn", "all"): "Beräknat utifrån en blandkost med animalier och vegetabilier och intag av fytinsyra på omkring 600 mg/d.",
    ("Zink", "all"): "Beräknat utifrån en blandkost med animalier och vegetabilier och intag av fytinsyra på omkring 600 mg/d.",
    ("Folat", "women"): "De flesta nationella myndigheter i de nordiska och baltiska länderna rekommenderar kosttillskott på 400 "
                        "μg utöver intaget från kosten för kvinnor i fertil ålder från att graviditet planeras till och med "
                        "graviditetens första trimester.",
}
UL_ROWS = {  # Table 16, as printed: name -> (unit, value); the line carries footnote digits after the name
    "Kalcium": ("mg/d", 2500), "Koppar": ("mg/d", 5), "Jod": ("µg/d", 600), "Järn": ("mg/d", 60),
    "Magnesium": ("mg/d", 250), "Fosfor": ("mg/d", 3000), "Selen": ("µg/d", 255), "Zink": ("mg/d", 25),
    "Folsyra (syntetisk)": ("µg/d", 1000), "Vitamin A": ("µg RE/d", 3000), "Vitamin B6": ("mg/d", 12),
    "Vitamin D": ("µg/d", 100), "Vitamin E": ("mg/d", 300),
}
UL_NOTES = {"Magnesium": "Gäller magnesiumsalter och föreningar i kosttillskott, vatten eller tillsatser, inte magnesium "
                         "som förekommer naturligt i mat och dryck.",
            "Vitamin A": "Retinol och retinylestrar.", "Folsyra (syntetisk)": "Syntetisk folsyra (tillskott, berikning)."}


# Definitions and statements quoted from the summary (checked to be in it)
QUOTES = {
    "RI": "RI (recommended intake) för vitaminer och mineraler baseras på AR och en marginal som ska täcka behovet hos "
          "praktiskt taget alla individer i en definierad grupp (utifrån kön, ålder, graviditet, amning) i den allmänna "
          "befolkningen.",
    "AI": "AI förväntas motsvara eller överstiga behovet hos de flesta individer i en definierad grupp.",
    "UL": "UL (upper intake level) anger den högsta mängden av ett näringsämne som kan intas under lång tid utan att "
          "sannolikt ge negativa hälsoeffekter.",
    "supplements": "Bland friska personer som äter en varierad och energimässigt tillräcklig kost har långvarigt intag av "
                   "näringsämnen från kosttillskott generellt inte visats vara hälsofrämjande eller kunnat kopplas till "
                   "minskad risk för sjukdomar relaterade till levnadsvanor.",
    "b12_vegan": "Tillskott av vitamin B12 är exempelvis nödvändigt om animaliska livsmedel helt utesluts från kosten.",
    "vitd_75": "Tillskott av vitamin D rekommenderas till spädbarn och kan även behövas för kvinnor som försöker att bli "
               "gravida, är gravida eller ammar samt kvinnor och män över 75 år.",
}
# Fatty acids as a share of energy (E%), from the bullet list under table 4
FATS = {
    "n-3": {"min_e": 1.0, "quote": "Intaget av cis-fleromättade fettsyror bör vara 5–10 E%, varav n-3-fettsyror bör bidra med minst 1 E%."},
    "ALA": {"min_e": 0.5, "quote": "Linolsyra (n-6) och alfa-linolensyra (n-3) är essentiella fettsyror och bör bidra med minst 3 E%, varav minst 0,5 E% som alfa-linolensyra."},
}
KJ_PER_G_FAT = 37  # "fett, kolhydrater och protein, vilka generellt bidrar med omkring 37 kJ/g" (page 11)


def _num(s):
    return float(s.replace(",", "."))


def parse_nnr(text):
    """{nutrient: {kind, unit, women: {age: value}, men: {...}}} from the extracted text of the summary's tables."""
    pages = re.split(r"=== PAGE \d+\n", text)
    out = {}
    for no, (kind, cols) in TABLES.items():
        page = next(p for p in pages if f"Tabell {no}." in p)
        sex = None
        for line in page.splitlines():
            if line.startswith(("KVINNOR", "MÄN")):
                sex = "women" if line.startswith("KVINNOR") else "men"
                continue
            age = next((a for a in ADULT_AGES if line.startswith(a)), None)
            if not sex or not age:
                continue
            cells = line[len(age):].split()
            if len(cells) != len(cols):
                raise ValueError(f"table {no} {sex} {age}: {len(cells)} cells, expected {len(cols)}: {line}")
            for (name, unit), cell in zip(cols, cells):
                note = FOOTNOTES.get((no, sex, age, name))
                if note:
                    if not cell.endswith(note):
                        raise ValueError(f"table {no} {sex} {age} {name}: {cell} lacks footnote {note}")
                    cell = cell[:-len(note)]
                elif not re.fullmatch(r"\d+(,\d+)?", cell):
                    raise ValueError(f"table {no} {sex} {age} {name}: unexpected cell {cell}")
                d = out.setdefault(name, {"kind": kind, "unit": unit, "table": no, "women": {}, "men": {}})
                d[sex][age] = _num(cell)
        for d in out.values():
            if d["table"] == no and (len(d["women"]) != 4 or len(d["men"]) != 4):
                raise ValueError(f"table {no}: missing adult rows")
    # Upper levels (table 16): "Name<footnotes> unit value" somewhere on the page
    page = next(p for p in pages if "Tabell 16." in p)
    for name, (unit, value) in UL_ROWS.items():
        m = re.search(re.escape(name) + r"[\d,]*\s+" + re.escape(unit) + r"\s+([\d,]+)", page)
        if not m or _num(m.group(1)) != value:
            raise ValueError(f"UL {name}: not found as {value} {unit}")
        key = "Folat" if name.startswith("Folsyra") else name
        # Two limits leave food alone: magnesium's covers supplements and additives, folate's synthetic folic acid
        out.setdefault(key, {})["ul"] = {"value": value, "unit": unit, "note": UL_NOTES.get(name),
                                         "applies_to_food": name not in ("Magnesium", "Folsyra (syntetisk)")}
    # Words must match; layout noise (line breaks, soft hyphens, stray footnote digits) is ignored
    # (and a word hyphenated across lines, "levnads-\nvanor", is joined)
    bare = lambda t: re.sub(r"[\s\d­-]+", "", re.sub(r"[-­]\s*\n", "", t).replace("μ", "µ"))
    flat = bare(text)
    for (name, who), note in NOTES.items():
        if bare(note) not in flat:
            raise ValueError(f"note for {name} not found in the PDF text: {note[:50]}")
        out[name].setdefault("notes", []).append({"applies": who.strip(), "text": note})
    for key, quote in list(QUOTES.items()) + [(k, v["quote"]) for k, v in FATS.items()]:
        if bare(quote) not in flat:
            raise ValueError(f"{key}: quote not found in the PDF text: {quote[:50]}")
    return out


def parse_energy(text):
    """Table 1: reference energy intake (MJ/d) for adults at PAL 1.4, 1.6 and 1.8, with the reference weight."""
    page = next(p for p in re.split(r"=== PAGE \d+\n", text) if "Tabell 1." in p)
    out, sex = {"women": {}, "men": {}}, None
    for line in page.splitlines():
        if line.startswith(("KVINNOR", "MÄN", "GRAVIDA", "AMMANDE")):
            sex = {"K": "women", "M": "men"}.get(line[0])
            continue
        age = next((a for a in ADULT_AGES if line.startswith(a)), None)
        if sex and age:
            cells = [_num(c) for c in line[len(age):].split()]
            if len(cells) != 5:
                raise ValueError(f"table 1 {sex} {age}: {line}")
            out[sex][age] = {"weight_kg": cells[0], "ree": cells[1], "low": cells[2], "medium": cells[3], "active": cells[4]}
    if any(len(v) != 4 for v in out.values()):
        raise ValueError("table 1: missing adult rows")
    return out


def build_nnr():
    import pdfplumber  # pip install pdfplumber
    with pdfplumber.open(NNR_PDF) as pdf:
        text = "".join(f"=== PAGE {i + 1}\n{p.extract_text() or ''}\n" for i, p in enumerate(pdf.pages))
    values = parse_nnr(text)
    doc = {"source": "Livsmedelsverket (2023, reviderad juni 2025). Referensvärden för energi och näringsämnen. En "
                     "sammanfattning av de nordiska näringsrekommendationerna, NNR 2023. Tabell 7–10 och 16. Errata "
                     "september 2025 tillämpad.",
           "url": "https://www.livsmedelsverket.se/globalassets/publikationsdatabas/broschyrer-foldrar/"
                  "slutleverans_nordiska-naringsrekommendationer-2023.pdf",
           "definitions": {k: QUOTES[k] for k in ("RI", "AI", "UL")},
           "statements": {k: QUOTES[k] for k in ("supplements", "b12_vegan", "vitd_75")},
           "energy_mj": parse_energy(text), "fats_energy_percent": FATS, "kj_per_g_fat": KJ_PER_G_FAT,
           "nutrients": values}
    with open(NNR_JSON, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {NNR_JSON}: {len(values)} nutrients")


# --- PGS Catalog ----------------------------------------------------------------------------------------------------

def fetch_pgs():
    cfg = json.load(open(NUTRIENTS, encoding="utf-8"))
    ids = sorted({m["pgs"] for n in cfg["nutrients"] for m in n["markers"] if m.get("pgs")})
    os.makedirs(f"{OUT}/pgs", exist_ok=True)
    suffix = gbuild.pgs_suffix()
    for pid in ids:
        path = f"{OUT}/pgs/{pid}_{suffix}.txt.gz"
        if not os.path.exists(path):
            print("downloading", pid)
            urllib.request.urlretrieve(PGS_FTP.format(id=pid, suffix=suffix), path)
        meta = f"{OUT}/pgs/{pid}.json"
        if not os.path.exists(meta):
            json.dump(_get(PGS_API.format(id=pid)), open(meta, "w", encoding="utf-8"), ensure_ascii=False)
    print("PGS files:", ", ".join(ids))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("nnr", "pgs"))
    a = ap.parse_args()
    {"nnr": build_nnr, "pgs": fetch_pgs}[a.what]()
