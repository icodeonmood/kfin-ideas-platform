#!/usr/bin/env bash
# Rehearse the UAT deploy on this machine (AT-B7-06): a UAT-shaped stack from an empty database, with throwaway
# secrets, then torn down. The dev stack is stopped while it runs (its data is kept) and started again after.
# The real UAT host needs KFin's Entra app, vault secrets and services (§9.1); see docs/UAT.md.
#
#   scripts/uat/rehearse.sh            # KEEP=1 leaves the rehearsal stack running for a look
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
WORK="$ROOT/.data-uat-rehearsal"
PROJECT=kfin-ideas-uat-rehearsal
[[ -e "$WORK" ]] && { echo "$WORK exists from an earlier run; remove it first"; exit 1; }
mkdir -p "$WORK/data"
rand() { openssl rand -hex 24; }

cat > "$WORK/app.env" <<ENV
APP_ENV=uat
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
PRIVACY_NOTICE_VERSION=0.2-draft
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
cat > "$WORK/db.env" <<ENV
POSTGRES_PASSWORD=$(rand)
DB_WEB_PASSWORD=$(rand)
DB_WORKER_PASSWORD=$(rand)
PSEUDONYM_VAULT_KEY=$(rand)
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
