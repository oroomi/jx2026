"""Aava's conversation (PROJECT_RULES D61).

  GET  /api/aava/status   {available, model, tts}: whether a key is configured (a boolean, never the key) and the model id.
  POST /api/aava/chat     {messages, view, thesis, company} -> Server-Sent Events: status, delta, action, entities, followups, done, error.
  POST /api/aava/tts      {text} -> audio/mpeg from ElevenLabs when ELEVENLABS_API_KEY is set, behind a daily character cap.
  POST /api/aava/tts/prepare {text} -> {url}; GET that url streams the same audio, so the page starts speaking as it arrives.

The chat is gated like the voice already is: the browser sends the header `X-Aava-Demo: 1` only when the demo flag is on (?demo=1 or localStorage
aava_demo=1), and the server refuses without it. Rate limit (per client IP per minute) and a daily cap are in memory. Whatever goes wrong
(no key, rate limit, cap, timeout, API error, refusal) the stream carries an `error` event with a graceful sentence and then the deterministic answer
of radar/ask.py, so the visitor always gets something and the page's filters still move when the question was a filter.
Everything the model may know comes through radar.aava_tools; this module only shapes HTTP.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from radar import aava_llm, aava_tools, ask, store, thesis as thesis_mod
from radar.routes import api as api_routes
from radar.routes.aava import _inputs
from radar.routes.ask import has_page
from radar.routes.home import templates

log = logging.getLogger("aava.chat")
router = APIRouter()
api_routes.ENDPOINTS.append({"path": "/api/aava/status", "what": "whether Aava's reasoning model is switched on: {available, model, tts}; a boolean, never the key"})

templates.env.globals["aava_chat_on"] = aava_llm.available   # the pages load the chat only when a key is configured

DEMO_HEADER = "x-aava-demo"
SSE_HEADERS = {"Cache-Control": "no-store", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def _warm_aava() -> None:
    """When a key is configured (even with the kill switch on: the switch can be lifted without a restart), build the caches the tools read, once at
    start, so the first question's first tool call is not the one that pays for them (the home list takes seconds to build cold). A rebuilt store is
    warmed again at the next turn (aava_tools.ensure_warm)."""
    try:
        if aava_llm.api_key_present():
            aava_tools.ensure_warm(thesis_mod.load())
    except Exception as e:  # noqa: BLE001  (a failed warm-up only means the first tool call builds the cache itself)
        print(f"aava warm-up: {type(e).__name__}: {e}", file=sys.stderr)


if "pytest" not in sys.modules and os.environ.get("RADAR_NO_WARM") is None:
    threading.Thread(target=_warm_aava, name="aava-warm-start", daemon=True).start()


# ---- limits (in memory; a restart resets them) ----------------------------------------------------------------------------------------------
class Limiter:
    """Per-IP sliding minute and one UTC-day counter. `check` records a request only when it is allowed."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.hits: dict[str, deque] = {}
        self.day = ""
        self.count = 0
        self.tts_day = ""
        self.tts_chars = 0

    def check(self, ip: str, rate_per_min: int, daily_cap: int, now: float | None = None) -> str | None:
        """None when allowed (and counted); 'rate' or 'cap' when refused."""
        now = time.monotonic() if now is None else now
        today = datetime.now(timezone.utc).date().isoformat()
        with self.lock:
            if self.day != today:
                self.day, self.count = today, 0
            q = self.hits.setdefault(ip, deque())
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= rate_per_min:
                return "rate"
            if self.count >= daily_cap:
                return "cap"
            q.append(now)
            self.count += 1
            if len(self.hits) > 5000:   # forget idle addresses
                for k in [k for k, v in self.hits.items() if not v or now - v[-1] > 60]:
                    self.hits.pop(k, None)
            return None

    def tts(self, chars: int, cap: int) -> bool:
        today = datetime.now(timezone.utc).date().isoformat()
        with self.lock:
            if self.tts_day != today:
                self.tts_day, self.tts_chars = today, 0
            if self.tts_chars + chars > cap:
                return False
            self.tts_chars += chars
            return True


limiter = Limiter()


def client_ip(request: Request) -> str:
    h = request.headers
    return (h.get("cf-connecting-ip") or (h.get("x-forwarded-for") or "").split(",")[0].strip() or (request.client.host if request.client else "?"))[:64]


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---- status ------------------------------------------------------------------------------------------------------------------------------
@router.get("/api/aava/status")
def aava_status():
    return JSONResponse(aava_llm.status(), headers={"Cache-Control": "no-store"})


