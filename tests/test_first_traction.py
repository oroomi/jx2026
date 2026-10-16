"""First-traction adapters and life-line. All sources are imitated by synthetic records built here (Fixture Oy); nothing is fetched."""
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from radar import db, emit, lifeline, store
from radar.adapters import openalex, prh, tax_registers as tr, webarchive as wa

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))

BID = "9000010-1"


def ytj(*entries, bid=BID):
    return {"businessId": {"value": bid}, "registeredEntries": [
        {"register": r, "type": t, "registrationDate": d, **({"endDate": e} if e else {})} for r, t, d, e in entries]}


def conn_with(*companies):
    conn = db.connect(":memory:")
    for key, name, founded, group in companies:
        emit.upsert_company(conn, company_key=key, name=name, y_tunnus=key if key[0].isdigit() else None, founded=founded,
                            group_tag=group, source_url="https://example.test/fixture/" + key)
    return conn


# --- tax registers ---------------------------------------------------------------------------------------------

def test_vat_counts_only_type_6_80():
    t = tr.extract(ytj(("6", "6_81", "2022-03-01", None)))
    assert t["first_sales"] is None
    t = tr.extract(ytj(("6", "80", "2022-03-01", None)))
    assert t["first_sales"] == ("2022-03-01", "VAT liability register (type 6_80)")


def test_first_sales_is_earliest_of_vat_and_prepayment():
    t = tr.extract(ytj(("6", "80", "2022-05-10", None), ("5", "55", "2022-04-02", None)))
    assert t["first_sales"] == ("2022-04-02", "prepayment register")
    t = tr.extract(ytj(("6", "80", "2022-04-02", None), ("5", "55", "2022-04-02", None)))
    assert t["first_sales"][1].startswith("VAT")


def test_first_hire_is_earliest_employer_entry_and_trade_register_is_ignored():
    t = tr.extract(ytj(("1", "1_1", "2021-01-01", None), ("7", "41", "2023-02-01", None), ("7", "41", "2022-09-01", None)))
    assert t["first_hire"] == "2022-09-01" and t["first_sales"] is None


def test_end_dates_need_every_entry_ended():
    t = tr.extract(ytj(("6", "80", "2022-01-01", "2023-06-30"), ("5", "55", "2022-01-01", "2023-08-31"), ("7", "41", "2022-03-01", "2024-01-31")))
    assert t["sales_ended"] == "2023-08-31" and t["employer_ended"] == "2024-01-31"
    t = tr.extract(ytj(("6", "80", "2022-01-01", "2023-06-30"), ("5", "55", "2022-01-01", None), ("7", "41", "2022-03-01", None)))
    assert t["sales_ended"] is None and t["employer_ended"] is None


def test_months_between_calendar_months():
    assert tr.months_between("2022-01-31", "2022-09-01") == 7
    assert tr.months_between("2022-01-15", "2022-01-20") == 0
    assert tr.months_between("2022-05-01", "2022-01-01") is None and tr.months_between(None, "2022-01-01") is None


def test_run_emits_signals_derived_row_and_no_signal_for_months(monkeypatch):
    conn = conn_with((BID, "Fixture Oy", "2022-01-31", "feed"))
    rec = ytj(("6", "80", "2022-04-01", None), ("7", "41", "2022-09-01", "2024-01-01"))
    monkeypatch.setattr(prh, "fetch", lambda params, client=None: ({"companies": [rec]}, False))
    res = tr.run(conn, {})
    assert res["companies"] == 1 and res["signals"] == 3 and res["blocked"] == 0
    rows = {r["signal_type"]: r for r in conn.execute("SELECT * FROM signals")}
    assert set(rows) == {"first_sales", "first_hire", "employer_ended"}
    hire = rows["first_hire"]
    assert hire["date"] == "2022-09-01" and hire["confidence"] == "high"
    assert hire["source_url"] == "https://tietopalvelu.ytj.fi/yritys/" + BID
    assert "Entered the employer register 2022-09-01, 7 months after founding (PRH)." in hire["detail"]
    assert prh._url({"businessId": BID}) in hire["detail"]
    d = conn.execute("SELECT * FROM company_traction").fetchone()
    assert d["months_to_first_hire"] == 7 and d["first_hire_date"] == "2022-09-01"
    assert "months" not in {r["signal_type"] for r in conn.execute("SELECT signal_type FROM signals")}


