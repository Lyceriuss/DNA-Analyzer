"""Builds docs/outreach/DNA-Analyzer_Ask_MCP-LLM-feature_en.pdf for an investor: three pages with everything worth knowing, then the
depth (a real conversation, under the hood, asynchronous work, token use, models and accounts, cloud and revenue).
Every figure comes from the code or a recorded run: ask_tokens.json and ask_example_turns.json (ask_token_measure.py),
the charts in img/ (ask_charts.py), and the screenshots in img/."""
import json
import math
import os

from PIL import Image as PILImage
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "img")
OUT = os.path.join(HERE, "DNA-Analyzer_Ask_MCP-LLM-feature_en.pdf")
EX = json.load(open(os.path.join(HERE, "ask_example_turns.json"), encoding="utf-8"))
TOK = json.load(open(os.path.join(HERE, "ask_tokens.json")))
A = TOK["average"]

F = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("Body", F + r"\segoeui.ttf"))
pdfmetrics.registerFont(TTFont("Bold", F + r"\segoeuib.ttf"))
pdfmetrics.registerFont(TTFont("Light", F + r"\segoeuil.ttf") if os.path.exists(F + r"\segoeuil.ttf") else TTFont("Light", F + r"\segoeui.ttf"))
pdfmetrics.registerFont(TTFont("Ital", F + r"\segoeuii.ttf") if os.path.exists(F + r"\segoeuii.ttf") else TTFont("Ital", F + r"\ariali.ttf"))
pdfmetrics.registerFont(TTFont("Mono", F + r"\consola.ttf"))
registerFontFamily("Body", normal="Body", bold="Bold", italic="Ital", boldItalic="Bold")

