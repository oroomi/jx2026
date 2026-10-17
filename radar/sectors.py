"""Sector taxonomy for one store (D42): which sub-sectors of the thesis' top-level sector a company belongs to, and why.

The taxonomy lives in the `taxonomy:` block of the thesis file (top-level sector, sub-sectors, code prefixes, keyword groups, impact areas, word sets
and the evidence kinds each sub-sector accepts); this module applies it and holds no sector word. A company can have several sub-sectors. Every link
stores its basis (the evidence kind) and the public page it rests on, so a page can say "Shipbuilding and boats, because industry code 30120 (PRH/YTJ
register)". Links are written to `company_sector` (radar/schema/062_sector.sql) by

    python3 -m radar.sectors backfill --db <store.sqlite> [--thesis <id>] [--dry-run]

The backfill is idempotent: it rebuilds every link from the stored records and keeps the `assigned_at` of a link that is still there.

Evidence kinds (the `basis` column):
  code               the industry code starts with one of the sub-sector's `code_prefixes` (a dot is ignored). A gated code (`gated_codes`) counts only
                     together with a word of a named word set in the company's own text, or in a corroborated name word; it never classifies alone.
  own_text           a word of the sub-sector in the company's own text: the registered line of business, the CORDIS title and objective, the BlueInvest
                     profile, a quote the stitcher checked on a page, the verified brief. Our own `detail` annotations are never read (D2).
  name_corroborated  a word in the legal name AND a record from a different source family (A6); a name word alone classifies nothing (A5).
  declared           the declared ecosystem dataset's capability, or a declared list's category, mapped in the thesis' `taxonomy.declared`.
  notice             a word of the sub-sector in the title of a public procurement notice the company won.
A company with no link at all is "Not yet classified": derived when a page reads the links, never stored as a link."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from radar import db as db_mod, fit as fit_mod, labels as lbl, store
from radar import thesis as thesis_mod
from radar.emit import now_utc

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = db_mod.SCHEMA_DIR / "062_sector.sql"
KINDS = thesis_mod.TAXONOMY_KINDS
_QUOTE = re.compile(r'^"(.+?)"\s*\(')
_SPACE = re.compile(r"\s+")


# ---- the model: the thesis block, resolved -------------------------------------------------------------------------------------
class Matcher:
    """One compiled word list under the project's word rule (A8): a word matches whole, or as the start of a longer word when it has
    5 or more characters. A stop word never matches. hit() returns the word as the text uses it, or None."""

    def __init__(self, words, stop: set[str]):
        uniq = list(dict.fromkeys(str(w).casefold().strip() for w in words if str(w).strip()))
        parts = sorted((re.escape(w) + ("" if len(w) >= fit_mod.MIN_PREFIX else r"(?!\w)") for w in uniq), key=len, reverse=True)
        self.rx = re.compile(r"(?<!\w)(?:" + "|".join(parts) + ")") if parts else None
        self.stop = stop

    def hit(self, text: str | None) -> str | None:
        if not self.rx or not text:
            return None
        t = _SPACE.sub(" ", text.casefold())
        for m in self.rx.finditer(t):
            token = re.match(r"\w+", t[m.start():])
            if token and token.group() in self.stop:
                continue
            end = m.end()
            while end < len(t) and (t[end].isalnum() or t[end] == "_"):
                end += 1  # a word-start match is shown as the whole word the text uses
            return t[m.start():end]
        return None


class Sub:
    """One sub-sector, resolved: its code prefixes, its word matcher, its gated codes and what it maps from the declared sources."""

    def __init__(self, spec: dict, groups: dict, areas: dict, word_sets: dict, stop: set[str]):
        self.slug, self.label = spec["slug"], spec["label"]
        self.evidence = list(spec["evidence"])
        codes = [str(p).replace(".", "").strip() for p in spec.get("code_prefixes") or []]
        words = list(spec.get("words") or [])
        for g in spec.get("keyword_groups") or []:
            words += groups[g].get("stems") or []
        for a in spec.get("impact_areas") or []:
            words += areas[a].get("words") or []
            codes += [str(p).replace(".", "").strip() for p in areas[a].get("code_prefixes") or []]
        drop = {str(w).casefold().strip() for w in spec.get("drop_words") or []}  # a stem of a referenced group or area this sub-sector does not take
        words = [w for w in words if str(w).casefold().strip() not in drop]
        self.codes = list(dict.fromkeys(c for c in codes if c))
        self.words = Matcher(words, stop)
        self.gates = []
        for g in spec.get("gated_codes") or []:
            gw = [w for n in g["needs"] for w in (words if n == "self" else (word_sets[n].get("words") or []))]
            self.gates.append(([str(p).replace(".", "").strip() for p in g["prefixes"]], Matcher(gw, stop), list(g.get("kinds") or ["own_text"])))
        d = spec.get("declared") or {}
        self.caps = {str(c).strip() for c in d.get("capabilities") or []}
        self.categories = {str(c).casefold().strip() for c in d.get("categories") or []}


class Model:
    def __init__(self, thesis: dict):
        tx = thesis["taxonomy"]
        self.slug, self.label = tx["slug"], tx["label"]
        self.unclassified = _unclassified(tx)
        stop = fit_mod.stop_words(thesis)
        groups = {g["id"]: g for g in (tx.get("keyword_groups") or []) + ((thesis.get("matching") or {}).get("keyword_groups") or [])}
        areas = (thesis.get("impact_readiness") or {}).get("areas") or {}
        word_sets = tx.get("word_sets") or {}
        self.subs = [Sub(s, groups, areas, word_sets, stop) for s in tx["sectors"]]
        self.declared = tx.get("declared") or {}
        self.thesis_id = thesis.get("id")

    def by_slug(self) -> dict:
        return {s.slug: s for s in self.subs}


def _block(thesis: dict) -> dict | None:
    """The thesis' `taxonomy:` block, or None when it defines none (an empty list or mapping)."""
    tx = thesis.get("taxonomy")
    return tx if isinstance(tx, dict) and tx.get("sectors") else None


