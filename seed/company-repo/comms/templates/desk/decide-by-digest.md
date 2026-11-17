---
type: comms-template
title: 'Past the decide-by date: {{digest.count_words}} still with the review desk'
description: The daily email to the review desk about ideas past their decide-by date (L-REVIEW.clock/3, NOT DRAWN default; BLD-A203). Draft for HR.
tags:
- comms
- template
- review
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: TPL-desk-decide-by-digest
  version: '1.0'
  events:
  - review.decide_by_digest
  subject: 'Past the decide-by date: {{digest.count_words}} still with the review desk'
  signed_as: The 1% Club team
  hr_signed_off: false
---

<!-- One line per idea: its title, its reference, the decide-by date, how late, and who opened it. Built by
notify/digest.py at send time; the "- {{digest.item}}" line is repeated once per idea. No reason, note or words. -->

Hi {{recipient.first_name}},

{{digest.count_words}} past the date the review desk promised a decision by.

- {{digest.item}}

{{#digest.has_more}}And {{digest.more}} more on the review desk.{{/digest.has_more}}

Nothing is decided for you. Open each one and decide, or move its date and tell the sharer.

[Open the review desk]({{links.desk}})

The 1% Club team
