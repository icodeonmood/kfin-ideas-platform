---
id: S-WALL
title: The Wall
rev: 1
status: baseline
source: reference/prototype/Wall.dc.html
depends_on: [C-SIDEBAR, C-CHIP, C-SORTS, C-PILL, C-CARD, L-WALL, L-ONES, L-IMPACT]
last_delta: none
---

# S-WALL: The Wall

**Route (proposed):** `/wall`. **Boards:** `Wall`, `PhoneWall`

## `S-WALL.purpose` Purpose

The public face of the programme: every shared idea and where it is, the people behind what shipped, and what it changed. Full light, cinematic arrival, sections reveal on scroll.

## `S-WALL.layout` Sections (desktop, top to bottom, 104px apart)

1. **Kindling** `S-WALL.kindling`: heading "Kindling" with "Every idea and problem shared at KFintech, and where it is now. Each one could catch." Kind chips: All, Problems, Fixes, Business ideas. Three stage cards side by side (Picked, Being built, Shipped): a stage pill, a count at the right, and up to three ideas (title link; "Problem, Distributor experience, 4 colleagues on it").
2. **Just in** `S-WALL.justin`: heading "Just in"; sub-line "12 with the review desk"; at the right the sort control (Popular, Newest, Crew size, Ones). A header row (Idea, Opened this week, Shared, Crew, Ones) and rows: title link with "Problem, Investor service" under it, then the four figures right-aligned in tabular numerals. The sorted column's header and cells are ink and weight 500; the rest `--mute`. Five rows, then a centred line button "Show 5 more"; when all are shown, "Show fewer". Column widths: flexible, 136px, 104px, 72px, 72px; 20px gaps.
3. **The Ones** `S-WALL.ones` (dark slab with a warm glow): heading "The Ones"; "Colleagues whose ideas shipped and made a measured difference. Each One keeps a number, and their tier warms as their impact grows." Five cards: a 24×4px tier bar, the flag ("Founding One" / "One"), the number at 80px, name, "Tier 4, Blaze", and the brief. Link "The Ones leaderboard".
4. **Impact** `S-WALL.impact`: heading "What shipped ideas have changed so far." with "Measured 30 and 90 days after each idea ships, and confirmed by Finance where money is involved." Four tiles in a row, all built the same: the number on one line, never wrapping (size `clamp(48px, 4.6vw, 72px)`; "₹24" keeps "lakh" as a small suffix because it is part of the amount), and the unit inside the label under it: "930 / Hours saved a month", "₹24 lakh / Saved a year, Finance confirmed", "6 / Fixes shipped and measured", "58,600 / Distributors reached by a shipped fix". All four tiles are the same height. Then the live-fixes table (Live fix, Measured change, Measured, Team that runs it) and the line "Already running elsewhere? Team up from its page to bring a live fix to your area."
5. **The Ember** `S-WALL.ember`: heading "The Ember"; "The 1% Club's newsletter: what caught, who built it, and what it changed." The latest issue card ("Issue 1, November 2026", a "Latest" pill, headline, three numbered items, "Read this issue"), beside it "Issue 2, December 2026" as a dashed "Coming soon" card and a card "Every issue lands in your inbox too."
6. **Footer**: "1% Club", "The Ember", "A KFintech programme".

## `S-WALL.rules` Rules

1. Data and sort definitions: `L-WALL`. Kind chips filter Kindling and Just in together; an empty Just in reads "Nothing of this kind with the review desk right now."
2. Re-sorting Just in glides rows to their new order. Each row's text stays the same across sorts (all four figures are always shown) so rows can be matched.
3. The count in each Kindling card and the big figures count up once on first reveal.
4. An idea title opens `S-09` (or `S-06` if it is the person's own).
5. Responsive: at 1100px and below the Kindling columns stack and the impact tiles go two across; at 640px and below everything is one column.

## `S-WALL.phone` Phone

Title "Wall" and one line. **Kindling** as groups down the page (Just in, Picked, Being built, Shipped), each with a count and rows (title; "Problem, Investor service. <fact>"; chevron), under a sideways chip row for kind. The **Just in** group adds a sort cycler under its header ("Sorted by newest" → popular → crew size → Ones on the crew), shows 3 rows with "Show 3 more", and each row's second line carries the figure for the current sort. **The Ones** as a dark slab with cards scrolling sideways. **What shipped ideas changed**: the four tiles two across, same rule (number on one line, unit in the label). Tweak `filter`: All, Problems, Fixes, Business ideas; an empty result shows "Nothing here for this filter yet" + "Show everything". The Ember is not on the phone board; `NOT DRAWN:` add it as the last section in one column.

## `S-WALL.reference` Reference (generated)

### Board `Wall` (1440×4400)

- Canvas caption: The Wall, on the new shell
- Prototype: `reference/prototype/Wall.dc.html`
- Exact copy and controls in every state: `reference/copy/Wall.md`
- Board-specific CSS: `reference/css/boards/Wall.css`
- Default screenshot: `reference/shots/Wall.jpg`

Links out, as wired on the board: S-09 (A one-page NFO kit for B30 branches, A paid data feed of anonymised SIP tre, Explain transaction rejections to dist)

### Board `PhoneWall` (390×844)

- Canvas caption: Wall
- Prototype: `reference/prototype/PhoneWall.dc.html`
- Exact copy and controls in every state: `reference/copy/PhoneWall.md`
- Board-specific CSS: `reference/css/boards/PhoneWall.css`
- Default screenshot: `reference/shots/PhoneWall.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `filter` | All; Problems; Fixes; Business ideas | `PhoneWall__filter-*.jpg` (3) |

Links out, as wired on the board: S-03 (1% Club); S-09 (A monthly digest of investor complaint, A one-page NFO kit for B30 branches Bu, A paid data feed of anonymised SIP tre); S-07 (My ideas); S-04 (Share a problem); S-H5 (Inbox, 2 new)
