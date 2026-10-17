"""One verdict everywhere (PROJECT_RULES D75 to D79): the company page, the match pages and the home list name the same verdict from one
engine; a company that is not a startup on the thesis' own rule cannot be an accelerator candidate and is never offered to an investor or
an accelerator; a public contract sets business readiness, never technology readiness; the register's line-of-business label is
code-level evidence; and the page names a rule by what it says. Synthetic companies only, plus the committed snapshot."""
from __future__ import annotations

import html
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import aava, briefs, db, emit, frameworks, home_list, matchmaker, matchmaker_orgs, memo, store, thesis
from radar.adapters import prh_notices  # noqa: F401  (registers the notice signal types on emit.SIGNAL_TYPES)

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
TODAY = date(2026, 10, 16)
CODE_ON_LIST = "30110"      # ship building: on the thesis list
CODE_OFF_LIST = "42910"     # construction of water projects: off the list; the register's label holds 'water'


def _day(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "v.sqlite"))
    c = db.connect(tmp_path / "v.sqlite")
    yield c
    c.close()


def _company(conn, key, name, *, code=CODE_ON_LIST, desc="Fixture activity", tag="feed", founded_days=400, extra=(), trl=None):
    """A register entry and a PRH startup notice, plus `extra` = (signal_type, adapter, {field: text} or None) records; `trl` adds a
    BlueInvest profile that states that TRL (the only way a technology level can reach High once contracts set none, D77)."""
    emit.upsert_company(conn, company_key=key, name=name, y_tunnus=key, founded=_day(founded_days), country="FI", industry_code=code,
                        industry_desc=desc, group_tag=tag, source_url=f"https://example.test/prh/{key}")
    for typ, ad, dt in (("register_entry", "prh", 40), ("startup_notice", "prh_notices", 30)):
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=_day(dt), source_url=f"https://example.test/{ad}/{key}/{typ}",
                         confidence="high", adapter=ad)
    for i, (typ, ad, text) in enumerate(extra):
        url = f"https://example.test/{ad}/{key}/{typ}/{i}"
        text = dict(text or {})                       # the module constants are shared: never change them
        detail = text.pop("detail", None)
        emit.emit_signal(conn, company_key=key, signal_type=typ, date=_day(20 + i), source_url=url, confidence="medium", adapter=ad, detail=detail)
        sid = conn.execute("SELECT id FROM signals WHERE source_url=?", (url,)).fetchone()[0]
        for field, t in (text or {}).items():
            conn.execute("INSERT INTO signal_text (signal_id, field, text) VALUES (?,?,?)", (sid, field, t))
    if trl is not None:
        conn.execute("INSERT INTO blueinvest_profiles (profile_id, company_key, title, company_name, country, trl, sector, description, url, listed_date, fetched_at) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (f"p-{key}", key, name, name, "Finland", trl, "maritime", "A fixture profile.",
                                                         f"https://example.test/blueinvest/{key}", None, "2026-10-16T00:00:00Z"))
    conn.commit()


PROJECT = ("eu_project", "cordis", {"objective": "A study of the sea and its fish."})       # the source's own text: a High fit reason
CONTRACT = ("public_contract", "hilma", {"detail": "Fixture Agency: Merialueen kunnostus (EUR 10,000)"})


def _memo(conn, key, th=None):
    return memo.build(conn, th or thesis.load(), key, today=TODAY.isoformat())


# ---- D75: one engine --------------------------------------------------------------------------------------------------------

def test_rule_e_is_reachable_by_the_match_engine_and_both_engines_agree(conn):
    """The matchmaker read the decision table before it set the technology band, so a company that the page called a partner
    introduction (rule e: technology High) was an accelerator on every match page."""
    _company(conn, "9500001-0", "Tech Ready Oy", trl=8, extra=[CONTRACT])
    th = thesis.load()
    m = _memo(conn, "9500001-0", th)
    v = matchmaker._verdict(conn, th, "9500001-0", TODAY)
    assert m["recommendation"]["decision"] == "PARTNER INTRODUCTION" and m["recommendation"]["kind"] == "rule"
    assert v["decision"] == "PARTNER INTRODUCTION" and v["bands"]["technology"] == "High"
    head = matchmaker.match_company("9500001-0", th, conn=conn, today=TODAY)["company"]
    assert head["verdict"] == "PARTNER INTRODUCTION"
    assert head["meets"] == [th["matching"]["kinds"]["cluster"]["label"]]          # the partner-introduction path meets clusters only


