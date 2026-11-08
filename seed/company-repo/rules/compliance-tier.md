---
type: rule
title: Garage compliance tiers
description: Standard versus express tier for handover and the regulatory gate, taken from the Garage handoff contract.
tags:
- rules
- compliance
- garage
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: RULE-compliance-tier
  version: '1.0'
  approver: null
  inherited_from: Product-Manager-Skills/config/schemas/handoff.schema.yaml (compliance-tier) and docs/plans/garage-whitepaper.md §4, §10 @ b7138ec on 2026-11-08
---

<!-- inherited-from: Product-Manager-Skills/config/schemas/handoff.schema.yaml (compliance-tier) and Product-Manager-Skills/docs/plans/garage-whitepaper.md §4, §10 @ b7138ec on 2026-11-08; do not edit by hand, re-run the inheritance step -->

The Garage project owns these rules (`docs/GARAGE_INHERITANCE.md`, item 4). The tier is declared by the Garage PM in `handoff.md` and reviewed at every pipeline run; the platform only proposes it in the handover pack.

**Standard** if the work touches transaction flows, investor data, regulated APIs, AMC integrations, a SEBI, PFRDA or RBI surface, or any regulated product (LAMF, NPS, SIF, IRIS transaction flows). Internal tooling that reads a regulated data surface is **always** standard. Standard defaults to gated mode.
**Express** for UI changes, content, internal tooling, skills, agents and automation on a non-regulated surface. Express defaults to autonomous mode, but PM sign-off at QA is always required.

The two `platform_` keys are the Ideas Platform's own triggers for the regulatory gate in qualify (ARCHITECTURE §4.5). They only ever make an item **more** cautious.

```yaml
version: '1.0'
source: garage:config/schemas/handoff.schema.yaml@b7138ec
standard_if_any:
- touches_transaction_flow
- touches_investor_data
- uses_regulated_api
- touches_amc_integration
- touches_regulator_surface
- regulated_product
- touches_iris_transaction_surface
- internal_tool_reads_regulated_data
regulated_products:
- lamf
- nps
- sif
- iris_transaction_flows
regulator_surfaces:
- sebi
- pfrda
- rbi
express_if_only:
- ui_change
- content
- internal_tooling
- skills_agents_automation
- non_regulated_surface
platform_standard_if_any:
- area_tag:AREA-compliance
- submitter_named_regulatory_risk
otherwise: express
default_mode:
  standard: gated
  express: autonomous
tier_review: every_pipeline_run
compliance_reviewer_limit_wd: 5
outcomes:
- clear
- clear_with_conditions
- conflict
```
