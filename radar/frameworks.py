"""Partner frameworks on screen two: BRL (KTH), TRL (Aalto), Investment Readiness read from the ten Investment
Potential dimensions, Ocean Impact Readiness (Ocean Impact Navigator), and the cross-source connection sentence.
Every level is a printed evidence-class rule, never a judgement: no signal in a class means no level (None)."""
from __future__ import annotations

import re
from datetime import date as _date
from pathlib import Path

import yaml

_CFG = Path(__file__).resolve().parent.parent / "config" / "frameworks.yaml"
CFG = yaml.safe_load(_CFG.read_text(encoding="utf-8"))
URLS = CFG["urls"]
CATEGORIES = {k: [w.lower() for w in v] for k, v in CFG["impact_categories"].items()}

LABELS = {
    "ocean_impact": "Ocean Impact Readiness (Ocean Impact Navigator)",
    "business": "Business Readiness Level (KTH BRL) 1-9",
    "technology": "Technology Readiness Level (Aalto TRL) 1-9",
    "investment": "Investment Readiness 1-9, read from the ten Investment Potential dimensions",
}
DIMENSIONS = ("Market", "Product", "Team", "Business Model", "Competition", "Marketing & Distribution",
              "Financials", "Tech", "Deal Dynamics", "Impact")

# (rule text, test on the company's signals) pairs; the highest satisfied level wins.
BRL_MAP = (
    (2, "register entry exists (PRH/YTJ)", "register_entry"),
    (3, "VAT registered: no VAT source in this radar, never assumed", None),
    (4, "first grant: Business Finland funding decision or EU project participation", ("bf_funding", "eu_project")),
    (6, "first public contract or named customer on own site", ("public_contract", "site_customer")),
    (7, "repeat contracts: two or more public contracts", "repeat"),
)
TRL_MAP = (
    (3, "patent filing: a protected concept", ("patent",)),
    (4, "Business Finland or EU project funding: a funded development project", ("bf_funding", "eu_project")),
    (5, "listed in the BlueInvest pipeline: screened for investment", ("blueinvest",)),
    (7, "public contract awarded: a buyer purchased in an operational setting", ("public_contract",)),
)
IRL_MAP = (
    (3, "public non-dilutive funding (Business Finland decision or EU project)", ("bf_funding", "eu_project")),
    (4, "two or more funding records", "repeat_funding"),
    (5, "listed in the BlueInvest investor pipeline", ("blueinvest",)),
)
# dimension -> signal types that source it; dimensions not here have no source in this radar
DIM_SOURCES = {
    "Market": ("public_contract",),
    "Financials": ("bf_funding", "public_contract"),
    "Tech": ("patent", "bf_funding", "eu_project", "blueinvest", "public_contract"),
}
DIM_NOTE = {
    "Market": "public buyers in the category", "Financials": "grants and contracts",
    "Tech": "TRL evidence classes", "Impact": "Navigator category match",
    "Deal Dynamics": "register capital events: none recorded in this radar",
}


def _types(sigs):
    out: dict[str, list] = {}
    for s in sigs:
        out.setdefault(s["signal_type"], []).append(s)
    return out


def _level(mapping, sigs, kind=None):
    t = _types(sigs)
    level, ev, why = None, [], None
    for lv, text, test in mapping:
        if test is None:
            continue
        if test == "repeat":
            hit = t.get("public_contract", []) if len(t.get("public_contract", [])) >= 2 else []
        elif test == "repeat_funding":
            f = t.get("bf_funding", []) + t.get("eu_project", [])
            hit = f if len(f) >= 2 else []
        elif isinstance(test, str):
            hit = t.get(test, [])
        else:
            hit = [s for ty in test for s in t.get(ty, [])]
        if hit:
            level, ev, why = lv, hit, text
    return {"level": level, "evidence": ev, "because": why}


def mapping_rows(mapping):
    return [{"level": lv, "rule": text} for lv, text, _ in mapping]


def whole_word(text: str, stem: str) -> str:
    """The whole word in `text` that holds the category hint `stem` ("aquacultur" -> "aquaculture"). The hints in frameworks.yaml are
    word stems, so a reader must never see one: every reason prints the word as the record spells it (D24)."""
    m = re.search(rf"\w*{re.escape(stem)}\w*", text or "")
    return m.group(0) if m else stem