INK, MUTED, TEAL, LINE, PALE = (colors.HexColor(c) for c in ("#1d2430", "#5b6472", "#0f766e", "#d5dbe3", "#eef5f4"))
WIDTH = 174 * mm
S = {
    "kicker": ParagraphStyle("k", fontName="Bold", fontSize=9, leading=12, textColor=TEAL, spaceAfter=4),
    "title": ParagraphStyle("t", fontName="Bold", fontSize=26, leading=31, textColor=INK, spaceAfter=8),
    "lead": ParagraphStyle("l", fontName="Light", fontSize=12.6, leading=18.5, textColor=INK, spaceAfter=10),
    "h1": ParagraphStyle("h1", fontName="Bold", fontSize=17, leading=22, textColor=INK, spaceBefore=4, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="Bold", fontSize=11.4, leading=15, textColor=TEAL, spaceBefore=10, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Body", fontSize=9.8, leading=14.2, textColor=INK, spaceAfter=6, alignment=TA_LEFT),
    "point": ParagraphStyle("pt", fontName="Body", fontSize=9.8, leading=14.2, textColor=INK, spaceAfter=0),
    "li": ParagraphStyle("li", fontName="Body", fontSize=9.8, leading=14, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=3),
    "cell": ParagraphStyle("c", fontName="Body", fontSize=8.7, leading=11.6, textColor=INK),
    "cellb": ParagraphStyle("cb", fontName="Bold", fontSize=8.7, leading=11.6, textColor=INK),
    "note": ParagraphStyle("n", fontName="Body", fontSize=8.3, leading=11.6, textColor=MUTED, spaceAfter=6),
    "big": ParagraphStyle("b", fontName="Bold", fontSize=20, leading=23, textColor=TEAL),
    "small": ParagraphStyle("s", fontName="Body", fontSize=8.4, leading=11.4, textColor=MUTED),
}
for k in ("h1", "h2", "kicker", "title"):
    S[k].keepWithNext = 1


def code(t):
    return f'<font name="Mono" size="8.5">{t}</font>'


def P(t, s="p"):
    return Paragraph(t, S[s])


def bullets(items):
    return [Paragraph(t, S["li"], bulletText="\u2022") for t in items]


def table(rows, widths, head=True, zebra=False):
    data = [[Paragraph(c, S["cellb" if (head and i == 0) else "cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
          ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if head:
        st += [("BACKGROUND", (0, 0), (-1, 0), PALE), ("LINEBELOW", (0, 0), (-1, 0), 0.8, TEAL)]
    t.setStyle(TableStyle(st))
    return t


def picture(name, width=WIDTH, caption=None, border=True):
    w, h = PILImage.open(os.path.join(IMG, name)).size
    img = Image(os.path.join(IMG, name), width=width, height=width * h / w)
    img.hAlign = "LEFT"
    out = [img]
    if caption:
        out += [Spacer(1, 3), P(caption, "note")]
    return KeepTogether(out)


def numbers(items):
    """A row of big figures with a line under each."""
    cells = [[Paragraph(a, S["big"]) for a, _ in items], [Paragraph(b, S["small"]) for _, b in items]]
    w = WIDTH / len(items)
    t = Table(cells, colWidths=[w] * len(items))
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 1),
                           ("LINEABOVE", (0, 0), (-1, 0), 1.4, TEAL)]))
    return t


def point(n, title, body):
    """A numbered point of the first pages: a big number, a bold title and a few lines."""
    num = Paragraph(f'<font name="Bold" size="17" color="#0f766e">{n}</font>', S["p"])
    txt = [Paragraph(f'<font name="Bold" size="11">{title}</font>', S["point"]), Spacer(1, 2), Paragraph(body, S["point"])]
    t = Table([[num, txt]], colWidths=[11 * mm, WIDTH - 11 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    return t


def callout(title, body):
    """A tinted box with a bold title, for the one sentence a reader should take away."""
    t = Table([[[Paragraph(f'<font name="Bold" size="10.5" color="#0f766e">{title}</font>', S["point"]), Spacer(1, 3),
                 Paragraph(body, S["point"])]]], colWidths=[WIDTH])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("LINEBEFORE", (0, 0), (0, -1), 3, TEAL),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                           ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    return t


def chain():
    """Page 1's five steps of a question, as linked chips."""
    W, H = WIDTH, 22 * mm
    d = Drawing(W, H)
    steps = [("Ask", "a plain question, in", "the person's own words"),
             ("Read and plan", "the model states how it", "read it, and its plan"),
             ("Your results", "read on the device,", "shown to the person"),
             ("Research", "public studies and", "databases, by tool"),
             ("Checked answer", "every source and figure", "traced before it shows")]
    n, gap = len(steps), 5 * mm
    w = (W - gap * (n - 1)) / n
    for k, (t, l1, l2) in enumerate(steps):
        x = k * (w + gap)
        fill = TEAL if k == n - 1 else PALE
        d.add(Rect(x, 2, w, H - 4, rx=6, ry=6, fillColor=fill, strokeColor=TEAL, strokeWidth=0.8))
        tc = colors.white if k == n - 1 else INK
        sc = colors.HexColor("#d9f0ec") if k == n - 1 else MUTED
        d.add(String(x + 7, H - 15, f"{k + 1}  {t}", fontName="Bold", fontSize=9, fillColor=tc))
        d.add(String(x + 7, H - 29, l1, fontName="Body", fontSize=7.4, fillColor=sc))
        d.add(String(x + 7, H - 39, l2, fontName="Body", fontSize=7.4, fillColor=sc))
        if k < n - 1:
            ax = x + w + 1
            d.add(Polygon([ax, H / 2 + 4, ax + gap - 2, H / 2, ax, H / 2 - 4], fillColor=TEAL, strokeColor=TEAL))
    return d


def diagram():
    """One Ask question, in layers: the app, the agent engine with its guardrails, the two data stores, and the cloud
    services the user chooses, with the device boundary that nothing personal crosses."""
    W, H = WIDTH, 76 * mm
    d = Drawing(W, H)
    GREY = colors.HexColor("#9aa5b1")

    def box(x, y, w, h, title, lines, fill=colors.white, stroke=LINE, first=None):
        d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=0.9))
        d.add(String(x + 7, y + h - 13, title, fontName="Bold", fontSize=8.6, fillColor=INK))
        rows = ([(first, TEAL)] if first else []) + [(ln, MUTED) for ln in lines]
        for k, (ln, col) in enumerate(rows):
            d.add(String(x + 7, y + h - 25 - k * 9.6, ln, fontName="Body", fontSize=7.4, fillColor=col))

    def arrow(x1, y1, x2, y2, both=True):
        d.add(Line(x1, y1, x2, y2, strokeColor=TEAL, strokeWidth=1.2))
        for (xa, ya, xb, yb) in ([(x1, y1, x2, y2)] + ([(x2, y2, x1, y1)] if both else [])):
            a = math.atan2(yb - ya, xb - xa)
            d.add(Polygon([xb, yb, xb - 5.5 * math.cos(a - 0.45), yb - 5.5 * math.sin(a - 0.45),
                           xb - 5.5 * math.cos(a + 0.45), yb - 5.5 * math.sin(a + 0.45)], fillColor=TEAL, strokeColor=TEAL))

    dev = 112 * mm
    d.add(Rect(1, 1, dev, H - 2, rx=9, ry=9, fillColor=colors.HexColor("#f7fbfa"), strokeColor=TEAL, strokeWidth=1,
               strokeDashArray=[4, 2]))
    d.add(String(8, H - 13, "ON THE PERSON'S DEVICE", fontName="Bold", fontSize=8, fillColor=TEAL))
    cx = 118 * mm
    d.add(Rect(cx, 1, W - cx - 1, H - 2, rx=9, ry=9, fillColor=None, strokeColor=GREY, strokeWidth=0.8, strokeDashArray=[4, 2]))
    d.add(String(cx + 7, H - 13, "CLOUD SERVICES", fontName="Bold", fontSize=8, fillColor=MUTED))

    # the app
    box(5 * mm, 55 * mm, 70 * mm, 12 * mm, "Ask, in the app", ["asks, streams every step live, draws the answer"])
    # the agent engine
    ey, eh = 22 * mm, 26 * mm
    box(5 * mm, ey, dev - 9 * mm, eh, "Agent engine: one question, with guardrails", [], fill=PALE, stroke=TEAL)
    steps = ["understand the question", "resolve the names", "read the person's results", "research what's missing",
             "draw the explorer's views", "answer, checked by guardrails", "pick the person's readings", "save for follow-ups"]
    for k, t in enumerate(steps):
        col, row = k // 4, k % 4
        x = 5 * mm + 8 + col * 50 * mm
        y = ey + eh - 26 - row * 10.4
        d.add(String(x, y, str(k + 1), fontName="Bold", fontSize=8, fillColor=TEAL))
        d.add(String(x + 9, y, t, fontName="Body", fontSize=7.6, fillColor=INK))
    # the data
    box(5 * mm, 4 * mm, 49 * mm, 12 * mm, "The person's data", ["DNA, imputed calls, results"])
    box(59 * mm, 4 * mm, 49 * mm, 12 * mm, "Public research data", ["index, cache, theme graphs"])
    # the cloud
    box(cx + 3 * mm, ey, W - cx - 6 * mm, eh, "The user's model", ["Claude Sonnet: the conversation", "Claude Haiku: the readings",
                                                                   "their own key or Claude plan"], first="prompts and tool calls")
    box(cx + 3 * mm, 4 * mm, W - cx - 6 * mm, 15 * mm, "Research sources", ["Europe PMC, UniProt, ClinPGx"],
        first="public ids and names only")
    # arrows
    arrow(30 * mm, 55 * mm, 30 * mm, ey + eh)
    d.add(Rect(32 * mm, 49.6 * mm, 18 * mm, 3.6 * mm, fillColor=colors.HexColor("#f7fbfa"), strokeColor=None))
    d.add(String(32.5 * mm, 50.4 * mm, "live events", fontName="Body", fontSize=7, fillColor=TEAL))
    arrow(dev - 4 * mm, ey + eh / 2, cx + 3 * mm, ey + eh / 2)
    arrow(29 * mm, 16 * mm, 29 * mm, ey)
    arrow(83 * mm, 16 * mm, 83 * mm, ey)
    arrow(108 * mm, 10 * mm, cx + 3 * mm, 10 * mm)
    d.add(String(dev - 6, 6, "nothing personal crosses this line", fontName="Bold", fontSize=6.6, fillColor=TEAL, textAnchor="end"))
    return d


T1, T2, T3 = EX
CONV = sum(t["usd"] + t["readings_usd"] for t in EX)
SENT_BACK = sum(len(t["rejections"]) for t in EX)
NAIVE_X = A["opus_no_cache_raw_tools"] / A["actual"]

story = []

# =====================================================================================================================
# Page 1: the opening
story += [P("DNA-ANALYZER \u00b7 ASK", "kicker"),
          P("Ask your own genome a question", "title"),
          P("A person types a plain question about their DNA, like <i>why should I care about this gene?</i> Ask answers from "
            "the public research behind it, checks every source before showing it, and keeps the DNA file on the person's "
            "own computer. It runs on their own Claude account, so a question costs a few cents and none of it passes "
            "through us.", "lead"),
          Spacer(1, 4),
          picture("t1_working.png", caption="Ask at work on a real question. It shows how it read the question and its plan first, "
                  "then every step as it runs: the person's own results (YOURS), public research (RESEARCH) and the explorer's "
                  "views (VIEW). On the right, the research sources light up as they are used; below, a live count of tokens "
                  "and cost."),
          Spacer(1, 10),
          numbers([(f"${A['actual']:.2f}", "a typical question, at API prices, measured over "
                                           f"{TOK['turns']} real questions"),
                   (f"{NAIVE_X:.0f}x", "cheaper than the same questions on a naive build"),
                   ("0", "DNA files sent anywhere: the analysis and the person's data stay on their computer"),
                   ("27", "research tools the model works through, from genes and drugs to papers")]),
          Spacer(1, 16), P("What happens when someone asks", "h2"), Spacer(1, 4), chain()]

# =====================================================================================================================
# Pages 2-3: everything worth knowing
story += [PageBreak(), P("Everything worth knowing, in two pages", "h1"),
          P("The rest of this document shows how each point works, with a real conversation, the code behind it and the "
            "measurements. If you read only this, you have the essentials.", "note"), Spacer(1, 4)]
story.append(point(1, "It answers real questions about a real genome",
    "Ask sits inside DNA-Analyzer, the desktop app that reads a consumer DNA test (MyHeritage, 23andMe, AncestryDNA), "
    "imputes the positions the chip didn't measure, and analyses it against public research. The person asks in plain "
    "words; a language model reads the question, works through the app's 27 tools, and answers with the person's own "
    "results, the studies behind them, and what the evidence can't tell. Follow-up questions continue the conversation."))
story.append(point(2, "Private by design, not by promise",
    "The model never touches files. It can only call tools, and the tools decide what goes back. Public tools return "
    "research facts. Personal tools put the person's results on their screen and give the model, at most, an interpreted "
    "summary of the items the question touched (\u201cCYP2C9 normal metaboliser\u201d), or only the kind of result if the "
    "user turns sharing off. The DNA file and the raw genotypes are never sent. Searches are built from public names only, "
    "so even the queries reveal nothing about the genome."))
story.append(point(3, "Answers you can check",
    "Every tool result is recorded in a ledger. Before the person sees an answer, the server checks it: each citation "
    "must be one a tool returned, each highlighted figure must appear in its source, clinical-advice wording is "
    "refused, and a question about what works can't be answered without research by genotype. A failed check goes back "
    f"to the model with the reasons. In the three-question conversation in this document, that happened {SENT_BACK} times, "
    "and each time the answer came back more complete."))
story.append(point(4, "Asynchronous and live",
    "Asking returns at once: the question runs as a background job, and the page streams its steps as they happen, the "
    "plan first, then each lookup, with the research sources lighting up and a live token and cost counter. Around the "
    "model, work runs in parallel: independent lookups overlap (one recorded question made 29 tool calls in 178 seconds, "
    "up to 4 at once), and the small model writes its readings in parallel batches."))
story.append(point(5, "Cheap by construction: tiered inference and context engineering",
    f"A question costs ${A['actual']:.3f} on average at API prices. Each job runs on the cheapest tier that can do it: "
    "rules with no model for matching and checking, the small Haiku model for bulk writing done once for everyone, the "
    "mid-size Sonnet model at medium effort for the conversation, and the large Opus model only for deep research. "
    "Around them, context engineering: prompt caching re-reads the stable part of every request at a tenth of the price, "
    "tool results are compact and capped, and a lookup budget puts a ceiling on every question."))
story.append(point(6, "Agentic, MCP-native and model-agnostic",
    "Ask is an agentic loop: the model plans, calls tools, reads the results and decides the next step until it can "
    "answer. Its tools are a Model Context Protocol (MCP) server, and the guardrails run inside that server, so the model "
    "is a guest: today the user's own Claude, through an API key or their Claude login; Gemini or another model is an "
    "integration, not a rebuild. The user brings the model, so we carry no inference bill and hold no genetic data."))
story.append(point(7, "Built to slot into a larger architecture, and to earn",
    "Running on the person's own device is a choice, not a limit. The public half, the research tools, already runs as a "
    "remote MCP server behind an OAuth 2.1 sign-in that other apps and agents can call; the personal half stays on the "
    "device as a local MCP server. That opens hosted tools, research-data subscriptions and managed model access, with measured unit "
    f"costs: about ${A['actual']:.2f} of model use per question, and roughly 11 minutes of a desktop processor to impute "
    "one genome with the new compact reference panel."))
story += [Spacer(1, 2), picture("waterfall.png", width=118 * mm, caption="Point 5 in one chart: the average question as "
                                  "built, against the same questions on a naive build, measure by measure."),
          picture("tiers.png", width=118 * mm, caption="Tiered inference: cheap models for the high-volume work, the mid-size "
                  "model for the conversation, the large one only for deep research (measured, API prices)."),
          P("In the rest of the document", "h2"),
          table([["", ""],
                 ["Ask in a larger architecture", "Agentic patterns, tiered inference with measured costs, the hosted "
                                                  "architecture, and how it maps onto AWS, Azure and Google Cloud"],
                 ["A real conversation", "Three questions, six screenshots, and what happened under each: tool calls, checks, tokens, cost"],
                 ["Under the hood", "The flow of a question, its eight steps, the 27 tools, what the model sees, how answers are checked"],
                 ["Asynchronous by design", "Background jobs, live streaming, parallel lookups and batches, with a measured timeline"],
                 ["Keeping token use low", "Nine measures, how each is done, and what each saves"],
                 ["Models, accounts and the cloud", "Claude, MCP, Gemini, OAuth: what runs today and what is next"],
                 ["Cloud computing and revenue", "Revenue options with their measured unit costs, and what each needs"],
                 ["Appendix", "Backends, the key, other ways in, where data is kept, methods"]],
                [44 * mm, WIDTH - 44 * mm], head=False)]

# =====================================================================================================================
# Ask in a larger architecture


def hosted_diagram():
    """The hosted platform: clients, an MCP gateway, hosted public MCP servers, a model router with tiers, and the
    personal MCP server that stays on the device."""
    W, H = WIDTH, 96 * mm
    d = Drawing(W, H)

    def box(x, y, w, h, title, lines, fill=colors.white, stroke=LINE, tcol=INK):
        d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=0.8))
        d.add(String(x + 6, y + h - 12, title, fontName="Bold", fontSize=8, fillColor=tcol))
        for i, ln in enumerate(lines):
            d.add(String(x + 6, y + h - 22.5 - i * 9, ln, fontName="Body", fontSize=6.9, fillColor=MUTED))

    def arrow(x1, y1, x2, y2, both=False, dash=None):
        d.add(Line(x1, y1, x2, y2, strokeColor=TEAL, strokeWidth=1, strokeDashArray=dash))
        for (xa, ya, xb, yb) in ([(x1, y1, x2, y2)] + ([(x2, y2, x1, y1)] if both else [])):
            a = math.atan2(yb - ya, xb - xa)
            d.add(Polygon([xb, yb, xb - 5 * math.cos(a - 0.45), yb - 5 * math.sin(a - 0.45),
                           xb - 5 * math.cos(a + 0.45), yb - 5 * math.sin(a + 0.45)], fillColor=TEAL, strokeColor=TEAL))

    # left column: the person's device with the local MCP server
    d.add(Rect(1, 1, 52 * mm, H - 2, rx=8, ry=8, fillColor=None, strokeColor=TEAL, strokeWidth=0.8, strokeDashArray=[3, 2]))
    d.add(String(6, H - 11, "The person's device", fontName="Bold", fontSize=8, fillColor=TEAL))
    box(4, 56 * mm, 48 * mm, 26 * mm, "Client", ["desktop app, phone or web app,", "or any MCP-capable agent", "(Claude Desktop, Gemini CLI ...)"])
    box(4, 6 * mm, 48 * mm, 42 * mm, "Local MCP server (personal)", ["my_* tools: the person's results", "DNA file and imputation",
        "readings picked here", "never leaves the device"], fill=PALE, stroke=TEAL)
    arrow(28 * mm, 48 * mm, 28 * mm, 56 * mm, both=True)
    # middle: the gateway and the hosted public servers
    box(60 * mm, 60 * mm, 54 * mm, 30 * mm, "MCP gateway", ["Streamable HTTP, OAuth 2.1", "rate limits, metering, billing",
        "routes tool calls by server"], fill=PALE, stroke=TEAL)
    box(60 * mm, 26 * mm, 54 * mm, 28 * mm, "Hosted MCP servers (public)", ["research tools: genes, variants,", "drugs, clusters, papers",
        "research data as MCP resources"])
    box(60 * mm, 2 * mm, 54 * mm, 20 * mm, "Shared caches", ["lookups and readings written", "once, served to every tenant"])
    arrow(52 * mm, 72 * mm, 60 * mm, 75 * mm, both=True)
    arrow(87 * mm, 60 * mm, 87 * mm, 54 * mm, both=True)
    arrow(87 * mm, 26 * mm, 87 * mm, 22 * mm, both=True)
    # right: the model router and its tiers
    box(122 * mm, 60 * mm, 52 * mm, 30 * mm, "Model router", ["the agentic loop picks a tier", "per job; guardrails run in",
        "the servers, not the model"], fill=PALE, stroke=TEAL)
    tiers = [("Tier 0: rules", "no model"), ("Tier 1: Haiku", "bulk writing, routing"), ("Tier 2: Sonnet", "the conversation"),
             ("Tier 3: Opus", "deep research")]
    for i, (a, b) in enumerate(tiers):
        y = 44 * mm - i * 12 * mm
        box(122 * mm, y, 52 * mm, 10 * mm, a, [b])
    arrow(114 * mm, 75 * mm, 122 * mm, 75 * mm, both=True)
    arrow(148 * mm, 60 * mm, 148 * mm, 54 * mm)
    return d


