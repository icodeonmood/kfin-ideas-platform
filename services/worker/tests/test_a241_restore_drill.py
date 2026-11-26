"""BLD-A241: the restore drill IT runs on the launch server (`make uat-restore-drill`, `scripts/uat/restore-drill.sh`),
and the dev drill's table list. No Docker: `docker`, `git` and `make` on PATH are stubs that write each call to a log
and answer with canned output, so these tests check the steps, the refusals, the trap and the output, never a real
database. Lane A rehearses the drill on real Docker (the rehearsal stack, kfin-ideas-uat-rehearsal)."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path

import pytest

from gonogo.__main__ import _latest
from tests import helpers
from tests.test_a234_uat_upgrade import UPGRADE
from tests.test_a234_uat_upgrade import _env as upgrade_env
from tests.test_a234_uat_upgrade import _env_files as upgrade_env_files
from tests.test_a234_uat_upgrade import _run as run_script

DRILL = helpers.ROOT / "scripts" / "uat" / "restore-drill.sh"
DEV_DRILL = helpers.ROOT / "scripts" / "ops" / "restore-drill.sh"
PROJECT = "kfin-ideas-uat"
COPY_DB = "ideas_restore_drill"
# A synthetic row: it is in the fake dump and in pg_restore's fake error, and must never reach the output.
ROW = "SYN-00001\tAsha Verma\tasha.verma@kfintech.example\tOps"
EMAIL = "asha.verma@kfintech.example"
DROP_HINT = (
    f'docker exec {PROJECT}-postgres-1 psql -U ideas -d postgres -c "DROP DATABASE {COPY_DB} WITH (FORCE)"'
)

FAKE_DOCKER = r"""#!/usr/bin/env bash
printf 'docker %s\n' "$*" >> "$FAKE_LOG"
a="$*"
live_tables() {
  printf 'table %s\n' 'audit_log 67' 'ideas 35' 'jobs 412' 'schema_migrations 77' 'users 226'
}
copy_lines() {
  printf 'migrations %s\n' "${FAKE_COPY_MIGRATIONS:-20261122300530}"
  live_tables | awk -v d="${FAKE_COPY_DIFF:-}" -v m="${FAKE_COPY_MISSING:-}" '
    BEGIN { split(d, x, " ") }
    $2 == m { next }
    d != "" && $2 == x[1] { print "table", x[1], x[2]; next }
    { print }'
  [[ -z "${FAKE_COPY_EXTRA:-}" ]] || printf 'table %s\n' "$FAKE_COPY_EXTRA"
}
case "$a" in
  *" ps --status running -q postgres") [[ -n "${FAKE_PG_DOWN:-}" ]] || echo cid-postgres ;;
  *"to_regclass"*) echo "${FAKE_REGCLASS:-t}" ;;
  *"FROM pg_database WHERE datname"*) if [[ -n "${FAKE_COPY_EXISTS:-}" ]]; then echo 1; else echo 0; fi ;;
  *"pg_database_size"*) echo 1048576 ;;
  *" df -Pk /var/lib/postgresql/data")
    printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\noverlay 9 1 %s 1%% /var/lib/postgresql/data\n' \
      "${FAKE_PG_FREE_KB:-99999999}" ;;
  *" -d ideas -tAq")
    # The read-only session on ideas: its script on stdin; the counts to a file in the container; the dump on stdout.
    cat > "$FAKE_STATE/session.sql"
    [[ -n "${FAKE_SESSION_FAIL:-}" ]] && { echo 'psql:<stdin>:6: ERROR:  synthetic failure' >&2; exit 3; }
    { printf 'migrations 20261122300530\n'; live_tables; printf 'dump %s\n' "${FAKE_DUMP_EXIT:-0}"; } > "$FAKE_STATE/counts"
    printf 'PGDMP synthetic dump %s\n' "$FAKE_ROW" ;;
  *" cat /tmp/restore-drill-"*".counts") cat "$FAKE_STATE/counts" ;;
  *" rm -f /tmp/restore-drill-"*".counts") rm -f "$FAKE_STATE/counts" ;;
  *"pg_restore --list")
    cat > /dev/null
    printf '3001; 0 16420 TABLE DATA public users ideas\n3002; 0 16421 TABLE DATA public ideas ideas\n' ;;
  *"pg_restore -U ideas -d ideas_restore_drill --exit-on-error")
    cat > /dev/null
    if [[ -n "${FAKE_RESTORE_HOLD:-}" ]]; then echo $$ > "$FAKE_STATE/restore.pid"; exec /bin/sleep 30; fi
    if [[ -n "${FAKE_RESTORE_FAIL:-}" ]]; then
      printf 'pg_restore: error: could not execute query: ERROR:  duplicate key value violates unique constraint "users_email_key"\n' >&2
      printf 'DETAIL:  Key (email)=(%s) already exists.\nCONTEXT:  COPY users, line 1: "%s"\n' "$FAKE_EMAIL" "$FAKE_ROW" >&2
      printf 'pg_restore: from TOC entry 3001; 0 16420 TABLE DATA public users ideas\n' >&2
      exit 1
    fi ;;
  *" -d ideas_restore_drill -tAq") cat > "$FAKE_STATE/copy.sql"; copy_lines ;;
  *) : ;;
