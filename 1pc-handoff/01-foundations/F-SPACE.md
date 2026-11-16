---
id: F-SPACE
title: Space, shape, layers and layout
rev: 1
status: baseline
source: reference/css/kit.css
depends_on: [F-COLOR]
last_delta: none
---

# Space, shape, layers and layout

## `F-SPACE.scale` Spacing

Base unit 4px. Use this scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 56, 72, 104.

| Use | Value |
|---|---|
| Gap between controls in a row | 8px (chips), 10 to 12px (buttons) |
| Padding inside a card | 20 to 24px desktop, 16 to 20px phone |
| Gap between cards in a column | 16px |
| Gap between the two columns of a task screen | 32px |
| Space above a page section | 40px inside a page, 104px between Wall sections |
| Page gutter | 48px desktop, 20px phone |
| Row padding in a list | 16px top and bottom, 1px `--rule` between rows |

## `F-SPACE.radius` Corner radius

Four radii plus the pill. Do not introduce others.

| Token | Value | Use |
|---|---|---|
| `--r-xs` | 8px | Small inner controls: sort options, keyboard hint, tooltip, skeleton bars |
| `--r-sm` | 12px | Buttons, fields, notes, sidebar items, list tiles, field messages |
| `--r-md` | 20px | Cards, glass panels, prompt box on phone, grid tiles |
| `--r-lg` | 28px | Pop-ups, sheets, the Home prompt box, crew and Ones cards |
| `--r-pill` | 999px | Chips, pills, badges, progress tubes |
| round | 50% | Avatars, icon buttons, dots |

2px and 3px appear only on hairline marks (the current-item bar in the sidebar, the tier bar on a One's card).

## `F-SPACE.shadow` Elevation

Elevation is light, not weight: a top highlight plus a long, soft, low-opacity drop.

| Level | Shadow | Use |
|---|---|---|
| Flat | none, 1px border `--rule2` | Cards on plain paper (signed-out pages) |
| Glass card | `inset 0 1px 0 rgba(255,255,255,.9), 0 18px 40px -30px rgba(17,17,17,.28)` | Cards and panels in the shell |
| Current nav item | `0 0 0 1px rgba(17,17,17,.07), 0 6px 16px -10px rgba(17,17,17,.3)` | Sidebar current item, account row when current |
| Primary button hover | `0 14px 30px -14px rgba(17,17,17,.6)` | Ink button on hover |
| Prompt box | soft blue-tinted drop; see `reference/computed/` `C-PROMPT` | Home and Tell it input |
| Sheet | `0 30px 80px -30px rgba(17,17,17,.45), 0 0 0 1px rgba(17,17,17,.06)` | Merge sheet, team-up sheet |
| Pop-up | `inset 0 1px 0 rgba(255,255,255,.95), 0 0 0 1px rgba(17,17,17,.06), 0 50px 100px -40px rgba(17,17,17,.5)` | Preview pop-up |

## `F-SPACE.z` Layers

| Layer | z-index |
|---|---|
| Ambient light | −1 |
| Page content | auto |
| Sticky bars (task bar, phone top bar) | 20 |
| Sidebar | 30 |
| Sheet scrim / sheet | 40 / 41 |
| Menus and dropdowns | 70 |
| Pop-ups (preview, team-up) | 80 |
| Motion effects layer (sparks, hand-over ghosts; never interactive) | top of stack |

## `F-SPACE.shell` The signed-in shell

Desktop (641px and wider):

1. A fixed left sidebar (`C-SIDEBAR`), 256px wide, foldable to 76px. The fold state persists per person and per device.
2. Content sits to the right, in a wrapper of max-width 1280px with 48px gutters, centred in the remaining space.
3. Task screens (`S-04`, `S-04B`, `S-05`, `S-06B`, `S-R3`) add a sticky task bar (`C-TASKBAR`) across the top of the content area: 64px tall, with the three steps "Tell it, Check it, Send it", the save status and "Save and close".
4. There is no top navigation bar on signed-in desktop screens. The old top bar class exists in the prototype CSS and is hidden; do not build it.
5. Signed-out screens (`S-01`, `S-02`) have no sidebar: a simple top row with the brand and, on Landing, two anchor links.

Phone (640px and narrower):

1. No sidebar. Root screens (Home, My ideas, Wall, Inbox) have a top row (brand left, account button right, top padding `max(52px, safe-area top)`) and a bottom tab bar (`C-PHONE-TABS`).
2. Child screens have one compact bar: Back on the left, a short centred title (max 180px, ellipsis), optional icon actions on the right. Never a brand row plus a back link.
3. Task screens replace the tab bar with a bottom dock holding the forward action (`.dock`: 12px top, `max(30px, safe-area bottom + 12px)` bottom).
4. The scroll area is the middle region only (`overscroll-behavior: contain`); bars do not scroll.
5. All fixed bars respect safe areas (`env(safe-area-inset-*)`).

## `F-SPACE.breakpoints` Breakpoints

The canvas draws two widths: 1440 and 390. The build needs the range between them.

| Range | Layout |
|---|---|
| ≤ 640px | Phone layout (the phone boards) |
| 641 to 1100px | Desktop shell with the sidebar folded by default; two-column task screens stack to one column with the side panel below or as a bottom sheet; grids drop one column (4 → 2, 3 → 2) |
| ≥ 1101px | Desktop layout (the desktop boards) |
| ≥ 1440px | Content stays capped at 1280px; extra width goes to the margins |

`OPEN:` the 641 to 1100px range is not drawn. The rules above are the default; each screen module lists its own stacking order under `layout` where it matters.

## `F-SPACE.targets` Touch and click targets

1. Every interactive element is at least 44×44px. Standard control height is 48px; small buttons 44px; full-width primary buttons 56px.
2. Where the visible control is smaller (a 32px sort option, a 30px sidebar action), the hit area is padded to 44px on touch devices.
3. Links inside paragraphs get 10px of vertical padding (with a negative margin) so they meet the target height without changing line spacing.

## `F-SPACE.scroll` Scrolling rules

1. Sticky bars never cover a focused element: every element has `scroll-margin-block: 96px 140px` (16px / 120px inside a phone scroll area).
2. `scrollbar-gutter: stable` on desktop so content does not shift when a scrollbar appears.
3. A side panel that is taller than the window scrolls on its own, sticks at 96px from the top, and keeps its main button pinned at its bottom (see `S-R2.panel`).
4. Horizontal chip rows on phone scroll edge to edge with snap and a 32px fade on the trailing edge to show there is more.
5. Back from a detail screen restores the list's filter, sort and scroll position (see `S-07.return`).

## `F-SPACE.cta` Where actions go

1. The forward action goes at the end of the flow: bottom right on desktop, in the bottom dock on phone. Never at the top, never left-aligned.
2. A backward action ("Back", "Skip for now") sits to the left of the forward action in the same row, as a line or text button.
3. One primary (ink) button per view. The team-up sheet, the merge sheet and the preview pop-up have exactly one button; the cross at the top right closes them and there is no "Cancel". Inline editors, the fix sheet and the Edit page keep a quiet "Cancel" text button to the left of the primary, as drawn (`P-DECISIONS.open/13`).
4. Destructive or reversing actions are never the primary style; they are line buttons that open a confirmation in place.
