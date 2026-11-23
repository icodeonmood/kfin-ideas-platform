"""BLD-A234: the upgrade path for the live server (`make uat-upgrade`, `make uat-rollback`,
`make uat-rehearsal-upgrade`). No Docker: `docker`, `git` and `make` on PATH are stubs that write each call to a log
and answer with canned output, so these tests check the order of the steps and every refusal, never a real stack.
Lane A rehearses the scripts on real Docker (`make uat-rehearsal-upgrade FROM=<ref>`)."""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
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
  *"extract(epoch FROM now())"*) echo 1763800000.25 ;;
  *"action = 'file.start_sweep'"*)
    # As Postgres answers it: the row exists once the new worker has started (after dbmate up here), and `->>`
    # of a missing key is NULL, so the line is empty. A query for the whole `after` gets the whole JSON.
    if [[ -f "$FAKE_STATE/migrated" && -n "${FAKE_SWEEP_AFTER:-}" ]]; then
      case "$a" in
        *"after->>'count'"*) "$FAKE_PY" -I -c 'import json, sys
d = json.loads(sys.argv[1]); c = d.get(sys.argv[2]); k = d.get(sys.argv[3])
if c is not None and k is not None: print(c, json.dumps(k))' "$FAKE_SWEEP_AFTER" count complete ;;
        *) printf '%s\n' "$FAKE_SWEEP_AFTER" ;;
      esac
    fi ;;
  *" python - plant"*)
    cat > "$FAKE_STATE/driver.py"
    [[ -n "${FAKE_PLANT_FAIL:-}" ]] && { echo "STOPPED: files-from: D ATT-2026-000001: still checking after 180 s"; exit 1; }
    printf 'files: D ATT-2026-000001 on draft 00000000-0000-4000-8000-000000000001 of SYN-00010\n'
    printf 'files: W ATT-2026-000002 on draft 00000000-0000-4000-8000-000000000002 of SYN-00011\n'
    printf 'files: V ATT-2026-000003 on draft 00000000-0000-4000-8000-000000000003 of SYN-00012\n'
    printf 'files: D ATT-2026-000001 upload_failed (check_failed, no gatekeeper key, quarantine copy kept)\n' ;;
  *"pg_get_constraintdef"*)
    t=""; [[ -f "$FAKE_STATE/migrated" ]] && t=", 'teamup'"
    printf "hidden_details_source_check: CHECK (source IN ('file'%s))\nidea_words_sealed_source_check: CHECK (source IN ('edit'%s))\n" "$t" "$t" ;;
  *"WITH due AS (UPDATE jobs SET run_at = now()"*) echo t ;;
  *"SELECT EXISTS"*)
    # D waits on TO (the sweep's job) and is upload_failed on FROM's schema; everything else holds.
    if [[ -n "${FAKE_CHECK_FAIL:-}" && "$a" == *"$FAKE_CHECK_FAIL"* ]]; then echo f
    elif [[ "$a" == *"'ATT-2026-000001' AND state = 'queued' AND attempts = 0"* ]]; then [[ -f "$FAKE_STATE/migrated" ]] && echo t || echo f
    elif [[ "$a" == *"id = 'ATT-2026-000001' AND file_state = 'upload_failed'"* ]]; then [[ -f "$FAKE_STATE/migrated" ]] && echo f || echo t
    else echo t; fi ;;
  *"to_regclass"*) echo "${FAKE_REGCLASS:-t}" ;;
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
  *"tar -C /data -cf -"*)
    # BLD-A247: the first FAKE_TAR_CHANGED tries race the running repo writer, as GNU tar reports it; FAKE_TAR_EXIT
    # fails every try with another message.
    n=$(( $(cat "$FAKE_STATE/tar-tries" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$FAKE_STATE/tar-tries"
    [[ -n "${FAKE_TAR_EXIT:-}" ]] && { echo "tar: kfin-ideas/rules: Cannot open: Permission denied" >&2; exit "$FAKE_TAR_EXIT"; }
    tar -cf - -C "$FAKE_STATE" kfin-ideas
    (( n > ${FAKE_TAR_CHANGED:-0} )) || { echo "tar: kfin-ideas/.git: file changed as we read it" >&2; exit 1; } ;;
  *"tar -C /data -xf -"*) cat > /dev/null ;;
  *"dbmate up"*) touch "$FAKE_STATE/migrated" ;;
  *"dbmate status"*) printf 'Applied: 3\nPending: 0\n' ;;
  *"bootstrap.synthetic_hr"*) printf 'cwd %s\n' "$PWD" >> "$FAKE_LOG"; [[ -n "${FAKE_GEN_FAIL:-}" ]] && exit 1; printf 'employee_id,name,email,department,job_title,location,manager_employee_id\nSYN-00001,Synthetic One,one@kfintech.example,Ops,Analyst,Hyderabad,\n' ;;
  *"identity.hr_import"*) cat > /dev/null; [[ -n "${FAKE_HR_FAIL:-}" ]] && { echo "failed: line 2: synthetic"; exit 1; }; echo "hr import: 1 rows, 1 created, 0 updated, 0 deactivated, 0 unmapped departments, 0 unmapped titles, 0 proposals opened" ;;
  *"identity.grants grant"*) [[ -n "${FAKE_GRANT_FAIL:-}" ]] && { echo "no active person with that employee ID"; exit 1; }; echo granted ;;
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
  "ls-tree --name-only $FAKE_TO "*) printf 'db/migrations/20261101000000_a.sql\ndb/migrations/20261102000000_b.sql\ndb/migrations/20261120000100_c.sql\n' ;;
  "ls-tree --name-only "*) printf 'db/migrations/20261101000000_a.sql\ndb/migrations/20261102000000_b.sql\n' ;;
  "describe --tags --exact-match HEAD") echo launch-2026-11-20-r3 ;;
  "describe --tags --exact-match "*) echo launch-2026-11-20-r2 ;;
  "show "*":apps/web/src/content/privacy-notice.ts") echo "  version: \"$FAKE_NOTICE\"," ;;
  "show $FAKE_TO:services/worker/attachments/files.py") [[ -n "${FAKE_SWEEP:-}" ]] && echo '    "file.start_sweep",' || echo 'JOB = "file.check"' ;;
  "show "*":services/worker/attachments/files.py") [[ -n "${FAKE_SWEEP_FROM:-}" ]] && echo '    "file.start_sweep",' || echo 'JOB = "file.check"' ;;
  "show "*) echo "services: {}" ;;
  "worktree add --detach "*)
    set -- $*; mkdir -p "$4/scripts/uat"
    {
      printf '#!/usr/bin/env bash\nmkdir -p "$UAT_DATA_DIR/kfin-ideas"\n'
      printf '%s\n' '[[ -z "${FAKE_DEPLOY_SLEEP:-}" ]] || { echo $$ > "$FAKE_STATE/deploy.pid"; sleep "$FAKE_DEPLOY_SLEEP"; }'
      printf 'echo "smoke: all checks passed"\n'
    } > "$4/scripts/uat/deploy.sh" ;;
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
        FAKE_PY=sys.executable,
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


