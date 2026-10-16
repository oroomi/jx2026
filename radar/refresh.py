"""Refresh the radar store from the web app (the /data page button). No LLM, no keys, no new data sources.

Safety, all enforced here:
  one run at a time     a lock file under the data directory (stale after LOCK_STALE_SECONDS or when its process is gone)
  cooldown              COOLDOWN_SECONDS after the previous run finished (shown on the page)
  never in place        the run works on a COPY of the thesis store; the copy replaces the live file with os.replace only when
                        every step has finished and PRAGMA quick_check on the copy says ok. A failed run deletes the copy.
  bounded steps         each step runs in its own process with a timeout (rows it committed before the stop are kept, they are whole); adapters keep their own rate limit (1 request per
                        1-2 s) and reuse cached responses under data/cache/
Which steps run is the thesis key refresh_adapters (names from STEPS). CLI used by the runner: python3 -m radar.refresh --step NAME --db PATH
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from radar import db as db_mod, fit, thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
COOLDOWN_SECONDS = 600
LOCK_STALE_SECONDS = 1800
STEP_TIMEOUT_SECONDS = {"prh_notices": 420, "prh_recent": 240}
DEFAULT_TIMEOUT = 300
RECENT_DAYS = 7
MAX_RECENT_REQUESTS = 120
MAX_NEW_LISTED = 200
RESULT_TAG = "RESULT_JSON "


# ---- steps (run inside the step process) ----
def prh_recent(conn: sqlite3.Connection, thesis: dict, today: date | None = None, days: int = RECENT_DAYS) -> dict:
    """New PRH/YTJ registrations of the last `days` days whose industry code or legal-name keyword is in the thesis.
    Same matching and confidence as the register adapter (radar/adapters/prh.py), only a shorter window."""
    from radar.adapters import prh
    today = today or date.today()
    start = (today - timedelta(days=days)).isoformat()
    window = {"registrationDateStart": start, "registrationDateEnd": today.isoformat()}
    codes = {str(c["code"]) for c in thesis.get("industry_codes", [])}
    kws = prh.thesis_keywords(thesis)
    stats = {"discovered": 0, "signals": 0, "samples": [], "examined": 0, "skipped": 0}
    seen: set[str] = set()
    requests = 0
    for q in [{"mainBusinessLine": c} for c in sorted(codes)] + [{"name": k} for k in kws]:
        page = 1
        while requests < MAX_RECENT_REQUESTS:
            params = {**q, **window, **({"page": page} if page > 1 else {})}
            data, _ = prh.fetch(params)
            requests += 1
            comps = data.get("companies", [])
            for c in comps:
                bid = c["businessId"]["value"]
                if bid in seen:
                    continue
                seen.add(bid)
                stats["examined"] += 1
                prh._consider(conn, c, codes, kws, start, stats)
            if len(comps) < prh.PAGE_SIZE or page * prh.PAGE_SIZE >= data.get("totalResults", 0):
                break
            page += 1
        conn.commit()  # each query is complete on its own, so a step stopped by its timeout leaves sound partial rows
    return {"companies": stats["discovered"], "signals": stats["signals"], "skipped": stats["examined"] - stats["discovered"],
            "requests": requests}


def _step_prh_notices(conn, thesis) -> dict:
    from radar.adapters import prh_notices
    res = prh_notices.run(conn, thesis)
    return {k: v for k, v in res.items() if isinstance(v, (int, float, str))}


def _step_prh_recent(conn, thesis) -> dict:
    return prh_recent(conn, thesis)


STEPS = {"prh_notices": _step_prh_notices, "prh_recent": _step_prh_recent}


def _step_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.refresh")
    ap.add_argument("--step", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--thesis", default=None)
    a = ap.parse_args(argv)
    if a.step not in STEPS:
        print(f"unknown refresh step {a.step!r}", file=sys.stderr)
        return 2
    conn = db_mod.connect(a.db)
    try:
        res = STEPS[a.step](conn, thesis_mod.load(a.thesis))
        conn.commit()
    finally:
        conn.close()
    print(RESULT_TAG + json.dumps(res))
    return 0


def run_step(name: str, db_path: Path, thesis_path: str, timeout: int | None = None) -> dict:
    """Run one step in its own process. Always returns {step, status ok|error|timeout, seconds, counts, error}."""
    timeout = timeout or STEP_TIMEOUT_SECONDS.get(name, DEFAULT_TIMEOUT)
    t0 = time.monotonic()
    out = {"step": name, "status": "ok", "seconds": 0.0, "counts": {}, "error": None}
    try:
        p = subprocess.run([sys.executable, "-m", "radar.refresh", "--step", name, "--db", str(db_path), "--thesis", thesis_path],
                           cwd=ROOT, capture_output=True, text=True, timeout=timeout, env={**os.environ})
        if p.returncode != 0:
            out.update(status="error", error=(p.stderr.strip().splitlines() or [f"exit code {p.returncode}"])[-1][:300])
        else:
            line = next((ln for ln in reversed(p.stdout.splitlines()) if ln.startswith(RESULT_TAG)), None)
            out["counts"] = json.loads(line[len(RESULT_TAG):]) if line else {}
    except subprocess.TimeoutExpired:
        out.update(status="timeout", error=f"stopped after {timeout} s")
    except Exception as e:  # never raise into the page
        out.update(status="error", error=f"{type(e).__name__}: {e}"[:300])
    out["seconds"] = round(time.monotonic() - t0, 1)
    return out


# ---- state, lock, cooldown ----
def _dir() -> Path:
    d = thesis_mod.data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path() -> Path:
    return _dir() / "refresh_state.json"


def lock_path() -> Path:
    return _dir() / "refresh.lock"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load_state() -> dict:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"last_finished_at": None, "runs": {}}


def _save_state(state: dict) -> None:
    tmp = state_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, state_path())


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def lock_holder(now: datetime | None = None) -> dict | None:
    """The live lock {pid, since}, or None when there is none or it is stale (old, or its process is gone)."""
    now = now or _now()
    try:
        info = json.loads(lock_path().read_text(encoding="utf-8"))
        since = datetime.fromisoformat(info["since"])
    except (OSError, ValueError, KeyError):
        return None if not lock_path().exists() else {"pid": 0, "since": now.isoformat()}
    if (now - since).total_seconds() > LOCK_STALE_SECONDS or not _pid_alive(int(info.get("pid", 0))):
        return None
    return info


def cooldown_until(now: datetime | None = None) -> datetime | None:
    fin = load_state().get("last_finished_at")
    if not fin:
        return None
    until = datetime.fromisoformat(fin) + timedelta(seconds=COOLDOWN_SECONDS)
    return until if until > (now or _now()) else None


def status(now: datetime | None = None) -> dict:
    now = now or _now()
    holder = lock_holder(now)
    until = cooldown_until(now)
    return {"running": holder is not None, "cooldown_until": until, "can_start": holder is None and until is None}


def try_start(now: datetime | None = None) -> tuple[bool, str]:
    """Take the global lock if no run is active and the cooldown is over. The caller must then call execute()."""
    now = now or _now()
    if lock_holder(now) is not None:
        return False, "A refresh is already running."
    until = cooldown_until(now)
    if until is not None:
        return False, f"Next refresh possible at {until.strftime('%H:%M')} UTC."
    try:
        lock_path().unlink()  # a stale lock
    except FileNotFoundError:
        pass
    try:
        fd = os.open(lock_path(), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False, "A refresh is already running."
    with os.fdopen(fd, "w") as f:
        json.dump({"pid": os.getpid(), "since": now.isoformat()}, f)
    return True, "started"


def _release() -> None:
    try:
        lock_path().unlink()
    except FileNotFoundError:
        pass


# ---- the run ----
def _keys(path) -> dict[str, str]:
    c = sqlite3.connect(str(path))
    try:
        return {r[0]: r[1] for r in c.execute("SELECT company_key, name FROM companies")}
    finally:
        c.close()


def _copy_store(live: Path, copy: Path) -> None:
    for suffix in ("", "-journal", "-wal", "-shm"):
        Path(str(copy) + suffix).unlink(missing_ok=True)
    if live.is_file():
        src, dst = sqlite3.connect(f"file:{live}?mode=ro", uri=True), sqlite3.connect(str(copy))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    conn = db_mod.connect(copy)  # creates an empty store or adds tables a newer schema has
    conn.close()


def _quick_check(path: Path, expect_companies: int) -> str | None:
    """None when the copy is sound, else the reason it is not."""
    try:
        c = sqlite3.connect(str(path))
        try:
            res = c.execute("PRAGMA quick_check").fetchone()[0]
            if res != "ok":
                return f"quick_check said {res}"
            n = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        finally:
            c.close()
    except sqlite3.Error as e:
        return f"{type(e).__name__}: {e}"
    if n < expect_companies:
        return f"the copy has {n} companies, fewer than the {expect_companies} it started with"
    return None


def execute(th: dict, *, now: datetime | None = None, step_runner=None) -> dict:
    """Run the configured steps on a copy and swap it in when sound. Call only after try_start() returned ok. Releases the lock."""
    runner = step_runner or run_step
    started = now or _now()
    live = thesis_mod.db_path(th)
    copy = live.with_name(live.stem + ".refresh.sqlite")
    names = [str(n) for n in (th.get("refresh_adapters") or [])]
    run = {"thesis": th["id"], "started_at": started.isoformat(), "finished_at": None, "steps": [], "swapped": False,
           "error": None, "new_companies": [], "new_count": 0, "configured": names}
    try:
        live.parent.mkdir(parents=True, exist_ok=True)
        _copy_store(live, copy)
        before = _keys(copy)
        for n in names:
            run["steps"].append(runner(n, copy, th["_path"]))
        problem = _quick_check(copy, len(before))
        if not names:
            run["error"] = "No refresh_adapters are configured in the sector file; nothing was run."
        elif problem:
            run["error"] = f"The refreshed copy was not used: {problem}."
        elif all(s["status"] == "error" for s in run["steps"]):
            run["error"] = "Every step failed; the store was left as it was."
        else:
            after = _keys(copy)
            os.replace(copy, live)
            run["swapped"] = True
            new = [(k, v) for k, v in after.items() if k not in before and not fit.looks_like_person(v, th)]
            run["new_count"] = len(new)
            run["new_companies"] = [{"company_key": k, "name": v} for k, v in sorted(new, key=lambda kv: kv[1].casefold())[:MAX_NEW_LISTED]]
    except Exception as e:
        run["error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(str(copy) + suffix).unlink(missing_ok=True)
        fin = _now() if now is None else now + timedelta(seconds=sum(s.get("seconds", 0) for s in run["steps"]))
        run["finished_at"] = fin.isoformat()
        state = load_state()
        state["last_finished_at"] = run["finished_at"]
        state.setdefault("runs", {})[th["id"]] = run
        _save_state(state)
        _release()
    return run


def start_in_background(th: dict, now: datetime | None = None) -> tuple[bool, str]:
    ok, msg = try_start(now)
    if ok:
        threading.Thread(target=execute, args=(th,), kwargs={"now": None}, daemon=True).start()
    return ok, msg


if __name__ == "__main__":
    raise SystemExit(_step_main(sys.argv[1:]))
