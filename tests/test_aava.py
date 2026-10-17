"""Aava narration scripts and the front end. Companies are the synthetic fixtures; nothing is fetched."""
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import company_fixture as fx  # noqa: E402

from radar import aava, db, emit  # noqa: E402

RICH, SPARSE = "9000001-1", "name:sparse"


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "t.sqlite"
    conn = fx.build(path)
    for i, (k, d) in enumerate([("bf_funding", "2025-09-01"), ("public_contract", "2025-11-20")]):
        emit.emit_signal(conn, company_key=RICH, signal_type=k, date=d, source_url=f"https://example.test/{k}", confidence="high",
                         adapter="hilma", detail=f"Synthetic {k} record \u2014 with a long dash.")
    emit.upsert_company(conn, company_key="9000005-5", name="Meri Fixture Oy", y_tunnus="9000005-5", country="FI", founded="2026-08-01",
                        industry_code="30110", industry_desc="Building of ships", source_url=fx.PRH + "9000005-5")
    emit.emit_signal(conn, company_key="9000005-5", signal_type="register_entry", date="2026-09-01", source_url=fx.PRH + "9000005-5",
                     confidence="high", adapter="prh", detail="Registered.")
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def client(db_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(db_path))
    import app
    return TestClient(app.app)


def script(client, key, intent="brief"):
    r = client.get(f"/aava/script/{key}", params={"intent": intent})
    assert r.status_code == 200
    return r.json()


def ids(html):
    return set(re.findall(r'\bid="([^"]+)"', html))


def test_order_of_a_rich_company(client):
    segs = script(client, RICH)["segments"]
    targets = [s["target"] for s in segs]
    assert targets[0] == "aava-who"
    sig_order = [t for t in targets if t.startswith("aava-sig-")]
    assert len(sig_order) == 4
    first = targets.index("signals")
    assert targets.index("aava-who") < first < targets.index("q1") < targets.index("q2") < targets.index("q3") < targets.index("q4")
    # oldest first: the register entry (2025-06-13) is read before the EU project (2026-03-01)
    texts = [s["text"] for s in segs if s["target"].startswith("aava-sig-")]
    assert "13 June 2025" in texts[0] and "1 March 2026" in texts[-1]
    assert segs[-1]["action"] == "none" and segs[-2]["target"] in ("q4", "memo")  # question four ends with the memo's verdict
    assert any(s["action"] == "draw_timeline" and len(s["points"]) == 4 for s in segs)


def test_levels_use_fill_level_with_value_and_max(client):
    segs = script(client, RICH)["segments"]
    lv = [s for s in segs if s["action"] == "fill_level"]
    assert lv and all(s["max"] == 9 and 1 <= s["value"] <= 9 and "level" in s["text"] for s in lv)


def test_missing_facts_are_spoken_as_missing(client):
    segs = script(client, SPARSE)["segments"]
    t = " ".join(s["text"] for s in segs)
    assert "No public record of its founding date." in t
    assert "No public record of its line of business." in t
    assert "No public record of its register status." in t
    assert "No public record of any signal" in t
    assert t.count("no public record of a level") == 3 and "no public record of a category" in t.lower()
    assert "No public record of a sector match" in t
    assert not any(s["action"] == "draw_timeline" for s in segs)


def test_every_target_exists_in_the_rendered_page(client):
    for key in (RICH, SPARSE, "9000003-3", "9000004-4"):
        html = client.get("/c/" + key).text
        have = ids(html)
        for s in script(client, key)["segments"]:
            assert s["target"] in have, (key, s["target"])
            assert s["action"] in aava.ACTIONS
    assert "id=\"aava\"" in html and "Ask Aava" in html


