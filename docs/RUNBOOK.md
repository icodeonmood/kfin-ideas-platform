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

Nothing switches itself back on. A person checks the cause, then flips the switch back with a reason.

## 2. Kill switches (§7.6)

Flip from **Admin → Kill switches** with a reason of at least 10 characters. Every change is audited. Each process reads switches through a 10-second cache, so a change takes up to 10 seconds to reach everyone. If the Admin page is unreachable: `python -m core.killswitch set <name> <on|off> --reason "…" --actor ops:<staff code>`.

| Switch | Flip it off when | Who | What people see | Check it worked |
|---|---|---|---|---|
| `ai.all` | Any leak-check hit, a model incident, or the route is withdrawn | Admin, InfoSec | Banner: the assistant is taking a break. Ideas are saved after the pattern check; scans queue and run when it is back on | Banner on the home page; new scans show "waiting" and run when it is back on |
| `agent.<name>` | One agent misbehaves | Admin | Nothing new; that step goes to the review desk as "manual" | Review items show the step as manual |
| `attachments.upload` | Scanner down, or a suspicious file wave | Admin, InfoSec | Banner; upload is hidden; files already uploaded stay | Upload answers 503 |
| `attachments.open` | Any doubt about a stored file | InfoSec | No one can open or download a file | File links answer 503 |
| `submissions` | Abuse wave, data incident, or maintenance | Admin | Read-only mode: browse and track, not share or edit; banner explains | "Share" answers 503; My ideas still loads |
| `matching.show` | Matches look wrong or revealing | Admin | Submitters see "we will show you colleagues a little later"; the desk still sees matches | A new scan shows no crew cards |
| `comms.email` | Bounces, wrong content, or mail service trouble | Admin | Emails queue; in-app messages carry on | `notifications` with `channel = 'email'` stay `queued` |
| `wall.public` | A bad summary on the wall, or an HR request | Admin, HR | The wall and everyone else's view of idea pages are hidden; owners and the desk keep theirs | `/api/wall` answers 503 |
| `ones.public` | A brief or name that should not be public, or an HR request | Admin, HR | The Ones disappear from the wall, the home carousel and the office screens; the console and each One's own dashboard keep working | `/api/ones` answers 503; the screen says the Ones are resting |
| `learning.jobs` | A learning report or proposal looks wrong, or the jobs load the database at a bad time | Admin | Nobody outside the product team notices; the Learning page shows "Off" and "Run it now" is disabled. Proposals already made can still be decided | `POST /api/learning/run` answers 503; no new `learning_reports` rows next morning |
| `ember.send` | An issue of The Ember has a mistake, or it should wait (for example while the Ones are paused) | Admin | Nothing visible; "Send to everyone" on Write The Ember says sending is paused. Past issues stay readable | `POST /api/ember/{id}/send` answers 503; queued `ember.issue` emails stay queued |

**Walkthrough (AT-B8-07).** In UAT, flip each switch off and on again in the order above and tick the "Check it worked" column. The automated version runs in `make test` (`tests/test_b8_switch_walkthrough.py`).

## 2a. The Ones (DEC-040 to DEC-087)

Everything happens in **Ones** (`/ones/console`): propose, approve (the chair, or "Record a meeting majority" with the meeting date), then "Carry out and send" by the admin member. A tier change needs the committee's message before it can be carried out. After a committee meeting, the admin member presses **Announce new Ones**, which emails everyone. Measured impact (time, money, effort, scale) is entered against each One; money shows publicly only with "Finance confirmed" ticked. For The Ones Night, mark the four impact awards in the roster; the legend number goes through its own proposal (one a year).

**Office screens:** open `/constellation` signed in on the screen's account and choose Full screen. It shows the static sky and alternates with impact cards. Switch to ambient mode for events from the console ("Switch to ambient mode"). Pause is on the screen itself.

**Founding Ones** (DEC-053): the product lead sends names and one-line citations. The CEO, or a core committee member on the CEO's behalf, proposes each one as "Founding One", the chair approves, and the admin carries it out. Numbers 1 to 6 then follow in order, as long as nobody has been inducted before.

## 2b. Delivery, lenses and learning (BLD-115 to BLD-124)

