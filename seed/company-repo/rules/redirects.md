---
type: rule
title: Where non-ideas go
description: Redirect targets for IT tickets, HR matters, complaints and questions, with the words the submitter sees.
tags:
- rules
- redirects
status: draft
verified: unverified
generated:
  by: human:product-team-draft
  at: '2026-11-08'
kfin:
  id: RULE-redirects
  version: '1.0'
  approver: null
---

When `gatekeeper` says a submission is not an idea (confidence at or above `gatekeeper.redirect_suggest`), the person sees a redirect card with the target below.
They can always choose "No, this is an idea" and add a reason. **IT, HR and Admin to supply the real links before launch** (`url: null` until then; the card then shows the team name only).

```yaml
version: '0.1'
targets:
  it_ticket:
    team: IT helpdesk
    url: null
    message: This looks like an IT issue that needs fixing for you now. The IT helpdesk can help fastest.
  hr_grievance:
    team: HR
    url: null
    message: This sounds like a personal work matter. Your HR partner is the right person, and it stays confidential there.
  complaint:
    team: Admin and facilities
    url: null
    message: This sounds like something to fix right away. The admin team can act on it today. If you see a pattern worth changing, tell us as
      an idea.
  question:
    team: Intranet help
    url: null
    message: This looks like a question. The intranet help pages or your manager may have the answer.
override_label: No, this is an idea
override_reason_min_chars: 15
```
