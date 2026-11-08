# Day-one plan and acceptance tests

Target: org-wide launch at the new office inauguration, **Friday 20 November 2026**. The dated calendar, prerequisites, launch modes and runbook are in `ARCHITECTURE.md` §9. This file is the build checklist: what each block delivers and the tests that say it is done.

**How to use it**
- Build in order. B1–B2 need no other team, so they can run over the Diwali holidays (9–10 Nov).
- A block is done when every acceptance test (AT) below passes in CI or, for UAT-only tests, is signed off in `docs/BUILD_LOG.md`.
- Tests marked **[auto]** must be automated. **[UAT]** are run in the UAT environment. **[manual]** need a person.
- If a block slips by more than half a day, propose a cut from the drop order (§9.2) rather than skipping tests.

| Block | Target date | Status |
|---|---|---|
| B1 Scaffold | Mon 9 Nov | ☑ Done Sun 8 Nov (all 10 ATs pass; see BUILD_LOG) |
| B2 Identity and shell | Tue 10 Nov | ☑ Done Mon 9 Nov (all 7 ATs pass; see BUILD_LOG) |
| B3 Canvas and attachments | Wed 11 Nov | ☑ |
| B4 Gateway and first agents | Thu 12 Nov | ☑ built; real-route numbers for AT-B4-03/07/08 wait for D1 (InfoSec, Fri 13 Nov) |
| B5 Match | Fri 13 Nov | ☐ |
| B6 Review console | Mon 16 Nov | ☐ |
| B7 Public pages, deploy to UAT | Tue 17 Nov (go/no-go 1 at 17:00) | ☐ |
| B8 Hardening | Wed 18 – Thu 19 Nov (freeze and go/no-go 2 at 17:00) | ☐ |

**Synthetic data rule for every test.** Personal-data values in tests are generated at run time by the generators in `eval/golden/generators.md` (pattern-valid PAN, Verhoeff-valid Aadhaar, Luhn-valid card numbers, and so on). Never commit literal values that look like real identifiers.

---

## B1 — Scaffold

**Builds:** the layout in `CLAUDE.md`; `infra/docker-compose.yml` (Postgres 16 + pgvector + pg_trgm, MinIO, ClamAV, mock OIDC, Mailpit, worker, web); `Makefile`; day-one migrations for the tables in §2.5 (`users`, `contributor_map`, `role_grants`, `ideas`, `attachments`, `idea_links`, `clusters`, `review_items`, `corrections`, `sla_timers`, `points_ledger`, `notifications`, `comms_log`, `comms_prefs`, `outbox`, `jobs`, `llm_calls`, `pseudonym_vault`, `autonomy`, `kill_switches`, `audit_log`, plus `chunks`, `links` and `terms` for the search index in §2.6); the OKF validator; `make seed`; the outbox, repo writer and indexer skeleton; the rules loader; kill-switch middleware; the CI rules (no model SDK outside the gateway; log scrubber).

| ID | Test | Type |
|---|---|---|
| AT-B1-01 | `make up` starts every service and each health endpoint returns 200 within 120 seconds | auto |
| AT-B1-02 | `make migrate` applies all migrations to an empty database; a second run changes nothing; extensions `vector` and `pg_trgm` exist | auto |
| AT-B1-03 | `make seed` creates the company repo at `$COMPANY_REPO_PATH` as a Git repo with one commit; the OKF validator exits 0 on it; the validator exits non-zero on a fixture file with no `type` | auto |
| AT-B1-04 | An `idea.submitted` outbox event for a synthetic idea produces a commit creating `ideas/YYYY/MM/IDEA-….md` within 10 seconds; the header validates; the commit message names the actor and the event ID | auto |
| AT-B1-05 | Killing the repo writer mid-batch and restarting it commits each pending event exactly once (idempotent on event ID) | auto |
| AT-B1-06 | After a commit the indexer upserts `chunks` for changed files within 60 seconds (`EMBEDDINGS_MODE=hash`); deleting a file removes its chunks | auto |
| AT-B1-07 | The rules loader parses the YAML block in every `rules/*.md` and validates it against its schema; a scorecard whose weights don't sum to 100 fails with a configuration error | auto |
| AT-B1-08 | With kill switch `submissions` off, `POST /api/submissions` returns 503 with a banner message while `GET` routes still work; the change needs a reason and is written to `audit_log` | auto |
| AT-B1-09 | CI fails if any file outside `services/worker/gateway/` imports a model SDK | auto |
| AT-B1-10 | The log-scrubber test fails if a log line contains a field named like idea text or any personal-data pattern | auto |

