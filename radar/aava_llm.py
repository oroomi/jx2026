"""Aava on a reasoning model (PROJECT_RULES D61). One chat turn = a short agent loop over the Messages API: the model reads the conversation, calls
the read-only tools of radar.aava_tools (search the home list, open a company, explain a match, list organisations, look at the visitor's screen,
set the page's filters), and writes the answer. The answer is streamed, then checked against what the tools returned (radar.aava_entities).

Nothing here is needed to run the site. Without ANTHROPIC_API_KEY in the environment (the service's EnvironmentFile holds it; this module reads
os.environ and nothing else) `available()` is False, the page never shows the chat, and the deterministic Aava and /api/ask run as before.

Settings: config/aava_llm.yaml holds every default; the environment variable of the same name overrides it (AAVA_MODEL, AAVA_THINKING_BUDGET,
AAVA_MAX_TOKENS, AAVA_TIMEOUT_S, AAVA_DAILY_CAP, AAVA_RATE_PER_MIN, AAVA_EFFORT, AAVA_MAX_STEPS, AAVA_TURN_DEADLINE_S, AAVA_TTS_DAILY_CHARS,
ELEVENLABS_VOICE_ID_LIVE). The system prompt is config/aava_prompt.md.

Thinking: models that take a token budget get thinking={"type": "enabled", "budget_tokens": N}; the 4.6 and newer models reject a budget with a 400,
so they get thinking={"type": "adaptive"} and an effort level read from the budget (config `effort_from_budget`) or from AAVA_EFFORT. If the API still
rejects the thinking parameters for the model, the call is retried once without them, logged, and remembered for the process.

The turn is a generator of events {"event", "data"}: status, delta, action, entities, followups, done, error. The SSE route is in radar/routes/aava_chat.py.

CLI:  python3 -m radar.aava_llm selftest "Which Finnish aquaculture startups should A'Pelago meet?" [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml

from radar import aava_entities, aava_tools, thesis as thesis_mod

log = logging.getLogger("aava.llm")
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "aava_llm.yaml"
PROMPT_PATH = ROOT / "config" / "aava_prompt.md"
EXIT_BLOCKED = 3
# Text the model writes in a turn that also calls data tools is an interim note ("let me check ..."): it is held back and never shown. Only the text of the
# turn that ends the loop (no data tool in it) is the answer. Its closing `Follow-ups: a? | b? | c?` line becomes the page's buttons (aava_tools.split_followups).
# The two notes below are the only messages the code adds.
LAST_ROUND_NOTE = ("This is your last round. Do not call a data tool again: write the answer now from what the tools returned, ending with the Follow-ups line.")
ANSWER_NOW = ("Write your answer now, in this turn, from the tool results you already have: 2 to 4 sentences that name the companies with one concrete fact each, then why, "
              "then one next step, then the Follow-ups line. Do not call a tool.")
ANSWER_SHAPE = ("Answer shape, every time: three short paragraphs (the direct answer in at most 4 sentences naming at most 3 companies, why in at most 2 sentences, "
                "the next step in 1 sentence), about 100 words in all, no bold, no bullets, then the Follow-ups line. Nothing is written before the tool calls are done.")
TOOL_LABELS = {"search_startups": "searching the list", "get_startup": "reading the company record", "explain_match": "checking the match",
               "list_organisations": "looking up organisations", "get_current_view": "looking at your screen", "apply_filters": "setting the filters"}
_NO_THINKING: set[str] = set()      # models whose API rejected the thinking parameters (this process): later calls skip them


# ---- settings ---------------------------------------------------------------------------------------------------------------------------
@dataclass
class Settings:
    model: str
    thinking_budget: int
    max_tokens: int
    timeout_s: float
    daily_cap: int
    rate_per_min: int
    effort: str
    max_steps: int
    turn_deadline_s: float
    tts_daily_chars: int
    voice_id: str
    limits: dict = field(default_factory=dict)
    budget_models: list = field(default_factory=list)
    effort_from_budget: list = field(default_factory=list)
    prices: dict = field(default_factory=dict)


_yaml_cache: tuple[float, dict] | None = None


def _yaml() -> dict:
    global _yaml_cache
    m = CONFIG_PATH.stat().st_mtime
    if _yaml_cache is None or _yaml_cache[0] != m:
        _yaml_cache = (m, yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {})
    return _yaml_cache[1]


def settings() -> Settings:
    """config/aava_llm.yaml with the environment on top, read on every call so the service picks up a changed EnvironmentFile after a restart and tests can set it."""
    y = _yaml()
    d = y["defaults"]

    def get(name: str, cast):
        raw = os.environ.get(name)
        if raw is not None and str(raw).strip() != "":
            try:
                return cast(str(raw).strip())
            except (TypeError, ValueError):
                log.warning("%s=%r is not a valid %s; the default is used", name, raw, cast.__name__)
        v = d.get(name)
        return cast(v) if v is not None and v != "" else cast() if cast is str else None

    return Settings(
        model=get("AAVA_MODEL", str), thinking_budget=get("AAVA_THINKING_BUDGET", int), max_tokens=get("AAVA_MAX_TOKENS", int),
        timeout_s=get("AAVA_TIMEOUT_S", float), daily_cap=get("AAVA_DAILY_CAP", int), rate_per_min=get("AAVA_RATE_PER_MIN", int),
        effort=get("AAVA_EFFORT", str) or "", max_steps=get("AAVA_MAX_STEPS", int), turn_deadline_s=get("AAVA_TURN_DEADLINE_S", float),
        tts_daily_chars=get("AAVA_TTS_DAILY_CHARS", int), voice_id=get("ELEVENLABS_VOICE_ID_LIVE", str),
        limits=dict(y.get("limits") or {}), budget_models=list(y.get("budget_models") or []),
        effort_from_budget=list(y.get("effort_from_budget") or []), prices=dict(y.get("prices") or {}))


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def api_key_present() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def available() -> bool:
    """True when a key is in the environment and the SDK is installed. A boolean only: the key is never returned, logged or echoed."""
    return not kill_switch_on() and can_call()


def kill_switch_on() -> bool:
    """Kill switch without a restart: the file data/AAVA_LLM_OFF (in RADAR_DATA_DIR) turns the reasoning Aava off; the deterministic Aava answers."""
    return (Path(os.environ.get("RADAR_DATA_DIR") or Path(__file__).resolve().parent.parent / "data") / "AAVA_LLM_OFF").exists()


def can_call() -> bool:
    """A key is in the environment and the SDK is installed (the kill switch is not looked at)."""
    if not api_key_present():
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def status() -> dict:
    s = settings()
    return {"available": available(), "model": s.model, "tts": bool(os.environ.get("ELEVENLABS_API_KEY", "").strip())}


def make_client(s: Settings):
    import anthropic
    return anthropic.Anthropic(timeout=s.timeout_s, max_retries=1)   # the key is read from ANTHROPIC_API_KEY by the SDK


# ---- thinking parameters ------------------------------------------------------------------------------------------------------------------
def takes_budget(model: str, s: Settings) -> bool:
    return any(re.search(p, model) for p in s.budget_models)


def effort_for(s: Settings) -> str:
    if s.effort in ("low", "medium", "high", "xhigh", "max"):
        return s.effort
    if s.thinking_budget <= 0:
        return "low"
    for top, level in s.effort_from_budget:
        if top is None or s.thinking_budget <= top:
            return level
    return "high"


def thinking_params(s: Settings) -> dict:
    if s.thinking_budget <= 0 or s.model in _NO_THINKING:
        return {}
    if takes_budget(s.model, s):
        return {"thinking": {"type": "enabled", "budget_tokens": max(1024, s.thinking_budget)}}
    return {"thinking": {"type": "adaptive"}, "output_config": {"effort": effort_for(s)}}


def request_params(s: Settings, system_extra: str, messages: list, final_step: bool = False, tools: list | None = None) -> dict:
    """The Messages request. `final_step` forbids tools (tool_choice none): used only for the call that must produce a missing answer."""
    thinking = thinking_params(s)
    kw = {"model": s.model, "max_tokens": s.max_tokens + (s.thinking_budget if thinking else 0), "tools": tools if tools is not None else aava_tools.TOOLS, "messages": messages,
          "system": [{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}, {"type": "text", "text": system_extra}], **thinking}
    if final_step:
        kw["tool_choice"] = {"type": "none"}
    return kw


# ---- input hygiene -------------------------------------------------------------------------------------------------------------------------
def clean_messages(raw, s: Settings) -> list[dict]:
    """The session history as the API wants it: user/assistant text only, the last `history_turns`, the newest a user message of at most `input_chars`.
    Raises ValueError with a message safe to show."""
    lim = s.limits
    if not isinstance(raw, list) or not raw:
        raise ValueError("messages must be a non-empty list")
    out: list[dict] = []
    for m in raw[-int(lim.get("history_turns", 12)):]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant") or not isinstance(m.get("content"), str):
            raise ValueError("each message needs a role (user or assistant) and a text content")
        text = " ".join(m["content"].split())
        if text:
            out.append({"role": m["role"], "content": text[: int(lim.get("history_chars", 1500))]})
    while out and out[0]["role"] != "user":
        out.pop(0)
    if not out or out[-1]["role"] != "user":
        raise ValueError("the last message must be from the user")
    if len(" ".join(raw[-1]["content"].split())) > int(lim.get("input_chars", 500)):
        raise ValueError(f"a question can be at most {int(lim.get('input_chars', 500))} characters")
    return out


def _system_extra(ctx: aava_tools.ToolContext, today: str) -> str:
    th = ctx.th
    lines = [f"Today is {today}. Sector file: {th.get('title') or th.get('id')}. The investor partners are A'Pelago and Redstone Blue.",
             ANSWER_SHAPE]
    if ctx.page_company:
        conn = ctx.conn()
        d = None
        try:
            from radar import store
            d = store.company(conn, ctx.page_company) if conn is not None else None
        except Exception:  # noqa: BLE001
            d = None
        if d:
            nm = d["company"]["name"]
            ctx.see(ctx.page_company, nm)
            lines.append(f"The person is on the page of {nm} (company_key {ctx.page_company}). 'It', 'they' and 'this company' mean {nm}; call get_startup for its record before answering about it.")
    return "\n".join(lines)


# ---- the turn --------------------------------------------------------------------------------------------------------------------------
class Turn:
    """One chat turn. `events()` yields {"event", "data"} dicts; after it ends `.usage`, `.steps`, `.answer`, `.ctx` describe what happened."""

    def __init__(self, messages: list[dict], thesis: dict, view: dict | None = None, page_company: str | None = None, client=None, s: Settings | None = None):
        self.s = s or settings()
        self.messages = [dict(m) for m in messages]
        self.user_text = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        self.ctx = aava_tools.ToolContext(thesis, view=view, page_company=page_company, limits=self.s.limits)
        self.tools = aava_tools.tools_for(thesis)
        self._client = client
        self.usage = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        self.steps = 0
        self.answer = ""
        self.interim: list[str] = []        # text written in turns that also called data tools: kept for the log and the selftest, never shown
        self.trace: list[dict] = []         # one entry per model call: seconds, stop reason, tools, characters of text, tokens (the selftest prints it)
        self.result: dict | None = None
        self.ms = 0

    # -- helpers ---------------------------------------------------------------------------------------------------------------------------
    def _add_usage(self, u) -> None:
        for k in self.usage:
            self.usage[k] += int(getattr(u, k, 0) or 0)

    def _error(self, kind: str, message: str, **extra) -> dict:
        return {"event": "error", "data": {"kind": kind, "message": message, **extra}}

    def _nudge(self, text: str) -> None:
        """Add an instruction to the user's side of the conversation: to the tool results the last user message already holds, or as a message of its own."""
        block = {"type": "text", "text": text}
        last = self.messages[-1] if self.messages else None
        if last is not None and last["role"] == "user":
            c = last["content"]
            self.messages[-1] = {"role": "user", "content": [*c, block] if isinstance(c, list) else [{"type": "text", "text": c}, block]}
        else:
            self.messages.append({"role": "user", "content": [block]})

    def _one_call(self, kw: dict, state: dict):
        """Stream one Messages call. Yields status events only: the text of the call is held back, because whether it is the answer or an interim note
        is only known when the call ends (a tool_use block follows an interim note). Returns the final message."""
        client = self._client or make_client(self.s)
        thinking_announced = False
        with client.messages.stream(**kw) as stream:
            for ev in stream:
                t = getattr(ev, "type", "")
                if t == "content_block_start":
                    blk = ev.content_block
                    bt = getattr(blk, "type", "")
                    if bt in ("thinking", "redacted_thinking") and not thinking_announced:
                        thinking_announced = True
                        if state["status"] != "thinking":
                            state["status"] = "thinking"
                            yield {"event": "status", "data": {"state": "thinking"}}
                    elif bt == "tool_use":
                        name = getattr(blk, "name", "")
                        if name in TOOL_LABELS:
                            state["status"] = name
                            yield {"event": "status", "data": {"state": "tool", "tool": name, "label": TOOL_LABELS[name]}}
            final = stream.get_final_message()
        return final

    # -- the loop --------------------------------------------------------------------------------------------------------------------------
    def events(self) -> Iterator[dict]:
        """The turn. Rounds of tool calls (at most `max_steps` model calls; the last one is told to answer), then the answer: the text of the call that
        ends the loop. If that call has no text (nothing but suggest_followups, or empty), one more call must answer (tool_choice none); if there is
        still none the turn ends in an `empty` error and the route falls back to the deterministic answer."""
        import datetime

        try:
            import anthropic as anthropic_mod
        except ImportError:   # a test with a stub client can run without the SDK
            anthropic_mod = None
        s, ctx = self.s, self.ctx
        t0 = time.monotonic()
        deadline = t0 + s.turn_deadline_s
        state = {"status": "thinking"}
        answer = ""
        err: dict | None = None
        truncated = False
        budget = s.max_steps               # model calls allowed; one more is allowed once, to get a missing answer
        extra_used = force_answer = False
        try:
            if self._client is None and not available():
                yield self._error("no_key", "Aava's reasoning is not switched on.")
                return
            yield {"event": "status", "data": {"state": "thinking", "label": "looking at the radar"}}
            aava_tools.ensure_warm(ctx.th)          # a rebuilt store is warmed in the background while the first model call runs
            extra = _system_extra(ctx, datetime.date.today().isoformat())
            while True:
                if time.monotonic() > deadline:
                    err = self._error("timeout", "Aava took too long on that one.")
                    break
                if self.steps >= budget:
                    err = self._error("steps", "Aava could not finish that one.")
                    break
                self.steps += 1
                note = f"\n\n{LAST_ROUND_NOTE}" if self.steps >= budget and not force_answer else ""
                kw = request_params(s, extra + note, self.messages, final_step=force_answer, tools=self.tools)
                attempt = 0
                while True:
                    try:
                        final = yield from self._one_call(kw, state)
                        break
                    except Exception as e:  # noqa: BLE001  (classified below)
                        bad = anthropic_mod is not None and isinstance(e, anthropic_mod.BadRequestError)
                        if bad and attempt == 0 and ("thinking" in kw or "output_config" in kw) and re.search(r"thinking|budget_tokens|effort|output_config", str(e), re.I):
                            attempt = 1
                            _NO_THINKING.add(s.model)
                            for k in ("thinking", "output_config"):
                                kw.pop(k, None)
                            kw["max_tokens"] = s.max_tokens
                            log.warning("aava: the API rejected the thinking parameters for %s (%s); retrying once without them", s.model, str(e)[:200])
                            continue
                        raise
                self._add_usage(getattr(final, "usage", None))
                content = list(getattr(final, "content", []) or [])
                text = "".join(getattr(b, "text", "") for b in content if getattr(b, "type", "") == "text").strip()
                stop = getattr(final, "stop_reason", None)
                u = getattr(final, "usage", None)
                self.trace.append({"step": self.steps, "end_s": round(time.monotonic() - t0, 1), "stop": stop, "text_chars": len(text), "forced": force_answer,
                                   "tools": [getattr(b, "name", "") for b in content if getattr(b, "type", "") == "tool_use"], "out_tokens": int(getattr(u, "output_tokens", 0) or 0)})
                if stop == "tool_use":
                    uses = [b for b in content if getattr(b, "type", "") == "tool_use"]
                    if not uses:    # a tool_use stop with no tool call in it: nothing to answer, nothing to send back
                        err = self._error("stop", "Aava stopped early.")
                        break
                    only_followups = all(b.name == "suggest_followups" for b in uses)
                    if only_followups and text:
                        for b in uses:      # the answer with its follow-ups beside it: run the follow-ups tool and stop, no second round trip
                            aava_tools.run_tool(ctx, b.name, b.input)
                            ctx.calls[-1]["args"] = json.dumps(b.input, ensure_ascii=False)[:300]
                        answer = text
                        break
                    if text:
                        self.interim.append(text)       # an interim note between tool calls: never shown
                    self.messages.append({"role": "assistant", "content": content})   # thinking blocks go back unchanged
                    results = []
                    for b in uses:
                        before = len(ctx.actions)
                        body, ok = aava_tools.run_tool(ctx, b.name, b.input)
                        ctx.calls[-1]["args"] = json.dumps(b.input, ensure_ascii=False)[:300]
                        results.append({"type": "tool_result", "tool_use_id": b.id, "content": body, **({} if ok else {"is_error": True})})
                        for act in ctx.actions[before:]:
                            yield {"event": "action", "data": act}
                    self.messages.append({"role": "user", "content": results})
                    if only_followups or self.steps >= budget:     # no answer written yet, or no round left to write it in: the next call must answer
                        if self.steps >= budget:
                            if extra_used:
                                err = self._error("steps", "Aava could not finish that one.")
                                break
                            extra_used, budget = True, budget + 1
                        force_answer = True
                        self._nudge(ANSWER_NOW)
                    continue
                if stop == "refusal":
                    err = self._error("refusal", "Aava could not answer that one.")
                elif stop == "max_tokens":
                    truncated = True
                    if text:
                        answer = text
                    else:
                        err = self._error("truncated", "Aava ran out of room before it could answer.")
                elif stop not in ("end_turn", "stop_sequence", None):
                    err = self._error("stop", "Aava stopped early.")
                elif text:
                    answer = text
                elif force_answer:
                    err = self._error("empty", "Aava did not write an answer.")
                else:                   # the loop ended with nothing written: one more call that has to answer
                    if self.steps >= budget:
                        extra_used, budget = True, budget + 1
                    force_answer = True
                    self._nudge(ANSWER_NOW)
                    continue
                break
        except Exception as e:  # noqa: BLE001
            err = self._classify(e, anthropic_mod)
        self.ms = round((time.monotonic() - t0) * 1000)
        if err is None and not answer.strip():
            err = self._error("empty", "Aava did not write an answer.")
        if err is not None:
            self._log(err["data"]["kind"])
            yield err
            return
        answer, asked = aava_tools.split_followups(answer, s.limits)       # the Follow-ups line is buttons, never text
        if asked:
            ctx.followups = asked
        if not answer.strip():
            err = self._error("empty", "Aava did not write an answer.")
            self._log("empty")
            yield err
            return
        guard = aava_entities.StreamGuard(ctx.seen, ctx.urls)    # the same link rules as the final check, applied to what is sent
        safe = guard.feed(answer) + guard.flush()
        if safe:
            yield {"event": "delta", "data": {"text": safe}}
        checked = aava_entities.enforce(answer, ctx.seen, ctx.urls, orgs=ctx.seen_orgs, user_text=self.user_text)
        self.answer = checked["text"]
        names = {k: ctx.seen[k] for k in checked["keys"]}
        yield {"event": "entities", "data": {"keys": checked["keys"], "names": names}}
        if ctx.followups:
            yield {"event": "followups", "data": {"questions": ctx.followups}}
        self.result = {"text": checked["text"], "keys": checked["keys"], "unverified": checked["unverified"], "truncated": truncated, "model": s.model,
                       "sources": aava_tools.source_lines(ctx, checked["keys"], checked["text"])}
        self._log("ok", flagged=checked["flagged"])
        yield {"event": "done", "data": {**self.result, "usage": dict(self.usage), "steps": self.steps, "ms": self.ms}}

    def _classify(self, e: Exception, anthropic_mod) -> dict:
        kind, msg = "api", "Aava's reasoning is not available right now."
        if anthropic_mod is not None:
            if isinstance(e, anthropic_mod.APITimeoutError):
                kind, msg = "timeout", "Aava took too long to answer."
            elif isinstance(e, anthropic_mod.RateLimitError):
                kind, msg = "busy", "Aava is busy right now."
            elif isinstance(e, anthropic_mod.APIStatusError):
                log.error("aava: Messages API answered %s (request %s)", getattr(e, "status_code", "?"), getattr(e, "request_id", None))
        log.warning("aava turn failed: %s", type(e).__name__)
        return self._error(kind, msg)

    def _log(self, outcome: str, flagged: list | None = None) -> None:
        log.info("aava turn %s", json.dumps({"outcome": outcome, "model": self.s.model, "steps": self.steps, "ms": self.ms, "usage": self.usage,
                                              "tools": [c["name"] for c in self.ctx.calls], "interim_notes_dropped": len(self.interim), "flagged_names": flagged or [], "thesis": self.ctx.th.get("id")}))


