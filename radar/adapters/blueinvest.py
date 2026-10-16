"""BlueInvest Project Pipeline (public HTML, no login) -> blueinvest_profiles, and blueinvest signals only when a page states a listing date.

Crawl: robots.txt first, then one list per thesis country (country filter params[co][]=FI by default), then the detail page of each Finnish
profile plus the detail pages of the declared companies' blueinvest_url values. One request per 2 s, hard cap 150
requests in total (cache hits are free), stop at once on HTTP 403 or 429 and keep what is stored.
The pages state no listing date as of 16 Oct 2026, so no signal is emitted: the fetch date is not an event date.
"""
from __future__ import annotations

import csv
import hashlib
import html
import logging
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from radar import emit
from radar import thesis as thesis_mod

NAME = "blueinvest"
PHASE = 1
ROOT = Path(__file__).resolve().parent.parent.parent
HOST = "https://blueinvest-community.converve.io"
LIST_URL = f"{HOST}/pipeline_front.html"
UA = "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"
REQUEST_CAP = 150
DELAY_S = 2.0
DECLARED_CSV = ROOT / "data" / "declared" / "cohort_portfolio_companies.csv"
_log = logging.getLogger(NAME)
_SUFFIX = re.compile(r"\b(oy|oyj|ab|abp|ltd|as|a/s|aps|gmbh|inc|ky|tmi)\b\.?")
# Only labels that clearly mean "when the profile was listed". A "last updated" label is never accepted.
_DATE_LABEL = re.compile(r"(listed|created|published|submitted|added)", re.I)
_UPDATED = re.compile(r"updated|modified|changed", re.I)


class Blocked(Exception):
    """HTTP 403/429, robots disallow or the request cap: the crawl stops, stored rows stay."""


def cache_dir() -> Path:
    return thesis_mod.data_dir() / "cache" / NAME


def detail_url(profile_id: str) -> str:
    return f"{LIST_URL}?action=detail&params%5Bevent_id%5D=1&params%5Bshow%5D=comp&params%5Bq%5D=&params%5Bother_id%5D={profile_id}"


def list_url(page: int = 1, country: str = "FI") -> str:
    q = {"params[co][]": country, "params[_filtered]": "1", "params[event_id]": "1"}
    if page > 1:
        q["params[page]"] = str(page)
    return f"{LIST_URL}?{urllib.parse.urlencode(q)}"


def fold(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9/ -]+", " ", s).replace("-", " ").replace("/", " ")
    return re.sub(r"\s+", " ", _SUFFIX.sub(" ", s)).strip()


def slug(s) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")


class Fetcher:
    """Cached, polite, capped HTTP GET. `opener(url) -> (status, text)` is replaceable for tests."""

    def __init__(self, opener=None, cap: int = REQUEST_CAP, delay: float = DELAY_S, sleep=time.sleep, cache: Path | None = None):
        self.opener, self.cap, self.delay, self.sleep = opener or self._http, cap, delay, sleep
        self.cache = cache or cache_dir()
        self.requests = 0
        self._last = 0.0

    @staticmethod
    def _http(url: str) -> tuple[int, str]:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""

    def get(self, url: str) -> str:
        path = self.cache / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")
        if path.exists():
            return path.read_text(encoding="utf-8")
        if self.requests >= self.cap:
            raise Blocked(f"request cap {self.cap} reached")
        wait = self.delay - (time.monotonic() - self._last)
        if self._last and wait > 0:
            self.sleep(wait)
        self.requests += 1
        status, text = self.opener(url)
        self._last = time.monotonic()
        if status in (403, 429):
            raise Blocked(f"HTTP {status} from {url}")
        if status != 200:
            raise OSError(f"HTTP {status} from {url}")
        self.cache.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return text


