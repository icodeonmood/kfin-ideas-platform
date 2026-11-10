---
type: comms-template
title: 'An update on {{cluster.id}}'
description: Message template for cluster.gate_outcome (draft, waiting for HR review, DEC-066).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-gate-outcome
  version: '0.1'
  events:
  - cluster.gate_outcome
  subject: 'An update on {{cluster.id}}'
  signed_as: 'The 1% Club review desk'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

The review desk has looked at **{{cluster.name}}**, the group your idea is part of.

{{outcome.text}}

You keep full credit as a contributor.

[See your idea]({{links.idea}})

The 1% Club review desk

A KFintech programme
