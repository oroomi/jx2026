"""Stitcher: the LLM proposes, code keeps only events whose page names the company and prints the date. Runs on a copy of the
data/snapshot thesis store with a fake LLM, fake pages and a fake archive: no network, no LLM session."""
import json
import shutil
from pathlib import Path

import pytest

from radar import build, db
from radar.adapters import stitcher
from radar.adapters._fetch import Blocked

SNAP = Path(__file__).resolve().parents[1] / "data" / "snapshot" / "radar_redstone_apelago_blue.sqlite"
KELLUU = "2902007-2"

PAGES = {
    "https://example.org/kelluu-funding": "News 12.5.2021. Kelluu Oy (2902007-2) received Business Finland funding for airship trials.",
    "https://example.org/other-company": "On 12 May 2021 Another Firm Oy won a contract for harbour cranes.",
    "https://example.org/kelluu-award-2022": "The award went to Kelluu Oy on 3 June 2022 for persistent aerial monitoring.",
    "https://example.org/kelluu-year-only": "Kelluu flew its first commercial pilot with a utility company in 2020.",
    "https://example.org/kelluu-person": "CEO Jane Doe said on 1 March 2023 that Kelluu Oy signed a pilot with a grid operator.",
    "https://example.org/kelluu-partner": "On 10 October 2023 Kelluu Oy announced a partnership with a grid company.",
}
LLM = {"queries_run": ['"Kelluu Oy"'], "events": [
    {"signal_type": "bf_funding", "date": "2021-05-12", "date_precision": "day", "source_url": "https://example.org/kelluu-funding",
     "quote": "Kelluu Oy (2902007-2) received Business Finland funding for airship trials.", "confidence": "high"},
    {"signal_type": "public_contract", "date": "2021-05-12", "date_precision": "day", "source_url": "https://example.org/other-company",
     "quote": "won a contract", "confidence": "medium"},
    {"signal_type": "site_customer", "date": "2021-01-01", "date_precision": "day", "source_url": "https://www.linkedin.com/posts/x",
     "quote": "x", "confidence": "low"},
    {"signal_type": "unmapped", "suggested_type": "award", "date": "2022-06-03", "date_precision": "day",
     "source_url": "https://example.org/kelluu-award-2022", "quote": "The award went to Kelluu Oy on 3 June 2022", "confidence": "high"},
    {"signal_type": "eu_project", "date": "2019-02-02", "date_precision": "day", "source_url": "https://example.org/gone", "quote": "", "confidence": "high"},
    {"signal_type": "job_ad", "date": "2020-01", "date_precision": "month", "quote": "no url here"},
    {"signal_type": "site_customer", "date": "2020-04-15", "date_precision": "day", "source_url": "https://example.org/kelluu-year-only",
     "quote": "Kelluu flew its first commercial pilot with a utility company in 2020.", "confidence": "medium"},
    {"signal_type": "site_customer", "date": "2023-03-01", "date_precision": "day", "source_url": "https://example.org/kelluu-person",
     "quote": "CEO Jane Doe said on 1 March 2023 that Kelluu Oy signed a pilot", "confidence": "high"},
    {"signal_type": "unmapped", "suggested_type": "partnership", "date": "2023-10-10", "date_precision": "day",
     "source_url": "https://example.org/kelluu-partner", "quote": "Kelluu Oy announced a partnership with a grid company", "confidence": "high"},
]}


def fake_fetch(url):
    if url not in PAGES:
        raise Blocked("HTTP 404")
    return PAGES[url]


def fake_capture(url):
    return ("2021-05-20", f"https://web.archive.org/web/20210520000000/{url}") if "funding" in url else (None, None)


