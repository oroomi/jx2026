"""Two display fixes (17 Oct): the Aava feed reader does not name a company whose thesis fit rests on a utility code alone (D22 applied to the
reader), and an organisation's declared description never shows a redaction marker (D31). Synthetic rows for the rules; the committed
snapshot for the pages."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import aava, fit, matchmaker, matchtext, memo, store, thesis
from radar.adapters import stitcher

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
needs_snapshot = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")
MARKER = "[name redacted]"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(SNAP))     # after the autouse fixture that points it at an empty directory
    monkeypatch.delenv("RADAR_DB", raising=False)
    from app import app
    return TestClient(app)


# ---- 1. the feed reader ---------------------------------------------------------------------------------------------------------
def _row(i, day, code, reasons, desc="Building of ships"):
    return {"company_key": f"900000{i}-{i}", "name": f"Fixture {i} Oy", "industry_code": code, "industry_desc": desc, "reasons": reasons,
            "signal_type": "first_sales", "date": day, "source_url": "https://example.test/x", "strength": "strong"}


def test_the_skip_predicate_reads_the_code_families_from_the_sector_file():
    th = thesis.load()
    skip = aava.code_only_skip(th)
    families = th["memo"]["bands"]["fit"]["medium_codes"]
    assert families and skip is not None
    utility = f"{families[0]}000"
    assert skip(_row(1, "2026-10-16", utility, ["industry_code"]))
    assert skip(_row(1, "2026-10-16", utility, ["industry_code", "line_of_business"]))      # the line of business is the code's own label
    assert not skip(_row(1, "2026-10-16", utility, ["industry_code", "own_text"]))
    assert not skip(_row(1, "2026-10-16", utility, ["industry_code", "corroborated_keyword"]))
    assert not skip(_row(1, "2026-10-16", "30110", ["industry_code"]))                      # a code outside the families
    for path in ("config/thesis_baltic_blue.yaml", "config/thesis_health_turku.yaml"):
        assert aava.code_only_skip(thesis.load(path)) is None, "a sector that lists no utility family skips nothing"
    assert aava.code_only_skip(None) is None


def test_the_reader_names_newest_first_and_never_a_code_only_utility_row():
    rows = [_row(0, "2026-10-16", "36000", ["industry_code", "line_of_business"], "Water collection, treatment and supply"),
            _row(1, "2026-10-15", "39000", ["industry_code"], "Remediation activities"),
            _row(2, "2026-10-12", "30110", ["industry_code"]), _row(3, "2026-10-14", "30110", ["industry_code"]),
            _row(4, "2026-10-13", "37000", ["industry_code", "own_text"], "Sewerage"), _row(5, "2026-10-10", "30110", ["industry_code"])]
    before = json.dumps(rows, sort_keys=True)
    text = " ".join(s["text"] for s in aava.feed_script(rows, today="2026-10-17", skip=aava.code_only_skip(thesis.load()))["segments"])
    assert json.dumps(rows, sort_keys=True) == before, "the list the page shows is not touched"
    assert "Fixture 0" not in text and "Fixture 1" not in text and "water collection" not in text
    assert text.index("Fixture 3") < text.index("Fixture 4") < text.index("Fixture 2"), "newest first among the rows that are named"
    assert text.startswith("Here is what is new this week.")
    assert "Fixture 0" in " ".join(s["text"] for s in aava.feed_script(rows, today="2026-10-17")["segments"]), "no predicate: as before"


def test_when_every_row_is_skipped_the_reader_still_answers():
    rows = [_row(1, "2026-10-16", "39000", ["industry_code"], "Remediation activities")]
    segs = aava.feed_script(rows, today="2026-10-17", skip=lambda r: True)["segments"]
    assert segs and "Fixture 1 Oy" in segs[0]["text"]


@needs_snapshot
def test_the_home_reader_and_the_endpoint_skip_the_same_rows_on_the_snapshot(client):
    th = thesis.load()
    conn = store.open_db(thesis=th)
    try:
        strong = [r for r in store.feed(conn, th, limit=500) if r["strength"] == "strong"]
    finally:
        conn.close()
    skipped = [r["name"] for r in strong if memo.code_only_fit(r["reasons"], r["industry_code"], th["memo"]["bands"]["fit"])]
    page = client.get("/")
    brief = json.loads(re.search(r'id="aava-data">(.*?)</script>', page.text, re.S).group(1))["brief"]
    endpoint = client.get("/aava/feed").json()["segments"]
    assert brief and endpoint
    for segs in (brief, endpoint):
        spoken = " ".join(s["text"] for s in segs)
        assert not [n for n in skipped if n in spoken], spoken


# ---- 2. organisation text -------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("raw,shown", [
    ("Ranked 5th in the 2025 Startup [name redacted] (behind Shell, DNV and Maersk). Finnish relevance not checked", "Finnish relevance not checked"),
    ("early-stage startups founded by Turku people, [name redacted], TUAS or Novia people; R2B", "R2B"),
    ("Fund; deals incl. NOK 50M in Zinus (with [name redacted]); other deals", "Fund; other deals"),
    ("Fund; deals incl. NOK 50M in Zinus; other [name redacted] deals", "Fund; deals incl. NOK 50M in Zinus"),
    ("Any company ready to commit to Helsinki. Sessions Feb-Apr 2027, [name redacted] 2027; co-organised with Business Helsinki.",
     "Any company ready to commit to Helsinki; co-organised with Business Helsinki."),
    ("Oil-spill response boats (EUR 357k, Apr 2026) won by [name redacted] Oy", ""),
    ("One sentence and no marker, with e.g. a dot.", "One sentence and no marker, with e.g. a dot."),
    ("", ""),
])
def test_a_sentence_or_clause_with_a_marker_is_dropped(raw, shown):
    assert fit.drop_redacted_clauses(raw) == shown


def test_the_redactor_still_hides_a_person_and_an_apostrophe_belongs_to_the_word():
    th = thesis.load()
    s = "Matti Meikäläinen joined Redstone Blue in 2026."
    assert fit.redact_person_names(s, "Kelluu Oy", th) == f"{MARKER} joined Redstone Blue in 2026."
    assert "Meikäläinen" not in fit.redact_person_names("The coach is Matti Meikäläinen of A'Pelago", "Kelluu Oy", th)
    assert "A'Pelago" in fit.redact_person_names("Matti Meikäläinen of A'Pelago", "Kelluu Oy", th)
    # write time: "A'Pelago Industries" is one run, never "A'[name]"; a person beside it is still hidden
    out = stitcher.redact_people("A'Pelago Industries signed with Matti Meikäläinen", "Kelluu Oy")
    assert "A'[name" not in out and "Matti" not in out and "Meikäläinen" not in out
    assert stitcher.redact_people("Matti Meikäläinen of A'Pelago", "Kelluu Oy") == "[name] of A'Pelago"
    assert stitcher.redact_people("Seamus O'Brien said", "Kelluu Oy") == "[name] said"
    assert "A’[name" not in stitcher.redact_people("A’Pelago Industries said", "Kelluu Oy")


@needs_snapshot
def test_org_text_on_the_match_page_and_the_org_api_has_no_marker(client):
    pages = [client.get("/match").text, client.get("/match?org=apelago").text]
    listing = client.get("/api/match/orgs").json()["orgs"]
    assert len(listing) > 100
    ids = ["apelago", "save-the-baltic-sea-award", "danske-bank-growth", "helsinki-blue-economy-studio-by-apelago-2027"]
    apis = [client.get(f"/api/match/org/{i}").text for i in ids if any(o["id"] == i for o in listing)]
    assert apis and any(o["id"] == "apelago" for o in listing)
    for text in [*pages, *apis, json.dumps(listing, ensure_ascii=False)]:
        assert MARKER not in text and "A'[name" not in text and "[name]" not in text


@needs_snapshot
def test_a_description_that_is_all_redacted_shows_the_organisation_type_only(client):
    th = thesis.load()
    cfg = matchtext.config(th)
    rows = {o["id"]: o for o in matchmaker.org_list(th)}
    # a declared description of one sentence that holds a person-shaped or unknown name: the type is shown, not a gap
    type_only = [o for o in rows.values() if o["focus"] == cfg["kinds"][o["kind"]]["label"]]
    assert type_only, "at least one declared description is dropped whole on the snapshot"
    for o in type_only:
        assert MARKER not in o["focus"]
