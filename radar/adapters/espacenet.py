"""EPO Open Patent Services (OPS 3.2) -> patent signals for the declared Finnish companies.

For every Finnish company in data/declared/cohort_portfolio_companies.csv and data/declared/startups_universe.csv, one
applicant search (CQL pa="<name>") returns bibliographic records. A record counts only when one applicant's name, with
the legal form dropped, equals the company's name AND the record gives that applicant the country FI. One signal per
patent family, dated at the family's earliest filing (earliest priority or application date the records state),
linked to the Espacenet page of the publication that states it. No match, no signal.

Confidence (emit.py rule): exact legal name = medium; exact match on a declared name that is not a confirmed legal
name = low. Never high: a patent record carries no business id.

Machine access goes through OPS only. Espacenet's web search is for people (EPO fair use charter: robots are denied),
so this adapter never queries it; Espacenet appears only as the link a human opens. OPS needs a registered consumer
key, read from EPO_OPS_KEY and EPO_OPS_SECRET (the systemd EnvironmentFile). Without them the run is BLOCKED and sends
nothing. 1 request per 2 s, stop at the first 401/403/429, search responses cached under data/cache/espacenet/ (the
access token is never written to disk). Run: python3 -m radar.adapters.espacenet
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx

from radar import emit
from radar.adapters.businessfinland import norm_name
from radar.adapters.declared import slug

NAME = "espacenet"
SIGNAL_TYPE = "patent"  # emit.SIGNAL_TYPES entry for a patent filing; the feed, readiness and labels read this one
ROOT = Path(__file__).resolve().parents[2]
COHORT_CSV = ROOT / "data" / "declared" / "cohort_portfolio_companies.csv"
UNIVERSE_CSV = ROOT / "data" / "declared" / "startups_universe.csv"
CACHE = ROOT / "data" / "cache" / NAME
TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
ESPACENET_URL = "https://worldwide.espacenet.com/patent/search?q=pn%3D{pn}"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
MIN_INTERVAL = 2.0
PAGE_SIZE = 100
MAX_PAGES = 5
STOP_STATUS = (401, 403, 429)
_LEGAL_FORM = re.compile(r"\b(oy|oyj|ab|abp|ltd)\b", re.I)
_APPLICANT_CC = re.compile(r"\s*\[([A-Z]{2})\]\s*$")  # epodoc applicant names end in "[FI]"
_log = logging.getLogger(NAME)
_last_call = 0.0


class Blocked(Exception):
    """OPS cannot be asked (no key) or told us to stop; no further requests go out in this run."""


def _http(*values: str) -> str | None:
    return next((v.strip() for v in values if (v or "").strip().startswith(("http://", "https://"))), None)


def _candidates(names: list[tuple[str, bool]]) -> list[tuple[str, str, bool]]:
    """(normalised, as declared, is_legal_name), legal names first, one entry per normalised form."""
    best: dict[str, tuple[str, str, bool]] = {}
    for shown, legal in names:
        n = norm_name(shown)
        if len(n) >= 3 and (n not in best or (legal and not best[n][2])):
            best[n] = (n, shown.strip(), legal)
    return sorted(best.values(), key=lambda c: not c[2])


def declared_companies(cohort_csv: Path = COHORT_CSV, universe_csv: Path = UNIVERSE_CSV) -> tuple[list[dict], int]:
    """Finnish companies to check, and how many declared rows were skipped (not Finnish, unconfirmed, or no link).

    Finnish means: cohort/portfolio row with country FI, or a universe row with a Y-tunnus. company_key follows
    radar/adapters/declared.py (Y-tunnus, else slug) so signals land on the same company rows.
    """
    out: list[dict] = []
    seen: set[str] = set()
    skipped = 0
    with open(cohort_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name, country = r["company"].strip(), r["country"].strip()[:2].upper()
            src = _http(r["ytj_source"], r["website"], r["customers_url"])
            if country != "FI" or not src:
                skipped += 1
                continue
            ytj, legal = r["y_tunnus"].strip() or None, r["ytj_name"].strip()
            names = ([(legal, True)] if legal else []) + [(n, False) for n in name.split(" / ")]
            out.append(dict(key=ytj or slug(country, name), name=legal or name, y_tunnus=ytj, group_tag=r["group"].strip(),
                            source_url=src, names=_candidates(names)))
    with open(universe_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ytj, src = r["y_tunnus_if_found"].strip(), _http(r["source_url"], r["website"])
            if not ytj or not src:  # no Finnish business id: the declared list says the country is unconfirmed
                skipped += 1
                continue
            main, _, alias = r["name"].strip().partition(" (")
            names = [(n, bool(_LEGAL_FORM.search(n))) for n in (main, alias.rstrip(")")) if n]
            out.append(dict(key=ytj, name=r["name"].strip(), y_tunnus=ytj, group_tag="feed", source_url=src,
                            names=_candidates(names)))
    uniq = []
    for c in out:
        if c["key"] in seen or not c["names"]:
            skipped += 1
            continue
        seen.add(c["key"])
        uniq.append(c)
    return uniq, skipped


class Ops:
    """OPS client: cache first, then one throttled request. After a stop status it stays blocked for the run."""

    def __init__(self, transport: httpx.BaseTransport | None = None, cache_dir: Path | str = CACHE):
        self.cache_dir = Path(cache_dir)
        self.key, self.secret = os.environ.get("EPO_OPS_KEY", ""), os.environ.get("EPO_OPS_SECRET", "")
        self.http = httpx.Client(headers={"User-Agent": UA}, timeout=30, transport=transport)
        self.token: str | None = None
        self.blocked: str | None = None
        self.requests = 0

    def close(self) -> None:
        self.http.close()

    def _send(self, method: str, url: str, **kw) -> httpx.Response:
        global _last_call
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.http.request(method, url, **kw)
        except httpx.TransportError as e:  # unreachable (refused, proxy denial, timeout): retrying per company only hammers
            self.blocked = f"OPS unreachable ({type(e).__name__}: {e}); stopped, no further requests this run"
            raise Blocked(self.blocked) from e
        finally:
            _last_call = time.monotonic()
            self.requests += 1
        if r.status_code in STOP_STATUS:
            self.blocked = f"OPS answered HTTP {r.status_code} on {url.split('?')[0]}; stopped, no further requests this run"
            raise Blocked(self.blocked)
        return r

    def _bearer(self) -> str:
        if self.token:
            return self.token
        if not (self.key and self.secret):
            self.blocked = ("BLOCKED: no OPS consumer key (EPO_OPS_KEY and EPO_OPS_SECRET not set); "
                            "OPS needs a registered key, so patents stay a connector slot")
            raise Blocked(self.blocked)
        r = self._send("POST", TOKEN_URL, auth=(self.key, self.secret), data={"grant_type": "client_credentials"})
        try:
            self.token = r.json().get("access_token") if r.status_code == 200 else None
        except ValueError:
            self.token = None
        if not self.token:  # one try per run, never once per company
            self.blocked = f"OPS token request answered HTTP {r.status_code} without a token; stopped, no further requests this run"
            raise Blocked(self.blocked)
        return self.token

    def search(self, cql: str, begin: int) -> dict:
        """One page of search/biblio JSON. OPS answers 404 when nothing matches; that is cached as {"status": 404}."""
        url = f"{SEARCH_URL}?{urlencode({'q': cql, 'Range': f'{begin}-{begin + PAGE_SIZE - 1}'})}"
        f = self.cache_dir / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        if self.blocked:
            raise Blocked(self.blocked)
        r = self._send("GET", url, headers={"Authorization": f"Bearer {self._bearer()}", "Accept": "application/json"})
        if r.status_code == 404:
            data = {"status": 404}
        else:
            r.raise_for_status()
            data = r.json()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data


def _list(v) -> list:
    return v if isinstance(v, list) else [] if v is None else [v]


def _text(v) -> str:
    return str(v.get("$", "")) if isinstance(v, dict) else str(v or "")


def _iso(v: str) -> str | None:
    d = re.sub(r"\D", "", v or "")
    if len(d) != 8:
        return None
    try:
        return date(int(d[:4]), int(d[4:6]), int(d[6:])).isoformat()
    except ValueError:
        return None


def documents(data: dict) -> tuple[list[dict], int]:
    """(exchange-documents, total-result-count) of one search/biblio page. OPS JSON gives one item as an object, many as a list."""
    s = (data.get("ops:world-patent-data") or {}).get("ops:biblio-search") or {}
    docs: list[dict] = []
    for group in _list((s.get("ops:search-result") or {}).get("exchange-documents")):
        docs.extend(_list(group.get("exchange-document")))
    return docs, int(s.get("@total-result-count") or 0)


def applicants(biblio: dict) -> list[dict]:
    """Per applicant sequence: normalised names, countries ("[FI]" suffix or residence), name as printed (original format first)."""
    seqs: dict[str, dict] = {}
    for a in _list(((biblio.get("parties") or {}).get("applicants") or {}).get("applicant")):
        raw = _text((a.get("applicant-name") or {}).get("name")).strip()
        s = seqs.setdefault(str(a.get("@sequence", "")), {"names": set(), "cc": set(), "printed": raw})
        m = _APPLICANT_CC.search(raw)
        if m:
            s["cc"].add(m.group(1))
            raw = raw[:m.start()]
        cc = _text((a.get("residence") or {}).get("country")).strip().upper()
        if cc:
            s["cc"].add(cc)
        if a.get("@data-format") == "original":
            s["printed"] = raw
        if norm_name(raw):
            s["names"].add(norm_name(raw))
    return list(seqs.values())


def earliest_filing(biblio: dict) -> str | None:
    """Earliest of the application date and every priority date the record states: the first filing of the invention."""
    ids = _list((biblio.get("application-reference") or {}).get("document-id"))
    for pc in _list((biblio.get("priority-claims") or {}).get("priority-claim")):
        ids += _list(pc.get("document-id"))
    dates = [d for d in (_iso(_text(i.get("date"))) for i in ids) if d]
    return min(dates) if dates else None


def publication(doc: dict, biblio: dict) -> tuple[str, str | None]:
    """(publication number such as EP1234567A1, publication date) from the docdb id, else the document attributes."""
    for i in _list((biblio.get("publication-reference") or {}).get("document-id")):
        if i.get("@document-id-type") == "docdb":
            return _text(i.get("country")) + _text(i.get("doc-number")) + _text(i.get("kind")), _iso(_text(i.get("date")))
    return f"{doc.get('@country', '')}{doc.get('@doc-number', '')}{doc.get('@kind', '')}", None


def _title(biblio: dict) -> str | None:
    titles = _list(biblio.get("invention-title"))
    en = [t for t in titles if isinstance(t, dict) and t.get("@lang") == "en"]
    return _text((en or titles or [None])[0]) or None


def match(doc: dict, candidates: list[tuple[str, str, bool]]) -> dict | None:
    """The hit for one record, or None. Needs a Finnish applicant whose normalised name equals a candidate exactly."""
    b = doc.get("bibliographic-data") or {}
    for a in applicants(b):
        if "FI" not in a["cc"]:
            continue
        for norm, shown, legal in candidates:
            if norm in a["names"]:
                pn, published = publication(doc, b)
                return dict(family=str(doc.get("@family-id") or pn), filed=earliest_filing(b), pn=pn, published=published,
                            applicant=a["printed"], title=_title(b), matched=shown, legal=legal)
    return None


def company_hits(ops: Ops, c: dict, stats: dict) -> list[dict]:
    """Earliest filing per patent family for one company, over up to MAX_PAGES result pages."""
    cql = " or ".join(f'pa="{n}"' for n, _, _ in c["names"])
    fams: dict[str, dict] = {}
    for page in range(MAX_PAGES):
        docs, total = documents(ops.search(cql, page * PAGE_SIZE + 1))
        for d in docs:
            h = match(d, c["names"])
            if h is None:
                continue
            if not h["filed"]:
                stats["records_no_date"] += 1
                continue
            old = fams.get(h["family"])
            if old is None or (h["filed"], h["pn"]) < (old["filed"], old["pn"]):
                fams[h["family"]] = h
        if not docs or (page + 1) * PAGE_SIZE >= total:
            break
    else:
        stats["truncated"] += 1
        _log.warning("%s: more than %d records, earliest filings read from the first %d only", c["name"], MAX_PAGES * PAGE_SIZE, MAX_PAGES * PAGE_SIZE)
    return sorted(fams.values(), key=lambda h: (h["filed"], h["pn"]))


def _detail(h: dict) -> str:
    published = f" on {h['published']}" if h["published"] else ""
    title = f"; title: {h['title']}" if h["title"] else ""
    how = "legal name" if h["legal"] else "declared name (not a confirmed legal name)"
    return (f"Patent family {h['family']}: earliest filing {h['filed']}, published as {h['pn']}{published}; "
            f"applicant as recorded: {h['applicant']}{title}. Matched: Finnish applicant, exact {how} '{h['matched']}' (EPO OPS).")


def run(conn: sqlite3.Connection, thesis: dict | None = None, *, transport: httpx.BaseTransport | None = None,
        cache_dir: Path | str = CACHE, cohort_csv: Path = COHORT_CSV, universe_csv: Path = UNIVERSE_CSV) -> dict:
    companies, skipped = declared_companies(cohort_csv, universe_csv)
    stats = {"companies": 0, "signals": 0, "skipped": skipped, "listed": len(companies) + skipped, "checked": 0,
             "not_checked": 0, "errors": 0, "matched_families": 0, "records_no_date": 0, "truncated": 0, "requests": 0,
             "blocked": ""}
    ops = Ops(transport=transport, cache_dir=cache_dir)
    try:
        for c in companies:
            try:
                hits = company_hits(ops, c, stats)
            except Blocked:
                stats["not_checked"] += 1
                continue
            except (httpx.HTTPError, ValueError, KeyError) as e:
                _log.warning("%s: %s", c["name"], e)
                stats["errors"] += 1
                continue
            stats["checked"] += 1
            if not hits:
                continue
            if not conn.execute("SELECT 1 FROM companies WHERE company_key=?", (c["key"],)).fetchone():
                emit.upsert_company(conn, company_key=c["key"], name=c["name"], source_url=c["source_url"],
                                    y_tunnus=c["y_tunnus"], country="FI", group_tag=c["group_tag"])
            for h in hits:
                stats["signals"] += emit.emit_signal(
                    conn, company_key=c["key"], signal_type=SIGNAL_TYPE, date=h["filed"],
                    source_url=ESPACENET_URL.format(pn=quote(h["pn"])), confidence="medium" if h["legal"] else "low",
                    adapter=NAME, detail=_detail(h))
            stats["companies"] += 1
            stats["matched_families"] += len(hits)
    finally:
        ops.close()
    stats["requests"], stats["blocked"] = ops.requests, ops.blocked or ""
    if ops.blocked:
        _log.warning(ops.blocked)
    conn.commit()
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from radar import db, thesis as thesis_mod
    th = thesis_mod.load()
    print(run(db.connect(thesis_mod.db_path(th)), th))
