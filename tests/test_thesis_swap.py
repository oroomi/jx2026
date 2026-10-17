import re

import pytest
from fastapi.testclient import TestClient

from radar import build, db, store, thesis
from tests.fixtures import thesis_swap_fixture as fx

DEFAULT_ID = "redstone_apelago_blue"
HEALTH_ID = "health_tech_turku"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("RADAR_DB", raising=False)
    monkeypatch.delenv("RADAR_THESIS", raising=False)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    fx.build(tmp_path / f"radar_{DEFAULT_ID}.sqlite", ["Synthetic Default One", "Synthetic Default Two", "Synthetic Default Three"], "d")
    fx.build(tmp_path / f"radar_{HEALTH_ID}.sqlite", ["Synthetic Health One"], "h")
    import app
    return TestClient(app.app)


def names(html):
    return re.findall(r'class="co" href="/c/[^"]+">([^<]+)<', html)


def test_swap_changes_rows_and_counts(client):
    d = client.get("/")
    h = client.get(f"/?thesis={HEALTH_ID}")
    assert d.status_code == h.status_code == 200
    assert len(names(d.text)) == 3 and names(h.text) == ["Synthetic Health One"]
    assert "3 companies" in d.text and "1 companies" in h.text


def test_cookie_keeps_choice(client):
    r = client.get(f"/?thesis={HEALTH_ID}")
    assert "radar_thesis=" + HEALTH_ID in r.headers["set-cookie"]
    assert "samesite=lax" in r.headers["set-cookie"].lower()
    nxt = client.get("/")
    assert names(nxt.text) == ["Synthetic Health One"]
    assert client.get(f"/?thesis={DEFAULT_ID}").text.count('class="feed-row') == 3


@pytest.mark.parametrize("bad", ["../../etc/passwd", "", "x" * 10000, "redstone_apelago_blue%00", "nope"])
def test_junk_falls_back_to_default(client, bad):
    r = client.get("/", params={"thesis": bad})
    assert r.status_code == 200
    assert len(names(r.text)) == 3
    assert "set-cookie" not in r.headers
    c = TestClient(client.app, cookies={"radar_thesis": bad.replace("\x00", "")})
    assert len(names(c.get("/").text)) == 3


def test_available_skips_malformed(tmp_path, monkeypatch, caplog):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "thesis_ok.yaml").write_text((thesis.ROOT / "config" / "thesis.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (cfg / "thesis_bad.yaml").write_text("id: [unclosed", encoding="utf-8")
    monkeypatch.setattr(thesis, "ROOT", tmp_path)
    with caplog.at_level("WARNING", logger="radar.thesis"):
        av = thesis.available()
    assert list(av) == [DEFAULT_ID]
    assert "thesis_bad.yaml" in caplog.text


def test_resolve_only_known_ids():
    av = thesis.available()
    assert {DEFAULT_ID, HEALTH_ID} <= set(av)
    assert thesis.resolve(HEALTH_ID) == av[HEALTH_ID]
    assert thesis.resolve("../config/thesis_health_turku") == thesis.default_path()
    assert thesis.resolve(None) == thesis.default_path()


def test_db_path_sanitises_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    assert thesis.db_path({"id": "../Evil Id/x"}) == tmp_path / "radar_evilidx.sqlite"
    monkeypatch.setenv("RADAR_DB", str(tmp_path / "forced.sqlite"))
    assert thesis.db_path(thesis.load()) == tmp_path / "forced.sqlite"
    assert thesis.db_path({"id": HEALTH_ID}) == tmp_path / f"radar_{HEALTH_ID}.sqlite"


def test_build_runs_only_listed_adapters(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    ran = []

    class A:
        NAME = "a"
        def run(self, conn, th): ran.append("a"); return {"companies": 1}
    class B:
        NAME = "b"
        def run(self, conn, th): ran.append("b"); return {"companies": 2}
    monkeypatch.setattr(build, "discover", lambda: [("a", A()), ("b", B())])
    assert build.main(["--thesis", HEALTH_ID, "--adapters", "b"]) == 0
    out = capsys.readouterr().out
    assert ran == ["b"]
    assert HEALTH_ID in out and f"radar_{HEALTH_ID}.sqlite" in out and "companies=2" in out
    assert (tmp_path / f"radar_{HEALTH_ID}.sqlite").is_file()


def test_method_page(client):
    t = client.get(f"/method?thesis={HEALTH_ID}").text
    assert "Health technology" in t
    assert "Confidence rule" in t and store.rule_text(thesis.load(thesis.resolve(HEALTH_ID))) in t
    assert "connector slot: not connected, no data shown" in t and "LinkedIn" in t
    assert "Business Finland funding export" in t and "not loaded in this build" in t
    assert "cohort_portfolio_companies.csv" not in t and "Cohort and portfolio company list" in t


def test_nav_has_radar_entry(client):
    t = client.get("/").text
    assert 'href="/method"' in t
    assert 'href="/radar"' in t
    assert "thesis-select" not in t and "<select" not in t           # no header switcher (D33): the sector is a filter group on the home list ...
    assert 'aria-label="Sector"' in t and f'href="/?thesis={HEALTH_ID}"' in t   # ... and plain links when there is no list to filter yet


def test_missing_db_gives_empty_state(tmp_path, monkeypatch):
    monkeypatch.delenv("RADAR_DB", raising=False)
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    import app
    t = TestClient(app.app).get(f"/?thesis={HEALTH_ID}").text
    assert "no signals yet for Health technology" in t
    assert "python3 -m radar.build --thesis" in t and "thesis_health_turku.yaml" in t
