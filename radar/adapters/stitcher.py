"""Stitcher: an LLM proposes dated public events for one company, plain code checks each one against the page it cites.

Four steps, each its own function, every step written to the stitch_log table (radar/schema/040_stitch_log.sql):
  search  build web queries from the legal name, business ID and website domain; log every query.
  read    `claude -p --model sonnet` with WebSearch/WebFetch proposes events as JSON (type, date, precision, URL, quote,
          confidence). The LLM never writes to the database; an event without a URL is not an event.
  verify  plain Python, no LLM: fetch each source_url and keep the event only if the page names the company (legal name,
          business ID, core name or website domain) AND shows the date or at least its year. The precision kept is the
          one the page supports, never more than proposed. The Internet Archive's first capture of the page is stored as
          public_since: the earliest day anyone could have read it. Every drop is logged with its reason.
  emit    radar.emit.emit_signal only, adapter "stitcher". Emittable: the existing radar.emit types in EMITTABLE plus
          programme_entry, award and funding_round (chief's decision 17 Oct: the thesis already counts them). Every other
          kept type is logged as not_emitted with the LLM's label and stays in stitch_log only, never a signal.

Not run by `python3 -m radar.build`: the module has no run(), because one LLM session per company is minutes, not
seconds. CLI:  python3 -m radar.adapters.stitcher --company <key> | --batch <file>  [--proposals DIR] [--print-prompt]
Database: --db, else env RADAR_DB, else the thesis store (radar.thesis.db_path). The default data/radar.sqlite is refused.
Companies only: quotes have person-shaped names redacted; the prompt forbids naming private individuals.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from radar import emit
from radar.adapters._fetch import CACHE_ROOT, UA, Blocked, cached_get
from radar.adapters.openalex import core_name, fold
from radar.adapters.webarchive import CDX, archive_url, domain_of

NAME = "stitcher"
INTERVAL = 2.0          # seconds between our own requests (page fetches and archive lookups)
MAX_QUOTE_WORDS = 20
MAX_EVENTS = 15
LLM_TIMEOUT = 900       # seconds for one company's read session
CACHE = CACHE_ROOT / NAME

# Types the LLM may propose. Register-derived types (register_entry, first_sales, first_hire, sales_ended,
# employer_ended) and website_first_seen come from their own adapters, never from a web page the LLM picked.
EMITTABLE = {
    "bf_funding": "Business Finland funding decision for the company",
    "eu_project": "EU-funded project (Horizon, LIFE, Interreg, EIC, EMFAF ...) the company takes part in",
    "blueinvest": "the company is listed or featured by the EU BlueInvest programme",
    "patent": "patent application or grant naming the company as applicant",
    "public_contract": "public procurement contract awarded to the company",
    "job_ad": "the company advertised an open job (the role, never the person)",
    "site_customer": "a named customer, pilot partner or buyer of the company (an organisation, not a person)",
    "research_output": "publication or report co-authored by the company as an organisation",
    "website_milestone": "launch of the company's product, customers, pricing or careers page",
}
# Chief's decision (17 Oct): these three become emittable because the thesis feed already counts them. They are registered
# the way radar/adapters/ecosystem.py registers its types (emit.py stays the chief's file). No other new type, ever.
THESIS_TYPES = {
    "programme_entry": "the company was selected into or joined an accelerator, incubator or programme cohort",
    "award": "the company won an award, prize or pitch competition (a win, not a nomination or a finalist place)",
    "funding_round": "the company raised an equity, convertible or crowdfunding round from investors",
}
emit.SIGNAL_TYPES = tuple(dict.fromkeys((*emit.SIGNAL_TYPES, *THESIS_TYPES)))
EMITTABLE.update(THESIS_TYPES)
assert all(t in emit.SIGNAL_TYPES for t in EMITTABLE), "EMITTABLE must stay a subset of radar.emit.SIGNAL_TYPES"

# Sources behind logins or paid walls: the honesty lines say connector slot only, never scraped.
BLOCKED_HOSTS = ("linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com", "crunchbase.com", "dealroom.co",
                 "pitchbook.com", "tracxn.com", "cbinsights.com", "nordic9.com", "zoominfo.com", "rocketreach.co")

_MONTHS_EN = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_MONTHS_EN3 = tuple(m[:3] for m in _MONTHS_EN)
_MONTHS_FI = ("tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesakuu", "heinakuu", "elokuu", "syyskuu", "lokakuu",
              "marraskuu", "joulukuu")  # folded (kesäkuu -> kesakuu); inflected forms (lokakuussa, lokakuuta) share the stem
_MONTHS_SV = ("januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december")
_MONTHS_DE = ("januar", "februar", "marz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "dezember")
_MONTHS_ES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
_MONTHS_DA = ("januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober", "november", "december")
_MONTH_NAMES = (_MONTHS_EN, _MONTHS_EN3, _MONTHS_FI, _MONTHS_SV, _MONTHS_DE, _MONTHS_ES, _MONTHS_DA)

# Capitalised words that are not personal names; any person-shaped run without one of these, or a company word, is redacted.
_NOT_PERSON = set("""
the a an and of for in on at to by with from our we this that their its new first
oy oyj ab ltd as aps gmbh inc llc sa bv plc ky
eu european union commission horizon life interreg eic emfaf council agency ministry government city port university
finland finnish nordic baltic sea ocean blue marine maritime business innovation fund funds capital ventures partners
group foundation centre center institute research technology technologies tech labs lab programme program accelerator
award awards prize challenge summit expo week conference cohort pilot project startup startups company
turku helsinki espoo tampere oulu vaasa rauma kotka naantali uusikaupunki copenhagen stockholm oslo madrid barcelona
denmark sweden norway spain estonia germany europe america
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
""".split())
_CAP = r"[A-ZÅÄÖÜÉÆØ][a-zåäöüéèæø'\-]+"
_PERSON_RUN = re.compile(rf"\b{_CAP}(?:\s+{_CAP}){{1,2}}\b")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(conn: sqlite3.Connection, run_id: str, company_key: str, step: str, outcome: str, **kw) -> None:
    cols = ["run_id", "company_key", "step", "outcome", "ts"] + list(kw)
    conn.execute(f"INSERT INTO stitch_log ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                 [run_id, company_key, step, outcome, now_utc()] + list(kw.values()))


# ---------------------------------------------------------------- step 1: search

def company_row(conn: sqlite3.Connection, company_key: str) -> dict:
    r = conn.execute("SELECT company_key, name, y_tunnus, country, website, founded, group_tag FROM companies WHERE company_key=?",
                     (company_key,)).fetchone()
    if r is None:
        raise KeyError(f"company {company_key!r} is not in the store; the stitcher only enriches companies that exist")
    return dict(r)


def search(conn: sqlite3.Connection, run_id: str, company: dict) -> list[str]:
    """Web queries from the legal name, business ID and website domain. Every query is logged. No personal names, ever."""
    name, yt, dom = company["name"], company.get("y_tunnus"), domain_of(company.get("website"))
    core = core_name(name) or fold(name)
    qs = [f'"{name}"']
    if yt:
        qs.append(f'"{yt}"')
    if dom:
        qs += [f'"{dom}"', f"site:{dom} news OR press OR customers OR partners"]
    qs += [f'"{core}" funding OR investment OR grant', f'"{core}" pilot OR customer OR contract OR award',
           f'"{core}" EU project OR Horizon OR BlueInvest OR "Business Finland"']
    if (company.get("country") or "FI") == "FI":
        qs.append(f'"{core}" rahoitus OR asiakas OR pilotti OR palkinto')
    seen, out = set(), []
    for q in qs:
        if q not in seen:
            seen.add(q)
            out.append(q)
            _log(conn, run_id, company["company_key"], "search", "query", query=q)
    return out


# ---------------------------------------------------------------- step 2: read (LLM proposes)

def build_prompt(company: dict, queries: list[str]) -> str:
    types = "\n".join(f'  - "{k}": {v}' for k, v in EMITTABLE.items())
    yt = company.get("y_tunnus") or "none"
    site = company.get("website") or "unknown"
    return f"""You are collecting PUBLIC, DATED events about one company, each with the exact web page that states it.
