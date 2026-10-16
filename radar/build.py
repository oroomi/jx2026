"""python3 -m radar.build : run every adapter in radar/adapters (modules with NAME and run(conn, thesis))."""
from __future__ import annotations

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


def build(conn, thesis: dict) -> list[tuple[str, str, str]]:
    rows = []
    for name, mod in discover():
        if isinstance(mod, Exception):
            rows.append((name, "ERROR", f"import failed: {mod}"))
            continue
        try:
            res = mod.run(conn, thesis)
            conn.commit()
            rows.append((name, "ok", ", ".join(f"{k}={v}" for k, v in (res or {}).items())))
        except Exception as e:
            conn.rollback()
            rows.append((name, "ERROR", f"{type(e).__name__}: {e}"))
    return rows


def main() -> int:
    th = thesis_mod.load()
    conn = db.connect()
    rows = build(conn, th)
    print(f"thesis: {th['id']}")
    if not rows:
        print("no adapters found in radar/adapters")
    else:
        w = max(len(r[0]) for r in rows)
        print(f"{'adapter'.ljust(w)}  status  counts")
        for name, status, counts in rows:
            print(f"{name.ljust(w)}  {status.ljust(6)}  {counts}")
    n = conn.execute("select count(*) from signals").fetchone()[0]
    print(f"signals in db: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
