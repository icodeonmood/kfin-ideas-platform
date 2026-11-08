---
type: comms-template
title: 'Overdue: {{item.label}}'
description: Message template for sla.breached.
tags:
- comms
- template
status: draft
verified: unverified
generated:
  by: human:product-team-draft
  at: '2026-11-08'
kfin:
  id: TPL-sla-breached
  version: '1.0'
  events:
  - sla.breached
  subject: 'Overdue: {{item.label}}'
  signed_as: The Garage platform
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

**{{item.label}}** is {{breach.days_late}} working day(s) past its limit of {{breach.limit_wd}} working days. Current owner: {{item.owner_name}}.

[Open it]({{links.item}})