def test_verdict_of_is_the_one_engine_behind_the_memo(conn):
    _company(conn, "9500002-9", "Sea Project Oy", extra=[PROJECT])
    th = thesis.load()
    v = memo.verdict_of(conn, th, "9500002-9", today=TODAY)
    m = _memo(conn, "9500002-9", th)
    assert v["decision"] == m["recommendation"]["decision"] == "ACCELERATOR"
    assert set(v["bands"]) == {"impact", "business", "investment", "fit", "technology"}
    assert memo.verdict_of(conn, th, "no-such-key") is None


# ---- D76: the startup cut ----------------------------------------------------------------------------------------------------

def test_not_startup_reads_the_age_cut_from_the_thesis_file():
    th = thesis.load()
    cut = th["geography"]["stage_max_company_age_years"]
    young = {"name": "Young Fixture Oy", "founded": _day(int(365.25 * cut) - 30), "group_tag": "feed"}
    old = {"name": "Old Fixture Oy", "founded": _day(int(365.25 * cut) + 30), "group_tag": "feed"}
    assert memo.not_startup(young, th, TODAY, {}) is None
    assert memo.not_startup(old, th, TODAY, {}) == f"founded in {old['founded'][:4]}, more than {cut} years ago"
    assert memo.not_startup({**old, "founded": old["founded"][:4]}, th, TODAY, {})          # a year-only date reads as 1 January
    assert memo.not_startup({**old, "founded": None}, th, TODAY, {}) is None                # no date on record: empty is not old
    for tag in ("cohort", "portfolio"):                                                    # a declared member is a startup by declaration
        assert memo.not_startup({**old, "group_tag": tag}, th, TODAY, {}) is None
    wide = {**th, "geography": {**th["geography"], "stage_max_company_age_years": 50}}
    assert memo.not_startup(old, wide, TODAY, {}) is None                                  # the cut is the sector file's, not the code's


def test_a_counterpart_organisation_is_not_a_startup():
    th = thesis.load()
    index = matchmaker_orgs.counterpart_index(th)
    assert index.get(matchmaker_orgs.okey("Rauma Marine Constructions Oy")) == "corporate"   # corporates_clients.csv and the dataset
    young = {"name": "Rauma Marine Constructions Oy", "founded": _day(100), "group_tag": "feed"}
    assert memo.not_startup(young, th, TODAY) == "listed as a counterpart organisation, a corporate or public buyer"
    assert memo.not_startup({**young, "name": "Unlisted Fixture Oy"}, th, TODAY) is None


def test_decide_replaces_only_a_startup_only_verdict():
    cfg = memo._cfg(thesis.load())
    assert cfg["stage_cut"]["verdicts"] == ["ACCELERATOR"] and cfg["stage_cut"]["decision"] == "WATCHLIST"
    accel = {"impact": "unknown", "business": "Medium", "investment": "unknown", "fit": "High", "technology": "unknown"}
    row, _ = memo.decide(accel, cfg, {"own_text"}, "founded in 2014, more than 5 years ago")
    assert row["kind"] == "stage" and row["decision"] == "WATCHLIST" and row["cut_decision"] == "ACCELERATOR"
    assert row["text"] == "not a startup (founded in 2014, more than 5 years ago)"
    assert memo.decide(accel, cfg, {"own_text"})[0]["decision"] == "ACCELERATOR"            # a startup keeps the table's verdict
    partner = dict(accel, technology="High")
    assert memo.decide(partner, cfg, set(), "founded in 2014, more than 5 years ago")[0]["decision"] == "PARTNER INTRODUCTION"
    member = memo.decide(accel, cfg, {"declared_member", "declared_portfolio"}, "anything")[0]
    assert member["kind"] == "member"                                                       # pass 0 is never cut


