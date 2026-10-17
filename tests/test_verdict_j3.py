"""The judge's round-3 verdict findings (D65 to D68): a declared member gets PORTFOLIO SUPPORT, never an accelerator place; a High fit
that rests on the industry code alone is capped at Medium; the memo and Aava read one who-to-meet list without a sector-mismatched
pitch session; the page and the home list count the public-record checks with one function. Synthetic companies, plus the snapshot."""
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

from radar import aava, db, emit, matching, memo, store, thesis
from radar.adapters import prh_notices  # noqa: F401  (registers the notice signal types on emit.SIGNAL_TYPES)

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"
TODAY = date(2026, 10, 16)
CODE_ON_LIST = "30110"


def _day(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "j3.sqlite"))
    c = db.connect(tmp_path / "j3.sqlite")
    yield c
    c.close()


def _company(conn, key, name, tag="feed", desc="Fixture activity"):
    emit.upsert_company(conn, company_key=key, name=name, y_tunnus=key, founded=_day(40), country="FI", industry_code=CODE_ON_LIST,
                        industry_desc=desc, group_tag=tag, source_url=f"https://example.test/prh/{key}")
    for typ, ad, dt in (("register_entry", "prh", 40), ("startup_notice", "prh_notices", 30)):
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=_day(dt), source_url=f"https://example.test/{ad}/{key}/{typ}",
                         confidence="high", adapter=ad)
    conn.commit()


def _memo(conn, key):
    return memo.build(conn, thesis.load(), key, today=TODAY.isoformat())


# ---- D65: a declared member is supported, not assessed for entry ------------------------------------------------------------

def test_member_rule_is_data_and_comes_first():
    cfg = memo._cfg(thesis.load())
    assert cfg["members"]["decision"] == "PORTFOLIO SUPPORT" and "PORTFOLIO SUPPORT" in memo.DECISIONS
    bands = {"impact": "High", "business": "Medium", "investment": "Medium", "fit": "High", "technology": "unknown"}
    row, _ = memo.decide(bands, cfg, frozenset({"declared_member", "declared_portfolio"}))
    assert row["decision"] == "PORTFOLIO SUPPORT" and row["kind"] == "member" and "Redstone Blue" in row["relation"]
    row, _ = memo.decide(bands, cfg, frozenset({"own_text"}))
    assert row["decision"] == "ACCELERATOR"  # the same bands without the membership: the team's row 3


def test_declared_portfolio_company_reads_portfolio_support(conn):
    _company(conn, "9300001-1", "Fixture Portfolio Oy", tag="portfolio")
    m = _memo(conn, "9300001-1")
    rec = m["recommendation"]
    assert rec["decision"] == "PORTFOLIO SUPPORT" and rec["note"].startswith("Already in Redstone Blue's portfolio")
    assert "accept into accelerator" not in rec["note"].lower() and rec["table_action"] != "Accept into accelerator and provide mentoring"


def test_cohort_company_names_its_cohort(conn):
    _company(conn, "9300002-1", "Fixture Cohort Oy", tag="cohort")
    rec = _memo(conn, "9300002-1")["recommendation"]
    assert rec["decision"] == "PORTFOLIO SUPPORT" and rec["note"].startswith("Already in A'Pelago's")


def test_member_next_support_never_names_its_own_organisation_or_an_accelerator():
    nxt = {"investors": [], "partners": [{"name": "Fixture Buyer Oy", "kind": "corporate", "source_url": "https://example.test/b"}],
           "funding": [{"name": "Redstone Blue", "kind": "investor vc", "source_url": "https://example.test/r"},
                       {"name": "Fixture Accelerator", "kind": "accelerator incubator", "source_url": "https://example.test/a"},
                       {"name": "Fixture Grant", "kind": "public funder", "source_url": "https://example.test/g"}]}
    rule = memo.member_rule(memo._cfg(thesis.load()), frozenset({"declared_portfolio"}))
    kept = memo.filter_next(nxt, own=rule["own"])
    note, acts = memo.member_support(rule, kept)
    assert "Redstone Blue" not in [r["name"] for r in kept["funding"]]
    assert note == "Already in Redstone Blue's portfolio, and the next support is a pilot with Fixture Buyer Oy and a grant from Fixture Grant"
    assert [a["url"] for a in acts] == ["https://example.test/b", "https://example.test/g"]