Company: {company['name']} | business ID: {yt} | country: {company.get('country') or 'unknown'} | website: {site}

Use WebSearch on these queries (add your own if useful) and WebFetch to open the pages you cite:
{chr(10).join('  ' + q for q in queries)}

Return ONLY one JSON object, no prose, no code fence:
{{"queries_run": ["..."], "events": [{{"signal_type": "...", "suggested_type": null, "date": "YYYY-MM-DD or YYYY-MM or YYYY",
  "date_precision": "day|month|year", "source_url": "https://...", "quote": "...", "confidence": "high|medium|low"}}]}}

signal_type must be one of these, or "unmapped" with a short snake_case suggested_type (e.g. product_launch, exhibitor,
partnership, incorporation):
{types}

Rules, all mandatory:
1. Every event has a source_url that you opened with WebFetch and that itself names the company and states the date.
   No URL, no event. Never invent, never infer a date the page does not print.
2. date = when the event happened, as precisely as the page states it; date_precision says how precise that is.
3. quote = at most {MAX_QUOTE_WORDS} words copied verbatim from that page, stating the event and naming the company.
   Never a sentence that names a private person: pick another sentence or drop the event. Companies only.
4. No LinkedIn, Facebook, Instagram, X/Twitter, Crunchbase, Dealroom, PitchBook, Tracxn, CB Insights, Nordic9.
   Prefer the company's own site, press releases, EU/CORDIS/BlueInvest, Business Finland, patent offices, news.
