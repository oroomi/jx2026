"""The decision fallback (memo pass 3) is gated: a High thesis fit that rests on an industry code alone does not get impact read as
implied by the sector. It does when the fit has more behind it: a declared cohort or portfolio company, a fit reason from the
source's own text, or a name word corroborated by a record from a different source family. Synthetic companies only."""
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import db, emit, memo, store, thesis
from radar.adapters import prh_notices  # noqa: F401  (registers the notice signal types on emit.SIGNAL_TYPES)

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"
TODAY = date(2026, 10, 16)
NOTE = "more public evidence needed: Ocean impact (fit rests on the industry code alone)"
CODE_ON_LIST = "30110"       # on the thesis industry-code list: thesis fit High from the code alone
CODE_OFF_LIST = "58290"      # not on the list


def _day(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "gate.sqlite"))
    c = db.connect(tmp_path / "gate.sqlite")
    yield c
    c.close()


def _company(conn, key, name, code=CODE_ON_LIST, tag="feed", extra=()):
    """A register entry and a PRH startup notice (one registry), plus `extra` = (signal_type, adapter, text-or-None) records."""
    emit.upsert_company(conn, company_key=key, name=name, y_tunnus=key, founded=_day(40), country="FI", industry_code=code,
                        industry_desc="Fixture activity", group_tag=tag, source_url=f"https://example.test/prh/{key}")
    for typ, ad, dt in (("register_entry", "prh", 40), ("startup_notice", "prh_notices", 30)):
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=_day(dt), source_url=f"https://example.test/{ad}/{key}/{typ}",
                         confidence="high", adapter=ad)
    for typ, ad, text in extra:
        url = f"https://example.test/{ad}/{key}/{typ}"
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=_day(20), source_url=url, confidence="medium", adapter=ad)
        sid = conn.execute("SELECT id FROM signals WHERE source_url=?", (url,)).fetchone()[0]
        for field, t in (text or {}).items():
            conn.execute("INSERT INTO signal_text (signal_id, field, text) VALUES (?,?,?)", (sid, field, t))
    conn.commit()


def _memo(conn, key):
    return memo.build(conn, thesis.load(), key, today=TODAY.isoformat())


# ---- the gate as data --------------------------------------------------------------------------------------------------

def test_gate_is_configured_as_data_and_every_name_is_known():
    th = thesis.load()
    fb = th["memo"]["decisions"]["fallback"]
    assert set(fb["requires_any"]) == {"declared_member", "own_text", "corroborated_signal"}   # D85: the line of business is code-level evidence
    for path in thesis.available().values():
        cfg = (thesis.load(path)["memo"]["decisions"].get("fallback") or {})
        assert set(cfg.get("requires_any") or []) <= set(memo.SUPPORT_KEYS), path


def test_fallback_function_applies_the_gate():
    cfg = memo._cfg(thesis.load())
    b = {"impact": "unknown", "business": "Low", "investment": "unknown", "fit": "High", "technology": "unknown"}
    assert memo.fallback(b, cfg) is None and memo.fallback_blocked(b, cfg)                         # no support: the code alone
    assert memo.decide(b, cfg)[0] is None
    for ev in ("declared_member", "own_text", "corroborated_signal"):
        assert memo.fallback(b, cfg, {ev})["id"] == "c2" and not memo.fallback_blocked(b, cfg, {ev})
        assert memo.decide(b, cfg, {ev})[0]["text"] == "the High-fit rule, impact implied by sector"
    assert memo.fallback(b, cfg, {"something_else"}) is None
    not_reached = dict(b, fit="Medium")                                                            # the fallback never reached it
    assert memo.fallback(not_reached, cfg, {"own_text"}) is None and not memo.fallback_blocked(not_reached, cfg)
    ungated = {"fallback": {k: v for k, v in cfg["fallback"].items() if k != "requires_any"}}
    assert memo.fallback(b, ungated)["id"] == "c2"                                                 # a config with no gate behaves as before


# ---- a company built end to end ------------------------------------------------------------------------------------------

def test_code_only_company_does_not_get_the_fallback(conn):
    _company(conn, "9400001-1", "Plain Code Only Oy")
    m = _memo(conn, "9400001-1")
    r = m["recommendation"]
    # D66: the industry code alone gives at most a Medium fit, so the fallback (High fit only) is never reached, rather than reached and blocked
    assert m["levels"]["fit"]["band"] == "Medium" and m["levels"]["impact"]["band"] == "unknown"
    assert r["decision"] == "WATCHLIST" and r["kind"] is None and r["matched"] is None and r["fallback_blocked"] is False
    assert "Ocean impact" in r["needs"]                                  # with a Medium fit the table also needs the other readiness levels
    assert any(a["text"].startswith("Revisit when the radar finds public evidence for: Ocean impact") for a in m["actions"])