# ---- BLD-A247: the company repo is copied again when the running repo writer races tar ----------------------------

RETRY_LINE = "the company repo changed while it was copied (try {} of 10): copying it again in 2 s"
CHANGED = "tar: kfin-ideas/.git: file changed as we read it"


def _quick_sleep(tmp_path: Path) -> None:
    """A `sleep` that only logs its call, so ten tries take no time here (the real script waits 2 s)."""
    stub = tmp_path / "bin"
    stub.mkdir(exist_ok=True)
    (stub / "sleep").write_text('#!/usr/bin/env bash\nprintf \'sleep %s\\n\' "$*" >> "$FAKE_LOG"\nexit 0\n')
    (stub / "sleep").chmod(stat.S_IRWXU)


def _tar_tries(tmp_path: Path) -> int:
    return int((tmp_path / "state" / "tar-tries").read_text())


def test_bld_a247_a_changed_company_repo_is_copied_again_and_the_upgrade_goes_on(tmp_path: Path) -> None:
    _quick_sleep(tmp_path)
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_TAR_CHANGED="2")
    assert run.returncode == 0, run.stdout + run.stderr
    assert _tar_tries(tmp_path) == 3
    # One line per retry, with its try number, in the output IT pastes back; tar's own line stays visible.
    retries = [ln for ln in run.stdout.splitlines() if ln.startswith("the company repo changed")]
    assert retries == [RETRY_LINE.format(1), RETRY_LINE.format(2)]
    assert run.stderr.count(CHANGED) == 2
    calls = _calls(tmp_path)
    assert calls.count("sleep 2") == 2
    archive = _first(calls, "tar -C /data -cf -")
    assert _first(calls, "pg_restore --list") < archive < _first(calls, "dbmate up")
    (record,) = (tmp_path / "data" / "ops").glob("upgrade-*.json")
    base = json.loads(record.read_text())["backup"][: -len(".dump")]
    repo_tar = Path(base + ".repo.tar")
    assert stat.S_IMODE(repo_tar.stat().st_mode) == 0o600
    listing = subprocess.run(["tar", "-tf", str(repo_tar)], capture_output=True, text=True, check=True)
    assert "kfin-ideas/README.md" in listing.stdout
    assert "smoke: all checks passed" in run.stdout


