---
type: rule
title: Committee scorecard
description: Dimensions, weights, bands and confidence multipliers committees use to score clusters.
tags:
- rules
- scoring
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: RULE-scorecard
  version: '1.1'
  approver: null
---

Committees score each cluster from 1 to 5 on six dimensions. Final score = Σ(weight × median rating) ÷ 5 × confidence multiplier, on a 0–100 scale.
Annual net benefit = recurring revenue + recurring cost saving − opex − capex ÷ 5 (capex spread over five years).
Changing this file needs core committee approval, recorded in the pull request.
Version 1.1 adds a label and anchor wording (levels 1, 3 and 5) for each dimension, shown on the scoring screen. The anchors are a draft for the core committee to approve before the first round.

```yaml
version: '1.1'
scale:
- 1
- 5
dimensions:
  financial_value:
    weight: 30
    measure: annual_net_benefit_band
    label: Financial value
    anchors:
      '1': "Under ₹5 lakh a year of net benefit"
      '3': "₹25 lakh to ₹1 crore a year"
      '5': "Over ₹5 crore a year"
  customer_experience:
    weight: 20
    label: Customer experience
    anchors:
      '1': "Investors, distributors or clients would barely notice"
      '3': "A clear improvement for one group of customers"
      '5': "A change many customers would talk about"
  risk_compliance:
    weight: 15
    label: Risk and compliance
    anchors:
      '1': "Adds regulatory or operational risk"
      '3': "Neutral on risk"
      '5': "Removes a known regulatory or operational risk"
  reach:
    weight: 15
    label: Reach
    anchors:
      '1': "One team or a handful of people"
      '3': "One LOB or one client segment"
      '5': "Several LOBs or most of KFintech's clients"
  time_to_value:
    weight: 10
    label: Time to value
    anchors:
      '1': "More than a year to any benefit"
      '3': "Benefit within about six months"
      '5': "Benefit within a month or two"
  effort:
    weight: 10
    label: Effort (higher is easier)
    anchors:
      '1': "A large programme across many teams"
      '3': "A few people for a quarter"
      '5': "A small change one team can make"
financial_bands_inr_per_year:
  1:
  - null
  - 500000
  2:
  - 500000
  - 2500000
  3:
  - 2500000
  - 10000000
  4:
  - 10000000
  - 50000000
  5:
  - 50000000
  - null
confidence_multiplier:
  data_backed: 1.0
  estimate: 0.8
  anecdote: 0.5
divergence_flag_points: 2
```

## Anchors

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Financial value | Annual net benefit under ₹5 lakh | ₹25 lakh – ₹1 crore | Over ₹5 crore |
| Customer experience | No visible change for clients or investors | Noticeably faster or simpler for one client segment | Removes a top complaint or creates a clear reason to choose KFin |
| Risk and compliance | Adds regulatory or operational risk | Neutral | Closes a known regulatory or operational risk |
| Reach | One team | One LOB, or a few clients | Several LOBs, or most clients |
| Time to value | More than 12 months | 3–6 months | Under 6 weeks |
| Effort | More than 50 person-weeks or a new platform | 10–20 person-weeks | Under 4 person-weeks, mostly configuration |
