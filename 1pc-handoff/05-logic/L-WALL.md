---
id: L-WALL
title: The Wall: what everyone sees
rev: 1
status: baseline
source: reference/copy/Wall.md
depends_on: [L-ONES, L-IMPACT, E-ENTITIES]
last_delta: none
---

# L-WALL: The Wall: what everyone sees

## `L-WALL.kindling` Kindling (ideas by stage)

1. Three columns: Picked, Being built, Shipped, each with a count and up to 3 ideas (title, "kind, area, N colleagues on it").
2. Kind chips filter the whole section: All, Problems, Fixes, Business ideas.
3. Only the public summary of an idea appears on the Wall. The sharer's name appears only if they allow it (`S-H6`).

## `L-WALL.justin` Just in (with the review desk)

1. Lists ideas currently with the review desk. The sub-line gives the total: "12 with the review desk".
2. Columns per row: the idea (title; "kind, area" under it), Opened this week, Shared, Crew, Ones.
3. Sort (one at a time): **Popular** (most colleagues who opened the idea in the last 7 days), **Newest** (default; most recently shared), **Crew size** (largest crew), **Ones** (most Ones on the crew). Ties go to the newest. `OPEN:` `P-DECISIONS.open/5–6`.
4. "Opened this week" counts distinct signed-in colleagues who opened the idea's page in the last 7 days, excluding the sharer and reviewers.
5. Paging: 5 rows first, "Show 5 more" each time, then "Show fewer". On phone: 3, "Show 3 more"; the row's second line shows the figure for the current sort ("Opened by 233 this week", "Shared 2h ago", "3 on the crew", "1 One on the crew").
6. The kind chips filter this list too. Nothing matching: "Nothing of this kind with the review desk right now."

## `L-WALL.ones` The Ones

Cards for each One: tier bar and flag ("Founding One" / "One"), number, name, "Tier 4, Blaze", and their impact brief. Link: "The Ones leaderboard". Source: `L-ONES`.

## `L-WALL.impact` What shipped ideas have changed

1. Four totals, each one number on one line with its unit in the label: "930 / Hours saved a month", "₹24 lakh / Saved a year, Finance confirmed", "6 / Fixes shipped and measured", "58,600 / Distributors reached by a shipped fix". Totals are sums over measured shipped fixes (`L-IMPACT`).
2. A table of live fixes: what it is, the measured change, when it was measured ("90 days", "30 days", "Due 18 Nov" with a status dot: green measured at 90, amber at 30, grey pending), and the team that runs it.
3. "Already running elsewhere? Team up from its page to bring a live fix to your area."

## `L-WALL.ember` The Ember (newsletter)

The latest issue (issue number, month, headline, three numbered items, "Read this issue"), the next issue as "Coming soon", and a note that every issue is also emailed. Content is editorial. `OPEN:` authoring is outside draft 0; default: a simple content record per issue.

## `L-WALL.touchpoints` Where the front end depends on this

`S-WALL`