def test_bld_a247_a_repo_that_changes_on_every_try_stops_after_the_tenth(tmp_path: Path) -> None:
    _quick_sleep(tmp_path)
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_TAR_CHANGED="99")
    assert run.returncode == 1
    assert _tar_tries(tmp_path) == 10
    retries = [ln for ln in run.stdout.splitlines() if ln.startswith("the company repo changed")]
    assert retries == [RETRY_LINE.format(n) for n in range(1, 10)]
    assert run.stderr.count(CHANGED) == 10
    # The same stop as before BLD-A247, and the same promise: nothing was changed, no half-made backup is left.
    assert "STOPPED: the company repo archive failed" in run.stderr and "Nothing was changed" in run.stderr
    calls = _calls(tmp_path)
    assert calls.count("sleep 2") == 9
    assert not any("dbmate" in c or " up -d" in c for c in calls)
    assert f"docker image tag {PROJECT}-worker:rollback-{FROM_SHA[:8]} {PROJECT}-worker:latest" in calls
    assert not list((tmp_path / "data" / "backups").iterdir())
    assert "uat-rollback" not in run.stderr


@pytest.mark.parametrize(
    "extra",
    [
        {"FAKE_TAR_EXIT": "2"},  # tar's fatal error
        {"FAKE_TAR_EXIT": "1"},  # exit 1 without the "file changed" text
    ],
    ids=["exit-2", "exit-1-other-text"],
)
def test_bld_a247_any_other_tar_failure_stops_at_once(tmp_path: Path, extra: dict[str, str]) -> None:
    _quick_sleep(tmp_path)
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", **extra)
    assert run.returncode == 1
    assert _tar_tries(tmp_path) == 1
    assert "the company repo changed" not in run.stdout
    assert "tar: kfin-ideas/rules: Cannot open: Permission denied" in run.stderr
    assert "STOPPED: the company repo archive failed" in run.stderr and "Nothing was changed" in run.stderr
    calls = _calls(tmp_path)
    assert "sleep 2" not in calls
    assert not any("dbmate" in c or " up -d" in c for c in calls)
    assert not list((tmp_path / "data" / "backups").iterdir())


def test_bld_a247_only_the_upgrade_makes_the_archive_and_the_check_after_it_stays() -> None:
    up = UPGRADE.read_text("utf-8")
    assert up.count("tar -C /data -cf - kfin-ideas") == 1
    assert "REPO_TAR_TRIES=10" in up
    assert '[[ $rc -eq 1 && "$err" == *"file changed as we read it"* ]] || return 1' in up
    after = up.split('archive_repo || fail "the company repo archive failed"', 1)[1]
    assert after.index('tar -tf "$BASE.repo.tar"') < after.index("record_upgrade false")
    for other in (DEPLOY, ROLLBACK):
        assert "-cf -" not in other.read_text("utf-8")


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
    assert run.returncode == 1 and "FROM=launch-2026-11-20-r3" in run.stderr
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
    assert (
        "Roll it back; do not run the upgrade again. Check it is the backup from before the failed upgrade"
        in run.stderr
    )
    data = tmp_path / "data"
    assert (
        f"  UAT_DATA_DIR={data} UAT_PROJECT={PROJECT} make uat-rollback BACKUP={dump} "
        f"APP_ENV_FILE={tmp_path / 'app.env'} DB_ENV_FILE={tmp_path / 'db.env'}\n"
    ) in run.stderr
    # The failed run named its backup as soon as it was checked: that is the one the hint gives.
    (record,) = (data / "ops").glob("upgrade-*.json")
    rec = json.loads(record.read_text())
    assert rec["backup"] == str(dump) and rec["from"] == FROM_SHA and rec["smoke_passed"] is False
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


def test_a234_upgrade_without_the_database_points_at_the_rollback_never_a_fresh_deploy(
    tmp_path: Path,
) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_REGCLASS="f")
    assert run.returncode == 1
    assert "If a rollback was interrupted, run make uat-rollback again with the same BACKUP" in run.stderr
    assert "Never run make uat-deploy over a live install" in run.stderr
    assert not any(" build " in c or "pg_dump" in c for c in _calls(tmp_path))


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


