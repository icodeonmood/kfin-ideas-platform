# UAT deploy runbook

**Read this runbook from the tag lane A sent you** for this install, upgrade or switch to full mode: `git fetch --tags`, then `git show <tag>:docs/UAT.md` (for r4, `git show launch-2026-11-20-r4:docs/UAT.md`). A copy anywhere else can be out of date: `release/2026-11-20` stays on r3 and has no upgrade section, the one in `launch-2026-11-20` lacks the privacy notice version and the Ones Committee step, and the one in `launch-2026-11-20-r2` lacks the fixes made after it (BLD-A248).

For: KFin IT and the product team, installing 1% Club with `make uat-deploy`, on a UAT host or on the launch server. **The launch server is production** (`APP_ENV=prod`): real employees sign in there. Synthetic data only in dev, UAT and tests: they never hold real employee, investor or client data. On a UAT host (`APP_ENV=uat`) the deploy loads 200 synthetic people (all `@kfintech.example`, who cannot sign in), which the smoke checks need. **The launch server uses `APP_ENV=prod`, so the install loads no people at all:** real people come only from HR's file, which IT loads after the first admin's first sign-in (the HR import, step 1b under After the deploy). That is the one difference: otherwise `uat` and `prod` behave the same in the code (BLD-A235).

## What you need first

| Item | Owner | Where it goes |
|---|---|---|
| A Linux host with Docker Engine and Compose v2.24 or later, and a checkout of this repo at the launch tag `launch-2026-11-20-r3`, the commit lane E tags on 20 Nov, not `main`. Check it before step 1: `git describe --tags --exact-match` prints `launch-2026-11-20-r3`, and `git rev-parse HEAD` prints the commit lane A sends IT. `launch-2026-11-20-r2` (543fa250) is the fallback only, if lane E says r3 is not ready: it has no production mode (it loads 200 synthetic people) and its HR import reads no stdin, so it needs the r2 steps lane A gives IT, not 1a to 2b below. `launch-2026-11-20` (29c1ef9c) is the earlier build with notice 0.2-draft: do not install it | IT | — |
| The privacy notice version: `PRIVACY_NOTICE_VERSION=0.2`, exactly the version in `apps/web/src/content/privacy-notice.ts` at the launch tag. If the two differ, nobody gets past the notice at first sign-in; the deploy's preflight stops on a mismatch (BLD-A232, BLD-A233). If a later build changes the notice's version, the env file changes with it; `make uat-upgrade` checks it and stops on a mismatch (BLD-A234) | IT | app env file |
| Entra app registration for UAT: issuer URL, client ID, client secret, redirect `https://<uat host>/auth/callback` (§9.1 O2) | IT | app env file |
| Four random secrets of at least 32 characters each: `INTERNAL_API_TOKEN`, `SESSION_SECRET`, `CONTRIBUTOR_HMAC_SECRET`, `VAULT_ENCRYPTION_KEY` | InfoSec (vault) | app env file |
| Three database passwords of at least 20 random letters and digits (no symbols: they go into connection URLs): `POSTGRES_PASSWORD`, `DB_WEB_PASSWORD`, `DB_WORKER_PASSWORD` | InfoSec (vault) | database env file |
| The worker-only pseudonym vault key: `PSEUDONYM_VAULT_KEY`, at least 32 random letters and digits, different from `VAULT_ENCRYPTION_KEY`. It must never be in the app env file, which the web app also reads | InfoSec (vault) | database env file |
| KFin's file store and scanner: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `CLAMAV_HOST`, `CLAMAV_PORT` (required; the deploy refuses to fall back to the local stand-ins), and the Graph service mailbox (the Graph row below) or `SMTP_URL`. If KFin's scanner is not on 3310, set `WORKER_CLAMAV_PORT` in the app env file (`CLAMAV_PORT` alone is ignored) | IT | app env file |
| Model route decision (D1). With or without it the deploy starts in Mode B: `ai.all` off (BLD-A245). Files wait for the personal-data check, seen only by the person who added them and opened by no one; they are checked as soon as `ai.all` and `agent.gatekeeper` are both on, and files that waited out their tries on earlier builds go back to waiting when the worker starts and are checked then too. At launch, `LLM_MODE=fake` whatever D1 says (see the bold line below this table); the route is set later, in **Switching to full mode (mode A)** | InfoSec | app env file |
| Not at launch: BGE-M3 (AT-B5-01). The deploy builds the worker without it (the compose files pass no `WITH_BGE` build argument and mount no model folder), so set `EMBEDDINGS_MODE=hash`; the preflight warns that matching quality is not representative. Adding BGE-M3 is an install change after launch: the build argument, the model files mounted at `EMBEDDINGS_MODEL_PATH`, then `EMBEDDINGS_MODE=bge-m3` and a re-index | Product team | app env file |
| Voice through Sarvam (DEC-108, on at launch): in the **database** env file (worker only), `SARVAM_API_KEY`; the deploy refuses it in the app env file, which the web app also reads, and the web container's copy is blanked. In the app env file, `SPEECH_MODE=sarvam` and `SPEECH_HOSTED_APPROVAL=DEC-108` (the deploy refuses `sarvam` without both). Outbound HTTPS and WSS from the worker to `api.sarvam.ai` only. The speech container and model below are now an optional fallback, not needed for launch | InfoSec (key in the vault), IT (outbound rule) | database env file, app env file |
| Email through Graph (BLD-A243, DEC-131; needed for full mode, not for the install): an Entra app registration for the worker with Microsoft Graph's `Mail.Send` **application** permission (admin consent), limited to the 1% Club service mailbox by an Exchange application access policy, so it can send as that mailbox and no other. The values go in only at step 1 of **Email through Graph (BLD-A243)**: until then `EMAIL_MODE` stays `smtp`, and neither the Graph settings nor the secret are in either env file. There, in the app env file: `EMAIL_MODE=graph`, `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_SERVICE_MAILBOX` and `EMAIL_FROM` (its address must be the mailbox's; the preflight checks it); in the **database** env file (worker only): `GRAPH_CLIENT_SECRET`; the deploy and the upgrade refuse it in the app env file, which the web app also reads, and the web container's copy is blanked. Outbound HTTPS from the worker to `login.microsoftonline.com` and `graph.microsoft.com` only. Note the secret's expiry date: when it lapses, the worker switches `comms.email` off by itself and email waits until a new one is set. The steps are in **Email through Graph (BLD-A243)** below | IT (app registration, policy, outbound rule), InfoSec (secret in the vault) | app env file, database env file |
| Optional fallback, not needed for launch (DEC-108): voice notes on the isolated speech service (DEC-096, BLD-C012, BLD-C015): its own container (`speech`, compose profile `speech`, built from `services/worker/speech_service/Dockerfile`), started by the deploy when the app env file sets `SPEECH_ENGINE_URL=http://speech:8300`. It runs as uid 10002 with a read-only root filesystem, a 64 MB tmpfs `/tmp`, no capabilities and no published port, on an internal network only the worker shares (no route to Postgres, S3, mail or the internet). On the host: the speech model (faster-whisper, multilingual, CTranslate2 int8) in `SPEECH_MODEL_DIR`, mounted read-only; about 2–3 GB of memory for it (`SPEECH_MEM_LIMIT`, default 3g). In the **database** env file: `SPEECH_SERVICE_TOKEN`, 32 or more random letters and digits, never the same as `INTERNAL_API_TOKEN` (the deploy refuses it in the app env file, which the web app also reads, refuses `INTERNAL_API_TOKEN` in the database env file, and refuses the two if equal). In the app env file: `SPEECH_ENGINE_URL=http://speech:8300` exactly (the deploy and the worker refuse any other host or scheme outside dev and test). The image is pinned by digest and hashes; it needs PyPI and Docker Hub only at build time | IT (host, memory, model folder), InfoSec (token in the vault) | database env file, host folder |
| Voice notes, KFin's S3 (DEC-096, BLD-C006): on the **quarantine** bucket, a lifecycle rule `voice-notes-expire-1-day` that expires the prefix `voice/` after 1 day, and **no versioning** on that bucket (a kept version would outlive a delete). The worker tries to set the rule itself at start; where the store refuses, IT sets it. The smoke check fails if the quarantine bucket is versioned | IT | the file store |

**At launch (Capture first), the app env file must say `LLM_MODE=fake`, even when the model key is already in it.** Step 7 of the deploy switches `ai.all` off whatever the model route (Mode B, audited) and never runs the golden sets on the server's database, in any `APP_ENV` (BLD-A245): with a route configured it only prints that they are not run there. The golden sets on the real route run only through `scripts/eval/live.sh`, on a throwaway database of its own. AI is switched on later, only when the product lead says so after that passes: follow **Switching to full mode (mode A)** below. **Never switch `ai.all` on while `LLM_MODE=fake`: the fake route would answer people with canned text.**

