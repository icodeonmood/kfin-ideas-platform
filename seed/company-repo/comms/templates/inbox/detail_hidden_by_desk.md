---
type: comms-template
title: 'A detail was hidden in your idea'
description: 'Inbox item and email for the detail_hidden_by_desk kind (L-HIDE/7, agreed with lane C, BLD-A205). Sent by the review desk as a whole, never by the reviewer''s name; not "Needs you"; no refs, so no hidden detail can reach it (L-HIDE/8). Heading and line: lane A draft for HR sign-off.'
tags:
- comms
- template
- inbox
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-inbox-detail-hidden-by-desk
  version: '1.0'
  kinds:
  - detail_hidden_by_desk
  subject: 'A detail was hidden in your idea'
  inbox:
    heading: 'A detail was hidden'
    line: 'hid a customer’s detail in your idea'
    note: 'Only you can still see it.'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- L-HIDE/7. The row reads "The review desk hid a customer’s detail in your idea"; with the note, the reader says
"The review desk hid a customer’s detail in your idea. Only you can still see it." Never name the reviewer, and
never say what was hidden: not the detail, its kind or where it was (L-HIDE/8, L-NOTIFY/3). -->

Hi {{recipient.first_name}},

The review desk hid a customer’s detail in your idea **{{idea.title}}**. Only you can still see it.

[Open your idea]({{links.action}})

The 1% Club team
