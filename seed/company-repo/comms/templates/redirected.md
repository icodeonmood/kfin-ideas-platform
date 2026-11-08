---
type: comms-template
title: 'Where to take this: {{redirect.team}}'
description: Message template for idea.redirected.
tags:
- comms
- template
status: draft
verified: unverified
generated:
  by: human:product-team-draft
  at: '2026-11-08'
kfin:
  id: TPL-redirected
  version: '1.0'
  events:
  - idea.redirected
  subject: 'Where to take this: {{redirect.team}}'
  signed_as: '{{reviewer.name}}, review desk'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Thanks for raising **"{{idea.one_line}}"**. {{redirect.message}}

{{#redirect.url}}[Go to {{redirect.team}}]({{redirect.url}}){{/redirect.url}}

If you think this is really an idea for changing how KFintech works, reply in the app and tell us why. We'll look again.

{{reviewer.name}}, review desk
