---
id: J-TRACK
title: Track an idea, answer the desk, read the decision
rev: 1
status: baseline
source: reference/prototype/Status.dc.html
depends_on: [S-06, S-R3, S-08, S-H5, S-07, S-03, L-QUESTIONS, L-DECIDE, L-COMMITTEE, L-INBOX, L-SUBMIT]
last_delta: none
---

# J-TRACK: Track an idea, answer the desk, read the decision

**Who:** the sharer, after sending. **Ends:** a decision with its reason, and what happens next.

## `J-TRACK.steps` Steps

| # | Screen | What happens | Rules |
|---|---|---|---|
| 1 | `S-06` | "With the review desk". The sharer may edit or withdraw until the desk opens it (at most 3 days) | `L-SUBMIT.edit`, `L-SUBMIT.withdraw` |
| 2 | Teams, email, `S-H5`, `S-03` | The desk asks 3 questions. Told on every channel the person has on; the idea shows "Needs you" everywhere with a countdown | `L-QUESTIONS.ask/5`, `L-INBOX.kinds`, `L-NOTIFY` |
| 3 | `S-06` / `S-08` / `S-H5` | The questions show as a card with "Answer the questions". The idea is now locked to edits | `C-QCARD`, `L-SUBMIT.edit/5` |
| 4 | `S-R3` | Answers one question at a time, typed or spoken, with files if needed; skips any; checks; "Send 2 answers to Meera" | `L-QUESTIONS.answer` |
| 5 | `S-06` | "Sent. Meera has your answers." Each answer sits under its part; the conversation has them as one message | `S-06.states` "Answers sent" |
| 6 | Reminders | If not answered: a reminder a day before and two hours before | `L-QUESTIONS.clock/2` |
| 7 | `S-06`, `S-H5` | The decision arrives with its reason, read at once: Picked, Not now (with the date it comes back) or Not picked (with where the words went, if anywhere) | `L-DECIDE`, `S-06.states` |
| 8 | `S-06` | A line says the Ones Committee can review the decision until a date. If they reverse it, their note arrives and the page shows the new decision, final | `L-COMMITTEE`, `S-06.states` "Reversed" |
| 9 | `S-08` | If picked: the build team writes and may ask the sharer to check something by a date | `L-DECIDE.after`, `L-CONVO` |
| 10 | `S-06`, `S-WALL` | Shipped: measured at 30 and 90 days; if the difference is confirmed, the sharer becomes a One | `L-IMPACT`, `J-ONE` |

Variation: withdraw at step 1 → "Withdrawn. It's back in your drafts." → "Restore it" at any time.

Acceptance: `V-ACC.track`.

## `J-TRACK.boards` Boards to walk on the canvas

`Status`, `Answer`, `Messages`, `Inbox`, `MyIdeas`
