# UAT deploy runbook

**Read this runbook from `release/2026-11-20`** (`git show origin/release/2026-11-20:docs/UAT.md`). A copy inside a checkout can be out of date: the one in `launch-2026-11-20` lacks the privacy notice version and the Ones Committee step, and the one in `launch-2026-11-20-r2` lacks the fixes made after it.

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
| KFin's file store and scanner: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `CLAMAV_HOST`, `CLAMAV_PORT` (required; the deploy refuses to fall back to the local stand-ins), and the Graph service mailbox or `SMTP_URL`. If KFin's scanner is not on 3310, set `WORKER_CLAMAV_PORT` in the app env file (`CLAMAV_PORT` alone is ignored) | IT | app env file |
| Model route decision (D1). Without it the deploy starts in Mode B: `ai.all` off, scans queue. At launch, `LLM_MODE=fake` whatever D1 says (see the bold line below this table) | InfoSec | app env file |
| Not at launch: BGE-M3 (AT-B5-01). The deploy builds the worker without it (the compose files pass no `WITH_BGE` build argument and mount no model folder), so set `EMBEDDINGS_MODE=hash`; the preflight warns that matching quality is not representative. Adding BGE-M3 is an install change after launch: the build argument, the model files mounted at `EMBEDDINGS_MODEL_PATH`, then `EMBEDDINGS_MODE=bge-m3` and a re-index | Product team | app env file |
| Voice through Sarvam (DEC-108, on at launch): in the **database** env file (worker only), `SARVAM_API_KEY`; the deploy refuses it in the app env file, which the web app also reads, and the web container's copy is blanked. In the app env file, `SPEECH_MODE=sarvam` and `SPEECH_HOSTED_APPROVAL=DEC-108` (the deploy refuses `sarvam` without both). Outbound HTTPS and WSS from the worker to `api.sarvam.ai` only. The speech container and model below are now an optional fallback, not needed for launch | InfoSec (key in the vault), IT (outbound rule) | database env file, app env file |
| Optional fallback, not needed for launch (DEC-108): voice notes on the isolated speech service (DEC-096, BLD-C012, BLD-C015): its own container (`speech`, compose profile `speech`, built from `services/worker/speech_service/Dockerfile`), started by the deploy when the app env file sets `SPEECH_ENGINE_URL=http://speech:8300`. It runs as uid 10002 with a read-only root filesystem, a 64 MB tmpfs `/tmp`, no capabilities and no published port, on an internal network only the worker shares (no route to Postgres, S3, mail or the internet). On the host: the speech model (faster-whisper, multilingual, CTranslate2 int8) in `SPEECH_MODEL_DIR`, mounted read-only; about 2–3 GB of memory for it (`SPEECH_MEM_LIMIT`, default 3g). In the **database** env file: `SPEECH_SERVICE_TOKEN`, 32 or more random letters and digits, never the same as `INTERNAL_API_TOKEN` (the deploy refuses it in the app env file, which the web app also reads, refuses `INTERNAL_API_TOKEN` in the database env file, and refuses the two if equal). In the app env file: `SPEECH_ENGINE_URL=http://speech:8300` exactly (the deploy and the worker refuse any other host or scheme outside dev and test). The image is pinned by digest and hashes; it needs PyPI and Docker Hub only at build time | IT (host, memory, model folder), InfoSec (token in the vault) | database env file, host folder |
| Voice notes, KFin's S3 (DEC-096, BLD-C006): on the **quarantine** bucket, a lifecycle rule `voice-notes-expire-1-day` that expires the prefix `voice/` after 1 day, and **no versioning** on that bucket (a kept version would outlive a delete). The worker tries to set the rule itself at start; where the store refuses, IT sets it. The smoke check fails if the quarantine bucket is versioned | IT | the file store |

**At launch (Capture first), the app env file must say `LLM_MODE=fake`, even when the model key is already in it.** With `LLM_MODE=anthropic` and a key, or `LLM_MODE=bedrock`, step 7 runs the golden sets on the launch database and leaves `ai.all` on, switching off only the agents whose golden set fails. AI is switched on later, only when the product lead says so after the golden sets pass on the real route: follow step 4 under After the deploy (set `LLM_MODE` and the key, restart the worker, run the golden sets on the route), then switch `ai.all` on from the Admin page with a reason. **Never switch `ai.all` on while `LLM_MODE=fake`: the fake route would answer people with canned text.**

## Env files

Two files, both readable only by the deploy account (`chmod 600`), never committed:

- **App env file** (`.env.uat`): start from `.env.example`, set `APP_ENV=prod` on the launch server (`uat` on a UAT host) and every value above. Leave `DATABASE_URL` out; each service gets its own login. Set `KFIN_EMAIL_DOMAINS=kfintech.com` in the app env file (add any other KFin email domain), whether or not Entra releases the employeeId claim: without it the web app refuses every sign-in by email. On the launch server the preflight then warns that `kfintech.example` is missing; that warning is about UAT's synthetic people and does not apply with `APP_ENV=prod`.
- **Database env file** (`.env.uat.db`): only `POSTGRES_PASSWORD`, `DB_WEB_PASSWORD`, `DB_WORKER_PASSWORD`, `PSEUDONYM_VAULT_KEY` and `SARVAM_API_KEY` (voice through Sarvam, DEC-108; never in the app env file, which the web app also reads), plus `SPEECH_SERVICE_TOKEN` only with the optional speech service. It builds each service's own settings and is never handed to a container as a whole.

