"""Fund memo (radar/memo.py): decision table engine on fixtures, plus the three named cases on the snapshot."""
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import db, emit, matching, memo, store, thesis
from radar.adapters import ecosystem
from tests.fixtures import ecosystem_fixture as fx

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"
CFG = {"rows": [
    {"id": 1, "impact": "High", "business": "High", "investment": "High", "fit": "High", "decision": "INVEST"},
    {"id": 2, "impact": "High", "business": "Medium", "investment": "Low", "fit": "High", "decision": "GRANT SUPPORT"},
    {"id": 3, "impact": "Low", "business": "Low", "investment": "Low", "fit": "Low", "decision": "REJECT / LOW FIT"}],
    "rules": [{"id": "c", "when": {"impact": "High", "business": "Medium"}, "decision": "ACCELERATOR"},
              {"id": "e", "when": {"technology": "High", "business": ["Low", "Medium"]}, "decision": "PARTNER INTRODUCTION"},
              {"id": "g", "when": {"impact": "Low", "fit": "Low"}, "decision": "REJECT / LOW FIT"}]}


def bands(i="High", b="High", v="High", f="High", t="Medium"):
    return {"impact": i, "business": b, "investment": v, "fit": f, "technology": t}


def test_band_mapping_and_unknown_is_never_low():
    spec = {"low_max": 3, "high_min": 7}
    assert [memo.band(x, spec) for x in (1, 3, 4, 6, 7, 9)] == ["Low", "Low", "Medium", "Medium", "High", "High"]
    assert memo.band(None, spec) == "unknown"


def test_pass_one_exact_row_then_pass_two_rules_then_watchlist():
    row, _ = memo.decide(bands(), CFG)
    assert row["decision"] == "INVEST" and row["text"] == "row 1, H/H/H/H"
    row, _ = memo.decide(bands("High", "Medium", "Low", "High"), CFG)
    assert row["text"] == "row 2, H/M/L/H"
    row, _ = memo.decide(bands("High", "Medium", "High", "Medium"), CFG)       # no row: rule c
    assert row["decision"] == "ACCELERATOR" and row["text"] == "rule c"
    row, _ = memo.decide(bands("Medium", "Low", "Low", "Medium", "High"), CFG)  # rule e needs technology High
    assert row["decision"] == "PARTNER INTRODUCTION" and row["text"] == "rule e"
    row, unknown = memo.decide(bands("Medium", "High", "High", "Medium"), CFG)
    assert row is None and unknown == []                                        # unmatched: the caller falls to WATCHLIST


def test_unknown_level_does_not_match_a_named_band():
    row, unknown = memo.decide(bands("High", "High", "unknown", "High"), CFG)
    assert row is None and unknown == ["investment"]
    row, unknown = memo.decide(bands("unknown", "Low", "Low", "Low"), CFG)
    assert row is None and "impact" in unknown                 # reject needs impact Low on evidence
    row, _ = memo.decide(bands("Low", "Low", "Low", "Low"), CFG)
    assert row["decision"] == "REJECT / LOW FIT"


def test_the_teams_ten_rows_and_seven_rules_are_in_the_config():
    for key, v in thesis.available().items():
        d = thesis.load(v)["memo"]["decisions"]
        assert len(d["rows"]) == 10 and [r["decision"] for r in d["rows"]][:3] == ["INVEST", "DUE DILIGENCE", "ACCELERATOR"]
    blue = thesis.load()["memo"]["decisions"]
    assert [r["id"] for r in blue["rules"]] == list("abcdefg") and blue["rows"][7]["decision"] == "REJECT / LOW FIT"


@pytest.fixture()
def world(tmp_path):
    ds = tmp_path / "eco.sqlite"
    fx.build_dataset(ds)
    conn = fx.build_radar(tmp_path / "r.sqlite")
    ecosystem.run(conn, None, path=ds)
    return conn


