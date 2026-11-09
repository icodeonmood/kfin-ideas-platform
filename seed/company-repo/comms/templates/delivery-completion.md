---
type: comms-template
title: 'Fixed? Please confirm {{delivery.label}}'
description: Message template for delivery.completion_to_approve (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-completion
  version: '0.1'
  events:
  - delivery.completion_to_approve
  subject: 'Fixed? Please confirm {{delivery.label}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

The owner of **{{delivery.label}}** says the fix is done and has added the before-and-after numbers. Please confirm it, so we can start measuring what it changed.

[Open it]({{links.delivery}})

The 1% Club team

A KFintech programme