## Env files

Two files, both readable only by the deploy account (`chmod 600`), never committed:

- **App env file** (`.env.uat`): start from `.env.example`, set `APP_ENV=prod` on the launch server (`uat` on a UAT host) and every value above. Leave `DATABASE_URL` out; each service gets its own login. Set `KFIN_EMAIL_DOMAINS=kfintech.com` in the app env file (add any other KFin email domain), whether or not Entra releases the employeeId claim: without it the web app refuses every sign-in by email. On the launch server the preflight then warns that `kfintech.example` is missing; that warning is about UAT's synthetic people and does not apply with `APP_ENV=prod`.
- **Database env file** (`.env.uat.db`): only `POSTGRES_PASSWORD`, `DB_WEB_PASSWORD`, `DB_WORKER_PASSWORD`, `PSEUDONYM_VAULT_KEY` and `SARVAM_API_KEY` (voice through Sarvam, DEC-108; never in the app env file, which the web app also reads), plus `GRAPH_CLIENT_SECRET` once email goes through Graph (BLD-A243; never in the app env file either) and `SPEECH_SERVICE_TOKEN` only with the optional speech service. It builds each service's own settings and is never handed to a container as a whole.

## Deploy

```bash
sudo mkdir -p /srv/kfin-ideas-uat && sudo chown 10001 /srv/kfin-ideas-uat     # the worker runs as uid 10001
UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-deploy APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db
```

The script stops at the first problem and says which. Its eight steps:

| Step | What happens | Stops when |
|---|---|---|
| 1 Preflight | Checks the settings without printing any secret | dev values, short secrets, mock sign-in, missing Entra or model settings, a privacy notice version that differs from the build's, `GRAPH_CLIENT_SECRET` in the app env file, `EMAIL_MODE=graph` without every Graph setting |
| 2 Empty database | Starts Postgres; checks there are no tables and no company repo yet | anything already exists (a fresh deploy only) |
| 3 Migrations | `dbmate up`, then `dbmate status` | anything pending |
| 4 Service logins | Creates `ideas_web` and `ideas_worker` with their own passwords | — |
| 5 Seed | Company repo from `seed/company-repo/` (no dev overlay outside dev), OKF check, rules, index; 200 synthetic people, none with `APP_ENV=prod` (the line reads `people: none loaded in production; …`) | the repo is not valid OKF or a rule file fails |
| 6 Model route | Switches `ai.all` off (Mode B), audited, whatever the route, before anything starts the worker, so nothing is queued while AI is on (BLD-A254). With a route configured it prints `model route configured: golden sets are not run on this database; …`: golden sets never run here (BLD-A245) | the switch cannot be written (nothing was started) |
| 7 Start | Every service up and healthy | a service does not become healthy in 4 minutes |
| 8 Smoke tests | Thirteen checks, listed below | any check fails |

Smoke checks (`python -m bootstrap.smoke --fresh`): the worker and web app answer; the sign-in page loads; the API refuses requests without a session; pages send signed-out people to sign in; the web app's own token reaches the worker and a wrong token is refused; the virus scanner answers (the report names the scanner and file store in use); all kill switches exist; the company repo is valid OKF with no dev-only files; the rules load; the index is at the repo's head; only synthetic people exist and nobody has a role yet (with `APP_ENV=prod`, nobody at all: the line reads `no people or roles yet (production)  0 people, 0 role grants`); voice notes are off, or on through Sarvam with `speech.hosted` on, its approval reference and the Sarvam key (DEC-108), or on the engine on KFin's own server, never the fake speech route, and the quarantine bucket is not versioned (DEC-096).

## After the deploy

