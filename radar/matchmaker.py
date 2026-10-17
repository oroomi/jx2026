"""Matchmaking: which counterpart is the next step for a startup, and which startups fit a counterpart. Filter, then rank, and every
rank explains itself in words (PROJECT_RULES D22 to D24; method and sources in docs/MATCHING.md).

Hard filters (a counterpart that fails one is not listed):
  1 kind     the startup's verdict path (the memo's decision) decides which kinds it meets; corporates and ports are pilot partners for all;
  2 geography  the place the counterpart declares must include the startup's country (nothing declared = not filtered, and said so);
  3 window   a stated TRL window or age limit that excludes the startup, a closed programme, a deadline in the past.
Soft components, each a sentence with the record behind it: sector (code, dataset capability tag, impact category or own text against the
counterpart's declared words), keywords (raw shared word stems), readiness window, portfolio lookalike (members of the counterpart's declared
cohort or portfolio), timing (deadline inside `deadline_days`), geography. The weights come from `matching.weights` in the thesis file. A
counterpart is listed only if at least one topic component holds. The page shows the components, never one number.
Organisations only. Pure functions over the store and the declared lists; no web code."""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from datetime import date, timedelta

from radar import blueinvest, fit as fit_mod, frameworks, matching, memo, store, matchmaker_orgs as orgs_mod, matchtext
from radar.matchtext import plain_list
from radar.store import name_key as fold

_IDX: dict = {}
COMPONENTS = ("sector", "lookalike", "keywords", "readiness", "timing", "geography")
LABELS = {"sector": "Sector or impact area", "lookalike": "Portfolio lookalike", "keywords": "Shared words", "readiness": "Readiness window",
          "timing": "Timing", "geography": "Geography", "member": "Declared member"}
RULE = ("Filter, then rank. A counterpart is listed when its kind fits the startup's verdict path (corporates and ports are pilot partners for "
        "everyone), the geography it declares includes the startup's country, it is open, and no stated TRL window or age limit excludes the "
        "startup. It must also hold at least one topic reason: the same sector or impact area, shared words, or lookalikes in its declared "
        "cohort or portfolio. Listed counterparts are ordered by how many reasons hold and by the weight the thesis file gives each reason "
        "(sector and lookalike most, then shared words and readiness, then timing and geography), then by the nearest deadline. "
        "The reasons are shown, never a total.")


# ---- the startup side ---------------------------------------------------------------------------------------------

_NOISE = re.compile(r"\[declared research[^\]]*\]|Open the source link for the details|Proposed by an LLM, checked by code[^.]*\.|Page first archived [\d-]+\.?|"
                    r"Page not in the Internet Archive\.?|Year only\.?|Month only[^.]*\.?|Matched on project (?:objective|title|keywords): '[^']*'\.|https?://\S+")


def _clean(text: str | None) -> str:
    """A signal's text without the radar's own annotations (provenance notes, links, 'declared research' brackets)."""
    return _NOISE.sub(" ", text or "")


