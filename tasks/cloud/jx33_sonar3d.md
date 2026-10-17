# jx33_sonar3d [cloud]: one 3D hero that carries meaning, the radar as a real sonar

Branch: `cloud/sonar3d`. Protocol: tasks/cloud/PROTOCOL.md. Pull main first.

## Why
Dayo wants the visuals to be the best of the best. The product is called a radar, so one 3D view makes it literal: a dark sea surface with a sonar sweep, where every blip is a real company. It must explain something a table cannot, at a glance, for a 50-year-old fund partner. Everything else on the site stays 2D and calm.

## Build (write it fresh; no code from any earlier project, that is a disqualification rule)
1. three.js vendored in radar/static/vendor/ (exact version, licence file, no CDN at runtime). Our own code in radar/static/sonar3d/sonar.js plus a partial radar/templates/_sonar3d.html. The data comes from a new read-only route radar/routes/sonar.py: GET /sonar.json?thesis=&view=backtest|feed.
2. Backtest view (on /radar): the centre is "cohort entry". Each cohort company is a blip at a distance from the centre equal to how many months before entry its first public signal was. Blips outside the ring are "found earlier", inside "found later", and companies with no signal sit in a hatched band at the edge. Colour by evidence: live public records, declared research, stitcher (public before entry). Labelled rings: "12 months earlier", "24 months earlier". The sweep passes and blips glow when hit.
3. Feed view (home page, small, above the feed): the last 90 days, with the newest blips nearest the centre.
4. Interaction: hover or tap a blip to show the company name, the first signal and its date; click opens /c/{key}. Keyboard: Tab moves through blips, Enter opens. Under the canvas, a plain-text legend sentence ("Each dot is a company. Further out = found earlier.").
5. Must not break anything:
   - 2D fallback: no WebGL, or prefers-reduced-motion, gets a static SVG of the same rings and dots.
   - Phone at 390 px: no horizontal scroll, under 2 s to first frame.
   - At most 150 KB of our own JS beyond three.js.
   - Animation pauses when the tab is hidden.
   - No fabricated dots: every dot is a row from /sonar.json. Person-shaped names are hidden.
6. Placement: one include line in radar.html and one in home.html. The visual-polish session owns those files, so add only that line and style in a new radar/static/sonar3d/sonar.css. Do not edit company or feed templates, store.py, matching.py, api.py, or the chief's docs. In RESULT, propose a DISCLOSURE line for three.js and a README line.

## See it
Screenshot with playwright (headless chromium, software WebGL is fine) at 1440x900 and 390x844, then read the PNGs. Also capture the fallback (reduced motion). Commit the shots under docs/shots/sonar3d/.

## Done
Tests: /sonar.json counts equal the backtest groups; every dot has a company_key that resolves; the fallback SVG renders without JS. RESULT names the after-shot paths and the groups shown. Push a working slice (backtest view plus fallback) by Sat 10:00 UTC. Feature freeze is Sat 18:30 UTC.
