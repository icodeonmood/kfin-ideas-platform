---
type: rule
title: Outcome reason codes
description: Allowed reasons for park, decline and gate outcomes, with the plain words submitters see.
tags:
- rules
- decisions
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: RULE-reason-codes
  version: '1.0'
  approver: null
---

Every park or decline needs a code from this list and a written note. Submitters never see the code itself, only the plain words and the committee's note,
plus what would change the decision and how to appeal.

```yaml
version: '1.0'
codes:
- code: LOW_VALUE
  used_for:
  - decline
  plain_words: The committee did not see enough value for KFintech right now.
- code: NOT_FEASIBLE_NOW
  used_for:
  - decline
  - park
  plain_words: It can't be done well with what we have today.
- code: REG_CONFLICT
  used_for:
  - decline
  plain_words: It conflicts with a regulation or a contract we must follow.
- code: OUT_OF_SCOPE
  used_for:
  - decline
  plain_words: It sits outside what this programme can take on.
- code: INSUFFICIENT_EVIDENCE
  used_for:
  - park
  plain_words: We need more evidence before the committee can weigh it.
- code: NOT_PRESENTED
  used_for:
  - park
  plain_words: It was shortlisted, but a presentation didn't happen after two slots.
- code: CAPACITY
  used_for:
  - park
  plain_words: It is worth doing, but this cycle's capacity is full. It returns next cycle.
- code: ALREADY_SOLVED
  used_for:
  - gate
  plain_words: 'Already running: a team has already built this. Team up to bring it to your area.'
- code: ALREADY_PLANNED
  used_for:
  - gate
  plain_words: 'Planned by a team: follow its progress here.'
- code: DUPLICATE
  used_for:
  - review
  plain_words: Colleagues raised the same thing. You're now part of that crew.
- code: REDIRECTED
  used_for:
  - review
  plain_words: This is best handled by another team, and we've pointed you there.
```
