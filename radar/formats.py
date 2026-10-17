"""The data formats every store row is held to (PROJECT_RULES.md, Formats). Read by radar/stop_and_ask.py and radar/consistency.py.

  dates         ISO 8601 calendar dates YYYY-MM-DD; the precision is day unless signal_meta says year or month (A18)
  Business ID   Finnish Y-tunnus NNNNNNN-C, C the check digit: weights 7 9 10 5 8 4 2, remainder 0 gives 0, 1 is never
                issued, otherwise 11 minus the remainder
  country       ISO 3166-1 alpha-2, upper case (A29)
  amounts       EUR as the source states them, no conversion (A19)
"""
from __future__ import annotations

import re

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRECISIONS = ("day", "month", "year")
BUSINESS_ID = re.compile(r"^\d{7}-\d$")
_WEIGHTS = (7, 9, 10, 5, 8, 4, 2)

# ISO 3166-1 alpha-2, the officially assigned codes.
ISO_COUNTRIES = frozenset("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG
CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL
GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA
LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP
NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV
SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
""".split())


def business_id_ok(value: str | None) -> bool:
    """True when value is a well-formed Finnish Business ID with a valid check digit."""
    if not value or not BUSINESS_ID.match(value):
        return False
    r = sum(int(d) * w for d, w in zip(value[:7], _WEIGHTS)) % 11
    if r == 1:
        return False
    return int(value[8]) == (0 if r == 0 else 11 - r)


def country_ok(value: str | None) -> bool:
    return bool(value) and value in ISO_COUNTRIES


def date_ok(value: str | None) -> bool:
    """A real calendar date in YYYY-MM-DD."""
    if not value or not DATE.match(value):
        return False
    from datetime import date
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True
