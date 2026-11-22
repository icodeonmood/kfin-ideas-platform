"""Full mode (mode A) without golden sets on the launch database (BLD-A245; the product lead's rule, 22 Nov 2026).

`scripts/uat/deploy.sh` step 7/8 never runs golden sets in the deployed database, in any APP_ENV: with or without a
model route it switches `ai.all` off (Mode B, audited, `--actor ops:uat-deploy`); with a route it says how full mode
starts instead (lane C's `scripts/eval/live.sh --server` on a throwaway database, then an admin). `upgrade.sh` never
runs them either. `docs/UAT.md` carries the hand steps ("Switching to full mode (mode A)").

No Docker, no make: `docker`, `git` and `make` on PATH are stubs that log each call. Only deploy.sh's own helpers and
the script from step 7/8 to its end run (as `test_a235_deploy_next_line_*` does), so the earlier steps' host checks
never apply.
"""

from __future__ import annotations

import os
import re
import shlex
import stat
import subprocess
from pathlib import Path

import pytest

from bootstrap import preflight
from tests import helpers

UAT = helpers.ROOT / "scripts" / "uat"
DEPLOY, UPGRADE, LIB = UAT / "deploy.sh", UAT / "upgrade.sh", UAT / "lib.sh"
UAT_DOC = helpers.ROOT / "docs" / "UAT.md"
PROJECT = "kfin-ideas-uat"

ROUTE_LINE = (
    "model route configured: golden sets are not run on this database; run scripts/eval/live.sh --server "
    "(UAT.md, Switching to full mode), then an admin switches ai.all on"
)
REASON_NO_ROUTE = "Mode B until InfoSec approves the model route (D1)"  # as before BLD-A245
REASON_ROUTE = "Mode B until scripts/eval/live.sh passes and the product lead says go (BLD-A245)"

# Synthetic app env lines; no real key anywhere.
ROUTES = {
    "anthropic": ["LLM_MODE=anthropic", "ANTHROPIC_API_KEY=test-only-synthetic-not-a-key"],
    "bedrock": ["LLM_MODE=bedrock", "AWS_REGION=ap-south-1"],
}
NO_ROUTES = {
    "fake": ["LLM_MODE=fake"],
    "fake-with-key": ["LLM_MODE=fake", "ANTHROPIC_API_KEY=test-only-synthetic-not-a-key"],  # Capture first
    "anthropic-no-key": ["LLM_MODE=anthropic"],
}

STUB_DOCKER = r"""#!/usr/bin/env bash
printf 'docker %s\n' "$*" >> "$FAKE_LOG"
case "$*" in
  *"bootstrap.preflight ai-route-ready"*) exit "$FAKE_ROUTE_EXIT" ;;
  *evalrunner*|*eval/golden*) echo "golden sets stub ran" ;;
  *"bootstrap.smoke"*) echo "smoke: all checks passed" ;;
esac
exit 0
"""
STUB_GIT = (
    '#!/usr/bin/env bash\n[[ "$*" == "rev-parse HEAD" ]] && { echo ' + "2" * 40 + "; exit 0; }\nexit 1\n"
)
STUB_MAKE = '#!/usr/bin/env bash\nprintf \'make %s\\n\' "$*" >> "$FAKE_LOG"\nexit 97\n'


def _route_exit(lines: list[str]) -> str:
    """What the worker's `preflight ai-route-ready` answers for these settings: the real rule, not a copy of it."""
    env = dict(line.split("=", 1) for line in lines)
    return "0" if preflight.ai_route_ready(env) else "1"


def _deploy_from_step_7(
    tmp_path: Path, app_env: str, lines: list[str]
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    script = DEPLOY.read_text("utf-8")
    assert script.count('\nstep "7/8 ') == 1
    helpers_part = script.split(f'PROJECT="${{UAT_PROJECT:-{PROJECT}}}"\n', 1)[1].split('\nstep "1/8 ', 1)[0]
    assert "compose() {" in helpers_part and "value() {" in helpers_part
    from_step_7 = 'step "7/8 ' + script.split('\nstep "7/8 ', 1)[1]

    app, db = tmp_path / "app.env", tmp_path / "db.env"
    app.write_text("\n".join([f"APP_ENV={app_env}", *lines]) + "\n")
    db.write_text(f"POSTGRES_PASSWORD={'P' * 24}\n")
    stub = tmp_path / "bin"
    stub.mkdir()
    for name, body in (("docker", STUB_DOCKER), ("git", STUB_GIT), ("make", STUB_MAKE)):
        (stub / name).write_text(body)
        (stub / name).chmod(stat.S_IRWXU)
    snippet = "\n".join(
        [
            "set -euo pipefail",
            f"ROOT={shlex.quote(str(tmp_path))}",
            f"APP_ENV_FILE={shlex.quote(str(app))}",
            f"DB_ENV_FILE={shlex.quote(str(db))}",
            f"export UAT_DATA_DIR={shlex.quote(str(tmp_path / 'data'))}",
            f"PROJECT={PROJECT}",
            helpers_part,
            from_step_7,
        ]
    )
    log = tmp_path / "calls.log"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("FAKE_", "UAT_", "COMPOSE_"))}
    env.update(
        PATH=f"{stub}{os.pathsep}{os.environ['PATH']}", FAKE_LOG=str(log), FAKE_ROUTE_EXIT=_route_exit(lines)
    )
    run = subprocess.run(
        ["bash", "-c", snippet],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )
    return run, (log.read_text().splitlines() if log.exists() else [])


