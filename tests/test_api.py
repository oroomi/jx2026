"""Read-only JSON API on the committed snapshot stores (data/snapshot): status codes, response shape, sources, read-only, speed."""
import hashlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import earliness, store

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "snapshot"
KELLUU = "2902007-2"
pytestmark = pytest.mark.skipif(not (SNAP / "radar_redstone_apelago_blue.sqlite").is_file(), reason="snapshot store not in this checkout")


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(SNAP))
    monkeypatch.delenv("RADAR_DB", raising=False)
    monkeypatch.delenv("RADAR_THESIS", raising=False)
    import app
    return TestClient(app.app)


def _is_link(u) -> bool:
    return isinstance(u, str) and u.startswith(("http://", "https://"))


def test_index_lists_endpoints_and_theses(client):
    r = client.get("/api")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    d = r.json()
    assert d["read_only"] is True and "redstone_apelago_blue" in d["theses"]
    assert {"/api/companies", "/api/company/{company_key}", "/api/feed", "/api/backtest"} <= {e["path"].split("?")[0] for e in d["endpoints"]}


def test_companies_search_and_list(client):
    d = client.get("/api/companies", params={"q": "kelluu"}).json()
    assert d["thesis"]["id"] == "redstone_apelago_blue"
    assert [c["company_key"] for c in d["companies"]] == [KELLUU]
    c = d["companies"][0]
    assert c["name"] == "Kelluu Oy" and _is_link(c["source_url"]) and c["links"]["page"] == f"/c/{KELLUU}"
    d = client.get("/api/companies", params={"limit": 3}).json()
    assert d["count"] == 3 and d["total"] >= 3
    assert [c["name"] for c in d["companies"]] == sorted((c["name"] for c in d["companies"]))


def test_company_has_facts_sourced_signals_levels_and_next(client):
    d = client.get(f"/api/company/{KELLUU}").json()
    assert d["company"]["y_tunnus"] == KELLUU and d["company"]["founded"] == "2018-03-09"
    assert d["signals"] and all(_is_link(s["source_url"]) and s["confidence"] in ("high", "medium", "low") for s in d["signals"])
    assert {s["signal_type"] for s in d["signals"]} >= {"register_entry", "eu_project"}
    tech = d["readiness"]["technology"]
    assert tech["level"] == 4 and tech["because"] and all(_is_link(e["source_url"]) for e in tech["evidence"])
    assert tech["rules"] and _is_link(tech["framework_url"])
    nxt = d["who_comes_next"]
    assert set(nxt) >= {"investors", "funding", "partners", "rank_rule"}
    for k in ("investors", "funding", "partners"):
        for i, row in enumerate(nxt[k], 1):
            assert row["rank"] == i and row["reason"] and row["name"] and _is_link(row["source_url"])
    ns = d["next_step"]  # the verdict as an action (D46), the same decision the memo states
    assert ns["sentence"] and ns["decision"] == d["verdict"]["decision"] and ns["rule"] and ns["table"]
    assert "not enough public evidence" not in ns["sentence"]
    assert d["connector_slots"]["status"] == "not connected"


def test_unknown_company_is_json_404(client):
    r = client.get("/api/company/name:no-such-company")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert "no company with key" in r.json()["error"]


def test_feed_rows_carry_their_reason(client):
    d = client.get("/api/feed").json()
    assert d["rule"] and d["count"] == len(d["rows"]) == d["counts"]["companies"]
    assert d["rows"], "the snapshot feed has rows"
    for r in d["rows"]:
        assert r["strength"] in ("strong", "weak") and r["why"] and set(r["reasons"]) <= set(store.REASON_IDS)
        assert _is_link(r["source_url"]) and r["links"]["page"] == f"/c/{r['company_key']}"
    dates = [r["date"] for r in d["rows"]]
    assert dates == sorted(dates, reverse=True)


def test_feed_window_and_type(client):
    d = client.get("/api/feed", params={"window": 30}).json()
    assert d["counts"]["window_days"] == 30
    assert all(d["counts"]["window_start"] <= r["date"] <= d["counts"]["window_end"] for r in d["rows"])
    assert len(d["rows"]) <= len(client.get("/api/feed").json()["rows"])
    d = client.get("/api/feed", params={"type": "register_entry"}).json()
    assert all(r["signal_type"] == "register_entry" for r in d["rows"])


