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
    c = db.connect(p)
    yield c
    c.close()


def run(conn, payload=LLM):
    return stitcher.stitch_company(conn, KELLUU, run_id="t1", runner=lambda prompt: json.dumps(payload),
                                   fetch=fake_fetch, capture=fake_capture, today="2026-10-16")


def test_pipeline_keeps_only_page_checked_events(conn):
    res = run(conn)
    assert res["proposed"] == 8 and res["kept"] == 5
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
                                  fetch=fake_fetch, capture=fake_capture, today="2026-10-16")
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
