import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import store, thesis
from tests.fixtures import feed_precision_fixture as fx

SHARED_HEALTH = Path("/root/hack/shared/jx2026/radar_health_tech_turku.sqlite")
HEALTH_ID = "health_tech_turku"
DEFAULT_ID = "redstone_apelago_blue"


@pytest.fixture()
def built(tmp_path):
    conn = fx.build(tmp_path / "p.sqlite")
    th = thesis.load(thesis.resolve(None))
    rows = {r["company_key"]: r for r in store.feed(conn, th, limit=1000)}
    return conn, th, rows


def test_each_reason_admits_a_row(built):
    _, _, rows = built
    assert rows["F-code"]["reasons"] == ["industry_code"] and rows["F-code"]["strength"] == "strong"
    assert rows["F-lob"]["reasons"] == ["line_of_business"] and rows["F-lob"]["strength"] == "strong"
    assert rows["F-own"]["reasons"] == ["own_text"] and rows["F-own"]["strength"] == "strong"
    assert rows["F-corr"]["reasons"] == ["corroborated_keyword"] and rows["F-corr"]["strength"] == "strong"


def test_name_keyword_only_row_is_weak_and_kept(built):
    _, _, rows = built
    r = rows["F-weak"]
    assert r["strength"] == "weak" and r["reasons"] == []
    assert r["why"].startswith("Weak: only the legal name ('Fixture Sea Weak Oy') contains 'sea'")
    assert "'Software publishing' (58290)" in r["why"]


def test_corroboration_needs_a_different_adapter(built):
    _, _, rows = built
    assert "corroborated_keyword" in rows["F-corr"]["reasons"]
    assert rows["F-one"]["strength"] == "weak"  # two signals, one adapter


def test_year_only_bf_is_not_entry_but_corroborates(built):
    conn, th, rows = built
    assert rows["F-year"]["signal_type"] == "register_entry"
    assert "corroborated_keyword" in rows["F-year"]["reasons"]
    assert "Business Finland export record from %d (year only)" % (fx.TODAY.year - 1) in rows["F-year"]["why"]
    assert "F-yearonly" not in rows  # its only in-window signal is year-only: no entry date
    assert store.feed_counts(conn, th)["year_only_not_entry"] == 2


def test_why_text_uses_stored_values_and_only_row_names(built):
    _, _, rows = built
    assert rows["F-code"]["why"] == "Why: Industry code 30110 (Fixture shipbuilding, PRH) is on the thesis list."
    assert rows["F-lob"]["why"] == "Why: The registered line of business 'Construction of water projects' contains 'water'."
    for r in rows.values():
        for m in re.findall(r"'(Fixture [^']+)'", r["why"]):
            assert m == r["name"]
    assert "'vesi'" in rows["F-own"]["why"]


def test_counts_and_footer_equal_rendered_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("RADAR_DB", raising=False)
    fx.build(tmp_path / f"radar_{DEFAULT_ID}.sqlite")
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    import app
    t = TestClient(app.app).get("/").text
    head, _, weak_part = t.partition('<details class="weak"')
    main_n, weak_n = head.count('class="feed-row'), weak_part.count('class="feed-row')
    assert main_n == int(re.search(r'n-main">(\d+)<', t).group(1)) == 5
    assert weak_n == int(re.search(r'n-weak">(\d+)<', t).group(1)) == 2
    assert f"Weak matches ({weak_n})" in t
    th = thesis.load(thesis.resolve(None))
    c = store.feed_counts(store.open_db(tmp_path / f"radar_{DEFAULT_ID}.sqlite"), th)
    assert (c["main"], c["weak"]) == (main_n, weak_n)
    assert set(c["by_reason"]) == set(store.REASON_IDS)
    m = TestClient(app.app).get("/method").text
    assert "Feed precision" in m and "a hint, not proof" in m and f"{c['main']} companies in the main list" in m


def test_health_swap_main_feed_non_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("RADAR_DB", raising=False)
    fx.build(tmp_path / f"radar_{DEFAULT_ID}.sqlite")
    fx.build(tmp_path / f"radar_{HEALTH_ID}.sqlite", words=("health", "bio"), code="86900", hilma_kw="terveys")
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    import app
    t = TestClient(app.app).get(f"/?thesis={HEALTH_ID}").text
    head = t.partition('<details class="weak"')[0]
    assert head.count('class="feed-row') >= 1 and "industry code 86900" in t.lower()


@pytest.mark.skipif(not SHARED_HEALTH.is_file(), reason="shared health database absent")
def test_real_health_copy_main_feed_not_empty(tmp_path, monkeypatch):
    shutil.copy(SHARED_HEALTH, tmp_path / f"radar_{HEALTH_ID}.sqlite")
    th = thesis.load(thesis.resolve(HEALTH_ID))
    conn = store.open_db(tmp_path / f"radar_{HEALTH_ID}.sqlite")
    c = store.feed_counts(conn, th, today=conn.execute("SELECT MAX(date) FROM signals").fetchone()[0])
    assert c["main"] > 0
