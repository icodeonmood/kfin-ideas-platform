---
type: comms-template
title: '{{left}} left to answer the review desk’s questions'
description: 'Inbox item and email for the answer_reminder kind (L-INBOX.kinds). Row text: pack (NOT DRAWN default). Email wording: draft for HR. 1.1 (DEC-111, BLD-B257): the questions are the review desk’s, never a reviewer’s by name.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-answer-reminder
  version: '1.1'
  kinds:
  - answer_reminder
  subject: '{{left}} left to answer the review desk’s questions'
  inbox:
    heading: 'Answer reminder'
    line: '{{left}} left to answer the review desk’s questions'
    note: 'Answer by {{due.long}}.'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{left}} left to answer the review desk’s questions about **{{idea.title}}**.

Answer by {{due.long}}.

[Answer the questions]({{links.action}})

The 1% Club team
