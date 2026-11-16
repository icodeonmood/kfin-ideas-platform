---
id: J-TEAMUP
title: Find your crew and team up
rev: 1
status: baseline
source: reference/prototype/Crew.dc.html
depends_on: [S-H2, S-03, S-09, S-06, S-H2B, S-08, C-CREW-DECK, C-SHEET-TEAMUP, L-CREW, L-TEAMUP]
last_delta: none
---

# J-TEAMUP: Find your crew and team up

**Who:** an employee who wants to help with someone else's idea, and that idea's lead.

| # | Who, where | What happens | Rules |
|---|---|---|---|
| 1 | Kavya: `S-H2` (or a crew card on Home, a tile on her idea's page, or a colleague's idea page) | Looks through ideas close to hers, each with why it is shown; passes or presses "Team up" | `L-CREW`, `C-CREW-DECK` |
| 2 | The sheet | Edits the drafted note (30+ characters). Optionally opens "Bring your ideas along" and ticks any of her shared ideas (none by default). "Send to Ravi" | `C-SHEET-TEAMUP.compose` |
| 3 | The sheet, then the card | "Sent to Ravi". The card reads "Waiting for Ravi"; she can withdraw | `L-TEAMUP.rules/3` |
| 4 | Ravi: `S-H2B` | Reads her note (and any idea brought). Answers: Merge it, Team up only, or Decline with an optional reason | `L-TEAMUP.rules/5–6` |
| 5 | Kavya: Inbox | "Ravi Nair approved your team-up request." The idea is in My ideas → Teamed up; its conversation is open to her; "Say hello" | `L-TEAMUP.rules/7–8` |
| 6 | Both: `S-08` | They talk in the idea's conversation | `L-CONVO` |

Acceptance: `V-ACC.teamup`.

## `J-TEAMUP.boards` Boards to walk on the canvas

`Crew`, `Home`, `Idea`, `CrewRequest`
