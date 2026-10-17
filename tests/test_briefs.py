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


def test_brief_with_too_few_passing_sentences_is_dropped(kelluu):
    exp, th = kelluu
    b = {"company_key": "2902007-2", "sentences": [sent("Kelluu Oy was registered on 2018-03-09.", PRH), sent("It has a strong team.", PRH)]}
    clean, drops = briefs.verify_brief(b, exp, th)
    assert clean is None and any("brief dropped" in d["reason"] for d in drops)
    b["sentences"].append(sent("The record lists a funding round dated 2026-04-14.", exp["signals"][1]["source_url"]))
    clean, drops = briefs.verify_brief(b, exp, th)
    assert clean and len(clean["sentences"]) == 2 and len(drops) == 1


def test_import_round_trip_and_template(snap, kelluu, tmp_path):
    exp, th = kelluu
    inn, out = tmp_path / "in", tmp_path / "out"
    inn.mkdir(), out.mkdir()
    (inn / "2902007-2.json").write_text(json.dumps(exp))
    brief = {"company_key": "2902007-2", "written": "2026-10-17", "sentences": [
        sent("Kelluu Oy was registered on 2018-03-09.", PRH),
        sent("The record shows one EU project that started on 2024-09-01.", CORDIS),
        sent("Kelluu Oy has a strong team and is a market leader.", PRH)]}
    (out / "2902007-2.json").write_text(json.dumps(brief))
    conn = db.connect(thesis.db_path(th))
    res = briefs.run_dir(out, inn, th, conn=conn, log=lambda m: None)
    conn.close()
    assert res["kept"] == 1 and res["dropped_sentences"] == 1
    b = briefs.brief_for("2902007-2", th)
    assert [s["text"] for s in b["sentences"]][0].startswith("Kelluu Oy was registered") and len(b["sentences"]) == 2
    assert b["sentences"][1]["cites"] == [{"n": 2, "url": CORDIS}] and b["written"] == "2026-10-17"
    assert briefs.brief_for("3543918-7", th) is None
    from radar.routes import briefs as _r  # noqa: F401  (registers brief_for)
    from radar.routes.home import templates
    t = templates.env.get_template("company_brief.html")
    with_brief = t.render(c={"company_key": "2902007-2"}, thesis=th)
    assert "What the public record says" in with_brief and 'class="brief-cite"' in with_brief and "checked by code; written 2026-10-17" in with_brief
    none = t.render(c={"company_key": "3543918-7"}, thesis=th)
    assert "No summary yet" in none and "brief-foot" not in none


def test_no_em_dash_in_brief_template_or_module():
    root = Path(__file__).resolve().parent.parent / "radar"
    for p in (root / "briefs.py", root / "templates" / "company_brief.html"):
        assert chr(0x2014) not in p.read_text()
