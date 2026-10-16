import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from radar import fit, thesis as thesis_mod  # noqa: E402

TH = thesis_mod.load()


def co(**kw):
    base = {"name": "Plain Words Oy", "industry_code": None, "source_url": "https://example.test/x", "fetched_at": "2026-10-16T00:00:00Z"}
    base.update(kw)
    return base


def test_code_only_is_low():
    r = fit.fit(co(industry_code="71200"), [], TH)
    assert [(x["kind"], x["confidence"]) for x in r] == [("industry_code", "low")]
    assert r[0]["evidence"]["url"]


def test_keyword_in_name_is_medium():
    r = fit.fit(co(name="Marine Synthetic Oy"), [], TH)
    assert [(x["kind"], x["confidence"]) for x in r] == [("name_keyword", "medium")]
    assert "marine" in r[0]["text"]


def test_none():
    assert fit.fit(co(), [], TH) == []


def test_signal_keeps_own_confidence_and_order():
    sig = {"signal_type": "eu_project", "date": "2026-03-01", "confidence": "high", "detail": None, "source_url": "https://example.test/s",
           "adapter": "cordis", "fetched_at": "2026-10-16T00:00:00Z"}
    r = fit.fit(co(industry_code="71200", name="Aqua Oy"), [sig], TH)
    assert [x["kind"] for x in r] == ["industry_code", "name_keyword", "signal"]
    assert r[2]["confidence"] == "high"
    assert "score" not in "".join(x["text"] for x in r).lower()
