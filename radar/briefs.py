"""The AI box on each company page: "What the public record says". A batch, so no live API key and no cost at page time.

    export  facts the page already shows, one JSON per company, pure Python, no person names (radar.briefs export)
    (write) a model writes 4 to 6 plain sentences per company from that JSON, each with `cites` taken only from that export
    verify  code checks every sentence before it is stored; a failing sentence is dropped and logged, a brief left with fewer than
            MIN_SENTENCES sentences is dropped
    import  loads the verified briefs into company_briefs (radar/schema/040_briefs.sql)

Brief file: {"company_key": "...", "written": "YYYY-MM-DD", "sentences": [{"text": "...", "cites": ["https://..."]}]}.
CLI: python3 -m radar.briefs export --keys FILE --out DIR | verify --dir DIR [--exports DIR] | import --dir DIR [--exports DIR]"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

from radar import db, fit as fit_mod, frameworks, matching, store, thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
BRIEFS = ROOT / "data" / "fetched" / "briefs"
MIN_SENTENCES, MAX_SENTENCES, MAX_CHARS = 2, 6, 420
PRAISE = ("strong team", "market leader", "market-leading", "leading", "world-class", "best-in-class", "outstanding", "excellent", "impressive",
          "unicorn", "game-changing", "game changing", "revolutionary", "top-tier", "cutting-edge", "promising", "exceptional", "disrupt")
# Capitalised words a sentence may use without them appearing in the export: months, weekdays and country or area words.
GENERIC = {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December",
           "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Finland", "Finnish", "Europe", "European",
           "EU", "Nordic", "Baltic", "The", "This", "That", "These", "It", "Its", "They", "There", "No", "Not", "Public", "For", "In", "On",
           "At", "A", "An", "As", "By", "With", "From", "Since", "Only", "One", "Two", "Three", "Four", "Five", "Six", "If", "So", "But", "And"}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12}
_CAP = re.compile(r"[A-ZÅÄÖ][\w'’-]*")
_NUM = re.compile(r"\d[\d  ,.]*\d|\d")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
_MONTH_YEAR = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", re.I)
_URL = re.compile(r"https?://[^\s\"'<>)]+")


def slug(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9-]+", "_", key)


# ---- export -------------------------------------------------------------------------------------------------

def _words_flagged(text: str, allowed: set[str]) -> list[str]:
    """Capitalised words in free text that are not in the allowed vocabulary and sit next to another capitalised word: a name shape."""
    toks = list(_CAP.finditer(text or ""))
    out = []
    for a, b in zip(toks, toks[1:]):
        if b.start() - a.end() == 1 and (a.group() not in allowed or b.group() not in allowed):
            out.append(f"{a.group()} {b.group()}")
    return out


def _clean(text: str | None, allowed: set[str]) -> str | None:
    """Free text goes into the export only if no capitalised pair looks like a name; otherwise it is left out (the facts stay)."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t or _words_flagged(t, allowed):
        return None
    return t


def _titles(conn, sig_ids: list[int]) -> dict[int, str]:
    out: dict[int, str] = {}
    for i in range(0, len(sig_ids), 500):
        chunk = sig_ids[i:i + 500]
        try:
            for r in conn.execute(f"SELECT signal_id, text FROM signal_text WHERE field='title' AND signal_id IN ({','.join('?' * len(chunk))})", chunk):
                out[r[0]] = r[1]
        except sqlite3.OperationalError:
            break
    return out