def test_no_long_dash_and_numbers_are_on_the_page(client):
    months = {m: i + 1 for i, m in enumerate(aava.MONTHS)}
    for key in (RICH, SPARSE, "9000003-3"):
        page = client.get("/c/" + key).text
        page_numbers = {int(n) for n in re.findall(r"\d+", re.sub(r"<[^>]+>", " ", page))}
        for s in script(client, key)["segments"]:
            assert "\u2014" not in s["text"] and "\u2013" not in s["text"]
            spoken = re.sub(r"\b\d{1,2} (%s) \d{4}\b" % "|".join(months), lambda m: "", s["text"])  # dates are checked below
            for d, mon, y in re.findall(r"\b(\d{1,2}) (%s) (\d{4})\b" % "|".join(months), s["text"]):
                assert f"{y}-{months[mon]:02d}-{int(d):02d}" in page, (key, s["text"])
            for n in re.findall(r"\d+", spoken):
                assert int(n) in page_numbers or int(n) == 9, (key, n, s["text"])  # 9 is the printed "of 9" scale


def test_source_urls_are_links(client):
    for s in script(client, RICH)["segments"]:
        assert s["source_url"] is None or s["source_url"].startswith("https://")
    seg = [s for s in script(client, RICH)["segments"] if s["target"].startswith("aava-sig-")][0]
    assert seg["source_url"]


def test_intents_and_errors(client):
    nxt = [s["target"] for s in script(client, RICH, "next")["segments"]]
    assert nxt[0] == "q4" and set(nxt) <= {"q4", "memo"}  # question four, then the memo's verdict and actions
    assert {s["target"] for s in script(client, RICH, "talk")["segments"]} == {"q3"}
    for intent in ("why", "meet", "missing"):
        assert script(client, RICH, intent)["segments"]
    assert client.get(f"/aava/script/{RICH}", params={"intent": "x"}).status_code == 400
    assert client.get("/aava/script/nope-1").status_code == 404


def test_feed_script_targets_exist_and_carry_dates_and_sources(client):
    data = client.get("/aava/feed").json()
    segs = data["segments"]
    html = client.get("/").text
    assert 1 <= len(segs) <= 5
    for s in segs:
        assert s["target"] in ids(html) and s["source_url"]
        assert re.search(r"\d{1,2} [A-Z][a-z]+ \d{4}", s["text"]) and "Source:" in s["text"]
    assert "Ask Aava what is new" in html


def test_empty_feed_is_spoken_as_empty():
    assert aava.feed_script([])["segments"][0]["text"] == "No public record in this window."


def test_clean_and_dates():
    assert aava.clean("a \u2014 b\u2013c") == "a, b, c"
    assert aava.say_date("2025-06-13") == "13 June 2025" and aava.say_date("2025-06-13", True) == "2025, year only"
    assert aava.say_date(None) is None and aava.say_date("2025-13-45") is None


# ---- browser smoke: skipped when playwright or chromium is missing --------------------------------------------

@pytest.fixture()
def live_url(db_path):
    sync = pytest.importorskip("playwright.sync_api")
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=Path(__file__).resolve().parent.parent, env={**__import__("os").environ, "RADAR_DB": str(db_path)},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(5)


def _page(sync_api, viewport):
    p = sync_api.sync_playwright().start()
    browser = None
    for kwargs in ({}, {"executable_path": "/opt/pw-browsers/chromium"}):  # the second is the cloud image's pinned binary
        try:
            browser = p.chromium.launch(**kwargs)
            break
        except Exception as e:  # no browser binary of this kind on this machine
            err = e
    if browser is None:
        p.stop()
        pytest.skip(f"chromium unavailable: {err}")
    return p, browser, browser.new_page(viewport=viewport)


def test_tap_caption_highlight_and_stop(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        page.goto(f"{live_url}/c/{RICH}")
        assert page.locator("#aava-open").inner_text() == "Ask Aava"
        assert page.locator("#aava-open").bounding_box()["height"] >= 44
        page.click("#aava-open")
        assert page.locator("#aava-sheet").is_visible()
        page.click("[data-intent=brief]")
        page.wait_for_function("document.getElementById('aava-caption').textContent.includes('Synthetic Rich Oy')")
        page.wait_for_selector(".aava-hl")
        assert page.locator(".aava-hl").count() == 1
        page.click("#aava-stop")
        assert page.locator(".aava-hl").count() == 0
        assert "Stopped" in page.locator("#aava-caption").inner_text()
        time.sleep(2.5)  # nothing advances after stop
        assert "Stopped" in page.locator("#aava-caption").inner_text()
    finally:
        browser.close()
        p.stop()
