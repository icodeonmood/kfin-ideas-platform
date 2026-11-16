---
id: S-H6
title: Profile and settings
rev: 1
status: baseline
source: reference/prototype/Profile.dc.html
depends_on: [C-SIDEBAR, C-AVATAR, C-CARD, L-ONES, L-NOTIFY]
last_delta: none
---

# S-H6: Profile and settings

**Route (proposed):** `/profile`. **Boards:** `Profile`

## `S-H6.purpose` Purpose

Who the person is in 1% Club, their private points, whether their name shows on the Wall, and how they are reached.

## `S-H6.layout` Layout

1. **Head**: a profile card (tilts toward the pointer) with the avatar and tier ring, the name, "Investor service, Hyderabad. Tier 2, Glow."
2. **Your points**: the figure (340, counts up once); "Only you see your points. They never decide who becomes a One."; "How points and tiers work" (opens an explanation).
3. **On the Wall**: a switch "Show my name next to my ideas". On: "Your name shows on the Wall next to your shared ideas. It applies to every idea you share, and you can change it here any time." Off: "Your ideas show on the Wall without your name. It applies to every idea you share, and you can change it here any time."
4. **How we reach you**: three switches, each with a line: "Teams messages. When the review desk asks you something, or one of your ideas moves a stage." "Email. The same updates, for your records." "Reminders before a question is due. A day before, and again two hours before."

## `S-H6.rules` Rules

1. Every switch saves at once and shows its new state; no Save button, no toast. `NOT DRAWN:` a failed save flips the switch back with a message under it: "Couldn't save that. Try again."
2. The Wall switch applies to every idea, past and future, within a minute.
3. The account menu (from the sidebar's account row) also holds: turn the `P` shortcut on or off, and "Sign out". `NOT DRAWN:` the menu itself; default: a small menu above the account row.
4. A One sees a link to their One dashboard here.
5. Switches are `role="switch"` with `aria-checked`, labelled by their title and described by their line.
6. No phone board; one column on phone, reached from the account button.

## `S-H6.reference` Reference (generated)

### Board `Profile` (1440×1000)

- Canvas caption: H6 · Profile and settings: your points, your name on the Wall, how we reach you (tweak: wall)
- Prototype: `reference/prototype/Profile.dc.html`
- Exact copy and controls in every state: `reference/copy/Profile.md`
- Board-specific CSS: `reference/css/boards/Profile.css`
- Default screenshot: `reference/shots/Profile.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `wall` | Shown; Hidden | `Profile__wall-*.jpg` (1) |

Links out, as wired on the board: S-H4 (How points and tiers work)
