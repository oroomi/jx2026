"""Aava questions 03 and 04 wired to the real rows (matching.who_comes_next, matching.next_step, memo.build), the question menu,
and speech that starts on the tap (the scripts are embedded in the page, no request after the tap)."""
import json
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

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"
VIVA = "2962040-6"


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


def test_viva_jets_segments_have_the_verdict_and_a_named_investor_or_programme(client):
    from radar import matching, memo, store
    th = thesis.load()
    conn = store.open_db(thesis=th)
    m = memo.build(conn, th, VIVA)
    nxt = matching.who_comes_next(VIVA, th, 5, conn=conn)
    conn.close()
    names = [r["name"] for k in ("investors", "funding") for r in nxt[k]]
    assert names, "the snapshot gives Viva Jets no investor or programme row"
    for intent in ("brief", "next", "why"):
        text = " ".join(s["text"] for s in client.get(f"/aava/script/{VIVA}", params={"intent": intent}).json()["segments"])
        assert f"recommends {m['recommendation']['decision']}" in text, intent
    meet = " ".join(s["text"] for s in client.get(f"/aava/script/{VIVA}", params={"intent": "meet"}).json()["segments"])
    assert any(n in meet for n in names)
    brief = client.get(f"/aava/script/{VIVA}").json()["segments"]
    assert any(any(n in s["text"] for n in names) and s["target"] == "q3" for s in brief)
    assert not any("not scored on this page" in s["text"] for s in brief)


def test_page_embeds_every_question_and_shows_the_menu(client):
    html = client.get(f"/c/{VIVA}").text
    data = _embedded(html)
    assert set(data) == set(aava.INTENTS)
    for intent, label in aava.QUESTIONS:
        assert f'data-intent="{intent}"' in html and label.replace("'", "&#39;") in html
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
    data = _embedded(client.get("/").text)
    assert set(data) == {"brief"} and data["brief"]


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
        page.click("[data-intent=why]")
        page.wait_for_function("document.getElementById('aava-caption').textContent.includes('recommends')", timeout=3000)
        assert not [u for u in seen if "/aava/" in u]
        page.click("#aava-stop")
    finally:
        browser.close()
        p.stop()