def _index(conn, thesis: dict, cfg: dict, today: date) -> dict:
    """One light record per company: code family, country, age, words, sector groups. Built once per store version."""
    dbp = conn.execute("PRAGMA database_list").fetchone()[2]
    from pathlib import Path
    sig = (thesis["id"], dbp, Path(dbp).stat().st_mtime_ns, today.isoformat())
    if sig in _IDX:
        return _IDX[sig]
    cs, cg = {}, {}                      # per distinct text: the same line of business repeats for thousands of companies
    text: dict[str, list[str]] = {}
    types = list(cfg.get("text_signal_types") or [])
    if types:
        for key, detail in conn.execute(f"SELECT company_key, detail FROM signals WHERE signal_type IN ({','.join('?' * len(types))}) AND detail IS NOT NULL", types):
            text.setdefault(key, []).append(_clean(detail))
    try:
        for key, t in conn.execute("SELECT s.company_key, t.text FROM signal_text t JOIN signals s ON s.id = t.signal_id"):
            text.setdefault(key, []).append(_clean(t))
        for key, title, desc in conn.execute("SELECT company_key, title, description FROM blueinvest_profiles WHERE company_key IS NOT NULL"):
            text.setdefault(key, []).append(_clean(f"{title or ''}. {desc or ''}"))
        for key, js in conn.execute("SELECT company_key, slots_json FROM company_brief_slots"):
            import json
            v = (json.loads(js) or {}).get("what_it_does")
            if v and v.get("text"):
                text.setdefault(key, []).append(v["text"])
    except sqlite3.OperationalError:
        pass
    eco_by_key = _eco_text(conn)
    cap_group = {g["capability"]: gid for gid, g in cfg["groups"].items() if g.get("capability")}
    out: dict[str, dict] = {}
    for r in conn.execute("SELECT company_key, name, country, founded, industry_code, industry_desc, group_tag, source_url, register_status FROM companies"):
        if r["register_status"] in ("bankrupt", "ended") or fit_mod.looks_like_person(r["name"] or "", thesis):
            continue
        key = r["company_key"]
        eco = eco_by_key.get(key) or {}
        own = " . ".join([r["industry_desc"] or ""] + text.get(key, []))
        extra = fit_mod.redact_person_names(" . ".join(eco.get("text") or []), r["name"], thesis).replace(fit_mod.REDACTED, " ") if eco.get("text") else ""
        full = f"{own} . {extra}" if extra else own
        fam = matchtext.code_family(r["industry_code"], cfg)
        groups: dict[str, list[str]] = {}
        code_digits = re.sub(r"\D", "", r["industry_code"] or "")
        for pre in sorted((str(k) for k in cfg.get("code_groups") or {}), key=len, reverse=True):
            if code_digits.startswith(pre):
                for gid in cfg["code_groups"][pre]:
                    groups.setdefault(gid, []).append(f"its industry code {r['industry_code']} ({(r['industry_desc'] or 'no description').lower()})")
                break
        for c in eco.get("caps") or []:
            if cap_group.get(c):
                groups.setdefault(cap_group[c], []).append(f"the dataset's capability tag {c}")
        if full not in cg:
            h = matchtext.group_hits(full, cfg)
            cg[full] = (h, matchtext.stems(full, cfg), matchtext.trigger_stems(h, cfg))
        hits, allstems, trig = cg[full]
        own_name = {matchtext.stem(w, cfg) for w in matchtext.words(r["name"])}
        for gid, found in hits.items():
            if cfg["groups"][gid].get("needs_structure") and gid not in groups:
                continue                  # a broad group (software, hardware) counts only when the industry code or the dataset says so
            groups.setdefault(gid, []).append("its own text naming " + plain_list([f"'{w}'" for w in found[:2]]))
        age = matchtext.age_years(r["founded"], today)
        out[key] = {"key": key, "name": r["name"], "country": r["country"], "founded": r["founded"], "age": age,
                    "band": matchtext.age_band(age, cfg), "code": r["industry_code"], "family": fam, "desc": r["industry_desc"],
                    "group_tag": r["group_tag"], "url": r["source_url"], "groups": groups, "stems": {s: w for s, w in allstems.items() if s not in trig and s not in own_name},
                    "all_stems": allstems, "eco_stage": eco.get("stage"), "text_n": len(text.get(key, [])) + (1 if r["industry_desc"] else 0) + (1 if extra else 0)}
    df = Counter(st for e in out.values() for st in e["stems"])
    cap = float(cfg.get("max_startup_share", 0.03)) * max(len(out), 1)
    common = {st for st, n in df.items() if n > cap}
    for e in out.values():
        e["stems"] = {st: w for st, w in e["stems"].items() if st not in common}
    _IDX.clear()
    _IDX[sig] = out
    return out


