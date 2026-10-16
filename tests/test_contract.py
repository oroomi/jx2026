import sqlite3
import pytest
from radar import db, emit


def _conn():
    return db.connect(":memory:")


def test_company_and_signal_roundtrip():
    c = _conn()
    emit.upsert_company(c, company_key="3543918-7", name="Emission-Eye Oy", source_url="https://avoindata.prh.fi/en/ytj/swagger-ui", y_tunnus="3543918-7", founded="2025-06-13")
    assert emit.emit_signal(c, company_key="3543918-7", signal_type="register_entry", date="2025-06-13", source_url="https://example.org/x", confidence="high", adapter="prh")
    assert not emit.emit_signal(c, company_key="3543918-7", signal_type="register_entry", date="2025-06-13", source_url="https://example.org/x", confidence="high", adapter="prh")
    assert c.execute("select count(*) from signals").fetchone()[0] == 1


def test_rejects_malformed_events():
    c = _conn()
    emit.upsert_company(c, company_key="k", name="K", source_url="https://example.org")
    for bad in ({"signal_type": "nope"}, {"confidence": "sure"}, {"date": "2025-6-1"}, {"source_url": "prh"}):
        kw = dict(company_key="k", signal_type="patent", date="2025-06-01", source_url="https://example.org/p", confidence="low", adapter="t")
        kw.update(bad)
        with pytest.raises(ValueError):
            emit.emit_signal(c, **kw)


def test_cohort_tag_never_downgraded():
    c = _conn()
    emit.upsert_company(c, company_key="k", name="K", source_url="https://example.org", group_tag="cohort")
    emit.upsert_company(c, company_key="k", name="K", source_url="https://example.org", group_tag="feed")
    assert c.execute("select group_tag from companies").fetchone()[0] == "cohort"


def test_foreign_key_enforced():
    c = _conn()
    with pytest.raises(sqlite3.IntegrityError):
        emit.emit_signal(c, company_key="missing", signal_type="patent", date="2025-06-01", source_url="https://example.org/p", confidence="low", adapter="t")
