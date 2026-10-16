
# Direction mockups (jx33)

Status: in progress. The sonar build is paused at the chief's instruction, before any
three.js or app code was written, so there is nothing of it to push. Nothing under
radar/ was touched.

## What this folder will hold

Three directions for the hero visual, as static mockups only, each at 1440x900 and
390x844, drawn from data/snapshot (489 companies, 1043 signals):

1. Map: a 2.5D Baltic view, one dot per company home town, arcs from a selected
   company to its matched investors, programmes and partners.
2. Life-lines: a 2D timeline of the 19 cohort companies, one row each, dated public
   signals as marks, cohort entry as a line, found-earlier marks highlighted.
3. Sonar: the original task's idea, drawn flat, for comparison.

Each direction gets two real-world references with URLs, and one sentence on what a
fund partner learns from it in five seconds.

## Open question for the chief

This cloud session cannot commit binary files. Its git push is blocked by a
permission gate, and the GitHub file API it has available takes text content only, so
PNG bytes cannot survive the round trip. SVG is text and commits cleanly, renders
inline on GitHub, and stays sharp at both widths.

Proposal: commit each mockup as SVG at the two sizes, plus the HTML source used to
render it, and send the PNGs to Dayo directly outside the repo. If PNGs in the repo
are required, someone with a working git push has to place them.

Nothing here is rendered yet. No file is listed above as present that is not present.