def cost_usd(usage: dict, model: str, s: Settings | None = None) -> float | None:
    """Estimated dollars from token counts and the per-million prices in config/aava_llm.yaml (read from Anthropic's pricing page)."""
    p = ((s or settings()).prices or {}).get(model)
    if not p:
        return None
    return (usage["input_tokens"] * p["input"] + usage["output_tokens"] * p["output"] + usage["cache_creation_input_tokens"] * p["cache_write_5m"]
            + usage["cache_read_input_tokens"] * p["cache_read"]) / 1_000_000


# ---- selftest ----------------------------------------------------------------------------------------------------------------------------
def _selftest(question: str, dry: bool, thesis_id: str | None) -> int:
    s = settings()
    th = thesis_mod.load(thesis_mod.resolve(thesis_id)) if thesis_id else thesis_mod.load()
    msgs = clean_messages([{"role": "user", "content": question}], s)
    ctx_probe = aava_tools.ToolContext(th, limits=s.limits)
    kw = request_params(s, _system_extra(ctx_probe, time.strftime("%Y-%m-%d")), msgs, tools=aava_tools.tools_for(th))
    ctx_probe.close()
    print(f"model {s.model}  thinking {json.dumps(kw.get('thinking'))}  effort {json.dumps(kw.get('output_config'))}  max_tokens {kw['max_tokens']}  "
          f"timeout {s.timeout_s}s  max_steps {s.max_steps}  tools {[t['name'] for t in kw['tools']]}")
    if dry:
        print(f"DRY RUN: no API call was made. System prompt {len(system_prompt())} characters, tool schemas {len(json.dumps(kw['tools']))} characters.")
        return 0
    if not can_call():
        print("BLOCKED: ANTHROPIC_API_KEY is not set in the environment (or the anthropic package is missing), so no turn was run. Put the key in the service's "
              "EnvironmentFile (unit hack-jx2026) and export it in this shell to run the selftest.", file=sys.stderr)
        return EXIT_BLOCKED
    if kill_switch_on():
        print("note: the kill switch file data/AAVA_LLM_OFF exists, so the site is serving the deterministic Aava; the selftest calls the model directly and does not touch the file.")
    warm_s = aava_tools.warm(th)      # the live server warms these caches at startup; the clock below does not include them
    print(f"warm-up (done at server start in production): {warm_s:.1f}s")
    turn = Turn(msgs, th, client=make_client(s), s=s)
    first_status = first_text = None
    t0 = time.monotonic()
    for ev in turn.events():
        now = time.monotonic() - t0
        if first_status is None and ev["event"] == "status":
            first_status = now
        if first_text is None and ev["event"] == "delta":
            first_text = now
        if ev["event"] == "status":
            print(f"[{now:5.1f}s] status {json.dumps(ev['data'])}")
        elif ev["event"] in ("action", "followups", "entities", "error"):
            print(f"[{now:5.1f}s] {ev['event']} {json.dumps(ev['data'], ensure_ascii=False)}")
    print("\n--- answer ---\n" + (turn.answer or "(none)"))
    if turn.interim:
        print(f"\n--- interim notes the model wrote between tool calls (dropped, never shown): {len(turn.interim)} ---")
        for n in turn.interim:
            print("  " + n[:200])
    print("\n--- model calls ---")
    for t in turn.trace:
        print(f"step {t['step']}: ended at {t['end_s']}s  stop={t['stop']}  text {t['text_chars']} chars  out {t['out_tokens']} tokens  tools {t['tools']}{'  (forced answer)' if t['forced'] else ''}")
    print("\n--- tool calls ---")
    for c in turn.ctx.calls:
        print(f"{c['name']:<20} {c['ms']:>6} ms  ok={c['ok']}  {c.get('args', '')}")
    u = turn.usage
    c = cost_usd(u, s.model, s)
    ft = f"{first_text:.1f}s" if first_text is not None else "none"
    fs = f"{first_status:.1f}s" if first_status is not None else "none"
    print(f"\nlatency {turn.ms / 1000:.1f}s (first status {fs}, answer text {ft})  steps {turn.steps}  tokens in {u['input_tokens']} out {u['output_tokens']} "
          f"cache write {u['cache_creation_input_tokens']} read {u['cache_read_input_tokens']}  cost ~" + (f"${c:.4f}" if c is not None else "unknown"))
    turn.ctx.close()
    return 0 if turn.result else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.aava_llm", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("selftest", help="run one real turn (needs ANTHROPIC_API_KEY) and print the answer, tool calls, latency and token usage")
    st.add_argument("question")
    st.add_argument("--dry-run", action="store_true", help="print the request settings and sizes; make no API call")
    st.add_argument("--thesis", default=None, help="sector id (default: the default thesis)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    return _selftest(a.question, a.dry_run, a.thesis)


if __name__ == "__main__":
    raise SystemExit(main())
