---
type: comms-template
title: "An appeal for your panel: {{cluster.id}}"
description: Message template for appeal.filed (draft, waiting for HR review, BLD-222).
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-10T00:00:00+05:30'
kfin:
  id: TPL-appeal-filed
  version: '0.1'
  events:
  - appeal.filed
  subject: "An appeal for your panel: {{cluster.id}}"
  signed_as: "The 1% Club core committee chair"
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Colleagues have appealed the committee's decision on **{{cluster.name}}**, and you are on the panel that hears it.

{{appeal.hearing_text}}

The panel's chair records the outcome by {{appeal.due_date}}.

[Open the appeal]({{links.appeal}})

The 1% Club core committee chair

A KFintech programme