story += [PageBreak(), P("Ask in a larger architecture", "h1"),
          P("Today Ask runs entirely on the person's own device, the strongest privacy promise a product can make. The design "
            "underneath is the same one a hosted, multi-client platform would use, and each pattern below is already in the "
            "code. This is how it maps onto the vocabulary of agentic systems, and what changes when it runs as a hosted platform.")]
story.append(table([["Pattern", "In Ask today", "Hosted, it becomes"],
    ["Agentic loop (tool use)", "The model plans, calls tools, reads results and decides the next step until it can answer; "
                                "16 steps at most, a lookup budget per question.", "The same loop, run by any client or agent "
                                "framework against our tools."],
    ["MCP-native tools", "27 tools as an MCP server on the device, driven by Claude Code; the 13 public ones also as a remote "
                         "MCP server over Streamable HTTP with OAuth 2.1 (built and tested).", "The remote server behind a "
                         "gateway with metering; research data exposed as MCP resources as well as tools."],
    ["Tiered inference (model routing)", "Rules, Haiku, Sonnet and Opus, each on the jobs it fits (below); a small model "
                                         "routes quick answers before anything is looked up.", "A router picks the tier per "
                                         "job and per customer plan; cost per answer stays predictable."],
    ["Context engineering", "Prompt caching, compact tool results, a lookup budget, short follow-up context.",
     "The same, plus shared caches across tenants: a lookup made once serves everyone."],
    ["Grounding and verification", "A ledger of every tool result; deterministic guardrails check citations, figures, "
                                   "advice wording and research coverage before anything is shown.", "A verification layer "
                                   "any model passes through: the trust lives in our servers, not in a model choice."],
    ["Local-first privacy split", "Personal tools read the person's data on the device; public tools see only public ids.",
     "Personal MCP server on the device, public MCP servers in the cloud: the compliance boundary doesn't move."],
    ["Bring your own model", "The user's Claude: an API key or their Claude login.", "Plus managed model access for users "
                                                                                    "without an account (metered)."],
    ["Observability", "Per-question token and cost telemetry, step traces, run logs with timestamps.", "Per-tenant metering "
                                                                                                     "and billing from the "
                                                                                                     "same records."]],
    [36 * mm, 70 * mm, WIDTH - 106 * mm]))

