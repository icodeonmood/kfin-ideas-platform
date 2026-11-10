---
type: comms-template
title: '{{#join.one}}A colleague raised the same thing as you{{/join.one}}{{#join.many}}{{join.count}} colleagues have now raised the same thing as you{{/join.many}}'
description: Message template for idea.joined.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: TPL-joined
  version: '1.2'
  events:
  - idea.joined
  subject: '{{#join.one}}A colleague raised the same thing as you{{/join.one}}{{#join.many}}{{join.count}} colleagues have now raised the same thing as you{{/join.many}}'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

{{#join.one}}Good news: a colleague has raised the same thing as your idea **"{{idea.one_line}}"**.{{/join.one}}{{#join.many}}Good news: {{join.count}} colleagues have now raised the same thing as your idea **"{{idea.one_line}}"**.{{/join.many}} Ideas raised by more people from more teams carry more weight with the committee.

{{#join.names_visible}}They are: {{join.names}}.{{/join.names_visible}}

[See your crew]({{links.idea}})

The 1% Club team

A KFintech programme
