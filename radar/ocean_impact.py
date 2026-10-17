"""Ocean Impact Assessment for one company: impact area, evidence, scalability, Ocean Impact Readiness (x of 9), confidence.

The level is EVIDENCE READINESS from public records, not true impact (D22). The ladder, the area table, the rung texts and the
"what would raise it" lines live in `impact_readiness` of the thesis file; this module only applies them. Every key of the answer
is always present (SHAPE); a missing value is None, an empty list or a plain sentence saying so, never a made-up number.

Rungs (highest satisfied wins, tests in `_rung`):
  1-2 sector implied only: the trade register's industry-code family, its registered line of business and a legal-name word
      backed by a second source family point to an area
  3-4 the source's own text (notice title, project text, investor-pipeline profile) holds an area word
  5-6 a second independent source family names the area, and/or a blue programme or portfolio page lists the company
  7-8 declared research (the ecosystem dataset) holds an assessment / a quantified outcome with a stated method, at its own
      confidence medium or high (a low-confidence reading is listed as a lead and sets nothing, A24)
  9   a measured outcome from an official or register source: no connected source holds one
A legal-name word alone gives no area (A5); it counts only when a record from a different source family backs it (A6)."""
from __future__ import annotations

import re
import sqlite3
from urllib.parse import urlparse

from radar import fit as fit_mod, labels as lbl, store

SHAPE = ("area", "area_basis", "evidence", "scalability", "level", "level_max", "level_rule", "band", "confidence",
         "confidence_reason", "raise")
BASES = ("own text", "corroborated name word", "industry code family")
NOT_ASSESSED = "not assessed from public records"
_CONF = {"low": 0, "medium": 1, "high": 2}
MAX_EVIDENCE = 8


def settings(thesis: dict) -> dict | None:
    """The thesis file's `impact_readiness` block, or None when the sector defines no impact areas (then there is no assessment)."""
    cfg = thesis.get("impact_readiness") or {}
    return cfg if cfg.get("areas") else None


# ---- word matching ----------------------------------------------------------------------------------------------------
def _pattern(word: str) -> re.Pattern:
    w = re.escape(word.casefold().strip())
    # a short word must be a whole word; a word of 5+ letters also matches as the start of a longer word (fit.MATCH_RULE)
    return re.compile(r"(?<!\w)" + w + ("" if len(word.strip()) >= fit_mod.MIN_PREFIX else r"(?!\w)"))


def first_hit(text: str | None, words, stop: set[str]) -> str | None:
    """The first of `words` found in the text under the project's word rule, or None. A stop word never matches."""
    t = (text or "").casefold()
    for w in words or []:
        if not str(w).strip():
            continue
        for m in _pattern(str(w)).finditer(t):
            token = re.match(r"\w+", t[m.start():])
            if token and token.group().casefold() in stop:
                continue
            end = m.end()
            while end < len(t) and (t[end].isalnum() or t[end] == "_"):
                end += 1  # a word-start match is shown as the whole word the text uses (aquacultur -> aquaculture)
            return t[m.start():end]
    return None


# ---- records ----------------------------------------------------------------------------------------------------------
def _rec(text, date, label, url, family, kind) -> dict:
    return {"text": text, "date": date, "source_label": label, "url": url, "family": family, "kind": kind}


def _public(rec: dict) -> dict:
    return {k: rec[k] for k in ("text", "date", "source_label", "url", "family")}


def _register_date(c: dict) -> str | None:
    return (c.get("fetched_at") or "")[:10] or None


def _host(url: str | None) -> str:
    h = urlparse(url or "").netloc.casefold()
    return h[4:] if h.startswith("www.") else h


def _own_text_records(conn, own: list[dict], areas: dict, stop: set[str]) -> list[tuple[str, dict]]:
    """(area key, record) for every source text that holds an area word. Only the source's own wording is read: a Hilma notice
    title, a CORDIS title and objective, a BlueInvest profile text. Never our own `detail` annotation (D2)."""
    texts = store.source_texts(conn, own)
    out = []
    for s in own:
        if s["signal_type"] not in store._OWN_TEXT_TYPES:
            continue
        if s["signal_type"] == "public_contract":
            body = store._title_part(s["detail"])
        else:
            body = " . ".join(texts.get(s["id"], []))
        if not body:
            continue
        for key, a in areas.items():
            hit = first_hit(body, a.get("words"), stop)
            if hit:
                label = lbl.source_label(s["adapter"], s["source_url"])
                text = f"{lbl.signal_label(s['signal_type'])} text names '{hit}'"
                out.append((key, _rec(text, s.get("date_label") or s["date"], label, s["source_url"],
                                      store.source_family(s["adapter"]), "own_text")))
    return out


