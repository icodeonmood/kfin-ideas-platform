---
type: comms-template
title: 'Friday check-in: {{delivery.label}}'
description: Message template for delivery.fix_checkin (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-fix-checkin
  version: '0.1'
  events:
  - delivery.fix_checkin
  subject: 'Friday check-in: {{delivery.label}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

A quick look at the plan for **{{delivery.label}}**: mark what's done and check the next dates still hold.

[Open it]({{links.delivery}})

The 1% Club team

A KFintech programme
