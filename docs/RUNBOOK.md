# Operations runbook

For: the product lead, IT on-call and InfoSec, running The Garage · Ideas in UAT and production. Every command below runs in the worker container (`docker compose … exec worker …`) unless it says otherwise. Synthetic data only outside production.

## 1. Alerts

Alerts are rows in `audit_log` with an `alert.` action and error-level log lines. Logs carry IDs and counts only, never idea text.

| Alert | Raised when | First step |
|---|---|---|
| `alert.kill_switch_auto` on `ai.all` | Leak check fired for 3 different ideas within an hour | Section 4.1 |
| `alert.kill_switch_auto` on `agent.<name>` | That agent's error rate passed 20% for 15 minutes, or its golden set failed on deploy | Section 4.2 |
| `alert.kill_switch_auto` on `attachments.upload` | The virus scanner did not answer for 5 minutes | Section 4.3 |
| `alert.kill_switch_auto` on `comms.email` | More than 5% of email bounced in an hour (20 or more sent) | Section 4.4 |
| Log `reconcile.visibility_drift` | An idea file shows a different visibility than the database | Section 4.6, treat as urgent |
| Log `health.worker_check_failed` | The web app cannot reach the worker with its token | Section 4.5 |
| `alert.repo_writer_dead_letter` on `outbox:<id>` | The repo writer can never write a document event as it stands (`doc_exists`: a file the product team added by hand; `personal_data_in_doc`; a record no longer approved) | Section 4.8 |

Nothing switches itself back on. A person checks the cause, then flips the switch back with a reason.

## 2. Kill switches (§7.6)

Flip from **Admin → Kill switches** with a reason of at least 10 characters. Every change is audited. Each process reads switches through a 10-second cache, so a change takes up to 10 seconds to reach everyone. If the Admin page is unreachable: `python -m core.killswitch set <name> <on|off> --reason "…" --actor ops:<staff code>`.

