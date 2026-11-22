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
# Files (BLD-A239, prod only, when this checkout has lane C's start sweep): phase files-from plants three synthetic
# files on FROM through FROM's own code (scripts/uat/rehearse_files.py), and a check follows each later phase
# (files-upgrade, files-rollback, files-again). A checkout without the sweep gets the row "files-from SKIPPED".
# The last line (BLD-A240) is the pass line only when every expected phase has its row and each reads PASS. TERM or
# INT stops the run this script started (and what it started), prints STOPPED and still tears everything down.
#
# It never starts or stops the dev stack: stop it first from the main checkout (`make down`), and start it again
# from there afterwards (`make up`). It refuses while the dev stack runs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/uat/lib.sh
. "$ROOT/scripts/uat/lib.sh"   # fail, has_start_sweep, rehearsal_verdict
WORK="${UPGRADE_REHEARSAL_WORK:-$ROOT/.data-uat-upgrade-rehearsal}"   # the tests point it at a temporary folder
PROJECT=kfin-ideas-uat-rehearsal
DEV_PROJECT=kfin-ideas
REHEARSE_APP_ENV="${REHEARSE_APP_ENV:-uat}"
running() { docker ps -q --filter "label=com.docker.compose.project=$1"; }

[[ "$PROJECT" != "$DEV_PROJECT" ]] || fail "the rehearsal never uses the dev stack's project"
[[ "$REHEARSE_APP_ENV" == "uat" || "$REHEARSE_APP_ENV" == "prod" ]] \
  || fail "REHEARSE_APP_ENV must be uat (the default) or prod, not $REHEARSE_APP_ENV"
[[ -n "${FROM:-}" ]] || fail "say which version to install first: FROM=<tag or sha>, for example FROM=launch-2026-11-20-r3"
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

# BLD-A239: the file phases run in production mode only, and only when this checkout (TO) has the start sweep.
FILES=0
if [[ "$REHEARSE_APP_ENV" == "prod" ]] && has_start_sweep "$TO_SHA"; then
  FILES=1
fi
# What a pass needs (BLD-A240): one row for each of these phases, in this mode, each PASS. files-from may be SKIPPED
# only when TO has no start sweep.
if [[ "$REHEARSE_APP_ENV" == "uat" ]]; then
  EXPECTED="install-from upgrade rollback upgrade-again"
  SKIPPABLE=""
elif [[ $FILES -eq 1 ]]; then
  EXPECTED="install-from people-prod files-from upgrade files-upgrade rollback files-rollback upgrade-again files-again"
  SKIPPABLE=""
else
  EXPECTED="install-from people-prod files-from upgrade rollback upgrade-again"
  SKIPPABLE="files-from"
fi
# The upgrade's "migrations applied now: N": the migration files TO has and FROM lacks, from the two trees.
migration_versions() { git ls-tree --name-only "$1" db/migrations/ | sed -nE 's#^db/migrations/([0-9]+)_.*#\1#p' | LC_ALL=C sort; }
NEW_MIGRATIONS="$(LC_ALL=C comm -13 <(migration_versions "$FROM_SHA") <(migration_versions "$TO_SHA") | grep -c . || true)"

