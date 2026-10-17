"""Matchmaking, counterpart side: the organisations a startup can meet and what each of them wants.

Each organisation gets a demand profile in two parts, kept apart so the page can say which one a reason rests on:
  declared  its own words: thesis or focus text, stages, geography, ticket, programme window and deadline, from the declared lists
            (investors.csv, programmes_grants.csv, corporates_clients.csv), the ecosystem dataset's entity rows and the thesis file's
            programme windows;
  revealed  the companies it has chosen: its declared cohort or portfolio (cohort_portfolio_companies.csv, the dataset's portfolio,
            investor and dated round rows), joined to the companies in our store.
An organisation with no declared text says so: its demand is then revealed from its portfolio only.
Organisations only. The dataset's people table is never read, and a round's counterparty is used only when it names a listed organisation."""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path

from radar import earliness, fit as fit_mod, matching, matchtext
from radar.store import name_key as fold

ROOT = Path(__file__).resolve().parent.parent
_CACHE: dict = {}
TEXT_FIELDS = ("inv_thesis", "description", "working_on_now", "need_pilots_customers", "need_partners")
ECO_TYPES = ("accelerator_incubator", "investor_vc", "investor_corporate", "investor_angel", "public_funder", "cluster_network", "corporate", "port")


def okey(name: str) -> str:
    """Folded organisation key: the name before a bracket or colon, legal-form words and punctuation removed."""
    return fold(re.split(r"\s*[(:]", name or "", maxsplit=1)[0])


def display_name(name: str) -> str:
    base = re.split(r"\s*\(", name or "", maxsplit=1)[0].strip()
    return base or name


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", display_name(name)).encode("ascii", "ignore").decode().lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48] or "org"


def _num(v) -> float | None:
    try:
        return float(str(v).strip()) if str(v or "").strip() else None
    except ValueError:
        return None


def _new(name: str, kind: str, source: str) -> dict:
    return {"id": None, "name": display_name(name), "full_name": name, "okey": okey(name), "kind": kind, "sources": [source], "types": [],
            "eco_id": None, "url": None, "parts": [], "stage_text": None, "stages": None, "geo_text": None, "ticket": None,
            "trl_window": None, "age_limit": None, "deadline": None, "amount": None, "caps": [], "status": None, "confidence": None,
            "members": {}, "declared_total": 0, "parent": None, "programme": False, "need": []}


def _merge_field(org: dict, key: str, value) -> None:
    if value not in (None, "", []) and org.get(key) in (None, "", []):
        org[key] = value


def _http(*urls) -> str | None:
    return next((u.strip() for u in urls if u and str(u).strip().startswith("http")), None)


def _kind(cfg: dict, typ: str | None) -> str | None:
    return (cfg["kind_by_type"] or {}).get((typ or "").strip())


