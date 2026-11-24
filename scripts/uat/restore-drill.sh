#!/usr/bin/env bash
# The restore drill on the launch server (BLD-A241; ARCHITECTURE §9.3, mode A: "Restore drill completed inside
# 4 hours", check: IT). IT runs it from the release checkout, with the env files the install uses:
#
#   UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-restore-drill APP_ENV_FILE=/secure/.env.uat DB_ENV_FILE=/secure/.env.uat.db
#
# Steps: checks → backup (one read-only snapshot of `ideas`: every table is counted in it, and pg_dump takes the
# backup from it, so the counts and the backup are of the same moment while people keep working) → restore the backup
# into the scratch database ideas_restore_drill on the same Postgres, as rollback.sh restores `ideas` → compare every
# table in schema public, from the catalog (the same tables, every row count equal, schema_migrations at the same
# version) → clean up (drop the scratch database, delete the drill's own dump) → record ops/restore-drill-<time>.json,
# the shape the go/no-go report reads. Whatever stops it, a trap drops the scratch database and deletes the drill's
# dump (INT and TERM too), and once the backup has started it records a failed drill.
# It never writes to `ideas`, never stops a service and never changes a kill switch. It prints table names, counts,
# paths and times only, never a row (non-negotiable 3): pg_restore's own messages can quote one, so only the names of
# the entries it stopped at are printed. The dump holds personal data and never leaves this server (DEC-103).
# It takes upgrade.sh's lock (ops/.lock): a drill never runs while an upgrade or a rollback does, nor the reverse.
# Optional, as for upgrade.sh: UAT_DATA_DIR (default ./.data-uat), UAT_PROJECT (kfin-ideas-uat). DRILL_WHERE (default
# "launch server") names the place in the record, for lane A's rehearsal.
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

compose() {
  docker compose -p "$PROJECT" -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . \
    --env-file "$APP_ENV_FILE" --env-file "$DB_ENV_FILE" "$@"
}
psql_c() {  # <database> <statement>
  compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U ideas -d "$1" -tAq -c "$2"
}
psql_in() {  # <database>: the statements on stdin
  compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U ideas -d "$1" -tAq
}

# The scratch database: fixed here, never `ideas`, never read from the environment.
readonly DRILL_DB=ideas_restore_drill
# Every table in schema public, from the catalog (never a list): one line "table <name> <rows>" each, by name.
COUNTS_SQL="SELECT format('SELECT %L || '' '' || count(*) FROM public.%I', 'table ' || c.relname, c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY c.relname"
MIGRATIONS_SQL="SELECT 'migrations ' || coalesce(max(version)::text, 'none') FROM schema_migrations"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
STARTED=$SECONDS
PHASE=checks
LOCK=""
DUMP=""            # the drill's own dump, from the moment it is written
COPY=0             # 1 from the moment the drill creates the scratch database
COUNTS_FILE=""     # in the postgres container: the session's table names and counts, never a row
SIGNAL=""
WHERE="$(tr -cd 'A-Za-z0-9 ._-' <<< "${DRILL_WHERE:-launch server}")"
DROP_HINT="docker exec $PROJECT-postgres-1 psql -U ideas -d postgres -c \"DROP DATABASE $DRILL_DB WITH (FORCE)\""

record() {  # <passed: true|false>: ops/restore-drill-<time>.json, exactly the keys the go/no-go report reads
  printf '{"passed": %s, "seconds": %d, "where": "%s", "at": "%s"}\n' "$1" "$(( SECONDS - STARTED ))" "$WHERE" \
    "$(utc_now)" > "$UAT_DATA_DIR/ops/restore-drill-$TS.json"
}
drop_copy() {
  [[ "$DRILL_DB" == "ideas_restore_drill" ]] || return 1
  psql_c postgres "DROP DATABASE IF EXISTS $DRILL_DB WITH (FORCE)" > /dev/null
}
# "<name> <rows>" lines from a session's output, sorted for join; nothing else ever leaves it.
table_counts() { sed -n 's/^table //p' <<< "$1" | LC_ALL=C sort -k1,1; }
# A session's output holds only these lines; anything else stops the drill and is not printed.
well_formed() { ! grep -Ev '^(table [A-Za-z0-9_$]+ [0-9]+|migrations [0-9]+|dump -?[0-9]+)$' <<< "$1" > /dev/null; }

