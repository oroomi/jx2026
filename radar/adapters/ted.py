"""TED (Tenders Electronic Daily) contract award notices -> public_contract signals for the WINNER.

The Baltic-wide twin of Hilma. Public API, no key: POST https://api.ted.europa.eu/v3/notices/search with an expert-search
query (checked 16 Oct 2026). One query covers the thesis CPV prefixes (thesis `ted_cpv`) and the thesis countries
(`countries`, matched against the WINNER's country). A country whose `country_depth` lists "contracts" (a national
procurement archive, Finland's Hilma) is skipped so no award is counted twice.

Cautious readings, stored as such: only winners TED marks as micro or small enterprises are kept (the radar looks for young
small companies; a large winner is not a discovery); the date is the notice publication date (TED's decision date is
not used); the value is the notice total and is kept only when the notice has exactly one winner; a winner name is paired
with its country by position in the notice, and a notice whose two lists differ in length and whose countries differ is
skipped. The company key is country plus folded name (TED notices carry no register id we can verify).
Politeness: 1 request per 2 s, responses cached under data/cache/ted/, HTTP 403/429 stops the run (BLOCKED, not a crash).
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from datetime import date
from pathlib import Path

import httpx

from radar import emit
from radar import thesis as thesis_mod
from radar.adapters.declared import slug

NAME = "ted"
PHASE = 1
ROOT = Path(__file__).resolve().parent.parent.parent
API = "https://api.ted.europa.eu/v3/notices/search"
NOTICE_URL = "https://ted.europa.eu/en/notice/-/detail/{}"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
PAGE = 250
MAX_PAGES = 20
FROM = "2025-01-01"
SMALL = ("micro", "small")
FIELDS = ["publication-number", "publication-date", "notice-title", "buyer-name", "winner-name", "winner-country",
          "winner-size", "total-value", "tender-value-cur"]
ISO3 = {"FI": "FIN", "SE": "SWE", "EE": "EST", "LV": "LVA", "LT": "LTU", "DK": "DNK", "DE": "DEU", "PL": "POL", "NO": "NOR",
        "IS": "ISL", "NL": "NLD", "BE": "BEL", "FR": "FRA", "ES": "ESP", "PT": "PRT", "IT": "ITA", "IE": "IRL", "AT": "AUT",
        "CZ": "CZE", "SK": "SVK", "HU": "HUN", "SI": "SVN", "HR": "HRV", "RO": "ROU", "BG": "BGR", "GR": "GRC", "CY": "CYP",
        "MT": "MLT", "LU": "LUX"}
_SUFFIX = re.compile(r"\b(oy|oyj|ab|abp|ltd|limited|as|a/s|aps|gmbh|inc|ky|tmi|sia|uab|ou|sp z o o|s a)\b\.?")


class Blocked(Exception):
    """HTTP 403 or 429: stop at once, keep what is stored."""


def fold(s) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", s)).strip()


def active_countries(thesis: dict) -> tuple[list[str], list[str]]:
    """(countries TED queries, countries skipped because a national contract archive covers them)."""
    use, skip = [], []
    for cc, depth in thesis_mod.country_depth(thesis).items():
        (skip if "contracts" in depth.lower() else use).append(cc) if cc in ISO3 else None
    return use, skip


def build_query(thesis: dict, countries: list[str], since: str = FROM) -> str | None:
    prefixes = [str(c["prefix"]) for c in thesis.get("ted_cpv") or [] if c.get("prefix")]
    if not prefixes or not countries:
        return None
    cpv = " OR ".join(f"classification-cpv={p}*" for p in prefixes)
    return (f"notice-type IN (can-standard can-social) AND winner-country IN ({' '.join(ISO3[c] for c in countries)}) "
            f"AND publication-date>={since.replace('-', '')} AND ({cpv})")


def _lang(d, order=("eng",)) -> str | None:
    """First text of a multilingual {lang: [..]} or {lang: text} field, English first."""
    if isinstance(d, str):
        return d.strip() or None
    if not isinstance(d, dict):
        return None
    for lang in [*order, *d]:
        v = d.get(lang)
        v = v[0] if isinstance(v, list) and v else v
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def parse_notice(n: dict) -> dict:
    """One TED search hit -> {pub, date, title, buyer, amount, winners:[{name, cc3, size}], skipped}. Pure, no network."""
    names = (n.get("winner-name") or {})
    lang = next(iter(names), None)
    names = [x.strip() for x in (names.get(lang) if lang else []) or [] if isinstance(x, str) and x.strip()]
    ccs = [str(x).upper() for x in n.get("winner-country") or []]
    sizes = [str(x).lower() for x in n.get("winner-size") or []]
    winners, skipped = [], 0
    if names and (len(ccs) == len(names) or len(set(ccs)) == 1):
        for i, nm in enumerate(names):
            cc = ccs[i] if len(ccs) == len(names) else ccs[0]
            size = sizes[i] if len(sizes) == len(names) else (sizes[0] if len(set(sizes)) == 1 and sizes else None)
            winners.append({"name": nm, "cc3": cc, "size": size})
    elif names:
        skipped = len(names)
    pub = str(n.get("publication-number") or "")
    d = str(n.get("publication-date") or "")[:10]
    total = n.get("total-value")
    cur = n.get("tender-value-cur") or []
    amount = float(total) if isinstance(total, (int, float)) and total > 0 and len(winners) == 1 and cur[:1] == ["EUR"] else None
    return {"pub": pub, "date": d, "title": _lang(n.get("notice-title")), "buyer": _lang(n.get("buyer-name")),
            "amount": amount, "winners": winners, "skipped": skipped}


def _detail(p: dict) -> str:
    base = f"{p['buyer'] or 'buyer not stated'}: {p['title'] or 'title not stated'}"
    return f"{base} (EUR {p['amount']:,.0f})" if p["amount"] else base


_last = 0.0


def search(query: str, page: int, cache: Path, client: httpx.Client | None = None) -> tuple[dict, bool]:
    """One cached search page. Returns (json, was_network_call). Raises Blocked on 403/429."""
    global _last
    body = {"query": query, "fields": FIELDS, "limit": PAGE, "page": page}
    f = cache / (hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16] + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")), False
    wait = 2.0 - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA}, timeout=60)
    try:
        r = client.post(API, json=body)
        _last = time.monotonic()
    finally:
        if own:
            client.close()
    if r.status_code in (403, 429):
        raise Blocked(f"HTTP {r.status_code} from {API}")
    r.raise_for_status()
    data = r.json()
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data, True


def run(conn: sqlite3.Connection, thesis: dict, client: httpx.Client | None = None, cache: Path | None = None,
        since: str = FROM) -> dict:
    cache = cache or thesis_mod.data_dir() / "cache" / NAME
    use, skip = active_countries(thesis)
    res = {"companies": 0, "signals": 0, "skipped": 0, "notices": 0, "requests": 0, "blocked": "",
           "by_country": {}, "skipped_countries": ",".join(skip), "skipped_large": 0}
    q = build_query(thesis, use, since)
    if q is None:
        res["note"] = "no ted_cpv in the thesis, or every country is covered by a national contract archive"
        return res
    cc2 = {v: k for k, v in ISO3.items()}
    declared = {fold(r[1]): r[0] for r in conn.execute("SELECT company_key, name FROM companies WHERE group_tag IN ('cohort','portfolio')")}
    new_keys: set[str] = set()
    try:
        page = 1
        while page <= MAX_PAGES:
            data, net = search(q, page, cache, client)
            res["requests"] += net
            hits = data.get("notices") or []
            for n in hits:
                res["notices"] += 1
                p = parse_notice(n)
                res["skipped"] += p["skipped"]
                if not p["pub"] or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["date"]):
                    res["skipped"] += len(p["winners"])
                    continue
                for w in p["winners"]:
                    cc = cc2.get(w["cc3"])
                    if cc not in use:
                        continue
                    key = declared.get(fold(w["name"]))
                    if key is None:
                        if w["size"] not in SMALL:
                            res["skipped_large"] += 1
                            continue
                        key = slug(cc, w["name"])
                        emit.upsert_company(conn, company_key=key, name=w["name"], source_url=NOTICE_URL.format(p["pub"]),
                                            country=cc, group_tag="feed")
                        new_keys.add(key)
                    if emit.emit_signal(conn, company_key=key, signal_type="public_contract", date=p["date"],
                                        source_url=NOTICE_URL.format(p["pub"]), confidence="high", adapter=NAME,
                                        detail=_detail(p), amount_eur=p["amount"]):
                        res["signals"] += 1
                        res["by_country"][cc] = res["by_country"].get(cc, 0) + 1
            if len(hits) < PAGE:
                break
            page += 1
    except Blocked as e:
        res["blocked"] = str(e)
    except (httpx.HTTPError, OSError, ValueError) as e:
        res["blocked"] = f"{type(e).__name__}: {e}"
    res["companies"] = len(new_keys)
    conn.commit()
    return res


if __name__ == "__main__":
    from radar import db

    th = thesis_mod.load()
    c = db.connect(thesis_mod.db_path(th))
    r = run(c, th)
    print(r)
    if r["blocked"]:
        print("BLOCKED:", r["blocked"])
