import importlib.util
from pathlib import Path

from radar import db, emit
from radar.adapters import hilma

_spec = importlib.util.spec_from_file_location("hilma_test_fixture", Path(__file__).parent / "fixtures" / "hilma_test_fixture.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

THESIS = {"geography": {"stage_max_company_age_years": 5}, "hilma_cpv_divisions": ["71"], "hilma_keywords": ["meri"]}


def _setup(with_cohort=True, cohort_win=True):
    conn = db.connect(":memory:")
    if with_cohort:
        emit.upsert_company(conn, company_key="7777777-7", name="Fixture Cohort Oy", y_tunnus="7777777-7",
                            source_url="https://example.org/c", group_tag="cohort")
    res = hilma.run(conn, THESIS, awards_conn=fx.build(with_cohort_win=cohort_win))
    return conn, res


def _keys(conn):
    return {r["company_key"] for r in conn.execute("SELECT company_key FROM signals")}


def test_young_filter_and_thesis_match():
    conn, res = _setup()
    keys = _keys(conn)
    assert "1111111-1" in keys and "4444444-4" in keys  # cpv match, keyword match
    assert "2222222-2" not in keys                      # registered 2001: not young
    assert "3333333-3" not in keys                      # young but off-thesis
    assert res["matched"] == 2


def test_first_win_only():
    conn, _ = _setup()
    rows = conn.execute("SELECT date, source_url, detail, amount_eur, confidence FROM signals WHERE company_key='1111111-1'").fetchall()
    assert len(rows) == 1 and rows[0]["date"] == "2026-03-01"
    assert rows[0]["source_url"] == "https://www.hankintailmoitukset.fi/fi/public/procedure/11/enotice/1"
    assert rows[0]["detail"] == "Testbuyer A: Fixture survey (EUR 50,000)" and rows[0]["amount_eur"] == 50000.0
    assert rows[0]["confidence"] == "high"
    # in-thesis win that is not the company's first win in the archive is not emitted
    assert "6666666-6" not in _keys(conn)


def test_missing_registration_is_skipped_not_guessed():
    conn, res = _setup()
    assert "5555555-5" not in _keys(conn)
    assert res["skipped"] == 1
    assert conn.execute("SELECT founded FROM companies WHERE company_key='1111111-1'").fetchone()[0] == "2024-06-01"


def test_amount_absent_stays_null():
    conn, _ = _setup()
    r = conn.execute("SELECT amount_eur, detail FROM signals WHERE company_key='4444444-4'").fetchone()
    assert r["amount_eur"] is None and "EUR" not in r["detail"]


def test_cohort_any_win_is_emitted():
    conn, res = _setup()
    assert res["cohort_hits"] == 1
    r = conn.execute("SELECT group_tag FROM companies WHERE company_key='7777777-7'").fetchone()
    assert r["group_tag"] == "cohort" and "7777777-7" in _keys(conn)


def test_zero_cohort_hits_path():
    conn, res = _setup(cohort_win=False)
    assert res["cohort_hits"] == 0 and "7777777-7" not in _keys(conn)
    assert res["signals"] == 2


def test_read_only_open_mode():
    assert hilma.AWARDS_DB_URI == "file:/opt/portfolio/tenderhub/data/awards_deep.sqlite?mode=ro"
    assert "mode=ro" in Path(hilma.__file__).read_text()


def test_legacy_notice_without_verified_page_is_not_emitted():
    conn = db.connect(":memory:")
    a = fx.build()
    a.execute("UPDATE awards SET noticeId='OLD-1' WHERE noticeId='EF-1'")
    a.execute("UPDATE award_winners SET noticeId='OLD-1' WHERE noticeId='EF-1'")
    hilma.run(conn, THESIS, awards_conn=a)
    assert "1111111-1" not in _keys(conn)
