"""Aava as a conversation: six answers per company page, one feed answer, the question list and the Next button.
Companies are the synthetic fixtures; nothing is fetched."""
import json
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import company_fixture as fx  # noqa: E402
from aava_rules import FEED_QUESTION, QUESTIONS, dirty  # noqa: E402

from radar import aava, db, emit  # noqa: E402

RICH, SPARSE = "9000001-1", "name:sparse"
KEYS = (RICH, SPARSE, "9000003-3", "9000004-4")
SEGMENT_KEYS = {"text", "target", "action", "source_url", "sha", "q"}


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "t.sqlite"
    conn = fx.build(path)
    for i, (k, d) in enumerate([("bf_funding", "2025-09-01"), ("public_contract", "2025-11-20")]):
        emit.emit_signal(conn, company_key=RICH, signal_type=k, date=d, source_url=f"https://example.test/{k}", confidence="high",
                         adapter="hilma", detail=f"Synthetic {k} record — with a long dash.")
    today = datetime.now(timezone.utc).date()
    for key, name, days in (("9000005-5", "Meri Fixture Oy", 3), ("9000006-6", "Laiva Fixture Oy", 5), ("9000007-7", "Vene Fixture Oy", 9),
                            ("9000008-8", "Satama Fixture Oy", 12)):
        day = (today - timedelta(days=days)).isoformat()
        emit.upsert_company(conn, company_key=key, name=name, y_tunnus=key, country="FI", founded=day,
                            industry_code="30110", industry_desc="Building of ships", source_url=fx.PRH + key)
        emit.emit_signal(conn, company_key=key, signal_type="register_entry", date=day, source_url=fx.PRH + key,
                         confidence="high", adapter="prh", detail="Registered.")
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def client(db_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(db_path))
    import app
    return TestClient(app.app)


