---
type: rule
title: Communication rules
description: Event → audiences, template, channels, urgency, approval and signer for every platform message.
tags:
- comms
- rules
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: RULE-comms
  version: '1.0'
---

How the communication module decides who hears what. For each event: audiences, template, channels, urgency, whether a person must approve, and who signs.
Quiet hours and holidays come from `rules/calendar.md`. Routine messages respect each person's digest preference; immediate ones always send.
Events with `day_one: false` are switched on as their stages go live (weeks 3–8). Wording lives in `comms/templates/` and is signed off by HR.

```yaml
version: '1.0'
limits:
  non_urgent_emails_per_person_per_day: 1
  hold_non_urgent_on:
  - weekend
  - holiday
  - quiet_hours
  track_email_opens: false
  fallback_on_email_failure:
  - teams
  - in_app
events:
  idea.submitted:
    day_one: true
    audiences:
    - submitter
    template: submitted
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: garage_team
  canvas.nudge:
    day_one: true
    audiences:
    - submitter
    template: quick-capture-nudge
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: garage_team
  idea.joined:
    day_one: true
    audiences:
    - existing_contributors
    template: joined
    channels:
    - in_app
    - digest
    urgency: routine
    approval: null
    signer: system
  adoption.requested:
    day_one: true
    audiences:
    - solution_owner
    template: adoption-requested
    channels:
    - email
    - in_app
    urgency: immediate
    approval: null
    signer: system
  idea.question:
    day_one: true
    audiences:
    - submitter
    template: question
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: reviewer
    reminders_wd:
    - 3
    - 6
  idea.reviewed:
    day_one: true
    audiences:
    - submitter
    template: reviewed
    channels:
    - in_app
    - digest
    urgency: routine
    approval: null
    signer: reviewer
  idea.redirected:
    day_one: true
    audiences:
    - submitter
    template: redirected
    channels:
    - email
    - in_app
    urgency: immediate
    approval: null
    signer: reviewer
  idea.reconsidered:
    day_one: true
    audiences:
    - submitter
    template: reconsidered
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: vetoing_member
    send_only_if_outcome_changed: true
  sla.breached:
    day_one: true
    audiences:
    - current_owner
    - escalation_target
    template: sla-breached
    channels:
    - email
    urgency: immediate
    approval: null
    signer: system
  cluster.approved:
    day_one: false
    audiences:
    - cluster_contributors
    template: cluster-approved
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: review_desk
  shortlist.invited:
    day_one: false
    audiences:
    - presenters
    - presenter_managers
    template: invited-to-present
    channels:
    - email
    - calendar_hold
    - manager_note
    urgency: immediate
    approval: core_chair
    signer: core_chair
  decision.accepted:
    day_one: false
    audiences:
    - presenters
    - contributors
    - managers
    template: accepted
    channels:
    - email
    - manager_note
    urgency: immediate
    approval: core_chair
    signer: core_chair
  decision.not_accepted:
    day_one: false
    audiences:
    - presenters
    - contributors
    template: not-accepted
    channels:
    - email
    urgency: immediate
    approval: core_chair
    signer: core_chair
```
