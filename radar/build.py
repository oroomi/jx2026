"""python3 -m radar.build : run every adapter in radar/adapters (modules with NAME and run(conn, thesis))."""
from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys

from radar import adapters, db, thesis as thesis_mod


def discover() -> list:
    found = []
    for m in sorted(pkgutil.iter_modules(adapters.__path__), key=lambda m: m.name):
        try:
            mod = importlib.import_module(f"radar.adapters.{m.name}")
        except Exception as e:  # reported per adapter, never stops the others
            found.append((m.name, e))
            continue
        if hasattr(mod, "NAME") and callable(getattr(mod, "run", None)):
            found.append((mod.NAME, mod))
    return found


def build(conn, thesis: dict, only: list[str] | None = None) -> list[tuple[str, str, str]]:
    rows = []
    for name, mod in discover():
        if only is not None and name not in only:
            continue
        if isinstance(mod, Exception):
            rows.append((name, "ERROR", f"import failed: {mod}"))
            continue
        try:
            res = mod.run(conn, thesis)
            conn.commit()
            rows.append((name, "ok", ", ".join(f"{k}={v}" for k, v in (res or {}).items() if not isinstance(v, (list, dict)))))
        except Exception as e:
            conn.rollback()
            rows.append((name, "ERROR", f"{type(e).__name__}: {e}"))
    return rows


def _thesis_arg(value: str | None) -> dict:
    """--thesis takes a path to a yaml file or a thesis id from thesis.available()."""
    if not value:
        return thesis_mod.load()
    av = thesis_mod.available()
    if value in av:
        return thesis_mod.load(av[value])
    return thesis_mod.load(value)


def main(argv: list[str] | None = None) -> int:
    """argv=None means no options (the default build); the command line passes sys.argv[1:]."""
    ap = argparse.ArgumentParser(prog="python3 -m radar.build")
    ap.add_argument("--thesis", help="thesis yaml path or thesis id (default: RADAR_THESIS or config/thesis.yaml)")
    ap.add_argument("--adapters", help="comma separated adapter names; default is every adapter")
    args = ap.parse_args(argv or [])
    th = _thesis_arg(args.thesis)
    only = [a.strip() for a in args.adapters.split(",") if a.strip()] if args.adapters else None
    path = thesis_mod.db_path(th)
    conn = db.connect(path)
    rows = build(conn, th, only)
    print(f"thesis: {th['id']}")
    print(f"database: {path}")
    if not rows:
        print("no adapters ran")
    else:
        w = max(len(r[0]) for r in rows)
        print(f"{'adapter'.ljust(w)}  status  counts")
        for name, status, counts in rows:
            print(f"{name.ljust(w)}  {status.ljust(6)}  {counts}")
    n = conn.execute("select count(*) from signals").fetchone()[0]
    print(f"signals in db: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