| Switch | Flip it off when | Who | What people see | Check it worked |
|---|---|---|---|---|
| `ai.all` | Any leak-check hit, a model incident, or the route is withdrawn | Admin, InfoSec | Banner: the assistant is taking a break. Ideas are saved after the pattern check; scans queue and run when it is back on. While the assistant (ai.all) or the gatekeeper is switched off, nobody can add files: new files wait as 'checking' and end as 'Didn't upload' if it stays off. People can still send their idea after removing the file. (Non-negotiable 4, BLD-C107.) | Banner on the home page; new scans show "waiting" and run when it is back on; a file added meanwhile stays "checking" |
| `agent.<name>` | One agent misbehaves | Admin | Nothing new; that step goes to the review desk as "manual" | Review items show the step as manual |
| `agent.gatekeeper` | The gatekeeper misbehaves (personal details missed or wrongly found) | Admin, InfoSec | While the assistant (ai.all) or the gatekeeper is switched off, nobody can add files: new files wait as 'checking' and end as 'Didn't upload' if it stays off. People can still send their idea after removing the file. (Non-negotiable 4, BLD-C107.) | A file added meanwhile stays "checking" |
| `agent.handover-draft` | The drafted handover packs are unhelpful or wrong | Admin | "Draft it with the assistant" says the assistant can't draft just now; people fill in the pack themselves | `POST /api/delivery/{id}/pack-draft` answers 503 `assistant_unavailable`; nothing else changes |
| `agent.role-themes` | Proposed friction themes are wrong or unsafe | Admin | Nothing for employees; no new theme sets are proposed, approved ones stay on the lenses page until declined | The Monday `role_themes` loop records failures as a count and proposes nothing |
| `attachments.upload` | Scanner down, or a suspicious file wave | Admin, InfoSec | Banner; upload is hidden; files already uploaded stay | Upload answers 503 |
| `attachments.open` | Any doubt about a stored file | InfoSec | No one can open or download a file | File links answer 503 |
| `submissions` | Abuse wave, data incident, or maintenance | Admin | Read-only mode: browse and track, not share or edit; banner explains | "Share" answers 503; My ideas still loads |
| `matching.show` | Matches look wrong or revealing | Admin | Submitters see "we will show you colleagues a little later"; the desk still sees matches | A new scan shows no crew cards |
| `comms.email` | Bounces, wrong content, or mail service trouble | Admin | Emails queue; in-app messages carry on | `notifications` with `channel = 'email'` stay `queued` |
| `wall.public` | A bad summary on the wall, or an HR request | Admin, HR | The wall and everyone else's view of idea pages are hidden; owners and the desk keep theirs | `/api/wall` answers 503 |
| `ones.public` | A brief or name that should not be public, or an HR request | Admin, HR | The Ones disappear from the wall, the home carousel and the office screens; the console and each One's own dashboard keep working | `/api/ones` answers 503; the screen says the Ones are resting |
| `learning.jobs` | A learning report or proposal looks wrong, or the jobs load the database at a bad time | Admin | Nobody outside the product team notices; the Learning page shows "Off" and "Run it now" is disabled. Proposals already made can still be decided | `POST /api/learning/run` answers 503; no new `learning_reports` rows next morning |
| `ember.send` | An issue of The Ember has a mistake, or it should wait (for example while the Ones are paused) | Admin | Nothing visible; "Send to everyone" on Write The Ember says sending is paused. Past issues stay readable | `POST /api/ember/{id}/send` answers 503; queued `ember.issue` emails stay queued |
| `solutions.publish` | A published write-up turns out wrong, or new write-ups should wait (for example a naming concern) | Admin | The sponsor's "Approve and publish" says publishing is paused; drafts and submissions carry on, and nothing already published changes | `POST /api/delivery/{id}/writeup/approve` answers 503; the worker refuses `publishing_paused` |
| `committee.flow` | Committee reviews, decisions or their messages go wrong, or the committee needs a pause | Admin | Committee actions answer with "The committee's reviews and decisions are switched off for now." Scoring, revealing, deciding, presentation sessions, the desk's qualify step, the panel's appeal decisions and admins clearing conflict flags stop; core members get Desk decisions back in the menu (after a page reload). Groups approved meanwhile start their qualify step when it is back on | `POST /api/committee/rounds/{id}/action` answers 503; the core committee's menu shows Desk decisions, not Committee |
| `appeals.filing` | Appeals arrive in a wave that needs handling first, or the appeal form misbehaves | Admin | Banner: "Appeals are paused for a short while." Nobody can file a new appeal; appeals already filed carry on with the panel | `POST /api/appeals` answers 503 |
| `clusters.batch` | The weekly grouping proposes wrong or revealing groups | Admin | Nothing for employees; the review page says weekly grouping is switched off and hides "Run the grouping now", and the Sunday 22:00 run skips itself. Groups already approved stay | The review page shows the switched-off notice |
| `attachments.deep_check` | The deep file checks (OCR, the gatekeeper on file text) misbehave or overload the worker | Admin, InfoSec | Files with a text layer get the day-one checks (virus scan, then the personal-data patterns) and no assistant's summary. Images and scanned pages added meanwhile are kept aside for a closer check, and are checked within 15 minutes of switching back on | A photo added after the switch stays "kept aside"; a text file shows no "Assistant's summary" on its review item |
| `capture.mic_hint` | InfoSec asks for the keyboard-mic tip to come down, or it confuses people | Admin, InfoSec | The tip under the quick capture box disappears; the box, files and sharing are unchanged | A new quick capture shows no "Tap the mic on your keyboard" line |
| `capture.voice` | **ON AT LAUNCH, from the migration** (DEC-108, confirmed by the product lead with the DPO's approval on 17 Nov; non-negotiable 2's voice exception). Migration `20261122300530` switches it on with `speech.hosted` (only where a migration left it off). Speech to text goes through Sarvam (`SPEECH_MODE=sarvam`, worker-only `SARVAM_API_KEY`). Deploy must set `SARVAM_API_KEY` in the database env file and `SPEECH_HOSTED_APPROVAL` (DEC-108, the default) before the smoke check; with both switches on and no key, the smoke check fails and the go/no-go report shows voice not met (Mode B), on purpose. **The key guard flips it:** outside dev and test, with `SPEECH_MODE=sarvam` and no key, the watch switches it and `speech.hosted` off with "Sarvam key missing (automatic)", audited, and nothing switches them back on when the key arrives: set the key, restart the worker, then switch both on here with a reason. The watch also switches it off with the fake route, or `local` without the isolated speech service (BLD-C007, BLD-C012); that engine is an allowed fallback. Switch it off if voice misbehaves, Sarvam is down or slow, or InfoSec or the DPO asks. When a switch pauses a note mid-recording, the proxy blocks `chunk` and `end`; the worker ends the note after about 20 seconds without a chunk and keeps the words, which `GET /api/drafts/{id}/voice/{stream}` returns (S-04 polls it) | Admin, InfoSec | Off: the mic shows voice as paused ("Voice notes are coming soon." until the pack gives a paused line); typing, files and sharing are unchanged. Go/no-go: off is a row to confirm, off with "Sarvam key missing (automatic)" and on without a working route are not met | `POST /api/drafts/{id}/voice/start`, `/chunk`, `/end` and `POST /api/submissions/{id}/voice` answer 503 `paused` |
| `speech.hosted` | **ON AT LAUNCH, from the migration** (DEC-108). Every Sarvam call refuses unless this switch is on (read fresh), `SPEECH_HOSTED_APPROVAL` names the approval (DEC-108) and `SARVAM_API_KEY` is in the worker's env (never the web's). Translation and Listen go to Sarvam whenever that gate passes, whatever `SPEECH_MODE` says; switch it off to stop every call to Sarvam at once. It goes off by itself with the key guard above, and when Sarvam's own failures pass 20% of at least 10 calls in 15 minutes (`speech_calls`; bad or short audio is not counted, BLD-C110, BLD-C117). Nothing switches it back on: check `speech_calls` (codes only), then switch it on with a reason | InfoSec | Off: voice notes pause and Listen falls back to the browser's on-device voice. Go/no-go: on without the approval or the key, or off with "Sarvam key missing (automatic)", is not met | Sarvam calls refuse with `hosted_switched_off`, `hosted_not_approved` or `hosted_key_missing`; `/api/ideas/{id}/listen` answers 503 `paused` |
| `scan.live` | The live progress stream misbehaves or loads the web servers | Admin | Nothing visible; the waiting screen checks every few seconds instead of live | `GET /api/submissions/{id}/scan-events` answers 503 |

