---
type: rule
title: Priority classification for the core committee brief
description: Eight parameters, anchors, weights, classes and override rules the rules engine uses to compute P1–P4. Core committee only.
tags:
- rules
- priority
- core-committee
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: RULE-priority
  version: '1.0'
  approver: null
---

`priority-brief` rates eight parameters from 1 to 5 using the anchors below and cites evidence. The rules engine, not the model, computes the score and class:
priority score = Σ(weight × rating) ÷ 5, on a 0–100 scale. Risk has no weight; it acts through the override rules.
The resulting class is shown to the core committee only and is never written to a decision file.

```yaml
version: '1.0'
weights:
  impact: 20
  value: 25
  right_to_win: 15
  competitive: 10
  value_chain_fit: 10
  build_buy_fit: 10
  urgency: 10
value_chain_fit_rating:
  direct: 5
  adjacent: 4
  new: 2
competitive_positions:
- parity_gap
- white_space
- crowded
classes:
  P1_act_now:
  - 75
  - 100
  P2_next_cycle:
  - 60
  - 75
  P3_watch:
  - 45
  - 60
  P4_not_now:
  - 0
  - 45
overrides:
- when: urgency.regulatory_deadline_within_months <= 6
  then: at_least P2
- when: value_chain_fit == new and right_to_win <= 2
  then: at_most P3
- when: risk == 5
  then: at_most P3 until compliance clears
- when: competitive == parity_gap and value_chain_fit == direct and competitive_rating >= 4
  then: at_least P2
```

## Anchors

| Parameter | 1 | 3 | 5 |
|---|---|---|---|
| Impact | A few people in one team, small change | One LOB or a client segment, clear change | Many clients or investors, or several LOBs, large change |
| Value | Annual net benefit under ₹5 lakh | ₹25 lakh – ₹1 crore | Over ₹5 crore (one-time revenue shown separately) |
| Competitive landscape | Crowded and done well by many | Some players, no clear leader | Parity gap with real urgency, or clear white space to lead |
| Value-chain fit | New: outside today's value chain (rated 2) | Adjacent: uses KFin's data, clients or rails (rated 4) | Direct: improves a service KFin runs today (rated 5) |
| Right to win | No KFin advantage | Some advantage from data, clients or rails | Strong advantage from data, client base, regulatory role, rails or cost |
| Build-vs-buy fit | Recommended route is costly, slow or gives up control | Workable route with trade-offs | Cheap, fast route with control (often reuse) |
| Urgency | None | Client commitment or competitor move within a year | Regulatory deadline within 6 months |
| Risk (higher = riskier) | Low delivery, regulatory and reputational risk | Manageable risks with known mitigations | High risk; compliance must clear first |
