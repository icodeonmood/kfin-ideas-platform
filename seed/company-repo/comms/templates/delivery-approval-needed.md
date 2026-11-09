---
type: comms-template
title: 'Your approval: the handover for {{delivery.label}}'
description: Message template for delivery.approval_needed (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-approval-needed
  version: '0.1'
  events:
  - delivery.approval_needed
  subject: 'Your approval: the handover for {{delivery.label}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

The handover pack for **{{delivery.label}}** is ready and names you as its sponsor. Please read it and approve it, or send it back with what is missing.

[Open it]({{links.delivery}})

The 1% Club team

A KFintech programme
