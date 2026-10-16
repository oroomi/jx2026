"""Declared cohort and portfolio companies: data/declared/cohort_portfolio_companies.csv -> companies. Emits no signals."""
from __future__ import annotations

import csv
import re
import sqlite3
import unicodedata
from pathlib import Path

from radar import emit

PHASE = 0
NAME = "declared"
CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "declared" / "cohort_portfolio_companies.csv"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def slug(country: str, name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return f"{country.lower()}-{s}"


def _http(*values: str) -> str | None:
    for v in values:
        v = (v or "").strip()
        if v.startswith(("http://", "https://")):
            return v
    return None


def _status(raw: str) -> str | None:
    raw = (raw or "").strip().lower()
    if not raw:
        return None
    if "bankrupt" in raw or "konk" in raw:
        return "bankrupt"
    if raw.startswith("registered"):
        return "active"
    return "unknown"


def run(conn: sqlite3.Connection, thesis: dict | None = None) -> dict:
    companies = skipped = 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = r["company"].strip()
            ytj = r["y_tunnus"].strip() or None
            country = (r["country"].strip()[:2].upper()) or None
            # source_url: the YTJ link, else the company site, else the declared evidence link; always a link a human can open
            src = _http(r["ytj_source"], r["website"], r["customers_url"])
            if not src:
                skipped += 1
                continue
            reg = r["ytj_registration_date"].strip()
            emit.upsert_company(
                conn, company_key=ytj or slug(country or "xx", name), name=(r["ytj_name"].strip() or name), source_url=src,
                y_tunnus=ytj, country=country, founded=reg if _DATE.match(reg) else None,
                industry_code=r["ytj_industry_code"].strip() or None, industry_desc=r["ytj_industry_desc"].strip() or None,
                website=_http(r["website"]), group_tag=r["group"].strip(), register_status=_status(r["ytj_status"]))
            companies += 1
    conn.commit()
    return {"companies": companies, "signals": 0, "skipped": skipped}


if __name__ == "__main__":
    from radar import db
    print(run(db.connect()))
