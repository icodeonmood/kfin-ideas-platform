"""BLD-A234: the upgrade path for the live server (`make uat-upgrade`, `make uat-rollback`,
`make uat-rehearsal-upgrade`). No Docker: `docker`, `git` and `make` on PATH are stubs that write each call to a log
and answer with canned output, so these tests check the order of the steps and every refusal, never a real stack.
Lane A rehearses the scripts on real Docker (`make uat-rehearsal-upgrade FROM=<ref>`)."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests import helpers

UAT = helpers.ROOT / "scripts" / "uat"
DEPLOY, LIB = UAT / "deploy.sh", UAT / "lib.sh"
UPGRADE, ROLLBACK, REHEARSE = UAT / "upgrade.sh", UAT / "rollback.sh", UAT / "rehearse-upgrade.sh"
NOTICE = helpers.ROOT / "apps" / "web" / "src" / "content" / "privacy-notice.ts"
FROM_SHA, TO_SHA = "1" * 40, "2" * 40
PROJECT = "kfin-ideas-uat"

FAKE_DOCKER = r"""#!/usr/bin/env bash
printf 'docker %s\n' "$*" >> "$FAKE_LOG"
a="$*"
key() { printf '%s' "$1" | tr ':/' '@_'; }
case "$a" in
  "ps -q --filter label=com.docker.compose.project=kfin-ideas") [[ -n "${FAKE_DEV_RUNNING:-}" ]] && echo dev1 ;;
  "ps -q --filter "*) : ;;
  *" ps --status running -q "*) case " ${FAKE_RUNNING-postgres worker web} " in *" ${a##* } "*) echo "cid-${a##* }" ;; esac ;;
  *" ps -q "*) echo "cid-${a##* }" ;;
  "inspect --format "*) echo "sha256:img-${a##*cid-}" ;;
  "image inspect "*) img="${a#image inspect }"; case "$img" in *:rollback-*) [[ -f "$FAKE_STATE/tag-$(key "$img")" ]] || exit 1 ;; esac ;;
  "image tag "*) set -- $a; touch "$FAKE_STATE/tag-$(key "$4")" ;;
  "image ls "*) for f in "$FAKE_STATE"/tag-*@rollback-*; do [[ -e "$f" ]] && basename "$f" | sed 's/^tag-//; s/@/:/'; done ;;
  "image rm "*) set -- $a; rm -f "$FAKE_STATE/tag-$(key "$3")" ;;
  *"to_regclass"*) echo t ;;
  *"FROM kill_switches"*) printf 'ai.all off\nsubmissions on\n' ;;
  *"pg_database_size"*) echo 1048576 ;;
  *"SELECT version FROM schema_migrations"*) printf '20261101000000\n20261102000000\n'; [[ -f "$FAKE_STATE/migrated" ]] && echo 20261120000100 ;;
  *"DROP DATABASE"*) rm -f "$FAKE_STATE/migrated" ;;
  *"core.killswitch list"*) printf 'ai.all                 %s\nsubmissions            on\n' "${FAKE_AI_ALL:-off}" ;;
  *"bootstrap.preflight ai-route-ready"*) exit "${FAKE_ROUTE_EXIT:-1}" ;;
  *"bootstrap.preflight"*) echo "preflight: ok" ;;
  *"pg_dump"*) [[ -n "${FAKE_PGDUMP_FAIL:-}" ]] && { echo "pg_dump: error: connection failed" >&2; exit 1; }; printf 'PGDMP-synthetic' ;;
  *"pg_restore --list"*) cat > /dev/null; echo "3001; 0 16420 TABLE DATA public users ideas" ;;
  *"pg_restore"*) cat > /dev/null ;;
  *"tar -C /data -cf -"*) tar -cf - -C "$FAKE_STATE" kfin-ideas ;;
  *"tar -C /data -xf -"*) cat > /dev/null ;;
  *"dbmate up"*) touch "$FAKE_STATE/migrated" ;;
  *"dbmate status"*) printf 'Applied: 3\nPending: 0\n' ;;
  *"bootstrap.smoke"*) if [[ -n "${FAKE_SMOKE_FAIL:-}" ]]; then echo "smoke: 1 check(s) failed"; exit 1; fi; echo "smoke: all checks passed" ;;
  *) : ;;
