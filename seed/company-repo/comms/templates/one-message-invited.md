---
type: comms-template
title: "A few words for {{one.display}}"
description: Message template for ones.message_invited.
tags:
- comms
- template
- ones
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-one-message-invited
  version: '1.0'
  events:
  - ones.message_invited
  subject: "A few words for {{one.display}}"
  signed_as: "The 1% Club team"
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, warm and specific, in the club's voice (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

The 1% Club core committee is about to move {{one.display}} to **{{tier.to_name}}**. Would you write them a few words? They'll read them when they see their new tier.

[Write your message]({{links.write}})

The 1% Club team

A KFintech programme