def test_a237_rehearsal_refuses_an_app_env_other_than_uat_or_prod(tmp_path: Path) -> None:
    work = tmp_path / "w"
    env = _env(
        tmp_path, FROM="launch-2026-11-20-r3", REHEARSE_APP_ENV="dev", UPGRADE_REHEARSAL_WORK=str(work)
    )
    run = _run(["bash", str(REHEARSE)], env)
    assert run.returncode == 1
    assert "REHEARSE_APP_ENV must be uat (the default) or prod, not dev" in run.stderr
    assert not work.exists() and not any(" compose " in c or "worktree" in c for c in _calls(tmp_path))


def test_a237_rehearsal_in_prod_imports_synthetic_people_and_grants_before_the_upgrade(
    tmp_path: Path,
) -> None:
    """BLD-A237: FROM installs in production mode; the synthetic HR file goes in through stdin, then the first admin
    and core_committee, then the smoke checks without --fresh, all before the upgrade's first migration."""
    work = tmp_path / "w"
    env = _env(
        tmp_path,
        FROM="launch-2026-11-20-r3",
        REHEARSE_APP_ENV="prod",
        UPGRADE_REHEARSAL_WORK=str(work),
        KEEP="1",
    )
    shutil.rmtree(tmp_path / "data")
    run = _run(["bash", str(REHEARSE)], env)
    out = run.stdout
    assert run.returncode == 0, out + run.stderr
    assert "== Summary (upgrade rehearsal, APP_ENV=prod)" in out
    for phase in ("install-from", "people-prod", "upgrade", "rollback", "upgrade-again"):
        assert re.search(rf"^{phase}\s+PASS\s+smoke: all checks passed", out, re.M), out
    assert "APP_ENV=prod\n" in (work / "app.env").read_text()
    # BLD-A239: this checkout (main without lane C's A2) has no start sweep, so no file is planted.
    assert re.search(r"^files-from\s+SKIPPED\s+TO has no start sweep$", out, re.M), out
    calls = _calls(tmp_path)
    worker = "kfin-ideas-uat-rehearsal-worker-1"
    gen = _first(calls, "bootstrap.synthetic_hr --count 20")
    assert (
        "-p kfin-ideas-uat-rehearsal " in calls[gen]
        and f"-v {work}/from/eval/golden:/app/eval/golden:ro" in calls[gen]
    )
    assert calls[gen + 1] == f"cwd {work}/from"  # FROM's compose files and env, not this checkout's
    imp = _first(calls, f"docker exec -i {worker} python -m identity.hr_import -")
    admin = _first(
        calls, f"docker exec {worker} python -m identity.grants grant --employee-id SYN-00001 --role admin"
    )
    core = _first(
        calls,
        f"docker exec {worker} python -m identity.grants grant --employee-id SYN-00002 --role core_committee",
    )
    smoke = next(
        i
        for i, c in enumerate(calls)
        if c == f"docker exec {worker} python -m bootstrap.smoke --web-url http://web:3000"
    )
    assert gen < imp < admin < core < smoke < _first(calls, "dbmate up")
    assert oct((work / "hr-synthetic.csv").stat().st_mode & 0o777) == "0o600"
    assert not (tmp_path / "calls.log.make").exists()
    _only_rehearsal_targets(calls, work)


@pytest.mark.parametrize(
    ("fail", "stopped", "never"),
    [
        ("FAKE_GEN_FAIL", "STOPPED: the synthetic HR file was not written", "identity.hr_import"),
        ("FAKE_HR_FAIL", "STOPPED: the HR import", "identity.grants"),
        ("FAKE_GRANT_FAIL", "STOPPED: the admin grant", "--role core_committee"),
    ],
)
def test_a237_rehearsal_in_prod_stops_before_the_upgrade_when_a_step_fails_and_tears_down(
    tmp_path: Path, fail: str, stopped: str, never: str
) -> None:
    work = tmp_path / "w"
    env = _env(
        tmp_path,
        FROM="launch-2026-11-20-r3",
        REHEARSE_APP_ENV="prod",
        UPGRADE_REHEARSAL_WORK=str(work),
        **{fail: "1"},
    )
    run = _run(["bash", str(REHEARSE)], env)
    out = run.stdout
    assert run.returncode != 0
    assert stopped in out
    assert re.search(r"^people-prod\s+FAIL", out, re.M), out
    calls = _calls(tmp_path)
    assert not any("dbmate up" in c or never in c for c in calls)
    assert any(
        "-p kfin-ideas-uat-rehearsal" in c and "down -v --rmi local --remove-orphans" in c for c in calls
    )
    assert f"git worktree remove {work}/from" in calls and not work.exists()
    _only_rehearsal_targets(calls, work)


