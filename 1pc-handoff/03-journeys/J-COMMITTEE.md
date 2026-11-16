---
id: J-COMMITTEE
title: The Ones Committee reviews a decision
rev: 1
status: baseline
source: reference/prototype/Committee.dc.html
depends_on: [S-R4, S-06, L-COMMITTEE]
last_delta: none
---

# J-COMMITTEE: The Ones Committee reviews a decision

| # | The member | The system |
|---|---|---|
| 1 | Opens "In the window", sorted by closing soonest | Lists every decision made in the last 30 days (or its extended window) with the reason as the sharer read it |
| 2 | "Review" on a row | The row opens: the reason, the window, "Extend to <date>" and "Reverse the decision" |
| 3a | Extends | The window moves 30 days, up to 3 months in all; the sharer sees the new date |
| 3b | Reverses: picks the new decision, writes a note (30+ characters), "Reverse and tell Kavya" | Final. The idea takes the new decision; the sharer and the reviewer are told at once; the row moves to "Reversed" |
| 3c | Does nothing | When the window closes the decision stands and the row moves to "Expired" |

Rules: `L-COMMITTEE`. Acceptance: `V-ACC.committee`.

## `J-COMMITTEE.boards` Boards to walk on the canvas

`Committee`
