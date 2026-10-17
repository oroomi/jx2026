"""Ask Aava: the deterministic answers behind the home bar (GET /api/ask?q=, radar/routes/ask.py). No model, no network call.

One question in, one answer out: {intent, say, url, action, ...}. The intent is chosen by rules over the question's words, in this order:
  1. "who should <org> meet" / "which startups fit <org>" / "match <org>" (patterns in thesis `ask.meet_patterns`): a company gets Aava's question 4
     answer, an organisation from the declared lists gets the match view with that organisation selected and the first startups it ranks (D77).
  2. a company by name or business id (legal-form words ignored, fuzzy for speech): Aava's question 1 answer and a link to the full memo.
  3. filter phrases (verdict words, countries, sector words, "TRL above 4"): the querystring of the home filter rail, and how many companies
     of the cached home list match.
  3b. "top startups", "best investment", "who should <org> invest in" (thesis `ask.top_phrases`, `ask.top_patterns`): the Top matching ranking of the
     default organisation, or of the investor or accelerator named; the same list the home tab and the Match page print (D63).
  4. "what is new / latest / recent": the feed answer, read by the same function as the home page's own (radar.routes.aava.feed_reader).
  5. an organisation name alone: the match view.
  6. a company name that only partly matches, once: that company. Anything else: the search page when it lists something for those letters, else
     "Nothing on the radar matches ..." with no link.
Every word the rules react to comes from the thesis file (`ask:` in config/thesis.yaml); this module holds no sector, verdict or country word.
The spoken text is the text of the Aava segments (their sha is returned, so the player can use a pre-rendered MP3 when one matches)."""
from __future__ import annotations

import csv
import difflib
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlencode

from radar import aava, aava_voice, fit as fit_mod, home_config, home_list, matching, store, thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
MAX_Q = 200
NONE = "none"                      # the filter rail's value for "no public record"
FILTER_PARAMS = ("verdict", "country", "sector", "trl", "brl", "irl", "impact", "fit")   # the rail's order (radar.home_filter.FACETS)
ORG_FILES = ("data/declared/investors.csv", "data/declared/programmes_grants.csv", "data/declared/corporates_clients.csv")
SCALE_MAX = 9
FUZZY_CUTOFF = 0.84
LIST_ITEMS = 5


# ---- text helpers ---------------------------------------------------------------------------------------------------------------------
def norm(text: str) -> str:
    """Folded, lower case, no apostrophes, hyphens and punctuation as spaces; the comparison symbols < > = stay (level words use them)."""
    t = unicodedata.normalize("NFKD", (text or "").replace("’", "'").replace("‘", "'"))
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).casefold().replace("'", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9<>=]+", " ", t)).strip()


def _phrase_re(phrase: str) -> re.Pattern:
    """A normalised phrase as a whole-word pattern."""
    parts = [re.escape(p) for p in norm(phrase).split()]
    return re.compile(r"(?<![a-z0-9])" + r"\s+".join(parts) + r"(?![a-z0-9])")


def _table(pairs: list[tuple[str, object]]) -> list[tuple[re.Pattern, object]]:
    """[(pattern, payload)] longest phrase first, so 'investment ready' is read before 'invest'."""
    pairs = [(p, v) for p, v in pairs if norm(p)]
    return [(_phrase_re(p), v) for p, v in sorted(pairs, key=lambda x: -len(norm(x[0])))]


def _scan(text: str, table) -> tuple[str, list]:
    """Find every phrase of the table in the text, longest first. Returns (text with the found phrases blanked, payloads in table order)."""
    found = []
    for rx, payload in table:
        if rx.search(text):
            found.append(payload)
            text = rx.sub(" ", text)
    return text, found


# ---- configuration --------------------------------------------------------------------------------------------------------------------
def config(th: dict) -> dict:
    """The thesis' `ask:` block over the default thesis' one: a key the thesis file leaves out is inherited (examples and sectors included, so
    a thesis that has none of its own must say `sectors: {}`)."""
    try:
        base = thesis_mod.load(thesis_mod.DEFAULT).get("ask") or {}
    except thesis_mod.ThesisError:
        base = {}
    return {**base, **(th.get("ask") or {})}


def examples(th: dict) -> list[str]:
    return [str(x) for x in config(th).get("examples") or []]


