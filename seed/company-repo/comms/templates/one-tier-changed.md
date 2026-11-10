---
type: comms-template
title: "{{#tier.up}}Your spark is hotter: {{tier.to_name}}{{/tier.up}}{{#tier.down}}Your tier has changed{{/tier.down}}"
description: Message template for ones.tier_changed.
tags:
- comms
- template
- ones
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-09T00:00:00+05:30'
kfin:
  id: TPL-one-tier-changed
  version: '1.1'
  events:
  - ones.tier_changed
  subject: "{{#tier.up}}Your spark is hotter: {{tier.to_name}}{{/tier.up}}{{#tier.down}}Your tier has changed{{/tier.down}}"
  signed_as: "The 1% Club team, on behalf of the core committee and the CEO"
  hr_signed_off: false
---

<!-- Mustache-style variables. Short, warm and specific, in the club's voice (docs/BRAND.md). HR reviews all wording later (DEC-066). -->

Hi {{recipient.first_name}},

{{#tier.up}}Your spark has moved {{#tier.from_name}}from {{tier.from_name}} {{/tier.from_name}}to **{{tier.to_name}}**. On behalf of the 1% Club core committee and the CEO: well done.{{/tier.up}}
{{#tier.down}}The 1% Club core committee has moved your tier {{#tier.from_name}}from {{tier.from_name}} {{/tier.from_name}}to {{tier.to_name}}.{{/tier.down}}

{{#tier.committee_message}}**From the core committee:** {{tier.committee_message}}{{/tier.committee_message}}

{{#tier.up}}Sign in to see your glow-up, your story so far and the messages colleagues wrote for you.{{/tier.up}}

[Open your dashboard]({{links.my_ideas}})

The 1% Club team, on behalf of the core committee and the CEO

A KFintech programme
