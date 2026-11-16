---
id: A-API
title: API shapes each screen expects
rev: 1
status: baseline
source: reference/copy/
depends_on: [E-ENTITIES, E-ENUMS]
last_delta: none
---

# API

What the front end needs from the back end, grouped by resource. Paths are proposed; if the repo's `contracts/` already has an endpoint that returns the same data, use it and record the mapping in `REPO-MAPPING.md`. What matters here is the data, the operations and the rules, not the URLs.

## `A-API.conventions` Conventions

1. JSON over HTTPS. Auth by session cookie. Every route checks permission on the server (`L-AUDIT.permissions`).
2. Errors: `{ error: { code: string, message: string, field?: string, retry_after?: number } }`. `message` is ready to show under the field named by `field`. Codes used by the UI are listed with each operation.
3. Every write that creates something takes an `Idempotency-Key` header; repeating the call returns the first result.
4. Lists return `{ items, total, counts?, next? }`. `counts` carries the per-filter or per-tab counts the UI shows.
5. Text that others can see is always masked by the server. Unmasked text is returned only to its owner, only on draft and own-idea reads.
6. Dates the UI shows as sentences ("by Friday 20 November", "3 days left") are computed on the server and returned both raw (`due_at`) and as a label, so every screen agrees.
7. Live updates: one server-sent-events (or WebSocket) channel per signed-in person, `A-API.events`.

## `A-API.auth` Sign-in

| Operation | Request | Response | Errors |
|---|---|---|---|
| `POST /auth/sso/start` | `{ intent?: { to: string, draft_id?: string, step?: string } }` | `{ redirect_url }` or `{ signed_in: true, to }` | `sso_unavailable` |
| `POST /auth/code/send` | `{ email, intent? }` | `{ sent_to, valid_minutes: 10, resend_in_seconds: 45 }` | `not_work_email`, `rate_limited`, `account_disabled` |
| `POST /auth/code/verify` | `{ email, code }` | `{ signed_in: true, to }` | `wrong_code` with `{ tries_left }`, `code_expired` (a new one was sent) |
| `GET /auth/session` | | `{ person: Person, expires_at, intent? }` | `expired` with `{ draft?: { id, title, saved_at, saved_on, step } }` |
| `POST /auth/sign-out` | | `204` | |

## `A-API.me` The signed-in person and the shell

| Operation | Response |
|---|---|
| `GET /me` | `Person` with `points` and `settings` |
| `PATCH /me/settings` | body: any of `settings`; returns `settings` |
| `GET /me/shell` | `{ inbox_unread: number, drafts: { id, title, saved_label }[2], ideas: { id, title, status_dot }[3], desk?: { waiting: {...}[3] }, committee?: { closing: {...}[3] } }` for the sidebar and tab bar. Also pushed over `A-API.events` |

`A-API.inbox-count`, `A-API.my-drafts` and the sidebar's top-three ideas are all `GET /me/shell`.

## `A-API.home` Home

`GET /home` → `{ first_visit: boolean, needs_you: { total, top: InboxItem[2] }, ideas: { total, top: Idea[3] }, crew: { total, top: CrewCard[3] }, ones: OnePost[], ways: { arrived: number } }`

## `A-API.drafts` Drafts

| Operation | Request | Response / notes |
|---|---|---|
| `POST /drafts` | `{ text?, files?, channel }` | `Draft`. Created on the first pause in typing, or by sending from Home |
| `GET /drafts/:id` | | `Draft` (owner only) |
| `GET /drafts?recent=1` | | Drafts for the "existing draft" prompt and lists |
| `POST /drafts/:id/messages` | `{ text, via, files? }` | `202` + the run id; parts arrive on `A-API.draft-stream` |
| `PATCH /drafts/:id/messages/:mid` | `{ text }` | Re-runs the draft |
| `PATCH /drafts/:id/parts/:part` | `{ value }` | Sets and pins the part (`L-DRAFT.pins`); `{ pinned: false }` unpins and re-suggests |
| `PATCH /drafts/:id/sorting` | `{ affects?, kind?, area?, brings? }` or `{ confirm: true }` | `Sorting`. Changing a field marks it `changed`; `confirm` marks untouched ones `confirmed` |
| `POST /drafts/:id/hidden/:hid/show` | `{ reason }` | `HiddenDetail`. Errors: `reason_required` |
| `POST /drafts/:id/hidden/:hid/hide` | | `HiddenDetail` |
| `PUT /drafts/:id/fix` | `Fix` fields | `Fix` with `ready_count`. Amounts are parsed from any Indian form and returned normalised in `Range.text` |
| `DELETE /drafts/:id/fix` | | |
| `PUT /drafts/:id/helpers` | `{ picks, text? }` | |
| `PATCH /drafts/:id` | `{ step }` | Saves where the person is |
| `POST /drafts/:id/voice` | audio stream | Streams interim and final transcript; audio is not stored |
| `POST /drafts/:id/merge-request` | `{ other_idea_id, note }` | `{ state: 'waiting' }`. Errors: `note_too_short` (30) |
| `DELETE /drafts/:id/merge-request` | | Withdraws |
| `POST /drafts/:id/submit` | `{ declaration_version }` | `{ idea_id }`. Errors: `sorting_unconfirmed` (field `sorting`), `file_blocked` (field = file id), `merge_waiting`, `not_ready`, `offline_queued` (client-side) |
| `DELETE /drafts/:id` | | Archives |

