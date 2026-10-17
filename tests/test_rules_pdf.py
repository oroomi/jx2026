"""The Assumptions & Decisions PDF (jx40): rendered from PROJECT_RULES.md, A4 portrait, vendored fonts, every decision parsed."""
import re
from pathlib import Path

import pytest

from radar import rules_pdf

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "PROJECT_RULES.md"
COMMITTED = ROOT / "docs" / "method" / "assumptions_and_decisions.pdf"


def test_every_decision_has_rule_reason_and_records_affected():
    md = RULES.read_text(encoding="utf-8")
    ds = [t for k, t in rules_pdf.blocks(md) if k == "para" and re.match(r"^\*\*D\d+\. ", t)]
    parts = [rules_pdf.decision_parts(t) for t in ds]
    assert len(parts) >= 21 and all(p and p["rule"] and p["why"] and p["affected"] for p in parts)
    ids = [p["id"] for p in parts]
    reserved = {f"D{i}" for i in range(32, 36)}   # held for the branch that adds D32 to D35 (fix/hygiene starts at D36); absent until it merges
    assert ids == [f"D{i}" for i in range(1, int(ids[-1][1:]) + 1) if f"D{i}" in ids or f"D{i}" not in reserved]


def test_fonts_are_vendored():
    for f in ("IBMPlexSans-Regular.ttf", "IBMPlexSans-Medium.ttf", "IBMPlexSans-SemiBold.ttf", "IBMPlexMono-Regular.ttf", "Newsreader-SemiBold.ttf"):
        assert (rules_pdf.FONTS / f).is_file(), f


def test_committed_pdf_is_a4_and_small():
    data = COMMITTED.read_bytes()
    assert data.startswith(b"%PDF") and len(data) < 2_000_000
    assert re.search(rb"/MediaBox \[ 0 0 595\.27\d* 841\.88\d* \]", data)
    for name in (b"IBMPlexSans-Regular", b"IBMPlexMono-Regular", b"Newsreader"):
        assert name in data


def test_render_refuses_superscripts_and_writes_a4(tmp_path):
    pytest.importorskip("reportlab")
    bad = tmp_path / "bad.md"
    bad.write_text("# x\n\nCO₂ and m²\n", encoding="utf-8")
    with pytest.raises(ValueError):
        rules_pdf.render(bad, tmp_path / "bad.pdf")
    r = rules_pdf.render(RULES, tmp_path / "out.pdf")
    assert r["decisions"] >= 21 and r["assumptions"] >= 33 and r["bytes"] < 2_000_000
