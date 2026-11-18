---
type: comms-template
title: '{{from.display}} revised what your idea is worth'
description: 'Inbox item and email for the worth_revised kind (L-INBOX.kinds). Row text: pack (NOT DRAWN default). 1.1 (BLD-A195): typographic apostrophes (’) in the row text, note and email, as in every other line. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-worth-revised
  version: '1.1'
  kinds:
  - worth_revised
  subject: '{{from.display}} revised what your idea is worth'
  inbox:
    heading: 'Worth revised'
    line: 'revised what your idea is worth'
    note: 'The new figure and the review desk’s note are on your idea’s page.'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} {{line}}: **{{idea.title}}**.

See the new figure and the note in the app.

[Open the idea]({{links.action}})

The 1% Club team
