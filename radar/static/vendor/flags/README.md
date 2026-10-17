# Country flags

Flags shown beside country names in the home list's filter (the Country group, the country links and the country chips).

- Source: the `flag-icons` package, version 7.2.3, https://github.com/lipis/flag-icons (the `flags/4x3/` set).
- Licence: MIT, Copyright (c) 2013 Panayiotis Lipiridis. The licence text is in `LICENSE` beside the files.
- Files: only the countries that appear in the stores' home lists today, one `<lowercase ISO 3166-1 alpha-2 code>.svg` each:
  bg, ch, de, dk, ee, es, fi, lv, no, pl, se.
- Used at 16 x 12 px, decorative (`alt=""`): the country's English name is always printed beside it.
- A country with no file here prints its name alone (`radar/home_config.py` `flag_url`). To add one, copy `<code>.svg` from the package's
  `flags/4x3/` folder into this folder; nothing else changes.