def model(thesis: dict) -> Model | None:
    """The resolved taxonomy of a thesis, or None when the thesis defines none (an empty block): the facet then hides."""
    return Model(thesis) if _block(thesis) else None


def _unclassified(tx: dict) -> dict:
    u = tx.get("unclassified") or {}
    return {"slug": u.get("slug") or "not_classified", "label": u.get("label") or "Not yet classified"}


# ---- the records a store holds about its companies ------------------------------------------------------------------------------
def _rows(conn, sql: str, args=()) -> list[sqlite3.Row]:
    cur = conn.cursor()
    cur.row_factory = sqlite3.Row
    try:
        return cur.execute(sql, args).fetchall()
    except sqlite3.OperationalError:  # a table this store does not have: no records of that kind
        return []


def _path(p: str | None) -> Path | None:
    if not p:
        return None
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def _eco_capabilities(path: Path | None) -> tuple[dict[str, set[str]], dict[str, str]]:
    """({entity id: capability codes}, {code: label}) from the declared ecosystem dataset (read only); empty when the file is missing."""
    if not path or not path.is_file():
        return {}, {}
    eco = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        caps: dict[str, set[str]] = {}
        for eid, code in eco.execute("SELECT entity_id, code FROM entity_capability"):
            caps.setdefault(eid, set()).add(code)
        return caps, dict(eco.execute("SELECT code, label FROM capability"))
    except sqlite3.OperationalError:
        return {}, {}
    finally:
        eco.close()


def _declared_lists(M: Model) -> dict[str, list[dict]]:
    """{company key: [{category, url, label}]} from the declared lists named in the thesis, rows that carry a company id and a link."""
    out: dict[str, list[dict]] = {}
    for spec in M.declared.get("lists") or []:
        f = _path(spec.get("file"))
        if not f or not f.is_file():
            continue
        with f.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                key, cat, url = (r.get(spec.get("id_column") or "") or "").strip(), (r.get(spec.get("category_column") or "") or "").strip(), (r.get(spec.get("url_column") or "") or "").strip()
                if key and cat and url.startswith("http"):
                    out.setdefault(key, []).append({"category": cat, "url": url, "label": spec.get("label") or f.name})
    return out


