---
id: P-REPO
title: Where each module lands in the repo
rev: 1
status: baseline
source: none
depends_on: []
last_delta: none
---

# Repo mapping

Filled in on 16 Nov 2026 by lane E (the planning session) from a read of `main` at e911de1. The full evidence, with file paths, reusable pieces and the old rules that must not carry over, is in four reports beside this file:

| Report | Covers |
|---|---|
| `mapping/screens.md` | Every `S-` screen and the shell (`C-SIDEBAR`, `C-PHONE-TABS`, `C-TASKBAR`); routes the pack does not describe; tests that die |
| `mapping/components.md` | Foundations and tokens; every other `C-` component; accessibility |
| `mapping/logic.md` | Every `L-` module; the non-negotiable check; the retire list (R1 to R28); new infrastructure |
| `mapping/contracts.md` | `E-ENTITIES`, `E-ENUMS`, `A-API`, `V-FIELDS`; retired tables and endpoints; the migration approach |

The shipping plan built on this mapping is `docs/SHIP_PLAN_1PC.md`. **Phase** is the cut in that plan (P0 Friday 20 Nov, P1 by Wednesday 25 Nov, P2 after outside approvals). **Lane** is who builds it. Update a row when its module lands.

## `P-REPO.screens`

| ID | Pack route | Closest today | State | Effort | Phase | Lane |
|---|---|---|---|---|---|---|
| `S-01` | `/` signed out | none (`proxy.ts` sends signed-out visitors to `/sign-in`) | missing | M | P0 | A |
| `S-02` | `/sign-in` | `app/sign-in`, `app/auth/{login,callback,logout}` | exists, differs | L | P0 (single sign-on), P2 (email code) | A |
| `S-03` | `/home` | `app/page.tsx` (signed-in home) | exists, differs | L | P0 | C |
| `S-04` | `/share` | `app/share/page.tsx`, `share/start.tsx` | exists, differs | L | P0 | C |
| `S-04B` | `/share/:draftId` | `app/share/[id]/canvas-form.tsx` | exists, differs | L | P0 | C |
| `S-05` | `/share/:draftId/check` | `app/share/[id]/done/*` (checks after submit today) | exists, differs | L | P0 | C |
| `S-06` | `/ideas/:id` (sharer) | `app/ideas/[id]` | exists, differs | L | P0 | E |
| `S-06B` | `/ideas/:id/edit` | none | missing | M | P0 | C |
| `S-07` | `/my-ideas` | `app/my-ideas` | exists, differs | M | P0 | E |
| `S-08` | `/ideas/:id/conversation` | none | missing | L | P1 | B |
| `S-09` | `/ideas/:id` (others) | `app/ideas/[id]` | exists, differs | M | P0 (team up P1) | E |
| `S-WALL` | `/wall` | `app/wall` | exists, differs | M to L | P0 | E |
| `S-ONE` | `/one` | `app/my-ideas/one-dashboard.tsx`, `glow-up.tsx` | exists, differs | S to M | P0 | E |
| `S-R1` | `/desk` | `app/review` | exists, differs | M to L | P0 | B |
| `S-R2` | `/desk/ideas/:id` | `app/review/[id]` | exists, differs | L | P0 (decide), P1 (ask, worth, merge, Listen) | B |
| `S-R3` | `/ideas/:id/answer` | none | missing | M to L | P1 | B |
| `S-R4` | `/committee` | `app/committee` (scoring rounds); closest behaviour is `app/desk-decisions` (veto) | exists, differs | L | P1 | B |
| `S-H2` | `/crew` | none (`crew.tsx` fragments) | missing | L | P1 | E |
| `S-H2B` | `/inbox/:itemId` | none | missing | M to L | P1 | E |
| `S-H3` | `/share/other-ways` | none | missing | M | P1 (page), P2 (arrivals) | A |
| `S-H4` | `/how-it-works` | `app/journey` | exists, differs | S | P1 | A |
| `S-H5` | `/inbox` | `app/inbox` | exists, differs | L | P0 | A |
| `S-H6` | `/profile` | none; pieces on `/my-ideas` (`points.tsx`, `name-on-wall.tsx`) | exists, differs | M | P0 | E |
| `S-OFFICE` | `/display/office` | `app/constellation` (`sky.tsx`) | exists, differs | M | P0 | A |
| `S-LAUNCH` | `/display/launch` | `app/launch/stage.tsx` (admin only today) | exists, differs | S | P0 | A |

## `P-REPO.components`

| ID | State | Effort | Phase | Lane |
|---|---|---|---|---|
| `C-SIDEBAR` | exists, differs | M to L | P0 | D |
| `C-PHONE-TABS` | missing | M | P0 | D |
| `C-TASKBAR` | missing | S to M | P0 | D |
| `C-BUTTON` | exists, differs (26 files use the old `.button`) | M | P0 | D |
| `C-CHIP` | exists, differs | M | P0 | D |
| `C-PILL` | missing | S | P0 | D |
| `C-FIELD`, `C-FIELD-MSG` | exists, differs | S | P0 | D |
| `C-CARD` | exists, differs (no glass today) | M | P0 | D |
| `C-AVATAR` | missing | S | P0 | D |
| `C-SKELETON` | missing | S | P0 | D |
| `C-EMPTY` | exists, differs | S | P0 | D |
| `C-SORTS` | missing | S | P0 | D |
| `C-TABS` | missing | S to M | P0 | D |
| `C-SEARCH` | missing | M | P0 (filters), P1 (ask) | D |
| `C-TRACK` | missing | S to M | P0 | D |
| `C-FILE` | exists, differs (keep the quarantine and scan logic in `attachments.tsx`) | M | P0 | D (UI), C (wiring) |
| `C-DROPDOWN` | missing | S | P1 | D |
| `C-PROMPT` | exists, differs | L | P0 | C |
| `C-DRAFT-LOADER` | missing | M | P0 | C |
| `C-DRAFT-PANEL` | missing | L | P0 | C |
| `C-HIDDEN` | exists, differs | M | P0 | C |
| `C-SIMGRID` | exists, differs | M | P0 | C |
| `C-PREVIEW` | missing | M | P0 | C |
| `C-WORTH` | exists, differs | M | P0 (view), P1 (revise) | C, B |
| `C-QCARD` | missing | M | P1 | B |
| `C-INBOX-READER` | exists, differs | L | P0 | A |
| `C-LISTEN` | missing | M | P1 | B |
| `C-SHEET-MERGE` | missing | M | P1 | B |
| `C-SHEET-TEAMUP` | exists, differs | M | P1 | E |
| `C-CREW-DECK` | exists, differs | L | P1 | D (motion), E (data) |
| `C-ONES-FAN` | exists, differs | M to L | P0 (static), P1 (motion) | D |

