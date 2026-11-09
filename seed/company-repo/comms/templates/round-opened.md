---
type: comms-template
title: 'A group is ready for your review: {{cluster.id}}'
description: Message template for round.opened (draft, waiting for HR review, DEC-066).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-round-opened
  version: '0.1'
  events:
  - round.opened
  subject: 'A group is ready for your review: {{cluster.id}}'
  signed_as: 'The 1% Club core committee chair'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

**{{cluster.name}}** is ready for the committee's written review. Please score it by {{round.due_date}}.

Scores stay sealed until everyone has scored. If you have a conflict of interest, say so on the page and step aside.

[Open the review]({{links.round}})

The 1% Club core committee chair

A KFintech programme