def export_one(conn: sqlite3.Connection, thesis: dict, key: str, *, today=None) -> dict | None:
    """The facts the company page shows, for one company, with every URL a sentence may cite. None when the company is unknown."""
    from radar import memo as memo_mod
    ctx = matching.company_context(conn, key)
    if ctx is None:
        return None
    c, sigs = ctx["c"], ctx["sigs"]
    own_name_words = set(_CAP.findall(c["name"]))
    allowed = set(GENERIC) | own_name_words | {"Oy", "Oyj", "Ab", "Ltd"}
    titles = _titles(conn, [s["id"] for s in sigs])
    fw = ctx["fw"]
    nxt = matching.who_comes_next(key, thesis, 5, conn=conn, today=today)
    for lst in nxt.values():
        for r in lst:
            allowed |= set(_CAP.findall(r["name"]))
    signals = []
    for n, s in enumerate(sigs, 1):
        title = titles.get(s["id"])
        if s["signal_type"] == "public_contract":
            title = title or store._title_part(s.get("detail"))
        signals.append({"ref": f"S{n}", "type": s["signal_type"], "type_label": s["type_label"], "date": s["date"], "date_label": s.get("date_label") or s["date"],
                        "source_url": s["source_url"], "source_label": s["evidence"]["label"], "confidence": s["confidence"], "adapter": s["adapter"],
                        "title": _clean(title, allowed), "note": _clean(re.sub(r"\s*\[[^\]]*\]\s*$", "", s.get("detail") or ""), allowed),
                        "amount_eur": s.get("amount_eur")})
    levels = {}
    for dim, k, label in (("technology", "trl", "Technology readiness level (Aalto TRL, 1-9)"), ("business", "brl", "Business readiness level (KTH BRL, 1-9)"),
                          ("investment", "irl", "Investment readiness level (1-9)")):
        lv = fw[k]
        ev = lv["evidence"]
        levels[dim] = {"label": label, "level": lv["level"], "rule": lv["because"],
                       "url": max(ev, key=lambda x: x["date"])["source_url"] if ev else None}
    if ctx["trl"] is not None and ctx["trl_src"] != "register rule":
        levels["technology"] = {**levels["technology"], "level": ctx["trl"], "rule": f"stated by the {ctx['trl_src']}"}
    cat = fw["category"]
    levels["impact_category"] = {"category": cat.get("category"), "keyword": cat.get("keyword"),
                                 "url": (cat.get("evidence") or {}).get("url") or (c.get("source_url") if cat.get("category") else None)}
    reasons = [{"text": _clean(r["text"], allowed), "confidence": r["confidence"], "url": (r.get("evidence") or {}).get("url")}
               for r in fit_mod.fit(c, sigs, thesis) if (r.get("evidence") or {}).get("url") and _clean(r["text"], allowed)]
    m = memo_mod.build(conn, thesis, key, today=today)
    memo = None
    if m:
        rec = m["recommendation"]
        memo = {"decision": rec["decision"], "matched": rec.get("matched"), "because": rec["because"], "note": rec.get("note"),
                "why": [{"text": _clean(w["text"], allowed), "url": w["url"]} for w in m["why"] if _clean(w["text"], allowed)],
                "risks": [{"text": _clean(w["text"], allowed), "url": w["url"]} for w in m["risks"] if _clean(w["text"], allowed)],
                "actions": [{"text": _clean(w["text"], allowed), "url": w["url"]} for w in m["actions"] if _clean(w["text"], allowed)]}
    next_names = {k: [{"name": r["name"], "kind": r["kind"], "reason": _clean(r["reason"], allowed), "url": r["source_url"]} for r in v] for k, v in nxt.items()}
    by_type: dict[str, int] = {}
    for s in sigs:
        by_type[s["signal_type"]] = by_type.get(s["signal_type"], 0) + 1
    exp = {"company_key": key, "name": c["name"], "business_id": c.get("y_tunnus"), "founded": c.get("founded"), "country": c.get("country"),
           "group": c["group_tag"], "register_status": c.get("register_status"),
           "industry": {"code": c.get("industry_code"), "description": c.get("industry_desc")}, "company_url": c.get("source_url"),
           "signals": signals, "levels": levels, "fit_reasons": reasons, "memo": memo, "next": next_names,
           "counts": {"signals": len(sigs), "by_type": by_type, **{f"next_{k}": len(v) for k, v in nxt.items()}},
           "exported": (today.isoformat() if hasattr(today, "isoformat") else str(today or date.today().isoformat()))}
    exp["urls"] = sorted({u for u in _URL.findall(json.dumps(exp)) if u})
    return exp


def export(conn: sqlite3.Connection, thesis: dict, keys: list[str], *, today=None) -> list[dict]:
    return [e for e in (export_one(conn, thesis, k, today=today) for k in keys) if e]


# ---- verify -------------------------------------------------------------------------------------------------

def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, float) and obj.is_integer():
        yield str(int(obj))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield str(obj)


