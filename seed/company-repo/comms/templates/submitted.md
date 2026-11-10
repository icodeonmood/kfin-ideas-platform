---
type: comms-template
title: 'Your idea is in: {{idea.id}}'
description: Message template for idea.submitted.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: TPL-submitted
  version: '1.2'
  events:
  - idea.submitted
  subject: 'Your idea is in: {{idea.id}}'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Thanks for sharing **"{{idea.one_line}}"** ({{idea.id}}).

**What happens next.** The review desk will look at it by **{{review.due_date}}** (within 5 working days). They may group it with colleagues who raised the same thing, or ask you a quick question.

**Make it stronger while you wait.** Your canvas is at {{idea.strength}} of 5.{{#idea.next_best.0}} What would help most:
- {{idea.next_best.0}}{{/idea.next_best.0}}{{#idea.next_best.1}}
- {{idea.next_best.1}}{{/idea.next_best.1}}

[Track or improve your idea]({{links.idea}})

The 1% Club team

A KFintech programme
