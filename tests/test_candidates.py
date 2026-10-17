"""Field candidates and the stop-and-ask list (jx40), on a copy of the committed snapshot store and the declared files.
The machine-local sources (the PRH cache, the Hilma awards file) are left out so the result is the same on every checkout."""
import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest

from radar import candidates, formats, stop_and_ask, thesis

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot" / "radar_redstone_apelago_blue.sqlite"
ECO = ROOT / "data" / "declared" / "ecosystem" / "blue_economy_fi.sqlite"
pytestmark = pytest.mark.skipif(not SNAP.is_file() or not ECO.is_file(), reason="snapshot store or ecosystem dataset not in this checkout")
LOCAL = ("prh", "hilma")


def _digest(conn, table):
    h = hashlib.sha256()
    for r in conn.execute(f"SELECT * FROM {table} ORDER BY 1"):
        h.update(repr(tuple(r)).encode())
    return h.hexdigest()


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    path = tmp_path_factory.mktemp("cand") / "copy.sqlite"
    shutil.copy(SNAP, path)
    conn = sqlite3.connect(str(path))
    before = {t: _digest(conn, t) for t in ("companies", "signals", "signal_meta", "blueinvest_profiles")}
    rows, stats = candidates.collect(conn, thesis.load(), skip=LOCAL)
    candidates.write(conn, rows)
    return conn, candidates.load_rows(conn), stats, before


def test_build_is_additive(built):
    conn, rows, _, before = built
    assert {t: _digest(conn, t) for t in before} == before  # no existing table changes
    assert len(rows) > 1000


def test_every_row_is_well_formed(built):
    _, rows, _, _ = built
    for r in rows:
        assert r["field"] in candidates.FIELDS and r["source"] in candidates.SOURCES and r["status"] in candidates.STATUSES
        assert r["source_url"].startswith(("http://", "https://")) and r["value"].strip() and r["basis"]
        assert r["rule_id"] == "A1" and r["field_rule"] in ("A1", "A18", "A29")
        assert r["observed"] is None or formats.date_ok(r["observed"])
        assert not (r["applied"] and r["status"] == "PENDING_DECISION")
        if r["field"] == "founded":
            assert r["precision"] in formats.PRECISIONS


def test_every_store_value_is_an_applied_row(built):
    conn, rows, stats, _ = built
    applied = {(r["company_key"], r["field"]) for r in rows if r["status"] == "applied"}
    th = thesis.load()
    from radar import fit
    n = 0
    for r in conn.execute("SELECT company_key, name, founded, industry_code, website, country FROM companies"):
        if fit.looks_like_person(r[1] or "", th):
            assert not any(x["company_key"] == r[0] for x in rows)  # a person-shaped company gets no rows at all
            continue
        for f, v in zip(("name", "founded", "industry_code", "website", "country"), r[1:]):
            if v:
                assert (r[0], f) in applied
                n += 1
    assert n > 2000 and stats["person_shaped_skipped"] >= 1


def test_sources_are_read(built):
    _, rows, stats, _ = built
    for src in ("store", "declared", "universe", "businessfinland", "ecosystem", "blueinvest", "cordis", "brreg", "cvr"):
        assert stats["read"][src] > 0, src
    assert stats["read"]["prh"] == 0 and stats["read"]["hilma"] == 0  # left out here, read on the server


def test_known_candidates(built):
    _, rows, _, _ = built
    viva = {(r["field"], r["source"], r["value"]) for r in rows if r["company_key"] == "2962040-6"}
    assert ("name", "store", "Viva Jets Oy") in viva and ("name", "declared", "Viva Electric Jets") in viva
    redkik = {(r["field"], r["value"], r["status"], r["issue_id"]) for r in rows if r["company_key"] == "3154837-8"}
    assert ("country", "US", "PENDING_DECISION", "B1-06") in redkik and ("country", "FI", "applied", None) in redkik


def test_no_person_data(built):
    _, rows, _, _ = built
    eco = sqlite3.connect(f"file:{ECO}?mode=ro", uri=True)
    people = {r[0] for r in eco.execute("SELECT name FROM person") if r[0] and len(r[0]) > 5}
    th = thesis.load()
    from radar import fit
    for r in rows:
        assert not any(p in r["value"] for p in people), r
        if r["field"] == "name":
            assert not fit.looks_like_person(r["value"], th), r


def test_comparison_rules():
    a = {"value_norm": "2019", "precision": "year"}
    assert candidates.same("founded", a, {"value_norm": "2019-09-18", "precision": "day"})
    assert not candidates.same("founded", a, {"value_norm": "2020-01-01", "precision": "day"})
    assert candidates.norm("town", "Piikkio (Kaarina)") == candidates.norm("town", "Piikkiö")
    assert candidates.norm("website", "https://www.Example.fi/about") == candidates.norm("website", "example.fi")
    assert candidates.norm("industry_code", "10.890") == "10890"
    assert candidates.norm("name", "Viva Jets Oy") == candidates.norm("name", "VIVA JETS OY")
    assert candidates.same("industry_desc", {"value_norm": "x", "lang": "en"}, {"value_norm": "y", "lang": "fi"}) is None


def test_conflicts_and_open_questions(built):
    _, rows, stats, _ = built
    c = candidates.conflicts(rows)
    assert set(c) == set(candidates.FIELDS)
    assert c["name"] and c["town"] and c["website"] and c["country"]
    pending = [r for r in rows if r["status"] == "PENDING_DECISION"]
    assert pending and stats["pending"] == len(pending)
    assert {r["issue_id"] for r in pending} <= set(candidates.OPEN_ISSUES)
    in_conflict = {(it["company_key"], f) for f, items in c.items() for it in items}
    assert all((r["company_key"], r["field"]) in in_conflict for r in pending)  # only rows in a conflict are asked about
    text = candidates.report(rows)
    assert all(f"  {f}:" in text for f in candidates.FIELDS) and "PENDING_DECISION rows by open issue" in text


def test_build_refuses_the_live_store(tmp_path):
    with pytest.raises(SystemExit):
        candidates._guard(ROOT / "data" / "radar_redstone_apelago_blue.sqlite", allow_live=False)
    candidates._guard(tmp_path / "copy.sqlite", allow_live=False)


def test_business_id_and_country_formats():
    assert formats.business_id_ok("2962040-6") and formats.business_id_ok("3166759-6")
    assert not formats.business_id_ok("2962040-5") and not formats.business_id_ok("296204-6")
    assert formats.country_ok("FI") and not formats.country_ok("XX") and not formats.country_ok("fi")


def test_stop_and_ask_on_the_snapshot(built):
    conn, _, _, _ = built
    res = stop_and_ask.signal_checks(conn, "2026-10-17")
    comp = stop_and_ask.company_checks(stop_and_ask.store_companies(conn), "2026-10-17")
    assert any({"2945733-8", "name:awake-ai"} <= {k for k, _, _ in g} for g in comp["duplicate_name"])
    assert comp["bad_business_id"] == [] and comp["bad_country"] == []
    assert all(t != "bf_funding" for t, *_ in res["amount_shared"])  # the export's one dashboard link is not a shared notice
    assert all(d > "2026-10-17" for *_, d in res["date_future"])