**Walkthrough (AT-B8-07).** In UAT, flip each switch off and on again in the order above and tick the "Check it worked" column. The automated version runs in `make test` (`tests/test_b8_switch_walkthrough.py`).

## 2a. The Ones (DEC-040 to DEC-087, DEC-106)

The Ones console, its proposals, awards and the "Announce new Ones" email are retired (DEC-106, BLD-E049). A person becomes a One when their shipped idea's measured difference is confirmed (L-ONES.rules/1): the programme team enters the measurements, and Finance's confirmation for money, on the admin page (`/admin`). Money shows publicly only once Finance has confirmed it. On the same page an admin marks a **Founding One** by work email, and removes a One after a confirm step (BLD-A217). The committee, the CEO and admins read and print a One's Showcase brief at `/ones/showcase/:id`. A glow-up message invitation made before the retirement can still be answered at `/ones/write/:id`.

**Office screens:** open `/constellation` signed in on the screen's account and choose Full screen. It shows the static sky and alternates with impact cards. Ambient mode for events is set through `PUT /api/ones/screen-mode` (admin); the console's button is retired. Pause is on the screen itself.

**Founding Ones** (DEC-053): the product lead sends names and one-line citations, and an admin marks each one on the admin page. Numbers then follow in order, as long as nobody has been inducted before.

## 2b. Delivery, lenses and learning (BLD-115 to BLD-124)

**Delivery** (`/delivery`). A core committee member or an admin starts the handover for a picked idea from "Picked, waiting for a handover". The owner fills in the pack and sends it; the named sponsor approves it. Until live sync is built, an admin pastes the delivery pipeline's page ID ("Link the pipeline page") and the delivery PM records each step ("Record the current step"); choosing Shipped opens the 30- and 90-day results. On the fix track the owner keeps the action plan and sends the before-and-after numbers for the sponsor. Results: the owner fills them in, the sponsor confirms; for money, an admin presses "Finance has confirmed the money" only after Finance has confirmed it in writing. Nobody else can do these steps for them; if a sponsor leaves, an admin names a new one in the pack (it must still be waiting for approval) or grants the sponsor role.

**Stuck deliveries.** `delivery.tick` (09:30) reminds owners of results due within 3 days, sponsors of results waiting 5 working days, fix-track owners every Friday, and flags overdue milestones (once), plans 10 working days late (to the chair, once) and builds blocked for 10 working days (to the sponsor, once). To see what it did: `SELECT action, count(*) FROM audit_log WHERE action LIKE 'delivery.%' AND at > now() - interval '1 day' GROUP BY 1`.

