"""AI brief pipeline (radar/briefs.py): person-free export, code verification, import round trip, template states."""
import json
import re
import shutil
from pathlib import Path

import pytest

from radar import briefs, db, emit, store, thesis
from radar.adapters import ecosystem

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot"
PRH = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId=2902007-2"
CORDIS = "https://cordis.europa.eu/project/id/101157488"


@pytest.fixture()
def snap(tmp_path, monkeypatch):
    if not (SNAP / "radar_redstone_apelago_blue.sqlite").exists():
        pytest.skip("no snapshot")
    for f in SNAP.glob("*.sqlite"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
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
def kelluu(snap):
    conn = store.open_db(thesis=snap)
    exp = briefs.export_one(conn, snap, "2902007-2", today="2026-10-17")
    conn.close()
    return exp, snap


def test_export_has_the_facts_and_every_url(kelluu):
    exp, _ = kelluu
    assert exp["name"] == "Kelluu Oy" and exp["business_id"] == "2902007-2" and exp["founded"] == "2018-03-09"
    assert exp["counts"]["signals"] == len(exp["signals"]) > 5 and exp["memo"]["decision"]
    assert PRH in exp["urls"] and CORDIS in exp["urls"] and all(s["source_url"] in exp["urls"] for s in exp["signals"])


def test_export_is_person_free(snap, tmp_path):
    conn = store.open_db(thesis=snap)
    keys = [r[0] for r in conn.execute("SELECT company_key FROM companies WHERE group_tag IN ('cohort','portfolio')")]
    exps = briefs.export(conn, snap, keys, today="2026-10-17")
    conn.close()
    assert len(exps) == len(keys) > 20
    for e in exps:
        vocab = {w for t in (e["name"], *[r["name"] for v in e["next"].values() for r in v]) for w in briefs._CAP.findall(t)} | briefs.GENERIC
        free = [s.get(k) for s in e["signals"] for k in ("title", "note")] + [r["text"] for r in e["fit_reasons"]]
        assert not any(briefs._words_flagged(t, vocab) for t in free if t), e["company_key"]


def test_export_drops_free_text_that_has_a_name(tmp_path):
    conn = db.connect(tmp_path / "x.sqlite")
    emit.upsert_company(conn, company_key="9300001-1", name="Fixture Brief Oy", source_url="https://example.test/c", y_tunnus="9300001-1", country="FI")
    emit.emit_signal(conn, company_key="9300001-1", signal_type="public_contract", date="2026-05-02", source_url="https://example.test/h1", confidence="high",
                     adapter="hilma", detail="Fixture Buyer Oy: contact Matti Virtanen about the survey (EUR 5,000)")
    emit.emit_signal(conn, company_key="9300001-1", signal_type="public_contract", date="2026-05-03", source_url="https://example.test/h2", confidence="high",
                     adapter="hilma", detail="Fixture Buyer Oy: water sampling service (EUR 6,000)")
    conn.commit()
    exp = briefs.export_one(conn, thesis.load(), "9300001-1", today="2026-10-17")
    by = {s["source_url"]: s for s in exp["signals"]}
    assert by["https://example.test/h1"]["title"] is None                       # the name is left out, the fact stays
    assert "Matti" not in json.dumps(exp, ensure_ascii=False)
    assert by["https://example.test/h2"]["title"] == "water sampling service"
    assert briefs.export_one(conn, thesis.load(), "no-such-key") is None


def sent(text, *cites):
    return {"text": text, "cites": list(cites)}


def test_verify_passes_a_supported_sentence(kelluu):
    exp, th = kelluu
    f = briefs.Facts(exp)
    assert briefs.verify_sentence(sent("Kelluu Oy was registered on 2018-03-09.", PRH), f, th) is None
    assert briefs.verify_sentence(sent("It has five Business Finland decisions and one EU project that started on 2024-09-01.", CORDIS), f, th) is None


@pytest.mark.parametrize("text,cite,reason", [
    ("Kelluu Oy was registered on 2018-03-09.", "https://example.test/not-in-export", "cited url not in the export"),
    ("Kelluu Oy raised EUR 99 000 in total.", PRH, "number not in the export"),
    ("Kelluu Oy was registered on 2017-02-01.", PRH, "date not in the export"),
    ("Kelluu Oy has a strong team.", PRH, "praise without a source title"),
    ("The company was founded by Matti Virtanen.", PRH, "capitalised word not in the export"),
    ("Kelluu Oy was registered on 2018-03-09.", None, "no cited url"),
])
def test_verify_drops_unsupported_sentences(kelluu, text, cite, reason):
    exp, th = kelluu
    why = briefs.verify_sentence(sent(text, *([cite] if cite else [])), briefs.Facts(exp), th)
    assert why and why.startswith(reason)


def slots(exp, **kw):
    sig = {s["type"]: s["source_url"] for s in exp["signals"]}
    base = {"what_it_does": sent("Kelluu Oy is a portfolio company registered on 2018-03-09.", PRH),
            "readiness": sent("Technology, business and investment readiness are all level 4 on the radar's rules.", exp["levels"]["technology"]["url"])}
    base.update(kw)
    return {"company_key": exp["company_key"], "written": "2026-10-17", "slots": base}


def test_brief_slots_pass_fail_and_null(kelluu):
    exp, th = kelluu
    clean, drops = briefs.verify_brief(slots(exp, thesis_fit=sent("It has a strong team.", PRH), whats_missing=None), exp, th)
    assert clean and clean["slots"]["what_it_does"] and clean["slots"]["readiness"] and clean["slots"]["thesis_fit"] is None
    assert clean["slots"]["whats_missing"] is None and drops[0]["slot"] == "thesis_fit"


def test_readiness_numbers_must_match_the_export_levels(kelluu):
    exp, th = kelluu
    lv = {d: exp["levels"][d]["level"] for d in ("technology", "business", "investment")}
    assert lv == {"technology": 4, "business": 4, "investment": 4}
    url = exp["levels"]["technology"]["url"]
    f = briefs.Facts(exp)
    ok = briefs.verify_slot("readiness", sent("Technology level 4, business level 4 and investment level 4.", url), exp, f, th)
    assert ok is None
    bad = briefs.verify_slot("readiness", sent("Technology readiness is level 6 on the radar's rules.", url), exp, f, th)
    assert bad and bad.startswith("level differs from the export")
    stray = briefs.verify_slot("readiness", sent("The company reaches level 9 overall.", url), exp, f, th)
    assert stray and stray.startswith("level differs from the export")


def test_who_to_meet_uses_only_list_names(kelluu):
    exp, th = kelluu
    names = [r for r in exp["next"]["investors"]][:2]
    f = briefs.Facts(exp)
    good = f"{names[0]['name']} and {names[1]['name']} are the first investors on the list."
    assert briefs.verify_slot("who_to_meet", sent(good, names[0]["url"], names[1]["url"]), exp, f, th) is None
    foreign = briefs.verify_slot("who_to_meet", sent(f"{names[0]['name']} and Acme Capital should be met.", names[0]["url"]), exp, f, th)
    assert foreign and ("Acme" in foreign or foreign.startswith("who_to_meet"))
    assert briefs.verify_slot("who_to_meet", sent("Someone should be met.", PRH), exp, f, th).startswith("who_to_meet")
    wrong_url = briefs.verify_slot("who_to_meet", sent(f"{names[0]['name']} is first on the list.", PRH), exp, f, th)
    assert wrong_url and "not a who-comes-next source" in wrong_url


def test_fund_slot_must_match_the_memo_verdict(kelluu):
    exp, th = kelluu
    assert exp["memo"]["decision"] == "ACCELERATOR"  # a declared member reads High fit since D47, so the fallback reaches it
    exp = {**exp, "memo": {**exp["memo"], "decision": "WATCHLIST", "matched": None}}  # the verifier is pinned on a watchlist export here
    f = briefs.Facts(exp)
    assert briefs.verify_slot("what_the_fund_should_do", sent("Keep it on the watchlist until a new public record appears.", PRH), exp, f, th) is None
    assert briefs.verify_slot("what_the_fund_should_do", sent("Start due diligence now.", PRH), exp, f, th)
    assert briefs.verify_slot("what_the_fund_should_do", sent("Meet them this week.", PRH), exp, f, th).startswith("memo verdict")


def test_one_sentence_slots(kelluu):
    exp, th = kelluu
    f = briefs.Facts(exp)
    two = sent("Kelluu Oy was registered on 2018-03-09. It is a portfolio company.", PRH)
    assert briefs.verify_slot("what_it_does", two, exp, f, th).startswith("slot what_it_does")


def test_brief_with_too_few_slots_is_dropped(kelluu):
    exp, th = kelluu
    clean, drops = briefs.verify_brief({"company_key": "2902007-2", "slots": {"what_it_does": sent("Kelluu Oy was registered on 2018-03-09.", PRH)}}, exp, th)
    assert clean is None and any("brief dropped" in d["reason"] for d in drops)


def test_import_round_trip_and_template(snap, kelluu, tmp_path):
    exp, th = kelluu
    inn, out = tmp_path / "in", tmp_path / "out"
    inn.mkdir(), out.mkdir()
    (inn / "2902007-2.json").write_text(json.dumps(exp))
    brief = slots(exp, thesis_fit=sent("Kelluu Oy has a strong team and is a market leader.", PRH))
    (out / "2902007-2.json").write_text(json.dumps(brief))
    conn = db.connect(thesis.db_path(th))
    res = briefs.run_dir(out, inn, th, conn=conn, log=lambda m: None)
    conn.close()
    assert res["kept"] == 1 and res["dropped_slots"] == 1 and res["slots_kept"] == 2
    b = briefs.brief_for("2902007-2", th)
    assert [s["key"] for s in b["slots"]] == list(briefs.SLOT_KEYS) and b["written"] == "2026-10-17"
    by = {s["key"]: s for s in b["slots"]}
    assert by["what_it_does"]["text"].startswith("Kelluu Oy is a portfolio") and by["what_it_does"]["cites"] == [{"n": 1, "url": PRH}]
    assert by["thesis_fit"]["text"] is None
    assert briefs.brief_for("3543918-7", th) is None
    assert briefs.one_liners(th)["2902007-2"].startswith("Kelluu Oy is a portfolio")
    from radar.routes import briefs as _r  # noqa: F401  (registers brief_for)
    from radar.routes.home import templates
    t = templates.env.get_template("company_brief.html")
    html = t.render(c={"company_key": "2902007-2"}, thesis=th)
    assert "What the public record says" in html and html.count('class="brief-row ') == 6 and 'class="brief-cite"' in html
    assert html.count("no public evidence yet") == 4 and "AI summary of the linked public records, checked by code" in html
    none = t.render(c={"company_key": "3543918-7"}, thesis=th)
    assert "No summary yet" in none and "brief-row" not in none


def test_no_em_dash_in_brief_template_or_module():
    root = Path(__file__).resolve().parent.parent / "radar"
    for p in (root / "briefs.py", root / "templates" / "company_brief.html"):
        assert chr(0x2014) not in p.read_text()


# ---- batch 2 rules: the fund slot cites the memo rule, no raw tokens ---------------------------------------------
EXP2 = {"company_key": "9400001-1", "name": "Fixture Two Oy", "levels": {"technology": {"level": None}, "business": {"level": 2}, "investment": {"level": None}},
        "signals": [{"ref": "S1", "type": "register_entry", "date": "2026-01-01", "source_url": "https://example.test/r", "title": None, "note": None}],
        "memo": {"decision": "ACCELERATOR", "matched": "fallback c2, impact implied by sector", "because": "Medium, implied by sector / Low / unknown / High"},
        "next": {"funding": [{"name": "Fixture Studio", "kind": "accelerator", "reason": "r", "url": "https://example.test/s"}]},
        "counts": {"signals": 1}, "urls": ["https://example.test/r", "https://example.test/s"]}


def test_fund_slot_states_the_current_verdict_and_cites_the_memo_rule():
    f = briefs.Facts(EXP2)
    ok = sent("The memo recommends an accelerator under fallback c2, so the fund should consider a place in an accelerator programme.", "https://example.test/r")
    assert briefs.verify_slot("what_the_fund_should_do", ok, EXP2, f) is None
    old = sent("The memo puts it on the watchlist, so the fund should reassess it later.", "https://example.test/r")
    assert briefs.verify_slot("what_the_fund_should_do", old, EXP2, f).startswith("memo verdict ACCELERATOR")
    norule = sent("The memo recommends an accelerator, so the fund should consider a place in an accelerator programme.", "https://example.test/r")
    assert briefs.verify_slot("what_the_fund_should_do", norule, EXP2, f).startswith("memo rule not cited: fallback c2")


@pytest.mark.parametrize("text", ["The record has a first_hire signal.", "It matches caps ['C4'] in the dataset.", "The kw [] list is empty."])
def test_raw_tokens_are_rejected(text):
    why = briefs.verify_sentence(sent(text, "https://example.test/r"), briefs.Facts(EXP2))
    assert why and why.startswith("raw token")