def test_an_old_company_reads_watchlist_and_says_why_on_every_surface(conn):
    _company(conn, "9500003-8", "Old Sea Project Oy", founded_days=365 * 12, extra=[PROJECT])
    th = thesis.load()
    m = _memo(conn, "9500003-8", th)
    rec = m["recommendation"]
    year = _day(365 * 12)[:4]
    assert rec["decision"] == "WATCHLIST" and rec["kind"] == "stage" and rec["cut_decision"] == "ACCELERATOR"
    assert rec["note"].startswith(f"Not a startup on the thesis' rule (founded in {year}, more than 5 years ago)")
    assert m["plain_why"][0]["text"].startswith("Not a startup on the thesis' rule") and m["plain_why"][0]["url"]
    ns = memo.next_step_view(m, None, th)
    assert ns["decision"] == "WATCHLIST" and ns["because"].startswith("Not a startup") and ns["rule"].startswith("the startup cut: ")
    assert any(line.startswith("Startup cut (after the table)") and "5 years" in line for line in ns["table"])
    assert matchmaker._verdict(conn, th, "9500003-8", TODAY)["decision"] == "WATCHLIST"
    wi = aava.what_if(m, th)                                     # no hypothetical band makes it an accelerator: the cut holds in the what-if
    assert wi is not None and "ACCELERATOR" not in {d for opts in wi["single"].values() for d in opts.values()}
    young = "9500004-7"
    _company(conn, young, "Young Sea Project Oy", founded_days=400, extra=[PROJECT])
    assert _memo(conn, young, th)["recommendation"]["decision"] == "ACCELERATOR"


def test_an_old_company_is_offered_no_investor_or_accelerator_and_none_is_offered_it(conn):
    _company(conn, "9500005-6", "Old Sea Project Oy", founded_days=365 * 12, extra=[PROJECT])
    _company(conn, "9500006-5", "Young Sea Project Oy", founded_days=400, extra=[PROJECT])
    th = thesis.load()
    cfg = th["matching"]
    kinds = set(cfg["startup_kinds"])
    assert kinds == {"investor", "accelerator"}
    res = matchmaker.match_company("9500005-6", th, conn=conn, today=TODAY, limit=50)
    assert res["company"]["startup"] is False and res["company"]["not_startup"].startswith("founded in")
    assert not {r["kind"] for r in res["counterparts"]} & kinds
    labels = {cfg["kinds"][k]["label"] for k in kinds}
    assert not set(res["company"]["meets"]) & labels
    young = matchmaker.match_company("9500006-5", th, conn=conn, today=TODAY, limit=50)
    assert young["company"]["startup"] is True
    reg = matchmaker_orgs.registry(conn, th)
    for org in [o for o in reg["orgs"] if o["kind"] in kinds][:12]:
        r = matchmaker.match_org(org["id"], th, conn=conn, today=TODAY, limit=1000)
        assert "9500005-6" not in {s["key"] for s in r["startups"]}, org["id"]
        assert r["not_startups"] >= 1 or r["org"]["closed_note"], org["id"]



def test_an_empty_investor_page_counts_startups_only(conn):
    # the empty-state count ("N of the M startups pass its topic and geography filters") leaves out the companies the cut removes
    _company(conn, "9500008-3", "Old Sea Code Oy", founded_days=365 * 12)
    _company(conn, "9500009-1", "Young Sea Code Oy", founded_days=400)       # code only: WATCHLIST, on no investor's path
    th = thesis.load()
    kinds = set(th["matching"]["startup_kinds"])
    seen = 0
    for org in [o for o in matchmaker_orgs.registry(conn, th)["orgs"] if o["kind"] in kinds]:
        r = matchmaker.match_org(org["id"], th, conn=conn, today=TODAY, limit=1000)
        m = re.search(r"of the ([\d,]+) startups", r["org"]["empty_reason"] or "")
        if m:
            seen += 1
            assert m.group(1) == "1" and r["not_startups"] == 1, (org["id"], r["org"]["empty_reason"])
    assert seen


# ---- D81: a stored brief sentence that states a level the page no longer prints is left out ------------------------------------