def robots_allows(text: str, path: str = "/pipeline_front.html") -> bool:
    """Minimal robots.txt reading for User-agent: * (and ours). Empty or missing file allows."""
    applies, disallow = False, []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        if k.lower() == "user-agent":
            applies = v == "*" or "oceanopportunityradar" in v.lower()
        elif applies and k.lower() == "disallow" and v:
            disallow.append(v)
    return not any(path.startswith(d) for d in disallow)


def _text(fragment: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", fragment)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return "\n".join(p.strip() for p in s.splitlines()).strip()


def parse_list(text: str) -> list[dict]:
    out, seen = [], set()
    for block in re.split(r'<div class="tb-name">', text)[1:]:
        m = re.search(r"other_id(?:%5D|\])=(\d+)", block)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        t = re.search(r"<h4>.*?>(.*?)</a></h4>", block, re.S)
        out.append({"profile_id": m.group(1), "title": _text(t.group(1)) if t else None})
    return out


def parse_trl(s: str | None) -> int | None:
    m = re.match(r"\s*TRL\s*([1-9])\b", s or "")
    return int(m.group(1)) if m else None


def _iso_date(s: str) -> str | None:
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if m:
        return m.group(0)
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def parse_detail(text: str) -> dict:
    body = text[text.find("catalogue-detail__content"):] if "catalogue-detail__content" in text else ""
    body = body.split("Back to Pipeline")[0]
    fields = re.findall(r'<div class="catalogue-field">(.*?)</div>(?=<div class="catalogue-field">|<hr>|</div></div>)', body, re.S)
    d = {"title": None, "description": None, "sector": None, "company_name": None, "country": None, "trl": None, "listed_date": None}
    if not body:
        return d
    labelled = {}
    for lab, val in re.findall(r"<span class='catalogue-detail-label[^']*'>(.*?)</span>(.*?)(?=<span class='catalogue-detail-label|<hr>|</div></div>)", body, re.S):
        labelled[_text(lab)] = _text(val)
    if fields:
        d["title"] = _text(fields[0]) or None
    if len(fields) > 1:
        d["description"] = _text(fields[1]) or None
    sm = re.search(r"keywords-catalogue-view[^>]*>(.*?)</ul>", body, re.S)
    if sm:
        d["sector"] = "; ".join(_text(x) for x in re.findall(r"<li[^>]*>(.*?)</li>", sm.group(1), re.S)) or None
    m = re.search(r"Company behind project</span><br />(?:<a[^>]*>)?(.*?)(?:</a>)?<br /><br /><div class=\"catalogue-field\">(.*?)<br />", body, re.S)
    if m:
        d["company_name"] = _text(m.group(1)) or None
        d["country"] = _text(m.group(2)) or None
    if d["sector"] and d["sector"].startswith("TRL"):
        d["sector"] = None
    d["trl"] = parse_trl(labelled.get("TRL"))
    for lab, val in labelled.items():
        if _DATE_LABEL.search(lab) and not _UPDATED.search(lab):
            d["listed_date"] = _iso_date(val)
            if d["listed_date"]:
                break
    return d


def _declared_links() -> list[tuple[str, str]]:
    """[(declared company name, profile_id)] from the declared CSV blueinvest_url column (read only)."""
    out = []
    if not DECLARED_CSV.exists():
        return out
    with open(DECLARED_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m = re.search(r"other_id(?:%5D|\])=(\d+)", r.get("blueinvest_url") or "")
            if m:
                out.append((r["company"], m.group(1)))
    return out


def run(conn, thesis: dict, fetcher: Fetcher | None = None, declared: list[tuple[str, str]] | None = None) -> dict:
    if "blueinvest" not in (thesis.get("feed_signal_types") or []):
        return {"skipped": "thesis has no blueinvest source"}
    f = fetcher or Fetcher()
    res = {"companies": 0, "signals": 0, "skipped": 0, "profiles": 0, "finnish": 0, "with_trl": 0, "linked_declared": 0,
           "requests": 0, "blocked": ""}
    declared = _declared_links() if declared is None else declared
    by_name = {}
    for r in conn.execute("SELECT company_key, name FROM companies"):
        by_name.setdefault(fold(r["name"]), r["company_key"])
    fin: list[str] = []
    cc_of: dict[str, str] = {}
    try:
        if not robots_allows(_robots(f)):
            res["blocked"] = "robots.txt disallows the pipeline path"
            res["requests"] = f.requests
            return res
        for cc in thesis_mod.countries(thesis):  # one list per thesis country (FI only by default)
            page = 1
            while True:
                items = parse_list(f.get(list_url(page, cc)))
                for i in items:
                    if i["profile_id"] not in fin:
                        fin.append(i["profile_id"])
                        cc_of[i["profile_id"]] = cc
                if len(items) < 20:
                    break
                page += 1
        dname = {pid: name for name, pid in declared}
        for pid in fin + [p for p in dname if p not in fin]:
            try:
                d = parse_detail(f.get(detail_url(pid)))
            except OSError as e:
                _log.warning("profile %s skipped: %s", pid, e)
                res["skipped"] += 1
                continue
            _store(conn, pid, d, dname.get(pid), by_name, res, finnish=pid in fin, country=cc_of.get(pid, "FI"))
    except Blocked as e:
        res["blocked"] = str(e)
        _log.warning("BLOCKED: %s", e)
    res["requests"] = f.requests
    return res


def _robots(f: Fetcher) -> str:
    try:
        return f.get(f"{HOST}/robots.txt")
    except OSError:
        return ""  # 404 and similar: no restrictions published


def _store(conn, pid, d, declared_name, by_name, res, finnish, country="FI"):  # `finnish` = in the thesis countries
    url = detail_url(pid)
    key, how = None, None
    if declared_name:
        key = by_name.get(fold(declared_name))
        if key:
            how = "high"
            res["linked_declared"] += 1
    if key is None and finnish and len(fold(d["company_name"])) < 3 and d["company_name"]:
        res["skipped"] += 1  # too short to be a trustworthy company name (the page title may hold the real one): profile kept, no company
    elif key is None and finnish and fold(d["company_name"]):
        key = by_name.get(fold(d["company_name"]))
        if key:
            how = "medium"
        else:
            key, how = f"name:{slug(d['company_name'])}", "high"
            emit.upsert_company(conn, company_key=key, name=d["company_name"], source_url=url, country=country, group_tag="feed")
            by_name[fold(d["company_name"])] = key
            res["companies"] += 1
    if finnish:
        res["finnish"] += 1
    if d["trl"] is not None:
        res["with_trl"] += 1
    res["profiles"] += 1
    conn.execute(
        """INSERT INTO blueinvest_profiles (profile_id,company_key,title,company_name,country,trl,sector,description,url,listed_date,fetched_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(profile_id) DO UPDATE SET company_key=excluded.company_key,title=excluded.title,company_name=excluded.company_name,
             country=excluded.country,trl=excluded.trl,sector=excluded.sector,description=excluded.description,url=excluded.url,
             listed_date=excluded.listed_date,fetched_at=excluded.fetched_at""",
        (pid, key, d["title"], d["company_name"], d["country"], d["trl"], d["sector"], d["description"], url, d["listed_date"], emit.now_utc()),
    )
    if key and d["listed_date"]:
        trl = f"TRL {d['trl']}" if d["trl"] is not None else "TRL not stated"
        if emit.emit_signal(conn, company_key=key, signal_type="blueinvest", date=d["listed_date"], source_url=url, confidence=how,
                            adapter=NAME, detail=f"Listed in the BlueInvest project pipeline, {trl}, sector {d['sector'] or 'not stated'}"):
            res["signals"] += 1


if __name__ == "__main__":
    import sys
    from radar import db
    logging.basicConfig(level=logging.INFO)
    c = db.connect()
    out = run(c, thesis_mod.load())
    c.commit()
    print(out)
    sys.exit(0)
