# Fonts for the rules PDF

These are the fonts `radar/rules_pdf.py` embeds in `docs/method/assumptions_and_decisions.pdf`. They are the same fonts the
site already self-hosts in `radar/static/fonts/` (from the @fontsource packages, declared in DISCLOSURE.md), converted from
WOFF2 to TrueType with fontTools on 17 Oct 2026, because reportlab reads TrueType only. The glyphs are unchanged, and so is
the Latin subset, which covers every character in PROJECT_RULES.md.

| File | From | Licence |
|---|---|---|
| IBMPlexSans-Regular.ttf, IBMPlexSans-Medium.ttf, IBMPlexSans-SemiBold.ttf | ibm-plex-sans-latin-400/500/600-normal.woff2 | SIL Open Font License 1.1, Copyright 2019 IBM Corp. |
| IBMPlexMono-Regular.ttf | ibm-plex-mono-latin-400-normal.woff2 | SIL Open Font License 1.1, Copyright IBM Corp. |
| Newsreader-SemiBold.ttf | newsreader-latin-600-normal.woff2 | SIL Open Font License 1.1, The Newsreader Project Authors |

Each file carries its copyright and licence URL (https://scripts.sil.org/OFL) in its name table.
