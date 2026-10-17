"""python3 -m radar.combined: the declared ecosystem file with the radar's public-record tables appended (radar_ prefix).
All checks run on the committed snapshot in data/snapshot and the committed ecosystem file."""
import hashlib
import sqlite3
from pathlib import Path

import pytest

from radar import blueinvest, combined, db as db_mod, frameworks, memo, store, thesis as thesis_mod
from radar.adapters.ecosystem import DB_PATH as ECO

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
THESIS = "redstone_apelago_blue"
STORE = SNAP / f"radar_{THESIS}.sqlite"


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _ro(p):
    c = sqlite3.connect(f"{Path(p).resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    c.row_factory = sqlite3.Row
    return c


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("combined") / "c.sqlite"
    shas = (_sha(STORE), _sha(ECO))
    res = combined.run(THESIS, out, store_path=STORE, progress=lambda m: None)
    res["files_after_run"] = sorted(p.name for p in out.parent.iterdir())  # before any test opens the file
    return out, res, shas


@pytest.fixture(scope="module")
def conn(built):
    c = sqlite3.connect(built[0])
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _count(c, table):
    return c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def test_every_table_of_the_ecosystem_file_arrives_with_equal_rows(conn):
    src = _ro(ECO)
    tables = combined._tables(src)
    assert "person" not in tables and "entity" in tables and len(tables) >= 20     # the public copy has no person table (D80)
    for t in tables:
        assert _count(conn, t) == _count(src, t), t
    assert combined._digests(src) == {t: d for t, d in combined._digests(conn).items() if not t.startswith("radar_")}
    views = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='view'")}
    assert views <= {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")}


def test_the_inputs_are_not_touched(built):
    _, _, (store_sha, eco_sha) = built
    assert _sha(STORE) == store_sha and _sha(ECO) == eco_sha


def test_radar_companies_equals_the_stores_companies(conn):
    src = _ro(STORE)
    assert _count(conn, "radar_companies") == _count(src, "companies") > 700
    assert _count(conn, "radar_signals") == _count(src, "signals")
    keys = {r[0] for r in src.execute("SELECT company_key FROM companies")}
    assert {r[0] for r in conn.execute("SELECT company_key FROM radar_companies")} == keys
    row = conn.execute("SELECT * FROM radar_companies WHERE business_id IS NOT NULL LIMIT 1").fetchone()
    assert row["business_id"] == row["company_key"] and row["source_url"].startswith("http")


def test_signals_carry_date_precision_and_their_source(conn):
    assert {r[0] for r in conn.execute("SELECT DISTINCT date_precision FROM radar_signals")} <= {"day", "year"}
    assert conn.execute("SELECT COUNT(*) FROM radar_signals WHERE source_url IS NULL OR source_url=''").fetchone()[0] == 0
    src = _ro(STORE)
    year_only = src.execute("SELECT COUNT(*) FROM signal_meta WHERE date_precision='year'").fetchone()[0]
    assert conn.execute("SELECT COUNT(*) FROM radar_signals WHERE date_precision='year'").fetchone()[0] == year_only > 0


def test_readiness_is_what_the_company_page_computes(built, conn, tmp_path):
    scratch = tmp_path / "s.sqlite"
    combined._scratch_copy(STORE, scratch)
    sc = db_mod.connect(scratch)
    assert _count(conn, "radar_readiness") == 4 * _count(conn, "radar_companies")
    keys = [r[0] for r in conn.execute("SELECT company_key FROM radar_signals GROUP BY company_key ORDER BY COUNT(*) DESC, company_key LIMIT 15")]
    keys += [r[0] for r in conn.execute("SELECT company_key FROM radar_companies ORDER BY company_key LIMIT 15")]
    for k in keys:
        d = store.company(sc, k)
        fw = frameworks.page_levels(d["company"], d["signals"], blueinvest.profile_for(sc, k))
        got = {r["dimension"]: r for r in conn.execute("SELECT * FROM radar_readiness WHERE company_key=?", (k,))}
        assert set(got) == set(frameworks.LABELS)
        for dim, field in combined.LEVEL_FIELD.items():
            assert got[dim]["level"] == fw[field]["level"], (k, dim)
            assert got[dim]["rule"] == fw[field]["because"]
            assert (got[dim]["evidence_url"] is None) == (fw[field]["level"] is None)
        assert got[combined.CATEGORY_DIM]["category"] == fw["category"]["category"]
        assert got[combined.CATEGORY_DIM]["level"] is None
    assert any(r[0] is not None for r in conn.execute("SELECT level FROM radar_readiness"))


def test_verdicts_are_the_memo_build(built, conn, tmp_path):
    scratch = tmp_path / "s.sqlite"
    combined._scratch_copy(STORE, scratch)
    sc = db_mod.connect(scratch)
    th = thesis_mod.load(thesis_mod.available()[THESIS])
    assert _count(conn, "radar_verdicts") == _count(conn, "radar_companies")
    assert built[1]["memo_errors"] == [] and conn.execute("SELECT COUNT(*) FROM radar_verdicts WHERE error IS NOT NULL").fetchone()[0] == 0
    assert {r[0] for r in conn.execute("SELECT DISTINCT decision FROM radar_verdicts")} <= set(memo.DECISIONS)
    decided = [r[0] for r in conn.execute("SELECT company_key FROM radar_verdicts WHERE decision <> 'WATCHLIST' ORDER BY company_key LIMIT 10")]
    assert decided
    for k in decided + [r[0] for r in conn.execute("SELECT company_key FROM radar_verdicts WHERE decision = 'WATCHLIST' ORDER BY company_key LIMIT 5")]:
        m = memo.build(sc, th, k)["recommendation"]
        v = conn.execute("SELECT * FROM radar_verdicts WHERE company_key=?", (k,)).fetchone()
        assert (v["decision"], v["matched"], v["because"], v["note"]) == (m["decision"], m["matched"], m["because"], m.get("note"))


def test_the_memoised_checks_are_put_back(built):
    assert not hasattr(store.is_partner_org, "cache_info") and not hasattr(store.name_key, "cache_info")


def test_no_person_data_in_any_radar_table(conn):
    src = _ro(ECO)
    from tests.people import person_names
    names = person_names()[:50]                     # none in the public file (D80); the full copy via RADAR_PERSON_GUARD_DB
    company_names = {r[0].casefold().strip() for r in conn.execute("SELECT name FROM radar_companies")}
    detail = "\n".join(r[0].casefold() for r in conn.execute("SELECT detail FROM radar_signals WHERE detail IS NOT NULL"))
    for n in names:
        assert n.casefold().strip() not in company_names
        assert n.casefold().strip() not in detail
    for t in (r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'radar\\_%' ESCAPE '\\'")):
        cols = [r[1].lower() for r in conn.execute(f"PRAGMA table_info({t})")]
        assert not [c for c in cols if "person" in c or "people" in c], t
    view_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (combined.VIEW,)).fetchone()[0].lower()
    assert "person" not in view_sql and "raw_json" not in view_sql
    assert combined.person_guard(conn, combined.person_names(src)) == []


def test_the_person_guard_finds_a_name():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE radar_x (id INTEGER, detail TEXT)")
    c.execute("INSERT INTO radar_x VALUES (1, 'a meeting with Firstname Lastname about a grant')")
    c.execute("CREATE TABLE other (detail TEXT)")
    c.execute("INSERT INTO other VALUES ('Firstname Lastname')")
    assert combined.person_guard(c, ["firstname lastname"]) == ["radar_x.detail"]
    assert combined.person_guard(c, ["someone else"]) == []


def test_the_view_joins_entities_to_companies_by_finnish_business_id(conn):
    src = _ro(ECO)
    rows = conn.execute(f"SELECT * FROM {combined.VIEW}").fetchall()
    assert len(rows) == _count(src, "entity") == 215
    assert len({r["entity_id"] for r in rows}) == 215
    matched = [r for r in rows if r["radar_company_key"]]
    assert matched and all(r["radar_company_key"] == r["join_business_id"] for r in matched)
    assert all(r["radar_company_key"] is None for r in rows if r["join_business_id"] is None)
    # the same join, written another way, on the store itself
    st = _ro(STORE)
    ids = {r[0] for r in st.execute("SELECT y_tunnus FROM companies WHERE y_tunnus IS NOT NULL")}
    expect = [r[0] for r in src.execute("SELECT id FROM entity WHERE business_id IN (%s)" % ",".join("?" * len(ids)), list(ids))]
    assert sorted(r["entity_id"] for r in matched) == sorted(expect)
    # signals land on the matched companies
    by_co = dict(st.execute("SELECT company_key, COUNT(*) FROM signals GROUP BY company_key").fetchall())
    for r in matched:
        assert r["n_signals"] == by_co.get(r["radar_company_key"], 0)
        assert r["radar_decision"] in memo.DECISIONS
    cov = combined._coverage(conn)
    assert cov["matched"] == len(matched) and cov["entities"] == 215
    assert cov["signals_on_matched_companies"] == sum(by_co.get(k, 0) for k in {r["radar_company_key"] for r in matched})
    assert cov["with_finnish_business_id"] + cov["without_finnish_business_id"] == 215


def test_meta_records_provenance_and_the_team_only_line(built, conn):
    meta = dict(conn.execute("SELECT key, value FROM radar_meta").fetchall())
    for k in ("built_at", "thesis_id", "source_store_path", "git_sha", "ecosystem_source_sha256", "audience", "coverage", "person_guard"):
        assert meta.get(k), k
    assert meta["thesis_id"] == THESIS and meta["source_store_path"] == str(STORE.resolve())
    assert meta["ecosystem_source_sha256"] == _sha(ECO)
    assert "team use only" in meta["audience"].lower() and "person table" in meta["audience"]
    for t in ("radar_companies", "radar_signals", "radar_readiness", "radar_verdicts", "radar_ocean_impact", "radar_briefs"):
        assert meta[f"rows_{t}"] == str(_count(conn, t))
    assert built[1]["counts"]["radar_meta"] == _count(conn, "radar_meta")


def test_the_output_is_one_file_and_passes_integrity_check(built, conn):
    out = built[0]
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert built[1]["files_after_run"] == [out.name]


def test_it_refuses_to_overwrite_its_inputs_and_unknown_theses(tmp_path):
    shas = (_sha(STORE), _sha(ECO))
    with pytest.raises(ValueError, match="read only"):
        combined.run(THESIS, STORE, store_path=STORE, progress=lambda m: None)
    with pytest.raises(ValueError, match="read only"):
        combined.run(THESIS, ECO, store_path=STORE, progress=lambda m: None)
    with pytest.raises(ValueError, match="unknown thesis"):
        combined.run("no_such_thesis", tmp_path / "x.sqlite", store_path=STORE)
    with pytest.raises(ValueError, match="no store"):
        combined.run(THESIS, tmp_path / "x.sqlite", store_path=tmp_path / "missing.sqlite")
    assert (_sha(STORE), _sha(ECO)) == shas and not list(tmp_path.iterdir())


def test_a_failed_guard_leaves_no_file(tmp_path, monkeypatch):
    out = tmp_path / "c.sqlite"
    monkeypatch.setattr(combined, "person_guard", lambda *a: ["radar_signals.detail"])
    with pytest.raises(RuntimeError, match="radar_signals.detail"):
        combined.run(THESIS, out, store_path=STORE, progress=lambda m: None)
    assert list(tmp_path.iterdir()) == []


def test_cli_default_name_second_thesis_and_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RADAR_DATA_DIR", str(SNAP))
    monkeypatch.setattr(combined, "OUT_DIR", tmp_path)
    assert combined.main(["--thesis", "no_such_thesis"]) == 2
    assert combined.main(["--thesis", "health_tech_turku"]) == 0
    out = tmp_path / "health_tech_turku_combined.sqlite"
    assert out.is_file()
    text = capsys.readouterr().out
    assert "join coverage" in text and "team use only" in text
    c = sqlite3.connect(out)
    n = _count(_ro(SNAP / "radar_health_tech_turku.sqlite"), "companies")
    assert _count(c, "radar_companies") == n and _count(c, "entity") == 215


def test_the_ocean_impact_table_has_one_row_per_company_and_reaches_the_view(built, conn):
    assert _count(conn, "radar_ocean_impact") == _count(conn, "radar_companies")
    r = conn.execute("SELECT * FROM radar_ocean_impact WHERE level IS NOT NULL LIMIT 1").fetchone()
    assert r is not None and 1 <= r["level"] <= r["level_max"] == 9 and (r["band"] in ("Low", "Medium", "High") or (r["band"] is None and r["level"] < 3)) and r["area"]
    assert r["confidence"] in ("high", "medium", "low") and r["level_rule"] and r["evidence_json"].startswith("[")
    assert conn.execute("SELECT COUNT(*) FROM radar_ocean_impact WHERE level IS NULL AND (band IS NOT NULL)").fetchone()[0] == 0
    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({combined.VIEW})")]
    assert {"radar_ocean_area", "radar_ocean_level", "radar_ocean_band", "radar_ocean_confidence"} <= set(cols)
    for v in conn.execute(f"SELECT radar_company_key, radar_ocean_level FROM {combined.VIEW} WHERE radar_ocean_level IS NOT NULL LIMIT 20"):
        assert conn.execute("SELECT level FROM radar_ocean_impact WHERE company_key=?", (v["radar_company_key"],)).fetchone()[0] == v["radar_ocean_level"]
