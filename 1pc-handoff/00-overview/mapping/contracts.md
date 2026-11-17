# 1% Club handoff pack (draft 0) — contracts mapped to the repo

Scope: `1pc-handoff/06-contracts/` (E-ENTITIES, E-ENUMS, A-API) and `1pc-handoff/07-validation/V-FIELDS.md`, compared with `db/migrations/*.sql` (44 files, latest `20261121300110_voice_notes.sql`), `apps/web/src/server/db-types.ts`, the 120 route handlers under `apps/web/src/app/api/**` and `apps/web/src/app/auth/**`, the worker services that own the logic (`services/worker/**`), `contracts/garage/` and the rule files in `seed/company-repo/rules/`.

Worktree read: `/Users/mantri/rome/kfin-ideas-platform/.worktrees/handoff` at `e911de1`. Read-only; nothing was run. All people named in the pack are fictional demo people; none are copied here.

## 0. Findings that sit above the mapping

These are things the mapping cannot settle on its own. Four touch CLAUDE.md non-negotiables, so per CLAUDE.md "Stop and ask the user", they need the product lead's call before any build.

| # | Finding | Pack source | Repo rule it hits | Severity |
|---|---|---|---|---|
| 0.1 | **Personal details are masked and can be un-hidden by the sharer** ("Show it" with a reason). The unmasked value is stored, encrypted, inside the owner's draft. | `L-HIDE.rules/4`, `/6`; `E-ENUMS.hidden`; `A-API.drafts` `…/hidden/:hid/show` | NN4: "Pattern blocks are absolute". `apps/web/src/server/submissions.ts` refuses to store a blocking match even encrypted (`personalDataGuard`). | Critical: ask |
| 0.2 | **Similar-idea previews and crew cards show the other idea's lead name, crew names and faces, and "the problem, in their words" (a one-sentence masked quote)** to any employee. Crew members see another person's files. | `L-SIMILAR/10`, `L-CREW/4`, `E-ENTITIES.crew` `IdeaPreview`, `P-PRODUCT.privacy` | NN7: "Submitters never see another person's raw text, files or name. Match cards show `neutral_summary`, area tag, stage and count only". Also the pack contradicts itself: `P-PRODUCT.privacy` says Everyone and Crew never see own words. | Critical: ask |
| 0.3 | **Links are checked for reachability** (internal/external, `ok`/`unreachable`). | `L-HIDE.files/7`, `E-ENUMS.file`, `A-API.files` `POST /links`, `V-FIELDS.checkit/7` | NN8: "Links are never fetched". A reachability probe is a server-side request to a person-supplied URL (SSRF exposure). | Critical: ask. Default to propose: classify by domain only, no network call; drop `unreachable`. |
| 0.4 | **Voice audio is streamed and not stored; the phone S3 flag can start with voice.** | `A-API.drafts` `POST /drafts/:id/voice`, `P-DECISIONS.open/11`, `P-DECISIONS.experiments` S3 | Resolved by DEC-108 (17 Nov): `capture.voice` and `speech.hosted` are on at launch through Sarvam, with the DPO's approval; raw voice goes to Sarvam untagged as NN2's stated exception, and every transcript is masked as it returns (seed reasons updated in `20261122100500_voice_on_reasons.sql`, BLD-A185). | Important: the switch stays off; the contract can be built behind it. |
| 0.5 | **The review desk decides Pick / Not now / Not picked on the idea; the committee only reverses.** The repo's desk "decide" is a tag-and-group step; picking is a cluster-level core-committee vote after scoring and presentation. | `L-DECIDE`, `L-COMMITTEE`, `P-DECISIONS.taken/3–4` | DEC-088 and the whole §4.5–§4.12 stack (qualify, scoring, presentations, appeals). | Decided by the pack (supersession); listed so nobody re-uses `decisions`. |
| 0.6 | **Email one-time code sign-in** next to SSO. | `L-AUTH.rules/2–3`, `A-API.auth` | Entra OIDC only today (`apps/web/src/server/auth/oidc.ts`); a second auth route needs IT/InfoSec. | Important |
| 0.7 | **The company repo (OKF) is not mentioned anywhere in the pack.** The repo writer, the indexer and match retrieval all read it. | none | CLAUDE.md "Two repos"; §2.7 write path | Important: decide whether idea files keep being written (recommended: yes, masked summary only, new header schema). |
| 0.8 | `apps/web/src/server/db-types.ts` is **stale**: it types 31 of the 72 tables (nothing after `20261112000100_comms_v1.sql`; no `ones`, `deliveries`, `decisions`, `voice_notes`, `idea_questions`, `idea_stage_history`…). The web app reaches the rest through the worker's `/internal/*`. | n/a | Kysely codegen | Regenerate after the cut-over migration; do not hand-edit. |
| 0.9 | **There is no Postgres row-level security anywhere.** "Database only" (NN6) is enforced by per-service role grants: `20261110000300_service_roles.sql` plus later `REVOKE … FROM ideas_web_svc`, pinned by `services/worker/tests/test_b4_service_roles.py` (`HIDDEN_FROM_WEB`). | n/a | NN6 | See §6. |

---

## 1. Entities

State key: **exists, matches** / **exists, differs** / **missing**. "Old rule" marks a column whose meaning comes from the old product and must not carry over.