def _area_records(conn, ctx: dict, areas: dict, stop: set[str], thesis: dict) -> dict[str, list[dict]]:
    """area key -> the records that point to it (own text, corroborated name word, registered line of business, code family)."""
    c = ctx["c"]
    own = [s for s in ctx["sigs"] if s["adapter"] != "ecosystem"]
    found: dict[str, list[dict]] = {k: [] for k in areas}
    for key, rec in _own_text_records(conn, own, areas, stop):
        found[key].append(rec)
    code = (c.get("industry_code") or "").replace(".", "").strip()
    desc = (c.get("industry_desc") or "").strip()
    reg_label = lbl.source_label("prh", c.get("source_url"))
    reg_family = store.source_family("prh")
    name = c.get("name") or ""
    second = next((s for s in own if store.source_family(s["adapter"]) != reg_family), None)
    for key, a in areas.items():
        fam = next((p for p in a.get("code_prefixes") or [] if code and code.startswith(str(p))), None)
        if fam and c.get("source_url"):
            found[key].append(_rec(f"The registered industry code {code} is in code family {fam}" + (f" ({desc})" if desc else ""),
                                   _register_date(c), reg_label, c["source_url"], reg_family, "code"))
        hit = first_hit(desc, a.get("words"), stop) if desc else None
        if hit and c.get("source_url"):
            found[key].append(_rec(f"The registered line of business '{desc}' names '{hit}'", _register_date(c), reg_label,
                                   c["source_url"], reg_family, "line_of_business"))
        nhit = first_hit(name, a.get("words"), stop)
        if nhit and second is not None:  # a name word counts only with a record from a different source family (A6)
            backer = f"{lbl.source_label(second['adapter'], second['source_url'])} record from {second.get('date_label') or second['date']}"
            found[key].append(_rec(f"The legal name holds '{nhit}', backed by a {backer}", _register_date(c), reg_label,
                                   c["source_url"], reg_family, "name"))
    return found


def _strength(recs: list[dict]) -> tuple:
    kinds = {r["kind"] for r in recs}
    return (sum(r["kind"] == "own_text" for r in recs), "name" in kinds, "line_of_business" in kinds, "code" in kinds)


def _pick_area(found: dict[str, list[dict]]) -> str | None:
    """The area with the strongest records: own-text records first, then a corroborated name, a line of business, a code. A tie
    goes to the earlier area in the thesis file."""
    best, best_s = None, None
    for key, recs in found.items():
        if not recs:
            continue
        s = _strength(recs)
        if best_s is None or s > best_s:
            best, best_s = key, s
    return best


def _basis(recs: list[dict]) -> str:
    kinds = {r["kind"] for r in recs}
    if "own_text" in kinds:
        return BASES[0]
    if "name" in kinds:
        return BASES[1]
    return BASES[2]


def _programme_records(ctx: dict, cfg: dict) -> list[dict]:
    """Records on a blue programme or portfolio host (thesis `programme_hosts`) that list the company."""
    hosts = {h.casefold(): n for h, n in (cfg.get("programme_hosts") or {}).items()}
    out = []
    for s in sorted(ctx["sigs"], key=lambda x: x["date"], reverse=True):
        if store.source_family(s["adapter"]) == store.REGISTRY_FAMILY:
            continue
        h = _host(s["source_url"])
        name = next((n for dom, n in hosts.items() if h == dom or h.endswith("." + dom)), None)
        if name and s["source_url"] not in {r["url"] for r in out}:
            out.append(_rec(f"Listed on the {name} page", s.get("date_label") or s["date"],
                            f"{name} page, via {lbl.source_label(s['adapter'], s['source_url'])}", s["source_url"],
                            store.source_family(s["adapter"]), "programme"))
    return out


