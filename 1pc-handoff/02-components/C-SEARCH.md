---
id: C-SEARCH
title: Search bar with filters inside
rev: 1
status: baseline
source: reference/css/boards/MyIdeas.css
depends_on: [C-CHIP, C-FIELD]
last_delta: none
---

# C-SEARCH: Search bar with filters inside

## `C-SEARCH.anatomy` Anatomy

One wide glass bar (radius 20px, height 62px): a search icon, the input ("Search your ideas" / "Search the desk"), any active filter chips inside the bar, and a "Filter" button at the right end.

## `C-SEARCH.behaviour` Behaviour

1. Focusing the bar opens a suggestions panel under it: "Narrow it to" (the filters, each with a live count) and "Or ask in your own words" (three example questions).
2. Picking a filter puts it in the bar as a removable chip. Backspace in an empty input removes the last chip.
3. Typing searches by meaning across titles, the person's own words, their files and the review desk's notes. A result line says what was found and how: "Found 4 ideas about "sms": 2 of yours and 2 you teamed up on. Closest: …" then "Matched on meaning across titles, your own words, your files and the review desk's notes."
4. Typing a question ("Which of my ideas need me this week?") answers in one line and narrows the list: "One idea needs you. …" then "Read your question as "Needs you" and narrowed the list to it."
5. "Clear" resets text and chips.
6. Enter runs the search; Escape closes the panel and keeps the text.
7. Search text and filters are part of the list state restored on Back.

Back-end behaviour: `L-SEARCH`.

## `C-SEARCH.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/MyIdeas.css` (classes: `.qbox`)
- Resolved values as painted: `reference/computed/components.md`, section `C-SEARCH` (bar)
- Used on: `S-07`, `S-R1`, `S-R2`