esac
exit 0
"""

FAKE_LOGGER = '#!/usr/bin/env bash\nprintf \'%s %s\\n\' "$(basename "$0")" "$*" >> "$FAKE_LOG"\nexit 0\n'


def _bin(tmp_path: Path) -> Path:
    stub = tmp_path / "bin"
    stub.mkdir(parents=True, exist_ok=True)
    for name, body in (("docker", FAKE_DOCKER), ("git", FAKE_LOGGER), ("make", FAKE_LOGGER)):
        (stub / name).write_text(body)
        (stub / name).chmod(stat.S_IRWXU)
    return stub


def _env_files(tmp_path: Path) -> tuple[Path, Path]:
    """Synthetic env files: the drill only hands them to Compose, and nothing in them is a real secret."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    app, db = tmp_path / "app.env", tmp_path / "db.env"
    app.write_text("APP_ENV=prod\nLLM_MODE=fake\n")
    db.write_text(
        f"POSTGRES_PASSWORD={'P' * 24}\nDB_WEB_PASSWORD={'W' * 24}\nDB_WORKER_PASSWORD={'K' * 24}\n"
    )
    return app, db


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("FAKE_", "UAT_", "DRILL_", "COMPOSE_", "FROM"))
    }
    env.update(
        PATH=f"{_bin(tmp_path)}{os.pathsep}{os.environ['PATH']}",
        FAKE_LOG=str(tmp_path / "calls.log"),
        FAKE_STATE=str(tmp_path / "state"),
        FAKE_ROW=ROW,
        FAKE_EMAIL=EMAIL,
        UAT_DATA_DIR=str(tmp_path / "data"),
    )
    env.update(extra)
    return env


def _drill(tmp_path: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    app, db = _env_files(tmp_path)
    return subprocess.run(
        ["bash", str(DRILL), str(app), str(db)],
        capture_output=True,
        text=True,
        env=_env(tmp_path, **extra),
        check=False,
        timeout=120,
    )


def _calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def _first(calls: list[str], needle: str) -> int:
    return next(i for i, c in enumerate(calls) if needle in c)


def _ending(calls: list[str], tail: str) -> int:
    return next(i for i, c in enumerate(calls) if c.endswith(tail))


def _last_line(out: str) -> str:
    return out.rstrip().splitlines()[-1]


def _records(tmp_path: Path) -> list[dict[str, object]]:
    ops = tmp_path / "data" / "ops"
    return [json.loads(p.read_text()) for p in sorted(ops.glob("restore-drill-*.json"))]


def _drill_dumps(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "data" / "backups").glob("restore-drill-*.dump"))