# ---- the deterministic answer that stands in when the model cannot ---------------------------------------------------------------------
def fallback(request: Request, th: dict, question: str) -> tuple[str, dict | None, list[str]]:
    """(markdown text, filter action or None, company keys) from radar.ask.resolve: the same answer the Ask bar gives without a model."""
    conn = store.open_db(thesis=th)
    try:
        a = ask.resolve(question, th, conn, inputs=_inputs, has_match=has_page(request, "/match"), thesis_id=th["id"])
    finally:
        if conn is not None:
            conn.close()
    text = a.get("say") or ask.HELP
    keys: list[str] = []
    items = a.get("items") or []
    if items:
        text += "\n\n" + "\n".join(f"- [{it['label']}]({it['url']})" for it in items[:8])
        keys = [m.group(1) for it in items[:8] if (m := re.match(r"/c/([^?#]+)", it["url"]))]
    if a.get("url") and a.get("label") and a["url"].startswith("/"):
        text += f"\n\n[{a['label']}]({a['url']})"
    action = None
    if a.get("action") == "filter" and a.get("filters"):
        action = {"type": "apply_filters", "filters": a["filters"], "group": "", "matches": a.get("count")}
    return text, action, keys


def _error_stream(request: Request, th: dict, question: str, kind: str, message: str):
    yield sse("error", {"kind": kind, "message": message})
    try:
        text, action, keys = fallback(request, th, question)
    except Exception:  # noqa: BLE001  (even the deterministic router failing must not leave the visitor with a broken stream)
        log.exception("fallback answer failed")
        text, action, keys = ask.HELP, None, []
    if action:
        yield sse("action", action)
    yield sse("delta", {"text": text, "fallback": True})
    if keys:
        yield sse("entities", {"keys": keys, "names": {}})
    yield sse("done", {"text": text, "keys": keys, "unverified": [], "sources": [], "fallback": True, "truncated": False, "model": None})


def _refuse(request: Request, th: dict, question: str, kind: str, message: str, status: int, extra: dict | None = None):
    return StreamingResponse(_error_stream(request, th, question, kind, message), status_code=status, media_type="text/event-stream",
                             headers={**SSE_HEADERS, **(extra or {})})


# ---- the chat ------------------------------------------------------------------------------------------------------------------------------
def _thesis(requested) -> dict:
    tid = requested if isinstance(requested, str) and requested in thesis_mod.available() else None
    return thesis_mod.load(thesis_mod.resolve(tid))


# The model client is built here so a test can replace it without a key.
def make_client(s):
    return None if not aava_llm.available() else aava_llm.make_client(s)


def _turn_stream(turn: aava_llm.Turn, request: Request, th: dict, question: str):
    try:
        failed = None
        for ev in turn.events():
            if ev["event"] == "error":
                failed = ev["data"]
                break
            yield sse(ev["event"], ev["data"])
        if failed is not None:
            yield from _error_stream(request, th, question, failed["kind"], failed["message"])
    except Exception:  # noqa: BLE001
        log.exception("aava stream failed")
        yield from _error_stream(request, th, question, "internal", "Aava hit a snag.")
    finally:
        turn.ctx.close()


@router.post("/api/aava/chat")
async def aava_chat(request: Request):
    if request.headers.get(DEMO_HEADER) != "1":
        return JSONResponse({"error": "the Aava chat is part of the demo: open the site with ?demo=1"}, status_code=403, headers={"Cache-Control": "no-store"})
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "send a JSON body {messages, view, thesis}"}, status_code=400)
    s = aava_llm.settings()
    try:
        messages = aava_llm.clean_messages(body.get("messages"), s)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    th = _thesis(body.get("thesis"))
    question = messages[-1]["content"]
    page_company = body.get("company") if isinstance(body.get("company"), str) and 0 < len(body["company"]) <= 40 else None

    if not aava_llm.available():
        return _refuse(request, th, question, "no_key", "Aava's reasoning is not switched on, so here is the radar's own answer.", 200)
    refused = limiter.check(client_ip(request), s.rate_per_min, s.daily_cap)
    if refused == "rate":
        return _refuse(request, th, question, "rate", "That is a lot of questions in a minute. Here is the radar's own answer; try Aava again shortly.", 429, {"Retry-After": "30"})
    if refused == "cap":
        return _refuse(request, th, question, "cap", "Aava has answered all the questions it can for today. Here is the radar's own answer.", 429, {"Retry-After": "3600"})

    turn = aava_llm.Turn(messages, th, view=body.get("view"), page_company=page_company, client=make_client(s), s=s)
    return StreamingResponse(_turn_stream(turn, request, th, question), media_type="text/event-stream", headers=SSE_HEADERS)


# ---- the spoken answer (optional) ---------------------------------------------------------------------------------------------------------
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def speakable(text: str) -> str:
    t = _MD_LINK.sub(r"\1", text or "")
    t = re.sub(r"[*_`#>]+", "", t)
    return " ".join(t.split())


_DATE = re.compile(r"\b(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})\b")
_ORDINALS = ("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth "
             "seventeenth eighteenth nineteenth twentieth twenty-first twenty-second twenty-third twenty-fourth twenty-fifth twenty-sixth "
             "twenty-seventh twenty-eighth twenty-ninth thirtieth thirty-first").split()
_LEGAL_SUFFIX = re.compile(r"(?<=\w) (?:Oy|Oyj|Ab|Abp|Ltd|ApS|GmbH)\b")


def _spoken_date(m: re.Match) -> str:
    day, month, year = int(m.group(1)), m.group(2), m.group(3)
    if not 1 <= day <= 31:
        return m.group(0)
    said = f"{month} {_ORDINALS[day - 1]}"
    return said if year == str(datetime.now(timezone.utc).year) else f"{said}, {year}"


