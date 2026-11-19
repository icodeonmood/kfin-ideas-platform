# UAT deploy runbook

**Read this runbook from `main`.** The copy inside the launch tag's checkout is older: it lacks the privacy notice version and the Ones Committee step.

For: KFin IT and the product team, deploying The Garage · Ideas to the UAT host. Synthetic data only: UAT never holds real employee, investor or client data.

## What you need first

| Item | Owner | Where it goes |
|---|---|---|
| A Linux host with Docker Engine and Compose v2.24 or later, and a checkout of this repo at the launch tag `launch-2026-11-20` (commit 29c1ef9c), not `main` | IT | — |
| The privacy notice version: `PRIVACY_NOTICE_VERSION=0.2-draft`, exactly the version in `apps/web/src/content/privacy-notice.ts` at the launch tag. If the two differ, nobody gets past the notice at first sign-in; the deploy's preflight stops on a mismatch (BLD-A232). When the DPO's lines land, the build's version becomes `0.2` and the env file changes with it; on that update no script checks it, so check it by hand before restarting the web app | IT | app env file |
| Entra app registration for UAT: issuer URL, client ID, client secret, redirect `https://<uat host>/auth/callback` (§9.1 O2) | IT | app env file |
| Four random secrets of at least 32 characters each: `INTERNAL_API_TOKEN`, `SESSION_SECRET`, `CONTRIBUTOR_HMAC_SECRET`, `VAULT_ENCRYPTION_KEY` | InfoSec (vault) | app env file |
| Three database passwords of at least 20 random letters and digits (no symbols: they go into connection URLs): `POSTGRES_PASSWORD`, `DB_WEB_PASSWORD`, `DB_WORKER_PASSWORD` | InfoSec (vault) | database env file |
| The worker-only pseudonym vault key: `PSEUDONYM_VAULT_KEY`, at least 32 random letters and digits, different from `VAULT_ENCRYPTION_KEY`. It must never be in the app env file, which the web app also reads | InfoSec (vault) | database env file |
| KFin's file store and scanner: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `CLAMAV_HOST`, `CLAMAV_PORT` (required; the deploy refuses to fall back to the local stand-ins), and the Graph service mailbox or `SMTP_URL` | IT | app env file |
| Model route decision (D1). Without it the deploy starts in Mode B: `ai.all` off, scans queue | InfoSec | app env file |
| BGE-M3 model files, mounted at `EMBEDDINGS_MODEL_PATH`, and the worker image built with `--build-arg WITH_BGE=1` (AT-B5-01) | Product team | host folder |
| Voice through Sarvam (DEC-108, on at launch): in the **database** env file (worker only), `SARVAM_API_KEY`; the deploy refuses it in the app env file, which the web app also reads, and the web container's copy is blanked. In the app env file, `SPEECH_MODE=sarvam` and `SPEECH_HOSTED_APPROVAL=DEC-108` (the deploy refuses `sarvam` without both). Outbound HTTPS and WSS from the worker to `api.sarvam.ai` only. The speech container and model below are now an optional fallback, not needed for launch | InfoSec (key in the vault), IT (outbound rule) | database env file, app env file |
| Optional fallback, not needed for launch (DEC-108): voice notes on the isolated speech service (DEC-096, BLD-C012, BLD-C015): its own container (`speech`, compose profile `speech`, built from `services/worker/speech_service/Dockerfile`), started by the deploy when the app env file sets `SPEECH_ENGINE_URL=http://speech:8300`. It runs as uid 10002 with a read-only root filesystem, a 64 MB tmpfs `/tmp`, no capabilities and no published port, on an internal network only the worker shares (no route to Postgres, S3, mail or the internet). On the host: the speech model (faster-whisper, multilingual, CTranslate2 int8) in `SPEECH_MODEL_DIR`, mounted read-only; about 2–3 GB of memory for it (`SPEECH_MEM_LIMIT`, default 3g). In the **database** env file: `SPEECH_SERVICE_TOKEN`, 32 or more random letters and digits, never the same as `INTERNAL_API_TOKEN` (the deploy refuses it in the app env file, which the web app also reads, refuses `INTERNAL_API_TOKEN` in the database env file, and refuses the two if equal). In the app env file: `SPEECH_ENGINE_URL=http://speech:8300` exactly (the deploy and the worker refuse any other host or scheme outside dev and test). The image is pinned by digest and hashes; it needs PyPI and Docker Hub only at build time | IT (host, memory, model folder), InfoSec (token in the vault) | database env file, host folder |
| Voice notes, KFin's S3 (DEC-096, BLD-C006): on the **quarantine** bucket, a lifecycle rule `voice-notes-expire-1-day` that expires the prefix `voice/` after 1 day, and **no versioning** on that bucket (a kept version would outlive a delete). The worker tries to set the rule itself at start; where the store refuses, IT sets it. The smoke check fails if the quarantine bucket is versioned | IT | the file store |