esac
exit 0
"""

FAKE_GIT = r"""#!/usr/bin/env bash
printf 'git %s\n' "$*" >> "$FAKE_LOG"
case "$*" in
  "status --porcelain") [[ -n "${FAKE_DIRTY:-}" ]] && echo " M Makefile" ;;
  "rev-parse HEAD") echo "$FAKE_TO" ;;
  "rev-parse --verify --quiet "*) echo "$FAKE_FROM" ;;
  "cat-file -e "*) : ;;
  "ls-tree --name-only "*) printf 'db/migrations/20261101000000_a.sql\ndb/migrations/20261102000000_b.sql\n' ;;
  "describe --tags --exact-match HEAD") echo launch-2026-11-20-r3 ;;
  "describe --tags --exact-match "*) echo launch-2026-11-20-r2 ;;
  "show "*":apps/web/src/content/privacy-notice.ts") echo "  version: \"$FAKE_NOTICE\"," ;;
  "show "*) echo "services: {}" ;;
  "worktree add --detach "*)
    set -- $*; mkdir -p "$4/scripts/uat"
    printf '#!/usr/bin/env bash\nmkdir -p "$UAT_DATA_DIR/kfin-ideas"\necho "smoke: all checks passed"\n' > "$4/scripts/uat/deploy.sh" ;;
  "worktree remove "*) set -- $*; rm -rf "$3" ;;
  *) : ;;
