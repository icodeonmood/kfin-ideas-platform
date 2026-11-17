---
type: comms-template
title: 'Your draft is saved'
description: 'Inbox item and email for the draft_kept kind (L-INBOX.kinds). Row text and buttons: pack, by where the draft came from (BLD-A188). Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-draft-kept
  version: '1.1'
  kinds:
  - draft_kept
  subject: 'Your draft is saved'
  inbox:
    heading: 'Draft kept'
    line: 'kept your draft{{#via.phone}} from your phone{{/via.phone}}{{#via.email}} from email{{/via.email}}{{#via.teams}} from Teams{{/via.teams}}'
    note: 'Pick up where you left off.'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008).
Where it came from is `via` (phone, email or Teams). With none, the line is the plain "kept your draft". A draft sent in
by email or Teams is "Check and send" (J-RESUME/6); one from the phone, or with no `via`, is "Carry on" (BLD-A188). -->

Hi {{recipient.first_name}},

1% Club {{line}}: **{{idea.title}}**.

Pick up where you left off.

{{#via.sent_in}}[Check and send]({{links.action}}){{/via.sent_in}}{{#via.kept}}[Carry on]({{links.action}}){{/via.kept}}

The 1% Club team
