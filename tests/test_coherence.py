"""One truth per page (D46 to D51): the impact band is the Ocean Impact ladder's, question 04 and /api/company state the memo's verdict,
Aava never says more evidence would lower a verdict, the home list orders by evidence inside a verdict, stored brief sentences that
contradict the memo are left out, and the raise line never asks for a second source family twice. The page tests read the committed
snapshot like tests/test_ocean_impact.py; the rest are fakes."""
import re
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import aava, briefs, db, home_list, matching, memo, ocean_impact, store, thesis
from radar.adapters import ecosystem

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
VIVA, ARCTIC, PAATTI, KELLUU = "2962040-6", "3166759-6", "3648578-3", "2902007-2"


@pytest.fixture()
def snap(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    th = thesis.load()
    conn = db.connect(thesis.db_path(th))
    try:
        ecosystem.run(conn, th)
        conn.commit()
    except Exception:
        pytest.skip("ecosystem dataset not available")
    conn.close()
    return th


@pytest.fixture()
def home(snap):
    conn = store.open_db(thesis=snap)
    data = home_list.build(conn, snap)
    conn.close()
    return data


def _text(html: str) -> str:
    import html as h
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    return h.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)))


def _memo(th, key):
    conn = store.open_db(thesis=th)
    try:
        return memo.build(conn, th, key)
    finally:
        conn.close()


# ---- 1. one impact truth ---------------------------------------------------------------------------------------------------------
def test_the_impact_band_is_the_ladders_for_every_home_row(snap, home):
    """A ladder band (Medium or High) is the impact band in the decision table; a level with no band or no level stays unknown."""
    conn = store.open_db(thesis=snap)
    seen = set()
    for r in home["rows"]:
        m = memo.build(conn, snap, r["company_key"])
        oi, band = m["ocean_impact"], m["levels"]["impact"]["band"]
        if oi["band"] in ("Medium", "High"):
            assert band == oi["band"], r["name"]
            seen.add("banded")
        else:
            assert band == memo.UNKNOWN, (r["name"], oi["level"], band)
            seen.add("level" if oi["level"] is not None else "none")
    conn.close()
    assert seen >= {"banded", "level", "none"}  # the snapshot holds all three cases


def test_viva_jets_says_one_thing_everywhere(snap):
    from app import app
    c = TestClient(app)
    m = _memo(snap, VIVA)
    assert m["ocean_impact"]["level"] == 5 and m["ocean_impact"]["band"] == "Medium" and m["levels"]["impact"]["band"] == "Medium"
    verdict = m["recommendation"]["decision"]
    page = _text(c.get(f"/c/{VIVA}").text)
    for old in ("Rule used", "not enough public evidence", "impact not yet measured", "Impact not yet measured"):
        assert old not in page, old
    assert f"reads {verdict.lower()}" in page
    head = page.split("Ocean Impact Assessment")[0]
    assert "implied by the sector" not in head and "evidence readiness is medium" in head          # headline and bullets
    assert "Ocean Impact Readiness level 5 of 9 Medium" in page                                    # the ocean block
    assert "Ocean impact Medium Business readiness" in page                                        # the analysts bars
    q4 = page.rsplit("04 What should happen next", 1)[1].strip()
    assert q4.startswith(verdict[:1] + verdict[1:].lower() + ": ") and "Decision used:" in q4
    api = c.get(f"/api/company/{VIVA}").json()
    assert api["verdict"]["decision"] == api["next_step"]["decision"] == verdict
    assert [b["band"] for b in api["verdict"]["bands"]][0] == "Medium"
    ro = api["readiness"]["ocean_impact"]
    assert (ro["level"], ro["band"]) == (5, "Medium") and api["ocean_impact"]["level"] == 5
    assert "not enough public evidence" not in str(api["next_step"])
    script = c.get(f"/c/{VIVA}").text
    spoken = " ".join(s["text"] for s in aava_segments(script))
    assert "level 5 of 9" in spoken and f"verdict is {verdict.lower()}" in spoken


def aava_segments(html: str) -> list[dict]:
    import json
    m = re.search(r'<script type="application/json" id="aava-data">(.*?)</script>', html, re.S)
    d = json.loads(m.group(1))
    groups = d.get("groups", d)
    return [s for g in ("brief", "why", "meet", "next", "missing") for s in groups[g]]


