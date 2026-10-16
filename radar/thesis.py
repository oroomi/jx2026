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
    data["_path"] = str(p)
    return data


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
