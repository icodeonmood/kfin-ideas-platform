---
type: comms-template
title: 'An update on {{cluster.id}}'
description: Message template for round.not_shortlisted (draft, waiting for HR review, DEC-066).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-not-shortlisted
  version: '0.1'
  events:
  - round.not_shortlisted
  subject: 'An update on {{cluster.id}}'
  signed_as: 'The 1% Club core committee chair'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

The committee reviewed **{{cluster.name}}** and has not shortlisted it this time.

{{outcome.text}}

You keep full credit as a contributor, and you can appeal within 15 working days from your idea page.

[See your idea]({{links.idea}})

The 1% Club core committee chair

A KFintech programme
