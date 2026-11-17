---
type: comms-template
title: '{{from.display}} asked you {{count_words}}'
description: 'Inbox item and email for the questions kind (L-INBOX.kinds). Row text: pack. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-questions
  version: '1.0'
  kinds:
  - questions
  subject: '{{from.display}} asked you {{count_words}}'
  inbox:
    heading: 'Questions from the review desk'
    line: 'asked you {{count_words}}'
    note: 'Answer by {{due.long}}.'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} asked you {{count_words}} about **{{idea.title}}**.

Answer by {{due.long}}.

[Answer the questions]({{links.action}})

The 1% Club team
