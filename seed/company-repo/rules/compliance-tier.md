---
type: rule
title: Garage compliance tiers (draft until copied from the Garage)
description: Standard versus express tier for handover and the regulatory gate. Replace with the Garage project's own rules during inheritance.
tags:
- rules
- compliance
- garage
status: draft
verified: unverified
generated:
  by: human:product-team-draft
  at: '2026-11-08'
kfin:
  id: RULE-compliance-tier
  version: '1.0'
  approver: null
---

**Draft.** The Garage project owns these rules. During the inheritance step (`docs/GARAGE_INHERITANCE.md`, item 4) replace the YAML below with the Garage's version, keeping this shape, and record the source.
Until then: anything that touches transaction flows, investor data, regulated APIs or an IRIS transaction surface is **standard**; so is internal tooling that reads regulated data. Everything else is **express**.

```yaml
version: '0.1'
source: architecture-draft
standard_if_any:
- touches_transaction_flow
- touches_investor_data
- uses_regulated_api
- touches_iris_transaction_surface
- internal_tool_reads_regulated_data
- area_tag:AREA-compliance
- submitter_named_regulatory_risk
otherwise: express
compliance_reviewer_limit_wd: 5
outcomes:
- clear
- clear_with_conditions
- conflict
```
