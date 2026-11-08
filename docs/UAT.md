# UAT deploy runbook

For: KFin IT and the product team, deploying The Garage · Ideas to the UAT host. Synthetic data only: UAT never holds real employee, investor or client data.

## What you need first

| Item | Owner | Where it goes |
|---|---|---|
| A Linux host with Docker Engine and Compose v2.24 or later, and a checkout of this repo at the release tag | IT | — |
| Entra app registration for UAT: issuer URL, client ID, client secret, redirect `https://<uat host>/auth/callback` (§9.1 O2) | IT | app env file |
| Four random secrets of at least 32 characters each: `INTERNAL_API_TOKEN`, `SESSION_SECRET`, `CONTRIBUTOR_HMAC_SECRET`, `VAULT_ENCRYPTION_KEY` | InfoSec (vault) | app env file |
| Three database passwords of at least 20 random letters and digits (no symbols: they go into connection URLs): `POSTGRES_PASSWORD`, `DB_WEB_PASSWORD`, `DB_WORKER_PASSWORD` | InfoSec (vault) | database env file |
| KFin's file store and scanner: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `CLAMAV_HOST`, `CLAMAV_PORT` (required; the deploy refuses to fall back to the local stand-ins), and the Graph service mailbox or `SMTP_URL` | IT | app env file |
| Model route decision (D1). Without it the deploy starts in Mode B: `ai.all` off, scans queue | InfoSec | app env file |
| BGE-M3 model files, mounted at `EMBEDDINGS_MODEL_PATH`, and the worker image built with `--build-arg WITH_BGE=1` (AT-B5-01) | Product team | host folder |

## Env files

Two files, both readable only by the deploy account (`chmod 600`), never committed:

- **App env file** (`.env.uat`): start from `.env.example`, set `APP_ENV=uat` and every value above. Leave `DATABASE_URL` out; each service gets its own login.
- **Database env file** (`.env.uat.db`): only `POSTGRES_PASSWORD`, `DB_WEB_PASSWORD`, `DB_WORKER_PASSWORD`. It builds each service's own connection and is never handed to a container as a whole.

## Deploy

```bash
sudo mkdir -p /srv/kfin-ideas-uat && sudo chown 10001 /srv/kfin-ideas-uat     # the worker runs as uid 10001
UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-deploy APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db
```

The script stops at the first problem and says which. Its eight steps:

| Step | What happens | Stops when |
|---|---|---|
| 1 Preflight | Checks the settings without printing any secret | dev values, short secrets, mock sign-in, missing Entra or model settings |
| 2 Empty database | Starts Postgres; checks there are no tables and no company repo yet | anything already exists (a fresh deploy only) |
| 3 Migrations | `dbmate up`, then `dbmate status` | anything pending |
| 4 Service logins | Creates `ideas_web` and `ideas_worker` with their own passwords | — |
| 5 Seed | Company repo from `seed/company-repo/` (no dev overlay outside dev), OKF check, rules, index; 200 synthetic people | the repo is not valid OKF or a rule file fails |
| 6 Start | Every service up and healthy | a service does not become healthy in 4 minutes |
| 7 Model route | Leaves `ai.all` on if a route is configured, else switches it off (Mode B), audited | — |
| 8 Smoke tests | Twelve checks, listed below | any check fails |

Smoke checks (`python -m bootstrap.smoke --fresh`): the worker and web app answer; the sign-in page loads; the API refuses requests without a session; pages send signed-out people to sign in; the web app's own token reaches the worker and a wrong token is refused; the virus scanner answers (the report names the scanner and file store in use); all kill switches exist; the company repo is valid OKF with no dev-only files; the rules load; the index is at the repo's head; only synthetic people exist and nobody has a role yet.

## After the deploy

1. Grant the first admin (they then use the Admin page for everyone else):
   `docker compose -p kfin-ideas-uat … exec worker python -m identity.grants grant --employee-id <ID> --role admin --reason "First UAT admin, <ticket>" --actor ops:<staff code>`
   The person must have signed in once, or be in the HR import.
2. When the model route is approved: set `LLM_MODE` and the key in the app env file, restart the worker, run `make eval` against the route, then switch `ai.all` on from the Admin page with a reason.
3. Point KFin's reverse proxy (TLS) at the web app's port (`UAT_WEB_PORT`, default 3100). Only the web app is published.

## Rehearsal

`make uat-rehearsal` runs the same script on a developer machine with throwaway secrets and local stand-ins (S3, ClamAV, Mailpit), then tears it down, images and volumes included. It pauses the dev stack while it runs and starts it again after. Run it before every UAT deploy.
