import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import earliness, thesis
from tests.fixtures import earliness_fixture as fx

HEALTH = Path("/root/hack/shared/jx2026/radar_health_tech_turku.sqlite")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data = tmp_path / "d"
    data.mkdir()
    monkeypatch.setenv("RADAR_DATA_DIR", str(data))
    conn = fx.build(data / "radar_redstone_apelago_blue.sqlite")
    th = thesis.load(thesis.resolve(None))
    totals = earliness.backtest(conn, th, entry_dates_path=tmp_path / "none.csv")
    from app import app
    return TestClient(app), totals


def test_counts_equal_module_totals(client):
    c, t = client
    html = c.get("/backtest").text
    assert t["headline"] in html
    for label, n in (("Found earlier by live public records", t["earlier"]), ("Found earlier only by declared research", t["declared"]),
                     ("Found later", t["later"]), ("No public signal", t["none"])):
        assert f"{label}: <strong>{n}</strong>" in html
    assert earliness.rule_lines(thesis.load(thesis.resolve(None)))[0].split(":")[0] in html


def test_one_lane_per_cohort_company(client):
    c, t = client
    html = c.get("/backtest").text
    assert len(re.findall(r'class="bt-lane', html)) == t["total"] == 15
    assert html.count('href="/c/') >= 2 * t["total"]  # lane name and table row both link to the company page


def test_blank_lane_has_words_and_no_marker(client):
    c, t = client
    html = c.get("/backtest").text
    lanes = re.findall(r'<g class="bt-lane blank".*?</g>', html, flags=re.S)
    assert len(lanes) == t["none"] == 6
    for lane in lanes:
        assert "no public signal" in lane and 'class="mk' not in lane and "<circle" not in lane


def test_year_only_marker_is_hollow_and_labelled(client):
    c, _ = client
    html = c.get("/backtest").text
    hollow = re.findall(r'<circle class="mk hollow".*?</g>', html, flags=re.S)
    assert len(hollow) == 2 and all("year only" in h for h in hollow)
    assert len(re.findall(r'<circle class="mk"', html)) == 7


def test_health_thesis_shows_empty_state(tmp_path, monkeypatch):
    data = tmp_path / "d"
    data.mkdir()
    monkeypatch.setenv("RADAR_DATA_DIR", str(data))
    from radar import db
    db.connect(data / "radar_health_tech_turku.sqlite").close()
    from app import app
    html = TestClient(app).get("/backtest?thesis=health_tech_turku").text
    assert "this thesis has no cohort group, nothing to backtest" in html and "bt-chart" not in html


def test_no_em_dash_in_page(client):
    assert chr(0x2014) not in client[0].get("/backtest").text
