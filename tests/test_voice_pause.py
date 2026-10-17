"""Voice mode waits for a real pause (D82): a short breath mid-sentence does not send the question, 1.5 s of quiet does, and a tap on the
orb while talking sends at once. The browser's speech recognition is replaced by a fake the test drives; chromium, skipped where missing."""
import time

import pytest

from test_aava import _page, client, db_path, live_url  # noqa: F401  (fixtures are used by name)

FAKE_SR = """
window.__sr = null;
function FakeSR() { window.__sr = this; this.continuous = false; this.interimResults = false; }
FakeSR.prototype.start = function () { window.__srStarts = (window.__srStarts || 0) + 1; };
FakeSR.prototype.abort = function () { this.aborted = true; };
FakeSR.prototype.stop = function () {};
window.SpeechRecognition = FakeSR; window.webkitSpeechRecognition = FakeSR;
window.__say = function (parts) {            /* parts: [[transcript, isFinal], ...], the whole session so far, as the browser reports it */
  var res = parts.map(function (p) { var r = [{ transcript: p[0], confidence: 0.9 }]; r.isFinal = p[1]; return r; });
  if (window.__sr && window.__sr.onresult) window.__sr.onresult({ resultIndex: 0, results: res });
};
"""


def _open_voice(page, live_url):
    asks = []
    page.on("request", lambda r: asks.append(r.url) if "/api/ask?" in r.url else None)
    page.add_init_script(FAKE_SR)
    page.goto(f"{live_url}/?demo=1")
    page.click("#ask-mic")
    page.wait_for_function("window.__sr && document.getElementById('ask-voice').dataset.state === 'listening'")
    return asks


def _state(page):
    return page.evaluate("document.getElementById('ask-voice').dataset.state")


def test_a_short_pause_mid_sentence_does_not_send_and_a_long_one_does(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 1280, "height": 800})
    try:
        asks = _open_voice(page, live_url)
        assert page.evaluate("window.__sr.continuous") is True
        page.evaluate("window.__say([['hi aava welcome to junction x turku', false]])")
        page.wait_for_timeout(300)
        page.evaluate("window.__say([['hi aava welcome to junction x turku', true]])")   # the browser closes a phrase at a breath
        page.wait_for_timeout(800)
        assert not asks and _state(page) == "listening", "a 0.8 s breath sent the question"
        page.evaluate("window.__say([['hi aava welcome to junction x turku', true], [' can you introduce yourself', true]])")
        deadline = time.time() + 5
        while not asks and time.time() < deadline:
            page.wait_for_timeout(100)
        assert len(asks) == 1, asks
        assert "hi%20aava%20welcome%20to%20junction%20x%20turku%20can%20you%20introduce%20yourself" in asks[0]
        assert _state(page) != "listening"
    finally:
        browser.close()
        p.stop()


def test_a_tap_on_the_orb_while_talking_sends_at_once_and_with_nothing_heard_stops(live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 1280, "height": 800})
    try:
        asks = _open_voice(page, live_url)
        page.click("#ask-orb-btn")                                  # nothing heard yet: the tap stops listening, nothing is sent
        page.wait_for_timeout(300)
        assert not asks and _state(page) == "idle"
        page.click("#ask-orb-btn")                                  # listen again
        page.wait_for_function("document.getElementById('ask-voice').dataset.state === 'listening'")
        page.evaluate("window.__say([['is since labs on your radar', false]])")
        page.click("#ask-orb-btn")
        page.wait_for_timeout(400)                                  # well inside the 1.5 s pause: only the tap can have sent it
        assert len(asks) == 1 and "is%20since%20labs%20on%20your%20radar" in asks[0], asks
    finally:
        browser.close()
        p.stop()