def _other_backups(tmp_path: Path) -> dict[Path, str]:
    """An upgrade's backup and a dump an earlier drill left: the drill never touches either."""
    backups = tmp_path / "data" / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    kept = {
        backups / "upgrade-20261123T101500Z-ecd92664.dump": "synthetic upgrade backup",
        backups / "restore-drill-20261120T000000Z.dump": "synthetic earlier drill",
    }
    for path, text in kept.items():
        path.write_text(text)
    return kept


# ---- a drill that passes ---------------------------------------------------------------------------------------------


def test_bld_a241_the_drill_runs_checks_backup_restore_compare_cleanup_record_in_that_order(
    tmp_path: Path,
) -> None:
    run = _drill(tmp_path)
    assert run.returncode == 0, run.stdout + run.stderr
    steps = [run.stdout.index(f"== {n}/6 ") for n in range(1, 7)]
    assert steps == sorted(steps)
    for title in ("Checks", "Backup", "Restore", "Compare", "Clean up", "Record"):
        assert re.search(rf"^== \d/6 {title}", run.stdout, re.M), title
    calls = _calls(tmp_path)
    order = [
        _ending(calls, " ps --status running -q postgres"),
        _first(calls, "FROM pg_database WHERE datname = 'ideas_restore_drill'"),
        _ending(calls, " -d ideas -tAq"),  # the read-only session: counts and pg_dump in one snapshot
        _first(calls, "pg_restore --list"),
        _first(calls, f"CREATE DATABASE {COPY_DB}"),
        _first(calls, f"REVOKE CONNECT ON DATABASE {COPY_DB} FROM PUBLIC"),
        _first(calls, f"pg_restore -U ideas -d {COPY_DB} --exit-on-error"),
        _ending(calls, f" -d {COPY_DB} -tAq"),
        _first(calls, f"DROP DATABASE IF EXISTS {COPY_DB} WITH (FORCE)"),
    ]
    assert order == sorted(order), calls
    # One snapshot: the session exports it, counts every table from the catalog in it, and pg_dump takes the backup
    # with it; the session is read only and ends with the dump.
    session = (tmp_path / "state" / "session.sql").read_text().splitlines()
    assert session[0] == "BEGIN ISOLATION LEVEL REPEATABLE READ, READ ONLY;"
    assert session[-1] == "COMMIT;"
    text = "\n".join(session)
    assert "SELECT pg_export_snapshot() AS snap \\gset" in text
    assert '\\! pg_dump -U ideas -d ideas -Fc --snapshot="$DRILL_SNAPSHOT"' in text
    assert text.index("\\gexec") < text.index("\\! pg_dump")
    assert "\\qecho dump :SHELL_EXIT_CODE" in text
    for sql in (text, (tmp_path / "state" / "copy.sql").read_text()):
        assert "FROM pg_class c JOIN pg_namespace n" in sql and "n.nspname = 'public'" in sql
        assert "max(version)" in sql and "FROM schema_migrations" in sql
    assert (
        "compare: 5 tables, the same in both; every count equal; schema_migrations at 20261122300530 in both"
        in run.stdout
    )
    assert re.fullmatch(r"restore drill: passed in \d+s \(5 tables, counts equal\)", _last_line(run.stdout))
    assert _drill_dumps(tmp_path) == []
    assert not (tmp_path / "data" / "ops" / ".lock").exists()
    assert not (tmp_path / "state" / "counts").exists()  # the counts file in the container is removed
    # It never stops a service, migrates, changes a switch, or calls git or make.
    assert not any(
        re.search(r" (stop|up|down|restart|run|build) ", c) or "killswitch" in c or "dbmate" in c
        for c in calls
    )
    assert all(c.startswith("docker compose -p kfin-ideas-uat ") for c in calls), calls


