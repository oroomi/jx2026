"""Build direction C (jx37, the Trading 212 feel on B's structure) from the snapshot store.

Home rows ARE the feed's main-tier rows (the chief's rule for "/"), newest public signal first, each with the fund memo
verdict, the card's "what it does" sentence and the dated signals for its sparkline. Nothing is typed by hand.

    python3 docs/design_v2/build_c.py
"""
import json
import os
import sqlite3
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault("RADAR_DATA_DIR", str(ROOT / "data" / "snapshot"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402
from build_ab import DB, DOSSIER_KEY, blueinvest_text, what_it_does  # noqa: E402
from radar import intake as intake_mod, memo, store, thesis  # noqa: E402

COUNTRIES = [("redstone_apelago_blue", "Finland"), ("baltic_blue", "Baltic")]


def main():
    client = TestClient(app)
    bi = blueinvest_text()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    groups = dict(con.execute("SELECT group_tag, COUNT(*) FROM companies GROUP BY group_tag").fetchall())
    tabs = []
    for tid, label in COUNTRIES:
        r = client.get("/api/feed", params={"thesis": tid})
        feed = r.json() if r.status_code == 200 else {}
        if "rows" not in feed:
            tabs.append({"id": tid, "label": label, "available": False})
            continue
        th = thesis.load(tid) if tid != "redstone_apelago_blue" else thesis.load()
        rows = []
        for f in feed["rows"]:
            if f["strength"] == "weak":
                continue
            c = client.get(f"/api/company/{f['company_key']}", params={"thesis": tid}).json()
            m = memo.for_template(f["company_key"], th) or {}
            rows.append({"key": f["company_key"], "name": f["name"], "line": what_it_does(c["company"], bi.get(f["company_key"])),
                         "verdict": (m.get("recommendation") or {}).get("decision"), "date": f["date"], "label": f["type_label"],
                         "src": f["source_url"], "src_label": f["source_label"],
                         "dates": sorted(s["date"] for s in c["signals"])})
        conn = store.open_db(thesis=th)
        try:
            intake_n = len(intake_mod.tier(conn, th, exclude={x["key"] for x in rows})) if conn is not None else None
        finally:
            if conn is not None:
                conn.close()
        cnt = feed["counts"]
        tabs.append({"id": tid, "label": label, "available": True, "rows": rows, "weak": cnt["weak"], "intake": intake_n,
                     "window_start": cnt["window_start"], "window_end": cnt["window_end"], "fetched": cnt["last_fetched"]})
    home = {"tabs": tabs, "lists": {"cohort": groups.get("cohort", 0), "portfolio": groups.get("portfolio", 0)}}
    k = client.get(f"/api/company/{DOSSIER_KEY}").json()
    k["memo"] = memo.for_template(DOSSIER_KEY, thesis.load())
    k["what_it_does"] = what_it_does(k["company"], bi.get(DOSSIER_KEY))
    k["today"] = tabs[0].get("window_end")
    for name, data in (("c_home", home), ("c_company", k)):
        src = HERE / "src" / f"{name}.src.html"
        if src.exists():
            blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
            (HERE / f"{name}.html").write_text(src.read_text(encoding="utf-8").replace("__DATA__", blob), encoding="utf-8")
    t0 = tabs[0]
    print(t0["label"], len(t0["rows"]), "rows; weak", t0["weak"], "intake", t0["intake"], "; lists", home["lists"],
          "; tabs", [(t["label"], t["available"]) for t in tabs])
    from collections import Counter
    print(Counter(r["verdict"] for r in t0["rows"]))


if __name__ == "__main__":
    main()
