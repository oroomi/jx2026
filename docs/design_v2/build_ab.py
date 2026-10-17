"""Build directions A and B (jx36) from the snapshot store.

List population: every cohort and portfolio company, plus the feed companies with a stated reason (the app's /api/feed
"main" rows). Per company: the app's /api/company JSON, the fund memo verdict (radar.memo), and the BlueInvest profile
text when one is stored. Nothing is typed by hand.

    python3 docs/design_v2/build_ab.py
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault("RADAR_DATA_DIR", str(ROOT / "data" / "snapshot"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402
from radar import memo, thesis  # noqa: E402

DOSSIER_KEY = "2962040-6"  # Viva Jets Oy (portfolio, electric watercraft)
DB = ROOT / "data" / "snapshot" / "radar_redstone_apelago_blue.sqlite"
COUNTRY = {"FI": "Finland", "SE": "Sweden", "DK": "Denmark", "NO": "Norway", "ES": "Spain", "BG": "Bulgaria", "CH": "Switzerland"}


def blueinvest_text():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute("SELECT company_key, description, url, sector FROM blueinvest_profiles WHERE company_key IS NOT NULL").fetchall()
    return {k: {"text": d, "url": u, "sector": s} for k, d, u, s in rows if d}


def what_it_does(co, bi_row):
    """The card's "what it does" sentence: the BlueInvest profile's first sentence when one is stored, otherwise the
    registered line of business (PRH industry code). Rule-written, never generated."""
    if bi_row:
        return {"text": one_line(bi_row["text"]) + ".", "src": bi_row["url"], "src_label": "BlueInvest profile"}
    if co.get("industry_desc"):
        return {"text": f"{co['industry_desc']} (industry code {co['industry_code']}).",
                "src": co["source_url"], "src_label": "PRH/YTJ register"}
    return None


def one_line(text, limit=110):
    t = " ".join((text or "").split())
    first = t.split(". ")[0].rstrip(".")
    return first if len(first) <= limit else first[: limit - 1].rsplit(" ", 1)[0] + "…"


def main():
    client = TestClient(app)
    th = thesis.load()
    feed = client.get("/api/feed").json()
    keys = [r["company_key"] for r in feed["rows"] if r["strength"] != "weak"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    keys = [k for (k,) in con.execute("SELECT company_key FROM companies WHERE group_tag IN ('cohort','portfolio') ORDER BY name")] + keys
    bi = blueinvest_text()
    rows = []
    for k in keys:
        c = client.get(f"/api/company/{k}").json()
        co = c["company"]
        m = memo.for_template(k, th) or {}
        sigs = c["signals"]
        newest = sigs[0] if sigs else None
        b = bi.get(k)
        line = what_it_does(co, b)
        rows.append({
            "key": k, "name": co["name"], "country": co.get("country") or "", "country_name": COUNTRY.get(co.get("country"), co.get("country")),
            "group": co.get("group_tag"), "founded": co.get("founded"), "y": co.get("y_tunnus"), "reg_src": co.get("source_url"),
            "line": line,
            "newest": {"label": newest["type_label"], "date": newest["date"], "date_label": newest["date_label"],
                       "prec": newest["date_precision"], "src": newest["source_url"], "src_label": newest["source_label"]} if newest else None,
            "n_signals": len(sigs),
            "verdict": (m.get("recommendation") or {}).get("decision"),
            "levels": {d: v.get("level") for d, v in (c.get("readiness") or {}).items() if isinstance(v, dict)},
        })
    tabs = {}
    for r in rows:
        tabs.setdefault(r["country"], 0)
        tabs[r["country"]] += 1
    home = {"rows": rows, "countries": [{"code": k, "name": COUNTRY.get(k, k), "n": n} for k, n in sorted(tabs.items(), key=lambda x: -x[1])],
            "fetched": feed["counts"]["last_fetched"], "window_days": feed["counts"]["window_days"]}
    k = client.get(f"/api/company/{DOSSIER_KEY}").json()
    k["memo"] = memo.for_template(DOSSIER_KEY, th)
    k["blueinvest"] = bi.get(DOSSIER_KEY)
    k["what_it_does"] = what_it_does(k["company"], bi.get(DOSSIER_KEY))
    for name, data in (("a_home", home), ("b_home", home), ("a_company", k), ("b_company", k)):
        src = HERE / "src" / f"{name}.src.html"
        if not src.exists():
            continue
        blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        (HERE / f"{name}.html").write_text(src.read_text(encoding="utf-8").replace("__DATA__", blob), encoding="utf-8")
    from collections import Counter
    print(len(rows), "companies;", Counter(r["verdict"] for r in rows), Counter(r["country"] for r in rows))
    print(sum(1 for r in rows if r["line"] and r["line"]["src_label"] == "BlueInvest profile"), "with BlueInvest text")


if __name__ == "__main__":
    main()