5. The EARLIEST events matter most: first funding, first customer or pilot, programme entries, awards, first product.
6. At most {MAX_EVENTS} events. confidence: high = the page names the company and the exact date; medium = name and
   month or year; low = anything weaker (low events are usually dropped later, so prefer leaving them out).
"""


def _extract_json(text: str) -> dict:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON object in the LLM answer")
    return json.loads(t[a:b + 1])


def claude_runner(prompt: str, *, model: str = "sonnet", timeout: int = LLM_TIMEOUT) -> str:
    """One headless Claude Code session with web tools; prompt over stdin. Auth comes from the caller's environment
    (the Max-plan login, or the farm runner's); this module never reads credential files."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("BLOCKED: the claude CLI is not on PATH")
    p = subprocess.run([exe, "-p", "--model", model, "--allowedTools", "WebSearch,WebFetch", "--output-format", "json"],
                       input=prompt, capture_output=True, text=True, timeout=timeout)
    try:
        env = json.loads(p.stdout)
    except ValueError:
        raise RuntimeError(f"claude -p gave no JSON (rc {p.returncode}): {(p.stderr or p.stdout)[:300]}")
    if env.get("is_error") or "Failed to authenticate" in str(env.get("result")):
        raise RuntimeError(f"BLOCKED: claude -p error: {str(env.get('result'))[:300]}")
    return str(env.get("result") or "")


def normalise_proposal(ev: dict) -> tuple[dict | None, str | None]:
    """A clean proposal or (None, reason). Checks shape only; truth is verify's job."""
    url = str(ev.get("source_url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return None, "no_source_url"
    d = str(ev.get("date") or "").strip()
    prec = str(ev.get("date_precision") or "").strip().lower()
    m = re.fullmatch(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", d)
    if not m:
        return None, "bad_date"
    implied = "day" if m.group(3) else "month" if m.group(2) else "year"
    order = {"year": 0, "month": 1, "day": 2}
    prec = prec if prec in order and order[prec] <= order[implied] else implied
    try:
        date(int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1))
    except ValueError:
        return None, "bad_date"
    st = str(ev.get("signal_type") or "").strip()
    sug = (str(ev.get("suggested_type") or "").strip() or None)
    if st == "unmapped" and sug in EMITTABLE:  # an answer saved before a type became emittable: take the type it named
        st, sug = sug, None
    if st not in EMITTABLE:
        sug = sug or st or "unlabelled"
        st = "unmapped"
    sug = re.sub(r"[^a-z0-9_]+", "_", sug.lower()).strip("_")[:40] if sug else None
    words = str(ev.get("quote") or "").split()
    conf = str(ev.get("confidence") or "").lower()
    return {"signal_type": st, "suggested_type": sug, "date": d, "date_precision": prec, "source_url": url,
            "quote": " ".join(words[:MAX_QUOTE_WORDS]), "llm_confidence": conf if conf in emit.CONFIDENCE else None}, None


def read(conn: sqlite3.Connection, run_id: str, company: dict, queries: list[str], runner=claude_runner) -> list[dict]:
    """Ask the LLM for proposals. The raw answer is cached under data/cache/stitcher/llm/ by prompt hash, so a re-run
    re-verifies the same proposals without a new LLM session. Proposals are logged, never trusted."""
    prompt = build_prompt(company, queries)
    key = hashlib.sha1(prompt.encode()).hexdigest()[:16]
    f = CACHE / "llm" / f"{re.sub(r'[^A-Za-z0-9_-]', '_', company['company_key'])}-{key}.txt"
    if f.exists():
        raw = f.read_text(encoding="utf-8")
    else:
        try:
            raw = runner(prompt)
        except Exception as e:
            _log(conn, run_id, company["company_key"], "read", "read_failed", reason=str(e)[:500])
            return []
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(raw, encoding="utf-8")
    try:
        data = _extract_json(raw)
    except ValueError as e:
        _log(conn, run_id, company["company_key"], "read", "read_failed", reason=f"unparseable LLM answer: {e}")
        return []
    for q in data.get("queries_run") or []:
        _log(conn, run_id, company["company_key"], "search", "llm_query", query=str(q)[:300])
    out, seen = [], set()
    for ev in (data.get("events") or [])[:MAX_EVENTS * 2]:
        p, why = normalise_proposal(ev if isinstance(ev, dict) else {})
        if p is None:
            _log(conn, run_id, company["company_key"], "read", "rejected", reason=why,
                 source_url=str((ev or {}).get("source_url") or "")[:500] if isinstance(ev, dict) else None)
            continue
        p["quote"] = redact_people(p["quote"], company["name"])
        k = (p["signal_type"], p["suggested_type"], p["date"], p["source_url"])
        if k in seen:
            continue
        seen.add(k)
        _log(conn, run_id, company["company_key"], "read", "proposed", signal_type=p["signal_type"], suggested_type=p["suggested_type"],
             date=p["date"], date_precision=p["date_precision"], source_url=p["source_url"], quote=p["quote"],
             confidence=p["llm_confidence"])
        out.append(p)
    return out


def redact_people(text: str, company_name: str) -> str:
    """Replace person-shaped runs of capitalised words ("Firstname Lastname") with [name]. A run survives only if one of
    its words is part of the company name or a known non-person word. Over-redaction is the accepted cost."""
    own = set(fold(company_name).split())

    def sub(m: re.Match) -> str:
        words = fold(m.group(0)).split()
        return m.group(0) if any(w in own or w in _NOT_PERSON for w in words) else "[name]"
    return _PERSON_RUN.sub(sub, text or "")


# ---------------------------------------------------------------- step 3: verify (plain code decides)

_last = 0.0


def _wait() -> None:
    global _last
    w = INTERVAL - (time.monotonic() - _last)
    if w > 0:
        time.sleep(w)
    _last = time.monotonic()


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<!--.*?-->", " ", raw)
    # keep meta descriptions and datetime attributes: news sites put the date there
    keep = " ".join(re.findall(r'(?i)(?:content|datetime)="([^"]{4,300})"', raw))
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", text + " " + html.unescape(keep)).strip()


def fetch_page(url: str, client: httpx.Client | None = None) -> str:
    """Page text, cached under data/cache/stitcher/pages/. Raises Blocked when unreachable or not readable."""
    f = CACHE / "pages" / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".txt")
    if f.exists():
        return f.read_text(encoding="utf-8")
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": UA, "Accept-Language": "en,fi;q=0.8"}, timeout=60, follow_redirects=True)
    try:
        _wait()
        try:
            r = client.get(url)
        except httpx.HTTPError as e:
            raise Blocked(f"{type(e).__name__}")
        if r.status_code >= 400:
            raise Blocked(f"HTTP {r.status_code}")
        ctype = r.headers.get("content-type", "").lower()
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            exe = shutil.which("pdftotext")
            if not exe:
                raise Blocked("pdf without pdftotext")
            p = subprocess.run([exe, "-q", "-", "-"], input=r.content, capture_output=True, timeout=60)
            text = re.sub(r"\s+", " ", p.stdout.decode("utf-8", "replace"))
        elif "html" in ctype or "xml" in ctype or "text" in ctype or not ctype:
            text = html_to_text(r.text)
        else:
            raise Blocked(f"unreadable content-type {ctype.split(';')[0]}")
    finally:
        if own:
            client.close()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return text


def name_match(company: dict, page_text: str) -> str | None:
    """Strongest way the page names the company, or None. Whole-word matches on folded text."""
    folded = " " + fold(page_text) + " "
    yt = company.get("y_tunnus")
    if yt and (yt in page_text or fold(yt) in folded or ("FI" + yt.replace("-", "")) in page_text):
        return "business_id"
    legal = fold(company["name"])
    if " " in legal and f" {legal} " in folded:
        return "legal_name"
    core = core_name(company["name"])
    if core and f" {core} " in folded:
        return "core_name"
    dom = domain_of(company.get("website"))
    if dom and dom.lower() in page_text.lower():
        return "domain"
    return None


def date_on_page(d: str, page_text: str) -> str | None:
    """The finest precision at which the proposed date (YYYY[-MM[-DD]]) is printed on the page: day | month | year | None."""
    parts = d.split("-")
    y = int(parts[0])
    mo = int(parts[1]) if len(parts) > 1 else None
    dd = int(parts[2]) if len(parts) > 2 else None
    raw = page_text
    f = " " + fold(page_text) + " "
    if mo and dd:
        pats = [rf"\b{y}-{mo:02d}-{dd:02d}", rf"\b0?{dd}\.\s?0?{mo}\.\s?{y}\b", rf"\b0?{dd}/0?{mo}/{y}\b", rf"\b{y}/{mo:02d}/{dd:02d}\b"]
        if any(re.search(p, raw) for p in pats):
            return "day"
        for names in _MONTH_NAMES:
            n = names[mo - 1]
            if re.search(rf"\b0?{dd}(?:st|nd|rd|th)? (?:of )?{n}[a-z]* {y}\b", f) or re.search(rf"\b{n}[a-z]* 0?{dd}(?:st|nd|rd|th)? {y}\b", f) \
                    or re.search(rf"\b0?{dd} {n}[a-z]* {y}\b", f):
                return "day"
    if mo:
        if re.search(rf"\b{y}-{mo:02d}\b", raw) or re.search(rf"\b0?{mo}[/.]{y}\b", raw):
            return "month"
        for names in _MONTH_NAMES:
            if re.search(rf"\b{names[mo - 1]}[a-z]*(?: \d{{1,2}}(?:st|nd|rd|th)?)? {y}\b", f):
                return "month"
    if re.search(rf"(?<!\d){y}(?!\d)", raw):
        return "year"
    return None


def first_capture(url: str) -> tuple[str | None, str | None]:
    """(YYYY-MM-DD, archived URL) of the earliest 200 capture of exactly this page, or (None, None)."""
    params = {"url": url, "output": "json", "fl": "timestamp,original,statuscode", "filter": "statuscode:200", "limit": "1"}
    try:
        rows, _ = cached_get(NAME, CDX, interval=INTERVAL, params=params)
    except Blocked:
        return None, None
    if not rows or len(rows) < 2 or not re.match(r"^\d{14}$", str(rows[1][0])):
        return None, None
    ts, original = rows[1][0], rows[1][1]
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", archive_url(ts, original)


def verify(conn: sqlite3.Connection, run_id: str, company: dict, proposals: list[dict], *, fetch=fetch_page,
           capture=first_capture, today: str | None = None) -> list[dict]:
    """Keep a proposal only if its page names the company AND prints the date or its year. Logs kept and dropped rows."""
    today = today or date.today().isoformat()
    kept = []
    order = {"year": 0, "month": 1, "day": 2}
    for p in proposals:
        why, nm, found, text = None, None, None, ""
        host = (urlparse(p["source_url"]).hostname or "").lower()
        if any(host == h or host.endswith("." + h) for h in BLOCKED_HOSTS):
            why = "source_not_allowed"
        elif p["date"][:10] > today:
            why = "date_in_future"
        else:
            try:
                text = fetch(p["source_url"])
            except Blocked as e:
                why = f"fetch_failed: {e}"
        if why is None:
            nm = name_match(company, text)
            found = date_on_page(p["date"], text)
            if nm is None and found is None:
                why = "name_and_date_not_on_page"
            elif nm is None:
                why = "company_not_on_page"
            elif found is None:
                why = "date_not_on_page"
        if why:
            _log(conn, run_id, company["company_key"], "verify", "dropped", reason=why, signal_type=p["signal_type"],
                 suggested_type=p["suggested_type"], date=p["date"], date_precision=p["date_precision"], source_url=p["source_url"],
                 quote=p["quote"], name_match=nm)
            continue
        prec = min(p["date_precision"], found, key=order.get)
        conf = "high" if nm in ("business_id", "legal_name") and prec in ("day", "month") else "medium"
        since, arch = capture(p["source_url"])
        quote_ok = bool(p["quote"]) and "[name]" not in p["quote"] and fold(p["quote"]) in fold(text)
        notes = [f"name by {nm}", f"date on page at {found} precision"]
        if prec != p["date_precision"]:
            notes.append(f"precision lowered from {p['date_precision']}")
        if company.get("founded") and p["date"][:10] < company["founded"][:len(p["date"][:10])]:
            notes.append("dated before the company's registration")
        notes.append("quote verbatim on page" if quote_ok else "quote not verbatim on page")
        k = dict(p, date_precision=prec, confidence=conf, name_match=nm, public_since=since, archive_url=arch, quote_on_page=quote_ok,
                 note="; ".join(notes))
        _log(conn, run_id, company["company_key"], "verify", "kept", reason=k["note"], signal_type=p["signal_type"],
             suggested_type=p["suggested_type"], date=p["date"], date_precision=prec, source_url=p["source_url"], quote=p["quote"],
             confidence=conf, name_match=nm, public_since=since, archive_url=arch)
        kept.append(k)
    return kept


# ---------------------------------------------------------------- step 4: emit (only through radar.emit)

def stored_date(d: str, precision: str) -> str:
    """ISO day for the signals table: day as is; month = last day of the month (the cautious end, as ecosystem.py does);
    year = 1 January (the radar's year-only convention, flagged in signal_meta)."""
    y = int(d[:4])
    if precision == "year":
        return f"{y}-01-01"
    mo = int(d[5:7])
    if precision == "month":
        return f"{y}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}"
    return d[:10]


def emit_events(conn: sqlite3.Connection, run_id: str, company: dict, kept: list[dict]) -> dict:
    stats = {"emitted": 0, "duplicate": 0, "not_emitted": 0}
    for k in kept:
        base = dict(signal_type=k["signal_type"], suggested_type=k["suggested_type"], date=k["date"], date_precision=k["date_precision"],
                    source_url=k["source_url"], quote=k["quote"], confidence=k["confidence"], name_match=k["name_match"],
                    public_since=k["public_since"], archive_url=k["archive_url"])
        if k["signal_type"] not in EMITTABLE:
            stats["not_emitted"] += 1
            _log(conn, run_id, company["company_key"], "emit", "not_emitted",
                 reason=f"type not emittable, kept in stitch_log only: {k['suggested_type']}", **base)
            continue
        day = stored_date(k["date"], k["date_precision"])
        host = urlparse(k["source_url"]).hostname or "the source"
        bits = [f'"{k["quote"]}"' if k["quote"] else "event stated on the page", f"({host})",
                {"day": "", "month": "Month only, stored as the last day of the month.", "year": "Year only."}[k["date_precision"]],
                f"Page first archived {k['public_since']}." if k["public_since"] else "Page not in the Internet Archive.",
                "Proposed by an LLM, checked by code: the page names the company and prints the date."]
        new = emit.emit_signal(conn, company_key=company["company_key"], signal_type=k["signal_type"], date=day, source_url=k["source_url"],
                               confidence=k["confidence"], adapter=NAME, detail=" ".join(b for b in bits if b))
        sid = conn.execute("SELECT id FROM signals WHERE company_key=? AND signal_type=? AND date=? AND source_url=?",
                           (company["company_key"], k["signal_type"], day, k["source_url"])).fetchone()[0]
        if new:
            if k["date_precision"] == "year":
                conn.execute("INSERT OR IGNORE INTO signal_meta (signal_id, date_precision) VALUES (?, 'year')", (sid,))
            if k["quote_on_page"]:  # the source's own words, verbatim; the feed reads thesis words only from signal_text
                conn.execute("INSERT OR IGNORE INTO signal_text (signal_id, field, text) VALUES (?, 'title', ?)", (sid, k["quote"]))
        stats["emitted" if new else "duplicate"] += 1
        _log(conn, run_id, company["company_key"], "emit", "emitted" if new else "duplicate", signal_id=sid, **base)
    return stats


# ---------------------------------------------------------------- orchestration and report

def stitch_company(conn: sqlite3.Connection, company_key: str, *, run_id: str | None = None, runner=claude_runner,
                   fetch=fetch_page, capture=first_capture, today: str | None = None) -> dict:
    run_id = run_id or now_utc()
    company = company_row(conn, company_key)
    queries = search(conn, run_id, company)
    proposals = read(conn, run_id, company, queries, runner=runner)
    kept = verify(conn, run_id, company, proposals, fetch=fetch, capture=capture, today=today)
    st = emit_events(conn, run_id, company, kept)
    conn.commit()
    return {"company": company_key, "queries": len(queries), "proposed": len(proposals), "kept": len(kept), **st}


def file_runner(directory: str | Path, company_key: str):
    """A runner that returns a saved LLM answer (<dir>/<company_key>.json) instead of starting a session."""
    def run(prompt: str) -> str:
        p = Path(directory) / f"{company_key}.json"
        if not p.exists():
            raise RuntimeError(f"no saved proposals at {p}")
        return p.read_text(encoding="utf-8")
    return run


def report(conn: sqlite3.Connection, run_id: str, entry: tuple[str, str] | None = None) -> dict:
    """Counts for the RESULT line: proposed, kept, dropped by reason, emitted, not emitted by label, and kept events
    dated (and publicly archived) before the cohort entry reference."""
    q = lambda sql, *a: conn.execute(sql, (run_id, *a)).fetchall()
    one = lambda sql, *a: conn.execute(sql, (run_id, *a)).fetchone()[0]
    out = {
        "proposed": one("SELECT count(*) FROM stitch_log WHERE run_id=? AND step='read' AND outcome='proposed'"),
        "rejected_shape": one("SELECT count(*) FROM stitch_log WHERE run_id=? AND step='read' AND outcome='rejected'"),
        "read_failed": [tuple(r) for r in q("SELECT company_key, reason FROM stitch_log WHERE run_id=? AND outcome='read_failed'")],
        "kept": one("SELECT count(*) FROM stitch_log WHERE run_id=? AND step='verify' AND outcome='kept'"),
        "dropped": {r[0].split(":")[0]: r[1] for r in q("SELECT reason, count(*) FROM stitch_log WHERE run_id=? AND step='verify' "
                                                       "AND outcome='dropped' GROUP BY substr(reason,1,instr(reason||':',':')-1)")},
        "emitted": one("SELECT count(*) FROM stitch_log WHERE run_id=? AND step='emit' AND outcome='emitted'"),
        "duplicate": one("SELECT count(*) FROM stitch_log WHERE run_id=? AND step='emit' AND outcome='duplicate'"),
        "not_emitted_types": {r[0]: r[1] for r in q("SELECT suggested_type, count(*) FROM stitch_log WHERE run_id=? AND step='emit' "
                                                     "AND outcome='not_emitted' GROUP BY 1 ORDER BY 2 DESC")},
    }
    if entry:
        ref = entry[0]
        rows = q("SELECT company_key, date, date_precision, public_since FROM stitch_log WHERE run_id=? AND step='verify' AND outcome='kept'")
        out["entry_reference"] = f"{ref} ({entry[1]})"
        out["kept_before_entry"] = sum(1 for r in rows if stored_date(r[1], r[2]) < ref)
        out["kept_before_entry_and_archived_before_entry"] = sum(1 for r in rows if stored_date(r[1], r[2]) < ref and r[3] and r[3] < ref)
        out["companies_with_kept_before_entry"] = len({r[0] for r in rows if stored_date(r[1], r[2]) < ref})
    return out


def _resolve_db(arg: str | None, th: dict) -> Path:
    from radar import db, thesis as thesis_mod
    p = Path(arg or os.environ.get("RADAR_DB") or thesis_mod.db_path(th))
    if p.resolve() == (db.ROOT / "data" / "radar.sqlite").resolve():
        raise SystemExit("refusing data/radar.sqlite: point --db or RADAR_DB at the thesis store (radar.thesis.db_path)")
    if not p.exists():
        raise SystemExit(f"no store at {p}")
    return p


def main(argv: list[str] | None = None) -> int:
    from radar import db, earliness, thesis as thesis_mod
    ap = argparse.ArgumentParser(prog="python3 -m radar.adapters.stitcher", description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--company", help="company_key in the store")
    g.add_argument("--batch", help="file with one company_key per line (# comments allowed)")
    ap.add_argument("--db", help="store path (default: env RADAR_DB, else the thesis store)")
    ap.add_argument("--thesis", help="thesis yaml path (default: radar.thesis.load())")
    ap.add_argument("--proposals", help="directory of saved LLM answers <company_key>.json instead of claude -p")
    ap.add_argument("--print-prompt", action="store_true", help="print the read-step prompt for each company and stop")
    a = ap.parse_args(argv)
    th = thesis_mod.load(a.thesis) if a.thesis else thesis_mod.load()
    conn = db.connect(_resolve_db(a.db, th))
    keys = [a.company] if a.company else [l.split("#")[0].strip() for l in Path(a.batch).read_text().splitlines() if l.split("#")[0].strip()]
    if a.print_prompt:
        for k in keys:
            c = company_row(conn, k)
            print(f"===== {k}\n{build_prompt(c, search(conn, 'print-prompt', c))}")
        conn.rollback()
        return 0
    run_id = now_utc()
    for k in keys:
        runner = file_runner(a.proposals, k) if a.proposals else claude_runner
        try:
            print(json.dumps(stitch_company(conn, k, run_id=run_id, runner=runner), ensure_ascii=False), flush=True)
        except KeyError as e:
            print(json.dumps({"company": k, "error": str(e)}), flush=True)
    print("RESULT " + json.dumps({"run_id": run_id, **report(conn, run_id, earliness.reference(th))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
