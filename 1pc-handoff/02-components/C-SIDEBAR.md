---
id: C-SIDEBAR
title: Sidebar (desktop navigation)
rev: 1
status: baseline
source: reference/css/sidebar.css
depends_on: [F-COLOR, F-ICONS, C-AVATAR]
last_delta: none
---

# C-SIDEBAR: Sidebar (desktop navigation)

## `C-SIDEBAR.anatomy` Anatomy

Fixed to the left edge, full height, 256px wide, frosted glass (`F-COLOR.glass`), with a soft blue glow at its top left. Padding 16px 12px. Top to bottom:

1. **Top row** (48px): the brand (mark + "1% Club", links to Home) and the fold button (40px, radius 12px).
2. **Share a problem**: ink button, 46px tall, radius 12px, a plus icon, and a `P` key hint at the right end (22px tile, white 16% fill). Links to `S-04`.
3. **Nav items** (44px tall, radius 12px, 20px icon + label, 450 15px, `--ink2`): Home, Find your crew, Wall, Inbox. Inbox has a count badge at the right end (22px tall, `--blue` fill, white 600 12px). Role-specific items follow: "Review desk" for reviewers, "Ones Committee" for committee members.
4. **Sections** (22px above the first, 16px between): a small heading (500 12.5px `--mute`) with optional actions, then rows (36px, 14px text, a 7px status dot, ellipsis).
   - "Drafts": up to 2 drafts, each with title and "Friday, on your phone". Hollow dot.
   - "Your ideas": up to 3, with "View all" → `S-07`. Dot colour = status (warn for needs you, blue for active, grey otherwise).
   - Reviewer: "Waiting on sharers" (search + "View all"), up to 3 ideas with dots (blue, warn, bad for overdue).
   - Committee: "Closing soonest", up to 3.
5. **Account row** at the foot (56px): avatar with the person's tier ring, name (500 14.5px), tier line (12.5px `--mute`). Links to `S-H6`.

## `C-SIDEBAR.states` States

| State | Look |
|---|---|
| Item hover | `rgba(17,17,17,.05)` fill, ink text |
| Item current (`aria-current="page"`) | White fill, weight 500, shadow (`F-SPACE.shadow`), `--blue` icon, and a 3px `--blue` bar at the bar's left edge |
| Share a problem current | Same 3px bar |

## `C-SIDEBAR.fold` Folding

1. The fold button narrows the bar to 76px. Icons stay put; labels, the key hint and the sections slide 8px left and fade (220 to 300ms). The content area widens with it over 340ms (`cubic-bezier(.2,0,0,1)`).
2. Folded: items are 52px wide icon buttons; the Inbox count becomes a small badge on the icon; each icon names itself in an ink tooltip to its right on hover and focus; a "My ideas" icon appears (it has no item when the bar is open because "Your ideas" covers it).
3. The fold state is remembered per person and device.
4. The button's label is "Fold the side bar" / "Open the side bar", with `aria-controls` and `aria-expanded`.

## `C-SIDEBAR.rules` Rules

1. `nav` landmark labelled "Main". The same items, order and current-page marker on every signed-in desktop screen.
2. The Inbox count is the number of unread items and is the same number everywhere it appears.
3. The bar never animates between screens.
4. Data: `A-API.me` (person, roles, tier), `A-API.inbox-count`, `A-API.my-drafts`, `A-API.my-ideas` (top 3), plus the role lists.

## `C-SIDEBAR.reference` Reference (generated)

- Source rules in the prototype: `reference/css/sidebar.css` (classes: `.sbar`, `.sb-i`)
- Resolved values as painted: `reference/computed/components.md`, section `C-SIDEBAR` (bar, new (Share a problem), item, item current, count badge, section head, row, me)
- Used on: `S-03`, `S-04`, `S-04B`, `S-05`, `S-06`, `S-06B`, `S-07`, `S-08`, `S-09`, `S-WALL`, `S-ONE`, `S-R1`, `S-R2`, `S-R3`, `S-R4`, `S-H2`, `S-H2B`, `S-H3`, `S-H4`, `S-H5`, `S-H6`