def test_run_is_idempotent_and_blank_register_stays_blank(monkeypatch):
    conn = conn_with((BID, "Fixture Oy", "2022-01-31", "feed"))
    monkeypatch.setattr(prh, "fetch", lambda params, client=None: ({"companies": [ytj()]}, False))
    tr.run(conn, {})
    tr.run(conn, {})
    assert conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0
    d = conn.execute("SELECT * FROM company_traction").fetchone()
    assert d["first_hire_date"] is None and d["months_to_first_hire"] is None


def test_run_stops_cleanly_when_the_source_is_blocked(monkeypatch):
    conn = conn_with(*[(f"90001{i}0-1", f"Fixture {i} Oy", "2022-01-01", "feed") for i in range(5)])

    def boom(params, client=None):
        raise httpx.ConnectError("blocked")
    monkeypatch.setattr(prh, "fetch", boom)
    res = tr.run(conn, {})
    assert res["blocked"] == 1 and res["companies"] == 0 and res["signals"] == 0


# --- OpenAlex --------------------------------------------------------------------------------------------------

def work(aff, day="2024-05-02", wid="https://openalex.org/W1"):
    return {"id": wid, "publication_date": day, "title": "Synthetic study", "primary_location": {"source": {"display_name": "Journal of Fixtures"}},
            "authorships": [{"raw_affiliation_strings": [aff]}]}


def test_core_name_strips_legal_form_and_refuses_short_names():
    assert openalex.core_name("Fixture Marine Oy") == "fixture marine"
    assert openalex.core_name("Sea Oy") == ""


def test_affiliation_must_contain_the_whole_folded_name():
    core = openalex.core_name("Fixtürë Oy")
    assert openalex.affiliation_matches(core, work("Fixture Lab, Fixture Oy, Turku"))
    assert not openalex.affiliation_matches(core, work("Prefixture Institute"))
    assert not openalex.affiliation_matches(core, work("University of Turku"))
    assert not openalex.affiliation_matches("", work("anything"))


def test_openalex_run_keeps_only_verified_works(monkeypatch):
    conn = conn_with(("name:fixture-oy", "Fixture Oy", None, "cohort"), ("name:other", "Other Oy", None, "feed"))
    payload = {"results": [work("Fixture Oy, Turku"), work("Unrelated Lab", wid="https://openalex.org/W2")]}
    monkeypatch.setattr(openalex, "cached_get", lambda *a, **k: (payload, False))
    res = openalex.run(conn, {})
    assert res["signals"] == 1 and res["companies"] == 1  # the feed group is never looked up
    s = conn.execute("SELECT * FROM signals").fetchone()
    assert s["signal_type"] == "research_output" and s["confidence"] == "medium" and s["source_url"] == "https://openalex.org/W1"
    assert "Journal of Fixtures" in s["detail"] and "Synthetic study" in s["detail"]


# --- web archive -----------------------------------------------------------------------------------------------

CDX = [["timestamp", "original", "statuscode"],
       ["20230105101010", "http://fixture.example.test/", "200"],
       ["20220301000000", "http://fixture.example.test/en/", "200"],
       ["20240210000000", "http://fixture.example.test/careers/", "200"],
       ["20231001000000", "http://fixture.example.test/asiakkaat", "200"],
       ["20230601000000", "http://fixture.example.test/about-us-careers-team", "200"],
       ["20210101000000", "http://fixture.example.test/missing", "404"]]


def test_domain_of():
    assert wa.domain_of("https://www.fixture.example.test/path") == "fixture.example.test"
    assert wa.domain_of("fixture.example.test") == "fixture.example.test"
    assert wa.domain_of("https://www.linkedin.com/company/x") is None and wa.domain_of(None) is None


def test_milestone_word_matches_path_segments_only():
    assert wa.milestone_word("http://x.test/fi/rekry/") == "rekry"
    assert wa.milestone_word("http://x.test/about-us-careers-team") == "careers"
    assert wa.milestone_word("http://x.test/careersite") is None
    assert wa.milestone_word("http://careers.x.test/") is None  # host names are not milestones


