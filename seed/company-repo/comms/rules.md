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
  version: '1.2'
---

How the communication module decides who hears what. For each event: audiences, template, channels, urgency, whether a person must approve, and who signs.
Quiet hours and holidays come from `rules/calendar.md`. Routine messages respect each person's digest preference; immediate ones always send.
Events with `day_one: false` are switched on as their stages go live (weeks 3–8). Wording lives in `comms/templates/` and is signed off by HR.
The review desk signs as a whole, never by a reviewer's name (DEC-111; 1.1, BLD-A222).
The Ones Committee signs as one, never by a member's name (DEC-113; 1.2, BLD-A231).

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
    signer: club_team
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
    signer: club_team
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
    signer: review_desk
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
    signer: review_desk
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
    signer: review_desk
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
    signer: ones_committee
    send_only_if_outcome_changed: true
  sla.reminder:
    day_one: true
    audiences:
    - current_owner
    template: sla-reminder
    channels:
    - in_app
    urgency: routine
    approval: null
    signer: system
  idea.withdrawn_no_answer:
    day_one: true
    audiences:
    - submitter
    template: withdrawn-no-answer
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: club_team
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
    day_one: true   # live with weekly clustering (switch clusters.batch); template waits for HR sign-off
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
    day_one: true   # live with the committee flow (switch committee.flow); the chair's recorded decision is the approval (BLD-218)
    audiences:
    - cluster_contributors
    template: invited-to-present
    channels:
    - in_app
    - email
    urgency: immediate
    approval: core_chair
    signer: core_chair
  decision.accepted:
    day_one: true   # live with the committee flow (switch committee.flow); the chair's recorded decision is the approval (BLD-218)
    audiences:
    - cluster_contributors
    template: accepted
    channels:
    - in_app
    - email
    urgency: immediate
    approval: core_chair
    signer: core_chair
  decision.not_accepted:
    day_one: true   # live with the committee flow (switch committee.flow); the chair's recorded decision is the approval (BLD-218)
    audiences:
    - cluster_contributors
    template: not-accepted
    channels:
    - in_app
    - email
    urgency: immediate
    approval: core_chair
    signer: core_chair
  decision.not_presented:
    day_one: true   # live with the committee flow; the chair records that the session did not take place (BLD-221)
    audiences:
    - cluster_contributors
    template: not-presented
    channels:
    - in_app
    - email
    urgency: immediate
    approval: core_chair
    signer: core_chair
  appeal.filed:
    day_one: true   # live with appeals (switch appeals.filing); to the panel that hears it (BLD-222)
    audiences:
    - round_members
    template: appeal-filed
    channels:
    - in_app
    - email
    urgency: immediate
    approval: core_chair
    signer: core_chair
  appeal.decided:
    day_one: true   # the panel chair's recorded outcome is the approval (BLD-222)
    audiences:
    - cluster_contributors
    template: appeal-decided
    channels:
    - in_app
    - email
    urgency: immediate
    approval: core_chair
    signer: core_chair
  ones.inducted:
    day_one: true
    audiences:
    - current_owner
    template: one-inducted
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: club_team
  ones.removed:
    day_one: true
    audiences:
    - current_owner
    template: one-removed
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: club_team
  ones.tier_changed:
    day_one: true
    audiences:
    - current_owner
    template: one-tier-changed
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: club_team
  ones.announced:
    day_one: true
    audiences:
    - everyone
    template: ones-announced
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  ember.issue:
    day_one: true
    audiences:
    - everyone
    template: ember
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  delivery.approval_needed:
    day_one: true
    audiences:
    - current_owner
    template: delivery-approval-needed
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  delivery.phase_changed:
    day_one: true
    audiences:
    - submitter
    - existing_contributors
    - cluster_contributors
    - current_owner
    template: delivery-phase-changed
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  delivery.completion_to_approve:
    day_one: true
    audiences:
    - current_owner
    template: delivery-completion
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  delivery.measure_due:
    day_one: true
    audiences:
    - current_owner
    template: delivery-measure-due
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  delivery.measure_to_confirm:
    day_one: true
    audiences:
    - current_owner
    template: delivery-measure-confirm
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  delivery.fix_checkin:
    day_one: true
    audiences:
    - current_owner
    template: delivery-fix-checkin
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  delivery.checkin_blocked:
    day_one: true
    audiences:
    - current_owner
    template: delivery-checkin-blocked
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: club_team
  delivery.writeup_submitted:
    day_one: true
    audiences:
    - current_owner
    template: delivery-writeup-submitted
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  delivery.writeup_decided:
    day_one: true
    audiences:
    - current_owner
    template: delivery-writeup-decided
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  delivery.overdue:
    day_one: true
    audiences:
    - current_owner
    - escalation_target
    template: delivery-overdue
    channels:
    - in_app
    - email
    urgency: routine
    approval: null
    signer: club_team
  cluster.gate_outcome:
    day_one: true   # live with the committee flow (switch committee.flow); template waits for HR review (DEC-066)
    audiences:
    - cluster_contributors
    template: gate-outcome
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: review_desk
  round.opened:
    day_one: true   # live with the committee flow
    audiences:
    - round_members
    template: round-opened
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: core_chair
  round.not_shortlisted:
    day_one: true   # live with the committee flow; the chair's recorded decision is the approval (BLD-218)
    audiences:
    - cluster_contributors
    template: not-shortlisted
    channels:
    - in_app
    - email
    urgency: immediate
    approval: core_chair
    signer: core_chair
  presentation.confirmed:
    day_one: true   # live with the committee flow
    audiences:
    - cluster_contributors
    template: presentation-confirmed
    channels:
    - in_app
    - email
    urgency: immediate
    approval: null
    signer: core_chair
```
