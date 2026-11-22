#!/usr/bin/env bash
# `make eval-live` (BLD-C229; V-EVAL, AT-B4-03, AT-B5-04): the golden sets for gatekeeper and judge on the REAL model
# route, on a throwaway database, with a pass/fail block to paste back. Never in CI.
#
# Two modes, one script (agreed with lane A; BLD-A245 documents server mode in docs/UAT.md):
#
#   The product lead's Mac, in his own terminal, the model key loaded there his own way (never on a command line):
#     make eval-live                       # route anthropic: ANTHROPIC_API_KEY
#     make eval-live ROUTE=bedrock         # AWS_REGION plus AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
#                                          # (and AWS_SESSION_TOKEN if yours has one), or AWS_BEARER_TOKEN_BEDROCK
#     make eval-live EVAL_LIVE_PYTHON=/path/to/services/worker/.venv/bin/python
#   Its own compose project kfin-eval-live with its own Postgres on 127.0.0.1:55447; the steps run with the checkout's
#   Python (EVAL_LIVE_PYTHON, as make sarvam-live does).
#
#   KFin IT on the launch server:
#     sudo scripts/eval/live.sh --server --checkout <release checkout> --project <install's compose project> \
#       --app-env <app env file> --route anthropic|bedrock [--data-dir <a folder that does not exist yet>]
#   Its own compose project kfin-ideas-eval with its own Postgres, unpublished, and throwaway containers from the
#   INSTALLED worker image (<project>-worker), on the eval project's own network only. From the app env file only the
#   route's credentials are passed, by name, through the process environment (never argv, never a file); everything
#   else the container gets is generated here. The install is only read: one `SELECT count(*) FROM llm_calls` through
#   its own Postgres container before and after, and the run FAILs if the count changed. The data folder (default
#   /srv/kfin-ideas-eval) holds the company repo copy and the reports, and goes at the end.
#
# Both modes: migrated with dbmate as CI does; the company repo seeded into a throwaway folder and the 200 synthetic
# people loaded (APP_ENV=test, so the dev overlay's synthetic client names are there for the golden sets); the switches
# ai.all, agent.gatekeeper and agent.judge set on in the throwaway database only (actor process:eval); then
# `python -m evalrunner --only gatekeeper,judge` with LLM_MODE=<route>, EMBEDDINGS_MODE=hash, SPEECH_MODE=fake and the
# reports in a throwaway folder (nothing lands in eval/reports/ or anywhere in the repo); no --switch-off-failing:
# people decide (non-negotiable 5). Then `python -m evalrunner.paste` prints the block from the report JSON.
#
# Refuses (exit 2), before any container: CI set; a route that is not anthropic or bedrock; the route's credentials
# missing; a base-URL override for the model set (so it can only reach the real API); then, asking Docker: the eval
# project, its volumes or networks already there; on the Mac, port 55447 busy; on the server, a relative path, the data
# folder already there, the install's worker image missing or without this command, or --project not running.
#
# Prints, between "=== PASTE FROM HERE ===" and "=== PASTE TO HERE ===", numbers and names only, ending with
# "EVAL-LIVE: PASS" or "EVAL-LIVE: FAIL (<gates>)". Exit 0 on PASS, 1 on FAIL or a stop. On an error it prints only
# "STOP: <error type> at <step>"; the details go to a mode-600 temp file it names, for your eyes only, never to paste.
# Everything it made is removed at the end, however it ends (Ctrl-C included); nothing that existed before is touched.
#
# The credentials are only ever tested with [ -n "${VAR:-}" ]: never echoed, printed, logged or written, and this
# script never traces itself (the first line below turns tracing off even under `bash -x`).
set +xv
set -uo pipefail
umask 077