def _eco_text(conn) -> dict[str, dict]:
    """company key -> {'text': [...], 'caps': [...], 'stage': ...} from the ecosystem dataset's startup rows (never its people table)."""
    eco = matching._eco_db()
    if eco is None:
        return {}
    try:
        keys = dict(conn.execute("SELECT entity_id, company_key FROM eco_entity WHERE company_key IS NOT NULL").fetchall())
    except sqlite3.OperationalError:
        return {}
    caps: dict[str, list[str]] = {}
    for eid, code in eco.execute("SELECT entity_id, code FROM entity_capability"):
        caps.setdefault(eid, []).append(code)
    words: dict[str, list[str]] = {}
    for eid, w in eco.execute("SELECT entity_id, keyword FROM entity_keyword UNION ALL SELECT entity_id, segment FROM entity_segment"):
        words.setdefault(eid, []).append(w.replace("_", " "))
    out = {}
    for r in eco.execute("SELECT id, description, working_on_now, need_pilots_customers, need_partners, stage FROM entity WHERE side='supply'"):
        k = keys.get(r["id"])
        if k:
            out[k] = {"text": [r["description"] or "", r["working_on_now"] or ""] + words.get(r["id"], []), "caps": caps.get(r["id"], []), "stage": r["stage"]}
    eco.close()
    return out


def _verdict(conn, thesis: dict, key: str) -> dict | None:
    """The memo's decision and the four bands, by the same functions memo.build uses (one source of truth), without the who-comes-next
    work it does for the page. Tested equal to memo.build for the demo companies."""
    ctx = matching.company_context(conn, key)
    if ctx is None:
        return None
    cfg = memo._cfg(thesis)
    lv = memo._levels(conn, ctx, key, cfg)
    imp = memo._impact(conn, ctx, key, cfg["bands"].get("impact") or {})
    fit = memo._fit(conn, ctx, thesis, cfg["bands"].get("fit") or {})
    bands = {"impact": imp["band"], "business": memo.band(lv["business"]["level"], cfg["bands"].get("business")),
             "investment": memo.band(lv["investment"]["level"], cfg["bands"].get("investment")), "fit": fit["band"]}
    if ctx["status"] in matching.INACTIVE:
        decision = "WATCHLIST"
    else:
        row, _ = memo.decide(bands, cfg, fit["support"])
        decision = row["decision"] if row else "WATCHLIST"
    bands["technology"] = memo.band(lv["technology"]["level"], cfg["bands"].get("technology"))
    return {"decision": decision, "bands": bands, "trl": ctx["trl"], "trl_src": ctx["trl_src"], "brl": ctx["fw"]["brl"]["level"],
            "irl": ctx["irl"], "category": ctx["category"], "stage": ctx["stage"], "sigs": ctx["sigs"]}


def startup(conn, thesis: dict, cfg: dict, key: str, today: date, full: bool = True) -> dict | None:
    """The startup profile the components read. `full` adds the verdict, readiness levels, impact category and grant history."""
    base = _index(conn, thesis, cfg, today).get(key)
    if base is None:
        return None
    sp = dict(base, groups={g: list(v) for g, v in base["groups"].items()})
    if not full:
        return sp
    v = _verdict(conn, thesis, key)
    if v is None:
        return None
    sp.update(decision=v["decision"], bands=v["bands"], trl=v["trl"], trl_src=v["trl_src"], brl=v["brl"], irl=v["irl"],
              category=v["category"], stage=v["stage"] or base["eco_stage"])
    if v["category"]:
        for gid, g in cfg["groups"].items():
            if g.get("category") == v["category"]:
                sp["groups"].setdefault(gid, []).append(f"the impact category {v['category']}")
    gts, pts = set(cfg.get("grant_signal_types") or []), set(cfg.get("pipeline_signal_types") or [])
    sp["grants"] = [s for s in v["sigs"] if s["signal_type"] in gts]
    sp["pipeline"] = [s for s in v["sigs"] if s["signal_type"] in pts]
    return sp


# ---- components ---------------------------------------------------------------------------------------------------

def _comp(cid: str, cfg: dict, met, chip: str | None = None, reason: str | None = None, note: str | None = None, links=None) -> dict:
    return {"id": cid, "label": LABELS[cid], "met": met, "weight": (cfg["weights"] or {}).get(cid, 0), "chip": chip, "reason": reason,
            "note": note, "links": [l for l in (links or []) if l.get("url")]}


