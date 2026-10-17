"""Judge round 3, UI findings (branch fix/j3_ui): the ranking in words, the sector named on the company page, the Ask Aava button off the
answer, and numbers and links that agree (D70 to D74). Real committed snapshot store (data/snapshot); the home list is built once per module."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import home_list, store, thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")
HEALTH_ONLY = "1091401-7"      # Biocomputing Platforms Ltd Oy: held by the health sector's store only (the committed blue store does not hold it)


def _use_snapshot(mp):
    mp.setenv("RADAR_DATA_DIR", str(SNAP))
    mp.delenv("RADAR_DB", raising=False)
    mp.delenv("RADAR_THESIS", raising=False)
    mp.setenv("RADAR_NO_WARM", "1")


@pytest.fixture(autouse=True)
def _snapshot_env(monkeypatch):
    _use_snapshot(monkeypatch)


@pytest.fixture(scope="module")
def H():
    mp = pytest.MonkeyPatch()
    _use_snapshot(mp)
    try:
        yield home_list.for_template(thesis_mod.load(), wait=None)
    finally:
        mp.undo()


@pytest.fixture()
def client(H):
    import app
    return TestClient(app.app)


def text_of(html: str) -> str:
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# ---- 1. the ranking in words ------------------------------------------------------------------------------------------------------------
def test_every_row_carries_its_first_reason_in_words(H):
    assert H["rows"]
    for r in H["rows"]:
        assert r.get("reason"), r["name"]
        assert len(r["reason"]) <= home_list.REASON_MAX + 1 and "—" not in r["reason"] and "–" not in r["reason"]
        assert r["reason"][-1] in ".)" or r["reason"].endswith(("...", "...'")), r["reason"]


def test_a_reason_is_cut_at_a_clause_not_mid_word():
    long = "Thesis fit is high: registered industry (Building of pleasure and sporting boats) is on the thesis list; declared portfolio company."
    assert home_list.shorten(long, 110) == "Thesis fit is high: registered industry is on the thesis list; declared portfolio company."   # the long bracket is on the row already
    clause = "Thesis fit is high: registered industry is on the thesis list; declared portfolio company, with more words after it."
    assert home_list.shorten(clause, 70) == "Thesis fit is high: registered industry is on the thesis list."      # cut at the last clause that fits
    short = "Thesis fit is high: declared cohort company."
    assert home_list.shorten(short, 110) == short
    quoted = "Thesis fit is medium: the registered line of business 'Other service activities incidental to water transportation' contains 'water'."
    out = home_list.shorten(quoted, 100)
    assert out.endswith("...'") and out.count("'") == 2 and "transportation" not in out
    one_clause = "Thesis fit is high: only the legal name contains 'vessel' and nothing else is on file about the company at all."
    out = home_list.shorten(one_clause, 60)
    assert out.endswith("...") and len(out) <= 63 and one_clause.startswith(out[:-3]) and one_clause[len(out) - 3] == " "
    assert home_list.shorten("", 50) is None and home_list.shorten(None, 50) is None


def test_the_reason_is_printed_visibly_on_each_row(client):
    html = client.get("/").text
    rows = re.findall(r'<li id="row-[^"]+".*?</li>', html, flags=re.S)
    assert len(rows) >= 20
    for li in rows:
        m = re.search(r'<span class="hc-reason"[^>]*>(.*?)</span></span>', li, flags=re.S)      # the reason, then the closing of the name block
        assert m and len(text_of(m.group(1))) > 15, li[:200]
    # visible text, not a tooltip: the reason is element text, so a phone shows it
    assert "hc-reason" in (ROOT / "radar" / "static" / "filters.css").read_text() + (ROOT / "radar" / "static" / "home_c.css").read_text()


def test_the_list_states_its_sort_order_above_it(client):
    html = client.get("/").text
    sort = html.index('id="hc-sort"')
    assert sort < html.index('<ol class="hc-rows">')
    line = text_of(re.search(r'<[a-z]+ [^>]*id="hc-sort".*?</(?:p|details)>', html, flags=re.S).group(0))
    assert line.startswith("Sorted by verdict") and "strongest first" in line
    for v in home_list.VERDICT_ORDER:
        assert v.capitalize() in line, v
    new = text_of(re.search(r'<[a-z]+ [^>]*id="hc-sort".*?</(?:p|details)>', client.get("/?group=new").text, flags=re.S).group(0))
    assert "newest" in new.lower() and "public record" in new.lower()


def test_the_sort_sentence_is_true_of_the_rows(H):
    """The sentence names verdict first, then declared members, ocean impact level, confidence, business readiness, records, newest record;
    the rows of the first tab are in exactly that order."""
    order = home_list.VERDICT_ORDER
    conf = home_list.CONFIDENCE_ORDER

    def key(r):
        oi = r.get("ocean") or {}
        lv = oi.get("level")
        brl = ((r.get("criteria") or {}).get("brl") or {}).get("level")
        return (order.index(r["verdict"]) if r["verdict"] in order else len(order), 0 if r["group_tag"] in home_list.DECLARED_TAGS else 1,
                -(lv if lv is not None else -1), conf.index(oi["confidence"]) if oi.get("confidence") in conf else len(conf),
                -(brl if brl is not None else -1), -len(r["signals"]))
    keys = [key(r) for r in H["rows"]]
    assert keys == sorted(keys)
    text = home_list.sort_text("all")
    pos = [text.index(w) for w in ("verdict", "declared", "ocean impact", "confidence", "business readiness", "public records", "newest")]
    assert pos == sorted(pos)
    new = [r for g in H["groups"] if g[0] == "new" for r in g[2]]
    assert [r["latest"] or "" for r in new] == sorted([r["latest"] or "" for r in new], reverse=True)


# ---- 2. the sector the verdict is read against -------------------------------------------------------------------------------------------
def test_company_page_names_the_sector_it_is_read_against(client):
    html = client.get("/c/2962040-6").text
    m = re.search(r'<p class="cc-sector" id="cc-sector">(.*?)</p>', html, flags=re.S)
    assert m, "the company page prints its sector line"
    line = text_of(m.group(1))
    assert "Blue economy, Finland and Nordics" in line and "Redstone Blue" not in line
    assert html.index('id="cc-sector"') < html.index('id="why-this-verdict"')
    assert "?thesis=" not in m.group(1), "the default sector offers no switch to itself"


def test_a_company_of_another_sector_names_that_sector_and_links_back_when_the_default_holds_it(client, monkeypatch):
    from radar.routes import method
    html = client.get(f"/c/{HEALTH_ONLY}").text
    line = text_of(re.search(r'<p class="cc-sector" id="cc-sector">(.*?)</p>', html, flags=re.S).group(1))
    assert "Health technology, Turku region" in line and "default" not in line.lower()      # the default sector holds no such company: no useless link
    monkeypatch.setattr(method, "_held_by", lambda th, key: True)
    html = client.get(f"/c/{HEALTH_ONLY}").text
    m = re.search(r'<p class="cc-sector" id="cc-sector">(.*?)</p>', html, flags=re.S)
    assert f'href="/c/{HEALTH_ONLY}?thesis=redstone_apelago_blue"' in m.group(1)
    assert "Blue economy, Finland and Nordics" in text_of(m.group(1)) and "default" in text_of(m.group(1)).lower()


def test_sector_reading_unit(monkeypatch):
    from radar.routes import method
    th = thesis_mod.load()
    r = method.sector_reading(th, "2962040-6")
    assert r["is_default"] and r["title"] == "Blue economy, Finland and Nordics" and r["switch_href"] is None
    other = thesis_mod.load(thesis_mod.resolve("baltic_blue"))
    monkeypatch.setattr(method, "_held_by", lambda t, k: True)
    r = method.sector_reading(other, "2962040-6")
    assert not r["is_default"] and r["title"] == "Blue economy, Baltic Sea region" and r["switch_href"] == "/c/2962040-6?thesis=redstone_apelago_blue"


# ---- 3. the Ask Aava button never covers an answer ---------------------------------------------------------------------------------------
def test_phone_css_moves_the_ask_button_off_the_answer_card():
    css = (ROOT / "radar" / "static" / "site.css").read_text() + (ROOT / "radar" / "static" / "askbar.css").read_text()
    m = re.search(r"@media \(max-width: 639px\) \{[^@]*?\.ask-card:not\(\[hidden\]\)[^{]*\.aava-fab\s*\{[^}]*display:\s*none", css, flags=re.S)
    assert m, "while the answer card is open on a phone the floating button steps aside"
    assert re.search(r"body:has\(\.aava-fab\) \.foot\s*\{[^}]*padding-bottom", css), "the page keeps room under its last line for the button"


@pytest.fixture()
def live_server(monkeypatch):
    import socket
    import subprocess
    import sys
    import time
    import urllib.request
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    import os
    env = {**os.environ, "RADAR_DATA_DIR": str(SNAP), "RADAR_NO_WARM": ""}
    env.pop("RADAR_DB", None)
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        for _ in range(120):      # the grouped home list is built in the background after start; the bar is part of it
            try:
                if b'id="ask-q"' in urllib.request.urlopen(f"http://127.0.0.1:{port}/?demo=1", timeout=5).read():
                    break
            except Exception:
                pass
            time.sleep(0.5)
        yield f"http://127.0.0.1:{port}"
    finally:
        p.terminate()
        p.wait(timeout=10)


def test_at_390_the_ask_button_does_not_cover_the_source_link(live_server):
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"no browser: {e}")
        page = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True).new_page()
        page.goto(live_server + "/?demo=1&thesis=redstone_apelago_blue")
        page.wait_for_selector("#ask-q")
        page.wait_for_timeout(500)
        page.fill("#ask-q", "Tell me about Viva Jets")
        page.keyboard.press("Enter")
        page.wait_for_selector(".ask-src", timeout=15000)
        page.wait_for_timeout(1200)
        fab = page.query_selector(".aava-fab")
        fab_box = fab.bounding_box() if fab and fab.is_visible() else None
        for a in page.query_selector_all(".ask-card a"):
            b = a.bounding_box()
            if fab_box and b:
                apart = (b["x"] + b["width"] <= fab_box["x"] or fab_box["x"] + fab_box["width"] <= b["x"]
                         or b["y"] + b["height"] <= fab_box["y"] or fab_box["y"] + fab_box["height"] <= b["y"])
                assert apart, (a.inner_text(), b, fab_box)
        browser.close()


# ---- 4. numbers and links that agree ---------------------------------------------------------------------------------------------------
def test_one_function_counts_the_first_seen_companies(H):
    th = thesis_mod.load()
    conn = store.open_db(thesis=th)
    try:
        c = home_list.window_counts(conn, th)
    finally:
        conn.close()
    assert c["first_seen"] == H["headline"]["new"]
    assert c["on_list"] == len(H["rows"]) and c["main"] + c["declared"] == c["on_list"]
    assert c["window_days"] == 90


def test_method_names_both_measures(client, H):
    t = text_of(client.get("/method").text)
    n = H["headline"]["new"]
    assert f"{n} of the {len(H['rows'])} companies on the home list were first seen in the last 90 days" in t
    assert "first dated public record" in t
    th = thesis_mod.load()
    conn = store.open_db(thesis=th)
    try:
        main = store.feed_counts(conn, th)["main"]
    finally:
        conn.close()
    assert f"{main} companies in the main list" in t and "new companies in the main list" not in t


def test_the_home_count_line_and_the_new_tab_agree(client, H):
    html = client.get("/").text
    n = H["headline"]["new"]
    assert f"{n} companies first seen in the last 90 days" in text_of(html)
    tabs = re.search(r'New this quarter <span>(\d+)</span>', html)
    assert tabs and int(tabs.group(1)) == n


def test_the_trl_example_means_what_the_filter_does():
    """An example question must name the level the filter's bands really start at: 'TRL above 4' selected the 4 to 6 band, which holds TRL 4."""
    from radar import ask
    for path in sorted((ROOT / "config").glob("thesis*.yaml")):
        th = thesis_mod.load(path)
        for q in (th.get("ask") or {}).get("examples") or []:
            m = re.search(r"\b(TRL|BRL)\s+(above|at least|below|at most)\s+([1-9])\b", q)
            if not m:
                continue
            res = ask.parse_filters(q, th, ask.config(th))
            lows = [int(v.split("-")[0]) for v in (res["sel"].get(m.group(1).lower()) or [])]
            n, op = int(m.group(3)), m.group(2)
            if op == "above":
                assert min(lows) > n, (path.name, q, lows)
            elif op == "at least":
                assert min(lows) == n, (path.name, q, lows)