def test_derive_first_seen_and_earliest_milestone_per_word():
    out = wa.derive(wa.captures(CDX))
    kinds = [(k, d) for k, d, _, _ in out]
    assert kinds[0] == ("website_first_seen", "2022-03-01")  # the 404 capture is ignored
    assert ("website_milestone", "2023-06-01") in kinds and ("website_milestone", "2023-10-01") in kinds
    assert ("website_milestone", "2024-02-10") not in kinds  # careers is already dated by its earlier page
    assert out[0][2] == "https://web.archive.org/web/20220301000000/http://fixture.example.test/en/"


def test_captures_empty_and_headerless():
    assert wa.captures([]) == [] and wa.derive([]) == []


def test_webarchive_run_writes_signals_and_blocks_cleanly(monkeypatch):
    conn = conn_with(("name:fixture", "Fixture Oy", None, "cohort"))
    conn.execute("UPDATE companies SET website='https://fixture.example.test'")
    monkeypatch.setattr(wa, "cached_get", lambda *a, **k: (CDX, False))
    res = wa.run(conn, {})
    assert res["signals"] == 3 and res["blocked"] == 0
    assert {r[0] for r in conn.execute("SELECT DISTINCT confidence FROM signals")} == {"medium"}

    def down(*a, **k):
        raise wa.Blocked("offline")
    monkeypatch.setattr(wa, "cached_get", down)
    assert wa.run(conn, {})["blocked"] == 0  # one failure is below the stop threshold; nothing crashes


# --- life-line -------------------------------------------------------------------------------------------------

def sig(i, kind, day, **kw):
    return {"id": i, "signal_type": kind, "date": day, "source_url": f"https://example.test/{i}", "detail": None, **kw}


def test_lifeline_orders_dots_and_groups_by_stage():
    c = {"founded": "2022-01-01"}
    ll = lifeline.build(c, [sig(3, "first_hire", "2022-09-01"), sig(1, "register_entry", "2022-01-01"),
                            sig(2, "first_sales", "2022-04-01"), sig(4, "eu_project", "2023-01-01"),
                            sig(5, "employer_ended", "2023-06-01")], today="2024-01-01")
    lanes = {l["id"]: l["dots"] for l in ll["lanes"]}
    assert [l["id"] for l in ll["lanes"]] == ["formation", "first_money", "first_team", "validation"]
    assert [d["date"] for d in lanes["first_team"]] == ["2022-09-01", "2023-06-01"]
    assert lanes["first_team"][1]["negative"] and not lanes["first_team"][0]["negative"]
    assert lanes["formation"][0]["left"] == 0 and 0 < lanes["first_money"][0]["left"] < lanes["first_team"][0]["left"] < 100
    assert ll["start"] == "2022-01-01" and ll["end"] == "2024-01-01"


def test_lifeline_axis_starts_at_earlier_research_and_handles_empty():
    ll = lifeline.build({"founded": "2022-01-01"}, [sig(1, "research_output", "2021-01-01")], today="2022-01-01")
    assert ll["start"] == "2021-01-01" and ll["lanes"][0]["dots"][0]["left"] == 0
    assert lifeline.build({"founded": None}, [], today="2024-01-01") == {}
    one = lifeline.build({"founded": "2024-01-01"}, [], today=date(2024, 1, 1))
    assert one["lanes"][0]["dots"] == []  # zero-length span does not divide by zero


def _traction(conn, n, year="2023", months=6):
    for i in range(n):
        key = f"900{i:04d}-1"
        emit.upsert_company(conn, company_key=key, name=f"Fixture {i} Oy", founded=f"{year}-01-10", source_url="https://example.test/f")
        conn.execute("INSERT OR REPLACE INTO company_traction VALUES (?,?,?,?,?)", (key, f"{year}-01-10", f"{year}-07-10", months + i % 3, "2026-10-17T00:00:00Z"))


