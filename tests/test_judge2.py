"""Judge dry-run 2 fixes (D22 to D26): water and waste utility codes read Medium, a company's own name is never redacted, no raw
token on a company page, the backtest ranks are stated per company, and the home list is warm for every thesis.
Synthetic companies for the rules; the committed snapshot (and, when RADAR_LIVE_COPY names a copy of the live store, that copy) for pages."""
import html
import os
import json
import re
import shutil
import sqlite3
import threading
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import db, emit, frameworks, labels, matching, memo, store, thesis
from radar.adapters import prh_notices  # noqa: F401  (registers the notice signal types on emit.SIGNAL_TYPES)
from radar.adapters import tax_registers

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
LIVE = Path(os.environ["RADAR_LIVE_COPY"]) if os.environ.get("RADAR_LIVE_COPY") else None
TODAY = date(2026, 10, 16)
needs_snapshot = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot missing")


def _day(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "j2.sqlite"))
    c = db.connect(tmp_path / "j2.sqlite")
    yield c
    c.close()


def _company(conn, key, name, code, desc="Fixture activity", tag="feed", extra=()):
    emit.upsert_company(conn, company_key=key, name=name, y_tunnus=key, founded=_day(40), country="FI", industry_code=code,
                        industry_desc=desc, group_tag=tag, source_url=f"https://example.test/prh/{key}")
    for typ, ad, dt in (("register_entry", "prh", 40), ("startup_notice", "prh_notices", 30)):
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=_day(dt), source_url=f"https://example.test/{ad}/{key}/{typ}",
                         confidence="high", adapter=ad)
    for typ, ad, text in extra:
        url = f"https://example.test/{ad}/{key}/{typ}"
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=_day(20), source_url=url, confidence="medium", adapter=ad)
        sid = conn.execute("SELECT id FROM signals WHERE source_url=?", (url,)).fetchone()[0]
        for field, t in (text or {}).items():
            conn.execute("INSERT INTO signal_text (signal_id, field, text) VALUES (?,?,?)", (sid, field, t))
    conn.commit()


def _memo(conn, key):
    return memo.build(conn, thesis.load(), key, today=TODAY.isoformat())


# ---- 1. water and waste utility codes (D22) ---------------------------------------------------------------------------------

def test_medium_codes_are_configured_as_data():
    spec = thesis.load()["memo"]["bands"]["fit"]
    assert spec["medium_codes"] == ["36", "37", "39"]
    for path in thesis.available().values():
        assert isinstance(thesis.load(path)["memo"]["bands"]["fit"].get("medium_codes"), list), path
    assert thesis.load("config/thesis_baltic_blue.yaml")["memo"]["bands"]["fit"]["medium_codes"] == []
    assert thesis.load("config/thesis_health_turku.yaml")["memo"]["bands"]["fit"]["medium_codes"] == []


def test_medium_code_matches_a_family_prefix_and_ignores_a_dot():
    spec = {"medium_codes": ["36", "37", "39"]}
    assert all(memo.medium_code(c, spec) for c in ("36000", "37000", "39000", "36.00", " 39000 "))
    assert not any(memo.medium_code(c, spec) for c in ("30110", "03210", "46900", "", None))
    assert not memo.medium_code("36000", {}) and not memo.medium_code("36000", {"medium_codes": []})


def test_validation_rejects_a_malformed_medium_codes(tmp_path):
    bad = (ROOT / "config" / "thesis.yaml").read_text(encoding="utf-8").replace('medium_codes: ["36", "37", "39"]', "medium_codes: 36")
    p = tmp_path / "t.yaml"
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(thesis.ThesisError, match="medium_codes"):
        thesis.load(p)


def test_a_utility_code_with_the_line_of_business_is_watchlist_and_a_ship_code_alone_is_capped_too(conn):
    # the same fixture, the same registered line of business (a thesis word), one code in a medium family and one not
    _company(conn, "9500001-1", "Plain Utility Oy", "36000", desc="Water collection and supply")
    _company(conn, "9500001-2", "Plain Yard Oy", "30110", desc="Water collection and supply")
    u, y = _memo(conn, "9500001-1"), _memo(conn, "9500001-2")
    assert u["levels"]["fit"]["band"] == "Medium" and u["recommendation"]["decision"] == "WATCHLIST"
    assert u["recommendation"]["kind"] is None and u["recommendation"]["fallback_blocked"] is False
    assert y["levels"]["fit"]["band"] == "Medium" and y["recommendation"]["decision"] == "WATCHLIST"   # D66: a High fit on the code and its label alone is capped (was High, ACCELERATOR)


