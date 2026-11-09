---
type: comms-template
title: 'Needs attention: {{delivery.label}}'
description: Message template for delivery.overdue (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-overdue
  version: '0.1'
  events:
  - delivery.overdue
  subject: 'Needs attention: {{delivery.label}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

{{#delivery.milestone}}A step in the plan for **{{delivery.label}}** is past its date.{{/delivery.milestone}}{{#delivery.plan_late}}The plan for **{{delivery.label}}** is more than 10 working days late. As chair, please look at it with the owner and sponsor.{{/delivery.plan_late}}{{#delivery.blocked}}The work on **{{delivery.label}}** has been blocked for more than 10 working days.{{/delivery.blocked}}

[Open it]({{links.delivery}})

The 1% Club team

A KFintech programme