class Facts:
    """What a sentence may rely on: URLs, numbers, dates and capitalised words of one company's export."""

    def __init__(self, exp: dict):
        self.exp = exp
        self.urls = set(exp.get("urls") or [])
        blob = "\n".join(_strings({k: v for k, v in exp.items() if k != "urls"}))
        self.blob = blob.casefold()
        self.dates = set(_ISO.findall(blob))
        self.iso = {"-".join(d) for d in self.dates}
        self.months = {(y, m) for y, m, _ in self.dates}
        self.numbers = {re.sub(r"\D", "", n) for n in _NUM.findall(blob)}
        self.numbers |= {str(int(x)) for x in self.numbers if x}
        self.counts = {v for v in _count_values(exp.get("counts") or {})}
        self.caps = set(_CAP.findall("\n".join(_strings({k: v for k, v in exp.items() if k != "urls"})))) | GENERIC
        self.cited_text = {s["source_url"]: ((s.get("title") or "") + " " + (s.get("note") or "")).casefold() for s in exp.get("signals", [])}


def _count_values(d) -> list[int]:
    out = []
    for v in d.values():
        if isinstance(v, dict):
            out += _count_values(v)
        elif isinstance(v, int):
            out.append(v)
    return out


def verify_sentence(sent: dict, facts: Facts, thesis: dict | None = None) -> str | None:
    """None when the sentence passes, else the reason it fails."""
    text, cites = (sent.get("text") or "").strip(), sent.get("cites") or []
    if not text:
        return "empty sentence"
    if len(text) > MAX_CHARS:
        return f"longer than {MAX_CHARS} characters"
    if not cites:
        return "no cited url"
    foreign = [u for u in cites if u not in facts.urls]
    if foreign:
        return f"cited url not in the export: {foreign[0]}"
    text_wo_urls = _URL.sub(" ", text)
    for y, m, d in _ISO.findall(text_wo_urls):
        if f"{y}-{m}-{d}" not in facts.iso:
            return f"date not in the export: {y}-{m}-{d}"
    stripped = _ISO.sub(" ", text_wo_urls)
    for mname, y in _MONTH_YEAR.findall(stripped):
        if (y, f"{_MONTHS[mname.lower()]:02d}") not in facts.months:
            return f"month not in the export: {mname} {y}"
    stripped = _MONTH_YEAR.sub(lambda m: f" {m.group(2)} ", stripped)
    for n in _NUM.findall(stripped):
        digits = re.sub(r"\D", "", n)
        if digits and digits not in facts.numbers and str(int(digits)) not in facts.numbers:
            return f"number not in the export: {n.strip()}"
    for w, v in NUMBER_WORDS.items():
        if re.search(rf"\b{w}\b", text, re.I) and v not in facts.counts and str(v) not in facts.numbers:
            return f"number word not supported by the export: {w}"
    low = text.casefold()
    cited_titles = " ".join(facts.cited_text.get(u, "") for u in cites)
    for p in PRAISE:
        if re.search(rf"\b{re.escape(p)}", low) and p not in cited_titles:
            return f"praise without a source title: {p}"
    toks = list(_CAP.finditer(text_wo_urls))
    for i, t in enumerate(toks):
        w = t.group()
        first = not text_wo_urls[:t.start()].strip() or text_wo_urls[:t.start()].rstrip().endswith((".", "!", "?", ":"))
        if w not in facts.caps and not w.isupper() and not first:
            return f"capitalised word not in the export (possible name): {w}"
    for a, b in zip(toks, toks[1:]):
        if b.start() - a.end() == 1:
            if thesis is not None and (a.group() not in facts.caps or b.group() not in facts.caps) and a.group() not in GENERIC and b.group() not in GENERIC \
                    and fit_mod.looks_like_person(f"{a.group()} {b.group()} Holding Oy", thesis):
                return f"person-shaped name: {a.group()} {b.group()}"
            if a.group() not in facts.caps or b.group() not in facts.caps:
                return f"person-shaped name: {a.group()} {b.group()}"
    return None


def verify_brief(brief: dict, exp: dict, thesis: dict | None = None) -> tuple[dict | None, list[dict]]:
    """(cleaned brief or None, drops [{sentence, reason}]). A brief with fewer than MIN_SENTENCES passing sentences is dropped."""
    facts = Facts(exp)
    keep, drops = [], []
    for s in (brief.get("sentences") or [])[:MAX_SENTENCES + 4]:
        why = verify_sentence(s, facts, thesis)
        if why:
            drops.append({"sentence": s.get("text"), "reason": why})
        else:
            keep.append({"text": s["text"].strip(), "cites": list(dict.fromkeys(s["cites"]))})
    keep = keep[:MAX_SENTENCES]
    if len(keep) < MIN_SENTENCES:
        drops.append({"sentence": None, "reason": f"brief dropped: {len(keep)} passing sentence(s), minimum {MIN_SENTENCES}"})
        return None, drops
    return {"company_key": brief["company_key"], "written": brief.get("written"), "sentences": keep}, drops