def spoken(text: str, model: str = "") -> str:
    """The answer as a person says it out loud: markdown off, dates spoken ("October eleventh", the year only when it is not this year),
    legal-form suffixes dropped ("Since Labs", not "Since Labs Oy"), and on eleven_v3 one delivery cue up front, which that model performs
    rather than reads. Older models would read a cue aloud, so they get none."""
    t = _DATE.sub(_spoken_date, speakable(text))
    t = " ".join(_LEGAL_SUFFIX.sub("", t).split())
    return f"[warmly] {t}" if t and model.startswith("eleven_v3") else t


def _tts_request(s, text: str) -> tuple[str, dict]:
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{quote(s.voice_id, safe='')}/stream"
           f"?output_format={quote(s.voice_format, safe='')}")
    vs = {"stability": s.voice_stability, "similarity_boost": s.voice_similarity}
    if not s.voice_model.startswith("eleven_v3"):          # eleven_v3 takes stability and similarity only
        vs.update(style=s.voice_style, use_speaker_boost=True)
    return url, {"text": text, "model_id": s.voice_model, "voice_settings": vs}


def _audio(url: str, payload: dict, key: str, keep: list | None = None):
    """MP3 bytes from ElevenLabs as they arrive; nothing on an error (the page then falls back to the browser voice). `keep` collects the bytes."""
    import httpx

    try:
        with httpx.stream("POST", url, json=payload, headers={"xi-api-key": key, "Accept": "audio/mpeg"}, timeout=30.0) as r:
            if r.status_code != 200:
                log.warning("ElevenLabs answered %s", r.status_code)
                return
            for chunk in r.iter_bytes():
                if keep is not None:
                    keep.append(chunk)
                yield chunk
    except Exception as e:  # noqa: BLE001
        log.warning("ElevenLabs stream failed: %s", type(e).__name__)


async def _tts_text(request: Request):
    """(settings, key, spoken text) for a voice request, or the JSONResponse that refuses it. The daily character cap is charged here."""
    if request.headers.get(DEMO_HEADER) != "1":
        return JSONResponse({"error": "demo flag off"}, status_code=403)
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return JSONResponse({"error": "the spoken voice is not configured"}, status_code=404)
    s = aava_llm.settings()
    try:
        body = await request.json()
        text = spoken(str(body.get("text") or ""), s.voice_model)[:1200]
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "send {text}"}, status_code=400)
    if not text:
        return JSONResponse({"error": "no text"}, status_code=400)
    if not limiter.tts(len(text), s.tts_daily_chars):
        return JSONResponse({"error": "the daily limit of spoken characters is used up; the browser voice is used instead"}, status_code=429)
    return s, key, text


@router.post("/api/aava/tts")
async def aava_tts(request: Request):
    got = await _tts_text(request)
    if isinstance(got, JSONResponse):
        return got
    s, key, text = got
    url, payload = _tts_request(s, text)
    return StreamingResponse(_audio(url, payload, key), media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


# The page's audio element plays a GET address as the bytes arrive, so speech starts within a second instead of after the whole file.
# prepare takes the text (POST, demo header, cap) and hands back a one-off address; play streams it and keeps the bytes, so a second
# request for the same address (a browser re-reading the start) is served from memory instead of being spoken, and paid for, twice.
TTS_TOKEN_TTL_S = 300
_tts_tokens: dict[str, dict] = {}
_tts_lock = threading.Lock()


@router.post("/api/aava/tts/prepare")
async def aava_tts_prepare(request: Request):
    import secrets

    got = await _tts_text(request)
    if isinstance(got, JSONResponse):
        return got
    s, _key, text = got
    url, payload = _tts_request(s, text)
    token = secrets.token_urlsafe(18)
    now = time.time()
    with _tts_lock:
        for k in [k for k, v in _tts_tokens.items() if now - v["at"] > TTS_TOKEN_TTL_S]:
            del _tts_tokens[k]
        while len(_tts_tokens) >= 50:
            del _tts_tokens[min(_tts_tokens, key=lambda k: _tts_tokens[k]["at"])]
        _tts_tokens[token] = {"at": now, "url": url, "payload": payload, "audio": None}
    return {"url": f"/api/aava/tts/play/{token}"}


@router.get("/api/aava/tts/play/{token}")
def aava_tts_play(token: str):
    with _tts_lock:
        item = _tts_tokens.get(token)
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if item is None or time.time() - item["at"] > TTS_TOKEN_TTL_S or not key:
        return JSONResponse({"error": "no such audio, or it expired"}, status_code=404)
    headers = {"Cache-Control": "no-store"}
    if item["audio"] is not None:
        return StreamingResponse(iter([item["audio"]]), media_type="audio/mpeg", headers=headers)
    chunks: list = []

    def tee():
        yield from _audio(item["url"], item["payload"], key, chunks)
        if chunks:
            item["audio"] = b"".join(chunks)

    return StreamingResponse(tee(), media_type="audio/mpeg", headers=headers)