def test_bld_a241_the_record_has_exactly_the_keys_the_go_no_go_report_reads(tmp_path: Path) -> None:
    assert _drill(tmp_path).returncode == 0
    ops = tmp_path / "data" / "ops"
    (path,) = ops.glob("restore-drill-*.json")
    assert re.fullmatch(r"restore-drill-\d{8}T\d{6}Z\.json", path.name)
    rec = json.loads(path.read_text())
    assert list(rec) == ["passed", "seconds", "where", "at"]
    assert rec["passed"] is True and rec["where"] == "launch server"
    assert isinstance(rec["seconds"], int) and 0 <= rec["seconds"] < 4 * 3600
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", rec["at"])
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert _latest(ops, "restore-drill-*.json") == rec  # the go/no-go report's own reader
    # The rehearsal names its place; nothing else changes.
    rehearsal = tmp_path / "rehearsal"
    assert _drill(rehearsal, DRILL_WHERE="rehearsal stack; rm -rf /").returncode == 0
    (rec2,) = _records(rehearsal)
    assert rec2["where"] == "rehearsal stack rm -rf " and rec2["passed"] is True


def test_bld_a241_the_scratch_database_is_never_ideas(tmp_path: Path) -> None:
    run = _drill(tmp_path, DRILL_DB="ideas")
    assert run.returncode == 0, run.stdout + run.stderr
    calls = _calls(tmp_path)
    named = [m.group(2) for c in calls for m in re.finditer(r"DATABASE (IF EXISTS )?(\w+)", c)]
    assert named and set(named) == {COPY_DB}, calls
    restores = [c for c in calls if "pg_restore -U" in c]
    assert restores and all(f" -d {COPY_DB} " in c for c in restores)
    # Every statement on ideas reads.
    writes = re.compile(r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|TRUNCATE|GRANT|REVOKE|COPY)\b", re.I)
    on_ideas = [c.split(" -c ", 1)[1] for c in calls if " -d ideas -tAq -c " in c]
    assert on_ideas and not any(writes.search(s) for s in on_ideas)
    session = (tmp_path / "state" / "session.sql").read_text()
    assert not writes.search(session.replace("READ ONLY", ""))
    script = DRILL.read_text("utf-8")
    assert "readonly DRILL_DB=ideas_restore_drill" in script
    assert not re.search(r"DATABASE (IF EXISTS )?ideas\b(?!_restore_drill)", script)


def test_bld_a241_a_leftover_drill_dump_and_other_backups_are_left_alone(tmp_path: Path) -> None:
    kept = _other_backups(tmp_path)
    run = _drill(tmp_path)
    assert run.returncode == 0, run.stdout + run.stderr
    for path, text in kept.items():
        assert path.read_text() == text
    leftover = tmp_path / "data" / "backups" / "restore-drill-20261120T000000Z.dump"
    assert (
        f"an earlier drill left its dump {leftover} (it holds personal data): delete it with  rm -f {leftover}"
        in run.stdout
    )
    assert _drill_dumps(tmp_path) == [leftover]


# ---- refusals ------------------------------------------------------------------------------------------------------


def test_bld_a241_refuses_an_existing_scratch_database_and_drops_nothing(tmp_path: Path) -> None:
    run = _drill(tmp_path, FAKE_COPY_EXISTS="1")
    assert run.returncode == 1
    assert f"STOPPED: {COPY_DB} already exists" in run.stderr
    assert "Nothing was dropped" in run.stderr and DROP_HINT in run.stderr
    calls = _calls(tmp_path)
    assert not any(
        "DROP DATABASE" in c or "CREATE DATABASE" in c or c.endswith(" -d ideas -tAq") for c in calls
    )
    assert _records(tmp_path) == [] and _drill_dumps(tmp_path) == []
    assert not (tmp_path / "data" / "ops" / ".lock").exists()
    assert _last_line(run.stdout) == "restore drill: FAILED (checks)"


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ({"UAT_PROJECT": "kfin-ideas"}, "UAT_PROJECT is kfin-ideas, the dev stack's project"),
        ({"FAKE_PG_DOWN": "1"}, "Postgres is not running in project kfin-ideas-uat"),
        ({"FAKE_REGCLASS": "f"}, "the database ideas or its schema_migrations is missing"),
        ({"FAKE_PG_FREE_KB": "2048"}, "not enough free disk where Postgres keeps its data for the copy"),
    ],
)
def test_bld_a241_refusals_before_the_backup_try_nothing_and_record_nothing(
    tmp_path: Path, extra: dict[str, str], message: str
) -> None:
    run = _drill(tmp_path, **extra)
    assert run.returncode == 1 and f"STOPPED: {message}" in run.stderr
    calls = _calls(tmp_path)
    assert not any(c.endswith(" -d ideas -tAq") or "DATABASE" in c or "pg_restore" in c for c in calls)
    assert _records(tmp_path) == [] and _drill_dumps(tmp_path) == []
    assert not (tmp_path / "data" / "ops" / ".lock").exists()
    assert _last_line(run.stdout) == "restore drill: FAILED (checks)"