## Env files

Two files, both readable only by the deploy account (`chmod 600`), never committed:

- **App env file** (`.env.uat`): start from `.env.example`, set `APP_ENV=uat` and every value above. Leave `DATABASE_URL` out; each service gets its own login.
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

Smoke checks (`python -m bootstrap.smoke --fresh`): the worker and web app answer; the sign-in page loads; the API refuses requests without a session; pages send signed-out people to sign in; the web app's own token reaches the worker and a wrong token is refused; the virus scanner answers (the report names the scanner and file store in use); all kill switches exist; the company repo is valid OKF with no dev-only files; the rules load; the index is at the repo's head; only synthetic people exist and nobody has a role yet; voice notes are off, or on through Sarvam with `speech.hosted` on and its approval reference (DEC-108), or on the engine on KFin's own server, never the fake speech route, and the quarantine bucket is not versioned (DEC-096).

## After the deploy

1. Grant the first admin (they then use the Admin page for everyone else):
   `docker compose -p kfin-ideas-uat … exec worker python -m identity.grants grant --employee-id <ID> --role admin --reason "First UAT admin, <ticket>" --actor ops:<staff code>`
   The person must have signed in once, or be in the HR import.
2. Ones Committee members, at launch (the product lead's decision, 19 Nov): give each member **Ones Committee** on the Admin page, and IT also gives each of them `core_committee` with the command in step 1 (`--role core_committee --reason "Ones Committee at launch, <ticket>"`). Give both. Ones Committee is the 1% Club role and stays. `core_committee` is a stopgap: until lane B's fix after launch, a member with only Ones Committee can use the Ones Committee page and open ideas, but cannot play an idea read aloud (Listen) or open the review desk's pages; the web app gives those only through `core_committee`. The Admin page cannot give `core_committee` (it lists it as a retired role), and the command cannot give Ones Committee. `core_committee` also shows some older pages (Delivery, The Ember note) and, while no chair is named, its holders receive the escalations sent when a review timer runs out. Do not remove it before the fix, even though the Admin page calls it retired. Once the fix is installed, remove it on the Admin page (the row reads "Core committee member (retired role)").
3. Voice is on at launch (`capture.voice` and `speech.hosted`, DEC-108, migration `20261122300530`). Check the smoke line "capture.voice on; speech.hosted on; SPEECH_MODE sarvam; Sarvam key set" (no call is made to Sarvam) and the go/no-go voice rows say "met". If the watch has switched them off with "Sarvam key missing (automatic)", put `SARVAM_API_KEY` in the database env file, restart the worker and switch both on from the Admin page with a reason. Then record one synthetic voice note on a draft and check that the words appear as you speak, the English copy is labelled "Typed up in English", and nothing is written to the quarantine bucket. Before the gates, the product lead runs `make sarvam-live` from a checkout with the local stack up, with `SARVAM_API_KEY` loaded in their own terminal (never in an env file of this repo), and every line reads PASS (BLD-C177).
4. When the model route is approved: set `LLM_MODE` and the key in the app env file, restart the worker, run `make eval` against the route, then switch `ai.all` on from the Admin page with a reason.
5. Point KFin's reverse proxy (TLS) at the web app's port (`UAT_WEB_PORT`, default 3100). Only the web app is published.

## Rehearsal

`make uat-rehearsal` runs the same script on a developer machine with throwaway secrets and local stand-ins (S3, ClamAV, Mailpit), then tears it down, images and volumes included. It pauses the dev stack while it runs and starts it again after. The rehearsal sets a throwaway Sarvam key so preflight and the smoke checks pass as at launch. Nothing in the rehearsal calls the service. With `KEEP=1`, voice on the kept stack fails at the service. Run it before every UAT deploy.
