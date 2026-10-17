"""The only reader of thesis YAML. load() returns a validated dict."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = "config/thesis.yaml"


log = logging.getLogger("radar.thesis")
_ID_OK = re.compile(r"[^a-z0-9_]")
_CACHE: dict[tuple[str, int], dict] = {}


class ThesisError(ValueError):
    pass


def _path(path) -> Path:
    p = Path(path or os.environ.get("RADAR_THESIS") or DEFAULT)
    return p if p.is_absolute() else ROOT / p


def load(path: str | Path | None = None) -> dict:
    """Validated thesis dict. Cached by path and mtime; callers get a shallow copy."""
    p = _path(path)
    try:
        key = (str(p), p.stat().st_mtime_ns)
    except OSError:
        raise ThesisError(f"thesis file not found: {p}")
    hit = _CACHE.get(key)
    if hit is None:
        hit = _parse(p)
        for k in [k for k in _CACHE if k[0] == key[0]]:
            del _CACHE[k]
        _CACHE[key] = hit
    return dict(hit)


def _parse(p: Path) -> dict:
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ThesisError(f"thesis file not found: {p}")
    except yaml.YAMLError as e:
        raise ThesisError(f"thesis file {p} is not valid YAML: {e}")
    if not isinstance(data, dict):
        raise ThesisError(f"thesis file {p} must be a mapping at the top level")
    for key in ("id", "title"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ThesisError(f"thesis file {p}: '{key}' must be a non-empty string")
    geo = data.get("geography")
    days = geo.get("feed_window_days") if isinstance(geo, dict) else None
    if not isinstance(days, int) or isinstance(days, bool) or days <= 0:
        raise ThesisError(f"thesis file {p}: geography.feed_window_days must be a positive integer")
    for key in ("industry_codes", "feed_signal_types"):
        if not isinstance(data.get(key), list):
            raise ThesisError(f"thesis file {p}: '{key}' must be a list")
    if not isinstance(data.get("name_keywords"), (dict, list)):
        raise ThesisError(f"thesis file {p}: 'name_keywords' must be a mapping of language to words, or a list")
    if "countries" in data and not (isinstance(data["countries"], list) and data["countries"]
                                    and all(isinstance(c, str) and re.fullmatch(r"[A-Za-z]{2}", c) for c in data["countries"])):
        raise ThesisError(f"thesis file {p}: 'countries' must be a non-empty list of two-letter ISO country codes")
    if "code_alone_weak" in data and not (isinstance(data["code_alone_weak"], list)
                                          and all(isinstance(x, (str, int)) and not isinstance(x, bool) and str(x).strip() for x in data["code_alone_weak"])):
        raise ThesisError(f"thesis file {p}: 'code_alone_weak' must be a list of industry code prefixes (for example [\"711\", \"721\"])")
    if "country_depth" in data and not isinstance(data["country_depth"], dict):
        raise ThesisError(f"thesis file {p}: 'country_depth' must be a mapping of country code to a depth text")
    if "intake" in data:
        _check_intake(p, data["intake"])
    data["_path"] = str(p)
    return data


def _check_intake(p: Path, it) -> None:
    if not isinstance(it, dict):
        raise ThesisError(f"thesis file {p}: 'intake' must be a mapping")
    forms = it.get("company_forms")
    if not (isinstance(forms, list) and forms and all(isinstance(f, dict) and str(f.get("code") or "").strip() for f in forms)):
        raise ThesisError(f"thesis file {p}: intake.company_forms must be a non-empty list of {{code, note}} mappings")
    for key in ("code_prefixes", "startup_signals"):
        v = it.get(key)
        if not (isinstance(v, list) and v and all(isinstance(x, (str, int)) and str(x).strip() for x in v)):
            raise ThesisError(f"thesis file {p}: intake.{key} must be a non-empty list")
    n = it.get("min_signals", 1)
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ThesisError(f"thesis file {p}: intake.min_signals must be a positive integer")


def intake(th: dict) -> dict | None:
    """The normalised intake section, or None when the thesis defines none. Codes and prefixes are strings."""
    it = th.get("intake")
    if not it:
        return None
    return {"company_forms": {str(f["code"]).strip(): str(f.get("note") or "") for f in it["company_forms"]},
            "code_prefixes": [str(x).strip() for x in it["code_prefixes"]],
            "startup_signals": [str(x).strip() for x in it["startup_signals"]],
            "min_signals": int(it.get("min_signals", 1)),
            "tuning_note": str(it.get("tuning_note") or "").strip(),
            "thesis_codes": [str(c.get("code")) for c in th.get("industry_codes") or []]}


DEFAULT_DEPTH = "EU sources only"


def countries(th: dict) -> list[str]:
    """Active ISO country codes: top-level `countries`, else geography.countries, else FI. Upper case, no duplicates."""
    raw = th.get("countries") or (th.get("geography") or {}).get("countries") or ["FI"]
    return list(dict.fromkeys(str(c).strip().upper() for c in raw if str(c).strip()))


def country_depth(th: dict) -> dict[str, str]:
    """{country: depth text} for every active country; a country with no entry is 'EU sources only'."""
    given = {str(k).upper(): str(v) for k, v in (th.get("country_depth") or {}).items()}
    return {c: given.get(c, DEFAULT_DEPTH) for c in countries(th)}


def available() -> dict[str, str]:
    """{thesis_id: path} for every config/thesis*.yaml that loads and validates; invalid files are skipped with a warning."""
    out: dict[str, str] = {}
    for f in sorted((ROOT / "config").glob("thesis*.yaml")):
        try:
            th = load(f)
        except ThesisError as e:
            log.warning("skipping thesis file %s: %s", f, e)
            continue
        out.setdefault(th["id"], str(f))
    return out


def default_path() -> str:
    return str(_path(None))


def resolve(thesis_id: str | None) -> str:
    """Path of the thesis for an id. Only an exact id from available() is honoured; anything else gives the default."""
    if isinstance(thesis_id, str) and thesis_id:
        av = available()
        if thesis_id in av:
            return av[thesis_id]
    return default_path()


def data_dir() -> Path:
    return Path(os.environ.get("RADAR_DATA_DIR") or ROOT / "data")


def db_path(th: dict) -> Path:
    """data/radar_<id>.sqlite. RADAR_DB applies only to the default thesis."""
    default_id = None
    try:
        default_id = load()["id"]
    except ThesisError:
        pass
    if os.environ.get("RADAR_DB") and th.get("id") == default_id:
        return Path(os.environ["RADAR_DB"])
    return data_dir() / f"radar_{_ID_OK.sub('', str(th['id']).lower())}.sqlite"
