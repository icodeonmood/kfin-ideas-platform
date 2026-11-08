#!/usr/bin/env bash
# Restore drill (AT-B8-02, §7.5): back up the database and the company repo, restore both into fresh places,
# check the restored copy, and time it against the 4-hour target. Synthetic data only.
#
#   scripts/ops/restore-drill.sh            # against the local dev stack; KEEP=1 keeps the restored copy
#
# What it proves: a database dump restores cleanly; the company repo comes back from its mirror (here a
# `git bundle`, in UAT the COMPANY_REPO_REMOTE mirror); `reconcile` finds no drift beyond what the source already
# had; row counts match. In UAT, IT restores Postgres to a point in time from its base backup and WAL archive
# instead of the dump (docs/RUNBOOK.md); the repo, reconcile and count steps are the same. The restored database
# needs the same VAULT_ENCRYPTION_KEY, or the pseudonym vault and drafts cannot be read.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f infra/docker-compose.yml --project-directory . --env-file .env)
WORK="$ROOT/.data/restore-drill"
DRILL_DB=ideas_restore_drill
TABLES=(ideas idea_links review_items corrections users role_grants pseudonym_vault notifications audit_log sla_timers outbox repo_files)
WHERE="$(tr -cd 'A-Za-z0-9 ._-' <<<"${DRILL_WHERE:-local dev stack}")"
# One value from .env, without running it as shell code.
env_value() { { grep -E "^$1=" .env || true; } | tail -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^"(.*)"$/\1/'; }
SRC_URL="$(env_value DATABASE_URL)"
[[ -n "$SRC_URL" ]] || SRC_URL="postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable"
DRILL_URL="${SRC_URL/\/ideas\?//$DRILL_DB?}"
REPO="$(env_value COMPANY_REPO_PATH)"; REPO="${REPO:-./.data/kfin-ideas}"
[[ "$REPO" = /* ]] || REPO="$ROOT/${REPO#./}"
started=$(date +%s)
step() { printf '\n== %s\n' "$*"; }
record() {  # the result for the go/no-go report, pass or fail
  mkdir -p "$ROOT/.data/ops"
  printf '{"passed": %s, "seconds": %d, "where": "%s", "at": "%s"}\n' "$1" "$(( $(date +%s) - started ))" "$WHERE" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ROOT/.data/ops/restore-drill-$(date -u +%Y%m%d-%H%M%S).json"
}
fail() { printf 'DRILL FAILED: %s\n' "$*" >&2; record false; exit 1; }
psql_q() { "${COMPOSE[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U ideas -tAq "$@"; }
counts() {
  local out="" n t
  for t in "${TABLES[@]}"; do
    n="$(psql_q -d "$1" -c "SELECT count(*) FROM $t")" || fail "could not count $t in $1"
    out+="$t=$n "
  done
  printf '%s' "$out"
}
reconcile() {  # the drift lines; exit 0 (none) or 1 (some) are both answers, anything else is a failure
  local out code=0
  out="$(cd services/worker && DATABASE_URL="$1" COMPANY_REPO_PATH="$2" EMBEDDINGS_MODE=hash \
    uv run --frozen python -m reconcile --report-only 2>/dev/null)" || code=$?
  [[ $code -le 1 ]] || fail "reconcile could not run (exit $code)"
  out="$(grep -E '^[a-z_]+( \(not drift\))? +[0-9]+$' <<<"$out" || true)"
  [[ "$(wc -l <<<"$out" | tr -d ' ')" -ge 7 ]] || fail "reconcile gave no drift report"
  printf '%s' "$out"
}

[[ -e "$WORK" ]] && fail "$WORK exists from an earlier drill; remove it first"
mkdir -p "$WORK"
cleanup() {
  if [[ "${KEEP:-0}" != "1" ]]; then
    psql_q -d postgres -c "DROP DATABASE IF EXISTS $DRILL_DB" >/dev/null 2>&1 || true
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT

step "1/5 Back up: database dump and company repo bundle"
before="$(counts ideas)"
"${COMPOSE[@]}" exec -T postgres pg_dump -U ideas -d ideas -Fc > "$WORK/ideas.dump"
git -C "$REPO" bundle create "$WORK/repo.bundle" --all >/dev/null 2>&1 || fail "could not bundle the company repo"
bundle_head="$(git bundle list-heads "$WORK/repo.bundle" HEAD | cut -d' ' -f1)"
printf 'dump %s bytes, bundle %s bytes\n' "$(wc -c < "$WORK/ideas.dump" | tr -d ' ')" "$(wc -c < "$WORK/repo.bundle" | tr -d ' ')"
baseline="$(reconcile "$SRC_URL" "$REPO")"

step "2/5 Restore the database into a fresh one"
psql_q -d postgres -c "DROP DATABASE IF EXISTS $DRILL_DB" >/dev/null
psql_q -d postgres -c "CREATE DATABASE $DRILL_DB" >/dev/null
"${COMPOSE[@]}" exec -T postgres pg_restore -U ideas -d "$DRILL_DB" --exit-on-error < "$WORK/ideas.dump"

step "3/5 Restore the company repo from its mirror"
git clone --quiet "$WORK/repo.bundle" "$WORK/kfin-ideas"
[[ "$(git -C "$WORK/kfin-ideas" rev-parse HEAD)" == "$bundle_head" ]] || fail "restored repo head differs from the backup"

step "4/5 Check: row counts and reconcile"
after="$(counts "$DRILL_DB")"
[[ "$before" == "$after" ]] || fail "row counts differ: before [$before] after [$after]"
echo "row counts match: $after"
restored="$(reconcile "$DRILL_URL" "$WORK/kfin-ideas")"
echo "$restored"
[[ "$restored" == "$baseline" ]] || fail "reconcile found drift the source did not have"
echo "reconcile: no new drift after the restore"

step "5/5 Time"
elapsed=$(( $(date +%s) - started ))
printf 'restore drill took %d min %d s (target: under 4 hours)\n' $((elapsed / 60)) $((elapsed % 60))
(( elapsed < 4 * 3600 )) || fail "over the 4-hour target"
record true
echo "DRILL PASSED"
