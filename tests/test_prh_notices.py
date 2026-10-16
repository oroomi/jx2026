"""prh_notices adapter, offline. The synthetic fixtures below imitate the registered-notices API shape ("Fixture Oy")."""
from datetime import date

import httpx
import pytest

from radar import db, emit
from radar.adapters import prh_notices as pn

TODAY = date(2026, 10, 16)
THESIS = {"industry_codes": [{"code": "30110"}], "name_keywords": {"en": ["marine", "ship"]}}


def company(bid, name, founded, code, desc, notices):
    return {"businessId": {"value": bid, "registrationDate": founded}, "names": [{"name": name, "type": "1"}],
            "mainBusinessLine": {"type": code, "descriptions": [{"languageCode": "3", "description": desc}]},
            "publicNotices": notices}


def notice(day, rec, codes, typ="M"):
    n = {"recordNumber": rec, "typeOfRegistration": typ, "entryCodes": codes}
    if day:
        n["registrationDate"] = day
    return n


def test_code_mapping_and_dedup():
    ns = [notice("2026-10-13", "2026/1", ["ANTIP", "KOROI", "VAL"]), notice("2026-10-13", "2026/1", ["ANTIP", "KOROI", "VAL"]),
          notice("2026-09-01", "2026/2", ["HAL"]), notice("2026-08-01", "2026/3", ["OPOMEN", "OPTIO"]),
          notice("2026-07-01", "2026/4", ["OANKO"]), notice("2026-06-01", "2026/5", ["TASE"]),
          notice("2026-05-01", "2026/6", ["MUU"], typ="U")]
    ev = {(e["signal_type"], e["date"]): e for e in pn.interpret(ns, "2021-01-01")}
    assert ev[("equity_event", "2026-10-13")]["codes"] == ["ANTIP", "KOROI"]
    assert ev[("equity_event", "2026-10-13")]["records"] == ["2026/1"]
    assert ("board_change", "2026-09-01") in ev and ("capital_loss", "2026-08-01") in ev
    assert ("equity_event", "2026-08-01") in ev and ("equity_event", "2026-07-01") in ev
    assert ("startup_notice", "2026-05-01") in ev
    assert not any(d == "2026-06-01" for _, d in ev)  # TASE is not mapped
    assert len(ev) == 6


def test_missing_date_is_skipped_and_old_rows_dropped():
    ns = [notice(None, "2026/9", ["ANTIP"]), notice("2019-01-01", "2019/1", ["ANTIP"])]
    assert pn.interpret(ns, "2021-10-16") == []


def test_detail_says_share_issue_with_date_and_record():
    ev = pn.interpret([notice("2026-10-13", "2026/1", ["ANTIP"])], "2021-01-01")[0]
    d = pn.detail_for(ev)
    assert d.startswith("Share issue registered 2026-10-13 (PRH).") and "2026/1" in d and "—" not in d


def _stub(monkeypatch, pages):
    calls = []

    def fake(url, client=None, stats=None):
        calls.append(url)
        return pages.get(url, {"totalResults": 0, "companies": []}), False
    monkeypatch.setattr(pn, "fetch", fake)
    return calls


