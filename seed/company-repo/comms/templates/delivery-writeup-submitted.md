---
type: comms-template
title: 'A write-up to approve: {{delivery.label}}'
description: Message template for delivery.writeup_submitted (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-writeup-submitted
  version: '0.1'
  events:
  - delivery.writeup_submitted
  subject: 'A write-up to approve: {{delivery.label}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

The owner of **{{delivery.label}}** has written it up so other teams can adopt it. Please read it and approve it, or send it back with what to change. Once approved, people see it as "Already running" when they share a similar idea.

[Read the write-up]({{links.delivery}})

The 1% Club team

A KFintech programme
