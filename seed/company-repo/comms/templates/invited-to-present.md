---
type: comms-template
title: "You're invited to present {{cluster.id}}"
description: Message template for shortlist.invited (draft, waiting for HR review, DEC-066).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-invited-to-present
  version: '0.1'
  events:
  - shortlist.invited
  subject: "You're invited to present {{cluster.id}}"
  signed_as: 'The 1% Club core committee chair'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Good news. The core committee has shortlisted **{{cluster.name}}**, the group your idea is part of, and invites you to present it.

Choose up to three presenters from the colleagues in the group and a time that suits you by {{presentation.reply_due}}. A draft outline for an 8-slide deck is ready for you to edit.

[Accept the invitation]({{links.presentation}})

The 1% Club core committee chair

A KFintech programme
