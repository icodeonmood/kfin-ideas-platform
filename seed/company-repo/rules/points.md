---
type: rule
title: Recognition points
description: Points for submissions, joins, strong canvases, shortlisting, acceptance and shipping. Points never decide 1% Club membership.
tags:
- rules
- recognition
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: RULE-points
  version: '1.0'
  approver: null
---

Points feed the wall, badges and leaderboard. Originators raised the problem before seeing a match; joiners joined after a match was shown.
The ledger is append-only. People can appear as "Anonymous contributor".

```yaml
version: '1.0'
submission:
  points: 1
  monthly_cap: 5
joined_with_context:
  points: 1
  monthly_cap: 5
strong_canvas:
  points: 2
  monthly_cap: 4
accepted_into_cluster:
  originator: 2
  joiner: 1
shortlisted:
  originator: 5
  joiner: 2.5
presented:
  presenter: 3
accepted:
  originator: 10
  joiner: 5
shipped_or_resolved:
  originator: 25
  joiner: 12.5
working_group_member_shipped: 15
appeal_overturned: restore_forfeited
```
