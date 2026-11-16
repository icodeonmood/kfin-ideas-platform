---
id: L-DECIDE
title: Decisions: Pick, Not now, Not picked
rev: 1
status: baseline
source: reference/copy/DeskIdea.md
depends_on: [L-COMMITTEE, L-NOTIFY, E-ENUMS]
last_delta: none
---

# L-DECIDE: Decisions: Pick, Not now, Not picked

## `L-DECIDE.options` The three decisions

| Decision | Shown to the sharer as | Reviewer's line | Extra input | Idea status after |
|---|---|---|---|---|
| Pick | "Picked" (blue) | "Take it forward. A build team is chosen next." | Optional: "join it with" a similar idea being taken forward | `picked` |
| Not now | "Not now" (warn) | "Right problem, wrong time. It comes back on a date you set." | "Look at it again in": 1 month, 3 months (default), 6 months | `not_now`, with a return date |
| Not picked | "Not picked" (neutral) | "It won't go ahead. Say what happens to her words." | The reason should say where the words go, if anywhere | `not_picked` |

## `L-DECIDE.rules` Rules

1. Every decision needs a reason of at least 30 characters. The field's question follows the choice: "Why are you picking it?", "Why not now, and what would change it?", "Why isn't it going ahead?" The counter reads "12 of at least 30 characters", then "Kavya reads this word for word."
2. Without a choice: "Choose Pick, Not now or Not picked first." With a short reason: "Give Kavya a reason of at least a line, 30 characters or more." (`V-FIELDS.decision`)
3. The reason is shown to the sharer exactly as written, at once, on their idea page, in their Inbox, on Teams and by email. There is no delay and no undo.
4. Wording check: the product never tells a sharer their idea was a "duplicate", "rejected" or "already solved". `NOT DRAWN:` default: warn the reviewer if the reason contains those words and suggest plain alternatives; do not block.
5. Sending a decision opens the Ones Committee's window (`L-COMMITTEE`) and shows it to the reviewer ("Open, 30 days left") and the sharer ("The Ones Committee can review this decision until Wednesday 16 December. If they change it, their note comes to your Inbox. After that, it stands.").
6. **Pick** → the stage "Reviewed" completes; a build team is to be chosen by a date the system sets (default 10 working days: "Team chosen by Friday 27 November"); the sharer can "Ask to join the build team".
7. **Not now** → the idea stays open with its answers and crew, leaves the active queue, and returns to "To review" on the return date ("Comes back to you and Kavya on Tuesday 16 February 2027").
8. **Not picked** → the idea closes. If its words were carried into another idea, the sharer's page says so and links to it ("Your words carry on in IDEA-2026-001412"), and the sharer gets that idea's updates.
9. A decision is recorded with: who, when, choice, reason, any join target, the return date. It is never edited; only the committee can reverse it.
10. Open question sets close when a decision is sent.

## `L-DECIDE.after` After picking (outside the review desk)

| Event | Status | Who triggers | Sharer sees |
|---|---|---|---|
| Team chosen | `being_built` | Programme admin | "Being built", the team's name, the conversation opens to the build team |
| Build updates and asks | `being_built` | Build team | Messages; asks appear in "Needs you" with a date ("Check the new rejection messages before they go live. By Thursday 19 November") |
| Shipped | `shipped` | Programme admin | "Shipped"; impact measurement starts (`L-IMPACT`) |

`OPEN:` the admin screens for choosing a team and marking shipped are not drawn. Default: an admin API plus a minimal admin page.

## `L-DECIDE.touchpoints` Where the front end depends on this

`S-R2`, `S-06`, `S-R4`
