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
    "brreg": "Brønnøysund Register Centre (Norway)",
    "cvr": "Danish Central Business Register (CVR)",
    "webarchive": "Internet Archive",
    "estonia_register": "Estonian e-Business Register",
    "ecosystem": "declared research",
    "stitcher": "AI stitcher (checked by code)",
}


# A company's group tag (companies.group_tag) in words. The tag is a table key; a page prints the label (D36).
GROUP_LABELS = {
    "cohort": "cohort company",
    "portfolio": "portfolio company",
    "feed": "found in the early-signal feed",
    "intake": "new startup, no thesis evidence yet",
    "ecosystem": "from the ecosystem dataset",
}


def group_label(tag: str | None) -> str:
    return GROUP_LABELS.get(tag or "") or plain(tag)


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


# A register type code in brackets, "(type 6_80)": the register's own list code. The words before it already say which register it is.
_TYPE_CODE = re.compile(r"\s*\((?:register )?type \d+_\d+\)", re.I)


def plain_text(text: str | None) -> str:
    """A stored detail line with any snake_case id our adapters wrote (for example a dataset event type) turned into words, and a
    register type code in brackets ("(type 6_80)") dropped. A quoted passage that holds a redaction marker is replaced by a short note (D36).
    Parts of a link are left alone."""
    from radar import words  # imported here: radar.words reaches radar.fit, which imports this module
    return _SNAKE.sub(lambda m: m.group(1).replace("_", " "), _TYPE_CODE.sub("", words.drop_marked_quotes(text)))
