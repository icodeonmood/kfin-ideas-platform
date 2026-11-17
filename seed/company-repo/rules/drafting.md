---
type: rule
title: Building the draft from a person's words
description: When the parts of a draft start forming, the lists the assistant chooses who it affects and the area from, and the timings the draft loader starts from (L-DRAFT).
tags:
- rules
- drafting
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-17T00:00:00+05:30'
kfin:
  id: RULE-drafting
  version: '1.0'
  approver: null
---

How "Tell it" turns a person's words into a draft (`L-DRAFT` in the design handoff). The parts start forming once the words reach `parts_from_chars`; similar ideas are looked for from `similar_from_chars`. The minimum before a draft can move to Check it, and how long a draft is kept, are promises: they live in `rules/promises.md`.

`affects` and `area` are the sorting lists (`E-ENUMS.sorting`). The assistant may only choose from them, and only when the person's words back the choice. Once `rules/sorting.md` (L-SORT) is in the company repo, its lists are the ones offered and these labels only carry their cues. `cues` are words that suggest an item; they help the assistant and decide which parts a new message can change. They are never shown. Changes go through a pull request approved by an admin.

`default_means_ms` are the loader's starting times per part (`C-DRAFT-LOADER.maths`) until a week of real timings exists.

```yaml
version: '1.0'
parts_from_chars: 25            # parts start forming (L-DRAFT.parts/3)
similar_from_chars: 50          # similar ideas are looked for from here
run_stale_seconds: 60           # a run still going after this has failed (the person fills the parts by hand)
latency_days: 7                 # the loader's means: the median time per part over this many days
max_message_chars: 4000
max_messages: 60
default_means_ms:
  title: 1800
  often: 900
  who: 1200
  value: 1500
  area: 700
  similar: 2600
affects:
  - label: Investors
    cues: [investor, investors, customer, customers, unitholder, unitholders, nominee, folio, redemption, sip]
  - label: KFin teams
    cues: [branch, branches, team, ops, operations, colleagues, staff, desk, "call centre", "back office"]
  - label: Distributors
    cues: [distributor, distributors, ifa, mfd, broker, brokers, arn, euin, partner]
  - label: AMC clients
    cues: [amc, amcs, "fund house", "fund houses", scheme, schemes]
  - label: Issuer and corporate clients
    cues: [issuer, issuers, company, companies, shareholder, shareholders, ipo, agm, dividend]
area:
  - label: Investor service
    cues: [investor, investors, sms, call, calls, complaint, complaints, kyc, query, queries]
  - label: Operations
    cues: [manual, "by hand", re-key, rekey, process, reconciliation, courier, form, forms, nigo]
  - label: Distributor experience
    cues: [distributor, distributors, iris, ifa, mfd, brokerage, commission]
  - label: Corporate registry
    cues: [issuer, issuers, shareholder, shareholders, ipo, agm, e-voting, dividend, registry]
  - label: Technology
    cues: [system, screen, app, portal, api, report, login, software, website]
  - label: Compliance
    cues: [sebi, amfi, circular, audit, regulation, regulatory, compliance, fatca]
  - label: Sales
    cues: [sales, sell, selling, lead, leads, prospect, prospects, pitch]
  - label: New business
    cues: [revenue, product, market, "new client", "new clients", offering, opportunity]
  - label: Distributor services
    cues: [empanelment, onboarding, arn, euin, sub-broker]
```