# Script-internal names start clean, so a same-named variable from the caller's environment is neither used nor passed.
unset EL_MODE EL_ROUTE EL_CHECKOUT EL_PROJECT EL_APP_ENV_FILE EL_DATA_DIR EL_WORK EL_ERR EL_PY EL_DB_URL EL_PG_PW \
  EL_GEN_VAULT EL_GEN_PSEUDO EL_GEN_HMAC EL_GEN_INTERNAL EL_GEN_SESSION EL_RUNS EL_CREATED_PROJECT EL_CREATED_DATA \
  EL_REPO EL_REPORTS EL_EVAL_PROJECT EL_SHA EL_TAG EL_BEFORE EL_AFTER EL_PASSED EL_CREDS \
  ROOT AGENTS MAC_PROJECT MAC_PORT SERVER_PROJECT SERVER_DATA_DIR WORKER_UID EMAIL_DOMAINS SWITCH_REASON \
  BASE_URL_NAMES CREDS_ANTHROPIC CREDS_BEDROCK SECRET_NAMES STEP_ENV_NAMES MAC_KEEP_NAMES NAME_START NL \
  where have_aws running pg ports changes bound block eval_exit paste_exit paste_args status_out sw g p name v
unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES COMPOSE_PATH_SEPARATOR

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENTS="gatekeeper,judge"
MAC_PROJECT="kfin-eval-live"
MAC_PORT=55447
SERVER_PROJECT="kfin-ideas-eval"
SERVER_DATA_DIR="/srv/kfin-ideas-eval"
WORKER_UID=10001
EMAIL_DOMAINS="kfintech.com,kfintech.example"
SWITCH_REASON="eval-live: golden sets on this throwaway database only (BLD-C229)"
# The model SDK's own base-URL overrides (gateway/routes.py builds anthropic.Anthropic() and AnthropicBedrockMantle()
# from the environment) and the AWS endpoint overrides: any of them set means the run might not reach the real API.
BASE_URL_NAMES="ANTHROPIC_BASE_URL ANTHROPIC_BEDROCK_BASE_URL ANTHROPIC_BEDROCK_MANTLE_BASE_URL AWS_ENDPOINT_URL AWS_ENDPOINT_URL_BEDROCK AWS_ENDPOINT_URL_BEDROCK_RUNTIME"
CREDS_ANTHROPIC="ANTHROPIC_API_KEY"
CREDS_BEDROCK="AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_BEARER_TOKEN_BEDROCK AWS_REGION"
# Every name that can carry or point to a model credential: none reaches any step but the golden sets'.
SECRET_NAMES="$CREDS_ANTHROPIC $CREDS_BEDROCK ANTHROPIC_AUTH_TOKEN ANTHROPIC_AWS_API_KEY ANTHROPIC_PROFILE AWS_PROFILE AWS_SHARED_CREDENTIALS_FILE AWS_CONFIG_FILE"
# What a step's process or container is given, besides the route's credentials for the golden sets.
STEP_ENV_NAMES="APP_ENV DATABASE_URL COMPANY_REPO_PATH EVAL_REPORTS_DIR LLM_MODE EMBEDDINGS_MODE SPEECH_MODE KFIN_EMAIL_DOMAINS VAULT_ENCRYPTION_KEY PSEUDONYM_VAULT_KEY CONTRIBUTOR_HMAC_SECRET INTERNAL_API_TOKEN SESSION_SECRET PYTHONDONTWRITEBYTECODE"
# Mac only: what the Python steps keep from the terminal (a proxy and CA bundle the lead's network may need).
MAC_KEEP_NAMES="PATH HOME USER LOGNAME TMPDIR LANG LC_ALL LC_CTYPE TERM HTTPS_PROXY https_proxy HTTP_PROXY http_proxy NO_PROXY no_proxy ALL_PROXY all_proxy SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE"
NAME_START="abcdefghijklmnopqrstuvwxyz0123456789" # spelled out: a range would follow the locale
NL=$'\n'

say() { printf '%s\n' "$*"; }
has_line() { case "$NL$1$NL" in *"$NL$2$NL"*) return 0 ;; esac; return 1; }  # <lines> <line>, no pipe
refuse() {
  say "eval-live refused: $*"
  exit 2
}
stop() {  # <error type> <step>: the one line to paste; the details are in the error file
  say "STOP: $1 at $2"
  exit 1
}
usage() { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; }
# One value from an env file without running it as shell code (as scripts/uat/lib.sh `value` reads it), on stdout
# for a command substitution only: never printed.
value() {
  { grep -E "^$1=" "$2" || true; } | tail -1 | cut -d= -f2- \
    | sed -E "s/[[:space:]]+#.*\$//; s/^\"(.*)\"\$/\\1/; s/^'(.*)'\$/\\1/"
}
gen() { od -An -N24 -tx1 /dev/urandom | tr -d ' \n'; }  # 48 hex characters, throwaway

