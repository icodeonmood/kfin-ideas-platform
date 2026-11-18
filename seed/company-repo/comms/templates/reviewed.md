---
type: comms-template
title: '{{idea.id}} has been reviewed'
description: Message template for idea.reviewed.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: TPL-reviewed
  version: '1.4'
  events:
  - idea.reviewed
  subject: '{{idea.id}} has been reviewed'
  signed_as: 'The review desk, 1% Club'
  hr_signed_off: false
---

<!-- Mustache-style variables. Keep it short, warm and specific. HR signs off all wording. -->

Hi {{recipient.first_name}},

Your idea **"{{idea.one_line}}"** has been reviewed.

{{#outcome.grouped}}It's now part of **{{cluster.name}}**, a group of similar ideas from colleagues. Grouped ideas are weighed together, and you keep full credit as a contributor.{{/outcome.grouped}}
{{#outcome.grouped_unnamed}}It's now part of a group of similar ideas from colleagues. Grouped ideas are weighed together, and you keep full credit as a contributor.{{/outcome.grouped_unnamed}}
{{#outcome.linked}}It's now linked with a similar idea from a colleague. Linked ideas are weighed together, and you keep full credit as a contributor.{{/outcome.linked}}
{{#outcome.standalone}}It stays as its own idea for now. If colleagues raise the same thing, we'll group them and tell you.{{/outcome.standalone}}
{{#reviewer.note}}**Note from the reviewer:** {{reviewer.note}}{{/reviewer.note}}

**What happens next:** {{next_step.text}}

[See your idea]({{links.idea}})

The review desk, 1% Club

A KFintech programme
