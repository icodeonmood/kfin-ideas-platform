# UAT deploy runbook

**Read this runbook from `release/2026-11-20`** (`git show origin/release/2026-11-20:docs/UAT.md`). A copy inside a checkout can be out of date: the one in `launch-2026-11-20` lacks the privacy notice version and the Ones Committee step, and the one in `launch-2026-11-20-r2` lacks the fixes made after it.

For: KFin IT and the product team, installing 1% Club with `make uat-deploy`, on a UAT host or on the launch server. **The launch server is production** (`APP_ENV=prod`): real employees sign in there. Synthetic data only in dev, UAT and tests: they never hold real employee, investor or client data. On any server, the deploy loads 200 synthetic people (all `@kfintech.example`, who cannot sign in), which the smoke checks need; `uat` and `prod` behave the same in the code.

## What you need first

| Item | Owner | Where it goes |
|---|---|---|
| A Linux host with Docker Engine and Compose v2.24 or later, and a checkout of this repo at the launch tag `launch-2026-11-20-r2`, the commit lane E tags with privacy notice 0.2 final, not `main`. `launch-2026-11-20` (29c1ef9c) is the earlier build with notice 0.2-draft: do not install it | IT | — |
| The privacy notice version: `PRIVACY_NOTICE_VERSION=0.2`, exactly the version in `apps/web/src/content/privacy-notice.ts` at the launch tag. If the two differ, nobody gets past the notice at first sign-in; the deploy's preflight stops on a mismatch (BLD-A232, BLD-A233). If a later build changes the notice's version, the env file changes with it; `make uat-upgrade` checks it and stops on a mismatch (BLD-A234) | IT | app env file |
| Entra app registration for UAT: issuer URL, client ID, client secret, redirect `https://<uat host>/auth/callback` (§9.1 O2) | IT | app env file |
| Four random secrets of at least 32 characters each: `INTERNAL_API_TOKEN`, `SESSION_SECRET`, `CONTRIBUTOR_HMAC_SECRET`, `VAULT_ENCRYPTION_KEY` | InfoSec (vault) | app env file |
| Three database passwords of at least 20 random letters and digits (no symbols: they go into connection URLs): `POSTGRES_PASSWORD`, `DB_WEB_PASSWORD`, `DB_WORKER_PASSWORD` | InfoSec (vault) | database env file |
| The worker-only pseudonym vault key: `PSEUDONYM_VAULT_KEY`, at least 32 random letters and digits, different from `VAULT_ENCRYPTION_KEY`. It must never be in the app env file, which the web app also reads | InfoSec (vault) | database env file |
| KFin's file store and scanner: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `CLAMAV_HOST`, `CLAMAV_PORT` (required; the deploy refuses to fall back to the local stand-ins), and the Graph service mailbox or `SMTP_URL` | IT | app env file |
| Model route decision (D1). Without it the deploy starts in Mode B: `ai.all` off, scans queue. At launch, `LLM_MODE=fake` whatever D1 says (see the bold line below this table) | InfoSec | app env file |
| Not at launch: BGE-M3 (AT-B5-01). The deploy builds the worker without it (the compose files pass no `WITH_BGE` build argument and mount no model folder), so set `EMBEDDINGS_MODE=hash`; the preflight warns that matching quality is not representative. Adding BGE-M3 is an install change after launch: the build argument, the model files mounted at `EMBEDDINGS_MODEL_PATH`, then `EMBEDDINGS_MODE=bge-m3` and a re-index | Product team | app env file |
| Voice through Sarvam (DEC-108, on at launch): in the **database** env file (worker only), `SARVAM_API_KEY`; the deploy refuses it in the app env file, which the web app also reads, and the web container's copy is blanked. In the app env file, `SPEECH_MODE=sarvam` and `SPEECH_HOSTED_APPROVAL=DEC-108` (the deploy refuses `sarvam` without both). Outbound HTTPS and WSS from the worker to `api.sarvam.ai` only. The speech container and model below are now an optional fallback, not needed for launch | InfoSec (key in the vault), IT (outbound rule) | database env file, app env file |
| Optional fallback, not needed for launch (DEC-108): voice notes on the isolated speech service (DEC-096, BLD-C012, BLD-C015): its own container (`speech`, compose profile `speech`, built from `services/worker/speech_service/Dockerfile`), started by the deploy when the app env file sets `SPEECH_ENGINE_URL=http://speech:8300`. It runs as uid 10002 with a read-only root filesystem, a 64 MB tmpfs `/tmp`, no capabilities and no published port, on an internal network only the worker shares (no route to Postgres, S3, mail or the internet). On the host: the speech model (faster-whisper, multilingual, CTranslate2 int8) in `SPEECH_MODEL_DIR`, mounted read-only; about 2–3 GB of memory for it (`SPEECH_MEM_LIMIT`, default 3g). In the **database** env file: `SPEECH_SERVICE_TOKEN`, 32 or more random letters and digits, never the same as `INTERNAL_API_TOKEN` (the deploy refuses it in the app env file, which the web app also reads, refuses `INTERNAL_API_TOKEN` in the database env file, and refuses the two if equal). In the app env file: `SPEECH_ENGINE_URL=http://speech:8300` exactly (the deploy and the worker refuse any other host or scheme outside dev and test). The image is pinned by digest and hashes; it needs PyPI and Docker Hub only at build time | IT (host, memory, model folder), InfoSec (token in the vault) | database env file, host folder |
| Voice notes, KFin's S3 (DEC-096, BLD-C006): on the **quarantine** bucket, a lifecycle rule `voice-notes-expire-1-day` that expires the prefix `voice/` after 1 day, and **no versioning** on that bucket (a kept version would outlive a delete). The worker tries to set the rule itself at start; where the store refuses, IT sets it. The smoke check fails if the quarantine bucket is versioned | IT | the file store |

