---
id: F-ICONS
title: Icons and the brand mark
rev: 1
status: baseline
source: reference/icons/INDEX.md
depends_on: [F-COLOR]
last_delta: none
---

# Icons and the brand mark

## `F-ICONS.style` Icon style

1. Line icons on a 24×24 grid, `fill: none`, `stroke: currentColor`, round caps and joins.
2. Stroke width 1.8 for navigation and informational icons, 2 for actions, 2.2 for small close and tick marks (so they hold at 14 to 18px). The current phone tab thickens to 2.2.
3. Drawn sizes: 20px in the sidebar, 24px in the phone tab bar, 16 to 18px inside buttons and rows, 14px inside pills and chips.
4. Icons take the colour of their text. The only coloured icons are file-type badges (`C-FILE`) and the brand mark.
5. Every decorative icon is `aria-hidden="true"`. An icon-only button carries the label.
6. The set matches Lucide closely. Use the project's icon library where an equivalent exists; where it does not, take the SVG from `reference/icons/`. `reference/icons/INDEX.md` lists all 169 distinct SVGs on the boards with how often and where each is used.

## `F-ICONS.mark` The brand mark

The mark is a percent sign: two rings and a slash with a dot. The rings are ink; the slash and the dot are spark.

```svg
<svg viewBox="0 0 200 240" role="img" aria-label="1% Club">
  <circle cx="52" cy="58" r="34" fill="none" stroke="#111111" stroke-width="14"/>
  <circle cx="148" cy="184" r="34" fill="none" stroke="#111111" stroke-width="14"/>
  <polygon points="34,236 146.9,27.2 169.1,40.8" fill="#F46835"/>
  <circle cx="171.6" cy="11.8" r="9" fill="#F46835"/>
</svg>
```

1. Sizes: 22×26px beside the word "1% Club" in the sidebar and phone top row; larger on Landing, Sign in and the launch screen (see those screens).
2. The word beside it: "1% Club", display face, weight 600, 18px (sidebar) to 21px, tracking −0.02em to −0.03em.
3. On a dark surface the rings are white; the slash and dot stay spark.
4. The mark is the only place spark orange appears in the interface chrome (`F-COLOR.principles/3`).
5. The slash is the "1% spark" used in the send burst (`F-MOTION.inside`, "The 1% spark").
6. Do not redraw, recolour, outline or animate the mark except where `S-06` (drawn once in the header when an idea is first shared) and `S-LAUNCH` specify.

## `F-ICONS.avatars` Avatars

Initials on a neutral disc: 44px in bars, 36px small, 32px in crews (overlapping by 8px with a 2px white ring), 28px in tight rows. Font 600, 11 to 14px. Tier rings follow `F-COLOR.tiers`. No photos in draft 0.