class Records:
    """Everything the links are derived from, read once per store (not once per company)."""

    def __init__(self, conn, M: Model):
        self.companies = _rows(conn, "SELECT company_key, name, country, industry_code, industry_desc, source_url FROM companies ORDER BY company_key")
        not_independent = sorted({*store.SOURCE_FAMILIES, "ecosystem"})
        mark = ",".join("?" * len(not_independent))
        # A6: the company's own register(s) (the adapters of its register entries) and the PRH family never back a name word; any other family does.
        self.reg: dict[str, list[str]] = {}
        for r in _rows(conn, "SELECT company_key, adapter FROM signals WHERE signal_type = 'register_entry' ORDER BY date, id"):
            self.reg.setdefault(r["company_key"], [])
            if r["adapter"] not in self.reg[r["company_key"]]:
                self.reg[r["company_key"]].append(r["adapter"])
        self.backers: dict[str, list[tuple]] = {}
        for r in _rows(conn, f"SELECT company_key, adapter, date FROM signals WHERE adapter NOT IN ({mark}) ORDER BY date, id", not_independent):
            self.backers.setdefault(r["company_key"], []).append((r["adapter"], r["date"]))
        self.texts: dict[str, list[dict]] = {}
        self._signal_texts(conn)
        self._profiles(conn)
        self._briefs(conn)
        caps, self.cap_label = _eco_capabilities(_path(M.declared.get("ecosystem_db")))
        self.eco: dict[str, dict] = {}
        for r in _rows(conn, "SELECT entity_id, company_key, source_url, website FROM eco_entity WHERE company_key IS NOT NULL"):
            url = r["source_url"] or r["website"] or ""
            if r["entity_id"] in caps and url.startswith("http"):
                self.eco[r["company_key"]] = {"caps": caps[r["entity_id"]], "url": url}
        self.lists = _declared_lists(M)

    def _add(self, key: str, kind: str, text: str | None, url: str | None, label: str) -> None:
        if text and text.strip() and url and url.startswith("http"):
            self.texts.setdefault(key, []).append({"kind": kind, "text": text, "url": url, "label": label})

    def _signal_texts(self, conn) -> None:
        sigs = _rows(conn, "SELECT id, company_key, adapter, signal_type, date, source_url, detail FROM signals "
                           "WHERE signal_type IN ('eu_project', 'public_contract') OR adapter = 'stitcher'")
        own = store.source_texts(conn, [dict(s) for s in sigs if s["signal_type"] == "eu_project"])
        for s in sigs:
            if s["signal_type"] == "public_contract":
                self._add(s["company_key"], "notice", store._title_part(s["detail"]), s["source_url"], f"{lbl.source_label(s['adapter'], s['source_url'])} of {s['date']}")
            elif s["signal_type"] == "eu_project":
                self._add(s["company_key"], "own_text", " . ".join(own.get(s["id"], [])), s["source_url"], f"{lbl.source_label(s['adapter'], s['source_url'])} project title and objective")
            else:  # a quote the stitcher checked on a page: the page's own words
                m = _QUOTE.match(s["detail"] or "")
                self._add(s["company_key"], "own_text", m.group(1) if m else None, s["source_url"], f"{lbl.source_label('stitcher')} quote from a page")

    def _profiles(self, conn) -> None:
        for r in _rows(conn, "SELECT company_key, title, description, sector, url FROM blueinvest_profiles WHERE company_key IS NOT NULL"):
            self._add(r["company_key"], "own_text", " . ".join(t for t in (r["title"], r["description"], r["sector"]) if t), r["url"], "BlueInvest pipeline profile text")

    def _briefs(self, conn) -> None:
        for r in _rows(conn, "SELECT company_key, sentences_json FROM company_briefs"):
            try:
                for s in json.loads(r["sentences_json"]):
                    self._add(r["company_key"], "own_text", s.get("text"), (s.get("cites") or [None])[0], "Verified brief")
            except (ValueError, TypeError, AttributeError):
                continue
        for r in _rows(conn, "SELECT company_key, slots_json FROM company_brief_slots"):
            try:
                slot = (json.loads(r["slots_json"]) or {}).get("what_it_does") or {}
                self._add(r["company_key"], "own_text", slot.get("text"), (slot.get("cites") or [None])[0], "Verified brief (what it does)")
            except (ValueError, TypeError, AttributeError):
                continue


