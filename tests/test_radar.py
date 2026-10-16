import re

import pytest
from fastapi.testclient import TestClient

from radar import thesis
from radar.routes import radar as rr
from tests.fixtures import radar_fixture as fx


@pytest.fixture()
def env(tmp_path, monkeypatch):
    data = tmp_path / "d"
    data.mkdir()
    monkeypatch.setenv("RADAR_DATA_DIR", str(data))
    conn = fx.build(data / "radar_redstone_apelago_blue.sqlite")
    from app import app
    return TestClient(app), conn, thesis.load(thesis.resolve(None))


def test_ranking_count_then_latest_then_name(env):
    _, conn, th = env
    rows = rr.radar_rows(conn, th, "cohort")
    assert [r["name"] for r in rows][:5] == ["Fixture Top Oy", "Fixture Alpha Oy", "Fixture Bravo Oy", "Fixture Charlie Oy", "Fixture Single Oy"]
    assert [r["event_count"] for r in rows] == [3, 2, 2, 2, 1, 0, 0]


def test_zero_events_last_and_not_one(env):
    c, conn, th = env
    rows = rr.radar_rows(conn, th, "cohort")
    assert {r["name"] for r in rows[-2:]} == {"Fixture Blank Oy", "Fixture Keyword Oy"}
    assert all(r["event_count"] == 0 and r["latest"] is None for r in rows[-2:])
    html = c.get("/radar").text
    assert "No public event found (2)" in html and "no public events" in html


def test_year_only_counted_once_and_labelled(env):
    c, conn, th = env
    r = [x for x in rr.radar_rows(conn, th, "cohort") if x["company_key"] == "F-one"][0]
    assert r["event_count"] == 1 and r["latest"]["date_label"] == "2024 (year only)"
    assert "2024 (year only)" in c.get("/radar").text


def test_header_count_equals_rows_and_portfolio_block(env):
    c, _, _ = env
    html = c.get("/radar").text
    assert "7 cohort companies, 5 with at least one dated public event." in html
    coh = re.search(r'data-group="cohort".*?</section>', html, re.S).group(0)
    pf = re.search(r'data-group="portfolio".*?</section>', html, re.S).group(0)
    assert coh.count('class="rd-row') == 7 and pf.count('class="rd-row') == 2
    assert "Fixture Portfolio Oy" in pf and "Fixture Portfolio Oy" not in coh
    assert "Fixture Feed Oy" not in html
    assert "register adapters cover Finland only" in html and "connector slot, not connected" in html


def test_rule_nav_and_backtest_link(env):
    c, _, th = env
    html = c.get("/radar").text
    assert rr.rule_text(th) in html.replace("&#39;", "'")
    assert "Rank = the number of distinct dated public events in the database" in html
    assert 'href="/radar"' in html and 'href="/backtest"' in html


def test_empty_thesis_state(env):
    c, _, _ = env
    r = c.get("/radar?thesis=health_tech_turku")
    assert r.status_code == 200 and "no signals yet" in r.text or "this thesis has no declared cohort" in r.text


def test_company_bar_links_radar(env):
    c, _, _ = env
    html = c.get("/c/F-top").text
    assert 'class="co-bar"' in html and "Radar of 7" in html and "opens Saturday" not in html