def _sector(sp: dict, org: dict, cfg: dict) -> dict:
    shared = [g for g in sp["groups"] if g in org["groups"]]
    shared.sort(key=lambda g: (not any(e.startswith(("its industry code", "the dataset", "the impact")) for e in sp["groups"][g]), -len(sp["groups"][g])))
    if not org["has_declared"]:
        return _comp("sector", cfg, None, note="no declared text and no dataset tags")
    if not shared:
        return _comp("sector", cfg, False, note="no sector or impact area in common")
    labels = [cfg["groups"][g]["label"] for g in shared[:2]]
    g0 = shared[0]
    reason = (f"Same sector: {'; '.join(labels)}. The startup shows it through {plain_list(sp['groups'][g0][:2])}; "
              f"{org['name']} through {plain_list(org['groups'][g0][:2])}.")
    c = _comp("sector", cfg, True, chip="Sector: " + " + ".join(labels), reason=reason,
              links=[{"text": "startup record", "url": sp["url"]}, {"text": org["name"], "url": org["url"]}])
    c["broad"] = all(cfg["groups"][g].get("needs_structure") for g in shared)   # only a broad group (software, hardware) in common: shown, never enough alone
    return c


def _keywords(sp: dict, org: dict, cfg: dict, df) -> dict:
    if not org["has_declared"]:
        return _comp("keywords", cfg, None, note="no declared text")
    shared = [s for s in sp["stems"] if s in org["stems_free"]]
    if len(shared) < int(cfg.get("min_shared_words", 1)):
        return _comp("keywords", cfg, False, note="no shared words beyond the sector groups" if not shared else "only one word in common")
    shared.sort(key=lambda s: (df.get(s, 0), -len(sp["stems"][s])))
    words = [sp["stems"][s] for s in shared[:6]]
    reason = f"Shared words: {plain_list([repr(w) for w in words])} appear in the startup's own text and in {org['name']}'s declared text."
    return _comp("keywords", cfg, True, chip="Shared words: " + ", ".join(words[:4]), reason=reason,
                 links=[{"text": "startup record", "url": sp["url"]}, {"text": org["name"], "url": org["url"]}])


def _members(org: dict, idx: dict) -> list[dict]:
    return [idx[k] for k in org["lookalikes"] if k in idx]


def _lookalike(sp: dict, org: dict, cfg: dict, idx: dict, today: date) -> dict:
    mem = [m for m in _members(org, idx) if m["key"] != sp["key"]]
    if not mem:
        return _comp("lookalike", cfg, None, note="no declared cohort or portfolio company in our records")
    fam = [m for m in mem if sp["family"] and m["family"] == sp["family"]]
    if len(fam) < int(cfg.get("min_lookalike", 1)) or len(fam) / len(mem) < float(cfg.get("min_lookalike_share", 0)):
        return _comp("lookalike", cfg, False, note=f"too few of its {len(mem)} declared companies in our records share industry group {sp['family'] or 'unknown'}")
    cc = [m for m in fam if m["country"] and m["country"] == sp["country"]]
    bd = [m for m in fam if sp["band"] and m["band"] and m["band"]["id"] == sp["band"]["id"]]
    best = [m for m in fam if m in cc and m in bd] or [m for m in fam if m in cc] or fam
    names = [m["name"] for m in best[:2]]
    n = len(mem)
    parts = [f"{len(fam)} of the {n} declared companies in its cohort or portfolio share the startup's industry group {sp['family']}"]
    if sp["country"]:
        parts.append(f"{len(cc)} of those are registered in {sp['country']}")
    if sp["band"]:
        parts.append(f"{len(bd)} are in the age band {sp['band']['label']}")
    reason = "Lookalikes: " + "; ".join(parts) + f". Closest: {plain_list(names)}."
    links = [{"text": m["name"], "url": "/c/" + m["key"]} for m in best[:2]]
    return _comp("lookalike", cfg, True, chip=f"{len(fam)} of {n} declared companies in the same industry group", reason=reason, links=links)


