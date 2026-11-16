---
id: C-HIDDEN
title: Hidden personal details
rev: 1
status: baseline
source: reference/css/boards/Compose.css
depends_on: [C-CHIP, C-BUTTON]
last_delta: none
---

# C-HIDDEN: Hidden personal details

How a customer's personal detail found in the person's words is shown and controlled.

## `C-HIDDEN.where` Where it shows

| Place | Form |
|---|---|
| In the person's own text box | Their words stay exactly as typed. The detail gets a dotted underline. Nothing is replaced while they type |
| In the conversation receipt | "Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10." |
| In the draft panel | One folded bar: "Personal details hidden", "Folio number, PAN and phone number", and a count. Opens to a list |
| On Check it and Status | A "Hidden from everyone" tile with chips: "Folio ••••89", "Phone ••••10", "+2 more" (opens the full list) |
| Everywhere others can see | Only the masked form |

Masked form: the kind, then dots, then the last two characters: "Folio ••••89", "PAN ••••4F", "Phone ••••10".

## `C-HIDDEN.list` The open list

Each row: the kind, the masked value, a status line ("Hidden from everyone but you"), and "Show it".

1. "Show it" opens a question in the row: "Only show it if it isn't about a real customer. What is it?" with three choices (single choice): "it's a scheme or product code", "it's an internal reference", "it's made up for the example".
2. Actions: "Keep it hidden" (text) and "Show it" (primary small, disabled until a choice is made). A line says "We note your reason with the idea."
3. After showing: the row reads "Shown, because it's a scheme or product code." with "Hide it" to reverse.
4. Focusing a row underlines the matching phrase in the person's text.

Rules and logging: `L-HIDE`.

## `C-HIDDEN.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Compose.css` (classes: `.hidb`, `.hidl`)
- Used on: `S-04`, `S-04B`
