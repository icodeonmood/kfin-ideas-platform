---
type: rule
title: Time limits and escalations
description: Working-day limits for every stage, reminders and who each breach escalates to.
tags:
- rules
- sla
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: RULE-sla
  version: '1.0'
  approver: null
---

Timers start when an item enters a stage and stop when it leaves. Working days are counted in IST using `rules/calendar.md`.
Reminders go to the current owner at 50% and 80% of the limit. A breach notifies the escalation target and is visible on the dashboard.

`decide_by` is the 1% Club's review clock (L-SUBMIT.send/4): it starts when an idea is shared or restored. Its due date comes from `rules/promises.md` (`review.decide_by_working_days`, at the deadline hour on the last working day); the entry here registers the kind with the timer engine. It has no reminders or escalation, and nothing is decided automatically. Lane B reads ideas.decide_by for the overdue flag on the desk (S-R1 countdown, 'Overdue by …'); no digest is sent.

```yaml
version: '1.0'
review:
  limit_wd: 5
  remind_at:
  - 0.5
  - 0.8
  escalate_to: core_chair
veto_window:
  limit_wd: 5
needs_info:
  limit_wd: 7
cluster_proposal:
  limit_wd: 5
  escalate_to: core_chair
qualify:
  limit_wd: 10
  escalate_to: core_chair
scoring_round:
  limit_wd: 10
  escalate_to: core_chair
invitation_reply:
  limit_wd: 3
  on_breach: remind_then_next_session
deck_upload:
  due_wd_before_session: 2
  on_breach: move_to_next_session
individual_assessment:
  limit_wd: 2
  escalate_to: core_chair
final_decision:
  limit_wd: 10
  escalate_to: core_chair
outcome_message:
  limit_wd: 2
  escalate_to: core_chair
handover:
  limit_wd: 5
  escalate_to: sponsor
appeal_window:
  limit_wd: 15
appeal_decision:
  limit_wd: 15
  escalate_to: core_chair
measure_30:
  limit_days: 30
measure_90:
  limit_days: 90
decide_by:
  limit_wd: 5
```
