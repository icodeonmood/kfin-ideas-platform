---
type: comms-template
title: 'Your draft is saved'
description: 'Inbox item and email for the draft_kept kind (L-INBOX.kinds). Row text: pack. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-draft-kept
  version: '1.0'
  kinds:
  - draft_kept
  subject: 'Your draft is saved'
  inbox:
    heading: 'Draft kept'
    line: 'kept your draft from {{#via.phone}}your phone{{/via.phone}}{{#via.email}}email{{/via.email}}{{#via.teams}}Teams{{/via.teams}}'
    note: 'Pick up where you left off.'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

1% Club {{line}}: **{{idea.title}}**.

Pick up where you left off.

[Carry on]({{links.action}})

The 1% Club team
