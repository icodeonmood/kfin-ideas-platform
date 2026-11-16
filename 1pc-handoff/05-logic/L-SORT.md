---
id: L-SORT
title: Sorting: suggested, then confirmed by the sharer
rev: 1
status: baseline
source: reference/copy/Review.md
depends_on: [L-DRAFT, E-ENUMS]
last_delta: none
---

# L-SORT: Sorting: suggested, then confirmed by the sharer

"Sorting" decides who reviews an idea. The assistant suggests; the sharer has the final word before sending; the reviewer may recategorise afterwards, visibly.

## `L-SORT.fields` Fields

| Field | Choice | Options |
|---|---|---|
| Who it affects | Pick all that apply | Investors, KFin teams, Distributors, plus "Search all groups" (configured list) |
| What kind it is | Pick one | A problem to fix, A new business idea |
| Area | Pick one | Investor service, Operations, Distributor experience, plus "Search all areas" (configured list, includes Corporate registry, Technology, Compliance, Sales, New business) |
| What it would bring | Pick all that apply | Saves time, Saves cost, Earns revenue, Cuts reliance on outside tools, Not sure yet ("Not sure yet" clears the others) |

## `L-SORT.rules` Rules

1. Each field arrives pre-filled from `L-DRAFT.parts` with its reason line ("Suggested because …").
2. **Confirmation is explicit.** The idea cannot be sent until the sorting is confirmed. One action confirms all untouched suggestions ("Looks right" on the Sorting part of Check it). Changing any value counts as confirming that field.
3. Each field records its source: `suggested`, `confirmed` (suggestion accepted) or `changed` (the sharer's own value). Changed values read as the person's call and are never overwritten.
4. Trying to send unconfirmed: the Send step shows "Not confirmed yet" on the sorting row and, on Submit, "Confirm the sorting first, or change any of it." with "Go to the sorting"; focus moves there (`V-FIELDS.sorting`).
5. After sharing, the sharer can change sorting in the edit window (`L-SUBMIT.edit`); the screen notes "Confirmed when you shared it. You can still change any of these."
6. The reviewer can change kind and area as part of "Revise and recategorise" (`L-WORTH`). The sharer is told what changed and why. Routing follows the latest area.
7. Routing: the area maps to a review queue. `OPEN:` the area-to-reviewer mapping is configuration owned by the review desk lead.
8. Record how often people change each suggested field (trust in pre-filled sorting is a launch metric).

## `L-SORT.touchpoints` Where the front end depends on this

`S-05`, `S-06B`, `S-R2`