on_exit() {
  local status=$?
  trap '' INT TERM   # the clean-up runs to its end
  set +e
  if [[ $COPY -eq 1 ]]; then
    if drop_copy; then
      echo "dropped $DRILL_DB"
    else
      printf 'could not drop %s: drop it with\n  %s\n' "$DRILL_DB" "$DROP_HINT" >&2
    fi
  fi
  if [[ -n "$DUMP" ]]; then
    rm -f "$DUMP" && echo "deleted the drill's dump $DUMP"
  fi
  [[ -z "$COUNTS_FILE" ]] || compose exec -T postgres rm -f "$COUNTS_FILE" > /dev/null 2>&1
  if [[ $status -ne 0 ]]; then
    [[ "$PHASE" == "checks" ]] || record false   # nothing was tried before the backup
  fi
  [[ -z "$LOCK" ]] || rmdir "$LOCK" 2>/dev/null
  if [[ $status -ne 0 ]]; then
    [[ -z "$SIGNAL" ]] || echo "stopped by $SIGNAL"
    echo "restore drill: FAILED ($PHASE)"
  fi
}
trap on_exit EXIT
trap 'SIGNAL=INT; exit 130' INT
trap 'SIGNAL=TERM; exit 143' TERM

step "1/6 Checks: the env files, Postgres, the live database, the scratch database's name, free disk"
[[ "$PROJECT" != "kfin-ideas" ]] \
  || fail "UAT_PROJECT is kfin-ideas, the dev stack's project with the product lead's demo: its drill is scripts/ops/restore-drill.sh"
[[ -r "$APP_ENV_FILE" && -r "$DB_ENV_FILE" ]] || fail "cannot read the env files: give the install's APP_ENV_FILE and DB_ENV_FILE"
if ! { mkdir -p "$UAT_DATA_DIR/ops" "$UAT_DATA_DIR/backups" 2>/dev/null && chmod 700 "$UAT_DATA_DIR/backups" 2>/dev/null \
  && [[ -w "$UAT_DATA_DIR/ops" && -w "$UAT_DATA_DIR/backups" ]]; }; then
  fail "cannot write $UAT_DATA_DIR/ops and $UAT_DATA_DIR/backups: run once  sudo install -d -m 700 -o $(id -un) $UAT_DATA_DIR/ops $UAT_DATA_DIR/backups"
fi
# upgrade.sh's lock: one upgrade, rollback or drill at a time; the folder goes when this run ends (short of kill -9).
mkdir "$UAT_DATA_DIR/ops/.lock" 2>/dev/null \
  || fail "an upgrade, a rollback or another restore drill holds $UAT_DATA_DIR/ops/.lock: if none is running (one was cut off), remove that folder"
LOCK="$UAT_DATA_DIR/ops/.lock"
[[ -n "$(compose ps --status running -q postgres)" ]] \
  || fail "Postgres is not running in project $PROJECT: is UAT_PROJECT the install's project?"
[[ "$(psql_c ideas "SELECT to_regclass('public.schema_migrations') IS NOT NULL")" == "t" ]] \
  || fail "the database ideas or its schema_migrations is missing: the drill backs up a running install"
[[ "$DRILL_DB" == "ideas_restore_drill" && "$DRILL_DB" != "ideas" ]] || fail "the scratch database must be ideas_restore_drill"
exists="$(psql_c postgres "SELECT count(*) FROM pg_database WHERE datname = '$DRILL_DB'")" \
  || fail "could not list the databases"
if [[ "$exists" != "0" ]]; then
  printf '\n%s already exists: an earlier drill stopped half-way. Nothing was dropped. Check that no drill is running, then\ndrop it with this one command and run the drill again:\n  %s\n' \
    "$DRILL_DB" "$DROP_HINT" >&2
  fail "$DRILL_DB already exists"
