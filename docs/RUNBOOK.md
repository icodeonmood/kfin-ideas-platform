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

**Walkthrough (AT-B8-07).** In UAT, flip each switch off and on again in the order above and tick the "Check it worked" column. The automated version runs in `make test` (`tests/test_b8_switch_walkthrough.py`).

## 3. Scheduled jobs to watch

| Job | When (IST) | Healthy when |
|---|---|---|
| `reconcile` | 02:00 | Log `reconcile.clean`; any `reconcile.drift` is read the same morning |
| `drafts.purge` | 03:30 | Drafts older than 30 days gone |
| `comms.nudges`, `comms.digest` | 10:00, 10:30 (digest Mondays) | No `comms.send_failed` bursts |
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