story += [CondPageBreak(100 * mm), P("Tiered inference, measured", "h2"),
          P("Cheap models do the high-volume work, the mid-size model does the conversation, and the large model is kept for "
            "the questions that need deep research. The difference between tiers is more than an order of magnitude, which "
            "is why placing each job on the right one matters."),
          table([["Tier", "Model", "Jobs", "Measured cost"],
                 ["0", "none: rules", "matching names to the explorer, result cards, every answer check", "$0"],
                 ["1", "Haiku 5.5", "readings for every possible result, written once for everyone; routing quick answers",
                  f"${T2['readings_usd']:.4f} for the readings in question 2, then cached for every future person"],
                 ["2", "Sonnet 5.5, medium effort", "the Ask conversation: planning, tool calls, the answer",
                  f"${A['actual']:.3f} a question (average of {TOK['turns']})"],
                 ["3", "Opus 5.5, adaptive thinking", "the deep research agent, from the command line and MCP",
                  "$0.94 to $1.01 a question (two recorded runs, 36 to 43 tool calls)"]],
                [12 * mm, 38 * mm, 70 * mm, WIDTH - 120 * mm]),
          P("Priced at API rates from recorded runs; the chart on page 3 shows the same. Tier 1's figure is a one-time cost: "
            "once written, a reading is reused for every person with that result.", "note")]

story += [CondPageBreak(110 * mm), P("As a hosted platform", "h2"),
          hosted_diagram(),
          P("A reference architecture for the hosted version. The client (the desktop app, a phone, or a third-party agent) "
            "keeps a local MCP server for everything personal. Public tool calls go through an MCP gateway that handles OAuth "
            "2.1, rate limits and metering, to hosted MCP servers that share one cache across every tenant. A model router "
            "places each job on its tier. The guardrails stay in the servers, so they hold whatever model or client is used.",
            "note")]
story += [CondPageBreak(90 * mm), P("On AWS, Azure or Google Cloud", "h2"),
          P("The hosted half is ordinary cloud building blocks: the MCP servers are containers, the research data is static "
            "files, the caches are key-value stores, and Claude is offered on all three clouds. So it fits one cloud, or "
            "several, without changing the design. An illustrative mapping (not deployed):"),
          table([["Component", "AWS", "Microsoft Azure", "Google Cloud"],
                 ["MCP gateway, OAuth 2.1", "Amazon API Gateway, Amazon Cognito", "Azure API Management, Microsoft Entra ID",
                  "Apigee or API Gateway, Identity Platform"],
                 ["Hosted MCP servers", "AWS Fargate (ECS) or Lambda", "Azure Container Apps or Functions", "Cloud Run"],
                 ["Research data, bundle", "Amazon S3, CloudFront", "Blob Storage, Azure Front Door", "Cloud Storage, Cloud CDN"],
                 ["Shared caches", "ElastiCache, DynamoDB", "Azure Cache for Redis, Cosmos DB", "Memorystore, Firestore"],
                 ["Model tiers (Claude)", "Amazon Bedrock: Haiku, Sonnet, Opus", "Microsoft Foundry: Claude models",
                  "Vertex AI: Claude (and Gemini)"],
                 ["Optional cloud imputation", "AWS Batch on Spot", "Azure Batch", "Batch on Spot VMs"],
                 ["Secrets and keys", "Secrets Manager, KMS", "Key Vault", "Secret Manager, Cloud KMS"],
                 ["Metering, observability", "CloudWatch, Marketplace metering", "Azure Monitor, Marketplace",
                  "Cloud Monitoring, Marketplace"],
                 ["A Nordic region", "eu-north-1 (Stockholm)", "Sweden Central", "europe-north1 (Finland)"]],
                [37 * mm, 45 * mm, 46 * mm, WIDTH - 128 * mm], zebra=True),
          P("What this buys an enterprise customer: model inference inside their own cloud account and region (Claude on "
            "Bedrock, Foundry or Vertex AI), billing through the cloud marketplace they already use, and the personal half "
            "still on the person's device. Running on several clouds at once is the same containers behind one gateway "
            "per cloud.", "note")]