# ---- the links ------------------------------------------------------------------------------------------------------------------
def _norm_code(code: str | None) -> str:
    return re.sub(r"[\s.]", "", code or "")


def links_for(c, rec: Records, M: Model) -> list[dict]:
    """Every (sub-sector, basis) link of one company, in taxonomy order, each with the page it rests on. Pure: reads only `rec` and the thesis model."""
    key, name, code, desc, reg_url = c["company_key"], c["name"] or "", _norm_code(c["industry_code"]), (c["industry_desc"] or "").strip(), c["source_url"]
    own_regs = rec.reg.get(key, [])
    reg = lbl.source_label(own_regs[0] if own_regs else "prh", reg_url)
    cands = [{"kind": "own_text", "text": desc, "url": reg_url, "label": f"{reg}: registered line of business"}] if desc else []
    cands += rec.texts.get(key, [])
    backer = next((b for b in rec.backers.get(key, []) if b[0] not in own_regs), None)
    out: list[dict] = []
    seen: set[tuple] = set()

    def add(sub: Sub, basis: str, url: str, label: str) -> None:
        if (sub.slug, basis) not in seen and url:
            seen.add((sub.slug, basis))
            out.append({"company_key": key, "sector": sub.slug, "basis": basis, "source_url": url, "source_label": label})

    for sub in M.subs:
        shown = f"{code} ({desc})" if desc else code
        for prefixes, gate, kinds in sub.gates:  # a gated code first: its label is the richer one when a plain word hit would give the same link
            if not code or not any(code.startswith(p) for p in prefixes):
                continue
            for kind in kinds:
                if kind == "own_text":
                    for cand in (x for x in cands if x["kind"] == "own_text"):
                        w = gate.hit(cand["text"])
                        if w:
                            add(sub, "own_text", cand["url"], f"{cand['label']} names '{w}', with industry code {shown}")
                            break
                elif kind == "name_corroborated" and backer:
                    w = gate.hit(name)
                    if w:
                        add(sub, "name_corroborated", reg_url, f"{reg}: legal name holds '{w}', backed by a {lbl.source_label(backer[0])} record of {backer[1]}, with industry code {shown}")
        if "code" in sub.evidence and code:
            p = next((p for p in sub.codes if code.startswith(p)), None)
            if p:
                add(sub, "code", reg_url, f"{reg}: industry code {shown} is in the family {p}")
        for kind in ("own_text", "notice"):
            if kind in sub.evidence:
                for cand in (x for x in cands if x["kind"] == kind):
                    w = sub.words.hit(cand["text"])
                    if w:
                        add(sub, kind, cand["url"], f"{cand['label']} names '{w}'")
                        break
        if "name_corroborated" in sub.evidence and backer:
            w = sub.words.hit(name)
            if w:
                add(sub, "name_corroborated", reg_url, f"{reg}: legal name holds '{w}', backed by a {lbl.source_label(backer[0])} record of {backer[1]}")
        if "declared" in sub.evidence:
            eco = rec.eco.get(key)
            shared = sorted(sub.caps & eco["caps"]) if eco else []
            if shared:
                add(sub, "declared", eco["url"], f"Declared research dataset: capability {shared[0]}, {rec.cap_label.get(shared[0], 'as declared')}")
            else:
                row = next((r for r in rec.lists.get(key, []) if r["category"].casefold() in sub.categories), None)
                if row:
                    add(sub, "declared", row["url"], f"{row['label']}: category '{row['category']}'")
    return out


def compute(conn, thesis: dict) -> dict:
    """The links of every company of the store, without writing: {"links": [...], "companies": n, "keys": [all company keys]}."""
    M = model(thesis)
    if M is None:
        return {"links": [], "companies": 0, "keys": []}
    rec = Records(conn, M)
    links = [ln for c in rec.companies for ln in links_for(c, rec, M)]
    return {"links": links, "companies": len(rec.companies), "keys": [c["company_key"] for c in rec.companies]}


