---
id: S-ONE
title: A One's dashboard
rev: 1
status: baseline
source: reference/prototype/OneDashboard.dc.html
depends_on: [C-SIDEBAR, C-CARD, C-FIELD, L-ONES, L-IMPACT]
last_delta: none
---

# S-ONE: A One's dashboard

**Route (proposed):** `/one`. **Boards:** `OneDashboard`

## `S-ONE.purpose` Purpose

A One's own page: their number, their brief, and what their idea changed.

## `S-ONE.layout` Layout

1. Breadcrumb "My ideas / Your One dashboard".
2. **Hero** (dark slab, the tier colour as a glow): the flag ("Founding One" / "One"), "Your number", the number very large, the name, "Tier 4, Blaze"; then "You're No. 1", "Tier 4, Blaze. Founding One since 1 Nov 2026." with a glowing tier dot, and "Your idea" with its one-line title.
3. **Your number**: "Keep No. 1, or choose any free number from 1 to 999 until 1 Dec 2026. First come, first served. After that, it's yours." A field "Number you'd like" and "Save my number".
4. **Your impact brief**: "On the wall" and the sentence; "Propose a new brief".
5. **Impact so far**: "Measured 30 and 90 days after your idea ships." Four tiles: Time, Money (with "Finance confirmed"), Effort, Scale, each a figure and one line.
6. **More for Ones**: "Your Showcase brief", "The Ones leaderboard".

## `S-ONE.states` States

| Tweak | States |
|---|---|
| `person` | Rohit Menon, founding One, Tier 4; Ananya Rao, No. 17, Tier 2 (all content follows the person) |
| `showGlowUp` | Off; On: a full-screen moment over the dashboard when the tier has just risen: "No. 17, your spark is hotter", "From Tier 1, Spark to Tier 2, Glow", "Your story so far" (ideas shared, picked or being built, shipped), "Messages for you" (a note from the core committee with its sender), and "Back to my dashboard" |

## `S-ONE.rules` Rules

1. Only a One can open it; others are sent to Profile.
2. Number field: whole numbers 1 to 999. Taken: "No. 7 is taken. Free numbers near it: 6, 8, 11." Window closed: the field is replaced by "No. 1 is yours for good." (`V-FIELDS.one`; both `NOT DRAWN:` defaults.)
3. The glow-up moment shows once per tier change, can be dismissed with Escape, and never plays under reduced motion (it appears already settled).
4. Figures count up once on arrival. Rules: `L-ONES`, `L-IMPACT`.
5. No phone board; one column on phone, the hero first.

## `S-ONE.reference` Reference (generated)

### Board `OneDashboard` (1440×2500)

- Canvas caption: A One’s own dashboard, on the new shell
- Prototype: `reference/prototype/OneDashboard.dc.html`
- Exact copy and controls in every state: `reference/copy/OneDashboard.md`
- Board-specific CSS: `reference/css/boards/OneDashboard.css`
- Default screenshot: `reference/shots/OneDashboard.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `person` | Rohit Menon, founding One, Tier 4; Ananya Rao, No. 17, Tier 2 | `OneDashboard__person-*.jpg` (1) |
| `showGlowUp` | boolean (default False) | |

Links out, as wired on the board: S-H6 (Your profile and settings, Ananya Rao,, Your profile and settings, Rohit Menon); S-07 (My ideas); S-WALL (The Ones leaderboard)
