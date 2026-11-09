---
type: comms-template
title: 'An update on {{cluster.id}}'
description: Message template for decision.not_presented (draft, waiting for HR review, BLD-221).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-not-presented
  version: '0.1'
  events:
  - decision.not_presented
  subject: 'An update on {{cluster.id}}'
  signed_as: 'The 1% Club core committee chair'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

The committee kept a slot for **{{cluster.name}}**, but the presentation did not take place. The group is parked for now.

If something got in the way, please tell the committee chair. You can also appeal within 15 working days from your idea page.

[See your idea]({{links.idea}})

The 1% Club core committee chair

A KFintech programme
