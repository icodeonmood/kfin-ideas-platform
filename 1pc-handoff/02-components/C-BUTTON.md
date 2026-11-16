---
id: C-BUTTON
title: Buttons
rev: 1
status: baseline
source: reference/css/kit.css
depends_on: [F-COLOR, F-TYPE, F-MOTION, F-SPACE]
last_delta: none
---

# C-BUTTON: Buttons

## `C-BUTTON.variants` Variants

| Variant | Class in prototype | Look | Use |
|---|---|---|---|
| Primary | `.btn.ink` | Ink fill, white text | The one forward action of a view |
| Line | `.btn.line` | Card fill, 1px `--edge` inset outline; outline turns ink on hover | Secondary actions: Back, Show 5 more, Merge, Preview actions |
| Soft | `.btn.soft` | `--sunk` fill, ink text; `#E0E0DC` on hover | Low-emphasis actions inside cards |
| Text | `.tb` | Underlined text (offset 4px, underline `#A3A3A6`, full colour on hover), no box | Tertiary: "Open the full idea", "Withdraw request", "Decide without asking" |
| Text, blue | `.tb.blue` | `--blueT` text, underline `#B9C3FF` | Links that open something related |
| Icon | 40 to 44px round or 12px-radius square | Icon only, with `aria-label` | Close, fold, remove, play |

## `C-BUTTON.sizes` Sizes

| Size | Height | Padding | Font | Radius |
|---|---|---|---|---|
| Regular | 48px | 0 20px | 500 15px / 1 | 12px |
| Small `.sm` | 44px | 0 16px | 500 15px / 1 | 12px |
| Full `.full` | 56px, width 100% | 0 20px | 500 16px / 1 | 12px |

Gap between icon and label 8px. Labels never wrap (`white-space: nowrap`).

## `C-BUTTON.states` States

1. Hover (primary): fill `--ink2`, a light sheen crosses once (900ms), shadow `0 14px 30px -14px rgba(17,17,17,.6)`.
2. Pressed: scale .97 in 110ms, released on the spring.
3. Focus: `F-A11Y.rules/2`.
4. Disabled: fill `--rule2`, text `#6B6B70`, no shadow, `cursor: not-allowed`. Use `aria-disabled="true"` and keep the button focusable so a screen reader can find it and hear why; clicking a disabled primary moves focus to the field that blocks it and shows its message (see `V-FIELDS`).
5. Busy: `NOT DRAWN:` label swaps to the action in progress ("Sending…") with a 12px spinner before it; the button keeps its width and ignores further clicks.

## `C-BUTTON.rules` Rules

1. One primary per view (`F-SPACE.cta/3`).
2. The primary sits at the end of the flow, bottom right; on phone it fills the dock.
3. Two buttons in a row: backward or lesser action on the left, forward on the right, 10 to 12px apart.
4. The label is the action in full (`F-COPY.buttons`).

## `C-BUTTON.reference` Reference (generated)

- Source rules in the prototype: `reference/css/kit.css` (classes: `.btn`, `.tb`)
- Resolved values as painted: `reference/computed/components.md`, section `C-BUTTON` (primary (ink), primary, regular, line, line small, text button, disabled)
- Used on: `S-01`, `S-02`, `S-03`, `S-04`, `S-04B`, `S-05`, `S-06`, `S-06B`, `S-07`, `S-08`, `S-09`, `S-WALL`, `S-ONE`, `S-LAUNCH`, `S-R1`, `S-R2`, `S-R3`, `S-R4`, `S-H2`, `S-H2B`, `S-H3`, `S-H4`, `S-H5`, `S-H6`
