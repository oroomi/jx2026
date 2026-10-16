"""Hilma adapter: young companies whose FIRST public contract win is in the thesis categories.

Reads the tenderhub awards archive strictly read-only and copies only the rows it uses into signals.
Run: python3 -m radar.adapters.hilma
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date

from radar import emit

NAME = "hilma"
AWARDS_DB_URI = "file:/opt/portfolio/tenderhub/data/awards_deep.sqlite?mode=ro"
# eForms notices only (noticeId "EF-<n>"). The older template .../procurement/{pid}/notice/{id}/overview shows
# "Ilmoitusta ei loytynyt" for every archive notice; this route was click-tested and renders the notice.
NOTICE_URL = "https://www.hankintailmoitukset.fi/fi/public/procedure/{procedure_id}/enotice/{notice_number}"

# One row per (winner, award). Winners are only counted when the archive names a business id.
_WIN_SQL = """
SELECT w.businessId AS business_id, w.rawName AS raw_name, a.noticeId AS notice_id, a.published AS published,
       a.buyer AS buyer, a.title AS title, a.amountEur AS amount_eur, a.cpv AS cpv, a.procedure_id AS procedure_id
FROM award_winners w JOIN awards a ON a.noticeId = w.noticeId
WHERE w.businessId IS NOT NULL AND w.businessId != ''
ORDER BY w.businessId, a.published, a.noticeId
"""


def open_awards_ro(uri: str = AWARDS_DB_URI) -> sqlite3.Connection:
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _iso_date(value) -> date | None:
    """Full ISO date (YYYY-MM-DD, optional time suffix) or None. Never guesses partial dates."""
    if not value or len(str(value)) < 10:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _is_young(registered: date, awarded: date, max_years: int) -> bool:
    if registered > awarded:
        return False
    try:
        limit = registered.replace(year=registered.year + max_years)
    except ValueError:  # 29 Feb
        limit = registered.replace(year=registered.year + max_years, day=28)
    return awarded <= limit


def _matches_thesis(row, divisions: set[str], keywords: list[str]) -> bool:
    cpv = (row["cpv"] or "").strip()
    if cpv[:2] in divisions:
        return True
    title = (row["title"] or "").casefold()
    return any(k.casefold() in title for k in keywords)


def _detail(row) -> str:
    amount = row["amount_eur"]
    base = f"{row['buyer'] or 'buyer not stated'}: {row['title'] or 'title not stated'}"
    return f"{base} (EUR {amount:,.0f})" if amount else base


def _notice_link(row) -> str | None:
    nid = str(row["notice_id"] or "")
    if not row["procedure_id"] or not re.fullmatch(r"EF-\d+", nid):
        return None  # legacy OLD- notices have no verified public page
    return NOTICE_URL.format(procedure_id=row["procedure_id"], notice_number=nid[3:])


def _cohort_index(conn: sqlite3.Connection):
    by_id, by_name = {}, {}
    for r in conn.execute("SELECT company_key, name, y_tunnus FROM companies WHERE group_tag IN ('cohort','portfolio')"):
        if r["y_tunnus"]:
            by_id[r["y_tunnus"]] = r["company_key"]
        by_name[r["name"].casefold()] = r["company_key"]
    return by_id, by_name


def run(conn: sqlite3.Connection, thesis: dict, awards_conn: sqlite3.Connection | None = None) -> dict:
    max_years = int(thesis["geography"]["stage_max_company_age_years"])
    divisions = {str(d) for d in thesis.get("hilma_cpv_divisions", [])}
    keywords = list(thesis.get("hilma_keywords", []))
    own = awards_conn is None
    src = awards_conn or open_awards_ro()
    try:
        profiles = {r["businessId"]: r for r in src.execute(
            "SELECT businessId, name, officialName, tolCode, tolDesc, website, registered FROM companies")}
        cohort_id, cohort_name = _cohort_index(conn)
        counts = dict(examined=0, matched=0, signals=0, skipped=0, cohort_hits=0)
        matched, seen = set(), set()
        for row in src.execute(_WIN_SQL):
            counts["examined"] += 1
            bid = row["business_id"]
            prof = profiles.get(bid)
            published = _iso_date(row["published"])
            link = _notice_link(row)
            if published is None:
                continue
            # Cohort/portfolio company: any win counts.
            names = {n.casefold() for n in (row["raw_name"], prof and prof["name"], prof and prof["officialName"]) if n}
            key = cohort_id.get(bid) or next((cohort_name[n] for n in names if n in cohort_name), None)
            if key and link:
                if emit.emit_signal(conn, company_key=key, signal_type="public_contract", date=published.isoformat(),
                                    source_url=link, confidence="high", adapter=NAME, detail=_detail(row),
                                    amount_eur=row["amount_eur"] or None):
                    counts["signals"] += 1
                counts["cohort_hits"] += 1
                continue
            # Discovery company: first win only, young, in the thesis categories.
            if key:
                continue
            if bid in seen:
                continue
            seen.add(bid)
            if link is None or not _matches_thesis(row, divisions, keywords):
                continue
            registered = _iso_date(prof["registered"]) if prof else None
            if prof is None or registered is None or not _is_young(registered, published, max_years):
                if prof is None or registered is None:
                    counts["skipped"] += 1
                continue
            emit.upsert_company(conn, company_key=bid, name=prof["officialName"] or prof["name"] or row["raw_name"],
                                source_url=link, y_tunnus=bid, country="FI", founded=registered.isoformat(),
                                industry_code=prof["tolCode"], industry_desc=prof["tolDesc"],
                                website=prof["website"], group_tag="feed")
            if emit.emit_signal(conn, company_key=bid, signal_type="public_contract", date=published.isoformat(),
                                source_url=link, confidence="high", adapter=NAME, detail=_detail(row),
                                amount_eur=row["amount_eur"] or None):
                counts["signals"] += 1
            matched.add(bid)
        counts["matched"] = len(matched)
        conn.commit()
        return counts
    finally:
        if own:
            src.close()


if __name__ == "__main__":
    from radar import db, thesis as thesis_mod

    c = db.connect()
    res = run(c, thesis_mod.load())
    print(f"hilma: examined awards={res['examined']} matched companies={res['matched']} signals={res['signals']} "
          f"skipped (no usable registration date)={res['skipped']} cohort/portfolio hits={res['cohort_hits']}")
    if res["cohort_hits"] == 0:
        print("hilma: none of the cohort/portfolio companies appears as a winner (not in public records)")
