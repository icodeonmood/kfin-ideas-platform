---
type: comms-template
title: 'Update on {{idea.id}}: reconsidered by the core committee'
description: Message template for idea.reconsidered.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: TPL-reconsidered
  version: '1.3'
  events:
  - idea.reconsidered
  subject: 'Update on {{idea.id}}: reconsidered by the core committee'
  signed_as: 'The Ones Committee, 1% Club'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

A member of the 1% Club core committee looked again at your idea **"{{idea.one_line}}"** and changed the earlier outcome.

**Final outcome:** {{outcome.text}}
**Why:** {{outcome.reason}}

**What happens next:** {{next_step.text}}

If you disagree, open your idea and use **Disagree with this?** to tell us why.

{{#links.idea}}[See your idea]({{links.idea}}){{/links.idea}}

The Ones Committee, 1% Club

A KFintech programme