1. Grant the first admin (they then use the Admin page for everyone else). On a UAT host, 1c alone. On the launch server (`APP_ENV=prod`) the install loaded nobody, so do 1a, 1b, 1c and 1d in this order, then step 2, then 2b (BLD-A235, BLD-A236). Every command runs in the running worker container, `kfin-ideas-uat-worker-1` (check the name with `docker ps --format '{{.Names}}' | grep worker`).

   **1a. The first admin signs in once** (Entra), on the launch server. If KFin's reverse proxy (step 5) does not reach the web app yet, skip 1a: the import then creates their row, and 1c still finds them.

   **1b. HR import (the launch server only; never on a UAT host, which holds synthetic people only).** HR's file is a CSV with exactly this header: `employee_id,name,email,department,job_title,location,manager_employee_id`. Keep it on the server under `/secure/hr/`, `chmod 600`, owned by the deploy account. Never paste the file, or any line of it, into a message, a ticket or the repo, and delete it when HR's policy says. **The first admin must be in HR's file with the same email they sign in with.** With Entra's employeeId claim, nothing else is needed: their sign-in row already carries their employee ID, 1c finds them, and the import matches them by that ID and takes HR's email. Without the employeeId claim (§9.1 O2), their sign-in row is keyed by email until this import adopts it by that email, so if they are missing from HR's file, 1c says "no active person with that employee ID". Without the employeeId claim, if HR's email for them differs from the one they sign in with, the import makes a second record and 1c gives `admin` to the record they do not sign in as.

   **Before importing, check two things for the first admin, with IT's Entra admin** (compare on screen; never paste either value):
   - **The employee ID:** HR's `employee_id` must be exactly the employeeId Entra releases, with the same prefix and the same leading zeros (`00012345`, `12345` and `KF12345` are three different people to the app; only case and spaces around it are ignored). If they differ, once the import has run no employee can sign in with the claim, because their email is already on HR's row under another ID. Stop and have HR or the Entra admin make them match first.
   - **The email:** HR's `email` must be exactly the address they sign in with (Entra's email claim, or their UPN if Entra sends no email). If it differs, stop and have HR correct the file first: without the employeeId claim the import would make a second record for them, and re-importing a corrected file after that fails until the stray record is removed by hand: on r3 with `failed: UniqueViolation`, and from the first upgrade on the import refuses with the line number instead, changing nothing (with the claim, the import simply takes HR's email).

   The file goes in through stdin, because the worker (uid 10001) cannot read a file that only the deploy account can read:

   ```bash
   docker exec -i kfin-ideas-uat-worker-1 python -m identity.hr_import - < /secure/hr/<file>.csv
   ```

   Pass: one line of counts, never a name or an email: `hr import: <N> rows, <N> created, <n> updated, 0 deactivated, <n> unmapped departments, <n> unmapped titles, <n> proposals opened`. `updated` counts the people who signed in before the import, the first admin at least. Unmapped departments and titles go to the review desk as proposals. A line `failed: line <n>: …` names the line to fix in HR's file; nothing was changed. If it prints `refused: this file would deactivate …`, the file lists fewer than half of the people from HR's last import: stop and ask HR for a full export. Add `--force` only when HR confirms in writing that the file is right.

   **1c. Grant the first admin:**
   `docker exec kfin-ideas-uat-worker-1 python -m identity.grants grant --employee-id <ID> --role admin --reason "First admin at launch, <ticket>" --actor ops:<staff code>`
   The person must have signed in once, or be in the HR import.

   **1d. The first admin signs in again** (the launch server only), in a new private browser window, and opens the Admin page. If the sign-in is refused, or the Admin page is, stop before step 2 and tell the product team. Check first that 1c printed `granted` (or `already granted`); otherwise the usual cause is that the employee ID or the email checked in 1b does not match.
2. Ones Committee members (the product lead's decisions, DEC-121; BLD-B270): give each member **Ones Committee** on the Admin page. It is the 1% Club role and stays. Builds from `main` 7b648174 on, the first update after r3 included, carry lane B's committee role check (BLD-B270), and the conversation's file rule follows it (`FILE_ROLES`): a member with only Ones Committee can use the Ones Committee page, open ideas, play an idea read aloud (Listen), read the review desk's pages, and open and attach the files on an idea's conversation. r3, the launch install, has the role check but not the file rule, so at launch IT also gave each member `core_committee` with the command in 1c (`--role core_committee --reason "Ones Committee at launch, <ticket>"`). `core_committee` also shows some older pages (Delivery, The Ember note) and, while no chair is named, its holders receive the overdue emails of the older timers that escalate to the chair (the 1% Club's own review clock sends none). On any install, give both until the product lead says otherwise. The Admin page cannot give `core_committee` (it lists it as a retired role), and the command cannot give Ones Committee. **Do not remove `core_committee`** from a member, even though the Admin page calls it retired, until lane A tells IT. That happens only when all three hold (BLD-B270): the first update with this role fix is installed on the launch server (Updating the live server, below), the product lead says so, and DEC-121's open question is settled with lane E. Then remove it on the Admin page (the row reads "Core committee member (retired role)"), except from anyone the product lead names as core committee. On the launch server the members already exist from the HR import, so they need not sign in first.

   **2b. On the launch server, the smoke checks without `--fresh`**, once the HR import and these grants are in:

   ```bash
   docker exec kfin-ideas-uat-worker-1 python -m bootstrap.smoke --web-url http://web:3000
   ```

   Pass: `people loaded (production)` with `<N> people, <n> role grants`, and `smoke: all checks passed`.
3. Voice is on at launch (`capture.voice` and `speech.hosted`, DEC-108, migration `20261122300530`). Check the smoke line "capture.voice on; speech.hosted on; SPEECH_MODE sarvam; Sarvam key set" (no call is made to Sarvam) and the go/no-go voice rows say "met". If the watch has switched them off with "Sarvam key missing (automatic)", put `SARVAM_API_KEY` in the database env file, restart the worker and switch both on from the Admin page with a reason. Then record one synthetic voice note on a draft and check that the words appear as you speak, the English copy is labelled "Typed up in English", and nothing is written to the quarantine bucket. Before the gates, the product lead runs `make sarvam-live` from a checkout with the local stack up, with `SARVAM_API_KEY` loaded in their own terminal (never in an env file of this repo), and every line reads PASS (BLD-C177).
4. Full mode (the assistant on, similar ideas, email) is never part of the deploy. When the model route is approved and the product lead says so, follow **Switching to full mode (mode A)** below.
5. Point KFin's reverse proxy (TLS) at the web app's port (`UAT_WEB_PORT`, default 3100). Only the web app is published.

## Updating the live server (upgrade and rollback)

Every fix after the install reaches the server this way, never by hand (BLD-A234). Before each upgrade, lane A rehearses it on a developer machine, from the version on the server to the new tag, in production mode as the launch server runs (see **Rehearse first** below). Lane A then sends IT the new tag, its commit and the line `rehearsal: upgrade, rollback and upgrade again all passed`. No upgrade runs on the server without that (the product lead's rule, 20 Nov 2026).

Run it in a quiet window, and tell the review desk first: a rollback loses anything written after the backup. Use the same checkout, data folder and env files as the install. The commands below use the paths from Deploy and the worker container `kfin-ideas-uat-worker-1`. Never run two upgrades or rollbacks at once: a lock (`ops/.lock`) stops the second. Run each one inside `tmux` or `screen`, so a dropped SSH session does not stop it halfway.

**Once, before the first upgrade,** if the deploy account is not root: `sudo install -d -m 700 -o <deploy account> /srv/kfin-ideas-uat/ops /srv/kfin-ideas-uat/backups`. The upgrade writes its records and backups there. The worker runs as uid 10001 and cannot read them. Without this step the upgrade stops at step 1 and prints the same command.

**What to paste back:** after each step below, paste to lane A the lines its **Paste back** names, and any `STOPPED:` line. Lane A checks them against the step's pass line before you go on. Never paste an env file, a secret, HR's file or any line of it. Nothing below prints one: the commands print commits, tags, counts, file paths, switch names and the env lines named in step 3, which hold no secret.

1. Before you start, record what runs now, from the checkout:

   ```bash
   cat /srv/kfin-ideas-uat/ops/installed.json 2>/dev/null
   git describe --tags --exact-match
   git rev-parse HEAD
   docker exec kfin-ideas-uat-worker-1 python -m core.killswitch list
   ```

   Paste back: all of it (the record holds only a commit, a tag and a time). Pass: the tag and commit installed (the first time, no record yet, then `launch-2026-11-20-r3` and `ecd9266411c02de0d14ce9c18ed0412218d13398`), and every switch as the product lead set it. When the record is there, it is what runs: after a rollback the checkout can still be on the newer tag (step 6 says how to put it back). Keep the switch list for step 5.

2. Check out the new tag:

   ```bash
   git fetch --tags && git checkout <new tag>
   git describe --tags --exact-match
   git rev-parse HEAD
   git status --short | wc -l
   ```

   Paste back: the last three lines. Pass: the new tag, the commit lane A sent with it, and `0`.

3. Check the env files still match the new build:

   ```bash
   grep -E '^(APP_ENV|PRIVACY_NOTICE_VERSION|LLM_MODE)=' /secure/.env.uat
   grep -o 'version: "[^"]*"' apps/web/src/content/privacy-notice.ts
   ```

   Paste back: the four lines. Pass: `APP_ENV=prod` on the launch server; the two notice versions are the same; `LLM_MODE=fake` unless the product lead has switched AI on. If the versions differ, set `PRIVACY_NOTICE_VERSION` in the app env file to the build's version: the upgrade stops on a mismatch. Lane A says in advance when a new tag changes the notice.

4. Upgrade:

   ```bash
   UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-upgrade APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db FROM=launch-2026-11-20-r3
   ```

   **`FROM=launch-2026-11-20-r3` is needed the first time only:** the r3 install wrote no record of what it installed. Every upgrade writes `/srv/kfin-ideas-uat/ops/installed.json` (an install from a later tag does too, when the deploy account can write `ops/`, as after the **Once** step above; otherwise it prints "Could not write" and the next upgrade needs `FROM` again). Once the record is there, leave `FROM` out. If you give it, it must match the record.

   Paste back: the whole output, each `==` step line and what follows it. Pass:
   - at the top, `FROM ecd9266411c02de0d14ce9c18ed0412218d13398 launch-2026-11-20-r3` (the first time) and `TO   <the commit from step 2> <new tag>`;
   - `ai.all off; model route not configured (LLM_MODE=fake: Mode B)` (unless the product lead has switched AI on);
   - `backup: … (N tables with data)`;
   - `Pending: 0` and `migrations applied now: N`;
   - at the end of step 6/8, `file checks: N files back to waiting for the personal-data check (none opened)`. N can be 0: it is the number of files people added since the install that read "Didn't upload" because AI was off. They are waiting for the check again, and none was opened. If the line says instead that the worker's start sweep stopped part-way, or that the worker did not report it within 120 s, the upgrade has still finished: send the whole output to lane A. A rollback puts those files back to "Didn't upload" (they are as at the backup), and the next upgrade brings them back again. An upgrade to a build without the start sweep prints no such line;
   - `people loaded (production)` and `smoke: all checks passed`;
   - the last line `upgrade: <old> -> <new> done in Ns. Backup kept at /srv/kfin-ideas-uat/backups/upgrade-<time>-<old>.dump`.

| Step | What happens | Stops when |
|---|---|---|
| 1 Checks | The checkout is clean; prints the old and new sha; Postgres runs and has migrations; the env file checks of deploy step 1, the notice version included; reads `ai.all`; free disk for the backup | anything fails; `ai.all` is on while `LLM_MODE=fake` |
| 2 Keep | Tags the running images `:rollback-<old sha>` and saves the old version's compose files beside the backup | — |
| 3 Build | Builds the new images while the old ones keep serving; runs preflight on the new worker image | the build or preflight fails (nothing changed) |
| 4 Backup | `pg_dump` of the database to `backups/` (mode 600), checked with `pg_restore --list`; an archive of the company repo, copied again (up to 10 tries, 2 s apart, one line per try) if the running worker changes it while it is copied (BLD-A247) | the backup fails or is empty (nothing changed) |
| 5 Migrations | `dbmate up`, then `dbmate status`; prints the migrations applied | anything pending |
| 6 Restart | Web and worker (and speech, if used) on the new images. Postgres is not restarted | a service does not become healthy in 4 minutes |
| 7 Smoke | The thirteen checks, without `--fresh`: real people and their roles are expected now | any check fails |
| 8 Record | `ops/installed.json` and `ops/upgrade-<time>.json` (from, to, backup, migrations, seconds) | — |

Before step 5/8 (Migrations) a failure changes nothing: the old version keeps serving. From step 5/8 on, a failure prints the rollback command and stops. It never rolls back by itself: decide with the product lead, then run it. **A failed upgrade is rolled back, not run again:** once a run has migrated the database, the upgrade refuses to start again and names the backup to roll back with.

5. After the upgrade, check the switches and the Admin page:

   ```bash
   docker exec kfin-ideas-uat-worker-1 python -m core.killswitch list
   ```

   Then the first admin signs in, in a new private browser window, and opens the Admin page.

   Paste back: the switch list, and "Admin page opens" or what they saw instead. Pass: every switch exactly as in step 1 (the upgrade never changes one), and the Admin page opens. If either fails, tell lane A and the product lead before anything else; the way back is the rollback in step 6.

6. Rollback, only when the product lead decides it, from the same new checkout, with the backup the upgrade printed. With `EMAIL_MODE=graph` in the app env file, read **Before a rollback** under **Email through Graph (BLD-A243)** first:

   ```bash
   UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-rollback BACKUP=/srv/kfin-ideas-uat/backups/upgrade-<time>-<old>.dump APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db
   ```

   It stops web and worker, puts the kept images back, drops and recreates the database and restores the backup, always restores the company repo from its archive, starts web and worker with the old version's compose files, runs the smoke checks and records the old version as installed. If you changed `PRIVACY_NOTICE_VERSION` for the upgrade, set it back first: the rollback stops and names the old version. It prints the kill switches before and after: they go back to their state at backup time, so check them on the Admin page.

   Paste back: the whole output. Pass: `database restored: migrations as at the backup (N)`, `smoke: all checks passed`, and the last line `rollback: back on <old> in Ns. Anything written after the backup is lost.` Then put the checkout back on the old tag, so it matches what runs, and run step 5's checks again; the switches should match step 1:

   ```bash
   git checkout <old tag> && git describe --tags --exact-match
   ```

   Pass: the tag from step 1. If step 1 showed a commit with no tag, check out that commit instead and check `git rev-parse HEAD` prints it.

**The first upgrade to a build with the hourly file clean-up (BLD-C242).** Builds before it never delete old file copies. From this build on, the worker runs `files.sweep` once when it starts and then every hour, at :30 past the hour (IST). Each run deletes the stored copy of every file that has read "Didn't upload" for more than 24 hours; Try again then asks the person for the file again. It also removes every file added to a conversation and never sent, a day after its last change (for a checked file, a day after its check ended). A file still being checked is never removed. It deletes nothing unless the most recent worker start sweep finished (its audit row says `complete` true). Until then each hourly run only logs that it waits. The three reads below only count. The 24 hours in the second read is `attachments.rejected_retention_hours` in the company repo's `rules/thresholds.md`: if the programme team has changed it, use their value there.

```bash
docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT after->>'complete' FROM audit_log WHERE entity = 'files:start_sweep' AND action = 'file.start_sweep' ORDER BY at DESC, id DESC LIMIT 1"
docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT count(*) FROM attachments WHERE kind = 'file' AND file_state = 'upload_failed' AND store_key IS NOT NULL AND (checks->>'ended_at')::timestamptz < now() - interval '24 hours' AND coalesce(checks->>'copy', '') <> 'gone'"
docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT count(*) FROM attachments WHERE purpose = 'conversation' AND conversation_entry_id IS NULL AND answer_id IS NULL AND file_state IS NOT NULL AND file_state <> 'checking' AND updated_at < now() - interval '24 hours'"
```

Run them about 5 minutes after step 5. Paste back: the three results. Pass: the first read prints `true`, and both counts are 0 or a handful (a file can pass its 24 hours in between). If a count is higher, read again after the next :30 past the hour and paste back again. If the first read is not `true`, the clean-up is waiting for a finished start sweep: send the reads to lane A. If a count is still more than a handful on the second read, send both sets of reads to lane A. After a rollback the database goes back to the backup, but the file store does not. A file whose copy the clean-up deleted still reads "Didn't upload", and Try again asks for the file again. A conversation file the clean-up removed comes back in its box without its copy: it does not open, and Remove clears it.

**What a rollback loses:** everything written after the backup. That covers ideas, drafts, messages, decisions, notice acceptances and any kill switch changed on the Admin page. That is why upgrades run in a quiet window.

**Kill switches:** the upgrade never changes a kill switch, and neither does the rollback. The upgrade only reads `ai.all`, and stops if it is on while there is no model route (`LLM_MODE=fake`). A rollback puts the switches back as they were at the backup, because they live in the database.

**The backup holds personal data:** the whole database, the sharers' own words and the encrypted vault included. It stays on this server under the database's controls (file mode 600, folder 700, owned by the deploy account). It is never copied off the server. Keep at least the latest backup; remove older ones only when the product lead says so.

**Rehearse first:** before each upgrade of the server, lane A runs `make uat-rehearsal-upgrade FROM=<the installed tag> REHEARSE_APP_ENV=prod` on a developer machine, at the new tag. It installs FROM with FROM's own deploy in production mode (no people), then does what IT did after the install, on synthetic people only (`@kfintech.example`): a synthetic HR file of 20 through stdin, `admin` for one of them, `core_committee` for another, and the smoke checks without `--fresh`. With a checkout that has the start sweep, it then adds three synthetic files on FROM through FROM's own code (one that reads "Didn't upload" after its waits, one still waiting on its last try, and the antivirus test file), and checks them by ID after each later phase (`files-upgrade`, `files-rollback`, `files-again`); without the sweep the summary says `files-from SKIPPED`. From `launch-2026-11-20-r4` on, FROM has lane C's file waits: a file waiting for the personal-data check no longer uses up its tries. So on such a FROM the first file waits for the check instead of reading "Didn't upload", the antivirus test file waits too (nothing is scanned while AI is off), and the upgrade moves 0 files back (`file checks: 0 files back to waiting for the personal-data check (none opened)`). The rehearsal picks what to expect from FROM's code and says which in one line before the install: `file phases: shape waits` (r4 and later) or `file phases: shape r3`. Then it upgrades to the checkout, rolls back, upgrades again, prints a summary (`== Summary (upgrade rehearsal, APP_ENV=prod)`, one PASS line per phase) and tears it all down (`KEEP=1` keeps it). Its last line is `rehearsal: upgrade, rollback and upgrade again all passed` only when every phase has its PASS line; otherwise `rehearsal: FAILED (exit N)`, or `rehearsal: STOPPED (TERM) after <phase>` when it was stopped, which also stops the runs it started. Ones Committee, which only the Admin page gives, is not rehearsed: nobody can sign in there. Without `REHEARSE_APP_ENV=prod` it rehearses a UAT host (`APP_ENV=uat`, with synthetic people loaded at install). It refuses while the dev stack runs and never starts or stops it: run `make down` from the main checkout first and `make up` there after.

## Restore drill (BLD-A241)

The Full go/no-go needs "Restore drill completed inside 4 hours" (ARCHITECTURE §9.3, mode A; check: IT). The drill proves that a backup of the live database restores whole on this server. It takes a fresh backup of the database `ideas`, restores it into a scratch database `ideas_restore_drill` on the same Postgres, compares the two table by table, then drops the scratch database and deletes its own backup. It reads the live database and changes nothing in it: no service stops, no kill switch changes, and people can keep using the 1% Club while it runs. IT's own point-in-time restore from the WAL archive stays as `docs/RUNBOOK.md` §5 describes; this drill does not replace it.

**When:** once before the Full go/no-go (Wed 25 Nov 2026, 16:00), in a quiet window; tell the review desk first. Lane A rehearses it on the rehearsal stack before IT runs it, and sends IT the tag to run it from. It never runs at the same time as an upgrade or a rollback: all three take the lock `ops/.lock`, and the second one stops at its step 1 (an upgrade then says "another upgrade or rollback holds": wait for the drill to end). Run it inside `tmux` or `screen`.

**Run on real Docker first (24 Nov 2026):** lane A ran it on a GitHub runner with Postgres 16.12 (CI run 45371104620), on a rehearsal stack upgraded from r5: 116 tables, counts equal, 2 s on that small synthetic database, then a refusal with the scratch database already there (it stopped and dropped nothing) and a second pass. On the server it takes longer: the backup and the restore grow with the database.

**Command,** from the release checkout, with the install's data folder and env files (as for an upgrade):

```bash
UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-restore-drill APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db
```

**How long:** a few minutes at today's size (one backup and one restore of the database); the target is under 4 hours. It needs free disk for one backup under `backups/`, and room for the copy where Postgres keeps its data; step 1 checks both.

| Step | What happens | Stops when |
|---|---|---|
| 1 Checks | The env files; takes the lock; Postgres runs and `ideas` has its migrations; the scratch database is `ideas_restore_drill` (never `ideas`) and does not exist yet; free disk for the backup and the copy. A backup an earlier drill left in `backups/` is named, with the command that deletes it | anything fails. If `ideas_restore_drill` exists, an earlier drill stopped half-way: it prints the one command that drops it and drops nothing |
| 2 Backup | One read-only snapshot of `ideas`: every table is counted in it, and `pg_dump` takes the backup from the same snapshot, to `backups/restore-drill-<time>.dump` (mode 600), checked with `pg_restore --list` | the backup fails or is empty |
| 3 Restore | Creates `ideas_restore_drill` (the services' logins cannot connect to it) and restores the backup into it, as a rollback restores `ideas` | the restore fails. It prints only the names of the entries it stopped at, never its messages: they can quote a row |
| 4 Compare | Every table in schema `public`, from the catalog: the same tables in both, every row count equal, `schema_migrations` at the same version | any difference (it prints the table and both counts) |
| 5 Clean up | Drops `ideas_restore_drill` and deletes the drill's own backup. No other backup is touched | — |
| 6 Record | `ops/restore-drill-<time>.json` (`passed`, `seconds`, `where`, `at`), the record the go/no-go report reads | over 4 hours |

Whatever stops the drill after step 1, Ctrl-C included, it still drops `ideas_restore_drill`, deletes its backup and writes a record with `"passed": false`. Its last line is then `restore drill: FAILED (<step>)`.

**What to paste back:** the six `==` lines, the `compare:` line, the `recorded:` line and the last line. Never paste an env file, a secret or HR's file, or any line of them. The drill prints table names, counts, paths and times only, never a row. The backup holds personal data: it never leaves this server, and the drill deletes it at the end.

**Pass:**
- `compare: N tables, the same in both; every count equal; schema_migrations at <version> in both`;
- `recorded: /srv/kfin-ideas-uat/ops/restore-drill-<time>.json {"passed": true, "seconds": N, "where": "launch server", "at": "<time>"}`;
- the last line `restore drill: passed in Ns (N tables, counts equal)`.

If it stops with `ideas_restore_drill already exists`, check with lane A that no drill is running, run the command it printed, then run the drill again. If it stops for any other reason, send the output to lane A before running it again.

## Switching to full mode (mode A)

Full mode turns on the assistant and similar ideas, and gets email through Graph ready; whether email goes on is the product lead's call at the go/no-go (DEC-131: go/no-go Wed 25 Nov 2026 at 16:00, switch Thu 26 Nov 2026 at 10:00). It is a hand step on the running server, never part of a deploy or an upgrade: neither of them runs the golden sets on the server's database, in any `APP_ENV` (BLD-A245). The golden sets on the real route run only in `scripts/eval/live.sh`, in a throwaway compose project with its own database. live.sh only reads the install's database, to count its model calls in `llm_calls` before and after.

Do the steps in order. After each one, paste to lane A the lines its **Paste back** names, as for an upgrade, and go on only when they match its pass line. Never paste an env file, a key or any line of HR's file. Nothing below prints a secret: the commands print tags, commits, counts, switch names and setting names.

Run every command from the release checkout, the one the server was deployed or last upgraded from.

1. **Check the build.** The build on the server must carry lane C's file wait (A2, BLD-C225 to BLD-C227), `scripts/eval/live.sh` (BLD-C229), lane C's re-check of the words typed while the assistant was off (BLD-C231, with BLD-C234), lane B's re-check of the review desk's own texts (BLD-B278) and this change (BLD-A245). Lane A sends IT the tag that has all five. If the server runs an older one, install the new tag first with **Updating the live server** above. `EMAIL_MODE` stays `smtp` through that upgrade and every step before 9: the Graph settings and `GRAPH_CLIENT_SECRET` go in only at step 1 of the **Email through Graph** section (step 9 below), once `comms.email` is off, so no restart here sends through Graph before the test message.

   ```bash
   git describe --tags --exact-match
   git rev-parse HEAD
   cat /srv/kfin-ideas-uat/ops/installed.json
   ls scripts/eval/live.sh
   ```

   Paste back: all of it. Pass: the tag and commit lane A sent for full mode, the same commit in `installed.json`, and `scripts/eval/live.sh`.

2. **Put the route's credentials in the app env file.** InfoSec or IT adds `ANTHROPIC_API_KEY` for the Anthropic route, or `AWS_REGION` and the AWS credentials for Bedrock (D1 says which route). On Bedrock, an instance role needs no key lines: `AWS_REGION` alone is enough. `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` go together or not at all. If the server reaches the internet through a proxy, its `HTTPS_PROXY` (and `NO_PROXY`) lines go in the same file. If InfoSec or lane A names model IDs, `LLM_FAST_MODEL` and `LLM_REASONING_MODEL` go in now too: step 3 measures the models this file names. `LLM_MODE` stays `fake` for now. The running worker reads its settings only when it starts, so it does not use the key yet. The web app never gets the key (BLD-A246). Check without printing a secret:

   ```bash
   sed -nE '/^LLM_(MODE|FAST_MODEL|REASONING_MODEL|REFUSAL_FALLBACK)=/p; s/^(ANTHROPIC_API_KEY|AWS_[A-Z_]+|(HTTPS|HTTP|NO|ALL)_PROXY|(https|http|no|all)_proxy)=.+$/\1 set/p' /secure/.env.uat
   ```

   It prints the model settings as they are (they are not secret) and, for a key or a proxy, only its name and `set`. Paste back: the lines it prints. Pass: `LLM_MODE=fake`, and either `ANTHROPIC_API_KEY set` (Anthropic) or `AWS_REGION set`, plus a `set` line for each AWS credential InfoSec issued (Bedrock; none for an instance role).

3. **Run the golden sets on the real route, on a throwaway database.** Run it with `sudo`, as below. `<release checkout>` is this folder (`pwd` prints it). For Bedrock, use `--route bedrock`.

   ```bash
   sudo scripts/eval/live.sh --server --checkout <release checkout> --project kfin-ideas-uat --app-env /secure/.env.uat --route anthropic
   ```

   It starts its own Postgres in a separate compose project (`kfin-ideas-eval`), with throwaway secrets, and runs the golden sets in throwaway containers from the installed worker image. From the app env file it takes only the route's credentials and proxy lines, for the golden sets' container alone, and the model settings, for that container and the one that prints the paste block. Its data folder is `/srv/kfin-ideas-eval` (it must not exist yet) and it goes at the end, with the project and its volume. It changes nothing on the install: no switch, no data, no container. It only reads the install's model calls, by `docker exec` into the install's own Postgres, before and after. Calls the install refused while `ai.all` is off are left out of that count, so people can keep using 1% Club during the run.

   While it runs, the key is in the golden sets' container's environment, so anyone in the server's `docker` group can read it with `docker inspect` until the run ends. The install's own worker holds the same key from step 5 on, the same way. The `docker` group is as good as root: keep it to IT's trusted admins, and run this from an account trusted with the key.

   Paste back: the block from `=== PASTE FROM HERE ===` to `=== PASTE TO HERE ===` (names and numbers only). Pass: `install database: llm_calls unchanged (N)`, and the line before the end `EVAL-LIVE: PASS`. The `model calls:` line is for information. On `EVAL-LIVE: FAIL (gates)` (the gates are named in the brackets), a `STOP: <error> at <step>` line or an `eval-live refused: …` line, stop here and send that block or line to lane A. Nothing has changed on the server, and `ai.all` stays off. Never paste the details file it names (`details, for your eyes only and never to paste: …`, mode 600): it is for IT's eyes only, and IT deletes it when done. If it is refused because `another eval-live run holds /srv/kfin-ideas-eval.lock` and none is running (a run that was cut off), remove that folder, and `/srv/kfin-ideas-eval` if it is still there, then run it again.

4. **The product lead says go.** The product lead reads the paste and says go, or names an agent to keep off. Agents propose; people decide (non-negotiable 5). For each agent the lead names, an admin switches that agent's switch off on the Admin page (for example `agent.judge`), with a reason, before step 6.

   Paste back: the product lead's go, and the switches switched off, if any.

5. **Set the route and restart the worker and the web app.** IT sets `LLM_MODE=anthropic` (or `LLM_MODE=bedrock`) in `/secure/.env.uat`, then restarts both in the install's compose project, with the same compose wrapper as the BGE-M3 section below. `ai.all` is still off. The web app reads neither `LLM_MODE` nor a model key (BLD-A246 blanks the key for it); its restart keeps its container in step with the env file. `EMAIL_MODE` stays `smtp` at this restart: email through Graph is set only at step 1 of the **Email through Graph** section (step 9).

   ```bash
   grep -E '^LLM_MODE=' /secure/.env.uat
   export UAT_APP_ENV_FILE=/secure/.env.uat UAT_DATA_DIR=/srv/kfin-ideas-uat
   compose() { docker compose -p kfin-ideas-uat -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
     --env-file /secure/.env.uat --env-file /secure/.env.uat.db "$@"; }
   compose up -d --wait worker web
   ```

   Paste back: the `LLM_MODE` line and the `Healthy` lines. Pass: `LLM_MODE=anthropic` (or `bedrock`), and `Healthy` for `kfin-ideas-uat-worker-1` and for `kfin-ideas-uat-web-1`.

6. **Switch `ai.all` on.** An admin switches `ai.all` on from the Admin page, with a reason (for example "Full mode, the product lead's go of 26 Nov"). The change is audited.

   ```bash
   docker exec kfin-ideas-uat-worker-1 python -m core.killswitch list
   ```

   Paste back: the switch list. Pass: `ai.all on`, and every other switch as before, apart from any agent switched off in step 4.

7. **Check the files and the words waiting for the personal-data check.** All of them go back into the queue on their own now that the assistant is on: the files on A2's ticker (about a minute); the words people typed while it was off, at up to 5 a minute (BLD-C231); and the review desk's own texts written then (questions sent, decision reasons, the Ones Committee's notes, merge and worth notes), at about 5 a minute alongside (BLD-B278). Every command here only reads, and prints counts and error codes only: no file name, no ID and no text.

   Files:

   ```bash
   docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT file_state, count(*) FROM attachments GROUP BY 1 ORDER BY 1"
   docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT state, last_error, count(*) FROM jobs WHERE type = 'file.check' GROUP BY 1, 2 ORDER BY 1, 2"
   ```

   Run both straight after step 6, then every 2 minutes. Paste back: the counts each time. Pass: within 10 minutes of step 6, no `file.check` row with `waiting_gatekeeper` is left (its count falls to 0). If one is still there after 10 minutes, send the counts to lane A.

   Words:

   ```bash
   docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT count(*) FROM idea_words_sealed WHERE gatekeeper_done_at IS NULL"
   docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT count(*) FROM (SELECT 1 FROM questions q JOIN question_sets s ON s.id = q.set_id WHERE q.gatekeeper_done_at IS NULL AND s.state <> 'queued' UNION ALL SELECT 1 FROM idea_decisions WHERE gatekeeper_done_at IS NULL UNION ALL SELECT 1 FROM decision_reversals WHERE gatekeeper_done_at IS NULL UNION ALL SELECT 1 FROM merges WHERE gatekeeper_done_at IS NULL AND via = 'review_desk' AND note_encrypted IS NOT NULL UNION ALL SELECT 1 FROM idea_worth WHERE gatekeeper_done_at IS NULL AND by_side = 'reviewer' AND note_encrypted IS NOT NULL) desk"
   docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT type, state, last_error, run_at <= now() AS due, count(*) FROM jobs WHERE type IN ('hide.recheck', 'desk.text_recheck') GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4"
   docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "WITH s AS (SELECT max(at) AS since FROM audit_log WHERE action = 'kill_switch.set' AND entity IN ('kill_switch:ai.all', 'kill_switch:agent.gatekeeper') AND after->>'state' = 'on') SELECT s.since, a.after->>'source' AS source, a.after->>'code' AS code, count(a.id) FROM s LEFT JOIN audit_log a ON a.action = 'hide.recheck_gave_up' AND a.at >= s.since GROUP BY 1, 2, 3 ORDER BY 2, 3"
   ```

   Run all four straight after step 6, then every 10 minutes until the first two counts are both 0. Paste back: the counts each time. The first count is the number of people's texts still to check, the second the review desk's. Each goes at about 300 an hour, side by side, so the larger count N takes about N/300 hours (600 take about two hours). Pass:
   - each of the first two counts falls between reads and reaches 0. Either can rise a little and fall again: a text people wrote in the last 10 minutes waits until it settles, and a new text is checked as it is written unless the model route fails on it;
   - in the jobs read, `hide.recheck` rows that are `running`, plus `queued` ones with `due` `t`, stay at 5 or fewer; `desk.text_recheck` has at most one row `queued` or `running`; and `done` grows for both. A `queued` row with a `last_error` and `due` `f` is a re-check waiting to try again after the model route failed: that is fine while the counts still fall. A `queued` row with `last_error` `waiting_gatekeeper` that shows on two reads in a row means a switch is off: go back to step 6. `dead` rows from before this build are history;
   - the fourth read prints one row: `since` is the time of step 6 (the switch-on; if it is empty, stop and tell lane A), the source and the code are empty and the count is `0`. Any other row means a re-check gave up since the switch-on: `desk` in the source is a review desk text, any other source is people's words. Paste its source, code and count, whatever the code says, for the product lead. Those texts are hidden by the patterns and names only, never by the gatekeeper.

   If either of the first two counts is the same on two reads 10 minutes apart, with `ai.all` and `agent.gatekeeper` both on, send all four reads to lane A.

   Step 8 waits until the first two counts are both 0, so similar ideas come on only after every text written while the assistant was off has had the gatekeeper's check. Until then, a similar-idea card could show a name or an address the gatekeeper would have hidden. Each re-check updates the similar-ideas index within seconds, so step 8 needs nothing more. Step 9 does not wait.

8. **Turn on similar ideas**, once step 7's first two counts are both 0. Follow **Moving a server from hash to BGE-M3 vectors (BLD-C211)** below first, with its own checks. Then, on the product lead's word, an admin switches `matching.show` on from the Admin page, with a reason.

   Paste back: that section's checks, then `docker exec kfin-ideas-uat-worker-1 python -m core.killswitch list`. Pass: as that section says, then `matching.show on`.

9. **Get email ready.** Follow **Email through Graph (BLD-A243)**, its own section of this runbook, with its own paste-backs and pass lines. Its steps 1 to 3 get email ready and leave `comms.email` off; its step 4 switches it on only if the product lead says so.

10. **Run the smoke checks**, without `--fresh`:

    ```bash
    docker exec kfin-ideas-uat-worker-1 python -m bootstrap.smoke --web-url http://web:3000
    ```

    Paste back: the whole output. Pass: `smoke: all checks passed`.

**The evidence window after the switch (BLD-A257; for information, not a gate).** Three read-only reads of the first hours of real use since the switch-on at step 6. They print counts and seconds only, with the agent and outcome labels in the second: no text, no ID and no name. Each starts its window at the latest time `ai.all` was switched on, read from `audit_log` as step 7's fourth read does, and prints that time as `since`. The first read is Send to sorted: the ideas sent since then (`sent`), how many have left the check (`sorted`), how many sent more than 15 minutes ago are still being checked (`checking_over_15_min`), and the seconds from Send to sorted at the 50th and 95th percentile and the longest. The second read is every model call since then, by agent and outcome, with its seconds at the 50th and 95th percentile and the longest. The third read counts team-up requests sent, answered (a request closed with its idea counts as answered) and declined (with or without the lead's reason), and drafts' asks sent and declined (with or without the lead's reason).

```bash
docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "WITH s AS (SELECT max(at) AS since FROM audit_log WHERE action = 'kill_switch.set' AND entity = 'kill_switch:ai.all' AND after->>'state' = 'on'), t AS (SELECT h.at AS sent, (SELECT min(o.at) FROM idea_status_history o WHERE o.idea_uuid = h.idea_uuid AND o.from_status = 'checking' AND o.at >= h.at) AS sorted FROM s JOIN idea_status_history h ON h.at >= s.since WHERE h.from_status = 'draft' AND h.to_status = 'checking' AND h.source = 'live') SELECT (SELECT since FROM s) AS since, count(*) AS sent, count(sorted) AS sorted, count(*) FILTER (WHERE sorted IS NULL AND sent < now() - interval '15 minutes') AS checking_over_15_min, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM sorted - sent))::numeric, 1) AS p50_s, round(percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM sorted - sent))::numeric, 1) AS p95_s, round(max(extract(epoch FROM sorted - sent))::numeric, 1) AS max_s FROM t"
docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "WITH s AS (SELECT max(at) AS since FROM audit_log WHERE action = 'kill_switch.set' AND entity = 'kill_switch:ai.all' AND after->>'state' = 'on') SELECT c.agent, c.outcome, count(*) AS calls, round((percentile_cont(0.5) WITHIN GROUP (ORDER BY c.latency_ms) / 1000.0)::numeric, 1) AS p50_s, round((percentile_cont(0.95) WITHIN GROUP (ORDER BY c.latency_ms) / 1000.0)::numeric, 1) AS p95_s, round(max(c.latency_ms) / 1000.0, 1) AS max_s FROM s JOIN llm_calls c ON c.created_at >= s.since GROUP BY 1, 2 ORDER BY 1, 2"
docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "WITH s AS (SELECT max(at) AS since FROM audit_log WHERE action = 'kill_switch.set' AND entity = 'kill_switch:ai.all' AND after->>'state' = 'on') SELECT (SELECT count(*) FROM teamup_requests r WHERE r.sent_at >= s.since) AS teamup_sent, (SELECT count(*) FROM teamup_requests r WHERE r.answered_at >= s.since) AS teamup_answered, (SELECT count(*) FROM teamup_requests r WHERE r.answered_at >= s.since AND r.state = 'declined') AS teamup_declined, (SELECT count(*) FROM merge_requests m WHERE m.sent_at >= s.since) AS draft_asks, (SELECT count(*) FROM merge_requests m WHERE m.answered_at >= s.since AND m.state = 'declined') AS draft_asks_declined FROM s"
```

Run all three about 60 minutes after step 6, and again at 17:00 IST the same day. Paste back: the three results, each time. They decide nothing: there is no pass or fail. Lane A sets the numbers beside ARCHITECTURE §9.3 mode A's "scan time at the 95th percentile under 15 s" for the product lead. If `checking_over_15_min` is above 0, or `since` is empty, send to lane A at once, with the three results. One honest limit: the server keeps no end-to-end time for a team-up send, a decline with a reason or a draft's ask. Each of them makes one gatekeeper call outside the lock (BLD-F100), so the `gatekeeper` rows of the second read are the time they wait for the model (those rows hold the gatekeeper's other calls too), and the third read counts them.

**Back to Capture first** (at any time): an admin switches `ai.all` off on the Admin page, with a reason. That is instant: the assistant stops for everyone. Then IT sets `LLM_MODE=fake` in the app env file and restarts the worker and the web app (`compose up -d --wait worker web`, with the wrapper from step 5). Always in this order, so `ai.all` is never on while `LLM_MODE=fake`. An upgrade stops if it finds `ai.all` on while `LLM_MODE=fake`.

## Email through Graph (BLD-A243)

Step 9 of **Switching to full mode (mode A)** comes here. Notifications go out through the KFin service mailbox with Microsoft Graph (DEC-131), not an SMTP relay: the worker signs in as its app registration (client credentials) and sends each email from the mailbox, which keeps a copy in its Sent Items for IT's retention policy. The web app never gets the secret. You need the Graph row under **What you need first**.

**Steps 1 to 3 get email ready and prove the mailbox with `comms.email` off; they pass on their own. Step 4 runs only when the product lead says so** (the Full go/no-go, Wed 25 Nov 2026 at 16:00, decides it). Until then email stays off and queued, and in-app messages carry on. An install leaves `comms.email` on, so step 1 checks it first.

Never paste an env file, the secret, the tenant ID or a mailbox address to lane A. Nothing below prints one: the commands print setting names, counts, codes and IDs.

1. **Switch `comms.email` off, then set the values.** An install leaves `comms.email` on unless someone has switched it off since. Read it first:

   ```bash
   docker exec kfin-ideas-uat-worker-1 python -m core.killswitch list
   ```

   If it reads `comms.email on`, an admin switches it off now from the Admin page, with a reason (for example "Email through Graph: off until the test message passes"), and tells the product lead: emails queue meanwhile and in-app messages carry on. Read the list again.

   Only now do the Graph values go in (until this step `EMAIL_MODE` stays `smtp`). In the app env file, these lines (with IT's values after the `=`; `EMAIL_FROM` is the display name and the mailbox's own address, for example `1% Club <the mailbox's address>`):

   ```
   EMAIL_MODE=graph
   GRAPH_TENANT_ID=
   GRAPH_CLIENT_ID=
   GRAPH_SERVICE_MAILBOX=
   EMAIL_FROM=
   ```

   In the **database** env file, one line: `GRAPH_CLIENT_SECRET=`, with the secret from the vault. Never put it in the app env file: the web app reads that file, and the upgrade stops if it finds it there. Check without printing a value:

   ```bash
   sed -nE '/^EMAIL_MODE=/p; s/^(GRAPH_[A-Z_]+|EMAIL_FROM)=.+$/app env file: \1 set/p' /secure/.env.uat
   sed -nE 's/^(GRAPH_[A-Z_]+|EMAIL_FROM)=.+$/database env file: \1 set/p' /secure/.env.uat.db
   ```

   Paste back: the `comms.email` line from each switch list read, and the lines the two `sed` commands print. Pass: `comms.email off` on the last read; `EMAIL_MODE=graph`; `app env file:` lines for `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_SERVICE_MAILBOX` and `EMAIL_FROM`, and none for `GRAPH_CLIENT_SECRET`; one `database env file: GRAPH_CLIENT_SECRET set` line.

2. **Run the preflight, then restart the worker**, from the release checkout, with the same compose wrapper as step 5 of full mode. The worker reads its settings only when it starts. The web app reads none of these settings and needs no restart.

   ```bash
   export UAT_APP_ENV_FILE=/secure/.env.uat UAT_DATA_DIR=/srv/kfin-ideas-uat
   compose() { docker compose -p kfin-ideas-uat -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
     --env-file /secure/.env.uat --env-file /secure/.env.uat.db "$@"; }
   compose run --rm --no-deps -T worker python -m bootstrap.preflight
   compose up -d --wait worker
   ```

   Paste back: the preflight's `PROBLEM` lines, if any, and its last line; then the `Healthy` line. Pass: `preflight: ok` (its warnings are as before: none of them is about email), and `Healthy` for `kfin-ideas-uat-worker-1`. On `EMAIL_MODE=graph needs …`, `EMAIL_FROM must be the service mailbox's address …` or `GRAPH_SERVICE_MAILBOX must be the service mailbox's email address`, fix the env file and run this step again.

3. **Send one test message.** IT names its own test mailbox: not an alias, a distribution list or anyone's address, and not in HR's file. The check sends one fixed message, "1% Club email check", with no idea, no person and no template in it, through the same path every email takes. It refuses any address of someone in 1% Club (an exact match on the email 1% Club holds for them); it cannot tell an alias or a list, which is why IT uses its own test mailbox. It does not need `comms.email`: it sends nobody's email. Each run is written to `audit_log`.

   ```bash
   docker exec kfin-ideas-uat-worker-1 python -m comms.email_check --to <test mailbox> --actor ops:<staff code>
   docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT id, at, after FROM audit_log WHERE action = 'comms.email_check' ORDER BY id DESC LIMIT 1"
   ```

   The first command's last line is the result, `email check: …`. Above it the worker's own log lines may show (JSON, codes only, never the address or the token): leave them out. Then IT looks in the test mailbox: the message should arrive from the service mailbox within a few minutes. Paste back: the `email check:` line, the audit row (its ID, time and result) and whether the message arrived (yes or no). Pass: `email check: sent (Graph accepted it, HTTP 202)`, the audit row's `after` reads `{"result": "sent", "http_status": 202}`, and yes. Otherwise fix what the line names, restart the worker (step 2) and run the check again:
   - `email check: failed graph_token_4xx …`: the tenant ID, the client ID or the secret is wrong, or the secret has expired;
   - `email check: failed graph_4xx (HTTP 403)`: the permission has no admin consent, or the access policy does not cover the mailbox;
   - `email check: failed graph_4xx (HTTP 404)`: `GRAPH_SERVICE_MAILBOX` is not the mailbox's address;
   - `email check: failed graph_timeout`, `graph_unreachable`, `graph_token_timeout` or `graph_token_unreachable`: the outbound rule to the two hosts is missing, the proxy is not set (`HTTPS_PROXY` in the app env file, as in step 2 of full mode), or a TLS-inspecting proxy presents a certificate the worker does not trust;
   - `email check: failed graph_429`, `graph_token_429`, `graph_5xx` or `graph_token_5xx`: Graph is busy; wait 15 minutes and run it again;
   - any other line (for example `graph_not_configured`, `graph_4xx (HTTP 400)` or `(HTTP 401)`, or the preflight's mailbox line): send it to lane A.

   Do not go on to step 4 until the check passes.

   **Pass for steps 1 to 3 (email ready, `comms.email` off):** `comms.email off` before the worker restarts, the env lines as step 1 says, `preflight: ok`, the worker `Healthy`, `email check: sent (Graph accepted it, HTTP 202)` with its audit row and the message in the test mailbox, and `comms.email` still off. This section can stop here: email stays off and queued until the product lead says otherwise.

4. **Only on the product lead's word: switch `comms.email` on.** Skip this step unless the product lead has said email goes on. First read what is waiting: every email queued while `comms.email` was off goes out once it is on (routine mail in working hours, one a day per person; the rest at once). The product lead sees this count before the switch.

   ```bash
   docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT channel, state, error_code, count(*) FROM notifications WHERE channel IN ('email', 'digest') GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"
   ```

   Then an admin switches `comms.email` on from the Admin page, with a reason (for example "Email through Graph, the product lead's go"). The change is audited. Five minutes later, run the count again and `docker exec kfin-ideas-uat-worker-1 python -m core.killswitch list`.

   Paste back: both counts and the switch list. A `queued` row with `graph_429` is Graph asking to wait: it keeps its try and goes again after Graph's wait (at most 15 minutes); one with `graph_5xx`, `graph_timeout` or `graph_unreachable` (or their `graph_token_` forms, an outage at Microsoft's login) goes again within 5 minutes; neither switches email off. If the list reads `comms.email off`, the worker switched it off itself: see **If email switches itself off** below, and send lane A the counts.

   **Pass for step 4 (only if the product lead switched email on):** `comms.email on`, `email` `sent` has grown and `queued` has fallen. A `failed` row with a `graph_` code is one message Graph refused (`graph_4xx`) or one that failed three tries (`graph_5xx`, `graph_timeout`, `graph_unreachable` or their `graph_token_` forms): the rest go on; send lane A their counts.

**If email switches itself off:** when Graph says no email can go at all (the token is refused, the Graph settings are missing, or Graph's send answers 401, 403 or 404), the worker stops at once and switches `comms.email` off by itself, audited, with the code in the reason. No email spends a try; they all stay queued. Read the reason (it holds a code and a status, never a value):

```bash
docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "SELECT at, reason FROM audit_log WHERE action = 'kill_switch.set' AND entity = 'kill_switch:comms.email' ORDER BY id DESC LIMIT 1"
```

IT fixes the cause (step 3's list says which), restarts the worker (step 2) and runs the step 3 check until it passes; then an admin switches `comms.email` back on with a reason, on the product lead's word. Nothing switches it back on by itself.

**To stop email at any time:** an admin switches `comms.email` off on the Admin page, with a reason. The worker reads the switch before each email, so it stops within seconds; an email already being sent finishes first, and that one email goes. Emails then queue again and in-app messages carry on. Non-delivery reports for addresses that bounce land in the service mailbox's inbox; 1% Club does not read them, so the automatic 5% bounce switch-off does not see them. IT tells lane A if they pile up.

**Before a rollback:** with `EMAIL_MODE=graph`, a rollback to a build without BLD-A243 would send by SMTP to nothing (there is no SMTP server on the launch server) and fail every email after three tries. So before such a rollback an admin switches `comms.email` off, with a reason; after it, IT sets `EMAIL_MODE=smtp` in the app env file until the build has BLD-A243 again, and `comms.email` stays off.

## Rehearsal

`make uat-rehearsal` runs the same script on a developer machine with throwaway secrets and local stand-ins (S3, ClamAV, Mailpit), then tears it down, images and volumes included. It pauses the dev stack while it runs and starts it again after. The rehearsal sets a throwaway Sarvam key so preflight and the smoke checks pass as at launch. Nothing in the rehearsal calls the service. With `KEEP=1`, voice on the kept stack fails at the service. Run it before every UAT deploy. `REHEARSE_APP_ENV=prod make uat-rehearsal` rehearses the launch server's production mode (BLD-A235): the install loads no people, then a synthetic HR file of 20 people (`@kfintech.example`) goes in through stdin with the command in step 1b, one of them gets `admin` (`--actor ops:rehearsal`), and the smoke checks run without `--fresh`. It ends with `Production-mode rehearsal passed.`

## Moving a server from hash to BGE-M3 vectors (BLD-C211)

**This runbook cannot be run until the subsection "BGE-M3 model files for IT" below is filled in.**

Every stored vector (search chunks, the review desk's past corrections, cluster centroids) was made by the model the server ran with. A server that moves from `EMBEDDINGS_MODE=hash` to `bge-m3` must rebuild all of them in one go: hash and BGE-M3 vectors mixed together make similar ideas meaningless, with no error. `python -m similar.reembed` does it from the text already in the database. It is the re-index the BGE-M3 row under What you need first names, and it needs no company repo.

You need the install change from that row first: a worker image built with `--build-arg WITH_BGE=1`, and the BGE-M3 model files on the host, mounted read-only at the path `EMBEDDINGS_MODEL_PATH` names. The compose files mount no model folder today, so until that install change adds one to the worker service, give the one-off container the folder with `-v`, as below. The worker you start at the end needs the same folder, or every match fails.

Use the same compose wrapper as `scripts/uat/deploy.sh`, from the checkout the server was deployed from:

```bash
export UAT_APP_ENV_FILE=/secure/.env.uat UAT_DATA_DIR=/srv/kfin-ideas-uat
compose() { docker compose -p kfin-ideas-uat -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
  --env-file /secure/.env.uat --env-file /secure/.env.uat.db "$@"; }
MODELS="-v /srv/models/bge-m3:/models/bge-m3:ro"          # host folder : EMBEDDINGS_MODEL_PATH
```

1. Pick a quiet window and stop the worker, so matching never sees mixed vectors: `compose stop worker`. The web app builds drafts and sends ideas through the worker, so while it is stopped nobody can tell, check or send; the web app itself can stay up.
2. In the app env file, set `EMBEDDINGS_MODE=bge-m3` and `EMBEDDINGS_MODEL_PATH=/models/bge-m3` (the path inside the container). Build the worker image with the library: `compose build --build-arg WITH_BGE=1 worker`.
3. Check the model (AT-B5-01): `compose run --rm --no-deps -T $MODELS worker python -m embeddings.check`. It must print `dimensions 1024: True · normalised: True` and a paraphrase cosine of 0.80 or more, and exit 0.
4. Count first: `compose run --rm --no-deps -T $MODELS worker python -m similar.reembed --dry-run`. It loads the model and tries it on one synthetic sentence before it reads any row; if that fails it says why, changes nothing and exits 1. It also refuses, changing nothing, while another run is going or while the jobs table shows a worker in the middle of a job. Otherwise it prints the counts it would change and changes nothing.
5. Rebuild: `compose run --rm --no-deps -T $MODELS worker python -m similar.reembed`. It works in batches of 32, each committed as it goes. If it stops (an error, Ctrl-C or `docker stop`), the batches done are kept and it writes an `embeddings.rebuild_stopped` row to `audit_log`. After a stopped run, don't start the worker; run it again until it exits 0. Each run redoes every row.
6. Check the counts and the audit row. The real run's counts match the dry run's. Chunks re-embedded (repo, idea and file) plus skipped plus changed during the run equal all chunks. Skipped (chunks with no text) is normally 0. Changed during the run is 0 while the worker is stopped; if it is not, something wrote to the index during the run: run the command again until it is 0. Corrections re-embedded plus cleared equal all corrections. A correction is re-embedded from its idea's card as it is now, which may differ from the card when the correction was made; cleared means the idea is gone or its card is empty, and the review desk's past corrections simply leave that one out. Centroids recomputed plus cleared equal all clusters: cleared means no member has a vector to average, as the cluster code itself would leave it. Then read the one audit row, which holds the mode and the counts, never text:
   `compose exec -T postgres psql -U ideas -d ideas -c "SELECT at, actor, action, after FROM audit_log WHERE action LIKE 'embeddings.%' ORDER BY id DESC LIMIT 1"`
   It must say `process:reembed`, `embeddings.rebuilt` and `"mode": "bge-m3"`.
7. Start the worker, once the install change mounts the model folder on the worker service (`compose up` takes no `-v`): `compose up -d --wait worker`. Share one synthetic idea and check that similar ideas appear.

To go back to hash vectors, do the same with `EMBEDDINGS_MODE=hash` (no model folder, no build argument).

For IT: on an x86_64 server, `--build-arg WITH_BGE=1` installs sentence-transformers, which pulls PyTorch with its CUDA libraries (several GB) unless torch is installed from PyTorch's CPU-only index first. The Dockerfile does not do that today, so plan for the larger image.

### BGE-M3 model files for IT (file list and checksums)

**Placeholder: to be filled in by the coordinator from the BGE-M3 test of 20 Nov 2026.** Until it is, do not install the model files on a server: the list of files, their sizes and their SHA-256 checksums come here.