def summarise(res: dict, M: Model) -> dict:
    """Counts: companies per sub-sector, links per basis, and how many companies got 0, 1 or 2+ sub-sectors."""
    per = {s.slug: set() for s in M.subs}
    basis = Counter()
    for ln in res["links"]:
        per[ln["sector"]].add(ln["company_key"])
        basis[ln["basis"]] += 1
    n_by_company = Counter()
    for slug, keys in per.items():
        for k in keys:
            n_by_company[k] += 1
    zero = res["companies"] - len(n_by_company)
    one = sum(1 for v in n_by_company.values() if v == 1)
    return {"companies": res["companies"], "links": len(res["links"]), "per_sector": {s.slug: len(per[s.slug]) for s in M.subs},
            "labels": {s.slug: s.label for s in M.subs}, "by_basis": dict(basis),
            "sub_sectors_per_company": {"0": zero, "1": one, "2+": len(n_by_company) - one}}


# ---- writing --------------------------------------------------------------------------------------------------------------------
def ensure_schema(conn) -> None:
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))


def assign(conn, thesis: dict, *, write: bool = True) -> dict:
    """Derive every company's sub-sector links from the stored records and the thesis' taxonomy; with write=True rebuild the `company_sector`
    table (and the `sector` rows) from them, idempotently. Returns the summary (counts per sub-sector and basis, companies with 0, 1, 2+)."""
    M = model(thesis)
    if M is None:
        return {"companies": 0, "links": 0, "per_sector": {}, "labels": {}, "by_basis": {}, "sub_sectors_per_company": {"0": 0, "1": 0, "2+": 0}, "taxonomy": False}
    res = compute(conn, thesis)
    summary = summarise(res, M) | {"taxonomy": True}
    if not write:
        return summary
    ensure_schema(conn)
    at = now_utc()
    old = {(r[0], r[1], r[2]): r[3] for r in conn.execute("SELECT company_key, s.slug, basis, assigned_at FROM company_sector JOIN sector s ON s.id = sector_id")}
    with conn:
        conn.execute("DELETE FROM company_sector")
        conn.execute("INSERT INTO sector (slug, label, parent_id) VALUES (?, ?, NULL) ON CONFLICT(slug) DO UPDATE SET label = excluded.label, parent_id = NULL", (M.slug, M.label))
        top = conn.execute("SELECT id FROM sector WHERE slug = ?", (M.slug,)).fetchone()[0]
        for slug, label in [(s.slug, s.label) for s in M.subs] + [(M.unclassified["slug"], M.unclassified["label"])]:
            conn.execute("INSERT INTO sector (slug, label, parent_id) VALUES (?, ?, ?) ON CONFLICT(slug) DO UPDATE SET label = excluded.label, parent_id = excluded.parent_id", (slug, label, top))
        keep = [M.slug, M.unclassified["slug"], *(s.slug for s in M.subs)]
        conn.execute(f"DELETE FROM sector WHERE slug NOT IN ({','.join('?' * len(keep))})", keep)
        ids = dict(conn.execute("SELECT slug, id FROM sector"))
        conn.executemany("INSERT INTO company_sector (company_key, sector_id, basis, source_url, source_label, assigned_at) VALUES (?,?,?,?,?,?)",
                         [(ln["company_key"], ids[ln["sector"]], ln["basis"], ln["source_url"], ln["source_label"],
                           old.get((ln["company_key"], ln["sector"], ln["basis"]), at)) for ln in res["links"]])
    return summary


# ---- reading the links back (home rows, the API, the combined file) -------------------------------------------------------------
def backfilled(conn) -> bool:
    """True when the store's sector tables exist and the backfill has run on it (the `sector` table holds the taxonomy)."""
    return bool(_rows(conn, "SELECT 1 FROM sector LIMIT 1"))


def _read(conn, key: str | None = None) -> dict[str, list[dict]]:
    sql = ("SELECT cs.company_key, s.slug, s.label, p.slug AS parent_slug, p.label AS parent_label, cs.basis, cs.source_url, cs.source_label "
           "FROM company_sector cs JOIN sector s ON s.id = cs.sector_id LEFT JOIN sector p ON p.id = s.parent_id")
    rows = _rows(conn, sql + (" WHERE cs.company_key = ?" if key else "") + " ORDER BY cs.company_key, s.id, cs.basis", (key,) if key else ())
    out: dict[str, list[dict]] = {}
    for r in rows:
        subs = out.setdefault(r["company_key"], [])
        item = next((x for x in subs if x["slug"] == r["slug"]), None)
        if item is None:
            item = {"slug": r["slug"], "label": r["label"], "parent": {"slug": r["parent_slug"], "label": r["parent_label"]}, "evidence": []}
            subs.append(item)
        item["evidence"].append({"basis": r["basis"], "source_url": r["source_url"], "source_label": r["source_label"]})
    return out