def _window(sp: dict, org: dict, cfg: dict, today: date) -> tuple[str, dict]:
    """('fail' | 'met' | 'unknown' | 'na', readiness component). Only windows the counterpart states are checked."""
    met, unknown, notes = [], [], []
    fail = None
    win = org.get("trl_window")
    if win:
        trl = sp.get("trl")
        if trl is None:
            unknown.append(f"TRL window {win[0]} to {win[1]} stated; the startup's TRL is not in public records")
        elif not win[0] <= trl <= win[1]:
            fail = f"TRL {trl} is outside the stated window {win[0]} to {win[1]}"
        else:
            met.append((f"TRL {trl} is inside the stated window {win[0]} to {win[1]}", f"TRL {trl} fits the window {win[0]} to {win[1]}"))
    lim = org.get("age_limit")
    if lim:
        yr = (sp.get("founded") or "")[:4]
        if not yr.isdigit():
            unknown.append(f"age limit under {lim} years stated; the founding year is not in public records")
        elif today.year - int(yr) >= lim:
            fail = fail or f"founded {yr}, over the age limit of {lim} years"
        else:
            met.append((f"founded {yr}, inside the age limit of {lim} years", f"Under {lim} years old"))
    stage = sp.get("stage")
    if org.get("stage_text") and not stage and (org["programme"] or org.get("stages")):
        unknown.append(f"{org['name']} states a stage ('{org['stage_text']}'); the startup's stage is not in public records")
    if org.get("stage_text") and stage:
        sw = org["stage_text"].casefold()
        why = matching.stage_mismatch(stage, org["stage_text"]) if org["programme"] else None
        if why:
            fail = fail or why
        elif stage in matching.EARLY_STAGES and any(w in sw for w in matching._EARLY_WORDS) or \
                stage in matching.LATER_STAGES and any(w in sw for w in matching._LATER_WORDS):
            met.append((f"its stage ({matching._stage_words(stage)}) fits the stage {org['name']} states, '{org['stage_text']}'", f"Stage {matching._stage_words(stage)} fits"))
    if org.get("stages") and stage:
        if stage in org["stages"]:
            met.append((f"its stage ({matching._stage_words(stage)}) is among the stages {org['name']} states", f"Stage {matching._stage_words(stage)} fits"))
        else:
            fail = fail or f"the dataset puts the startup at {matching._stage_words(stage)} stage, outside the stages {org['name']} states"
    if fail:
        return "fail", _comp("readiness", cfg, False, note=fail)
    if met:
        return "met", _comp("readiness", cfg, True, chip=met[0][1], reason="Readiness window: " + "; ".join(m[0] for m in met) + ".",
                            links=[{"text": "stated window", "url": org.get("window_source") or org["url"]}])
    if unknown:
        return "unknown", _comp("readiness", cfg, False, note="; ".join(unknown))
    return "na", _comp("readiness", cfg, None, note="no window stated")


def _timing(org: dict, cfg: dict, today: date) -> dict:
    d = org["deadline"].get("date")
    if not d:
        return _comp("timing", cfg, None, note=org["deadline"].get("text") or "no deadline stated")
    n = (date.fromisoformat(d) - today).days
    if 0 <= n <= int(cfg.get("deadline_days", 90)):
        when = "today" if n == 0 else f"{n} days from {today.isoformat()}"
        return _comp("timing", cfg, True, chip="Closes today" if n == 0 else f"Closes in {n} days", reason=f"The deadline is {d}, {when}.",
                     links=[{"text": "call page", "url": org.get("window_source") or org["url"]}])
    return _comp("timing", cfg, False, note=f"deadline {d} is more than {cfg.get('deadline_days', 90)} days away")


def _geography(sp: dict, org: dict, cfg: dict) -> tuple[bool, dict]:
    """(passes, component). Nothing declared, or nothing we can read, or an unknown startup country, filters nothing."""
    geo = org["geo"]
    if not org.get("geo_text") or not geo:
        return True, _comp("geography", cfg, None, note="no geography declared" if not org.get("geo_text") else "geography text names no place we can read")
    if not sp["country"]:
        return True, _comp("geography", cfg, None, note="the startup's country is not in public records")
    if "*" in geo or sp["country"] in geo:
        return True, _comp("geography", cfg, True, chip=f"Covers {sp['country']}",
                           reason=f"{org['name']} declares the geography '{org['geo_text']}', which includes {sp['country']}, where the startup is registered.",
                           links=[{"text": org["name"], "url": org["url"]}])
    return False, _comp("geography", cfg, False, note=f"declared geography '{org['geo_text']}' does not include {sp['country']}")


