"""Judge round 3 fixes: corroboration families, listed and excluded companies, bands from the frameworks levels, the decision fallback,
the declared-member thesis-fit line, the backtest business-id bug and the stitcher name redaction. Synthetic fixtures only."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import round3_fixture as fx  # noqa: E402


@pytest.fixture()
def built(tmp_path, monkeypatch):
    path = tmp_path / "t.sqlite"
    conn = fx.build(path)
    monkeypatch.setenv("RADAR_DB", str(path))
    return conn


@pytest.fixture()
def client(built):
    import app
    return TestClient(app.app)


def _row(conn, key):
    from radar import store, thesis
    return next((r for r in store.feed(conn, thesis.load(), limit=10**6) if r["company_key"] == key), None)


# ---- item 3: a PRH record never corroborates a PRH name ------------------------------------------------------------

def test_prh_notices_do_not_corroborate_a_name_word(built):
    r = _row(built, "9300002-2")
    assert r is not None and r["strength"] == "weak" and "corroborated_keyword" not in r["reasons"]


def test_a_non_prh_source_corroborates(built):
    r = _row(built, "9300003-3")
    assert r is not None and "corroborated_keyword" in r["reasons"] and r["strength"] == "strong"
    assert "CORDIS" in r["why"]


def test_source_family_rule_is_printed(client):
    from radar import store
    assert store.source_family("prh_notices") == store.source_family("tax_registers") == store.source_family("prh")
    t = client.get("/method").text
    assert "same registry" in t and "never corroborate" in t


# ---- item 7: listed companies and human-health practice are left out ------------------------------------------------

def test_listed_company_is_never_in_the_feed(built, client):
    from radar import store, thesis
    assert store.is_listed_company("Solar Foods Oyj") and not store.is_listed_company("Oyjala Boats Oy")
    assert _row(built, "9300004-4") is None
    assert store.feed_counts(built, thesis.load())["excluded_listed"] == 1
    t = client.get("/").text
    assert "Synthetic Shipping Oyj" not in t and "listed company (Oyj)" in t


def test_health_file_excludes_human_health_practice(built):
    from radar import emit, store, thesis
    th = thesis.load(str(Path(__file__).resolve().parent.parent / "config" / "thesis_health_turku.yaml"))
    assert th["feed_exclude_code_prefixes"] == ["86"]
    assert "86900" not in {str(c["code"]) for c in th["industry_codes"]}
    for key, name, code in (("9300010-1", "Synthetic Terveys Oy", "86220"), ("9300011-2", "Synthetic Medtech Oy", "32500")):
        emit.upsert_company(built, company_key=key, name=name, y_tunnus=key, founded=fx.d(20), industry_code=code,
                            industry_desc="Medical specialists activities" if code == "86220" else "Medical instruments",
                            source_url=fx.PRH + key)
        emit.emit_signal(built, company_key=key, signal_type="register_entry", date=fx.d(20), source_url=fx.PRH + key,
                         confidence="high", adapter="prh")
    keys = {r["company_key"] for r in store.feed(built, th, limit=10**6)}
    assert "9300010-1" not in keys and "9300011-2" in keys
    assert store.feed_counts(built, th)["excluded_codes"] == 1


# ---- items 1 and 6: memo bands from the page's levels; the fallback decision -------------------------------------------
import shutil  # noqa: E402

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"


@pytest.fixture()
def snap(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    from radar import db, thesis
    from radar.adapters import ecosystem
    th = thesis.load()
    conn = db.connect(thesis.db_path(th))
    try:
        ecosystem.run(conn, th)
        conn.commit()
    except Exception:
        pytest.skip("ecosystem dataset not available")
    conn.close()
    return th


def test_memo_bands_are_the_page_levels(built):
    from radar import matching, memo, thesis
    th = thesis.load()
    cfg = memo._cfg(th)
    for key in ("9300001-1", "9300005-5", "dk-synthetic"):
        m = memo.build(built, th, key)
        fw = matching.company_context(built, key)["fw"]
        for dim, k in (("business", "brl"), ("investment", "irl"), ("technology", "trl")):
            assert m["levels"][dim]["band"] == memo.band(fw[k]["level"], cfg["bands"].get(dim)), (key, dim)
        assert m["recommendation"]["dimensions"]["text"].endswith("of 10 investment dimensions have public evidence")


def test_viva_jets_memo_matches_its_readiness_section_and_uses_the_fallback(snap):
    from radar import frameworks, matching, memo, store
    conn = store.open_db(thesis=snap)
    m = memo.build(conn, snap, "2962040-6")
    ctx = matching.company_context(conn, "2962040-6")
    conn.close()
    irl = ctx["fw"]["irl"]["level"]
    assert irl is not None and m["levels"]["investment"]["band"] == memo.band(irl, snap["memo"]["bands"]["investment"])
    inv_why = [w["text"] for w in m["why"] if w["text"].startswith("Investment readiness ")]
    assert inv_why and f"(level {irl})" in inv_why[0]
    r = m["recommendation"]
    assert r["decision"] == "ACCELERATOR" and r["matched"] == "fallback c2, impact implied by sector"
    assert "Medium, implied by sector" in r["because"]
    from app import app
    html = TestClient(app).get("/c/2962040-6").text
    assert "because: fallback c2, impact implied by sector" in html
    assert f"investment {irl} of 9" in html and "of 10 investment dimensions have public evidence" in html


def test_fallback_rules():
    from radar import memo, thesis
    cfg = memo._cfg(thesis.load())
    b = lambda **kw: {**{"impact": "unknown", "business": "Low", "investment": "unknown", "fit": "High", "technology": "unknown"}, **kw}  # noqa: E731
    ev = {"own_text"}                                                                     # the High fit rests on more than the industry code
    assert memo.decide(b(), cfg, ev)[0]["id"] == "c2"                                     # business Low, TRL unknown
    assert memo.decide(b(business="Medium", technology="Low"), cfg, ev)[0]["decision"] == "GRANT SUPPORT"   # TRL 1-3
    assert memo.decide(b(business="High", investment="High"), cfg, ev)[0]["decision"] == "DUE DILIGENCE"
    assert memo.decide(b(fit="Medium"), cfg, ev)[0] is None                               # fit not High: no fallback
    assert memo.decide(b(impact="Medium"), cfg, ev)[0] is None                            # impact known: the team's table decides
    assert memo.decide(b(business="unknown"), cfg, ev)[0] is None
    assert memo.decide(b(), cfg)[0] is None                                               # the industry code alone: the gate is shut


def test_fallback_rule_is_on_method(client):
    t = client.get("/method").text
    assert 'id="memo-fallback"' in t and "implied by the sector" in t and "industry code" in t


# ---- item 2: a declared company never reads "no public evidence yet"; the legal form is read from the name -----------

def test_declared_company_reads_its_membership_not_no_evidence(client):
    t = client.get("/c/9300006-6").text
    assert "Thesis fit: declared cohort company" in t
    assert "Thesis fit: no public evidence yet" not in t
    assert "legal form not in public records" not in t
    assert "industry code 46900 is outside the intake code families" in t


def test_legal_form_from_the_name():
    from radar import intake
    assert intake.form_from_name("Arctic Fry Oy") == ("16", "limited company (Oy)")
    assert intake.form_from_name("Solar Foods Oyj")[0] == "17"
    assert intake.form_from_name("Synthetic Reef") == (None, None)
    cfg = {"company_forms": {"16": "x"}, "code_prefixes": ["30"], "thesis_codes": []}
    assert intake.eligible("17", "30120", cfg, "public limited company (Oyj)")[1] == "legal form public limited company (Oyj) is not a limited company or cooperative"


# ---- item 5: the backtest intake table and the business id --------------------------------------------------------

def test_backtest_finnish_cohort_rows_are_not_no_business_id(built, client):
    from radar import earliness, thesis
    res = earliness.backtest(built, thesis.load())
    by = {r["company_key"]: r["intake"] for r in res["rows"]}
    assert by["dk-synthetic"]["state"] == "not_in_register"
    assert by["9300006-6"]["state"] == "ineligible" and "46900" in by["9300006-6"]["reason"]
    assert by["9300001-1"]["state"] != "not_in_register"


def test_backtest_on_the_snapshot_names_no_business_id_only_without_one(snap):
    from radar import earliness, store
    conn = store.open_db(thesis=snap)
    res = earliness.backtest(conn, snap)
    yt = {r[0]: r[1] for r in conn.execute("SELECT company_key, y_tunnus FROM companies WHERE group_tag='cohort'")}
    conn.close()
    finnish = [r for r in res["rows"] if yt.get(r["company_key"])]
    assert len(finnish) == 7
    assert all(r["intake"]["state"] != "not_in_register" for r in finnish)
    assert all("no business id" in r["intake"]["reason"] for r in res["rows"] if not yt.get(r["company_key"]))
    from app import app
    html = TestClient(app).get("/backtest").text
    assert html.count("(no business id)") == len(res["rows"]) - 7


# ---- item 8: the stitcher block never prints a person-shaped name ---------------------------------------------------

def test_redaction_keeps_company_and_business_words():
    from radar import fit, thesis
    th = thesis.load()
    r = lambda t: fit.redact_person_names(t, "Arctic Fry Oy", th)  # noqa: E731
    assert r('"Arctic Fry Oy" Nordic Blue') == '"Arctic Fry Oy" Nordic Blue'
    assert r("Arctic Fry Oy toimitusjohtaja Matti Virtanen") == "Arctic Fry Oy toimitusjohtaja [name redacted]"
    assert r("CEO Liisa Korhonen, Arctic Fry Oy") == "CEO [name redacted], Arctic Fry Oy"
    assert r("Business Finland funding Arctic Fry") == "Business Finland funding Arctic Fry"


def test_show_the_searches_redacts_person_names(built, client):
    rows = [("search", "query", None, '"Synthetic Harbour Boats Oy" Matti Virtanen', None),
            ("search", "llm_query", None, "Synthetic Harbour Boats founder Liisa Korhonen interview", None),
            ("verify", "kept", "Synthetic Harbour Boats Oy hired Pekka Niemi as CEO", None, "https://example.test/news/1"),
            ("verify", "dropped", "quote_not_on_page: Jussi Lahtinen", None, "https://example.test/news/2")]
    for step, outcome, reason, query, url in rows:
        built.execute("""INSERT INTO stitch_log (run_id, company_key, step, outcome, reason, query, signal_type, date, date_precision,
                         source_url, quote, confidence, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      ("2026-10-17T00:00:00Z", "9300001-1", step, outcome, reason, query, "job_ad" if step == "verify" else None,
                       "2026-09-01" if step == "verify" else None, "day" if step == "verify" else None, url,
                       "Synthetic Harbour Boats Oy CEO Pekka Niemi said the boats ship in May" if step == "verify" else None,
                       "high" if step == "verify" else None, "2026-10-17T00:00:00Z"))
    built.commit()
    t = client.get("/c/9300001-1").text
    assert 'id="stitch"' in t and "[name redacted]" in t
    for person in ("Matti Virtanen", "Liisa Korhonen", "Pekka Niemi", "Jussi Lahtinen"):
        assert person not in t, person
    assert "Synthetic Harbour Boats" in t
