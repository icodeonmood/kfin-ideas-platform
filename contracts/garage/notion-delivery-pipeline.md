<!-- inherited-from: Product-Manager-Skills/.claude/agents/notion-setup-agent.md and Product-Manager-Skills/.claude/agents/notion-sync-agent.md @ b7138ec on 2026-11-08; do not edit by hand, re-run the inheritance step -->

# Garage Delivery Pipeline — Notion properties

The Garage's Notion database **"Garage Delivery Pipeline"** (17 properties). Names, types and allowed values are copied exactly from the Garage's `notion-setup-agent`. The lookup key is `feature-slug`. Notion is the Garage's tracking layer, not its control plane: the source of truth for pipeline state is `delivery/<feature-slug>/status.md` in the Garage's Product Agent OS.

## Properties

| # | Field | Notion type | Values / Notes |
|---|---|---|---|
| 1 | `feature-name` | Title | Primary display field |
| 2 | `feature-slug` | Rich Text | Kebab-case · unique lookup key |
| 3 | `product` | Select | iris · lamf · guardian · api-marketplace · ai-tooling · sif-aif-pms · mf-central · other |
| 4 | `feature-type` | Select | ai-tooling · kfintech-product |
| 5 | `mode` | Select | gated · autonomous |
| 6 | `compliance-tier` | Select | standard · express |
| 7 | `current-phase` | Select | 01-discover · 02-shape · 03-gate · 04-handoff · 05-build · 06-test · 07-review · 08-qa · 09-deploy · shipped · handed-off |
| 8 | `gate-status` | Select | clear · blocked |
| 9 | `open-blockers` | Number | Count of blocking entries from status.md |
| 10 | `build-mode` | Select | full · delta |
| 11 | `spec-version` | Rich Text | e.g. "1.0" |
| 12 | `pipeline-started` | Date | Phase 04 start timestamp |
| 13 | `last-updated` | Date | Updated on every sync event |
| 14 | `shipped-date` | Date | Set only when current-phase = shipped |
| 15 | `skills-used` | Multi-select | Flattened unique list from audit.md |
| 16 | `mcps-used` | Multi-select | Flattened unique list from audit.md |
| 17 | `tools-used` | Multi-select | Flattened unique list from audit.md |

## How the Garage writes these properties (event map, from `notion-sync-agent`)

| Event | Fired by | Notion action | Fields written |
|---|---|---|---|
| `spec-approved` | Phase 03 | CREATE (or UPDATE if slug exists) | feature-name · feature-slug · product · feature-type · mode · compliance-tier · build-mode · spec-version · current-phase=03-gate · gate-status=clear · last-updated |
| `in-build` | Phase 04 | UPDATE | current-phase=04-handoff · pipeline-started · gate-status=clear · last-updated |
| `delta-review` | Phase 04 (v2.0+ only) | UPDATE | current-phase=04-handoff · gate-status=blocked · last-updated |
| `gate-approved` | Phase 07, 08 | UPDATE | current-phase · gate-status=clear · open-blockers · last-updated |
| `gate-blocked` | Phase 07, 08 | UPDATE | gate-status=blocked · open-blockers · last-updated |
| `audit-sync` | End of each phase | UPDATE | skills-used · mcps-used · tools-used (flattened unique union from all audit.md entries) · last-updated |
| `shipped` | Phase 09 | UPDATE | current-phase=shipped · shipped-date · gate-status=clear · last-updated |

Page lookup on the first call (`spec-approved`): query the database by `feature-slug`. Match found → UPDATE that page and store its page ID in `status.md`. No match → CREATE. All later calls use the stored page ID.

## Not in the Garage schema (Ideas Platform addition)

| Field | Notion type | Notes |
|---|---|---|
| `source-cluster` | Rich Text | `CL-NNNN`. Needed by `garage.sync` (ARCHITECTURE §4.8–4.9). A one-time change to the Garage database, owned by the product lead (§9.1, week 4). The Garage's `notion-setup-agent` lists 17 properties, so it must add this as property 18 or a fresh setup will lack it. Recorded in `docs/DECISIONS.md` (BLD-012). |
