---
type: comms-template
title: '{{from.display}} merged your idea'
description: 'Inbox item and email for the desk_merge kind (L-INBOX.kinds). Row text: pack (NOT DRAWN default). 1.1 (BLD-A195): typographic apostrophes (’) in the row text, note and email, as in every other line. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-desk-merge
  version: '1.1'
  kinds:
  - desk_merge
  subject: '{{from.display}} merged your idea'
  inbox:
    heading: 'Ideas merged by the desk'
    line: 'merged your idea with {{other.possessive}}'
    note: 'Both of you are credited, and you’re on one crew now.'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} {{line}}: **{{idea.title}}**.

Both of you are credited. See what changed in the app.

[Open the idea]({{links.action}})

The 1% Club team
