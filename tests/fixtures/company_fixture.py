"""Test-only builder: labelled SYNTHETIC companies for the company page. Never loaded by the app."""
from __future__ import annotations

from radar import db, emit

PRH = "https://example.test/synthetic-prh?businessId="


def build(path):
    conn = db.connect(path)
    emit.upsert_company(conn, company_key="9000001-1", name="Synthetic Rich Oy", y_tunnus="9000001-1", country="FI", founded="2025-06-13",
                        industry_code="30110", industry_desc="Synthetic shipbuilding", website="https://rich.example.test",
                        group_tag="cohort", register_status="active", source_url=PRH + "9000001-1")
    emit.emit_signal(conn, company_key="9000001-1", signal_type="register_entry", date="2025-06-13", source_url=PRH + "9000001-1",
                     confidence="high", adapter="prh", detail="Synthetic registration.")
    emit.emit_signal(conn, company_key="9000001-1", signal_type="eu_project", date="2026-03-01", source_url="https://example.test/cordis/1",
                     confidence="medium", adapter="cordis", detail="Synthetic EU project.")
    emit.upsert_company(conn, company_key="name:sparse", name="Synthetic Sparse", group_tag="cohort", source_url="https://example.test/declared")
    emit.upsert_company(conn, company_key="9000003-3", name="Marine Synthetic Oy", y_tunnus="9000003-3", register_status="bankrupt",
                        industry_code="62100", source_url=PRH + "9000003-3")
    emit.upsert_company(conn, company_key="9000004-4", name="Plain Words Oy", y_tunnus="9000004-4", industry_code="71200",
                        source_url=PRH + "9000004-4")
    conn.commit()
    return conn
