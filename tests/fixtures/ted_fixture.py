"""Test-only: SYNTHETIC TED search hits in the shape of api.ted.europa.eu/v3/notices/search. Never loaded by the app."""

BASE = {"buyer-name": {"eng": ["Fixture Harbour Authority"]}, "tender-value-cur": ["EUR"]}


def hit(pub, day, title, names, ccs, sizes, total=None, lang="eng"):
    n = {**BASE, "publication-number": pub, "publication-date": f"{day}+01:00", "notice-title": {"eng": title},
         "winner-name": {lang: names}, "winner-country": ccs, "winner-size": sizes}
    if total is not None:
        n["total-value"] = total
    return n


HITS = [
    hit("1-2026", "2026-02-03", "Estonia - Harbour construction work - Fixture quay", ["Fixture Sadam OU"], ["EST"], ["small"], 125000.5),
    hit("2-2026", "2026-02-04", "Latvia - Boats - Fixture ferries", ["Fixture Laivas SIA", "Fixture Two SIA"], ["LVA", "LVA"], ["micro", "small"], 900000),
    hit("3-2026", "2026-02-05", "Sweden - Ships - Fixture hull", ["Fixture Large AB"], ["SWE"], ["large"], 5000000),
    hit("4-2026", "2026-02-06", "Mixed - Fish - Fixture", ["Fixture Fish AB", "Fixture Fish Ltd"], ["SWE"] + ["FIN", "DNK"], ["small", "small"]),
    hit("5-2026", "2026-02-07", "Finland - Harbour - Fixture", ["Fixture Suomi Oy"], ["FIN"], ["small"]),
]
