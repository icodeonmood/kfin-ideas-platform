---
id: L-COMMITTEE
title: The Ones Committee's window: view, extend, reverse
rev: 1
status: baseline
source: reference/copy/Committee.md
depends_on: [L-DECIDE, L-NOTIFY]
last_delta: none
---

# L-COMMITTEE: The Ones Committee's window: view, extend, reverse

## `L-COMMITTEE.rules` Rules

1. Every decision by the review desk (and every merge by the desk) opens a window of 30 days from the decision time. During it the decision is listed for every committee member under "In the window", with the reviewer's reason "as {sharer} read it".
2. **Extend**: any member can extend an open window by 30 days at a time, up to 3 months from the decision in total. The row shows "Extended", days left, the new end date and how many times ("Until Friday 11 December. Extended once"). The sharer sees the extended date on their idea.
3. **Reverse**: any member can reverse an open decision once. They choose what to change it to (one of the other two decisions; reversing to "Not now" takes a return period) and write a note of at least 30 characters to the sharer. Errors: "Choose what to change it to." / "Write a note of at least a line, 30 characters or more."
4. A reversal is **final**: the window closes, no further reversal or extension is possible. "This is final. The review desk's decision stays on record, next to yours."
5. On reversal: the idea's status changes to the new decision with all its consequences (`L-DECIDE.rules/6–8`); the sharer gets the note at once ("The Ones Committee changed the decision to not now", the note in quotes, "Was: Picked by Meera from the review desk, Monday 16 November"); the original reviewer is told; the desk's "Decided this week" row reads "Reversed: …".
6. **Expire**: when the window ends with no reversal, the decision stands. It moves to "Expired" ("Expired Wednesday 18 November. After 30 days. The decision stands.").
7. Tabs: In the window (count), Reversed (count), Expired. Sort: Closing soonest (default), Decided, Area.
8. The header summarises: "3 decisions open to review. You reversed 1 this month."
9. A member cannot reverse a decision on their own idea. `NOT DRAWN:` default: the action is hidden for that member.
10. All actions are audited: who, when, from, to, note.

## `L-COMMITTEE.states` Window states

`open → extended (n) → reversed | expired`. Dates: `opens_at`, `closes_at` (moves on extend), `max_closes_at` (decision + 3 months).

## `L-COMMITTEE.touchpoints` Where the front end depends on this

`S-R4`, `S-06`, `S-R1`