**Delivery** (`/delivery`). A core committee member or an admin starts the handover for a picked idea from "Picked, waiting for a handover". The owner fills in the pack and sends it; the named sponsor approves it. Until live sync is built, an admin pastes the delivery pipeline's page ID ("Link the pipeline page") and the delivery PM records each step ("Record the current step"); choosing Shipped opens the 30- and 90-day results. On the fix track the owner keeps the action plan and sends the before-and-after numbers for the sponsor. Results: the owner fills them in, the sponsor confirms; for money, an admin presses "Finance has confirmed the money" only after Finance has confirmed it in writing. Nobody else can do these steps for them; if a sponsor leaves, an admin names a new one in the pack (it must still be waiting for approval) or grants the sponsor role.

**Stuck deliveries.** `delivery.tick` (09:30) reminds owners of results due within 3 days, sponsors of results waiting 5 working days, fix-track owners every Friday, and flags overdue milestones (once), plans 10 working days late (to the chair, once) and builds blocked for 10 working days (to the sponsor, once). To see what it did: `SELECT action, count(*) FROM audit_log WHERE action LIKE 'delivery.%' AND at > now() - interval '1 day' GROUP BY 1`.

**Lenses** (`/lenses`) rebuild on Mondays at 05:00; an admin can press "Rebuild now". Counts only; to name the colleagues behind a count, use Admin's reveal (with a reason; it is logged).

**Learning** (Admin, then "Learning reports and proposals"). Approve or decline each proposed glossary term or area-tag group; approving records the decision only, and the product team then adds the term or tag to the company repo by hand. Acceptance rates are for information: nothing switches to automatic at launch.

## 3. Scheduled jobs to watch

| Job | When (IST) | Healthy when |
|---|---|---|
| `reconcile` | 02:00 | Log `reconcile.clean`; any `reconcile.drift` is read the same morning |
| `drafts.purge` | 03:30 | Drafts older than 30 days gone |
| `comms.nudges`, `comms.digest` | 10:00, 10:30 (digest Mondays) | No `comms.send_failed` bursts |
| `learning.run` | 05:30 (each loop on its own day: daily, Mondays, the 1st, quarter starts) | Log `learning.ran` per loop, or `learning.switched_off` while `learning.jobs` is off; any `alert.drift_*` row is read the same morning |
| `lenses.build` | Mondays 05:00 | Log `lenses.built` with the LOB and role counts |
| `delivery.tick` | 09:30 | Log `delivery.tick` with its counts |
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
2. When it answers again, switch uploads back on. Files still in quarantine are checked on their job's next retry; a file whose retries ran out was rejected as "check failed", and the person is told to upload it again.

### 4.4 Email bouncing (`comms.email` off)
1. Look at `notifications` with `state = 'failed'` and `error_code = 'smtprecipientsrefused'` in the last hour (IDs only). Only refusals the mail server gives at send time are seen; delivery reports that arrive later in the Graph mailbox are not read on day one.
2. Fix the cause (addresses from HR import, mailbox limits), then switch email back on. Bounces from before you switched it on are not counted again. Queued email goes out within working hours.

### 4.5 Web cannot reach the worker
`GET /api/health?deep=1` on the web app says `worker: refused` (wrong `INTERNAL_API_TOKEN`) or `unreachable` (worker down). Restart the worker; check both services read the same token from the vault.

### 4.6 Reconcile drift
Run `python -m reconcile --report-only`. Index drift fixes itself at 02:00 or with `python -m reconcile`. `idea_visibility_mismatch` means an idea file in the company repo shows the wrong visibility: switch `wall.public` and `matching.show` off until the repo writer has rewritten the file (any review action on the idea rewrites it), then rerun reconcile.

### 4.7 Repo writer behind
`SELECT count(*), min(created_at) FROM outbox WHERE committed_at IS NULL` growing, or rows with `last_error`, means the writer is stuck. The app keeps working; restart the worker. A `last_error` code that repeats needs a fix before restart.

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

## The Ember, each month

1. In the last week of the month, an admin opens **Write The Ember** (`/ember/compose`) and starts the month's issue.
2. The core committee chair writes "What the committee looks for" there (up to 90 words, no names of colleagues or clients).
3. An admin reads the preview and presses **Send to everyone**, then **Yes, send to everyone**. It goes out through the usual email rules (working hours, one routine email a day, then the digest).
4. Sent issues stay in the archive at `/ember`. To stop a send in progress, switch `ember.send` off: queued Ember emails wait.