def test_a_stored_brief_sentence_with_a_level_the_page_no_longer_prints_is_dropped():
    th = thesis.load()
    page = {"recommendation": {"decision": "WATCHLIST", "kind": None, "because_labels": [
        {"label": "Ocean impact", "band": "unknown"}, {"label": "Business readiness", "band": "Medium"},
        {"label": "Investment readiness", "band": "unknown"}, {"label": "Thesis fit", "band": "Medium"}]},
        "levels": {"technology": {"band": "unknown"}}}
    now = briefs._memo_now(page, th)
    old = "On the radar's rules technology readiness is level 7 and business readiness is level 6, while investment readiness has no level."
    assert briefs.stale_reason(old, "readiness", now) == "names technology readiness level 7, the memo now says unknown"
    assert briefs.stale_reason("On the radar's rules business readiness is level 6.", "readiness", now) is None
    assert briefs.stale_reason("Business readiness is level 2 on the rules.", "readiness", now).startswith("names business readiness level 2")
    page["levels"]["technology"]["band"] = "Medium"
    assert briefs.stale_reason("On the radar's rules technology readiness is level 4.", "readiness", briefs._memo_now(page, th)) is None

# ---- D77: a public contract sets business readiness, never TRL -------------------------------------------------------------

def test_a_public_contract_sets_brl_and_no_trl():
    assert not any("public_contract" in (test or ()) for _, _, test in frameworks.TRL_MAP if isinstance(test, tuple))
    assert "public_contract" not in frameworks.DIM_SOURCES["Tech"]
    sig = {"signal_type": "public_contract", "adapter": "hilma", "detail": "Buyer: dredging works", "id": 1, "date": "2026-07-20",
           "evidence": {"url": "https://example.test/h"}}
    fw = frameworks.assess({"industry_desc": "", "source_url": None}, [sig])
    assert fw["brl"]["level"] == 6 and fw["trl"]["level"] is None
    for path in thesis.available().values():
        tech = (thesis.load(path).get("readiness") or {}).get("technology") or {}
        assert "public_contract" not in (tech.get("source_classes") or []), path


# ---- D78: the line-of-business label is code-level evidence ----------------------------------------------------------------

def test_the_line_of_business_alone_or_with_the_code_is_capped_and_the_gate_does_not_count_it(conn):
    th = thesis.load()
    for path in thesis.available().values():                     # D66 holds in every sector, so the rule every page prints is true
        fit = thesis.load(path)["memo"]["bands"]["fit"]
        assert fit.get("code_alone_band") == "Medium" and set(fit.get("code_alone_reasons")) == {"industry_code", "line_of_business"}, path
    assert "line_of_business" not in th["memo"]["decisions"]["fallback"]["requires_any"]
    _company(conn, "9500007-4", "Plain Works Oy", code=CODE_OFF_LIST, desc="Construction of water projects")
    m = _memo(conn, "9500007-4", th)
    assert m["levels"]["fit"]["band"] == "Medium" and m["recommendation"]["decision"] == "WATCHLIST"
    _company(conn, "9500008-3", "Plain Yard Oy", code=CODE_ON_LIST, desc="Building of ships and floating structures in water")
    assert _memo(conn, "9500008-3", th)["levels"]["fit"]["band"] == "Medium"


def test_the_fit_line_names_the_reason_that_sets_the_band(conn):
    """A High fit whose first stored reason is the line of business must not read as if the line of business gave it."""
    _company(conn, "9500009-2", "Plain Works Oy", code=CODE_OFF_LIST, desc="Construction of water projects", extra=[PROJECT])
    m = _memo(conn, "9500009-2")
    assert m["levels"]["fit"]["band"] == "High"
    line = next(w["text"] for w in m["why"] if w["text"].startswith("Thesis fit:"))
    assert line.startswith("Thesis fit: The eu project text contains") and line.endswith("; 1 more reason.")
    assert m["plain_why"][0]["text"].startswith("Thesis fit is high: the eu project text contains")


# ---- D79: no rule letter, a true count, the path of the verdict -------------------------------------------------------------

def test_a_condition_rule_is_named_by_what_it_says():
    cfg = memo._cfg(thesis.load())
    b = {"impact": "unknown", "business": "Medium", "investment": "unknown", "fit": "Medium", "technology": "High"}
    row, _ = memo.decide(b, cfg)
    assert row["text"] == "the rule for technology readiness High and business readiness Low or Medium"
    rec = {"kind": "rule", "matched": row["text"]}
    assert memo.rule_label(rec) == "the decision table's condition rule for technology readiness High and business readiness Low or Medium"
    assert not re.search(r"\brule [a-g]\b", memo.rule_label(rec))


def _visible(text: str) -> str:
    t = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))


