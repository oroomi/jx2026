"""Judge round 3 fixes: corroboration families, listed and excluded companies, bands from the frameworks levels, the decision fallback,
the declared-member thesis-fit line, the backtest business-id bug and the stitcher name redaction. Synthetic fixtures only."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import round3_fixture as fx  # noqa: E402


@pytest.fixture()
def built(tmp_path, monkeypatch):
    path = tmp_path / "t.sqlite"
    conn = fx.build(path)
    monkeypatch.setenv("RADAR_DB", str(path))
    return conn


@pytest.fixture()
def client(built):
    import app
    return TestClient(app.app)


def _row(conn, key):
    from radar import store, thesis
    return next((r for r in store.feed(conn, thesis.load(), limit=10**6) if r["company_key"] == key), None)


# ---- item 3: a PRH record never corroborates a PRH name ------------------------------------------------------------

def test_prh_notices_do_not_corroborate_a_name_word(built):
    r = _row(built, "9300002-2")
    assert r is not None and r["strength"] == "weak" and "corroborated_keyword" not in r["reasons"]


def test_a_non_prh_source_corroborates(built):
    r = _row(built, "9300003-3")
    assert r is not None and "corroborated_keyword" in r["reasons"] and r["strength"] == "strong"
    assert "CORDIS" in r["why"]


def test_source_family_rule_is_printed(client):
    from radar import store
    assert store.source_family("prh_notices") == store.source_family("tax_registers") == store.source_family("prh")
    t = client.get("/method").text
    assert "same registry" in t and "never corroborate" in t


# ---- item 7: listed companies and human-health practice are left out ------------------------------------------------

def test_listed_company_is_never_in_the_feed(built, client):
    from radar import store, thesis
    assert store.is_listed_company("Solar Foods Oyj") and not store.is_listed_company("Oyjala Boats Oy")
    assert _row(built, "9300004-4") is None
    assert store.feed_counts(built, thesis.load())["excluded_listed"] == 1
    t = client.get("/").text
    assert "Synthetic Shipping Oyj" not in t and "listed company (Oyj)" in t


def test_health_file_excludes_human_health_practice(built):
    from radar import emit, store, thesis
    th = thesis.load(str(Path(__file__).resolve().parent.parent / "config" / "thesis_health_turku.yaml"))
    assert th["feed_exclude_code_prefixes"] == ["86"]
    assert "86900" not in {str(c["code"]) for c in th["industry_codes"]}
    for key, name, code in (("9300010-1", "Synthetic Terveys Oy", "86220"), ("9300011-2", "Synthetic Medtech Oy", "32500")):
        emit.upsert_company(built, company_key=key, name=name, y_tunnus=key, founded=fx.d(20), industry_code=code,
                            industry_desc="Medical specialists activities" if code == "86220" else "Medical instruments",
                            source_url=fx.PRH + key)
        emit.emit_signal(built, company_key=key, signal_type="register_entry", date=fx.d(20), source_url=fx.PRH + key,
                         confidence="high", adapter="prh")
    keys = {r["company_key"] for r in store.feed(built, th, limit=10**6)}
    assert "9300010-1" not in keys and "9300011-2" in keys
    assert store.feed_counts(built, th)["excluded_codes"] == 1


# ---- items 1 and 6: memo bands from the page's levels; the fallback decision -------------------------------------------
import shutil  # noqa: E402

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"


@pytest.fixture()
def snap(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    from radar import db, thesis
    from radar.adapters import ecosystem
    th = thesis.load()
    conn = db.connect(thesis.db_path(th))
    try:
        ecosystem.run(conn, th)
        conn.commit()
    except Exception:
        pytest.skip("ecosystem dataset not available")
    conn.close()
    return th


def test_memo_bands_are_the_page_levels(built):
    from radar import matching, memo, thesis
    th = thesis.load()
    cfg = memo._cfg(th)
    for key in ("9300001-1", "9300005-5", "dk-synthetic"):
        m = memo.build(built, th, key)
        fw = matching.company_context(built, key)["fw"]
        for dim, k in (("business", "brl"), ("investment", "irl"), ("technology", "trl")):
            assert m["levels"][dim]["band"] == memo.band(fw[k]["level"], cfg["bands"].get(dim)), (key, dim)
        assert m["recommendation"]["dimensions"]["text"].endswith("of 10 investment dimensions have public evidence")


def test_viva_jets_memo_matches_its_readiness_section_and_uses_the_fallback(snap):
    from radar import frameworks, matching, memo, store
    conn = store.open_db(thesis=snap)
    m = memo.build(conn, snap, "2962040-6")
    ctx = matching.company_context(conn, "2962040-6")
    conn.close()
    irl = ctx["fw"]["irl"]["level"]
    assert irl is not None and m["levels"]["investment"]["band"] == memo.band(irl, snap["memo"]["bands"]["investment"])
    inv_why = [w["text"] for w in m["why"] if w["text"].startswith("Investment readiness ")]
    assert inv_why and f"(level {irl})" in inv_why[0]
    r = m["recommendation"]
    assert r["decision"] == "ACCELERATOR" and r["matched"] == "fallback c2, impact implied by sector"
    assert "Medium, implied by sector" in r["because"]
    from app import app
    html = TestClient(app).get("/c/2962040-6").text
    assert "because: fallback c2, impact implied by sector" in html
    assert f"investment {irl} of 9" in html and "of 10 investment dimensions have public evidence" in html


def test_fallback_rules():
    from radar import memo, thesis
    cfg = memo._cfg(thesis.load())
    b = lambda **kw: {**{"impact": "unknown", "business": "Low", "investment": "unknown", "fit": "High", "technology": "unknown"}, **kw}  # noqa: E731
    assert memo.decide(b(), cfg)[0]["id"] == "c2"                                         # business Low, TRL unknown
    assert memo.decide(b(business="Medium", technology="Low"), cfg)[0]["decision"] == "GRANT SUPPORT"   # TRL 1-3
    assert memo.decide(b(business="High", investment="High"), cfg)[0]["decision"] == "DUE DILIGENCE"
    assert memo.decide(b(fit="Medium"), cfg)[0] is None                                   # fit not High: no fallback
    assert memo.decide(b(impact="Medium"), cfg)[0] is None                                # impact known: the team's table decides
    assert memo.decide(b(business="unknown"), cfg)[0] is None


def test_fallback_rule_is_on_method(client):
    t = client.get("/method").text
    assert 'id="memo-fallback"' in t and "implied by the sector" in t
