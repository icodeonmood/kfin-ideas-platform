---
type: rule
title: Sorting lists and review routing
description: The groups and areas people choose from when they confirm how their idea is sorted, the "Who would help" choices, and which reviewers each area goes to.
tags:
- rules
- sorting
- routing
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: RULE-sorting
  version: '1.0'
  approver: null
---

Sorting decides who reviews an idea (`L-SORT` in the design handoff). The assistant suggests a value for each field from the person's words, and the person confirms or changes it before sending. The lists below are what they choose from: `shown` values are the chips on the screen, `more` sit behind "Search all groups" or "Search all areas". What kind it is (a problem to fix, a new business idea) and what it would bring (saves time, saves cost, earns revenue, cuts reliance on outside tools, not sure yet) are fixed by the product and are not listed here.

The groups are the ones the earlier canvas used. The areas are the ones drawn on the boards; the boards say "Search all 12", so three more areas come from the programme team.

Review routing (`L-SORT.rules/7`) is owned by the review desk lead. Until the lead sends a map, every area goes to any reviewer, never the person who shared the idea. To route an area, list the work email of each reviewer for it under `review_routing.areas`; someone listed who is not an active reviewer is skipped, and an area whose reviewers are all unavailable falls back to any reviewer. The person who shared an idea never reviews it, whatever the map says. Changes go through a pull request approved by an admin; no release is needed.

```yaml
version: '1.0'
affects:
  shown:
  - Investors
  - KFin teams
  - Distributors
  more:
  - AMC clients
  - Issuer and corporate clients
  - Others
areas:
  shown:
  - Investor service
  - Operations
  - Distributor experience
  more:
  - Corporate registry
  - Technology
  - Compliance
  - Sales
  - New business
  - Distributor services
helpers:
- Someone at a branch
- Someone in operations
- Someone from tech
- Someone who knows the rules
- Data or reports
review_routing:
  default: any_reviewer
  areas: {}
```
