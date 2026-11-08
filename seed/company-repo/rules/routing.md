---
type: rule
title: Routing, thresholds for shortlisting, presentations and appeals
description: Which body handles which scope, shortlist and nomination thresholds, presentation settings, review-desk veto and appeal panel rules.
tags:
- rules
- routing
- committees
status: draft
verified: unverified
generated:
  by: human:product-team-draft
  at: '2026-11-08'
kfin:
  id: RULE-routing
  version: '1.0'
  approver: null
---

The review desk decides review items on the core committee's behalf; core committee members can veto within the veto window (`rules/sla.md`).
LOB-scope clusters go to that LOB's committee, unless the LOB file names the core committee. Everything cross-LOB, org-wide or a business idea goes to the core committee.
Presentation slot length is not fixed yet (DEC-013). There are no comeback routes after a decline (DEC-018); appeals are the only route.

```yaml
version: '1.0'
review_desk:
  decides: true
  veto_by: core_committee
  veto_needs_reason: true
scope_routes:
  lob: lob_committee_or_core_per_lob_file
  cross-lob: core
  org-wide: core
business_idea_route: core
lob_comment_window_wd: 5
nomination_threshold: 70
shortlist_threshold: 65
chair_may_shortlist_below_with_reason: true
finance_check_inr: 2500000
presentation:
  format:
  - pitch
  - qna
  slot_minutes: null
  quorum: 0.6
  max_slots_before_not_presented: 2
cycle:
  cadence: monthly
appeals:
  outside_seat: false
  panel_size: 3
  panel_from: core_committee_rotation
  exclude:
  - conflicted_members
  - brief_owner
  must_include_member_not_in_original_majority: true
  desk_decision_appeals_heard_by: uninvolved_core_member
resubmission_after_months: 12
parked:
  return_next_cycle: true
  archive_after_cycles_without_joiners: 2
```