**Lenses** (`/lenses`) rebuild on Mondays at 05:00; an admin can press "Rebuild now". Counts only; to name the colleagues behind a count, use Admin's reveal (with a reason; it is logged).

**Learning** (Admin, then "Learning reports and proposals"). Approve or decline each proposed glossary term or area-tag group; approving records the decision only, and the product team then adds the term or tag to the company repo by hand. Acceptance rates are for information: nothing switches to automatic at launch.

**Learning from the core committee** (Committee, then Desk decisions, then "What the platform learns from your decisions"; core committee only). Proposed scorecard weights wait for the chair and proposed scoring bands (the shortlist line, confidence multipliers) for any core committee member. Approving records the decision only: the product team then edits `rules/scorecard.md` or `rules/routing.md`, bumps the version and records the committee's approval in the pull request. If approving answers "On hold", lane B's fairness report (`/reports`) shows a gap of 25 points or more in shortlist or pick rate between LOBs or locations; look there, then decide again or decline. If it answers "Not enough people in each group yet", fewer than two LOBs or two locations have 5 or more people in the report; wait for more decisions or decline. A loop that fails logs `learning.failed` with the loop's name and the error's type; the other loops that day still run, and the failed one can be run again from the Learning page. To see what was decided: `SELECT action, entity, at FROM audit_log WHERE action IN ('learning.approved', 'learning.declined') ORDER BY at DESC LIMIT 20`.

### The speech service's image (BLD-C032)

The speech service's base image is pinned by digest and every Python package by version and hash; nothing else gets in. To refresh them (a security fix, or a newer engine), on a machine with network access:

1. Packages: in `services/worker/speech_service/`, run `uv pip compile requirements.in --universal --generate-hashes --python-version 3.12 --exclude-newer <a date two weeks back> --no-header -o requirements.txt`. Read the diff: every package that changed, and why.
2. Base image: look up the current multi-architecture digest of `python:3.12-slim` (`docker buildx imagetools inspect python:3.12-slim`, or the registry's API) and put it in the `FROM` line of `services/worker/speech_service/Dockerfile`.
3. Rebuild with `COMPOSE_PROFILES=speech docker compose build speech`, run `make test` (the contract and compose tests), then deploy through UAT as usual.

## 3. Scheduled jobs to watch

| Job | When (IST) | Healthy when |
|---|---|---|
| `reconcile` | 02:00 | Log `reconcile.clean`; any `reconcile.drift` is read the same morning |
| `drafts.purge` | 03:30 | Drafts older than 30 days gone |
| `comms.nudges`, `comms.digest` | 10:00, 10:30 (digest Mondays) | No `comms.send_failed` bursts |
| `learning.run` | 05:30 (each loop on its own day: daily; Mondays, including committee agreement; the 1st, including what the committee rewards and scoring bands; quarter starts) | Log `learning.ran` per loop, or `learning.switched_off` while `learning.jobs` is off; any `alert.drift_*` row is read the same morning |
| `lenses.build` | Mondays 05:00 | Log `lenses.built` with the LOB and role counts |
| `delivery.tick` | 09:30 | Log `delivery.tick` with its counts |
| `voice.sweep` | Every 15 minutes | Log `voice.swept` with `deleted_count`, `failed_count` (notes it could not delete this run; they are tried again) and `orphan_count` (bucket objects older than 25 hours that no row was tracking); no `voice_notes` row older than 24 hours without `deleted_at` (DEC-096) |
| `desk.clocks` | Every 5 minutes | Lane B's one sweep (`desk.clocks.run_due`): a Not now whose return date has come goes back to the review desk, a committee window past its end is recorded as expired, and a sharer is reminded 1 day and 2 hours before an answer is due. Log `desk.sweep` with `returned`, `windows_closed`, `reminded` and `failed` (counts only); a `desk.sweep.item_failed` line names the kind and the row's ID, never text, and the rest of the sweep carries on. A run that finds the last one still going logs `desk.sweep.busy` and does nothing. Repeated `failed` for the same ID: read that row by ID and tell lane B |
| Voice notes, what a person sees and how long text is held | Continuous | A person's browser asks for the text every 2 seconds and stops after 5 minutes ("We couldn't turn that into text just now"); any text it never fetched is deleted by `voice.sweep` within 24 hours. A failed note is deleted at once. The quarantine bucket's own rule expires `voice/` after a day (IT; UAT.md) |
| The speech service (`speech` container, BLD-C015) | Continuous, only when voice notes are on | Its health check (`/health`) is green and says `ready: true` with the engine `faster-whisper`. One recording at a time; each has a wall-clock limit (`SPEECH_TIMEOUT_S`, 300 s), after which the engine child is killed and restarted (the model reloads) and that note fails as `engine_timeout`; a crash fails it as `engine_crashed`. The worker retries a note while the service is unreachable. It logs no request and no text. If it is down, voice notes wait and then fail; switch `capture.voice` off with a reason while it is fixed |
| `points.sync` | Every hour | Log `points.synced` with a count when it adds anything. Points are private: nobody reads anyone else's |
| Ticker (every 20 s, checks every minute) | Continuous | Email goes out; reminders and breaches appear; the watches run |

## 4. Incidents

### 4.1 Leak check fired (`ai.all` off)
1. InfoSec reads the `llm_calls` rows with `outcome = 'leak_abort'` (IDs, agent, error code; no text is stored).
2. Find which pattern the tagged payload still matched: rerun that scan in a dev copy with synthetic text of the same shape, or ask the person to edit.
3. Fix the tagger or the pattern, add a golden case, and run the golden sets on the real route (`python -m evalrunner`, or `make eval` from a checkout).
4. Switch `ai.all` back on with the change reference as the reason. Queued scans run.

### 4.2 An agent switched itself off
1. Check its error codes in `llm_calls` for the last hour, or the eval report in `eval/reports/`.
2. Roll back its `config.yaml` version if a change caused it, run `python -m evalrunner`, then switch it back on.

### 4.3 Scanner unreachable (`attachments.upload` off)
1. Check the scanner host in the smoke report (`python -m bootstrap.smoke`), and `CLAMAV_HOST`.
2. When it answers again, switch uploads back on: the switch never comes back on by itself. Files still in quarantine are checked on their job's next retry; a file whose retries ran out was rejected as "check failed", and the person is told to upload it again.

### 4.4 Email bouncing (`comms.email` off)
1. Look at `notifications` with `state = 'failed'` and `error_code = 'smtprecipientsrefused'` in the last hour (IDs only). Only refusals the mail server gives at send time are seen; delivery reports that arrive later in the Graph mailbox are not read on day one.
2. Fix the cause (addresses from HR import, mailbox limits), then switch email back on. Bounces from before you switched it on are not counted again. Queued email goes out within working hours.

### 4.5 Web cannot reach the worker
`GET /api/health?deep=1` on the web app says `worker: refused` (wrong `INTERNAL_API_TOKEN`) or `unreachable` (worker down). Restart the worker; check both services read the same token from the vault.

### 4.6 Reconcile drift
Run `python -m reconcile --report-only`. Index drift fixes itself at 02:00 or with `python -m reconcile`. `idea_visibility_mismatch` means an idea file in the company repo shows the wrong visibility: switch `wall.public` and `matching.show` off until the repo writer has rewritten the file (any review action on the idea rewrites it), then rerun reconcile.

### 4.7 Repo writer behind
`SELECT count(*), min(created_at) FROM outbox WHERE committed_at IS NULL AND dead_lettered_at IS NULL` growing, or rows with `last_error`, means the writer is stuck. The app keeps working; restart the worker. A `last_error` code that repeats needs a fix before restart.

Two log lines mean the writer is waiting on purpose (BLD-A167). `repo_writer.waiting_for_seed` (a warning after 60 seconds) means a seed holds the marker `.kfin-ideas.seeding` next to the company repo. Let the seed finish. If no seed is running, the seed was killed: delete the marker, and the writer carries on at its next round. `repo_writer.repo_has_no_commit` means the company repo was initialised but never committed, which is a seed's first moments or a bad restore. If it lasts, restore the repo from backup (§5) or seed it again on an empty folder. Never commit to it by hand.

### 4.8 A dead-lettered repo event (BLD-143)
Document events the writer can never commit (solutions, glossary terms, area tags) leave the queue so later writes carry on: `SELECT id, event_type, aggregate_id, last_error FROM outbox WHERE dead_lettered_at IS NOT NULL`. Fix the cause first: for `doc_exists`, decide with the product team whether the hand-added file stays (then leave the event dead) or goes (remove it through a normal repo commit); for `personal_data_in_doc`, have the owner change the write-up or the definition and approve or publish it again, which queues a fresh event. To retry the same event once the cause is gone: `UPDATE outbox SET dead_lettered_at = NULL, attempts = 0, last_error = NULL WHERE id = <id>`, and note who and why in `audit_log` (`INSERT INTO audit_log (actor, action, entity) VALUES ('user:<id>', 'repo_writer.dead_letter_retried', 'outbox:<id>')`). Never edit the event's payload.

### 4.9 Rolling back the delivery evidence migration (`20261118000100`)
Its down step deletes the delivery attachments' rows but cannot reach the object store, so their files stay in the `quarantine` and `clean` buckets. Before rolling back, list them with `SELECT store_key FROM attachments WHERE delivery_id IS NOT NULL` and remove each key from both buckets (`mc rm <alias>/<bucket>/<key>` in dev; KFin's storage tooling in UAT and prod). Left behind, they are unreachable from the app but still hold the uploaded files.