esac
exit 0
"""

FAKE_MAKE = '#!/usr/bin/env bash\nprintf \'make %s\\n\' "$*" >> "$FAKE_LOG.make"\nexit 0\n'


def _notice() -> str:
    m = re.findall(r'^\s*version: "([^"]*)",\s*$', NOTICE.read_text("utf-8"), re.M)
    assert len(m) == 1
    return m[0]


def _bin(tmp_path: Path) -> Path:
    stub = tmp_path / "bin"
    stub.mkdir(exist_ok=True)
    for name, body in (("docker", FAKE_DOCKER), ("git", FAKE_GIT), ("make", FAKE_MAKE)):
        (stub / name).write_text(body)
        (stub / name).chmod(stat.S_IRWXU)
    return stub


def _env_files(tmp_path: Path) -> tuple[Path, Path]:
    """Synthetic env files that pass the copied deploy.sh checks; nothing in them is a real secret."""
    app, db = tmp_path / "app.env", tmp_path / "db.env"
    app.write_text(
        f"APP_ENV=uat\nPRIVACY_NOTICE_VERSION={_notice()}\nLLM_MODE=fake\nINTERNAL_API_TOKEN={'t' * 40}\n"
    )
    db.write_text(
        f"POSTGRES_PASSWORD={'P' * 24}\nDB_WEB_PASSWORD={'W' * 24}\nDB_WORKER_PASSWORD={'K' * 24}\n"
        f"PSEUDONYM_VAULT_KEY={'V' * 40}\nSARVAM_API_KEY=test-only-synthetic\n"
    )
    return app, db


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    state = tmp_path / "state"
    (state / "kfin-ideas").mkdir(parents=True, exist_ok=True)
    (state / "kfin-ideas" / "README.md").write_text("synthetic company repo\n")
    data = tmp_path / "data"
    (data / "kfin-ideas").mkdir(parents=True, exist_ok=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("FAKE_", "UAT_", "FROM", "COMPOSE_", "SPEECH_"))
    }
    env.update(
        PATH=f"{_bin(tmp_path)}{os.pathsep}{os.environ['PATH']}",
        FAKE_LOG=str(tmp_path / "calls.log"),
        FAKE_STATE=str(state),
        FAKE_FROM=FROM_SHA,
        FAKE_TO=TO_SHA,
        FAKE_NOTICE=_notice(),
        UAT_DATA_DIR=str(data),
    )
    env.update(extra)
    return env


def _run(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, env=env, check=False, timeout=120)


def _upgrade(tmp_path: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    app, db = _env_files(tmp_path)
    return _run(["bash", str(UPGRADE), str(app), str(db)], _env(tmp_path, **extra))


def _calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def _first(calls: list[str], needle: str) -> int:
    return next(i for i, c in enumerate(calls) if needle in c)


# ---- upgrade.sh ----------------------------------------------------------------------------------------------------


def test_a234_upgrade_runs_build_preflight_backup_dbmate_restart_smoke_in_that_order(tmp_path: Path) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2")
    assert run.returncode == 0, run.stdout + run.stderr
    calls = _calls(tmp_path)
    order = [
        _first(calls, "build --quiet worker web"),
        next(
            i
            for i, c in enumerate(calls)
            if c.endswith("run --rm --no-deps -T worker python -m bootstrap.preflight")
        ),
        _first(calls, "pg_dump -U ideas -d ideas -Fc"),
        _first(calls, "pg_restore --list"),
        _first(calls, "dbmate up"),
        _first(calls, "dbmate status"),
        _first(calls, "up -d --wait"),
        _first(calls, "bootstrap.smoke"),
    ]
    assert order == sorted(order), calls
    # The running images are kept before the build replaces :latest.
    assert _first(calls, f"image tag sha256:img-worker {PROJECT}-worker:rollback-{FROM_SHA[:8]}") < order[0]
    restart = calls[order[6]]
    assert "--no-deps" in restart and "--no-build" in restart and restart.endswith("worker web")
    assert "postgres" not in restart
    assert "--no-deps" in calls[order[4]]
    smoke = calls[order[7]]
    assert "--fresh" not in smoke and smoke.endswith("--web-url http://web:3000")
    assert not any("killswitch set" in c for c in calls)
    for line in (
        "== 1/8",
        "== 4/8",
        "== 8/8",
        f"FROM {FROM_SHA}",
        f"TO   {TO_SHA}",
        "smoke: all checks passed",
    ):
        assert line in run.stdout


def test_a234_upgrade_records_the_install_and_keeps_a_private_checked_backup(tmp_path: Path) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2")
    assert run.returncode == 0, run.stderr
    ops = tmp_path / "data" / "ops"
    installed = json.loads((ops / "installed.json").read_text())
    assert installed["sha"] == TO_SHA and installed["tag"] == "launch-2026-11-20-r3" and installed["at"]
    (record,) = ops.glob("upgrade-*.json")
    rec = json.loads(record.read_text())
    assert rec["from"] == FROM_SHA and rec["to"] == TO_SHA and rec["smoke_passed"] is True
    assert rec["migrations_applied"] == ["20261120000100"] and isinstance(rec["seconds"], int)
    dump = Path(rec["backup"])
    assert dump.parent == tmp_path / "data" / "backups" and dump.name.endswith(f"-{FROM_SHA[:8]}.dump")
    assert stat.S_IMODE(dump.stat().st_mode) == 0o600
    assert stat.S_IMODE(dump.parent.stat().st_mode) == 0o700
    base = str(dump)[: -len(".dump")]
    assert stat.S_IMODE(Path(base + ".repo.tar").stat().st_mode) == 0o600
    saved = Path(base + ".from")
    assert (saved / "docker-compose.yml").exists() and (saved / "compose.uat.yml").exists()
    assert f"FROM_SHA={FROM_SHA}" in (saved / "from.env").read_text()
    assert f"FROM_NOTICE={_notice()}" in (saved / "from.env").read_text()
    calls = _calls(tmp_path)
    assert f"git show {FROM_SHA}:infra/docker-compose.yml" in calls
    assert f"git show {FROM_SHA}:infra/uat/compose.uat.yml" in calls


def test_a234_upgrade_refuses_when_pg_dump_fails_and_never_runs_dbmate(tmp_path: Path) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_PGDUMP_FAIL="1")
    assert run.returncode == 1
    assert "STOPPED: pg_dump" in run.stderr and "Nothing was changed" in run.stderr
    calls = _calls(tmp_path)
    assert not any("dbmate" in c or " up -d" in c for c in calls)
    # :latest goes back to the running images, and no half-written backup is left.
    assert f"docker image tag {PROJECT}-worker:rollback-{FROM_SHA[:8]} {PROJECT}-worker:latest" in calls
    assert not list((tmp_path / "data" / "backups").iterdir())
    assert "uat-rollback" not in run.stderr


def test_a234_upgrade_refuses_fake_mode_while_ai_all_is_on(tmp_path: Path) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_AI_ALL="on", FAKE_ROUTE_EXIT="1")
    assert run.returncode == 1 and "ai.all is on but the app env file has no model route" in run.stderr
    calls = _calls(tmp_path)
    assert not any(
        " build " in c or "pg_dump" in c or "image tag" in c or "killswitch set" in c for c in calls
    )


def test_a234_upgrade_goes_on_with_ai_all_on_when_a_route_is_configured(tmp_path: Path) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_AI_ALL="on", FAKE_ROUTE_EXIT="0")
    assert run.returncode == 0, run.stderr
    assert "ai.all on; model route configured" in run.stdout
    assert not any("killswitch set" in c for c in _calls(tmp_path))


def test_a234_upgrade_refuses_without_from_when_there_is_no_install_record(tmp_path: Path) -> None:
    run = _upgrade(tmp_path)
    assert run.returncode == 1 and "FROM=launch-2026-11-20-r2" in run.stderr
    assert not any(c.startswith("docker") for c in _calls(tmp_path))


def test_a234_upgrade_reads_from_out_of_installed_json_and_refuses_a_different_from(tmp_path: Path) -> None:
    ops = tmp_path / "data" / "ops"
    ops.mkdir(parents=True)
    (ops / "installed.json").write_text(f'{{"sha": "{FROM_SHA}", "tag": "", "at": "2026-11-20T00:00:00Z"}}\n')
    run = _upgrade(tmp_path)
    assert run.returncode == 0, run.stderr
    assert f"FROM {FROM_SHA}" in run.stdout
    (ops / "installed.json").write_text(f'{{"sha": "{"3" * 40}", "tag": "", "at": "2026-11-20T00:00:00Z"}}\n')
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2")
    assert run.returncode == 1 and "says " + "3" * 40 + " is installed" in run.stderr


def test_a234_upgrade_refuses_a_checkout_with_changes(tmp_path: Path) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_DIRTY="1")
    assert run.returncode == 1 and "this checkout has changes" in run.stderr
    assert not any(c.startswith("docker") for c in _calls(tmp_path))


def test_a234_upgrade_refuses_when_nothing_is_installed(tmp_path: Path) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_RUNNING="")
    assert run.returncode == 1 and "Postgres is not running" in run.stderr
    assert not any(" build " in c for c in _calls(tmp_path))


def test_a234_upgrade_after_the_backup_prints_the_rollback_and_does_not_roll_back(tmp_path: Path) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_SMOKE_FAIL="1")
    assert run.returncode == 1 and "STOPPED: smoke tests" in run.stderr
    (dump,) = (tmp_path / "data" / "backups").glob("*.dump")
    assert f"make uat-rollback BACKUP={dump}" in run.stderr
    calls = _calls(tmp_path)
    assert not any("DROP DATABASE" in c or "pg_restore -U" in c for c in calls)
    assert not (tmp_path / "data" / "ops" / "installed.json").exists()


def test_a234_upgrade_refuses_a_database_an_earlier_run_already_migrated(tmp_path: Path) -> None:
    """Review S1: a second run after a failure past dbmate would back up the new schema, and its rollback would start
    the old images on it. It points at the first run's backup instead."""
    assert _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_SMOKE_FAIL="1").returncode == 1
    (dump,) = (tmp_path / "data" / "backups").glob("*.dump")
    (tmp_path / "calls.log").unlink()
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2")
    assert run.returncode == 1
    assert f"already migrated this database (20261120000100 are not in {FROM_SHA[:8]})" in run.stderr
    assert f"(make uat-rollback BACKUP={dump}) instead of running the upgrade again" in run.stderr
    assert f"git ls-tree --name-only {FROM_SHA} db/migrations/" in _calls(tmp_path)
    assert not any(" build " in c or "pg_dump" in c or "image tag" in c for c in _calls(tmp_path))
    assert len(list((tmp_path / "data" / "backups").glob("*.dump"))) == 1
    assert not (tmp_path / "data" / "ops" / ".lock").exists()


