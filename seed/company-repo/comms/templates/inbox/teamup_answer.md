---
type: comms-template
title: '{{from.display}} answered your team-up request'
description: 'Inbox item and email for the teamup_answer kind (L-INBOX.kinds). Row text: pack for "approved your team-up request"; the declined line is for HR. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-teamup-answer
  version: '1.0'
  kinds:
  - teamup_answer
  subject: '{{from.display}} answered your team-up request'
  inbox:
    heading: 'Request answered'
    line: '{{#answer.approved}}approved your team-up request{{/answer.approved}}{{#answer.declined}}declined your team-up request, with a reason{{/answer.declined}}'
    note: '{{#answer.approved}}You''re on {{from.first_name}}''s crew now.{{/answer.approved}}{{#answer.declined}}The reason is in the app, with your request.{{/answer.declined}}'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} {{line}}: **{{idea.title}}**.

{{#answer.approved}}You're on the crew now.{{/answer.approved}}{{#answer.declined}}Read the reason in the app.{{/answer.declined}}

[Open the idea]({{links.action}})

The 1% Club team
