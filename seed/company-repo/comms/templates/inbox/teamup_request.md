---
type: comms-template
title: '{{from.display}} asks to team up on your idea'
description: 'Inbox item and email for the teamup_request kind (L-INBOX.kinds). Row text: pack, with "her" made "their" (BLD-E008); "asks to team up" for a team-up only request is for HR. Email wording: draft for HR.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-teamup-request
  version: '1.0'
  kinds:
  - teamup_request
  subject: '{{from.display}} asks to team up on your idea'
  inbox:
    heading: '{{#request.merge}}Merge request{{/request.merge}}{{#request.team_only}}Team-up request{{/request.team_only}}'
    line: '{{#request.merge}}asks to team up and merge their idea into yours{{/request.merge}}{{#request.team_only}}asks to team up{{/request.team_only}}'
    note: '{{#brought.any}}{{from.first_name}} is bringing other ideas along.{{/brought.any}}'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-INBOX.kinds. The row reads "<sender> <line>". Never add a reason, a note, a question or anyone's words: the
reader opens those in the app (L-NOTIFY/3, BLD-E004). No pronouns for a person: first name, or they/their (BLD-E008). -->

Hi {{recipient.first_name}},

{{from.display}} {{line}}: **{{idea.title}}**.

Read the note and answer in the app.

[Answer the request]({{links.action}})

The 1% Club team
