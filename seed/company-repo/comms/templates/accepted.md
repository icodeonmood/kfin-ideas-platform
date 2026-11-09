---
type: comms-template
title: '{{cluster.id}} is picked'
description: Message template for decision.accepted (draft, waiting for HR review, DEC-066).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-accepted
  version: '0.1'
  events:
  - decision.accepted
  subject: '{{cluster.id}} is picked'
  signed_as: 'The 1% Club core committee chair'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

The core committee has picked **{{cluster.name}}**.

{{decision.reason}}

A working group is forming with the colleagues who raised it and a sponsor. You will hear about the first steps soon.

[See your idea]({{links.idea}})

The 1% Club core committee chair

A KFintech programme
