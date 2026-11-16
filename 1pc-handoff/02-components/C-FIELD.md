---
id: C-FIELD
title: Text fields, text areas and labels
rev: 1
status: baseline
source: reference/css/kit.css
depends_on: [F-COLOR, F-TYPE, C-FIELD-MSG]
last_delta: none
---

# C-FIELD: Text fields, text areas and labels

## `C-FIELD.anatomy` Anatomy

1. **Label** above the field: 500 15px / 1.4, ink, 8px gap. An optional marker follows in normal weight and `--mute`: "Optional".
2. **Field**: min-height 48px, 1px `#8C8C91` border, radius 12px, padding 12px 14px, card fill, font 400 16px / 1.5 (16px stops iOS zooming on focus). Placeholder `#6B6B70`.
3. **Text area**: same, min-height 112px, vertical resize only.
4. **Help line** under the field (optional): 13.5px `--mute`. A live character or readiness line uses the same slot ("12 of at least 30 characters", then "Kavya reads this word for word.").
5. **Message** under the field when there is an error or warning: `C-FIELD-MSG`.

## `C-FIELD.states` States

| State | Look |
|---|---|
| Focus | Border `--blue`, ring `0 0 0 3px rgba(57,93,237,.16)`, no outline |
| Invalid | Border `--badT`, ring `0 0 0 3px rgba(180,35,24,.12)`, `aria-invalid="true"` |
| Disabled | `--sunk` fill, `--mute` text |
| Read-only | No border, text only |

## `C-FIELD.kinds` Special fields

| Field | Where | Notes |
|---|---|---|
| Work email | `S-02` | 56px tall, 17px text, `type="email"`, `inputmode="email"`, `autocomplete="email"`, placeholder "name@kfintech.com" |
| 6-digit code | `S-02` | Six boxes, numeric keypad (`inputmode="numeric"`, `autocomplete="one-time-code"`), paste fills all six, auto-advance, Backspace steps back. Shakes on a wrong code |
| Prompt box | `S-03`, `S-04`, `S-04B` | `C-PROMPT` |
| Question box | `S-R2` | Text area with a "Pinned to <part>" selector and a round send button inside the box |
| Search | `S-07`, `S-R1` | `C-SEARCH` |
| Note fields in sheets | `C-SHEET-TEAMUP`, `C-SHEET-MERGE`, `S-R4` | Text area, 3 to 4 rows, pre-filled with a drafted note the person can change |
| Number you'd like | `S-ONE` | Numeric, 1 to 999 |

## `C-FIELD.rules` Rules

1. Every field has a label; a placeholder is never the label.
2. Validation runs on blur and on submit, not on every keystroke, except live counters, which update as the person types.
3. A minimum length is stated before the person hits it: as a counter under the field or in the help line.
4. Typing in an invalid field clears its error at once.

## `C-FIELD.reference` Reference (generated)

- Source rules in the prototype: `reference/css/kit.css` (classes: `.fld`, `.lbl`)
- Resolved values as painted: `reference/computed/components.md`, section `C-FIELD` (text field, label)
- Used on: `S-04`, `S-04B`, `S-05`, `S-06`, `S-06B`, `S-R2`, `S-R4`