def test_arctic_fry_reads_the_ladder_and_a_declared_member_reads_high_fit(snap):
    m = _memo(snap, ARCTIC)
    assert m["levels"]["fit"]["band"] == "High" and m["levels"]["impact"]["band"] == "Medium" and m["ocean_impact"]["level"] == 5
    assert m["recommendation"]["decision"] == "PORTFOLIO SUPPORT" and m["recommendation"]["note"].startswith("Already in A'Pelago's")   # D65 (was ACCELERATOR, D53)


def test_a_sector_implied_level_stays_unknown_and_the_fallback_gate_still_holds(snap):
    m = _memo(snap, PAATTI)
    assert m["ocean_impact"]["level"] == 1 and m["ocean_impact"]["band"] is None
    assert m["levels"]["impact"]["band"] == memo.UNKNOWN and m["recommendation"]["fallback_blocked"] is False and m["levels"]["fit"]["band"] == "Medium"   # D66: capped, so never reached
    assert m["recommendation"]["decision"] == "WATCHLIST"
    assert any("not yet evidenced beyond the sector" in k["text"] for k in m["risks"]) and not any("No public evidence for ocean impact" in k["text"] for k in m["risks"])
    assert "not yet evidenced" in m["plain_why"][1]["text"] and "unknown" not in m["plain_why"][1]["text"]


def test_next_step_view_states_the_verdict_and_keeps_a_concrete_lead(snap):
    m = _memo(snap, VIVA)
    v = memo.next_step_view(m, {"rule": 5, "sentence": "Watch: not enough public evidence for a next step yet", "source_url": None, "because": "x"}, snap)
    assert v["sentence"].startswith("Portfolio support: ") and "not enough public evidence" not in str(v)   # D65 (Accelerator under D53)
    assert v["table"] and v["table"][0].startswith("Row 1:") and v["decision"] == m["recommendation"]["decision"]
    lead = {"rule": 1, "sentence": "Introduce them to X before 2026-12-01", "source_url": "https://example.test/x", "because": "open call"}
    v2 = memo.next_step_view(m, lead, snap)
    assert v2["concrete"]["sentence"] == lead["sentence"] and v2["sentence"] == v["sentence"]
    assert memo.next_step_view(None, lead, snap) is None


# ---- 2. Aava ---------------------------------------------------------------------------------------------------------------------
def _answers(th, key, memo_):
    conn = store.open_db(thesis=th)
    ctx = matching.company_context(conn, key)
    nxt = matching.who_comes_next(key, th, 5, conn=conn)
    step = matching.next_step(key, th, conn=conn)
    conn.close()
    sigs = ctx["sigs"]
    g = aava.company_groups(ctx["c"], sigs, nxt=nxt, step=step, memo=memo_, thesis=th)
    return {s["q"]: s["text"] for grp in ("brief", "why", "meet", "next", "missing") for s in g[grp]}


def test_question_six_never_says_more_evidence_would_lower_a_verdict_on_the_snapshot(snap, home):
    conn = store.open_db(thesis=snap)
    for r in home["rows"]:
        m = memo.build(conn, snap, r["company_key"])
        a = _answers(snap, r["company_key"], m)
        assert len(a[6]) <= aava.MAX_ANSWER and len(a[3]) <= aava.MAX_ANSWER, r["name"]
        assert not re.search(r"\b(drops?|downgrade|settle it|falls?)\b", a[6]), (r["name"], a[6])
        oi = m.get("ocean_impact") or {}
        if oi.get("evidence"):
            for q in (1, 3, 6):
                assert not re.search(r"evidence (?:yet )?for (?:[a-z ]+, )*(?:[a-z ]+ and )?ocean impact", a[q]), (r["name"], q, a[q])
    conn.close()


def test_question_six_for_a_fallback_company_with_the_ladder_says_what_a_record_would_change(snap):
    """The old what-if read: at medium or low it drops to watchlist, while the page already read Medium (Viva Jets)."""
    m = _memo(snap, KELLUU)
    # D65: the snapshot holds no fallback company now (declared members read PORTFOLIO SUPPORT); tests/test_verdict_j3.py keeps the fallback case
    assert m["recommendation"]["kind"] == "member" and m["recommendation"]["decision"] == "PORTFOLIO SUPPORT"
    q6 = _answers(snap, KELLUU, m)[6]
    assert "drop" not in q6 and "watchlist" not in q6 and aava.MEMBER_FIXED in q6
    assert "no public record names an ocean impact area yet" in _answers(snap, KELLUU, m)[3]
    viva = _answers(snap, VIVA, _memo(snap, VIVA))
    assert "level 5 of 9" in viva[2] and "drop" not in viva[6] and aava.MEMBER_FIXED in viva[6]


