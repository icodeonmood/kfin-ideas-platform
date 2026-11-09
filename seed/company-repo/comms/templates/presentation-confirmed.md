---
type: comms-template
title: 'Presentation confirmed: {{cluster.id}}'
description: Message template for presentation.confirmed (draft, waiting for HR review, DEC-066).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-presentation-confirmed
  version: '0.1'
  events:
  - presentation.confirmed
  subject: 'Presentation confirmed: {{cluster.id}}'
  signed_as: 'The 1% Club core committee chair'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Your presentation of **{{cluster.name}}** is confirmed for {{presentation.slot}}.

The format is a short pitch, then questions. Bring your deck; uploading it here is coming soon.

[See the details]({{links.presentation}})

The 1% Club core committee chair

A KFintech programme