def embedded(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="aava-data">(.*?)</script>', html, re.S)
    assert m, "no embedded Aava script"
    return json.loads(m.group(1))


def undeclare(db_path, *keys):
    """The fixtures are declared cohort companies, which now read PORTFOLIO SUPPORT (D65). These tests are about the entry decision a company
    outside the lists gets, so they take the cohort tag off first."""
    import sqlite3
    c = sqlite3.connect(db_path)
    c.executemany("UPDATE companies SET group_tag='feed' WHERE company_key=?", [(k,) for k in keys])
    c.commit()
    c.close()


def answers(client, key) -> dict[int, dict]:
    """{question number: its one segment}, from what the company page itself embeds."""
    data = embedded(client.get("/c/" + key).text)
    out = {}
    for group in aava.INTENTS:
        for s in data[group]:
            out[s["q"]] = s
    return out


def script(client, key, intent="brief"):
    r = client.get(f"/aava/script/{key}", params={"intent": intent})
    assert r.status_code == 200
    return r.json()


def ids(html):
    return set(re.findall(r'\bid="([^"]+)"', html))


def test_six_questions_in_the_asked_order_each_with_one_answer(client):
    assert [q[0] for q in aava.QUESTIONS] == [1, 2, 3, 4, 5, 6]
    assert [q[2] for q in aava.QUESTIONS] == list(QUESTIONS)
    assert [q[2] for q in aava.FEED_QUESTIONS] == [FEED_QUESTION]
    for key in KEYS:
        a = answers(client, key)
        assert sorted(a) == [1, 2, 3, 4, 5, 6], key
        for q, s in a.items():
            assert set(s) >= SEGMENT_KEYS and s["q"] == q


def test_every_answer_is_short_clean_and_points_at_the_page(client):
    for key in KEYS:
        html = client.get("/c/" + key).text
        have = ids(html)
        for q, s in answers(client, key).items():
            assert 0 < len(s["text"]) <= aava.MAX_ANSWER, (key, q, len(s["text"]))
            assert not dirty(s["text"]), (key, q, dirty(s["text"]), s["text"])
            assert s["target"] in have, (key, q, s["target"])
            assert s["action"] in aava.ACTIONS
            assert s["sha"] == aava.text_sha(s["text"])
            assert s["source_url"] is None or s["source_url"].startswith("https://")


def test_old_intent_names_map_to_the_questions(client):
    expected = {"brief": [1], "why": [2, 3], "meet": [4], "talk": [4], "next": [5], "missing": [6]}
    assert set(expected) == set(aava.INTENTS)
    data = embedded(client.get("/c/" + RICH).text)
    for intent, qs in expected.items():
        assert [s["q"] for s in data[intent]] == qs, intent
        assert [s["q"] for s in script(client, RICH, intent)["segments"]] == qs, intent
    assert client.get(f"/aava/script/{RICH}", params={"intent": "x"}).status_code == 400
    assert client.get("/aava/script/nope-1").status_code == 404


def test_the_first_answer_opens_with_the_opinion_and_gives_the_facts(client, db_path):
    undeclare(db_path, RICH)
    t = answers(client, RICH)[1]["text"]
    assert t.startswith("Based on what the radar holds on Synthetic Rich Oy, I think ")
    assert "synthetic shipbuilding" in t and "since 2025" in t          # line of business and the registration year
    assert re.search(r"\b\d{1,2} [A-Z][a-z]+ 2025\b", t) and " in a Finnish public procurement notice" in t   # a dated record, its source family in words


def test_a_watchlist_company_reads_honestly(client, db_path):
    undeclare(db_path, SPARSE)
    t = answers(client, SPARSE)[1]["text"]
    assert "I think we should watch, not call, and here is why:" in t
    assert "no public evidence yet for" in t and "No public record of its line of business or of when it was registered." in t
    assert "The radar holds no dated signal for it yet." in t
    assert "good accelerator" not in t and "deserves" not in t
    nxt = answers(client, SPARSE)[5]["text"]
    assert nxt.startswith("No call yet.") and "Watch: not enough public evidence" not in nxt


def test_the_score_answer_has_the_verdict_the_bands_the_rule_and_no_number(client, db_path):
    undeclare(db_path, RICH)
    import sqlite3
    c = sqlite3.connect(db_path)    # technology High from a BlueInvest profile's stated TRL: a public contract sets no TRL since D84
    c.execute("INSERT INTO blueinvest_profiles (profile_id, company_key, title, trl, url, fetched_at) VALUES "
              "('p-rich', ?, 'Rich Fixture', 8, 'https://example.test/bi/rich', '2026-10-16T00:00:00Z')", (RICH,))
    c.commit()
    c.close()
    t = answers(client, RICH)[2]["text"]
    assert t.startswith("On ocean impact")
    assert "The verdict is partner introduction" in t
    assert "Thesis fit is medium and business readiness is medium." in t     # outside the lists the industry code alone gives at most a Medium fit (D66)
    assert "The rule that fired is a condition rule of the team's decision table: technology high, business low or medium." in t
    assert "a rule the code checks, not my mood" in t and "no single number by design" in t
    assert not re.search(r"\d", re.sub(r"level \d of 9", "", t))                                          # never invents a number
    assert "dataset match" not in t


def _memo(ocean=None, impact="Medium", **rec):
    r = {"decision": "WATCHLIST", "row_id": None, "table_action": None, "kind": None, "note": "more public evidence needed: Investment readiness",
         "because_labels": [{"label": "Ocean impact", "band": impact}, {"label": "Business readiness", "band": "Low"},
                            {"label": "Investment readiness", "band": "unknown"}, {"label": "Thesis fit", "band": "Medium"}],
         "needs": ["Investment readiness"], **rec}
    m = {"company_key": "x", "name": "X", "recommendation": r, "why": [], "risks": [], "actions": [], "levels": {}}
    if ocean is not None:
        m["ocean_impact"] = ocean
    return m


def test_the_score_answer_leads_with_the_ocean_impact_the_memo_carries():
    t = aava.score(_memo({"area": "Ocean energy and propulsion", "level": 4, "band": "Medium", "confidence": "medium"}))["text"]
    assert t.startswith("On ocean impact the report puts it in ocean energy and propulsion, at level 4 of 9, with medium confidence.")
    assert "The verdict is watchlist." in t and "Thesis fit is medium and business readiness is low." in t
    assert "No row or rule of the table matched, because the code still needs public evidence for investment readiness." in t
    assert len(t) <= aava.MAX_ANSWER and not dirty(t)
    no_level = aava.score(_memo({"area_label": "Aquaculture", "level": None, "band": "High", "confidence": "low"}))["text"]
    assert no_level.startswith("On ocean impact the report puts it in aquaculture, at the high band, with no level on record, with low confidence.")
    assert "of 9" not in no_level
    assert "of 9" not in aava.score(_memo())["text"] and aava.score(_memo())["text"].startswith("On ocean impact the report puts it at the medium band.")


def test_the_verdict_is_said_with_the_rule_that_fired_never_a_bare_id():
    fb = aava.score(_memo(decision="ACCELERATOR", kind="fallback", row_id="c2", table_action="Accept into accelerator and provide mentoring",
                          impact="Medium, implied by sector",
                          note="Impact not yet measured; thesis fit is High, so impact is read as Medium, implied by the sector, and fallback c2 of the decision rules applies."))["text"]
    assert "The rule that fired is the table's High-fit rule: impact not yet measured, and thesis fit is high." in fb   # the page's chip names it so (D67)
    assert "The verdict is accelerator: accept into accelerator and provide mentoring." in fb
    assert not re.search(r"\bc2\b", fb) and not dirty(fb)


def test_missing_facts_are_spoken_as_missing(client, db_path):
    undeclare(db_path, SPARSE)
    a = answers(client, SPARSE)
    assert "No public record of its line of business or of when it was registered." in a[1]["text"]
    assert "nothing here is verified in an official register" in a[3]["text"]
    assert "no evidence yet for" in a[6]["text"]
    assert "I have nobody to point you to" in a[4]["text"]               # outside the lists this fixture has no counterpart match
    nxt = {"investors": [{"name": "Fixture Fund", "kind": "investor", "score": 3, "reason": None, "source_url": "https://example.test/f"}]}
    assert "I would not take a meeting yet." in aava.meet(nxt, _memo())["text"]
    assert "I have nobody to point you to" in answers(client, "9000003-3")[4]["text"]
    bare = aava.company_groups({"name": "Bare", "company_key": "k"}, [], thesis=None)
    assert all("None" not in s["text"] for g in bare.values() for s in g)
    assert bare["why"][0]["text"] == "There is no report for this company in this radar, so there is no verdict or score for me to read."


def test_dates_and_numbers_are_on_the_page(client):
    months = {m: i + 1 for i, m in enumerate(aava.MONTHS)}
    for key in (RICH, SPARSE, "9000003-3"):
        page = client.get("/c/" + key).text
        page_numbers = {int(n) for n in re.findall(r"\d+", re.sub(r"<[^>]+>", " ", page))}
        for s in answers(client, key).values():
            spoken = re.sub(r"\b\d{1,2} (%s) \d{4}\b" % "|".join(months), "", s["text"])
            for d, mon, y in re.findall(r"\b(\d{1,2}) (%s) (\d{4})\b" % "|".join(months), s["text"]):
                assert f"{y}-{months[mon]:02d}-{int(d):02d}" in page, (key, s["text"])
            for n in re.findall(r"\d+", spoken):
                assert int(n) in page_numbers or int(n) == 9, (key, n, s["text"])


def test_clean_and_dates():
    assert aava.clean("a — b–c") == "a, b, c"
    assert aava.say_date("2025-06-13") == "13 June 2025" and aava.say_date("2025-06-13", True) == "2025, year only"
    assert aava.say_date(None) is None and aava.say_date("2025-13-45") is None


# ---- the feed reader --------------------------------------------------------------------------------------------------------------
def test_the_feed_answer_names_four_or_five_companies_with_dates_and_no_codes(client):
    segs = client.get("/aava/feed").json()["segments"]
    html = client.get("/").text
    assert 4 <= len(segs) <= 5
    assert sum(len(s["text"]) for s in segs) <= aava.MAX_FEED and len(" ".join(s["text"] for s in segs)) <= aava.MAX_FEED
    for s in segs:
        assert s["target"] in ids(html) and s["source_url"] and s["q"] == 1 and s["sha"] == aava.text_sha(s["text"])
        assert re.search(r"\b\d{1,2} [A-Z][a-z]+ \d{4}\b", s["text"]) and " in building of ships" in s["text"]
        assert not dirty(s["text"]), s["text"]
    assert segs[0]["text"].startswith("Here is what is new this week.")
    assert embedded(html)["brief"] == segs


def _row(i, day, desc="Building of ships"):
    return {"company_key": f"900000{i}-{i}", "name": f"Fixture {i} Oy", "industry_desc": desc, "signal_type": "first_sales", "date": day,
            "source_url": "https://example.test/x"}


def test_the_feed_answer_stays_under_the_limit_and_says_when_nothing_is_new():
    rows = [_row(i, f"2026-10-{16 - i:02d}", "Manufacture of other electrical equipment and of installation of industrial machinery") for i in range(6)]
    segs = aava.feed_script(rows, today="2026-10-17")["segments"]
    assert 4 <= len(segs) <= 5 and len(" ".join(s["text"] for s in segs)) <= aava.MAX_FEED
    assert segs[0]["text"].startswith("Here is what is new this week. Fixture 0 Oy, in manufacture of other electrical equipment")
    assert "first sales on 16 October 2026" in segs[0]["text"]
    old = aava.feed_script([_row(1, "2026-09-18"), _row(2, "2026-09-17")], today="2026-10-17")["segments"]
    assert old[0]["text"].startswith("Here are the newest records on the radar, the latest from 18 September 2026.")
    none_desc = aava.feed_script([_row(1, "2026-10-16", desc="")], today="2026-10-17")["segments"][0]["text"]
    assert "with no line of business on record" in none_desc


def test_empty_feed_is_spoken_as_empty():
    assert aava.feed_script([])["segments"][0]["text"] == "No public record in this window."


# ---- browser: skipped when playwright or chromium is missing ------------------------------------------------------------------------
@pytest.fixture()
def live_url(db_path):
    pytest.importorskip("playwright.sync_api")
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
        page.goto(f"{live_url}/c/{RICH}?demo=1")
        assert page.locator("#aava-open").inner_text() == "Ask Aava"
        assert page.locator("#aava-open").bounding_box()["height"] >= 44
        page.click("#aava-open")
        assert page.locator("#aava-sheet").is_visible()
        page.click("[data-q='1']")
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


def test_the_six_questions_show_in_order_as_large_tappable_lines(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 844})
    try:
        page.goto(f"{live_url}/c/{RICH}?demo=1")
        page.click("#aava-open")
        lines = page.locator(".aava-q")
        assert lines.count() == 6
        assert [lines.nth(i).locator(".aava-qt").inner_text() for i in range(6)] == list(QUESTIONS)
        assert [lines.nth(i).get_attribute("data-q") for i in range(6)] == ["1", "2", "3", "4", "5", "6"]
        boxes = [lines.nth(i).bounding_box() for i in range(6)]
        assert all(b["height"] >= 44 for b in boxes) and all(boxes[i]["y"] < boxes[i + 1]["y"] for i in range(5))
        assert page.locator("#aava-next").inner_text() == "Next"
    finally:
        browser.close()
        p.stop()