def test_every_medium_family_reads_medium(conn):
    for i, code in enumerate(("36000", "37000", "39000")):
        _company(conn, f"9500002-{i}", f"Plain Family {i} Oy", code)
        m = _memo(conn, f"9500002-{i}")
        assert m["levels"]["fit"]["band"] == "Medium" and m["recommendation"]["decision"] == "WATCHLIST", code
        assert any("ndustry code" in w["text"] and w["url"] for w in m["why"]), code  # the code is still shown as the sourced reason


def test_own_text_still_lifts_a_utility_code_to_high(conn):
    _company(conn, "9500003-1", "Plain Utility Text Oy", "36000",
             extra=[("eu_project", "cordis", {"objective": "A study of the sea and its fish."})])
    m = _memo(conn, "9500003-1")
    assert m["levels"]["fit"]["band"] == "High" and m["recommendation"]["kind"] == "fallback" and m["recommendation"]["decision"] == "ACCELERATOR"


def test_a_declared_member_on_a_utility_code_reads_high(conn):
    """D47 raises the floor of a declared cohort or portfolio member from Medium to High, so the utility code (Medium, D22) is lifted."""
    _company(conn, "9500004-1", "Plain Declared Utility Oy", "37000", tag="portfolio")
    assert _memo(conn, "9500004-1")["levels"]["fit"]["band"] == "High"


@needs_snapshot
def test_snapshot_utilities_are_not_high_on_the_code_alone_and_viva_jets_reads_portfolio_support(tmp_path, monkeypatch):
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    th = thesis.load()
    c = store.open_db(thesis=th)
    rows = c.execute("SELECT company_key, name, industry_code FROM companies WHERE substr(industry_code,1,2) IN ('36','37','39')").fetchall()
    assert len(rows) > 10
    for key, name, code in rows:
        m = memo.build(c, th, key)
        fit_line = next(w["text"] for w in m["why"] if w["text"].startswith("Thesis fit"))
        if m["levels"]["fit"]["band"] == "High":  # another reason has to stand beside the code (the source's own text)
            assert "more reason" in fit_line or "declared" in fit_line, (name, code, fit_line)   # D47: a declared member is High by its floor
        else:
            assert m["recommendation"]["decision"] != "ACCELERATOR", (name, code)
    assert memo.build(c, th, "2962040-6")["recommendation"]["decision"] == "PORTFOLIO SUPPORT"   # D65 (ACCELERATOR under D53)


# ---- 3. no raw token on a page (D24) -------------------------------------------------------------------------------------------

def test_the_tax_register_detail_names_the_register_without_its_list_code():
    cands = tax_registers.extract({"registeredEntries": [{"register": "6", "type": "80", "registrationDate": "2019-01-02"}]})
    assert cands["first_sales"] == ("2019-01-02", "VAT liability register")
    assert "6_80" not in cands["first_sales"][1]


def test_plain_text_drops_a_register_type_code_and_keeps_the_sentence():
    old = "Entered the VAT liability register (type 6_80) on 2019-01-02: the company is invoicing. Source: PRH/YTJ open data https://x.test/a_b"
    assert labels.plain_text(old) == "Entered the VAT liability register on 2019-01-02: the company is invoicing. Source: PRH/YTJ open data https://x.test/a_b"
    assert labels.plain_text("a first_hire signal") == "a first hire signal"
    assert labels.plain_text(None) == ""


def test_a_stored_legacy_detail_reaches_the_page_data_clean(conn):
    _company(conn, "9500005-1", "Plain Legacy Oy", "30110")
    emit.emit_signal(conn, company_key="9500005-1", signal_type="first_sales", date=_day(10), source_url="https://example.test/ytj/9500005-1",
                     confidence="high", adapter="tax_registers",
                     detail="Entered the VAT liability register (type 6_80) on 2026-10-06: the company is invoicing. Source: PRH/YTJ open data https://example.test/a")
    conn.commit()
    sig = next(s for s in store.company(conn, "9500005-1")["signals"] if s["signal_type"] == "first_sales")
    assert "type 6_" not in sig["detail"] and sig["detail"].startswith("Entered the VAT liability register on 2026-10-06")