story += [P("What hosting would add", "h2")] + bullets([
    "<b>Reach.</b> Any MCP-capable agent, ours or a partner's, can use the research tools; integration is a URL and an OAuth "
    "client, not a codebase.",
    "<b>Shared economics.</b> A lookup or a reading made for one user serves all of them; the cache that already makes a "
    "question cost cents gets cheaper with every customer.",
    "<b>Metering.</b> Tool calls and model tiers are already counted per question; per-tenant billing reads the same records.",
    "<b>The same privacy line.</b> The personal half never moves: hosting the public half doesn't put genetic data on our "
    "servers.",
])
story += [P("One question through the hosted version", "h2"),
          table([["", "Step", "Where it runs"],
                 ["1", "The person asks on their phone; the app's agentic loop starts.", "the device"],
                 ["2", "The personal tools read the person's results from the local MCP server; nothing personal leaves.",
                  "the device"],
                 ["3", "Public tool calls go to the MCP gateway with the app's OAuth 2.1 token; it checks the plan, the rate "
                       "limit, and meters the call.", "the cloud gateway"],
                 ["4", "The hosted MCP servers answer from the shared cache, or fetch from the research sources once and "
                       "cache it for everyone.", "the cloud, any region"],
                 ["5", "The model router puts each step on its tier: rules, Haiku, Sonnet, or Opus for deep research, on "
                       "Bedrock, Foundry or Vertex AI, or the person's own Claude account.", "the chosen cloud or provider"],
                 ["6", "The answer goes through the guardrails: citations, figures, advice wording, research coverage. A "
                       "failed check goes back to the model.", "our MCP servers"],
                 ["7", "The checked answer and the readings picked for the person are drawn on the device; the gateway "
                       "records the tokens and tool calls for billing.", "the device, the gateway"]],
                [8 * mm, 118 * mm, WIDTH - 126 * mm]),
          P("The same seven steps run today on one computer, with the gateway and router left out: the user's own model, "
            "and every server on the person's own computer.", "note")]

story += [CondPageBreak(95 * mm), P("Built and tested: the research tools as a remote MCP server", "h2"),
          P(f"The first piece of the hosted platform exists. {code('python -m cluster_analysis.agent remote')} serves the 13 "
            "public research tools over Streamable HTTP, protected the way the MCP authorization specification defines, so "
            "Claude or any other MCP client on another machine can connect with a proper sign-in. No personal tool sits behind "
            "it: nothing about anyone's genome can be reached through it."),
          table([["", "The sign-in, as the automated test runs it against a live server", "Standard"],
                 ["1", "A client calls the server without a token and is turned away with a pointer to the server's metadata.",
                  "RFC 9728"],
                 ["2", "The client reads where to sign in, and registers itself automatically.", "RFC 8414, RFC 7591"],
                 ["3", "It sends the person to sign in, with a one-time proof that only it can complete.", "OAuth 2.1, PKCE"],
                 ["4", "The person signs in; the client exchanges a single-use code for a token bound to this server.",
                  "RFC 8707"],
                 ["5", "With the token, the client opens an MCP session and sees exactly the public tools.", "MCP"],
                 ["6", "A wrong password, a reused code or a made-up token is refused.", ""]],
                [8 * mm, 136 * mm, WIDTH - 144 * mm]),
          Spacer(1, 4),
          P("<b>Tokens</b> come from a built-in sign-in for demos (tokens for an hour, rotating refresh tokens, revocation) or "
            "from your identity provider: Microsoft Entra ID, Auth0, Amazon Cognito, Keycloak or Google, checked against "
            "their published keys. <b>Not yet:</b> a public HTTPS address and stored sessions for a hosted service. In the "
            "repository: cluster_analysis/agent/remote.py and its end-to-end test, tests/test_remote_mcp.py.", "note")]

# =====================================================================================================================
# A real conversation
story += [PageBreak(), P("A real conversation", "h1"),
          P("Three questions asked in a row about XY_1's genome (a consenting participant), on Claude Code with the user's "
            "own Claude plan. For each, what the person saw, and what happened underneath, from the saved record of the "
            "turn: the tool calls, the answers the check sent back, the tokens and their price."),
          P("What the person sees while Ask works", "h2"),
          P("The screenshot on page 1 is this conversation's first question, mid-way:", "note"),
          table([["", ""],
                 ["How the question was read", "The model's first call. Its reading of the question, including what a genome can "
                  "and can't say about it, and the plan it will follow. Shown within seconds, before any research."],
                 ["Every step", "Each tool call as it runs, tagged by kind: <b>YOURS</b> (the person's own results, read on the "
                  "computer), <b>RESEARCH</b> (public facts), <b>VIEW</b> (an explorer view drawn into the answer)."],
                 ["Reading now", "The research sources light up as tools use them: GWAS Catalog, ClinVar, UniProt, Gene Ontology, "
                  "STRING, Reactome and the rest, with Claude itself as one tile."],
                 ["The counter", "New and cached tokens and the running cost, updated as the question runs. Stop ends it at any "
                  "point."],
                 ["AI: Claude Code", "Which model is connected: here the user's own Claude plan through Claude Code."]],
                [40 * mm, WIDTH - 40 * mm], head=False),
          P("All of this arrives while the question runs, through the event stream described under <i>Asynchronous by "
            "design</i>.", "note")]


def turn_facts(t):
    rows = [["Tool calls", " \u2192 ".join(t["calls"])],
            ["Time", f"{t['seconds']:.0f} s"],
            ["Tokens", f"{t['tokens_in']:,} in ({t['cached_share'] * 100:.2f}% from cache), {t['out']:,} out"],
            ["Cost", f"<b>${t['usd']:.3f}</b>" + (f" + ${t['readings_usd']:.4f} readings" if t["readings_usd"] else "")
             + f" &nbsp;\u00b7&nbsp; without caching ${t['no_cache']:.3f} &nbsp;\u00b7&nbsp; Opus, no caching ${t['opus_no_cache']:.3f}"]]
    return table(rows, [22 * mm, WIDTH - 22 * mm], head=False)


story += [CondPageBreak(95 * mm), Spacer(1, 6), P("1 \u00b7 \u201cShow me the cluster for ACTN3\u201d", "h2"),
          P("ACTN3 makes alpha-actinin-3, a protein of fast-twitch muscle fibres, and is one of the most studied genes in "
            "sports genetics. The model states its reading and plan, then calls <b>my_gene</b>: the person's result, "
            "rs1815739 TT, goes straight to their screen as the red card. With sharing on, the model also receives it in "
            "interpreted form (\u201cless active\u201d), never the DNA file. <b>gene</b> brings the public facts and "
            "<b>show_cluster</b> draws the explorer's network of muscle genes around ACTN3, coloured by the person's results. "
            "The first answer came back from the check once: it lacked the links that let the tab draw it as a web. The model "
            "added them."),
          turn_facts(T1), Spacer(1, 8),
          picture("t1_answer.png", width=140 * mm, caption="The answer: the person's result, the summary, the web (what the "
                  "question needed, the gene behind it, the findings), the evidence, the cluster graph, and suggested follow-ups. "
                  "The footer states the model, the time, the tokens and cost, and that the DNA file stayed on the computer.")]

story += [PageBreak(), P("2 \u00b7 \u201cWhy should I care about this gene?\u201d", "h2"),
          P("A follow-up. The model receives the earlier question, its own plan and its explanation, never the person's "
            "results. The explorer's own data can't answer \u201cwhy care\u201d, so it looks outward: <b>research_genotypes</b> "
            "finds study sentences that name a genotype group of rs1815739 and an effect, and <b>search_papers</b> looks for "
            "meta-analyses. Each of the three highlighted figures had to be found in the paper it cites."),
          P(f"The two cards under \u201cFor XY_1\u201d are readings: a small model wrote them once, for every genotype group the "
            f"studies name, without knowing whose genome it is, and this computer picked the ones for TT. Writing them cost "
            f"${T2['readings_usd']:.4f}, once, for every future person. \u201cWhat it can't tell you\u201d is part of every "
            "answer: the effects are small and vary between studies."),
          turn_facts(T2), Spacer(1, 8),
          picture("t2_answer.png", width=150 * mm, caption="Research by genotype: checked figures, the web from question to gene "
                  "to papers, readings picked for the person, the evidence with citations, and its five sources.")]