def _declared_reading(conn, company_key: str, cfg: dict) -> dict | None:
    """The ecosystem dataset's own ocean impact reading (declared research), or None when it has no row for the company."""
    try:
        r = conn.execute("SELECT oi_score, oir_score, oir_evidence, sources, confidence, last_verified FROM eco_readiness WHERE company_key=?",
                         (company_key,)).fetchone()
    except sqlite3.OperationalError:
        return None
    if r is None or (r[0] is None and r[1] is None and not (r[2] or "").strip()):
        return None
    oi, oir, ev, sources, conf, verified = r
    urls = [u for u in (sources or "").split("\n") if u.startswith(("http://", "https://"))]
    dr = cfg.get("declared_research") or {}
    top = dr.get("scale_max", 5)
    parts = []
    if oir is not None:
        parts.append(f"ocean impact readiness {oir} of {top}")
    if oi is not None:
        parts.append(f"impact {oi} of {top}")
    conf = (conf or "").lower() or None
    ok_conf = conf is not None and _CONF.get(conf, -1) >= _CONF.get(dr.get("min_confidence", "medium"), 1)
    text = "Declared research reading on the dataset's own scale: " + (", ".join(parts) or "no score") + \
        f"; dataset confidence {conf or 'not stated'}" + ("" if ok_conf else ", so it is a lead and sets no rung")
    rec = _rec(text, verified, lbl.source_label("ecosystem"), urls[0] if urls else None, store.source_family("ecosystem"), "declared")
    return {"rec": rec if rec["url"] else None, "oir": oir, "has_evidence": bool((ev or "").strip()), "ok_confidence": ok_conf}


# ---- the ladder -------------------------------------------------------------------------------------------------------
def _rung(recs: list[dict], programme: list[dict], declared: dict | None, cfg: dict) -> int | None:
    """The highest rung whose test passes (the thesis file's text for each rung is what the page prints)."""
    if not recs:
        return None
    implied = {r["kind"] for r in recs if r["kind"] in ("code", "line_of_business", "name")}
    own_n = len({r["url"] for r in recs if r["kind"] == "own_text"})
    families = {r["family"] for r in recs}
    level = 1 if implied else None
    if len(implied) >= 2:
        level = 2
    if own_n >= 1:
        level = 3
    if own_n >= 2:
        level = 4
    corroborated = len(families) >= 2
    if corroborated or programme:
        level = 5
    if corroborated and programme:
        level = 6
    dr = cfg.get("declared_research") or {}
    if declared and declared["ok_confidence"] and declared["has_evidence"] and declared["oir"] is not None:
        if declared["oir"] >= dr.get("assessment_min_score", 1):
            level = max(level or 0, 7)
        if declared["oir"] >= dr.get("measured_min_score", 4):
            level = max(level or 0, 8)
    return level


def _band(level: int | None, cfg: dict) -> str | None:
    if level is None:
        return None
    spec = cfg.get("bands") or {}
    if level < spec.get("evidenced_min", 1):
        return None  # sector-implied only: a gap to investigate, never a low score (A'Pelago guidance, D-rule in PROJECT_RULES.md)
    if level <= spec.get("low_max", 2):
        return "Low"
    return "High" if level >= spec.get("high_min", 7) else "Medium"


def _confidence(recs: list[dict], programme: list[dict], declared: dict | None) -> tuple[str, str]:
    """high: two or more independent source families agree; medium: one family that is not just the sector implied; low: only
    the sector implied (the trade register's code family and line of business) or nothing at all."""
    support = list(recs) + list(programme)
    if declared and declared["ok_confidence"] and declared["rec"]:
        support.append(declared["rec"])
    if not support:
        return "low", "No record names an impact area."
    fams: dict[str, str] = {}
    for r in support:
        fams.setdefault(r["family"], r["source_label"])
    names = list(fams.values())
    if len(fams) >= 2:
        return "high", f"{len(fams)} independent source families agree: " + ", ".join(names) + "."
    if all(r["kind"] in ("code", "line_of_business", "name") for r in support):
        return "low", f"Sector implied only: the one source is the {names[0]}."
    return "medium", f"One source family: {names[0]}."


def _scalability(ctx: dict, cfg: dict, stop: set[str]) -> dict:
    sc = cfg.get("scalability") or {}
    sigs = ctx["sigs"]
    countries = sc.get("register_countries") or {}
    seen = {}
    for s in sigs:
        fam = store.source_family(s["adapter"])
        if fam in countries:
            seen.setdefault(countries[fam], lbl.source_label(s["adapter"], s["source_url"]))
    if len(seen) >= 2:
        return {"text": "On the public registers of " + " and ".join(f"{c} ({n})" for c, n in sorted(seen.items())) + ".",
                "basis": "registers in more than one country"}
    eu = [s for s in sigs if s["signal_type"] in (sc.get("eu_level_types") or [])]
    if eu:
        s = max(eu, key=lambda x: x["date"])
        return {"text": f"{lbl.signal_label(s['signal_type'])} record from {s.get('date_label') or s['date']}: a programme that runs across EU member states.",
                "basis": "EU-level programme record"}
    own = [s for s in sigs if s["adapter"] != "ecosystem" and s["signal_type"] in store._OWN_TEXT_TYPES]
    texts = store.source_texts(ctx["conn"], own) if ctx.get("conn") is not None else {}
    for s in own:
        body = store._title_part(s["detail"]) if s["signal_type"] == "public_contract" else " . ".join(texts.get(s["id"], []))
        hit = first_hit(body, sc.get("market_words"), stop)
        if hit:
            return {"text": f"{lbl.signal_label(s['signal_type'])} text mentions '{hit}' ({s.get('date_label') or s['date']}).",
                    "basis": "own text about markets"}
    return {"text": NOT_ASSESSED, "basis": None}


