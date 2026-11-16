---
id: C-CHIP
title: Chips (single and multi choice)
rev: 1
status: baseline
source: reference/css/kit.css
depends_on: [F-COLOR, F-MOTION]
last_delta: none
---

# C-CHIP: Chips (single and multi choice)

## `C-CHIP.anatomy` Anatomy

Pill-shaped button: height 40px on desktop (44px on phone and in the base kit), padding 0 15px to 16px, radius 999px, font 500 14px to 14.5px / 1 on desktop (15px on phone), white fill with a 1px `--edge` inset outline. Optional 14px leading icon or tick, 7px gap. Optional trailing count in `--mute`.

## `C-CHIP.states` States

| State | Look |
|---|---|
| Rest | Card fill, `--edge` outline, ink text |
| Hover | Outline turns ink |
| Selected | `--wash` fill, `--blueT` text, 1.5px `--blue` inset ring, and a leading tick on choice chips (sorting, filters on phone) |
| Pressed | Scale .97 |
| Disabled | `NOT DRAWN:` 50% opacity, not focusable |

## `C-CHIP.behaviour` Behaviour

1. **Single choice** ("Pick one"): `role="radiogroup"` with `role="radio"` chips and `aria-checked`. Arrow keys move, Space selects. Exactly one is selected once any is.
2. **Multi choice** ("Pick all that apply"): buttons with `aria-pressed`. Any number, including none.
3. **Filter chips** (Wall kinds, My ideas filters on phone): single choice with an "All" option; selecting one re-filters at once. Counts update live.
4. When the selection changes, a ring slides from the old chip to the new one and the new one pops on the spring (`F-MOTION.inside`, "Choices land").
5. A chip set that offers more options than fit ends with a text button ("Search all groups", "Search all areas") that opens a searchable list.
6. On phone, long chip rows scroll sideways edge to edge (`F-SPACE.scroll/4`).

## `C-CHIP.reference` Reference (generated)

- Source rules in the prototype: `reference/css/kit.css` (classes: `.chip`)
- Resolved values as painted: `reference/computed/components.md`, section `C-CHIP` (rest, selected, radio selected)
- Used on: `S-04`, `S-04B`, `S-05`, `S-06B`, `S-07`, `S-WALL`, `S-R2`, `S-H2`, `S-H2B`, `S-H5`