## `A-API.draft-stream` The draft as it builds

`GET /drafts/:id/stream` (server-sent events). One run per message.

| Event | Data |
|---|---|
| `run` | `{ run_id, parts: { key, mean_ms }[] }` at the start: the means the loader uses (`C-DRAFT-LOADER.maths`) |
| `hidden` | `{ spans: HiddenSpan[], details: HiddenDetail[] }` first, before any part |
| `part` | `{ key, state: 'filled'|'failed', value, why?, source_quote?, took_ms }` once per part, in whatever order they finish |
| `receipt` | `{ lines: string[], suggestions: string[] }` |
| `done` | `{ ready: boolean }` |

The front end computes the bar from `mean_ms` and elapsed time; the server does not send percentages.

## `A-API.files` Files and links

| Operation | Notes |
|---|---|
| `POST /files` (multipart, with `draft_id`, `idea_id` or `answer_id`) | Returns `FileItem` in `uploading`/`checking`; state changes arrive on `A-API.events`. Errors: `too_big` with `{ limit_mb }`, `type_not_allowed`, `locked` |
| `POST /links` `{ url, … }` | Returns `FileItem` with `link_scope` and reachability. Error: `not_a_link` |
| `POST /files/:id/hide` | "Hide it for me": produces the masked copy; returns the item as `hidden_checked` with `hidden_note` |
| `POST /files/:id/retry`, `DELETE /files/:id` | |
| `GET /files/:id/view` | The checked (masked) copy only |
| `GET /config/uploads` | `{ limit_mb, types[], help_text }` so the help line is rendered from configuration |

## `A-API.ideas` Ideas

| Operation | Notes |
|---|---|
| `GET /ideas/:id` | `Idea`, shaped by who asks (`P-PRODUCT.privacy`): public fields for anyone; private fields for sharer, crew, reviewers, committee |
| `GET /ideas/:id/preview` (`A-API.idea-preview`) | `IdeaPreview`; `compare` only for reviewers |
| `GET /me/ideas` (`A-API.my-ideas`) | Query: `list=yours|teamed`, `filter`, `sort=latest|shared|stage`, `q`. Returns rows with `next_step`, plus `counts` per filter and per list, and for a search `{ sentence, matched_on, closest }` |
| `PATCH /ideas/:id` | The edit page's save: any of title, summary, often, sorting, fix, helpers. Returns the new version. Errors: `edit_window_closed` with `{ opened_by_desk_at }` |
| `POST /ideas/:id/withdraw` `{ reason? }`, `POST /ideas/:id/restore` | `Idea` |
| `GET /ideas/:id/versions` | For "Draft history" |
| `GET /ideas/:id/similar` | `SimilarMatch[]` |
| `POST /ideas/:id/join-build` | "Ask to join the build team" |

## `A-API.questions` Questions and answers

| Operation | Who | Notes |
|---|---|---|
| `GET /desk/ideas/:id/suggested-questions` | Reviewer | `{ part, text }[]` |
| `POST /desk/ideas/:id/question-sets` `{ questions: { part, text }[], time_to_answer }` | Reviewer | Sends. Returns `QuestionSet` with `due_at` and its label |
| `POST /question-sets/:id/extend` `{ days: 2 }`, `POST /question-sets/:id/remind` | Reviewer | |
| `GET /ideas/:id/question-set` | Sharer | The open set; marks it seen |
| `PUT /questions/:id/answer` `{ text, file_ids? }` | Sharer | Saves a draft answer |
| `POST /question-sets/:id/send` | Sharer | Sends all saved answers. Error: `nothing_answered` |

## `A-API.desk` Review desk

| Operation | Notes |
|---|---|
| `GET /desk` | Query: `tab`, `sort=time_left|decide_by|area`, `q`. Rows carry questions state, time-left label and variant, decide-by, action; plus tab `counts` and the summary sentence |
| `POST /desk/ideas/:id/open` | Marks opened (idempotent) |
| `GET /desk/ideas/:id` | The reviewer's view of the idea: everything in `S-R2.left` |
| `PUT /desk/ideas/:id/worth` `{ worth, kind?, area?, note? }` | `L-WORTH` |
| `POST /desk/ideas/:id/decision` `{ choice, reason, joined_with?, return_in? }` | Returns `Decision`. Errors: `choice_required`, `reason_too_short` (30) |
| `POST /desk/ideas/:id/merge` `{ other_idea_id, lead: 'this'|'other', team_up: boolean, note }` | Returns `Merge`. Error: `note_too_short` (20) |
| `GET /desk/ideas/:id/audio` | `{ url, total_seconds, chapters: { part, at }[] }` (`L-LISTEN`) |