# ---- the answer shape ----------------------------------------------------------------------------------------------------------------
def answer(intent: str, q: str, say: str, *, url: str | None = None, action: str = "none", label: str | None = None, segments: list[dict] | None = None,
           audio_dir: str | None = None, items: list[dict] | None = None, count: int | None = None, total: int | None = None, **extra) -> dict:
    """{intent, say, url, action} plus what the bar needs to show and speak it. `segments` carry the Aava text and its sha."""
    return {"intent": intent, "q": q, "say": say, "url": url, "action": action, "label": label, "segments": segments or [], "audio_dir": audio_dir,
            "items": items or [], "count": count, "total": total, **extra}


def _segments(segs: list[dict]) -> list[dict]:
    return [{"text": s["text"], "sha": s["sha"], "source_url": s.get("source_url")} for s in segs]


# ---- companies ------------------------------------------------------------------------------------------------------------------------
_BIZ_ID = re.compile(r"\b(\d{7})\s*-?\s*(\d)\b")


_partner_cache: dict = {}


def _partner_keys() -> tuple[tuple[str, ...], frozenset[str]]:
    """(folded partner prefixes, folded partner names) computed once per version of the declared lists (store.is_partner_org does this per call)."""
    po = store.partner_orgs()
    hit = _partner_cache.get(id(po))
    if hit is None:
        names = {store.name_key(n) for n in po["names"]} | {store.name_key(re.sub(r"\s*\([^)]*\)", "", n)) for n in po["names"]}
        hit = (tuple(store.name_key(p) for p in po["prefixes"]), frozenset(names))
        _partner_cache.clear()
        _partner_cache[id(po)] = hit
    return hit


_rows_cache: dict = {}


def _company_rows(conn, th: dict) -> list[tuple[str, str, str, str]]:
    """(company_key, name, folded name key, y-tunnus) for every company that may be named: neither a legal name shaped like a private person's
    nor a partner organisation (A'Pelago, Redstone and the declared lists) is. Read once per version of the store (17,000 names are folded)."""
    dbp = conn.execute("PRAGMA database_list").fetchone()[2]
    sig = (th.get("id"), dbp, Path(dbp).stat().st_mtime_ns if dbp and Path(dbp).is_file() else 0)
    hit = _rows_cache.get(sig)
    if hit is not None:
        return hit
    rows = _company_rows_uncached(conn, th)
    if dbp:
        _rows_cache.clear()
        _rows_cache[sig] = rows
    return rows


def _company_rows_uncached(conn, th: dict) -> list[tuple[str, str, str, str]]:
    prefixes, partner_names = _partner_keys()
    out = []
    for r in conn.execute("SELECT company_key, name, y_tunnus FROM companies"):
        if not r["name"] or fit_mod.looks_like_person(r["name"], th):
            continue
        k = store.name_key(r["name"])
        if k in partner_names or k.startswith(prefixes):   # partner organisations are not startups (store.is_partner_org, cached)
            continue
        out.append((r["company_key"], r["name"], k, r["y_tunnus"] or ""))
    return out


def find_company(conn, th: dict, text: str) -> tuple[str, dict | list | None]:
    """('exact' | 'unique' | 'fuzzy', {company_key, name}) for one company, ('many', [..]) for an ambiguous part of a name, ('none', None)."""
    rows = _company_rows(conn, th)
    m = _BIZ_ID.search(text or "")
    if m:
        bid = f"{m.group(1)}-{m.group(2)}"
        for key, name, _k, yt in rows:
            if bid in (key, yt):
                return "exact", {"company_key": key, "name": name}
    k = store.name_key(text)
    if len(k) < 3:
        return "none", None
    exact = [r for r in rows if r[2] == k]
    if exact:
        return "exact", {"company_key": exact[0][0], "name": exact[0][1]}
    if len(k) >= 4:
        part = sorted((r for r in rows if k in r[2]), key=lambda r: (not r[2].startswith(k), len(r[2]), r[1]))
        if len(part) == 1:
            return "unique", {"company_key": part[0][0], "name": part[0][1]}
        if part:
            return "many", [{"company_key": r[0], "name": r[1]} for r in part[:LIST_ITEMS]]
        close = difflib.get_close_matches(k, [r[2] for r in rows], n=2, cutoff=FUZZY_CUTOFF) if len(k) <= 30 else []   # speech spells names its own way
        hit = [r for r in rows if r[2] == close[0]] if close else []
        if hit:
            return "fuzzy", {"company_key": hit[0][0], "name": hit[0][1]}
    return "none", None