def test_the_category_keyword_is_the_whole_word_not_the_stem():
    c = {"industry_desc": "Freshwater aquaculture", "source_url": "https://example.test/prh"}
    cat = frameworks.category(c, [])
    assert cat["category"] == "aquatech" and cat["keyword"] == "aquaculture"
    sig = {"detail": "Took part in a project on seaweed farming", "evidence": {"url": "https://example.test/s"}}
    assert frameworks.category({}, [sig])["keyword"] == "seaweed"
    assert frameworks.whole_word("zero-emission ships", "emission") == "emission" and frameworks.whole_word("no hit", "xyz") == "xyz"


def test_the_impact_reason_prints_no_quoted_stem(conn):
    """The impact line of the memo is the Ocean Impact ladder's (D46): level and area in words, never a quoted word stem."""
    _company(conn, "9500006-1", "Plain Fry Oy", "03220", desc="Freshwater aquaculture",
             extra=[("eu_project", "cordis", {"objective": "A project on freshwater aquaculture."})])
    m = _memo(conn, "9500006-1")
    text = next(w["text"] for w in m["why"] if w["text"].startswith("Ocean impact"))
    assert text == "Ocean impact Medium: evidence readiness is level 5 of 9 (sustainable ocean resources: aquaculture and fisheries)"
    assert "keyword '" not in text and "aquacultur)" not in text


def test_capability_codes_become_their_labels():
    s = matching.plain_why("caps ['C10', 'C3']; kw []; stage 1.0", 67.5)
    assert "Maritime decarbonisation and energy" in s and "Coastal tourism, boating and marine services" in s
    assert not re.search(r"\bC\d+\b", s)
    assert matching.cap_names(["C99"]) == [] and matching._caps_phrase(["C99"]) == "a shared capability"
    # Aava's spoken answers are checked for bare capability ids in tests/test_aava.py (the conversational rewrite has no _reason).


# ---- the rendered company pages: snapshot, and the live copy when one is named ----------------------------------------------

FORBIDDEN = (("type 6_", re.compile(r"type 6_")), ("keyword '", re.compile(r"keyword '")), ("a bare C3 or C10", re.compile(r"\bC(?:3|10)\b")),
             ("[name redacted]", re.compile(re.escape("[name redacted]"))))
LEVEL_WORDS = {"Low", "Medium", "High", "no public evidence yet"}


def _page_text(client, key):
    r = client.get(f"/c/{key}")
    assert r.status_code == 200, key
    return html.unescape(r.text)


