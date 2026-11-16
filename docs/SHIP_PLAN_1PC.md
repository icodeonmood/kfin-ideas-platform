# Shipping the revised 1% Club (design handoff, draft 0)

Written 16 Nov 2026 by the planning session (lane E); revised the same afternoon with the product lead's answers (DEC-102 to DEC-106). Source: `1pc-handoff/` (canvas v106) and the repo mapping in `1pc-handoff/00-overview/REPO-MAPPING.md`, which links the four full reports in `1pc-handoff/00-overview/mapping/`.

## 1. Summary

The revised design replaces the product's front end and most of its review machinery. It keeps the platform underneath: the gateway, personal-data detection, file checks, speech to text, timers, email, Ones numbers and tiers, impact measurement and matching. Everything in the pack ships for the inauguration on Friday 20 November, in one cut-over, built by six lanes in parallel (DEC-105). Channels that need IT or InfoSec are built and switched off until their approvals land: Teams, email intake, email-code sign-in, streamed voice and a hosted voice for Listen. While InfoSec's model-route approval (D1) is open, the draft's parts are filled by hand.

## 2. Decisions

| ID | Decision |
|---|---|
| DEC-102 | The pack is the source of truth; earlier DECs that conflict are superseded (sorting, the canvas, pitches and scoring, appeals, Ones induction, the OFFER and tier tokens where they differ) |
| DEC-103 | Customer details are hidden, not blocked; "Show it" with a reason; the unmasked value only for the sharer (non-negotiable 4 rewritten) |
| DEC-104 | Who sees what follows `P-PRODUCT.privacy`: names, crew files and the conversation as designed; raw words only for the sharer, desk and committee (non-negotiable 7 rewritten) |
| DEC-105 | Everything by Friday; outside-approval channels built and switched off |
| DEC-106 | The retirements in section 6 |
| BLD-E001 | Links are never fetched; classified by domain only |
| BLD-E002 | Email-code sign-in behind a switch, off until InfoSec approves |
| BLD-E003 | Listen uses the browser's local voice on the masked script |
| BLD-E004 | A decision's reason is read in the app only |
| BLD-E005 | No animation library; CSS, the Web Animations API and a FLIP helper |
| BLD-E006 | The cut-over evolves `public` in place, in lane E's migration range |
| BLD-E007 | One configurable file limit (25 MB) and the wider type list |

Still needed from outside the build: the DPO's privacy notice covering names and crew files (DEC-104), HR's sign-off on launch-facing copy, the desk lead's area-to-reviewer map.

## 3. What carries over

| Engine today | Becomes | Change |
|---|---|---|
| Gateway `run_agent`, grounding (DEC-095, DEC-097) | `L-DRAFT` parts | Six part calls per message, selective re-runs, pins, receipts, a streamed run |
| `pii/` patterns, Presidio, vault | `L-HIDE` | Outcome changes from block to mask; spans with kind; "Show it" and the desk's "Hide this" |
| `attachments/` (sandbox, OCR, ClamAV) | `C-FILE`, `L-HIDE.files` | Adds blacked-out copies for PDFs and images, ZIP unpacking, locked-file refusal |
| `gatekeeper` agent | `L-HIDE` second pass | Returns spans to hide, not verdicts |
| `canvas-assist` agent | `L-DRAFT` parts | Retargeted to the six parts |
| `judge` agent, `router/match.py`, BGE-M3 | `L-SIMILAR`, `L-CREW` | Close or related, with a one-line reason |
| `attachment-digest` agent | Listen and the reviewer's file lines | Unchanged |
| `sla/` engine, calendar, `jobs/` | Every clock in `L-REVIEW`, `L-SUBMIT`, `L-QUESTIONS`, `L-COMMITTEE`, `L-DECIDE`, `L-MERGE`, `L-IMPACT` | New timer kinds; values in configuration |
| `comms/` (email, in-app, templates) | `L-NOTIFY`, `L-INBOX` | New inbox kinds; Teams switched off until IT |
| `review_items`, `refuse_own` | `L-REVIEW` | Desk states: to review, waiting on the sharer, decided |
| `review/veto.py` listing and audit | `L-COMMITTEE` | 30 days, extend to 3 months, reverse once |
| `ones/numbers.py`, `ones/tiers.py`, glow-ups, briefs | `L-ONES`, `S-ONE` | Automatic induction; new tier colours |
| `delivery_measurements` with Finance confirmation | `L-IMPACT` | Per idea, 30 and 90 days |
| OIDC with PKCE, 8-hour sessions | `L-AUTH` | Silent sign-on, intent kept on the server |
| `kill_switches`, `audit_log`, RBAC | `L-AUDIT` | Per-person flags for S1 to S3, exposure logging, a configuration store |
| Launch stage, constellation, One dashboard | `S-LAUNCH`, `S-OFFICE`, `S-ONE` | New routes and the pack's look |

