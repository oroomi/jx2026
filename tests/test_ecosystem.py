import pytest
from fastapi.testclient import TestClient

from radar import db, earliness, frameworks, store, thesis
from radar.adapters import ecosystem
from tests.fixtures import ecosystem_fixture as fx


@pytest.fixture()
def imported(tmp_path):
    ds = tmp_path / "eco.sqlite"
    fx.build_dataset(ds)
    conn = fx.build_radar(tmp_path / "r.sqlite")
    res = ecosystem.run(conn, None, path=ds)
    return conn, ds, res, tmp_path


def _counts(conn):
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("companies", "signals", "eco_entity", "eco_match", "eco_readiness")}


def test_import_is_idempotent(imported):
    conn, ds, _, _ = imported
    before = _counts(conn)
    ecosystem.run(conn, None, path=ds)
    assert _counts(conn) == before


def test_matching_existing_companies_by_id_then_name_then_domain(imported):
    conn, *_ = imported
    keys = {r["entity_id"]: r["company_key"] for r in conn.execute("SELECT entity_id, company_key FROM eco_entity WHERE side='supply'")}
    assert keys["S1"] == "9100001-1"                       # business id
    assert keys["S4"] == "name:fixture-domain"             # website domain
    assert keys["S2"] == "9100002-2"                       # new company keyed by its business id
    assert conn.execute("SELECT group_tag FROM companies WHERE company_key='9100002-2'").fetchone()[0] == "ecosystem"
    assert conn.execute("SELECT group_tag FROM companies WHERE company_key='9100001-1'").fetchone()[0] == "cohort"  # never downgraded


def test_defunct_target_and_missing_link_are_not_imported_as_matches(imported):
    conn, *_ = imported
    names = {r[0] for r in conn.execute("SELECT t.name FROM eco_match m JOIN eco_entity t ON t.entity_id=m.target_id WHERE m.company_key='9100001-1'")}
    assert names == {"Fixture Capital", "Fixture Angels", "Fixture Fund", "Fixture Buyer"}
    assert conn.execute("SELECT source_url FROM eco_entity WHERE entity_id='C3'").fetchone()[0] == "https://fund.example.test/about"


def test_only_dated_typed_events_become_signals(imported):
    conn, *_ = imported
    rows = {(r["signal_type"], r["date"]): r for r in conn.execute("SELECT * FROM signals WHERE adapter='ecosystem'")}
    assert ("pilot_named", "2025-11-20") in rows
    assert ("exhibitor", "2025-10-31") in rows            # month only: last day of the month, labelled
    assert "month only" in rows[("exhibitor", "2025-10-31")]["detail"]
    assert ("award", "2024-01-01") in rows                # year only
    assert conn.execute("SELECT date_precision FROM signal_meta WHERE signal_id=?", (rows[("award", "2024-01-01")]["id"],)).fetchone()[0] == "year"
    types = {k[0] for k in rows}
    assert "product_launch" not in types                  # no date
    assert not any(t == "founding" for t in types)
    assert ("ecosystem_event", "2026-02-09") in rows and ("programme_entry", "2026-02-09") not in rows  # the cohort entry is not a discovery
    assert [k for k in rows if k[0] == "job_ad"] == [("job_ad", "2026-10-16")]  # month capped at the dataset's verification date; "open application" skipped
    r = rows[("pilot_named", "2025-11-20")]
    assert "declared research (16 Oct 2026)" in r["detail"] and "dataset confidence high" in r["detail"]
    assert "Some Person" not in r["detail"]               # no free text, no named individuals


def test_readiness_text_has_no_personal_links_or_roles(imported):
    conn, *_ = imported
    r = conn.execute("SELECT * FROM eco_readiness WHERE company_key='9100001-1'").fetchone()
    assert "linkedin" not in (r["sources"] + r["br_evidence"]).lower()
    assert "chair" not in r["br_evidence"].lower() and "https://rev.example.test/fixture" in r["br_evidence"]


def test_dataset_signals_never_change_a_rule_level(imported):
    conn, *_ = imported
    c = dict(conn.execute("SELECT * FROM companies WHERE company_key='9100001-1'").fetchone())
    sigs = store.company(conn, "9100001-1")["signals"]
    live = [s for s in sigs if s["adapter"] != "ecosystem"]
    assert any(s["signal_type"] == "funding_round" for s in sigs)
    assert frameworks.assess(c, live)["trl"]["level"] is None


def test_company_page_prints_dataset_reading_beside_the_rule(imported, monkeypatch):
    conn, _, _, tmp = imported
    conn.close()
    monkeypatch.setenv("RADAR_DB", str(tmp / "r.sqlite"))
    import app
    t = TestClient(app.app).get("/c/9100001-1").text
    assert "Dataset evidence (16 Oct 2026)" in t
    assert "The dataset reads TRL 6; the register rule gives no level" in t
    assert "not a rule level" in t
    assert "Fixture Capital" in t and "caps [&#39;C1&#39;]" in t           # reason string as given, escaped
    assert "linkedin.com/in" not in t.lower()


def test_backtest_keeps_declared_research_in_its_own_group(imported):
    conn, *_ = imported
    th = thesis.load()
    res = earliness.backtest(conn, th)
    assert res["declared"] == 1 and res["earlier"] == 0   # the 2024 year-only award is declared research, found earlier only by it
    assert res["earlier"] + res["declared"] + res["later"] + res["none"] == res["total"]
    for r in res["rows"]:
        if r["group"] == "earlier":
            assert r["first_signal"]["adapter"] != "ecosystem"   # declared research never counts as a live public record
        if r["group"] == "declared":
            assert r["first_signal"]["adapter"] == "ecosystem"
