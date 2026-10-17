"""Aava's pre-rendered narration: the render CLI (dry run, cache by text hash, no key printed, BLOCKED without a key) and the player
(plays the MP3 sequence when every segment's sha is in the manifest, falls back to the browser voice otherwise).
Companies are the synthetic fixtures; no ElevenLabs call is ever made (the HTTP layer is replaced, the dry run never reaches it)."""
import io
import json
import re
import time
import urllib.error
from pathlib import Path

import pytest

# fixtures and helpers of the Aava front-end tests: the synthetic company database, the app client, a live server, a chromium page
from test_aava import RICH, _page, client, db_path, live_url  # noqa: F401  (fixtures are used by name)

from radar import aava, aava_voice

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SILENCE = FIXTURES / "silence.mp3"  # 0.627 s of mono 44.1 kHz silence, 32 kbps


def embedded(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="aava-data">(.*?)</script>', html, re.S)
    assert m, "no embedded Aava script"
    return json.loads(m.group(1))


@pytest.fixture(autouse=True)
def no_key_no_network(monkeypatch):
    """The suite never holds a key and never reaches ElevenLabs: a test that wants the HTTP layer replaces it itself."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

    def refuse(*a, **k):
        raise AssertionError("a test reached the network")
    monkeypatch.setattr(aava_voice.urllib.request, "urlopen", refuse)


# ---- the fingerprint ---------------------------------------------------------------------------------------------------------
def test_every_segment_carries_the_sha_of_its_text(client):
    data = embedded(client.get(f"/c/{RICH}").text)
    served = client.get(f"/aava/script/{RICH}").json()["segments"]
    for s in [x for segs in data.values() for x in segs] + served + client.get("/aava/feed").json()["segments"]:
        assert s["sha"] == aava.text_sha(s["text"]) and re.fullmatch(r"[0-9a-f]{16}", s["sha"])
    assert aava.text_sha("a") != aava.text_sha("b")


def test_audio_directory_name_is_a_safe_single_path_segment():
    assert aava_voice.dir_name("2962040-6") == "2962040-6"
    assert aava_voice.dir_name("name:sparse") == "name_sparse"
    for key in ("..", ".", "", "../x", "a/b\\c", "ä ö"):
        d = aava_voice.dir_name(key)
        assert re.fullmatch(r"[A-Za-z0-9._-]+", d) and set(d) != {"."}, (key, d)  # one plain path segment, never "." or ".."


# ---- MP3 length --------------------------------------------------------------------------------------------------------------
def test_mp3_duration_is_read_from_the_frames():
    seconds = aava_voice.mp3_duration(SILENCE.read_bytes())
    assert seconds is not None and abs(seconds - 0.627) < 0.01  # 24 frames of 1152 samples at 44.1 kHz
    assert aava_voice.mp3_duration(b"not audio at all") is None
    assert aava_voice.mp3_duration(b"") is None
    assert aava_voice.estimate_seconds("one two three four five six") == pytest.approx(6 / 2.6, abs=0.01)


# ---- dry run: a manifest that matches the page, no key, no call ------------------------------------------------------------
def test_dry_run_manifest_matches_the_pages_own_segments(client, tmp_path, capsys):
    out = tmp_path / "audio"
    assert aava_voice.main(["render", "--keys", f"{RICH},nope-1", "--feed", "--dry-run", "--out", str(out)]) == 1  # nope-1 is not a company
    err = capsys.readouterr().err
    assert "FAILED nope-1" in err and "BLOCKED" not in err
    assert not (out / "nope-1").exists()

    page = embedded(client.get(f"/c/{RICH}").text)
    m = json.loads((out / RICH / "manifest.json").read_text(encoding="utf-8"))
    by_sha = {e["text_sha"]: e for e in m["segments"]}
    page_segments = [s for intent in aava.INTENTS for s in page[intent]]
    assert page_segments and {s["sha"] for s in page_segments} == set(by_sha)  # every text on the page is in the manifest, and nothing else
    for s in page_segments:
        e = by_sha[s["sha"]]
        assert e["target"] == s["target"] and e["file"] == f"{e['n']}_{s['sha'][:8]}.mp3"
        assert e["duration_source"] == "estimated" and e["duration_s"] > 0 and e["chars"] == len(s["text"])
    assert [e["n"] for e in m["segments"]] == list(range(len(m["segments"])))
    assert m["model"] == "eleven_multilingual_v2" and m["voice_id"] == aava_voice.DEFAULT_VOICE_ID
    assert not list((out / RICH).glob("*.mp3"))  # a dry run writes no audio

    feed = embedded(client.get("/").text)["brief"]
    fm = json.loads((out / "feed" / "manifest.json").read_text(encoding="utf-8"))
    assert [e["text_sha"] for e in fm["segments"]] == list(dict.fromkeys(s["sha"] for s in feed))


def test_dry_run_reports_the_characters_it_would_send(client, tmp_path, capsys):
    assert aava_voice.main(["render", "--keys", RICH, "--dry-run", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    chars = sum(len(s["text"]) for s in aava_voice.plan(aava_voice.collect_company(RICH, __import__("radar.thesis", fromlist=["load"]).load())))
    assert f"({chars} characters)" in out and f"Characters still to render: {chars}" in out and "no API call was made" in out


def test_without_a_key_the_render_is_blocked_and_writes_nothing(client, tmp_path, capsys):
    assert aava_voice.main(["render", "--keys", RICH, "--out", str(tmp_path / "audio")]) == aava_voice.EXIT_BLOCKED == 3
    err = capsys.readouterr().err
    assert err.startswith("BLOCKED: ELEVENLABS_API_KEY is not set")
    assert not (tmp_path / "audio").exists()
    with pytest.raises(SystemExit) as e:
        aava_voice.main(["render", "--dry-run"])  # neither --keys nor --feed
    assert e.value.code == 2


# ---- render and cache by text hash (the synthesiser is a fake) -----------------------------------------------------------------
def test_render_caches_by_text_hash_and_rerenders_only_what_changed(tmp_path):
    mp3 = SILENCE.read_bytes()
    texts = ["First sentence.", "Second sentence.", "Third sentence."]

    def groups(ts):
        return {"brief": [aava.seg(t, "aava-who") for t in ts], "next": [aava.seg(ts[0], "aava-who")]}  # "next" repeats the first text: one clip

    called = []

    def fake(text):
        called.append(text)
        return mp3

    r = aava_voice.render_target("k1", groups(texts), "th", out_root=tmp_path, synth=fake)
    assert called == texts and r["todo"] == 3 and r["cached"] == 0 and r["characters"] == sum(map(len, texts)) and r["clips"] == 3
    rows = r["manifest"]["segments"]
    assert all(x["duration_source"] == "measured" and abs(x["duration_s"] - 0.627) < 0.01 and x["rendered"] for x in rows)
    assert all((tmp_path / "k1" / x["file"]).is_file() for x in rows)

    called.clear()
    r2 = aava_voice.render_target("k1", groups(texts), "th", out_root=tmp_path, synth=fake)
    assert called == [] and r2["todo"] == 0 and r2["cached"] == 3 and r2["characters"] == 0  # nothing changed, nothing is sent

    r3 = aava_voice.render_target("k1", groups([texts[0], "A changed second sentence.", texts[2]]), "th", out_root=tmp_path, synth=fake)
    assert called == ["A changed second sentence."] and r3["cached"] == 2

    called.clear()
    aava_voice.render_target("k1", groups(texts), "th", out_root=tmp_path, synth=fake, force=True)
    assert called == texts  # --force: a new voice renders everything again


def test_a_failing_synthesiser_leaves_the_earlier_manifest_and_clips_alone(tmp_path):
    mp3 = SILENCE.read_bytes()
    g = {"brief": [aava.seg("One.", "aava-who"), aava.seg("Two.", "aava-who")]}
    aava_voice.render_target("k2", g, "th", out_root=tmp_path, synth=lambda t: mp3)
    before = (tmp_path / "k2" / "manifest.json").read_text(encoding="utf-8")
    g2 = {"brief": [aava.seg("One.", "aava-who"), aava.seg("Two, changed.", "aava-who")]}

    def broken(text):
        raise aava_voice.VoiceError("ElevenLabs refused the request (HTTP 401)")
    with pytest.raises(aava_voice.VoiceError):
        aava_voice.render_target("k2", g2, "th", out_root=tmp_path, synth=broken)
    assert (tmp_path / "k2" / "manifest.json").read_text(encoding="utf-8") == before


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def test_elevenlabs_request_shape_and_the_key_stays_out_of_every_message(monkeypatch):
    key = "sk_test_SECRET_VALUE_1234567890"
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append(req)
        if len(seen) == 1:  # first answer: rate limit with a body that echoes the key, then success
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {"Retry-After": "1"}, io.BytesIO(json.dumps({"detail": {"message": f"slow down {key}"}}).encode()))
        return _Resp(SILENCE.read_bytes())

    monkeypatch.setattr(aava_voice.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(aava_voice, "_sleep", lambda s: None)
    synth = aava_voice.ElevenLabs(key, "21m00Tcm4TlvDq8ikWAM")
    assert key not in repr(synth) and key not in str(vars(synth).get("voice_id"))
    assert synth("Hello there.") == SILENCE.read_bytes() and len(seen) == 2
    req = seen[-1]
    assert req.full_url.startswith("https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM?output_format=mp3_44100_64")
    assert req.get_header("Xi-api-key") == key and req.get_method() == "POST"
    body = json.loads(req.data)
    assert body["model_id"] == "eleven_multilingual_v2" and body["text"] == "Hello there."

    def refuse(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(json.dumps({"detail": {"message": f"invalid key {key}"}}).encode()))
    monkeypatch.setattr(aava_voice.urllib.request, "urlopen", refuse)
    with pytest.raises(aava_voice.VoiceError) as e:
        synth("Hello there.")
    assert key not in str(e.value) and "401" in str(e.value)

    monkeypatch.setattr(aava_voice.urllib.request, "urlopen", lambda req, timeout=None: _Resp(b"<html>not audio</html>"))
    with pytest.raises(aava_voice.VoiceError, match="not MP3"):
        synth("Hello there.")
    with pytest.raises(aava_voice.VoiceError, match="voice id"):
        aava_voice.ElevenLabs(key, "../../etc")


def test_the_module_never_opens_a_file_that_could_hold_a_key():
    src = Path(aava_voice.__file__).read_text(encoding="utf-8")
    assert "os.environ" in src and "ELEVENLABS_API_KEY" in src
    assert not re.search(r"dotenv|open\([^)]*\.env|read_text\([^)]*env", src)


# ---- the player (chromium; skipped where it is missing) ----------------------------------------------------------------------
def _manifest_for(client, key=RICH, tamper=None, url=None):
    """A manifest listing a clip for every text the page embeds, built the way the render writes it. tamper(sha) -> sha changes one entry.
    url is the page that embeds the script (the company page by default, "/" for the feed)."""
    page = embedded(client.get(url or f"/c/{key}").text)
    rows, seen = [], set()
    for segs in page.values():
        for s in segs:
            if s["sha"] in seen:
                continue
            seen.add(s["sha"])
            sha = tamper(s["sha"]) if tamper else s["sha"]
            rows.append({"n": len(rows), "target": s["target"], "text_sha": sha, "file": f"{len(rows)}_{sha[:8]}.mp3", "duration_s": 0.627, "duration_source": "measured"})
    return page, {"version": 1, "key": key, "segments": rows}


def _serve_audio(page, manifest, hits, mp3_status=200):
    """The manifest and the clips come from the test (the silence fixture), not from the repo's static directory."""
    mp3 = SILENCE.read_bytes()

    def handler(route):
        url = route.request.url
        hits.append(url)
        if url.split("?")[0].endswith("/manifest.json"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps(manifest))
        elif mp3_status != 200:
            route.fulfill(status=mp3_status, body="gone")
        else:
            route.fulfill(status=200, content_type="audio/mpeg", body=mp3)
    page.route(re.compile(r".*/static/aava/audio/.*"), handler)


SPY = ("window.__spoken = []; if (window.speechSynthesis) { var o = window.speechSynthesis.speak.bind(window.speechSynthesis);"
       " window.speechSynthesis.speak = function (u) { window.__spoken.push(u.text); return o(u); }; }")


def _caption(page):
    return page.locator("#aava-caption").inner_text()


def _by_q(data):
    return {s["q"]: s for segs in data.values() for s in segs}


def test_player_plays_each_answer_from_its_clip_when_the_hash_matches(client, live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        data, manifest = _manifest_for(client)
        q = _by_q(data)
        hits, requests = [], []
        _serve_audio(page, manifest, hits)
        page.on("request", lambda r: requests.append(r.url))
        page.add_init_script(SPY)
        page.goto(f"{live_url}/c/{RICH}?demo=1")
        page.wait_for_function("window.Aava && window.Aava.audioDir", timeout=5000)
        page.click("#aava-open")
        time.sleep(0.5)  # the manifest fetch settles
        by_sha = {e["text_sha"]: e["file"] for e in manifest["segments"]}
        page.click("[data-q='1']")
        assert _caption(page) == q[1]["text"]
        assert page.locator("#aava-mode").inner_text() == "Recorded voice and captions"
        page.wait_for_function("document.getElementById('aava-audio').ended", timeout=5000)
        assert _caption(page) == q[1]["text"]                      # the answer stays on screen; nothing plays until Next
        page.click("#aava-next")
        assert _caption(page) == q[2]["text"]
        page.wait_for_function("document.getElementById('aava-audio').ended", timeout=5000)
        page.keyboard.press("ArrowRight")
        assert _caption(page) == q[3]["text"] and page.evaluate("document.getElementById('aava-audio').src").endswith(".mp3")
        assert page.locator(".aava-hl").count() <= 1
        clips = [u for u in hits if u.endswith(".mp3")]
        assert [u.rsplit("/", 1)[1] for u in clips[:3]] == [by_sha[q[n]["sha"]] for n in (1, 2, 3)]
        assert page.evaluate("window.__spoken") == []  # the browser voice never spoke
        assert all(u.startswith(live_url) or u.startswith(("data:", "about:", "blob:")) for u in requests), [u for u in requests if not u.startswith(live_url)]
        page.click("#aava-stop")
        assert page.evaluate("document.getElementById('aava-audio').paused")
        assert "Stopped" in _caption(page)
        time.sleep(1.2)
        assert "Stopped" in _caption(page)  # nothing advances after stop
    finally:
        browser.close()
        p.stop()


def test_player_plays_the_feed_answer_clip_by_clip(client, live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        data, manifest = _manifest_for(client, key="feed", url="/")
        segs = data["brief"]
        assert len(segs) >= 3
        hits = []
        _serve_audio(page, manifest, hits)
        page.goto(f"{live_url}/?demo=1")
        page.click("#aava-open")
        time.sleep(0.5)
        page.click("[data-q='1']")
        assert _caption(page) == segs[0]["text"]
        for s in segs[1:3]:
            page.wait_for_function("t => document.getElementById('aava-caption').textContent === t", arg=s["text"], timeout=5000)  # advanced on 'ended'
        by_sha = {e["text_sha"]: e["file"] for e in manifest["segments"]}
        for _ in range(30):  # the request for the third clip is recorded a moment after its caption shows
            if len([u for u in hits if u.endswith(".mp3")]) >= 3:
                break
            time.sleep(0.1)
        assert [u.rsplit("/", 1)[1] for u in hits if u.endswith(".mp3")][:3] == [by_sha[s["sha"]] for s in segs[:3]]
        page.click("#aava-stop")
    finally:
        browser.close()
        p.stop()


def test_player_pause_holds_the_recording_and_resume_goes_on(client, live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        data, manifest = _manifest_for(client, key="feed", url="/")
        _serve_audio(page, manifest, [])
        page.goto(f"{live_url}/?demo=1")
        page.click("#aava-open")
        time.sleep(0.5)
        page.click("[data-q='1']")
        page.click("#aava-pause")
        assert page.locator("#aava-pause").inner_text() == "Resume"
        held = _caption(page)
        time.sleep(1.6)  # a clip is 0.6 s: a run that was not held would be two segments further
        assert _caption(page) == held and page.evaluate("document.getElementById('aava-audio').paused")
        page.click("#aava-pause")
        assert page.locator("#aava-pause").inner_text() == "Pause"
        page.wait_for_function("t => document.getElementById('aava-caption').textContent !== t", arg=held, timeout=5000)
        page.click("#aava-stop")
    finally:
        browser.close()
        p.stop()


def test_player_falls_back_to_the_browser_voice_for_an_answer_whose_hash_differs(client, live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        second = _by_q(embedded(client.get(f"/c/{RICH}").text))[2]["sha"]
        page_data, manifest = _manifest_for(client, tamper=lambda sha: "0" * 16 if sha == second else sha)  # one text was edited since the render
        assert any(e["text_sha"] == "0" * 16 for e in manifest["segments"])
        q = _by_q(page_data)
        hits = []
        _serve_audio(page, manifest, hits)
        page.add_init_script(SPY)
        page.goto(f"{live_url}/c/{RICH}?demo=1")
        page.click("#aava-open")
        time.sleep(0.5)
        page.click("[data-q='1']")                                  # an untouched answer still plays from its clip
        assert page.locator("#aava-mode").inner_text() == "Recorded voice and captions"
        page.wait_for_function("document.getElementById('aava-audio').ended", timeout=5000)
        clips = [u for u in hits if u.endswith(".mp3")]
        page.click("#aava-next")                                    # the edited one goes to the browser voice
        assert _caption(page) == q[2]["text"]
        assert page.locator("#aava-mode").inner_text() != "Recorded voice and captions"
        time.sleep(0.8)
        assert [u for u in hits if u.endswith(".mp3")] == clips     # no clip was requested for it
        assert page.evaluate("window.__spoken")[-1:] == [q[2]["text"]]  # the browser voice was asked to read it
        page.click("#aava-stop")
    finally:
        browser.close()
        p.stop()


def test_a_feed_answer_with_one_changed_hash_plays_from_no_clip_at_all(client, live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        second = embedded(client.get("/").text)["brief"][1]["sha"]
        page_data, manifest = _manifest_for(client, key="feed", url="/", tamper=lambda sha: "0" * 16 if sha == second else sha)
        hits = []
        _serve_audio(page, manifest, hits)
        page.add_init_script(SPY)
        page.goto(f"{live_url}/?demo=1")
        page.click("#aava-open")
        time.sleep(0.5)
        page.click("[data-q='1']")
        segs = page_data["brief"]
        assert _caption(page) == segs[0]["text"]
        assert page.locator("#aava-mode").inner_text() != "Recorded voice and captions"
        time.sleep(0.8)
        assert [u for u in hits if u.endswith(".mp3")] == []  # not one clip was requested: all or nothing for a question
        assert page.locator("#aava-audio").count() == 0
        assert page.evaluate("window.__spoken")[:1] == [segs[0]["text"]]
        page.click("#aava-stop")
    finally:
        browser.close()
        p.stop()


def test_player_without_a_manifest_behaves_exactly_as_before(client, live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        hits = []
        page.route(re.compile(r".*/static/aava/audio/.*"), lambda route: (hits.append(route.request.url), route.fulfill(status=404, body="no")))
        q = _by_q(embedded(client.get(f"/c/{RICH}").text))
        page.goto(f"{live_url}/c/{RICH}?demo=1")
        page.click("#aava-open")
        time.sleep(0.5)
        page.click("[data-q='1']")
        assert _caption(page) == q[1]["text"]
        assert page.locator("#aava-mode").inner_text() in ("Voice and captions", "Captions only (no English voice on this device)")
        assert page.locator("#aava-audio").count() == 0
        assert len(hits) == 1 and hits[0].split("?")[0].endswith(f"/static/aava/audio/{RICH}/manifest.json")
        page.click("#aava-stop")
    finally:
        browser.close()
        p.stop()


def test_a_clip_that_will_not_load_hands_the_rest_to_the_browser_voice(client, live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        data, manifest = _manifest_for(client)
        _serve_audio(page, manifest, [], mp3_status=404)
        page.goto(f"{live_url}/c/{RICH}?demo=1")
        page.click("#aava-open")
        time.sleep(0.5)
        page.click("[data-q='1']")
        page.wait_for_function("document.getElementById('aava-mode').textContent !== 'Recorded voice and captions'", timeout=5000)
        assert _caption(page) == _by_q(data)[1]["text"]  # still on the first answer, now read by the browser voice or its captions
        page.click("#aava-stop")
    finally:
        browser.close()
        p.stop()


def test_the_players_directory_name_equals_the_renderers(client, live_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    p, browser, page = _page(sync_api, {"width": 390, "height": 800})
    try:
        page.goto(f"{live_url}/c/{RICH}?demo=1")
        page.wait_for_function("window.Aava && window.Aava.audioDir", timeout=5000)
        for key in ("2962040-6", "name:sparse", "..", ".", "a/b c", "äö", "x?y#z", "feed"):
            assert page.evaluate("k => window.Aava.audioDir(k)", key) == aava_voice.dir_name(key), key
    finally:
        browser.close()
        p.stop()
