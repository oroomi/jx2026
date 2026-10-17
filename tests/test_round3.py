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
