---
type: comms-template
title: '{{delivery.label}}: {{delivery.phase_words}}'
description: Message template for delivery.phase_changed (draft, waiting for HR sign-off).
tags:
- comms
- template
- delivery
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-delivery-phase-changed
  version: '0.3'
  events:
  - delivery.phase_changed
  subject: '{{delivery.label}}: {{delivery.phase_words}}'
  signed_as: 'The 1% Club team'
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, plain and specific (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

{{#delivery.started}}The work on **{{delivery.label}}** has started. You'll hear from us at each step.{{/delivery.started}}{{#delivery.building}}The work on **{{delivery.label}}** has moved to a new step: {{delivery.phase_words}}.{{/delivery.building}}{{#delivery.shipped}}**{{delivery.label}}** has shipped. We measure what it changed at 30 and 90 days.{{/delivery.shipped}}{{#delivery.resolved}}**{{delivery.label}}** is fixed. We measure what it changed at 30 and 90 days.{{/delivery.resolved}}{{#delivery.measured}}The first results for **{{delivery.label}}** are in.{{/delivery.measured}}{{#delivery.closed}}**{{delivery.label}}** is closed: {{delivery.outcome_words}}. Everyone who raised it keeps full credit.{{/delivery.closed}}

[Open it]({{links.delivery}})

The 1% Club team

A KFintech programme
