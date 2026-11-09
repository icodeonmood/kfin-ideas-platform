---
type: comms-template
title: 'Blocked: {{delivery.label}}'
description: Message template for delivery.checkin_blocked (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-checkin-blocked
  version: '0.1'
  events:
  - delivery.checkin_blocked
  subject: 'Blocked: {{delivery.label}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

This week's check-in for **{{delivery.label}}** says the work is blocked. A word from you may be all it needs.

[See the check-in]({{links.delivery}})

The 1% Club team

A KFintech programme