def company_answer(q: str, key: str, name: str, th: dict, conn, inputs, which: str = "brief") -> dict:
    """Aava's answer for one company: question 1 (`brief`) or question 4 (`meet`). `inputs(conn, th, key)` is radar.routes.aava._inputs."""
    x = inputs(conn, th, key)
    if x is None:
        return answer("search", q, f"No company with key {key} in this radar.", url=_search_url(q), action="search")
    segs = aava.company_script(x["c"], x["signals"], which, nxt=x["nxt"], step=x["step"], memo=x["memo"], thesis=th)["segments"]
    if which == "meet":
        segs = [s for s in segs if s.get("q") == 4] or segs
    segs = segs[:1]
    return answer("company", q, " ".join(s["text"] for s in segs), url=f"/c/{quote(key, safe='')}?demo=1", action="open",
                  label="Open the full memo", segments=_segments(segs), audio_dir=aava_voice.dir_name(key),
                  company={"company_key": key, "name": x["c"]["name"]})


# ---- the feed -------------------------------------------------------------------------------------------------------------------------
FEED_ROWS = 500          # the rows the home feed reads (radar.routes.feed.ROW_LIMIT); the answer reads the same ones


def feed_answer(q: str, th: dict, conn, reader=None) -> dict:
    """The home feed's own reader: the strong rows of the same feed, with the same utility-code skip (D22), so "what is new" never opens with
    a row the home answer would not name. `reader(rows, thesis)` is radar.routes.aava.feed_reader; without it the same two calls are made."""
    rows = store.feed(conn, th, limit=FEED_ROWS)
    if reader is not None:
        segs = reader(rows, th)["segments"]
    else:
        segs = aava.feed_script([r for r in rows if r["strength"] == "strong"], skip=aava.code_only_skip(th))["segments"]
    names = {r["company_key"]: r["name"] for r in rows}
    items = []
    for sg in segs:
        key = (sg.get("target") or "").removeprefix("aava-feed-")
        if key in names:
            items.append({"label": names[key], "url": f"/c/{quote(key, safe='')}"})
    return answer("feed", q, " ".join(sg["text"] for sg in segs), url="/?group=new" if items else None, action="open" if items else "none",
                  label="See all new this quarter", segments=_segments(segs), audio_dir="feed", items=items)


# ---- organisations --------------------------------------------------------------------------------------------------------------------
_orgs_cache: dict = {}


