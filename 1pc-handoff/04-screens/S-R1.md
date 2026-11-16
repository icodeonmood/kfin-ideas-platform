---
id: S-R1
title: Review desk
rev: 1
status: baseline
source: reference/prototype/Desk.dc.html
depends_on: [C-SIDEBAR, C-SEARCH, C-TABS, C-SORTS, C-PILL, L-REVIEW, L-QUESTIONS]
last_delta: none
---

# S-R1: Review desk

**Route (proposed):** `/desk`. **Boards:** `Desk`

## `S-R1.purpose` Purpose

The reviewer's queue: what to open next, and every clock that is running.

## `S-R1.layout` Layout

1. Title "Review desk" and a summary line of what needs attention ("3 waiting on colleagues. One is overdue and one has under a day left. 2 answered and back with you.").
2. Search bar ("Search the desk", "Filter").
3. Tabs with counts (`C-TABS`): To review, Waiting on the sharer, Answered back to you, Decided this week. Sort at the right (`C-SORTS`): Time left, Decide by, Area.
4. A table: **Idea** (title; "Kavya Menon, Investor service, Hyderabad"), **Questions** ("0 of 3 answered, seen 12:05 pm" / "Not seen yet" / "No questions asked" / "Both answered, 1 hour ago"), **Time left** (a countdown pill: "3 days to answer", "07:38 to answer", "Overdue by 5 hours" in the bad variant; on To review "6 days to decide"), **Decide by** (date), **Action** (one button per row, all the same width, at the row's right edge: "Open", "Read answers", "Remind Divya").
5. On "Decided this week" the columns are Idea, Questions, Decision ("Picked, 2 November"; "Reversed: picked"), Ones Committee ("Ones Committee can review it until Wednesday 2 December"; "The Ones Committee picked it on 13 November, with a note to Kavya").

## `S-R1.rules` Rules

1. Tab contents and rules: `L-REVIEW.queue`. Clocks: `L-QUESTIONS.clock`, `L-REVIEW.clock`.
2. Countdowns update live without reloading; under a day they show hours and minutes and update each minute.
3. A row opens `S-R2` with the grow-from-row hand-over. "Remind Divya" sends the reminder in place; `NOT DRAWN:` the button then reads "Reminded, just now" for that session.
4. Tab, sort, search and scroll are restored on Back.
5. The sidebar shows "Review desk" as current and a "Waiting on sharers" section with the three most urgent ideas (dot: blue normal, amber under a day, red overdue).
6. No phone board; on phone the table becomes cards with the same five facts.

## `S-R1.reference` Reference (generated)

### Board `Desk` (1440×920)

- Canvas caption: R1 · Review desk: search first, tabs, every question’s clock, and each decision’s committee window (tweak: tab)
- Prototype: `reference/prototype/Desk.dc.html`
- Exact copy and controls in every state: `reference/copy/Desk.md`
- Board-specific CSS: `reference/css/boards/Desk.css`
- Default screenshot: `reference/shots/Desk.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `tab` | Waiting on the sharer; To review; Answered, back to you; Decided this week | `Desk__tab-*.jpg` (3) |

Links out, as wired on the board: S-H5 (Inbox, 1 unread); S-R2 (Bank mandate rejections need plain rea, Branch queue times are not tracked any, Cheque scans need re-uploading at mont); S-H6 (Your profile and settings, Meera Iyer,)
