---
id: J-RESUME
title: Start anywhere, finish anywhere
rev: 1
status: baseline
source: reference/prototype/Home.dc.html
depends_on: [S-03, S-04B, S-H3, S-H5, L-DRAFT]
last_delta: none
---

# J-RESUME: Start anywhere, finish anywhere

**Who:** an employee with an unfinished draft, or who sent something in by email or Teams. **Ends:** the draft is open where they left it.

## `J-RESUME.steps` Steps

| # | Where | What happens | Rules |
|---|---|---|---|
| 1 | Phone, `S-04` | The person starts by voice, then leaves (closes the tab, loses signal, the session expires) | Saved within 2 seconds of each pause, on the account and the device (`L-DRAFT.autosave`) |
| 2 | Desktop sidebar, Home, My ideas | The draft is listed under "Drafts" with "Friday, on your phone" | `C-SIDEBAR.anatomy/4`, `S-07.rows` |
| 3 | `S-04B` | "Carry on" opens it: "Picked up where you left off. Last saved on your phone, Friday 8:42 pm." Messages, files, parts, pins, sorting and the step are as they were | `L-DRAFT.autosave/2,4` |
| 4 | `S-04` | Or, starting fresh while a draft exists: "You have a draft from Friday… Continue it here, or start a new one below." | `L-DRAFT.autosave/6` |
| 5 | Email or Teams | The person forwards a thread or sends a voice note | Lands as a draft; personal details hidden first; an Inbox item "kept your draft" | `L-DRAFT.channels` |
| 6 | `S-H3` or the Inbox | "Check and send" opens that draft on `S-04B` with a banner saying where it came from | `S-04.states` "Forwarded from email" |
| 7 | `S-02` | If the session expired mid-draft: "Sign in again to carry on." and back to the same step | `L-AUTH.rules/5` |

Acceptance: `V-ACC.resume`.

## `J-RESUME.boards` Boards to walk on the canvas

`Home`, `ComposeResume`, `Ways`
