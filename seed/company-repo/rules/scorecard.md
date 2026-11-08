---
type: rule
title: Committee scorecard
description: Dimensions, weights, bands and confidence multipliers committees use to score clusters.
tags:
- rules
- scoring
status: draft
verified: unverified
generated:
  by: human:product-team-draft
  at: '2026-11-08'
kfin:
  id: RULE-scorecard
  version: '1.0'
  approver: null
---

Committees score each cluster from 1 to 5 on six dimensions. Final score = Σ(weight × median rating) ÷ 5 × confidence multiplier, on a 0–100 scale.
Annual net benefit = recurring revenue + recurring cost saving − opex − capex ÷ 5 (capex spread over five years).
Changing this file needs core committee approval, recorded in the pull request.

```yaml
version: '1.0'
scale:
- 1
- 5
dimensions:
  financial_value:
    weight: 30
    measure: annual_net_benefit_band
  customer_experience:
    weight: 20
  risk_compliance:
    weight: 15
  reach:
    weight: 15
  time_to_value:
    weight: 10
  effort:
    weight: 10
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