def company_subsectors(conn, thesis: dict, key: str) -> list[dict]:
    """The sub-sectors of one company with the evidence of each: [{slug, label, parent, evidence: [{basis, source_url, source_label}]}].
    A company the backfill classified nowhere reads "Not yet classified" with no evidence; a store not backfilled, or a thesis without a taxonomy, gives []."""
    tx = _block(thesis)
    if tx is None or not backfilled(conn):
        return []
    found = _read(conn, key).get(key)
    return found or [{**_unclassified(tx), "parent": {"slug": tx["slug"], "label": tx["label"]}, "evidence": []}]


def home_map(conn, thesis: dict) -> dict[str, list[dict]] | None:
    """{company key: [{slug, label, basis: [...]}]} for every company with a link, for the home list's row builder; None when the thesis has no
    taxonomy or the store is not backfilled (rows then carry no sub-sectors and the facet hides)."""
    if _block(thesis) is None or not backfilled(conn):
        return None
    return {k: [{"slug": s["slug"], "label": s["label"], "basis": [e["basis"] for e in s["evidence"]]} for s in subs] for k, subs in _read(conn).items()}


def row_subsectors(smap: dict | None, thesis: dict, key: str) -> list[dict]:
    """One home row's sub-sectors from home_map(); a company with no link reads "Not yet classified"."""
    if smap is None:
        return []
    return smap.get(key) or [{**_unclassified(thesis["taxonomy"]), "basis": []}]


# ---- command line -----------------------------------------------------------------------------------------------------------------
def _thesis_for(db_path: Path, arg: str | None) -> dict:
    av = thesis_mod.available()
    if arg:
        return thesis_mod.load(av[arg] if arg in av else arg)
    stem = db_path.stem.removeprefix("radar_")
    for tid, p in av.items():
        if re.sub(r"[^a-z0-9_]", "", tid.lower()) == stem:
            return thesis_mod.load(p)
    return thesis_mod.load()


def report(s: dict, title: str) -> str:
    lines = [title, f"companies {s['companies']}, links {s['links']}"]
    w = max([len(v) for v in s["labels"].values()] + [10])
    for slug, n in s["per_sector"].items():
        lines.append(f"  {s['labels'][slug].ljust(w)}  {n}")
    lines.append("links by basis: " + (", ".join(f"{k} {v}" for k, v in sorted(s["by_basis"].items())) or "none"))
    c = s["sub_sectors_per_company"]
    lines.append(f"companies with 0 sub-sectors (Not yet classified) {c['0']}, 1 {c['1']}, 2 or more {c['2+']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.sectors")
    sub = ap.add_subparsers(dest="cmd", required=True)
    bf = sub.add_parser("backfill", help="derive every company's sub-sector links from the stored records and the thesis' taxonomy")
    bf.add_argument("--db", required=True, help="the store (a data/radar_<thesis id>.sqlite file)")
    bf.add_argument("--thesis", help="thesis id or yaml path (default: the thesis the file name belongs to, else config/thesis.yaml)")
    bf.add_argument("--dry-run", action="store_true", help="count only; the store is opened read-only and nothing is written")
    args = ap.parse_args(argv)
    path = Path(args.db)
    if not path.is_file():
        print(f"no store at {path}", file=sys.stderr)
        return 2
    th = _thesis_for(path, args.thesis)
    if model(th) is None:
        print(f"thesis {th['id']} defines no taxonomy: nothing to do")
        return 0
    if args.dry_run:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        conn = db_mod.connect(path)
    try:
        s = assign(conn, th, write=not args.dry_run)
    finally:
        conn.close()
    print(report(s, f"thesis {th['id']}, store {path}" + (" (dry run, nothing written)" if args.dry_run else "")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
