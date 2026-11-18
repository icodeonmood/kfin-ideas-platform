---
type: comms-template
title: 'The Ones Committee reversed a decision'
description: 'Inbox item and email for the decision_reversed kind (L-INBOX.kinds). Row text: pack for the sharer; the reviewer''s line is for HR. 1.1 (BLD-A195): typographic apostrophes (’) in the row text, note and email, as in every other line. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-decision-reversed
  version: '1.1'
  kinds:
  - decision_reversed
  subject: 'The Ones Committee reversed a decision'
  inbox:
    heading: 'Decision reversed'
    line: '{{#viewer.sharer}}reversed a decision on your idea{{/viewer.sharer}}{{#viewer.decided}}reversed your decision on this idea{{/viewer.decided}}'
    note: 'The Ones Committee’s note and the new decision are on the idea’s page. This is final.'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} {{line}}: **{{idea.title}}**.

Read the note and the new decision in the app. This is final.

[Read the note]({{links.action}})

The 1% Club team
