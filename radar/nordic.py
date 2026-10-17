"""Shared pieces of the Norwegian and Danish register adapters (radar/adapters/brreg.py, radar/adapters/cvr.py).

A register record is normalised to {id, name, form, registered, founded, code, code_desc, website, url, status}. Two jobs:
  cohort lookup  find each declared non-Finnish cohort or portfolio company in its national register by name (or by the
                 registration number the declared list states); an exact normalised name that matches ONE company is found, anything
                 else is not found, and a name with several or near candidates is ambiguous and lists them (never guessed);
  live window    companies registered in the last 365 days under the thesis codes and keywords (Norway only).
The fetched rows are written as JSON under data/fetched/nordic/ so another machine imports them without network."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import re

from radar import emit, fit as fit_mod, store

ROOT = Path(__file__).resolve().parent.parent
GROUPS = ("cohort", "portfolio")


def fetched_dir() -> Path:
    return Path(os.environ.get("RADAR_NORDIC_DIR") or ROOT / "data" / "fetched" / "nordic")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_SLASH_FORM = re.compile(r"\ba[./]s\b\.?", re.I)


def name_key(name: str) -> str:
    """Comparison key: the radar's folded name with the Danish and Norwegian A/S, A.S. and ApS forms removed too."""
    return store.name_key(_SLASH_FORM.sub("as", name or ""))


def targets(conn: sqlite3.Connection, country: str) -> list[dict]:
    """Declared cohort and portfolio companies of `country` that no Finnish business id identifies."""
    return [dict(r) for r in conn.execute(
        "SELECT company_key, name, group_tag FROM companies WHERE group_tag IN ('cohort','portfolio') AND country=? AND y_tunnus IS NULL ORDER BY name",
        (country,))]


def decide(wanted: str, candidates: list[dict]) -> dict:
    """{status: found|not_found|ambiguous, match, candidates}. Exact normalised name, one company: found. Several exact, or none exact but
    near (one name contains the other, 4 characters or more): ambiguous, candidates listed, nothing chosen. Otherwise not found."""
    wk = name_key(wanted)
    exact = [c for c in candidates if name_key(c["name"]) == wk]
    if len(exact) == 1:
        return {"status": "found", "match": exact[0], "candidates": []}
    if len(exact) > 1:
        return {"status": "ambiguous", "match": None, "candidates": exact}
    near = [c for c in candidates if len(wk) >= 4 and (wk in name_key(c["name"]) or (len(name_key(c["name"])) >= 4 and name_key(c["name"]) in wk))]
    if near:
        return {"status": "ambiguous", "match": None, "candidates": near}
    return {"status": "not_found", "match": None, "candidates": []}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict | None:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def import_cohort(conn: sqlite3.Connection, data: dict, adapter: str, register: str, country: str) -> dict:
    """Store each found cohort match and emit its register_entry. Returns counts. Ambiguous and missing ones store nothing."""
    out = {"found": 0, "not_found": 0, "ambiguous": 0, "blocked": 0, "signals": 0}
    for item in data.get("cohort", []):
        st = item["status"]
        out[st if st in out else "not_found"] += 1
        m = item.get("match")
        if st != "found" or not m:
            continue
        row = conn.execute("SELECT name, group_tag FROM companies WHERE company_key=?", (item["company_key"],)).fetchone()
        if row is None:
            continue
        emit.upsert_company(conn, company_key=item["company_key"], name=row["name"], source_url=m["url"], country=country, founded=m.get("founded"),
                            industry_code=m.get("code"), industry_desc=m.get("code_desc"), group_tag=row["group_tag"], register_status=m.get("status"))
        if m.get("registered"):
            out["signals"] += emit.emit_signal(
                conn, company_key=item["company_key"], signal_type="register_entry", date=m["registered"], source_url=m["url"], confidence="medium",
                adapter=adapter, detail=(f"Registered in {register} on {m['registered']} (organisation number {m['id']}); matched by exact legal name "
                                         f"'{m['name']}' to the declared company '{row['name']}'." + (f" Founded {m['founded']}." if m.get("founded") else "")))
    return out


def import_rows(conn: sqlite3.Connection, thesis: dict, data: dict, adapter: str, register: str, country: str, key_prefix: str) -> dict:
    """Store the live-window companies (a name keyword is medium, a code alone is low, as in the Finnish register adapter)."""
    out = {"companies": 0, "signals": 0, "skipped": 0}
    for r in data.get("rows", []):
        if not r.get("registered"):
            out["skipped"] += 1
            continue
        key = f"{key_prefix}-{r['id']}"
        emit.upsert_company(conn, company_key=key, name=r["name"], source_url=r["url"], country=country, founded=r.get("founded") or r["registered"],
                            industry_code=r.get("code"), industry_desc=r.get("code_desc"), website=r.get("website"), group_tag="feed",
                            register_status=r.get("status"))
        out["companies"] += 1
        why = r["reason"]
        out["signals"] += emit.emit_signal(conn, company_key=key, signal_type="register_entry", date=r["registered"], source_url=r["url"],
                                           confidence=r["confidence"], adapter=adapter,
                                           detail=f"Registered in {register} on {r['registered']}; matched because {why}.")
    return out


def person_or_partner(name: str, thesis: dict) -> bool:
    return fit_mod.looks_like_person(name, thesis) or store.is_partner_org(name)