## 4. Scope (DEC-105)

All 10 journeys, 25 screens, 33 components and 24 logic modules. Built and switched off until approved: Teams notifications and intake, email intake (`S-H3` shows the page, arrivals say "coming soon"), email-code sign-in, streamed voice, a hosted Listen voice. With `ai.all` off (D1 open), Tell it saves the words and offers every part to fill in by hand, which the pack draws as the failed-part state (`C-DRAFT-LOADER.failure`, `L-DRAFT.errors`); hidden-detail patterns run without AI.

If Thursday's go/no-go finds a lane short, the product lead chooses from this drop order (each item is switched off, not half-shipped): Listen; search "ask in your own words" (filters stay); the S1 to S3 alternatives (defaults stay); crew-deck and Ones-fan motion (static cards stay); `S-H4`.

## 5. Lanes and days

| Lane | Session | Builds (screens, components, logic) |
|---|---|---|
| D | kfin-ideas-platform-cf | Foundations (`tokens.css` with the OFFER names aliased, type, glass, motion), the shell (`C-SIDEBAR`, `C-PHONE-TABS`, `C-TASKBAR`), every shared component from `C-BUTTON` to `C-DROPDOWN`, `C-ONES-FAN` and `C-CREW-DECK` motion; then visual and accessibility QA of every screen against `reference/shots` |
| E | kfin-ideas-platform-29 | The cut-over migration, contracts as shared types, retirements, synthetic reseed (first, alone); then `S-06`, `S-07`, `S-09`, `S-WALL`, `S-H6`, `S-ONE`; `L-WALL`, `L-ONES`; integration and the go/no-go |
| F | new session | `S-H2`, `S-H2B`, `S-08`; `C-SHEET-TEAMUP`, `C-CREW-DECK` data, `C-SEARCH` ask; `L-TEAMUP`, `L-CREW`, `L-CONVO`, `L-MERGE.request`, `L-SEARCH` |
| C | kfin-ideas-platform-ad | `S-03`, `S-04`, `S-04B`, `S-05`, `S-06B`; `C-PROMPT`, `C-DRAFT-LOADER`, `C-DRAFT-PANEL`, `C-HIDDEN`, `C-SIMGRID`, `C-PREVIEW`; `L-DRAFT`, `L-HIDE`, `L-SORT`, `L-SIMILAR`, `L-SUBMIT`; the S1 to S3 variants |
| B | kfin-ideas-platform-67 | `S-R1`, `S-R2`, `S-R3`, `S-R4`; `C-QCARD`, `C-WORTH`, `C-SHEET-MERGE`, `C-LISTEN`; `L-REVIEW`, `L-DECIDE`, `L-QUESTIONS`, `L-COMMITTEE`, `L-WORTH`, `L-MERGE.desk`, `L-LISTEN` |
| A | kfin-ideas-platform-3b | `S-01`, `S-02`, `S-H3`, `S-H4`, `S-H5`, `S-LAUNCH`, `S-OFFICE`, the minimal admin page (build team, shipped, measurements, Finance confirmation, Founding Ones, "Take off the Wall", roles, flags); `C-INBOX-READER`; `L-AUTH`, `L-AUDIT`, `L-INBOX`, `L-NOTIFY`, `L-DISPLAY`, `L-IMPACT`, every clock; the gates, CI and the demo stack |

| When | Checkpoint |
|---|---|
| Mon 16, 20:00 | Decisions recorded; lane F started; every lane briefed. Lanes A, B, C and F build their back ends against `06-contracts`; lane D starts the foundation |
| Tue 17, 13:00 | Cut-over migration, shared types, the foundation, the shell and the core components on `main`. Old pages retired from navigation |
| Wed 18, 22:00 | Every screen built on `main`, with its `V-ACC` tests |
| Thu 19, 14:00 | Full gates green on `main` (lint, unit, e2e with axe, eval); 17:00 go/no-go with the product lead; launch-screen and office-screen rehearsal |
| Fri 20 | Inauguration. Code freeze except fixes |
| Mon 23 | Cleanup migration drops the retired tables |

Rules for every lane: your own worktree; one module per commit, pushed; module IDs in test names and commit messages (`S-R2.panel`, `V-ACC.review/1`); `REPO-MAPPING.md` updated when a module lands; deltas (`D-00NN`) applied in order by the lane that owns the module; nothing merges to `main` without lint, unit and the e2e of its journey green on GitHub CI.

## 6. Data and retirements

### 6.1 Data

