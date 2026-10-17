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
