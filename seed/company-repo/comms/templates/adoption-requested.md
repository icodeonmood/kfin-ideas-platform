---
type: comms-template
title: A team wants to adopt {{solution.title}}
description: Message template for adoption.requested.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: TPL-adoption-requested
  version: '1.3'
  events:
  - adoption.requested
  subject: A team wants to adopt {{solution.title}}
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

A colleague from **{{requester.lob_name}}** wants to bring **{{solution.title}}** to their area.{{#request.context}} In their words:{{/request.context}}

{{#request.context}}> {{request.context}}{{/request.context}}

If your team can help them adopt it, the 1% Club team can put you in touch.

{{#links.request}}[Open the request]({{links.request}}){{/links.request}}

The 1% Club team

A KFintech programme