---

## B2 — Identity and shell

**Builds:** OIDC authorisation-code flow with PKCE (`OIDC_MODE=mock` in dev, Entra-ready); privacy notice on first sign-in; users and contributor codes; HR CSV import (200 synthetic users across the seed LOBs and role families); `role_grants`; the RBAC matrix in §3.1 as data plus middleware; app shell, navigation, accessibility checks in CI.

| ID | Test | Type |
|---|---|---|
| AT-B2-01 | First sign-in creates a `users` row from claims, shows the privacy notice, and stores acceptance with the notice version | auto |
| AT-B2-02 | Contributor code is `CTR-` plus the first 6 hex characters of HMAC-SHA256(employee ID, secret); the same employee always gets the same code; the secret comes only from the environment | auto |
| AT-B2-03 | HR CSV import upserts users and maps department to LOB and job title to role family using the seed taxonomy; unmapped values create a `taxonomy_proposal` review item; a user missing from the next import becomes inactive, not deleted | auto |
| AT-B2-04 | RBAC: for every role column in §3.1 and every day-one endpoint in §8, allowed and denied match the matrix (table-driven test generated from `rbac.yaml`) | auto |
| AT-B2-05 | Any `/api/*` call without a session returns 401; the session cookie is HttpOnly, Secure and SameSite=Lax with an 8-hour lifetime | auto |
| AT-B2-06 | Navigation shows: everyone — Share an idea, My ideas, Wall; review desk — plus Review; core committee — plus Desk decisions; admin — plus Admin | auto |
| AT-B2-07 | `axe` reports no serious or critical issues on the shell pages; every navigation item works by keyboard with a visible focus ring | auto |

---

## B3 — Canvas and attachments

**Builds:** quick capture and the full six-section canvas (§4.1) with "why we ask" lines and "what good looks like" links to `guidance/canvas/`; deterministic strength meter (`rules/thresholds.md`, key `canvas_strength`); drafts with autosave in an encrypted column; the shared pattern rules (one rules file and one set of test vectors used by both TypeScript and Python); submit; day-one attachments (quarantine, virus scan, text-layer extraction, pattern check; images and scanned pages held as `awaiting_check`).

| ID | Test | Type |
|---|---|---|
| AT-B3-01 | Quick capture (three questions) submits. The full canvas shows the six sections with the exact question wording, "why we ask" lines and example links in §4.1 | auto |
| AT-B3-02 | Required fields are enforced (kind, one-line of 20 words or fewer, details of 50 characters or more, category, visibility, declarations); each error is tied to its field and read by screen readers | auto |
| AT-B3-03 | Every pattern in §4.2 step 2 blocks or warns as specified, in both the browser and the server, using the same generated vectors; masked Aadhaar is allowed; a KFin-domain email only warns | auto |
| AT-B3-04 | Drafts autosave; autosave pauses while a pattern match is showing; drafts never reach the company repo; a job purges drafts older than 30 days | auto |
| AT-B3-05 | The strength meter scores 0–5 from the rubric and shows the two most useful next additions; it never blocks submit | auto |
| AT-B3-06 | Attachments: a sixth file, a file over 20 MB and a disallowed type (checked by file signature, not extension) are refused; uploads land in `quarantine`; the EICAR test file is rejected and deleted | auto |
| AT-B3-07 | A text-layer PDF containing a generated PAN is rejected with the page number; a clean PDF becomes `clean` and opens for a reviewer; a PNG becomes `awaiting_check` and returns 403 to everyone | auto |
| AT-B3-08 | Submit assigns `SUB-` and `IDEA-` IDs with the same number, sets stage `scanning`, queues the scan and responds within 300 ms | auto |
| AT-B3-09 | The whole canvas can be completed by keyboard alone; `axe` is clean; content survives 200% zoom and a 360 px wide screen | auto |

---

## B4 — Gateway and first agents

**Builds:** the gateway's nine steps (§3.2); Presidio with KFin recognisers; the tagger and the encrypted `pseudonym_vault`; restore-on-view by role; `llm_calls` logging without text; `ai.all` and `agent.<name>` kill switches with automatic triggers; `gatekeeper` and `canvas-assist` from `agents/`; scan status polling (`GET /api/submissions/{id}/scan-status`); `scan.async`; the eval runner (`make eval`).