# ---- BLD-A239: the start sweep's count in the upgrade's output ----------------------------------------------------

COUNT_LINE = "file checks: {} files back to waiting for the personal-data check (none opened)"
PART_WAY = (
    "file checks: the worker's start sweep stopped part-way after {} files; nothing was opened. "
    "Send this output to lane A."
)
NOT_REPORTED = (
    "file checks: the worker did not report its start sweep within {} s; nothing was opened. "
    "Send this output to lane A."
)


def _sweep_reads(calls: list[str]) -> list[str]:
    return [c for c in calls if "file.start_sweep" in c and c.startswith("docker ")]


def test_a239_upgrade_prints_the_start_sweep_count_from_its_audit_row_after_the_restart(
    tmp_path: Path,
) -> None:
    run = _upgrade(
        tmp_path,
        FROM="launch-2026-11-20-r2",
        FAKE_SWEEP="1",
        FAKE_SWEEP_AFTER='{"count": 3, "complete": true}',
    )
    assert run.returncode == 0, run.stdout + run.stderr
    out = run.stdout
    assert out.index("== 6/8") < out.index(COUNT_LINE.format(3) + "\n") < out.index("== 7/8")
    calls = _calls(tmp_path)
    restart = _first(calls, "up -d --wait")
    clock = _first(calls, "extract(epoch FROM now())")
    (read,) = _sweep_reads(calls)
    assert (
        _first(calls, "dbmate status")
        < clock
        < restart
        < calls.index(read)
        < _first(calls, "bootstrap.smoke")
    )
    # The database's clock from before the restart bounds the row; only count and complete leave the database.
    assert "exec -T postgres psql" in read and "at >= to_timestamp(1763800000.25)" in read
    assert "after->>'count'" in read and "after->>'complete'" in read and "SELECT after " not in read
    assert "ORDER BY id DESC LIMIT 1" in read
    assert not any(w in read for w in ("INSERT", "UPDATE", "DELETE")), read
    assert f"git show {TO_SHA}:services/worker/attachments/files.py" in calls