fi
echo "scratch database: $DRILL_DB (not there yet)"
for f in "$UAT_DATA_DIR"/backups/restore-drill-*.dump; do
  [[ -e "$f" ]] || continue
  echo "an earlier drill left its dump $f (it holds personal data): delete it with  rm -f $f"
done
db_bytes="$(psql_c ideas "SELECT pg_database_size('ideas')")" || fail "could not read the database size"
[[ "$db_bytes" =~ ^[0-9]+$ ]] || fail "could not read the database size"
free_kb="$(df -Pk "$UAT_DATA_DIR/backups" | awk 'NR == 2 { print $4 }')" || true
need_kb=$(( db_bytes / 1024 + 1048576 ))   # the database uncompressed, plus 1 GB
[[ "$free_kb" =~ ^[0-9]+$ && $free_kb -ge $need_kb ]] \
  || fail "not enough free disk for the drill's dump: ${free_kb:-?} KB free under $UAT_DATA_DIR/backups, $need_kb KB needed"
pg_free_kb="$(compose exec -T postgres df -Pk /var/lib/postgresql/data | awk 'NR == 2 { print $4 }')" || true
pg_need_kb=$(( 2 * (db_bytes / 1024) + 1048576 ))   # the copy, and the dump if it shares the disk, plus 1 GB
[[ "$pg_free_kb" =~ ^[0-9]+$ && $pg_free_kb -ge $pg_need_kb ]] \
  || fail "not enough free disk where Postgres keeps its data for the copy: ${pg_free_kb:-?} KB free, $pg_need_kb KB needed"
echo "free disk: $free_kb KB under backups/ (the dump needs at most $need_kb KB); $pg_free_kb KB for Postgres (the copy needs at most $pg_need_kb KB)"

PHASE=backup
step "2/6 Backup: one read-only snapshot of ideas; every table counted in it, and pg_dump takes the backup from it"
# One psql session on `ideas`, read only: it exports its snapshot, counts every table in it into a file in the
# container, then runs pg_dump with that snapshot, whose output is the session's output: the dump. PG16's
# SHELL_EXIT_CODE carries pg_dump's exit code into the same file. The session ends (COMMIT) once the dump is written.
DUMP="$UAT_DATA_DIR/backups/restore-drill-$TS.dump"
COUNTS_FILE="/tmp/restore-drill-$TS.counts"
session_sql="$(printf '%s\n' \
  'BEGIN ISOLATION LEVEL REPEATABLE READ, READ ONLY;' \
  'SELECT pg_export_snapshot() AS snap \gset' \
  '\setenv DRILL_SNAPSHOT :snap' \
  "\\o $COUNTS_FILE" \
  "$MIGRATIONS_SQL;" \
  "$COUNTS_SQL \\gexec" \
  '\! pg_dump -U ideas -d ideas -Fc --snapshot="$DRILL_SNAPSHOT"' \
  '\qecho dump :SHELL_EXIT_CODE' \
  '\o' \
  'COMMIT;')"
psql_in ideas <<< "$session_sql" > "$DUMP" || fail "the read-only session on ideas stopped: no backup"
chmod 600 "$DUMP"
live="$(compose exec -T postgres cat "$COUNTS_FILE")" || fail "could not read the counts of ideas"
compose exec -T postgres rm -f "$COUNTS_FILE" > /dev/null 2>&1 && COUNTS_FILE=""
well_formed "$live" || fail "the counts of ideas could not be read"
dump_exit="$(sed -n 's/^dump //p' <<< "$live")"
[[ "$dump_exit" == "0" ]] || fail "pg_dump (exit ${dump_exit:-unknown}): no backup"
[[ -s "$DUMP" ]] || fail "the backup is empty"
toc="$(compose exec -T postgres pg_restore --list < "$DUMP")" || fail "pg_restore --list cannot read the backup"
with_data="$(grep -c ' TABLE DATA ' <<< "$toc" || true)"
[[ "$with_data" -gt 0 ]] || fail "the backup has no table data"
live_counts="$(table_counts "$live")"
live_tables="$(grep -c . <<< "$live_counts" || true)"
live_migrations="$(sed -n 's/^migrations //p' <<< "$live")"
[[ "$live_tables" -gt 0 && -n "$live_migrations" ]] || fail "no tables counted in ideas"
echo "backup: $DUMP ($with_data tables with data)"
echo "ideas at the backup: $live_tables tables counted in the backup's own snapshot; schema_migrations at $live_migrations"

