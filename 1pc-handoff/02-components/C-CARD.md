---
id: C-CARD
title: Cards, glass panels, notes and wells
rev: 1
status: baseline
source: reference/css/glass-and-light.css
depends_on: [F-COLOR, F-SPACE]
last_delta: none
---

# C-CARD: Cards, glass panels, notes and wells

## `C-CARD.variants` Surfaces

| Surface | Look | Use |
|---|---|---|
| Card | Radius 20px, 1px border, glass fill inside the shell (`F-COLOR.glass`), solid white on signed-out pages | The default container |
| Glass panel | Radius 20px, stronger blur and a vertical white gradient | Review side, side panels, players, filter panels |
| Tile | Radius 20px (12px for small fact tiles), `rgba(17,17,17,.03)` or white 82% fill, 1px faint inner ring | Facts inside a card: "How often", "Who it affects", worth tiles, similar-idea tiles |
| Well | `--sunk` fill, radius 12px | Inset areas, quoted text |
| Note | `--sunk` fill, radius 12px, padding 12px 14px, 14.5px text, optional leading icon | Inline explanation. Blue variant: `--wash` fill, `#1E2E99` text |
| Dark slab | `#18191D` fill, radius 28px, white text, a tier-coloured glow | "The Ones" on the Wall, the One dashboard hero |
| Dashed placeholder | 1px dashed `#BDBDB7`, radius 20px | "Coming soon" items |

## `C-CARD.rules` Rules

1. No coloured stripe down the side of a card. Meaning is carried by a pill, an icon or the content.
2. Cards do not nest more than one level: a card may hold tiles; a tile holds no card.
3. Card padding 20 to 24px desktop, 16 to 20px phone. Header row inside a card: title left, one quiet action right.
4. A card that is a link is a link as a whole: the title is the link text, the whole card is the hit area, and it has one focus ring.
5. Glass needs something behind it. On a plain background use the solid card.

## `C-CARD.reference` Reference (generated)

- Source rules in the prototype: `reference/css/glass-and-light.css` (classes: `.card`, `.glass`, `.note`, `.well`, `.panel`)
- Resolved values as painted: `reference/computed/components.md`, section `C-CARD` (card, glass, panel)
- Used on: `S-03`, `S-05`, `S-06`, `S-06B`, `S-07`, `S-08`, `S-09`, `S-02`, `S-WALL`, `S-ONE`, `S-R1`, `S-R2`, `S-R3`, `S-R4`, `S-H2`, `S-H3`, `S-H4`