def test_question_three_does_not_say_no_evidence_when_the_ladder_has_rows():
    m = {"recommendation": {"decision": "WATCHLIST", "needs": ["Ocean impact", "Investment readiness"], "kind": None, "note": "x",
                            "because_labels": [{"label": "Ocean impact", "band": "unknown"}]},
         "risks": [], "ocean_impact": {"level": 1, "band": None, "evidence": [{"text": "code family"}]}}
    assert aava._gaps(m) == ["ocean impact is only implied by the sector so far", "no evidence yet for investment readiness"]
    m["ocean_impact"] = {"level": None, "band": None, "evidence": []}
    assert aava._gaps(m) == ["no evidence yet for ocean impact and investment readiness"]


# ---- 3. ranking ------------------------------------------------------------------------------------------------------------------
def _expected_key(r):
    conf = {"high": 0, "medium": 1, "low": 2}
    oi = r["ocean"] or {}
    brl = r["criteria"]["brl"]["level"]
    return (home_list.VERDICT_ORDER.index(r["verdict"]), r["group_tag"] not in ("cohort", "portfolio"),
            -(oi.get("level") if oi.get("level") is not None else -1), conf.get(oi.get("confidence"), 3), -(brl if brl is not None else -1),
            -len(r["signals"]), -int(r["latest"].replace("-", "")[:8]) if r["latest"] else 0, r["name"])


def test_inside_a_verdict_the_home_list_orders_by_evidence(home):
    rows = home["rows"]
    assert [_expected_key(r) for r in rows] == sorted(_expected_key(r) for r in rows)
    first = next(r for r in rows if r["verdict"] == "PORTFOLIO SUPPORT")     # D65: the members' verdict; inside it a declared company with High fit comes first
    assert first["group_tag"] in ("cohort", "portfolio") and first["fit"] == "High"
    for verdict in {r["verdict"] for r in rows}:
        grp = [r for r in rows if r["verdict"] == verdict]
        flags = [r["group_tag"] in ("cohort", "portfolio") for r in grp]
        assert flags == sorted(flags, reverse=True), verdict       # declared members come before everyone else in the same verdict
    freight = next(r for r in rows if r["company_key"] == "3657918-1")                    # level 1, low confidence, found three weeks ago
    lvl = lambda r: (r["ocean"] or {}).get("level")  # noqa: E731
    # D66 moved it from ACCELERATOR to WATCHLIST, where non-declared companies precede it only by a ladder level at least as high as its own
    assert rows.index(freight) > 0 and all(r["group_tag"] in ("cohort", "portfolio") or (lvl(r) is not None and lvl(r) >= lvl(freight))
                                          for r in rows[:rows.index(freight)] if r["verdict"] == freight["verdict"])


def test_the_top_fits_group_keeps_the_same_order(home):
    fit = next(g for g in home["groups"] if g[0] == "fit")[2]
    allrows = home["rows"]
    assert [r["company_key"] for r in fit] == [r["company_key"] for r in allrows if r in fit]
    assert any(r["group_tag"] in ("cohort", "portfolio") for r in fit[:5])


def test_every_declared_member_reads_high_fit_and_aquaculture_0322_is_a_listed_code(home):
    th = thesis.load()
    assert th["memo"]["bands"]["fit"]["declared_member_band"] == "High"
    assert {"03210", "03220"} <= {str(c["code"]) for c in th["industry_codes"]}
    assert all(r["fit"] == "High" for r in home["rows"] if r["group_tag"] in ("cohort", "portfolio"))


# ---- 4. stored brief sentences ---------------------------------------------------------------------------------------------------
def _now(th, **over):
    rec = {"decision": "WATCHLIST", "kind": None, "because_labels": [{"label": "Ocean impact", "band": "Medium"}, {"label": "Business readiness", "band": "Medium"},
                                                                     {"label": "Investment readiness", "band": "unknown"}, {"label": "Thesis fit", "band": "High"}]}
    rec.update(over)
    return briefs._memo_now({"recommendation": rec, "levels": {"technology": {"band": "unknown"}}}, th)


