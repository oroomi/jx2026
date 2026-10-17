"""The Top matching tab of the home list: the investors and accelerators the matchmaker knows (the picker), and, for one of them, the
startups the matchmaker's organisation view ranks (`radar.matchmaker.match_org`), each with its top reasons in words. Nothing here scores
or ranks: it asks the matchmaker, keeps its order, its count (`matching.show_startups`) and its reason sentences, so the tab and the Match
page never disagree (D62, D63; it replaces the intersection with the home list that D35 described). The other filters of the rail apply on
top, to the rows that carry those facts.

The matchmaker's organisation view takes about 1.5 s per organisation, so a ranking is built once per organisation and store version, in a
background thread; a request waits for it at most WAIT_SECONDS and then shows the plain Top matching list with a one-line note, the same
rule D26 gives the grouped list. Which organisation is picked when the URL names none, which kinds the picker lists and how many reasons a
row shows are in config/home_filters.yaml (`top_matching`)."""
from __future__ import annotations

import logging
import re
import threading

from radar import home_config, home_list, matchmaker, matchtext

log = logging.getLogger(__name__)
WAIT_SECONDS = 3.0
ANY = "any"                      # the picker's "no organisation": the plain Top matching list
_lock = threading.Lock()
_orgs: dict[tuple, list[dict]] = {}
_ranks: dict[tuple, dict] = {}
_building: dict[tuple, threading.Event] = {}


def organisations(thesis: dict) -> list[dict]:
    """The picker's organisations: every counterpart of the configured kinds (investors and accelerators), those with declared members in
    our records first. Empty when the thesis has no matchmaking."""
    key = home_list.stamp(thesis)
    if key is None or matchtext.config(thesis) is None:
        return []
    with _lock:
        hit = _orgs.get(key)
    if hit is not None:
        return hit
    kinds = list(home_config.top_matching()["kinds"])
    rows = matchmaker.org_list(thesis) or []
    out = sorted(({"id": o["id"], "name": o["name"], "kind": o["kind"], "kind_label": o["kind_label"], "members": o["members_in_records"]}
                  for o in rows if o["kind"] in kinds),
                 key=lambda o: (kinds.index(o["kind"]), -o["members"], o["name"].casefold()))
    with _lock:
        _orgs.clear() if len(_orgs) > 8 else None
        _orgs[key] = out
    return out


def default_org(orgs: list[dict]) -> str | None:
    """The configured default organisation, when this thesis' matchmaker knows it; otherwise none."""
    want = home_config.top_matching().get("default_org")
    return want if want and any(o["id"] == want for o in orgs) else None


def chosen(orgs: list[dict], asked: str) -> str | None:
    """The organisation in view for a `for` parameter: its id when the matchmaker knows it, none for 'any', the default when nothing valid is asked."""
    if asked == ANY:
        return None
    return asked if any(o["id"] == asked for o in orgs) else default_org(orgs)


def _words(component: dict) -> str:
    """A reason's sentence. The matchmaker prints a country as its code ('Covers FI'); here it is the name."""
    text = component["chip"]
    if component.get("id") == "geography":
        names = home_config.country_names()
        text = re.sub(r"\b[A-Z]{2}\b", lambda m: names.get(m.group(0), m.group(0)), text)
    return text


def top_reasons(components: list[dict], n: int) -> list[str]:
    """The `n` strongest reasons a startup is listed for an organisation, in words: being in its declared cohort or portfolio first, then the
    satisfied components by the weight the thesis gives them (the order they came in breaks ties)."""
    met = [c for c in components if c.get("met") and c.get("chip")]
    met.sort(key=lambda c: (0 if c.get("id") == "member" else 1, -int(c.get("weight") or 0)))
    return [_words(c) for c in met[:n]]


def _build(thesis: dict, key: tuple, org_id: str, done: threading.Event) -> None:
    try:
        res = matchmaker.match_org(org_id, thesis) or {}          # the default limit: the number the Match page prints
        n = int(home_config.top_matching()["reasons"])
        names = home_config.country_names()
        rows = [{"key": s["key"], "name": s["name"], "rank": s["rank"], "verdict": s["verdict"], "early": s.get("early", False),
                 "country": names.get(s["country"] or "", s["country"]), "why": top_reasons(s["components"], n)} for s in res.get("startups", [])]
        pipe = res.get("pipeline") or {}
        org = res.get("org") or {}
        ranks = {"rows": rows, "listed": res.get("listed", 0), "connected": len(res.get("connected", [])), "note": pipe.get("note"),
                 "early_label": pipe.get("early_label"), "empty_reason": org.get("empty_reason"), "closed_note": org.get("closed_note")}
        with _lock:
            _ranks.clear() if len(_ranks) > 40 else None
            _ranks[key] = ranks
    except Exception:  # noqa: BLE001  (the tab then shows the plain list; the next request tries again)
        log.exception("Top matching ranking for %s could not be built", org_id)
    finally:
        with _lock:
            _building.pop(key, None)
        done.set()


def ranking(thesis: dict, org_id: str, wait: float | None = WAIT_SECONDS) -> dict | None:
    """The matchmaker's ranking for one organisation, as the tab prints it: {rows: [{key, name, rank, verdict, early, country, why}], listed,
    connected, note, early_label, empty_reason, closed_note}, in the matchmaker's order and count. Built in the background once per store
    version; None while it is not ready (after waiting `wait` seconds; `wait=None` builds here and blocks)."""
    stamp = home_list.stamp(thesis)
    if stamp is None:
        return None
    key = (*stamp, org_id)
    with _lock:
        hit = _ranks.get(key)
        if hit is not None:
            return hit
        done = _building.get(key)
        mine = done is None
        if mine:
            done = _building[key] = threading.Event()
    if mine and wait is None:
        _build(thesis, key, org_id, done)
    elif mine:
        threading.Thread(target=_build, args=(thesis, key, org_id, done), name=f"home-orgs-{org_id}", daemon=True).start()
    done.wait(wait)
    with _lock:
        return _ranks.get(key)


def context(thesis: dict, asked: str, wait: float | None = WAIT_SECONDS) -> dict | None:
    """What the home list needs for its Top matching tab and picker: {orgs, org, name, rank, pending}. None when the thesis has no matchmaking
    (the tab is then the plain Top matching list). `rank` is None while the ranking is still being built (`pending`)."""
    orgs = organisations(thesis)
    if not orgs:
        return None
    org = chosen(orgs, asked)
    name = next((o["name"] for o in orgs if o["id"] == org), None)
    rank = ranking(thesis, org, wait) if org else None
    return {"orgs": orgs, "org": org, "name": name, "rank": rank, "pending": bool(org) and rank is None,
            "any_label": home_config.top_matching().get("any_label") or "Any"}


def warm(thesis: dict) -> None:
    """Build the picker's list and the default organisation's ranking now, on this thread (after the home list: it is the cheaper one)."""
    orgs = organisations(thesis)
    org = default_org(orgs)
    if org:
        ranking(thesis, org, wait=None)
