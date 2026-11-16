---
id: C-SIMGRID
title: Similar ideas: tiles and grid
rev: 1
status: baseline
source: reference/css/similar-grid.css
depends_on: [C-PILL, C-AVATAR, C-PREVIEW, C-SHEET-TEAMUP]
last_delta: none
---

# C-SIMGRID: Similar ideas: tiles and grid

## `C-SIMGRID.tile` A similar-idea tile

Radius 20px tile, in this order: status pill; title (500, display); "IDEA-2026-001412, Investor service, Hyderabad"; a match line ("Close match: same SMS, same calls" / "Related: the calls you describe"); crew faces + "4 colleagues on it"; an action row with "Preview" (text button, left) and "Team up" (primary small, right).

After a request: the action row shows "Waiting for Ravi" with "Withdraw". After approval: "On the crew".

## `C-SIMGRID.grid` The grid on Check it

1. A grid three across (two at narrower widths, one on phone). The first tile is always the person's own idea, marked "Yours, not sent yet", with its title and summary and no actions.
2. Then the similar ideas, closest first. With many matches the grid shows up to eight more (a 3×3 with yours); beyond that, "Show more".
3. Under the grid: "None of these the same? Just carry on. Yours goes on its own."
4. After "Keep mine separate": the grid folds to a note, "Kept separate. The review desk still sees the similar ideas next to yours." with "Show them again".

## `C-SIMGRID.other` Other places

| Place | Form |
|---|---|
| `S-06` Status | A card "Colleagues on something similar" with the same tiles in a row |
| `S-R2` reviewer | A "Similar ideas" card as a list: title (opens the preview), reference, lead, place, crew size, match line; "Preview" and "Merge" at the right |
| `S-04B` draft panel | One quiet line with the count; opening it lists titles only |

Matching: `L-SIMILAR`.

## `C-SIMGRID.reference` Reference (generated)

- Source rules in the prototype: `reference/css/similar-grid.css` (classes: `.simgrid`, `.sgt`)
- Resolved values as painted: `reference/computed/components.md`, section `C-SIMGRID` (tile, yours)
- Used on: `S-05`, `S-R2`
