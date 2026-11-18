---
type: comms-template
title: '{{from.display}} answered your team-up request'
description: 'Inbox item and email for the teamup_answer kind (L-INBOX.kinds). Row text: pack for "approved your team-up request"; the declined line is for HR. 1.1 (BLD-A195): typographic apostrophes (’) in the row text, note and email, as in every other line. BLD-A196, for HR (NOT DRAWN; lane F''s word, BLD-F029): when the lead declined and has hidden their name from the Wall, or has left, the sender reads `hidden_sender`, so the row and email say "The lead declined your team-up request, with a reason" and the subject "The lead answered your team-up request"; an approved requester is on the crew and reads the name. Email wording: draft for HR.'
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
  version: '1.1'
  kinds:
  - teamup_answer
  subject: '{{from.display}} answered your team-up request'
  inbox:
    heading: 'Request answered'
    line: '{{#answer.approved}}approved your team-up request{{/answer.approved}}{{#answer.declined}}declined your team-up request, with a reason{{/answer.declined}}'
    note: '{{#answer.approved}}You’re on {{from.first_name}}’s crew now.{{/answer.approved}}{{#answer.declined}}The reason is in the app, with your request.{{/answer.declined}}'
    hidden_sender: 'The lead'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} {{line}}: **{{idea.title}}**.

{{#answer.approved}}You’re on the crew now.{{/answer.approved}}{{#answer.declined}}Read the reason in the app.{{/answer.declined}}

[Open the idea]({{links.action}})

The 1% Club team