# ---- failures after the backup: the trap ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "lines"),
    [
        (
            {"FAKE_COPY_DIFF": "jobs 413"},
            [
                "  differs: jobs: 412 rows in ideas, 413 in the copy",
                "compare: 5 tables in ideas, 5 in the copy; 1 differ; "
                "schema_migrations at 20261122300530 in ideas, 20261122300530 in the copy",
            ],
        ),
        (
            {"FAKE_COPY_MISSING": "users"},
            [
                "  missing from the copy: users (226 rows in ideas)",
                "compare: 5 tables in ideas, 4 in the copy; 1 differ;",
            ],
        ),
        ({"FAKE_COPY_EXTRA": "zz_extra 0"}, ["  only in the copy: zz_extra (0 rows)"]),
        (
            {"FAKE_COPY_MIGRATIONS": "20261120000100"},
            ["compare: 5 tables in ideas, 5 in the copy; 0 differ; schema_migrations at 20261122300530 in ideas, "
             "20261120000100 in the copy"],
        ),
    ],
)  # fmt: skip
def test_bld_a241_a_failed_compare_fails_and_the_trap_drops_the_copy_and_the_dump(
    tmp_path: Path, extra: dict[str, str], lines: list[str]
) -> None:
    kept = _other_backups(tmp_path)
    run = _drill(tmp_path, **extra)
    assert run.returncode == 1, run.stdout + run.stderr
    for line in lines:
        assert line in run.stdout
    assert "STOPPED: the copy differs from ideas at the backup" in run.stderr
    assert _last_line(run.stdout) == "restore drill: FAILED (compare)"
    calls = _calls(tmp_path)
    assert _ending(calls, f" -d {COPY_DB} -tAq") < _first(
        calls, f"DROP DATABASE IF EXISTS {COPY_DB} WITH (FORCE)"
    )
    assert f"dropped {COPY_DB}" in run.stdout
    assert "deleted the drill's dump" in run.stdout
    assert _drill_dumps(tmp_path) == [tmp_path / "data" / "backups" / "restore-drill-20261120T000000Z.dump"]
    for path, text in kept.items():
        assert path.read_text() == text
    (rec,) = _records(tmp_path)
    assert rec["passed"] is False and list(rec) == ["passed", "seconds", "where", "at"]
    assert not (tmp_path / "data" / "ops" / ".lock").exists()


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ({"FAKE_SESSION_FAIL": "1"}, "the read-only session on ideas stopped: no backup"),
        ({"FAKE_DUMP_EXIT": "1"}, "pg_dump (exit 1): no backup"),
    ],
)
def test_bld_a241_a_failed_backup_creates_no_copy_and_deletes_its_dump(
    tmp_path: Path, extra: dict[str, str], message: str
) -> None:
    run = _drill(tmp_path, **extra)
    assert run.returncode == 1 and f"STOPPED: {message}" in run.stderr
    assert not any("CREATE DATABASE" in c or "DROP DATABASE" in c for c in _calls(tmp_path))
    assert _drill_dumps(tmp_path) == []
    (rec,) = _records(tmp_path)
    assert rec["passed"] is False
    assert _last_line(run.stdout) == "restore drill: FAILED (backup)"


