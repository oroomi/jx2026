import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import blueinvest_fixture as fx  # noqa: E402

from radar import blueinvest, db, emit  # noqa: E402
from radar.adapters import blueinvest as bi  # noqa: E402

THESIS = {"feed_signal_types": ["register_entry", "blueinvest"]}


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


def make_fetcher(tmp_path, pages, status=None, cap=150):
    """pages: url-substring -> html. status: url-substring -> http status."""
    seen = []

    def opener(url):
        seen.append(url)
        for k, v in (status or {}).items():
            if k in url:
                return v, ""
        if url.endswith("/robots.txt"):
            return pages.get("robots", (404, ""))
        for k, v in pages.items():
            if k != "robots" and k in url:
                return 200, v
        return 404, ""

    f = bi.Fetcher(opener=opener, cap=cap, delay=0, sleep=lambda s: None, cache=tmp_path / "c")
    f.seen = seen
    return f


def pages_for(*profiles):
    pages = {"co%5D%5B%5D=FI": fx.list_page([(pid, "t") for pid, _ in profiles])}
    for pid, kw in profiles:
        pages[f"other_id%5D={pid}"] = fx.detail_page(**kw)
    return pages


def test_parse_list():
    items = bi.parse_list(fx.list_page([("11", "A &amp; B"), ("12", "C"), ("11", "dup")]))
    assert items == [{"profile_id": "11", "title": "A & B"}, {"profile_id": "12", "title": "C"}]


def test_detail_with_and_without_trl():
    d = bi.parse_detail(fx.detail_page())
    assert d["trl"] == 5 and d["company_name"] == "Fixture Oy" and d["country"] == "Finland"
    assert d["sector"] == "Fixture sector" and d["description"] == "Fixture description & text." and d["listed_date"] is None
    assert bi.parse_detail(fx.detail_page(trl=None))["trl"] is None


def test_listed_date_label_rules():
    assert bi.parse_detail(fx.detail_page(date_label="Listed on", date_value="2025-03-04"))["listed_date"] == "2025-03-04"
    assert bi.parse_detail(fx.detail_page(date_label="Last updated", date_value="2025-03-04"))["listed_date"] is None


def test_robots_disallow_stops(conn, tmp_path):
    f = make_fetcher(tmp_path, {"robots": (200, "User-agent: *\nDisallow: /pipeline")})
    res = bi.run(conn, THESIS, fetcher=f, declared=[])
    assert "robots" in res["blocked"] and f.requests == 1


@pytest.mark.parametrize("code", [403, 429])
def test_block_keeps_partial(conn, tmp_path, code):
    pages = pages_for(("1", {"company": "First Oy"}), ("2", {"company": "Second Oy"}))
    f = make_fetcher(tmp_path, pages, status={"other_id%5D=2": code})
    res = bi.run(conn, THESIS, fetcher=f, declared=[])
    assert str(code) in res["blocked"]
    assert conn.execute("SELECT profile_id FROM blueinvest_profiles").fetchall()[0][0] == "1"
    assert conn.execute("SELECT COUNT(*) FROM blueinvest_profiles").fetchone()[0] == 1


def test_request_cap(conn, tmp_path):
    pages = pages_for(*[(str(i), {"company": f"Fixture {i} Oy"}) for i in range(1, 6)])
    f = make_fetcher(tmp_path, pages, cap=4)  # robots + list + 2 details
    res = bi.run(conn, THESIS, fetcher=f, declared=[])
    assert f.requests == 4 and "cap" in res["blocked"] and res["profiles"] == 2


def test_cache_reuse(conn, tmp_path):
    pages = pages_for(("1", {}))
    f1 = make_fetcher(tmp_path, pages)
    bi.run(conn, THESIS, fetcher=f1, declared=[])
    f2 = make_fetcher(tmp_path, {})
    res = bi.run(conn, THESIS, fetcher=f2, declared=[])
    assert f2.requests == 1 and f2.seen == [f"{bi.HOST}/robots.txt"] and res["profiles"] == 1  # only robots.txt (404, never cached)


def test_signal_only_with_stated_date(conn, tmp_path):
    pages = pages_for(("1", {"company": "Dated Oy", "date_label": "Listed on", "date_value": "2025-03-04"}), ("2", {"company": "Undated Oy"}))
    res = bi.run(conn, THESIS, fetcher=make_fetcher(tmp_path, pages), declared=[])
    rows = conn.execute("SELECT company_key,date,confidence,detail,source_url FROM signals WHERE signal_type='blueinvest'").fetchall()
    assert res["signals"] == 1 and len(rows) == 1
    assert rows[0]["company_key"] == "name:dated" and rows[0]["date"] == "2025-03-04"
    assert rows[0]["detail"] == "Listed in the BlueInvest project pipeline, TRL 5, sector Fixture sector"
    assert conn.execute("SELECT COUNT(*) FROM blueinvest_profiles").fetchone()[0] == 2


def test_folded_name_match_and_slug_insert(conn, tmp_path):
    emit.upsert_company(conn, company_key="1234567-8", name="Merikuva Oy", source_url="https://example.invalid/x", country="FI")
    pages = pages_for(("1", {"company": "MERIKUVA"}), ("2", {"company": "New Fixture Ab"}))
    res = bi.run(conn, THESIS, fetcher=make_fetcher(tmp_path, pages), declared=[])
    keys = dict(conn.execute("SELECT profile_id, company_key FROM blueinvest_profiles").fetchall())
    assert keys == {"1": "1234567-8", "2": "name:new-fixture"}
    c = conn.execute("SELECT group_tag,country,founded,source_url FROM companies WHERE company_key='name:new-fixture'").fetchone()
    assert tuple(c) == ("feed", "FI", None, bi.detail_url("2")) and res["companies"] == 1


def test_declared_link_by_url(conn, tmp_path):
    emit.upsert_company(conn, company_key="dk-1", name="Fixture Reef", source_url="https://example.invalid/x", country="DK", group_tag="cohort")
    pages = pages_for()
    pages["other_id%5D=490"] = fx.detail_page(company="Fixture Reef - tagline", country="Denmark", trl="TRL 3 - proof")
    res = bi.run(conn, THESIS, fetcher=make_fetcher(tmp_path, pages), declared=[("Fixture Reef", "490")])
    r = conn.execute("SELECT company_key,trl FROM blueinvest_profiles WHERE profile_id='490'").fetchone()
    assert tuple(r) == ("dk-1", 3) and res["linked_declared"] == 1 and res["finnish"] == 0
    assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 1


def test_skip_without_blueinvest_thesis(conn):
    assert bi.run(conn, {"feed_signal_types": ["register_entry"]}) == {"skipped": "thesis has no blueinvest source"}


def test_profile_for_none_without_table():
    c = sqlite3.connect(":memory:")
    assert blueinvest.profile_for(c, "x") is None


def test_profile_for_row(conn, tmp_path):
    bi.run(conn, THESIS, fetcher=make_fetcher(tmp_path, pages_for(("1", {"company": "Row Oy"}))), declared=[])
    p = blueinvest.profile_for(conn, "name:row")
    assert p["trl"] == 5 and p["url"] == bi.detail_url("1")
    assert blueinvest.profile_for(conn, "nope") is None
