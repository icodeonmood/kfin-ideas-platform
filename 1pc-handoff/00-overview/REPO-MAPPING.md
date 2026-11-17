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

The shipping plan built on this mapping is `docs/SHIP_PLAN_1PC.md`. **Phase**: since DEC-105 everything ships for Friday 20 Nov (P0); P2 marks what is built but switched off until an outside approval lands. **Lane** is who builds it (`docs/SHIP_PLAN_1PC.md` §5). Update a row when its module lands.

## `P-REPO.screens`

| ID | Pack route | Closest today | State | Effort | Phase | Lane |
|---|---|---|---|---|---|---|
| `S-01` | `/` signed out | none (`proxy.ts` sends signed-out visitors to `/sign-in`) | missing | M | P0 | A |
| `S-02` | `/sign-in` | `app/sign-in`, `app/auth/{login,callback,logout}` | exists, differs | L | P0 (single sign-on), P2 (email code) | A |
| `S-03` | `/home` | `app/page.tsx` (signed-in home) | exists, differs | L | P0 | C |
| `S-04` | `/share` | `app/share/page.tsx`, `share/start.tsx` | exists, differs | L | P0 | C |
| `S-04B` | `/share/:draftId` | `app/share/[id]/canvas-form.tsx` | exists, differs | L | P0 | C |
| `S-05` | `/share/:draftId/check` | `app/share/[id]/done/*` (checks after submit today) | exists, differs | L | P0 | C |
| `S-06` | `/ideas/:id` (sharer) | data: worker `ideapage/sharer.py`, `GET /api/ideas/:id` (`SharerView`); composes lane B's `/api/ideas/:id/decision` and `/question-set`; withdraw and restore `ideapage/withdraw.py`. Screen: `app/ideas/[id]` (old) | server built, screen to come | L | P0 | E |
| `S-06B` | `/ideas/:id/edit` | none | missing | M | P0 | C |
| `S-07` | `/my-ideas` | data: worker `ideapage/mine.py`, `GET /api/me/ideas` (`MyIdeasResponse`, state in the URL). Screen: `app/my-ideas` (old) | server built, screen to come | M | P0 | E |
| `S-08` | `/ideas/:id/conversation` | none | missing | L | P0 | F |
| `S-09` | `/ideas/:id` (others) | data: worker `ideapage/colleague.py`, `GET /api/ideas/:id` (`ColleagueView`, cut to public fields in `server/idea-page.ts`). Screen: `app/ideas/[id]` (old) | server built, screen to come | M | P0 | E |
| `S-WALL` | `/wall` | `app/wall` | exists, differs | M to L | P0 | E |
| `S-ONE` | `/one` | `app/my-ideas/one-dashboard.tsx`, `glow-up.tsx` | exists, differs | S to M | P0 | E |
| `S-R1` | `/desk` | `app/review` | exists, differs | M to L | P0 | B |
| `S-R2` | `/desk/ideas/:id` | `app/review/[id]` | exists, differs | L | P0 | B |
| `S-R3` | `/ideas/:id/answer` | none | missing | M to L | P0 | B |
| `S-R4` | `/committee` | `app/committee` (scoring rounds); closest behaviour is `app/desk-decisions` (veto) | exists, differs | L | P0 | B |
| `S-H2` | `/crew` | none (`crew.tsx` fragments) | missing | L | P0 | F |
| `S-H2B` | `/inbox/:itemId` | none | missing | M to L | P0 | F |
| `S-H3` | `/share/other-ways` | `app/share/other-ways` (page, `ways.tsx`), `server/ways.ts`, `POST /api/me/app-news` over `app_news_requests` | built (16 Nov, BLD-A192); email and Teams intake switched off (`intake.email`, `intake.teams`), arrivals read `ideas.channel` after the cut-over | M | P0 (page), P2 (arrivals) | A |
| `S-H4` | `/how-it-works` | `app/how-it-works`, `lib/how-it-works.ts` (old `app/journey` stays until lane E retires it) | built (16 Nov, BLD-A194) | S | P0 | A |
| `S-H5` | `/inbox`, `/inbox/:itemId` (also S-H2B's route) | `app/inbox` (`page.tsx`, `[item]/page.tsx`, `inbox-reader.tsx`, `teamup-request.tsx`, `inbox.css`), `server/inbox.ts`, `server/inbox-route.ts`, `/api/inbox/*` | built (17 Nov, BLD-A200 to A209); e2e `e2e/inbox.spec.ts` | L | P0 | A |
| `S-H6` | `/profile` | none; pieces on `/my-ideas` (`points.tsx`, `name-on-wall.tsx`) | exists, differs | M | P0 | E |
| `S-OFFICE` | `/display/office` | `app/display/office`, `lib/display.ts`, `server/display.ts`, worker `display/office.py`, `GET /api/display/office` (old `app/constellation` stays until lane E retires it) | built (16 Nov, BLD-A190, BLD-A191) | M | P0 | A |
| `S-LAUNCH` | `/display/launch` | `app/display/launch` (`stage.tsx`, `sound.ts`); old `app/launch` stays until lane E retires it | built (16 Nov, BLD-A190, BLD-A193) | S | P0 | A |

## `P-REPO.components`

| ID | State | Effort | Phase | Lane |
|---|---|---|---|---|
| `C-SIDEBAR` | built (BLD-D011): `components/shell/sidebar.tsx`, `account-menu.tsx`, `frame.tsx`, `app/shell.css`; links from `policy/rbac.yaml` `navigation:`; data `server/shell.ts`. Lanes B fill `desk` and `committee` rows | M to L | P0 | D |
| `C-PHONE-TABS` | built (BLD-D011): `components/shell/phone.tsx` (`PhoneTabs`, `PhoneTop`, `PhoneBar` for child screens, `Dock` for task screens) | M | P0 | D |
| `C-TASKBAR` | built (BLD-D011): `components/shell/taskbar.tsx`; task screens mount it as the first child of `main` | S to M | P0 | D |
| `C-BUTTON` | built: `offer.css` (`.btn` family, `.tb`), `components/ui/button.tsx` (`Button`, `ButtonLink`, `buttonClass`); the legacy `.button` classes take the same look in `globals.css` | M | P0 | D |
| `C-CHIP` | built: `components/ui/chips.tsx` (`ChoiceChips` radio group with arrows, `MultiChips` pressed), `components.css`; the sliding ring waits for the FLIP polish | M | P0 | D |
| `C-PILL` | built: `components/ui/pill.tsx` (`Pill`, `StatusPill`, `IDEA_STATUS` from `E-ENUMS.idea-status`) | S | P0 | D |
| `C-FIELD`, `C-FIELD-MSG` | built: `components/ui/field.tsx` (`Field` wires label, help, message, `aria-describedby`, `aria-invalid`; `FieldMsg`); 3:1 border; `code-field.tsx` (six boxes, paste, auto-advance, Backspace, shake, autofill) and `question-box.tsx` ("Pinned to" a part, Enter adds) | S | P0 | D |
| `C-CARD` | built: `components.css` (`.card`, `.panel`, `.tile`, `.well`, `.note`, `.note.blue`, `.slab`, `.placeholder`, `.card-link`); glass inside the shell (`shell.css`) | M | P0 | D |
| `C-AVATAR` | built: `components/ui/avatar.tsx` (`Avatar` with sizes, neutral and tier rings, the system mark; `CrewFaces` and `crewLine`) | S | P0 | D |
| `C-SKELETON` | built: `components/ui/skeleton.tsx` (`Skeleton`, `SkeletonRows`, `Loading`, `Spinner`) | S | P0 | D |
| `C-EMPTY` | built: `components/ui/empty.tsx`; screens replace their ad hoc lines as they are rebuilt | S | P0 | D |
| `C-SORTS` | built: `components/ui/sorts.tsx` (row on desktop, cycling button on a phone); row gliding waits for the FLIP polish | S | P0 | D |
| `C-TABS` | built: `components/ui/tabs.tsx` (`Tabs`, `tabPanelProps`); the sliding underline waits for the FLIP polish | S to M | P0 | D |
| `C-SEARCH` | bar built (lane D): `components/ui/search.tsx` (`SearchBar`: chips in the bar, Backspace, Clear, Filter, the panel with counts and example questions, the result line); search by meaning and "ask" are lane F's (`L-SEARCH`) | M | P0 | D (bar), F (ask) |
| `C-TRACK` | built: `components/ui/track.tsx` (horizontal and vertical, state suffixes, draw-in motion) | S to M | P0 | D |
| `C-FILE` | UI built (lane D): `components/ui/file.tsx` (`FileRow`, `FileList`, `DropArea`); upload, quarantine and scan stay in `share/[id]/attachments.tsx`; no "couldn't open this link" state (BLD-E001) | M | P0 | D (UI), C (wiring) |
| `C-DROPDOWN` | built: `components/ui/dropdown.tsx`; named "{label}: {summary}", with `optional` and `empty` (lane F, BLD-F070) | S | P0 | D |
| `C-PROMPT` | exists, differs | L | P0 | C |
| `C-DRAFT-LOADER` | missing | M | P0 | C |
| `C-DRAFT-PANEL` | missing | L | P0 | C |
| `C-HIDDEN` | exists, differs | M | P0 | C |
| `C-SIMGRID` | exists, differs | M | P0 | C |
| `C-PREVIEW` | missing | M | P0 | C |
| `C-WORTH` | exists, differs | M | P0 | C, B |
| `C-QCARD` | missing | M | P0 | B |
| `C-INBOX-READER` | built (17 Nov, BLD-A201, A204): `app/inbox/inbox-reader.tsx`; S-H2B's request body and answers in `app/inbox/teamup-request.tsx` over lane F's `/api/team-up/:id` | L | P0 | A |
| `C-LISTEN` | missing | M | P0 | B |
| `C-SHEET-MERGE` | missing | M | P0 | B |
| `C-SHEET-TEAMUP` | built (lane F, BLD-F070 to BLD-F073): `components/teamup/teamup-sheet.tsx` (`TeamUpSheet`: compose with the drafted note and "Bring your ideas along", or on Check it (`draftId`) "Ask {lead} to merge mine in" / "Keep mine separate"; sending; sent in place with "Withdraw request"; every API error; `useTeamUpSheet()` gives hosts `open(ideaId)` and `sheet`); tests `tests/unit/teamup-sheet.test.ts` | M | P0 | F |
| `C-CREW-DECK` | motion and controls built (lane D): `components/ui/deck.tsx` (`Deck`: one pile, the flight out and back at 620 ms, round buttons, pager dots, "Idea 1 of 5", ← →; only the front card in the reading order); card content, filters and states are lane F's | L | P0 | D (motion), F (data) |
| `C-ONES-FAN` | built (lane D): `components/ui/ones-fan.tsx` (`OnesFan`: stacked, spread, buttons, ← →, swipe, one wheel step per card handing the scroll back at either end, tilt, "Post 1 of 4", the empty and one-post states; `OnesPost` on the dark slab with the consent rule); `components/ones-carousel.tsx` retires when Home uses it | M to L | P0 | D |

## `P-REPO.logic`

| ID | Owner today | State | Phase | Lane |
|---|---|---|---|---|
| `L-AUDIT` | `policy/rbac.yaml`, `proxy.ts`, `audit_log`, `core/killswitch.py`, `server/killswitch.ts` | exists, differs | P0 | A |
| `L-AUTH` | `server/auth/*`, `app/auth/*`, `identity/*` | exists, differs | P0 (single sign-on), P2 (email code) | A |
| `L-DRAFT` | `gateway/run_agent`, `gateway/grounding.py`, `agents/canvas-assist`; `L-DRAFT.voice`: `speech/drafts.py` and `POST /api/drafts/:id/voice/start|chunk|end` (BLD-C112) | exists, differs | P0 | C |
| `L-HIDE` | `pii/*`, `agents/gatekeeper`, `attachments/*` | exists, differs | P0 | C |
| `L-SORT` | `ideas.area`, taxonomy | exists, differs | P0 | C |
| `L-SIMILAR` | `router/match.py`, `agents/judge`, embeddings | exists, differs | P0 | C |
| `L-SUBMIT` | `server/submissions.ts`, `scan/save.py` | exists, differs | P0 | C |
| `L-REVIEW` | `services/worker/desk/review.py`, `queue.py`, `reads.py`, `clock.py`, `clocks.py`; web forwarders in `server/desk.ts` | landed at 82668c1 (17 Nov, back end; follow-up on `b/1pc-review-fu`) | P0 | B |
| `L-DECIDE` | `services/worker/desk/decide.py`, `promises.py`, `when.py`; `idea_decisions` | landed at 82668c1 (17 Nov, back end) | P0 | B |
| `L-INBOX` | worker `notify/inbox.py`, `notify/render.py`, `notify/ops.py` over `notifications` (kind NOT NULL); `/internal/inbox/*`; templates `comms/templates/inbox/` | built (17 Nov, BLD-A200 to A206); old `comms/inbox.py` stays until lane E retires it | P0 | A |
| `L-NOTIFY` | worker `notify/__init__.py` (`post`, `resolve`, BLD-A180), `comms/send.py`, `notify/digest.py` (decide-by digest, `comms.digest` job), migration `20261122100300_notify_dedupe.sql` | built (17 Nov, BLD-A180, A200, A203); Teams built and switched off (`comms.teams`, DEC-105) | P0 (email, in-app), P2 (Teams) | A |
| `L-WALL` | `views/wall.py` | exists, differs | P0 | E |
| `L-ONES` | `ones/*` | exists, differs | P0 | E |
| `L-IMPACT` | `delivery_measurements`, `delivery/service.py` | exists, differs | P0 (admin entry) | A |
| `L-DISPLAY` | `app/display/*`, `open_display` in `policy/rbac.yaml` (the `display` role and admins), `server/display.ts` over the worker's `display/office.py` (`/internal/display/office`) | built (16 Nov, BLD-A190 to A193) | P0 | A |
| `L-QUESTIONS` | `services/worker/desk/asking.py`, `questions.py`, `clock.py`; `question_sets`, `questions`, `answers` | landed at 82668c1 (17 Nov, back end) | P0 | B |
| `L-COMMITTEE` | `services/worker/desk/committee.py`, `window.py`; `decision_windows`, `decision_reversals` | landed at 82668c1 (17 Nov, back end) | P0 | B |
| `L-CONVO` | none | missing | P0 | F |
| `L-WORTH` | `services/worker/desk/worth.py`, `revise.py` | landed at 82668c1 (17 Nov, back end) | P0 | B |
| `L-MERGE` | desk: `services/worker/desk/merge.py`, `merging.py`, `merges` (landed at 82668c1, 17 Nov, back end). `.request` and `.effects` for lead-accepted merges: `services/worker/teamup/drafts.py`, `teamup/merging.py` (`apply_lead_merge`); `/api/drafts/[id]/merge-request`; the lead answers through `/api/team-up/[id]/answer` (BLD-F010, BLD-F012). `.desk`: lane B's `desk/merging.py` | desk landed; request built 17 Nov (lane F) | P0 | B (desk), F (request) |
| `L-TEAMUP` | `services/worker/teamup/` (`requests.py`, `crew.py`, `rules.py`, `routes.py`, `inbox_ops.py`: the lead's answers as Inbox ops `decline`, `team_only`, `merge` in lane A's `notify.ops`, BLD-F028); `apps/web/src/server/teamup.ts`; `/api/ideas/[id]/team-up` (+ `/draft-note`), `/api/team-up/[id]` (+ `/answer`), `/api/ideas/[id]/crew/leave`, `/api/ideas/[id]/crew/[member]` | built 17 Nov (branch `f/teamup`); screens wire to it in lane F's front end | P0 | F |
| `L-CREW` | none | missing | P0 | F |
| `L-SEARCH` | `chunks`, `tsv`, BGE-M3 | missing | P0 | F |
| `L-LISTEN` | lane B: `services/worker/desk/listen.py`, `reads.script_for`, `GET /api/desk/ideas/:id/listen` (BLD-B237); lane C: `speech/listen.py` (speak, chapters, cache, prefetch), `gateway/sarvam.py` (bulbul:v4-flash), `GET /api/ideas/:id/listen` and `/listen/chapters` (BLD-C114) | lane B's back end landed at 82668c1 (17 Nov); lane C's hosted voice on c/sarvam; the player (`C-LISTEN`) and the script are lane B's | P0 | B, C |

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

**Built** (lane D, BLD-D010, 16 Nov 2026): `apps/web/src/app/tokens.css` (verbatim), `foundation.css` (the groups tokens.css leaves out, base, type classes, ambient light, reduced motion), `offer.css` (aliases only), `motion.css` (the pack's motion sheet, re-pointed), `src/lib/motion/flip.ts` (WAAPI FLIP, BLD-E005). Tests: `apps/web/tests/unit/foundation.test.ts`.

## `P-REPO.not-in-pack`

What the repo has that the pack does not describe, and what happens to it, is the retire list in `mapping/logic.md` §3 and `mapping/contracts.md` §5, summarised in `docs/SHIP_PLAN_1PC.md` §6.
