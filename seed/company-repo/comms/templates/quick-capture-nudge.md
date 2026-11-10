---
type: comms-template
title: 'Quick additions for {{idea.id}}'
description: Message template for canvas.nudge.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: TPL-quick-capture-nudge
  version: '1.2'
  events:
  - canvas.nudge
  subject: 'Quick additions for {{idea.id}}'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Your idea **"{{idea.one_line}}"** is with the review desk. Ideas with a bit more detail move faster in committee.{{#idea.next_best.0}} What would help most:
- {{idea.next_best.0}}{{/idea.next_best.0}}{{#idea.next_best.1}}
- {{idea.next_best.1}}{{/idea.next_best.1}}

It takes a couple of minutes. [Add to your canvas]({{links.idea}})

We'll only remind you twice.

The 1% Club team

A KFintech programme
