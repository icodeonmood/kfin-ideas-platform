---
type: comms-template
title: '{{from.display}} asks to team up on your idea'
description: 'Inbox item and email for the teamup_request kind (L-INBOX.kinds). Row text: pack, with "her" made "their" (BLD-E008); "asks to team up" for a team-up only request is for HR. 1.1 (BLD-A195): a request that brings any idea reads "Merge request" and "asks to team up and merge their idea into yours", a sheet request with ideas brought included; "their ideas" when it brings two or more (lane F''s HR list); the reader''s note "… is bringing other ideas along." is gone (not in the pack; the idea brought shows in the reader). Email wording: draft for HR.'
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
  version: '1.1'
  kinds:
  - teamup_request
  subject: '{{from.display}} asks to team up on your idea'
  inbox:
    heading: '{{#request.merge}}Merge request{{/request.merge}}{{#request.team_only}}Team-up request{{/request.team_only}}'
    line: '{{#request.merge}}asks to team up and merge their {{#brought.many}}ideas{{/brought.many}}{{#brought.single}}idea{{/brought.single}} into yours{{/request.merge}}{{#request.team_only}}asks to team up{{/request.team_only}}'
    note: ''
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
