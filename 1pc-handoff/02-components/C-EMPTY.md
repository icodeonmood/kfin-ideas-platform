---
id: C-EMPTY
title: Empty states
rev: 1
status: baseline
source: reference/copy/MyIdeas.md
depends_on: [F-COPY, C-CARD, C-BUTTON]
last_delta: none
---

# C-EMPTY: Empty states

## `C-EMPTY.anatomy` Anatomy

Inside the card or list area it replaces: a short title (h3), one or two lines saying what will show here, and at most one action. Centred in a card; left-aligned in a list.

## `C-EMPTY.kinds` Three kinds

| Kind | When | Example |
|---|---|---|
| First time | The person has nothing yet | "Nothing shared yet" + "Share your first problem" |
| Filtered to nothing | A filter or search has no matches | "Nothing with the review desk right now." + "Show all ideas"; if another list has matches, also "See 1 in Teamed up" |
| All done | The person has gone through everything | "That's everyone for now" + "See them again" |

## `C-EMPTY.rules` Rules

1. Never a blank area. Never an illustration standing in for words.
2. The action fills the state (share, clear the filter, browse the Wall); it is a primary button only in the first-time kind.
3. Exact texts per screen are in each screen module under `states`.

## `C-EMPTY.reference` Reference (generated)

- Source rules in the prototype: `reference/copy/MyIdeas.md` (classes: `.emp`)
- Used on: `S-WALL`
