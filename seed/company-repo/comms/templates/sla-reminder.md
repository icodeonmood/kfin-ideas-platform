---
type: comms-template
title: 'Reminder: {{item.label}} is due {{item.due_date}}'
description: Message template for sla.reminder.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-sla-reminder
  version: '1.0'
  events:
  - sla.reminder
  subject: 'Reminder: {{item.label}} is due {{item.due_date}}'
  signed_as: The Garage team
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

**{{item.label}}** is {{reminder.share_percent}}% of the way to its time limit. It is due by **{{item.due_date}}**.

[Open the review desk]({{links.item}})

The Garage · Ideas
