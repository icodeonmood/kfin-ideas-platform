---
id: J-ONE
title: An idea ships and its sharer becomes a One
rev: 1
status: baseline
source: reference/prototype/Wall.dc.html
depends_on: [S-06, S-WALL, S-ONE, S-OFFICE, S-03, L-IMPACT, L-ONES]
last_delta: none
---

# J-ONE: An idea ships and its sharer becomes a One

| # | What happens | Where it shows | Rules |
|---|---|---|---|
| 1 | The picked idea is built and marked shipped | The sharer's track reaches "Shipped"; the Wall's Shipped column | `L-DECIDE.after` |
| 2 | 30 days later the first measurement is entered; money figures are confirmed by Finance | The Wall's live-fixes table and totals | `L-IMPACT` |
| 3 | With a measured, confirmed difference, the people credited become Ones: each gets a number and a tier | Inbox; the Wall's "The Ones"; the office screen | `L-ONES.rules/1–3` |
| 4 | The new One opens their dashboard, may swap their number for 30 days, and may propose their brief | `S-ONE` | `L-ONES.rules/2,5` |
| 5 | The One posts what changed | Home's "The Ones" for everyone | `L-ONES.rules/7` |
| 6 | At 90 days the figures are updated; a tier may rise, with a moment on the dashboard | `S-ONE` glow-up | `L-ONES.rules/3` |

## `J-ONE.boards` Boards to walk on the canvas

`Wall`, `OneDashboard`, `Office`
