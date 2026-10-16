"""Synthetic imitation of the PRH registered-notices JSON (fixture companies only; never loaded by the app)."""


def notice(bid="0000000-0", name="Fixture Oy", reg="2026-09-10", codes=("ANTIP",), founded="2024-03-01",
           industry="30110", desc="Building of ships and floating structures", kind="", number="FX-1"):
    d = {"businessId": bid, "name": name, "foundingDate": founded, "industryCode": industry,
         "industryDescription": desc, "entryCodes": [{"code": c} for c in codes], "typeOfRegistration": kind,
         "noticeNumber": number}
    if reg is not None:
        d["registrationDate"] = reg
    return d


def page(items):
    return {"results": items}
