#!/usr/bin/env bash
# Rehearse the UAT deploy on this machine (AT-B7-06): a UAT-shaped stack from an empty database, with throwaway
# secrets, then torn down. The dev stack is stopped while it runs (its data is kept) and started again after.
# The real UAT host needs KFin's Entra app, vault secrets and services (§9.1); see docs/UAT.md.
#
#   scripts/uat/rehearse.sh            # KEEP=1 leaves the rehearsal stack running for a look
#   REHEARSE_APP_ENV=prod scripts/uat/rehearse.sh
#
# REHEARSE_APP_ENV=prod (BLD-A235) rehearses the launch server's production mode: the install loads no people, then
# the steps after the first admin in docs/UAT.md run with a small SYNTHETIC HR file through stdin, a grant and the
# smoke checks without --fresh. The default stays uat.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
WORK="$ROOT/.data-uat-rehearsal"
PROJECT=kfin-ideas-uat-rehearsal
REHEARSE_APP_ENV="${REHEARSE_APP_ENV:-uat}"
[[ "$REHEARSE_APP_ENV" == "uat" || "$REHEARSE_APP_ENV" == "prod" ]] \
  || { echo "REHEARSE_APP_ENV must be uat (the default) or prod"; exit 1; }
[[ -e "$WORK" ]] && { echo "$WORK exists from an earlier run; remove it first"; exit 1; }
mkdir -p "$WORK/data"
rand() { openssl rand -hex 24; }

cat > "$WORK/app.env" <<ENV
APP_ENV=$REHEARSE_APP_ENV
APP_BASE_URL=http://localhost:3100
INTERNAL_API_TOKEN=$(rand)
SESSION_SECRET=$(rand)
CONTRIBUTOR_HMAC_SECRET=$(rand)
VAULT_ENCRYPTION_KEY=$(rand)
KFIN_EMAIL_DOMAINS=kfintech.com,kfintech.example
REPO_WRITER_AUTHOR=Ideas Platform Bot <ideas-bot@uat.invalid>
OIDC_MODE=entra
OIDC_ISSUER=https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0
OIDC_CLIENT_ID=rehearsal-only
OIDC_CLIENT_SECRET=$(rand)
PRIVACY_NOTICE_VERSION=0.2
LLM_MODE=fake
EMBEDDINGS_MODE=hash
S3_ENDPOINT=http://s3:9000
S3_ACCESS_KEY=rehearsal
S3_SECRET_KEY=$(rand)
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
EMAIL_MODE=smtp
SMTP_URL=smtp://mailpit:1025
GOLDEN_SEED=42
ENV
# SARVAM_API_KEY is a throwaway (BLD-A232): deploy.sh defaults SPEECH_MODE to sarvam (DEC-108, BLD-C115) and stops
# without a key in the database env file. Only the smoke check's "Sarvam key set" reads it; nothing calls Sarvam.
cat > "$WORK/db.env" <<ENV
POSTGRES_PASSWORD=$(rand)
DB_WEB_PASSWORD=$(rand)
DB_WORKER_PASSWORD=$(rand)
PSEUDONYM_VAULT_KEY=$(rand)
SARVAM_API_KEY=rehearsal-only-$(rand)
ENV
chmod 600 "$WORK"/*.env

cleanup() {
  status=$?
  if [[ "${KEEP:-0}" != "1" ]]; then
    echo; echo "== Tearing down the rehearsal"
    UAT_APP_ENV_FILE="$WORK/app.env" UAT_DATA_DIR="$WORK/data" docker compose -p "$PROJECT" \
      -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
      --env-file "$WORK/app.env" --env-file "$WORK/db.env" down -v --rmi local --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$WORK"
    echo "== Starting the dev stack again"
    make --no-print-directory up >/dev/null && echo "dev stack is up"
  fi
  exit $status
}
trap cleanup EXIT

echo "== Stopping the dev stack (data kept)"
make --no-print-directory down >/dev/null
UAT_PROJECT="$PROJECT" UAT_DATA_DIR="$WORK/data" scripts/uat/deploy.sh "$WORK/app.env" "$WORK/db.env"
[[ "$REHEARSE_APP_ENV" == "prod" ]] || exit 0

# Production mode (BLD-A235): the commands docs/UAT.md gives IT (steps 1b, 1c and 2b, in the running worker container),
# on synthetic people only (@kfintech.example). Nobody can sign in here, so 1a is left out: the import creates the row.
WORKER="$PROJECT-worker-1"
compose() {
  UAT_APP_ENV_FILE="$WORK/app.env" UAT_DATA_DIR="$WORK/data" docker compose -p "$PROJECT" \
    -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
    --env-file "$WORK/app.env" --env-file "$WORK/db.env" "$@"
}
stop() { printf 'STOPPED: %s\n' "$*" >&2; exit 1; }

printf '\n== Production mode (a): no person and no role after the install\n'
fresh="$(compose exec -T worker python -m bootstrap.smoke --web-url http://web:3000 --fresh)" \
  || { printf '%s\n' "$fresh"; stop "the fresh smoke failed in production mode"; }
grep -F "no people or roles yet (production)" <<<"$fresh" || stop "the fresh smoke has no production people line"

printf '\n== Production mode (b): a synthetic HR file of 20 people, imported through stdin\n'
# The seed's own generator (eval/golden/generators.py), written to the rehearsal folder as HR's file is kept: mode 600.
(umask 077 && compose run --rm -T -v "$ROOT/eval/golden:/app/eval/golden:ro" worker \
  python -m bootstrap.synthetic_hr --count 20 >"$WORK/hr-synthetic.csv")
docker exec -i "$WORKER" python -m identity.hr_import - <"$WORK/hr-synthetic.csv"

printf '\n== Production mode (c): one imported person gets admin\n'
docker exec "$WORKER" python -m identity.grants grant --employee-id SYN-00001 --role admin \
  --reason "Rehearsal: first admin from the synthetic HR file" --actor ops:rehearsal

printf '\n== Production mode (d): smoke checks without --fresh\n'
docker exec "$WORKER" python -m bootstrap.smoke --web-url http://web:3000
printf '\nProduction-mode rehearsal passed.\n'