# ---- 0. Arguments ----------------------------------------------------------------------------------------------------
EL_MODE=mac
EL_ROUTE=""
EL_CHECKOUT=""
EL_PROJECT=""
EL_APP_ENV_FILE=""
EL_DATA_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --server) EL_MODE=server ;;
    --route | --checkout | --project | --app-env | --data-dir)
      [ $# -ge 2 ] || refuse "$1 needs a value"
      case "$1" in
        --route) EL_ROUTE="$2" ;;
        --checkout) EL_CHECKOUT="$2" ;;
        --project) EL_PROJECT="$2" ;;
        --app-env) EL_APP_ENV_FILE="$2" ;;
        --data-dir) EL_DATA_DIR="$2" ;;
      esac
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    --*) refuse "unknown option ${1%%=*} (see scripts/eval/live.sh --help)" ;;
    *) refuse "unexpected argument (see scripts/eval/live.sh --help)" ;;
  esac
  shift
done

# ---- 1. Refusals that need nothing but this shell ------------------------------------------------------------------
[ -z "${CI:-}" ] || refuse "this calls the real model with a real key, so it never runs in CI. Run it in your own terminal."
if [ "$EL_MODE" = mac ]; then
  [ -z "$EL_CHECKOUT$EL_PROJECT$EL_APP_ENV_FILE$EL_DATA_DIR" ] \
    || refuse "--checkout, --project, --app-env and --data-dir are for --server only"
  EL_ROUTE="${EL_ROUTE:-anthropic}"
fi
case "$EL_ROUTE" in
  anthropic) EL_CREDS="$CREDS_ANTHROPIC" ;;
  bedrock) EL_CREDS="$CREDS_BEDROCK" ;;
  *) refuse "the route must be anthropic or bedrock (--route, or ROUTE= for make eval-live)" ;;
esac

