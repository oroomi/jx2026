"""Restore company names the person-name redactor hid by mistake (D23), in a store that already holds redacted text.

  python3 -m radar.repair_redaction --db data/radar_redstone_apelago_blue.sqlite [--dry-run]

Where the text is stored:   stitch_log.query / quote / reason, signals.detail (adapter stitcher), company_brief_slots.slots_json,
                            company_briefs.sentences_json, signal_text.text. Stored markers are `[name]` (the stitcher, at write time)
                            and `[name redacted]` (radar.fit.redact_person_names).
Where the original is kept: the stitcher's saved LLM answers (data/fetched/stitcher/proposals/<key>.json: queries_run and the events'
                            quotes) and the written briefs (data/fetched/briefs/out*/<key>.json).
How a text is repaired:     the stored text with each marker read as "any words" must match exactly one original of the same company.
                            The original is then redacted again with the fixed redactor (radar.names.known_names), so a person's name
                            stays redacted and a company's name comes back. A text with no matching original is left as it is and
                            counted. Nothing is written without a matching original; --dry-run writes nothing at all.
Counts:  markers found, markers on a company name (restored), markers left (a person, or a name the store does not know),
         texts with no recoverable original. The command is safe to run twice: a repaired text has nothing left to restore.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from radar import fit, names, thesis as thesis_mod
from radar.adapters import stitcher

ROOT = Path(__file__).resolve().parent.parent
MARKER = re.compile(r"\[name redacted\]|\[name\]")
QUERY_LIMIT = 300  # the stitcher stores at most 300 characters of a query


def n_markers(text: str | None) -> int:
    return len(MARKER.findall(text or ""))


def _template(stored: str) -> re.Pattern:
    """The stored text with every marker read as any words."""
    return re.compile("(.+?)".join(re.escape(p) for p in MARKER.split(stored)), re.S)


def _matches(stored: str, candidates: list[str], *, prefix: bool = False) -> list[tuple[str, tuple[str, ...]]]:
    """Distinct candidates the stored text can be read from, each with the words the markers stand for."""
    rx, out, seen = _template(stored), [], set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        m = rx.match(c) if prefix else rx.fullmatch(c)
        if m:
            out.append((c, m.groups()))
    return out


def _clean(q: str) -> str:
    """The text as the stitcher saw it before redacting: long dashes become hyphens."""
    return str(q).translate(stitcher._DASHES)


def _words(q: str) -> str:
    return " ".join(_clean(q).split()[:stitcher.MAX_QUOTE_WORDS])


class Originals:
    """The saved originals, read lazily per company from the fetched-data folder."""

    def __init__(self, fetched: Path):
        self.fetched = fetched
        self._cache: dict[tuple, list[str]] = {}

    def _json(self, p: Path):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def queries(self, key: str) -> list[str]:
        d = self._json(self.fetched / "stitcher" / "proposals" / f"{key}.json")
        return [_clean(q) for q in (d or {}).get("queries_run") or [] if isinstance(q, str)] if isinstance(d, dict) else []

    def quotes(self, key: str) -> list[str]:
        d = self._json(self.fetched / "stitcher" / "proposals" / f"{key}.json")
        evs = (d or {}).get("events") or [] if isinstance(d, dict) else []
        return [_words(e.get("quote") or "") for e in evs if isinstance(e, dict) and e.get("quote")]

    def brief_texts(self, key: str) -> list[str]:
        out: list[str] = []
        for p in sorted((self.fetched / "briefs").glob(f"out*/{key}.json")):
            d = self._json(p)
            if not isinstance(d, dict):
                continue
            out += [v.get("text") for v in (d.get("slots") or {}).values() if isinstance(v, dict) and v.get("text")]
            out += [s.get("text") for s in d.get("sentences") or [] if isinstance(s, dict) and s.get("text")]
        return out


class Fixer:
    def __init__(self, conn: sqlite3.Connection, thesis: dict, originals: Originals):
        self.conn, self.thesis, self.orig = conn, thesis, originals
        self.counts = {"markers": 0, "restored": 0, "left": 0, "texts": 0, "texts_changed": 0, "unrecoverable": 0, "ambiguous": 0,
                       "newly_redacted": 0}
        self.by_place: dict[str, dict[str, int]] = {}
        self.samples: list[str] = []
        self._legal: dict[str, str] = {}

    def _name(self, key: str) -> str:
        if key not in self._legal:
            r = self.conn.execute("SELECT name FROM companies WHERE company_key=?", (key,)).fetchone()
            self._legal[key] = r[0] if r else ""
        return self._legal[key]

    def _redact(self, original: str, key: str, marker_kind: str) -> str:
        known = names.known_names(self.conn, self.thesis, key)
        if marker_kind == "[name redacted]":
            return fit.redact_person_names(original, self._name(key), self.thesis, known=known)
        return stitcher.redact_people(original, self._name(key), known)

    def repair(self, place: str, key: str, stored: str, candidates: list[str], *, prefix: bool = False,
               limit: int | None = None) -> str | None:
        """The repaired text, or None when there is nothing to change. Counts every marker and the ones restored."""
        n = n_markers(stored)
        if not n:
            return None
        c, pl = self.counts, self.by_place.setdefault(place, {"texts": 0, "markers": 0, "restored": 0, "unrecoverable": 0})
        c["texts"] += 1
        c["markers"] += n
        pl["texts"] += 1
        pl["markers"] += n
        found = _matches(stored, candidates, prefix=prefix)
        if len(found) != 1:
            c["ambiguous" if found else "unrecoverable"] += 1
            c["left"] += n
            pl["unrecoverable"] += 1
            return None
        original, spans = found[0]
        kind = MARKER.search(stored).group(0)
        new = self._redact(original, key, kind)
        if limit:
            new = new[:limit]
        now = n_markers(new)
        restored = max(0, n - now)
        c["restored"] += restored
        pl["restored"] += restored
        c["left"] += n - restored
        c["newly_redacted"] += max(0, now - n)
        if new == stored:
            return None
        if restored and len(self.samples) < 40:
            self.samples += [f"{key}: {s}" for s in spans if s in new][:3]
        c["texts_changed"] += 1
        return new

    # --- the places a marker is stored --------------------------------------------------------------------------------------------
    def stitch_log(self, write: bool) -> None:
        rows = self.conn.execute("SELECT id, company_key, outcome, query, quote, reason FROM stitch_log "
                                 "WHERE query LIKE '%[name%' OR quote LIKE '%[name%' OR reason LIKE '%[name%'").fetchall()
        for rid, key, outcome, query, quote, reason in rows:
            upd: dict[str, str] = {}
            if query and n_markers(query):
                new = self.repair("stitch_log.query", key, query, self.orig.queries(key), prefix=len(query) >= QUERY_LIMIT, limit=QUERY_LIMIT)
                if new is not None:
                    upd["query"] = new
            if quote and n_markers(quote):
                new = self.repair("stitch_log.quote", key, quote, self.orig.quotes(key))
                if new is not None:
                    upd["quote"] = new
            if reason and n_markers(reason):  # a reason is code-written text; no original is kept, so it is only counted
                self.repair("stitch_log.reason", key, reason, [])
            if upd and write:
                self.conn.execute("UPDATE stitch_log SET " + ", ".join(f"{k}=?" for k in upd) + " WHERE id=?", (*upd.values(), rid))

    def signals(self, write: bool) -> None:
        rows = self.conn.execute("SELECT id, company_key, detail FROM signals WHERE adapter='stitcher' AND detail LIKE '%[name%'").fetchall()
        for sid, key, detail in rows:
            m = re.match(r'^"(.*)" \((\S+?)\)(?=\s|$)', detail, re.S)
            if not m:
                self.repair("signals.detail", key, detail, [])
                continue
            quote = m.group(1)
            new_quote = self.repair("signals.detail", key, quote, self.orig.quotes(key))
            if new_quote is not None and write:
                self.conn.execute("UPDATE signals SET detail=? WHERE id=?", ('"' + new_quote + '"' + detail[m.end(1) + 1:], sid))

    def briefs(self, write: bool) -> None:
        for table, col, is_slots in (("company_brief_slots", "slots_json", True), ("company_briefs", "sentences_json", False)):
            try:
                rows = self.conn.execute(f"SELECT company_key, {col} FROM {table} WHERE {col} LIKE '%[name%'").fetchall()
            except sqlite3.OperationalError:
                continue
            for key, blob in rows:
                data = json.loads(blob)
                items = [v for v in data.values() if isinstance(v, dict)] if is_slots else [v for v in data if isinstance(v, dict)]
                changed = False
                for it in items:
                    if n_markers(it.get("text")):
                        new = self.repair(f"{table}.{col}", key, it["text"], self.orig.brief_texts(key))
                        if new is not None:
                            it["text"], changed = new, True
                if changed and write:
                    self.conn.execute(f"UPDATE {table} SET {col}=? WHERE company_key=?", (json.dumps(data, ensure_ascii=False), key))

    def signal_text(self, write: bool) -> None:
        rows = self.conn.execute("SELECT s.company_key, t.text FROM signal_text t JOIN signals s ON s.id=t.signal_id "
                                 "WHERE t.text LIKE '%[name%'").fetchall()
        for key, text in rows:  # register and CORDIS titles: no original is kept, so these are only counted
            self.repair("signal_text.text", key, text, [])


def run(db: str | Path, *, dry_run: bool, fetched: Path | None = None, thesis_path: str | None = None) -> dict:
    th = thesis_mod.load(thesis_path)
    conn = sqlite3.connect(str(db), timeout=60)
    originals = Originals(fetched or ROOT / "data" / "fetched")
    fx = Fixer(conn, th, originals)
    try:
        fx.stitch_log(not dry_run)
        fx.signals(not dry_run)
        fx.briefs(not dry_run)
        try:
            fx.signal_text(not dry_run)
        except sqlite3.OperationalError:  # a store without signal_text
            pass
        if dry_run:
            conn.rollback()
        else:
            conn.commit()  # one transaction: every repair or none
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"db": str(db), "thesis": th.get("id"), "dry_run": dry_run, **fx.counts, "by_place": fx.by_place, "samples": fx.samples}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the radar store to repair")
    ap.add_argument("--dry-run", action="store_true", help="count only; write nothing")
    ap.add_argument("--fetched", help="folder with stitcher/proposals and briefs/out*/ (default data/fetched in this repo)")
    ap.add_argument("--thesis", help="thesis yaml whose declared lists protect names (default: the default thesis)")
    a = ap.parse_args(argv)
    if not Path(a.db).is_file():
        raise SystemExit(f"no store at {a.db}")
    r = run(a.db, dry_run=a.dry_run, fetched=Path(a.fetched) if a.fetched else None, thesis_path=a.thesis)
    print(f"store {r['db']} (thesis {r['thesis']}){'  DRY RUN, nothing written' if r['dry_run'] else ''}")
    print(f"texts with a marker {r['texts']}, markers {r['markers']}: restored (a company name) {r['restored']}, "
          f"left redacted {r['left']}; texts changed {r['texts_changed']}; texts with no single original found {r['unrecoverable'] + r['ambiguous']} "
          f"(ambiguous {r['ambiguous']}); markers newly added by the fixed redactor {r['newly_redacted']}")
    for place, c in sorted(r["by_place"].items()):
        print(f"  {place}: texts {c['texts']}, markers {c['markers']}, restored {c['restored']}, no original {c['unrecoverable']}")
    for s in r["samples"][:12]:
        print(f"  restored: {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
