---
id: C-QCARD
title: Questions card
rev: 1
status: baseline
source: reference/css/boards/Status.css
depends_on: [C-PILL, C-BUTTON]
last_delta: none
---

# C-QCARD: Questions card

How the review desk's questions appear everywhere except the Answer screen. It is a card with a button, never a text box.

## `C-QCARD.anatomy` Anatomy

1. Header: the reviewer's avatar; "Meera from the review desk, Monday 16 November, 11:20 am"; a countdown pill ("3 days left"; under a day, hours and minutes in the warn variant: "07:38 left").
2. Title: "Meera has 3 questions for you".
3. The questions, numbered. Each: the question text, and "Answer goes to" followed by the part of the idea it is pinned to (The problem, How often, Who it affects, What it's worth, Attached, Fix).
4. Deadline line: "Answer by Thursday 19 November, 6 pm. One at a time, typed or spoken."
5. One button, bottom right: "Answer the questions" → `S-R3`.

## `C-QCARD.states` States

| State | Card |
|---|---|
| Waiting | As above |
| Partly answered | `NOT DRAWN:` answered questions show a tick; the button reads "Carry on answering" |
| Answered | Title "Meera's 3 questions, answered", an "Answered" pill, "Answered on Monday 16 November, 4:32 pm. Your answers are below, each added to its part of your idea." Each answer shows under its question with "Added to <part>" and any files |
| Overdue | The countdown reads "Overdue by 5 hours"; the button still works until the reviewer decides |

## `C-QCARD.places` Where it appears

`S-03` Home (compact, in "Needs you"), `S-06` Status, `S-08` conversation, `S-H5` Inbox reader. Rules: `L-QUESTIONS`.

## `C-QCARD.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Status.css` (classes: `.verq`, `.qn`)
- Used on: `S-05`, `S-06`, `S-06B`, `S-08`, `S-R3`