def test_a234_upgrade_takes_one_lock_and_leaves_anothers_alone(tmp_path: Path) -> None:
    lock = tmp_path / "data" / "ops" / ".lock"
    lock.mkdir(parents=True)
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2")
    assert run.returncode == 1 and "another upgrade or rollback holds" in run.stderr and lock.exists()
    assert not any(" build " in c or "pg_dump" in c for c in _calls(tmp_path))
    lock.rmdir()
    assert _upgrade(tmp_path, FROM="launch-2026-11-20-r2").returncode == 0 and not lock.exists()


@pytest.mark.parametrize("script", ["upgrade", "rollback"])
def test_a234_upgrade_and_rollback_refuse_the_dev_stacks_project(tmp_path: Path, script: str) -> None:
    """Review S2: the dev project holds the product lead's demo, and a rollback drops its database."""
    app, db = _env_files(tmp_path)
    dump = tmp_path / "x.dump"
    dump.write_text("synthetic")
    args = [str(app), str(db)] if script == "upgrade" else [str(dump), str(app), str(db)]
    env = _env(tmp_path, UAT_PROJECT="kfin-ideas", FROM="launch-2026-11-20-r2")
    run = _run(["bash", str(UAT / f"{script}.sh"), *args], env)
    assert run.returncode == 1 and "UAT_PROJECT is kfin-ideas, the dev stack's project" in run.stderr
    assert _calls(tmp_path) == []


