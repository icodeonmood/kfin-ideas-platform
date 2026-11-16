# Shipping the revised 1% Club (design handoff, draft 0)

Written 16 Nov 2026, 15:30 IST, by the planning session (lane E). Source: `1pc-handoff/` (canvas v106) and the repo mapping in `1pc-handoff/00-overview/REPO-MAPPING.md`, which links the four full reports in `1pc-handoff/00-overview/mapping/`.

## 1. Summary

The revised design replaces the product's front end and most of its review machinery. It keeps the platform underneath: the gateway, personal-data detection, file checks, speech to text, timers, email, Ones numbers and tiers, impact measurement and matching. We ship it in one cut-over this week. On Friday 20 November the share journey, the idea page, My ideas, the Wall, the review desk's decide path and the launch and office screens are live. The questions loop, the conversation, the Ones Committee window and team-up follow by Wednesday 25 November, before the first decisions fall due. Channels that need IT or InfoSec (Teams, email intake, email-code sign-in, streamed voice, a hosted voice for Listen) wait for their approvals and are switched off until then.

Three of the repo's non-negotiables collide with the pack and need the product lead's call before that part is built. Everything else in this plan proceeds now.

## 2. Decisions for the product lead

| # | Question | Pack | Repo today | Recommended |
|---|---|---|---|---|
| Q1 | Customer details | Hidden automatically; the sharer's own box keeps their words; "Show it" with one of three reasons, logged (`L-HIDE.rules`) | Non-negotiable 4: blocked at submission, pattern blocks absolute; a contest goes to the desk (BLD-082) | Adopt the pack. The masked copy is the only copy any other person, service or log receives, which keeps non-negotiable 2 intact. The unmasked value lives encrypted in a worker-only table, readable by the sharer alone |
| Q2 | Names, files and conversation | The sharer's name shows on their idea, the Wall (unless they hide it in Profile), crew cards and requests; crew see checked files and the conversation | Non-negotiable 7: submitters never see another person's raw text, files or name | Adopt the pack for names, files and the conversation. Raw words stay with the sharer, the desk and the committee, as the pack's own privacy table says (`P-PRODUCT.privacy`); previews show the short summary, never raw words |
| Q3 | Friday scope | All 25 screens | n/a | The cut in section 4: P0 on Friday, P1 by Wednesday 25 November, P2 after approvals |
| Q4 | Back-end retirements that something still depends on | No place in the pack | Built | The defaults in section 6.3 |

Decided here under CLAUDE.md "How to work" step 3 (the simpler reading that keeps every non-negotiable), recorded as build decisions:

