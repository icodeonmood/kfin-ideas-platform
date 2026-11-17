---
type: comms-template
title: '{{from.display}} commented on your idea'
description: 'Inbox item and email for the comment kind (L-INBOX.kinds). Row text: pack. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-comment
  version: '1.0'
  kinds:
  - comment
  subject: '{{from.display}} commented on your idea'
  inbox:
    heading: 'Comment on your idea'
    line: 'commented on your idea'
    note: ''
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} commented on **{{idea.title}}**.

[Open the conversation]({{links.action}})

The 1% Club team
