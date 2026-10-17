"""Fill companies.town from the PRH responses already cached on disk. No network.

    RADAR_DB=/path/to/store_copy.sqlite python3 -m radar.backfill_town [--cache-dir DIR ...] [--dry-run]

Reads every JSON under data/cache/prh and data/cache/prh_intake (or the --cache-dir given), maps businessId -> town with
radar.town.of (the newest record of a business id wins), then sets town and town_source_url on every company in the store
with that y_tunnus. Writes only the two town columns. Run it on a copy of the store, then replace the live file atomically.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from radar import db, town as town_mod

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIRS = [ROOT / "data" / "cache" / "prh", ROOT / "data" / "cache" / "prh_intake"]


def read_cache(dirs: list[Path]) -> tuple[dict[str, tuple[str, str]], dict]:
    """{businessId: (town, kind)} for every cached company record that has a town, plus counts. The newest record (lastModified) of a business id wins."""
    best: dict[str, tuple[tuple[str, bool], tuple[str | None, str | None]]] = {}
    stats = {"files": 0, "unreadable": 0, "records": 0}
    for d in dirs:
        for f in sorted(d.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                stats["unreadable"] += 1
                continue
            stats["files"] += 1
            for c in data.get("companies", []) if isinstance(data, dict) else []:
                bid = (c.get("businessId") or {}).get("value")
                if not bid:
                    continue
                stats["records"] += 1
                found = town_mod.of(c)
                rank = (c.get("lastModified") or "", found[0] is not None)
                if bid not in best or rank >= best[bid][0]:
                    best[bid] = (rank, found)
    stats["business_ids"] = len(best)
    return {bid: found for bid, (_, found) in best.items() if found[0]}, stats


def backfill(conn, towns: dict[str, tuple[str, str]]) -> dict:
    rows = conn.execute("SELECT company_key, y_tunnus, source_url FROM companies WHERE y_tunnus IS NOT NULL").fetchall()
    out = {"with_y_tunnus": len(rows), "updated": 0, "changed": 0, "no_cached_address": 0, "towns": Counter(), "kinds": Counter()}
    for r in rows:
        found = towns.get(r["y_tunnus"])
        if not found:
            out["no_cached_address"] += 1
            continue
        t, kind = found
        out["updated"] += 1
        out["changed"] += town_mod.set_town(conn, r["company_key"], t, town_mod.source_url(r["y_tunnus"], r["source_url"]))
        out["towns"][t] += 1
        out["kinds"][kind] += 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache-dir", action="append", type=Path, help="directory of cached PRH JSON (repeatable; default data/cache/prh and prh_intake)")
    ap.add_argument("--dry-run", action="store_true", help="report only; roll the changes back")
    args = ap.parse_args(argv)
    dirs = args.cache_dir or DEFAULT_DIRS
    towns, cs = read_cache(dirs)
    if not cs["files"]:
        print(f"no cached PRH responses found under {', '.join(map(str, dirs))}; pass --cache-dir", file=sys.stderr)
        return 2
    conn = db.connect()
    print(f"store: {db.DB_PATH}")
    print(f"cache: {cs['files']} files ({cs['unreadable']} unreadable), {cs['records']} records, {cs['business_ids']} business ids, {len(towns)} with a town")
    res = backfill(conn, towns)
    if args.dry_run:
        conn.rollback()
    else:
        conn.commit()
    print(f"companies with a y-tunnus: {res['with_y_tunnus']}")
    print(f"companies updated: {res['updated']} ({res['changed']} changed)" + (" [dry run, rolled back]" if args.dry_run else ""))
    print(f"companies with no cached address: {res['no_cached_address']}")
    print(f"town from visiting address: {res['kinds'][town_mod.VISITING]}, from postal address only: {res['kinds'][town_mod.POSTAL]}")
    print(f"distinct towns: {len(res['towns'])}")
    print("top 10 towns:")
    for t, n in res["towns"].most_common(10):
        print(f"  {t}: {n}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