def _compose_call(app: Path, db: Path, rest: str) -> str:
    return (
        f"docker compose -p {PROJECT} -f infra/docker-compose.yml -f infra/uat/compose.uat.yml --project-directory . "
        f"--env-file {app} --env-file {db} {rest}"
    )


def _assert_no_golden_sets(run: subprocess.CompletedProcess[str], calls: list[str]) -> None:
    assert not [c for c in calls if "evalrunner" in c or "eval/golden" in c or "switch-off-failing" in c]
    assert not [c for c in calls if c.startswith("make ")]
    assert "golden sets stub ran" not in run.stdout + run.stderr
    assert not [c for c in calls if "ai.all on" in c]


def _assert_tail(run: subprocess.CompletedProcess[str], app_env: str) -> None:
    out = run.stdout
    assert (
        out.index("== 7/8 Model route")
        < out.index("== 8/8 Smoke tests")
        < out.index("smoke: all checks passed")
    )
    if app_env == "prod":
        assert "Next (APP_ENV=prod, no people yet): docs/UAT.md After the deploy, 1a to 2b" in out
    else:
        assert "Next: grant the first admin with" in out


@pytest.mark.parametrize("app_env", ["uat", "prod"])
@pytest.mark.parametrize("route", sorted(ROUTES))
def test_a245_deploy_step_7_with_a_route_switches_ai_all_off_and_never_runs_golden_sets(
    tmp_path: Path, app_env: str, route: str
) -> None:
    lines = ROUTES[route]
    assert _route_exit(lines) == "0"  # the worker would say a route is configured
    run, calls = _deploy_from_step_7(tmp_path, app_env, lines)
    assert run.returncode == 0, run.stdout + run.stderr
    assert ROUTE_LINE in run.stdout.splitlines()
    app, db = tmp_path / "app.env", tmp_path / "db.env"
    off = _compose_call(
        app,
        db,
        f"exec -T worker python -m core.killswitch set ai.all off --reason {REASON_ROUTE} --actor ops:uat-deploy",
    )
    assert [c for c in calls if "core.killswitch" in c] == [off]
    ready = calls.index(_compose_call(app, db, "exec -T worker python -m bootstrap.preflight ai-route-ready"))
    assert ready < calls.index(off) < next(i for i, c in enumerate(calls) if "bootstrap.smoke" in c)
    _assert_no_golden_sets(run, calls)
    _assert_tail(run, app_env)


@pytest.mark.parametrize("app_env", ["uat", "prod"])
@pytest.mark.parametrize("settings", sorted(NO_ROUTES))
def test_a245_deploy_step_7_without_a_route_is_mode_b_as_before(
    tmp_path: Path, app_env: str, settings: str
) -> None:
    lines = NO_ROUTES[settings]
    assert _route_exit(lines) == "1"
    run, calls = _deploy_from_step_7(tmp_path, app_env, lines)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "model route configured" not in run.stdout
    app, db = tmp_path / "app.env", tmp_path / "db.env"
    off = _compose_call(
        app,
        db,
        f"exec -T worker python -m core.killswitch set ai.all off --reason {REASON_NO_ROUTE} --actor ops:uat-deploy",
    )
    assert [c for c in calls if "core.killswitch" in c] == [off]  # the same call as before BLD-A245
    _assert_no_golden_sets(run, calls)
    _assert_tail(run, app_env)


def test_a245_deploy_step_7_has_no_golden_set_mount_and_the_eight_steps_stay() -> None:
    deploy = DEPLOY.read_text("utf-8")
    step7 = deploy.split('step "7/8 Model route"', 1)[1].split('step "8/8 ', 1)[0]
    assert "eval/golden" not in step7 and "evalrunner" not in step7
    assert step7.count("core.killswitch set ai.all off") == 1
    assert "set ai.all on" not in step7
    assert re.findall(r'^step "(\d)/8 ', deploy, re.M) == list("12345678")