SUMMARY=""     # the summary's rows, as printed
ROWS=""        # "<phase> <PASS|FAIL|SKIPPED|STOPPED>", one line per row, for the verdict
LAST_PHASE="setup"
RUNNING=""     # the phase running now
PHASE_T0=0
CHILD=""       # its process group: the run this script started (BLD-A240)
SIGNAL=""
add_row() {  # <phase> <status> <the rest of the line>
  SUMMARY="$SUMMARY$(printf '%-18s %-7s %s' "$1" "$2" "$3")"$'\n'
  ROWS="$ROWS$1 $2"$'\n'
}
run_phase() {  # <name> <command…>: its output to the screen and $WORK/<name>.log; a line for the summary
  local name="$1" rc=0 smoke="no smoke line"
  shift
  printf '\n######## %s\n' "$name"
  LAST_PHASE="$name" RUNNING="$name" PHASE_T0=$SECONDS
  # In its own process group (job control on for this one fork only), so a stop ends everything this run started and
  # nothing else; `wait` lets TERM and INT through at once, where a foreground pipeline would hold them to its end.
  set -m
  ( set +m; "$@" 2>&1 | tee "$WORK/$name.log" ) < /dev/null &
  CHILD=$!
  set +m
  wait "$CHILD" || rc=$?
  CHILD="" RUNNING=""
  grep -q '^smoke: all checks passed$' "$WORK/$name.log" && smoke="smoke: all checks passed"
  grep -q '^smoke: [0-9]* check(s) failed$' "$WORK/$name.log" && smoke="smoke: FAILED"
  add_row "$name" "$([[ $rc -eq 0 ]] && echo PASS || echo FAIL)" "$(printf '%-26s %ss' "$smoke" "$(( SECONDS - PHASE_T0 ))")"
  return $rc
}
skip_phase() {  # <name> <why>
  printf '\n######## %s\nSKIPPED: %s\n' "$1" "$2"
  LAST_PHASE="$1"
  add_row "$1" SKIPPED "$2"
}

stop_children() {  # BLD-A240: the run this script started and what that run started (its process group), never more
  local pgid="$CHILD" n=0
  [[ -n "$pgid" ]] || return 0
  CHILD=""
  if kill -0 "$pgid" 2>/dev/null; then   # still this script's child (or not yet reaped): the group is still its own
    echo "stopping the $RUNNING run this rehearsal started (process group $pgid)"
    kill -TERM -- "-$pgid" 2>/dev/null
  fi
  wait "$pgid" 2>/dev/null
  while kill -0 -- "-$pgid" 2>/dev/null && [[ $n -lt 20 ]]; do
    sleep 0.5
    n=$(( n + 1 ))
  done
  if kill -0 -- "-$pgid" 2>/dev/null; then
    kill -KILL -- "-$pgid" 2>/dev/null
  fi
}

