---
type: comms-template
title: '{{#cluster.named}}Your idea is now in a group: {{cluster.name}}{{/cluster.named}}{{#cluster.unnamed}}Your idea is now in a group of similar ideas{{/cluster.unnamed}}'
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
  version: '0.3'
  events:
  - cluster.approved
  subject: '{{#cluster.named}}Your idea is now in a group: {{cluster.name}}{{/cluster.named}}{{#cluster.unnamed}}Your idea is now in a group of similar ideas{{/cluster.unnamed}}'
  signed_as: 'The 1% Club review desk'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Colleagues raised the same thing as you. {{#cluster.named}}The review desk has put your idea in a group of similar ideas: **{{cluster.name}}**.{{/cluster.named}}{{#cluster.unnamed}}The review desk has put your idea in a group of similar ideas.{{/cluster.unnamed}}{{#cluster.one_other}} It holds one other idea.{{/cluster.one_other}}{{#cluster.many_others}} It holds {{cluster.other_count}} other ideas.{{/cluster.many_others}}

{{cluster.description}}

Grouped ideas are weighed together, and you keep full credit as a contributor.

**What happens next:** the review desk checks the evidence and what the group could be worth. We'll tell you when it moves on.

[See your idea]({{links.idea}})

The 1% Club review desk

A KFintech programme