@pytest.fixture
def conn(tmp_path, monkeypatch):
    p = tmp_path / "store.sqlite"
    shutil.copy(SNAP, p)
    monkeypatch.setattr(stitcher, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(stitcher, "registered_names", lambda company: [])  # no register call in tests
    c = db.connect(p)
    yield c
    c.close()


def run(conn, payload=LLM):
    return stitcher.stitch_company(conn, KELLUU, run_id="t1", runner=lambda prompt: json.dumps(payload),
                                   fetch=fake_fetch, capture=fake_capture, refetch=fake_fetch, today="2026-10-16")


def test_pipeline_keeps_only_page_checked_events(conn):
    res = run(conn)
    assert res["proposed"] == 8 and res["kept"] == 5 and res["confirmed"] == 5
    assert res["emitted"] == 4 and res["not_emitted"] == 1
    rep = stitcher.report(conn, "t1", ("2026-01-01", "test reference"))
    assert rep["rejected_shape"] == 1
    assert rep["dropped"] == {"company_not_on_page": 1, "source_not_allowed": 1, "fetch_failed": 1}
    assert rep["not_emitted_types"] == {"partnership": 1}  # kept in stitch_log only, never a signal
    assert rep["kept_before_entry"] == 5 and rep["kept_before_entry_and_archived_before_entry"] == 1
    sig = {r["signal_type"]: dict(r) for r in conn.execute("SELECT * FROM signals WHERE adapter='stitcher'")}
    assert set(sig) == {"bf_funding", "site_customer", "award"}
    assert sig["bf_funding"]["confidence"] == "high" and sig["bf_funding"]["date"] == "2021-05-12"
    assert "first archived 2021-05-20" in sig["bf_funding"]["detail"]


def test_precision_lowered_to_what_the_page_prints(conn):
    run(conn)
    r = conn.execute("SELECT s.id, s.date, s.confidence, m.date_precision FROM signals s LEFT JOIN signal_meta m ON m.signal_id=s.id "
                     "WHERE s.source_url='https://example.org/kelluu-year-only'").fetchone()
    assert r["date"] == "2020-01-01" and r["date_precision"] == "year" and r["confidence"] == "medium"
    log = conn.execute("SELECT reason FROM stitch_log WHERE step='verify' AND source_url LIKE '%year-only'").fetchone()[0]
    assert "precision lowered from day" in log


def test_person_names_never_stored(conn):
    run(conn)
    quotes = [r[0] for r in conn.execute("SELECT quote FROM stitch_log WHERE quote IS NOT NULL")]
    assert not any("Jane Doe" in q for q in quotes)
    sid = conn.execute("SELECT id, detail FROM signals WHERE source_url='https://example.org/kelluu-person'").fetchone()
    assert "Jane" not in sid["detail"]
    # a redacted quote is no longer the source's verbatim words, so it never reaches signal_text
    assert conn.execute("SELECT count(*) FROM signal_text WHERE signal_id=?", (sid["id"],)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM signal_text t JOIN signals s ON s.id=t.signal_id WHERE s.signal_type='bf_funding' "
                        "AND s.adapter='stitcher'").fetchone()[0] == 1


def test_every_query_logged_and_rerun_is_idempotent(conn):
    run(conn)
    n = conn.execute("SELECT count(*) FROM signals").fetchone()[0]
    qs = [r[0] for r in conn.execute("SELECT query FROM stitch_log WHERE step='search' AND outcome='query'")]
    assert '"Kelluu Oy"' in qs and '"2902007-2"' in qs and '"kelluu.com"' in qs
    res = stitcher.stitch_company(conn, KELLUU, run_id="t2", runner=lambda p: (_ for _ in ()).throw(AssertionError("LLM re-called")),
                                  fetch=fake_fetch, capture=fake_capture, refetch=fake_fetch, today="2026-10-16")
    assert res["duplicate"] == 4 and res["emitted"] == 0  # cached LLM answer, same signals, nothing new
    assert conn.execute("SELECT count(*) FROM signals").fetchone()[0] == n


def test_read_failure_is_logged_not_raised(conn):
    def boom(prompt):
        raise RuntimeError("BLOCKED: claude -p error: Failed to authenticate")
    res = stitcher.stitch_company(conn, KELLUU, run_id="t3", runner=boom, fetch=fake_fetch, capture=fake_capture)
    assert res["proposed"] == 0
    assert stitcher.report(conn, "t3")["read_failed"][0][1].startswith("BLOCKED")


def test_unknown_company_refused(conn):
    with pytest.raises(KeyError):
        stitcher.stitch_company(conn, "no-such-company", runner=lambda p: "{}")


@pytest.mark.parametrize("d,text,want", [
    ("2021-05-03", "julkaistu 3.5.2021", "day"),
    ("2021-05-03", "Published May 3, 2021", "day"),
    ("2021-05-03", "on 3rd May 2021 the", "day"),
    ("2021-05-03", "toukokuussa 2021 yhtiö", "month"),
    ("2021-05-03", "© 2021 Example", "year"),
    ("2021-05-03", "© 2020 Example", None),
    ("2021", "founded in 2021.", "year"),
    ("2021-05", "updated 2021-05", "month"),
    ("2022-06-03", "3. juni 2022", "day"),
])
def test_date_on_page(d, text, want):
    assert stitcher.date_on_page(d, text) == want


def test_name_match_levels():
    c = {"name": "Kelluu Oy", "y_tunnus": "2902007-2", "website": "https://kelluu.com/"}
    assert stitcher.name_match(c, "Y-tunnus 2902007-2") == "business_id"
    assert stitcher.name_match(c, "VAT FI29020072") == "business_id"
    assert stitcher.name_match(c, "KELLUU OY announced") == "legal_name"
    assert stitcher.name_match(c, "the Kelluu airship") == "core_name"
    assert stitcher.name_match(c, "Kelluuhuone is not it") is None
    short = {"name": "MOR", "y_tunnus": None, "website": "https://garvemor.se/"}
    assert stitcher.name_match(short, "more and more") is None
    assert stitcher.name_match(short, "see garvemor.se") == "domain"


def test_redact_people_keeps_organisations():
    assert stitcher.redact_people("Jane Doe joined Kelluu Oy", "Kelluu Oy") == "[name] joined Kelluu Oy"
    assert stitcher.redact_people("Business Finland granted Kelluu Oy funding", "Kelluu Oy") == "Business Finland granted Kelluu Oy funding"


def test_stored_date():
    assert stitcher.stored_date("2024-02", "month") == "2024-02-29"
    assert stitcher.stored_date("2024-02-10", "year") == "2024-01-01"
    assert stitcher.stored_date("2024-02-10", "day") == "2024-02-10"


def test_emittable_types_exist_and_build_skips_stitcher():
    from radar import emit, store, thesis
    assert set(stitcher.EMITTABLE) <= set(emit.SIGNAL_TYPES)
    assert {"programme_entry", "award", "funding_round"} <= set(stitcher.EMITTABLE)
    assert {"programme_entry", "award", "funding_round"} <= set(thesis.load()["feed_signal_types"])
    assert all(t in store.TYPE_LABELS for t in stitcher.EMITTABLE)
    assert "stitcher" not in [n for n, _ in build.discover()]


def test_saved_unmapped_answer_takes_a_newly_emittable_type():
    p, _ = stitcher.normalise_proposal({"signal_type": "unmapped", "suggested_type": "funding_round", "date": "2024-05",
                                        "source_url": "https://example.org/x"})
    assert p["signal_type"] == "funding_round" and p["suggested_type"] is None
    p, _ = stitcher.normalise_proposal({"signal_type": "unmapped", "suggested_type": "partnership", "date": "2024",
                                        "source_url": "https://example.org/x"})
    assert p["signal_type"] == "unmapped" and p["suggested_type"] == "partnership"


def test_default_store_refused(monkeypatch):
    monkeypatch.delenv("RADAR_DB", raising=False)
    with pytest.raises(SystemExit):
        stitcher._resolve_db(str(db.ROOT / "data" / "radar.sqlite"), {"id": "x"})


# ---- adversarial second pass ------------------------------------------------------------------------------------------
COMPANY = {"company_key": KELLUU, "name": "Kelluu Oy", "y_tunnus": KELLUU, "website": "https://kelluu.com/"}


def kept(signal_type, quote, url="https://example.org/p", date="2022-06-03", precision="day"):
    return {"signal_type": signal_type, "suggested_type": None, "date": date, "date_precision": precision, "source_url": url,
            "quote": quote, "confidence": "high", "name_match": "legal_name", "public_since": None, "archive_url": None}


def test_recheck_drops_a_page_that_changed_since_the_first_read(conn):
    changed = dict(PAGES)
    changed["https://example.org/kelluu-award-2022"] = "This page has moved. Kelluu Oy news archive, 2022."

    def refetch(url):
        if url == "https://example.org/kelluu-year-only":
            raise Blocked("HTTP 404")
        return changed[url]
    res = stitcher.stitch_company(conn, KELLUU, run_id="t9", runner=lambda p: json.dumps(LLM), fetch=fake_fetch,
                                  capture=fake_capture, refetch=refetch, today="2026-10-16")
    assert res["kept"] == 5 and res["confirmed"] == 3 and res["emitted"] == 2
    rep = stitcher.report(conn, "t9")
    assert rep["kept"] == 5 and rep["confirmed"] == 3
    assert rep["refuted"] == {"quote_not_on_page": 1, "refetch_failed": 1}
    assert {r[0] for r in conn.execute("SELECT signal_type FROM signals WHERE adapter='stitcher'")} == {"bf_funding", "site_customer"}
    why = conn.execute("SELECT reason FROM stitch_log WHERE outcome='refuted' AND source_url LIKE '%award-2022'").fetchone()[0]
    assert why.startswith("quote_not_on_page")


@pytest.mark.parametrize("event,page,ok,reason", [
    (kept("award", "Kelluu Oy won the Blue Prize 2022"), "Turku, 3 June 2022. Kelluu Oy won the Blue Prize 2022 for airships.", True, ""),
    (kept("award", "Kelluu Oy won the Blue Prize"), "Kelluu Oy took home the Blue Prize on 3 June 2022.", False, "quote_not_on_page"),
    (kept("award", "Kelluu Oy announced a partnership with a grid company"),
     "3 June 2022: Kelluu Oy announced a partnership with a grid company.", False, "type_not_in_quote"),
    (kept("award", "Kelluu Oy was a finalist for the Blue Award 2022"),
     "3 June 2022. Kelluu Oy was a finalist for the Blue Award 2022.", False, "nomination_not_award"),
    (kept("programme_entry", "was selected into the accelerator cohort"),
     "Kelluu Oy " + "and many other words here " * 20 + "3 June 2022 a startup was selected into the accelerator cohort.",
     False, "company_not_near_quote"),
    (kept("programme_entry", "We were selected into the accelerator cohort", url="https://kelluu.com/news/1"),
     "Kelluu news. 3 June 2022 We were selected into the accelerator cohort.", True, ""),
    (kept("funding_round", "Kelluu Oy received a grant for airship trials"),
     "3.6.2022 Kelluu Oy received a grant for airship trials.", False, "type_not_in_quote"),
    (kept("funding_round", "Kelluu raised a EUR 15M Series A round", date="2026", precision="year"),
     "Kelluu raised a EUR 15M Series A round. " + "Other text " * 60 + "(c) 2026 Example Media", False, "year_not_near_quote"),
    (kept("funding_round", "Kelluu raised a EUR 15M Series A round in 2026", date="2026", precision="year"),
     "News. Kelluu raised a EUR 15M Series A round in 2026.", True, ""),
    (kept("site_customer", "[name] said that Kelluu Oy signed a pilot"),
     "CEO Jane Doe said that Kelluu Oy signed a pilot on 3 June 2022.", True, ""),
    (kept("site_customer", ""), "Kelluu Oy signed a pilot on 3 June 2022.", False, "no_quote"),
])
def test_recheck_event(event, page, ok, reason):
    got, why = stitcher.recheck_event(COMPANY, event, page)
    assert got is ok, why
    assert why.startswith(reason if not ok else "second pass")


def test_every_emittable_type_has_type_words():
    assert set(stitcher.TYPE_WORDS) == set(stitcher.EMITTABLE)


def test_recheck_run_over_an_older_run_logs_under_that_run(conn):
    run(conn)
    # pretend the run predates the second pass: remove its recheck rows, then recheck it with one page gone
    conn.execute("DELETE FROM stitch_log WHERE run_id='t1' AND outcome IN ('confirmed','refuted')")
    gone = lambda url: (_ for _ in ()).throw(Blocked("HTTP 410")) if "partner" in url else fake_fetch(url)  # noqa: E731
    res = stitcher.recheck_run(conn, "t1", KELLUU, refetch=gone)
    assert res == {"company": KELLUU, "kept": 5, "confirmed": 4}
    assert stitcher.report(conn, "t1")["refuted"] == {"refetch_failed": 1}
    assert stitcher.recheck_run(conn, "t1", KELLUU, refetch=gone)["skipped"] == "already rechecked"


# ---- company page block -----------------------------------------------------------------------------------------------
def _page(path, monkeypatch, key=KELLUU):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("RADAR_DB", str(path))
    import app
    return TestClient(app.app).get(f"/c/{key}")


def test_company_page_shows_the_checked_run(conn, tmp_path, monkeypatch):
    def refetch(url):  # the award page changed after the first read: refuted on the second check
        return "Moved. Kelluu Oy, 2022." if "award" in url else fake_fetch(url)
    stitcher.stitch_company(conn, KELLUU, run_id="2026-10-17T01:00:00Z", runner=lambda p: json.dumps(LLM), fetch=fake_fetch,
                            capture=fake_capture, refetch=refetch, today="2026-10-16")
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    r = _page(path, monkeypatch)
    assert r.status_code == 200
    t = r.text
    assert "Found by the AI stitcher, checked by code" in t
    block = t.split('id="stitch"')[1].split("</section>")[0]
    assert "2026-10-17" in block and "pages read by code" in block
    assert "Kelluu Oy (2902007-2) received Business Finland funding for airship trials." in block
    assert "public since" in block and "2021-05-20" in block and "web.archive.org" in block
    assert "not in the Internet Archive" in block
    assert "2020 (year only)" in block
    assert "partnership (not a radar signal type)" in block and "kept in the log only" in block
    assert "the quote is not on the page word for word" in block and "the page does not name the company" in block
    assert "The award went to Kelluu Oy" not in block  # refuted: never shown as a fact
    assert "won a contract" not in block  # dropped claims show the reason only
    assert "Jane" not in t and "Doe" not in t
    for q in block.split('<q class="st-quote">')[1:]:
        assert len(q.split("</q>")[0].split()) <= stitcher.MAX_QUOTE_WORDS


def test_company_page_without_a_run_shows_nothing(conn, monkeypatch):
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    t = _page(path, monkeypatch).text
    assert "AI stitcher" not in t and 'id="stitch"' not in t


def test_page_view_without_stitch_log_table(tmp_path):
    import sqlite3
    c = sqlite3.connect(tmp_path / "bare.sqlite")
    assert stitcher.page_view(c, KELLUU) is None


# ---- recall: other names of the company --------------------------------------------------------------------------------
ARCTIC, TAIKOA = "3166759-6", "3380111-1"
REGISTER = {ARCTIC: ["Arctic Fry Oy", "WESI Solutions"], TAIKOA: ["Taikoa Oy", "Taikoa Ltd"]}


def test_registered_and_declared_names_widen_the_search(conn):
    c = stitcher.company_row(conn, ARCTIC)
    c["aliases"] = stitcher.aliases(c, lambda co: REGISTER[co["y_tunnus"]])
    assert c["aliases"] == [{"name": "WESI Solutions", "kind": "registered_name", "confirmed": True}]  # declared duplicate folded in
    qs = stitcher.search(conn, "t", c)
    assert '"WESI Solutions"' in qs and '"FI31667596"' in qs and "site:wesi.fi" in qs
    assert any(q.startswith('"wesi solutions" rahoitus') for q in qs)
    assert "Also known as: WESI Solutions (registered name in the trade register)" in stitcher.build_prompt(c, qs)
    assert stitcher.name_match(c, "WESI Solutions won the Blue Prize on 3 June 2022") == "registered_name"
    ok, why = stitcher.recheck_event(c, kept("award", "WESI Solutions won the Blue Prize"), "3 June 2022: WESI Solutions won the Blue Prize.")
    assert ok and "registered_name" in why


def test_unconfirmed_declared_name_searches_but_never_names_the_company(conn):
    c = stitcher.company_row(conn, TAIKOA)
    c["aliases"] = stitcher.aliases(c, lambda co: REGISTER[co["y_tunnus"]])
    assert c["aliases"] == [{"name": "WAIing", "kind": "declared_name", "confirmed": False}]  # Taikoa Ltd folds to the legal name
    assert '"WAIing"' in stitcher.search(conn, "t", c)
    assert stitcher.name_match(c, "WAIing joined the accelerator on 3 June 2022") is None


def test_person_shaped_names_are_never_aliases(conn):
    c = stitcher.company_row(conn, ARCTIC)
    got = stitcher.aliases(c, lambda co: ["Matti Virtanen Holding Oy", "Arctic Fry Oy"])
    assert [a["name"] for a in got] == ["WESI Solutions"]  # only the declared name; the person-shaped one is dropped
