---
id: C-ONES-FAN
title: The Ones: fan of cards
rev: 1
status: baseline
source: reference/css/boards/Home.css
depends_on: [C-AVATAR, F-COLOR, F-MOTION]
last_delta: none
---

# C-ONES-FAN: The Ones: fan of cards

On Home, the posts from the Ones (people whose fixes shipped) sit as a fan of cards.

## `C-ONES-FAN.card` A card

341×511px, radius 28px, a dark card (`#18191D`, white text, a faint white inner ring and a deep drop shadow) lit by its One's tier colour. Top: avatar with tier ring, name, "One No. 1, Tier 4, Blaze", how long ago ("2d"). Body: one sentence on what changed. A "Shipped" pill and, if any, "Adopted by 3 teams". One big figure with its unit line ("1,240" / "failed debits avoided last quarter"). Footer: a like count, "Read the thread", a comment count.

## `C-ONES-FAN.behaviour` Behaviour

1. **Stacked** at rest: cards overlap as a fan, the first on top, the rest peeking with a slight rotation.
2. **Spread**: on first interaction (click, focus, arrow, wheel or swipe) the fan opens into a row. Gap between cards when spread: 12px (desktop and phone).
3. **Moving**: Previous and Next buttons, ← and → keys, a sideways swipe or trackpad swipe, and the mouse wheel.
4. **Wheel**: with the pointer over the cards, wheel down goes to the next card and wheel up to the previous one, one card per wheel step. While stacked, the first wheel down spreads the fan. At the last card, wheel down scrolls the page on; at the first card, wheel up scrolls the page up. The page never gets stuck.
5. A position line: "Post 1 of 4".
6. Cards tilt slightly toward the pointer. With reduced motion, cards move without gliding and do not tilt.
7. On phone the row scrolls by swipe with snap.

## `C-ONES-FAN.states` States

| Count | Shows |
|---|---|
| None | "No Ones yet. When a shared fix ships and its result is measured, the people behind it are posted here first." |
| One | The card, plus a companion card: "The next One could be you. Every fix here started with one person saying what kept going wrong." |
| Several | The fan |

Data: `A-API.ones-posts`. "See the Wall" links to `S-WALL`.

## `C-ONES-FAN.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Home.css` (classes: `.ofan`, `.ocard`)
- Resolved values as painted: `reference/computed/components.md`, section `C-ONES-FAN` (card)
- Used on: `S-03`