story += [PageBreak(), P("3 \u00b7 \u201cOther muscle and hormone genes about me?\u201d", "h2"),
          P("The broadest question. The model lists the muscle theme's mechanisms (<b>cluster</b>), reads the person's genes in "
            "the hormone and growth ones (<b>my_cluster</b>), and looks up AR and IGF1. Its plan named more areas than it had "
            "read, so the check sent the answer back twice (\u201cyou listed these areas but haven't read them\u201d). Each time "
            "the model read the missing areas and rewrote; the final answer covers every area it promised."),
          turn_facts(T3), Spacer(1, 8),
          picture("t3_working.png", width=140 * mm, caption="Mid-question: each step as it runs, and the running cost ($0.068 at "
                  "this point; 130,032 tokens read from cache, 12 new)."),
          Spacer(1, 6),
          picture("t3_answer_top.png", width=WIDTH, caption="The answer: four of the person's own genotypes at the top, a "
                  "plain-language summary, figures checked against the studies they come from, and a web from the question's "
                  "areas to the person's genes to the papers."),
          Spacer(1, 6),
          picture("t3_answer_evidence.png", width=WIDTH, caption="Further down the same answer: the evidence area by area, "
                  "studies on the person's own genotypes, what the answer can't tell, the person's genes in every area drawn "
                  "as one network, and the six sources.")]

story += [CondPageBreak(95 * mm), P("The conversation in numbers", "h2"),
          table([["Question", "Lookups", "Sent back", "Tokens in", "Cost", "Without caching", "Opus, no caching"]] +
                [[f"{i + 1}", str(len([c for c in t['calls'] if c not in ('understand', 'answer')])), str(len(t["rejections"])),
                  f"{t['tokens_in']:,}", f"${t['usd'] + t['readings_usd']:.3f}", f"${t['no_cache']:.3f}", f"${t['opus_no_cache']:.3f}"]
                 for i, t in enumerate(EX)] +
                [["<b>All</b>", str(sum(len([c for c in t['calls'] if c not in ('understand', 'answer')]) for t in EX)),
                  str(SENT_BACK), f"{sum(t['tokens_in'] for t in EX):,}", f"<b>${CONV:.3f}</b>",
                  f"${sum(t['no_cache'] for t in EX):.3f}", f"${sum(t['opus_no_cache'] for t in EX):.3f}"]],
                [20 * mm, 20 * mm, 20 * mm, 26 * mm, 22 * mm, 32 * mm, WIDTH - 140 * mm]),
          Spacer(1, 8), picture("turns.png", width=WIDTH)]

# =====================================================================================================================
# Under the hood
story += [PageBreak(), P("Under the hood", "h1"),
          P("Ask is a tool-using agent with the rules on the engine's side. The model (Claude Sonnet 5.5 through the user's "
            "API key, or Claude Code on their Claude plan) works through a fixed set of tools served by the agent engine on "
            "the person's device. It ends by calling an <b>answer</b> tool, which the engine checks. Then the engine adds "
            "readings of the person's own results, written once for everyone and picked on the device."),
          diagram(),
          P("Everything on the left runs on the person's device. On the right are the model the user chose and the public "
            "research sources, which receive only public ids and names (a gene, an rsID, a drug, a search phrase).", "note"),
          P("<b>How it could look as a platform.</b> The same four layers split cleanly between device and cloud. The app, the "
            "person's data and the personal tools stay on the device; the agent engine's public tools, the research data and "
            "the guardrails move behind an MCP gateway in the cloud, with a model router choosing a tier for each step. That is "
            "the architecture on page 4, and the AWS, Azure and Google Cloud mapping on page 5.")]

steps = [
    ("1 Understand", f"The first call, {code('understand')}: what the model took the question to mean (and what a genome can and "
     "can't say about it), its aim, the areas and strategies it will cover, and its plan. Shown at once."),
    ("2 Resolve", f"{code('resolve')} and {code('catalogue')} map names to the explorer: a drug by any name or spelling "
     "(paracetamol is acetaminophen), a gene, a test, a condition, a mechanism."),
    ("3 The person's results", f"The {code('my_*')} tools read the person's results for the items named; the cards go to the "
     "person's screen."),
    ("4 Research", f"When local data doesn't answer: {code('search_papers')}, {code('read_paper')}, {code('research_genotypes')}, "
     f"{code('recent_papers')}. A question about what works needs at least two such lookups before an answer is accepted."),
    ("5 Views", "The explorer's own views drawn into the answer: a cluster, a pathway, a medicine, a nutrient, a set of papers."),
    ("6 Answer", "Summary, highlights, explanation with citations, links for the web, follow-up questions. Checked; sent back with "
     "every problem at once if it fails."),
    ("7 Readings", "Readings for every possible result (every CPIC gene result, every score band, every genotype group in a study "
     "sentence), written once by the small model and cached; the server picks the person's."),
    ("8 Saved", f"The turn goes to {code('data/output/agent/sessions/')}, so a follow-up continues the conversation."),
]
story += [P("A question, step by step", "h2"), table([["Step", "What happens"]] + [[a, b] for a, b in steps], [34 * mm, WIDTH - 34 * mm])]

story += [CondPageBreak(70 * mm), P("The tools", "h2"),
          table([["Kind", "Tools", "What the model gets back"],
                 ["Public (13)", code("catalogue, resolve, gene, variant, cluster, trait_variants, drug, research_genotypes, "
                                      "search_papers, read_paper, pathway, nutrient, recent_papers"),
                  "The full result: facts that are the same for everyone (UniProt, GWAS Catalog, ClinVar, ClinPGx, CPIC, Europe "
                  "PMC, Reactome). Every source and text goes into the ledger the checks use."],
                 ["Personal (7)", code("my_medicine, my_medicines, my_scores, my_cluster, my_gene, my_condition, my_nutrient"),
                  "The person's results go to their screen. The model gets the result's shape, plus the interpreted results "
                  "when sharing is on."],
                 ["View (5)", code("show_cluster, show_pathway, show_medicine, show_nutrient, show_papers"), "\u201cshown\u201d"],
                 ["Control (2)", code("understand, answer"), "The plan is shown; the answer is checked."]],
                [24 * mm, 66 * mm, WIDTH - 90 * mm])]

story += [CondPageBreak(80 * mm), P("What the model sees", "h2"),
          P(f"One setting, {code('share_results')}, chosen by the user in the Ask tab. Connecting a model is the user's own "
            "setup, so what it receives is their decision."),
          table([["", "Sharing on (default)", "Sharing off"],
                 ["The question", "sent", "sent"],
                 ["Public research", "sent", "sent"],
                 ["The person's results", "for the items the question touches, interpreted: a gene's type, a score's band and "
                  "which way is better, the genotype a study finding applies to", "the kind of result only: never a value or "
                  "a genotype"],
                 ["The summary", "written by the model from results and evidence", "the model's general explanation; readings "
                  "added on the computer"]],
                [32 * mm, 74 * mm, WIDTH - 106 * mm]),
          P("Never sent, in either mode: the DNA file, raw genotypes beyond the items a question touches, the person's name. "
            "Follow-ups send the earlier questions, plans, tool calls and explanations, never the person's results.", "note")]

