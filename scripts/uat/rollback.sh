#!/usr/bin/env bash
# Put an install back to the backup an upgrade took (BLD-A234). Run it from the checkout of the NEW tag, with the
# env files the install uses:
#
#   scripts/uat/rollback.sh <backup .dump> <app env file> <database env file>
#
# Uses what upgrade.sh saved beside the dump: <name>.repo.tar (the company repo), <name>.from/ (the old version's
# compose files, its sha and privacy notice version, its migration list), and the :rollback-<sha> images.
# Steps: checks → stop web and worker → the old images back as current → drop and recreate the database `ideas`,
# then restore the dump → the company repo back from its archive (always) → start web and worker on the old compose
# files → the 13 smoke checks → record. Anything written after the backup is lost. Never changes a kill switch.
# Optional, as for deploy.sh: UAT_DATA_DIR (default ./.data-uat), UAT_WEB_PORT (3100), UAT_PROJECT (kfin-ideas-uat).
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
DUMP="$(cd "$(dirname "${1:?backup .dump}")" && pwd)/$(basename "$1")"
APP_ENV_FILE="$(cd "$(dirname "${2:?app env file}")" && pwd)/$(basename "$2")"
DB_ENV_FILE="$(cd "$(dirname "${3:?database env file}")" && pwd)/$(basename "$3")"
export UAT_APP_ENV_FILE="$APP_ENV_FILE"
export UAT_DATA_DIR="${UAT_DATA_DIR:-$ROOT/.data-uat}"
PROJECT="${UAT_PROJECT:-kfin-ideas-uat}"
# shellcheck source=scripts/uat/lib.sh
. "$ROOT/scripts/uat/lib.sh"

BASE="${DUMP%.dump}"
FROMDIR="$BASE.from"
# Every compose call uses the OLD version's compose files, saved by the upgrade, from this checkout's folder.
compose() {
  docker compose -p "$PROJECT" -f "$FROMDIR/docker-compose.yml" -f "$FROMDIR/compose.uat.yml" --project-directory . \
    --env-file "$APP_ENV_FILE" --env-file "$DB_ENV_FILE" "$@"
}
sql() {  # <database> <statement>
  compose exec -T postgres psql -v ON_ERROR_STOP=1 -U ideas -d "$1" -tAq -c "$2"
}
TS="$(date -u +%Y%m%dT%H%M%SZ)"
STARTED=$SECONDS
PHASE=checks
on_exit() {
  local status=$?
  [[ $status -eq 0 || "$PHASE" == "checks" ]] && return 0
  printf '\nThe rollback stopped. The backup is untouched at %s: fix what stopped it and run the rollback again.\n' \
    "$DUMP" >&2
}
trap on_exit EXIT

step "1/8 Checks: the backup, its saved files, the env files, the kept images"
[[ "$DUMP" == *.dump && -s "$DUMP" ]] || fail "BACKUP must be a .dump file that make uat-upgrade wrote under $UAT_DATA_DIR/backups"
for f in "$BASE.repo.tar" "$FROMDIR/docker-compose.yml" "$FROMDIR/compose.uat.yml" "$FROMDIR/from.env" \
  "$FROMDIR/migrations.txt"; do
  [[ -s "$f" ]] || fail "the backup's saved file $f is missing"
done
FROM_SHA="$(value FROM_SHA "$FROMDIR/from.env")"
FROM_TAG="$(value FROM_TAG "$FROMDIR/from.env")"
[[ "$FROM_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "$FROMDIR/from.env has no sha"
FROM_SHORT="${FROM_SHA:0:8}"
echo "back to $FROM_SHA $FROM_TAG, from $DUMP"
# The old build's privacy notice: the app env file must name its version again if the upgrade changed it.
uat_env_checks "$(value FROM_NOTICE "$FROMDIR/from.env")"
SERVICES="worker web${SPEECH_BUILD:+ $SPEECH_BUILD}"
for svc in $SERVICES; do
  docker image inspect "$PROJECT-$svc:rollback-$FROM_SHORT" > /dev/null 2>&1 \
    || fail "no kept image $PROJECT-$svc:rollback-$FROM_SHORT"
done
[[ -n "$(compose ps --status running -q postgres)" ]] \
  || fail "Postgres is not running in project $PROJECT: is UAT_PROJECT the install's project?"

PHASE=stop
step "2/8 Stop $SERVICES (Postgres keeps running)"
compose stop $SERVICES

step "3/8 The kept $FROM_SHORT images back as current"
for svc in $SERVICES; do
  docker image tag "$PROJECT-$svc:rollback-$FROM_SHORT" "$PROJECT-$svc:latest"
  echo "$PROJECT-$svc:latest is $FROM_SHORT again"
done

step "4/8 Database: drop and recreate ideas, then restore the backup"
# Not pg_restore --clean: it would leave behind the tables a newer migration added.
sql postgres "DROP DATABASE IF EXISTS ideas WITH (FORCE)"
sql postgres "CREATE DATABASE ideas"
compose exec -T postgres pg_restore -U ideas -d ideas --exit-on-error < "$DUMP"
sql ideas "SELECT version FROM schema_migrations ORDER BY version" | cmp -s - "$FROMDIR/migrations.txt" \
  || fail "the restored database's migrations differ from the backup's list"
echo "database restored: migrations as at the backup ($(grep -c . "$FROMDIR/migrations.txt"))"

step "5/8 Company repo: back from its archive (always restored)"
compose run --rm --no-deps -T worker sh -c 'rm -rf /data/kfin-ideas && tar -C /data -xf -' < "$BASE.repo.tar"
echo "company repo restored"

step "6/8 Start $SERVICES on the $FROM_SHORT images and compose files"
compose up -d --wait --wait-timeout 240 --no-deps --no-build $SERVICES

step "7/8 Smoke tests (13 checks; real people and their roles are expected)"
smoke_out="$(compose exec -T worker python -m bootstrap.smoke --web-url http://web:3000)" || { printf '%s\n' "$smoke_out"; fail "smoke tests"; }
printf '%s\n' "$smoke_out"
grep -qx 'smoke: all checks passed' <<< "$smoke_out" || fail "smoke tests"

step "8/8 Record the rollback"
mkdir -p "$UAT_DATA_DIR/ops"
write_installed "$FROM_SHA" "$FROM_TAG" "$UAT_DATA_DIR/ops/installed.json"
printf '{"to": "%s", "backup": "%s", "smoke_passed": true, "seconds": %d}\n' \
  "$FROM_SHA" "$DUMP" "$(( SECONDS - STARTED ))" > "$UAT_DATA_DIR/ops/rollback-$TS.json"
echo "recorded: $UAT_DATA_DIR/ops/installed.json and $UAT_DATA_DIR/ops/rollback-$TS.json"
printf '\nrollback: back on %s in %ss. Anything written after the backup is lost.\n' "$FROM_SHORT" "$(( SECONDS - STARTED ))"
