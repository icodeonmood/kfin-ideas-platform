---
id: S-H2
title: Find your crew
rev: 1
status: baseline
source: reference/prototype/Crew.dc.html
depends_on: [C-SIDEBAR, C-CREW-DECK, C-SHEET-TEAMUP, C-CHIP, C-EMPTY, L-CREW, L-TEAMUP]
last_delta: none
---

# S-H2: Find your crew

**Route (proposed):** `/crew`. **Boards:** `Crew`, `PhoneCrew`

## `S-H2.purpose` Purpose

Ideas close to yours, one at a time. Team up, or pass.

## `S-H2.layout` Layout (desktop)

A "Home" back link, then three areas across. **Left**: the title "Find your crew" on a single line (`S-H2.title`: 32px so it fits the column, never wrapping), the line "Ideas close to yours. Team up, or pass.", and a row with a "Filters" button (pill, with a sliders icon) and the count "5 ideas close to yours". **Centre**: the deck (`C-CREW-DECK`) with Previous and Next and the pager dots under the card. **Right**: a small glass card "Your crews" (ideas joined or asked, with state; "Ideas you team up on show here." when empty), the passes line ("None passed" / "5 passed" + "Undo last pass") and the link "All your crews in My ideas".

## `S-H2.states` States (board tweak `view`)

Cards; Filters open; Request; Request sent; Approved; Nothing yet; Everyone seen. Content for each: `C-CREW-DECK.states`. The filter panel is a glass dialog labelled "Filter ideas".

## `S-H2.rules` Rules

1. Card order and reasons: `L-CREW`. Requests: `L-TEAMUP`.
2. The transition between cards is the pack of cards (`C-CREW-DECK.behaviour/2–3`), not a sideways slide.
3. Sending a request keeps the person on the deck: the card shows "Waiting for Ravi"; "Keep looking" moves to the next card.
4. Cinematic arrival; the front card tilts toward the pointer.

## `S-H2.phone` Phone

The card is the screen, under a compact bar (Back "Home", title). Swipe left for the next card, swipe up for the detail sheet (reference, "They're looking for", "The crew", "Open the full idea"). "Team up" is a glass button at the bottom right: full with a label the first time, then icon only (tweak `teamUp`). States: Cards, Request sent ("Waiting for Ravi"), Teamed up ("You're on it"), Everyone seen ("That's everyone for now. You teamed up on 1 idea. New ideas close to yours show up here." + "See them again").

## `S-H2.reference` Reference (generated)

### Board `Crew` (1440×920)

- Canvas caption: H2 · Find your crew: previous and next under the card; Team up sends the lead a note and, if you like, one of your ideas; zero state built (tweak: view)
- Prototype: `reference/prototype/Crew.dc.html`
- Exact copy and controls in every state: `reference/copy/Crew.md`
- Board-specific CSS: `reference/css/boards/Crew.css`
- Default screenshot: `reference/shots/Crew.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `view` | Cards; Filters open; Request; Request sent; Approved; Nothing yet; Everyone seen | `Crew__view-*.jpg` (6) |

Links out, as wired on the board: S-07 (All your crews in My ideas); S-09 (Rejection SMS codes confuse investors,); S-08 (Say hello to Ravi); S-WALL (Browse the Wall); S-04 (Share a problem)

### Board `PhoneCrew` (390×844)

- Canvas caption: Find your crew: the card fills the screen, swipe up for the detail, swipe left for the next; Team up sends the lead a request (tweaks: view, details, teamUp)
- Prototype: `reference/prototype/PhoneCrew.dc.html`
- Exact copy and controls in every state: `reference/copy/PhoneCrew.md`
- Board-specific CSS: `reference/css/boards/PhoneCrew.css`
- Default screenshot: `reference/shots/PhoneCrew.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `view` | Cards; Request sent; Teamed up; Everyone seen | `PhoneCrew__view-*.jpg` (3) |
| `details` | Closed; Open | `PhoneCrew__details-*.jpg` (1) |
| `teamUp` | Full, then icon; Icon only | `PhoneCrew__teamup-*.jpg` (1) |

Links out, as wired on the board: S-03 (Back to Home); S-07 (My ideas); S-04 (Share a problem); S-WALL (Wall); S-H5 (Inbox, 2 new); S-09 (Open the full idea)
