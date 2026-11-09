---
type: comms-template
title: A quick question about {{idea.id}}
description: Message template for idea.question.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: TPL-question
  version: '1.1'
  events:
  - idea.question
  subject: A quick question about {{idea.id}}
  signed_as: '{{reviewer.name}}, review desk'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

I'm reviewing your idea **"{{idea.one_line}}"** and have one question:

> {{question.text}}

Please reply in the app by **{{question.due_date}}**. The review clock pauses until you answer. If we don't hear back within 7 working days, we'll set the idea aside, and you can reopen it any time.

[Reply here]({{links.idea}})

{{reviewer.name}}, review desk, 1% Club

A KFintech programme
