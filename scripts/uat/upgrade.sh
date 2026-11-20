#!/usr/bin/env bash
# Update a running install to this checkout (BLD-A234, the product lead's order of 20 Nov, 01:05). Run it from a
# clean checkout of the NEW tag, with the env files the install uses:
#
#   [FROM=<installed tag or sha>] scripts/uat/upgrade.sh <app env file> <database env file>
#
# FROM is read from $UAT_DATA_DIR/ops/installed.json; an install without one (launch-2026-11-20-r3) needs FROM.
# Steps: checks → keep the running images for rollback → build the new images and run preflight on them (the old
# containers keep serving) → fresh backup of the database and company repo, or stop → dbmate up → restart web and
# worker on the new images (Postgres keeps running) → the 13 smoke checks → record. Stops at the first failure.
# Nothing is changed before the backup is taken and checked. After it, a failure prints the rollback command and
# stops; it never rolls back by itself. It never changes a kill switch.
# Optional, as for deploy.sh: UAT_DATA_DIR (default ./.data-uat), UAT_WEB_PORT (3100), UAT_PROJECT (kfin-ideas-uat).
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
APP_ENV_FILE="$(cd "$(dirname "${1:?app env file}")" && pwd)/$(basename "$1")"
DB_ENV_FILE="$(cd "$(dirname "${2:?database env file}")" && pwd)/$(basename "$2")"
export UAT_APP_ENV_FILE="$APP_ENV_FILE"
export UAT_DATA_DIR="${UAT_DATA_DIR:-$ROOT/.data-uat}"
PROJECT="${UAT_PROJECT:-kfin-ideas-uat}"
# shellcheck source=scripts/uat/lib.sh
. "$ROOT/scripts/uat/lib.sh"
[[ "$PROJECT" != "kfin-ideas" ]] || fail "UAT_PROJECT is kfin-ideas, the dev stack's project with the product lead's demo: never upgrade it"

compose() {
  docker compose -p "$PROJECT" -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
    --env-file "$APP_ENV_FILE" --env-file "$DB_ENV_FILE" "$@"
}
sql() { compose exec -T postgres psql -v ON_ERROR_STOP=1 -U ideas -d ideas -tAq -c "$1"; }

TS="$(date -u +%Y%m%dT%H%M%SZ)"
STARTED=$SECONDS
PHASE=checks
SERVICES="worker web"
FROM_SHORT=""
BASE=""
DUMP=""
LOCK=""

APPLIED=""
record_upgrade() {  # <smoke passed: true|false>: ops/upgrade-<ts>.json, written after the backup and again at the end
  local applied_json="" v
  for v in $APPLIED; do applied_json="${applied_json:+$applied_json, }\"$v\""; done
  printf '{"from": "%s", "to": "%s", "backup": "%s", "migrations_applied": [%s], "smoke_passed": %s, "seconds": %d}\n' \
    "$FROM_SHA" "$TO_SHA" "$DUMP" "$applied_json" "$1" "$(( SECONDS - STARTED ))" > "$UAT_DATA_DIR/ops/upgrade-$TS.json"
}
restore_tags() {  # the :latest tags back to the running images, so a later `up` cannot start a half-built version
  local svc
  for svc in $SERVICES; do
    docker image tag "$PROJECT-$svc:rollback-$FROM_SHORT" "$PROJECT-$svc:latest" || true
  done
}
on_exit() {
  local status=$?
  [[ -z "$LOCK" ]] || rmdir "$LOCK" 2>/dev/null || true
  [[ $status -eq 0 ]] && return 0
  case "$PHASE" in
    keep)
      [[ -n "$BASE" ]] && rm -rf "$BASE.from"
      ;;
    build|backup)
      restore_tags
      [[ -n "$BASE" ]] && rm -rf "$BASE.dump" "$BASE.repo.tar" "$BASE.from" "$UAT_DATA_DIR/ops/upgrade-$TS.json"
      printf '\nNothing was changed: the database was not touched and the running version still serves.\n' >&2
      ;;
    migrate|restart|smoke|record)
      printf '\nThe upgrade stopped after the backup. To go back to %s (anything written since the backup is lost):\n' \
        "$FROM_SHORT" >&2
      printf '  UAT_DATA_DIR=%s UAT_PROJECT=%s make uat-rollback BACKUP=%s APP_ENV_FILE=%s DB_ENV_FILE=%s\n' \
        "$UAT_DATA_DIR" "$PROJECT" "$DUMP" "$APP_ENV_FILE" "$DB_ENV_FILE" >&2
      ;;
  esac
}
trap on_exit EXIT

