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
for name in POSTGRES_PASSWORD DB_WEB_PASSWORD DB_WORKER_PASSWORD; do
  v="$(value "$name" "$DB_ENV_FILE")"
  # Letters and digits only: they go into connection URLs, and Compose and this script must read them alike.
  [[ ${#v} -ge 20 && "$v" =~ ^[A-Za-z0-9]+$ ]] || fail "$name must be 20 or more random letters and digits"
done
v="$(value PSEUDONYM_VAULT_KEY "$DB_ENV_FILE")"
[[ ${#v} -ge 32 && "$v" =~ ^[A-Za-z0-9]+$ ]] || fail "PSEUDONYM_VAULT_KEY must be 32 or more random letters and digits"
[[ -z "$(value PSEUDONYM_VAULT_KEY "$APP_ENV_FILE")" ]] \
  || fail "PSEUDONYM_VAULT_KEY belongs in the database env file only: the app env file also reaches the web app"
compose build --quiet worker web
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
    || echo "golden sets: at least one agent failed; it is switched off and its step goes to the review desk"
else
  compose exec -T worker python -m core.killswitch set ai.all off \
    --reason "Mode B until InfoSec approves the model route (D1)" --actor ops:uat-deploy
fi

step "8/8 Smoke tests"
compose exec -T worker python -m bootstrap.smoke --web-url http://web:3000 --fresh

printf '\nUAT stack is up: web on port %s (project %s).\n' "${UAT_WEB_PORT:-3100}" "$PROJECT"
printf 'Next: grant the first admin with\n  docker compose -p %s ... exec worker python -m identity.grants grant --employee-id <ID> --role admin --reason "…" --actor ops:<code>\n' "$PROJECT"
