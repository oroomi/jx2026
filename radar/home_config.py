"""The home list's filter configuration (config/home_filters.yaml): the rail's facets, the group labels, the Top matching picker's
settings and the country name table. The only reader of that file; the Python below names no sector, country or investor."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "config" / "home_filters.yaml"
_cache: dict = {}


def load() -> dict:
    """The parsed file, re-read when it changes (so a test or an editor sees an edit without a restart)."""
    stamp = PATH.stat().st_mtime_ns
    if _cache.get("stamp") != stamp:
        data = yaml.safe_load(PATH.read_text(encoding="utf-8")) or {}
        facets = [f for f in data.get("facets") or [] if isinstance(f, dict) and f.get("param")]
        if not facets:
            raise ValueError(f"{PATH}: no facets listed")
        data["facets"] = facets
        _cache.update(stamp=stamp, data=data)
    return _cache["data"]


def facets() -> tuple[tuple, ...]:
    """(param, heading, section, open by default, source) per facet, in rail order."""
    return tuple((f["param"], f.get("heading") or f["param"], f.get("section") or "more", bool(f.get("open")), f.get("source")) for f in load()["facets"])


def sections() -> dict[str, str]:
    return dict(load().get("sections") or {})


def group_label(key: str, default: str | None = None) -> str:
    return ((load().get("groups") or {}).get(key) or {}).get("label") or default or key


def group_label_for(key: str, org: str) -> str:
    """The tab label when an organisation is picked: the `label_for` template with {org} filled in, else the plain label."""
    spec = (load().get("groups") or {}).get(key) or {}
    tmpl = spec.get("label_for")
    return tmpl.format(org=org) if tmpl else group_label(key)


def top_matching() -> dict:
    t = dict(load().get("top_matching") or {})
    t.setdefault("kinds", [])
    t.setdefault("reasons", 2)
    return t


def country_names() -> dict[str, str]:
    """ISO 3166-1 alpha-2 code -> English name."""
    return dict(load().get("countries") or {})


def country_name(code: str) -> str:
    return country_names().get(str(code).upper(), code)


def flag_dir() -> str:
    return str((load().get("flags") or {}).get("dir") or "").rstrip("/")


def flag_codes() -> frozenset[str]:
    """Upper-case codes that have a vendored flag file beside the static files."""
    d = flag_dir()
    if not d.startswith("/static/"):
        return frozenset()
    folder = ROOT / "radar" / d.lstrip("/")
    return frozenset(p.stem.upper() for p in folder.glob("*.svg")) if folder.is_dir() else frozenset()


def flag_url(code: str) -> str | None:
    """The flag file's URL for a country code, or None when none is vendored (the name is then printed alone)."""
    code = str(code).upper()
    return f"{flag_dir()}/{code.lower()}.svg" if code in flag_codes() else None
