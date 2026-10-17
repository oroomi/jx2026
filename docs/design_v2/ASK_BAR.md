# Ask Aava bar: references and direction

Task: replace the home hero count block ("In the past 90 days / 22 companies surfaced / 3 this month") with an AI bar that has
text, a microphone and a voice mode. Read 17 Oct 2026. These are public write-ups, not screenshots we copied; each line says what
we took and what we left.

## References (one line each)

1. **ChatGPT voice orb.** A single blue-and-white orb in the middle of a dark screen that swells while it speaks; nothing else competes
   with it. Took: one orb, centred, no chrome around it, state shown by motion not labels.
   https://oodaloop.com/briefs/cyber/openai-rolls-out-advanced-voice-mode-with-more-voices-and-a-new-look ,
   https://community.openai.com/t/voice-mode-visual-improvements/1386614 (users ask for colour themes: ours reads the skin's accent token).
2. **Perplexity composer.** "Ask anything" bar with the mic next to a primary action that changes with state (dictate, send, stop);
   a teardown also notes five controls on one bar is crowded. Took: mic and send side by side, send is the only filled control.
   Left: model picker, mode chips, attachments (one input, two buttons).
   https://aiuxplayground.com/teardowns/perplexity/composer , https://screensdesign.com/showcase/perplexity-ask-anything
3. **Gemini Live.** A waveform that lives inside a pill, with the live transcript written directly above the controls, and a soft
   glow around the overlay. Took: the transcript line sits between the orb and the answer; a glow at the screen edge.
   https://9to5google.com/2025/08/12/gemini-overlay-redesign-pill-starts/ ,
   https://www.androidauthority.com/gemini-overlay-and-live-ui-changes-3655577/
4. **Siri on iOS 18 (glow edge).** The orb was replaced by light that wraps the screen edge and follows the voice, so the page stays
   usable underneath. Took: the edge glow whose strength follows the microphone level; the overlay is translucent, the page shows through.
   https://9to5mac.com/2024/11/03/new-apple-intelligence-siri-looks-different-works-the-same/
5. **Arc Search "Call Arc".** Voice treated as a call: a face, an end-call control, an answer spoken back. Took: one clear way out
   (Close and Escape) and the answer is spoken and written at once. Left: the character and hold music.
   https://www.macrumors.com/2024/05/23/arc-search-call-feature
6. **Linear and Raycast command bars.** A centred input summoned by one chord (Cmd/Ctrl K), recent items first, the primary action
   shown beside the input. Took: Cmd/Ctrl K focuses the bar from anywhere on the home page; Enter asks.
   https://brainy.ink/paper/glossary/command-bar , https://www.raycast.com/changelog/macos-beta/0-65

## Direction

Editorial skin first (Newsreader title, ruled card, one accent), dark default; terminal (mono, amber, square) and product (rounded
surfaces) read the same tokens. No new colour: the orb, the glow and the focus ring are mixes of `--accent`, `--text` and `--bg`,
so light theme and all three skins work. No purple gradient, no emoji.

- Hero: "Ask Aava" in the page's display type, one large field, mic and send inside it, a one-line muted count under it.
- The placeholder cycles through five real questions the bar can answer. Cycling stops on focus and under reduced motion.
- Text mode: Enter asks, the answer card appears under the bar (no orb), with the sentence, the link and the source.
- Voice mode (only when the Aava demo flag is on): the mic opens a translucent overlay. States: listening (orb follows the microphone
  level through an AnalyserNode, ripples on peaks, edge glow), thinking (orb contracts and turns), speaking (orb follows the audio
  that is playing; the browser voice has no tap-able signal, so it pulses on word boundaries). The answer is written word by word.
- Reduced motion: no pulsing, no ripples, no word-by-word; the state shows as a steady ring and a text label.
- Answers are deterministic (`/api/ask`, `radar/ask.py`): company name or id, feed, filter phrases, organisation, search.

## What we could not take

No model sits behind the bar, so there is no free-form follow-up conversation; an unknown phrase goes to the search page and says so.

## What shipped (feat/ask_bar)

- `GET /api/ask?q=&thesis=` (radar/routes/ask.py, logic in radar/ask.py): `{intent, say, url, action, label, segments, audio_dir, items, count, total}`.
  Intents: `company` (name or business id, Aava question 1; "who should <company> meet" gives question 4), `feed`, `filter` (the home filter rail's
  querystring and a count from the cached home list), `match` (an organisation from the declared lists; the link appears when /match is in the build),
  `search`, `help`. The vocabulary is `ask:` in config/thesis.yaml; another thesis file inherits it and sets its own `examples` and `sectors`.
- Hero: radar/templates/_ask_bar.html, radar/static/askbar.js, radar/static/askbar.css. The old count block is the one muted line under the bar.
- Header: radar/templates/_nav_menu.html (a details element, works without JavaScript) and the footer read one list, `site_pages`.
- Voice: needs the Aava demo flag; recorded MP3 only when the manifest holds the answer's text sha (the committed manifests predate the six-question
  rewrite, so today the browser voice speaks); the orb follows the playing audio either way.
- Privacy line, printed in the overlay: the browser does the speech-to-text and some browsers do that on the vendor's servers; this site only
  receives the text of the question. Add one line to DISCLOSURE.md for the Web Speech API.
