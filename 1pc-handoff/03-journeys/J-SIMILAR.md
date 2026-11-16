---
id: J-SIMILAR
title: Someone raised it already: merge request, or go it alone
rev: 1
status: baseline
source: reference/prototype/Review.dc.html
depends_on: [S-05, S-H2B, S-06, C-PREVIEW, C-SHEET-TEAMUP, L-SIMILAR, L-MERGE, L-TEAMUP]
last_delta: none
---

# J-SIMILAR: Someone raised it already: merge request, or go it alone

**Who:** a sharer (Kavya) whose draft matches an existing idea, and that idea's lead (Ravi).

## `J-SIMILAR.steps` Steps

| # | Who, where | What happens | Rules |
|---|---|---|---|
| 1 | Kavya, `S-04B` | A quiet line in the draft: "2 similar ideas" | `L-SIMILAR.rules/4` |
| 2 | Kavya, `S-05` part 3 | The grid: hers first, then the matches. She opens "Preview" on the closest | `C-SIMGRID.grid`, `C-PREVIEW` |
| 3 | Kavya, the sheet | From the preview or the tile: "Team up". She writes a note (30+ characters) and chooses "Ask Ravi to merge mine in" or "Keep mine separate" | `C-SHEET-TEAMUP`, `L-MERGE.request/1–3` |
| 4a | Kavya | Keep separate → carries on to send hers; the reviewer will see she kept it separate | `L-SIMILAR.rules/8` |
| 4b | Kavya | Ask to merge → "Sent to Ravi". Her draft is held: "Waiting for Ravi to accept the merge." Submit is unavailable; she can withdraw the request | `L-MERGE.request/4` |
| 5 | Ravi, `S-H2B` | An Inbox item: her note, a summary of her idea, and three answers: Decline, Team up only, Merge it | `L-TEAMUP.rules/5` |
| 6a | Ravi: Merge it | Kavya: "Merged into IDEA-…, with credit to you. Nothing else to send." She is on Ravi's crew; her draft closes as merged | `L-MERGE.effects` |
| 6b | Ravi: Team up only | Kavya is on Ravi's crew; her draft stays hers and can be sent on its own | `L-MERGE.request/6` |
| 6c | Ravi: Decline | Kavya sees his reason; the button becomes "Send mine on its own" | `L-MERGE.request/7` |
| 7 | Later, review desk, `S-R2` | A reviewer who sees two separate ideas about one problem can merge them and team the sharers up without asking | `J-REVIEW`, `L-MERGE.desk` |

Acceptance: `V-ACC.similar`.

## `J-SIMILAR.boards` Boards to walk on the canvas

`Review`, `CrewRequest`, `Status`
