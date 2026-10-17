"""Plain words for every token a page can print: signal types and sources. The ONLY label table in the app.

Every page, feed pill, company row, backtest line, /data row and /method list reads these through `signal_label()` and
`source_label()` (Jinja filters of the same names). A token missing here still never reaches a page as snake_case: the
fallback turns underscores into spaces."""
from __future__ import annotations

import re
from urllib.parse import urlparse

SIGNAL_LABELS = {
    "register_entry": "New register entry",
    "bf_funding": "Business Finland funding",
    "eu_project": "EU project",
    "eu_grant": "EU grant",
    "blueinvest": "BlueInvest pipeline",
    "patent": "Patent filing",
    "public_contract": "Public contract",
    "job_ad": "Open job ad",
    "site_customer": "Customer on own site",
    "first_sales": "First sales",
    "first_hire": "First hire",
    "sales_ended": "Sales ended",
    "employer_ended": "Employer register ended",
    "research_output": "Research output",
    "website_first_seen": "Website first seen",
    "website_milestone": "Website milestone",
    "pilot_named": "First customer or pilot named",
    "certification": "Certification or type approval",
    "programme_entry": "Accelerator or programme entry",
    "exhibitor": "Exhibitor or demo",
    "award": "Award or pitch win",
    "funding_round": "Funding round",
    "product_launch": "Product launch",
    "public_funding": "Grant or public funding",
    "ecosystem_event": "Other dated event",
    "startup_notice": "Start-up notification",
    "board_change": "Board change",
    "equity_event": "Share issue or capital increase",
    "capital_loss": "Loss of share capital",
}

# Adapter NAME -> human source name. A name missing here falls back to plain words, never the raw id.
SOURCE_LABELS = {
    "prh": "PRH/YTJ register",
    "prh_notices": "PRH registered notices",
    "prh_intake": "PRH/YTJ register (wide intake)",
    "prh_recent": "PRH/YTJ register (recent registrations)",
    "tax_registers": "PRH/YTJ tax registers",
    "hilma": "Hilma notice",
    "businessfinland": "Business Finland export",
    "cordis": "CORDIS",
    "eu_grants": "EU grants",
    "ted": "TED contract awards",
    "blueinvest": "BlueInvest pipeline",
    "declared": "declared list",
    "openalex": "OpenAlex",
    "webarchive": "Internet Archive",
    "estonia_register": "Estonian e-Business Register",
    "ecosystem": "declared research",
    "stitcher": "AI stitcher (checked by code)",
}


# Where a who-comes-next row came from (matching.py `origin`), in words.
ORIGIN_LABELS = {"programmes_grants.csv": "declared programmes list", "ecosystem dataset": "ecosystem dataset"}


def origin_label(origin: str | None) -> str:
    return ORIGIN_LABELS.get(origin or "", plain(origin) or "declared list")


def plain(token: str | None) -> str:
    """Any id as words: underscores become spaces. Never returns a snake_case token."""
    return (token or "").replace("_", " ").strip()


def signal_label(signal_type: str | None) -> str:
    return SIGNAL_LABELS.get(signal_type or "") or plain(signal_type).capitalize()


def source_label(adapter: str | None, url: str | None = None) -> str:
    """The source name of an adapter; for an unknown adapter the url host, else the adapter id in plain words."""
    if adapter in SOURCE_LABELS:
        return SOURCE_LABELS[adapter]
    host = urlparse(url or "").netloc
    return host or plain(adapter) or "unknown source"


_SNAKE = re.compile(r"(?<![/\w.=&?-])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?![\w/.=&-])")


def plain_text(text: str | None) -> str:
    """A stored detail line with any snake_case id our adapters wrote (for example a dataset event type) turned into words.
    Parts of a link are left alone."""
    return _SNAKE.sub(lambda m: m.group(1).replace("_", " "), text or "")