def orgs() -> list[dict]:
    """[{name, key, type}] from the declared investor, programme and corporate lists (read once per file version)."""
    sig = tuple((rel, (ROOT / rel).stat().st_mtime_ns if (ROOT / rel).is_file() else 0) for rel in ORG_FILES)
    hit = _orgs_cache.get(sig)
    if hit is None:
        hit = []
        for rel in ORG_FILES:
            p = ROOT / rel
            if not p.is_file():
                continue
            with p.open(encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    name = re.sub(r"\s*\([^)]*\)", "", (r.get("name") or "")).strip()
                    if name:
                        hit.append({"name": name, "key": store.name_key(name), "type": (r.get("type") or "").strip()})
        _orgs_cache.clear()
        _orgs_cache[sig] = hit
    return hit


def counterparts(th: dict, conn) -> list[dict]:
    """The matchmaking page's counterpart list ([{id, name, kind_label, ...}], radar.matchmaker.org_list) when that module is in this build, else []."""
    try:
        from radar import matchmaker
        return list(matchmaker.org_list(th, conn=conn) or [])
    except Exception:  # noqa: BLE001  (no matchmaker in this build, or it is not configured for this thesis)
        return []


def _counterpart(rows: list[dict], text: str) -> dict | None:
    k = store.name_key(text)
    if len(k) < 4:
        return None
    hit = [o for o in rows if store.name_key(o["name"]) == k] or [o for o in rows if len(k) >= 5 and store.name_key(o["name"]).startswith(k)]
    return hit[0] if len({store.name_key(o["name"]) for o in hit}) == 1 else None


def find_org(text: str, rows: list[dict] | None = None) -> dict | None:
    """The organisation a phrase names: {name, type, id?, kind_label?} or None. A partner prefix (store.PARTNER_PREFIXES) names the organisation behind its
    programmes. `rows` is the matchmaking counterpart list: it supplies the id the match page selects by, and names the declared lists do not hold."""
    k = store.name_key(text)
    if len(k) < 4:
        return None
    prefix = next((p for p in store.PARTNER_PREFIXES if store.name_key(p) == k), None)
    found = [o for o in orgs() if o["key"] == k]
    if not found:   # a longer list name that starts with the phrase, or the phrase that starts with a short list name; one organisation only
        found = [o for o in orgs() if (len(k) >= 5 and o["key"].startswith(k)) or (len(o["key"]) >= 5 and k.startswith(o["key"]))]
        if prefix is None and len({o["key"] for o in found}) != 1:
            found = []
    cp = _counterpart(rows or [], prefix or (found[0]["name"] if found else text))
    if not found and cp is None:
        return None
    types = [o["type"] for o in found if o["type"]]
    out = {"name": prefix or (found[0]["name"] if found else cp["name"]), "type": max(set(types), key=types.count) if types else ""}
    if cp:
        out.update({"id": cp.get("id"), "kind_label": cp.get("kind_label")})
    return out


def _match_list(th: dict | None, org_id: str | None) -> dict | None:
    """The match view's ranking for one organisation (radar.home_orgs.ranking over radar.matchmaker.match_org: the list /match?org= prints), or
    None while it is still being built or when there is no matchmaker (D77)."""
    if not th or not org_id:
        return None
    try:
        from radar import home_orgs
        return home_orgs.ranking(th, org_id)
    except Exception:  # noqa: BLE001  (no matchmaker in this build)
        return None


def match_answer(q: str, org: dict, cfg: dict, has_match: bool, thesis_id: str | None, th: dict | None = None) -> dict:
    kind = (cfg.get("org_types") or {}).get(org["type"])
    if kind:
        say = f"{org['name']} is on the declared lists as {kind}."
    elif org.get("kind_label"):
        say = f"{org['name']} is on the counterpart list as {org['kind_label'].lower()}."
    else:
        say = f"{org['name']} is {cfg.get('org_default') or 'an organisation in the declared lists'}."
    url = f"/match?{urlencode({'org': org.get('id') or org['name'], **({'thesis': thesis_id} if thesis_id else {})})}"
    rank = _match_list(th, org.get("id")) if has_match else None
    rows = (rank or {}).get("rows") or []
    if rows:      # D77: the same startups, in the same order, as the match view (and the model's get_org_matches); D38: the connected apart
        first = [r["name"] for r in rows[:3]]
        say += f" Of the startups that fit it, the match view puts {', '.join(first[:-1]) + ' and ' + first[-1] if len(first) > 1 else first[0]} first"
        say += f"; the {rank['connected']} companies it is already connected to are listed apart." if rank.get("connected") else "."
        if rank.get("note"):
            say += " " + rank["note"]
    elif rank and (rank.get("closed_note") or rank.get("empty_reason")):
        why = matching.closed_words(rank["closed_note"]) + "." if rank.get("closed_note") else rank["empty_reason"]     # D76: a closed call is said one way
        say += f" No startup is listed for it: {why}" + (" The companies it is already connected to are on the match view." if rank.get("connected") else "")
    elif has_match:
        say += " The match view lists the startups that fit it and the companies it is already connected to."
    return answer("match", q, say, url=url if has_match else None, action="open" if has_match else "none", label="Open the match view",
                  items=[{"label": r["name"], "url": f"/c/{quote(r['key'], safe='')}"} for r in rows[:TOP_ITEMS]],
                  count=len(rows) if rows else None, total=(rank or {}).get("listed"), org={"name": org["name"], "type": org["type"], "id": org.get("id")})


# ---- the top matching ranking --------------------------------------------------------------------------------------------------------
TOP_ITEMS = 5


def _top_orgs(th: dict) -> list[dict]:
    """The investors and accelerators the Top matching tab can be made for (radar.home_orgs.organisations); [] when the thesis has no matchmaking."""
    try:
        from radar import home_orgs
        return home_orgs.organisations(th)
    except Exception:  # noqa: BLE001  (no matchmaker in this build)
        return []


def top_request(t: str, core: str, th: dict, cfg: dict) -> dict | None:
    """{org: id | None} when the question asks for the top or best startups ('top startups', 'who should Redstone invest in'), else None. A
    named organisation that the tab cannot be made for is not read as this question (the other rules then look at it)."""
    rows = _top_orgs(th)
    if not rows:
        return None
    for text in dict.fromkeys((t, norm(core))):
        for pat in cfg.get("top_patterns") or []:
            before, _sep, after = pat.partition("{org}")
            rx = re.compile(r"^\s*" + re.escape(norm(before)) + r"\s*(?P<org>.+?)\s*" + re.escape(norm(after)) + r"\s*$")
            m = rx.match(text)
            if m and m.group("org"):
                org = find_org(m.group("org"), rows)
                if org and org.get("id") in {o["id"] for o in rows}:
                    return {"org": org["id"]}
    if any(rx.search(" " + t + " ") for rx, _ in _table([(w, 1) for w in cfg.get("top_phrases") or []])):
        return {"org": None}
    return None


def top_answer(q: str, req: dict, th: dict, thesis_id: str | None) -> dict:
    """The Top matching ranking of one organisation, named in a sentence with its first startups as links, and the tab as the link."""
    from radar import home_orgs
    orgs = home_orgs.organisations(th)
    org_id = req["org"] or home_orgs.default_org(orgs) or orgs[0]["id"]
    name = next(o["name"] for o in orgs if o["id"] == org_id)
    url = "/?" + urlencode([("group", "fit"), ("for", org_id), *([("thesis", thesis_id)] if thesis_id else [])])
    rank = home_orgs.ranking(th, org_id)
    if rank is None:
        return answer("top_match", q, f"The ranking for {name} is still being prepared. Open the Top matching tab in a moment.", url=url, action="open",
                      label="Open the Top matching tab", org={"id": org_id, "name": name})
    rows = rank["rows"]
    if not rows:
        why = rank.get("closed_note") or rank.get("empty_reason")
        return answer("top_match", q, f"No startup on the radar is ranked for {name}" + (f": {why}" if why else "."), url=url, action="open",
                      label="Open the Top matching tab", org={"id": org_id, "name": name}, count=0, total=rank["listed"])
    first = [r["name"] for r in rows[:3]]
    say = f"The top startups for {name}, in the matchmaker's order: {', '.join(first[:-1])} and {first[-1]}." if len(first) > 1 else f"The top startup for {name} is {first[0]}."
    if rank.get("note"):
        say += " " + rank["note"]
    return answer("top_match", q, say, url=url, action="open", label="Show the whole ranking", count=len(rows), total=rank["listed"],
                  items=[{"label": r["name"], "url": f"/c/{quote(r['key'], safe='')}"} for r in rows[:TOP_ITEMS]], org={"id": org_id, "name": name})


# ---- filters ---------------------------------------------------------------------------------------------------------------------------
def _bands(th: dict, scale: str) -> list[tuple[int, int, str]]:
    """The Low / Medium / High cuts of a 1-9 scale as (lowest level, highest level, '4-6'), read from the thesis' memo bands."""
    spec = (((th.get("memo") or {}).get("bands") or {}).get(scale) or {})
    low, high = int(spec.get("low_max", 3)), int(spec.get("high_min", 7))
    return [(1, low, f"1-{low}"), (low + 1, high - 1, f"{low + 1}-{high - 1}"), (high, SCALE_MAX, f"{high}-{SCALE_MAX}")]


def band_value(th: dict, scale: str, level: int | None) -> str:
    if level is None:
        return NONE
    return next((lab for lo, hi, lab in _bands(th, scale) if lo <= level <= hi), NONE)


_SCALE_OF = {"trl": "technology", "brl": "business", "irl": "investment"}
_OP_WORD = {"above": "above ", "atleast": "at least ", "below": "below ", "atmost": "at most ", None: ""}


def _level_filters(text: str, th: dict, cfg: dict) -> tuple[str, dict[str, list[str]], list[str]]:
    """'TRL above 4', 'BRL 6': (text with them blanked, {param: [band values]}, the words that name them). Bands that reach the stated levels are
    chosen, and the answer says so, because the filter rail groups levels in bands."""
    names = {norm(w): p for p, ws in (cfg.get("level_names") or {}).items() for w in ws}
    ops = {norm(w): o for o, ws in (cfg.get("level_ops") or {}).items() for w in ws}
    if not names:
        return text, {}, []
    alt = lambda ks: "|".join(re.escape(k) for k in sorted(ks, key=len, reverse=True))   # noqa: E731
    rx = re.compile(r"(?<![a-z0-9])(" + alt(names) + r")(?:\s+level)?\s*(?:(" + alt(ops) + r")\s*)?([1-9])(?![0-9])") if ops else \
        re.compile(r"(?<![a-z0-9])(" + alt(names) + r")(?:\s+level)?\s*()([1-9])(?![0-9])")
    sel: dict[str, list[str]] = {}
    said: list[str] = []
    for m in rx.finditer(text):
        param, op, n = names[m.group(1)], ops.get(m.group(2) or ""), int(m.group(3))
        if param == "irl":
            sel["irl"] = ["known"]
            said.append("IRL on record (the filter rail groups investment readiness as on record or not)")
            continue
        bands = _bands(th, _SCALE_OF[param])
        pick = [b for b in bands if (b[1] > n if op == "above" else b[1] >= n if op == "atleast" else b[0] < n if op == "below"
                                      else b[0] <= n if op == "atmost" else b[0] <= n <= b[1])]
        sel[param] = [b[2] for b in pick]
        span = " and ".join(b[2].replace("-", " to ") for b in pick) or "no band"
        said.append(f"{param.upper()} {_OP_WORD[op]}{n} ({'bands' if len(pick) > 1 else 'band'} {span})")
    return rx.sub(" ", text), sel, said


def parse_filters(text: str, th: dict, cfg: dict) -> dict | None:
    """The filter rail selection a question names, or None when it names none: {sel, said, unused}. `sel` is {param: [values]} with the rail's
    parameter names (plus `group`), `said` the readable parts, `unused` the content words that were not understood."""
    t = " " + norm(text) + " "
    sel: dict[str, list[str]] = {}
    said: list[str] = []

    def put(param: str, vals: list[str]) -> None:
        sel[param] = list(dict.fromkeys([*sel.get(param, []), *vals]))

    t, lv_sel, lv_said = _level_filters(t, th, cfg)
    for p, v in lv_sel.items():
        put(p, v)
    rules = cfg.get("filters") or []
    t, hit = _scan(t, _table([(w, i) for i, r in enumerate(rules) for w in r.get("words") or []]))
    for i in sorted(set(hit)):
        for p, v in (rules[i].get("set") or {}).items():
            put(p, [str(v)])
        said.append(rules[i].get("say") or "")
    names = home_config.country_names()
    country_words = {name: code for code, name in names.items()}
    country_words.update({w: code for code, ws in (cfg.get("countries") or {}).items() for w in ws})
    t, codes = _scan(t, _table([(w, c) for w, c in country_words.items()]))
    if codes:
        put("country", list(dict.fromkeys(codes)))
        said.append("in " + " or ".join(names.get(c, c) for c in dict.fromkeys(codes)))
    t, secs = _scan(t, _table([(w, s) for s, ws in (cfg.get("sectors") or {}).items() for w in ws]))
    if secs:
        put("sector", list(dict.fromkeys(secs)))
        said.append("in the " + " or ".join(s.lower() for s in dict.fromkeys(secs)) + " sector")
    said += lv_said
    if not sel:
        return None
    filler = {norm(w) for w in cfg.get("filler_words") or []}
    unused = [w for w in t.split() if w not in filler and not w.isdigit()]
    return {"sel": sel, "said": [s for s in said if s], "unused": unused}


def filter_url(sel: dict[str, list[str]], thesis_id: str | None = None) -> str:
    """The home page's querystring: group first, then the rail's parameters in the rail's order (radar.home_filter.href)."""
    pairs = [(k, v) for k in ("group",) for v in sel.get(k, [])[:1]]
    pairs += [(p, v) for p in FILTER_PARAMS for v in sel.get(p, [])]
    if thesis_id:
        pairs.append(("thesis", thesis_id))
    return "/?" + urlencode(pairs) if pairs else "/"


def _row_facets(row: dict, th: dict, conn, memo_of=None) -> dict[str, list[str]] | None:
    """What a row offers each rail parameter. A list build with the criteria columns carries it already (row['facets']); otherwise it is read
    from the row and the readiness levels the company page prints. Ocean impact needs the full memo, which the cached list does not hold: None."""
    if row.get("facets"):
        return row["facets"]
    ctx = matching.company_context(conn, row["company_key"]) or {}
    fw = ctx.get("fw") or {}
    cat = (fw.get("category") or {}).get("category")
    lv = lambda k: (fw.get(k) or {}).get("level")   # noqa: E731
    return {"verdict": [row.get("verdict") or NONE], "country": [row.get("country") or NONE], "fit": [row.get("fit") or NONE],
            "sector": [cat.capitalize() if cat else NONE], "trl": [band_value(th, "technology", lv("trl"))],
            "brl": [band_value(th, "business", lv("brl"))], "irl": ["known" if lv("irl") is not None else NONE]}


def count_matches(H: dict | None, sel: dict[str, list[str]], th: dict, conn) -> tuple[int | None, int | None, list[dict]]:
    """(matching, on the list, up to five matching rows) from the cached home list, or (None, total, []) when a selected parameter cannot be read."""
    if not H or not H.get("rows"):
        return None, None, []
    rows = H["rows"]
    total = len(rows)
    group = (sel.get("group") or [None])[0]
    if group:
        rows = next((rs for k, _l, rs in [*H.get("groups", []), *H.get("countries", [])] if k == group), [])
    keyed = {p: v for p, v in sel.items() if p != "group"}
    if "impact" in keyed and not all(r.get("facets") for r in rows):
        return None, total, []
    hits = []
    for r in rows:
        f = _row_facets(r, th, conn) or {}
        if all(set(f.get(p) or []) & set(vs) for p, vs in keyed.items()):
            hits.append(r)
    return len(hits), total, hits[:LIST_ITEMS]


def filter_answer(q: str, parsed: dict, th: dict, conn, thesis_id: str | None) -> dict:
    sel, desc = parsed["sel"], ", ".join(parsed["said"])
    H = home_list.for_template(th)
    n, total, hits = count_matches(H, sel, th, conn)
    if n is None:
        say = f"I read that as: {desc}." + (" The list is empty, so there is nothing to count." if not total else " I cannot count that filter from the cached list here.")
    elif n == 0:
        say = f"No company of the {total} on the list matches: {desc}."
    else:
        say = f"{n} of {total} companies on the list match: {desc}."
    if parsed["unused"]:
        say += " I did not use: " + ", ".join(parsed["unused"][:4]) + "."
    items = [{"label": r["name"], "url": f"/c/{quote(r['company_key'], safe='')}"} for r in hits]
    return answer("filter", q, say, url=filter_url(sel, thesis_id), action="filter", label="Show them in the list", items=items, count=n, total=total,
                  filters={p: v for p, v in sel.items()})


# ---- the search page ------------------------------------------------------------------------------------------------------------------
def _search_url(q: str, thesis_id: str | None = None) -> str:
    return "/search?" + urlencode({"q": q, **({"thesis": thesis_id} if thesis_id else {})})


def search_answer(q: str, thesis_id: str | None, items: list[dict] | None = None) -> dict:
    return answer("search", q, f"Here is what the radar holds on {q}.", url=_search_url(q, thesis_id), action="search", label="Open the search results", items=items)


def nothing_answer(q: str) -> dict:
    """A question the rules cannot place and the search page cannot either: say so, link nowhere, open nothing."""
    return answer("nothing", q, f"Nothing on the radar matches {q}. Try a company name, a country, or a sector.")


HELP = ("Ask about a company by name, ask what is new, name a verdict, a country or a sector, or ask who an organisation should meet. "
        "Every answer comes from the records on file.")


# ---- the one entry point -----------------------------------------------------------------------------------------------------------------
def _clean(q: str) -> str:
    return re.sub(r"\s+", " ", (q or "")).strip()[:MAX_Q]


def classify(q: str, th: dict, conn, *, has_match: bool = False) -> tuple[str, object, str]:
    """(kind, payload, core) for a question, by the rules in the module docstring. kind is meet_company | meet_org | meet_search | company |
    filter | top | feed | match | many | none. `core` is the question without its lead-in. resolve() answers from this, and the example chips ask it
    too, so an example is shown only when the answer it would get is not empty."""
    cfg = config(th)
    t = norm(q)
    core, words = q, q.split()
    for rx, n in _table([(w, len(norm(w).split())) for w in cfg.get("lead_ins") or []]):   # one lead-in: 'tell me about Viva Jets'
        if rx.match(t) and len(words) > n:
            core = " ".join(words[n:])
            break

    for pat in cfg.get("meet_patterns") or []:   # "who should A'Pelago meet", "match Redstone"
        before, _sep, after = pat.partition("{org}")
        rx = re.compile(r"^\s*" + re.escape(norm(before)) + r"\s*(?P<org>.+?)\s*" + re.escape(norm(after)) + r"\s*$")
        m = rx.match(t)
        if not m or not m.group("org"):
            continue
        subject = m.group("org")
        kind, hit = find_company(conn, th, subject)
        if kind == "exact":
            return "meet_company", hit, core
        org = find_org(subject, counterparts(th, conn) if has_match else None)
        if org:
            return "meet_org", org, core
        if kind in ("unique", "fuzzy"):
            return "meet_company", hit, core
        return "meet_search", subject, core

    kind, hit = find_company(conn, th, core)
    if kind == "exact":
        return "company", hit, core
    top = top_request(t, core, th, cfg)
    if top:
        return "top", top, core
    parsed = parse_filters(core, th, cfg)
    if parsed:
        return "filter", parsed, core
    if any(rx.search(" " + t + " ") for rx, _ in _table([(w, 1) for w in cfg.get("feed_words") or []])):
        return "feed", None, core
    org = find_org(core, counterparts(th, conn) if has_match else None)
    if org:
        return "match", org, core
    if kind in ("unique", "fuzzy"):
        return "company", hit, core
    if kind == "many":
        return "many", hit, core
    return "none", None, core


def resolve(q: str, th: dict, conn, *, inputs, has_match: bool = False, thesis_id: str | None = None, feed_reader=None) -> dict:
    """The answer to a question. `inputs` is radar.routes.aava._inputs; `has_match` says whether the /match page exists in this build;
    `feed_reader` is radar.routes.aava.feed_reader, the home feed's own reader."""
    q = _clean(q)
    cfg = config(th)
    if len(norm(q)) < 2:
        return answer("help", q, HELP)
    if conn is None:
        return answer("help", q, "The radar has no data loaded yet. " + store.NO_DB_MESSAGE)
    kind, hit, core = classify(q, th, conn, has_match=has_match)
    if kind == "meet_company":
        return company_answer(q, hit["company_key"], hit["name"], th, conn, inputs, "meet")
    if kind == "meet_org":
        return match_answer(q, hit, cfg, has_match, thesis_id, th)
    if kind == "meet_search":
        return search_answer(hit, thesis_id)
    if kind == "company":
        return company_answer(q, hit["company_key"], hit["name"], th, conn, inputs)
    if kind == "top":
        return top_answer(q, hit, th, thesis_id)
    if kind == "filter":
        return filter_answer(q, hit, th, conn, thesis_id)
    if kind == "feed":
        return feed_answer(q, th, conn, feed_reader)
    if kind == "match":
        return match_answer(q, hit, cfg, has_match, thesis_id, th)
    if kind == "many":
        return search_answer(core, thesis_id, [{"label": h["name"], "url": f"/c/{quote(h['company_key'], safe='')}"} for h in hit])
    if store.search(conn, core, 1):          # the search page would list something for these letters
        return search_answer(core, thesis_id)
    return nothing_answer(core)


# ---- the example chips -------------------------------------------------------------------------------------------------------------------
_examples_cache: dict = {}


def example_has_answer(q: str, th: dict, conn, H) -> bool:
    """True when the answer to this example is not empty for the thesis: a company, an organisation, a feed with rows, a filter that counts
    at least one company of the cached home list `H` (a list that is not built yet counts nothing, so the chip waits)."""
    q = _clean(q)
    kind, hit, _core = classify(q, th, conn, has_match=False)
    if kind in ("company", "meet_company", "match", "meet_org", "many", "top"):
        return True
    if kind == "filter":
        n, _total, _hits = count_matches(H, hit["sel"], th, conn)
        return bool(n)
    if kind == "feed":
        return any(r["strength"] == "strong" for r in store.feed(conn, th, limit=FEED_ROWS))
    return False


def live_examples(th: dict, conn) -> list[str]:
    """The thesis' example questions that have a non-empty answer in this store, in the file's order. Cached per store version once the home
    list is built; computed again while it is not."""
    if conn is None:
        return []
    exs = examples(th)
    H = home_list.for_template(th)
    ready = bool(H and H.get("rows"))
    dbp = conn.execute("PRAGMA database_list").fetchone()[2]
    sig = (th["id"], dbp, Path(dbp).stat().st_mtime_ns if dbp and Path(dbp).is_file() else 0, tuple(exs))
    if ready and sig in _examples_cache:
        return list(_examples_cache[sig])
    out = [q for q in exs if example_has_answer(q, th, conn, H)]
    if ready:
        _examples_cache[sig] = out
    return out