| E- entity | Existing table(s) | State | Field-level differences | Recommendation |
|---|---|---|---|---|
| `E-ENTITIES.person` `Person` | `users` (`20261108000200`, `20261109000100`), `comms_prefs`, `role_grants`, `contributor_map`, `sessions` | exists, differs | **Missing:** `first_name`, `initials`, `area` (department from the configured list), `city` (nearest: `users.location`), `tier` 1–7 for **every** employee (repo: only Ones have a tier, `services/worker/ones/tiers.py`), `settings` (only `show_name_on_wall` exists, as `comms_prefs.public_name_consent`; `teams`, `email`, `reminders`, `shortcut_p`, `sidebar_folded` missing). **Different meaning:** `roles` (see §2.12); `area` vs `users.lob_id` / `hr_department` (LOB taxonomy, not the pack's area list). **Extra:** `emp_id_hash`, `entra_oid`, `lob_id`, `role_title`, `role_family`, `manager_user_id`, `staff_code` (`REV-NNNN`), `source`, `hr_department`, `hr_job_title`, `last_seen_in_hr_at`, `last_sign_in_at`. | **Alter** `users`: add `first_name`, `area`, `city`, `tier smallint NOT NULL DEFAULT 1`; derive `initials` in the view. Keep HR and identity columns (they serve L-AUTH/6). **New** `person_settings` (user_id PK, six booleans) or extend `comms_prefs` and drop `routine`/`manager_notes` (old rules: digest and manager notes have no place). |
| `PersonRef` | computed | missing | `role_label` ("from the review desk") is new. Domain rows hold `contributor_code` (pseudonym, no FK, so deleting the `contributor_map` row anonymises everywhere). | Keep `contributor_code` as the person key on every new domain row (crew, team-up, answers, messages) so DPDPA erasure still works; resolve to `PersonRef` in the server for viewers allowed to see names. Staff actions keep `users.id`. |
| `Person.one` | `ones`, `one_number_history`, `one_legend_numbers`, `one_glow_ups`, `one_showcase_briefs` | exists, differs | `number` ✓ (1–999), `since` = `inducted_at` ✓, `number_locked_at` = `swap_until` ✓ (30 days), `brief` = `brief_encrypted` (+`brief_approved_at`). `flag: founding\|one` ← `way_in` (`founding` → founding; `accepted_idea` → one; `sponsored` has no home). **Extra (old rules):** `induction_no`, `status active/retired`, `retired_at`, `announced_at`, `title_encrypted`; 6-month rest of freed numbers and legend numbers (`ones/numbers.py`). **Meaning differs:** a One is made automatically when a credited idea ships and impact is confirmed (`L-ONES.rules/1`), not by committee proposal (`one_proposals.kind='include'`). | **Alter** `ones`: add `flag` (or generated from `way_in`), drop `sponsored` from the CHECK, keep `measures` (it already holds time/money/effort/scale = pack `Impact`). Ask the product lead whether the 6-month rest and legend numbers survive; the pack only says "any free number". |
| `Person.points` | `points_ledger` (append-only, trigger + TRUNCATE revoke) | exists, matches | Private to the person ✓. Event names are old (`submission`, `strong_canvas`, `accepted_into_cluster`, `shortlisted`, `presented`, `working_group_member_shipped`; `services/worker/points/ledger.py`, `rules/points.md`). | **Reuse** unchanged; rewrite `rules/points.md` events for the new lifecycle (`L-ONES.open`: configurable table). |
| `E-ENTITIES.draft` `Draft` | `ideas` with `stage='draft'` (`draft_encrypted` = whole canvas JSON, `draft_expires_at`, `capture_mode quick/full`), `attachments`, `voice_notes`, `pseudonym_vault` scope `DRAFT-<uuid>` | exists, differs | **Missing:** `channel` (`web/voice/email/teams`), `origin` (forwarded email subject), `messages[]`, `parts` with `state/pinned/why/source_quote/mean_ms`, `hidden[]`, `sorting` with per-field source and `confirmed`, `fix` (structured), `helpers`, `merge_request`, `step`, `saved_on {device, this_device}`, `ready`, `char_count`, `receipt`, `suggestions`. **Extra (old rules):** `capture_mode` (quick/full canvas), the canvas sections `ecosystem.solved_elsewhere/references/our_advantage`, `value.play`, `value.category` (incl. `both`), yearly ₹ estimates, `visibility committee`, three-part `declarations`, `strength` meter. **Retention differs:** old purges drafts after 30 days (`jobs/handlers.py` `drafts.purge`, deletes); pack archives and never deletes silently (`P-PRODUCT.promises`). | **Keep the `ideas` row as the anchor** (one row from draft to shipped keeps the IDEA- number on withdraw/restore, the vault scope and file FKs). **New** child tables: `idea_messages`, `idea_parts`, `hidden_details`, `merge_requests` (or `teamup_requests` with `kind`). Drop `draft_encrypted`/`capture_mode` after cut-over. Replace `drafts.purge` with an archive job. |
| `Message` | none (`ideas.raw_encrypted` is one blob, cleared after the scan, BLD-074) | missing | `id, text, lang, at, device, via, files, spans` all new. **Retention differs:** pack keeps the raw words with the idea (`P-DECISIONS.open/11`). | **New** `idea_messages` (idea_uuid, seq, via, device, lang, `text_sealed` (owner, unmasked, encrypted), `text_masked` (tagged, encrypted), `spans jsonb` (start, end, kind; never values), created_at, edited_at). Worker-only for `text_sealed` (§6). |
| `Part<T>` | `ideas.canvas` jsonb with `provenance[path]` (`submitter/suggested/accepted/reviewer`) and `evidence` quotes (DEC-095) | exists, differs | `state` (`waiting/updating/filled/pinned/failed`), `why`, `mean_ms` new. `source_quote` ≈ the DEC-095 evidence quotes ✓ (keep that rule). Part keys differ (§2.5). | **New** `idea_parts` (idea_uuid, key, value jsonb tagged, state, pinned, why_tagged, source_quote_tagged, run_id, took_ms). `mean_ms` from a rolling stat per part key (new `draft_runs` or aggregate of `took_ms`); `llm_calls.latency_ms` is per agent, not per part. |
| `HiddenSpan`, `HiddenDetail` | `pseudonym_vault` (tag → encrypted value, `type`, scopes `IDEA-…` / `DRAFT-…`), `vault_counters`, `scans.overrides.not_personal_data` | exists, differs | Vault holds the value ✓ and is worker-only ✓. **Differs:** display mask "Folio ••••89" vs `[[TAG_n]]`; `state hidden/shown`, `reason`, `shown_at` new; span positions new. Old contest flow (`scan-choice not_personal_data`) applies only to gatekeeper blocks, never to pattern hits. | **Reuse** the vault for the values (NN6). **New** `hidden_details` (id, idea_uuid, vault_tag, kind, masked, state, reason, shown_by, shown_at) — never the value. Blocked on finding 0.1. |
| `Sorting`, `Choice<T>` | `ideas.kind`, `category`, `play`, `area_ids`, `lobs`, `roles_affected`, `canvas.who.segments`, `canvas.provenance` | exists, differs | `affects` ← `who.segments` (different list); `area` single value from a new list vs `area_ids[]` (AREA- themes set by the reviewer) — different meaning; `brings[]` ← `category` (single); `confirmed` and per-field `source` new (old provenance values differ, §2.4). | **Alter** `ideas`: add `affects text[]`, `area text`, `brings text[]`, `sorting_sources jsonb`, `sorting_confirmed_at`. Retire `category`, `play`, `scope`, `lobs`, `systems`, `roles_affected` (keep `systems`/`roles_affected` only if matching still needs them). |
| `Fix`, `Worth`, `Range` | `canvas.solution {approach, needs, risks}`, `canvas.value.estimate {hours_saved_per_month, inr_saved_per_year, inr_revenue_one_time, inr_revenue_per_year, clients_who_would_pay, note}`, `canvas.value.basis`, `canvas.ecosystem.solved_elsewhere`; reviewer side: `corrections` (category/play), `impact_estimates` (cluster) | exists, differs | `how/needs/risks` ✓. `solved_already` values ✓ identical. **Differs:** worth is **per month** with ranges (`low/high/text`), plus `outside_tools`; old is ₹ per year, one-time, client counts, single numbers. `basis` values differ (§2.10). `solved_note`, `ready_count`, `included` new. Reviewer worth must be stored next to the sharer's, versioned (`L-WORTH/3`, `/7`); old reviewer changes overwrite `ideas.category/play`. | **New** `idea_fix` (1:1) and `idea_worth` (rows: by `sharer\|reviewer`, hours/cost/revenue low–high, outside_tools, note_tagged, by, at). Retire `impact_estimates`. |
| `E-ENTITIES.idea` `Idea` | `ideas` (+ `idea_stage_history`, `review_items`, `sla_timers`, `idea_links`) | exists, differs | `id` = `ideas.idea_id` (`IDEA-YYYY-NNNNNN`) ✓, `ideas.id` uuid stays internal. `status` ← `stage` (§2.1). `kind` values differ (§2.3). `title` ← `canvas.one_line` (≤20 words vs 1–70 chars). `summary` ← `canvas.neutral_summary` (old: reviewer-written 15–220 chars; new: assistant-built, sharer-confirmed). `often` ← `who.frequency_or_reach`. `shared_at` ← `submitted_at`. **Missing:** `city` snapshot, `credited[]`, `share_seconds`, `stages[]` (derive), `crew{}`, `linked_similar_count`, `wall{shown, opened_7d}`, `merged_into`, `own_words` (→ `idea_messages`), `edit_window`, `review{decide_by, reviewer, opened_at}`, `decision`, `versions`, `kept_separate`, `next_step` (computed, like `views/mine.py` `OWNER_WORDS`), `declaration_version`. **Extra (old rules):** `submission_id` (and its pairing CHECK), `capture_mode`, `category`, `play`, `basis`, `strength`, `scope`, `lobs`, `systems`, `roles_affected`, `cluster_id`, `visibility`/`visibility_reason` (committee-only ideas have no place), `canvas` blob, `raw_encrypted`, `draft_encrypted`, `language` (→ per message). Keep `repo_path`/`repo_commit` if 0.7 keeps the repo writer. | **Alter in place** (new `status` column with the new CHECK; `opened_at`, `opened_by`, `edit_closes_at`, `decide_by`, `merged_into`, `withdrawn_at`, `share_seconds`, `city`, `declaration_version`, `declared_at`, `kept_separate`); drop `stage` and its trigger `ideas_stage_history`/`record_idea_stage` at cut-over; drop the old columns in a later cleanup migration. |
| `StageState` | `idea_stage_history` (from/to stage, at, source live/backfill; trigger on `ideas.stage`) | exists, differs | Five stages × `done/now/to_come/not_going_ahead` with detail and date are not stored; derivable from a status history. | **Reuse** the table, retarget the trigger to `status` (rename columns `from_status`/`to_status`); derive `StageState[]` in the view. Truncate synthetic history at cut-over. |
| `E-ENTITIES.review` `QuestionSet`, `Question`, `Answer` | `idea_questions` (one question per row: `question_encrypted`, `answer_encrypted`, `due_at`, `answered_at`, `review_item_id`) + `sla_timers` stage `needs_info` | exists, differs | No set, no `part` pin, no `suggested`, no `state` (`queued/sent/seen/partly_answered/answered/closed`), no `overdue`, no `time_to_answer`, no answer files, no `added_to`, no saved-but-unsent answers. **Old rule:** the `needs_info` timer pauses the review clock and, on breach, withdraws the idea (`sla/engine.py` `withdraw_with_reopen`); pack: asking does not pause and overdue closes nothing (`L-REVIEW` clock/2, `L-QUESTIONS.clock/4`). | **New** `question_sets`, `questions`, `answers` (answer text tagged + encrypted, like `idea_questions`). Retire `idea_questions` and the `needs_info` SLA rule. |
| `Decision`, `Window`, `Reversal` | `decisions` (cluster_id NOT NULL, core/lob body, `outcome picked/parked/declined`, votes, route, conditions, `appeal_window_closes`); `review_items.final`/`vetoed_by`/`veto_reason`; `sla_timers` stage `veto_window` | exists, differs (fundamentally) | Decision is per **idea**, by one reviewer, `choice pick/not_now/not_picked`, `reason ≥30`, `joined_with`, `return_at`, `team_by`. Window: 30 days calendar, extend +30 to 3 months, `extended_times`. Reversal: final, to one of the other two, note ≥30. Old veto (5 working days) sends the item back to the queue for the vetoing member; it is not a reversal to a chosen outcome. | **New tables** `idea_decisions` (avoid the name `decisions` until that table is dropped), `decision_windows` (also used for desk merges), `decision_reversals`. Do not reuse `decisions` or `review_items.vetoed_*`. |
| `E-ENTITIES.crew` `TeamUpRequest` | `idea_links` (`joiner` with `context_text` ≥30 chars, created at scan time, no approval) | exists, differs | Request with lead approval, three answers, `brought[]`, `lead_reason`, `state`, withdraw: all new. | **New** `teamup_requests` + `teamup_brought` (request_id, idea_uuid). |
| Crew (inside `Idea.crew`) | `idea_links` `originator`/`joiner`; `working_groups.members` jsonb (cluster) | exists, differs | One lead, members, `ones_count`, leave/remove (`L-TEAMUP/11`). `plus_one` and `adoption` have no home. | **New** `crew_members` (idea_uuid, contributor_code, role lead/member, via teamup/merge/desk_merge, joined_at, left_at, removed_by). Retire `idea_links`. |
| `Merge` | `idea_links` joiner (scan time); `cluster_proposals.kind='merge'` (clusters) | missing | Lead-accepted or desk merge, `team_up`, note ≥20, window, reversal. | **New** `merges` (lead_idea_uuid, merged_idea_uuid, by, via, team_up, note_tagged, at, window_id, reversed_at). |
| `IdeaRef`, `IdeaPreview`, `SimilarMatch`, `CrewCard` | match cards from `services/worker/scan/matching.py` over `repo_files.summary/area_ids` + `chunks` (embeddings, tsv) | exists (as a view), differs | Adds `lead`, `crew_faces`, `in_their_words`, `looking_for`, `city`, `hue`, `compare` (reviewers), `strength close/related`, `reason`, `reason_kind`. Blocked on finding 0.2. | **New** `similar_links` (idea_uuid, other_idea_uuid, strength, reason_tagged, outcome previewed/kept_separate/merge_asked) + **new** `crew_passes` (user, idea, passed_at, undone_at). Keep `chunks`/`repo_files` as the match index. |
| `E-ENTITIES.files` `FileItem` | `attachments` (owner `idea_uuid` or `delivery_id`; `state quarantine/processing/awaiting_check/clean/rejected`; `rejection {type, location}`; `checks`, `digest_meta`) | exists, differs | **Missing:** `kind file/link/folder`, `pages`, `count`, `problem`, `hidden_note`, `link_scope`, `url`, masked copy (`view_url`), owners `answer_id`/message. **States differ** (§2.9). Links today are text inside `canvas.ecosystem.references`, never fetched. Limits differ (§4). | **Alter** `attachments`: add `kind`, `answer_id`, `message_id`, `masked_store_key`, `hidden_note`, `pages`, `group_id` (folder), `link_scope`, `url_encrypted`; replace the state CHECK. Keep the quarantine → scan → personal-data pipeline (NN8). |
| `E-ENTITIES.inbox` `InboxItem`, `Action` | `notifications` (`channel in_app/email/teams/digest`, `event`, `template`, `payload` IDs only, `read_at`, BLD-088) + `comms_log` | exists, differs | **Missing:** `kind` enum, `from`, `idea_id`, `needs_you` (open until the action is done), `due`, `archived`, `actions[]`. `line`/`body` are rendered from templates at read time ✓ (keeps BLD-088: no text in the table). | **Alter** `notifications`: add `kind`, `idea_uuid`, `actor_ref`, `due_at`, `needs_you_until`/`resolved_at`, `archived_at`. Keep `comms_log`. |
| `Conversation`, `ConversationEntry` | none (idea page timeline is built from stage history: `views/idea_page.py`) | missing | One conversation per idea; audiences `you_and_desk/crew_and_desk/build_team`; messages with files and mentions. | **New** `conversation_entries` (idea_uuid, type, author contributor_code or user_id, text_tagged_encrypted, mentions, at) + files via `attachments.message_id`. |
| `E-ENTITIES.wall` `WallStage`, `JustInRow` | `views/wall.py` (recent / picked clusters / being built / shipped / solutions files) | exists (view), differs | `kind` filter, `opened_7d`, `crew_count`, `ones_count`, three stages only. | **New view**; **new** `idea_opens` (idea_uuid, user, day; counts only, kept 8 days). |
| `OneCard`, `OnePost` | `ones` (+ `tiers.py`); no posts | `OneCard` exists, differs; `OnePost` missing | `tier_name`, `flag`, `brief` from `ones`. Posts with likes, comments, thread: new. | **New** `one_posts`, `one_post_likes`; comments via a conversation thread. |
| `ImpactTotals`, `LiveFix`, `Impact` | `deliveries`, `delivery_measurements` (`day_30/day_90`, results, sponsor and finance confirmation), `ones.measures` | exists, differs | `Impact` four measures = `ones.measures` (DEC-071) ✓; `finance_confirmed` = `delivery_measurements.finance_confirmed_at` ✓. Totals and `LiveFix` rows need a view. | **Reuse** `delivery_measurements`; **alter** `deliveries` to an idea-only build record (drop pack, sponsor approval, fix track). |
| `EmberIssue` | `ember_issues` (`month`, `state draft/ready/sent`, `content` jsonb) | exists, differs | `number` (derive by month order), `headline`/`items` (inside `content`), `state latest/coming_soon` (view of sent/next). | **Reuse**; map in the view. |
| Build team (role `build_team`) | `working_groups` (cluster_id NOT NULL, `WG-` id), `deliveries.owner_user_id/pm_user_id` | exists, differs | Per idea, chosen by an admin, `team_by` date. | **New** `build_teams` (idea_uuid, name, lead user, members, chosen_at); retire `working_groups`. |
| Feature flags S1–S3 | `kill_switches` (on/off, global) | exists, differs | Per person or percentage assignment and exposure logging (`L-AUDIT.flags`) are new. | **Keep** `kill_switches`; **new** `flags`, `flag_assignments`, `flag_exposures`. |
| Sign-in code and intent | `sessions`; intent rides in a sealed cookie (`/auth/login` `next`) | missing | 6-digit code, 10 min, 3 tries, resend 45 s; intent stored server-side with draft id and step. | **New** `sign_in_codes` (email_hash, code_hash, expires_at, tries_left, sent_at, superseded_at), `sign_in_intents`. Blocked on 0.6. |
| Edit versions | none | missing | `GET /ideas/:id/versions`, "3 versions. Title changed once". | **New** `idea_versions` (idea_uuid, n, changed_fields, at; tagged snapshot encrypted). |

---

## 2. Enums and state machines

### 2.1 `E-ENUMS.idea-status` ← `ideas.stage` (CHECK in `20261108000300_ideas_and_review.sql`, 28 values; machine in `docs/ARCHITECTURE.md` §2.4)

| Old `stage` | New `status` | Note |
|---|---|---|
| `draft` | `draft` | Retention differs (archive, never delete). |
| `scanning` | `checking` | Old scan runs after submit and can block; new check never blocks (masking). |
| `blocked` | none → `draft` | Personal data is masked, not blocked (finding 0.1). |
| `redirected` | **no home** | Redirects (`rules/redirects.md`, IT ticket/HR grievance) have no place. |
| `scanned` | `with_review_desk` | |
| `merged` | `merged` | **Different meaning:** old = the submitter's own team-up/+1 at scan; new = lead-accepted merge or desk merge, with `merged_into`. |
| `adoption_requested` | **no home** | Solution adoption ("Already running") has no place. |
| `reviewed` | `with_review_desk` | Old "reviewed" = desk accepted the tags; not a decision. |
| `needs_info` | `with_review_desk` (+ open question set; sharer sees `needs_you`) | `needs_you` is a view, not stored. |
| `withdrawn` | `withdrawn` | **Different meaning:** old = auto-withdrawn after 7 working days without an answer, reopened by answering; new = sharer withdraws inside the edit window; restorable any time. |
| `in_cluster`, `ready_for_scoring`, `scored`, `shortlisted`, `presenting` | **no home** (nearest `with_review_desk`) | Clustering, scoring and presentations are gone. |
| `already_solved` | **no home** (nearest `not_picked` with "Your words carry on in …") | Never shown to a sharer as "already solved" (`L-DECIDE.rules/4`). |
| `already_planned` | **no home** (nearest `not_now`) | |
| `parked` | `not_now` | Needs `return_at`; old returns "next cycle". |
| `declined` | `not_picked` | |
| `appealed` | **no home** | No appeals (`P-DECISIONS.taken/4`). |
| `picked` | `picked` | **Different meaning:** old = core committee vote after a presentation; new = one reviewer's Pick. |
| `handover` | `picked` (team being chosen) | |
| `in_garage`, `in_fix_track` | `being_built` | The fix track folds into Built. |
| `shipped`, `resolved`, `measuring`, `closed` | `shipped` | Measuring is impact, not a status. |
| (none) | `needs_you` | View of `with_review_desk` with an open set. |

New machine (`E-ENUMS.idea-machine`) transitions with no old equivalent: `draft → merged` (lead accepts); `checking|with_review_desk (unopened) → withdrawn → checking` (restore); `with_review_desk → merged → with_review_desk` (committee reverses a desk merge); `picked|not_now|not_picked → other` (committee reverses, once, final); `not_now → with_review_desk` on the return date. Guards: `opened_at` set closes the edit window. Old guards to drop: `review/service.py` `_decide` allowed stages, `answer()` reopening `withdrawn`, `sla/engine.py` auto-withdraw.

Code that hard-codes old stage strings and must be rewritten or retired: `services/worker/core/stage_words.py`, `views/common.py` (`RECENT`, `PICKED`, `IN_GARAGE`, `SHIPPED`), `views/mine.py` (`_OWNER`), `points/ledger.py` (`SHORTLISTED`, `ACCEPTED`, `SHIPPED`), `review/service.py`, `scan/save.py`, `sla/engine.py`, `20261118000150_review_fixes_ember_points.sql` backfill list.

### 2.2 `E-ENUMS.stage` (track) — no stored equivalent

`shared, checked_matched, reviewed, built, shipped` × `done/now/to_come/not_going_ahead`. Derive from the status history (`idea_stage_history`, retargeted). No old values map one to one.

### 2.3 `E-ENUMS.kind` ← `ideas.kind`

| Old | New | Note |
|---|---|---|
| `problem` | `problem` | |
| `problem_with_solution` | `problem` + a `Fix` → Wall label `fix` | Check it offers two kinds; Wall derives `fix` (`E-ENUMS.kind` OPEN default). |
| `business_idea` | `business_idea` | |

### 2.4 `E-ENUMS.sorting`

| List | Old source | Mapping |
|---|---|---|
| `affects` | `canvas.who.segments` (`investors, distributors, amc_clients, issuer_clients, kfin_teams, other`) | `investors`→Investors, `kfin_teams`→KFin teams, `distributors`→Distributors; `amc_clients`, `issuer_clients`, `other` → entries in the configured "Search all groups" list. |
| `area` | `ideas.area_ids` (AREA- themes: compliance, customer-experience, data-reporting, facility, partners-distribution, people-policy, process, technology), `users.lob_id` (LOB-) | **Different meaning.** Only Technology and Compliance line up. Nearest: customer-experience→Investor service, process→Operations, partners-distribution→Distributor experience/services. data-reporting, facility, people-policy: **no home**. New list is configuration. |
| `brings` | `ideas.category` (`cost_saving, new_revenue, both, not_sure`) | `cost_saving`→`saves_cost`; `new_revenue`→`earns_revenue`; `both`→`[saves_cost, earns_revenue]`; `not_sure`→`not_sure`. `saves_time`, `less_outside_tools` new. |
| (none) | `ideas.play` (`process_improvement, upsell, cross_sell, new_product, other`) | **No home.** Retire. |
| `sorting_source` | `canvas.provenance` (`submitter, suggested, accepted, reviewer`) | `suggested`→`suggested`, `accepted`→`confirmed`, `submitter`→`changed`, `reviewer`→ a reviewer revision row (`L-WORTH`, `L-SORT.rules/6`). |
| `helper` | none | New. |

DEC-004 (category is the submitter's call) and DEC-094 (unchosen category saved as "Not sure yet") are superseded by `P-DECISIONS.taken/2`; `finaliseQuick()` in `apps/web/src/lib/canvas/rules.ts` goes.

### 2.5 `E-ENUMS.part` ← canvas sections (`lib/canvas/model.ts`, strength rubric)

| New part | Old field | |
|---|---|---|
| `summary` | `one_line`, `details`, `neutral_summary` | |
| `often` | `who.frequency_or_reach` | |
| `who` | `who.segments`, `who.today_alternative` | |
| `cost` | `value.estimate`, `value.category` | units differ |
| `evidence` | `value.basis`, `ecosystem.references`, attachments | |
| `fix` | `solution.approach/needs/risks` | |
| none | `ecosystem.solved_elsewhere` + `our_advantage` | **no home** (fix's `solved_already` covers part) |
| none | strength rubric `what_it_is … solved_elsewhere` (`canvas_strength`) | **no home**; retire with the meter |

Draft parts (`E-ENUMS.draft`): `title, often, who, value, area, similar`; part state, channel and step have no old equivalent. `capture_mode quick/full` has no home.

### 2.6 `E-ENUMS.decision` ← `decisions.outcome` (cluster) and `review_items.final.action`

| Old | New |
|---|---|
| `decisions.outcome='picked'` | `pick` (different body: committee → desk) |
| `'parked'` | `not_now` (+ `return_in 1m/3m/6m`; new) |
| `'declined'` | `not_picked` |
| `review_items.final.action='decide'` (accept tags, attach to cluster/idea) | **no home** (not a decision) |
| `'redirect'`, `'hold'`/`confirm_hold`, `'visibility'` | **no home** |
| `'ask'` | moves to question sets |
| `decisions.route` (`reuse/build/buy/partner`), `reason_code`, `what_would_change`, `conditions`, `votes`, `casting_vote`, `override_reason` | **no home** |

### 2.7 `E-ENUMS.windows` ← `sla_timers` stage `veto_window` (+ `review_items.vetoed_*`)

| Old | New |
|---|---|
| timer `running` | `open` |
| (none) | `extended` (+30 days, up to 3 months; new) |
| veto (item back to `open`, assigned to the member) | **no home**; nearest `reversed`, but a reversal sets a chosen outcome and is final |
| `stopped`/`breached` at expiry | `expired` |

Old length 5 working days (`rules/sla.md` `veto_window.limit_wd: 5`); new 30 calendar days. The timer table can carry it; the rule key and semantics are new.

### 2.8 `E-ENUMS.questions` ← `idea_questions` + `sla_timers` `needs_info`

`answered_at IS NULL` → `sent`; `answered_at` set → `answered`. `queued`, `seen`, `partly_answered`, `closed` (on decision) and the `overdue` flag are new. Time to answer `1d/3d/1w` (6 pm office time) replaces the fixed 7 working days. Old `needs_info` breach → `withdrawn`: **no home** (overdue closes nothing).

### 2.9 `E-ENUMS.teamup` ← `idea_links.link_type`

| Old | New |
|---|---|
| `originator` | the sharer = crew `lead` |
| `joiner` (instant, ≥30-char context) | nearest `approved_team_only`; the request/approval states are new |
| `plus_one` | **no home** |
| `adoption` | **no home** |

Draft merge request `none/waiting/accepted/team_only/declined/withdrawn`: new.

### 2.10 `E-ENUMS.fix`

`solved_already` = `canvas.ecosystem.solved_elsewhere` (`yes/partly/no/dont_know`) — **matches**. Basis: `own_data`→`own_research`, `document`→`report` (or `verified_documents`; split is new), `conversation`→`conversation`, `hunch`→`hunch`. `outside_tools none/partly/fully`: new.

### 2.11 `E-ENUMS.file` ← `attachments.state` (+ `rejection.type`)

| Old | New |
|---|---|
| `quarantine` | `uploading` → `checking` |
| `processing`, `awaiting_check` | `checking` |
| `clean` | `checked` |
| `rejected` + personal data | `personal_data_found` |
| `rejected` + virus | `infected` |
| `rejected` + size/type | `too_big` (type: error `type_not_allowed`, not a state) |
| (none) | `hidden_checked` (masked copy), `locked`, `upload_failed` (client); links `ok`/`unreachable` (finding 0.3) |

### 2.12 `E-ENUMS.hidden` ← `apps/web/src/lib/pii/patterns.json` (shared with Python)

| Pattern id (action) | New kind |
|---|---|
| `pan` (block) | `pan` |
| `aadhaar` (block) | `aadhaar` |
| `mobile` (block) | `phone` |
| `email` (block) | `email` |
| `bank_account`, `card`, `demat_in`, `demat_16` (block) | `account` |
| `folio` (block) | `folio` |
| `pran` (block), `dob` (block) | **no home** in the pack list; must still be hidden: add kinds or map to `account` |
| `ifsc`, `arn`, `euin` (warn) | not hidden (IFSC only "with account") |
| Presidio names / `[[KFIN_EMPLOYEE_n]]`, `[[CLIENT_AMC_n]]` tags | `name` covers customer names only. Colleague and client names are still tagged before any model call (NN2); they are not masked for display in the pack. |

Show reasons (`scheme_or_product_code`, `internal_reference`, `made_up_example`): new; nearest old is `scans.overrides.not_personal_data` (gatekeeper only).

### 2.13 `E-ENUMS.inbox` ← `notifications.event` (events in `seed/company-repo/comms/rules.md`)

| Old event | New kind |
|---|---|
| `idea.submitted` | `sent_to_desk` |
| `idea.question` | `questions` |
| `sla.reminder` (needs_info) | `answer_reminder` |
| `decision.accepted`, `decision.not_accepted` | `decision` |
| `idea.reconsidered` (after a veto) | `decision_reversed` (different meaning) |
| `idea.joined` | `crew_joined` |
| `delivery.phase_changed` | `stage_moved` |
| `canvas.nudge`, `idea.reviewed`, `idea.redirected`, `idea.withdrawn_no_answer`, `sla.breached`, `adoption.requested`, `cluster.approved`, `cluster.gate_outcome`, `round.opened`, `round.not_shortlisted`, `shortlist.invited`, `presentation.confirmed`, `decision.not_presented`, `appeal.filed`, `appeal.decided`, `ones.removed`, `ones.message_invited`, `ones.announced`, `delivery.approval_needed`, `delivery.completion_to_approve`, `delivery.measure_due`, `delivery.measure_to_confirm`, `delivery.fix_checkin`, `delivery.checkin_blocked`, `delivery.writeup_submitted`, `delivery.writeup_decided`, `delivery.overdue` | **no home** in the Inbox (admin tasks become admin API/email; the rest retire) |
| `ones.inducted`, `ones.tier_changed` | no Inbox kind; the tier moment on `GET /one` (`one_glow_ups`) |
| `ember.issue` | no Inbox kind; Wall's Ember |
| (none) | `teamup_request`, `teamup_answer`, `desk_merge`, `worth_revised`, `build_ask`, `mention`, `comment`, `draft_kept` |

### 2.14 `E-ENUMS.roles` ← `role_grants.role` CHECK (`20261114000100_ones.sql`) and `apps/web/src/lib/rbac.json`

| Old | New |
|---|---|
| `contributor` (every signed-in person, `rbac.json`) | `employee` |
| `reviewer` | `reviewer` |
| `core_committee`, `core_chair` (alias) | `committee` (chair has no separate rights; Ember note approval is an old rule) |
| `working_group` (scope `WG-`) | `build_team` (per idea) |
| `admin` | `admin` |
| (none) | `display`; per-idea `sharer`, `lead`, `crew` |
| `lob_committee`, `appeal_panel`, `sponsor`, `ceo` | **no home** |
| `infosec`, `hr` | not in the pack; keep as operations roles (kill switches with reason, HR comms sign-off) |

### 2.15 `E-ENUMS.tier`, `E-ENUMS.match`

Tier names and order 1–7 **match** `ones/tiers.py` exactly (Spark … Star). Meaning differs: every employee has a tier. Match `close/related` and crew reasons are new; old `MATCH_CARD_WORDS` ("Already running", "Looked at before") retire.

---

## 3. API

Conventions first (`A-API.conventions`), then each operation. Existing handlers live in `apps/web/src/app/api/**/route.ts`; most delegate to the worker's `/internal/*` (`services/worker/api/app.py`).

### 3.1 Conventions

| Convention | Repo today | Gap |
|---|---|---|
| Error `{ error: { code, message, field?, retry_after? } }` | `{ error: code, details? }` (`apps/web/src/server/http.ts`); field errors as `details: FieldError[]` | Alter `asResponse`; messages come from V-FIELDS copy. |
| `Idempotency-Key` on creates | none | New middleware + `idempotency_keys` table. |
| Lists `{ items, total, counts?, next? }` | ad hoc (`{ideas, joined, name_on_wall}`, arrays) | Alter every list. |
| Server-computed date labels | `views/mine.py` returns ISO `due` only | Add labels server-side. |
| One SSE stream per person (`A-API.events`) | only `GET /api/submissions/[id]/scan-events` per submission (behind `scan.live`) | New. |
| Permission on every route | `authorize(capability)` + `rbac.json` | New capabilities for the new actions. |
| Kill switch on every request (NN9) | `apps/web/src/lib/killswitch-routes.ts` maps route prefixes to switches | Every new route must be mapped; retired routes removed. |

### 3.2 Operations

| A- endpoint | Existing route handler | State | Shape differences | Recommendation |
|---|---|---|---|---|
| `POST /auth/sso/start` | `GET /auth/login` (+ `GET /auth/callback`) | exists, differs | GET redirect; intent = `next` in a sealed cookie; no `draft_id`/`step`; no silent attempt | Alter: JSON wrapper, server-side intent, `prompt=none` attempt |
| `POST /auth/code/send`, `POST /auth/code/verify` | none | missing | — | New, after IT/InfoSec (finding 0.6) |
| `GET /auth/session` | `GET /api/me` (partly) | exists, differs | No `expires_at`, `intent`, or `expired` draft payload | Alter |
| `POST /auth/sign-out` | `POST /auth/logout` | exists, matches | path only | Reuse (alias) |
| `GET /me` | `GET /api/me` | exists, differs | Returns `contributor_code, lob_id, role_family, grants, nav, privacy_notice`; lacks `first_name, initials, area, city, tier, one, points, settings` | Alter |
| `PATCH /me/settings` | `PUT /api/me/comms-prefs` (`name_on_wall` only) | exists, differs | One switch vs six | Alter → new route |
| `GET /me/shell` | none | missing | — | New aggregate |
| (points) | `GET /api/me/points` | exists, matches | Pack folds into `GET /me` | Reuse internally |
| `GET /home` | none (pieces: `/api/inbox`, `/api/me/ideas`, `/api/ones`) | missing | — | New aggregate |
| `POST /drafts` | `POST /api/submissions` | exists, differs | Body `{mode, canvas}` → `{text?, files?, channel}`; returns `{id}` not `Draft` | Replace |
| `GET /drafts/:id` | `GET /api/submissions/[id]` | exists, differs | Canvas JSON vs messages/parts/sorting/hidden | Replace |
| `GET /drafts?recent=1` | none (drafts sit inside `/api/me/ideas`) | missing | — | New |
| `POST /drafts/:id/messages`, `PATCH …/messages/:mid` | `PUT /api/submissions/[id]` (whole-canvas autosave) | exists, differs | Per-message append and re-run vs whole document | New |
| `PATCH /drafts/:id/parts/:part` | `PUT /api/submissions/[id]`; `POST …/confirm-card` (`keep` paths, after submit) | exists, differs | Pin/unpin per part | New |
| `PATCH /drafts/:id/sorting` | `POST /api/submissions/[id]/confirm-card` (closest) | exists, differs | Confirm before submit vs accept suggestions after scan | New |
| `POST …/hidden/:hid/show`, `…/hide` | `POST /api/submissions/[id]/scan-choice` `{choice: not_personal_data, reason}` | exists, differs | Gatekeeper contest vs pattern un-hide | New, blocked on 0.1 |
| `PUT`/`DELETE /drafts/:id/fix`, `PUT …/helpers`, `PATCH /drafts/:id {step}` | inside `PUT /api/submissions/[id]` (fix only) | missing | Indian-form amount parsing and ranges are new | New |
| `POST /drafts/:id/voice` | `POST /api/submissions/[id]/voice`, `GET`/`DELETE …/voice/[voice]` | exists, differs | Stored recording (≤24 h) + fetched transcript vs streamed transcript, audio not stored; `capture.voice` off | Alter behind the switch (finding 0.4) |
| `POST`/`DELETE /drafts/:id/merge-request` | none (`POST …/choose {team_up}` is after submit) | missing | — | New |
| `POST /drafts/:id/submit` | `POST /api/submissions/[id]/submit` | exists, differs | Body is the whole canvas, validated with 50-char rule and three declarations; errors `invalid` (FieldError[]), `personal_data`, `already_submitted`. New body `{declaration_version}`; errors `sorting_unconfirmed`, `file_blocked`, `merge_waiting`, `not_ready`; idempotent | Alter |
| `DELETE /drafts/:id` | none (`drafts.purge` job deletes) | missing | Archive, not delete | New |
| `GET /drafts/:id/stream` | `GET /api/submissions/[id]/scan-events` | exists, differs | Scan progress after submit vs `run/hidden/part/receipt/done` while drafting | New (reuse SSE plumbing) |
| `POST /files` | `POST /api/submissions/[id]/attachments`, `POST /api/delivery/[id]/evidence` | exists, differs | Owner by `draft_id/idea_id/answer_id`; states; errors `too_big {limit_mb}`, `type_not_allowed`, `locked` | Alter |
| `POST /links` | none (references are canvas text) | missing | — | New, finding 0.3 |
| `POST /files/:id/hide` | none | missing | Masked copy | New |
| `POST /files/:id/retry` / `DELETE /files/:id` | — / `DELETE /api/submissions/[id]/attachments/[att]` | missing / exists, matches | | New / reuse |
| `GET /files/:id/view` | `GET /api/attachments/[id]` | exists, differs | Clean original vs masked copy | Alter |
| file states | `GET /api/attachments/[id]/status` (poll) | exists, differs | Push via `A-API.events` | Replace |
| `GET /config/uploads`, `GET /config` | `GET /api/canvas/config` (limits, strength rubric, examples) | exists, differs | Promises, sorting lists, flags, placeholders | Alter → `GET /config` |
| `GET /ideas/:id` | `GET /api/ideas/[id]` | exists, differs | Old view per §3.1; new shape by viewer (public / sharer / crew / desk / committee), crew, stages, decision, window, worth | Alter |
| `GET /ideas/:id/preview`, `GET /ideas/:id/similar` | match cards inside the scan view | missing | — | New, finding 0.2 |
| `GET /me/ideas` | `GET /api/me/ideas` | exists, differs | No `list/filter/sort/q`, no `counts`, no search sentence | Alter |
| `PATCH /ideas/:id`, `POST …/withdraw`, `POST …/restore`, `GET …/versions` | `POST …/choose {withdraw}` at scan only | missing | — | New |
| `POST /ideas/:id/join-build` | none | missing | — | New |
| `GET /desk/ideas/:id/suggested-questions` | none | missing | Needs an agent through the gateway (NN1) | New |
| `POST /desk/ideas/:id/question-sets` | `POST /api/review/items/[id]/action {action:'ask', question}` | exists, differs | One question, ≥10 chars, 7 working days, pauses review | New |
| `POST /question-sets/:id/extend`, `…/remind`, `…/send`; `GET /ideas/:id/question-set`; `PUT /questions/:id/answer` | `POST /api/ideas/[id]/answer` (`{text}` ≥5, answers at once) | exists, differs | Saved drafts per question, send once | New |
| `GET /desk` | `GET /api/review/items` | exists, differs | Queue of mixed `review_items` vs tabs, counts, time-left labels | New |
| `POST /desk/ideas/:id/open` | none | missing | Closes the edit window | New |
| `GET /desk/ideas/:id` | `GET /api/review/items/[id]` | exists, differs | | New |
| `PUT /desk/ideas/:id/worth` | `…/action {decide, category, play, note}` | exists, differs | Versioned, both kept | New |
| `POST /desk/ideas/:id/decision` | `…/action {decide}` (tagging) and `POST /api/committee/presentations/[id]/action` (picking) | exists, differs | Neither is Pick/Not now/Not picked by one reviewer | New |
| `POST /desk/ideas/:id/merge` | `…/action {decide, attach:{type:'idea'}}` (link only) | exists, differs | | New |
| `GET /desk/ideas/:id/audio` | none | missing | TTS (`L-LISTEN`), provider OPEN | New behind a switch |
| `GET /committee` | `GET /api/review/desk-decisions` | exists, differs | Tabs `window/reversed/expired`, counts, sentence | Alter |
| `POST /decisions/:id/extend` | none | missing | | New |
| `POST /decisions/:id/reverse` | `POST /api/review/items/[id]/veto {reason ≥10}` | exists, differs | Reverse to a chosen outcome, final, note ≥30 | New; retire veto |
| `GET /ideas/:id/team-up/draft-note`, `POST /ideas/:id/team-up`, `DELETE /team-up/:id`, `POST /team-up/:id/answer` | `POST /api/submissions/[id]/choose {team_up\|plus_one}` | exists, differs | Instant join vs request and lead's three answers | New; retire `choose` |
| `GET /crew`, `POST /crew/pass`, `/undo`, `/reset` | none | missing | | New |
| `GET /inbox` | `GET /api/inbox` | exists, differs | Rendered subject/body; no tabs, kinds, `needs_you`, `counts`, actions | Alter |
| `POST /inbox/:id/read` | `POST /api/inbox/[id]/read` | exists, matches | | Reuse |
| `POST /inbox/:id/archive` | none | missing | Error `needs_you` | New |
| `GET /ideas/:id/conversation`, `POST …/conversation/messages` | none | missing | | New |
| `GET /wall/kindling`, `GET /wall/just-in` | `GET /api/wall`, `GET /api/ideas` | exists, differs | Sections and sorts differ; `opened_7d`, `ones_count` | Replace |
| `GET /wall/ones` | `GET /api/ones` | exists, differs | `OneCard` shape | Alter |
| `GET /wall/impact` | none | missing | | New view |
| `GET /wall/ember` | `GET /api/ember` (sent issues) | exists, differs | `EmberIssue` shape, `coming_soon` | Alter |
| `GET /ones/posts` | none | missing | | New |
| `GET /one` | `GET /api/me/one` | exists, differs | Adds number window, pending tier moment | Alter |
| `PUT /one/number` | `POST /api/me/one/number` | exists, differs | Method; error `taken {near[]}`, `window_closed`, `out_of_range`; old rest/legend rules | Alter |
| `POST /one/brief` | `POST /api/me/one/brief` | exists, differs | Length 20–140 vs 10–240; approval by programme team vs committee proposal | Alter |
| `GET /display/office` | `GET /api/ones/constellation`, `PUT /api/ones/screen-mode` | exists, differs | `display` role, briefs + figures | Alter |
| `GET /search/suggest`; `q` on lists | none | missing | | New |

---

## 4. Validation: V-FIELDS vs existing checks

There is no zod in the repo. Browser and server share hand-written TypeScript (`apps/web/src/lib/canvas/rules.ts` `validate()`, `apps/web/src/server/submissions.ts` `sanitiseCanvas()`); the worker uses `_tagged(…, min_chars)` (`services/worker/review/service.py`) and `checked(…, min_chars, max_chars, max_words)` (`ones/`, `delivery/`, `ember/`), which also run the patterns and the gatekeeper. Numbers come from `seed/company-repo/rules/thresholds.md` and `sla.md`, validated by `services/worker/rules/schemas/*.schema.json`. The pack's promises must also be configuration (`P-PRODUCT.promises`), so new keys go into `thresholds.md` + its JSON schema.

| V-FIELDS rule | Pack | Existing | Where | Difference |
|---|---|---|---|---|
| `V-FIELDS/1` counting | Trim, count characters | TS `.trim().length` (UTF-16 units); Python `len()` (code points) | `rules.ts`, `review/service.py` | Browser and server disagree on emoji and some scripts; use one shared code-point count |
| `tellit/1` minimum | **30** characters in total | **50** (`canvas.details_min_chars`, DEC-094) | `thresholds.md`, `validate()` | 30 vs 50 (`P-DECISIONS.open/15` picks 30) |
| `tellit/2` per message | ≤5,000 with a message | `details` silently cut at 10,000 | `sanitiseCanvas` `text()` | Truncation vs error |
| `tellit/5` voice | ≤3 minutes | `speech_max_seconds = 180` | `services/worker/core/config.py` | Matches (switch off) |
| `tellit/7`, `checkit/1` title | 1–70 characters | `one_line` ≤20 **words**, cut at 400 chars | `thresholds.md`, `validate()` | Unit differs |
| `checkit/2` "what happens" | Not empty | `details` ≥50 | `validate()` | |
| `checkit/3` sorting | affects ≥1; kind exactly 1; area exactly 1; brings ≥1, `not_sure` exclusive | kind required (full only); one `category`; segments optional; areas set by reviewer | `validate()`, `review/service.py` | Rule set is new |
| `checkit/4` sorting confirmed | Required at submit | none | | New |
| `tellit/9` attachment size | One limit from config: 15 MB drawn, **25 MB** default (`P-DECISIONS.open/12`) | **20 MB** each, 50 MB per idea, max 5 files | `thresholds.md` `attachments` | Limit and per-idea cap differ |
| Attachment types | PDF, Word, PowerPoint, Excel, Markdown, HTML, ZIP, images, folders | pdf, docx, pptx, xlsx, csv, png, jpg | `thresholds.md` | Markdown, HTML, ZIP, folders new; ZIP unpacking and `locked` new |
| `tellit/10` link | Must be a URL | references ≤1,000 chars, no URL check | `sanitiseCanvas` | New |
| `tellit/8` show hidden | Reason from 3 | gatekeeper contest only; patterns absolute | `scan-choice` | Finding 0.1 |
| `checkit/8` fix "how" | ≥20 characters | non-empty when kind is `problem_with_solution` | `validate()` | 20 vs 1 |
| `checkit/9` amounts | Number or range, Indian forms (2 lakh, 2L, 2,00,000), per month | single number; strips commas and ₹; no lakh/L; no ranges; per year | `parseFigure()` | New parser; units |
| `checkit/10` helpers | ≤140 | none | | New |
| `checkit/11` merge note | ≥30 | team-up context ≥30 (`join_context_min_chars`) | `thresholds.md`, `scan/save.py` | Same number, different flow |
| `checkit/16` withdraw reason | Optional ≤280 | none | | New |
| `teamup/1` note | 30–600 | ≥30, no max | `scan/save.py` | Max new |
| `answer/1` answer | Optional per question, ≤2,000 | ≥**5** characters, required | `review/service.py` `answer()` | Min dropped, max added |
| `answer/2` send | ≥1 answer | n/a | | New |
| `answer/4–5` message | Text or file; ≤4,000 | none | | New |
| `review/1` question | Not empty, ≤300 | ≥**10**, no max | `review/service.py` `ask` | |
| `review/3` time to answer | 1d/3d/1w, warn if after decide-by | fixed 7 working days | `sla.md` `needs_info` | |
| `review/5` decision reason | **30–1,000** | desk note ≥10 only when category/play change; committee `plain_reason` ≥30 | `review/service.py`, `committee/decide.py` | |
| `review/6` not now | 1/3/6 months | next cycle | `20261119200100_parked_return.sql` | |
| `review/8` worth note | Optional ≤280 | ≥10, required on change | `review/service.py` | |
| `review/10` merge note | 20–600 | none | | New |
| `committee/2` reversal note | **30–1,000** | veto reason ≥**10** | `review/veto.py` | |
| `committee/3` extend | Up to 3 months | 5 working days, no extend | `sla.md` `veto_window` | |
| `one/1–3` number | 1–999, free, 30-day window | 1–999, 30 days ✓; plus 6-month rest and legend numbers | `ones/numbers.py` | Extra old rules |
| `one/4` impact brief | **20–140** characters, one sentence | **10–240**, ≤30 words | `ones/service.py:180` | |
| `one/5` settings switch | Saves at once | `name_on_wall` only | `PUT /api/me/comms-prefs` | |
| `signin/1–7` | Work-email domain, 6-digit code, 10 min, 3 tries, resend 45 s, rate limit | none (OIDC) | | New |
| Session | 8 hours | 8 h sliding, **12 h absolute** | `server/auth/session.ts` (`SESSION_ABSOLUTE_HOURS = 12`) | Align to 8 h |
| Review clock | 5 working days, not paused by questions | 5 working days, **paused** by `needs_info` | `sla.md`, `sla/engine.py` | Pause rule goes |
| Reviewer summary | (assistant writes it; sharer edits) | reviewer writes `neutral_summary` 15–220 chars, ≤25 words | `review/service.py` `SUMMARY_*` | Owner changes |

---

## 5. Retire list

Each line: what to retire, then what depends on it. "Web-revoked" = in `HIDDEN_FROM_WEB` (`services/worker/tests/test_b4_service_roles.py`); update that pinned set in the same change.

### 5.1 Tables

| Group | Tables | Foreign keys and dependents |
|---|---|---|
| Clustering | `clusters`, `cluster_runs`, `cluster_proposals`, `cluster_pairs` | FK targets of `cluster_gates`, `impact_estimates`, `scoring_rounds`, `presentations`, `assessments`, `decision_sheets`, `decisions`, `working_groups`, `appeals` (all `REFERENCES clusters`); `cluster_proposals.run_id → cluster_runs`, `cluster_proposals.review_item_id → review_items ON DELETE CASCADE`; `ideas.cluster_id` and `idea_links.cluster_id` (pattern CHECK, no FK); vault scopes `CL-`/`CLP-`; job `cluster.batch`; switches `clusters.batch`, `agent.cluster-summary`; code `services/worker/cluster/*`, `router/match.py`, `scan/matching.py`, `views/wall.py`, `repo_writer/render_cluster.py`; routes `/api/review/cluster-*`; pages `app/review/clusters/*` |
| Qualify, scoring, presenting, committee decisions | `cluster_gates`, `impact_estimates`, `cycles`, `capacity`, `scoring_rounds`, `sealed_scores`*, `ai_prescores`*, `coi_flags`, `presentations`, `assessments`*, `decision_sheets`*, `decisions` (* web-revoked, NN6 set) | `capacity/scoring_rounds/presentations/decision_sheets/decisions → cycles`; `sealed_scores/ai_prescores/coi_flags → scoring_rounds ON DELETE CASCADE`; `presentations.round_id`, `decisions.round_id → scoring_rounds`; `assessments/decision_sheets/decisions → presentations`; `working_groups.decision_id`, `appeals.decision_id → decisions`. Job `qualify.backfill`; switches `committee.flow`, `agent.prescore`, `agent.pitch-prep`, `agent.collation`, `agent.reason-writer`; code `committee/*`, `learning/decisions.py`, `repo_writer/render_decision.py`; routes `/api/committee/*`, `/api/presentations/*`, `/api/review/qualify/*`, `/api/admin/conflicts`, `/api/reports/[kind]`; rules `scorecard.md`, `priority.md`, `routing.md` (thresholds, veto), `reason-codes.md`, `compliance-tier.md`; repo folders `decisions/`, `themes/` |
| Appeals | `appeals`* | FK `decisions`, `clusters`; `review_items.item_type='disagreement'`; switch `appeals.filing`; routes `/api/appeals/*`, `/api/ideas/[id]/disagree`; `repo_writer/render_appeal.py`; comms `appeal.*`; points `restore_forfeited`; `rules/schemas/routing.schema.json`; repo `appeals/` |
| Working groups | `working_groups` | FK `clusters`, `decisions`; `role_grants` role `working_group` scope `WG-`; route `/api/working-groups/[id]`; `points/ledger.py` (`working_group_member_shipped`) |
| Review queue internals | `review_items` (for ideas), `corrections`, `autonomy` | `corrections.review_item_id → review_items ON DELETE CASCADE`; `idea_questions.review_item_id ON DELETE SET NULL`; `cluster_proposals.review_item_id`; partial index `review_items_open_ref` used by **`services/worker/identity/hr_import.py` taxonomy proposals on every HR import** (move that path before dropping); `corrections` feed `learning/*`, `router/corrections.py`, `gateway/grounding.py`, `scripts/ops/restore-drill.sh`; `autonomy` feeds `learning/run.py`, `rules/loader.py`, `thresholds.schema.json` |
| Scan after submit | `scans` | FK `ideas ON DELETE CASCADE`; web column grants (`20261111000200_b4_review.sql`); job `scan.run`; switch `scan.live`; routes `/api/submissions/[id]/scan-*`, `choose`, `confirm-card`; `gonogo`, `bootstrap/preflight.py`. Replace with `draft_runs`. |
| Old links and questions | `idea_links`, `idea_questions` | `idea_links` is read by `points/ledger.py`, `views/mine.py`, `views/common.py`, `lenses`, `comms/route.py`, `cluster/batch.py` (must-links), `restore-drill.sh`; `idea_questions → ideas`, `review_items` |
| Delivery pack layer | `delivery_milestones`, `delivery_checkins`, `solution_writeups`; columns on `deliveries`: `pack`, `sponsor_*`, `submitted_by`, `completed_by`, `objective_encrypted`, `completion*`, `track`, `state` values `drafting/awaiting_sponsor`, `resolved_at` | FKs `→ deliveries ON DELETE CASCADE`; `attachments.delivery_id`; switches `solutions.publish`, `agent.handover-draft`; job `delivery.tick` (partly); routes `/api/delivery/[id]/{pack,pack-draft,submit,approve,send-back,milestones*,checkin,writeup*,complete,approve-completion,link,phase}`; `SOL-` IDs, repo `solutions/`, `handovers/`. Keep `deliveries` (slimmed) + `delivery_measurements`. |
| Learning and lenses | `learning_reports`, `learning_proposals`, `role_themes`, `lens_snapshots` | switches `learning.jobs`, `agent.role-themes`; jobs `learning.run`, `lenses.build`; routes `/api/learning/*`, `/api/lenses/*`, `/api/me/lens`; `evalrunner/role_themes.py`; repo `learning/`, `lenses/` |
| Ones extras (ask first) | `one_legend_numbers`, `one_awards`, `one_message_invites`; `one_proposals` kinds `include/remove/tier_up/tier_down/legend` (keep `impact_brief` or replace with brief approvals); `one_messages.author_role` `ceo/peer` | FK `→ ones ON DELETE RESTRICT/CASCADE`; `ones/numbers.py`, `ones/service.py`, `ones/views.py`, `comms/render.py`; routes `/api/ones/proposals/*`, `/api/ones/[id]/awards`, `/api/ones/announce`, `/api/me/team`; role `ceo`; `ones.way_in='sponsored'` |
| Gateway cache | none (keep `llm_cache`, `llm_calls`) | — |

### 5.2 Columns, constraints, enums

| Item | Depends on it |
|---|---|
| `ideas.stage` + CHECK (28 values), trigger `ideas_stage_history`/`record_idea_stage()`, indexes `ideas_stage`, `ideas_draft_expiry`, `ideas_public` | every view and service in §2.1 |
| `ideas.submission_id` + CHECKs pairing it with `idea_id`; `id_counters` kind shared by SUB-/IDEA- | `submissions.ts` submit, repo writer |
| `ideas.capture_mode`, `category`, `play`, `basis`, `strength`, `scope`, `lobs`, `systems`, `roles_affected`, `cluster_id`, `visibility`, `visibility_reason`, `canvas`, `raw_encrypted`, `draft_encrypted` | `lib/canvas/*`, `scan/*`, `review/*`, `views/*`, `chunks.visibility`/`repo_files.visibility` (`committee`), rbac `see_committee_only_ideas` |
| `role_grants.role` values `lob_committee, core_chair, appeal_panel, working_group, sponsor, ceo` | `rbac.json` (`role_aliases`, capabilities), committee/delivery/ones services |
| `review_items.item_type` values beyond `taxonomy_proposal` | see 5.1 |
| `attachments.state` CHECK | `attachments/*`, `/api/attachments/[id]/status` |
| `comms_prefs.routine`, `manager_notes` | `comms/route.py` digest, `comms.digest` job |
| `sla.md` keys `needs_info` (auto-withdraw), `veto_window`, `cluster_proposal`, `qualify`, `scoring_round`, `invitation_reply`, `deck_upload`, `individual_assessment`, `final_decision`, `outcome_message`, `handover`, `appeal_window`, `appeal_decision` | `sla/engine.py` (keep the engine and `sla_timers`) |
| `thresholds.md` keys `canvas_strength`, `cluster`, `working_group_trigger`, `autonomy`, `consistency`, `match.reserve_*`, `canvas.nudge_*` | `rules/schemas/thresholds.schema.json`, canvas config route |
| `rules/redirects.md`, `REDIRECT_KINDS` | `review/service.py`, comms `idea.redirected` |
| `rules/points.md` events (old lifecycle) | `points/ledger.py` |
| Kill switches: `clusters.batch`, `agent.cluster-summary`, `committee.flow`, `agent.prescore`, `agent.pitch-prep`, `agent.collation`, `agent.reason-writer`, `appeals.filing`, `learning.jobs`, `agent.role-themes`, `solutions.publish`, `agent.handover-draft`, `scan.live`, `capture.mic_hint` (keyboard-mic tip for quick capture) | `killswitch-routes.ts`, the go/no-go report (`services/worker/gonogo`), demo-stack gates. Delete rows with an audited migration, as `20261119000100` did for state changes. |

### 5.3 Endpoints

`/api/submissions/[id]/{choose,confirm-card,scan-choice,scan-status,scan-events}`, `/api/ideas/[id]/disagree`, `/api/appeals/*`, `/api/committee/*`, `/api/presentations/*`, `/api/review/{cluster-proposals,cluster-runs,qualify,items/[id]/veto}/*`, `/api/working-groups/[id]`, `/api/admin/conflicts`, `/api/reports/[kind]`, `/api/learning/*`, `/api/lenses/*`, `/api/me/{lens,team}`, `/api/ones/{proposals/*,[id]/awards,announce}`, `/api/delivery/[id]/*` except measurements. Kept but reshaped: §3.2. Each removal also removes its `rbac.json` capability, `killswitch-routes.ts` entry and pages under `apps/web/src/app/`.

### 5.4 Contracts and schemas

| Item | Note |
|---|---|
| `contracts/garage/{schemas/*.schema.yaml, phases.yaml, notion-delivery-pipeline.md}` | Inherited, read-only (NN12). Used by `delivery/phases.py` and the pipeline link. The pack has a build team and an admin "mark shipped", no Garage pipeline. **Do not delete**; mark unused unless the product lead keeps the Notion pipeline link for picked ideas (CLAUDE.md says accepted ideas go to the Garage pipeline). |
| `agents/*/schema.json` for `canvas-assist` | Output is the old canvas (`neutral_summary`, sections, provenance). Needs a new parts schema (out of this scope). |
| `docs/ARCHITECTURE.md` §2.2 idea file header, §2.4 machine, §2.5 table list | Superseded; record in `docs/DECISIONS.md`. |

---

## 6. Migration approach

### Recommendation: evolve in place in `public`, with one cut-over and a later cleanup — not a second schema

1. **Keep the platform spine unchanged:** `users`, `sessions`, `privacy_acceptances`, `role_grants`, `contributor_map`, `pseudonym_vault`, `vault_counters`, `llm_calls`, `llm_cache`, `jobs`, `outbox`, `audit_log`, `kill_switches`, `id_counters`, `sla_timers`, `points_ledger`, `comms_log`, `chunks`/`repo_files`/`links`/`terms`/`index_state`, `ones` (+ `one_number_history`, `one_glow_ups`, `one_showcase_briefs`), `ember_issues`, `screen_settings`, `delivery_measurements`, `voice_notes`.
2. **Re-purpose the anchors:** `ideas` (new `status` with the new CHECK, new columns from §1; drop `stage`, its trigger and old CHECKs), `attachments`, `notifications`, `deliveries`, `idea_stage_history`, `users`.
3. **Add the new domain tables** from §1 (`idea_messages`, `idea_parts`, `hidden_details`, `idea_fix`, `idea_worth`, `idea_versions`, `similar_links`, `merge_requests`, `teamup_requests`, `teamup_brought`, `crew_members`, `merges`, `question_sets`, `questions`, `answers`, `idea_decisions`, `decision_windows`, `decision_reversals`, `conversation_entries`, `build_teams`, `idea_opens`, `crew_passes`, `one_posts`, `one_post_likes`, `person_settings`, `flags`, `flag_assignments`, `flag_exposures`, `sign_in_codes`, `sign_in_intents`, `idempotency_keys`, `draft_runs`).
4. **No data migration.** All data is synthetic: truncate the idea domain at cut-over and reseed with a new synthetic fixture set (the pack's cast is fictional, so dev/UAT only, never production; NN11). `services/worker/bootstrap/demo.py` writes into most retired tables and is replaced, not patched.
5. **Freeze, then drop.** Retired tables stay read-only and unreferenced for launch (routes removed, switches deleted, jobs unscheduled); a cleanup migration drops them and the old `ideas` columns after 20 November.

Why not a fresh schema (`club.*`) alongside: (a) `ALTER DEFAULT PRIVILEGES … IN SCHEMA public` in `20261110000300_service_roles.sql` would not cover it, so every grant and revoke must be repeated; (b) the pinned privilege test checks `public` only (`format('public.%I', …)`), so a sensitive table in a new schema would escape it; (c) Kysely codegen and psycopg `search_path` both change; (d) `attachments`, `voice_notes` (FK `ON DELETE RESTRICT`), `pseudonym_vault` scopes and IDEA- numbering all key off `public.ideas`, so a second `ideas` would mean two identities for one idea. With no real data to protect, a second schema adds four days of plumbing and buys nothing. Old rules are removed by dropping their constraints and code, not by working around them.

### Migration timestamps (lane ranges, BLD-A162)

On `main` the newest migration is lane C's `20261121300110_voice_notes.sql` (FK to `ideas`, inserts `capture.voice`/`speech.hosted`), and `20261121300100` inserts `capture.mic_hint`. A lane A file (`202611211xxxxx`) **sorts before them**. dbmate applies pending versions in order, so on a fresh database lane C's inserts would run *after* a lane A cut-over and put retired switches back. Put the cut-over in a range that sorts after every existing file: lane D's reserved `202611214xxxxx` (this is the design track) or a new lane E (`202611215xxxxx`) registered in the lanes table on `main` first. Check the other worktrees' unmerged migrations before choosing; this task did not open them.

### What must survive (NN6 and the role grants)

1. There is no row-level security today (finding 0.9); protection is role grants. Keep the `ideas_web_svc` revokes on `pseudonym_vault`, `vault_counters`, `llm_cache`, `voice_notes`; `llm_calls` read-only for web; no `UPDATE`/`DELETE` on `contributor_map` for web; append-only triggers and `TRUNCATE` revoke on `points_ledger` and `audit_log`.
2. Dropping `sealed_scores`, `ai_prescores`, `assessments`, `decision_sheets`, `appeals` shrinks `HIDDEN_FROM_WEB`; change the pinned set in the same commit.
3. New tables are granted to the web role **by default**. Add explicit revokes (and add them to the pinned set) for anything that holds unmasked words or links a mask to a value: put the sharer's unmasked text in its own worker-only table (e.g. `idea_words_sealed`), not a column in `idea_messages`, so the existing table-level test covers it. `hidden_details` holds the vault tag only, never the value.
4. NN6 "database only, never the repo or the search index" now covers: the vault and hidden values, `contributor_map`, the sharer's own words, points, the people view. The repo writer and indexer may take the masked summary only (if finding 0.7 keeps the repo). The old NN6 items (core briefs, sealed scores, assessments, decision sheets) disappear with the scoring stack; update CLAUDE.md wording through the product lead, not in code.
5. Row-level security on the new private tables (`conversation_entries`, `answers`, `idea_messages`) would back the pack's sharer/crew/desk/committee matrix; it is worth adding after launch, not in these four days. Until then, enforce in the server with tests per `L-AUDIT.permissions` row.
6. Every new privileged action writes `audit_log` (NN9; `L-AUDIT.trail`), never with hidden values.
