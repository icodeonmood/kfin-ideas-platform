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
  version: '1.1'
  events:
  - adoption.requested
  subject: A team wants to adopt {{solution.title}}
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

A colleague from **{{requester.lob_name}}** wants to bring **{{solution.title}}** ({{solution.id}}) to their area. Here is their context:

> {{request.context}}

Could you have a short conversation with them? They'll be credited for taking it to a new area, and you'll be credited for the reuse.

[Open the request]({{links.request}})

The 1% Club team

A KFintech programme