# ---- rollback.sh ---------------------------------------------------------------------------------------------------


def test_a234_rollback_drops_and_recreates_before_pg_restore_and_starts_the_old_compose(
    tmp_path: Path,
) -> None:
    assert _upgrade(tmp_path, FROM="launch-2026-11-20-r2").returncode == 0
    (dump,) = (tmp_path / "data" / "backups").glob("*.dump")
    (tmp_path / "calls.log").unlink()
    app, db = tmp_path / "app.env", tmp_path / "db.env"
    run = _run(["bash", str(ROLLBACK), str(dump), str(app), str(db)], _env(tmp_path))
    assert run.returncode == 0, run.stdout + run.stderr
    calls = _calls(tmp_path)
    order = [
        _first(calls, "stop worker web"),
        _first(calls, f"image tag {PROJECT}-worker:rollback-{FROM_SHA[:8]} {PROJECT}-worker:latest"),
        _first(calls, "-d postgres -tAq -c DROP DATABASE IF EXISTS ideas WITH (FORCE)"),
        _first(calls, "-d postgres -tAq -c CREATE DATABASE ideas"),
        _first(calls, "pg_restore -U ideas -d ideas --exit-on-error"),
        _first(calls, "tar -C /data -xf -"),
        _first(calls, "up -d --wait"),
        _first(calls, "bootstrap.smoke"),
    ]
    assert order == sorted(order), calls
    assert not any("--clean" in c for c in calls)
    saved = str(dump)[: -len(".dump")] + ".from"
    for i in order[0], order[6], order[7]:
        assert f"-f {saved}/docker-compose.yml -f {saved}/compose.uat.yml" in calls[i]
    assert (
        "--fresh" not in calls[order[7]]
        and "--no-deps" in calls[order[6]]
        and "--no-build" in calls[order[6]]
    )
    installed = json.loads((tmp_path / "data" / "ops" / "installed.json").read_text())
    assert installed["sha"] == FROM_SHA
    assert len(list((tmp_path / "data" / "ops").glob("rollback-*.json"))) == 1
    assert "Anything written after the backup is lost" in run.stdout
    # Review S4: the switches, names and states only, before the drop and after the restore.
    switches = [i for i, c in enumerate(calls) if "FROM kill_switches" in c]
    assert len(switches) == 2 and switches[0] < order[2] and order[4] < switches[1]
    assert "  ai.all off" in run.stdout
    assert "kill switches are back to their state at backup time: check them on the Admin page" in run.stdout
    assert not (tmp_path / "data" / "ops" / ".lock").exists()


