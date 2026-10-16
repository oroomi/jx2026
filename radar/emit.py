"""The only way an adapter writes. One event shape: company, signal_type, date, source_url, confidence.

Confidence rule (printed in the UI beside every signal):
  high   = the source names the company or its business id directly and states the date.
  medium = matched by an exact legal name or website domain, date stated by the source.
  low    = matched by name keyword or industry code only; shown, but never counted in rankings.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

SIGNAL_TYPES = (
    "register_entry",      # new entry in a trade register (PRH/YTJ), date = registration date
    "bf_funding",          # Business Finland funding decision
    "eu_project",          # CORDIS / EU funding participation
    "blueinvest",          # listed in the BlueInvest project pipeline
    "patent",              # patent filing (Espacenet)
    "public_contract",     # public contract awarded (Hilma)
    "job_ad",              # open job posting (Finnish open-jobs API)
    "site_customer",       # customer or partner named on the company's own site
    "first_sales",         # earliest VAT-liability or prepayment register entry (tax_registers)
    "first_hire",          # employer register entry: first salary could be paid (tax_registers)
    "sales_ended",         # VAT-liability and prepayment entries all ended (negative)
    "employer_ended",      # employer register entry ended (negative)
    "research_output",     # OpenAlex work whose author affiliation names the company
    "website_first_seen",  # first 200 capture of the company website in the web archive
    "website_milestone",   # first archived capture of a customers, careers or pricing page
)
CONFIDENCE = ("high", "medium", "low")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def upsert_company(conn: sqlite3.Connection, *, company_key: str, name: str, source_url: str, y_tunnus: str | None = None,
                   country: str | None = None, founded: str | None = None, industry_code: str | None = None,
                   industry_desc: str | None = None, website: str | None = None, group_tag: str = "feed",
                   register_status: str | None = None) -> None:
    """Insert or update a company. A non-null new value replaces the old one; NULL never erases. group_tag cohort/portfolio is never downgraded to feed."""
    if not company_key or not name or not source_url:
        raise ValueError("company_key, name and source_url are required")
    if founded is not None and not _DATE.match(founded):
        raise ValueError(f"founded must be YYYY-MM-DD, got {founded!r}")
    conn.execute(
        """INSERT INTO companies (company_key,name,y_tunnus,country,founded,industry_code,industry_desc,website,group_tag,register_status,source_url,fetched_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(company_key) DO UPDATE SET
             name=excluded.name,
             y_tunnus=COALESCE(excluded.y_tunnus,y_tunnus), country=COALESCE(excluded.country,country),
             founded=COALESCE(excluded.founded,founded), industry_code=COALESCE(excluded.industry_code,industry_code),
             industry_desc=COALESCE(excluded.industry_desc,industry_desc), website=COALESCE(excluded.website,website),
             group_tag=CASE WHEN companies.group_tag IN ('cohort','portfolio') THEN companies.group_tag ELSE excluded.group_tag END,
             register_status=COALESCE(excluded.register_status,register_status),
             source_url=excluded.source_url, fetched_at=excluded.fetched_at""",
        (company_key, name, y_tunnus, country, founded, industry_code, industry_desc, website, group_tag, register_status, source_url, now_utc()),
    )


def emit_signal(conn: sqlite3.Connection, *, company_key: str, signal_type: str, date: str, source_url: str, confidence: str,
                adapter: str, detail: str | None = None, amount_eur: float | None = None) -> bool:
    """Insert one signal. Returns True if new, False if it already existed. Raises on a malformed event; never fabricates."""
    if signal_type not in SIGNAL_TYPES:
        raise ValueError(f"unknown signal_type {signal_type!r}")
    if confidence not in CONFIDENCE:
        raise ValueError(f"unknown confidence {confidence!r}")
    if not _DATE.match(date or ""):
        raise ValueError(f"date must be YYYY-MM-DD, got {date!r}")
    if not source_url or not source_url.startswith(("http://", "https://")):
        raise ValueError("source_url must be an http(s) link a human can open")
    cur = conn.execute(
        """INSERT OR IGNORE INTO signals (company_key,signal_type,date,source_url,confidence,adapter,detail,amount_eur,fetched_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (company_key, signal_type, date, source_url, confidence, adapter, detail, amount_eur, now_utc()),
    )
    return cur.rowcount == 1
