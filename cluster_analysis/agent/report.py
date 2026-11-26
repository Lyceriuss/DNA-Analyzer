"""An Ask conversation as a structured PDF: each question's answer and the whole chain behind it.

    python -m cluster_analysis.agent.report SESSION_ID [--turn N] [--out FILE]
    GET /api/agent/report?session=ID[&turn=N]      (the Ask tab's "Save as PDF")

Per turn, in reading order:
  1. the question, and how it was read (the model's reading, the aim, the plan);
  2. the answer: the summary, the key figures with their sources, how it ties together, the evidence in more detail;
  3. the person's own readings (picked on this computer) and the results the turn put on their screen;
  4. the chain: every tool called, in order, with its letter logo, kind, the public arguments it was called with, what
     came back (or why the answer check sent it back), and the databases and APIs it read;
  5. the sources the answer cites, with links; follow-up questions; the model, Restricted mode, tokens, time.

Everything comes from the saved conversation (agent/session.py): nothing is asked again and no model is called. The
PDF holds the person's genetic results, so it is written where the person saves it and nowhere else; the first page
says so. Tool names, abbreviations and databases: explorer/ask_tools.json and explorer/sources.json.
"""
import argparse
import datetime
import io
import json
import os
import re

from cluster_analysis.agent import session as sess

HERE = os.path.dirname(os.path.abspath(__file__))
EXPLORER = os.path.join(os.path.dirname(HERE), "explorer")
KIND = {"public": ("Looks up research", "#3b6fd8"), "personal": ("Reads your DNA", "#2f9e6a"), "view": ("Draws a view", "#8a5cd6"),
        "control": ("Answer step", "#6b7280")}