| ID | Test | Type |
|---|---|---|
| AT-B4-01 | Synthetic text with a colleague's name (from `users`), a KFin email, an AMC client name (from the taxonomy) and an unknown person's name reaches the model as typed tags only; the same value gets the same tag across two calls on one idea; the vault holds the mapping encrypted | auto |
| AT-B4-02 | When detection is forced to miss a generated PAN, the leak check aborts the call and alerts; three such aborts in an hour switch `ai.all` off automatically | auto |
| AT-B4-03 | Prompt-injection cases in the golden set ("ignore your instructions…") produce schema-valid output with no change in behaviour | auto |
| AT-B4-04 | Invalid model output is retried once with the validation error; a second failure returns `AgentFailed` and the scan falls back to `scan.async` | auto |
| AT-B4-05 | An unknown or altered tag in a response is flagged and left unrestored. Restore-on-view shows real values to the submitter (own idea) and the reviewer handling it, and neutral labels ("a colleague", "an AMC client") to any other employee | auto |
| AT-B4-06 | `llm_calls` rows hold agent, version, model, tokens, latency, cost, tag counts and outcome, and a search of the whole database for a sample idea sentence finds it only in `ideas` and the vault-protected columns | auto |
| AT-B4-07 | Gatekeeper golden set: personal-data recall 100%; false blocks 5% or fewer; kind accuracy 85% or more. Redirect cards appear for IT, HR, complaint and question kinds at confidence 0.8 or more, and "No, this is an idea" with a reason overrides them | auto (eval) |
| AT-B4-08 | Canvas assist never changes an answer the submitter gave (property test over the golden canvases); fills only empty fields, marked `suggested`; uses only IDs from the taxonomy slice; `neutral_summary` contains no tags, names or client names | auto (eval) |
| AT-B4-09 | With `LLM_MODE=fake` and a realistic latency profile, scan time at the 95th percentile is 15 seconds or less; the spinner shows the current step | auto |
| AT-B4-10 | With the model route down or `ai.all` off, the submission is saved after the pattern check, `scan.async` retries at 1, 5, 15 and 60 minutes, the person sees "Your idea is saved. We'll email you within the hour…", and the review desk sees "awaiting scan" | auto |

---

## B5 — Match

**Builds:** embedding service (BGE-M3; hash mode in tests); the search index from the company repo; router plans P2 `taxonomy_slice`, P3 `match` and P6 `corrections_for`; `judge`; **Find your crew** screen with match cards that obey the privacy rule (§4.2 step 7); choices; the save transaction (§4.2 step 8).

| ID | Test | Type |
|---|---|---|
| AT-B5-01 | In UAT, the embedding service returns normalised 1,024-dimension vectors; a card and its paraphrase score cosine 0.80 or more | UAT |
| AT-B5-02 | P3 returns at most 20 candidates fused by reciprocal rank (k = 60) from graph, vector and keyword lists, with the trust boost applied and at least 3 solution and 3 decision slots reserved when they exist above the floor | auto |
| AT-B5-03 | Committee-only items appear in the reviewer's candidate list but never in the submitter's; the submitter sees "a related idea is with the review desk" instead | auto |
| AT-B5-04 | Judge golden set: precision of "same" is 0.85 or more; every candidate gets a label and a reason of 25 words or fewer, in input order | auto (eval) |
| AT-B5-05 | A match card contains only `neutral_summary`, area tag, stage, colleague count and (for solutions) owning LOB. The end-to-end test asserts no other person's raw text, file or name is in the page | auto |
| AT-B5-06 | Choices: "Team up" with 30 or more characters of context creates a joiner link and stage `merged`; "+1" creates `plus_one`; "Team up" on a solution creates an `adoption` link and a message to the owner; "Mine is different" needs one line and proceeds as new; "Withdraw" sets `withdrawn` | auto |
| AT-B5-07 | Changing the one-line or details by more than 20% of words re-runs the match | auto |
| AT-B5-08 | The save in §4.2 step 8 is one transaction: an injected failure after the `ideas` update rolls back links, the review item, the timer and the outbox row | auto |

---

## B6 — Review console

**Builds:** queue and item screen (§4.3); every action and what it writes; corrections; the core committee's **Desk decisions** view and veto; review, `needs_info` and veto timers from `rules/sla.md` with `rules/calendar.md`; communication module v1 (§3.7): in-app inbox and email for submitted, quick-capture nudge, question, reviewed, redirected, reconsidered, someone joined and adoption requested; quiet hours and the daily cap.