def test_next_button_space_and_right_arrow_walk_the_questions_and_a_tap_plays_that_one(live_url, client):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 1440, "height": 900})
    try:
        a = answers(client, RICH)
        page.goto(f"{live_url}/c/{RICH}?demo=1")
        page.click("#aava-open")
        now = lambda: page.eval_on_selector(".aava-q.is-now", "e => e.dataset.q")  # noqa: E731
        caption = lambda: page.locator("#aava-caption").inner_text()  # noqa: E731
        assert page.locator(".aava-q.is-now").count() == 0
        page.click("#aava-next")                                  # nothing asked yet: Next plays the first question
        assert now() == "1" and caption() == a[1]["text"]
        page.keyboard.press("Space")
        assert now() == "2" and caption() == a[2]["text"]
        page.keyboard.press("ArrowRight")
        assert now() == "3" and caption() == a[3]["text"]
        assert page.locator(".aava-q.is-done").count() == 2
        page.click("[data-q='5']")                                # a tap plays that question
        assert now() == "5" and caption() == a[5]["text"]
        page.click("#aava-next")
        assert now() == "6" and caption() == a[6]["text"] and page.locator("#aava-next").is_disabled()
        page.keyboard.press("Space")                              # the last one: nothing further
        assert now() == "6" and caption() == a[6]["text"]
        page.click("[data-q='2']")
        assert now() == "2" and not page.locator("#aava-next").is_disabled()
        page.click("#aava-pause")                                 # Next while paused: the new answer runs and the button says Pause again
        assert page.locator("#aava-pause").inner_text() == "Resume"
        page.click("#aava-next")
        assert now() == "3" and caption() == a[3]["text"] and page.locator("#aava-pause").inner_text() == "Pause"
        page.click("#aava-close")
        page.click("#aava-open")
        assert page.locator(".aava-q.is-now").count() == 0        # a fresh start
    finally:
        browser.close()
        p.stop()


