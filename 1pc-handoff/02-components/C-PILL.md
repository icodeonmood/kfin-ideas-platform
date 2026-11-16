---
id: C-PILL
title: Status pill
rev: 1
status: baseline
source: reference/css/kit.css
depends_on: [F-COLOR]
last_delta: none
---

# C-PILL: Status pill

## `C-PILL.anatomy` Anatomy

Inline, not interactive: a 7px dot, 7px gap, words. Padding 4px 10px, radius 999px, font 500 13px / 1.4, never wraps. Height 26px.

## `C-PILL.variants` Variants

| Variant | Fill | Text | Dot |
|---|---|---|---|
| Neutral | `--sunk` | `--ink` | `--faint` |
| Blue | `--wash` | `--blueT` | `--blue` |
| OK | `--okW` | `--okT` | `--okD` |
| Warn | `--warnW` | `--warnT` | `--warnD` |
| Bad | `--badW` | `--badT` | `--badD` |
| On a gradient band | `rgba(255,255,255,.2)` | white | white |
| Outline ("Coming soon") | transparent, 1px `#BDBDB7` inset | `#3F3F44` | none |

## `C-PILL.rules` Rules

1. Which status gets which variant is fixed in `E-ENUMS.idea-status`. Do not choose colours per screen.
2. The words are the status. The dot is never shown alone.
3. A countdown next to a pill ("3 days left") is its own small pill in the warn variant when under a day, else neutral text.

## `C-PILL.reference` Reference (generated)

- Source rules in the prototype: `reference/css/kit.css` (classes: `.pill`)
- Resolved values as painted: `reference/computed/components.md`, section `C-PILL` (blue, warn, neutral, ok)
- Used on: `S-03`, `S-04`, `S-04B`, `S-05`, `S-06`, `S-06B`, `S-07`, `S-08`, `S-09`, `S-WALL`, `S-R2`, `S-R4`, `S-H2`, `S-H2B`, `S-H3`, `S-H5`
