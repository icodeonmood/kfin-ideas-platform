---
type: comms-template
title: "Thank you, {{recipient.first_name}}"
description: Message template for ones.removed.
tags:
- comms
- template
- ones
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-one-removed
  version: '1.0'
  events:
  - ones.removed
  subject: "Thank you, {{recipient.first_name}}"
  signed_as: "The 1% Club team"
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, warm and specific, in the club's voice (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

Thank you for everything you did as No. {{one.number}}. The 1% Club core committee has closed your membership.

{{#removal.reason}}**Why:** {{removal.reason}}{{/removal.reason}}

Your spark stays in the sky, and your number rests for six months before anyone else can wear it. The door stays open: a new idea can bring you back.

The 1% Club team

A KFintech programme
