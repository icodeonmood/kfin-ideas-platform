---
type: comms-template
title: 'We have paused {{idea.id}}'
description: Message template for idea.withdrawn_no_answer.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-withdrawn-no-answer
  version: '1.0'
  events:
  - idea.withdrawn_no_answer
  subject: 'We have paused {{idea.id}}'
  signed_as: The Garage team
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

We asked a question about **"{{idea.one_line}}"** and have not heard back in 7 working days, so we have paused it for now.

You can pick it up again at any time: answer the question and it goes straight back to the review desk.

[Reopen your idea]({{links.idea}})

The Garage · Ideas