Evolve the existing `public` schema in one cut-over migration, not a second schema (reasons in `mapping/contracts.md` §6). The platform spine stays. `ideas` takes the pack's status values; the new domain tables are added; the idea domain is truncated and reseeded with new synthetic people (the pack's cast is fictional and stays out of production). Retired tables are frozen for launch and dropped on Monday 23 November. Unmasked words go in a worker-only table with explicit revokes, added to the pinned privilege test.

### 6.2 Retired (DEC-106): pages go now, code and tables after launch

Appeals and "Disagree with this?"; contesting a gatekeeper block (BLD-082); redirects and "not an idea"; the post-submit choice step and +1; clusters and the weekly batch; qualify; scoring rounds, pre-scores and conflict flags; presentations, assessments, collation, decision sheets and working groups; the five-working-day veto (rebuilt as the 30-day window); handover, sponsor, milestones, check-ins and solution write-ups (measurements kept); lenses and the manager view; learning loops; fairness and calibration reports; the canvas, strength meter, quick and full modes; category and play; pausing the clock for questions and auto-withdrawal; points rule keys tied to the old funnel (the ledger stays); the `SUB-` twin ID; deleting drafts at 30 days (they are archived instead); seven agents (cluster-summary, collation, prescore, pitch-prep, reason-writer, handover-draft, role-themes) with their golden sets; fourteen kill switches for retired features.

### 6.3 The five that something still depended on

| Item | What it is today | Call |
|---|---|---|
| Company repo writer and outbox | Every idea, cluster, decision and appeal is also written as a Markdown file into the second Git repo (`kfin-ideas`); the search index and some pages read from it; rules, taxonomy and message templates live there as files | Stop writing ideas, clusters, decisions and appeals. Keep `rules/`, `taxonomy/` and `comms/` as read-only configuration the programme team changes without a release. Search and pages read the database |
| Spam and abuse hold | A reviewer can hold a suspicious idea; a second reviewer must confirm before anything happens to it | Retire the hold. The Wall shows a short summary the moment an idea is shared, and with AI off that summary is what the person typed, so one audit-logged action stays: "Take off the Wall", for the desk and admins, from the admin page |
| Committee-only visibility | The desk could mark an idea as committee-only, hiding it from the Wall and from matching | Retire. Every shared summary is visible to employees (`L-AUDIT.permissions`); "Take off the Wall" covers sensitive cases |
| Ones console proposals | The committee proposes a One, the chair approves and an admin carries it out; sponsor slots, legend numbers, awards and peer-message invites | Retire the proposal flow, sponsor slots, legend numbers and awards. Ones are inducted automatically on measured, confirmed impact (`L-ONES.rules/1`). Numbers, tiers, glow-ups, briefs and the Showcase brief stay, plus an admin path to mark Founding Ones and to remove a One, both logged |
| Reviewer identity reveal | Reviewers saw a staff code instead of the sharer's name; an admin could reveal it with a logged reason | Retire with DEC-104: the desk sees the name. A reviewer still never reviews their own idea, and any other reviewer takes it |

## 7. Gates

Old specs for retired pages are deleted with the pages (about 50 routes; the lists are in `mapping/screens.md` §3). New tests carry the module ID. Friday needs every `V-ACC` journey, `V-FIELDS`, axe on every screen, the log scrubber, the no-SDK rule, the decision-ID check and the pinned privilege test green on `main`. The e2e `signIn()` helper drives single sign-on, so that route keeps working throughout.

## 8. Outside dependencies

| Who | What | Needed by | If it does not come |
|---|---|---|---|
| InfoSec | Model route (D1) | Friday for AI drafting | Parts filled by hand; AI switched on later without a release |
| DPO, Legal | Privacy notice covering names, crew files and the conversation (DEC-104) | Friday | Go/no-go shows Mode C until it is live |
| HR | Launch-facing copy (`reference/copy`) and message templates | Thursday | The pack's copy as written |
| Review desk lead | Area-to-reviewer map (`L-SORT.rules/7`) | Thursday | Any reviewer, never the sharer |
| IT | Teams app, the 1% Club mailbox, Graph permissions | After launch | In-app and email only |
| InfoSec | Email-code sign-in | After launch | Single sign-on only |
| IT, InfoSec, DPO | Speech service and voice | After launch | Typing only; the mic says "coming soon" |

## 9. Risks

1. Scope. Six lanes, three and a half days, about 17 new components and a new draft engine. Lanes run their own subagents in worktrees; lane E watches the checkpoints and raises a slip at once with the drop order in section 4.
2. The cut-over touches everything. It lands by Tuesday 13:00 or the screens build on sand; lane E does nothing else until it is in.
3. Privacy notice. The new visibility needs the DPO's notice before Friday.
4. AI off. If D1 does not land, the product works but the draft is manual; the copy already covers it.
5. The 4 GB Colima VM cannot run several stacks. Lanes test on GitHub CI; only lane A runs the demo stack.
