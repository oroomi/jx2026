"""The "Assumptions & Decisions" chapter as a PDF, rendered from PROJECT_RULES.md (jx40).

A4 portrait, the fonts vendored in docs/method/fonts/ (IBM Plex Sans and Mono, Newsreader; SIL OFL 1.1), one rule per
paragraph, and for every decision its rule, reason and records affected on lines of their own. Only plain digits are used:
no Unicode superscript or subscript characters reach the page (the renderer refuses them). Needs reportlab, a tool for this
document only, not an app dependency. Every character on the page is set in a vendored font; reportlab's page preamble
names its base font (Helvetica) in an empty text block that sets no character.

  python3 -m radar.rules_pdf                      # writes docs/method/assumptions_and_decisions.pdf
"""
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "PROJECT_RULES.md"
OUT = ROOT / "docs" / "method" / "assumptions_and_decisions.pdf"
FONTS = ROOT / "docs" / "method" / "fonts"
SUPER_SUB = re.compile("[²³¹⁰-₟]")
ACCENT = "#0b5d7a"
INK = "#1d2327"
MUTED = "#5b6670"


def _fonts() -> None:
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for name, file in (("Plex", "IBMPlexSans-Regular.ttf"), ("PlexMedium", "IBMPlexSans-Medium.ttf"),
                       ("PlexSemiBold", "IBMPlexSans-SemiBold.ttf"), ("PlexMono", "IBMPlexMono-Regular.ttf"),
                       ("Newsreader", "Newsreader-SemiBold.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))
    addMapping("Plex", 0, 0, "Plex")
    addMapping("Plex", 1, 0, "PlexSemiBold")
    addMapping("Plex", 0, 1, "PlexMedium")  # no italic is vendored: emphasis is set in the medium weight
    addMapping("Plex", 1, 1, "PlexSemiBold")


def inline(text: str) -> str:
    """Markdown inline marks of PROJECT_RULES.md to reportlab paragraph markup."""
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"`([^`]+)`", lambda m: f'<font name="PlexMono" size="8">{m.group(1)}</font>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2" color="' + ACCENT + r'">\1</link>', t)
    return t


def blocks(md: str) -> list[tuple[str, object]]:
    """(kind, payload) for each block: h1, h2, h3, para, bullets, table."""
    out: list[tuple[str, object]] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,3}) (.*)$", ln)
        if m:
            out.append((f"h{len(m.group(1))}", m.group(2)))
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append(("table", rows))
        elif re.match(r"^\s*- ", ln):
            items: list[str] = []
            while i < len(lines) and (re.match(r"^\s*- ", lines[i]) or (lines[i].startswith("  ") and items)):
                if re.match(r"^\s*- ", lines[i]):
                    items.append(re.sub(r"^\s*- ", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            out.append(("bullets", items))
        else:
            para = [ln]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,3} |\||\s*- )", lines[i]):
                para.append(lines[i])
                i += 1
            out.append(("para", " ".join(p.strip() for p in para)))
    return out


_DECISION = re.compile(r"^\*\*(D\d+)\. (.+?)\*\* \*Rule:\*(.*?)\*Why:\*(.*?)\*Affected[^*]*:\*(.*)$")


def decision_parts(text: str) -> dict | None:
    m = _DECISION.match(text)
    if not m:
        return None
    return {"id": m.group(1), "head": m.group(2), "rule": m.group(3).strip(), "why": m.group(4).strip(), "affected": m.group(5).strip()}