def test_declared_company_gets_the_fallback(conn):
    for tag in ("cohort", "portfolio"):
        key = f"9400002-{tag[0]}"
        _company(conn, key, "Plain Declared Oy", tag=tag)
        r = _memo(conn, key)["recommendation"]
        assert r["decision"] == "PORTFOLIO SUPPORT" and r["kind"] == "member", tag     # D65: a declared member is supported, no fallback to an accelerator
        assert r["fallback_blocked"] is False


def test_own_text_company_gets_the_fallback(conn):
    _company(conn, "9400003-3", "Plain Project Oy", extra=[("eu_project", "cordis", {"objective": "A study of the sea and its fish."})])
    r = _memo(conn, "9400003-3")["recommendation"]
    assert r["decision"] == "ACCELERATOR" and r["matched"] == "the High-fit rule, impact implied by sector"
    # a High fit from the source's own text alone (the code is off the list) passes too
    _company(conn, "9400003-4", "Plain Text Oy", code=CODE_OFF_LIST, extra=[("eu_project", "cordis", {"objective": "A study of the sea and its fish."})])
    m = _memo(conn, "9400003-4")
    assert m["levels"]["fit"]["band"] == "High" and m["recommendation"]["kind"] == "fallback"


def test_corroborated_name_word_gets_the_fallback_but_a_same_family_record_does_not(conn):
    _company(conn, "9400004-4", "Marine Plain Oy", extra=[("eu_project", "cordis", None)])            # CORDIS: a different family
    assert _memo(conn, "9400004-4")["recommendation"]["kind"] == "fallback"
    _company(conn, "9400004-5", "Marine Plain Two Oy", extra=[("equity_event", "tax_registers", None)])  # the same registry family
    r = _memo(conn, "9400004-5")["recommendation"]
    assert r["decision"] == "WATCHLIST" and r["kind"] is None       # D66: a same-family record leaves the fit on the code alone, capped at Medium


def test_a_row_or_rule_match_never_reaches_the_gate(conn):
    # a code-only company whose levels the team's rules decide keeps that decision: the gate only guards pass 3. Technology High comes
    # from a BlueInvest profile's stated TRL (a public contract sets no TRL since D84); the contract sets business readiness Medium.
    _company(conn, "9400005-5", "Plain Rule Oy", extra=[("public_contract", "hilma", None)])
    conn.execute("INSERT INTO blueinvest_profiles (profile_id, company_key, title, trl, url, fetched_at) VALUES "
                 "('p-9400005-5', '9400005-5', 'Plain Rule', 8, 'https://example.test/bi/9400005-5', '2026-10-16T00:00:00Z')")
    conn.commit()
    r = _memo(conn, "9400005-5")["recommendation"]
    assert r["kind"] == "rule" and r["decision"] == "PARTNER INTRODUCTION" and r["fallback_blocked"] is False


# ---- printed rule and the real data ----------------------------------------------------------------------------------------

def test_method_page_prints_the_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "m.sqlite"))
    db.connect(tmp_path / "m.sqlite").close()
    from app import app
    t = TestClient(app).get("/method").text
    assert 'id="memo-fallback"' in t and "more than an industry code" in t and "stays on the watchlist" in t


@pytest.fixture()
def snap(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    return thesis.load()


def test_on_the_snapshot_a_code_only_company_is_gated_and_a_declared_one_is_not(snap):
    c = store.open_db(thesis=snap)
    try:
        assert _memo_snap(c, snap, "2962040-6")["decision"] == "PORTFOLIO SUPPORT"                    # Viva Jets: portfolio (D65)
        capped = [m for m in (memo.build(c, snap, k, today="2026-10-16") for (k,) in c.execute("SELECT company_key FROM companies WHERE group_tag='feed' LIMIT 400"))
                  if any("industry code alone" in w["text"] for w in m["why"])]
    finally:
        c.close()
    assert capped and all(m["levels"]["fit"]["band"] == "Medium" and m["recommendation"]["kind"] != "fallback" for m in capped)


def _memo_snap(c, th, key):
    return memo.build(c, th, key, today="2026-10-16")["recommendation"]
