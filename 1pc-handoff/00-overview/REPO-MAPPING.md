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
| `S-01` | `/` signed out | `app/landing.tsx`, `landing-motion.tsx`, `landing.css`, served by `app/page.tsx` when signed out (BLD-A172); the Ones from `publicOnes()` in `server/ones.ts`; sign-out lands here (BLD-A179); e2e `landing.spec.ts` | built (branch `a/auth-landing`) | M | P0 | A |
| `S-02` | `/sign-in` | `app/sign-in/{page,email-code,sso-form}.tsx`, `sign-in.css` (both boards: `si-desk` / `si-phone`, BLD-A179); `server/auth/{session,intents,drafts,codes}.ts`; e2e `sign-in.spec.ts` | built (branch `a/auth-landing`); email steps behind `auth.email_code`, off (BLD-E002); `/signed-out` retired (BLD-A179) | L | P0 (single sign-on), P2 (email code) | A |
| `S-03` | `/home` | `app/page.tsx` (signed-in home) | exists, differs | L | P0 | C |
| `S-04` | `/share` | `app/share/page.tsx`, `share/start.tsx` | exists, differs | L | P0 | C |
| `S-04B` | `/share/:draftId` | `app/share/[id]/canvas-form.tsx` | exists, differs | L | P0 | C |
| `S-05` | `/share/:draftId/check` | built: `app/share/[id]/check/` (`check-it.tsx` the rail and stage, phone as one page; `parts.tsx`, `similar.tsx`, `proof.tsx`, `fix.tsx`, `hidden.tsx`; `client.ts` the calls, `model.ts` the rules, `copy.ts` the words). The old `share/[id]/done/` stays until the old canvas flow retires with `S-04B` | built (lane C, BLD-C130 to C139); draft, similar, files and team-up routes from their branches | L | P0 | C |
| `S-06` | `/ideas/:id` (sharer) | data: worker `ideapage/sharer.py`, `GET /api/ideas/:id` (`SharerView`); composes lane B's `/api/ideas/:id/decision` and `/question-set` on the server (`app/ideas/[id]/page.tsx`); withdraw and restore `ideapage/withdraw.py`. Screen: `app/ideas/[id]/sharer-screen.tsx` (card sentence from the decision in `decision.ts`), `idea-page.css`; the address is cleaned of `from`/`back` once read and the way back is kept in the history entry (`parts.tsx`: `WayBack`, `BackLink`, BLD-E021). "You and the review desk" has "Open the conversation" (to S-08) beside its heading and the desk's line under it, as Status.md draws it (BLD-E045); the similar tiles' "Team up" and C-PREVIEW's `onPrimary` open lane F's C-SHEET-TEAMUP (`useTeamUpSheet`). Tests `e2e/idea-page.spec.ts`, `tests/unit/idea-page-screens.test.ts`, `tests/unit/idea-page-teamup.test.ts` | built (team-up sheet wired 18 Nov; conversation entries, join-build and live updates wait on lanes F, B and E) | L | P0 | E |
| `S-06B` | `/ideas/:id/edit` | built: `app/ideas/[id]/edit/` (`edit-idea.tsx` the one page, phone in one column with the dock; `model.ts` what changed and the Save body; `copy.ts` the words), reusing S-05's parts from `app/share/[id]/check/` with edit props and `use-proof.ts`; data `GET`/`PATCH /api/ideas/:id/edit` (`server/share.ts`, worker `submit/edit.py`) | built (lane C, BLD-C160 to C166); files and links over c/files-2's routes, lands after it; the unsaved words go to S-08's box through `components/convo/prefill.ts` (BLD-C165) | M | P0 | C |
| `S-07` | `/my-ideas` | data: worker `ideapage/mine.py`, `GET /api/me/ideas` (`MyIdeasResponse`, state in the URL). Screen: `app/my-ideas/page.tsx` (first view on the server), `my-ideas-screen.tsx`, `my-ideas.css`; the way back `components/browse/return-to.ts`. Tests `e2e/my-ideas.spec.ts` | built | M | P0 | E |
| `S-08` | `/ideas/:id/conversation` | `app/ideas/[id]/conversation/page.tsx` over `server/convo.ts` (`readConversation`); the screen `components/convo/conversation.tsx` (+ `compose.ts`, `conversation.css`); dev-only `app/kit/conversation` for e2e. Questions as a plain entry until `C-QCARD` lands (BLD-F065); no attach control until a conversation upload route exists (BLD-F064); reads S-06B's carried words once into the box (`prefill.ts`, BLD-C165) | built (18 Nov, `f/convo-7`) | L | P0 | F |
| `S-09` | `/ideas/:id` (others) | data: worker `ideapage/colleague.py`, `GET /api/ideas/:id` (`ColleagueView`, cut to public fields in `server/idea-page.ts`). Screen: `app/ideas/[id]/colleague-screen.tsx` (Back link from `parts.tsx`; `TeamUpCard` draws the API's `team_up.state`: Team up opens lane F's C-SHEET-TEAMUP through `useTeamUpSheet`, "Waiting for {lead}" with Withdraw (`DELETE /api/team-up/:id`, marked with `teamUpOpener`), "Say hello" to the conversation for the crew only, one line for closed or merged; BLD-E046), `idea-page.css`. Tests `e2e/idea-page.spec.ts`, `tests/unit/idea-page-teamup.test.ts` | built; Team up wired (18 Nov) | M | P0 | E |
| `S-WALL` | `/wall` | `app/wall/page.tsx` (first view on the server, `app/wall/load.ts`), `wall-screen.tsx` (kind chips, sorts, Show more in place; state in the URL, `state.ts`), `wall.css`; data `GET /api/wall/*` (`server/wall.ts`). Tests `e2e/wall.spec.ts` | built | M to L | P0 | E |
| `S-ONE` | `/one` | `app/one` (`page.tsx`, `one-screen.tsx`, `glow-up.tsx`, `showcase-sheet.tsx`, `rules.ts`); data `GET /api/one` and its writes (`server/wall.ts`, worker `wall/ones.py`); `/ones/leaderboard` and `/my-ideas/showcase` retired, `/ones/write/:id` and `/ones/showcase/:id` (admin-only) kept (BLD-E042) | built (17 Nov, BLD-E040 to BLD-E042) | S to M | P0 | E |
| `S-R1` | `/desk` | `app/desk` (`page.tsx`, `desk-view.tsx`, `desk.css`), `server/desk.ts` `deskRead`, worker `desk/reads.py`; `/review` redirects here (old page, actions and `review.spec.ts` retired) | built (17 Nov, lane B, b/1pc-screens-1) | M to L | P0 | B |
| `S-R2` | `/desk/ideas/:id` | `app/desk/ideas/[id]` (`page.tsx`, `reviewer-idea.tsx`, `reviewer.css`), `lib/desk/{panel,when,countdown,files,hide}.ts`, `components/review/hide-this.tsx` ("Hide this", L-HIDE.rules/7, and "Shown, because …", L-HIDE.rules/6, BLD-B246); `/review/:id` redirects here. "See changes" on Draft history waits for A-API's versions route | built (17 Nov, lane B, b/1pc-screens-1) | L | P0 | B |
| `S-R3` | `/ideas/:id/answer` | `app/ideas/[id]/answer` (`page.tsx`, `answer-view.tsx`, `answer.css`); files on an answer and the voice are seams | built (17 Nov, lane B, b/1pc-screens-1) | M to L | P0 | B |
| `S-R4` | `/committee` | `app/committee` (`page.tsx`, `committee-view.tsx`, `committee.css`; the scoring-round page replaced), worker `desk/committee.py`; page rule `committee_window` | built (17 Nov, lane B, b/1pc-screens-1) | L | P0 | B |
| `S-H2` | `/crew` | none (`crew.tsx` fragments) | missing | L | P0 | F |
| `S-H2B` | `/inbox/:itemId` | none | missing | M to L | P0 | F |
| `S-H3` | `/share/other-ways` | `app/share/other-ways` (page, `ways.tsx`), `server/ways.ts`, `POST /api/me/app-news` over `app_news_requests` | built (16 Nov, BLD-A192); email and Teams intake switched off (`intake.email`, `intake.teams`), arrivals read `ideas.channel` after the cut-over | M | P0 (page), P2 (arrivals) | A |
| `S-H4` | `/how-it-works` | `app/how-it-works`, `lib/how-it-works.ts` (old `app/journey` stays until lane E retires it) | built (16 Nov, BLD-A194) | S | P0 | A |
| `S-H5` | `/inbox`, `/inbox/:itemId` (also S-H2B's route) | `app/inbox` (`page.tsx`, `[item]/page.tsx`, `inbox-reader.tsx`, `address.ts`, `teamup-request.tsx`, `inbox.css`), `server/inbox.ts`, `server/inbox-route.ts`, `/api/inbox/*` | built (17 Nov, BLD-A200 to A209; tab, search and open item in the address 18 Nov, BLD-A198); e2e `e2e/inbox.spec.ts` | L | P0 | A |
| `S-H6` | `/profile` | `app/profile` (`page.tsx`, `profile-screen.tsx`, `refer-as.tsx`, `rules.ts`); data `GET /api/me/profile`, `PATCH /api/me/settings` (worker `wall/profile.py`), lane C's `server/refer-as.ts` and `PUT /api/me/refer-as` | built (17 Nov, BLD-E043) | M | P0 | E |
| `S-OFFICE` | `/display/office` | `app/display/office`, `lib/display.ts`, `server/display.ts`, worker `display/office.py`, `GET /api/display/office` (old `app/constellation` stays until lane E retires it) | built (16 Nov, BLD-A190, BLD-A191) | M | P0 | A |
| `S-LAUNCH` | `/display/launch` | `app/display/launch` (`stage.tsx`, `sound.ts`); old `app/launch` stays until lane E retires it | built (16 Nov, BLD-A190, BLD-A193) | S | P0 | A |

## `P-REPO.components`

| ID | State | Effort | Phase | Lane |
|---|---|---|---|---|
| `C-SIDEBAR` | built (BLD-D011): `components/shell/sidebar.tsx`, `account-menu.tsx`, `frame.tsx`, `app/shell.css`; links from `policy/rbac.yaml` `navigation:`; data `server/shell.ts`. The `desk` and `committee` rows are lane B's (`deskRows`, `committeeRows`, 17 Nov) | M to L | P0 | D |
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
| `C-FILE` | UI built (lane D): `components/ui/file.tsx` (`FileRow`, `FileList`, `DropArea`); wired on `S-05` part 4 in `app/share/[id]/check/proof.tsx` and on `S-06B` (rows and calls in `use-proof.ts`, shared) against A-API.files (BLD-C133); the old canvas's `share/[id]/attachments.tsx` retires with it; no "couldn't open this link" state (BLD-E001). Files API (lane C, BLD-C105 to C109): `services/worker/attachments/files.py`, `files_api.py`, `hide/files.py`; web `server/files.ts`, `/api/files`, `/api/files/:id`, `/view`, `/retry`, `/hide`, `/api/links`, `/api/config/uploads` | M | P0 | D (UI), C (wiring) |
| `C-DROPDOWN` | built: `components/ui/dropdown.tsx`; named "{label}: {summary}", with `optional` and `empty` (lane F, BLD-F070) | S | P0 | D |
| `C-PROMPT` | exists, differs | L | P0 | C |
| `C-DRAFT-LOADER` | missing | M | P0 | C |
| `C-DRAFT-PANEL` | missing | L | P0 | C |
| `C-HIDDEN` | exists, differs | M | P0 | C |
| `C-SIMGRID` | grid built on `S-05`: `app/share/[id]/check/similar.tsx` (yours first, tiles, waiting and on the crew, fold after "Keep mine separate" in the sheet, BLD-C131); team-up through lane F's `components/teamup/teamup-sheet.tsx` (`useTeamUpSheet` with `returnFocus`, `teamUpOpener` on Team up and Withdraw) | M | P0 | C |
| `C-PREVIEW` | built: `components/preview/idea-preview.tsx` (`IdeaPreviewDialog`), the band's status is lane D's `<Pill variant="band">` (BLD-D012); used on `S-05` | M | P0 | C |
| `C-WORTH` | reviewer's view and editor built (lane B): `components/review/worth.tsx` (`WorthView`, `WorthEditor` from `WorthResponse`), its sheet `worth.css` imported with it, so S-05 can place `WorthView` | M | P0 | C, B |
| `C-QCARD` | built (lane B): `components/review/qcard.tsx` (`QuestionsCard`, `variant` `status` for S-06 and S-08, `home` for S-03's Needs you, `inbox` for the S-H5 reader, each with its board's words); placed by the screens that show it. Placed on S-H5 (18 Nov, BLD-B248): the reader's body for `questions` and `answer_reminder`, with the reader's header and foot (`answerLabel` gives the forward action's words). Placed on S-08 (18 Nov, BLD-B249): `components/review/qcard-for.tsx` reads the entry's set for the sharer while it is open; everyone else keeps the plain line | M | P0 | B |
| `C-INBOX-READER` | built (17 Nov, BLD-A201, A204): `app/inbox/inbox-reader.tsx`; S-H2B's request body and answers in `app/inbox/teamup-request.tsx` over lane F's `/api/team-up/:id` | L | P0 | A |
| `C-LISTEN` | built (lane B): `components/review/listen-player.tsx` with `listen.css`, `lib/desk/listen.ts`; lane C's hosted audio and chapters first (DEC-108, `AudioEngine`), the browser's voice (BLD-B230, `ListenEngine`) on a 404 or 503 (BLD-B245) | M | P0 | B |
| `C-SHEET-MERGE` | built (lane B): `components/review/merge-sheet.tsx` with `merge-sheet.css`, opened from S-R2's rows and C-PREVIEW's Merge | M | P0 | B |
| `C-SHEET-TEAMUP` | built (lane F, BLD-F070 to BLD-F073): `components/teamup/teamup-sheet.tsx` (`TeamUpSheet`: compose with the drafted note and "Bring your ideas along", or on Check it (`draftId`) "Ask {lead} to merge mine in" / "Keep mine separate"; sending; sent in place with "Withdraw request"; every API error; `useTeamUpSheet()` gives hosts `open(ideaId)` and `sheet`, `teamUpOpener(ideaId)` marks what stands where "Team up" was); tests `tests/unit/teamup-sheet.test.ts`, `e2e/teamup-sheet.spec.ts` on the dev-only `/kit/team-up` (BLD-F074) | M | P0 | F |
| `C-CREW-DECK` | motion and controls built (lane D): `components/ui/deck.tsx` (`Deck`: one pile, the flight out and back at 620 ms, round buttons, pager dots, "Idea 1 of 5", ← →; only the front card in the reading order); card content, filters and states are lane F's | L | P0 | D (motion), F (data) |
| `C-ONES-FAN` | built (lane D): `components/ui/ones-fan.tsx` (`OnesFan`: stacked, spread, buttons, ← →, swipe, one wheel step per card handing the scroll back at either end, tilt, "Post 1 of 4", the empty and one-post states; `OnesPost` on the dark slab with the consent rule); `components/ones-carousel.tsx` retires when Home uses it | M to L | P0 | D |

## `P-REPO.logic`

| ID | Owner today | State | Phase | Lane |
|---|---|---|---|---|
| `L-AUDIT` | `policy/rbac.yaml`, `proxy.ts`, `audit_log`, `core/killswitch.py`, `server/killswitch.ts`; the admin page `app/admin/*` (roles: the pack's only, BLD-A215; flags S1 to S3 with `server/flags.ts`, `programme/flags.py`, `GET /api/config`, BLD-A216) | built (17 Nov, BLD-A210, A215, A216) | P0 | A |
| `L-AUTH` | `server/auth/{intents,sso,reference,codes,email-code,drafts,session}.ts`; `app/auth/{sso/start,login,callback,code/send,code/verify,session,sign-out,logout}`; worker `comms/sign_in_code.py` (BLD-A173 to A176) | built (branch `a/auth-landing`) on the cut-over's `sign_in_intents` and `sign_in_codes` | P0 (single sign-on), P2 (email code) | A |
| `L-DRAFT` | `gateway/run_agent`, `gateway/grounding.py`, `agents/canvas-assist`; `L-DRAFT.voice`: `speech/drafts.py` and `POST /api/drafts/:id/voice/start|chunk|end` (BLD-C112) | exists, differs | P0 | C |
| `L-HIDE` | `pii/*`, `agents/gatekeeper`, `attachments/*` | exists, differs | P0 | C |
| `L-SORT` | `services/worker/submit/{sorting,routing,config}.py`, `rules/sorting.md` (lists, review routing), `sorting_trust` view; `GET`/`PATCH /api/drafts/:id/sorting` (BLD-C080, BLD-C082) | built (API) | P0 | C |
| `L-SIMILAR` | `router/match.py`, `agents/judge`, embeddings | exists, differs | P0 | C |
| `L-SUBMIT` | `services/worker/submit/{ready,send,check,clock,edit,fix,helpers,adapters}.py`, `server/share.ts`; `GET /api/drafts/:id/send`, `PUT`/`DELETE /api/drafts/:id/fix` and `PUT /api/drafts/:id/helpers` (S-05.fix and part 6; figures through lane B's `desk/worth.py`), `POST /api/drafts/:id/submit`, `GET`/`PATCH /api/ideas/:id/edit` (A-API `PATCH /ideas/:id`), `GET /api/ideas/:id/versions`; timer kind `decide_by`; withdraw and restore are lane E's `ideapage/withdraw.py` through `submit/adapters.py`. Old `server/submissions.ts` and `scan/save.py` stay for the old `/share` pages until S-05 replaces them (BLD-C081, BLD-C083 to BLD-C086) | built (API) | P0 | C |
| `L-REVIEW` | `services/worker/desk/review.py`, `queue.py`, `reads.py`, `clock.py`, `clocks.py`; web forwarders in `server/desk.ts` | landed at 82668c1 (17 Nov, back end; follow-up on `b/1pc-review-fu`) | P0 | B |
| `L-DECIDE` | `services/worker/desk/decide.py`, `promises.py`, `when.py`; `idea_decisions` | landed at 82668c1 (17 Nov, back end) | P0 | B |
| `L-INBOX` | worker `notify/inbox.py`, `notify/render.py`, `notify/ops.py` over `notifications` (kind NOT NULL); `/internal/inbox/*`; templates `comms/templates/inbox/` | built (17 Nov, BLD-A200 to A206); old `comms/inbox.py` stays until lane E retires it | P0 | A |
| `L-NOTIFY` | worker `notify/__init__.py` (`post`, `resolve`, BLD-A180), `comms/send.py`, `notify/digest.py` (decide-by digest, `comms.digest` job), migration `20261122100300_notify_dedupe.sql` | built (17 Nov, BLD-A180, A200, A203); Teams built and switched off (`comms.teams`, DEC-105) | P0 (email, in-app), P2 (Teams) | A |
| `L-WALL` | `views/wall.py` | exists, differs | P0 | E |
| `L-ONES` | `ones/*` | exists, differs | P0 | E |
| `L-IMPACT` | write side: `programme/impact.py` and `programme/build.py` (team chosen, shipped, the 30- and 90-day due dates, Finance's confirmation by a second admin) behind `/api/admin/ideas/*`, on `delivery_measurements`; read side lane E's `wall/impact.py`. Inductions call lane E's `wall.ones`; tiers `programme/ones.py` with `rules/tiers.md`. "Take off the Wall": `programme/wall.py`, `wall_removals`, `idea_off_wall()` inside lane E's `on_wall_sql`, `wall.ones.posts` and the old `ones/views.py` | built (17 Nov, BLD-A211 to A214, A217) | P0 (admin entry) | A |
| `L-DISPLAY` | `app/display/*`, `open_display` in `policy/rbac.yaml` (the `display` role and admins), `server/display.ts` over the worker's `display/office.py` (`/internal/display/office`) | built (16 Nov, BLD-A190 to A193) | P0 | A |
| `L-QUESTIONS` | `services/worker/desk/asking.py`, `questions.py`, `clock.py`; `question_sets`, `questions`, `answers` | landed at 82668c1 (17 Nov, back end) | P0 | B |
| `L-COMMITTEE` | `services/worker/desk/committee.py`, `window.py`; `decision_windows`, `decision_reversals` | landed at 82668c1 (17 Nov, back end) | P0 | B |
| `L-CONVO` | `services/worker/convo/` (`post` the cross-lane entry point, SHIP_PLAN §5a; `reads.py`, `render.py`, `messages.py`, `access.py`, `routes.py`); `apps/web/src/server/convo.ts`; `/api/ideas/[id]/conversation` (+ `/messages`, `/messages/[entryId]`) (BLD-F050 to BLD-F059) | built 17 Nov (branch `f/convo-2`); S-08 wires to it | P0 | F |
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