def git_sha() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%h", "--", str(SRC)], capture_output=True,
                              text=True, timeout=10).stdout.strip() or "uncommitted"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def render(src: Path = SRC, out: Path = OUT) -> dict:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    md = src.read_text(encoding="utf-8")
    if SUPER_SUB.search(md):
        raise ValueError("PROJECT_RULES.md holds a Unicode superscript or subscript character; write plain digits")
    _fonts()
    ink, muted, accent = colors.HexColor(INK), colors.HexColor(MUTED), colors.HexColor(ACCENT)
    base = ParagraphStyle("base", fontName="Plex", fontSize=9.2, leading=13, textColor=ink, alignment=TA_LEFT, spaceAfter=5)
    st = {
        "title": ParagraphStyle("title", parent=base, fontName="Newsreader", fontSize=24, leading=28, spaceAfter=4),
        "sub": ParagraphStyle("sub", parent=base, textColor=muted, fontSize=9, spaceAfter=14),
        "h1": ParagraphStyle("h1", parent=base, fontName="Newsreader", fontSize=24, leading=28, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base, fontName="Newsreader", fontSize=15, leading=19, spaceBefore=12, spaceAfter=6, textColor=accent),
        "h3": ParagraphStyle("h3", parent=base, fontName="PlexSemiBold", fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=4),
        "para": base,
        "rule": ParagraphStyle("rule", parent=base, spaceAfter=8),
        "dhead": ParagraphStyle("dhead", parent=base, fontName="PlexSemiBold", spaceAfter=2),
        "dline": ParagraphStyle("dline", parent=base, leftIndent=10, spaceAfter=2),
        "cell": ParagraphStyle("cell", parent=base, fontSize=7.8, leading=10, spaceAfter=0),
        "bullet": ParagraphStyle("bullet", parent=base, spaceAfter=2),
    }
    sha = git_sha()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Plex", 7.5)
        canvas.setFillColor(muted)
        canvas.drawString(18 * mm, 10 * mm, f"Ocean Opportunity Radar. Assumptions & Decisions, from PROJECT_RULES.md ({sha}), rendered {stamp}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"page {doc.page}")
        canvas.restoreState()

    story: list = []
    counts = {"A": 0, "D": 0, "tables": 0}
    width = A4[0] - 36 * mm
    for kind, payload in blocks(md):
        if kind == "h1":
            story += [Paragraph("Assumptions &amp; Decisions", st["title"]),
                      Paragraph(inline(payload) + f". The rules register of the Ocean Opportunity Radar, rendered from PROJECT_RULES.md "
                                f"at {sha}. Times are UTC.", st["sub"])]
        elif kind in ("h2", "h3"):
            story.append(Paragraph(inline(payload), st[kind]))
        elif kind == "para":
            text = payload
            d = decision_parts(text)
            if d:
                counts["D"] += 1
                story.append(KeepTogether([
                    Paragraph(inline(f"**{d['id']}. {d['head']}**"), st["dhead"]),
                    Paragraph(inline(f"**Rule:** {d['rule']}"), st["dline"]),
                    Paragraph(inline(f"**Why:** {d['why']}"), st["dline"]),
                    Paragraph(inline(f"**Records affected:** {d['affected']}"), st["dline"]),
                    Spacer(1, 6)]))
                continue
            if re.match(r"^\*\*A\d+\. ", text):
                counts["A"] += 1
            elif re.match(r"^\*\*D\d+\. ", text):
                counts["D"] += 1  # a decision written in another shape still renders, as one paragraph
            story.append(Paragraph(inline(text), st["rule"] if text.startswith("**") or text.startswith("*Example") else st["para"]))
        elif kind == "bullets":
            story.append(ListFlowable([ListItem(Paragraph(inline(x), st["bullet"]), leftIndent=10, value="-", bulletFontName="Plex") for x in payload],
                                      bulletType="bullet", start="-", leftIndent=10, bulletFontName="Plex", bulletFontSize=8))
        elif kind == "table":
            counts["tables"] += 1
            rows = [[Paragraph(inline(c), st["cell"]) for c in r] for r in payload]
            n = max(len(r) for r in rows)
            t = Table(rows, colWidths=[width / n] * n, repeatRows=1)
            t.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "PlexSemiBold"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, accent), ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#d5dade")),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            story += [t, Spacer(1, 8)]
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title="Assumptions & Decisions: Ocean Opportunity Radar", author="Ocean Opportunity Radar team (Old Hackers)",
                            subject="PROJECT_RULES.md rendered", creator="radar/rules_pdf.py (reportlab)")
    from functools import partial
    from reportlab.pdfgen.canvas import Canvas
    # the canvas starts in the vendored font, so no unembedded base-14 font is referenced
    doc.build(story, onFirstPage=footer, onLaterPages=footer, canvasmaker=partial(Canvas, initialFontName="Plex", initialFontSize=9))
    return {"out": str(out), "bytes": out.stat().st_size, "assumptions": counts["A"], "decisions": counts["D"], "tables": counts["tables"],
            "sha": sha}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.rules_pdf", description=__doc__.split("\n")[0])
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    r = render(a.src, a.out)
    print(f"wrote {r['out']} ({r['bytes'] / 1e3:.0f} kB): {r['assumptions']} assumptions, {r['decisions']} decisions, "
          f"{r['tables']} tables, from PROJECT_RULES.md at {r['sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
