---
type: rule
title: The numbers the product promises
description: Times, windows and minimum lengths the 1% Club shows people and keeps to, from P-PRODUCT.promises. They change without a release.
tags:
- rules
- promises
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-16T00:00:00+05:30'
kfin:
  id: RULE-promises
  version: '1.0'
  approver: null
---

Every number here is a promise made on screen or in a message (`P-PRODUCT.promises` in the design handoff). The app shows these values and keeps to them, so a change here changes both, with no release. Changes go through a pull request approved by an admin. Working days follow `rules/calendar.md`.

```yaml
version: '1.0'
draft:
  min_chars_to_check: 30        # minimum before a draft can move to Check it
  kept_days: 30                 # then archived, never deleted silently
voice:
  max_seconds: 180              # a voice clip, up to 3 minutes
review:
  decide_by_working_days: 5     # a decision within 5 working days of sharing
edit_window:
  max_days: 3                   # edit and withdraw until the desk opens it, at most 3 days
questions:
  answer_options_days: [1, 3, 7]
  answer_default_days: 3
  deadline_hour: 18             # questions fall due at 6 pm, India time
  reminder_hours_before: [24, 2]
notes:
  decision_reason_min_chars: 30
  reversal_note_min_chars: 30
  teamup_note_min_chars: 30
  merge_note_min_chars: 20
committee_window:
  days: 30
  extend_by_days: 30
  max_months: 3
not_now:
  return_options_months: [1, 3, 6]
  return_default_months: 3
team_by:
  working_days: 10              # a picked idea has its build team within 10 working days
impact:
  check_days: [30, 90]          # measured 30 and 90 days after shipping
sign_in:
  code_digits: 6
  code_valid_minutes: 10
  code_tries: 3
  resend_after_seconds: 45
session:
  hours: 8                      # KFintech policy
ones:
  number_change_days: 30        # a new One may pick any free number for 30 days
  number_max: 999
```
