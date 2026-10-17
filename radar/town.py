"""Home town of a company, read from the address block of a PRH/YTJ company record (open data API v3). No network.

The town is the post office name of the company's current registered address, in Finnish, title-cased ("TURKU" -> "Turku").
The visiting address (type 1) is preferred, the postal address (type 2) is the fallback. Addresses abroad carry no post
office entry in the register (only a free text line), so they give no town: the field stays NULL, never guessed.
Post office names are postal localities: most are municipalities, some are villages inside one ("Veikkola" in Kirkkonummi).
They are shown as the register states them. Entries that name a mail recipient, not a place ("VARMA", "OSOITE TUNTEMATON"), are skipped.
Used by radar/backfill_town.py (store copy) and by the prh and prh_intake adapters (at insert time), so both write the same way.
"""
from __future__ import annotations

import re
import sqlite3

YTJ_PAGE = "https://tietopalvelu.ytj.fi/yritys/{}"
_PRH_HOST = "https://avoindata.prh.fi/"
_LANG_ORDER = ("1", "3", "2")  # languageCode: 1 fi, 3 en, 2 sv
VISITING, POSTAL = "visiting", "postal"
_KIND = {1: VISITING, 2: POSTAL}

# Post office names that are a mail recipient (big-customer postcodes), not a place. Compared upper-case.
NON_PLACE = frozenset({
    "OSOITE TUNTEMATON", "YRITYSLOKERO", "BOX", "LASKUT", "LASKUTUS", "LASKUNET", "KAUPUNKILIIKENNE", "ADMINISTER", "AZETS",
    "AALTO", "ATRIA", "FENNIA", "FINNAIR", "HELEN", "HUS", "ILMARINEN", "KEVA", "KOLLEKTOR SCAN", "LÄHITAPIOLA", "METROPOLIA",
    "METSÄ", "OP POHJOLA", "POSTI", "PULP", "S-RYHMÄ", "SMÅBÖNDERS", "VALIO", "VARMA", "VR", "VTT",
    "ESPOON KAUPUNKI", "HELSINGIN KAUPUNKI", "HELSINGIN YLIOPISTO", "TAMPEREEN YLIOPISTO", "TURUN YLIOPISTO", "EERIKKILÄN URHEILUOPISTO",
})
# Post office service point suffixes ("KAUHAJOKI AS", "HOLLOLA KK"): the town is the part before them.
_SERVICE_SUFFIX = re.compile(r"\s+(?:AS|KK)$")


def clean_city(raw: str | None) -> str | None:
    """Title-cased town from a post office name, or None when it is empty or names a mail recipient, not a place."""
    city = re.sub(r"\s+", " ", raw or "").strip().upper()
    city = _SERVICE_SUFFIX.sub("", city)
    if not city or city in NON_PLACE:
        return None
    return city.title()


def _city_of(address: dict) -> str | None:
    by = {str(p.get("languageCode")): p.get("city") for p in address.get("postOffices") or [] if p.get("city")}
    for code in _LANG_ORDER:
        if by.get(code):
            return clean_city(by[code])
    return clean_city(next(iter(by.values()), None))


def of(c: dict) -> tuple[str | None, str | None]:
    """(town, "visiting" | "postal") of a PRH company record; (None, None) when it has no current address with a Finnish post office."""
    current = [a for a in c.get("addresses") or [] if not a.get("endDate") and a.get("type") in _KIND]
    current.sort(key=lambda a: a.get("registrationDate") or "", reverse=True)  # latest first within a type
    current.sort(key=lambda a: a["type"])                                       # stable: visiting before postal
    for a in current:
        town = _city_of(a)
        if town:
            return town, _KIND[a["type"]]
    return None, None


def source_url(y_tunnus: str, stored: str | None) -> str:
    """The page a human opens to check the town: the PRH company URL already stored for the company, else its YTJ page."""
    return stored if stored and stored.startswith(_PRH_HOST) else YTJ_PAGE.format(y_tunnus)


def set_town(conn: sqlite3.Connection, company_key: str, town: str | None, url: str) -> bool:
    """Store a town on one company. NULL never erases. Returns True when the stored value changed."""
    if not town:
        return False
    row = conn.execute("SELECT town, town_source_url FROM companies WHERE company_key=?", (company_key,)).fetchone()
    if row is None or (row[0], row[1]) == (town, url):
        return False
    conn.execute("UPDATE companies SET town=?, town_source_url=? WHERE company_key=?", (town, url, company_key))
    return True


def record_town(conn: sqlite3.Connection, company_key: str, c: dict) -> str | None:
    """Adapter helper: read the town from the PRH record c and store it on company_key (after emit.upsert_company). Returns the town."""
    town, _ = of(c)
    if town:
        row = conn.execute("SELECT y_tunnus, source_url FROM companies WHERE company_key=?", (company_key,)).fetchone()
        if row is not None:
            set_town(conn, company_key, town, source_url(row[0] or c["businessId"]["value"], row[1]))
    return town
