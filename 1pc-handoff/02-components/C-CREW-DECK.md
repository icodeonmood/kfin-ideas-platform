---
id: C-CREW-DECK
title: Find your crew: deck of cards
rev: 1
status: baseline
source: reference/css/boards/Crew.css
depends_on: [C-PILL, C-AVATAR, C-SHEET-TEAMUP, F-MOTION]
last_delta: none
---

# C-CREW-DECK: Find your crew: deck of cards

Ideas close to yours, one card at a time, as a pack of cards.

## `C-CREW-DECK.card` A card

440×540px on desktop (the whole screen on phone), radius 28px, white, with a soft blue-to-peach light across its top band; the edges of the next two cards show under it. In order: status pill; title; "Investor service, Hyderabad"; then a full-width blue-wash strip with a small spark slash saying why it is shown to you ("Same R07 SMS as your idea from Saturday", "Your area, Investor service", "Same office as you, Hyderabad"); "The problem, in their words" with one sentence; "They're looking for" with one sentence; crew faces + "Ravi Nair and 3 others on it"; and one full-width primary button, "Team up".

## `C-CREW-DECK.behaviour` Behaviour

1. All cards sit in one pile, in the same place. Only the front card and the edge of the next are visible.
2. **Next**: the front card lifts out to the right with a slight tilt (to 46% of its width, 18px up, 6°), then tucks behind the pile (scales to .9, drops 26px, fades), and the next card is in front. About 620ms, `cubic-bezier(.45,0,.25,1)`.
3. **Previous**: the reverse. The last card comes out from behind and lands on top.
4. Controls centred under the card: round Previous and Next buttons (Previous disabled on the first card), then a row of pager dots with the current one as a short bar; the position is also given in words for screen readers ("Idea 1 of 5"). Also ← and → keys. Next on a card is a "pass".
5. With reduced motion the cards swap without the flight.
6. Phone: the card fills the screen; swipe left for the next, swipe up for the detail; "Team up" is a glass button at the bottom right that shrinks to an icon after first use. `OPEN:` `P-DECISIONS.open/8`.

## `C-CREW-DECK.states` States

| State | Shows |
|---|---|
| Cards | The deck; a side list "Your crews" ("Ideas you team up on show here.") and "None passed" |
| Filters open | A filter panel: Location, Category, Idea status, Team size (Just the lead, 2 to 3 people, 4 or more), Looking for; each option with a live count; "Clear all" and "Show 2 ideas" |
| Request / Request sent | `C-SHEET-TEAMUP`; the card then shows "Waiting for Ravi" |
| Approved | The card shows "You're on this crew" and "Say hello to Ravi" |
| Nothing yet | "No crews to join yet. We look for ideas close to the problems you've shared. Share one and we'll show you people working on the same thing, or browse the Wall for ideas you can help with." + "Browse the Wall" |
| Everyone seen | "That's everyone for now. You asked to team up on 1 idea. New ideas close to yours show up here." + "See them again"; "5 passed" with "Undo last pass" |

Matching and ordering: `L-CREW`.

## `C-CREW-DECK.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Crew.css` (classes: `.pcard`, `.deck`)
- Resolved values as painted: `reference/computed/components.md`, section `C-CREW-DECK` (card)
- Used on: `S-03`, `S-H2`, `S-H6`
