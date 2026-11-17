---
type: comms-template
title: 'A decision on your idea'
description: 'Inbox item and email for the decision kind (L-INBOX.kinds). Row text: pack for Picked and Not picked; the Not now line is for HR. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-decision
  version: '1.0'
  kinds:
  - decision
  subject: 'A decision on your idea'
  inbox:
    heading: 'Decision'
    line: '{{#choice.pick}}picked your idea{{/choice.pick}}{{#choice.not_picked}}didn''t pick your idea, with a reason{{/choice.not_picked}}{{#choice.not_now}}said Not now to your idea, with a date it comes back{{/choice.not_now}}'
    note: 'The reason is on your idea''s page.'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} {{line}}: **{{idea.title}}**.

Read the decision and the reason in the app.

[Read the decision]({{links.action}})

The 1% Club team
