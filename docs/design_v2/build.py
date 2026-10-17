"""Build the design v2 prototypes from the snapshot store.

Reads the same JSON the app serves (/api/feed and /api/company/{key}) through FastAPI's
TestClient against data/snapshot, and embeds it into src/*.src.html. No number is typed by hand.

    python3 docs/design_v2/build.py
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault("RADAR_DATA_DIR", str(ROOT / "data" / "snapshot"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402

DOSSIER_KEY = "2902007-2"  # Kelluu Oy


def home_data(client):
    feed = client.get("/api/feed").json()
    counts = feed["counts"]
    main = []
    for r in feed["rows"]:
        if r["strength"] == "weak":
            continue
        c = client.get(f"/api/company/{r['company_key']}").json()
        main.append({
            "key": r["company_key"], "name": r["name"], "why": r["why"], "date": r["date"],
            "type": r["signal_type"], "type_label": r["type_label"], "src": r["source_url"],
            "src_label": r["source_label"], "kinds": list(r["reasons"]), "rule": c["next_step"]["rule"],
            "signals": [{"date": s["date"], "t": s["signal_type"]} for s in c["signals"]],
        })
    start = dt.date.fromisoformat(counts["window_start"])
    end = dt.date.fromisoformat(counts["window_end"])
    weeks, d = [], start
    while d <= end:
        weeks.append({"start": d.isoformat(), "main": 0, "weak": 0})
        d += dt.timedelta(days=7)
    for r in feed["rows"]:
        i = (dt.date.fromisoformat(r["date"]) - start).days // 7
        if 0 <= i < len(weeks):
            weeks[i]["weak" if r["strength"] == "weak" else "main"] += 1
    weak = [{"name": r["name"], "date": r["date"], "key": r["company_key"]}
            for r in feed["rows"] if r["strength"] == "weak"]
    return {"counts": counts, "rule": feed["rule"], "main": main, "weeks": weeks, "weak": weak}


def write(name, data):
    src = (HERE / "src" / f"{name}.src.html").read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    (HERE / f"{name}.html").write_text(src.replace("__DATA__", blob), encoding="utf-8")


def main():
    client = TestClient(app)
    write("home", home_data(client))
    write("company", client.get(f"/api/company/{DOSSIER_KEY}").json())
    print("built home.html and company.html")


if __name__ == "__main__":
    main()