def _start_held_drill(tmp_path: Path) -> subprocess.Popen[str]:
    """A drill held inside pg_restore (its own process group, as a terminal or tmux runs it)."""
    app, db = _env_files(tmp_path)
    proc = subprocess.Popen(
        ["bash", str(DRILL), str(app), str(db)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_env(tmp_path, FAKE_RESTORE_HOLD="1"),
        start_new_session=True,
    )
    pid_file = tmp_path / "state" / "restore.pid"
    deadline = time.monotonic() + 30
    while not (pid_file.exists() and pid_file.read_text().strip()):
        if proc.poll() is not None or time.monotonic() > deadline:
            out, err = proc.communicate()
            pytest.fail(f"the held restore never started: {out}{err}")
        time.sleep(0.05)
    return proc


def _term(proc: subprocess.Popen[str]) -> tuple[str, str]:
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        return proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()


def test_bld_a241_term_during_the_restore_drops_the_copy_and_deletes_the_dump(tmp_path: Path) -> None:
    kept = _other_backups(tmp_path)
    proc = _start_held_drill(tmp_path)
    assert (tmp_path / "data" / "ops" / ".lock").is_dir()
    assert len(_drill_dumps(tmp_path)) == 2  # its own dump and the earlier drill's
    out, err = _term(proc)
    assert proc.returncode == 143, out + err
    assert "stopped by TERM" in out and _last_line(out) == "restore drill: FAILED (restore)"
    calls = _calls(tmp_path)
    assert _first(calls, f"pg_restore -U ideas -d {COPY_DB}") < _first(
        calls, f"DROP DATABASE IF EXISTS {COPY_DB}"
    )
    assert _drill_dumps(tmp_path) == [tmp_path / "data" / "backups" / "restore-drill-20261120T000000Z.dump"]
    for path, text in kept.items():
        assert path.read_text() == text
    (rec,) = _records(tmp_path)
    assert rec["passed"] is False
    assert not (tmp_path / "data" / "ops" / ".lock").exists()


# ---- the lock it shares with upgrade.sh and rollback.sh ------------------------------------------------------------


def test_bld_a241_a_drill_refuses_while_an_upgrade_or_rollback_holds_the_lock(tmp_path: Path) -> None:
    lock = tmp_path / "data" / "ops" / ".lock"
    lock.mkdir(parents=True)
    run = _drill(tmp_path)
    assert run.returncode == 1
    assert "STOPPED: an upgrade, a rollback or another restore drill holds" in run.stderr and lock.is_dir()
    assert not any(c.endswith(" -d ideas -tAq") or "DATABASE" in c for c in _calls(tmp_path))
    assert _records(tmp_path) == []


def test_bld_a241_an_upgrade_refuses_while_a_drill_holds_the_lock(tmp_path: Path) -> None:
    drill = tmp_path / "drill"
    proc = _start_held_drill(drill)
    try:
        data = drill / "data"
        (data / "kfin-ideas").mkdir()  # the upgrade checks the company repo before it takes the lock
        up = tmp_path / "up"
        up.mkdir()
        app, db = upgrade_env_files(up)
        env = upgrade_env(up, FROM="launch-2026-11-20-r2", UAT_DATA_DIR=str(data))
        run = run_script(["bash", str(UPGRADE), str(app), str(db)], env)
        assert run.returncode == 1 and "another upgrade or rollback holds" in run.stderr, (
            run.stdout + run.stderr
        )
        assert (data / "ops" / ".lock").is_dir()
        up_calls = (up / "calls.log").read_text().splitlines() if (up / "calls.log").exists() else []
        assert not any("pg_dump" in c or " build " in c for c in up_calls)
    finally:
        out, err = _term(proc)
    assert _last_line(out) == "restore drill: FAILED (restore)", out + err
    assert not (drill / "data" / "ops" / ".lock").exists()


def test_bld_a241_the_drill_uses_upgrade_sh_s_compose_wrapper_and_lock() -> None:
    def wrapper(text: str) -> str:
        return text.split("compose() {", 1)[1].split("\n}\n", 1)[0]

    drill, upgrade = DRILL.read_text("utf-8"), UPGRADE.read_text("utf-8")
    assert wrapper(drill) == wrapper(upgrade)
    assert 'mkdir "$UAT_DATA_DIR/ops/.lock" 2>/dev/null' in drill
    assert 'mkdir "$UAT_DATA_DIR/ops/.lock" 2>/dev/null' in upgrade
    assert '. "$ROOT/scripts/uat/lib.sh"' in drill


# ---- no row ever reaches the output (non-negotiable 3) -------------------------------------------------------------


def test_bld_a241_the_output_carries_table_names_and_counts_never_a_row(tmp_path: Path) -> None:
    ok = _drill(tmp_path / "ok")
    assert ok.returncode == 0
    failed = _drill(tmp_path / "failed", FAKE_RESTORE_FAIL="1")
    assert failed.returncode == 1
    assert "pg_restore: from TOC entry 3001; 0 16420 TABLE DATA public users ideas" in failed.stderr
    assert "its messages are not printed: they can quote a row" in failed.stderr
    assert _last_line(failed.stdout) == "restore drill: FAILED (restore)"
    for run in (ok, failed):
        both = run.stdout + run.stderr
        for secret in (ROW, EMAIL, "Asha", "SYN-00001", "PGDMP", "duplicate key", "DETAIL", "CONTEXT"):
            assert secret not in both, secret
    # The failed restore still drops the copy and deletes the dump.
    assert f"DROP DATABASE IF EXISTS {COPY_DB} WITH (FORCE)" in "\n".join(_calls(tmp_path / "failed"))
    assert _drill_dumps(tmp_path / "failed") == []


# ---- the dev drill, the Makefile and the runbook -------------------------------------------------------------------


def test_bld_a241_the_dev_drill_counts_every_table_in_public_from_the_catalog() -> None:
    dev = DEV_DRILL.read_text("utf-8")
    assert "TABLES=(" not in dev and "${TABLES" not in dev
    assert "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace" in dev
    assert "n.nspname = 'public'" in dev and "\\\\gexec" in dev
    run = subprocess.run(["bash", "-n", str(DEV_DRILL)], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr


def test_bld_a241_make_target_and_the_runbook_section() -> None:
    make = (helpers.ROOT / "Makefile").read_text("utf-8")
    assert "uat-restore-drill: ## " in make
    assert '\tscripts/uat/restore-drill.sh "$(APP_ENV_FILE)" "$(DB_ENV_FILE)"' in make
    assert "uat-restore-drill" in make.split(".PHONY:", 1)[1].splitlines()[0]
    doc = (helpers.ROOT / "docs" / "UAT.md").read_text("utf-8")
    headings = re.findall(r"^## (.+)$", doc, re.M)
    i = headings.index("Restore drill (BLD-A241)")
    assert headings[i - 1 : i + 2] == [
        "Updating the live server (upgrade and rollback)",
        "Restore drill (BLD-A241)",
        "Switching to full mode (mode A)",
    ]
    start = doc.index("## Restore drill (BLD-A241)")
    section = doc[start:].split("\n## ", 1)[0]
    for words in (
        "UAT_DATA_DIR=/srv/kfin-ideas-uat make uat-restore-drill APP_ENV_FILE=/secure/.env.uat "
        "DB_ENV_FILE=/secure/.env.uat.db",
        "ideas_restore_drill",
        "tell the review desk first",
        "changes nothing in it",
        "4 hours",
        "restore drill: passed in",
        "Never paste an env file, a secret or HR's file",
        "ops/.lock",
    ):
        assert words in section, words


def test_bld_a241_bash_n_and_make_can_run_it() -> None:
    run = subprocess.run(["bash", "-n", str(DRILL)], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    assert os.access(DRILL, os.X_OK)  # the make target runs it directly


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is not installed here")
def test_bld_a241_shellcheck() -> None:
    run = subprocess.run(
        ["shellcheck", "-x", "-S", "warning", "-s", "bash", str(DRILL)],
        capture_output=True,
        text=True,
        check=False,
        cwd=helpers.ROOT,
    )
    assert run.returncode == 0, run.stdout + run.stderr
