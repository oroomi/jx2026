import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import company_fixture as fx  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / "t.sqlite"
    fx.build(path).close()
    monkeypatch.setenv("RADAR_DB", str(path))
    import app
    return TestClient(app.app)


def test_four_sections_in_order(client):
    t = client.get("/c/9000001-1").text
    pos = [t.index(x) for x in ("01</span> Who is most promising", "02</span> How ready are they", "03</span> Who comes next",
                                "04</span> What should happen next")]
    assert pos == sorted(pos)


def test_founded_and_ytunnus_chip_with_register_link(client):
    t = client.get("/c/9000001-1").text
    assert "2025-06-13" in t
    assert t.count(fx.PRH + "9000001-1") >= 3
    assert 'class="ev-chip"' in t


def test_no_ytunnus(client):
    t = client.get("/c/name:sparse").text
    assert "no Y-tunnus" in t and "not in public records" in t
    assert "ev-missing" in t


def test_bankrupt_status_word_with_source(client):
    t = client.get("/c/9000003-3").text
    assert "status-bankrupt" in t and "bankrupt" in t


def test_readiness_without_signals_is_empty(client):
    t = client.get("/c/name:sparse").text
    assert t.count("no public evidence") >= 4
    assert not re.search(r"level \d of 9", t)


def test_later_sections_are_honest_lines(client):
    t = client.get("/c/9000001-1").text
    assert "not yet scored: matching rules land Saturday" in t
    assert "not yet scored: next-step rules land Saturday" in t


def test_unknown_key_404_escaped(client):
    r = client.get("/c/<b>x</b>")
    assert r.status_code == 404
    assert "<b>x</b>" not in r.text and "&lt;b&gt;x&lt;/b&gt;" in r.text
    assert "no company with key" in r.text and 'href="/"' in r.text and 'type="search"' in r.text


def test_sticky_bar_n_from_db_links_radar(client):
    t = client.get("/c/9000001-1").text
    assert "Radar of 2" in t
    assert 'href="/radar"' in t.split('class="co-bar"')[1]
    assert "opens Saturday" not in t


def test_sticky_bar_links_when_radar_route_exists(client):
    import app
    app.app.add_api_route("/radar", lambda: "x")
    try:
        t = client.get("/c/9000001-1").text
        assert 'href="/radar"' in t.split('class="co-bar"')[1]
    finally:
        app.app.router.routes[:] = [x for x in app.app.router.routes if getattr(x, "path", None) != "/radar"]


def test_sources_and_connectors(client):
    t = client.get("/c/9000001-1").text
    assert "Sources on this page" in t and "https://example.test/cordis/1" in t
    assert t.count("connector slot, not connected") == 5


def test_no_em_dash_and_search(client):
    t = client.get("/c/9000001-1").text
    assert chr(0x2014) not in t
    assert "Synthetic Rich" in client.get("/company-search?q=rich").text