cleanup() {
  local status=$?
  set +e   # the teardown always runs to its end, whatever fails in it
  trap 'echo "(the teardown carries on to its end)" >&2' TERM INT
  stop_children
  if [[ -n "$RUNNING" ]]; then
    add_row "$RUNNING" "$([[ -n "$SIGNAL" ]] && echo STOPPED || echo FAIL)" \
      "$(printf '%-26s %ss' "${SIGNAL:+stopped by $SIGNAL}" "$(( SECONDS - PHASE_T0 ))")"
    RUNNING=""
  fi
  printf '\n== Summary (upgrade rehearsal, APP_ENV=%s)\nFROM %s (%s)\nTO   %s\n' "$REHEARSE_APP_ENV" "$FROM_SHA" "$FROM" "$TO_SHA"
  local rec
  rec="$(ls "$WORK"/data/ops/upgrade-*.json 2>/dev/null | head -1 || true)"
  if [[ -n "$rec" ]]; then
    printf 'migrations applied by the upgrade: %s\n' "$(sed -nE 's/.*"migrations_applied": \[([^]]*)\].*/\1/p' "$rec")"
  fi
  printf '%s' "$SUMMARY"
  rehearsal_verdict "$status" "$SIGNAL" "$LAST_PHASE" "$EXPECTED" "$ROWS" "$SKIPPABLE" || [[ $status -ne 0 ]] || status=1
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
    rm -rf "$WORK/data" "$WORK"/*.env "$WORK"/*.env.new "$WORK/hr-synthetic.csv" 2>/dev/null \
      || echo "could not remove all of $WORK/data (files of uid 10001?): remove it with sudo"
    if [[ -d "$WORK/from" ]]; then
      git worktree remove "$WORK/from" || echo "could not remove the worktree $WORK/from: remove it by hand (git worktree remove)"
    fi
    [[ -d "$WORK/from" ]] || rm -rf "$WORK" || true
  fi
  echo "start the dev stack again from the main checkout: make up"
  exit $status
}
on_signal() {  # <name> <exit status>: recorded for the verdict; the exit runs cleanup, once
  SIGNAL="$1"
  exit "$2"
}
trap cleanup EXIT
trap 'on_signal TERM 143' TERM
trap 'on_signal INT 130' INT

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

# ---- Files (BLD-A239): what the launch server holds while AI is off, and what each later phase leaves of it --------
# r3's file check waits on the gatekeeper while ai.all is off, counts each wait as a failed try, and after its last
# try ends the file "Didn't upload". Lane C's A2 (in TO) stops counting the waits and, at worker start, moves those
# files back to waiting. files-from plants, on FROM, D (dead by waits), W (waiting on its last try) and V (a real
# failure: infected) through FROM's own code; each check below reads them by ID (read-only, through Postgres), after
# the switch is read off. Nothing prints a file's text, its name or a person's name.
# A2's names, pinned here and not parsed: TO's check raises jobs.runner.JobWaits; the runner puts the job back
# (`queued`, the claim's +1 undone, last_error `waiting_gatekeeper`, run_at in 300 s); the file's checks get
# `waiting_for: gatekeeper`; the log events jobs.waiting and jobs.waits_reset are not read.
FILES_IDS="$WORK/files-ids.txt"
SOURCE_CHECKS="SELECT conname || ': ' || pg_get_constraintdef(oid) FROM pg_constraint WHERE conname IN ('hidden_details_source_check', 'idea_words_sealed_source_check') ORDER BY conname"
pg() { docker exec "$PROJECT-postgres-1" psql -v ON_ERROR_STOP=1 -U ideas -d ideas -tAq -c "$1"; }
ai_off() {  # read with the running build's own command, never set: it must be off before every check
  local v
  v="$(docker exec "$PROJECT-worker-1" python -m core.killswitch list | awk '$1 == "ai.all" { print $2 }')" || v=""
  if [[ "$v" != "off" ]]; then
    echo "STOPPED: ai.all is ${v:-unreadable}, not off (the rehearsal never sets a switch)"
    return 1
  fi
  echo "ai.all off"
}
file_id() {  # <D|W|V>: the file files-from planted
  local id
  id="$(sed -nE "s/^$1=(ATT-[0-9]{4}-[0-9]{6})$/\\1/p" "$FILES_IDS" 2>/dev/null | head -1)"
  [[ -n "$id" ]] || { echo "STOPPED: files-from named no file $1" >&2; return 1; }
  printf '%s' "$id"
}
describe() {  # <file id>: its state and its newest file.check job's, IDs and states only
  pg "SELECT 'file ' || id || ': ' || file_state || coalesce(', waiting for ' || (checks->>'waiting_for'), '') FROM attachments WHERE id = '$1'" || true
  pg "SELECT 'job ' || id || ': ' || state || ', ' || attempts || ' of ' || max_attempts || ' tries, ' || coalesce(last_error, 'no error') FROM jobs WHERE type = 'file.check' AND payload->>'attachment_id' = '$1' ORDER BY id DESC LIMIT 1" || true
}
holds() {  # <seconds to wait, 0 for once> <what> <SQL that prints t when it holds>
  local deadline=$(( SECONDS + $1 )) got
  while :; do
    got="$(pg "$3" 2>/dev/null || true)"
    if [[ "$got" == "t" ]]; then
      echo "ok: $2"
      return 0
    fi
    (( SECONDS < deadline )) || break
    sleep 3
  done
  if [[ $1 -gt 0 ]]; then
    echo "STOPPED: expected within $1 s: $2"
  else
    echo "STOPPED: expected: $2"
  fi
  return 1
}
job_of() {  # <file id>: the SQL condition for its file.check jobs
  printf "type = 'file.check' AND payload->>'attachment_id' = '%s'" "$1"
}

files_from() {  # on FROM, after people-prod
  local out
  ai_off || return 1
  out="$(docker exec -i "$PROJECT-worker-1" python - plant < "$ROOT/scripts/uat/rehearse_files.py")" \
    || { printf '%s\n' "$out"; echo "STOPPED: the three files were not planted on $FROM"; return 1; }
  printf '%s\n' "$out"
  printf '%s\n' "$out" | sed -nE 's/^files: ([DWV]) (ATT-[0-9]{4}-[0-9]{6}) on draft .*/\1=\2/p' > "$FILES_IDS"
  [[ "$(grep -c . "$FILES_IDS")" -eq 3 ]] || { echo "STOPPED: files-from did not name three files"; return 1; }
  pg "$SOURCE_CHECKS" > "$WORK/source-checks-from.txt" || { echo "STOPPED: could not read the source checks"; return 1; }
  if [[ "$(grep -c . "$WORK/source-checks-from.txt")" -ne 2 ]] || grep -q teamup "$WORK/source-checks-from.txt"; then
    echo "STOPPED: $FROM's hidden_details and idea_words_sealed source checks are not the two expected"
    return 1
  fi
  echo "kept: $FROM's hidden_details_source_check and idea_words_sealed_source_check (no teamup)"
}