**At launch (Capture first), the app env file must say `LLM_MODE=fake`, even when the model key is already in it.** With `LLM_MODE=anthropic` and a key, or `LLM_MODE=bedrock`, step 7 runs the golden sets on the launch database and leaves `ai.all` on, switching off only the agents whose golden set fails. AI is switched on later, only when the product lead says so after the golden sets pass on the real route: follow step 4 under After the deploy (set `LLM_MODE` and the key, restart the worker, run the golden sets on the route), then switch `ai.all` on from the Admin page with a reason. **Never switch `ai.all` on while `LLM_MODE=fake`: the fake route would answer people with canned text.**

## Env files

Two files, both readable only by the deploy account (`chmod 600`), never committed:

- **App env file** (`.env.uat`): start from `.env.example`, set `APP_ENV=prod` on the launch server (`uat` on a UAT host) and every value above. Leave `DATABASE_URL` out; each service gets its own login.
- **Database env file** (`.env.uat.db`): only `POSTGRES_PASSWORD`, `DB_WEB_PASSWORD`, `DB_WORKER_PASSWORD` and `PSEUDONYM_VAULT_KEY`. It builds each service's own settings and is never handed to a container as a whole.

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
| 5 Seed | Company repo from `seed/company-repo/` (no dev overlay outside dev), OKF check, rules, index; 200 synthetic people | the repo is not valid OKF or a rule file fails |
| 6 Start | Every service up and healthy | a service does not become healthy in 4 minutes |
| 7 Model route | Leaves `ai.all` on if a route is configured, else switches it off (Mode B), audited | — |
| 8 Smoke tests | Thirteen checks, listed below | any check fails |

Smoke checks (`python -m bootstrap.smoke --fresh`): the worker and web app answer; the sign-in page loads; the API refuses requests without a session; pages send signed-out people to sign in; the web app's own token reaches the worker and a wrong token is refused; the virus scanner answers (the report names the scanner and file store in use); all kill switches exist; the company repo is valid OKF with no dev-only files; the rules load; the index is at the repo's head; only synthetic people exist and nobody has a role yet; voice notes are off, or on through Sarvam with `speech.hosted` on, its approval reference and the Sarvam key (DEC-108), or on the engine on KFin's own server, never the fake speech route, and the quarantine bucket is not versioned (DEC-096).

## After the deploy

1. Grant the first admin (they then use the Admin page for everyone else):
   `docker compose -p kfin-ideas-uat … exec worker python -m identity.grants grant --employee-id <ID> --role admin --reason "First UAT admin, <ticket>" --actor ops:<staff code>`
   The person must have signed in once, or be in the HR import.
2. Ones Committee members, at launch (the product lead's decision, 19 Nov): give each member **Ones Committee** on the Admin page, and IT also gives each of them `core_committee` with the command in step 1 (`--role core_committee --reason "Ones Committee at launch, <ticket>"`). Give both. Ones Committee is the 1% Club role and stays. `core_committee` is a stopgap: until lane B's fix after launch, a member with only Ones Committee can use the Ones Committee page and open ideas, but cannot play an idea read aloud (Listen) or open the review desk's pages; the web app gives those only through `core_committee`. The Admin page cannot give `core_committee` (it lists it as a retired role), and the command cannot give Ones Committee. `core_committee` also shows some older pages (Delivery, The Ember note) and, while no chair is named, its holders receive the overdue emails of the older timers that escalate to the chair (the 1% Club's own review clock sends none). Do not remove it before the fix, even though the Admin page calls it retired. Once the fix is installed, remove it on the Admin page (the row reads "Core committee member (retired role)").
3. Voice is on at launch (`capture.voice` and `speech.hosted`, DEC-108, migration `20261122300530`). Check the smoke line "capture.voice on; speech.hosted on; SPEECH_MODE sarvam; Sarvam key set" (no call is made to Sarvam) and the go/no-go voice rows say "met". If the watch has switched them off with "Sarvam key missing (automatic)", put `SARVAM_API_KEY` in the database env file, restart the worker and switch both on from the Admin page with a reason. Then record one synthetic voice note on a draft and check that the words appear as you speak, the English copy is labelled "Typed up in English", and nothing is written to the quarantine bucket. Before the gates, the product lead runs `make sarvam-live` from a checkout with the local stack up, with `SARVAM_API_KEY` loaded in their own terminal (never in an env file of this repo), and every line reads PASS (BLD-C177).
4. When the model route is approved: set `LLM_MODE` and the key in the app env file, restart the worker, run `make eval` against the route, then switch `ai.all` on from the Admin page with a reason.
5. Point KFin's reverse proxy (TLS) at the web app's port (`UAT_WEB_PORT`, default 3100). Only the web app is published.