def test_next_and_pause_are_visible_and_the_button_clears_the_tab_bar(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    for w, h in ((390, 844), (1440, 900)):
        p, browser, page = _page(sync_api, {"width": w, "height": h})
        try:
            page.goto(f"{live_url}/c/{RICH}?demo=1")
            bar = page.locator(".c-tabbar")
            fab = page.locator("#aava-open").bounding_box()
            if w < 640:
                assert bar.is_visible() and fab["y"] + fab["height"] <= bar.bounding_box()["y"] + 1, (w, fab)   # the button never covers the tab bar
            page.click("#aava-open")
            page.click("#aava-next")
            assert not page.locator("#aava-pause").is_disabled()
            for sel in ("#aava-next", "#aava-pause"):
                assert page.locator(sel).is_visible(), (w, sel)
                b = page.locator(sel).bounding_box()
                assert b["x"] >= 0 and b["y"] >= 0 and b["x"] + b["width"] <= w and b["y"] + b["height"] <= h, (w, sel, b)
                if w < 640:
                    assert b["y"] + b["height"] <= bar.bounding_box()["y"], (w, sel, b)                    # and nor does the open sheet
            sheet = page.locator("#aava-sheet").bounding_box()
            assert sheet["y"] >= 0 and sheet["y"] + sheet["height"] <= h
        finally:
            browser.close()
            p.stop()


# ---- the demo flag: Aava shows only with demo=1 (or the stored aava_demo = "1"); the public site shows nothing -----------------
def test_markup_ships_hidden_and_the_flag_check_precedes_it(client):
    for url in (f"/c/{RICH}", "/"):
        html = client.get(url).text
        assert re.search(r'<div id="aava" class="aava" hidden\b', html), url
        assert "/static/aava.js" not in html.split('<div id="aava"')[0], url
        assert html.index("aava_demo") < html.index('<div id="aava"'), url  # the inline check sits ahead of the markup: no flash


def test_the_page_lists_the_six_questions_in_order(client):
    html = client.get(f"/c/{RICH}?demo=1").text
    at = [html.index(q.replace("'", "&#39;")) for q in QUESTIONS]
    assert at == sorted(at) and len(set(at)) == 6
    assert [int(n) for n in re.findall(r'class="aava-btn aava-q" type="button" data-q="(\d)"', html)] == [1, 2, 3, 4, 5, 6]
    assert 'id="aava-next"' in html
    feed = client.get("/?demo=1").text
    assert FEED_QUESTION in feed and re.findall(r'data-q="(\d)"', feed) == ["1"]


def test_without_the_flag_no_aava_is_visible_and_its_script_is_never_requested(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        seen = []
        page.on("request", lambda r: seen.append(r.url))
        for url in (f"/c/{RICH}", "/", f"/c/{RICH}?demo=0"):
            page.goto(live_url + url)
            assert not page.locator("#aava-open").is_visible(), url
            assert not page.locator("#aava-sheet").is_visible(), url
            assert not page.locator("#aava-caption").is_visible(), url
        assert not [u for u in seen if "aava" in u.lower()], seen
    finally:
        browser.close()
        p.stop()


def test_demo_one_is_remembered_on_the_device_and_demo_zero_clears_it(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        page.goto(f"{live_url}/c/{RICH}")
        assert not page.locator("#aava-open").is_visible()
        page.goto(f"{live_url}/c/{RICH}?demo=1")
        assert page.locator("#aava-open").is_visible()
        assert page.evaluate("localStorage.getItem('aava_demo')") == "1"
        page.goto(f"{live_url}/c/{RICH}")  # plain URL, same context: localStorage carries it
        assert page.locator("#aava-open").is_visible()
        page.goto(f"{live_url}/")  # and the feed
        assert page.locator("#aava-open").is_visible()
        page.click("#aava-open")
        assert page.locator("#aava-sheet").is_visible()  # the script loaded and works on a flagged plain URL
        page.goto(f"{live_url}/c/{RICH}?demo=0")
        assert not page.locator("#aava-open").is_visible()
        assert page.evaluate("localStorage.getItem('aava_demo')") is None
        page.goto(f"{live_url}/c/{RICH}")
        assert not page.locator("#aava-open").is_visible()
    finally:
        browser.close()
        p.stop()