def test_aava_says_the_member_sentence(conn):
    _company(conn, "9300003-1", "Fixture Member Oy", tag="portfolio")
    th = thesis.load()
    m = _memo(conn, "9300003-1")
    c = dict(matching.company_context(conn, "9300003-1")["c"])
    g = aava.company_groups(c, [], nxt={}, step=None, memo=m, thesis=th)
    text = " ".join(s["text"] for k in ("brief", "why", "missing") for s in g[k])
    assert "accelerator candidate" not in text and "already in Redstone Blue's portfolio" in text
    assert aava.MEMBER_FIXED in text


# ---- D66: the industry code alone is at most a Medium fit ---------------------------------------------------------------------

def test_code_alone_fit_is_capped_at_medium_and_members_are_excepted(conn):
    _company(conn, "9300004-1", "Fixture Code Oy")
    _company(conn, "9300005-1", "Fixture Declared Oy", tag="portfolio")
    assert _memo(conn, "9300004-1")["levels"]["fit"]["band"] == "Medium"
    assert _memo(conn, "9300005-1")["levels"]["fit"]["band"] == "High"
    spec = thesis.load()["memo"]["bands"]["fit"]
    assert spec["code_alone_band"] == "Medium" and set(spec["code_alone_reasons"]) == {"industry_code", "line_of_business"}


def test_code_alone_cap_says_why(conn):
    _company(conn, "9300006-1", "Fixture Code Two Oy")
    m = _memo(conn, "9300006-1")
    fit_line = next(w["text"] for w in m["why"] if w["text"].startswith("Thesis fit:"))
    assert "the industry code alone gives at most a Medium fit" in fit_line
    assert m["recommendation"]["decision"] == "WATCHLIST" and not m["recommendation"]["fallback_blocked"]


# ---- D67: one who-to-meet list, no sector-mismatched pitch session, one market-evidence record -------------------------------

def test_sector_mismatch_reads_the_declared_sector_in_brackets():
    labels = {"aquaculture and fisheries", "shipbuilding and boats"}
    name = "Fixture E-Pitching Session (energy transition in aquaculture and fisheries)"
    assert memo.sector_mismatch(name, {"shipbuilding and boats"}, labels)
    assert not memo.sector_mismatch(name, {"aquaculture and fisheries"}, labels)
    assert not memo.sector_mismatch("Fixture Programme", {"shipbuilding and boats"}, labels)  # no declared sector: kept


def test_meet_list_puts_the_actions_first_and_stops_at_three():
    nxt = {"investors": [{"name": f"Inv {i}", "score": 50 + i} for i in range(4)], "funding": [{"name": "Grant A", "score": None}], "partners": []}
    out = memo.meet_list(nxt, [{"text": "Point them to Grant A (deadline: not stated)"}])
    assert [r["name"] for r in out] == ["Grant A", "Inv 3", "Inv 2"]


def test_market_gap_reads_the_business_record(conn):
    _company(conn, "9300007-1", "Fixture Customer Oy")
    emit.emit_signal(conn, company_key="9300007-1", signal_type="site_customer", date=_day(10), source_url="https://example.test/site/customer",
                     confidence="medium", adapter="stitcher")
    conn.commit()
    risks = [r["text"] for r in _memo(conn, "9300007-1")["risks"]]
    assert not any(t.startswith("No public market evidence") for t in risks)
    assert any(t.startswith("No public buyer on record yet") for t in risks)


# ---- D68: one count of the public-record checks ------------------------------------------------------------------------------

def test_record_checks_is_one_function_with_six_checks():
    out = memo.record_checks({"register_entry", "site_customer"}, None, [])
    assert len(out) == 6 and [ok for _, ok in out] == [True, False, False, True, False, False]
    assert memo.record_checks(set(), "ocean data", [{"name": "x"}])[4:] == [("a category match for ocean impact", True), ("an investor match", True)]


# ---- the snapshot: the three companies the judge named ------------------------------------------------------------------------

@pytest.fixture()
def snap(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    return thesis.load()


@pytest.mark.parametrize("key,org", [("2902007-2", "Redstone Blue"), ("2962040-6", "Redstone Blue"), ("3166759-6", "A'Pelago")])
def test_judge_named_members_read_portfolio_support(snap, key, org):
    conn = store.open_db(thesis=snap)
    try:
        c = dict(matching.company_context(conn, key)["c"])
        if c["group_tag"] not in ("cohort", "portfolio"):
            pytest.skip("not declared in this snapshot")
        m = memo.build(conn, snap, key, today=TODAY.isoformat())
    finally:
        conn.close()
    rec = m["recommendation"]
    assert rec["decision"] == "PORTFOLIO SUPPORT" and org in rec["note"]
    assert not any(r["name"].startswith(org) for r in m["meet"])
    assert not any("Pitching Session" in r["name"] for r in m["meet"] if "aquaculture" in r["name"].lower()) or key == "3166759-6"
