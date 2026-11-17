---
type: comms-template
title: '{{from.display}} joined your crew'
description: 'Inbox item and email for the crew_joined kind (L-INBOX.kinds). Row text: pack. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-crew-joined
  version: '1.0'
  kinds:
  - crew_joined
  subject: '{{from.display}} joined your crew'
  inbox:
    heading: 'Joined your crew'
    line: 'joined your crew'
    note: ''
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} joined your crew on **{{idea.title}}**.

[Open the idea]({{links.action}})

The 1% Club team
