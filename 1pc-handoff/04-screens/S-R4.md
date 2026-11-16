---
id: S-R4
title: Ones Committee
rev: 1
status: baseline
source: reference/prototype/Committee.dc.html
depends_on: [C-SIDEBAR, C-TABS, C-SORTS, C-PILL, C-FIELD, C-FIELD-MSG, L-COMMITTEE]
last_delta: none
---

# S-R4: Ones Committee

**Route (proposed):** `/committee`. **Boards:** `Committee`

## `S-R4.purpose` Purpose

Every decision the review desk made, for 30 days after: read it, extend its window, or reverse it with a note.

## `S-R4.layout` Layout

1. Title "Ones Committee"; a summary ("3 decisions open to review. You reversed 1 this month."); and the standing explanation: "The review desk decides on the committee's behalf, and the sharer hears at once. For 30 days after, you can reverse a decision, with a note the sharer reads. Extend a window 30 days at a time, up to 3 months. Then it expires and the decision stands."
2. Tabs with counts: In the window, Reversed, Expired. Sort: Closing soonest, Decided, Area.
3. A table: **Idea** (title; "IDEA-2026-001433, Swati Kulkarni, Distributor services, Mumbai"), **The review desk's decision** (pill, "by Meera from the review desk, Monday 12 October", and the reason in full), **Your window** ("22 days left", "Until Wednesday 16 December"; if extended an "Extended" pill and "Extended once"), **Action** ("Review").

## `S-R4.states` States (board tweaks)

| Tweak | States |
|---|---|
| `tab` | In the window; Reversed (rows show the original decision, "Now: Picked by Rohan Mehta, Friday 13 November", "Reversed Friday 13 November. Final. Kavya has the note.", action "See it"); Expired ("Expired Wednesday 18 November. After 30 days. The decision stands.", action "See it") |
| `view` | List; Reviewing a decision (the row opens in place: "The review desk's reason, as Kavya read it", the window line "Open until Wednesday 16 December. You can extend it 30 days at a time, up to Tuesday 16 February 2027. When it closes, the decision stands.", and two actions at the right: "Extend to Friday 15 January 2027" (line) and "Reverse the decision" (line)); Reversing (a form in place: "Reverse the decision. On "{title}". The review desk picked it. Kavya reads your note at once, and Meera from the review desk sees it too."; "Change it to" with the two other decisions as radio rows, each with its line ("Right problem, wrong time. It comes back to the review desk in 3 months." / "It won't go ahead."); "Your note to Kavya" with "Kavya reads this word for word."; "This is final. The review desk's decision stays on record, next to yours."; bottom right "Back" and "Reverse and tell Kavya") |

## `S-R4.rules` Rules

1. Rules: `L-COMMITTEE`. Field rules: `V-FIELDS.committee`.
2. Extend acts in place: the row updates to the new date with the "Extended" pill; the button then offers the next 30 days; `NOT DRAWN:` it is replaced by "At the 3-month limit" when no extension remains.
3. Reversing fires the spark burst, moves the row to Reversed and updates its counts.
4. The sidebar shows "Ones Committee" as current and a "Closing soonest" section.
5. No phone board; cards on phone.

## `S-R4.reference` Reference (generated)

### Board `Committee` (1440×1000)

- Canvas caption: R4 · Ones Committee: every decision with its 30-day window; extend 30 days at a time up to 3 months, or reverse it with a note the sharer reads (tweaks: tab, view)
- Prototype: `reference/prototype/Committee.dc.html`
- Exact copy and controls in every state: `reference/copy/Committee.md`
- Board-specific CSS: `reference/css/boards/Committee.css`
- Default screenshot: `reference/shots/Committee.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `tab` | In the window; Reversed; Expired | `Committee__tab-*.jpg` (2) |
| `view` | List; Reviewing a decision; Reversing | `Committee__view-*.jpg` (2) |

Links out, as wired on the board: S-H5 (Inbox); S-H6 (Your profile and settings, Rohan Mehta)
