---
type: comms-template
title: 'Overdue: {{item.label}}'
description: Message template for sla.breached.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: TPL-sla-breached
  version: '1.2'
  events:
  - sla.breached
  subject: 'Overdue: {{item.label}}'
  signed_as: 1% Club
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

**{{item.label}}** has passed its time limit of {{breach.limit_wd}} working days.{{#item.owner_name}} It is with {{item.owner_name}}.{{/item.owner_name}}{{#item.unassigned}} Nobody on the review desk has picked it up yet.{{/item.unassigned}}

[Open it]({{links.item}})

1% Club, a KFintech programme
