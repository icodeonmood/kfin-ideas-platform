---
type: comms-template
title: '{{from.display}} asked you to check new messages'
description: 'Inbox item and email for the build_ask kind (L-INBOX.kinds). Row text: pack. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-build-ask
  version: '1.0'
  kinds:
  - build_ask
  subject: '{{from.display}} asked you to check new messages'
  inbox:
    heading: 'A build team asks'
    line: 'asked you to check new messages'
    note: '{{#due.any}}Please look by {{due.long}}.{{/due.any}}'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} asked you to check new messages about **{{idea.title}}**.

{{#due.any}}Please look by {{due.long}}.{{/due.any}}

[Open the conversation]({{links.action}})

The 1% Club team
