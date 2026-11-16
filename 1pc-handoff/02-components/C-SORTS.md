---
id: C-SORTS
title: Sort control
rev: 1
status: baseline
source: reference/css/boards/MyIdeas.css
depends_on: [C-BUTTON, F-MOTION]
last_delta: none
---

# C-SORTS: Sort control

## `C-SORTS.anatomy` Anatomy

A row: the words "Sort by" (13px `--mute`), then 2 to 4 options as small text buttons (height 32px, padding 0 10px, radius 8px, 500 13.5px, `--mute2`). The selected option is ink on `rgba(17,17,17,.06)`.

## `C-SORTS.behaviour` Behaviour

1. `role="group"` with `aria-label="Sort by"`; each option is a button with `aria-pressed`. Exactly one is selected.
2. Choosing an option re-sorts at once; rows glide to their new places (`F-MOTION.inside`, "Lists re-sort").
3. Where the sort key has a column, that column's header and cells turn ink and weight 500 so the order explains itself.
4. The sort is part of the list state that is restored on Back and kept in the URL.
5. Phone: one text button with a sort icon, "Sorted by <option>", that cycles through the options on tap and announces the change (`aria-live="polite"`).

## `C-SORTS.uses` Options per screen

| Screen | Options (default first) |
|---|---|
| `S-07` My ideas | Latest activity, Date shared, Stage |
| `S-R1` Review desk | Time left, Decide by, Area |
| `S-R4` Ones Committee | Closing soonest, Decided, Area |
| `S-WALL` Just in | Popular, Newest (default), Crew size, Ones |

## `C-SORTS.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/MyIdeas.css` (classes: `.sorts`)
- Resolved values as painted: `reference/computed/components.md`, section `C-SORTS` (group, option, option on)
- Used on: `S-07`, `S-WALL`, `S-R1`, `S-R4`