def _ocean_impact_stat(page: str) -> str | None:
    m = re.search(r"<dt>Ocean impact</dt>\s*<dd>(.*?)</dd>", page, re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else None


def _check_pages(client):
    for key in ("2962040-6", "3166759-6"):
        page = _page_text(client, key)
        for label, rx in FORBIDDEN:
            assert not rx.search(page), (key, label, rx.search(page) and page[max(0, rx.search(page).start() - 80):rx.search(page).end() + 80])
        stat = _ocean_impact_stat(page)
        assert stat is None or stat in LEVEL_WORDS, (key, stat)
    assert "Ocean Impact Assessment" in _page_text(client, "3166759-6")  # Arctic Fry: the ocean block replaces the key-statistic row (D27)


@needs_snapshot
def test_company_pages_on_the_snapshot_have_no_raw_token(monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(SNAP))
    monkeypatch.delenv("RADAR_DB", raising=False)
    import app
    _check_pages(TestClient(app.app))


@pytest.mark.skipif(LIVE is None or not LIVE.is_file(), reason="set RADAR_LIVE_COPY to a copy of the live store")
def test_company_pages_on_the_live_copy_have_no_raw_token(monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(LIVE))
    import app
    _check_pages(TestClient(app.app))


# ---- D23: a company's own name is never taken for a person's ----------------------------------------------------------------

def _names_conn(companies, candidates=()):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE companies (company_key TEXT PRIMARY KEY, name TEXT, group_tag TEXT)")
    c.execute("CREATE TABLE field_candidates (company_key TEXT, field TEXT, value TEXT)")
    c.executemany("INSERT INTO companies VALUES (?,?,?)", companies)
    c.executemany("INSERT INTO field_candidates VALUES (?,?,?)", [(k, "name", v) for k, v in candidates])
    c.commit()
    return c


STORE = [("2962040-6", "Viva Jets Oy", "portfolio"), ("2902007-2", "Kelluu Oy", "cohort"), ("3508136-5", "Suomen Vesistökunnostus Oy", "feed"),
         ("3999999-9", "Pekka Virtanen Oy", "intake")]


def test_a_company_name_and_a_person_in_one_sentence():
    from radar import fit, names
    th = thesis.load()
    c = _names_conn(STORE)
    s = "Viva Jets Oy, founded in Oulu in 2018, was joined by Jane Doe."
    for page in ("2962040-6", "2902007-2"):  # its own page, and another company's page
        out = fit.redact_person_names(s, dict((k, n) for k, n, _ in STORE)[page], th, known=names.known_names(c, th, page))
        assert out == "Viva Jets Oy, founded in Oulu in 2018, was joined by [name redacted]."
    # with no store read, as before: another company's name is hidden, but the legal form is no part of a name
    assert fit.redact_person_names(s, "Kelluu Oy", th) == "[name redacted] Oy, founded in Oulu in 2018, was joined by [name redacted]."


def test_a_name_without_its_legal_form_and_a_former_name_survive():
    from radar import fit, names
    th = thesis.load()
    c = _names_conn(STORE, [("2962040-6", "SNOWSUS OY")])
    known = names.known_names(c, th, "2962040-6")
    r = lambda t, own="Viva Jets Oy", k=known: fit.redact_person_names(t, own, th, known=k)  # noqa: E731
    assert r("Snowsus Ltd., founded in Oulu in 2018, is set to start production") == "Snowsus Ltd., founded in Oulu in 2018, is set to start production"
    assert r("Viva Jets announced a dealer", "Kelluu Oy", names.known_names(c, th, "2902007-2")) == "Viva Jets announced a dealer"
    assert r('OR "Suomen Vesistökunnostus" OR "Matti Meikalainen"', "Kelluu Oy") == 'OR "Suomen Vesistökunnostus" OR "[name redacted]"'
    assert r("Kelluu's Canadian subsidiary", "Kelluu Oy") == "Kelluu's Canadian subsidiary"


def test_a_register_name_that_could_be_a_persons_is_kept_only_with_its_legal_form():
    from radar import fit, names
    th = thesis.load()
    known = names.known_names(_names_conn(STORE), th, "2962040-6")
    assert fit.redact_person_names("Pekka Virtanen Oy won it", "Viva Jets Oy", th, known=known) == "Pekka Virtanen Oy won it"
    assert fit.redact_person_names("Pekka Virtanen said", "Viva Jets Oy", th, known=known) == "[name redacted] said"  # a person who shares a register name


def test_the_declared_lists_and_a_stray_bracket_fragment():
    from radar import fit, names
    th = thesis.load()
    declared = names.declared_names(th)
    assert declared  # the investor, corporate and programme lists named under `matching`
    idx = names.known_names(_names_conn([]), th, None)
    assert ("funding",) not in idx.base and ("business", "finland", "young", "innovative", "company", "funding") in idx.base  # "(NIY)" is read out
    protected = [n for n in declared if fit.redact_person_names(n, "", th) != n and fit.redact_person_names(n, "", th, known=idx) == n]
    assert protected, "a declared name the plain redactor hides is kept when the declared lists are read"


def test_the_write_time_redactor_keeps_a_known_name_inside_a_longer_run():
    from radar import names
    from radar.adapters import stitcher
    th = thesis.load()
    known = names.known_names(_names_conn(STORE), th, "2902007-2")
    assert stitcher.redact_people("Today Viva Jets said Jane Doe", "Kelluu Oy", known) == "Today Viva Jets said [name]"
    assert stitcher.redact_people("Jane Doe joined Kelluu Oy", "Kelluu Oy", known) == "[name] joined Kelluu Oy"
    assert stitcher.redact_people("Jane Doe met Viva Jets", "Kelluu Oy") == "[name] met [name]"  # no store read: as before


def _repair_fixture(tmp_path):
    db = tmp_path / "s.sqlite"
    c = _names_conn(STORE)
    disk = sqlite3.connect(db)
    c.backup(disk)
    disk.executescript("""CREATE TABLE stitch_log (id INTEGER PRIMARY KEY, run_id TEXT, company_key TEXT, step TEXT, outcome TEXT, reason TEXT,
                          query TEXT, quote TEXT);
                          CREATE TABLE signals (id INTEGER PRIMARY KEY, company_key TEXT, adapter TEXT, detail TEXT);
                          CREATE TABLE company_brief_slots (company_key TEXT PRIMARY KEY, written TEXT, slots_json TEXT, imported_at TEXT);""")
    disk.execute("INSERT INTO stitch_log VALUES (1,'r','2902007-2','search','llm_query',NULL,?,NULL)", ('"[name]" OR "[name]"',))
    disk.execute("INSERT INTO stitch_log VALUES (2,'r','2902007-2','read','proposed',NULL,NULL,?)", ("[name] announced a deal with [name]",))
    disk.execute("INSERT INTO stitch_log VALUES (3,'r','2902007-2','read','proposed',NULL,NULL,?)", ("kept as it is: [name] only",))
    disk.execute("INSERT INTO signals VALUES (9,'2902007-2','stitcher',?)", ('"[name] announced a deal with [name]" (kelluu.com) Page first archived 2026-01-01.',))
    disk.execute("INSERT INTO company_brief_slots VALUES ('2902007-2','2026-10-17',?, 'x')",
                 (json.dumps({"what_it_does": {"text": "[name redacted] makes airships.", "cites": []}}),))
    disk.commit()
    disk.close()
    f = tmp_path / "fetched"
    (f / "stitcher" / "proposals").mkdir(parents=True)
    (f / "briefs" / "out2").mkdir(parents=True)
    (f / "stitcher" / "proposals" / "2902007-2.json").write_text(json.dumps({
        "queries_run": ['"Viva Jets" OR "Jane Doe"'],
        "events": [{"quote": "Viva Jets announced a deal with Jane Doe"}]}), encoding="utf-8")
    (f / "briefs" / "out2" / "2902007-2.json").write_text(json.dumps({"slots": {"what_it_does": {"text": "Viva Jets makes airships."}}}), encoding="utf-8")
    return db, f


def test_repair_restores_company_names_and_keeps_the_person_redacted(tmp_path):
    from radar import repair_redaction
    db, f = _repair_fixture(tmp_path)
    before = sqlite3.connect(db).execute("SELECT group_concat(coalesce(query,quote,detail,'')) FROM (SELECT query, quote, NULL AS detail FROM stitch_log "
                                         "UNION ALL SELECT NULL, NULL, detail FROM signals)").fetchone()
    dry = repair_redaction.run(db, dry_run=True, fetched=f)
    assert dry["texts_changed"] == 4 and dry["restored"] == 4  # the query, the quote, the signal detail and the brief slot
    assert sqlite3.connect(db).execute("SELECT group_concat(coalesce(query,quote,detail,'')) FROM (SELECT query, quote, NULL AS detail FROM stitch_log "
                                       "UNION ALL SELECT NULL, NULL, detail FROM signals)").fetchone() == before  # a dry run writes nothing
    r = repair_redaction.run(db, dry_run=False, fetched=f)
    assert (r["markers"], r["restored"], r["left"], r["unrecoverable"]) == (8, 4, 4, 1)  # row 3 has no saved original; every person stays hidden
    c = sqlite3.connect(db)
    assert c.execute("SELECT query FROM stitch_log WHERE id=1").fetchone()[0] == '"Viva Jets" OR "[name]"'
    assert c.execute("SELECT quote FROM stitch_log WHERE id=2").fetchone()[0] == "Viva Jets announced a deal with [name]"
    assert c.execute("SELECT quote FROM stitch_log WHERE id=3").fetchone()[0] == "kept as it is: [name] only"
    assert c.execute("SELECT detail FROM signals").fetchone()[0].startswith('"Viva Jets announced a deal with [name]" (kelluu.com) Page first')
    assert json.loads(c.execute("SELECT slots_json FROM company_brief_slots").fetchone()[0])["what_it_does"]["text"] == "Viva Jets makes airships."
    again = repair_redaction.run(db, dry_run=False, fetched=f)
    assert again["restored"] == 0 and again["texts_changed"] == 0  # safe to run twice


@pytest.mark.skipif(LIVE is None or not LIVE.is_file(), reason="set RADAR_LIVE_COPY to a copy of the live store")
def test_viva_jets_stitcher_block_names_the_former_company_on_the_live_copy(monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(LIVE))
    import app
    page = _page_text(TestClient(app.app), "2962040-6")
    assert "Snowsus Ltd., founded in Oulu in 2018" in page and "[name redacted]., founded" not in page


# ---- D26: every sector's home list is warm, and no request waits more than 3 seconds for it ---------------------------------

@pytest.fixture
def warm_env(tmp_path, monkeypatch):
    for n in ("radar_redstone_apelago_blue.sqlite", "radar_health_tech_turku.sqlite"):
        shutil.copy(SNAP / n, tmp_path / n)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    from radar import home_list
    monkeypatch.setattr(home_list, "_cache", {})
    monkeypatch.setattr(home_list, "_building", {})
    return home_list


def _wait_idle(hl, seconds=20):
    end = time.time() + seconds
    while hl._building and time.time() < end:
        time.sleep(0.05)
    assert not hl._building


@needs_snapshot
def test_warm_all_builds_every_thesis_with_a_store_default_first(warm_env, monkeypatch):
    hl, seen = warm_env, []
    monkeypatch.setattr(hl, "build", lambda conn, th, today=None: seen.append(th["id"]) or {"rows": [], "groups": [], "countries": []})
    assert set(thesis.available()) >= {"redstone_apelago_blue", "baltic_blue", "health_tech_turku"}  # three sectors in config/
    hl.warm_all()
    end = time.time() + 20
    while len(seen) < 2 and time.time() < end:
        time.sleep(0.05)
    _wait_idle(hl)
    assert seen[0] == "redstone_apelago_blue" and sorted(seen) == ["health_tech_turku", "redstone_apelago_blue"]  # baltic has no store in this folder
    assert len(hl._cache) == 2


@needs_snapshot
def test_a_request_during_warming_gets_the_plain_feed_and_a_note(warm_env, monkeypatch):
    hl, gate = warm_env, threading.Event()
    monkeypatch.setattr(hl, "WAIT_SECONDS", 0.3)
    monkeypatch.setattr(hl, "build", lambda conn, th, today=None: gate.wait(30) and {"rows": [], "groups": [], "countries": []})
    import app
    client = TestClient(app.app)
    t0 = time.time()
    r = client.get("/?thesis=health_tech_turku")
    assert r.status_code == 200 and time.time() - t0 < 3
    assert 'id="home-warming"' in r.text and "Every line links to the public record" in r.text  # the plain feed, one note
    assert client.get("/?thesis=health_tech_turku").text.count('id="home-warming"') == 1  # still building: no second build, same answer
    assert sum(1 for k in hl._building if k[0] == "health_tech_turku") == 1
    gate.set()
    _wait_idle(hl)
    assert 'id="home-warming"' not in client.get("/?thesis=health_tech_turku").text and any(k[0] == "health_tech_turku" for k in hl._cache)


@needs_snapshot
def test_a_failed_build_gives_the_plain_feed_without_a_note_and_is_tried_again(warm_env, monkeypatch):
    hl, calls = warm_env, []
    monkeypatch.setattr(hl, "build", lambda conn, th, today=None: calls.append(1) or (_ for _ in ()).throw(RuntimeError("boom")))
    th = thesis.load(thesis.available()["health_tech_turku"])
    assert hl.for_template(th) is None
    _wait_idle(hl)
    assert hl.for_template(th) is None and len(calls) == 2


def test_partner_organisations_are_still_found_by_the_folded_name_lists():
    from radar import store
    assert store.is_partner_org("A'Pelago Accelerator Oy") and store.is_partner_org("Redstone Blue Oy")
    assert store.is_partner_org("Voima Ventures") and not store.is_partner_org("Viva Jets Oy")