def test_a239_upgrade_says_when_the_sweep_stopped_part_way_and_still_finishes(tmp_path: Path) -> None:
    run = _upgrade(
        tmp_path,
        FROM="launch-2026-11-20-r2",
        FAKE_SWEEP="1",
        FAKE_SWEEP_AFTER='{"count": 2, "complete": false}',
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert PART_WAY.format(2) + "\n" in run.stdout and "files back to waiting" not in run.stdout
    assert "smoke: all checks passed" in run.stdout and "upgrade: " in run.stdout
    assert json.loads((tmp_path / "data" / "ops" / "installed.json").read_text())["sha"] == TO_SHA


def test_a239_upgrade_says_when_the_worker_did_not_report_and_still_finishes(tmp_path: Path) -> None:
    run = _upgrade(tmp_path, FROM="launch-2026-11-20-r2", FAKE_SWEEP="1", UAT_SWEEP_WAIT_S="0")
    assert run.returncode == 0, run.stdout + run.stderr
    assert NOT_REPORTED.format(0) + "\n" in run.stdout
    assert run.stdout.rstrip().splitlines()[-1].startswith("upgrade: ")
    assert (tmp_path / "data" / "ops" / "installed.json").exists()
    assert "STOPPED" not in run.stderr and "uat-rollback" not in run.stderr
    # IT's runs wait the brief's 120 s: the knob is for these tests only.
    assert 'wait_s="${UAT_SWEEP_WAIT_S:-120}"' in UPGRADE.read_text("utf-8")


def test_a239_upgrade_to_a_build_without_the_sweep_prints_nothing_for_file_checks(tmp_path: Path) -> None:
    """Decided from TO's tree, never FROM's: FROM has the sweep here, TO does not."""
    run = _upgrade(
        tmp_path,
        FROM="launch-2026-11-20-r2",
        FAKE_SWEEP_FROM="1",
        FAKE_SWEEP_AFTER='{"count": 3, "complete": true}',
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "file checks:" not in run.stdout
    calls = _calls(tmp_path)
    assert f"git show {TO_SHA}:services/worker/attachments/files.py" in calls
    assert f"git show {FROM_SHA}:services/worker/attachments/files.py" not in calls
    assert not _sweep_reads(calls) and not any("extract(epoch" in c for c in calls)


def test_a239_upgrade_prints_the_count_only_never_another_key_of_the_row(tmp_path: Path) -> None:
    decoy = "SYN-DECOY-7731"
    run = _upgrade(
        tmp_path,
        FROM="launch-2026-11-20-r2",
        FAKE_SWEEP="1",
        FAKE_SWEEP_AFTER=json.dumps(
            {"count": 1, "complete": True, "note": decoy, "file_id": "ATT-2026-000099"}
        ),
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert COUNT_LINE.format(1) + "\n" in run.stdout
    both = run.stdout + run.stderr
    assert decoy not in both and "ATT-2026-000099" not in both and '"note"' not in both


# ---- BLD-A239: the rehearsal plants files on FROM and checks them after each later phase ---------------------------

FILE_PHASES = (
    "install-from",
    "people-prod",
    "files-from",
    "upgrade",
    "files-upgrade",
    "rollback",
    "files-rollback",
    "upgrade-again",
    "files-again",
)


def _summary(out: str) -> str:
    return out.split("== Summary", 1)[1]


def _rehearse_prod(tmp_path: Path, **extra: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    work = tmp_path / "w"
    env = _env(
        tmp_path,
        FROM="launch-2026-11-20-r3",
        REHEARSE_APP_ENV="prod",
        UPGRADE_REHEARSAL_WORK=str(work),
        **extra,
    )
    shutil.rmtree(tmp_path / "data")
    return _run(["bash", str(REHEARSE)], env), work


def test_a239_rehearsal_plants_three_files_on_from_and_checks_them_after_each_later_phase(
    tmp_path: Path,
) -> None:
    run, work = _rehearse_prod(tmp_path, FAKE_SWEEP="1", FAKE_SWEEP_AFTER='{"count": 1, "complete": true}')
    out = run.stdout
    assert run.returncode == 0, out + run.stderr
    summary = _summary(out)
    rows = [m.group(1) for m in re.finditer(r"^([a-z-]+)\s+PASS\b", summary, re.M)]
    assert rows == list(FILE_PHASES), summary
    assert "rehearsal: upgrade, rollback and upgrade again all passed" in out
    calls = _calls(tmp_path)
    worker = "kfin-ideas-uat-rehearsal-worker-1"
    # files-from: r3's own code in FROM's running worker, fed the driver on stdin, after people-prod.
    plant = _first(calls, f"docker exec -i {worker} python - plant")
    core = _first(calls, "--role core_committee")
    assert core < plant < _first(calls, "dbmate up")
    assert (tmp_path / "state" / "driver.py").read_text() == (UAT / "rehearse_files.py").read_text()
    # The switch is read before each file phase, never set.
    reads = [i for i, c in enumerate(calls) if c == f"docker exec {worker} python -m core.killswitch list"]
    assert len(reads) == 4 and reads[0] < plant
    assert not any("killswitch set" in c for c in calls)
    # The checks read Postgres; the only write is W's poke, once after each upgrade, never into ideas or attachments.
    psql = [c for c in calls if c.startswith("docker exec kfin-ideas-uat-rehearsal-postgres-1 psql ")]
    writes = [c for c in psql if re.search(r"\b(INSERT|UPDATE|DELETE)\b", c)]
    poke = "WITH due AS (UPDATE jobs SET run_at = now() WHERE type = 'file.check'"
    assert len(writes) == 2, writes
    assert all(poke in c and "'ATT-2026-000002'" in c for c in writes), writes
    assert not any("INSERT" in c or "attachments SET" in c or "ideas SET" in c for c in calls)
    ups = [i for i, c in enumerate(calls) if "up -d --wait" in c]
    pokes = [i for i, c in enumerate(calls) if poke in c]
    assert (
        len(ups) == 3 and ups[0] < pokes[0] < ups[1] < ups[2] < pokes[1]
    )  # upgrade, rollback, upgrade-again
    for line in (
        "files: D ATT-2026-000001 on draft",
        "ok: migrations applied now: 1 (TO's migration files that FROM lacks)",
        "ok: file checks: 1 files back to waiting (D)",
        "ok: D ATT-2026-000001 checking, waiting for the gatekeeper; its job queued at 0 tries",
        "ok: W ATT-2026-000002 claimed after that and back to waiting for the gatekeeper",
        "ok: D ATT-2026-000001 upload_failed again (check_failed), as in the backup",
        "ok: hidden_details_source_check and idea_words_sealed_source_check as on launch-2026-11-20-r3 (no teamup)",
    ):
        assert line in out, line
    d_waits = [c for c in psql if "'ATT-2026-000001' AND state = 'queued' AND attempts = 0" in c]
    assert len(d_waits) == 2 and all(
        "last_error = 'waiting_gatekeeper' AND run_at > now()" in c
        and "checks->>'waiting_for' = 'gatekeeper'" in c
        for c in d_waits
    )
    w_claims = [c for c in psql if "locked_at >= to_timestamp(1763800000.25)" in c]
    assert len(w_claims) == 2 and all(
        "attempts < max_attempts AND last_error = 'waiting_gatekeeper'" in c and "state = 'dead'" in c
        for c in w_claims
    )
    assert not work.exists()
    _only_rehearsal_targets(calls, work)


def test_a239_rehearsal_skips_files_from_when_to_has_no_start_sweep_and_can_still_pass(
    tmp_path: Path,
) -> None:
    run, _ = _rehearse_prod(tmp_path, FAKE_SWEEP_FROM="1")
    out = run.stdout
    assert run.returncode == 0, out + run.stderr
    summary = _summary(out)
    assert re.search(r"^files-from\s+SKIPPED\s+TO has no start sweep$", summary, re.M), summary
    for phase in ("files-upgrade", "files-rollback", "files-again"):
        assert phase not in summary
    assert "rehearsal: upgrade, rollback and upgrade again all passed" in out
    calls = _calls(tmp_path)
    assert not any(" python - plant" in c or "postgres-1 psql" in c for c in calls)
    assert f"git show {TO_SHA}:services/worker/attachments/files.py" in calls


@pytest.mark.parametrize(
    ("extra", "row", "stopped"),
    [
        (
            {"FAKE_PLANT_FAIL": "1"},
            "files-from",
            "STOPPED: files-from: D ATT-2026-000001: still checking after 180 s",
        ),
        ({"FAKE_AI_ALL": "on", "FAKE_ROUTE_EXIT": "0"}, "files-from", "STOPPED: ai.all is on, not off"),
        (
            {"FAKE_SWEEP_AFTER": '{"count": 2, "complete": true}'},
            "files-upgrade",
            'STOPPED: upgrade did not print "file checks: 1 files back to waiting …"',
        ),
        (
            {"FAKE_CHECK_FAIL": "id = 'ATT-2026-000003' AND file_state = 'infected'"},
            "files-upgrade",
            "STOPPED: expected: V ATT-2026-000003 still infected",
        ),
    ],
)
def test_a239_rehearsal_stops_on_a_failed_file_check_and_tears_down(
    tmp_path: Path, extra: dict[str, str], row: str, stopped: str
) -> None:
    run, work = _rehearse_prod(
        tmp_path, FAKE_SWEEP="1", **{"FAKE_SWEEP_AFTER": '{"count": 1, "complete": true}', **extra}
    )
    out = run.stdout
    assert run.returncode == 1, out + run.stderr
    assert stopped in out
    assert re.search(rf"^{row}\s+FAIL\b", _summary(out), re.M), out
    assert "rehearsal: FAILED (exit 1)" in out and "all passed" not in out
    assert "rollback " not in _summary(out)
    assert not work.exists()
    _only_rehearsal_targets(_calls(tmp_path), work)


def test_a239_the_rehearsal_driver_uses_r3s_own_code_and_prints_no_file_text_or_name() -> None:
    driver = UAT / "rehearse_files.py"
    tree = ast.parse(driver.read_text("utf-8"))
    imported = {(n.module, a.name) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert {("draft.store", "create"), ("attachments", "files"), ("attachments", "store")} <= imported
    text = driver.read_text("utf-8")
    assert "files.accept(" in text and "INSERT" not in text and "UPDATE attachments" not in text
    assert text.count("UPDATE jobs SET attempts = max_attempts - 1") == 1
    secret = {"TEXT", "NAMES", "EICAR_HALVES", "_data"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("print", "Stop"):
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            assert not names & secret, ast.unparse(node)
    # The antivirus test string is assembled at run time: no file holds it whole.
    halves = next(
        ast.literal_eval(n.value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "EICAR_HALVES"
    )
    whole = "".join(halves)
    assert len(whole) == 68 and whole.startswith("X5O!P%@AP")
    for path in (driver, REHEARSE, UPGRADE, LIB, Path(__file__)):
        assert whole not in path.read_text("utf-8"), path


# ---- BLD-A240: the rehearsal never reports a pass it did not earn ---------------------------------------------------


def test_a240_rehearsal_stopped_by_term_mid_phase_stops_its_own_run_says_so_and_tears_down(
    tmp_path: Path,
) -> None:
    work = tmp_path / "w"
    env = _env(
        tmp_path, FROM="launch-2026-11-20-r2", UPGRADE_REHEARSAL_WORK=str(work), FAKE_DEPLOY_SLEEP="60"
    )
    shutil.rmtree(tmp_path / "data")
    pid_file = tmp_path / "state" / "deploy.pid"
    proc = subprocess.Popen(
        ["bash", str(REHEARSE)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
    )
    try:
        deadline = time.monotonic() + 30
        while not (pid_file.exists() and pid_file.read_text().strip()):
            assert proc.poll() is None and time.monotonic() < deadline, "the held deploy never started"
            time.sleep(0.1)
        deploy = int(pid_file.read_text())
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    assert proc.returncode == 143, out + err
    assert "rehearsal: STOPPED (TERM) after install-from" in out
    assert "all passed" not in out and "rehearsal: FAILED" not in out
    assert re.search(r"^install-from\s+STOPPED\s+stopped by TERM", _summary(out), re.M), out
    assert "stopping the install-from run this rehearsal started" in out
    # The deploy it started is gone (not left running, as on 21 Nov 17:13).
    deadline = time.monotonic() + 10
    while True:
        try:
            os.kill(deploy, 0)
        except ProcessLookupError:
            break
        assert time.monotonic() < deadline, "the deploy the rehearsal started is still running"
        time.sleep(0.1)
    calls = _calls(tmp_path)
    assert any(
        "-p kfin-ideas-uat-rehearsal" in c and "down -v --rmi local --remove-orphans" in c for c in calls
    )
    assert f"git worktree remove {work}/from" in calls and not work.exists()
    assert not any("dbmate up" in c for c in calls)
    assert out.rstrip().endswith("start the dev stack again from the main checkout: make up")


PASS_LINE = "rehearsal: upgrade, rollback and upgrade again all passed"


@pytest.mark.parametrize(
    ("status", "sig", "expected", "rows", "skippable", "line"),
    [
        (0, "", "install-from upgrade", "install-from PASS\nupgrade PASS\n", "", PASS_LINE),
        (0, "", "install-from upgrade", "install-from PASS\n", "", "rehearsal: FAILED (exit 1)"),
        (0, "", "install-from upgrade", "", "", "rehearsal: FAILED (exit 1)"),
        (0, "", "", "", "", "rehearsal: FAILED (exit 1)"),
        (
            0,
            "",
            "install-from upgrade",
            "install-from PASS\nupgrade FAIL\n",
            "",
            "rehearsal: FAILED (exit 1)",
        ),
        (
            2,
            "",
            "install-from upgrade",
            "install-from PASS\nupgrade PASS\n",
            "",
            "rehearsal: FAILED (exit 2)",
        ),
        (0, "", "a files-from b", "a PASS\nfiles-from SKIPPED\nb PASS\n", "files-from", PASS_LINE),
        (0, "", "a files-from b", "a PASS\nfiles-from SKIPPED\nb PASS\n", "", "rehearsal: FAILED (exit 1)"),
        (0, "", "a upgrade", "a PASS\nupgrade SKIPPED\n", "files-from", "rehearsal: FAILED (exit 1)"),
        (0, "", "a upgrade", "a PASS\nupgrade PASS\nupgrade PASS\n", "", "rehearsal: FAILED (exit 1)"),
        (0, "", "a upgrade", "a PASS\nupgrade PASS\nextra PASS\n", "", "rehearsal: FAILED (exit 1)"),
        (
            143,
            "TERM",
            "a upgrade",
            "a PASS\nupgrade STOPPED\n",
            "",
            "rehearsal: STOPPED (TERM) after upgrade",
        ),
    ],
)
def test_a240_the_pass_line_needs_one_pass_row_for_every_expected_phase(
    status: int, sig: str, expected: str, rows: str, skippable: str, line: str
) -> None:
    run = subprocess.run(
        ["bash", "-c", '. "$1"; shift; rehearsal_verdict "$@"', "_", str(LIB), str(status), sig, "upgrade",
         expected, rows, skippable],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert run.stdout == line + "\n", run.stdout + run.stderr
    assert run.returncode == (0 if line == PASS_LINE else 1)


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
    assert 'FROM="$(FROM)" REHEARSE_APP_ENV="$(REHEARSE_APP_ENV)" scripts/uat/rehearse-upgrade.sh' in make
    doc = (helpers.ROOT / "docs" / "UAT.md").read_text("utf-8")
    section = doc.split("## Updating the live server (upgrade and rollback)", 1)[1]
    for words in (
        "FROM=launch-2026-11-20-r3",
        "make uat-upgrade",
        "make uat-rollback",
        "never changes a kill switch",
    ):
        assert words in section
