"""Test-only builder: two labelled SYNTHETIC databases, one per thesis, written through radar.emit. Never loaded by the app."""
from __future__ import annotations

from datetime import date, timedelta

from radar import db, emit


def day(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def build(path, names: list[str], prefix: str):
    conn = db.connect(path)
    for i, name in enumerate(names):
        key = f"{prefix}-{i}"
        emit.upsert_company(conn, company_key=key, name=name, source_url=f"https://example.test/synthetic/{key}")
        emit.emit_signal(conn, company_key=key, signal_type="register_entry", date=day(5 + i), confidence="high",
                         adapter="prh", source_url=f"https://example.test/synthetic/{key}/reg")
    conn.commit()
    conn.close()