def _open(org: dict, today: date) -> str | None:
    dl = org["deadline"]
    if not dl.get("open"):
        return "closed: " + (dl.get("text") or "not accepting applications")
    if dl.get("date") and dl["date"] < today.isoformat():
        return f"the deadline {dl['date']} has passed"
    return None


def evaluate(sp: dict, org: dict, cfg: dict, idx: dict, df, today: date, full: bool = True) -> dict:
    """Components and filter result for one startup and one counterpart. `excluded` is the reason a hard filter removed the pair."""
    comps: list[dict] = []
    excluded = None
    geo_ok, geo = _geography(sp, org, cfg)
    if not geo_ok:
        excluded = geo["note"]
    comps.append(_sector(sp, org, cfg))
    comps.append(_lookalike(sp, org, cfg, idx, today))
    comps.append(_keywords(sp, org, cfg, df))
    spw = sp if full else dict(sp, stage=sp.get("eco_stage"), trl=None)   # first pass: age and the dataset's stage only, TRL is read in the full pass
    state, ready = _window(spw, org, cfg, today)
    if state == "fail" and cfg.get("exclude_when_window_fails"):
        excluded = excluded or ready["note"]
    comps.append(ready)
    comps.append(_timing(org, cfg, today))
    comps.append(geo)
    topic = set(cfg.get("topic_components") or [])
    agnostic = set(cfg.get("agnostic_qualifies_by") or []) if not org["groups"] else set()
    qualifies = any(c["met"] and not c.get("broad") for c in comps if c["id"] in topic | agnostic)
    if not qualifies and not full and agnostic and state == "unknown":
        qualifies = True        # first pass only: the TRL is not read yet, the full pass decides
    if not qualifies:
        excluded = excluded or "no sector, word or lookalike reason holds"
    met = [c for c in comps if c["met"]]
    shared = [g for g in sp["groups"] if g in org["groups"]]
    strength = sum(len(sp["groups"][g]) for g in shared) + sum(1 for s in sp["stems"] if s in org["stems_free"])
    return {"components": comps, "excluded": excluded, "met": len(met), "of": sum(1 for c in comps if c["met"] is not None),
            "_w": sum(c["weight"] for c in met), "_s": strength}


def _demand(org: dict) -> str:
    has_members = bool(org["lookalikes"])
    if org["has_declared"] and has_members:
        return "declared and revealed"
    if org["has_declared"]:
        return "declared only"
    if has_members:
        return "revealed from its portfolio only (no declared text)"
    return "no declared text and no portfolio in our records"


def _org_row(org: dict, cfg: dict) -> dict:
    kind = cfg["kinds"][org["kind"]]
    dl = org["deadline"]
    return {"id": org["id"], "name": org["name"], "kind": org["kind"], "kind_label": kind["label"], "role": kind.get("role"),
            "focus": org["focus"] or ("no declared text: its demand is revealed from its portfolio only" if org["lookalikes"] else "no declared text"),
            "demand": _demand(org), "url": org["url"], "deadline": dl.get("date"), "deadline_text": dl.get("text") or None,
            "open": dl.get("open", True), "members_in_records": len(org["members"]), "declared_companies": org["declared_total"],
            "geography": org.get("geo_text"), "sources": org["sources"]}


def _sort_key(r: dict, primary: set[str]):
    return (-r["_w"], -r["met"], -r["_s"], 0 if r["kind"] in primary else 1, r["deadline"] or "9999-99-99", r["name"].casefold())


# ---- the two views ------------------------------------------------------------------------------------------------

def _with_conn(conn, thesis):
    if conn is not None:
        return conn, False
    return store.open_db(thesis=thesis), True