def _read(cfg: dict, thesis: dict) -> list[dict]:
    """Every counterpart row from the declared lists, the dataset and the thesis windows, merged by organisation key."""
    m = thesis.get("matching") or {}
    orgs: dict[str, dict] = {}

    def get(name: str, kind: str, source: str) -> dict:
        k = okey(name)
        if k in orgs:
            o = orgs[k]
            if source not in o["sources"]:
                o["sources"].append(source)
            return o
        orgs[k] = _new(name, kind, source)
        return orgs[k]

    for r in matching._read_csv(m.get("investors")):
        kind = _kind(cfg, r.get("type"))
        if not kind or not r.get("name"):
            continue
        o = get(r["name"], kind, "investors.csv")
        o["types"].append(r["type"])
        o["parts"].append(r.get("thesis_keywords") or "")
        _merge_field(o, "stage_text", r.get("stage"))
        _merge_field(o, "geo_text", r.get("geography"))
        lo, hi = _num(r.get("ticket_eur_min")), _num(r.get("ticket_eur_max"))
        if lo is not None or hi is not None:
            o["ticket"] = {"min": lo, "max": hi}
        _merge_field(o, "url", _http(r.get("source_url"), r.get("website"), r.get("portfolio_url")))

    eco = matching._eco_db()
    if eco is not None:
        types = [t for t in ECO_TYPES if t in cfg["kind_by_type"]]
        eco_rows = [r for r in eco.execute(f"SELECT * FROM entity WHERE entity_type IN ({','.join('?' * len(types))})", types)
                    if (r["status"] or "active") != "defunct"]
        caps: dict[str, list[str]] = {}
        words: dict[str, list[str]] = {}
        for eid, code in eco.execute("SELECT entity_id, code FROM entity_capability"):
            caps.setdefault(eid, []).append(code)
        for eid, w in eco.execute("SELECT entity_id, keyword FROM entity_keyword UNION ALL SELECT entity_id, segment FROM entity_segment"):
            words.setdefault(eid, []).append(w.replace("_", " "))
        for r in eco_rows:
            kind = _kind(cfg, r["entity_type"])
            if not kind:
                continue
            o = get(r["name"], kind, "ecosystem dataset")
            o["types"].append(r["entity_type"])
            o["eco_id"] = o["eco_id"] or r["id"]
            o["parts"] += [r[f] or "" for f in TEXT_FIELDS] + words.get(r["id"], [])
            o["caps"] = sorted(set(o["caps"]) | set(caps.get(r["id"], [])))
            if r["inv_stages"]:
                o["stages"] = [x.strip() for x in re.split(r"[;,]", r["inv_stages"]) if x.strip()]
            _merge_field(o, "geo_text", r["inv_geography"])
            _merge_field(o, "ticket_text", r["inv_ticket_eur"])
            o["confidence"] = o["confidence"] or r["confidence"]
            _merge_field(o, "url", matching._eco_url(eco, r["id"], r["website"]))
            if r["need_pilots_customers"]:
                o["need"].append(r["need_pilots_customers"])

    for r in matching._read_csv(m.get("corporates")):
        kind = _kind(cfg, r.get("type"))
        if not kind or not r.get("name"):
            continue
        o = get(r["name"], kind, "corporates_clients.csv")
        o["types"].append(r["type"])
        o["parts"].append(r.get("what_they_buy_or_pilot") or "")
        _merge_field(o, "url", _http(r.get("source_url"), r.get("website"), r.get("innovation_contact_page")))

    prog = []
    for r in matching._read_csv(m.get("programmes")):
        kind = _kind(cfg, r.get("type"))
        if kind and r.get("name"):
            prog.append((r, kind))
    base = dict(orgs)
    for r, kind in prog:
        k = okey(r["name"])
        parent = max((b for bk, b in base.items() if len(bk) >= 5 and k.startswith(bk) and bk != k and not b["programme"]),
                     key=lambda b: len(b["okey"]), default=None)
        if k in orgs or (kind == "investor" and parent is not None):
            o = orgs.get(k) or parent
            if "programmes_grants.csv" not in o["sources"]:
                o["sources"].append("programmes_grants.csv")
        else:
            o = _new(r["name"], kind, "programmes_grants.csv")
            o["programme"] = True
            o["parent"] = parent["okey"] if parent else None
            orgs[k] = o
        o["types"].append(r["type"])
        o["parts"] += [r.get("eligibility_summary") or "", r.get("stage_window") or ""]
        _merge_field(o, "stage_text", r.get("stage_window"))
        _merge_field(o, "geo_text", r.get("geography"))
        _merge_field(o, "amount", r.get("amount_eur"))
        _merge_field(o, "trl_window", matching.trl_window(r.get("TRL_window_if_stated")))
        _merge_field(o, "age_limit", matching.age_limit(r.get("stage_window")))
        o["deadline"] = o["deadline"] or matching.parse_deadline(r.get("next_deadline"))
        _merge_field(o, "url", _http(r.get("source_url"), r.get("url")))

    for g in m.get("grants_next_dates") or []:
        gk = fold(re.split(r"\s*[(:]", g["name"], maxsplit=1)[0].replace("cut-off", ""))
        o = next((x for x in orgs.values() if x["okey"] and (x["okey"].startswith(gk) or gk.startswith(x["okey"])) and len(min(x["okey"], gk, key=len)) >= 8), None)
        if o is None:
            continue
        o["deadline"] = {"open": True, "date": g["date"], "text": g["date"]}
        win = matching.trl_window(g.get("trl_window"))
        if win:
            o["trl_window"] = win
        if g.get("source"):
            o["url"] = o["url"] or g["source"]
        o["window_source"] = g.get("source")
    if eco is not None:
        eco.close()
    for k in sorted(orgs, key=len, reverse=True):     # "Redstone Blue Fund I" is a fund of "Redstone Blue": one counterpart, both texts
        o = orgs.get(k)
        parent = max((b for bk, b in orgs.items() if o is not None and bk != k and len(bk) >= 8 and k.startswith(bk) and not b["programme"]
                      and b["kind"] == o["kind"] == "investor" and not o["programme"]), key=lambda b: len(b["okey"]), default=None)
        if parent is not None:
            parent["parts"] += o["parts"]
            parent["caps"] = sorted(set(parent["caps"]) | set(o["caps"]))
            parent["sources"] += [x for x in o["sources"] if x not in parent["sources"]]
            for f in ("stage_text", "geo_text", "url", "ticket", "stages"):
                _merge_field(parent, f, o.get(f))
            del orgs[k]
    out = list(orgs.values())
    seen: dict[str, int] = {}
    for o in out:
        s = slug(o["name"])
        seen[s] = seen.get(s, 0) + 1
        o["id"] = s if seen[s] == 1 else f"{s}-{seen[s]}"
        o["deadline"] = o["deadline"] or {"open": True, "date": None, "text": ""}
    return out


