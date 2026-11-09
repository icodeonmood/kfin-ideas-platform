---
type: comms-template
title: 'Results due: {{delivery.label}}, {{delivery.mark_words}}'
description: Message template for delivery.measure_due (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-measure-due
  version: '0.1'
  events:
  - delivery.measure_due
  subject: 'Results due: {{delivery.label}}, {{delivery.mark_words}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

It's time to record what **{{delivery.label}}** has changed ({{delivery.mark_words}}): the metric against its baseline, costs so far, and how many people use it.

[Open it]({{links.delivery}})

The 1% Club team

A KFintech programme
