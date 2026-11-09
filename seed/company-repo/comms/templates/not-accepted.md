---
type: comms-template
title: 'An update on {{cluster.id}}'
description: Message template for decision.not_accepted (draft, waiting for HR review, DEC-066).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-not-accepted
  version: '0.1'
  events:
  - decision.not_accepted
  subject: 'An update on {{cluster.id}}'
  signed_as: 'The 1% Club core committee chair'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Thank you for presenting **{{cluster.name}}**. The committee has decided not to take it forward now.

{{decision.reason}}

**What would change this:** {{decision.what_would_change}}

A committee member can take you through the feedback in a 15-minute call. You can appeal within 15 working days from your idea page.

[See your idea]({{links.idea}})

The 1% Club core committee chair

A KFintech programme
