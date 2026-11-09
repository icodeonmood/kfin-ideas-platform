---
type: comms-template
title: "Your appeal on {{cluster.id}} has been heard"
description: Message template for appeal.decided (draft, waiting for HR review, BLD-222).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-appeal-decided
  version: '0.1'
  events:
  - appeal.decided
  subject: "Your appeal on {{cluster.id}} has been heard"
  signed_as: "The appeal panel"
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

The panel has heard the appeal on **{{cluster.name}}**.

{{appeal.outcome_text}}

[See your idea]({{links.idea}})

[Your appeals]({{links.appeals}})

The appeal panel

A KFintech programme