def match_company(company_key: str, thesis: dict, *, conn: sqlite3.Connection | None = None, today=None, limit: int = 10) -> dict | None:
    """The next steps for one startup: ranked counterparts with their components. None when matchmaking is not configured for the thesis
    or the company is unknown."""
    cfg = matchtext.config(thesis)
    if cfg is None:
        return None
    conn, own = _with_conn(conn, thesis)
    if conn is None:
        return None
    try:
        t = store._today(today)
        reg = orgs_mod.registry(conn, thesis)
        idx = _index(conn, thesis, cfg, t)
        sp = startup(conn, thesis, cfg, company_key, t)
        if sp is None:
            return None
        allowed = set(cfg["path_kinds"].get(sp["decision"]) or []) | set(cfg.get("always_kinds") or [])
        primary = set(cfg["path_kinds"].get(sp["decision"]) or [])
        rows, connected, dropped = [], [], {}
        for org in reg["orgs"]:
            if company_key in org["members"]:
                connected.append({"id": org["id"], "name": org["name"], "why": org["members"][company_key]["basis"]})
                continue
            if org["kind"] not in allowed:
                continue
            closed = _open(org, t)
            if closed:
                dropped["closed or past deadline"] = dropped.get("closed or past deadline", 0) + 1
                continue
            ev = evaluate(sp, org, cfg, idx, reg["df"], t)
            if ev["excluded"]:
                continue
            row = _org_row(org, cfg)
            row.update(components=ev["components"], met=ev["met"], of=ev["of"], _w=ev["_w"], _s=ev["_s"],
                       shared_words=[c["chip"] for c in ev["components"] if c["id"] == "keywords" and c["met"]])
            rows.append(row)
        rows.sort(key=lambda r: _sort_key(r, primary))
        shown = rows[:limit]
        for i, r in enumerate(shown, 1):
            r["rank"] = i
            del r["_w"], r["_s"]
        return {"company": _company_head(sp, cfg, primary), "as_of": t.isoformat(), "rule": RULE, "weights": cfg["weights"],
                "connected": connected, "listed": len(rows), "counterparts": shown, "limits": LIMITS}
    finally:
        if own:
            conn.close()


LIMITS = ("Reasons rest on declared lists and the ecosystem dataset; an organisation that declares nothing is matched on its portfolio only. "
          "Ticket size is not scored because a startup's funding ask is not in public records. A startup's text is its registered line of "
          "business, a few signal texts and, for the dataset's startups, its description. TRL is the radar's rule level, 'not in public records' when none.")


def _company_head(sp: dict, cfg: dict, primary: set[str]) -> dict:
    return {"key": sp["key"], "name": sp["name"], "url": "/c/" + sp["key"], "country": sp["country"], "founded": sp["founded"],
            "industry_code": sp["code"], "industry_family": sp["family"], "age_band": (sp["band"] or {}).get("label"),
            "verdict": sp["decision"], "meets": [cfg["kinds"][k]["label"] for k in primary if k in cfg["kinds"]],
            "bands": sp["bands"], "trl": sp["trl"], "brl": sp["brl"], "irl": sp["irl"], "impact_category": sp["category"],
            "sector_groups": [cfg["groups"][g]["label"] for g in sp["groups"]],
            "words": sorted(sp["stems"].values())[:12],
            "grants_on_record": len(sp["grants"]), "pipeline_on_record": len(sp["pipeline"])}


