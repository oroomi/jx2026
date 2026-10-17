"""Aava questions 03 and 04 wired to the real rows (matching.who_comes_next, matching.next_step, memo.build), the question menu,
and speech that starts on the tap (the scripts are embedded in the page, no request after the tap)."""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import aava, db, thesis
from radar.adapters import ecosystem

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from aava_rules import dirty  # noqa: E402

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"
VIVA, ARCTIC = "2962040-6", "3166759-6"


@pytest.fixture()
def snap(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    th = thesis.load()
    conn = db.connect(thesis.db_path(th))
    try:
        ecosystem.run(conn, th)
        conn.commit()
    except Exception:
        pytest.skip("ecosystem dataset not available")
    conn.close()
    return tmp_path


@pytest.fixture()
def client(snap):
    import app
    return TestClient(app.app)


def _embedded(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="aava-data">(.*?)</script>', html, re.S)
    assert m, "no embedded Aava script"
    return json.loads(m.group(1))


def _answers(key: str) -> dict[int, dict]:
    """{question number: segment} as the company page embeds them, from whichever store the environment points at."""
    from radar.routes import aava as page
    g = json.loads(str(page.company_json(key, thesis.load())))
    return {s["q"]: s for grp in aava.INTENTS for s in g[grp]}


@pytest.fixture(params=["snapshot", "live"])
def corpus(request, monkeypatch):
    """The two stores the answers are checked on: data/snapshot (a copy, as the page tests use it) and a copy of the live store when
    AAVA_LIVE_COPY names one (AAVA_LIVE_DATA_DIR, default the repo's data directory, is the data directory that goes with it)."""
    if request.param == "snapshot":
        request.getfixturevalue("snap")
        return "snapshot"
    live = os.environ.get("AAVA_LIVE_COPY")
    if not live or not Path(live).exists():
        pytest.skip("AAVA_LIVE_COPY is not set")
    monkeypatch.setenv("RADAR_DB", live)
    monkeypatch.setenv("RADAR_DATA_DIR", os.environ.get("AAVA_LIVE_DATA_DIR") or str(SNAP.parent))
    return "live"


def test_viva_jets_and_arctic_fry_answers_are_clean_short_and_in_order(corpus):
    for key in (VIVA, ARCTIC):
        a = _answers(key)
        assert sorted(a) == [1, 2, 3, 4, 5, 6], key
        for q, s in a.items():
            assert 0 < len(s["text"]) <= aava.MAX_ANSWER, (key, q, len(s["text"]))
            assert not dirty(s["text"]), (key, q, dirty(s["text"]), s["text"])
            assert s["sha"] == aava.text_sha(s["text"]) and s["target"] and s["action"] in aava.ACTIONS
            assert s["source_url"] is None or s["source_url"].startswith("http")
        assert a[1]["text"].startswith(f"Based on what the radar holds on {'Viva Jets Oy' if key == VIVA else 'Arctic Fry Oy'}, I think ")
        assert a[2]["text"].startswith("On ocean impact") and "no single number by design" in a[2]["text"]
        assert "not my mood" in a[2]["text"]


def test_arctic_fry_reads_as_a_company_to_watch_not_call(corpus):
    # D65: Arctic Fry is a declared cohort member, so it reads PORTFOLIO SUPPORT (was ACCELERATOR under D53): it is already inside the programme.
    a = _answers(ARCTIC)
    assert "I think it needs portfolio support, not an entry decision: already in A'Pelago's" in a[1]["text"] and "accelerator candidate" not in a[1]["text"]
    assert "The verdict is portfolio support" in a[2]["text"] and not a[5]["text"].startswith("No call yet.")
    assert "Watch: not enough public evidence" not in " ".join(s["text"] for s in a.values())


def test_the_feed_answer_is_clean_and_short_with_no_codes(corpus):
    from radar import aava_voice
    th, data = aava_voice.collect_feed(None)
    segs = data["brief"]
    assert 4 <= len(segs) <= 5 and len(" ".join(s["text"] for s in segs)) <= aava.MAX_FEED
    for s in segs:
        assert not dirty(s["text"]), s["text"]
        assert re.search(r"\b\d{1,2} [A-Z][a-z]+ \d{4}\b", s["text"]) and s["source_url"] and s["q"] == 1


def test_viva_jets_answers_have_the_verdict_and_a_named_organisation(client):
    from radar import matching, memo, store
    th = thesis.load()
    conn = store.open_db(thesis=th)
    m = memo.build(conn, th, VIVA)
    nxt = matching.who_comes_next(VIVA, th, 5, conn=conn)
    conn.close()
    names = [aava._spoken_name(r["name"]) for k in ("investors", "funding", "partners") for r in nxt[k]]   # D65: a member's next support is a pilot partner and a grant
    assert names, "the snapshot gives Viva Jets no investor or programme row"
    a = {s["q"]: s["text"] for s in _answers(VIVA).values()}
    assert aava.OPINION[m["recommendation"]["decision"]] in a[1]
    assert f"The verdict is {aava._dec(m['recommendation']['decision'])}" in a[2]
    assert any(n in a[4] for n in names)
    seg4 = [s for s in _answers(VIVA).values() if s["q"] == 4][0]
    assert seg4["target"] == "q3" and seg4["source_url"].startswith("http")
    assert "not scored on this page" not in " ".join(a.values())


def test_page_embeds_every_question_in_order_and_the_player_controls(client):
    html = client.get(f"/c/{VIVA}?demo=1").text
    data = _embedded(html)
    assert set(data) == set(aava.INTENTS)
    labels = [label.replace("'", "&#39;") for _n, _intent, label in aava.QUESTIONS]
    at = [html.index(label) for label in labels]
    assert at == sorted(at) and len(set(at)) == 6
    assert [int(n) for n in re.findall(r'class="aava-btn aava-q" type="button" data-q="(\d)"', html)] == [1, 2, 3, 4, 5, 6]
    assert 'id="aava-next"' in html and 'id="aava-pause"' in html
    have = set(re.findall(r'\bid="([^"]+)"', html))
    for intent, segs in data.items():
        assert segs, intent
        for s in segs:
            assert s["target"] in have, (intent, s["target"])
            assert s["source_url"] is None or s["source_url"].startswith("http")
    text = re.sub(r"<[^>]+>", " ", html.split('id="aava-data"')[0])
    page_numbers = set(re.findall(r"\d+", text))
    for intent in ("why", "meet", "missing", "next", "talk"):
        for s in data[intent]:
            spoken = re.sub(r"\b\d{1,2} (%s) \d{4}\b" % "|".join(aava.MONTHS), "", s["text"])
            for n in re.findall(r"\d+", spoken):
                assert n in page_numbers or n == "9", (intent, n, s["text"])


def test_feed_page_embeds_its_script(client):
    html = client.get("/?demo=1").text
    data = _embedded(html)
    assert set(data) == {"brief"} and data["brief"]
    assert aava.FEED_QUESTIONS[0][2] in html and 'data-q="1"' in html


# ---- browser: a tap plays at once, with no request ---------------------------------------------------------------
@pytest.fixture()
def live_url(snap):
    pytest.importorskip("playwright.sync_api")
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    env = {**__import__("os").environ, "RADAR_DATA_DIR": str(snap)}
    env.pop("RADAR_DB", None)
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=Path(__file__).resolve().parent.parent, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(5)


def test_question_tap_plays_without_a_request(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p = sync_api.sync_playwright().start()
    browser = None
    for kwargs in ({}, {"executable_path": "/opt/pw-browsers/chromium"}):
        try:
            browser = p.chromium.launch(**kwargs)
            break
        except Exception as e:
            err = e
    if browser is None:
        p.stop()
        pytest.skip(f"chromium unavailable: {err}")
    try:
        page = browser.new_page(viewport={"width": 390, "height": 800})
        page.goto(f"{live_url}/c/{VIVA}?demo=1")
        seen = []
        page.on("request", lambda r: seen.append(r.url))
        page.click("#aava-open")
        page.click("[data-q='2']")
        page.wait_for_function("document.getElementById('aava-caption').textContent.startsWith('On ocean impact')", timeout=3000)
        assert not [u for u in seen if "/aava/" in u and "/static/aava/audio/" not in u]  # the pre-rendered clip is a static file, not a request for the answer
        page.click("#aava-stop")
    finally:
        browser.close()
        p.stop()
