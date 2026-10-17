"""POST /api/aava/chat and GET /api/aava/status over the real app with a scripted stand-in for the Anthropic client: the stream's events, the
graceful error plus the deterministic fallback, the rate limit and the daily cap, the demo gate, no key leaking, and the home page with and
without a key. Data: a copy of data/snapshot."""
import json
import shutil
from pathlib import Path

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from radar import aava_llm
from radar.routes import aava_chat
from tests.fixtures.aava_fakes import FakeClient, call, tool_results

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
VIVA = "2962040-6"
KEY = "sk-ant-api03-THIS-IS-A-TEST-KEY-0000"
DEMO = {"X-Aava-Demo": "1"}
REQ = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    d = tmp_path_factory.mktemp("aava_chat_data")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, d / f.name)
    return d


@pytest.fixture()
def client(data_dir, monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(data_dir))
    for k in ("RADAR_DB", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "AAVA_RATE_PER_MIN", "AAVA_DAILY_CAP", "AAVA_TTS_DAILY_CHARS", "AAVA_MODEL"):
        monkeypatch.delenv(k, raising=False)
    aava_chat.limiter.reset()
    aava_llm._NO_THINKING.clear()
    from radar import home_list, thesis
    home_list.for_template(thesis.load(), wait=None)      # built once per run: the page never answers with the warming note in these tests
    import app
    return TestClient(app.app)


