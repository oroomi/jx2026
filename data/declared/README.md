# Business Finland funding granted (Myönnetty rahoitus)

- Export date (UTC): 2026-10-16 17:07
- URL: https://tietopankki.businessfinland.fi/anonymous/extensions/MyonnettyRahoitus/MyonnettyRahoitus.html (tab "Asiakkaat", button "XLS")
- Method: headless Chromium via Playwright, script /root/hack/bin_bf/export_bf.py; anonymous, no login
- Filter: none (all years 2010-2026). The year-filter click did not work headless, so subset on column "Myöntämisvuosi" (2024-2026 = 5,350 rows).
- Rows: 59,020 data rows (plus header); one row per organisation per year
- Columns: Organisaatio | Y-tunnus | Myöntämisvuosi | Avustus € | Laina € | EAKR-rahoitus € | Tutkimusrahoitus € | Yhteensä €
- Note: rows with Organisaatio/Y-tunnus "-" are non-attributed aggregates (e.g. 2022: 9,715,827 EUR); 2020 spike is Covid grants.
