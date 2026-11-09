---
type: comms-template
title: 'Please confirm the results for {{delivery.label}}'
description: Message template for delivery.measure_to_confirm (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-measure-confirm
  version: '0.1'
  events:
  - delivery.measure_to_confirm
  subject: 'Please confirm the results for {{delivery.label}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

The results for **{{delivery.label}}** ({{delivery.mark_words}}) are in and need your confirmation as sponsor.

[Open it]({{links.delivery}})

The 1% Club team

A KFintech programme