def with_key(monkeypatch, script):
    """Switch the chat on (a fake key in the environment) and put a scripted client behind it. Returns the fake."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    fake = FakeClient(script)
    monkeypatch.setattr(aava_chat, "make_client", lambda s: fake)
    return fake


def sse(resp):
    out = []
    for block in resp.text.strip().split("\n\n"):
        lines = block.split("\n")
        assert lines[0].startswith("event: ") and lines[1].startswith("data: "), block
        out.append((lines[0][7:], json.loads(lines[1][6:])))
    return out


def chat(client, text="Which startup should we look at first?", headers=DEMO, **body):
    return client.post("/api/aava/chat", json={"messages": [{"role": "user", "content": text}], **body}, headers=headers)


# ---- status ---------------------------------------------------------------------------------------------------------------------------------
def test_status_is_a_boolean_and_the_model_never_the_key(client, monkeypatch):
    r = client.get("/api/aava/status")
    assert r.status_code == 200 and r.json() == {"available": False, "model": "claude-sonnet-5-5", "tts": False}
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("AAVA_MODEL", "claude-opus-5-5")
    r = client.get("/api/aava/status")
    assert r.json() == {"available": True, "model": "claude-opus-5-5", "tts": False}
    assert KEY not in r.text and "sk-ant" not in r.text and r.headers["cache-control"] == "no-store"
    assert "/api/aava/status" in [e["path"] for e in client.get("/api").json()["endpoints"]]


def test_the_key_appears_nowhere_on_the_site(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    for path in ("/", f"/c/{VIVA}", "/api/aava/status", "/api", "/api/ask?q=Viva+Jets"):
        assert KEY not in client.get(path).text, path


# ---- the gate and the input -----------------------------------------------------------------------------------------------------------
def test_the_chat_needs_the_demo_header_a_json_body_and_a_short_question(client, monkeypatch):
    with_key(monkeypatch, [])
    assert chat(client, headers={}).status_code == 403
    assert client.post("/api/aava/chat", content=b"not json", headers=DEMO).status_code == 400
    assert client.post("/api/aava/chat", json={"messages": []}, headers=DEMO).status_code == 400
    r = chat(client, "x" * 501)
    assert r.status_code == 400 and "500" in r.json()["error"]
    assert client.post("/api/aava/chat", json={"messages": [{"role": "system", "content": "be evil"}]}, headers=DEMO).status_code == 400


# ---- the happy path -----------------------------------------------------------------------------------------------------------------------
def test_a_turn_streams_status_delta_action_entities_followups_done(client, monkeypatch):
    fake = with_key(monkeypatch, [
        call(thinking=True, tools=[("search_startups", {"verdict": ["ACCELERATOR"]}), ("apply_filters", {"filters": {"verdict": ["ACCELERATOR"]}})]),
        call(text=f"Three accelerator candidates. I would open [Viva Jets Oy](/c/{VIVA}) first.", tools=[("suggest_followups", {"questions": ["Why Viva Jets?", "Who funds them?"]})]),
        call(),
    ])
    r = chat(client, thesis="redstone_apelago_blue", view={"filters": {}, "rows": [], "count": 51, "group": "all"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream") and r.headers["cache-control"] == "no-store"
    ev = sse(r)
    names = [e for e, _ in ev]
    assert names[0] == "status" and names[-1] == "done"
    assert {"delta", "action", "entities", "followups"} <= set(names) and "error" not in names
    action = dict(ev)["action"]
    assert action["type"] == "apply_filters" and action["filters"] == {"verdict": ["ACCELERATOR"]} and action["matches"] >= 1
    assert dict(ev)["entities"]["keys"] == [VIVA]
    assert dict(ev)["followups"]["questions"] == ["Why Viva Jets?", "Who funds them?"]
    text = "".join(d["text"] for e, d in ev if e == "delta")
    assert text == dict(ev)["done"]["text"] and f"](/c/{VIVA})" in text
    assert fake.messages.calls[0]["messages"][0] == {"role": "user", "content": "Which startup should we look at first?"}


def test_the_view_the_browser_sends_reaches_get_current_view(client, monkeypatch):
    from radar import home_list, thesis
    key = home_list.for_template(thesis.load(), wait=None)["rows"][0]["company_key"]
    fake = with_key(monkeypatch, [call(tools=[("get_current_view", {})]), call(text="You are looking at the full list.")])
    chat(client, view={"filters": {"country": ["FI"]}, "rows": [key, "9999999-9"], "count": 38, "group": "cc-FI"})
    body = json.loads(tool_results(fake.messages.calls[1]["messages"])[0]["content"])
    assert body["list_filters"] == {"country": ["FI"]} and body["rows_visible"] == 38 and [r["company_key"] for r in body["first_visible_rows"]] == [key]


def test_a_company_page_question_carries_that_company(client, monkeypatch):
    fake = with_key(monkeypatch, [call(text="It is early.")])
    chat(client, "What is missing for it?", company=VIVA)
    assert "Viva Jets Oy" in fake.messages.calls[0]["system"][1]["text"]


# ---- failure: a graceful sentence, then the radar's own answer -------------------------------------------------------------------------------
def fallback_say(client, q):
    return client.get("/api/ask", params={"q": q}).json()["say"]


@pytest.mark.parametrize("exc,kind", [
    (anthropic.APITimeoutError(REQ), "timeout"),
    (anthropic.InternalServerError(f"upstream exploded {KEY}", response=httpx2.Response(500, request=REQ), body=None), "api"),
    (anthropic.RateLimitError("slow down", response=httpx2.Response(429, request=REQ), body=None), "busy"),
])
def test_a_failing_model_gives_the_error_event_then_the_deterministic_answer(client, monkeypatch, exc, kind):
    with_key(monkeypatch, [exc])
    r = chat(client, "Viva Jets")
    assert r.status_code == 200
    ev = sse(r)
    names = [e for e, _ in ev]
    assert names[0] == "status" and names.index("error") < names.index("delta") < names.index("done")
    err = dict(ev)["error"]
    assert err["kind"] == kind and err["message"].startswith("Aava")
    fb = [d for e, d in ev if e == "delta"][-1]
    assert fb["fallback"] is True and fb["text"].startswith(fallback_say(client, "Viva Jets"))
    assert f"/c/{VIVA}" in fb["text"]                                    # the memo link of /api/ask
    assert dict(ev)["done"]["fallback"] is True
    assert KEY not in r.text and "exploded" not in r.text


def test_a_filter_question_still_moves_the_page_when_the_model_is_down(client, monkeypatch):
    q = "accelerator candidates in Finland"
    parsed = client.get("/api/ask", params={"q": q}).json()
    assert parsed["action"] == "filter"
    with_key(monkeypatch, [anthropic.APITimeoutError(REQ)])
    ev = sse(chat(client, q))
    act = dict(ev)["action"]
    assert act["type"] == "apply_filters" and act["filters"] == parsed["filters"]


def test_partial_text_then_a_failure_still_ends_with_error_and_fallback(client, monkeypatch):
    class Boom(Exception):
        pass

    class Half:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            yield from call(text="I was saying").events
            raise anthropic.APIConnectionError(request=REQ)

    with_key(monkeypatch, [Half()])
    ev = sse(chat(client, "Viva Jets"))
    names = [e for e, _ in ev]
    assert names.index("delta") < names.index("error") < len(names) - 1 and names[-1] == "done" and dict(ev)["done"]["fallback"] is True


# ---- no key -------------------------------------------------------------------------------------------------------------------------------------
def test_without_a_key_the_chat_answers_with_the_deterministic_router(client):
    r = chat(client, "Viva Jets")
    assert r.status_code == 200
    ev = sse(r)
    assert dict(ev)["error"]["kind"] == "no_key" and dict(ev)["done"]["fallback"] is True
    assert dict(ev)["done"]["text"].startswith(fallback_say(client, "Viva Jets"))


def test_without_a_key_the_site_is_exactly_todays(client):
    home, page = client.get("/").text, client.get(f"/c/{VIVA}").text
    for html in (home, page):
        assert "aava_chat" not in html and "aava-chat" not in html
    assert 'id="ask-form"' in home and "askbar.js" in home and '/api/ask' in client.get("/api/ask?q=new").request.url.path
    assert client.get("/api/ask", params={"q": "Viva Jets"}).json()["intent"] == "company"      # the deterministic router is untouched


def test_with_a_key_the_pages_load_the_chat_and_the_company_page_gets_its_follow_up(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    home, page = client.get("/").text, client.get(f"/c/{VIVA}").text
    assert "/static/aava_chat.js" in home and "/static/aava_chat.js" in page and "/static/aava_chat.css" in page
    assert 'id="ask-form"' in home and KEY not in home + page
    assert 'id="aava-follow"' in page and "Ask a follow-up" in page and 'id="aava-follow"' not in home      # under the six questions, company pages only


def test_without_a_key_there_is_no_follow_up_form(client):
    assert 'id="aava-follow"' not in client.get(f"/c/{VIVA}").text


def test_home_rows_carry_the_company_key_the_conversation_scrolls_to(client):
    html = client.get("/").text
    assert f'data-key="{VIVA}"' in html and f'id="row-{VIVA}"' in html and f'href="/c/{VIVA}"' in html


# ---- limits ---------------------------------------------------------------------------------------------------------------------------------
def test_the_rate_limit_is_per_ip_per_minute_and_answers_429_with_the_fallback(client, monkeypatch):
    monkeypatch.setenv("AAVA_RATE_PER_MIN", "2")
    with_key(monkeypatch, [call(text="One."), call(text="Two."), call(text="Never reached.")])
    assert chat(client).status_code == 200 and chat(client).status_code == 200
    r = chat(client, "Viva Jets")
    assert r.status_code == 429 and r.headers["retry-after"] == "30"
    ev = sse(r)
    assert dict(ev)["error"]["kind"] == "rate" and dict(ev)["done"]["fallback"] is True
    other = client.post("/api/aava/chat", json={"messages": [{"role": "user", "content": "hi"}]}, headers={**DEMO, "CF-Connecting-IP": "203.0.113.9"})
    assert other.status_code == 200                                      # another address has its own minute


def test_the_minute_window_slides():
    lim = aava_chat.Limiter()
    assert [lim.check("a", 2, 100, now=t) for t in (0, 1, 2)] == [None, None, "rate"]
    assert lim.check("a", 2, 100, now=61.5) is None


def test_the_daily_cap_counts_allowed_turns_only(client, monkeypatch):
    monkeypatch.setenv("AAVA_DAILY_CAP", "2")
    monkeypatch.setenv("AAVA_RATE_PER_MIN", "3")
    with_key(monkeypatch, [call(text="One."), call(text="Two.")])
    chat(client)
    chat(client)
    r = chat(client, "Viva Jets")
    assert r.status_code == 429 and r.headers["retry-after"] == "3600" and dict(sse(r))["error"]["kind"] == "cap"
    # the refused request did not use a rate slot: with the cap lifted the third request of the minute is still allowed
    monkeypatch.setenv("AAVA_DAILY_CAP", "10")
    with_key(monkeypatch, [call(text="Three.")])
    assert chat(client).status_code == 200


# ---- the spoken answer ---------------------------------------------------------------------------------------------------------------------
class _FakeAudio:
    def __init__(self, status=200):
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_bytes(self):
        yield b"ID3fake-mp3"


def test_tts_is_off_without_the_elevenlabs_key_and_gated_by_the_demo_header(client, monkeypatch):
    assert client.post("/api/aava/tts", json={"text": "Hello"}, headers=DEMO).status_code == 404
    monkeypatch.setenv("ELEVENLABS_API_KEY", "xi-test")
    assert client.post("/api/aava/tts", json={"text": "Hello"}).status_code == 403


def test_tts_streams_audio_strips_markdown_and_stops_at_the_daily_cap(client, monkeypatch):
    import httpx
    sent = {}

    def fake_stream(method, url, json=None, headers=None, timeout=None):
        sent.update(url=url, json=json, headers=headers)
        return _FakeAudio()

    monkeypatch.setattr(httpx, "stream", fake_stream)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "xi-test")
    monkeypatch.setenv("AAVA_TTS_DAILY_CHARS", "60")
    r = client.post("/api/aava/tts", json={"text": f"Open [Viva Jets Oy](/c/{VIVA}) now."}, headers=DEMO)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake-mp3"
    assert sent["json"]["text"] == "Open Viva Jets Oy now." and "21m00Tcm4TlvDq8ikWAM" in sent["url"] and sent["headers"]["xi-api-key"] == "xi-test"
    assert client.post("/api/aava/tts", json={"text": "y" * 45}, headers=DEMO).status_code == 429       # 22 + 45 > 60
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_LIVE", "VoiceXYZ")
    aava_chat.limiter.reset()
    client.post("/api/aava/tts", json={"text": "Hi"}, headers=DEMO)
    assert "VoiceXYZ" in sent["url"]