def match_org(org_id: str, thesis: dict, *, conn: sqlite3.Connection | None = None, today=None, limit: int = 25) -> dict | None:
    """The startups that fit one counterpart. Its declared cohort or portfolio companies come first; the others are ranked by the same
    components after a cheap first pass over every company and a full profile of the best `candidates`."""
    cfg = matchtext.config(thesis)
    if cfg is None:
        return None
    conn, own = _with_conn(conn, thesis)
    if conn is None:
        return None
    try:
        t = store._today(today)
        reg = orgs_mod.registry(conn, thesis)
        org = reg["by_id"].get(org_id)
        if org is None:
            return None
        idx = _index(conn, thesis, cfg, t)
        out_rows = []
        for key, m in org["members"].items():
            if key not in idx:
                continue
            sp = startup(conn, thesis, cfg, key, t)
            if sp is None:
                continue
            ev = evaluate(sp, org, cfg, idx, reg["df"], t)
            comps = [{"id": "member", "label": LABELS["member"], "met": True, "weight": 0, "chip": "In its declared cohort or portfolio",
                      "reason": f"Declared member: {m['basis']}" + (f", dated {m['since']}" if m["since"] else "") + ".",
                      "note": None, "links": [{"text": "declared list", "url": m["url"] or sp["url"]}]}] + [c for c in ev["components"] if c["met"]]
            out_rows.append(_startup_row(sp, comps, True, ev))
        out_rows.sort(key=lambda r: (-r["met"], r["name"].casefold()))
        closed = _open(org, t)
        cand = []
        tiers = {g: i for i, g in enumerate(cfg.get("tier_order") or [])}
        if not closed:
            for key, base in idx.items():
                if key in org["members"]:
                    continue
                ev = evaluate(dict(base), org, cfg, idx, reg["df"], t, full=False)
                if ev["excluded"]:
                    continue
                cand.append((ev["_w"], ev["met"], ev["_s"], tiers.get(base["group_tag"], 9), base["name"].casefold(), key))
            cand.sort(key=lambda c: (-c[0], -c[1], -c[2], c[3], c[4]))
            kinds_ok = lambda dec: org["kind"] in set(cfg["path_kinds"].get(dec) or []) | set(cfg.get("always_kinds") or [])
            full_rows = []
            for _w, _m, _s, _t, _n, key in cand[: int(cfg.get("candidates", 300))]:
                sp = startup(conn, thesis, cfg, key, t)
                if sp is None or not kinds_ok(sp["decision"]):
                    continue
                ev = evaluate(sp, org, cfg, idx, reg["df"], t)
                if ev["excluded"]:
                    continue
                full_rows.append(_startup_row(sp, ev["components"], False, ev))
            full_rows.sort(key=lambda r: (-r["_w"], -r["met"], -r["_s"], tiers.get(r["tier"], 9), r["name"].casefold()))
            out_rows += full_rows
        shown = out_rows[:limit]
        for i, r in enumerate(shown, 1):
            r["rank"] = i
            for k in ("_w", "_s", "tier"):
                r.pop(k, None)
        row = _org_row(org, cfg)
        row["closed_note"] = closed
        row["revealed"] = {"members_in_records": len(org["members"]), "declared_companies": org["declared_total"],
                           "basis": sorted({m["basis"] for m in org["members"].values()}),
                           "lookalikes_from": org.get("via_parent")}
        return {"org": row, "as_of": t.isoformat(), "rule": RULE, "weights": cfg["weights"],
                "candidates_profiled": min(len(cand), int(cfg.get("candidates", 300))) if not closed else 0,
                "listed": len(out_rows), "startups": shown, "limits": LIMITS}
    finally:
        if own:
            conn.close()


def _startup_row(sp: dict, comps: list[dict], member: bool, ev: dict) -> dict:
    return {"key": sp["key"], "name": sp["name"], "url": "/c/" + sp["key"], "country": sp["country"], "member": member,
            "verdict": sp.get("decision"), "industry_family": sp["family"], "components": comps,
            "met": sum(1 for c in comps if c["met"] and c["id"] != "member"), "_w": ev["_w"], "_s": ev["_s"], "tier": sp["group_tag"]}


def org_list(thesis: dict, *, conn: sqlite3.Connection | None = None, today=None) -> list[dict] | None:
    """Every counterpart in the registry as a row for the page's list: kind, name, declared focus in one line."""
    cfg = matchtext.config(thesis)
    if cfg is None:
        return None
    conn, own = _with_conn(conn, thesis)
    if conn is None:
        return None
    try:
        reg = orgs_mod.registry(conn, thesis)
        order = {k: i for i, k in enumerate(cfg["kinds"])}
        rows = [_org_row(o, cfg) for o in reg["orgs"]]
        rows.sort(key=lambda r: (order.get(r["kind"], 99), -r["members_in_records"], r["name"].casefold()))
        return rows
    finally:
        if own:
            conn.close()
