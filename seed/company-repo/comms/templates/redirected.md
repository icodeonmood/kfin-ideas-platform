---
type: comms-template
title: 'Where to take this: {{redirect.team}}'
description: 'Message template for idea.redirected. 1.3 (DEC-111, BLD-A222): signed by the review desk as a whole, never by a reviewer’s name. For HR.'
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: TPL-redirected
  version: '1.3'
  events:
  - idea.redirected
  subject: 'Where to take this: {{redirect.team}}'
  signed_as: 'The review desk, 1% Club'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Thanks for raising **"{{idea.one_line}}"**. {{redirect.message}}

{{#redirect.url}}[Go to {{redirect.team}}]({{redirect.url}}){{/redirect.url}}

If you think this is really an idea for changing how KFintech works, open your idea and use **Disagree with this?** to tell us why. We'll look again.

{{#links.idea}}[See your idea]({{links.idea}}){{/links.idea}}

The review desk, 1% Club

A KFintech programme
