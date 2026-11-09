---
type: comms-template
title: "New Ones"
description: Message template for ones.announced.
tags:
- comms
- template
- ones
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-ones-announced
  version: '1.0'
  events:
  - ones.announced
  subject: "New Ones"
  signed_as: "The 1% Club team"
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, warm and specific, in the club's voice (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

{{ones.count}} {{ones.count_word}} joined the 1% Club after this week's core committee meeting.

{{ones.list}}

Each of them noticed something, then did the work to fix it.

Yours could be next. You don't apply. You build your way in.

[See the Ones]({{links.wall}})

The 1% Club team

A KFintech programme
