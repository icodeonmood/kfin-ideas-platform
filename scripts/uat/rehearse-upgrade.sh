#!/usr/bin/env bash
# Rehearse the upgrade path on this machine (BLD-A234): install FROM with FROM's own deploy.sh, upgrade to this
# checkout, roll back to the backup, then upgrade again so it ends on this checkout. Throwaway secrets, a throwaway
# project (kfin-ideas-uat-rehearsal), everything torn down at the end, even on failure (KEEP=1 skips the teardown).
#
#   FROM=<tag or sha> scripts/uat/rehearse-upgrade.sh        # or: make uat-rehearsal-upgrade FROM=<ref>
#   REHEARSE_APP_ENV=prod FROM=launch-2026-11-20-r3 scripts/uat/rehearse-upgrade.sh
#
# REHEARSE_APP_ENV=prod (BLD-A237) rehearses the launch server: FROM is installed in production mode (no people), then
# the steps after the install in docs/UAT.md run on a SYNTHETIC HR file of 20 (import through stdin, the first admin,
# core_committee for one member, the smoke checks without --fresh) before the upgrade. The default stays uat.
#
# It never starts or stops the dev stack: stop it first from the main checkout (`make down`), and start it again
# from there afterwards (`make up`). It refuses while the dev stack runs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
WORK="${UPGRADE_REHEARSAL_WORK:-$ROOT/.data-uat-upgrade-rehearsal}"   # the tests point it at a temporary folder
PROJECT=kfin-ideas-uat-rehearsal
DEV_PROJECT=kfin-ideas
REHEARSE_APP_ENV="${REHEARSE_APP_ENV:-uat}"
fail() { printf 'STOPPED: %s\n' "$*" >&2; exit 1; }
running() { docker ps -q --filter "label=com.docker.compose.project=$1"; }

[[ "$PROJECT" != "$DEV_PROJECT" ]] || fail "the rehearsal never uses the dev stack's project"
[[ "$REHEARSE_APP_ENV" == "uat" || "$REHEARSE_APP_ENV" == "prod" ]] \
  || fail "REHEARSE_APP_ENV must be uat (the default) or prod, not $REHEARSE_APP_ENV"
[[ -n "${FROM:-}" ]] || fail "say which version to install first: FROM=<tag or sha>, for example FROM=launch-2026-11-20-r2"
if [[ -n "$(running "$DEV_PROJECT")" ]]; then
  echo "stop the dev stack first from the main checkout: make down"
  fail "the dev stack (compose project $DEV_PROJECT) is running"
fi
[[ -z "$(running "$PROJECT")" ]] || fail "compose project $PROJECT is running (an earlier KEEP=1 run?): tear it down first"
[[ -e "$WORK" ]] && fail "$WORK exists from an earlier run; remove it first"
[[ -z "$(git status --porcelain)" ]] || fail "this checkout has changes or untracked files (git status --porcelain): upgrade.sh refuses them"
FROM_SHA="$(git rev-parse --verify --quiet "${FROM}^{commit}")" || fail "FROM=$FROM is not a commit here: git fetch --tags first"
TO_SHA="$(git rev-parse HEAD)"
[[ "$FROM_SHA" != "$TO_SHA" ]] || fail "FROM is this checkout: nothing to upgrade"

SUMMARY=""
run_phase() {  # <name> <command…>: its output to the screen and $WORK/<name>.log; a line for the summary
  local name="$1" t0=$SECONDS rc=0 smoke="no smoke line"
  shift
  printf '\n######## %s\n' "$name"
  "$@" 2>&1 | tee "$WORK/$name.log" || rc=$?
  grep -q '^smoke: all checks passed$' "$WORK/$name.log" && smoke="smoke: all checks passed"
  grep -q '^smoke: [0-9]* check(s) failed$' "$WORK/$name.log" && smoke="smoke: FAILED"
  SUMMARY="$SUMMARY$(printf '%-18s %-7s %-26s %ss' "$name" "$([[ $rc -eq 0 ]] && echo PASS || echo FAIL)" "$smoke" \
    "$(( SECONDS - t0 ))")"$'\n'
  return $rc
}