def test_a234_rollback_refuses_a_notice_version_the_old_build_does_not_have(tmp_path: Path) -> None:
    assert _upgrade(tmp_path, FROM="launch-2026-11-20-r2").returncode == 0
    (dump,) = (tmp_path / "data" / "backups").glob("*.dump")
    from_env = Path(str(dump)[: -len(".dump")] + ".from") / "from.env"
    from_env.write_text(from_env.read_text().replace(f"FROM_NOTICE={_notice()}", "FROM_NOTICE=0.1"))
    (tmp_path / "calls.log").unlink()
    run = _run(
        ["bash", str(ROLLBACK), str(dump), str(tmp_path / "app.env"), str(tmp_path / "db.env")],
        _env(tmp_path),
    )
    assert run.returncode == 1 and "but this build's privacy notice is 0.1" in run.stderr
    assert not any("stop" in c or "DROP" in c for c in _calls(tmp_path))


def test_a234_rollback_refuses_without_the_kept_images(tmp_path: Path) -> None:
    assert _upgrade(tmp_path, FROM="launch-2026-11-20-r2").returncode == 0
    (dump,) = (tmp_path / "data" / "backups").glob("*.dump")
    for f in (tmp_path / "state").glob("tag-*rollback-*"):
        f.unlink()
    (tmp_path / "calls.log").unlink()
    run = _run(
        ["bash", str(ROLLBACK), str(dump), str(tmp_path / "app.env"), str(tmp_path / "db.env")],
        _env(tmp_path),
    )
    assert run.returncode == 1 and "no kept image" in run.stderr
    assert not any("DROP" in c for c in _calls(tmp_path))


# ---- rehearse-upgrade.sh -------------------------------------------------------------------------------------------


def _only_rehearsal_targets(calls: list[str], work: Path) -> None:
    """Review S3b: every destructive call names the rehearsal's project, its images or its worktree."""
    for c in calls:
        if any(f" {r}" in c for r in ("down", "--rmi", "image rm", "DROP DATABASE", "worktree remove")):
            assert "-p kfin-ideas " not in c and "-p kfin-ideas-uat " not in c, c
            assert (
                "-p kfin-ideas-uat-rehearsal " in c
                or " image rm kfin-ideas-uat-rehearsal-" in c
                or f" worktree remove {work}/from" in c
            ), c


def test_a234_rehearsal_refuses_while_the_dev_stack_runs_and_never_calls_make(tmp_path: Path) -> None:
    env = _env(
        tmp_path,
        FROM="launch-2026-11-20-r2",
        FAKE_DEV_RUNNING="1",
        UPGRADE_REHEARSAL_WORK=str(tmp_path / "w"),
    )
    run = _run(["bash", str(REHEARSE)], env)
    assert run.returncode == 1
    assert "stop the dev stack first from the main checkout: make down" in run.stdout
    assert not (tmp_path / "calls.log.make").exists()
    calls = _calls(tmp_path)
    assert not any(" compose " in c or "worktree" in c for c in calls) and not (tmp_path / "w").exists()


def test_a234_rehearsal_installs_from_upgrades_rolls_back_upgrades_and_tears_down(tmp_path: Path) -> None:
    work = tmp_path / "w"
    env = _env(tmp_path, FROM="launch-2026-11-20-r2", UPGRADE_REHEARSAL_WORK=str(work))
    shutil.rmtree(tmp_path / "data")
    run = _run(["bash", str(REHEARSE)], env)
    out = run.stdout
    assert run.returncode == 0, out + run.stderr
    assert "rehearsal: upgrade, rollback and upgrade again all passed" in out
    for phase in ("install-from", "upgrade", "rollback", "upgrade-again"):
        assert re.search(rf"^{phase}\s+PASS\s+smoke: all checks passed", out, re.M), out
    assert 'migrations applied by the upgrade: "20261120000100"' in out
    assert out.rstrip().endswith("start the dev stack again from the main checkout: make up")
    calls = _calls(tmp_path)
    assert _first(calls, f"git worktree add --detach {work}/from {FROM_SHA}") < _first(calls, "dbmate up")
    dbmate_ups = [i for i, c in enumerate(calls) if "dbmate up" in c]
    assert len(dbmate_ups) == 2 and dbmate_ups[0] < _first(calls, "DROP DATABASE") < dbmate_ups[1]
    assert any(
        "-p kfin-ideas-uat-rehearsal" in c and "down -v --rmi local --remove-orphans" in c for c in calls
    )
    assert any(
        c.startswith(f"docker image rm kfin-ideas-uat-rehearsal-worker:rollback-{FROM_SHA[:8]}")
        for c in calls
    )
    assert f"git worktree remove {work}/from" in calls and not any("--force" in c for c in calls)
    assert not work.exists() and not (tmp_path / "calls.log.make").exists()
    _only_rehearsal_targets(calls, work)