## `P-REPO.logic`

| ID | Owner today | State | Phase | Lane |
|---|---|---|---|---|
| `L-AUDIT` | `policy/rbac.yaml`, `proxy.ts`, `audit_log`, `core/killswitch.py`, `server/killswitch.ts` | exists, differs | P0 | A |
| `L-AUTH` | `server/auth/*`, `app/auth/*`, `identity/*` | exists, differs | P0 (single sign-on), P2 (email code) | A |
| `L-DRAFT` | `gateway/run_agent`, `gateway/grounding.py`, `agents/canvas-assist` | exists, differs | P0 | C |
| `L-HIDE` | `pii/*`, `agents/gatekeeper`, `attachments/*` | exists, differs | P0 | C |
| `L-SORT` | `ideas.area`, taxonomy | exists, differs | P0 | C |
| `L-SIMILAR` | `router/match.py`, `agents/judge`, embeddings | exists, differs | P0 | C |
| `L-SUBMIT` | `server/submissions.ts`, `scan/save.py` | exists, differs | P0 | C |
| `L-REVIEW` | `review/service.py`, `review_items` | exists, differs | P0 | B |
| `L-DECIDE` | `review/service.py` (tags and groups today) | exists, differs | P0 | B |
| `L-INBOX` | `notifications`, `comms/inbox.py` | exists, differs | P0 | A |
| `L-NOTIFY` | `comms/*` | exists, differs | P0 (email, in-app), P2 (Teams) | A |
| `L-WALL` | `views/wall.py` | exists, differs | P0 | E |
| `L-ONES` | `ones/*` | exists, differs | P0 | E |
| `L-IMPACT` | `delivery_measurements`, `delivery/service.py` | exists, differs | P0 (admin entry) | A |
| `L-DISPLAY` | `app/launch`, `app/constellation` | exists, differs | P0 | A |
| `L-QUESTIONS` | `idea_questions`, SLA `needs_info` | exists, differs | P1 | B |
| `L-COMMITTEE` | `review/veto.py` (5-day veto) | exists, differs | P1 | B |
| `L-CONVO` | none | missing | P1 | B |
| `L-WORTH` | impact estimates (qualify) | exists, differs | P1 | B |
| `L-MERGE` | `idea_links` | exists, differs | P1 | B (desk), C (request) |
| `L-TEAMUP` | `idea_links` (`plus_one`, team-up at scan) | exists, differs | P1 | E |
| `L-CREW` | none | missing | P1 | E |
| `L-SEARCH` | `chunks`, `tsv`, BGE-M3 | missing | P0 (filters), P1 (ask) | E |
| `L-LISTEN` | none | missing | P1 | B |

## `P-REPO.contracts`

| ID | Schema or contract | Differences |
|---|---|---|
| `E-ENTITIES` | `db/migrations/*.sql`, `apps/web/src/server/db-types.ts` (stale: 31 of 72 tables) | About 30 new tables; `ideas` re-purposed; `decisions` today is a cluster vote. Full list: `mapping/contracts.md` §1 |
| `E-ENUMS` | `ideas.stage` CHECK (28 values), `role_grants.role`, `attachments.state`, `notifications.event` | About 12 old stages have no new home; `withdrawn`, `merged` and `picked` change meaning. Mapping: `mapping/contracts.md` §2 |
| `A-API` | `apps/web/src/app/api/**` | Most endpoints new or reshaped; about 50 routes retire. `mapping/contracts.md` §3 |
| `V-FIELDS` | zod schemas, Python validators, DB checks | 30-character minimum (50 today), one configurable file limit (25 MB), note lengths 30 and 20. `mapping/contracts.md` §4 |

Approach: one cut-over migration in lane E's range (`202611215xxxxx`, sorting after lane C's `20261121300110`), evolving `public` in place; synthetic reseed; retired tables dropped after launch.

## `P-REPO.tokens`

`01-foundations/tokens.css` is imported as-is into `apps/web/src/app/`, and the OFFER names in `offer.css` become aliases of the pack's tokens, so existing call sites keep working while screens move over. Fonts stay self-hosted through `@fontsource-variable` (BLD-D008); `--fd` and `--ft` are overridden because the pack names "Inter" and the installed family is "Inter Variable". Tier colours change in `services/worker/ones/tiers.py`, the emails and `docs/BRAND.md` too. Detail: `mapping/components.md` §1.

## `P-REPO.not-in-pack`

What the repo has that the pack does not describe, and what happens to it, is the retire list in `mapping/logic.md` §3 and `mapping/contracts.md` §5, summarised in `docs/SHIP_PLAN_1PC.md` §6.