def test_bad_parameters_are_json_errors(client):
    r = client.get("/api/feed", params={"thesis": "no_such_thesis"})
    assert r.status_code == 400 and "redstone_apelago_blue" in r.json()["available"]
    assert client.get("/api/feed", params={"type": "made_up"}).status_code == 400
    assert client.get("/api/feed", params={"window": 0}).status_code == 422
    r = client.get("/api/no/such/endpoint")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json") and r.json()["endpoints"]


def test_second_thesis(client):
    d = client.get("/api/feed", params={"thesis": "health_tech_turku"}).json()
    assert d["thesis"]["id"] == "health_tech_turku"


def test_backtest_shape(client):
    d = client.get("/api/backtest").json()
    assert d["total"] == 19 and d["headline"] and d["rule"]
    assert d["earlier"] + d["declared"] + d["later"] + d["none"] == d["total"]
    assert all(r["group"] in earliness.GROUP_ORDER for r in d["rows"])
    assert all(_is_link(r["first_signal"]["source_url"]) for r in d["rows"] if r["first_signal"] and "source_url" in r["first_signal"])


def test_read_only(client):
    files = sorted(SNAP.glob("*.sqlite"))
    before = [hashlib.sha256(f.read_bytes()).hexdigest() for f in files]
    for u in ("/api", "/api/companies?q=oy", f"/api/company/{KELLUU}", "/api/feed", "/api/backtest"):
        assert client.get(u).status_code == 200
    assert client.post("/api/feed").status_code == 405
    assert client.delete(f"/api/company/{KELLUU}").status_code == 405
    assert [hashlib.sha256(f.read_bytes()).hexdigest() for f in files] == before
    assert "access-control-allow-origin" not in client.get("/api/feed", headers={"Origin": "https://example.test"}).headers


def test_each_endpoint_answers_under_500_ms(client):
    for u in ("/api/companies?q=oy", f"/api/company/{KELLUU}", "/api/feed", "/api/backtest"):
        client.get(u)
        best = 9.0
        for _ in range(3):
            t = time.perf_counter()
            assert client.get(u).status_code == 200
            best = min(best, time.perf_counter() - t)
        assert best < 0.5, f"{u} took {best:.3f} s"


# ---- database browser config (deploy/datasette/metadata.yml) --------------------------------------------------------
ECO = ROOT / "data" / "declared" / "ecosystem" / "blue_economy_fi.sqlite"
META = ROOT / "deploy" / "datasette" / "metadata.yml"


def _person_marks(conn) -> list:
    import re
    from tests.people import person_names
    names = person_names(5)
    email = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.I)
    return [lambda v, n=n: n in v for n in names] + [lambda v: "linkedin.com" in v.casefold(), lambda v: bool(email.search(v))]


def _leaks(conn, sql: str, marks, params=()) -> bool:
    return any(isinstance(v, str) and any(m(v) for m in marks) for row in conn.execute(sql, params) for v in row)


@pytest.mark.skipif(not ECO.is_file(), reason="ecosystem dataset not in this checkout")
def test_datasette_hides_every_table_that_names_a_person():
    import sqlite3

    import yaml
    meta = yaml.safe_load(META.read_text(encoding="utf-8"))
    assert meta["allow_sql"] is False
    tables = meta["databases"]["blue_economy_fi"]["tables"]
    assert tables["person"]["allow"] is False and tables["person"]["hidden"] is True
    conn = sqlite3.connect(f"file:{ECO}?mode=ro", uri=True)
    marks = _person_marks(conn)
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'").fetchall():
        if _leaks(conn, f'SELECT * FROM "{t}"', marks):
            assert (tables.get(t) or {}).get("allow") is False, f"{t} holds a person's name, an email or a LinkedIn link but is served"
    for name, q in meta["databases"]["blue_economy_fi"]["queries"].items():
        assert not _leaks(conn, q["sql"], marks, {"company": "Oy"}), f"canned query {name} returns a person's name, email or LinkedIn link"
    for f in sorted(SNAP.glob("radar_*.sqlite")):
        radar = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
        for (t,) in radar.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            assert not _leaks(radar, f'SELECT * FROM "{t}"', marks), f"{f.name}:{t} holds a person's name, email or LinkedIn link"
