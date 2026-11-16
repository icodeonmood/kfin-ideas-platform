---
id: L-IMPACT
title: Measuring what a shipped idea changed
rev: 1
status: baseline
source: reference/copy/Wall.md
depends_on: [E-ENTITIES]
last_delta: none
---

# L-IMPACT: Measuring what a shipped idea changed

1. `L-IMPACT/1` When an idea is marked shipped, two measurement points are scheduled: 30 days and 90 days after.
2. `L-IMPACT/2` A measurement records, for the fix: time saved (hours a month), money (rupees a year), effort (steps removed, per what), scale (how many branches, teams, distributors or investors use or are reached by it), and a plain sentence ("620 hours a month saved; bounced first debits down by a third").
3. `L-IMPACT/3` Who enters it: the team that runs the fix. Anything about money must be confirmed by Finance before it shows as "Finance confirmed"; unconfirmed money figures are not shown publicly.
4. `L-IMPACT/4` States per fix: "Being measured" (before 30 days, shows "Due 18 Nov"), measured at 30 days, measured at 90 days. The latest measured figures are the ones shown.
5. `L-IMPACT/5` The sharer and crew are told when a measurement lands. The Status page's Shipped stage shows it.
6. `L-IMPACT/6` Wall totals are sums of the latest confirmed figures across shipped fixes; "Fixes shipped and measured" counts fixes with at least a 30-day measurement.
7. `L-IMPACT/7` A fix can be adopted by other teams ("Adopted by 3 teams"); each adoption adds its own scale and is counted once.
8. `OPEN:` the screen where a team enters a measurement and Finance confirms it is not drawn. Default: an admin form and API.

## `L-IMPACT.touchpoints` Where the front end depends on this

`S-WALL`, `S-ONE`, `S-06`
