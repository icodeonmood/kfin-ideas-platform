---
type: comms-template
title: 'Your idea is now part of {{cluster.id}}'
description: Message template for cluster.approved (draft, waiting for HR sign-off).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-cluster-approved
  version: '0.1'
  events:
  - cluster.approved
  subject: 'Your idea is now part of {{cluster.id}}'
  signed_as: 'The 1% Club review desk'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Colleagues raised the same thing as you. The review desk has put your idea in a group with {{cluster.other_count}} similar ideas: **{{cluster.name}}**.

{{cluster.description}}

Grouped ideas are weighed together, and you keep full credit as a contributor.

**What happens next:** the review desk checks the evidence and what the group could be worth. We'll tell you when it moves on.

[See your idea]({{links.idea}})

The 1% Club review desk

A KFintech programme
