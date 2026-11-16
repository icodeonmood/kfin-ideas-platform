---
id: L-ONES
title: The Ones: numbers, tiers, points
rev: 1
status: baseline
source: reference/copy/OneDashboard.md
depends_on: [L-IMPACT, E-ENTITIES]
last_delta: none
---

# L-ONES: The Ones: numbers, tiers, points

## `L-ONES.rules` Rules

1. A person becomes a One when an idea they are credited on has shipped and its impact has been measured and confirmed (`L-IMPACT`). Founding Ones are marked "Founding One".
2. Each One has a **number**, unique across the programme. On becoming a One they are given the next free number and may swap it for any free number from 1 to 999 for 30 days ("Keep No. 17, or choose any free number from 1 to 999 until 3 Dec 2026. First come, first served. After that, it's yours."). After that it is permanent.
3. Each One has a **tier** from 1 to 7: Spark, Glow, Flame, Blaze, White heat, Blue flame, Star. "Their tier warms as their impact grows." A tier change triggers a moment on the dashboard ("No. 17, your spark is hotter. From Tier 1, Spark to Tier 2, Glow") with "Your story so far" (ideas shared, picked or being built, shipped) and any message from the core committee.
4. Every employee also has a tier shown on their own account button and Profile (Kavya: "Tier 2, Glow") and **points** (340) that only they can see. "Only you see your points. They never decide who becomes a One."
5. Each One has an **impact brief**: one sentence shown on the Wall and the office screen. They can "Propose a new brief"; it goes live after the programme team approves it (`NOT DRAWN:` default).
6. The One dashboard shows impact so far in four measures: Time ("620 hours a month"), Money ("₹18 lakh a year", "Finance confirmed"), Effort ("3 fewer steps", "Per new mandate"), Scale ("41 branches", "Using it every day"). Plus "Your Showcase brief" and "The Ones leaderboard".
7. Ones post short updates about what shipped; these are the cards on Home's "The Ones" (`C-ONES-FAN`) with a headline figure, likes, comments and "Read the thread".

## `L-ONES.open` Open

`OPEN:` (`P-DECISIONS.open/9`) what earns points, the thresholds between tiers, and whether the leaderboard ranks by tier, impact or number are not specified by the design. Build tiers and points as values set by a rules table the programme team can edit, with an audit trail; build the leaderboard as Ones ordered by tier, then by measured hours saved.

## `L-ONES.touchpoints` Where the front end depends on this

`S-ONE`, `S-WALL`, `S-H6`, `S-03`, `S-OFFICE`