story += [CondPageBreak(80 * mm), P("How answers are checked", "h2"),
          table([["Check", "Rejects"],
                 ["Summary", "an answer without a 2-4 sentence summary"],
                 ["Research done", "a \u201cwhat works\u201d answer before two outward lookups, or with a listed strategy unsearched"],
                 ["Areas read", "an answer that skips areas its own plan listed"],
                 ["Citations", "a reference no tool returned in this conversation"],
                 ["Highlights", "a figure not found in its cited source, or not in the person's result it names"],
                 ["Ranks", "a rank the question didn't ask about, or written the wrong way round"],
                 ["Advice", "anything that reads as clinical advice: answers speak in risk and evidence"]],
                [30 * mm, WIDTH - 30 * mm]),
          P("Hard problems always send the answer back; soft ones up to twice, after which unsupported citations and highlights "
            "are removed and listed. The small model's readings pass the same advice check and may only use their source's "
            "numbers.", "note")]

# =====================================================================================================================
# Asynchronous by design
story += [PageBreak(), P("Asynchronous by design", "h1"),
          P("A question takes from twenty seconds to two minutes, most of it waiting on the model and on research services. "
            "Ask is built so that nothing waits that doesn't have to: the person sees progress from the first second, the "
            "app stays usable, and independent work runs side by side.")]
story += [Spacer(1, 4), P("In the Ask tab's own engine, the lookups of one model step run one after another: they are local and "
            "take milliseconds, so running them in parallel would save almost nothing, and in order they keep the event stream "
            "simple. The slow parts, the model and the network, are where the concurrency is.", "note"),
          picture("timeline.png", width=156 * mm, caption=(
    "Measured: one research-agent question (\u201cWhat medicines should I watch out for?\u201d, Claude Code on Opus, 19 November). "
    "Each bar is a tool call from start to finish, stacked into slots when calls overlap; the lower panel counts calls in "
    "flight. The short teal bursts in the first 30 seconds are local lookups (a variant or gene in milliseconds); the long "
    "red bars are papers fetched from Europe PMC, which overlap up to four at once. Gaps are the model thinking."))]
story.append(Spacer(1, 6))
story.append(table([["Where", "What runs concurrently", "In the code"],
    ["The question itself", "Asking starts a background job and returns its id at once. The job runs in its own thread; the "
                            "page fetches only the events added since its last look and draws them as they come: the plan, each "
                            "lookup, the sources in use, the running token count.", code("server.Agent.converse")
                            + ", " + code("/api/agent/events?after=N")],
    ["The server", "A threading HTTP server: the page, its data, the event stream and other requests are served side by side "
                   "while a question runs.", code("ThreadingHTTPServer")],
    ["Claude Code", "The model runs as its own process (Claude Code, streaming JSON) and the tools as another (the MCP server); "
                    "they share the turn through a file, so the person's results reach the page without passing through "
                    "the model.", code("converse._engine_cc") + ", " + code("mcp_server")],
    ["Parallel lookups", "When the model asks for several lookups at once, the research agent runs up to four in parallel and "
                         "returns them together.", code("run.py: ThreadPoolExecutor(4)")],
    ["Readings and studies", "The small model writes readings four batches at a time; quick answers search studies six at "
                             "a time and fetch a cluster's genotype findings in the background.",
     code("categories, interpret: 4") + ", " + code("quick: 6")],
    ["Scripts (prototype)", "With programmatic tool calling on, the model writes a short script that runs independent lookups "
                            "together (asyncio.gather) inside Claude's code execution, and only the filtered result comes back "
                            "into the context.", code("DNA_AGENT_PTC=1")]],
    [30 * mm, 98 * mm, WIDTH - 128 * mm]))

# =====================================================================================================================
# Keeping token use low
story += [PageBreak(), P("Keeping token use low", "h1"),
          P(f"A question re-reads a lot: the system prompt, 27 tool definitions and every tool result so far go back on each "
            f"step, about {A['tokens_in'] / 1000:,.0f}k input tokens a question on average against {A['tokens_out']:,.0f} "
            "output tokens. So the measures go where the tokens are: the input that repeats, the size of what tools return, "
            "and which model reads it."),
          table([["Measure", "How it is done", "What it saves"],
                 ["Prompt caching", f"Requests mark their stable part for caching ({code('cache_control')}); Claude Code caches "
                  "the same way. Later steps read it from cache.", "Cache reads cost a tenth of fresh input; in the example "
                  "conversation 99.99% of input came from cache."],
                 ["The right model per job", "Sonnet 5.5 at medium effort for the conversation, Haiku 5.5 for readings, Opus 5.5 "
                  "only in the older research agent.", "Opus costs twice Sonnet per token; Haiku a twentieth."],
                 ["Readings once, for everyone", "Every possible result's reading is written once and cached; a question only "
                  "picks.", "After the first time, readings cost nothing."],
                 ["Compact tool results", f"{code('facts.clip')} drops empty fields, writes compact JSON and caps a result at "
                  "24,000 characters.", f"Raw results would be {TOK['tool_raw_over_clipped']:.1f}x as long: about "
                  f"{TOK['extra_input_tokens_per_turn_raw_tools'] / 1000:,.1f}k more tokens a question."],
                 ["Lookup budget", "10 lookups a question (20 for research), 16 model steps, 8,000 output tokens a step.",
                  "A ceiling on every question."],
                 ["Local data first", "GWAS, ClinVar and 1000 Genomes from a local index; other lookups from the shipped cache.",
                  "The model never pages through files."],
                 ["Short follow-ups", "Follow-ups carry questions, plans and explanations, not earlier tool results; sources "
                  "carry over.", "Context grows slowly."],
                 ["One round of corrections", "All problems reported at once; accepted after two soft rounds.", "Fewer rewrites."],
                 ["No model where none is needed", "Quick answers and name matching are rules.", "Zero tokens."]],
                [36 * mm, 80 * mm, WIDTH - 116 * mm]),
          Spacer(1, 8), picture("waterfall.png", width=WIDTH, caption=(
              f"Method: the average of {TOK['turns']} recorded questions, priced at API rates. Without caching prices every input "
              "token at full rate; raw tool results add the extra input measured by re-running "
              f"{TOK['tool_calls_rerun']} recorded tool calls without clipping, counted once for each later step that re-reads "
              "them; Opus prices the same tokens at Opus 5.5's rates. The questions ran on Claude Code, where they count against "
              "the plan's usage; the dollars are what they would cost on the API. The size of each step depends on the order "
              "they are taken in (caching first would show a larger caching saving); the total, from $"
              f"{A['opus_no_cache_raw_tools']:.3f} to ${A['actual']:.3f}, does not."))]

