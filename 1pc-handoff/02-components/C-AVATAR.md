---
id: C-AVATAR
title: Avatars and crew faces
rev: 1
status: baseline
source: reference/css/sidebar.css
depends_on: [F-COLOR, F-ICONS]
last_delta: none
---

# C-AVATAR: Avatars and crew faces

## `C-AVATAR.anatomy` Anatomy

A disc with initials (two letters, 600 weight). Sizes: 44px (bars), 36px (`.sm`: sidebar foot, phone top row), 32px (crew faces), 28px (tight rows). Fill `#E2E2DE`; `#ECECE8` inside a ring.

## `C-AVATAR.ring` Rings

1. Neutral ring by default: 3px, `#D9D9DE`, with a 2px white inner ring.
2. Tier ring (conic gradient, `F-COLOR.tiers`) only where `F-COLOR.tiers/1` allows.
3. Crew faces in a preview use soft tints by position (`#FFE7D6`, `#FFE0D6`, `#FFDDE8`, `#FFD6D6`), not tier colours.

## `C-AVATAR.crew` Crew faces

1. Up to 4 faces overlap by 8px, each with a 2px white ring; then a text line: "Ravi Nair and 3 others on it" or "4 colleagues on it".
2. Each face is focusable and names its person on hover and focus (a small ink tooltip above), and exposes the name to screen readers.
3. System senders use the mark in place of initials ("1%").

## `C-AVATAR.reference` Reference (generated)

- Source rules in the prototype: `reference/css/sidebar.css` (classes: `.av`, `.pvav`)
- Resolved values as painted: `reference/computed/components.md`, section `C-AVATAR` (with tier ring)
- Used on: `S-03`, `S-04`, `S-04B`, `S-05`, `S-06`, `S-06B`, `S-07`, `S-08`, `S-09`, `S-WALL`, `S-ONE`, `S-R1`, `S-R2`, `S-R3`, `S-R4`, `S-H2`, `S-H2B`, `S-H3`, `S-H4`, `S-H5`, `S-H6`