## `A-API.committee` Ones Committee

| Operation | Notes |
|---|---|
| `GET /committee` | Query: `tab=window|reversed|expired`, `sort=closing|decided|area`. Rows: idea, decision with reason, window; `counts`; the summary sentence |
| `POST /decisions/:id/extend` | +30 days. Error: `at_limit` |
| `POST /decisions/:id/reverse` `{ to, note, return_in? }` | Final. Errors: `to_required`, `note_too_short` (30), `window_closed`, `already_reversed` |

## `A-API.team-up` Team up

| Operation | Notes |
|---|---|
| `GET /ideas/:id/team-up/draft-note` | The pre-filled note and the person's own ideas that can be brought |
| `POST /ideas/:id/team-up` `{ note, brought_idea_ids: string[] }` | Returns `TeamUpRequest`. Errors: `note_too_short` (30), `already_requested`, `already_on_crew`, `idea_closed` |
| `DELETE /team-up/:id` | Withdraw |
| `POST /team-up/:id/answer` `{ answer: 'merge'|'team_only'|'decline', reason? }` | Lead only |
| `GET /crew` | Query: filters of `L-CREW/5`. Returns `CrewCard[]`, filter `counts`, `{ joined, pending, passed }` |
| `POST /crew/pass` `{ idea_id }`, `POST /crew/pass/undo`, `POST /crew/pass/reset` | |

## `A-API.inbox` Inbox and conversations

| Operation | Notes |
|---|---|
| `GET /inbox` | Query: `tab=all|needs_you|unread|archived`. Items grouped by the client; `counts` per tab; `unread` total |
| `POST /inbox/:id/read`, `POST /inbox/:id/archive` | Error: `needs_you` on archiving an open ask |
| `GET /ideas/:id/conversation` | `Conversation` |
| `POST /ideas/:id/conversation/messages` `{ text, file_ids?, mentions? }` | Error: `empty_message` |

## `A-API.wall` Wall, Ones, impact

| Operation | Notes |
|---|---|
| `GET /wall/kindling?kind=` | `WallStage[3]` |
| `GET /wall/just-in?kind=&sort=popular|newest|crew|ones&limit=&offset=` | `JustInRow[]`, `total` |
| `GET /wall/ones` (`A-API.ones`) | `OneCard[]` |
| `GET /wall/impact` | `{ totals: ImpactTotals, live: LiveFix[] }` |
| `GET /wall/ember` | `EmberIssue[]` |
| `GET /ones/posts` (`A-API.ones-posts`) | `OnePost[]` for Home |
| `GET /one` | The signed-in One's dashboard: `OneCard`, idea, `Impact`, number window, pending tier moment |
| `PUT /one/number` `{ number }` | Errors: `taken` with `{ near: number[] }`, `window_closed`, `out_of_range` |
| `POST /one/brief` `{ text }` | Proposes a new brief |
| `GET /display/office` | Ones with briefs and headline figures, for the display role |

## `A-API.search` Search

Search is part of the list endpoints (`q` on `/me/ideas` and `/desk`). `GET /search/suggest?scope=` returns the filter counts and three example questions for the suggestions panel.

## `A-API.events` Live events (`A-API.idea-events`)

One stream per person. Events carry enough to update a screen in place, or a `refetch` hint.

| Event | Sent when | Updates |
|---|---|---|
| `shell` | Unread count, drafts or top ideas change | Sidebar, tab bar |
| `inbox.item` | A new or changed Inbox item | `S-H5`, Home "Needs you" |
| `idea.changed` `{ id, fields[] }` | Status, stage, opened by desk, questions, answers, decision, reversal, merge, worth revised | `S-06`, `S-09`, `S-R2`, lists |
| `file.state` `{ id, state, … }` | A file finishes uploading or checking | `C-FILE.row` |
| `conversation.message` `{ idea_id, entry }` | A new entry | `S-08`, `S-06` |
| `teamup.changed` | A request is answered or withdrawn | Tiles, cards, `S-H2B` |
| `desk.row` / `committee.row` | A clock crosses a threshold, or a row moves tab | `S-R1`, `S-R4` |

## `A-API.config` Configuration the front end reads

`GET /config` → the values in `P-PRODUCT.promises` that are shown in copy (minimum characters, voice limit, times to answer, review days, window lengths), the sorting lists (`E-ENUMS.sorting`), upload limits, the three placeholders, and feature flags for the person (`L-AUDIT.flags`).
