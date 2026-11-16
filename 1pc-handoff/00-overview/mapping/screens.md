# 1% Club handoff (draft 0) → `apps/web`: screens and shell

Read-only map, Mon 16 Nov 2026. Repo: `.worktrees/handoff` at `e911de1` (main + the pack). Pack: `1pc-handoff/` (canvas v106).
All file paths below are relative to `apps/web/src/` unless they start with `e2e/`, `tests/`, `policy/` or `1pc-handoff/`.
Policy applied: front end can be scrapped; reuse server loaders, route handlers, guards and the odd component; never carry an old product rule into the new design.

---

## Headline findings

1. **Only two screens are near-reusable as they stand: `S-LAUNCH` and `S-ONE`.** `app/launch/stage.tsx` already has the operator frame, Start and Full screen, the timed beats (0, 4, 8, 14, 16.5 and 30 s), the Web Audio bell and crackle, and the QR code from `server/qr.ts`. To match `L-DISPLAY.launch` it only needs the route `/display/launch`, a display-operator role and the six-beat timeline. `app/my-ideas/one-dashboard.tsx` with `glow-up.tsx` is `S-ONE` already: the number window, the brief, measured impact and a glow-up dialog that plays once. It only needs its own route, `/one`.
2. **The whole share journey (`S-03`, `S-04`, `S-04B`, `S-05`) is new.** The repo has a form canvas, `app/share/[id]/canvas-form.tsx` (872 lines, quick or full mode, a strength meter, personal data that *blocks* input). The person then submits, and the gatekeeper, canvas-assist and matching run *after* sending (`share/[id]/done/scan-status.tsx`, `crew.tsx`). The pack reverses this. Words become a live draft before sending, and personal details are *masked* rather than blocked. The sorting is confirmed and similar ideas are offered on Check it, before the idea is sent. This needs a back end for draft messages and parts, not just new screens. It is the largest risk for Friday.
3. **The pack conflicts with two non-negotiables in `CLAUDE.md`. Stop and ask before building.**
   - Non-negotiable **#4** says investor and customer identifiers are *blocked at submission*, and pattern blocks are absolute. The pack's `L-HIDE` instead *hides them automatically* and lets the person "Show it" if they give a reason (`P-DECISIONS.taken/5`).
   - Non-negotiable **#7** says submitters never see another person's name or raw text. The pack shows other people's names in several places:
     - `S-09` has "Shared … by Ravi Nair" (subject to the sharer's consent).
     - `C-CREW-DECK` shows "Ravi Nair and 3 others on it" and "The problem, in their words".
     - `S-H2B` names the requester and links to "Open her idea".
     - `C-SIMGRID` shows crew faces.
   - `server/restore.ts` and the `see_restored_values` capability still give real values to reviewers and the core committee. `P-PRODUCT.privacy` says that only the sharer ever sees unmasked customer details.
4. **The whole review side is new behaviour on old routes.**
   - `/review` and `/review/[id]` are a triage tool. A reviewer sets area tags, LOBs and scope, attaches the idea to a cluster, redirects it to IT or HR, changes its visibility or holds it as spam. The result goes on to committee scoring rounds.
   - `/committee` is sealed scoring and presentations. `/desk-decisions` is a veto open for 5 working days. `/appeals` is the appeal flow.
   - The pack replaces all of this. Reviewers choose Pick, Not now or Not picked, with a reason of at least 30 characters. They can send a set of questions, each pinned to a part of the idea, with a time to answer. The committee has a window of 30 days, extendable to 3 months, in which it can extend or reverse a decision. There are no appeals (`P-DECISIONS.taken/4`).
5. **There is no code at all behind `S-08` (conversation), `S-H2` (crew deck), `S-H2B` (team-up request), `S-H3` (other ways), `S-R3` (Answer) or `S-06B` (Edit).** The database has nothing to hold conversations, team-up requests, passed crew cards, sign-in codes or draft messages and parts. `idea_questions` has one question with `due_at`. `notifications` has template rows but no item kinds or needs-you state.
6. **The shell is new, but its mechanism can be reused.**
   - `app/layout.tsx` and `components/nav.tsx` draw a header with a top menu. The pack needs `C-SIDEBAR`, `C-PHONE-TABS`, `C-TASKBAR`, the dock and display screens with no chrome. Build these as Next route groups.
   - Keep `navFor()`, the role-driven `policy/rbac.yaml` `navigation:`/`pages:` blocks and the kill-switch filtering. Rewrite the items.
   - `/` now has to be the **signed-out Landing**. Today `proxy.ts` sends every signed-out visitor to `/sign-in`.
7. **The pack's GAPS admin tasks all have a home in the repo already, but each sits inside a larger old flow.**
   - Choosing a build team: `delivery/start-handover.tsx`.
   - Marking shipped: the delivery completion step.
   - Measurements at 30 and 90 days with Finance confirmation: `delivery/[id]/delivery-view.tsx` and `/api/delivery/[id]/measurements/[mark]/finance`.
   - Roles: `admin/roles.tsx`.
   - The Ember: `ember/compose`.
   - Strip each one down to a minimal admin page, and retire the handover pack, write-up, check-ins and sponsor approvals around them.
8. **Surprise: becoming a One works differently.** In the pack, a person becomes a One automatically when a shipped idea's impact is measured and confirmed (`L-ONES/1`). In the repo, the committee proposes a One, the chair approves and an admin carries it out (`ones/console`, `/api/ones/proposals/*`). That proposal flow is an old rule. Raise it with the product lead before cutting it.

---

## Table 1 · Every pack screen and shell module

State key: **exists, matches** · **exists, differs** · **missing**. Effort: S ≤ ½ day, M 1–2 days, L 3 days or more, back end included.

| ID | Pack route | Closest existing route + page file | State | Reusable pieces (loaders, actions, route handlers, components) | Old rules in the existing page that must NOT carry over | Effort |
|---|---|---|---|---|---|---|
| **S-01** Landing | `/` (signed out) | none. `proxy.ts` redirects every signed-out visitor to `/sign-in` (`PUBLIC_PAGES` = `/sign-in`, `/signed-out`). Signed-in `/` is today's Home, `app/page.tsx` | missing | `components/spark-mark.tsx` (the mark), `server/ones.ts` `publicOnes()` (feeds "The Ones so far"; needs a signed-out-safe path), `one-card.tsx` `OneCardBody` for names with consent, `server/config.ts` for the configured promises | Today's `/` copy "Ideas from everyone at KFintech" and "Share an idea" (a problem, a fix or a business idea). The pack is problem-first: "Share a problem". Signed-out `/` → `/sign-in` must change to `/` → Landing, with a signed-in visitor sent to `/home`. Ones' names on a signed-out page need the consent rule checked | M |
| **S-02** Sign in | `/sign-in` | `/sign-in`: `app/sign-in/page.tsx`; `/signed-out`: `app/signed-out/page.tsx`; `auth/login`, `auth/callback`, `auth/logout` route handlers | exists, differs | OIDC with PKCE in `server/auth/oidc.ts`. Sealed sign-in transaction with `next` in `server/auth/session.ts` (`sealTx`, `openTx`, `safeNext`). 8-hour session (`SESSION_TTL_SECONDS`). `server/auth/users.ts` `userFromClaims` and its `SignInRefused` reasons. Mock OIDC for dev. The right panel's mark and tagline already match | A single "Sign in with your KFintech account" button with no email-code route. The pack needs **email + 6-digit code** (10 minutes, 3 tries, resend after 45 s): new `/auth/code/send` and `/verify` endpoints and a store for codes. Silent SSO first (`prompt=none`), a failure reference ("SSO-7F3A"), the "Session expired mid-draft" state with the draft card, and intent (draft id and step) kept **server-side**. A 12-hour absolute cap (`SESSION_ABSOLUTE_HOURS`) on top of the sliding 8 hours: the pack says 8 hours. The `/signed-out` page is not in the pack | L |
| **S-03** Home | `/home` | `/`: `app/page.tsx` | exists, differs | `currentUser()`. `publicOnes()` with `components/ones-carousel.tsx` as a base for `C-ONES-FAN` (keyboard and reduced-motion handling are reusable). `server/ideas.ts` `myIdeas()` for the top three "Your ideas". `server/inbox.ts` `messagesFor()` as a stopgap only. A new `A-API.home` aggregate is needed | Three cards ("Share an idea", "My ideas", "Wall") and "Hello, {first}". "Quick capture vs full canvas" copy. No prompt box, no "Jump back in", no needs-you, no crew, no other-ways tiles, no first-visit variant. Home moves from `/` to `/home` | L |
| **S-04** Tell it (new) | `/share` | `/share`: `app/share/page.tsx` + `share/start.tsx` (picks quick or full, then `POST /api/submissions`) | exists, differs | Ownership checks and 30-day retention in `server/submissions.ts` (`createDraft`, `getDraft`, `owned()`, `retentionDays()`). The draft list query in `share/page.tsx` (for the "Existing draft prompt"). `share/[id]/voice-recorder.tsx` + `voice-logic.ts` + `/api/submissions/[id]/voice*` (the base for `C-PROMPT.voice`). Kill switches `capture.voice` and `capture.mic_hint`. Microphone permission for `/share/*` in `next.config.ts` | Two ways in (Quick capture / Full canvas). "Share an idea" with three kinds. A draft created by a button press: the pack creates it on the first pause in typing or on send. Today's flow has no conversation, no live draft panel and no loader | L |
| **S-04B** Tell it, conversation or saved draft | `/share/:draftId` | `/share/[id]`: `app/share/[id]/page.tsx` → `canvas-form.tsx` | exists, differs | Route shape is identical (UUID draft id): keep it. The autosave chain in `canvas-form.tsx` (one save at a time, in order; "Saving…" / "Saved at") becomes the `C-TASKBAR.save` logic. `share/[id]/attachments.tsx` + `server/attachments.ts` + `/api/submissions/[id]/attachments*` for upload → quarantine → scan → status (`C-FILE`). `lib/pii/patterns.ts` (shared patterns) to underline spans in the person's own text. The SSE pattern in `/api/submissions/[id]/scan-events` + `EventSource` in `scan-status.tsx` can carry `A-API.draft-stream` | The whole form canvas: six sections, the 0–5 strength meter and its "next two additions" (`lib/canvas/rules.ts` `strengthPanel`), "why we ask" and example links, required-field validation before sharing, and the quick declaration checkbox. **Personal data blocks and pauses autosave** (`blocks(hits)`): the pack masks it and keeps saving. A 50-character details minimum: the pack's threshold is 30. Category, play and estimate fields (`value.category`, `value.play`) | L |
| **S-05** Check it, then send it | `/share/:draftId/check` | `/share/[id]/done`: `app/share/[id]/done/page.tsx` + `scan-status.tsx` + `crew.tsx` + `follow-up.tsx` (after submit) | exists, differs (runs *after* submit today) | `crew.tsx`: match-card rendering, `showSuggestion()` (₹ with Indian grouping, hours a month) and suggestions shown with the person's quotes (DEC-095, which matches "Suggested because …"). `server/scan.ts` `confirmCard` / `chooseMatch` as handler skeletons only. `POST /api/submissions/[id]/submit` (ownership, sanitising, declaration). Attachments as above | The post-submit scan screen ("Checking for personal details…"). The redirect card ("an IT issue", `take_redirect` / `is_an_idea`). Contesting an investor block ("This is not personal data", BLD-082). Match actions "+1 only", "Mine is different" (one line), "Something has changed" and "Team up with my context", which joins at once: the pack sends a team-up or merge **request to the lead**. Rule that match cards show the neutral summary only (see the non-negotiable #7 conflict). The pack's 7-part rail, the sorting confirmation (`L-SORT`), the fix sheet, "Who would help" and the Send summary are all new | L |
| **S-06** Status (sharer) | `/ideas/:id` | `/ideas/[id]`: `app/ideas/[id]/page.tsx` (full view when `p.owner`) + `follow-up-panel.tsx`; "Just shared" today is `/share/[id]/done` | exists, differs | `server/ideas.ts` `ideaPage()` / `viewFor()`: the owner / desk / public branching is exactly the pack's S-06 / S-R2 / S-09 split. `status.stage`, `next_step`, `due`. `TimelineRow` events (seed for `L-CONVO` system lines). The `IDEA-YYYY-NNNNNN` reference format (same in the pack) | "Disagree with this?" (goes to the core committee: an appeal path). One question answered inline in a textarea: the pack puts questions in `C-QCARD` and answers them only on `S-R3`. "Canvas strength N of 5". Visibility "Committees only". "Back to My ideas" fixed: the pack restores the list state. No edit or withdraw window, decision reason, committee window line, track or similar-ideas card | L |
| **S-06B** Edit after sharing | `/ideas/:id/edit` | none (`PUT /api/ideas/{id}/canvas` is in `policy/rbac.yaml` but has no route file) | missing | Pieces from the S-05 build (sorting chips, fix sheet, `C-FILE`). Autosave pattern from `canvas-form.tsx` | Today nothing can be changed after submit. Edit window = until the desk opens it, at most 3 days (`L-SUBMIT.edit`) | M |
| **S-07** My ideas | `/my-ideas` | `/my-ideas`: `app/my-ideas/page.tsx` | exists, differs | `myIdeas()` → worker `/internal/me/{id}/ideas`: it already returns `ideas` (draft flag, stage, `next_step`, `due`, `idea_id`) and `joined`, which map to the **Yours / Teamed up** tabs. `day()` in `lib/dates.ts`. `/api/me/ideas` | The One dashboard, points, "Your lens", "How an idea becomes a One" and "Committee decisions and appeals" links (BLD-227). The "Your team's ideas" manager link. Name on the wall placed here (moves to `S-H6`). Links to `/share/[id]/done` for `scanning` / `blocked`. A plain list with no search, filters, sort, mini track, skeleton or URL-restored state | M |
| **S-08** An idea's conversation | `/ideas/:id/conversation` | none (closest: the `Timeline` block in `app/ideas/[id]/page.tsx`) | missing | `TimelineRow` system events. The SSE pattern for `A-API.idea-events`. Attachments pipeline for files in messages | No idea-level messaging exists; the existing "Messages" item is the inbox. A new table, handlers, live updates and the side panel are needed | L |
| **S-09** A colleague's idea | `/ideas/:id` | `/ideas/[id]`: `app/ideas/[id]/page.tsx` (the `view === "public"` branch) | exists, differs | `ideaPage()` public view (`PublicCard`: summary, area, stage, colleagues). The `IDEA_ID` check. Name-on-wall consent (`public_name_consent`) for the "Shared … by" line | "Back to the wall" is always the same: the pack names where the person came from. The public timeline. No track, team-up card, crew faces or "Waiting for Ravi" / "On the crew" states. Rule that a submitter never sees another person's name: see the non-negotiable #7 conflict | M |
| **S-WALL** The Wall | `/wall` | `/wall`: `app/wall/page.tsx` | exists, differs | `server/ideas.ts` `wall()`: `picked`, `in_garage` and `shipped` feed the **Kindling** stage cards; `recent` seeds **Just in**; `showcase` feeds the live-fixes table. `publicOnes()` + `OneCardBody` / `jerseyProps` for The Ones slab. `BANNERS["wall.public"]` pause. The `layout.tsx` footer ("1% Club" / "The Ember" / "A KFintech programme") matches `S-WALL` item 6 word for word. `components/idea-card.tsx` | "Recent ideas" as a card list (the pack: Just in table with Popular / Newest / Crew size / Ones sort and "Show 5 more"). The `in_garage` naming and "Already running" as a card section. The Ones blurb "If their ideas work, this is what changes" (the pack: shipped and measured). No kind chips, impact totals or Ember section | M–L |
| **S-ONE** A One's dashboard | `/one` | Inside `/my-ideas`: `app/my-ideas/one-dashboard.tsx` + `glow-up.tsx` (+ `/my-ideas/showcase`, `/ones/leaderboard`) | exists, matches (different place) | `OneDashboard` and `GlowUp` almost whole: native dialog, Escape, plays once, reduced motion. `components/one-spark.tsx`, `lib/measures.ts` `measureList`, `server/ones.ts` `myOne`, `swapNumber`, `proposeBrief`, `glowUpSeen`. Handlers `/api/me/one/number`, `/brief`, `/glow-up/[id]/seen`, `/showcase` | The error "taken, or resting after someone retired it" and legend or retired numbers (`one_legend_numbers`). The pack: "No. 7 is taken. Free numbers near it: 6, 8, 11." The brief is "approved by the committee": the pack says by the programme team. "Founding One since" and four tiles need checking against `L-ONES/6` | S–M |
| **S-R1** Review desk | `/desk` | `/review`: `app/review/page.tsx` + `run-now.tsx` | exists, differs | `server/review.ts` `queue()` as a handler skeleton (worker `/internal/review/*`). Filters already kept in the query string (the pack wants list state in the URL). RBAC `view_review_queue` / `work_review_queue` | Item types (disagreement, cluster proposal, working group, qualify). Filters on kind, category, confidence band, LOB, strength and waiting days. "Run grouping now". Sort "soonest due, then least confident". The pack: tabs To review / Waiting on the sharer / Answered back to you / Decided this week, live countdowns and "Remind {sharer}". Route moves to `/desk` | M–L |
| **S-R2** The idea, for the reviewer | `/desk/ideas/:id` | `/review/[id]`: `app/review/[id]/page.tsx` + `actions.tsx` + `summary-form.tsx` | exists, differs | `itemView()` / `mayAct()` / `act()` skeletons. Field provenance labels ("from the person", "suggested by the assistant", "accepted", "changed by the review desk") behind "Sorting confirmed by her". Category change with a note the person sees (a seed for `C-WORTH` "Revise what it's worth"). One "ask" action (a seed for question sets). Desk-side `summary-form.tsx` (neutral summary edit) | "Decide" means area tags, LOBs, scope and attach to a cluster, idea or new, plus "strong canvas". **Redirect** to IT, HR, facilities or intranet. **Visibility** org or "Committees only". **Hold as spam or abuse** with a second reviewer to confirm. Committee-veto takeover (`mayAct` vetoed-by). Reviewers seeing restored real values (`restoreMode` `handled_items`). The pack: Pick, Not now or Not picked with a reason of 30 characters or more, an optional Ask panel, merge, listen, and a 30-day committee window | L |
| **S-R3** Answer the review desk | `/ideas/:id/answer` | none (closest: the `FollowUp` textarea in `share/[id]/done/follow-up.tsx`, used on `/ideas/[id]`) | missing | `POST /api/ideas/[id]/answer` → `server/review.ts` `ideaWrite()`. The `idea_questions` table (encrypted question and answer, `due_at`, `answered_at`). Personal-data errors already mapped | One free-text question answered inline, "pauses their clock". The pack: a set of questions pinned to parts, with 1 day / 3 days / 1 week, answered one at a time with autosave, then "Check your answers" and Send. Each answer is added to its part and posted to the conversation | M–L |
| **S-R4** Ones Committee | `/committee` | Route `/committee` exists but holds scoring rounds (`app/committee/page.tsx`, `rounds/[id]`, `presentations/[id]`). The behaviour closest to the pack is `/desk-decisions` (`app/desk-decisions/page.tsx` + `veto-form.tsx`) | exists, differs | `deskDecisions()` (decision, decided_at, decided_by, note, `veto_open`, `veto_until`) as a loader seed. `vetoItem()` handler skeleton. RBAC `veto_desk_decision` | Sealed blind scoring, quorum, reveal, cycles and presentations (`/committee`, `/committee/rounds`, `/committee/presentations`). Veto window of **5 working days**: the pack's window is 30 days, extendable by 30 to 3 months. Veto **takes over the item**: the pack lets a member reverse once, to one of the other two decisions, with a note of 30 characters or more the sharer reads. "People who disagree" list. Links to appeals and fairness reports. "1% Club core committee" wording: the pack says "Ones Committee" | L |
| **S-H2** Find your crew | `/crew` | none (crew appears only after submit, inside `share/[id]/done/crew.tsx`) | missing | Match-card markup and copy rules in `crew.tsx` (plain words, never "duplicate"). Worker matching (`services/worker/match`) as the data source for `L-CREW` | Crew as a one-off post-submit step. "Join at once" teaming up | L |
| **S-H2B** Team-up or merge request (lead's Inbox) | `/inbox/:itemId` | none | missing | Inbox read handler `/api/inbox/[id]/read` | Nothing exists: no lead approval, no merge, no "team up only", no decline reason | M–L |
| **S-H3** Share another way | `/share/other-ways` | none | missing | Draft list query (as on `/share`). `P-DECISIONS.signoff/5` placeholders | No email or Teams intake in the web app | M (page S, intake back end L) |
| **S-H4** What happens after you share | `/how-it-works` | `/journey`: `app/journey/page.tsx` | exists, differs | The idea of a static explainer page. Promises should come from `server/config.ts` | Four isometric steps "How an idea becomes a One" (DEC-065). The pack: five stages with promises and one "Share your first problem" button | S |
| **S-H5** Inbox | `/inbox` | `/inbox`: `app/inbox/page.tsx` + `message-list.tsx` | exists, differs | `server/inbox.ts` `messagesFor()` / `markRead()`. `/api/inbox` and `/api/inbox/[id]/read`. `notifications` table (`in_app`, `read_at`). Plain-text rendering of template Markdown (no HTML injection) | Titled "Messages"; one flat accordion of template messages. No item kinds, Needs you, Unread or Archived tabs, Today / This week / Earlier groups, reader pane or actions. Count consistency with sidebar and Home | L |
| **S-H6** Profile and settings | `/profile` | Pieces live on `/my-ideas`: `my-ideas/points.tsx` (`PointsPanel`), `my-ideas/name-on-wall.tsx` (`NameOnWall`) | missing (parts exist) | `server/points.ts` `myPoints()` + `/api/me/points`. `NameOnWall` switch + `PUT /api/me/comms-prefs` → `setNameOnWall`. `comms_prefs.public_name_consent` | `comms_prefs.routine` (immediate or digest) and `manager_notes`: not in the pack. The pack has Teams / Email / Reminders switches. A points list with a 12-month figure (the pack: one figure and "How points and tiers work"). A tier for **every** employee is new (today tiers exist only for Ones) | M |
| **S-OFFICE** Office screen | `/display/office` | `/constellation`: `app/constellation/page.tsx` + `sky.tsx` | exists, differs | `server/ones.ts` `constellation()`. Rotation, refresh, pause and reduced motion in `sky.tsx`. `OneSpark`. `screen_settings` / `/api/ones/screen-mode` if `stars` and `secondsPerOne` are made configurable | 45 s of sky alternating with 15 s impact cards, plus "ambient mode" switched on by an admin. The pack rotates one One at a time ("1 of 7"). Today it needs a signed-in session: the pack wants a display account or a signed link, with no chrome. Must keep its own `Office.css` look (`S-OFFICE/4`) | M |
| **S-LAUNCH** Launch screen | `/display/launch` | `/launch`: `app/launch/page.tsx` + `stage.tsx` | exists, matches (route and role differ) | Almost all: `LaunchStage`, `qrPath()`, the `appBaseUrl()` guard, Start as the audio gesture, `requestFullscreen`, and reduced motion jumping to the final frame | Gate `grant_roles` (admin): the pack has a **display operator** role. It also needs the operator frame's six-beat timeline, "Escape leaves full screen but doesn't stop", and reload returning to the operator frame | S |
| **C-SIDEBAR** | all signed-in desktop screens | `app/layout.tsx` header + `components/nav.tsx` `MainNav`; items from `policy/rbac.yaml` `navigation:` via `lib/rbac.ts` `navFor()` | exists, differs | `navFor()` role and kill-switch filtering. `aria-current` logic in `nav.tsx`. Skip link. `currentUser().nav`. `PausedBanners` (if banners stay) | Top horizontal header, account name and Sign out in the header. Items "Share an idea", "My ideas", "Wall", "Messages", "Review", "Committee", "Desk decisions", "Ones", "Delivery", "Lenses", "Admin". The pack needs a 256px folding sidebar with drafts, your ideas, waiting-on-sharers and closing-soonest sections, an account row with tier ring, an inbox count and the `P` shortcut. `A-API.me/shell` is new. `CurrentUser` has no tier, initials or area | M–L |
| **C-PHONE-TABS** | phone root, child and task screens | none (the header just wraps) | missing | Same nav source | none | M |
| **C-TASKBAR** | `S-04`, `S-04B`, `S-05` | none (save status text inside `canvas-form.tsx`) | missing | Save state machine and timestamp formatting (`Asia/Kolkata`) in `canvas-form.tsx` | none | S–M |

---

## Table 2 · Existing pages the pack does not describe

The pack's **GAPS** list of admin tasks with no screens is: choosing a build team, marking shipped, entering measurements, managing roles, and the Ember. Those are marked **KEEP-ADMIN**. Build each as a minimal admin page with no new design (`P-GAPS`, `L-DECIDE.after`, `L-IMPACT/8`, `L-AUTH/7`, `L-WALL.ember`).

### 2a · Pages

| Existing route | Page file(s) | What it does today | Suggestion |
|---|---|---|---|
| `/admin` | `admin/page.tsx`, `kill-switches.tsx`, `roles.tsx` | Kill switches with a reason, role grants, voice-note setting | **KEEP-ADMIN** (roles, `L-AUTH/7`; flags and kill switches, `L-AUDIT.flags`). Add a `display_operator` role and S1, S2 and S3 experiment flags. Reach it from the account menu: the sidebar has no Admin item |
| `/admin/conflicts` | `admin/conflicts/page.tsx`, `conflicts.tsx` | Conflict-of-interest flags for committee scoring rounds | **Retire**. Scoring is gone. "A reviewer never reviews their own idea" and "a member can't reverse their own" become server rules |
| `/appeals`, `/appeals/[id]` | `appeals/page.tsx`, `appeal-form.tsx`, `[id]/page.tsx`, `appeal-decision.tsx` | File an appeal; the panel decides | **Retire** (`P-DECISIONS.taken/4`: no appeals) |
| `/committee` (as built) | `committee/page.tsx`, `open-cycle.tsx`, `conflict.ts` | Scoring cycles and rounds | **Rewrite as `S-R4`**. Retire the content and keep the route |
| `/committee/rounds/[id]` | `rounds/[id]/page.tsx`, `round-actions.tsx` | Sealed scoring, reveal, decide | **Retire** |
| `/committee/presentations/[id]`, `/presentations/[id]` | `committee/presentations/[id]/*`, `presentations/[id]/page.tsx`, `invitation.tsx` | Invite a sharer to present to the committee | **Retire** |
| `/desk-decisions` | `desk-decisions/page.tsx`, `veto-form.tsx` | Desk outcomes; core committee veto within 5 working days; "People who disagree" | **Fold into `S-R4`** (In the window / Reversed / Expired) and the **`S-R1` "Decided this week"** tab |
| `/review/clusters/[id]` | `review/clusters/[id]/page.tsx`, `proposal-actions.tsx`, `review/run-now.tsx` | Weekly grouping proposals the desk approves | **Retire**. Fold the merge into `S-R2` via `C-SHEET-MERGE` (`L-MERGE.desk`) |
| `/review/qualify/[id]` | `review/qualify/[id]/*` | Qualify a group for the committee | **Retire** |
| `/review/working-groups/[id]`, `/working-groups/[id]` | both `page.tsx` | Form or view a working group | **Retire**. The pack uses a crew plus the build team chosen by an admin |
| `/delivery`, `/delivery/[id]` | `delivery/page.tsx`, `start-handover.tsx`, `actions.tsx`, `[id]/page.tsx`, `[id]/delivery-view.tsx` (1,281 lines) | Garage handover pack, track, milestones, Friday check-ins, evidence, completion with sponsor approval, 30- and 90-day measurements with Finance confirmation, write-up | **KEEP-ADMIN, stripped down.** Keep: choose the build team (track and team name), mark shipped, enter the 30- and 90-day measurement, Finance confirms. Retire: handover pack and AI pack draft, pipeline link, phases, milestones, check-ins, write-up and send-back. Raise the Garage pipeline handover with the product lead: the pack is silent on it |
| `/ember` (archive), `/ember/[id]` | `ember/page.tsx`, `[id]/page.tsx`, `issue-view.tsx` | Archive and issue reader | **Fold into `S-WALL.ember`**. Keep `/ember/[id]` as the target of "Read this issue" (undrawn) and drop the archive page |
| `/ember/compose` | `ember/compose/page.tsx`, `actions.tsx` | The chair writes the note; an admin sends | **KEEP-ADMIN** (Ember authoring, `L-WALL.ember` "simple content record per issue") |
| `/journey` | `journey/page.tsx` | "How an idea becomes a One", isometric | **Fold into `S-H4`** (`/how-it-works`) |
| `/constellation` | `constellation/page.tsx`, `sky.tsx` | Office sky screen | **Fold into `S-OFFICE`** (`/display/office`) |
| `/launch` | `launch/page.tsx`, `stage.tsx` | Launch sequence | **Fold into `S-LAUNCH`** (`/display/launch`) |
| `/learning` | `learning/page.tsx`, `learning-actions.tsx` | Learning proposals; a person approves (non-negotiable 5) | **Keep as admin-only**, outside the pack's nav. Retire after launch if unused |
| `/learning/committee` | `learning/committee/page.tsx` | Scorecard and scoring-band proposals from committee decisions | **Retire** (scoring is gone) |
| `/lenses` | `lenses/page.tsx`, `rebuild.tsx` | Counts by LOB and role for committees | **Keep as admin-only** or retire; not needed for launch |
| `/reports` | `reports/page.tsx` | Fairness and calibration of committee scoring | **Retire** |
| `/my-ideas/lens` | `my-ideas/lens/page.tsx` | Personal "lens" numbers | **Retire** |
| `/my-team` | `my-team/page.tsx` | Manager's view of direct reports (DEC-079) | **Retire**. The pack has no manager view, and `comms_prefs.manager_notes` goes with it. Raise with the product lead |
| `/my-ideas/showcase` | `my-ideas/showcase/page.tsx`, `showcase-form.tsx` | A One writes their Showcase brief | **Keep** (linked from `S-ONE` "Your Showcase brief"; undrawn) |
| `/ones/leaderboard` | `ones/leaderboard/page.tsx` | Ones by tier, then impact | **Keep** (linked from `S-ONE` and `S-WALL`; undrawn; `L-ONES.open` default ordering matches) |
| `/ones/console` | `ones/console/page.tsx`, `console-view.tsx` (771 lines) | Propose, decide and carry out Ones; awards; measures; screen mode; announce | **KEEP-ADMIN, stripped down**: approve proposed briefs (`L-ONES/5`), tier rules (`L-ONES.open`), glow-up messages. **Raise** the proposal and vote flow before retiring it: in the pack a person becomes a One when measured impact is confirmed (`L-ONES/1`) |
| `/ones/showcase/[id]` | `ones/showcase/[id]/page.tsx` | Printable brief for the committee | **Keep as admin-only** |
| `/ones/write/[id]` | `ones/write/[id]/*` | Invited colleague, CEO or committee writes a glow-up message | **Keep** (feeds `S-ONE` "Messages for you") |
| `/privacy-notice` | `privacy-notice/page.tsx`, `accept.tsx` | Notice to accept before the first use (§9.1 launch gate) | **Keep** (not in the pack). It must keep the share intent so the person still "lands in the box" (`L-AUTH/4`). Raise with Legal and the product lead |
| `/share/examples/[slug]` | `share/examples/[slug]/page.tsx` | "What good looks like" per canvas section | **Retire** |
| `/share/[id]/done` | `done/page.tsx` + `scan-status.tsx`, `crew.tsx`, `follow-up.tsx` | Post-submit scan, confirm, crew | **Retire as a route**. Its behaviour moves to `S-05` (before submit) and to `S-06` "Just shared" |
| `/signed-out` | `signed-out/page.tsx` | "You have signed out" | **Fold into `S-01`** (Landing) or `S-02` |

### 2b · Page-specific API handlers (generic APIs skipped)

| Handler family | Suggestion |
|---|---|
| `/api/appeals/*`, `/api/ideas/[id]/disagree`, `/api/reports/[kind]` | **Retire** |
| `/api/committee/{cycles,rounds/*,presentations/*}`, `/api/presentations/*`, `/api/admin/conflicts` | **Retire** |
| `/api/review/{cluster-runs,cluster-proposals/*,qualify/*}`, `/api/working-groups/[id]` | **Retire**. The desk merge is new (`POST /desk/ideas/:id/merge`) |
| `/api/review/items*`, `/api/review/items/[id]/action` | **Rewrite** for `S-R1`/`S-R2` (`A-API` desk endpoints) |
| `/api/review/desk-decisions`, `/api/review/items/[id]/veto` | **Rewrite** as `/committee` + `/decisions/:id/{extend,reverse}` |
| `/api/ideas/[id]/answer` | **Rewrite** for question sets (`S-R3`) |
| `/api/submissions/*` (incl. `scan-status`, `scan-events`, `scan-choice`, `confirm-card`, `choose`, `submit`) | **Rewrite** as `/drafts/*`. Keep the `attachments*` and `voice*` handlers and the SSE pattern |
| `/api/canvas/config` | **Retire**. Replace with `/config/uploads` and the promises config |
| `/api/me/comms-prefs`, `/api/me/points` | **Reuse** for `S-H6`; widen the prefs to Teams, Email and Reminders |
| `/api/me/one/*` | **Reuse** for `S-ONE` |
| `/api/me/lens`, `/api/me/team`, `/api/lenses/*` | **Retire** (or keep `lenses` admin-only) |
| `/api/ones/proposals/*`, `/api/ones/{announce,awards,measures}` | **KEEP-ADMIN** until the One-hood rule is settled |
| `/api/ones/{constellation,screen-mode}` | **Fold into `S-OFFICE`** (`GET /display/office`) |
| `/api/ones/leaderboard`, `/api/ones/[id]/showcase` | **Keep** |
| `/api/delivery/*` | **KEEP-ADMIN**, subset: `route.ts` (start), `phase` / `complete` / `approve-completion` (mark shipped), `measurements/[mark]{,/finance,/confirm}`. Retire `pack*`, `writeup*`, `checkin`, `evidence*`, `link`, `milestones*`, `send-back` |
| `/api/ember/*` | **Keep**: `current` / `[id]` for the Wall; `drafts`, `note`, `ready`, `send` for admin |
| `/api/learning/*` | **Keep admin-only** (`learning`) / **retire** (`learning/committee`, `role-themes`) |
| `/api/wall` | **Rewrite** into `/wall/{kindling,just-in,ones,impact,ember}` |
| `/api/inbox`, `/api/inbox/[id]/read` | **Rewrite** with tabs, kinds and archive |

---

## Table 3 · Tests tied to retired or rewritten pages

Fates: **dies** = delete with the page. **rewrite** = same journey, new screen. **keep** = page-independent or admin that stays.

| Screen / area | Test file (test) | Fate |
|---|---|---|
| **S-01 Landing** | `e2e/smoke.spec.ts` "signed-out visitors land on sign in, which is keyboard reachable and passes axe" | rewrite (they land on Landing) |
| **S-02 Sign in** | `e2e/shell.spec.ts` "axe … public pages: sign in and signed out"; "first sign-in shows the privacy notice, then the shell"; "sign out ends the session" | rewrite |
| | `e2e/helpers.ts` `signIn()` (drives mock OIDC from `/sign-in`): **every** spec depends on it | keep working: SSO must stay a route |
| | `tests/unit/session.test.ts` | keep (adjust if the absolute cap moves to 8 h) |
| **Shell (C-SIDEBAR, C-PHONE-TABS)** | `e2e/shell.spec.ts` "navigation by role (AT-B2-06)" per persona; "every navigation item works by keyboard with a visible focus ring"; "axe on the shell pages" (path lists include `/review`, `/committee`, `/delivery`, `/lenses`); "people without the role are sent home from Review and Admin" | rewrite |
| | `e2e/shell.spec.ts` "My ideas links to committee decisions and appeals while the committee flow or appeals run" | dies |
| | `e2e/helpers.ts` `navLabels()` | rewrite |
| | `tests/unit/rbac.test.ts` "navigation and pages (AT-B2-06)" block (labels Share an idea, Messages, Review, Committee, Desk decisions, Ones, Delivery, Lenses; `/review` page checks; `committee.flow` `when_on`/`when_off`) | rewrite. Endpoint tests for retired APIs die |
| | `tests/unit/killswitch-routes.test.ts` (BANNERS and route → switch map, incl. `appeals.filing`, `committee.flow`, `clusters.batch`) | rewrite |
| **S-03 Home** | `e2e/demo-tour.spec.ts` "1-3: home carousel, share an idea, Find your crew" | rewrite |
| **S-04 / S-04B Tell it** | `e2e/canvas.spec.ts`: all 11 tests (quick capture one box; category optional; keyboard-mic tip; full canvas six sections; required-field errors; personal data highlighted and autosave paused; autosave draft; strength meter; keyboard completion; 200% zoom; research files) | dies (zoom, keyboard and axe checks to be re-written for the new screen) |
| | `e2e/helpers.ts` `confirmQuickCapture()` | dies |
| | `tests/unit/canvas.test.ts` (`lib/canvas/model`, `lib/canvas/rules`) | dies with `lib/canvas/*` |
| | `e2e/voice.spec.ts` "the microphone is allowed on the share pages only" | keep (paths `/share/*` survive) |
| | `e2e/voice.spec.ts` "voice notes off: coming soon…", "voice notes on: record by keyboard…" | rewrite (`C-PROMPT.voice`, 3-minute clip, live transcript) |
| | `tests/unit/voice.test.ts` (imports `app/share/[id]/voice-logic` and `voice-recorder`) | rewrite / move with the components |
| | `tests/unit/security-headers.test.ts` | keep. Update the non-share path list (`/review/x`, `/launch`) |
| **S-05 Check it** | `e2e/scan.spec.ts` "the waiting screen ends with the summary and suggestions"; "an IT issue gets a redirect card…"; "an investor block can be contested…" | dies |
| | `e2e/scan-live.spec.ts` "the waiting screen follows the scan over server-sent events" | dies (rewrite as a draft-stream test) |
| | `e2e/crew.spec.ts` "a colleague's idea shows as a card with nothing of theirs on it; teaming up (AT-B5-05, AT-B5-06)" | rewrite (`C-SIMGRID` + `C-SHEET-TEAMUP`). The assertion "nothing of theirs on it" conflicts with the pack |
| **S-06 / S-09 Idea page** | `e2e/public.spec.ts` "a reviewed idea reaches the wall, My ideas and its page, each as §3.1 allows (AT-B7-01..05)" | rewrite |
| | `e2e/demo-tour.spec.ts` "5-6: the wall and an idea page" | rewrite |
| | `e2e/desk.spec.ts` "disagree, then the core committee reconsiders the desk's decision" | dies |
| **S-07 My ideas** | `e2e/lens.spec.ts` "anyone opens their own lens from My ideas" | dies |
| | `e2e/ember.spec.ts` "My ideas shows your own points, and the journey page explains the steps" | rewrite (points → `S-H6`, journey → `S-H4`) |
| | `e2e/demo-tour.spec.ts` "4: My ideas as a One: the tier dashboard and the glow-up" | rewrite → `S-ONE` |
| **S-H5 Inbox** | `e2e/inbox.spec.ts` "the submitted message lands in Messages and opens by keyboard" | rewrite |
| **S-WALL** | `e2e/ember.spec.ts` "everyone reads The Ember's archive from the footer; only the chair and admins write it" | rewrite (Ember on the Wall; compose stays admin) |
| | `e2e/ones.spec.ts` "the Showcase brief, the leaderboard and the office screen" (visits `/`, `/wall`, `/constellation`) | rewrite |
| **S-R1 / S-R2 Review desk** | `e2e/review.spec.ts` "a reviewer opens an item, sees every panel and saves a decision (AT-B6-02)" | dies (rewrite for Pick, Not now, Not picked) |
| | `e2e/clusters.spec.ts` "the desk runs the weekly grouping and approves a proposal" + `e2e/proposals.ts` | dies |
| | `e2e/demo-tour.spec.ts` "7-8: the review desk and desk decisions" | rewrite |
| **S-R4 Committee** | `e2e/committee.spec.ts` "from a group of ideas to a committee decision" | dies |
| | `e2e/appeals.spec.ts` "a declined group is appealed and the panel records the outcome" | dies |
| | `e2e/committee-helpers.ts` (shared by committee and appeals) | dies |
| | `e2e/desk.spec.ts` (veto path) | dies (see S-06) |
| **S-ONE** | `e2e/ones.spec.ts` "the new One sees their dashboard, chooses a number and writes a brief"; "a tier up plays the glow-up once, with the committee's message" | rewrite (route `/one`) |
| | `e2e/ones.spec.ts` "the committee proposes, the chair approves and the admin carries it out" | dies if One-hood becomes automatic; else admin |
| | `e2e/ones.spec.ts` "nobody outside the committee, the CEO or admin opens the console" | keep (admin) |
| | `tests/unit/ones.test.ts` (`lib/measures`, `lib/spark`) | keep |
| | `tests/unit/tier-colour-text.test.ts` (scans CSS for tier colours) | rewrite against `1pc-handoff/01-foundations/tokens.css` |
| **S-OFFICE** | `e2e/demo-tour.spec.ts` "10-12: leaderboard, manager view and the office screen" | rewrite (manager view dies) |
| **S-LAUNCH** | `e2e/launch.spec.ts` "the admin runs the launch screen to the invitation and back"; "nobody else can open the launch screen"; "the full timed sequence … plays every step in order" | rewrite (route `/display/launch`, display-operator role); the timed-sequence logic survives |
| **Admin (kept)** | `e2e/delivery.spec.ts` (3 tests: admin sees Delivery, Lenses and Learning; employee sees only own; not-yours not found) | rewrite to the reduced admin |
| | `e2e/demo-tour.spec.ts` "9: the console's three waiting states"; "13-14: the launch screen and the kill switches"; "15-21: delivery, lenses and learning" | rewrite or die with the scope cut |
| | `e2e/shell.spec.ts` "an admin can switch a feature off and on with a reason" | keep |
| | `e2e/ember.spec.ts` "an admin opens Write The Ember" | keep |
| **Not page-tied (keep)** | `tests/unit/{codes,config,crypto,dates-timezone,log,pattern-vectors,patterns-sync,patterns,proxy-matcher,restore}.test.ts`; `e2e/smoke.spec.ts` health and email-marks tests; `e2e/switch-lock.ts` | keep. `restore.test.ts` changes if `see_restored_values` is narrowed to the sharer |

`e2e/demo-tour.spec.ts` as a whole walks the old product's demo. Plan to replace it with a tour of the pack's journeys (`03-journeys/J-*`).

---

## Cross-cutting notes for the build plan

1. **Route moves:**
   - `/` becomes Landing, and Home moves to `/home`.
   - `/review` → `/desk`, and `/review/[id]` → `/desk/ideas/:id`. A reviewer opening `/ideas/:id` lands on `S-R2`.
   - `/launch` → `/display/launch`, and `/constellation` → `/display/office`.
   - Add redirects from the old paths. The QR codes and the email templates link into the app (`comms/templates/` in the company repo).
2. **`policy/rbac.yaml` is the source of truth.** Its `pages:` (line 244) and `navigation:` (line 266) blocks generate `lib/rbac.json`. Change them there, add `display_operator`, and regenerate.
3. **Layout.** Split `app/layout.tsx` into route groups:
   - `(public)`: Landing and Sign in, with no sidebar.
   - `(app)`: sidebar plus tabs.
   - `(task)`: task bar plus the phone dock.
   - `(display)`: no chrome.
4. **Kill switches.** Today's model is a banner per paused feature (`components/banners.tsx`, `BANNERS`). The pack says to hide the feature's entry point and leave everything else working (`L-AUDIT.flags`). Non-negotiable 9 still applies on the server.
5. **Vocabulary changes.** Write a `DEC-` entry to record these changes against `CLAUDE.md` "Words on screen" and DEC-034 / DEC-038:
   - "Share an idea" → "Share a problem".
   - "Messages" → "Inbox".
   - "1% Club core committee" → "Ones Committee".
   - Stages: Shared, Checked and matched, Reviewed, Built, Shipped.
   - Statuses: With the review desk, Needs you, Not now, Not picked.
6. **Styles.** `globals.css`, `offer.css` and `ds-app.css` (4,536 lines, the OFFER theme from DEC-101) give way to `1pc-handoff/01-foundations/tokens.css`. The exceptions are the two display screens, which keep `reference/css/boards/Office.css` and `Launch.css`. GSAP is accepted (DEC-100) but not yet in `package.json`.
