---
type: rule
title: The Ones' tiers
description: How measured, confirmed impact sets a One's tier, from Tier 1, Spark to Tier 7, Star. The programme team changes these without a release.
tags:
- rules
- ones
- tiers
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: RULE-tiers
  version: '1.0'
  approver: null
---

A person becomes a One when an idea they are credited on has shipped and its impact has been measured and confirmed. Their tier warms as their impact grows (`L-ONES.rules/1`, `/3`). The design leaves the thresholds open (`L-ONES.open`), so they live here, where the programme team can change them through an admin-approved pull request, with Git as the audit trail.

How a tier is worked out: add up, across every shipped idea the person is credited on, the latest measured figures that count. Hours saved count once entered. Money counts only once Finance has confirmed it. The tier is the highest one whose hours **or** money threshold is met. A tier only rises on its own; it never falls because a later figure is lower. Points never decide a tier.

```yaml
version: '1.0'
# tier: {hours_month: hours saved a month, money_year: rupees saved or earned a year}. Either one is enough.
tiers:
  1: {hours_month: 0, money_year: 0}            # Spark: every new One
  2: {hours_month: 100, money_year: 500000}     # Glow: 100 hours a month, or ₹5 lakh a year
  3: {hours_month: 250, money_year: 1000000}    # Flame
  4: {hours_month: 500, money_year: 2500000}    # Blaze
  5: {hours_month: 1000, money_year: 5000000}   # White heat
  6: {hours_month: 2500, money_year: 10000000}  # Blue flame: ₹1 crore a year
  7: {hours_month: 5000, money_year: 25000000}  # Star
```
