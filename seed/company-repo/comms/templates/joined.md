---
type: comms-template
title: '{{join.count}} more colleagues raised the same thing'
description: Message template for idea.joined.
tags:
- comms
- template
status: draft
verified: unverified
generated:
  by: human:product-team-draft
  at: '2026-11-08'
kfin:
  id: TPL-joined
  version: '1.0'
  events:
  - idea.joined
  subject: '{{join.count}} more colleagues raised the same thing'
  signed_as: The Garage team
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Good news: **{{join.count}}** more {{join.count_word}} raised the same thing as your idea **"{{idea.one_line}}"**. Ideas raised by more people from more teams carry more weight with the committee.

{{#join.names_visible}}They are: {{join.names}}.{{/join.names_visible}}

[See your crew]({{links.idea}})

The Garage · Ideas