def _focus(o: dict, thesis: dict, names: tuple[str, ...]) -> str:
    """One line of what the organisation says it wants, person names redacted (the words of listed organisation names are not names),
    or '' when it says nothing. A sentence or clause that holds a redaction marker is dropped (D31); when that leaves nothing,
    `o["focus_dropped"]` is set and the caller shows the organisation type only."""
    text = next((p.strip() for p in o["parts"] if p and len(p.strip()) > 12), "")
    segs = [x for x in re.split(r"(?<=[.;])\s+", text) if not re.search(r"\.csv\b|\b(?:we|our)\b", x, re.I)]   # the list's own working notes are not the organisation's words
    text = " ".join(segs).replace("_", " ")
    text = fit_mod.redact_person_names(text, o["name"], thesis, also_allowed=names)
    text = re.sub(r"\s+", " ", text).strip(" ;,.")
    kept = fit_mod.drop_redacted_clauses(text).strip(" ;,.")
    o["focus_dropped"] = bool(text) and not kept
    text = kept
    if len(text) > 150:
        text = text[:150].rsplit(" ", 1)[0].rstrip(" ;,.") + "..."
    return text


def _profile_text(o: dict, cfg: dict) -> None:
    """Tokenise the declared text into stems and keyword groups (the dataset's capability codes count as group evidence)."""
    text = " ; ".join(p for p in o["parts"] + o["need"] if p)
    o["text"] = text
    o["stems_all"] = matchtext.stems(text, cfg)
    hits = matchtext.group_hits(text, cfg)
    o["groups"] = {gid: ["declared words " + matchtext.plain_list([f"'{w}'" for w in found[:3]])] for gid, found in hits.items()}
    cap_group = {g["capability"]: gid for gid, g in cfg["groups"].items() if g.get("capability")}
    for c in o["caps"]:
        gid = cap_group.get(c)
        if gid:
            o["groups"].setdefault(gid, []).append(f"dataset capability tag {c}")
    trig = matchtext.trigger_stems(hits, cfg)
    o["stems_free"] = {s: w for s, w in o["stems_all"].items() if s not in trig}
    o["has_declared"] = bool(o["stems_all"] or o["groups"])


def _company_names(conn) -> dict[str, str]:
    """Folded name -> company key for the companies that carry a declared role (cohort, portfolio, dataset, feed), plus the dataset's
    own startup rows. The 16,000 intake companies are left out: a name match there is too weak to call a member."""
    out = {}
    for key, name in conn.execute("SELECT company_key, name FROM companies WHERE group_tag != 'intake'"):
        out.setdefault(fold(name), key)
    try:
        for name, key in conn.execute("SELECT name, company_key FROM eco_entity WHERE company_key IS NOT NULL"):
            out.setdefault(fold(name), key)
    except sqlite3.OperationalError:
        pass
    return out


def _add_member(o: dict, key: str, since: str | None, basis: str, url: str | None) -> None:
    cur = o["members"].get(key)
    if cur is None:
        o["members"][key] = {"since": since, "basis": basis, "url": url}
    elif since and not cur["since"]:
        cur["since"] = since