## Deploy

```bash
sudo mkdir -p /srv/kfin-ideas-uat && sudo chown 10001 /srv/kfin-ideas-uat     # the worker runs as uid 10001
UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-deploy APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db
```

The script stops at the first problem and says which. Its eight steps:

| Step | What happens | Stops when |
|---|---|---|
| 1 Preflight | Checks the settings without printing any secret | dev values, short secrets, mock sign-in, missing Entra or model settings, a privacy notice version that differs from the build's |
| 2 Empty database | Starts Postgres; checks there are no tables and no company repo yet | anything already exists (a fresh deploy only) |
| 3 Migrations | `dbmate up`, then `dbmate status` | anything pending |
| 4 Service logins | Creates `ideas_web` and `ideas_worker` with their own passwords | — |
| 5 Seed | Company repo from `seed/company-repo/` (no dev overlay outside dev), OKF check, rules, index; 200 synthetic people, none with `APP_ENV=prod` (the line reads `people: none loaded in production; …`) | the repo is not valid OKF or a rule file fails |
| 6 Start | Every service up and healthy | a service does not become healthy in 4 minutes |
| 7 Model route | Leaves `ai.all` on if a route is configured, else switches it off (Mode B), audited | — |
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
4. When the model route is approved: set `LLM_MODE` and the key in the app env file, restart the worker, run `make eval` against the route, then switch `ai.all` on from the Admin page with a reason.
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
| 4 Backup | `pg_dump` of the database to `backups/` (mode 600), checked with `pg_restore --list`; an archive of the company repo | the backup fails or is empty (nothing changed) |
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

6. Rollback, only when the product lead decides it, from the same new checkout, with the backup the upgrade printed:

   ```bash
   UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-rollback BACKUP=/srv/kfin-ideas-uat/backups/upgrade-<time>-<old>.dump APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db
   ```

   It stops web and worker, puts the kept images back, drops and recreates the database and restores the backup, always restores the company repo from its archive, starts web and worker with the old version's compose files, runs the smoke checks and records the old version as installed. If you changed `PRIVACY_NOTICE_VERSION` for the upgrade, set it back first: the rollback stops and names the old version. It prints the kill switches before and after: they go back to their state at backup time, so check them on the Admin page.

   Paste back: the whole output. Pass: `database restored: migrations as at the backup (N)`, `smoke: all checks passed`, and the last line `rollback: back on <old> in Ns. Anything written after the backup is lost.` Then put the checkout back on the old tag, so it matches what runs, and run step 5's checks again; the switches should match step 1:

   ```bash
   git checkout <old tag> && git describe --tags --exact-match
   ```

   Pass: the tag from step 1. If step 1 showed a commit with no tag, check out that commit instead and check `git rev-parse HEAD` prints it.

**What a rollback loses:** everything written after the backup. That covers ideas, drafts, messages, decisions, notice acceptances and any kill switch changed on the Admin page. That is why upgrades run in a quiet window.

**Kill switches:** the upgrade never changes a kill switch, and neither does the rollback. The upgrade only reads `ai.all`, and stops if it is on while there is no model route (`LLM_MODE=fake`). A rollback puts the switches back as they were at the backup, because they live in the database.

**The backup holds personal data:** the whole database, the sharers' own words and the encrypted vault included. It stays on this server under the database's controls (file mode 600, folder 700, owned by the deploy account). It is never copied off the server. Keep at least the latest backup; remove older ones only when the product lead says so.

**Rehearse first:** before each upgrade of the server, lane A runs `make uat-rehearsal-upgrade FROM=<the installed tag> REHEARSE_APP_ENV=prod` on a developer machine, at the new tag. It installs FROM with FROM's own deploy in production mode (no people), then does what IT did after the install, on synthetic people only (`@kfintech.example`): a synthetic HR file of 20 through stdin, `admin` for one of them, `core_committee` for another, and the smoke checks without `--fresh`. With a checkout that has the start sweep, it then adds three synthetic files on FROM through FROM's own code (one that reads "Didn't upload" after its waits, one still waiting on its last try, and the antivirus test file), and checks them by ID after each later phase (`files-upgrade`, `files-rollback`, `files-again`); without the sweep the summary says `files-from SKIPPED`. Then it upgrades to the checkout, rolls back, upgrades again, prints a summary (`== Summary (upgrade rehearsal, APP_ENV=prod)`, one PASS line per phase) and tears it all down (`KEEP=1` keeps it). Its last line is `rehearsal: upgrade, rollback and upgrade again all passed` only when every phase has its PASS line; otherwise `rehearsal: FAILED (exit N)`, or `rehearsal: STOPPED (TERM) after <phase>` when it was stopped, which also stops the runs it started. Ones Committee, which only the Admin page gives, is not rehearsed: nobody can sign in there. Without `REHEARSE_APP_ENV=prod` it rehearses a UAT host (`APP_ENV=uat`, with synthetic people loaded at install). It refuses while the dev stack runs and never starts or stops it: run `make down` from the main checkout first and `make up` there after.

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
