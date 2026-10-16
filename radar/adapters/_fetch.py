"""Shared polite fetcher for the first-traction adapters: disk cache under data/cache/<adapter>/, one request per interval.
Not an adapter (no NAME); build.py skips it."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import httpx

UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
CACHE_ROOT = Path(__file__).resolve().parents[2] / "data" / "cache"
_last_call = 0.0


class Blocked(Exception):
    """The source could not be reached after retries (offline, 403, 5xx). Callers stop cleanly and report BLOCKED."""


def cached_get(adapter: str, url: str, *, interval: float = 2.0, retries: int = 3, params: dict | None = None,
               client: httpx.Client | None = None) -> tuple[object, bool]:
    """GET json, cached by URL. Returns (json, was_network_call). Retries with backoff 2, 4, 8 s; raises Blocked after that."""
    global _last_call
    key = url + "?" + json.dumps(params or {}, sort_keys=True)
    f = CACHE_ROOT / adapter / (hashlib.sha1(key.encode()).hexdigest()[:16] + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")), False
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    last: Exception | None = None
    try:
        for attempt in range(retries):
            wait = interval - (time.monotonic() - _last_call)
            if wait > 0:
                time.sleep(wait)
            try:
                r = client.get(url, params=params)
                _last_call = time.monotonic()
                r.raise_for_status()
                data = r.json() if r.content.strip() else []  # CDX answers an empty body when nothing is archived
                break
            except (httpx.HTTPError, ValueError) as e:
                _last_call = time.monotonic()
                last = e
                time.sleep(2 ** (attempt + 1))
        else:
            raise Blocked(f"{type(last).__name__}: {last}")
    finally:
        if own:
            client.close()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data, True
