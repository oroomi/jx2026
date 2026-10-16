import sys
import textwrap

import pytest
from fastapi.testclient import TestClient

from radar import build, db, thesis


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.sqlite")
    import app
    return TestClient(app.app)


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_routes_autodiscovered(client):
    import app
    assert {"home", "method"} <= set(app.LOADED_ROUTES)
    assert client.get("/method").status_code == 200


def test_home_empty_state(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.text.count("no signals yet") == 1
    assert "https://" not in r.text.replace("https://jx.hankintaviikko.fi", "")


def test_method_prints_confidence_rule(client):
    t = client.get("/method").text
    assert "Confidence rule" in t and "never counted in rankings" in t


def test_thesis_load_default():
    th = thesis.load()
    assert th["id"] and th["geography"]["feed_window_days"] == 90


def test_thesis_malformed(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("id: x\ntitle: y\n")
    with pytest.raises(thesis.ThesisError, match="feed_window_days"):
        thesis.load(p)
    p.write_text("- a\n- b\n")
    with pytest.raises(thesis.ThesisError, match="mapping"):
        thesis.load(p)
    with pytest.raises(thesis.ThesisError, match="not found"):
        thesis.load(tmp_path / "nope.yaml")


def test_build_with_no_adapters(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "b.sqlite")
    monkeypatch.setattr(build, "discover", lambda: [])
    assert build.main() == 0
    assert "no adapters" in capsys.readouterr().out


def test_build_isolates_adapter_errors():
    class Bad:
        NAME = "bad"
        def run(self, conn, th): raise RuntimeError("boom")
    class Good:
        NAME = "good"
        def run(self, conn, th): return {"companies": 1}
    import types
    conn = db.connect(":memory:")
    monkey = [("bad", Bad()), ("good", Good())]
    orig = build.discover
    build.discover = lambda: monkey
    try:
        rows = build.build(conn, {})
    finally:
        build.discover = orig
    assert rows[0][1] == "ERROR" and rows[1] == ("good", "ok", "companies=1")
