#!/usr/bin/env bash
# Deploy a UAT stack from a clean database (AT-B7-06). Synthetic data only.
#
#   scripts/uat/deploy.sh <app env file> <database env file>
#
# The app env file holds the services' settings (APP_ENV=uat, secrets from the vault, Entra, model route).
# The database env file holds POSTGRES_PASSWORD, DB_WEB_PASSWORD, DB_WORKER_PASSWORD and the worker-only
# PSEUDONYM_VAULT_KEY; it builds each service's own settings and is never handed to a container as a whole.
#
# Steps: preflight → build → empty database check → migrations → service logins → company repo seed (no dev
# overlay outside dev) → start → golden sets on the model route (failing agents switch off), or Mode B if no route
# is approved → smoke tests. Stops at the first failure.
# Optional: UAT_DATA_DIR (default ./.data-uat), UAT_WEB_PORT (3100), UAT_PROJECT (kfin-ideas-uat).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
APP_ENV_FILE="$(cd "$(dirname "${1:?app env file}")" && pwd)/$(basename "$1")"
DB_ENV_FILE="$(cd "$(dirname "${2:?database env file}")" && pwd)/$(basename "$2")"
export UAT_APP_ENV_FILE="$APP_ENV_FILE"
export UAT_DATA_DIR="${UAT_DATA_DIR:-$ROOT/.data-uat}"
PROJECT="${UAT_PROJECT:-kfin-ideas-uat}"

