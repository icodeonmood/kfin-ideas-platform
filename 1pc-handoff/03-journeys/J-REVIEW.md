---
id: J-REVIEW
title: Review an idea and decide
rev: 1
status: baseline
source: reference/prototype/Desk.dc.html
depends_on: [S-R1, S-R2, C-LISTEN, C-WORTH, C-SHEET-MERGE, C-PREVIEW, L-REVIEW, L-QUESTIONS, L-WORTH, L-DECIDE, L-MERGE]
last_delta: none
---

# J-REVIEW: Review an idea and decide

**Who:** a reviewer (Meera). **Ends:** a decision the sharer has read, inside 5 working days.

## `J-REVIEW.main` Main path: decide without asking

| # | Screen | The reviewer | The system |
|---|---|---|---|
| 1 | `S-R1` | Opens the next idea from "To review" (sorted by time left) | Marks it opened; closes the sharer's edit window (`L-REVIEW.open/1`) |
| 2 | `S-R2` | Reads the idea, or listens to it; opens the files, her own words, the draft history | `C-LISTEN`, `S-R2.left` |
| 3 | `S-R2` | If the idea is worth more than its sharer could put into numbers: "Revise what it's worth", changes the figures or the category, adds a note | Stores both sets; tells the sharer (`L-WORTH`) |
| 4 | `S-R2` | Checks "Similar ideas": previews one; merges if it is the same problem | `J-REVIEW.merge` |
| 5 | `S-R2` panel | "Decide on this idea" | Panel → Deciding |
| 6 | `S-R2` panel | Chooses Pick, Not now or Not picked; writes the reason (30+ characters); "Send decision to Kavya" | The sharer reads it at once; the committee's 30-day window opens (`L-DECIDE.rules`) |
| 7 | `S-R2` panel | Sees "Decision sent to Kavya" with the committee's window | The idea moves to "Decided this week" |

## `J-REVIEW.ask` Optional path: ask first

| # | Screen | The reviewer | The system |
|---|---|---|---|
| A1 | `S-R2` | Opens "Ask Kavya first", or presses "Ask about this" on a part | The section opens; the suggestion for that part is queued |
| A2 | `S-R2` | Types questions in their own words (each pinned to a part), adds suggestions, sets the time to answer | Shows the deadline before sending |
| A3 | `S-R2` | "Send 3 questions to Kavya", or changes their mind: "Decide without asking" | Sharer notified; idea → "Waiting on the sharer" |
| A4 | `S-R1` / `S-R2` | Watches the clock: answered count, seen time, time left; may give 2 more days or send a reminder | `L-QUESTIONS.clock` |
| A5 | `S-R2` | Reads each answer under its part; may ask a follow-up; then decides (step 5) | |

## `J-REVIEW.merge` Merge two ideas (forced team-up)

| # | The reviewer | The system |
|---|---|---|
| M1 | "Preview" on a similar idea: reads it next to the one being reviewed | `C-PREVIEW` reviewer's view |
| M2 | "Merge": chooses which idea leads, leaves "Team them up" ticked, writes a note to both | `C-SHEET-MERGE` |
| M3 | "Merge and tell both" | One idea survives; both sharers credited and told; the other sharer joins the crew; the committee can reverse for 30 days (`L-MERGE.desk`, `L-MERGE.effects`) |

Acceptance: `V-ACC.review`.

## `J-REVIEW.boards` Boards to walk on the canvas

`Desk`, `DeskIdea`