def test_memo_on_fixture_has_the_four_parts_and_links(world):
    th = thesis.load()
    m = memo.build(world, th, "9100001-1", today="2026-10-16")
    assert m["recommendation"]["decision"] in memo.DECISIONS
    assert m["recommendation"]["because"].count(" / ") == 3
    assert all(w["url"].startswith("http") for w in m["why"])
    assert 1 <= len(m["actions"]) <= 3 and all(a["url"].startswith("http") for a in m["actions"])
    assert memo.build(world, th, "no-such-key") is None


def test_company_without_levels_lands_in_watchlist_with_what_is_missing(world):
    th = thesis.load()
    m = memo.build(world, th, "9100002-2", today="2026-10-16")
    r = m["recommendation"]
    assert r["decision"] == "WATCHLIST" and r["note"].startswith("more public evidence needed:")
    assert any("No public evidence" in k["text"] and k["url"] is None for k in m["risks"])


def test_no_unlinked_claim_in_why_or_actions(world):
    th = thesis.load()
    for key in ("9100001-1", "9100002-2", "name:fixture-domain"):
        m = memo.build(world, th, key, today="2026-10-16")
        if m:
            assert all(x["url"] for x in m["why"] + m["actions"])


def test_next_rules_speak_to_the_fund():
    text = " ".join(matching.NEXT_RULES).casefold()
    assert "introduce them to" in text and "ask about" in text and "meet now" in text and "check in" in text and "watch" in text
    assert "apply to" not in text and "raise:" not in text


# ---- snapshot -----------------------------------------------------------------------------------------------
@pytest.fixture()
def snap(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    from radar import build
    th = thesis.load()
    conn = db.connect(thesis.db_path(th))
    try:
        ecosystem.run(conn, th)
        conn.commit()
    except Exception:
        pytest.skip("ecosystem dataset not available")
    conn.close()
    return th


def test_kelluu_on_the_snapshot(snap):
    conn = store.open_db(thesis=snap)
    m = memo.build(conn, snap, "2902007-2", today="2026-10-16")
    conn.close()
    assert m["recommendation"]["decision"] in memo.DECISIONS
    assert any("Business Finland" in w["text"] or "funding" in w["text"] for w in m["why"])
    assert all(w["url"].startswith("http") for w in m["why"]) and m["actions"]


def test_company_with_almost_no_evidence_on_the_snapshot(snap):
    conn = store.open_db(thesis=snap)
    m = memo.build(conn, snap, "no-tunisea", today="2026-10-16")
    conn.close()
    r = m["recommendation"]
    assert r["decision"] == "WATCHLIST" and "more public evidence needed" in r["note"]
    assert m["risks"] and all(x["url"] for x in m["why"])


def test_company_page_includes_the_memo_and_print_rule(snap):
    from app import app
    html = TestClient(app).get("/c/2902007-2").text
    assert 'id="memo"' in html and "Print memo" in html and "Recommended actions for the fund" in html
    assert "@media print" in (Path(__file__).resolve().parent.parent / "radar" / "static" / "memo.css").read_text()


def test_health_thesis_memo_has_no_ocean_wording(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    th = thesis.load(thesis.available()["health_tech_turku"])
    conn = db.connect(thesis.db_path(th))
    emit.upsert_company(conn, company_key="9200001-1", name="Fixture Health Oy", source_url="https://example.test/h", industry_code="86909", country="FI")
    emit.emit_signal(conn, company_key="9200001-1", signal_type="bf_funding", date="2026-06-01", source_url="https://example.test/bf", confidence="high", adapter="businessfinland")
    conn.commit()
    m = memo.build(conn, th, "9200001-1", today="2026-10-16")
    blob = repr(m).casefold() + " ".join(th["memo"]["labels"].values()).casefold() + th["memo"]["decisions"]["source"].casefold()
    for w in ("ocean", "blue", "marine", "maritime"):
        assert w not in re.findall(r"[a-z]+", blob)
    assert m["recommendation"]["decision"] in memo.DECISIONS