compose() {
  docker compose -p "$PROJECT" -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
    --env-file "$APP_ENV_FILE" --env-file "$DB_ENV_FILE" "$@"
}
step() { printf '\n== %s\n' "$*"; }
fail() { printf 'STOPPED: %s\n' "$*" >&2; exit 1; }
# One value from an env file, without running the file as shell code.
value() { { grep -E "^$1=" "$2" || true; } | tail -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^"(.*)"$/\1/'; }

step "1/8 Preflight: no dev settings, no weak secrets"
# The privacy notice (BLD-A232): the web app shows its notice only when PRIVACY_NOTICE_VERSION equals the version
# in its text, and sends everyone who has not accepted that version to the notice first. A mismatch locks everyone
# out at sign-in. The two values are printed only when both look like versions (digits and dots, "-draft" allowed),
# so a secret pasted on the wrong line never reaches the terminal.
notice_env="$(value PRIVACY_NOTICE_VERSION "$APP_ENV_FILE")"
# More than one match, or none, leaves a value that is not a version, so the check stops.
notice_text="$(sed -nE 's/^[[:space:]]*version: "([^"]*)",[[:space:]]*$/\1/p' apps/web/src/content/privacy-notice.ts 2>/dev/null || true)"
notice_re='^[0-9]+(\.[0-9]+)*(-draft)?$'
if [[ -z "$notice_text" || "$notice_env" != "$notice_text" ]]; then
  if [[ "$notice_env" =~ $notice_re && "$notice_text" =~ $notice_re ]]; then
    fail "PRIVACY_NOTICE_VERSION in the app env file is $notice_env, but this build's privacy notice is $notice_text: set it to $notice_text"
  fi
  fail "PRIVACY_NOTICE_VERSION in the app env file must equal the version in apps/web/src/content/privacy-notice.ts"
fi
for name in POSTGRES_PASSWORD DB_WEB_PASSWORD DB_WORKER_PASSWORD; do
  v="$(value "$name" "$DB_ENV_FILE")"
  # Letters and digits only: they go into connection URLs, and Compose and this script must read them alike.
  [[ ${#v} -ge 20 && "$v" =~ ^[A-Za-z0-9]+$ ]] || fail "$name must be 20 or more random letters and digits"
done
v="$(value PSEUDONYM_VAULT_KEY "$DB_ENV_FILE")"
[[ ${#v} -ge 32 && "$v" =~ ^[A-Za-z0-9]+$ ]] || fail "PSEUDONYM_VAULT_KEY must be 32 or more random letters and digits"
[[ -z "$(value PSEUDONYM_VAULT_KEY "$APP_ENV_FILE")" ]] \
  || fail "PSEUDONYM_VAULT_KEY belongs in the database env file only: the app env file also reaches the web app"
# Voice notes (DEC-096, BLD-C015): with SPEECH_ENGINE_URL set, the isolated speech service starts too. Its token
# lives in the database env file (worker and speech service only), never the app env file (the web app reads that).
SPEECH_BUILD=""
speech_url="$(value SPEECH_ENGINE_URL "$APP_ENV_FILE")"
if [[ -n "$speech_url" ]]; then
  # Only the speech service on its internal network, over plain http inside it (BLD-C030); the worker refuses
  # anything else at start too.
  [[ "$speech_url" =~ ^http://speech(:[0-9]+)?/?$ ]] || fail "SPEECH_ENGINE_URL must be http://speech:8300 (the isolated speech service)"
  v="$(value SPEECH_SERVICE_TOKEN "$DB_ENV_FILE")"
  [[ ${#v} -ge 32 && "$v" =~ ^[A-Za-z0-9]+$ ]] || fail "SPEECH_SERVICE_TOKEN must be 32 or more random letters and digits, in the database env file"
  # Two different secrets, never reused (BLD-C017): the speech service must not hold the worker's own API token.
  [[ "$v" != "$(value INTERNAL_API_TOKEN "$APP_ENV_FILE")" ]] || fail "SPEECH_SERVICE_TOKEN must differ from INTERNAL_API_TOKEN"
  [[ -n "$(value SPEECH_MODEL_DIR "$DB_ENV_FILE")$(value SPEECH_MODEL_DIR "$APP_ENV_FILE")" ]] || fail "set SPEECH_MODEL_DIR to the speech model folder on the host"
  export COMPOSE_PROFILES=speech
  SPEECH_BUILD="speech"
fi
[[ -z "$(value SPEECH_SERVICE_TOKEN "$APP_ENV_FILE")" ]] \
  || fail "SPEECH_SERVICE_TOKEN belongs in the database env file only: the app env file also reaches the web app"
# Voice through Sarvam (DEC-108, BLD-C115): on at launch, so the route is sarvam unless the app env file says
# otherwise. The key is the worker's alone, in the database env file; the app env file also reaches the web app, so
# the key is refused there. The approval reference is DEC-108 unless the app env file names another. Both are set
# before the smoke check, which fails loudly without them (as the go/no-go report does).
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
compose build --quiet worker web $SPEECH_BUILD
compose run --rm --no-deps -T worker python -m bootstrap.preflight || fail "preflight"

step "2/8 Database: must be empty"
[[ -e "$UAT_DATA_DIR/kfin-ideas" ]] && fail "$UAT_DATA_DIR/kfin-ideas already exists; a fresh deploy needs an empty data folder"
mkdir -p "$UAT_DATA_DIR"
if [[ "$(uname)" == "Linux" && "$(stat -c %u "$UAT_DATA_DIR")" != "10001" ]]; then
  fail "the worker runs as uid 10001: run  sudo chown 10001 $UAT_DATA_DIR  first"
fi
compose up -d --wait --wait-timeout 120 postgres
existing="$(compose exec -T postgres psql -U ideas -d ideas -tAc "SELECT to_regclass('public.schema_migrations') IS NOT NULL")"
[[ "$existing" == "f" ]] || fail "the database already has tables; a fresh deploy needs an empty database"

step "3/8 Migrations"
compose run --rm -T dbmate up
compose run --rm -T dbmate status | tee /dev/stderr | grep -q "Pending: 0" || fail "migrations pending"

step "4/8 Service logins (each service has its own password)"
# The passwords travel on stdin (\set), never as arguments, so they do not show in process lists.
{
  printf '\\set web_pw %s\n\\set worker_pw %s\n' \
    "'$(value DB_WEB_PASSWORD "$DB_ENV_FILE")'" "'$(value DB_WORKER_PASSWORD "$DB_ENV_FILE")'"
  cat <<'SQL'
SELECT format('CREATE ROLE ideas_web LOGIN IN ROLE ideas_web_svc PASSWORD %L', :'web_pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ideas_web') \gexec
SELECT format('CREATE ROLE ideas_worker LOGIN IN ROLE ideas_worker_svc PASSWORD %L', :'worker_pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ideas_worker') \gexec
SQL
} | compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U ideas -d ideas

step "5/8 Company repo: seed, validate, index; synthetic people"
compose run --rm -T -v "$ROOT/seed:/seed:ro" -v "$ROOT/eval/golden:/app/eval/golden:ro" worker \
  python -m bootstrap.seed --seed-dir /seed/company-repo  # the synthetic people come from eval/golden/generators.py

step "6/8 Start the stack"
compose up -d --wait --wait-timeout 240

step "7/8 Model route"
if compose exec -T worker python -m bootstrap.preflight ai-route-ready; then
  echo "model route configured: golden sets run on it; an agent that fails switches itself off (§7.6)"
  compose run --rm -T -v "$ROOT/eval/golden:/app/eval/golden:ro" worker python -m evalrunner --switch-off-failing \
    || echo "golden sets: at least one agent failed or could not run; any switched off is listed above"
else
  compose exec -T worker python -m core.killswitch set ai.all off \
    --reason "Mode B until InfoSec approves the model route (D1)" --actor ops:uat-deploy
fi

step "8/8 Smoke tests"
compose exec -T worker python -m bootstrap.smoke --web-url http://web:3000 --fresh

# Record what is installed (BLD-A234): `make uat-upgrade` reads it as the version it upgrades from. A folder the
# deploy account cannot write only costs the record; the first upgrade then needs FROM=<this tag>.
installed_sha="$(git rev-parse HEAD 2>/dev/null || true)"
if [[ -n "$installed_sha" ]] && mkdir -p "$UAT_DATA_DIR/ops" 2>/dev/null && printf '{"sha": "%s", "tag": "%s", "at": "%s"}\n' \
  "$installed_sha" "$(git describe --tags --exact-match HEAD 2>/dev/null || true)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  2>/dev/null > "$UAT_DATA_DIR/ops/installed.json"; then
  echo "Recorded $UAT_DATA_DIR/ops/installed.json ($installed_sha)."
else
  echo "Could not write $UAT_DATA_DIR/ops/installed.json: the first make uat-upgrade needs FROM=<this tag>."
fi
printf '\nUAT stack is up: web on port %s (project %s).\n' "${UAT_WEB_PORT:-3100}" "$PROJECT"
# Production mode (BLD-A235): APP_ENV read as preflight reads it (stripped). The install loaded nobody.
if [[ "$(value APP_ENV "$APP_ENV_FILE" | tr -d '[:space:]')" == "prod" ]]; then
  printf 'Next (APP_ENV=prod, no people yet): docs/UAT.md After the deploy, 1a to 2b: the first admin signs in, then the HR import through stdin, then the grants.\n'
else
  printf 'Next: grant the first admin with\n  docker compose -p %s ... exec worker python -m identity.grants grant --employee-id <ID> --role admin --reason "…" --actor ops:<code>\n' "$PROJECT"
fi
