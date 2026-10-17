"""A scripted stand-in for anthropic.Anthropic: `client.messages.stream(**kw)` returns a context manager that yields the raw stream events of one
scripted model call and then `get_final_message()`. No network, no key. A script step is built with `call(...)` or is an Exception to raise.

    client = FakeClient([call(thinking=True, tools=[("search_startups", {"limit": 3})]), call(text=["Hello ", "there."], usage=(900, 120))])
"""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace as NS


def _delta(i, **kw):
    return NS(type="content_block_delta", index=i, delta=NS(**kw))


class _Stream:
    def __init__(self, events, final):
        self.events, self.final = events, final

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self.events)

    def get_final_message(self):
        return self.final


def call(text=None, tools=(), thinking=False, stop=None, usage=(1000, 100, 0, 0), chunk=None):
    """One model call. `text` is a string (split into small chunks, so a markdown link is cut across events) or a list of chunks; `tools` is
    [(name, input_dict)]; `usage` is (input, output, cache_write, cache_read) tokens."""
    events, content, i = [], [], 0
    if thinking:
        events += [NS(type="content_block_start", index=i, content_block=NS(type="thinking", thinking="", signature="")),
                   _delta(i, type="thinking_delta", thinking=""), _delta(i, type="signature_delta", signature="sig"),
                   NS(type="content_block_stop", index=i)]
        content.append(NS(type="thinking", thinking="", signature="sig"))
        i += 1
    if text is not None:
        chunks = text if isinstance(text, list) else [text[k:k + (chunk or 7)] for k in range(0, len(text), chunk or 7)]
        events.append(NS(type="content_block_start", index=i, content_block=NS(type="text", text="")))
        events += [_delta(i, type="text_delta", text=c) for c in chunks]
        events.append(NS(type="content_block_stop", index=i))
        content.append(NS(type="text", text="".join(chunks)))
        i += 1
    for n, (name, inp) in enumerate(tools):
        tid = f"toolu_{name}_{n}"
        events.append(NS(type="content_block_start", index=i, content_block=NS(type="tool_use", id=tid, name=name, input={})))
        events.append(_delta(i, type="input_json_delta", partial_json=json.dumps(inp)))
        events.append(NS(type="content_block_stop", index=i))
        content.append(NS(type="tool_use", id=tid, name=name, input=inp))
        i += 1
    u = NS(input_tokens=usage[0], output_tokens=usage[1], cache_creation_input_tokens=usage[2], cache_read_input_tokens=usage[3])
    return _Stream(events, NS(content=content, stop_reason=stop or ("tool_use" if tools else "end_turn"), usage=u))


class FakeMessages:
    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    def stream(self, **kw):
        snap = {k: (copy.deepcopy(v) if k in ("tools", "system") else list(v) if k == "messages" else v) for k, v in kw.items()}
        self.calls.append(snap)
        if not self.script:
            raise AssertionError("the model was called more often than the test scripted")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeClient:
    def __init__(self, script):
        self.messages = FakeMessages(script)


def tool_results(messages) -> list[dict]:
    """Every tool_result block the loop sent back, in order."""
    out = []
    for m in messages:
        if m["role"] == "user" and isinstance(m["content"], list):
            out += [b for b in m["content"] if b.get("type") == "tool_result"]
    return out