def test_stale_brief_sentences_are_dropped_and_rule_ids_never_print():
    th = thesis.load()
    now = _now(th)
    fund = ("The memo recommends an accelerator under fallback c2 (ocean impact Medium (implied by the sector), business readiness Medium, "
            "investment readiness Medium, thesis fit High), so the fund should consider a place for it in an accelerator programme.")
    assert briefs.current_text(fund, "what_the_fund_should_do", now) is None                      # names accelerator, the memo says watchlist
    right = "The memo puts it on the watchlist under row 7 (ocean impact Medium, business readiness Medium, thesis fit High), so the fund should reassess it."
    kept = briefs.current_text(right, "what_the_fund_should_do", now)
    assert kept and "row 7" not in kept and "watchlist" in kept                                  # right verdict and bands: kept, the id is out
    assert briefs.current_text("It is a declared portfolio company, and the memo reads thesis fit as Medium.", "thesis_fit", now) is None
    assert briefs.current_text("It is a declared portfolio company, and the memo reads thesis fit as High.", "thesis_fit", now)
    assert briefs.current_text("Business readiness is unknown and investment readiness is unknown.", "readiness", now) is None
    assert briefs.current_text("Technology readiness is level 4; ocean impact reads Medium (implied by the sector).", "readiness", now) is None
    assert briefs.current_text("Gaps on the record: no public evidence for ocean impact.", "whats_missing", now) is None
    two = "The memo puts it on the watchlist. The memo reads thesis fit as Low."
    assert briefs.current_text(two, "what_the_fund_should_do", now) == "The memo puts it on the watchlist."   # sentence by sentence
    assert briefs.current_text("Meet Hatch Blue, an accelerator and incubator.", "who_to_meet", now)          # a programme called accelerator is no verdict
    assert briefs.current_text("It is covered by rule c2 of the table.", "whats_missing", None) is None       # an id left in the text is dropped, memo or not


def test_a_fallback_verdict_keeps_the_implied_sentence_and_drops_the_evidenced_one():
    th = thesis.load()
    now = _now(th, decision="ACCELERATOR", kind="fallback",
               because_labels=[{"label": "Ocean impact", "band": "Medium, implied by sector"}, {"label": "Business readiness", "band": "Medium"},
                               {"label": "Investment readiness", "band": "Medium"}, {"label": "Thesis fit", "band": "High"}])
    assert briefs.current_text("The ocean impact reads Medium (implied by the sector).", "readiness", now)
    assert briefs.current_text("The ocean impact reads Medium.", "readiness", now) is None


def test_the_company_page_leaves_out_a_stale_stored_slot_and_prints_no_rule_id(snap):
    from app import app
    conn = db.connect(thesis.db_path(snap))
    fund = ("The memo recommends an accelerator under fallback c2 (ocean impact Medium, business readiness Low, investment readiness unknown, "
            "thesis fit High), so the fund should consider a place for it in an accelerator programme.")
    slots = {"what_it_does": {"text": "Paattikiiltoon Oy is a company registered on 2026-08-20.", "cites": [f"{briefs.PRH if hasattr(briefs, 'PRH') else 'https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId='}{PAATTI}"]},
             "thesis_fit": {"text": "The registered industry is on the thesis list; the memo reads thesis fit as Medium.", "cites": ["https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=" + PAATTI]},
             "what_the_fund_should_do": {"text": fund, "cites": ["https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=" + PAATTI]},
             "readiness": None, "who_to_meet": None, "whats_missing": None}
    briefs.store_brief(conn, {"company_key": PAATTI, "written": "2026-10-17", "slots": slots})
    conn.commit()
    conn.close()
    page = _text(TestClient(app).get(f"/c/{PAATTI}").text)
    box = page[page.index("What the public record says"):]
    box = box[:box.index("Next steps") if "Next steps" in box else 1500]
    assert "registered on 2026-08-20" in box and "thesis fit as Medium" in box
    assert "accelerator" not in box and "fallback c2" not in box and "What the fund should do" not in box
    assert "fallback c2" not in page and "under fallback" not in page