cleanup() {
  local status=$?
  set +e   # the teardown always runs to its end, whatever fails in it
  printf '\n== Summary (upgrade rehearsal, APP_ENV=%s)\nFROM %s (%s)\nTO   %s\n' "$REHEARSE_APP_ENV" "$FROM_SHA" "$FROM" "$TO_SHA"
  local rec
  rec="$(ls "$WORK"/data/ops/upgrade-*.json 2>/dev/null | head -1 || true)"
  if [[ -n "$rec" ]]; then
    printf 'migrations applied by the upgrade: %s\n' "$(sed -nE 's/.*"migrations_applied": \[([^]]*)\].*/\1/p' "$rec")"
  fi
  printf '%s' "$SUMMARY"
  [[ $status -eq 0 ]] && echo "rehearsal: upgrade, rollback and upgrade again all passed" || echo "rehearsal: FAILED (exit $status)"
  if [[ "${KEEP:-0}" == "1" ]]; then
    echo "KEEP=1: project $PROJECT is left running with its data in $WORK; tear it down by hand when done"
  else
    echo; echo "== Tearing down the rehearsal"
    if [[ -f "$WORK/app.env" && -f "$WORK/db.env" ]]; then   # without them nothing was started
      UAT_APP_ENV_FILE="$WORK/app.env" UAT_DATA_DIR="$WORK/data" docker compose -p "$PROJECT" \
        -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
        --env-file "$WORK/app.env" --env-file "$WORK/db.env" down -v --rmi local --remove-orphans >/dev/null 2>&1 || true
    fi
    docker image ls --filter "reference=$PROJECT-*:rollback-*" --format '{{.Repository}}:{{.Tag}}' 2>/dev/null \
      | while read -r img; do docker image rm "$img" >/dev/null 2>&1 || true; done || true
    rm -rf "$WORK/data" "$WORK"/*.env "$WORK"/*.env.new 2>/dev/null \
      || echo "could not remove all of $WORK/data (files of uid 10001?): remove it with sudo"
    if [[ -d "$WORK/from" ]]; then
      git worktree remove "$WORK/from" || echo "could not remove the worktree $WORK/from: remove it by hand (git worktree remove)"
    fi
    [[ -d "$WORK/from" ]] || rm -rf "$WORK" || true
  fi
  echo "start the dev stack again from the main checkout: make up"
  exit $status
}
trap cleanup EXIT

mkdir -p "$WORK/data"
rand() { openssl rand -hex 24; }
notice_of() { git show "$1:apps/web/src/content/privacy-notice.ts" | sed -nE 's/^[[:space:]]*version: "([^"]*)",[[:space:]]*$/\1/p'; }
FROM_NOTICE="$(notice_of "$FROM_SHA")"
TO_NOTICE="$(notice_of "$TO_SHA")"
# As rehearse.sh: synthetic and random, LLM_MODE=fake, a throwaway Sarvam key in the database env file only.
cat > "$WORK/app.env" <<ENV
APP_ENV=$REHEARSE_APP_ENV
APP_BASE_URL=http://localhost:${UAT_WEB_PORT:-3100}
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
PRIVACY_NOTICE_VERSION=$FROM_NOTICE
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
SARVAM_API_KEY=rehearsal-only-$(rand)
ENV
chmod 600 "$WORK"/*.env
# What IT does by hand before each run: the app env file names the privacy notice version of the build it starts.
set_notice() {
  sed -E "s/^PRIVACY_NOTICE_VERSION=.*/PRIVACY_NOTICE_VERSION=$1/" "$WORK/app.env" > "$WORK/app.env.new"
  mv "$WORK/app.env.new" "$WORK/app.env"
  chmod 600 "$WORK/app.env"
}

# Production mode (BLD-A237): what IT does on the launch server after the install and before its first upgrade
# (docs/UAT.md After the deploy, 1b, 1c, 2 and 2b), in FROM's running worker, on synthetic people only
# (@kfintech.example). Nobody can sign in here, so 1a and 1d are left out (the import creates the rows), and Ones
# Committee, which only the Admin page gives, is not rehearsed. Each step stops the phase if it fails.
people_prod() {
  local worker="$PROJECT-worker-1"
  (cd "$WORK/from" && umask 077 && UAT_APP_ENV_FILE="$WORK/app.env" UAT_DATA_DIR="$WORK/data" docker compose \
    -p "$PROJECT" -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
    --env-file "$WORK/app.env" --env-file "$WORK/db.env" \
    run --rm -T -v "$WORK/from/eval/golden:/app/eval/golden:ro" worker python -m bootstrap.synthetic_hr --count 20 \
    > "$WORK/hr-synthetic.csv") || { echo "STOPPED: the synthetic HR file was not written"; return 1; }
  [[ -s "$WORK/hr-synthetic.csv" ]] || { echo "STOPPED: the synthetic HR file is empty"; return 1; }
  docker exec -i "$worker" python -m identity.hr_import - < "$WORK/hr-synthetic.csv" \
    || { echo "STOPPED: the HR import"; return 1; }
  docker exec "$worker" python -m identity.grants grant --employee-id SYN-00001 --role admin \
    --reason "Rehearsal: first admin from the synthetic HR file" --actor ops:rehearsal \
    || { echo "STOPPED: the admin grant"; return 1; }
  docker exec "$worker" python -m identity.grants grant --employee-id SYN-00002 --role core_committee \
    --reason "Rehearsal: a Ones Committee member at launch (DEC-121)" --actor ops:rehearsal \
    || { echo "STOPPED: the core_committee grant"; return 1; }
  docker exec "$worker" python -m bootstrap.smoke --web-url http://web:3000
}

git worktree add --detach "$WORK/from" "$FROM_SHA"
export UAT_PROJECT="$PROJECT" UAT_DATA_DIR="$WORK/data"
run_phase install-from bash -c 'cd "$1" && bash scripts/uat/deploy.sh "$2" "$3"' _ "$WORK/from" "$WORK/app.env" "$WORK/db.env"
[[ "$REHEARSE_APP_ENV" != "prod" ]] || run_phase people-prod people_prod
set_notice "$TO_NOTICE"
run_phase upgrade env FROM="$FROM_SHA" "$ROOT/scripts/uat/upgrade.sh" "$WORK/app.env" "$WORK/db.env"
BACKUP="$(ls -t "$WORK"/data/backups/*.dump | head -1)"
set_notice "$FROM_NOTICE"
run_phase rollback "$ROOT/scripts/uat/rollback.sh" "$BACKUP" "$WORK/app.env" "$WORK/db.env"
set_notice "$TO_NOTICE"
run_phase upgrade-again env FROM="$FROM_SHA" "$ROOT/scripts/uat/upgrade.sh" "$WORK/app.env" "$WORK/db.env"
