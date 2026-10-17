"""Test-only builder for the judge round-3 fixes: SYNTHETIC companies with every signal type a page can print. Never loaded by the app."""
from __future__ import annotations

from datetime import date, timedelta

from radar import db, emit
from radar.adapters import ecosystem, prh_notices, stitcher  # noqa: F401  (register their signal types on emit.SIGNAL_TYPES)

PRH = "https://example.test/synthetic-prh?businessId="
TODAY = date.today()


def d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


def build(path):
    conn = db.connect(path)
    # a declared cohort company with a business id, a thesis industry code and every kind of record
    emit.upsert_company(conn, company_key="9300001-1", name="Synthetic Harbour Boats Oy", y_tunnus="9300001-1", country="FI",
                        founded="2023-02-01", industry_code="30120", industry_desc="Building of pleasure and sporting boats",
                        group_tag="cohort", register_status="active", source_url=PRH + "9300001-1")
    sigs = [("register_entry", "2023-02-01", "prh"), ("startup_notice", "2023-02-02", "prh_notices"),
            ("board_change", "2024-03-01", "prh_notices"), ("equity_event", "2024-05-01", "prh_notices"),
            ("first_sales", "2023-06-01", "tax_registers"), ("first_hire", "2024-01-01", "tax_registers"),
            ("research_output", "2025-01-10", "openalex"), ("public_funding", "2025-03-01", "ecosystem"),
            ("bf_funding", "2025-01-01", "businessfinland")]
    for i, (t, dt, ad) in enumerate(sigs):
        emit.emit_signal(conn, company_key="9300001-1", signal_type=t, date=dt, source_url=f"https://example.test/{ad.replace('_', '-')}/{i}",
                         confidence="high", adapter=ad, detail=f"Synthetic {t.replace('_', ' ')} record.")
    # a cohort company with a business id, an Oy name and no thesis evidence (code off the list, no intake profile stored)
    emit.upsert_company(conn, company_key="9300006-6", name="Synthetic Sauna Shop Oy", y_tunnus="9300006-6", country="FI", founded="2024-05-01",
                        industry_code="46900", industry_desc="Non-specialised wholesale trade", group_tag="cohort", source_url=PRH + "9300006-6")
    emit.emit_signal(conn, company_key="9300006-6", signal_type="register_entry", date="2024-05-01", source_url=PRH + "9300006-6",
                     confidence="high", adapter="prh")
    emit.emit_signal(conn, company_key="9300006-6", signal_type="first_sales", date="2024-06-01", source_url="https://example.test/tax/6",
                     confidence="high", adapter="tax_registers")
    # a cohort company with no business id (non-Finnish)
    emit.upsert_company(conn, company_key="dk-synthetic", name="Synthetic Reef", country="DK", group_tag="cohort",
                        source_url="https://example.test/declared/dk")
    # feed companies inside the window: a name-word company corroborated only by PRH notices, one by a non-PRH source
    emit.upsert_company(conn, company_key="9300002-2", name="Ocean Media Synthetic Oy", y_tunnus="9300002-2", founded=d(20),
                        industry_code="59110", industry_desc="Motion picture production", source_url=PRH + "9300002-2")
    emit.emit_signal(conn, company_key="9300002-2", signal_type="register_entry", date=d(20), source_url=PRH + "9300002-2",
                     confidence="high", adapter="prh")
    emit.emit_signal(conn, company_key="9300002-2", signal_type="startup_notice", date=d(18), source_url="https://example.test/notice/2",
                     confidence="high", adapter="prh_notices")
    emit.emit_signal(conn, company_key="9300002-2", signal_type="first_sales", date=d(15), source_url="https://example.test/tax/2",
                     confidence="high", adapter="tax_registers")
    emit.upsert_company(conn, company_key="9300003-3", name="Marine Synthetic Labs Oy", y_tunnus="9300003-3", founded=d(30),
                        industry_code="72190", industry_desc="Other research", source_url=PRH + "9300003-3")
    emit.emit_signal(conn, company_key="9300003-3", signal_type="register_entry", date=d(30), source_url=PRH + "9300003-3",
                     confidence="high", adapter="prh")
    emit.emit_signal(conn, company_key="9300003-3", signal_type="eu_project", date=d(10), source_url="https://example.test/cordis/3",
                     confidence="medium", adapter="cordis", detail="Synthetic project.")
    # a listed company (Oyj) with a thesis industry code: never in the feed
    emit.upsert_company(conn, company_key="9300004-4", name="Synthetic Shipping Oyj", y_tunnus="9300004-4", founded=d(40),
                        industry_code="50200", industry_desc="Sea and coastal freight water transport", source_url=PRH + "9300004-4")
    emit.emit_signal(conn, company_key="9300004-4", signal_type="register_entry", date=d(40), source_url=PRH + "9300004-4",
                     confidence="high", adapter="prh")
    emit.emit_signal(conn, company_key="9300004-4", signal_type="equity_event", date=d(12), source_url="https://example.test/notice/4",
                     confidence="high", adapter="prh_notices")
    # a feed company on the thesis code list, recent, with a startup notice and website milestone
    emit.upsert_company(conn, company_key="9300005-5", name="Synthetic Port Tools Oy", y_tunnus="9300005-5", founded=d(25),
                        industry_code="52220", industry_desc="Service activities incidental to water transportation", source_url=PRH + "9300005-5")
    emit.emit_signal(conn, company_key="9300005-5", signal_type="register_entry", date=d(25), source_url=PRH + "9300005-5",
                     confidence="high", adapter="prh")
    emit.emit_signal(conn, company_key="9300005-5", signal_type="startup_notice", date=d(24), source_url="https://example.test/notice/5",
                     confidence="high", adapter="prh_notices")
    emit.emit_signal(conn, company_key="9300005-5", signal_type="website_milestone", date=d(5), source_url="https://example.test/web/5",
                     confidence="medium", adapter="webarchive")
    conn.commit()
    return conn