# ---- deploy.sh and upgrade.sh never run golden sets ----------------------------------------------------------------

_GOLDEN = re.compile(r"evalrunner|\bmake\b[^;&|\n]*\beval\b")


def _commands(path: Path) -> list[str]:
    """The script's lines without its comment lines (a trailing comment stays: stricter, never looser)."""
    return [
        line
        for line in path.read_text("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_a245_the_golden_set_check_catches_what_it_must() -> None:
    old_step_7 = '  compose run --rm -T -v "$ROOT/eval/golden:/app/eval/golden:ro" worker python -m evalrunner --switch-off-failing \\'
    for line in (old_step_7, "make eval", "  make eval-live", "make -C . eval"):
        assert _GOLDEN.search(line), line
    for line in (
        'echo "run scripts/eval/live.sh --server"',
        "make uat-rollback BACKUP=x",
        "compose exec -T worker python -m bootstrap.preflight ai-route-ready",
    ):
        assert not _GOLDEN.search(line), line


@pytest.mark.parametrize("script", [DEPLOY, UPGRADE, LIB], ids=lambda p: p.name)
def test_a245_deploy_and_upgrade_never_run_golden_sets(script: Path) -> None:
    """lib.sh is in: upgrade.sh sources it, so its lines are upgrade's commands too."""
    commands = _commands(script)
    assert len(commands) > 20
    assert [line for line in commands if _GOLDEN.search(line)] == []


# ---- docs/UAT.md ---------------------------------------------------------------------------------------------------


def _section(doc: str, heading: str) -> str:
    return doc.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def test_a245_runbook_says_what_step_7_does_now() -> None:
    doc = UAT_DOC.read_text("utf-8")
    bold = next(p for p in doc.split("\n\n") if p.startswith("**At launch (Capture first)"))
    assert "switches `ai.all` off whatever the model route" in bold
    assert "never runs the golden sets on the server's database, in any `APP_ENV`" in bold
    assert "`scripts/eval/live.sh`" in bold and "**Switching to full mode (mode A)**" in bold
    assert "**Never switch `ai.all` on while `LLM_MODE=fake`" in bold
    assert "runs the golden sets on the launch database" not in doc
    assert "make eval" not in doc
    after = _section(doc, "After the deploy")
    [step4] = [line for line in after.splitlines() if line.startswith("4. ")]
    assert "**Switching to full mode (mode A)**" in step4


def test_a245_runbook_full_mode_section_in_order_with_paste_backs_and_no_secret() -> None:
    doc = UAT_DOC.read_text("utf-8")
    headings = re.findall(r"^## (.+)$", doc, re.M)
    i = headings.index("Switching to full mode (mode A)")
    assert headings[i - 1] == "Updating the live server (upgrade and rollback)"
    section = _section(doc, "Switching to full mode (mode A)")
    assert re.findall(r"^ ?(\d+)\. \*\*", section, re.M) == [str(n) for n in range(1, 11)]
    order = [
        "BLD-C225 to BLD-C227",
        "git describe --tags --exact-match",
        "`LLM_MODE` stays `fake` for now",
        "sudo scripts/eval/live.sh --server --checkout <release checkout> --project kfin-ideas-uat "
        "--app-env /secure/.env.uat --route anthropic",
        "`=== PASTE FROM HERE ===`",
        "`install database: llm_calls unchanged (N)`",
        "`EVAL-LIVE: PASS`",
        "`EVAL-LIVE: FAIL (gates)`",
        "non-negotiable 5",
        "compose up -d --wait worker web",
        "switches `ai.all` on from the Admin page, with a reason",
        "FROM jobs WHERE type = 'file.check' GROUP BY 1, 2",
        "`waiting_gatekeeper`",
        "**Moving a server from hash to BGE-M3 vectors (BLD-C211)**",
        "`matching.show`",
        "**Email through Graph (BLD-A243)**",
        "python -m bootstrap.smoke --web-url http://web:3000\n",
        "`smoke: all checks passed`",
        "**Back to Capture first**",
    ]
    positions = [section.index(s) for s in order]
    assert positions == sorted(positions)
    assert "--fresh`" in section and "bootstrap.smoke --web-url http://web:3000 --fresh" not in section
    assert "--switch-off-failing" not in section and "evalrunner" not in section
    back = section.split("**Back to Capture first**", 1)[1]
    assert back.index("switches `ai.all` off") < back.index("`LLM_MODE=fake`")
    # Never a real key, address or name: setting names only, no value after them, no key shapes.
    assert not re.search(r"(ANTHROPIC_API_KEY|AWS_[A-Z_]+)=[^.+$ ]", section)
    assert not re.search(r"sk-ant-|AKIA[0-9A-Z]{12,}|@kfintech\.com", section)