PHASE=restore
step "3/6 Restore: create $DRILL_DB on the same Postgres and restore the backup into it (as the rollback restores ideas)"
COPY=1   # from here the trap drops it, whatever stops the drill
psql_c postgres "CREATE DATABASE $DRILL_DB" > /dev/null || fail "could not create $DRILL_DB"
# Only the database owner reads the copy: the services' logins cannot connect to it.
psql_c postgres "REVOKE CONNECT ON DATABASE $DRILL_DB FROM PUBLIC" > /dev/null || fail "could not close $DRILL_DB to the services"
rc=0
err="$( { compose exec -T postgres pg_restore -U ideas -d "$DRILL_DB" --exit-on-error < "$DUMP" > /dev/null; } 2>&1 )" || rc=$?
if [[ $rc -ne 0 ]]; then
  # The names of the entries it stopped at, never its messages: an error's detail or context can quote a row.
  grep -E '^pg_restore: from TOC entry [0-9]+;' <<< "$err" | cut -c1-200 >&2 || true
  fail "pg_restore into $DRILL_DB (exit $rc; its messages are not printed: they can quote a row)"
fi
echo "restored: $DRILL_DB"

PHASE=compare
step "4/6 Compare: every table in schema public (from the catalog) in ideas at the backup and in $DRILL_DB"
copy="$(psql_in "$DRILL_DB" <<< "$(printf '%s;\n%s \\gexec\n' "$MIGRATIONS_SQL" "$COUNTS_SQL")")" \
  || fail "could not count the tables in $DRILL_DB"
well_formed "$copy" || fail "the counts of $DRILL_DB could not be read"
copy_counts="$(table_counts "$copy")"
copy_tables="$(grep -c . <<< "$copy_counts" || true)"
copy_migrations="$(sed -n 's/^migrations //p' <<< "$copy")"
joined="$(LC_ALL=C join -a 1 -a 2 -e - -o 0,1.2,2.2 <(printf '%s\n' "$live_counts") <(printf '%s\n' "$copy_counts"))"
differ="$(awk '$2 != $3' <<< "$joined")"
n_differ="$(grep -c . <<< "$differ" || true)"
if [[ "$n_differ" -eq 0 && "$live_tables" -eq "$copy_tables" && "$live_migrations" == "$copy_migrations" ]]; then
  echo "compare: $live_tables tables, the same in both; every count equal; schema_migrations at $live_migrations in both"
else
  [[ -z "$differ" ]] || awk '{
    if ($2 == "-") printf "  only in the copy: %s (%s rows)\n", $1, $3
    else if ($3 == "-") printf "  missing from the copy: %s (%s rows in ideas)\n", $1, $2
    else printf "  differs: %s: %s rows in ideas, %s in the copy\n", $1, $2, $3
  }' <<< "$differ"
  echo "compare: $live_tables tables in ideas, $copy_tables in the copy; $n_differ differ; schema_migrations at $live_migrations in ideas, ${copy_migrations:-none} in the copy"
  fail "the copy differs from ideas at the backup"
fi

PHASE=cleanup
step "5/6 Clean up: drop $DRILL_DB and delete the drill's dump (no other backup is touched)"
drop_copy || fail "could not drop $DRILL_DB"
COPY=0
echo "dropped $DRILL_DB"
rm -f "$DUMP" || fail "could not delete $DUMP"
echo "deleted the drill's dump $DUMP"
DUMP=""

PHASE=record
step "6/6 Record the drill for the go/no-go report"
seconds=$(( SECONDS - STARTED ))
(( seconds < 4 * 3600 )) || fail "the drill took ${seconds}s, over the 4-hour target"
record true
echo "recorded: $UAT_DATA_DIR/ops/restore-drill-$TS.json $(cat "$UAT_DATA_DIR/ops/restore-drill-$TS.json")"
printf '\nrestore drill: passed in %ss (%s tables, counts equal)\n' "$seconds" "$live_tables"