# =====================================================================================================================
# Models, accounts and the cloud
story += [PageBreak(), P("Models, accounts and the cloud", "h1"),
          P("One decision runs through the design: <b>the model is a guest, the server is the host</b>. Tools, data, privacy "
            "rules and answer checks live in the app's own server; the model reasons and calls tools. That keeps the model "
            "replaceable, the connection standard, and the privacy line the same whichever model or cloud is on the other side."),
          table([["", "Today (built and running)", "Next (designed, not built)"],
                 ["Claude", "On the user's own account: an Anthropic API key, or their Claude login through Claude Code (signed in "
                            "through the browser, usage on their plan). The tab shows which is connected and what each "
                            "question costs.", "A sign-in button in the app, so people without Claude Code can connect their "
                            "Claude account without handling a key."],
                 ["MCP", f"The toolset is an MCP server ({code('python -m cluster_analysis.agent mcp')}). The Ask tab runs Claude Code "
                         "through it; Claude Code adds it with one command, Claude Desktop or another client through its "
                         "settings. The answer check runs in the server, so every model gets the same discipline.",
                  "Built: the public tools as a remote MCP server over HTTP with OAuth 2.1 (page 6). Next: hosting it."],
                 ["Gemini and others", "Not connected yet. Nothing in the tools or checks is specific to Claude.",
                  "Gemini through an MCP client (Google's Gemini CLI loads MCP servers), or a third engine on the Gemini API; "
                  "either needs a test pass against the same checks."],
                 ["OAuth", "Built for the remote MCP server: OAuth 2.1 with PKCE, automatic client registration, a "
                           "built-in sign-in or an external identity provider. The app on the device needs none: it answers "
                           "only itself.", "Accounts for a hosted or phone version, and signing in to a model provider "
                           "instead of pasting a key, where the provider offers it."],
                 ["Cloud", "Deliberately local for everything personal. The cloud carries what is public or the user's choice: "
                           "their model, and live research lookups.", "Host the public half as a service (next section). Keep the "
                           "personal half on the device, phones included."]],
                [26 * mm, 76 * mm, WIDTH - 102 * mm])]

# =====================================================================================================================
# Cloud computing and revenue
story += [CondPageBreak(60 * mm), Spacer(1, 6), P("Cloud computing and revenue", "h1"),
          P("The architecture splits cleanly into a public half (research data, tools, the research-data bundle) and a personal "
            "half (the DNA, the results, the readings picked for a person). The public half is a natural cloud product; the "
            "personal half stays with the person, which keeps the most sensitive data out of every business model below. These "
            "are options, with their unit costs where we have measured them, not decisions."),
          table([["Option", "Who pays for what", "Unit cost to us", "Status"],
                 ["Desktop app licence", "The person, once or yearly, for the app and its updates.", "None per question: the "
                  "analysis runs on their computer and the model is theirs.", "The app and installer exist (Windows; Linux "
                  "built, not yet tested)."],
                 ["Research-data subscription", "The person or an organisation, for a refreshed research bundle (new studies, "
                  "updated references).", "Rebuilding the bundle (a few hours of one machine) and static hosting.", "The bundle "
                  "is built and shipped; the app already checks an update feed."],
                 ["Managed model access", "People without their own Claude account pay per question or month; we carry the "
                  "model bill.", f"Measured: ${A['actual']:.3f} a question at API prices (50 questions a month is about "
                  f"${50 * A['actual']:.2f}).", "Not built: needs accounts (OAuth) and billing."],
                 ["Hosted research tools (B2B)", "Other apps and agents pay for the curated genetics research tools over MCP.",
                  "Hosting the public tools and their cache; no genetic data involved.", "The remote MCP server with OAuth "
                  "2.1 is built and tested; hosting it is next."],
                 ["Phone and web app", "A subscription, for people without a computer.", "Static hosting; the imputation runs "
                  "on the phone. Optional cloud imputation would be about 11 minutes of a 6-thread processor per genome "
                  "(measured on a desktop), with the person's explicit consent.", "Designed; the compact reference panel is "
                  "built and validated; the browser imputer is a prototype."]],
                [30 * mm, 46 * mm, 52 * mm, WIDTH - 128 * mm]),
          Spacer(1, 8),
          callout("Why the economics hold up", "The person brings the compute (their computer) and the model (their account), so "
                  "serving them costs us little; the paid value is the curation, the checks and the research data, which are "
                  "ours. The compact reference panel matters here too: it lets every install impute without the 12 GB panel, "
                  "and makes imputation on a phone realistic."),
          Spacer(1, 10),
          picture("economics.png", width=WIDTH, caption=f"If we provided the model (the managed option), from the measured "
                  f"average of {TOK['turns']} questions: ${A['actual']:.3f} a question as built, against "
                  f"${A['opus_no_cache_raw_tools']:.3f} on a naive build. The token-saving work is what makes a managed tier "
                  "affordable to offer.")]

# =====================================================================================================================
# Appendix
story += [PageBreak(), P("Appendix", "h1"), P("The two backends", "h2"),
          table([["", "API key", "Claude Code"],
                 ["When", "a key is set (in the Ask tab, or ANTHROPIC_API_KEY)", "no key, and Claude Code is installed"],
                 ["How", "the Messages API in a hand-written loop: each tool result recorded, reported to the tab, a failed check "
                         "sent back as a tool error; prompt caching on", f"{code('claude -p')} with no built-in tools, only this "
                         f"app's tools over MCP ({code('--strict-mcp-config')}); the MCP server shares the turn through a file"],
                 ["Billing", "the user's key; tokens and price shown per question", "the user's plan; the tab shows the API "
                                                                                     "price of the same question"]],
                [22 * mm, 76 * mm, WIDTH - 98 * mm]),
          P("<b>The key</b> is held in memory, or stored encrypted with Windows DPAPI when the user ticks \u201cremember\u201d (Linux: a "
            "file only its owner can read). No endpoint returns it."),
          P("Other ways in", "h2")] + bullets([
    f"<b>The research agent</b> ({code('agent/run.py')}): the earlier, stricter design, from the command line and over MCP. Opus "
    "5.5 researches from public facts only and writes a template (what 0, 1 or 2 copies of an allele mean); the model never sees "
    "a genotype, and every quote must be word for word in its source.",
    f"<b>Quick answers</b> ({code('agent/quick.py')}): no model; rules match the question, read the results and the studies.",
    f"<b>Any MCP client</b>: {code('python -m cluster_analysis.agent mcp')} serves the same tools and checks.",
]) + [P("Where things are kept", "h2"),
      table([["Path", "Holds", "Personal"],
             [code("data/output/agent/sessions/"), "conversations: questions, plans, tool calls, results shown, answers", "yes"],
             [code("data/output/agent/fills/"), "the research agent's per-person readings", "yes"],
             [code("data/output/agent/answers/"), "the research agent's answer templates", "the questions"],
             [code("data/output/agent/api_key"), "the remembered key, encrypted", "the key"],
             [code("cluster_analysis/cache/"), "public lookups, and readings written for everyone", "no"]],
            [58 * mm, 92 * mm, WIDTH - 150 * mm]),
      P("All of it is on the user's computer; the app's \u201cDelete everything\u201d removes the agent folder and the key.", "note"),
      P("Methods", "h2"),
      P(f"Costs use the token counts recorded for each question and Anthropic's API prices as of November 2026 (Sonnet 5.5: $2 "
        f"input, $10 output, $0.10 cache read per million tokens; Opus 5.5 twice that; cache writes 1.25 times input). The "
        f"example conversation is session 20261124-134315 (three questions); the averages cover {TOK['turns']} recorded "
        "questions. The timeline is run 20261119-134302 of the research agent. The imputation time is half of a 22-minute "
        "genome-wide validation that ran the full panel and the compact one on the same desktop (Intel i7-7700K, 6 threads).",
        "note")]


def page(c, doc):
    c.saveState()
    c.setFont("Body", 7.6)
    c.setFillColor(MUTED)
    if doc.page > 1:
        c.drawString(18 * mm, 10 * mm, "DNA-Analyzer \u00b7 Ask")
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, str(doc.page))
    c.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=17 * mm,
                        title="Ask your own genome a question", author="DNA-Analyzer",
                        subject="How DNA-Analyzer's Ask works: a real conversation, under the hood, cost, the cloud and revenue")
doc.build(story, onFirstPage=page, onLaterPages=page)
print("ok", OUT)