step "1/8 Checks: a clean checkout, the install, the env files, the AI mode, free disk"
[[ -z "$(git status --porcelain)" ]] || fail "this checkout has changes or untracked files (git status --porcelain): check out the new tag cleanly"
TO_SHA="$(git rev-parse HEAD)"
TO_TAG="$(git describe --tags --exact-match HEAD 2>/dev/null || true)"
INSTALLED="$UAT_DATA_DIR/ops/installed.json"
recorded=""
if [[ -f "$INSTALLED" ]]; then
  recorded="$(installed_sha "$INSTALLED")"
  [[ -n "$recorded" ]] || fail "$INSTALLED has no sha: pass FROM=<the installed tag or sha>"
fi
if [[ -n "${FROM:-}" ]]; then
  FROM_SHA="$(git rev-parse --verify --quiet "${FROM}^{commit}")" || fail "FROM=$FROM is not a commit in this checkout: git fetch --tags first"
  [[ -z "$recorded" || "$recorded" == "$FROM_SHA" ]] \
    || fail "FROM=$FROM is $FROM_SHA, but $INSTALLED says $recorded is installed"
elif [[ -n "$recorded" ]]; then
  FROM_SHA="$recorded"
  git cat-file -e "${FROM_SHA}^{commit}" 2>/dev/null || fail "the installed $FROM_SHA is not in this checkout: git fetch --tags first"
else
  fail "no install record at $INSTALLED: say what is installed (the tag git describe printed before you checked out the new one), for example FROM=launch-2026-11-20-r3"
fi
[[ "$FROM_SHA" != "$TO_SHA" ]] || fail "this checkout ($TO_SHA) is what is installed: nothing to upgrade"
FROM_SHORT="${FROM_SHA:0:8}"
printf 'FROM %s %s\nTO   %s %s\n' "$FROM_SHA" "$(git describe --tags --exact-match "$FROM_SHA" 2>/dev/null || true)" \
  "$TO_SHA" "$TO_TAG"

uat_env_checks "$(notice_version_of < apps/web/src/content/privacy-notice.ts 2>/dev/null || true)"
SERVICES="worker web${SPEECH_BUILD:+ $SPEECH_BUILD}"

if ! { mkdir -p "$UAT_DATA_DIR/ops" "$UAT_DATA_DIR/backups" 2>/dev/null && chmod 700 "$UAT_DATA_DIR/backups" 2>/dev/null \
  && [[ -w "$UAT_DATA_DIR/ops" && -w "$UAT_DATA_DIR/backups" ]]; }; then
  fail "cannot write $UAT_DATA_DIR/ops and $UAT_DATA_DIR/backups: run once  sudo install -d -m 700 -o $(id -un) $UAT_DATA_DIR/ops $UAT_DATA_DIR/backups"
fi
[[ -d "$UAT_DATA_DIR/kfin-ideas" ]] || fail "no company repo at $UAT_DATA_DIR/kfin-ideas: set UAT_DATA_DIR to the install's data folder"
# One upgrade or rollback at a time; the folder goes when this run ends, however it ends (short of kill -9).
mkdir "$UAT_DATA_DIR/ops/.lock" 2>/dev/null \
  || fail "another upgrade or rollback holds $UAT_DATA_DIR/ops/.lock: if none is running (one was cut off), remove that folder"
LOCK="$UAT_DATA_DIR/ops/.lock"
[[ -n "$(compose ps --status running -q postgres)" ]] \
  || fail "Postgres is not running in project $PROJECT: is UAT_PROJECT the install's project?"
[[ "$(sql "SELECT to_regclass('public.schema_migrations') IS NOT NULL")" == "t" ]] \
  || fail "the database ideas or its schema_migrations is missing. If a rollback was interrupted, run make uat-rollback again with the same BACKUP. Never run make uat-deploy over a live install"