def test_the_menu_new_this_quarter_opens_the_new_tab(client):
    html = client.get("/").text
    assert '<a href="/">New this quarter</a>' not in html
    assert html.count('href="/?group=new">New this quarter</a>') >= 2           # the menu sheet and the footer
    new = client.get("/?group=new").text
    assert re.search(r'aria-current="true">(?:<kbd[^>]*>\d</kbd>)?New this quarter', new) or 'aria-current="true"' in re.search(r'<a [^>]*href="/\?group=new"[^>]*data-key="\d"[^>]*>', new).group(0)
    assert 'aria-current="page">New this quarter' in new


def test_how_redirects_to_the_rules_and_nothing_links_to_it(client):
    r = client.get("/how", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308) and r.headers["location"] == "/method"
    assert client.get("/how?thesis=health_tech_turku", follow_redirects=False).headers["location"] == "/method?thesis=health_tech_turku"
    for path in ("/", "/method", "/radar", "/backtest", f"/c/{HEALTH_ONLY}"):
        assert 'href="/how"' not in client.get(path).text, path
    assert "read this first" not in client.get("/method").text


def test_backtest_and_radar_agree_on_what_counts(client):
    bt = client.get("/backtest").text
    assert "No counted signal" in bt and "No public signal" not in bt and "no public signal" not in text_of(bt).replace("no public signal since", "")
    lanes = re.findall(r'<g class="bt-lane blank".*?</g>', bt, flags=re.S)
    assert lanes
    for lane in lanes:
        assert "no counted signal" in lane
    taikoa = re.search(r'<g class="bt-lane blank" data-company="3380111-1".*?</g>', bt, flags=re.S).group(0)
    assert re.search(r"no counted signal, \d+ records? on file", taikoa)
    assert "does not mean there is no record" in text_of(bt)
    radar = text_of(client.get("/radar").text)
    assert "no counted signal" in radar and "/backtest" in client.get("/radar").text
    assert "before the thesis rule" in radar


def test_earliness_words_say_counted_not_public(H):
    from radar import earliness
    th = thesis_mod.load()
    conn = store.open_db(thesis=th)
    try:
        res = earliness.backtest(conn, th)
    finally:
        conn.close()
    assert "no counted signal" in res["headline"] and "no public signal" not in res["headline"]
