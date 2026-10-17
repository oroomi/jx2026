"""/data page and the guarded refresh, on a temp copy of the real-data snapshot. No network: steps are faked or fail fast."""
import hashlib
import json
import shutil
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import fit, refresh, thesis

SNAP = Path(__file__).resolve().parent.parent / "data" / "snapshot" / "radar_redstone_apelago_blue.sqlite"
pytestmark = pytest.mark.skipif(not SNAP.is_file(), reason="snapshot missing")
T0 = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RADAR_DB", raising=False)
    th = thesis.load(thesis.resolve("redstone_apelago_blue"))
    live = thesis.db_path(th)
    shutil.copy(SNAP, live)
    import app
    return TestClient(app.app), th, live


def sql(live, q, *a):
    c = sqlite3.connect(live)
    try:
        return c.execute(q, a).fetchall()
    finally:
        c.close()


def text(r):
    return r.text


def test_counts_equal_sql(env):
    client, th, live = env
    hidden = {k for k, n in sql(live, "SELECT company_key, name FROM companies") if fit.looks_like_person(n, th)}
    ph = ",".join("?" * len(hidden)) or "''"
    t = text(client.get("/data"))
    for adapter, n, cos in sql(live, f"SELECT adapter, COUNT(*), COUNT(DISTINCT company_key) FROM signals WHERE company_key NOT IN ({ph}) GROUP BY adapter", *hidden):
        assert f"<td>{n}</td><td>{cos}</td>" in t.replace("\n", "").replace("  ", ""), adapter
    total_c = sql(live, "SELECT COUNT(*) FROM companies")[0][0] - len(hidden)
    total_s = sql(live, f"SELECT COUNT(*) FROM signals WHERE company_key NOT IN ({ph})", *hidden)[0][0]
    assert f"{total_c} companies and {total_s} dated records" in t
    assert f"{total_c} rows, page 1 of" in t


def test_person_shaped_names_absent_and_no_eco_tables(env):
    client, th, live = env
    c = sqlite3.connect(live)
    c.execute("CREATE TABLE eco_person (name TEXT)")
    c.execute("INSERT INTO eco_person VALUES ('Fixture Person Eco')")
    c.commit()
    c.close()
    hidden = [n for _, n in sql(live, "SELECT company_key, name FROM companies") if fit.looks_like_person(n, th)]
    assert hidden, "snapshot has person-shaped names to test with"
    seen = ""
    for view in ("companies", "signals"):
        page = 1
        while True:
            r = text(client.get(f"/data?view={view}&page={page}"))
            seen += r
            if "Next</a>" not in r:
                break
            page += 1
    for n in hidden:
        assert n not in seen, n
    assert "Fixture Person Eco" not in seen and "eco_" not in seen


def test_filters_and_paging(env):
    client, _, live = env
    n = sql(live, "SELECT COUNT(*) FROM signals WHERE adapter='cordis'")[0][0]
    t = text(client.get("/data?view=signals&source=cordis"))
    assert f"{n} rows, page 1 of" in t and 'href="https://cordis.europa.eu/' in t
    assert client.get("/data?page=9999").status_code == 200 and client.get("/data?view=nonsense&source=nope").status_code == 200


def fake_ok(n_new=1):
    def runner(name, db_path, thesis_path, timeout=None):
        c = sqlite3.connect(db_path)
        for i in range(n_new):
            c.execute("INSERT OR IGNORE INTO companies (company_key,name,country,group_tag,source_url,fetched_at) VALUES (?,?,?,?,?,?)",
                      (f"9999{i}-1", f"Fixture Fresh {i} Oy", "FI", "feed", "https://example.test/f", "2026-10-17T09:00:00Z"))
        c.commit()
        c.close()
        return {"step": name, "status": "ok", "seconds": 0.1, "counts": {"signals": n_new, "skipped": 2}, "error": None}
    return runner


def test_refresh_swaps_atomically_and_lists_new_companies(env):
    client, th, live = env
    ino = live.stat().st_ino
    ok, _ = refresh.try_start(T0)
    assert ok
    run = refresh.execute(th, now=T0, step_runner=fake_ok(2))
    assert run["swapped"] and run["new_count"] == 2 and run["error"] is None
    assert live.stat().st_ino != ino                      # replaced, not written in place
    assert sql(live, "SELECT COUNT(*) FROM companies WHERE name LIKE 'Fixture Fresh%'")[0][0] == 2
    assert not live.with_name(live.stem + ".refresh.sqlite").exists() and not refresh.lock_path().exists()
    t = text(client.get("/data"))
    assert "+2 new companies since the last refresh" in t and "Fixture Fresh 0 Oy" in t and "/c/99990-1" in t


def test_failed_run_leaves_the_original_untouched(env):
    _, th, live = env
    before = hashlib.sha256(live.read_bytes()).hexdigest()

    def boom(name, db_path, thesis_path, timeout=None):
        c = sqlite3.connect(db_path)
        c.execute("DELETE FROM signals")                   # damage the copy, then fail
        c.commit()
        c.close()
        raise RuntimeError("adapter error (simulated)")
    assert refresh.try_start(T0)[0]
    run = refresh.execute(th, now=T0, step_runner=boom)
    assert not run["swapped"] and "adapter error" in run["error"]
    assert hashlib.sha256(live.read_bytes()).hexdigest() == before
    assert not live.with_name(live.stem + ".refresh.sqlite").exists() and not refresh.lock_path().exists()