@pytest.fixture()
def site(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    c = db.connect(tmp_path / "radar_redstone_apelago_blue.sqlite")
    _company(c, "9500010-6", "Tech Ready Oy", trl=8, extra=[CONTRACT])                  # PARTNER INTRODUCTION by rule e
    _company(c, "9500011-4", "Old Sea Project Oy", founded_days=365 * 12, extra=[PROJECT])  # cut by age
    c.close()
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    monkeypatch.delenv("RADAR_THESIS", raising=False)
    import app
    return TestClient(app.app)


def test_the_company_page_says_the_rule_its_path_and_a_true_count(site):
    t = _visible(site.get("/c/9500010-6").text)
    assert "Partner introduction" in t
    assert not re.search(r"\brule [a-g]\b", t), re.search(r".{60}\brule [a-g]\b.{60}", t)
    assert "On the partner introduction path this startup meets" in t and "accelerator path" not in t
    m = re.search(r"(\d+) counterparts? pass(?:es)? the filters(; the (\w+) with the most reasons)?", t)
    assert m, "the Next steps count line"
    shown = len(re.findall(r'class="mn-item"', site.get("/c/9500010-6").text))
    if m.group(2):
        assert m.group(3) == {1: "one", 2: "two", 3: "three"}[shown] and int(m.group(1)) > shown
    else:
        assert int(m.group(1)) == shown
    old = _visible(site.get("/c/9500011-4").text)
    assert re.search(r"Old Sea Project Oy reads watchlist\s*: not a startup on the thesis' rule \(founded in \d{4}, more than 5 years ago\)", old)
    assert "this company meets" in old and "no investor or accelerator is offered to it" in old


def test_the_match_engine_agrees_with_the_memo_for_every_home_row(site):
    th = thesis.load()
    conn = store.open_db(thesis=th)
    try:
        rows = home_list.build(conn, th)["rows"]
        for r in rows:
            m = memo.build(conn, th, r["company_key"])
            v = matchmaker._verdict(conn, th, r["company_key"])
            assert v["decision"] == m["recommendation"]["decision"] == r["verdict"], r["name"]
            assert v["bands"]["technology"] == m["levels"]["technology"]["band"], r["name"]
    finally:
        conn.close()


# ---- D80: a public contract's title is the buyer's words: a Medium fit ----------------------------------------------------

def test_a_contract_title_alone_gives_a_medium_fit_and_the_row_stays_strong(conn):
    """The shape of the dredging contractor: off-list code, a register label with 'water', and a Hilma title with a thesis word."""
    th = thesis.load()
    for path in thesis.available().values():
        assert thesis.load(path)["memo"]["bands"]["fit"].get("buyer_text_types") == ["public_contract"], path
    _company(conn, "9500012-2", "Plain Works Oy", code=CODE_OFF_LIST, desc="Construction of water projects", extra=[CONTRACT])
    m = _memo(conn, "9500012-2", th)
    assert m["levels"]["fit"]["band"] == "Medium" and m["recommendation"]["decision"] == "WATCHLIST"
    ctx = memo.matching.company_context(conn, "9500012-2")
    own = [s for s in ctx["sigs"] if s["signal_type"] in th["feed_signal_types"]]
    ex = store.explain({**ctx["c"], **own[0]}, own[1:], th, store.source_texts(conn, own))
    assert ex["strength"] == "strong" and "own_text" in ex["reasons"]          # the feed rule (A5) is unchanged: still a main-list row


def test_a_contract_title_beside_a_listed_code_or_a_project_text_still_gives_high(conn):
    th = thesis.load()
    _company(conn, "9500013-0", "Plain Yard Oy", code=CODE_ON_LIST, extra=[CONTRACT])          # code on the list + a buyer's title
    assert _memo(conn, "9500013-0", th)["levels"]["fit"]["band"] == "High"
    _company(conn, "9500014-9", "Plain Works Two Oy", code=CODE_OFF_LIST, desc="Construction of water projects", extra=[CONTRACT, PROJECT])
    m = _memo(conn, "9500014-9", th)
    assert m["levels"]["fit"]["band"] == "High"                                              # the company's own project text
    assert next(w["text"] for w in m["why"] if w["text"].startswith("Thesis fit:")).startswith("Thesis fit: The ")