def test_median_is_blank_under_30_and_shown_at_30():
    conn = db.connect(":memory:")
    _traction(conn, 29)
    assert lifeline.median_months(conn, "2023") == (None, 29)
    _traction(conn, 30)
    med, n = lifeline.median_months(conn, "2023")
    assert n == 30 and med == 7 and lifeline.median_months(conn, "2021") == (None, 0)


def test_median_without_traction_table_is_blank():
    conn = db.connect(":memory:")
    conn.execute("DROP TABLE company_traction")
    assert lifeline.median_months(conn, "2023") == (None, 0)


# --- feed and page ---------------------------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / "t.sqlite"
    conn = db.connect(path)
    emit.upsert_company(conn, company_key=BID, name="Fixture Marine Oy", y_tunnus=BID, country="FI", founded="2026-06-01",
                        industry_code="30110", industry_desc="Building of ships", group_tag="feed", source_url="https://example.test/f")
    emit.emit_signal(conn, company_key=BID, signal_type="register_entry", date="2026-06-01", source_url="https://example.test/f",
                     confidence="high", adapter="prh", detail="Registered.")
    page = "https://tietopalvelu.ytj.fi/yritys/" + BID
    emit.emit_signal(conn, company_key=BID, signal_type="first_hire", date="2026-09-01", source_url=page, confidence="high",
                     adapter="tax_registers", detail="Entered the employer register 2026-09-01, 3 months after founding (PRH).")
    conn.execute("INSERT INTO company_traction VALUES (?,?,?,?,?)", (BID, "2026-06-01", "2026-09-01", 3, "2026-10-17T00:00:00Z"))
    conn.commit()
    conn.close()
    monkeypatch.setenv("RADAR_DB", str(path))
    import app
    return TestClient(app.app)


def test_company_page_has_lifeline_with_linked_dots_and_blank_median(client):
    t = client.get("/c/" + BID).text
    assert t.index('id="lifeline"') < t.index('id="q1"')
    assert t.count('class="ll-dot') == 2 and "https://tietopalvelu.ytj.fi/yritys/" + BID in t
    assert "First salary paid 3 months after founding" in t
    assert "sample size 1 is under 30" in t
    assert "First hire, 2026-09-01" in t


def test_empty_lanes_are_labelled_not_filled(client):
    t = client.get("/c/" + BID).text
    assert "no public evidence" in t and chr(0x2014) not in t


def test_first_hire_row_in_feed_with_why_detail(client):
    html = client.get("/").text
    assert "Entered the employer register 2026-09-01, 3 months after founding (PRH)." in html
    assert "First hire" in html


def test_live_shape_type_80_and_incorrect_lines():
    # the live API writes type "80" inside register "6"; 6_82 (property rental) and x_99 (incorrect line) never count
    assert tr.extract(ytj(("6", "80", "2022-01-01", None)))["first_sales"][0] == "2022-01-01"
    assert tr.extract(ytj(("6", "82", "2022-01-01", None)))["first_sales"] is None
    assert tr.extract(ytj(("6", "6_80", "2022-02-01", None)))["first_sales"][0] == "2022-02-01"
    assert tr.extract(ytj(("5", "99", "2022-01-01", None), ("7", "99", "2022-02-01", None))) == {
        "first_sales": None, "first_hire": None, "sales_ended": None, "employer_ended": None}


def test_affiliation_single_word_needs_legal_form_and_multiword_whole_words():
    assert not openalex.affiliation_matches("fixture", work("Fixture Lab, Somewhere"))  # ordinary word, no legal form
    assert openalex.affiliation_matches("fixture", work("Fixture"))
    assert openalex.affiliation_matches("fixture robotics", work("Fixture Robotics, Turku"))
    assert not openalex.affiliation_matches("fixture robotics", work("Fixture Roboticsx"))


def test_affiliation_prose_is_rejected():
    assert not openalex.affiliation_matches("fixture robotics", work("He wrote about Fixture Robotics. " + "x" * 200))


def test_archive_ignores_robots_and_favicon_for_first_seen():
    caps = [("20180101000000", "http://fixture.test/robots.txt"), ("20190505000000", "http://fixture.test/")]
    out = wa.derive(caps)
    assert out[0][0] == "website_first_seen" and out[0][1] == "2019-05-05"