def test_window_mode_filters_age_and_fit_and_pages(monkeypatch):
    start, end = "2026-04-19", "2026-10-16"
    young = company("0000000-0", "Fixture Oy", "2024-03-01", "30110", "Building of ships", [notice("2026-10-13", "2026/1", ["ANTIP"])])
    old = company("0000001-8", "Fixture Old Oy", "2010-03-01", "30110", "Building of ships", [notice("2026-10-13", "2026/2", ["ANTIP"])])
    nofit = company("0000002-6", "Fixture Marine Oy", "2025-03-01", "62010", "Software publishing", [notice("2026-10-13", "2026/3", ["ANTIP"])])
    lob = company("0000003-4", "Fixture Lob Oy", "2025-05-01", "99999", "Ship hull inspection", [notice("2026-09-01", "2026/4", ["HAL"])])
    filler = [company(f"9{i:06d}-1", f"Fixture Filler {i} Oy", "2010-01-01", "1", "x", []) for i in range(48)]
    pages = {pn.window_url(start, end, code="ANTIP"): {"totalResults": 53, "companies": [young, old, nofit] + filler[:47]},
             pn.window_url(start, end, code="ANTIP", page=2): {"totalResults": 53, "companies": filler[:2] + [lob][:0] + [young]},
             pn.window_url(start, end, code="HAL"): {"totalResults": 1, "companies": [lob]}}
    calls = _stub(monkeypatch, pages)
    conn = db.connect(":memory:")
    res = pn.run(conn, THESIS, today=TODAY)
    keys = {r[0] for r in conn.execute("select company_key from companies")}
    assert keys == {"0000000-0", "0000003-4"}
    rows = conn.execute("select company_key, signal_type, date, confidence, source_url, adapter from signals order by 1").fetchall()
    assert [(r[0], r[1], r[2], r[3]) for r in rows] == [("0000000-0", "equity_event", "2026-10-13", "high"),
                                                         ("0000003-4", "board_change", "2026-09-01", "high")]
    assert rows[0]["source_url"] == "https://avoindata.prh.fi/opendata-registerednotices-api/v3/0000000-0"
    assert res["signals_equity_event"] == 1 and res["signals_board_change"] == 1 and res["equity"][0]["date"] == "2026-10-13"
    assert any("page=2" in u for u in calls)


def test_company_mode_five_year_history(monkeypatch):
    conn = db.connect(":memory:")
    emit.upsert_company(conn, company_key="0000000-0", name="Fixture Oy", source_url="https://example.org/f", y_tunnus="0000000-0")
    emit.upsert_company(conn, company_key="no-id", name="Fixture NoId Oy", source_url="https://example.org/g")
    full = company("0000000-0", "Fixture Oy", "2020-01-01", "30110", "Ships",
                   [notice("2026-02-02", "2026/1", ["KOROI"]), notice("2022-03-03", "2022/1", ["OPTIO"]),
                    notice("2019-03-03", "2019/1", ["ANTIP"]), notice(None, "2026/7", ["ANTIP"]), notice("2025-01-01", "2025/1", [], typ="U")])
    _stub(monkeypatch, {pn.company_url("0000000-0"): full})
    res = pn.run(conn, THESIS, today=TODAY)
    got = sorted(tuple(r) for r in conn.execute("select signal_type, date from signals"))
    assert got == [("equity_event", "2022-03-03"), ("equity_event", "2026-02-02"), ("startup_notice", "2025-01-01")]
    assert res["company_mode_companies"] == 1


class FakeClient:
    def __init__(self, statuses):
        self.statuses, self.n = list(statuses), 0

    def get(self, url):
        self.n += 1
        code = self.statuses.pop(0)
        return httpx.Response(code, json={"totalResults": 0, "companies": []}, request=httpx.Request("GET", url))

    def close(self):
        pass


def test_429_backoff_waits_60s_then_succeeds(monkeypatch, tmp_path):
    sleeps = []
    monkeypatch.setattr(pn, "CACHE", tmp_path)
    monkeypatch.setattr(pn, "_sleep", sleeps.append)
    stats = {}
    c = FakeClient([429, 200])
    data, net = pn.fetch("https://avoindata.prh.fi/x", c, stats)
    assert data == {"totalResults": 0, "companies": []} and net and c.n == 2
    assert pn.BACKOFF_429 in sleeps and stats["backoffs"] == 1
    again, net2 = pn.fetch("https://avoindata.prh.fi/x", c, stats)  # cached, no network
    assert again == data and not net2 and c.n == 2


def test_persistent_429_gives_up_without_raising(monkeypatch, tmp_path):
    monkeypatch.setattr(pn, "CACHE", tmp_path)
    monkeypatch.setattr(pn, "_sleep", lambda s: None)
    data, _ = pn.fetch("https://avoindata.prh.fi/y", FakeClient([429] * 10), {})
    assert data is None


def test_new_types_are_accepted_by_emit():
    for t in pn.NEW_TYPES:
        assert t in emit.SIGNAL_TYPES
