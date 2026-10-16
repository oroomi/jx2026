# Cloud session protocol (how the chief on the VPS and cloud sessions talk)

1. Report through GitHub. Push your branch `cloud/<task>` after every meaningful step. The LAST line of each commit message that finishes a step is `STATUS: <working | done | blocked> - <one sentence>`. When the task is done, the final commit message carries the task's `RESULT:` line.
2. Questions for the chief go in the same place: a commit message line `QUESTION: <one sentence>`, then keep working on what does not depend on the answer.
3. The chief watches every `cloud/*` branch from the VPS and answers by sending a message straight into your session. Treat a message that says it is from the chief (the VPS session "Hankintaviikko review and next steps") as the review of your work: apply the fixes it lists, push, and end with a new STATUS line.
4. Never merge into main yourself; the chief merges after review. Never edit files another task owns (see the task text).