def _level_rule(level: int | None, cfg: dict, recs, programme, declared) -> str:
    if level is None:
        return (cfg.get("no_level") or {}).get("rule") or "No rung applies."
    rung = next((r for r in cfg.get("levels") or [] if r.get("level") == level), {})
    used = []
    if level >= 5 and programme:
        used.append(programme[0]["text"])
    if level >= 7 and declared and declared["rec"]:
        used.append(declared["rec"]["text"])
    if level <= 6 and recs:
        used.append(sorted(recs, key=lambda r: ("own_text", "name", "line_of_business", "code").index(r["kind"]))[0]["text"])
    return f"Level {level}: {rung.get('rule', '')}" + (" On file: " + "; ".join(used) + "." if used else "")


def _raise(level: int | None, cfg: dict, recs, programme, declared) -> str:
    if level is None:
        return (cfg.get("no_level") or {}).get("raise") or ""
    text = next((r.get("raise") for r in cfg.get("levels") or [] if r.get("level") == level), "") or ""
    if level == 6 and declared and declared["rec"] and not declared["ok_confidence"]:
        text = "A better-sourced declared research reading: the one on file is low confidence and sets no rung."
    if level == 5:
        families = {r["family"] for r in recs}
        if programme and len(families) < 2:
            text = "A second independent source family that names the same area."
        elif not programme and len(families) >= 2:
            text = "A listing on a blue programme or portfolio page."
    return text


def empty(cfg: dict | None = None) -> dict:
    """The full shape with nothing on record."""
    nl = (cfg or {}).get("no_level") or {}
    return {"area": None, "area_basis": None, "evidence": [], "scalability": {"text": NOT_ASSESSED, "basis": None}, "level": None,
            "level_max": int((cfg or {}).get("level_max") or 9), "level_rule": nl.get("rule") or "No rung applies.", "band": None,
            "confidence": "low", "confidence_reason": "No record names an impact area.", "raise": nl.get("raise") or ""}


def assess(conn, ctx: dict, company_key: str, cfg: dict) -> dict:
    """The assessment for one company. `ctx` is radar.matching.company_context, `cfg` the thesis dict. Reads the store only."""
    ir = settings(cfg)
    if ir is None:
        return empty(cfg.get("impact_readiness"))
    areas = ir["areas"]
    stop = fit_mod.stop_words(cfg)
    found = _area_records(conn, ctx, areas, stop, cfg)
    key = _pick_area(found)
    recs = found[key] if key else []
    programme = _programme_records(ctx, ir)
    declared = _declared_reading(conn, company_key, ir)
    scal = _scalability({**ctx, "conn": conn}, ir, stop)
    evidence = [*recs, *programme] + ([declared["rec"]] if declared and declared["rec"] else [])
    if not recs:  # no record names an area: nothing to climb, but the records on file are still listed
        out = empty(ir)
        out.update(evidence=[_public(e) for e in evidence[:MAX_EVIDENCE]], scalability=scal)
        return out
    level = _rung(recs, programme, declared, ir)
    conf, why = _confidence(recs, programme, declared)
    return {"area": areas[key]["label"], "area_basis": _basis(recs), "evidence": [_public(e) for e in evidence[:MAX_EVIDENCE]],
            "scalability": scal, "level": level, "level_max": int(ir.get("level_max") or 9),
            "level_rule": _level_rule(level, ir, recs, programme, declared), "band": _band(level, ir),
            "confidence": conf, "confidence_reason": why, "raise": _raise(level, ir, recs, programme, declared)}


def for_company(conn, thesis: dict, company_key: str) -> dict | None:
    """The assessment from the store alone (the API and tests). None when the company is unknown or the thesis defines no areas."""
    from radar import matching
    if settings(thesis) is None:
        return None
    ctx = matching.company_context(conn, company_key)
    return None if ctx is None else assess(conn, ctx, company_key, thesis)