# ---- store and read -----------------------------------------------------------------------------------------

def store_brief(conn: sqlite3.Connection, brief: dict) -> None:
    conn.execute("INSERT OR REPLACE INTO company_briefs (company_key, written, sentences_json, imported_at) VALUES (?,?,?,datetime('now'))",
                 (brief["company_key"], brief.get("written") or date.today().isoformat(), json.dumps(brief["sentences"], ensure_ascii=False)))


def brief_for(company_key: str, thesis: dict) -> dict | None:
    """Template hook: the stored brief with numbered cites, or None ("No summary yet")."""
    conn = store.open_db(thesis=thesis)
    if conn is None:
        return None
    try:
        row = conn.execute("SELECT written, sentences_json FROM company_briefs WHERE company_key=?", (company_key,)).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    if row is None:
        return None
    order: list[str] = []
    sents = []
    for s in json.loads(row[1]):
        nums = []
        for u in s["cites"]:
            if u not in order:
                order.append(u)
            nums.append({"n": order.index(u) + 1, "url": u})
        sents.append({"text": s["text"], "cites": nums})
    return {"written": row[0], "sentences": sents}


# ---- CLI ----------------------------------------------------------------------------------------------------

def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def run_dir(dir_out: Path, dir_in: Path, thesis: dict, *, conn=None, log=print) -> dict:
    """Verify every brief in dir_out against its export in dir_in; store the survivors when conn is given."""
    res = {"briefs": 0, "kept": 0, "dropped_briefs": 0, "dropped_sentences": 0, "reasons": {}}
    for p in sorted(Path(dir_out).glob("*.json")):
        res["briefs"] += 1
        b = _load(p)
        ep = Path(dir_in) / f"{slug(b['company_key'])}.json"
        if not ep.is_file():
            log(f"DROP brief {b['company_key']}: no export {ep.name}")
            res["dropped_briefs"] += 1
            res["reasons"]["no export"] = res["reasons"].get("no export", 0) + 1
            continue
        clean, drops = verify_brief(b, _load(ep), thesis)
        for d in drops:
            kind = d["reason"].split(":")[0]
            res["reasons"][kind] = res["reasons"].get(kind, 0) + 1
            if d["sentence"] is not None:
                res["dropped_sentences"] += 1
            log(f"DROP {b['company_key']}: {d['reason']}" + (f" | {d['sentence']}" if d["sentence"] else ""))
        if clean is None:
            res["dropped_briefs"] += 1
            continue
        res["kept"] += 1
        if conn is not None:
            store_brief(conn, clean)
    if conn is not None:
        conn.commit()
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.briefs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--keys", required=True, help="file with one company key per line, or 'all'")
    e.add_argument("--out", default=str(BRIEFS / "in"))
    e.add_argument("--thesis")
    for name in ("verify", "import"):
        v = sub.add_parser(name)
        v.add_argument("--dir", default=str(BRIEFS / "out"))
        v.add_argument("--exports", default=str(BRIEFS / "in"))
        v.add_argument("--thesis")
    a = ap.parse_args(argv)
    th = thesis_mod.load(thesis_mod.available().get(a.thesis, a.thesis)) if a.thesis else thesis_mod.load()
    if a.cmd == "export":
        conn = store.open_db(thesis=th)
        if conn is None:
            print(store.empty_state_text(th))
            return 1
        keys = [r[0] for r in conn.execute("SELECT company_key FROM companies ORDER BY company_key")] if a.keys == "all" else \
            [k.strip() for k in Path(a.keys).read_text().splitlines() if k.strip()]
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        n = 0
        for exp in export(conn, th, keys):
            (out / f"{slug(exp['company_key'])}.json").write_text(json.dumps(exp, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
        print(f"exported {n} of {len(keys)} companies to {out}")
        return 0
    conn = db.connect(thesis_mod.db_path(th)) if a.cmd == "import" else None
    res = run_dir(Path(a.dir), Path(a.exports), th, conn=conn)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
