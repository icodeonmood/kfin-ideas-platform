---
id: C-FIELD-MSG
title: Field errors and warnings
rev: 1
status: baseline
source: reference/css/field-messages.css
depends_on: [F-COLOR, F-MOTION]
last_delta: none
---

# C-FIELD-MSG: Field errors and warnings

There are no snackbars, toasts or Undo messages anywhere in the product (`P-DECISIONS.taken/12`). What went wrong, or what needs attention, is said right under the thing it is about.

## `C-FIELD-MSG.anatomy` Anatomy

A soft tinted note directly under its field or group: fits its content (max 100% of the field), margin-top 8px, padding 7px 12px 7px 9px, radius 12px, font 500 13.5px / 1.45. A 16px round icon leads: white "!" on a filled disc, or a specific SVG.

| Kind | Fill | Text and icon | Inner ring |
|---|---|---|---|
| Error | `--badW` | `--badT` | `inset 0 0 0 1px rgba(180,35,24,.14)` |
| Warning | `--warnW` | `--warnT` | `inset 0 0 0 1px rgba(181,71,8,.16)` |

## `C-FIELD-MSG.behaviour` Behaviour

1. Placement: immediately below the component it refers to. For a group (the sorting card, a chip set), below the whole group. Never at the top of the page, never floating.
2. Arrival: drops in from 4px above over 280ms; an error also nudges sideways once.
3. `role="alert"` so it is announced; the field points at it with `aria-describedby`.
4. It stays until the cause is fixed, then disappears without animation. It does not time out.
5. One message per field. If two things are wrong, show the one the person must fix first.
6. A blocking condition that is not about a field (microphone blocked, offline) uses the same warning style under the control it affects: the mic note sits under the prompt box.
7. A successful change is shown by the content itself changing (a row updates, a pill changes, a banner unfolds in place), not by a message.

Message texts: `V-FIELDS`.

## `C-FIELD-MSG.reference` Reference (generated)

- Source rules in the prototype: `reference/css/field-messages.css` (classes: `.err`, `.caperr`, `.cerr`, `.blkn`)
- Resolved values as painted: `reference/computed/components.md`, section `C-FIELD-MSG` (error, error under a group)
- Used on: `S-02`, `S-04`, `S-04B`, `S-05`, `S-06B`, `S-08`, `S-R2`, `S-R4`
