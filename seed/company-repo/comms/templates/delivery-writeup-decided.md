---
type: comms-template
title: 'Your write-up: {{delivery.label}}'
description: Message template for delivery.writeup_decided (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-writeup-decided
  version: '0.2'
  events:
  - delivery.writeup_decided
  subject: 'Your write-up: {{delivery.label}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

{{#writeup.approved}}The sponsor approved your write-up for **{{delivery.label}}**. Other teams now see it as "Already running" when they share a similar idea.{{/writeup.approved}}{{#writeup.sent_back}}The sponsor sent your write-up for **{{delivery.label}}** back for changes. Open it, change what is needed and submit it again.{{/writeup.sent_back}}

[Open the delivery]({{links.delivery}})

The 1% Club team

A KFintech programme
