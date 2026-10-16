"""The only reader of thesis YAML. load() returns a validated dict."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = "config/thesis.yaml"


class ThesisError(ValueError):
    pass


def load(path: str | Path | None = None) -> dict:
    p = Path(path or os.environ.get("RADAR_THESIS") or DEFAULT)
    if not p.is_absolute():
        p = ROOT / p
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