def test_a234_rehearsal_tears_down_when_a_phase_fails(tmp_path: Path) -> None:
    """Review S3a: the upgrade's smoke check fails; the rehearsal stops, says so and still tears everything down."""
    work = tmp_path / "w"
    env = _env(tmp_path, FROM="launch-2026-11-20-r2", UPGRADE_REHEARSAL_WORK=str(work), FAKE_SMOKE_FAIL="1")
    run = _run(["bash", str(REHEARSE)], env)
    out = run.stdout
    assert run.returncode != 0
    assert re.search(r"^upgrade\s+FAIL\s+smoke: FAILED", out, re.M), out
    assert "rehearsal: FAILED" in out and "rollback " not in out.split("== Summary", 1)[1]
    assert out.rstrip().endswith("start the dev stack again from the main checkout: make up")
    calls = _calls(tmp_path)
    assert any(
        "-p kfin-ideas-uat-rehearsal" in c and "down -v --rmi local --remove-orphans" in c for c in calls
    )
    assert f"git worktree remove {work}/from" in calls
    assert not work.exists() and not (tmp_path / "calls.log.make").exists()
    _only_rehearsal_targets(calls, work)


def test_a234_rehearsal_never_runs_make_and_never_starts_the_dev_stack() -> None:
    for line in REHEARSE.read_text("utf-8").splitlines():
        code = re.sub(r'"[^"]*"|\'[^\']*\'', "", line).split("#", 1)[0]
        assert not re.search(r"\bmake\b", code), line


# ---- the scripts themselves ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("script", sorted(UAT.glob("*.sh")), ids=lambda p: p.name)
def test_a234_bash_n(script: Path) -> None:
    run = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is not installed here")
def test_a234_shellcheck() -> None:
    scripts = [str(p) for p in (UPGRADE, ROLLBACK, REHEARSE, LIB)]
    run = subprocess.run(
        ["shellcheck", "-x", "-S", "warning", "-s", "bash", *scripts],
        capture_output=True,
        text=True,
        check=False,
        cwd=helpers.ROOT,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_a234_the_copied_env_checks_keep_every_stop_of_deploy_sh_step_1() -> None:
    deploy = DEPLOY.read_text("utf-8")
    step1 = deploy.split('step "1/8', 1)[1].split("compose build", 1)[0]
    stops = re.findall(r'fail "([^"]*)"', step1)
    assert len(stops) >= 12
    lib = LIB.read_text("utf-8")
    assert [s for s in stops if s not in lib] == []


def test_a234_deploy_records_the_install_only_after_the_smoke_tests() -> None:
    deploy = DEPLOY.read_text("utf-8")
    assert deploy.index("bootstrap.smoke") < deploy.index('"$UAT_DATA_DIR/ops/installed.json"')


def test_a234_makefile_targets_and_the_runbook_section() -> None:
    make = (helpers.ROOT / "Makefile").read_text("utf-8")
    assert 'FROM="$(FROM)" scripts/uat/upgrade.sh "$(APP_ENV_FILE)" "$(DB_ENV_FILE)"' in make
    assert 'scripts/uat/rollback.sh "$(BACKUP)" "$(APP_ENV_FILE)" "$(DB_ENV_FILE)"' in make
    assert 'FROM="$(FROM)" scripts/uat/rehearse-upgrade.sh' in make
    doc = (helpers.ROOT / "docs" / "UAT.md").read_text("utf-8")
    section = doc.split("## Updating the live server (upgrade and rollback)", 1)[1]
    for words in (
        "FROM=launch-2026-11-20-r2",
        "make uat-upgrade",
        "make uat-rollback",
        "never changes a kill switch",
    ):
        assert words in section