## Updating the live server (upgrade and rollback)

Every fix after the install reaches the server this way, never by hand (BLD-A234). Run it in a quiet window and tell the review desk first: a rollback loses anything written after the backup. Use the same checkout, data folder and env files as the install. The commands below use the paths from Deploy.

**Once, before the first upgrade,** if the deploy account is not root: `sudo install -d -m 700 -o <deploy account> /srv/kfin-ideas-uat/ops /srv/kfin-ideas-uat/backups`. The upgrade writes its records and backups there. The worker runs as uid 10001 and cannot read them. Without this step the upgrade stops at step 1 and prints the same command.

1. Check out the new tag:

   ```bash
   git fetch --tags && git checkout <new tag> && git rev-parse HEAD
   ```

   Pass: the sha lane E gives with the tag, and `git status` shows nothing changed.

2. Check the env files still match the new build:

   ```bash
   grep -E '^(PRIVACY_NOTICE_VERSION|LLM_MODE)=' /secure/.env.uat
   grep -E '^\s*version:' apps/web/src/content/privacy-notice.ts
   ```

   Pass: the two versions are the same, and `LLM_MODE=fake` unless the product lead has switched AI on. If the versions differ, set `PRIVACY_NOTICE_VERSION` to the build's version. The upgrade stops on a mismatch.

3. Upgrade:

   ```bash
   UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-upgrade APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db FROM=launch-2026-11-20-r2
   ```

   **`FROM=launch-2026-11-20-r2` is needed the first time only:** the r2 install wrote no record of what it installed. Every upgrade and every later install writes `/srv/kfin-ideas-uat/ops/installed.json`, so leave `FROM` out after that. If you give it, it must match the record.

   Pass: `FROM <sha> launch-2026-11-20-r2` and `TO <sha> <new tag>` at the top, `backup: … (N tables with data)`, `Pending: 0`, `migrations applied now: N`, `smoke: all checks passed`, and the last line `upgrade: <old> -> <new> done in Ns. Backup kept at /srv/kfin-ideas-uat/backups/upgrade-<time>-<old>.dump`.

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

Before step 5 a failure changes nothing: the old version keeps serving. From step 5 on, a failure prints the rollback command and stops. It never rolls back by itself: decide with the product lead, then run it.

4. Rollback, from the same new checkout, with the backup the upgrade printed:

   ```bash
   UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-rollback BACKUP=/srv/kfin-ideas-uat/backups/upgrade-<time>-<old>.dump APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db
   ```

   It stops web and worker, puts the kept images back, drops and recreates the database and restores the backup, always restores the company repo from its archive, starts web and worker with the old version's compose files, runs the smoke checks and records the old version as installed. If you changed `PRIVACY_NOTICE_VERSION` for the upgrade, set it back first: the rollback stops and names the old version.

   Pass: `database restored: migrations as at the backup (N)`, `smoke: all checks passed`, and the last line `rollback: back on <old> in Ns.`

**What a rollback loses:** everything written after the backup. That covers ideas, drafts, messages, decisions, notice acceptances and any kill switch changed on the Admin page. That is why upgrades run in a quiet window.

**Kill switches:** the upgrade never changes a kill switch, and neither does the rollback. The upgrade only reads `ai.all`, and stops if it is on while there is no model route (`LLM_MODE=fake`). A rollback puts the switches back as they were at the backup, because they live in the database.

**The backup holds personal data:** the whole database, the sharers' own words and the encrypted vault included. It stays on this server under the database's controls (file mode 600, folder 700, owned by the deploy account). It is never copied off the server. Keep at least the latest backup; remove older ones only when the product lead says so.

**What to paste back:** the output only, that is the `==` lines, the pass lines and any `STOPPED:` line. Never paste an env file or a secret. The scripts print none.

**Rehearse first:** lane A runs `make uat-rehearsal-upgrade FROM=launch-2026-11-20-r2` on a developer machine before each upgrade of the server. It installs FROM with FROM's own deploy, upgrades to the checkout, rolls back, upgrades again, prints a summary and tears it all down (`KEEP=1` keeps it). It refuses while the dev stack runs and never starts or stops it: run `make down` from the main checkout first and `make up` there after.

## Rehearsal

`make uat-rehearsal` runs the same script on a developer machine with throwaway secrets and local stand-ins (S3, ClamAV, Mailpit), then tears it down, images and volumes included. It pauses the dev stack while it runs and starts it again after. The rehearsal sets a throwaway Sarvam key so preflight and the smoke checks pass as at launch. Nothing in the rehearsal calls the service. With `KEEP=1`, voice on the kept stack fails at the service. Run it before every UAT deploy.
