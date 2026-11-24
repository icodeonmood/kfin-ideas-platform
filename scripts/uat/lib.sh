# shellcheck shell=bash
# shellcheck disable=SC2034,SC2154
# Shared by scripts/uat/upgrade.sh and scripts/uat/rollback.sh (BLD-A234), and by scripts/uat/rehearse-upgrade.sh
# for its verdict, the start-sweep check and the file-waits check (BLD-A239, BLD-A240, BLD-A250). Sourced, never run
# on its own.
# The caller sets APP_ENV_FILE and DB_ENV_FILE (absolute paths) first and reads SPEECH_BUILD after uat_env_checks
# (hence SC2154 and SC2034 off). Bash 3.2 or later: macOS runs the rehearsal.

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'STOPPED: %s\n' "$*" >&2; exit 1; }
# One value from an env file, without running the file as shell code.
value() { { grep -E "^$1=" "$2" || true; } | tail -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^"(.*)"$/\1/'; }
# The privacy notice's version from privacy-notice.ts on stdin; more than one match, or none, is not a version.
notice_version_of() { sed -nE 's/^[[:space:]]*version: "([^"]*)",[[:space:]]*$/\1/p'; }
# The time now in UTC, for the records.
utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# A copy of deploy.sh's step 1 checks (from its line 38 to its build line). deploy.sh stays as it was installed at
# launch, so the two are kept in step by hand; tests/test_a234_uat_upgrade.py fails if a stop message of deploy.sh
# is missing here. $1 is the privacy notice version of the build being started: the checkout's own on an upgrade,
# the one saved with the backup on a rollback. Sets SPEECH_BUILD ("speech" when the speech service is used) and
# exports what deploy.sh exports. Prints no value that could be a secret.
uat_env_checks() {
  local notice_text="$1" notice_env v speech_url speech_mode approval
  local notice_re='^[0-9]+(\.[0-9]+)*(-draft)?$'
  notice_env="$(value PRIVACY_NOTICE_VERSION "$APP_ENV_FILE")"
  if [[ -z "$notice_text" || "$notice_env" != "$notice_text" ]]; then
    if [[ "$notice_env" =~ $notice_re && "$notice_text" =~ $notice_re ]]; then
      fail "PRIVACY_NOTICE_VERSION in the app env file is $notice_env, but this build's privacy notice is $notice_text: set it to $notice_text"
    fi
    fail "PRIVACY_NOTICE_VERSION in the app env file must equal the version in apps/web/src/content/privacy-notice.ts"
  fi
  for name in POSTGRES_PASSWORD DB_WEB_PASSWORD DB_WORKER_PASSWORD; do
    v="$(value "$name" "$DB_ENV_FILE")"
    [[ ${#v} -ge 20 && "$v" =~ ^[A-Za-z0-9]+$ ]] || fail "$name must be 20 or more random letters and digits"
  done
  v="$(value PSEUDONYM_VAULT_KEY "$DB_ENV_FILE")"
  [[ ${#v} -ge 32 && "$v" =~ ^[A-Za-z0-9]+$ ]] || fail "PSEUDONYM_VAULT_KEY must be 32 or more random letters and digits"
  [[ -z "$(value PSEUDONYM_VAULT_KEY "$APP_ENV_FILE")" ]] \
    || fail "PSEUDONYM_VAULT_KEY belongs in the database env file only: the app env file also reaches the web app"
  SPEECH_BUILD=""
  speech_url="$(value SPEECH_ENGINE_URL "$APP_ENV_FILE")"
  if [[ -n "$speech_url" ]]; then
    [[ "$speech_url" =~ ^http://speech(:[0-9]+)?/?$ ]] || fail "SPEECH_ENGINE_URL must be http://speech:8300 (the isolated speech service)"
    v="$(value SPEECH_SERVICE_TOKEN "$DB_ENV_FILE")"
    [[ ${#v} -ge 32 && "$v" =~ ^[A-Za-z0-9]+$ ]] || fail "SPEECH_SERVICE_TOKEN must be 32 or more random letters and digits, in the database env file"
    [[ "$v" != "$(value INTERNAL_API_TOKEN "$APP_ENV_FILE")" ]] || fail "SPEECH_SERVICE_TOKEN must differ from INTERNAL_API_TOKEN"
    [[ -n "$(value SPEECH_MODEL_DIR "$DB_ENV_FILE")$(value SPEECH_MODEL_DIR "$APP_ENV_FILE")" ]] || fail "set SPEECH_MODEL_DIR to the speech model folder on the host"
    export COMPOSE_PROFILES=speech
    SPEECH_BUILD="speech"
  fi
  [[ -z "$(value SPEECH_SERVICE_TOKEN "$APP_ENV_FILE")" ]] \
    || fail "SPEECH_SERVICE_TOKEN belongs in the database env file only: the app env file also reaches the web app"
  [[ -z "$(value SARVAM_API_KEY "$APP_ENV_FILE")" ]] \
    || fail "SARVAM_API_KEY belongs in the database env file only: the app env file also reaches the web app"
  speech_mode="$(value SPEECH_MODE "$APP_ENV_FILE")"
  export SPEECH_MODE="${speech_mode:-sarvam}"
  if [[ "$SPEECH_MODE" == "sarvam" ]]; then
    [[ -n "$(value SARVAM_API_KEY "$DB_ENV_FILE")" ]] || fail "SPEECH_MODE is sarvam: put SARVAM_API_KEY in the database env file"
    approval="$(value SPEECH_HOSTED_APPROVAL "$APP_ENV_FILE")"
    export SPEECH_HOSTED_APPROVAL="${approval:-DEC-108}"
    [[ -n "$SPEECH_HOSTED_APPROVAL" ]] || fail "SPEECH_MODE is sarvam: SPEECH_HOSTED_APPROVAL must be set (DEC-108)"
  fi
  [[ -z "$(value INTERNAL_API_TOKEN "$DB_ENV_FILE")" ]] \
    || fail "INTERNAL_API_TOKEN belongs in the app env file only: never next to SPEECH_SERVICE_TOKEN"
}

# installed.json: what this install runs, read by the next upgrade as the version it upgrades from.
write_installed() {  # <sha> <tag or ""> <file>
  printf '{"sha": "%s", "tag": "%s", "at": "%s"}\n' "$1" "$2" "$(utc_now)" > "$3"
}
installed_sha() {  # <file>: the sha, or nothing
  sed -nE 's/.*"sha": *"([0-9a-f]{40})".*/\1/p' "$1" | head -1
}

# BLD-A239: whether the tree at <sha> has lane C's start sweep (A2): its audit action in attachments/files.py. Read
# from git, so upgrade.sh and the rehearsal decide it alike, from the build being started (TO), never from FROM.
has_start_sweep() {  # <sha>
  local text
  text="$(git show "$1:services/worker/attachments/files.py" 2>/dev/null)" || return 1
  grep -qE "[\"']file\\.start_sweep[\"']" <<< "$text"
}

# BLD-A250: whether the tree at <sha> has lane C's file waits (BLD-C225, from launch-2026-11-20-r4 on): the class
# JobWaits in jobs/runner.py. The upgrade rehearsal reads it from FROM's tree to pick what its file phases expect. The
# class's name is pinned; nothing else in the file is read.
has_file_waits() {  # <sha>
  local text
  text="$(git show "$1:services/worker/jobs/runner.py" 2>/dev/null)" || return 1
  grep -qE '^class JobWaits[(:]' <<< "$text"
}

# BLD-A240: the upgrade rehearsal's last line, and whether it passed. A pass is earned only when the script ended with
# 0, no signal stopped it, and the summary has exactly one row for each expected phase and no other, each PASS
# (SKIPPED only for <skippable>). An empty summary is never a pass. Prints the line; returns 0 only on a pass.
rehearsal_verdict() {  # <status> <signal or ""> <last phase> <expected phases> <rows: "name status" lines> <skippable>
  local status="$1" signal="$2" last="$3" expected="$4" rows="$5" skippable="$6" name got ok=1 n=0
  if [[ -n "$signal" ]]; then
    echo "rehearsal: STOPPED ($signal) after $last"
    return 1
  fi
  for name in $expected; do
    n=$(( n + 1 ))
    got="$(printf '%s\n' "$rows" | awk -v n="$name" '$1 == n { print $2 }')"
    case "$got" in
      PASS) ;;
      SKIPPED) [[ -n "$skippable" && "$name" == "$skippable" ]] || ok=0 ;;
      *) ok=0 ;;   # no row, FAIL, STOPPED, or more than one row
    esac
  done
  [[ $n -gt 0 && "$(printf '%s\n' "$rows" | grep -c .)" -eq $n ]] || ok=0
  if [[ $status -eq 0 && $ok -eq 1 ]]; then
    echo "rehearsal: upgrade, rollback and upgrade again all passed"
    return 0
  fi
  echo "rehearsal: FAILED (exit $(( status == 0 ? 1 : status )))"
  return 1
}
