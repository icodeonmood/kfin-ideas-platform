---
id: C-DROPDOWN
title: Dropdown with multi-select
rev: 1
status: baseline
source: reference/css/team-up-sheet.css
depends_on: [C-FIELD]
last_delta: none
---

# C-DROPDOWN: Dropdown with multi-select

1. `C-DROPDOWN/1` Looks like a field (48px, radius 12px, 1px border) with the current selection as text and a chevron at the right. Collapsed by default.
2. `C-DROPDOWN/2` Nothing is selected by default. The empty state reads "None picked" in `--mute`. There is no "none" option in the list: an empty selection means none.
3. `C-DROPDOWN/3` Opening shows the options under the field as rows with a tick box, a title and a meta line. Any number can be ticked; the list stays open while ticking.
4. `C-DROPDOWN/4` The field summarises: one selected → its title; several → "2 ideas picked".
5. `C-DROPDOWN/5` Button with `aria-expanded` and `aria-controls`; the list is a group of checkboxes. Escape closes the list (not the sheet) when it is open.
6. `C-DROPDOWN/6` The chevron turns 180° when open (200ms).

Used in `C-SHEET-TEAMUP`. Use the same component wherever a list of the person's own items is offered as an optional multi-choice.

## `C-DROPDOWN.reference` Reference (generated)

- Source rules in the prototype: `reference/css/team-up-sheet.css` (classes: `.rq-dd`)
- Used on: `S-03`, `S-06`, `S-09`, `S-H2`