def category(c: dict, sigs: list[dict]) -> dict:
    """First Navigator-style category whose keyword appears in a signal detail or the industry description. `keyword` is the whole
    word as the record spells it, not the stem hint that found it."""
    for cat, words in CATEGORIES.items():
        for s in sigs:
            text = (s.get("detail") or "").lower()
            hit = next((w for w in words if w in text), None)
            if hit:
                return {"category": cat, "keyword": whole_word(text, hit), "evidence": s["evidence"]}
        ind = (c.get("industry_desc") or "").lower()
        hit = next((w for w in words if w in ind), None)
        if hit and c.get("source_url"):
            return {"category": cat, "keyword": whole_word(ind, hit), "evidence": None, "industry": c.get("industry_desc")}
    return {"category": None, "keyword": None, "evidence": None}


def assess(c: dict, sigs: list[dict]) -> dict:
    brl, trl, irl = _level(BRL_MAP, sigs), _level(TRL_MAP, sigs), _level(IRL_MAP, sigs)
    cat = category(c, sigs)
    t = _types(sigs)
    dims = []
    for d in DIMENSIONS:
        ev = []
        if d == "Impact":
            ev = [cat["evidence"]] if cat["evidence"] else []
        elif d in DIM_SOURCES:
            ev = [s["evidence"] for ty in DIM_SOURCES[d] for s in t.get(ty, [])]
        dims.append({"name": d, "evidence": ev[:3], "n": len(ev), "note": DIM_NOTE.get(d)})
    return {"labels": LABELS, "brl": brl, "trl": trl, "irl": irl, "category": cat, "dimensions": dims, "urls": URLS,
            "brl_map": mapping_rows(BRL_MAP), "trl_map": mapping_rows(TRL_MAP), "irl_map": mapping_rows(IRL_MAP)}


# ---- connection sentence -------------------------------------------------------------------------------------
CONNECT_TYPES = ("register_entry", "bf_funding", "public_contract", "eu_project", "blueinvest", "patent")
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")
_SRC = {"register_entry": "PRH", "bf_funding": "Business Finland", "public_contract": "Hilma", "eu_project": "CORDIS",
        "blueinvest": "BlueInvest", "patent": "Espacenet"}
_PHRASE = {"register_entry": "registered in the trade register", "bf_funding": "received a Business Finland funding decision",
           "public_contract": "was awarded a public contract", "eu_project": "joined an EU project (project start)",
           "blueinvest": "was listed in the BlueInvest pipeline", "patent": "filed a patent"}


def _when(s: dict) -> str:
    if s.get("date_precision") == "year":
        return f"in {s['date'][:4]} (year only)"
    y, m = int(s["date"][:4]), int(s["date"][5:7])
    return f"in {_MONTHS[m - 1]} {y}"


def connections(sigs: list[dict]) -> list[dict] | None:
    """Clauses in date order, one per source type (its earliest signal), or None below two distinct source types."""
    by: dict[str, list] = {}
    for s in sigs:
        if s["signal_type"] in CONNECT_TYPES:
            by.setdefault(s["signal_type"], []).append(s)
    if len(by) < 2:
        return None
    clauses = []
    for ty, rows in by.items():
        first = min(rows, key=lambda s: (s["date"], s["id"]))
        extra = len(rows) - 1
        text = f"{_PHRASE[ty]} {_when(first)}"
        if ty == "public_contract" and first.get("adapter") == "hilma" and ": " in (first.get("detail") or ""):
            text = f"{_PHRASE[ty]} from {first['detail'].split(': ', 1)[0]} {_when(first)}"  # Hilma detail is "buyer: title"
        if extra:
            text += f", and {extra} more of the same type"
        clauses.append({"date": first["date"], "text": text, "source": _SRC[ty], "url": first["source_url"],
                        "type": ty})
    clauses.sort(key=lambda c: (c["date"], c["type"]))
    clauses[0]["text"] = clauses[0]["text"][0].upper() + clauses[0]["text"][1:]
    return clauses


# ---- the levels the company page prints ------------------------------------------------------------------------
def profile_trl(profile: dict) -> dict:
    """The TRL a BlueInvest profile states, in the shape _level returns, with its profile page as the evidence chip."""
    ev = {"label": "BlueInvest pipeline", "event_date": None, "date_precision": "day", "date_label": "no date stated",
          "fetched_at": profile.get("fetched_at"), "url": profile.get("url"), "confidence": None, "confidence_rule": None}
    return {"level": profile["trl"], "evidence": [{"evidence": ev}], "because": f"the BlueInvest profile states TRL {profile['trl']}"}


def page_levels(c: dict, sigs: list[dict], profile: dict | None = None) -> dict:
    """The one source of truth for readiness levels: the rule levels over the company's own records (declared research never
    sets a level), with the TRL a BlueInvest profile states. The company page (question 02), its answer line and the fund
    memo's Low / Medium / High bands all read this."""
    fw = assess(c, [x for x in sigs if x.get("adapter") != "ecosystem"])
    if profile and profile.get("trl") is not None:
        fw["trl"] = profile_trl(profile)
    return fw