1. **Links are never fetched (non-negotiable 8 stands).** Links are classified internal or external by domain only. The "couldn't open this link" state is not used; the desk opens links themselves.
2. **Email-code sign-in is built behind a switch, off at launch.** Single sign-on only on Friday; the email route goes live when InfoSec approves it (it changes the identity model).
3. **Listen uses the reviewer's browser voice, on the device.** The script is the masked idea; no hosted text-to-speech provider sees it. A hosted voice waits for InfoSec (`L-LISTEN/6`).
4. **Voice stays as DEC-096 built it** (record, scan, then transcribe on KFin's own speech service, switch off until IT, InfoSec and the DPO approve). Words appearing live while speaking (`L-DRAFT.voice/2`) waits for the same approvals plus per-chunk scanning.
5. **A decision's reason is read in the app only.** `L-DECIDE.rules/3` and `L-NOTIFY/3` disagree; we follow `L-NOTIFY/3`.
6. **The look follows the pack** (tokens, glass inside the signed-in shell, the conditioned blue and spark, the new tier colours, 12/20/28 radii). This supersedes DEC-101 and DEC-098 where they differ; the fonts stay self-hosted. Recorded as a DEC because it reverses a product decision.
7. **No animation library.** The pack's `motion.css` is plain CSS; the rest uses the Web Animations API and a small FLIP helper, the pack's own fallback (`F-MOTION`). Nothing goes to Legal.
8. **Ones are inducted automatically** once a shipped idea's difference is measured and confirmed (`L-ONES.rules/1`). An admin path stays for Founding Ones and removal.

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
| `sla/` engine, calendar, `jobs/` | Every clock in `L-REVIEW`, `L-SUBMIT`, `L-QUESTIONS`, `L-COMMITTEE`, `L-DECIDE`, `L-IMPACT` | New timer kinds; values in configuration |
| `comms/` (email, in-app, templates) | `L-NOTIFY`, `L-INBOX` | New inbox kinds; Teams later |
| `review_items`, `refuse_own` | `L-REVIEW` | Desk states: to review, waiting on the sharer, decided |
| `ones/numbers.py`, `ones/tiers.py`, glow-ups, briefs | `L-ONES`, `S-ONE` | Automatic induction; new tier colours |
| `delivery_measurements` with Finance confirmation | `L-IMPACT` | Per idea, 30 and 90 days |
| OIDC with PKCE, 8-hour sessions | `L-AUTH` | Silent sign-on, intent kept on the server |
| `kill_switches`, `audit_log`, RBAC | `L-AUDIT` | Adds per-person flags for S1 to S3, a configuration store |
| Launch stage, office screen, One dashboard | `S-LAUNCH`, `S-OFFICE`, `S-ONE` | New routes and the pack's look |

## 4. The cut

**P0, live at the inauguration on Friday 20 November**

| Journey | In P0 | Held back |
|---|---|---|
| `J-SHARE` | Landing, sign in (single sign-on), Home's prompt, Tell it with the live draft (parts by hand when AI is off), Check it with sorting, similar ideas (Preview, Keep mine separate), proof, fix, who would help, Submit, the idea page "Just shared" | Team up from Check it (P1) |
| `J-RESUME` | Drafts saved within 2 seconds, on any device, "Carry on" | Email and Teams arrivals (P2) |
| `J-RECOVER` | Sign-in failures, offline saving, send failures, file failures, hidden-detail "Show it" | Merge-request waits (P1) |
| `J-TRACK` | Idea page with stage track, edit and withdraw window, decision and reason, Inbox, My ideas, restore | Answer screen and questions (P1); the desk's "Ask first" stays folded away until then |
| `J-REVIEW` | Review desk, the idea for the reviewer, decide with reason | Ask first, revise worth, merge, Listen (P1) |
| `J-BROWSE` | My ideas, Wall, a colleague's idea, list state in the URL | Search "ask in your own words" (P1) |
| `J-ONE` | The Ones on the Wall, Home and the office screen; the One dashboard at `/one`; the launch screen | Posts by Ones (P1) |
| `J-TEAMUP`, `J-SIMILAR`, `J-COMMITTEE` | Not in P0 | P1 |

AI-off fallback: InfoSec has not approved the model route (D1). With `ai.all` off, Tell it saves the words and offers every part for the person to fill in, which the pack already draws as the failed-part state (`C-DRAFT-LOADER.failure`, `L-DRAFT.errors`). Hidden-detail patterns run without AI.

**P1, by Wednesday 25 November:** Answer and questions (`S-R3`, `L-QUESTIONS`), the conversation (`S-08`, `L-CONVO`), the Ones Committee (`S-R4`, `L-COMMITTEE`), Find your crew and team-up (`S-H2`, `S-H2B`, `C-SHEET-TEAMUP`, `L-TEAMUP`, `L-CREW`), merge requests and desk merges (`L-MERGE`), worth revision (`C-WORTH`, `L-WORTH`), What happens after you share (`S-H4`), Share another way as a page (`S-H3`, arrivals switched off), Listen, search, the S1 to S3 flags with exposure logging, product metrics, idempotent offline submit.

**P2, after approvals:** Teams notifications and intake, email intake (IT); email-code sign-in (InfoSec); streamed voice and a hosted Listen voice (IT, InfoSec, DPO); row-level security on the new private tables; redaction inside Office files (until then a detail found in a Word, Excel or PowerPoint file asks the person to remove it and add the file again).

## 5. Lanes and days

Lane E is new: this planning session, registered in `docs/DECISIONS.md`, migrations `202611215xxxxx` (they must sort after lane C's `20261121300110`).

| Lane | Session | P0 work | P1 work |
|---|---|---|---|
| D | kfin-ideas-platform-cf | `tokens.css` imported with the old names aliased; type, glass and motion primitives; the shell (`C-SIDEBAR`, `C-PHONE-TABS`, `C-TASKBAR`); core components `C-BUTTON` to `C-FILE`; then visual and accessibility QA of every screen against `reference/shots` | `C-ONES-FAN`, `C-CREW-DECK`, motion polish |
| E | kfin-ideas-platform-29 | The cut-over migration, contracts as shared types, retirements, synthetic reseed; then the idea page, My ideas, a colleague's idea, the Wall, Profile, the One dashboard (`S-06`, `S-07`, `S-09`, `S-WALL`, `S-H6`, `S-ONE`, `L-WALL`) | Team-up and crew (`S-H2`, `S-H2B`, `L-TEAMUP`, `L-CREW`), search |
| C | kfin-ideas-platform-ad | Home, Tell it, Check it, Edit (`S-03`, `S-04`, `S-04B`, `S-05`, `S-06B`); `L-DRAFT`, `L-HIDE`, `L-SORT`, `L-SIMILAR`, `L-SUBMIT` | Merge requests from Check it (`L-MERGE.request`), the S1 to S3 flags |
| B | kfin-ideas-platform-67 | Review desk and the reviewer's idea, decide path (`S-R1`, `S-R2`, `L-REVIEW`, `L-DECIDE`) | Questions and Answer, the committee, the conversation, worth, desk merges, Listen |
| A | kfin-ideas-platform-3b | Landing and sign in with kept intent (`S-01`, `S-02`, `L-AUTH`); roles, audit, switches and configuration (`L-AUDIT`); Inbox and notifications (`S-H5`, `L-INBOX`, `L-NOTIFY`); the clocks; launch and office screens (`S-LAUNCH`, `S-OFFICE`, `L-DISPLAY`); the minimal admin page (team, shipped, measurements); the gates, CI and the demo stack | `S-H3`, `S-H4`, metrics |

| When | Checkpoint |
|---|---|
| Mon 16, 19:00 | Decisions recorded; lane E registered; this plan and the mapping on `main`; every lane briefed |
| Tue 17, 13:00 | Cut-over migration, shared types and the foundation and shell on `main`. Lanes B, C and A build their back ends against `06-contracts` until then. This replaces Tuesday's go/no-go with a checkpoint |
| Wed 18, 18:00 | P0 screens complete on `main`; the P0 acceptance tests (`V-ACC`) written |
| Thu 19, 12:00 | Full gates green on `main` (lint, unit, e2e with axe, eval); go/no-go. 15:00: rehearsal of the launch screen and the office screen |
| Fri 20 | Inauguration. Code freeze except fixes |
| Mon 23 to Wed 25 | P1, then the cleanup migration that drops retired tables |

Rules for every lane: work in your own worktree; one module per commit, pushed; module IDs in test names and commit messages (`S-R2.panel`, `V-ACC.review/1`); `REPO-MAPPING.md` updated when a screen, component or service lands; deltas (`D-00NN`) applied in order by the lane that owns the module.

## 6. Data and retirements

### 6.1 Data

Evolve the existing `public` schema in one cut-over migration, not a second schema (reasons in `mapping/contracts.md` §6). The platform spine stays. `ideas` takes the pack's status values; the new domain tables are added; the idea domain is truncated and reseeded with new synthetic people (the pack's cast is fictional and stays out of production). Retired tables are frozen for launch and dropped in a cleanup migration after 20 November. Unmasked words go in a worker-only table with explicit revokes, added to the pinned privilege test.

### 6.2 Retired now (switched off, routes and navigation removed in the cut-over; code and tables deleted after launch)

Appeals and "Disagree with this?"; contesting a gatekeeper block (BLD-082); redirects and "not an idea"; the post-submit choice step and +1; clusters and the weekly batch; qualify; scoring rounds, pre-scores and conflict flags; presentations, assessments, collation, decision sheets and working groups; the five-working-day veto (rebuilt as the 30-day window); handover, sponsor, milestones, check-ins and solution write-ups (measurements kept); lenses and the manager view; learning loops; fairness and calibration reports; the canvas, strength meter, quick and full modes; category and play; pausing the clock for questions and auto-withdrawal; points rule keys tied to the old funnel (the ledger stays); the `SUB-` twin ID; deleting drafts at 30 days (they are archived instead); seven agents (cluster-summary, collation, prescore, pitch-prep, reason-writer, handover-draft, role-themes) with their golden sets; fourteen kill switches for retired features. Front-end pages for all of these go without further notice.

### 6.3 Retired with a default the product lead confirms (Q4)

| Item | Default |
|---|---|
| Company repo writer, outbox, OKF bundle | Stop writing ideas, decisions and appeals to the repo. Keep the seeded `rules/`, `taxonomy/` and `comms/` as read-only configuration until a database configuration store lands. CLAUDE.md's "two repos" section is updated to match |
| Spam and abuse hold | Retire the hold and its second reviewer. Keep one admin action, "Take off the Wall", audit-logged, with no new screen |
| Committee-only visibility | Retire; every shared idea's summary is visible to employees (`L-AUDIT.permissions`) |
| Ones console proposals, sponsor slots, legend numbers, awards | Retire the proposal flow. Keep numbers, tiers, glow-ups, briefs and the Showcase brief; keep an admin path for Founding Ones and removal |
| Identity reveal for reviewers | Retire with Q2: the desk sees the sharer's name |

## 7. Gates

Old specs for retired pages are deleted with the pages (about 50 routes; the lists are in `mapping/screens.md` §3). New tests carry the module ID. P0 must pass `V-ACC.share`, `V-ACC.track` (P0 parts), `V-ACC.review` (main path), `V-ACC.browse`, `V-ACC.recover`, `V-FIELDS`, axe on every screen, the log scrubber, the no-SDK rule and the decision-ID check. The e2e `signIn()` helper drives single sign-on, so that route keeps working throughout.

## 8. Outside dependencies

| Who | What | Needed by | If it does not come |
|---|---|---|---|
| InfoSec | Model route (D1) | Friday for AI drafting | Parts filled by hand; AI switched on later without a release |
| IT | Teams app, the 1% Club mailbox, Graph permissions | P2 | In-app and email only |
| InfoSec | Email-code sign-in | P2 | Single sign-on only |
| IT, InfoSec, DPO | Speech service and voice | P2 | Typing only; the mic says "coming soon" |
| Legal, DPO | Privacy notice covering the new visibility (names, crew files) | Friday | Go/no-go shows Mode C until it is live |
| HR | Launch-facing wording in `reference/copy` | Thursday | The pack's copy as written |
| Review desk lead | Area-to-reviewer map | Thursday | Any reviewer, never the sharer |

## 9. Risks

1. Scope. Four lanes, three and a half days, about 17 new components and a new draft engine. If a lane slips by half a day, cut in this order: the desk's merge preview, the Ones fan and crew-deck motion, Home's crew cards, S-H4, then similar ideas on Check it (matching still runs for the desk).
2. The cut-over touches everything. It lands by Tuesday 13:00 or the screens build on sand; lane E does nothing else until it is in.
3. Privacy notice. The new visibility (names, crew files) needs the DPO's notice before Friday.
4. AI off. If D1 does not land, the product works but the draft is manual; the copy already covers it.