def _revealed(orgs: list[dict], conn, thesis: dict, cfg: dict) -> None:
    by_key = {o["okey"]: o for o in orgs}
    by_eco = {o["eco_id"]: o for o in orgs if o["eco_id"]}
    aliases = {fold(k): fold(v) for k, v in (cfg.get("org_aliases") or {}).items()}

    def find(name: str) -> dict | None:
        k = okey(name)
        k = aliases.get(k, k)
        return by_key.get(k)

    def parent_of(prefix_name: str) -> dict | None:
        k = fold(prefix_name)
        cands = [o for o in orgs if o["okey"].startswith(k)]
        return min(cands, key=lambda o: len(o["okey"])) if cands else None

    names = _company_names(conn)
    ref = earliness.reference(thesis)[0]
    counts: dict[str, set] = {}
    csv_rows = matching._read_csv("data/declared/cohort_portfolio_companies.csv")
    for group, targets in (cfg.get("revealed_groups") or {}).items():
        for t in targets:
            o = parent_of(t)
            if o is None:
                continue
            for key, in conn.execute("SELECT company_key FROM companies WHERE group_tag=?", (group,)):
                _add_member(o, key, ref if group == (thesis.get("backtest") or {}).get("cohort_group") else None,
                            f"declared {group} company in the declared cohort and portfolio list", None)
            counts.setdefault(o["id"], set()).update(fold(r["company"]) for r in csv_rows if r.get("group") == group)

    eco = matching._eco_db()
    if eco is not None:
        eco_names = {r["id"]: r["name"] for r in eco.execute("SELECT id, name FROM entity")}
        for inv_id, cname in eco.execute("SELECT investor_id, company_name FROM investor_portfolio"):
            o = by_eco.get(inv_id)
            if o is None:
                continue
            counts.setdefault(o["id"], set()).add(fold(cname))
            key = names.get(fold(cname))
            if key:
                _add_member(o, key, None, "listed in the dataset's portfolio table", None)
        for eid, iname in eco.execute("SELECT entity_id, investor_name FROM entity_investor"):
            o = find(iname)
            cname = eco_names.get(eid)
            if o is None or not cname:
                continue
            counts.setdefault(o["id"], set()).add(fold(cname))
            key = names.get(fold(cname))
            if key:
                _add_member(o, key, None, "named as an investor of the company in the dataset", None)
        for date_, company, counterparty, src in eco.execute(
                "SELECT date, company, counterparty, sources FROM event WHERE counterparty IS NOT NULL AND counterparty != ''"):
            for piece in re.split(r"[;,]", counterparty):
                o = find(piece)
                if o is None:
                    continue
                cname = re.split(r"\s*\(", company or "", maxsplit=1)[0]
                counts.setdefault(o["id"], set()).add(fold(cname))
                key = names.get(fold(cname)) or names.get(fold(company or ""))
                if key:
                    url = next((u for u in re.findall(r"https?://[^\s;,)]+", src or "")), None)
                    _add_member(o, key, (date_ or None), "named in a dated round or programme entry in the dataset", url)
        eco.close()
    for o in orgs:
        o["declared_total"] = max(len(counts.get(o["id"], ())), len(o["members"]))
    for o in orgs:      # a programme is only a member list of its own, but it looks for lookalikes in the cohort of the organisation that runs it
        p = by_key.get(o["parent"]) if o["parent"] else None
        o["lookalikes"] = {**p["members"], **o["members"]} if p is not None else dict(o["members"])
        o["lookalike_total"] = max(o["declared_total"], p["declared_total"]) if p is not None else o["declared_total"]
        o["via_parent"] = p["name"] if p is not None else None


def _sig(thesis: dict, conn) -> tuple:
    from radar.adapters.ecosystem import DB_PATH
    m = thesis.get("matching") or {}
    files = [DB_PATH, ROOT / "data/declared/cohort_portfolio_companies.csv"] + [ROOT / m[k] for k in ("investors", "corporates", "programmes") if m.get(k)]
    dbp = conn.execute("PRAGMA database_list").fetchone()[2]
    return (thesis["id"], dbp, *(Path(f).stat().st_mtime_ns if Path(f).is_file() else 0 for f in [dbp, *files]))


def registry(conn, thesis: dict) -> dict | None:
    """{'orgs': [...], 'by_id': {...}, 'df': Counter, 'n_text': int} for a thesis, rebuilt when a source file or the store changes."""
    cfg = matchtext.config(thesis)
    if cfg is None:
        return None
    sig = _sig(thesis, conn)
    hit = _CACHE.get(sig)
    if hit is not None:
        return hit
    orgs = _read(cfg, thesis)
    all_names = tuple(o["full_name"] for o in orgs)
    for o in orgs:
        _profile_text(o, cfg)
        o["focus"] = _focus(o, thesis, all_names)
        o["geo"] = matchtext.countries(o["geo_text"], cfg)
    _revealed(orgs, conn, thesis, cfg)
    names = {matchtext.stem(w, cfg) for o in orgs for w in matchtext.words(o["full_name"])}   # a shared organisation name is a connection, not a topic
    df = Counter(s for o in orgs for s in o["stems_free"])
    n_text = sum(1 for o in orgs if o["stems_all"])
    cap = cfg.get("max_doc_share", 0.12) * max(n_text, 1)
    common = {s for s, n in df.items() if n > cap} | names
    for o in orgs:
        o["stems_free"] = {s: w for s, w in o["stems_free"].items() if s not in common}
    out = {"orgs": orgs, "by_id": {o["id"]: o for o in orgs}, "df": df, "n_text": n_text, "common": common}
    _CACHE.clear()
    _CACHE[sig] = out
    return out