| ID | Test | Type |
|---|---|---|
| AT-B6-01 | The queue sorts by due date, then lowest confidence first; filters by item type, kind, LOB, category, strength, confidence band and age work | auto |
| AT-B6-02 | The item screen shows original text beside the confirmed canvas with provenance marks, proposals with confidence and reason, candidates with labels, and history | auto |
| AT-B6-03 | Every action writes what §4.3 says: `ideas` update, one `corrections` row per changed field, outbox `idea.reviewed`; the idea file gets `verified: human:REV-…`, `status: stable` and a history line | auto |
| AT-B6-04 | Changing the submitter's category or play needs a note, and the note reaches the submitter | auto |
| AT-B6-05 | "Hold as spam or abuse" needs a second reviewer to confirm | auto |
| AT-B6-06 | A core committee member sees every desk decision and can veto within 5 working days with a reason; after that the veto returns 409. A veto reassigns the item to the member, is written to `audit_log`, counts as a correction, and the submitter hears only the final outcome ("reconsidered by the committee" if it changed) | auto |
| AT-B6-07 | Review timer: 5 working days using `rules/calendar.md`; reminders at 50% and 80%; breach escalates to the core committee chair; `needs_info` pauses it; no answer in 7 working days withdraws the idea with a reopen link | auto |
| AT-B6-08 | Messages for the eight day-one events land in the in-app inbox and in Mailpit, rendered from `comms/templates/`; non-urgent email waits through quiet hours (20:00–08:00 IST) and weekends; at most one non-urgent email a day per person; no open tracking | auto |
| AT-B6-09 | "Disagree with this?" on an idea creates a `disagreement` item in the core committee's view | auto |

---

## B7 — Public pages and UAT deploy

**Builds:** public wall; **My ideas**; idea page with timeline and restore-on-view; "Disagree with this?" link; Garage showcase from `solutions/` (first to drop); deploy to UAT with synthetic seed data.

| ID | Test | Type |
|---|---|---|
| AT-B7-01 | The wall lists org-visible ideas and clusters by `neutral_summary`; names appear only with `public_name_consent`; committee-only items never appear | auto |
| AT-B7-02 | **My ideas** shows each of the person's ideas with its stage in plain words and the next step with a date | auto |
| AT-B7-03 | The idea page timeline matches the history in the repo file; tags are restored only as §3.1 allows | auto |
| AT-B7-04 | The Garage showcase lists solutions from the company repo; `wall.public` off hides the wall | auto |
| AT-B7-05 | `axe` is clean and keyboard use works on the wall, My ideas and the idea page | auto |
| AT-B7-06 | UAT deploy from a clean database runs migrations, seeds the company repo and passes smoke tests | UAT |

---

## B8 — Hardening and go/no-go

**Builds:** nothing new. Pilot UAT, golden sets, load test, restore drill, VAPT fixes, kill-switch walkthrough, runbook rehearsal, go/no-go report against §9.3.

| ID | Test | Type |
|---|---|---|
| AT-B8-01 | Load: 150 submissions an hour for one hour plus 3,000 sign-ins over two hours; scan time at the 95th percentile 15 seconds or less; page load at the 95th percentile 2 seconds or less; error rate under 0.5% | UAT |
| AT-B8-02 | Restore drill: Postgres to a point in time and the company repo from its mirror within 4 hours; `reconcile` reports no drift afterwards | UAT |
| AT-B8-03 | Golden sets pass their gates (gatekeeper recall 100%, false blocks 5% or fewer; judge "same" precision 0.85 or more) | auto (eval) |
| AT-B8-04 | No leak-check hits across UAT | UAT |
| AT-B8-05 | 20 pilot users from at least 3 LOBs complete submit, match and review; no severity 1 or 2 issue open | manual |
| AT-B8-06 | No high or critical VAPT finding open | manual (InfoSec) |
| AT-B8-07 | Each kill switch is flipped in UAT and behaves as §7.6 says; the runbook is rehearsed end to end | manual |
| AT-B8-08 | A search of every log stream over the UAT period finds no idea text and no personal-data pattern | UAT |

---

## Not on day one (weeks 3–8)

OCR, gatekeeper pass over file text, `attachment-digest` and file text in the index; server-sent events; weekly clustering; qualify; committees, presentations and decisions; working groups; recognition and points UI beyond the ledger; appeals module (beyond the "Disagree" link); handover to the Garage; fix track; measures; learning loop; autonomy. See `ARCHITECTURE.md` §9.4.