## 5. Restore (AT-B8-02, target 4 hours)

1. **Database (IT):** restore Postgres to the chosen point in time from the base backup and WAL archive, into a new instance. Use the same `VAULT_ENCRYPTION_KEY`, or the pseudonym vault and drafts cannot be read.
2. **Company repo:** `git clone <COMPANY_REPO_REMOTE>` into the data folder.
3. **Point the services** at the restored database and repo; start them.
4. **Check:** `python -m reconcile --report-only` shows no drift beyond what was there before; `python -m bootstrap.smoke` passes.

Rehearse with `scripts/ops/restore-drill.sh` (dump and bundle instead of point-in-time; same checks). The last drill's time goes into the go/no-go report.

## 6. Load test (AT-B8-01)

From the test Mac or a machine with `uv`, against UAT (needs a sign-in route for the synthetic load accounts, agreed with IT):

```bash
cd services/worker && uv run python -m loadtest --base-url https://<uat host>       # the full hour
uv run python -m loadtest --base-url http://localhost:3000 --scale 0.1               # a 6-minute rehearsal
```

Pass: scan time p95 15 s or less, page p95 2 s or less, error rate under 0.5%. The report lands in `.data/loadtest/`.

## 7. Logs (AT-B8-04, AT-B8-08)

```bash
docker compose logs --no-color --no-log-prefix web worker | (cd services/worker && uv run python ../../scripts/ci/check_logs.py -)
```

It prints only line numbers, kinds and field paths, never the value. Any hit is an incident under non-negotiable 3: find the log call, fix it, add a scrubber test.

## 8. Go/no-go report (§9.3)

In UAT, inside the worker (it reads the UAT database and the reports kept in the data folder):

```bash
python -m gonogo --since 2026-11-16 --vapt-open-high <n> --sso-ready yes \
  --loadtest-dir /data/loadtest --drill-dir /data/ops --out /data/gonogo/report.md
```

Copy the load test report and the restore drill result into `/data/loadtest` and `/data/ops` first. It reads the golden-set reports (`EVAL_REPORTS_DIR`), leak aborts since the date, the latest load test and restore drill, and the privacy notice version, then names the launch mode the evidence supports: Mode A only when every criterion is met. Rows marked "confirm" need a person's sign-off at the meeting.

Below the table it prints how often the gateway dropped canvas-assist suggestions the person's words did not back (`ungrounded_dropped`) and refused its answer (`invalid_output`), for the last 24 hours, since launch (`--launch`, default 2026-11-20) and in golden-set runs since `--since` (DEC-095, DEC-097, BLD-C029). **Read it on the first real-route golden-set run once D1 is approved, and again before go-live.** A refused share near 20% would trip the automatic switch-off of `agent.canvas-assist` at launch (20% of failed calls over 15 minutes, at least 10 calls). If it is high, read the dropped and refused cases by ID in `llm_calls` (never text), fix the prompt and run `make eval` again before switching anything on. A dropped share well above 10% means the assistant keeps reaching past the person's words: tell the product team.

## The Ember, each month

1. In the last week of the month, an admin opens **Write The Ember** (`/ember/compose`) and starts the month's issue.
2. The core committee chair writes "What the committee looks for" there (up to 90 words, no names of colleagues or clients).
3. An admin reads the preview and presses **Send to everyone**, then **Yes, send to everyone**. It goes out through the usual email rules (working hours, one routine email a day, then the digest).
4. Sent issues stay in the archive at `/ember`. To stop a send in progress, switch `ember.send` off: queued Ember emails wait.
