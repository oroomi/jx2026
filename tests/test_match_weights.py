"""Weigh the reasons (D90): the weight panel above a startup's counterparts on /match, on the committed snapshot store (data/snapshot).
Unit tests for the query parsing, the ranking rule and the include; a chromium test (skipped where missing) moves the sliders and checks
the order the browser draws against the rule, the brief preset, a counterpart brought up from below the cut, and that no score appears."""
import json
import os
from html import unescape
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import match_weights as mw, matchmaker, thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")
ARCTIC, VIVA = "3166759-6", "2962040-6"
THESIS_W = {"sector": 3, "lookalike": 3, "keywords": 2, "readiness": 2, "timing": 1, "geography": 1}


def _use_snapshot(mp):
    mp.setenv("RADAR_DATA_DIR", str(SNAP))
    mp.delenv("RADAR_DB", raising=False)
    mp.delenv("RADAR_THESIS", raising=False)
    mp.setenv("RADAR_NO_WARM", "1")


@pytest.fixture(autouse=True)
def _snapshot_env(monkeypatch):
    _use_snapshot(monkeypatch)


@pytest.fixture()
def client():
    import app
    return TestClient(app.app)


def embedded(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="mw-data">(.*?)</script>', html, re.S)
    assert m, "no weight panel data on the page"
    return json.loads(m.group(1))


# ---- 1. the query value and the scale -----------------------------------------------------------------------------------------------
def test_parse_w_reads_the_link_and_ignores_what_it_cannot_use():
    base = mw.thesis_values(THESIS_W)
    full = mw.parse_w("sector-25,readiness-20,geography-15,lookalike-10,timing-5,keywords-10", THESIS_W)
    assert full == mw.brief_values(THESIS_W) == {"sector": 25, "readiness": 20, "geography": 15, "lookalike": 10, "timing": 5, "keywords": 10}
    assert mw.parse_w("timing-50", THESIS_W) == {**base, "timing": 50}                 # a factor left out keeps the thesis file's value
    assert mw.parse_w("ticket-15,sector-0,bogus-3,keywords-x,,geography-999", THESIS_W) == {**base, "sector": 0, "geography": mw.slider_max(THESIS_W)}
    assert mw.parse_w("sector-1,geography-99999", THESIS_W) == {**base, "sector": 1}   # more than three digits is not a weight
    assert mw.parse_w(" SECTOR-7 ", THESIS_W)["sector"] == 7
    for raw in (None, "", "ticket-15", "nonsense", "sector=3", "sector--3"):
        assert mw.parse_w(raw, THESIS_W) is None, raw
    assert mw.parse_w(mw.format_w(full, THESIS_W), THESIS_W) == full
    assert mw.format_w(full, THESIS_W) == "sector-25,readiness-20,geography-15,lookalike-10,timing-5,keywords-10"


def test_the_thesis_scale_keeps_the_shares_and_the_brief_drops_ticket_size():
    base = mw.thesis_values(THESIS_W)
    k = base["sector"] // THESIS_W["sector"]
    assert k >= 1 and all(base[f] == THESIS_W[f] * k for f in THESIS_W) and max(base.values()) <= mw.SLIDER_MAX
    assert "ticket" not in mw.brief_values(THESIS_W) and mw.BRIEF["ticket"] == 15
    assert sum(mw.shares(mw.brief_values(THESIS_W)).values()) in (99, 100, 101)
    assert mw.shares({"sector": 0, "timing": 0}) == {"sector": 0, "timing": 0}


def test_the_rule_sums_the_weights_of_the_reasons_that_hold_and_keeps_the_server_order_on_ties():
    rows = [{"id": "a", "met": ["sector"]}, {"id": "b", "met": ["timing", "geography"]}, {"id": "c", "met": ["sector"]}, {"id": "d", "met": []}]
    assert mw.order(rows, {"sector": 3, "timing": 1, "geography": 1}) == ["a", "c", "b", "d"]
    assert mw.order(rows, {"sector": 0, "timing": 50, "geography": 1}) == ["b", "a", "c", "d"]
    assert mw.order(rows, {"sector": 0, "timing": 0, "geography": 0}) == ["a", "b", "c", "d"]


def test_with_the_thesis_weights_the_rule_gives_the_server_order_for_every_featured_startup():
    th = thesis_mod.load()
    base = mw.thesis_values(matchmaker.matchtext.config(th)["weights"])
    import sqlite3
    conn = sqlite3.connect(f"file:{SNAP / 'radar_redstone_apelago_blue.sqlite'}?mode=ro", uri=True)
    keys = [r[0] for r in conn.execute("SELECT company_key FROM companies WHERE group_tag IN ('cohort','portfolio')")]
    conn.close()
    checked = 0
    for key in keys:
        res = matchmaker.match_company(key, th, limit=1000)
        if not res or not res["counterparts"]:
            continue
        p = mw.panel(dict(res, counterparts=res["counterparts"][:12]), th)
        assert mw.order(p["rows"], base) == [r["id"] for r in res["counterparts"]], key
        checked += 1
    assert checked >= 10


# ---- 2. the include on the page -----------------------------------------------------------------------------------------------------
def test_match_html_has_one_include_right_above_the_counterparts():
    src = (ROOT / "radar" / "templates" / "match.html").read_text()
    assert src.count('{% include "_match_weights.html" %}') == 1
    i = src.index('{% include "_match_weights.html" %}')
    assert src.rindex("Next steps (", 0, i) < i < src.index('<ol class="mt-results">', i) < i + 80, "between the Next steps heading and its list"


def test_the_panel_renders_hidden_above_the_list_with_seven_factors(client):
    html = client.get(f"/match?company={VIVA}").text
    assert html.index('id="mw"') < html.index('<ol class="mt-results">')
    panel = unescape(html[html.index('<details class="mw"'):html.index("</details>", html.index('<details class="mw"'))])
    assert "hidden" in panel.split(">")[0], "without JavaScript the panel stays hidden and the server order stands"
    assert "Your weights change the order, never a score" in panel
    for label in ("Sector and thesis", "Stage", "Geography", "Ticket size", "Portfolio similarity", "Recent activity", "Strategic fit"):
        assert f'<span class="mw-n">{label}</span>' in panel, label
    for engine in ("Sector or impact area", "Readiness window", "Portfolio lookalike", "Timing", "Shared words"):
        assert engine in panel, engine
    assert panel.count('type="range"') == 6
    assert "Not in public records: a startup's funding ask is not published (connector slot)" in panel
    assert "The thesis file's weights" in panel and "The brief's weights" in panel and ">Reset<" in panel
    assert "/100" not in html and "—" not in panel
    d = embedded(html)
    assert d["shown"] == 12 and len(d["rows"]) > 12 and d["company"] == VIVA
    lis = re.findall(r'<a class="mt-res-n" href="/match\?org=([^"]+)"', html[html.index('<ol class="mt-results">'):])
    assert [r["id"] for r in d["rows"][:12]] == lis[:12]


def test_a_link_with_weights_sets_the_sliders_and_names_the_preset(client):
    html = unescape(client.get(f"/match?company={VIVA}&w=sector-25,readiness-20,geography-15,lookalike-10,timing-5,keywords-10").text)
    assert re.search(r'id="mw-sector"[^>]*value="25"', html) and re.search(r'id="mw-timing"[^>]*value="5"', html)
    assert '<span class="mw-state" id="mw-state">The brief\'s weights</span>' in html
    assert re.search(r'data-preset="brief" aria-pressed="true"', html)
    html = client.get(f"/match?company={VIVA}&w=timing-50").text
    assert "Your weights</span>" in html and re.search(r'id="mw-timing"[^>]*value="50"', html)


def test_no_panel_on_the_counterpart_view_or_without_a_startup(client):
    assert 'id="mw"' not in client.get("/match").text
    assert 'id="mw"' not in client.get("/match?view=company").text
    assert 'id="mw"' not in client.get("/match?company=no-such-key").text


def test_rows_below_the_cut_come_back_as_the_same_list_rows(client):
    d = embedded(client.get(f"/match?company={VIVA}").text)
    j = client.get(f"/match/weights/rows?company={VIVA}&skip=12").json()
    assert [r["id"] for r in j["rows"]] == [r["id"] for r in d["rows"][12:]]
    for r in j["rows"]:
        assert r["html"].startswith('<li class="mt-res">') and f'href="/match?org={r["id"]}"' in r["html"] and 'class="mt-chips"' in r["html"]
        assert "/100" not in r["html"] and "%" not in r["html"].split('class="mt-why"')[0]
    assert client.get("/match/weights/rows?company=no-such-key").status_code == 404


# ---- 3. in a browser ----------------------------------------------------------------------------------------------------------------
@pytest.fixture()
def live_url():
    pytest.importorskip("playwright.sync_api")
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    env = {k: v for k, v in os.environ.items() if k not in ("RADAR_DB", "RADAR_THESIS")}
    env.update(RADAR_DATA_DIR=str(SNAP))
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(5)


def _browser(sync_api, viewport):
    p = sync_api.sync_playwright().start()
    browser, err = None, None
    for kwargs in ({}, {"executable_path": "/opt/pw-browsers/chromium"}):
        try:
            browser = p.chromium.launch(**kwargs)
            break
        except Exception as e:  # no browser binary of this kind on this machine
            err = e
    if browser is None:
        p.stop()
        pytest.skip(f"chromium unavailable: {err}")
    return p, browser, browser.new_page(viewport=viewport)


def _shown(page):
    return page.eval_on_selector_all("ol.mt-results > li a.mt-res-n", "as => as.map(a => new URL(a.href).searchParams.get('org'))")


def _rows_text(page):
    return page.inner_text("ol.mt-results")


def _values(page, keys):
    return {k: int(page.input_value(f"#mw-{k}")) for k in keys}


def _open(page, url):
    page.goto(url, timeout=120000)
    page.wait_for_selector("#mw[data-ready]", state="attached", timeout=60000)
    d = json.loads(page.inner_text("#mw-data"))
    if not page.evaluate("document.getElementById('mw').open"):
        page.click("#mw > summary")
    return d


def test_sliders_reorder_by_the_rule_and_no_score_appears(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _browser(sync_api, {"width": 1280, "height": 900})
    try:
        d = _open(page, f"{live_url}/match?company={VIVA}")
        server = [r["id"] for r in d["rows"]]
        assert _shown(page) == server[:12], "on load the page keeps the server's order"
        assert page.locator("ol.mt-results .mw-bar").count() == 12
        page.focus("#mw-sector")
        page.keyboard.press("Home")                                   # Sector and thesis to 0
        page.focus("#mw-timing")
        page.keyboard.press("End")                                    # Recent activity to the maximum
        w = _values(page, d["keys"])
        assert w["sector"] == 0 and w["timing"] == mw.slider_max(THESIS_W)
        expected = mw.order(d["rows"], w)
        assert expected[:12] != server[:12], "the snapshot moves under these weights"
        assert _shown(page) == expected[:12]
        assert page.locator("ol.mt-results .mw-move").count() >= 1
        assert re.search(r"\b(up|down) \d+\b", _rows_text(page))
        text = _rows_text(page)
        assert "%" not in text and "/100" not in text and "score" not in text.lower()
        assert "w=" in page.url and "sector-0" in page.url and f"timing-{w['timing']}" in page.url
        page.goto(page.url)                                           # the link reproduces the order
        page.wait_for_selector("#mw[data-ready]", state="attached")
        assert _shown(page) == expected[:12]

        page.click("button[data-preset=brief]")
        page.wait_for_timeout(300)
        assert _values(page, d["keys"]) == d["presets"]["brief"]
        assert _shown(page) == mw.order(d["rows"], d["presets"]["brief"])[:12]
        assert page.inner_text("#mw-state") == "The brief's weights"
        assert page.inner_text("#mw-o-sector") == "29%"
        text = _rows_text(page)
        assert "%" not in text and "/100" not in text

        page.click("button[data-reset]")
        page.wait_for_timeout(300)
        assert _shown(page) == server[:12] and "w=" not in page.url
    finally:
        browser.close()
        p.stop()


def test_a_counterpart_from_below_the_cut_comes_up_with_its_reasons(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    from fastapi.testclient import TestClient as TC
    import app
    d = embedded(TC(app.app).get(f"/match?company={VIVA}").text)
    top = mw.slider_max(THESIS_W)
    pick = None
    for k in d["keys"]:
        w = {x: (top if x == k else 0) for x in d["keys"]}
        o = mw.order(d["rows"], w)
        below = [i for i in o[:12] if [r["id"] for r in d["rows"]].index(i) >= 12]
        if below:
            pick = (w, o, below[0])
            break
    if pick is None:
        pytest.skip("no single-factor weighting brings a counterpart up from below the cut on this snapshot")
    w, o, comer = pick
    p, browser, page = _browser(sync_api, {"width": 390, "height": 844})
    try:
        _open(page, f"{live_url}/match?company={VIVA}&w=" + mw.format_w(w, THESIS_W))
        page.wait_for_function(f"document.querySelector('ol.mt-results a.mt-res-n[href=\"/match?org={comer}\"]')", timeout=30000)
        assert _shown(page) == o[:12]
        li = page.locator("ol.mt-results > li", has=page.locator(f'a.mt-res-n[href="/match?org={comer}"]'))
        assert li.locator(".mt-chips").count() == 1 and li.locator(".mw-bar").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        text = _rows_text(page)
        assert "%" not in text and "/100" not in text
    finally:
        browser.close()
        p.stop()