def test_all_steps_failing_does_not_swap(env):
    _, th, live = env
    before = hashlib.sha256(live.read_bytes()).hexdigest()

    def failing(name, db_path, thesis_path, timeout=None):
        return {"step": name, "status": "error", "seconds": 0.0, "counts": {}, "error": "boom"}
    assert refresh.try_start(T0)[0]
    run = refresh.execute(th, now=T0, step_runner=failing)
    assert not run["swapped"] and hashlib.sha256(live.read_bytes()).hexdigest() == before


def test_cooldown_and_lock(env):
    client, th, _ = env
    assert refresh.try_start(T0)[0]
    ok, msg = refresh.try_start(T0 + timedelta(seconds=5))
    assert not ok and "already running" in msg                      # locked
    refresh.execute(th, now=T0, step_runner=fake_ok(0))
    ok, msg = refresh.try_start(T0 + timedelta(minutes=5))
    assert not ok and "Next refresh possible at 09:10 UTC" in msg   # cooldown (finished at T0)
    assert refresh.try_start(T0 + timedelta(minutes=11))[0]
    refresh._release()


def test_stale_lock_is_ignored(env):
    refresh.lock_path().write_text(json.dumps({"pid": 1, "since": (T0 - timedelta(hours=2)).isoformat()}))
    assert refresh.lock_holder(T0) is None and refresh.try_start(T0)[0]
    refresh._release()


def test_post_refresh_runs_and_then_shows_cooldown(env, monkeypatch):
    client, th, live = env
    monkeypatch.setenv("REFRESH_ENABLED", "1")
    monkeypatch.setattr(refresh, "run_step", fake_ok(1))
    r = client.post("/data/refresh", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/data?")
    for _ in range(100):
        if refresh.load_state().get("runs", {}).get(th["id"], {}).get("finished_at"):
            break
        time.sleep(0.05)
    assert sql(live, "SELECT COUNT(*) FROM companies WHERE name LIKE 'Fixture Fresh%'")[0][0] == 1
    r2 = client.post("/data/refresh", follow_redirects=True)
    assert "Next refresh possible at" in r2.text and "disabled" in r2.text


def test_unknown_step_fails_fast_in_its_own_process(env):
    _, th, live = env
    res = refresh.run_step("no_such_step", live, th["_path"], timeout=60)
    assert res["status"] == "error" and "unknown refresh step" in res["error"]


def test_step_timeout_is_reported(env, monkeypatch):
    _, th, live = env
    import subprocess

    def slow(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)
    monkeypatch.setattr(subprocess, "run", slow)
    res = refresh.run_step("prh_notices", live, th["_path"], timeout=1)
    assert res["status"] == "timeout"


def test_no_adapters_configured_runs_nothing(env):
    _, th, live = env
    assert refresh.try_start(T0)[0]
    run = refresh.execute(dict(th, refresh_adapters=[]), now=T0, step_runner=fake_ok())
    assert not run["swapped"] and "No refresh_adapters" in run["error"]


def test_thesis_files_name_the_refresh_steps():
    for p in ("config/thesis.yaml", "config/thesis_health_turku.yaml"):
        assert set(thesis.load(p)["refresh_adapters"]) <= set(refresh.STEPS)


def test_prh_recent_uses_the_register_matching(monkeypatch):
    from radar import db
    from radar.adapters import prh
    fx = json.loads((Path(__file__).parent / "fixtures" / "prh_discovery_meri.json").read_text(encoding="utf-8"))
    seen = []

    def fake(params, client=None):
        seen.append(params)
        return (fx if params.get("name") == "meri" else {"totalResults": 0, "companies": []}), False
    monkeypatch.setattr(prh, "fetch", fake)
    c = db.connect(":memory:")
    from datetime import date
    res = refresh.prh_recent(c, {"industry_codes": [{"code": "30110"}], "name_keywords": {"fi": ["meri"]}}, today=date(2026, 10, 16), days=30)
    assert all(p["registrationDateStart"] == "2026-09-16" for p in seen)
    assert res["companies"] == c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    assert all(r[0] >= "2026-09-16" for r in c.execute("SELECT founded FROM companies"))


def test_refresh_is_switched_off_unless_enabled(env, monkeypatch):
    client, th, live = env
    monkeypatch.delenv("REFRESH_ENABLED", raising=False)
    before = hashlib.sha256(live.read_bytes()).hexdigest()
    r = client.post("/data/refresh", follow_redirects=False)
    assert r.status_code == 403 and "Refresh is switched off on this deployment" in r.text
    assert not refresh.lock_path().exists() and hashlib.sha256(live.read_bytes()).hexdigest() == before
    page = client.get("/data").text
    assert "Refresh is switched off on this deployment" in page
    assert '<button type="submit" disabled>Refresh sources</button>' in page
    monkeypatch.setenv("REFRESH_ENABLED", "0")
    assert client.post("/data/refresh", follow_redirects=False).status_code == 403


def test_data_page_renders_for_a_thesis_without_refresh_adapters(env):
    client, _, _ = env
    th = thesis.load(thesis.resolve("baltic_blue"))
    assert th["id"] == "baltic_blue" and not th.get("refresh_adapters")
    assert client.get("/data?thesis=baltic_blue").status_code == 200       # no store for it yet: the empty state
    shutil.copy(SNAP, thesis.db_path(th))                                   # with a store: the full page, refresh section included
    r = client.get("/data?thesis=baltic_blue")
    assert r.status_code == 200 and "no sources (none are set in the sector file)" in r.text
    assert '<button type="submit" disabled>Refresh sources</button>' in r.text