# A database that an earlier, failed run already migrated is rolled back with that run's backup, never upgraded again:
# a new backup would hold the new schema, and its rollback would start the old images on it.
from_versions="$(git ls-tree --name-only "$FROM_SHA" db/migrations/ | sed -nE 's#^db/migrations/([0-9]+)_.*#\1#p')"
[[ -n "$from_versions" ]] || fail "could not list the migrations of $FROM_SHORT (git ls-tree)"
ahead="$(sql "SELECT version FROM schema_migrations ORDER BY version" | LC_ALL=C sort \
  | LC_ALL=C comm -23 - <(printf '%s\n' "$from_versions" | LC_ALL=C sort))" || fail "could not read schema_migrations"
if [[ -n "$ahead" ]]; then
  # The backup that run recorded (its upgrade-<ts>.json from FROM is written as soon as the backup is checked), else
  # the newest backup.
  hint=""
  rec="$(grep -l "\"from\": \"$FROM_SHA\"" "$UAT_DATA_DIR"/ops/upgrade-*.json 2>/dev/null | LC_ALL=C sort | tail -1 || true)"
  [[ -z "$rec" ]] || hint="$(sed -nE 's/.*"backup": "([^"]*)".*/\1/p' "$rec")"
  [[ -n "$hint" && -s "$hint" ]] || hint="$(ls -t "$UAT_DATA_DIR"/backups/*.dump 2>/dev/null | head -1 || true)"
  printf '\nRoll it back; do not run the upgrade again. Check it is the backup from before the failed upgrade, then run:\n' >&2
  printf '  UAT_DATA_DIR=%s UAT_PROJECT=%s make uat-rollback BACKUP=%s APP_ENV_FILE=%s DB_ENV_FILE=%s\n' \
    "$UAT_DATA_DIR" "$PROJECT" "${hint:-<the .dump from before the failed upgrade>}" "$APP_ENV_FILE" "$DB_ENV_FILE" >&2
  fail "an earlier upgrade already migrated this database ($(printf '%s ' $ahead)are not in $FROM_SHORT)"
fi
for svc in $SERVICES; do
  [[ -n "$(compose ps --status running -q "$svc")" ]] || fail "$svc is not running: an upgrade starts from a running install"
done

# The AI mode (UAT.md, "Never switch ai.all on while LLM_MODE=fake"). Read only; the upgrade never sets a switch.
ai_all="$(compose exec -T worker python -m core.killswitch list | awk '$1 == "ai.all" { print $2 }')" || true
[[ "$ai_all" == "on" || "$ai_all" == "off" ]] || fail "could not read the ai.all kill switch"
if compose run --rm --no-deps -T worker python -m bootstrap.preflight ai-route-ready >/dev/null 2>&1; then
  route="configured"
else
  route="not configured (LLM_MODE=fake: Mode B)"
fi
if [[ "$ai_all" == "on" && "$route" != "configured" ]]; then
  fail "ai.all is on but the app env file has no model route (LLM_MODE=fake): the fake route would answer people. Switch ai.all off on the Admin page with a reason, or set the route, then run this again"
fi
echo "ai.all $ai_all; model route $route"

db_bytes="$(sql "SELECT pg_database_size('ideas')")"
[[ "$db_bytes" =~ ^[0-9]+$ ]] || fail "could not read the database size"
repo_kb="$(du -sk "$UAT_DATA_DIR/kfin-ideas" 2>/dev/null | awk '{ print $1 }')" || true
free_kb="$(df -Pk "$UAT_DATA_DIR/backups" | awk 'NR == 2 { print $4 }')"
need_kb=$(( db_bytes / 1024 + ${repo_kb:-0} + 1048576 ))   # the database and repo uncompressed, plus 1 GB
[[ "$free_kb" =~ ^[0-9]+$ && $free_kb -ge $need_kb ]] \
  || fail "not enough free disk for the backup: ${free_kb:-?} KB free under $UAT_DATA_DIR/backups, $need_kb KB needed"
echo "free disk: $free_kb KB; the backup needs at most $need_kb KB"

PHASE=keep
step "2/8 Keep the running images for rollback (:rollback-$FROM_SHORT) and the $FROM_SHORT compose files"
while [[ -e "$UAT_DATA_DIR/backups/upgrade-$TS-$FROM_SHORT.from" ]]; do  # one backup name per second
  sleep 1
  TS="$(date -u +%Y%m%dT%H%M%SZ)"
done
BASE="$UAT_DATA_DIR/backups/upgrade-$TS-$FROM_SHORT"
DUMP="$BASE.dump"
for svc in $SERVICES; do
  if docker image inspect "$PROJECT-$svc:rollback-$FROM_SHORT" >/dev/null 2>&1; then
    # An earlier attempt from this same install kept them; the running container may already be the new one.
    echo "$PROJECT-$svc:rollback-$FROM_SHORT already kept by an earlier attempt: left as it is"
    continue
  fi
  image_id="$(docker inspect --format '{{.Image}}' "$(compose ps -q "$svc")")"
  docker image tag "$image_id" "$PROJECT-$svc:rollback-$FROM_SHORT"
  echo "$PROJECT-$svc:rollback-$FROM_SHORT"
done
mkdir "$BASE.from"
git show "$FROM_SHA:infra/docker-compose.yml" > "$BASE.from/docker-compose.yml"
git show "$FROM_SHA:infra/uat/compose.uat.yml" > "$BASE.from/compose.uat.yml"
{
  printf 'FROM_SHA=%s\n' "$FROM_SHA"
  printf 'FROM_TAG=%s\n' "$(git describe --tags --exact-match "$FROM_SHA" 2>/dev/null || true)"
  printf 'FROM_NOTICE=%s\n' "$(git show "$FROM_SHA:apps/web/src/content/privacy-notice.ts" | notice_version_of)"
} > "$BASE.from/from.env"
echo "saved: $BASE.from/"

PHASE=build
step "3/8 Build the new images (the running containers keep serving) and run preflight on them"
compose build --quiet $SERVICES
compose run --rm --no-deps -T worker python -m bootstrap.preflight || fail "preflight on the new worker image"

PHASE=backup
step "4/8 Fresh backup of the database and the company repo, checked (it holds personal data: it stays on this server)"
compose exec -T postgres pg_dump -U ideas -d ideas -Fc > "$DUMP" || fail "pg_dump: no backup, so nothing was changed"
chmod 600 "$DUMP"
[[ -s "$DUMP" ]] || fail "the database backup is empty"
toc="$(compose exec -T postgres pg_restore --list < "$DUMP")" || fail "pg_restore --list cannot read the backup"
tables="$(grep -c ' TABLE DATA ' <<< "$toc" || true)"
[[ "$tables" -gt 0 ]] || fail "the database backup has no table data"
compose exec -T worker tar -C /data -cf - kfin-ideas > "$BASE.repo.tar" || fail "the company repo archive failed"
chmod 600 "$BASE.repo.tar"
tar -tf "$BASE.repo.tar" > /dev/null || fail "the company repo archive cannot be read"
sql "SELECT version FROM schema_migrations ORDER BY version" > "$BASE.from/migrations.txt"
echo "backup: $DUMP ($tables tables with data) and $BASE.repo.tar"
record_upgrade false   # names this backup at once, so a later run can point a rollback at it

PHASE=migrate
step "5/8 Migrations: dbmate up, then nothing pending"
compose run --rm --no-deps -T dbmate up
status_out="$(compose run --rm --no-deps -T dbmate status)" || fail "dbmate status"
printf '%s\n' "$status_out"
grep -q "Pending: 0" <<< "$status_out" || fail "migrations pending"
APPLIED="$(sql "SELECT version FROM schema_migrations ORDER BY version" | LC_ALL=C comm -13 "$BASE.from/migrations.txt" -)"
echo "migrations applied now: $(printf '%s' "$APPLIED" | grep -c . || true)"
[[ -z "$APPLIED" ]] || printf '  %s\n' $APPLIED

PHASE=restart
step "6/8 Restart $SERVICES on the new images (Postgres keeps running)"
compose up -d --wait --wait-timeout 240 --no-deps --no-build $SERVICES

PHASE=smoke
step "7/8 Smoke tests (13 checks; real people and their roles are expected now)"
smoke_out="$(compose exec -T worker python -m bootstrap.smoke --web-url http://web:3000)" || { printf '%s\n' "$smoke_out"; fail "smoke tests"; }
printf '%s\n' "$smoke_out"
grep -qx 'smoke: all checks passed' <<< "$smoke_out" || fail "smoke tests"

PHASE=record
step "8/8 Record the upgrade"
write_installed "$TO_SHA" "$TO_TAG" "$INSTALLED"
record_upgrade true
echo "recorded: $INSTALLED and $UAT_DATA_DIR/ops/upgrade-$TS.json"
printf '\nupgrade: %s -> %s done in %ss. Backup kept at %s\n' "$FROM_SHORT" "${TO_SHA:0:8}" "$(( SECONDS - STARTED ))" "$DUMP"