files_after_upgrade() {  # <upgrade phase>: after upgrade and after upgrade-again
  local log="$WORK/$1.log" d w v t
  ai_off || return 1
  d="$(file_id D)" && w="$(file_id W)" && v="$(file_id V)" || return 1
  grep -qx "migrations applied now: $NEW_MIGRATIONS" "$log" \
    || { echo "STOPPED: $1 did not print \"migrations applied now: $NEW_MIGRATIONS\" (TO's migration files that FROM lacks)"; return 1; }
  echo "ok: migrations applied now: $NEW_MIGRATIONS (TO's migration files that FROM lacks)"
  # D only: r3's live waiters such as W are reset too, but not counted.
  if ! grep -qx 'file checks: 1 files back to waiting for the personal-data check (none opened)' "$log"; then
    echo "STOPPED: $1 did not print \"file checks: 1 files back to waiting …\"; it printed:"
    grep '^file checks: ' "$log" || echo "(no file checks line)"
    return 1
  fi
  echo "ok: file checks: 1 files back to waiting (D)"
  # D: the sweep's new job, claimed by TO's worker and put back to wait with the claim undone.
  holds 180 "D $d checking, waiting for the gatekeeper; its job queued at 0 tries, waiting_gatekeeper, due later" \
    "SELECT EXISTS (SELECT 1 FROM jobs WHERE $(job_of "$d") AND state = 'queued' AND attempts = 0 AND last_error = 'waiting_gatekeeper' AND run_at > now()) AND EXISTS (SELECT 1 FROM attachments WHERE id = '$d' AND file_state = 'checking' AND checks->>'waiting_for' = 'gatekeeper')" \
    || { describe "$d"; return 1; }
  describe "$d"
  holds 0 "V $v still infected" "SELECT EXISTS (SELECT 1 FROM attachments WHERE id = '$v' AND file_state = 'infected')" \
    || { describe "$v"; return 1; }
  holds 0 "W $w still checking, its job never dead" \
    "SELECT EXISTS (SELECT 1 FROM attachments WHERE id = '$w' AND file_state = 'checking') AND NOT EXISTS (SELECT 1 FROM jobs WHERE $(job_of "$w") AND state = 'dead')" \
    || { describe "$w"; return 1; }
  # W's try now: the rehearsal's one write on TO. Its attempts are not pinned (0 if the sweep reset it, or max - 1).
  t="$(pg "SELECT extract(epoch FROM now())" 2>/dev/null || true)"
  [[ "$t" =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "STOPPED: could not read the database's time"; return 1; }
  holds 30 "W $w: its job is due now" \
    "WITH due AS (UPDATE jobs SET run_at = now() WHERE $(job_of "$w") AND state = 'queued' RETURNING id) SELECT count(*) > 0 FROM due" \
    || { describe "$w"; return 1; }
  holds 180 "W $w claimed after that and back to waiting for the gatekeeper: queued, under its last try, never dead" \
    "SELECT EXISTS (SELECT 1 FROM jobs WHERE $(job_of "$w") AND locked_at >= to_timestamp($t) AND state = 'queued' AND attempts < max_attempts AND last_error = 'waiting_gatekeeper' AND run_at > now()) AND NOT EXISTS (SELECT 1 FROM jobs WHERE $(job_of "$w") AND state = 'dead') AND EXISTS (SELECT 1 FROM attachments WHERE id = '$w' AND file_state = 'checking' AND checks->>'waiting_for' = 'gatekeeper')" \
    || { describe "$w"; return 1; }
  describe "$w"
}

files_after_rollback() {  # the backup's states again, and FROM's source checks
  local d w v
  ai_off || return 1
  d="$(file_id D)" && w="$(file_id W)" && v="$(file_id V)" || return 1
  holds 0 "D $d upload_failed again (check_failed), as in the backup" \
    "SELECT EXISTS (SELECT 1 FROM attachments WHERE id = '$d' AND file_state = 'upload_failed' AND checks->>'result' = 'check_failed')" \
    || { describe "$d"; return 1; }
  holds 0 "V $v infected" "SELECT EXISTS (SELECT 1 FROM attachments WHERE id = '$v' AND file_state = 'infected')" \
    || { describe "$v"; return 1; }
  holds 0 "W $w checking" "SELECT EXISTS (SELECT 1 FROM attachments WHERE id = '$w' AND file_state = 'checking')" \
    || { describe "$w"; return 1; }
  pg "$SOURCE_CHECKS" > "$WORK/source-checks-rollback.txt" || { echo "STOPPED: could not read the source checks"; return 1; }
  if ! cmp -s "$WORK/source-checks-from.txt" "$WORK/source-checks-rollback.txt"; then
    echo "STOPPED: hidden_details_source_check or idea_words_sealed_source_check is not as on $FROM"
    return 1
  fi
  echo "ok: hidden_details_source_check and idea_words_sealed_source_check as on $FROM (no teamup)"
}

git worktree add --detach "$WORK/from" "$FROM_SHA"
export UAT_PROJECT="$PROJECT" UAT_DATA_DIR="$WORK/data"
run_phase install-from bash -c 'cd "$1" && bash scripts/uat/deploy.sh "$2" "$3"' _ "$WORK/from" "$WORK/app.env" "$WORK/db.env"
if [[ "$REHEARSE_APP_ENV" == "prod" ]]; then
  run_phase people-prod people_prod
  if [[ $FILES -eq 1 ]]; then
    run_phase files-from files_from
  else
    skip_phase files-from "TO has no start sweep"
  fi
fi
set_notice "$TO_NOTICE"
run_phase upgrade env FROM="$FROM_SHA" "$ROOT/scripts/uat/upgrade.sh" "$WORK/app.env" "$WORK/db.env"
[[ $FILES -eq 0 ]] || run_phase files-upgrade files_after_upgrade upgrade
BACKUP="$(ls -t "$WORK"/data/backups/*.dump | head -1)"
set_notice "$FROM_NOTICE"
run_phase rollback "$ROOT/scripts/uat/rollback.sh" "$BACKUP" "$WORK/app.env" "$WORK/db.env"
[[ $FILES -eq 0 ]] || run_phase files-rollback files_after_rollback
set_notice "$TO_NOTICE"
run_phase upgrade-again env FROM="$FROM_SHA" "$ROOT/scripts/uat/upgrade.sh" "$WORK/app.env" "$WORK/db.env"
[[ $FILES -eq 0 ]] || run_phase files-again files_after_upgrade upgrade-again
