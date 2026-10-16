"""PRH registered-notices adapter, offline on a synthetic fixture shaped like the API (Fixture Oy, 0000000-0)."""
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from prh_notices_fixture import notice, page  # noqa: E402

from radar import db, emit  # noqa: E402
from radar.adapters import prh_notices as pn  # noqa: E402

TODAY = date(2026, 10, 16)
THESIS = {"geography": {"stage_max_company_age_years": 5}, "industry_codes": [{"code": "30110"}],
          "name_keywords": {"en": ["marine", "ship"]}}


def fake_fetcher(by_key):
    """by_key maps (entryCode or typeOfRegistration or businessId, page) to a response page."""
    def f(params):
        key = params.get("entryCode") or params.get("typeOfRegistration") or params.get("businessId")
        return by_key.get((key, params.get("page", 1)), page([]))
    return f


@pytest.fixture
def conn():
    return db.connect(":memory:")


def test_types_registered_and_mapped():
    assert {"equity_event", "board_change", "capital_loss", "startup_notice"} <= set(emit.SIGNAL_TYPES)
    assert {c: v[0] for c, v in pn.CODES.items()} == {
        "ANTIP": "equity_event", "ANTIK": "equity_event", "OANTI": "equity_event", "OANKO": "equity_event",
        "KOROI": "equity_event", "OPTIO": "equity_event", "HAL": "board_change", "OPOMEN": "capital_loss"}
    n = pn.parse_notice(notice(codes=("HAL",), kind="U"))
    assert [c[0] for c in pn.classify(n)] == ["board_change", "startup_notice"]


def test_window_emits_equity_event(conn):
    f = fake_fetcher({("ANTIP", 1): page([notice()])})
    res = pn.run(conn, THESIS, today=TODAY, fetcher=f)
    s = conn.execute("select * from signals").fetchall()
    assert len(s) == 1 and res["signals"] == 1 and res["companies"] == 1
    assert s[0]["signal_type"] == "equity_event" and s[0]["date"] == "2026-09-10" and s[0]["confidence"] == "high"
    assert s[0]["source_url"] == "https://avoindata.prh.fi/opendata-registerednotices-api/v3/0000000-0"
    assert "Decision to issue shares" in s[0]["detail"] and "FX-1" in s[0]["detail"]


def test_five_year_and_thesis_filter(conn):
    old = notice(bid="0000001-1", name="Old Fixture Oy", founded="2018-01-01")
    off = notice(bid="0000002-2", name="Off Fixture Oy", industry="62010", desc="Computer programming")
    by_desc = notice(bid="0000003-3", name="Desc Fixture Oy", industry="99999", desc="Marine services")
    res = pn.run(conn, THESIS, today=TODAY, fetcher=fake_fetcher({("KOROI", 1): page([old, off, by_desc])}))
    keys = {r[0] for r in conn.execute("select company_key from signals")}
    assert keys == {"0000003-3"} and res["skipped"] == 2


def test_missing_registration_date_is_skipped(conn):
    assert pn.parse_notice(notice(reg=None)) is None
    assert pn.parse_notice(notice(reg="2026-09")) is None
    res = pn.run(conn, THESIS, today=TODAY, fetcher=fake_fetcher({("OPTIO", 1): page([notice(reg=None)])}))
    assert conn.execute("select count(*) from signals").fetchone()[0] == 0 and res["skipped"] == 1


def test_paging(conn):
    first = [notice(bid=f"{i:07d}-1", name=f"Fixture {i} Oy", number=str(i)) for i in range(pn.PAGE_SIZE)]
    second = [notice(bid="9999999-9", name="Last Fixture Oy")]
    res = pn.run(conn, THESIS, today=TODAY, fetcher=fake_fetcher({("ANTIK", 1): page(first), ("ANTIK", 2): page(second)}))
    assert conn.execute("select count(*) from signals").fetchone()[0] == pn.PAGE_SIZE + 1 and res["companies"] == pn.PAGE_SIZE + 1


def test_startup_and_capital_loss_and_board(conn):
    f = fake_fetcher({("U", 1): page([notice(codes=(), kind="U", number="U-1")]),
                      ("OPOMEN", 1): page([notice(bid="0000004-4", name="Loss Fixture Oy", codes=("OPOMEN",))]),
                      ("HAL", 1): page([notice(bid="0000005-5", name="Board Fixture Oy", codes=("HAL",))])})
    pn.run(conn, THESIS, today=TODAY, fetcher=f)
    got = {r["signal_type"] for r in conn.execute("select signal_type from signals")}
    assert got == {"startup_notice", "capital_loss", "board_change"}


def test_company_mode_five_years(conn):
    emit.upsert_company(conn, company_key="0000000-0", name="Fixture Oy", source_url="https://example.org/f", y_tunnus="0000000-0")
    f = fake_fetcher({("0000000-0", 1): page([notice(reg="2025-05-05"), notice(reg="2019-01-01", number="OLD")])})
    res = pn.run(conn, {"industry_codes": []}, today=TODAY, fetcher=f)
    dates = [r[0] for r in conn.execute("select date from signals")]
    assert dates == ["2025-05-05"] and res["touched"] == 1


class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._b = code, body or {"results": []}

    def json(self):
        return self._b

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=None, response=None)


class _Client:
    def __init__(self, codes):
        self.codes, self.calls = list(codes), 0

    def get(self, url):
        self.calls += 1
        return _Resp(self.codes.pop(0))


def test_429_backoff(tmp_path, monkeypatch):
    monkeypatch.setattr(pn, "CACHE", tmp_path)
    sleeps = []
    c = _Client([429, 200])
    data = pn.fetch({"entryCode": "ANTIP"}, client=c, sleep=sleeps.append)
    assert data == {"results": []} and c.calls == 2 and pn.BACKOFF_SECONDS in sleeps
    again = _Client([])
    pn.fetch({"entryCode": "ANTIP"}, client=again, sleep=sleeps.append)  # served from cache
    assert again.calls == 0


def test_offline_run_reports_blocked(conn):
    def boom(params):
        raise httpx.ConnectError("no route")
    res = pn.run(conn, THESIS, today=TODAY, fetcher=boom)
    assert res["blocked"] == 1 and res["signals"] == 0
