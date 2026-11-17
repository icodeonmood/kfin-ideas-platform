---
type: comms-template
title: 'Your idea is with the review desk'
description: 'Inbox item and email for the sent_to_desk kind (L-INBOX.kinds). Row text: pack. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-sent-to-desk
  version: '1.0'
  kinds:
  - sent_to_desk
  subject: 'Your idea is with the review desk'
  inbox:
    heading: 'Sent to the review desk'
    line: 'sent your idea to the review desk'
    note: '{{#decide_by.any}}The review desk will look at it by {{decide_by.long}}.{{/decide_by.any}}'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

1% Club {{line}}: **{{idea.title}}**.

{{#decide_by.any}}The review desk will look at it by {{decide_by.long}}.{{/decide_by.any}}

[Open the idea]({{links.action}})

The 1% Club team