def _font():
    """A Unicode font on this computer (DejaVu Sans from matplotlib, Segoe UI on Windows, DejaVu on Linux), or the
    PDF's built-in Helvetica, then with the few characters it lacks written out."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    cands = []
    try:
        import matplotlib
        d = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
        cands.append((os.path.join(d, "DejaVuSans.ttf"), os.path.join(d, "DejaVuSans-Bold.ttf")))
    except ImportError:
        pass
    cands += [(r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
              ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
              ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf")]
    for reg, bold in cands:
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont("Body", reg))
                pdfmetrics.registerFont(TTFont("Body-Bold", bold))
                addMapping("Body", 0, 0, "Body"); addMapping("Body", 1, 0, "Body-Bold")
                addMapping("Body", 0, 1, "Body"); addMapping("Body", 1, 1, "Body-Bold")
                return "Body", "Body-Bold", True
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold", False


PLAIN = {"≤": "<=", "≥": ">=", "→": "->", "←": "<-", "χ": "chi", "²": "2", "≈": "~", "−": "-", "…": "...", "✓": "ok", "×": "x"}


def _catalogues():
    tools = json.load(open(os.path.join(EXPLORER, "ask_tools.json"), encoding="utf-8"))
    dbs = {d["id"]: d for d in json.load(open(os.path.join(EXPLORER, "sources.json"), encoding="utf-8"))["databases"]}
    dbs.setdefault("claude", {"id": "claude", "name": "Claude (the connected AI model)", "url": "https://www.anthropic.com"})
    return tools, dbs


def _kinds():
    try:
        from cluster_analysis.agent import tools
        return tools.KIND
    except Exception:
        return {}


def build(session_id, turn=None):
    """The PDF as bytes: the whole conversation, or one turn."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    s = sess.Session.load(session_id)
    turns = list(enumerate(s.turns))
    if turn is not None:
        if not 0 <= int(turn) < len(turns):
            raise ValueError(f"No turn {turn} in {session_id}.")
        # a follow-up builds on what came before: the conversation up to and including this question
        turns = turns[:int(turn) + 1]
    reg, bold, unicode_ok = _font()
    tools, dbs = _catalogues()
    kinds = _kinds()
    try:
        from cluster_analysis.version import VERSION
    except Exception:
        VERSION = "?"

    def esc(x):
        x = "" if x is None else str(x)
        if not unicode_ok:
            for a, b in PLAIN.items():
                x = x.replace(a, b)
            x = x.encode("cp1252", "replace").decode("cp1252")
        return x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def refs_inline(text, refs):
        """[PMID:123] -> a small linked marker."""
        out = esc(text)
        def link(m):
            k = m.group(1)
            r = (refs or {}).get(k) or {}
            u = r.get("url")
            return f'<font size="7" color="#3b6fd8">[{"<a href=%s>" % json.dumps(u) if u else ""}{esc(k)}{"</a>" if u else ""}]</font>'
        out = re.sub(r"\[((?:PMID|ClinPGx|GWAS|Reactome|ClinVar|UniProt)[: ][^\]]+)\]", link, out)
        # The model writes a little markdown: **bold** and blank-line paragraphs
        out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
        return out.replace("\n\n", "<br/><br/>").replace("\n", " ")

    ink, muted, line = colors.HexColor("#1b1b1b"), colors.HexColor("#5f6368"), colors.HexColor("#d9dce1")
    st = {
        "title": ParagraphStyle("title", fontName=bold, fontSize=20, leading=24, textColor=ink, spaceAfter=4),
        "sub": ParagraphStyle("sub", fontName=reg, fontSize=9.5, leading=13, textColor=muted),
        "q": ParagraphStyle("q", fontName=bold, fontSize=14, leading=18, textColor=ink, spaceBefore=4, spaceAfter=6),
        "h": ParagraphStyle("h", fontName=bold, fontSize=10.5, leading=14, textColor=ink, spaceBefore=10, spaceAfter=3),
        "p": ParagraphStyle("p", fontName=reg, fontSize=9.5, leading=13.5, textColor=ink),
        "small": ParagraphStyle("small", fontName=reg, fontSize=8, leading=10.5, textColor=muted),
        "cell": ParagraphStyle("cell", fontName=reg, fontSize=8, leading=10.2, textColor=ink),
        "cellb": ParagraphStyle("cellb", fontName=bold, fontSize=8, leading=10.2, textColor=ink),
        "summary": ParagraphStyle("summary", fontName=reg, fontSize=10.5, leading=15, textColor=ink, backColor=colors.HexColor("#f3f5f8"),
                                  borderPadding=(7, 8, 7, 8), leftIndent=4, rightIndent=4, spaceBefore=4, spaceAfter=8),
    }
    P = lambda text, style="p": Paragraph(text, st[style])
    grid = lambda data, widths, head=True: _table(data, widths, head, line, colors, TableStyle, Table)

    story = []
    first = s.turns[0]["question"] if s.turns else ""
    story += [P("Ask report", "title"),
              P(esc(f"Profile {s.person} · conversation {s.id} · {len(s.turns)} question{'s' if len(s.turns) != 1 else ''} · "
                    f"made {datetime.datetime.now():%Y-%m-%d %H:%M} by DNA-Analyzer {VERSION}"), "sub"),
              Spacer(1, 4),
              P("This report holds the person's own genetic results. It was made on this computer from the saved "
                "conversation; nothing was sent anywhere to make it. Results are written in risk and evidence, not as "
                "clinical advice.", "small"),
              Spacer(1, 8)]
    # Contents: the questions
    if len(turns) > 1:
        story += [P("Questions", "h")] + [P(esc(f"{i + 1}. {t['question']}" + ("   (follow-up)" if i else "")), "p") for i, t in turns]
        if turn is not None and int(turn) < len(s.turns) - 1:
            story.append(P(esc(f"The conversation up to question {int(turn) + 1} of {len(s.turns)}."), "small"))
        story.append(Spacer(1, 6))

    for n, (i, t) in enumerate(turns):
        if n:
            story.append(PageBreak())
        a = t.get("answer") or {}
        refs = a.get("refs") or {}
        story.append(P(esc(f"{i + 1}. {t['question']}"), "q"))
        if i > 0:
            before = "question 1" if i == 1 else f"questions 1 to {i}"
            story.append(P(esc(f"A follow-up: the model had {before} and the answers in front of it, not the person's "
                               f"results from them."), "small"))
        meta = [t.get("model") or "model not recorded",
                "Restricted mode off: interpreted results were shared with the model" if t.get("shared") else "Restricted mode on: the model saw no results",
                f"{t.get('seconds', '?')} s"]
        tok = t.get("tokens") or {}
        if tok:
            meta.append(f"{tok.get('input', 0) + tok.get('cache_read', 0) + tok.get('cache_write', 0):,} tokens in, {tok.get('output', 0):,} out"
                        + (f", ${tok['usd']:.3f}" if tok.get("usd") else ""))
        story.append(P(esc(" · ".join(meta)), "small"))

        # 1. How it was read
        u = t.get("understood") or {}
        if u:
            story.append(P("How the question was read", "h"))
            if u.get("reading"):
                story.append(P(f"<i>{esc(u['reading'])}</i>"))
            if u.get("aim"):
                story.append(P(esc(f"Aim: {u['aim']}" + (f" · areas: {', '.join(u['areas'])}" if u.get("areas") else "")), "small"))
            for k, step in enumerate(u.get("plan") or [], 1):
                story.append(P(esc(f"{k}. {step}"), "small"))

        # 2. The answer
        if a.get("summary"):
            story.append(P("The answer", "h"))
            story.append(P(refs_inline(a["summary"], refs), "summary"))
        hl = a.get("highlights") or []
        if hl:
            story.append(P("Key figures", "h"))
            rows = [[P("Figure", "cellb"), P("Value", "cellb"), P("Source", "cellb")]]
            for h in hl:
                if isinstance(h, dict):
                    lab, val, src = h.get("label"), h.get("value"), h.get("source")
                else:
                    lab, val, src = (str(h).split("|") + ["", "", ""])[:3]
                rows.append([P(esc(lab), "cell"), P(f"<b>{esc(val)}</b>", "cell"), P(esc(src), "cell")])
            story.append(grid(rows, [80 * mm, 35 * mm, 55 * mm]))
        links = a.get("links") or []
        if links:
            story.append(P("How it ties together", "h"))
            rows = [[P(h, "cellb") for h in ("Area or strategy", "Genes behind it", "Studies", "The finding")]]
            join = lambda v: ", ".join(map(str, v)) if isinstance(v, list) else (v or "")
            for l in links:
                if isinstance(l, str):
                    parts = [x.strip() for x in l.split("|")] + ["", "", "", ""]
                else:
                    parts = [l.get("node") or l.get("area") or "", join(l.get("genes")) or "none read", join(l.get("refs")) or "none", l.get("finding") or ""]
                rows.append([P(esc(x), "cell") for x in parts[:4]])
            story.append(grid(rows, [40 * mm, 35 * mm, 35 * mm, 60 * mm]))
        if a.get("explanation"):
            story.append(P("The evidence in more detail", "h"))
            story.append(P(refs_inline(a["explanation"], refs)))

        # 3. The person's own results
        written = t.get("written") or []
        if written:
            story.append(P("Readings for the person", "h"))
            story.append(P("Picked on this computer from readings written once for every result.", "small"))
            rows = [[P(h, "cellb") for h in ("Gene", "Genotype", "Reading", "Source")]]
            for w in written[:16]:
                gts = ", ".join(x for x in (w.get("genotypes") or []) if x)
                rows.append([P(esc(w.get("gene") or w.get("title")), "cell"), P(esc(gts), "cell"),
                             P(esc((w.get("reading") or "")[:600]), "cell"), P(esc(w.get("source") or w.get("type")), "cell")])
            story.append(grid(rows, [28 * mm, 22 * mm, 95 * mm, 25 * mm]))
        cards = t.get("cards") or []
        if cards:
            story.append(P("Results shown on the person's screen", "h"))
            rows = [[P("Result", "cellb"), P("What it said", "cellb"), P("Kind", "cellb")]]
            for c in cards[:24]:
                said = esc(ranked(c.get("headline")))
                imp = (c.get("data") or {}).get("impact") or {}
                if imp.get("explains_pct") is not None:
                    lvl = imp.get("level") or ""
                    col = {"high": "#2f9e6a", "modest": "#b7791f"}.get(lvl, "#5f6368")
                    said += (f'<br/><font size="7" color="{col}"><b>{esc(lvl.upper())} IMPACT {esc(imp["explains_pct"])}%</b></font>'
                             f'<font size="7" color="#5f6368"> of the differences explained by the study\'s strongest variants</font>')
                rows.append([P(esc(c.get("title")), "cell"), P(said, "cell"), P(esc(c.get("provider")), "cell")])
            story.append(grid(rows, [62 * mm, 88 * mm, 20 * mm]))

        # 4. The chain
        trace = t.get("trace") or [dict(c, ok=True, note=None) for c in (t.get("calls") or [])]
        if trace:
            story.append(P("The chain: every tool called, in order", "h"))
            rows = [[P(h, "cellb") for h in ("#", "Tool", "Called with", "What came back", "Read from")]]
            used = []
            for k, c in enumerate(trace, 1):
                name = c.get("name")
                tdef = tools["tools"].get(name, {"abbr": "SC" if name == "script" else (name or "?")[:3].upper(), "label": name, "sources": []})
                kind = kinds.get(name, "control")
                kl, kc = KIND.get(kind, ("", "#6b7280"))
                args = c.get("args") or c.get("input") or {}
                if name == "understand":
                    args = {"": "its reading, aim and plan (above)"}
                elif name == "answer":
                    args = {"": "the summary, figures, links and explanation (above)"}
                args_txt = "; ".join((f"{a_}: " if a_ else "") + (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for a_, v in args.items())
                srcs = tdef.get("sources") or []
                used += [x for x in srcs if x not in used]
                result = c.get("note") or ("" if c.get("ok", True) else "")
                if not c.get("ok", True):
                    result = f'<font color="#b3261e">Sent back: {esc(cut(c.get("error"), 560))}</font>'
                else:
                    result = esc(cut(re.sub(r"<[^>]+>", "", result or ""), 560))
                rows.append([P(str(k), "cell"),
                             P(f'<font color="{kc}"><b>{esc(tdef["abbr"])}</b></font> {esc(tdef.get("label") or name)}<br/><font size="6.5" color="#5f6368">{esc(kl)} · {esc(name)}</font>', "cell"),
                             P(esc(cut(args_txt, 420)), "cell"), P(result, "cell"),
                             P(esc(", ".join(dbs.get(x, {}).get("name", x) for x in srcs)), "cell")])
            story.append(grid(rows, [7 * mm, 38 * mm, 50 * mm, 45 * mm, 30 * mm]))
            if used:
                story.append(P("Databases and APIs this answer drew on", "h"))
                rows = [[P("Source", "cellb"), P("Who runs it", "cellb"), P("Link", "cellb")]]
                for x in used:
                    d = dbs.get(x, {"name": x})
                    u_ = d.get("url") or ""
                    rows.append([P(esc(d.get("name")), "cell"), P(esc(d.get("org", "")), "cell"),
                                 P(f'<link href={json.dumps(u_)} color="#3b6fd8">{esc(u_)}</link>' if u_ else "", "cell")])
                story.append(grid(rows, [55 * mm, 60 * mm, 55 * mm]))

        # 5. Sources, follow-ups, drawings
        if refs:
            story.append(P("Sources the answer cites", "h"))
            for k, (rid, r) in enumerate(refs.items(), 1):
                lab = re.sub(r"<[^>]+>", "", r.get("label") or rid)
                u_ = r.get("url")
                story.append(P(f"{k}. <b>{esc(rid)}</b> {esc(lab)}" + (f' <link href={json.dumps(u_)} color="#3b6fd8">{esc(u_)}</link>' if u_ else ""), "small"))
        views = t.get("views") or []
        if views:
            story.append(P("Drawn in the answer (open the conversation in the app to see them)", "h"))
            for v in views:
                what = v.get("theme") or v.get("gene") or v.get("nutrient") or v.get("drug") or v.get("title") or ""
                story.append(P(esc(f"{v.get('view')}: {what}" + (" (added by the app)" if v.get("auto") else "")), "small"))
        if a.get("dropped"):
            story.append(P(esc("Left out by the answer check, as no tool supported it: " + "; ".join(a["dropped"])), "small"))
        if a.get("followups"):
            story.append(P("Follow-up questions", "h"))
            for q in a["followups"]:
                story.append(P(esc(f"· {q}"), "small"))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(reg, 7)
        canvas.setFillColor(muted)
        canvas.drawString(18 * mm, 10 * mm, esc(f"DNA-Analyzer {VERSION} · Ask report · {s.person} · contains personal genetic results"))
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
        canvas.restoreState()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Ask report: {first[:80]}", author="DNA-Analyzer", subject=f"Ask conversation {s.id}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def cut(text, n):
    """At most n characters, ending with an ellipsis when shortened."""
    text = "" if text is None else str(text)
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def ranked(text):
    """Percentiles as the explorer says them (CLAUDE.md): "at the 45th percentile of Europeans" -> "in the Bottom 45% ·
    lower of Europeans", "the 79th percentile" -> "Top 21% · higher"; older saved turns used the ordinal form."""
    def band(n):
        n = int(n)
        return f"Top {max(1, 100 - n)}% · higher" if n >= 50 else f"Bottom {max(1, n)}% · lower"
    text = re.sub(r"\b(?:at|near) the (\d{1,3})(?:st|nd|rd|th) percentile", lambda m: "in the " + band(m.group(1)), text or "")
    return re.sub(r"\b(?:the )?(\d{1,3})(?:st|nd|rd|th) percentile", lambda m: band(m.group(1)), text)


def _table(data, widths, head, line, colors, TableStyle, Table):
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, line),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 4)]
    if head:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f5"))]
    t.setStyle(TableStyle(style))
    return t


def filename(session_id, turn=None):
    s = sess.Session.load(session_id)
    q = s.turns[int(turn)]["question"] if turn is not None else (s.turns[0]["question"] if s.turns else "conversation")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", q).strip("-")[:50] or "ask"
    return f"Ask-{s.person}-{slug}.pdf"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session")
    ap.add_argument("--turn", type=int)
    ap.add_argument("--out")
    a = ap.parse_args()
    out = a.out or filename(a.session, a.turn)
    with open(out, "wb") as f:
        f.write(build(a.session, a.turn))
    print(f"✅ {out}")


if __name__ == "__main__":
    main()