# ---- 5. the Baltic ladder and the sector's own label -----------------------------------------------------------------------------
def test_the_baltic_ladder_is_the_blue_ladder_with_no_band_below_level_three():
    blue, baltic = thesis.load(), thesis.load("config/thesis_baltic_blue.yaml")
    assert baltic["impact_readiness"]["bands"] == blue["impact_readiness"]["bands"] == {"evidenced_min": 3, "low_max": 2, "high_min": 8}
    for key in ("levels", "areas", "scalability", "declared_research", "level_max"):
        assert baltic["impact_readiness"][key] == blue["impact_readiness"][key], key
    cfg = baltic["impact_readiness"]
    assert [ocean_impact._band(n, cfg) for n in (1, 2, 3, 7, 8, 9)] == [None, None, "Medium", "Medium", "High", "High"]


def test_a_baltic_row_with_a_sector_implied_level_is_not_low(snap):
    baltic = thesis.load("config/thesis_baltic_blue.yaml")
    conn = store.open_db(thesis=snap)
    m = memo.build(conn, baltic, PAATTI)
    conn.close()
    assert m["ocean_impact"]["level"] == 1 and m["ocean_impact"]["band"] is None
    crit, facets = home_list.criteria(m, {"fw": {"category": {}, "trl": {"level": None}, "brl": {"level": None}, "irl": {"level": None}},
                                          "c": {"country": "FI", "founded": None, "group_tag": "feed"}, "sigs": []}, {}, baltic,
                                      __import__("datetime").date(2026, 10, 17))
    assert crit["impact"]["band"] is None and crit["impact"]["text"] == home_list.GAP and facets["impact"] == [home_list.GAP]


def test_the_health_thesis_prints_its_own_impact_label(tmp_path, monkeypatch):
    if not (SNAP / "radar_health_tech_turku.sqlite").exists():
        pytest.skip("no snapshot")
    shutil.copy(SNAP / "radar_health_tech_turku.sqlite", tmp_path / "radar_health_tech_turku.sqlite")
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    from app import app
    c = sqlite3.connect(tmp_path / "radar_health_tech_turku.sqlite")
    key = c.execute("SELECT company_key FROM companies ORDER BY company_key LIMIT 1").fetchone()[0]
    c.close()
    page = _text(TestClient(app).get(f"/c/{key}?thesis=health_tech_turku").text)
    assert "ocean impact" not in page.lower() and "Clinical impact" in page


# ---- 6. the raise line -----------------------------------------------------------------------------------------------------------
def test_the_raise_line_names_the_next_record_when_two_families_are_already_on_file(snap):
    m = _memo(snap, VIVA)
    oi = m["ocean_impact"]
    assert oi["level"] == 5 and "2 independent source families agree" in oi["confidence_reason"]
    assert "second independent source family" not in oi["raise"] and "second source family" not in oi["raise"]
    assert oi["raise"].startswith("Rung 6 needs a record")


def test_the_raise_line_still_asks_for_a_second_family_when_only_one_is_on_file():
    cfg = thesis.load()["impact_readiness"]
    rec = [{"family": "prh", "kind": "code"}]
    one = [{"family": "prh", "kind": "programme"}]
    assert ocean_impact._raise(5, cfg, rec, one, None) == "A second independent source family that names the same area."
    two = [{"family": "ecosystem", "kind": "programme"}]
    assert ocean_impact._raise(5, cfg, rec, two, None).startswith("Rung 6 needs a record")
    assert ocean_impact._raise(5, cfg, rec + [{"family": "cordis", "kind": "own_text"}], [], None) == "A listing on a blue programme or portfolio page."


def test_the_matchmakers_light_verdict_is_the_memos_for_every_home_row(snap, home):
    """The company page's 'On the <verdict> path' line and the memo headline must name the same verdict (the light verdict calls memo._impact)."""
    from radar import matchmaker
    conn = store.open_db(thesis=snap)
    for r in home["rows"]:
        m = memo.build(conn, snap, r["company_key"])
        v = matchmaker._verdict(conn, snap, r["company_key"])
        assert v["decision"] == m["recommendation"]["decision"], r["name"]   # D75: one engine, rule e included (it reads the technology band)
        assert v["bands"]["technology"] == m["levels"]["technology"]["band"], r["name"]
        assert v["bands"]["impact"] == m["levels"]["impact"]["band"], r["name"]
    conn.close()
    from app import app
    page = _text(TestClient(app).get(f"/c/{VIVA}").text)
    assert "On the portfolio support path" in page and "On the watchlist path" not in page   # D65 (accelerator path under D53)