if [ "$EL_MODE" = server ]; then
  { [ -n "$EL_CHECKOUT" ] && [ -n "$EL_PROJECT" ] && [ -n "$EL_APP_ENV_FILE" ]; } \
    || refuse "--server needs --checkout, --project, --app-env and --route"
  EL_DATA_DIR="${EL_DATA_DIR:-$SERVER_DATA_DIR}"
  for p in "$EL_CHECKOUT" "$EL_APP_ENV_FILE" "$EL_DATA_DIR"; do
    case "$p" in
      /*) ;;
      *) refuse "--checkout, --app-env and --data-dir must be absolute paths" ;;
    esac
  done
  case "$EL_PROJECT" in
    [!${NAME_START}]* | *[!${NAME_START}_-]*) refuse "--project must be a compose project name (lower-case letters, digits, - and _)" ;;
  esac
  [ "$EL_PROJECT" != "$SERVER_PROJECT" ] && [ "$EL_PROJECT" != "$MAC_PROJECT" ] \
    || refuse "--project is the install's own project, never $EL_PROJECT"
  [ "$EL_PROJECT" != kfin-ideas ] || refuse "--project kfin-ideas is the dev stack with the product lead's demo: never read"
  { [ -f "$EL_CHECKOUT/infra/docker-compose.yml" ] && [ -d "$EL_CHECKOUT/db/migrations" ] \
    && [ -d "$EL_CHECKOUT/seed/company-repo" ] && [ -d "$EL_CHECKOUT/eval/golden" ]; } \
    || refuse "--checkout is not a release checkout (infra/docker-compose.yml, db/migrations, seed/company-repo, eval/golden)"
  { [ -f "$EL_APP_ENV_FILE" ] && [ -r "$EL_APP_ENV_FILE" ]; } || refuse "--app-env is not a file this user can read"
  case "$EL_DATA_DIR/" in "${EL_CHECKOUT%/}"/*) refuse "--data-dir must be outside the checkout" ;; esac
  [ ! -e "$EL_DATA_DIR" ] && [ ! -L "$EL_DATA_DIR" ] \
    || refuse "the data folder $EL_DATA_DIR already exists (a run that was cut off?). Check it is the eval's and remove it."
  [ -d "$(dirname "$EL_DATA_DIR")" ] || refuse "the folder that would hold $EL_DATA_DIR does not exist"
else
  EL_CHECKOUT="$ROOT"
fi

# A base-URL override anywhere means the run might not reach the real API: in this shell, and on the server in the
# install's app env file too (the install would not be using the route this measures).
for name in $BASE_URL_NAMES; do
  [ -z "${!name+x}" ] || refuse "$name is set, so this might not reach the real model API. Unset it and run this again."
  if [ "$EL_MODE" = server ] && [ -n "$(value "$name" "$EL_APP_ENV_FILE")" ]; then
    refuse "$name is set in the app env file, so the install would not use the route this measures"
  fi
done

# The route's credentials. Mac: from this terminal. Server: from the app env file only, into shell variables of this
# script (not exported) that only the golden sets' container is given, by name.
if [ "$EL_MODE" = server ]; then
  for name in $SECRET_NAMES; do unset "$name"; done
  for name in $EL_CREDS; do
    v="$(value "$name" "$EL_APP_ENV_FILE")"
    [ -z "$v" ] || printf -v "$name" '%s' "$v"
  done
  unset v
  where="in the app env file"
else
  where="in this terminal. Load it your own way (never on a command line) and run this again"
fi
if [ "$EL_ROUTE" = anthropic ]; then
  [ -n "${ANTHROPIC_API_KEY:-}" ] || refuse "ANTHROPIC_API_KEY is not set $where."
else
  have_aws=0
  if [ -n "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then have_aws=1; fi
  if [ -n "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then have_aws=1; fi
  { [ "$have_aws" = 1 ] && [ -n "${AWS_REGION:-}" ]; } \
    || refuse "the Bedrock route needs AWS_REGION and AWS credentials (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, or AWS_BEARER_TOKEN_BEDROCK) $where."
fi

command -v docker >/dev/null 2>&1 || refuse "docker is not on this PATH"
command -v git >/dev/null 2>&1 || refuse "git is not on this PATH"
if [ "$EL_MODE" = mac ]; then
  read -r -a EL_PY <<<"${EVAL_LIVE_PYTHON:-uv run --frozen python}"
  [ "${#EL_PY[@]}" -gt 0 ] || refuse "EVAL_LIVE_PYTHON is empty"
  if (exec 3<>"/dev/tcp/127.0.0.1/$MAC_PORT") 2>/dev/null; then
    refuse "port $MAC_PORT on 127.0.0.1 is in use: stop what is using it and run this again"
  fi
  EL_EVAL_PROJECT="$MAC_PROJECT"
else
  EL_EVAL_PROJECT="$SERVER_PROJECT"
fi

# ---- 2. The error file and the clean-up, armed before Docker is asked anything ------------------------------------
EL_ERR="$(mktemp "${TMPDIR:-/tmp}/kfin-eval-live-err.XXXXXX")" || refuse "could not make a temp file"
chmod 600 "$EL_ERR"
EL_WORK=""
EL_RUNS=""
EL_CREATED_PROJECT=0
EL_CREATED_DATA=0
EL_PASSED=0

# Docker never gets a credential: every call runs with them unset, except the golden sets' container (worker_run).
D() (
  for n in $SECRET_NAMES; do unset "$n"; done
  exec docker "$@"
)
# docker compose for the throwaway project only, with its own override and an empty env file (never the checkout's
# .env or the install's env files).
EC() (
  for n in $SECRET_NAMES; do unset "$n"; done
  export KFIN_EVAL_PG_PASSWORD="$EL_PG_PW"
  cd "$EL_WORK" || exit 97
  exec docker compose -p "$EL_EVAL_PROJECT" -f "$EL_CHECKOUT/infra/docker-compose.yml" -f "$EL_WORK/override.yml" \
    --project-directory "$EL_CHECKOUT" --env-file "$EL_WORK/empty.env" "$@"
)

cleanup() {
  local code=$?
  trap - EXIT
  trap '' INT TERM HUP # the clean-up itself is never cut short
  local n made=0
  for n in $EL_RUNS; do D rm -f "$n" >/dev/null 2>>"$EL_ERR" || true; done
  if [ "$EL_CREATED_PROJECT" = 1 ]; then
    made=1
    if ! EC down -v --remove-orphans >>"$EL_ERR" 2>&1; then
      say "clean-up: could not remove the throwaway project; remove it with: docker compose -p $EL_EVAL_PROJECT down -v"
      [ "$code" != 0 ] || code=1
    fi
  fi
  if [ "$EL_CREATED_DATA" = 1 ]; then
    made=1
    rm -rf "$EL_DATA_DIR" 2>>"$EL_ERR" || say "clean-up: could not remove $EL_DATA_DIR; remove it by hand"
  fi
  [ -z "$EL_WORK" ] || rm -rf "$EL_WORK"
  [ "$made" = 0 ] || say "cleaned up: project $EL_EVAL_PROJECT, its database volume and the throwaway folders are gone"
  if [ "$code" = 0 ] && [ "$EL_PASSED" = 1 ] || [ ! -s "$EL_ERR" ]; then
    rm -f "$EL_ERR"
  else
    say "details, for your eyes only and never to paste: $EL_ERR (mode 600; delete it when done)"
  fi
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# ---- 3. Refusals that ask Docker (read-only) -------------------------------------------------------------------------
# 0: the project's containers, volumes or networks exist; 1: none; anything else: Docker could not tell (a stop).
project_exists() {
  local out
  out="$(D compose ls -a -q 2>>"$EL_ERR")" || return 2
  if has_line "$out" "$1"; then return 0; fi
  out="$(D ps -a -q --filter "label=com.docker.compose.project=$1" 2>>"$EL_ERR")" || return 2
  [ -z "$out" ] || return 0
  out="$(D ps -a -q --filter "name=$1" 2>>"$EL_ERR")" || return 2 # a container with one of its step names
  [ -z "$out" ] || return 0
  out="$(D volume ls -q --filter "label=com.docker.compose.project=$1" 2>>"$EL_ERR")" || return 2
  [ -z "$out" ] || return 0
  out="$(D volume ls -q --filter "name=${1}_" 2>>"$EL_ERR")" || return 2
  [ -z "$out" ] || return 0
  out="$(D network ls -q --filter "label=com.docker.compose.project=$1" 2>>"$EL_ERR")" || return 2
  [ -z "$out" ] || return 0
  return 1
}
project_exists "$EL_EVAL_PROJECT"
case $? in
  0) refuse "a $EL_EVAL_PROJECT project, or its volumes or network, already exists (a run that was cut off?). Remove it with: docker compose -p $EL_EVAL_PROJECT down -v" ;;
  1) ;;
  *) stop "docker did not answer" "checks" ;;
esac

if [ "$EL_MODE" = server ]; then
  D image inspect "$EL_PROJECT-worker" >/dev/null 2>>"$EL_ERR" \
    || refuse "the install's worker image $EL_PROJECT-worker is missing: is --project the install's project?"
  running="$(D compose ls -q 2>>"$EL_ERR")" || stop "docker did not answer" "checks"
  has_line "$running" "$EL_PROJECT" || refuse "--project $EL_PROJECT is not running"
  pg="$(D ps -q --filter "label=com.docker.compose.project=$EL_PROJECT" --filter "label=com.docker.compose.service=postgres" --filter status=running 2>>"$EL_ERR")" \
    || stop "docker did not answer" "checks"
  [ -n "$pg" ] || refuse "the install's Postgres is not running in project $EL_PROJECT"
  # The installed image must carry this command (BLD-C229): a release from before it has no --only and no paste block.
  D run --rm --pull never --network none "$EL_PROJECT-worker" python -c "import evalrunner.paste" >>"$EL_ERR" 2>&1 \
    || refuse "the install's worker image has no make eval-live (BLD-C229): install a release that carries it first"
fi

# ---- 4. Throwaway values, folders and the compose override ---------------------------------------------------------
EL_WORK="$(mktemp -d "${TMPDIR:-/tmp}/kfin-eval-live.XXXXXX")" || stop "no temp folder" "setup"
EL_PG_PW="$(gen)"
EL_GEN_VAULT="$(gen)"
EL_GEN_PSEUDO="$(gen)"
EL_GEN_HMAC="$(gen)"
EL_GEN_INTERNAL="$(gen)"
EL_GEN_SESSION="$(gen)"
for g in "$EL_PG_PW" "$EL_GEN_VAULT" "$EL_GEN_PSEUDO" "$EL_GEN_HMAC" "$EL_GEN_INTERNAL" "$EL_GEN_SESSION"; do
  [ "${#g}" -eq 48 ] || stop "no random values" "setup"
done
: >"$EL_WORK/empty.env"
if [ "$EL_MODE" = mac ]; then
  ports="    ports: !override [\"127.0.0.1:$MAC_PORT:5432\"]"
  EL_DB_URL="postgres://ideas:$EL_PG_PW@127.0.0.1:$MAC_PORT/ideas?sslmode=disable"
  case "$EL_DB_URL" in
    "postgres://ideas:"*"@127.0.0.1:55447/ideas?sslmode=disable") ;;
    *) stop "the database address is not 127.0.0.1:55447" "setup" ;;
  esac
  EL_REPO="$EL_WORK/data/kfin-ideas"
  EL_REPORTS="$EL_WORK/data/eval-reports"
  mkdir -p "$EL_WORK/data" || stop "no temp folder" "setup"
else
  ports="    ports: !reset []"
  EL_DB_URL="postgres://ideas:$EL_PG_PW@postgres:5432/ideas?sslmode=disable"
  case "$EL_DB_URL" in
    "postgres://ideas:"*"@postgres:5432/ideas?sslmode=disable") ;;
    *) stop "the database address is not the eval project's own Postgres" "setup" ;;
  esac
  EL_REPO=/data/kfin-ideas
  EL_REPORTS=/data/eval-reports
  mkdir -m 700 "$EL_DATA_DIR" 2>>"$EL_ERR" || stop "no data folder" "setup"
  EL_CREATED_DATA=1
  chown "$WORKER_UID:$WORKER_UID" "$EL_DATA_DIR" 2>>"$EL_ERR" || stop "the data folder cannot be handed to the worker's user (run it with sudo)" "setup"
fi
# The base file's postgres and dbmate, with a generated password; on the Mac published on 127.0.0.1 only, on the server
# not published at all. The ${...} below are compose's, filled from KFIN_EVAL_PG_PASSWORD in EC's environment.
{
  printf '%s\n' "services:" "  postgres:" "    environment:" '      POSTGRES_PASSWORD: ${KFIN_EVAL_PG_PASSWORD:?}' "$ports"
  printf '%s\n' "  dbmate:" "    environment:" \
    '      DATABASE_URL: postgres://ideas:${KFIN_EVAL_PG_PASSWORD:?}@postgres:5432/ideas?sslmode=disable'
} >"$EL_WORK/override.yml"

# The Mac's Python steps: the terminal's basics, the throwaway settings and, for the golden sets only, the route's
# credentials; everything else in the terminal's environment is left out. $1 is the route for the golden sets, or none.
py() {
  local creds="" mode=fake
  if [ "$1" != none ]; then
    creds="$EL_CREDS"
    mode="$1"
  fi
  shift
  (
    for v in $(compgen -e); do
      case " $MAC_KEEP_NAMES $creds " in *" $v "*) continue ;; esac
      case "$v" in UV_*) continue ;; esac
      unset "$v" 2>/dev/null || true
    done
    export APP_ENV=test DATABASE_URL="$EL_DB_URL" COMPANY_REPO_PATH="$EL_REPO" EVAL_REPORTS_DIR="$EL_REPORTS" \
      LLM_MODE="$mode" EMBEDDINGS_MODE=hash SPEECH_MODE=fake KFIN_EMAIL_DOMAINS="$EMAIL_DOMAINS" \
      VAULT_ENCRYPTION_KEY="$EL_GEN_VAULT" PSEUDONYM_VAULT_KEY="$EL_GEN_PSEUDO" CONTRIBUTOR_HMAC_SECRET="$EL_GEN_HMAC" \
      INTERNAL_API_TOKEN="$EL_GEN_INTERNAL" SESSION_SECRET="$EL_GEN_SESSION" PYTHONDONTWRITEBYTECODE=1
    cd "$ROOT/services/worker" || exit 97
    exec "${EL_PY[@]}" "$@"
  )
}

# The server's steps: one throwaway container each, from the installed worker image, on the eval project's network
# only, given only the throwaway settings by name and, for the golden sets only, the route's credentials by name (their
# values reach docker through its environment, never argv). $1 is the step's name, $2 the route or none, $3 rw or ro
# for the data folder; then the command.
worker_run() {
  local step="$1" route="$2" data="$3" creds="" mode=fake name n
  shift 3
  if [ "$route" != none ]; then
    creds="$EL_CREDS"
    mode="$route"
  fi
  name="$SERVER_PROJECT-$step"
  EL_RUNS="$EL_RUNS $name"
  local -a args
  args=(run --rm --pull never --name "$name" --label "com.docker.compose.project=$SERVER_PROJECT"
    --network "${SERVER_PROJECT}_default" --user "$WORKER_UID:$WORKER_UID" --cap-drop ALL
    --security-opt no-new-privileges -v "$EL_DATA_DIR:/data:$data" -v "$EL_CHECKOUT/seed:/seed:ro"
    -v "$EL_CHECKOUT/eval/golden:/app/eval/golden:ro")
  for n in $STEP_ENV_NAMES $creds; do args+=(-e "$n"); done
  (
    for n in $SECRET_NAMES; do
      case " $creds " in *" $n "*) [ -z "${!n:-}" ] || export "${n?}" ;; *) unset "$n" ;; esac
    done
    export APP_ENV=test DATABASE_URL="$EL_DB_URL" COMPANY_REPO_PATH="$EL_REPO" EVAL_REPORTS_DIR="$EL_REPORTS" \
      LLM_MODE="$mode" EMBEDDINGS_MODE=hash SPEECH_MODE=fake KFIN_EMAIL_DOMAINS="$EMAIL_DOMAINS" \
      VAULT_ENCRYPTION_KEY="$EL_GEN_VAULT" PSEUDONYM_VAULT_KEY="$EL_GEN_PSEUDO" CONTRIBUTOR_HMAC_SECRET="$EL_GEN_HMAC" \
      INTERNAL_API_TOKEN="$EL_GEN_INTERNAL" SESSION_SECRET="$EL_GEN_SESSION" PYTHONDONTWRITEBYTECODE=1
    exec docker "${args[@]}" "$EL_PROJECT-worker" "$@"
  )
}

# The install's llm_calls, read-only through its own Postgres container: the only command this script sends to the
# install's project.
install_count() {
  local out
  out="$(cd "$EL_WORK" && D compose -p "$EL_PROJECT" exec -T postgres psql -U ideas -d ideas -At \
    -c "SELECT count(*) FROM llm_calls" 2>>"$EL_ERR")" || return 1
  case "$out" in '' | *[!0123456789]*) return 1 ;; esac
  printf '%s' "$out"
}

# ---- 5. Run -----------------------------------------------------------------------------------------------------------
if [ "$EL_MODE" = server ]; then
  EL_SHA="$(git -c safe.directory="$EL_CHECKOUT" -C "$EL_CHECKOUT" rev-parse HEAD 2>>"$EL_ERR")" || stop "no commit" "checkout"
  EL_TAG="$(git -c safe.directory="$EL_CHECKOUT" -C "$EL_CHECKOUT" describe --tags 2>>"$EL_ERR")" || EL_TAG=""
  EL_BEFORE="$(install_count)" || stop "the install's llm_calls could not be read" "install count before"
  say "eval-live (BLD-C229), server, route $EL_ROUTE: throwaway project $SERVER_PROJECT beside $EL_PROJECT (read-only)"
else
  EL_SHA="$(git -C "$ROOT" rev-parse HEAD 2>>"$EL_ERR")" || stop "no commit" "checkout"
  changes=""
  [ -z "$(git -C "$ROOT" status --porcelain --untracked-files=no 2>>"$EL_ERR")" ] || changes="--checkout-changes"
  say "eval-live (BLD-C229), mac, route $EL_ROUTE: throwaway project $MAC_PROJECT on 127.0.0.1:$MAC_PORT"
fi

say "  database ..."
EL_CREATED_PROJECT=1 # from here the clean-up takes the project down, whatever this step managed to create
EC up -d --wait --wait-timeout 120 postgres >>"$EL_ERR" 2>&1 || stop "exit $?" "database"
if [ "$EL_MODE" = mac ]; then
  bound="$(EC port postgres 5432 2>>"$EL_ERR")" || stop "exit $?" "database"
  [ "$bound" = "127.0.0.1:$MAC_PORT" ] || stop "the database is not on 127.0.0.1:$MAC_PORT" "database"
fi
say "  migrations ..."
EC run --rm -T dbmate up >>"$EL_ERR" 2>&1 || stop "exit $?" "migrations"
status_out="$(EC run --rm -T dbmate status 2>>"$EL_ERR")" || stop "exit $?" "migrations"
has_line "$status_out" "Pending: 0" || stop "migrations pending" "migrations"

say "  company repo copy and the 200 synthetic people ..."
if [ "$EL_MODE" = mac ]; then
  py none -m bootstrap.seed >>"$EL_ERR" 2>&1 || stop "exit $?" "seed"
else
  worker_run seed none rw python -m bootstrap.seed --seed-dir /seed/company-repo >>"$EL_ERR" 2>&1 || stop "exit $?" "seed"
fi

say "  switches ai.all, agent.gatekeeper and agent.judge on, in this throwaway database only ..."
for sw in ai.all agent.gatekeeper agent.judge; do
  if [ "$EL_MODE" = mac ]; then
    py none -m core.killswitch set "$sw" on --reason "$SWITCH_REASON" --actor process:eval >>"$EL_ERR" 2>&1 \
      || stop "exit $?" "switches"
  else
    worker_run "switch-$sw" none rw python -m core.killswitch set "$sw" on --reason "$SWITCH_REASON" \
      --actor process:eval >>"$EL_ERR" 2>&1 || stop "exit $?" "switches"
  fi
done

say "  golden sets $AGENTS on the real model ($EL_ROUTE); this takes a few minutes ..."
if [ "$EL_MODE" = mac ]; then
  py "$EL_ROUTE" -m evalrunner --only "$AGENTS" >>"$EL_ERR" 2>&1
else
  worker_run golden-sets "$EL_ROUTE" rw python -m evalrunner --only "$AGENTS" >>"$EL_ERR" 2>&1
fi
eval_exit=$? # 1 is a gate that failed: the paste block says which

paste_args=(--reports "$EL_REPORTS" --route "$EL_ROUTE" --agents "$AGENTS" --eval-exit "$eval_exit")
if [ "$EL_MODE" = server ]; then
  EL_AFTER="$(install_count)" || stop "the install's llm_calls could not be read" "install count after"
  paste_args+=(--mode server --installed-sha "$EL_SHA" --install-before "$EL_BEFORE" --install-after "$EL_AFTER")
  [ -z "$EL_TAG" ] || paste_args+=(--installed-tag "$EL_TAG")
  block="$(worker_run paste none ro python -m evalrunner.paste "${paste_args[@]}" 2>>"$EL_ERR")"
else
  paste_args+=(--mode mac --checkout-sha "$EL_SHA")
  [ -z "$changes" ] || paste_args+=("$changes")
  block="$(py none -m evalrunner.paste "${paste_args[@]}" 2>>"$EL_ERR")"
fi
paste_exit=$?
case "$NL$block" in
  *"${NL}EVAL-LIVE: PASS$NL=== PASTE TO HERE ===" | *"${NL}EVAL-LIVE: FAIL ("*")$NL=== PASTE TO HERE ===") ;;
  *) stop "no paste block (exit $paste_exit)" "paste" ;;
esac
printf '%s\n' "$block"
if [ "$paste_exit" = 0 ] && has_line "$block" "EVAL-LIVE: PASS" \
  && { [ "$EL_MODE" = mac ] || [ "$EL_BEFORE" = "$EL_AFTER" ]; }; then
  EL_PASSED=1
  exit 0
fi
exit 1
