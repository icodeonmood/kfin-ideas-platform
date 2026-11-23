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

import importlib.util
import os
import re
import shlex
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

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


def test_bld_a248_runbook_is_read_from_the_tag_lane_a_sent() -> None:
    """release/2026-11-20 stays on r3 and has no upgrade section, so IT reads the runbook from the tag it installs."""
    doc = UAT_DOC.read_text("utf-8")
    first = next(p for p in doc.split("\n\n") if p.startswith("**Read this runbook from"))
    assert first.startswith("**Read this runbook from the tag lane A sent you**")
    assert "`git show <tag>:docs/UAT.md`" in first and "git show launch-2026-11-20-r4:docs/UAT.md" in first
    assert "git show origin/release/2026-11-20" not in doc
    assert "`release/2026-11-20` stays on r3 and has no upgrade section" in first


DESK_FILTERS = (  # lane B's `_UNCHECKED` in desk/text_recheck.py (BLD-B278), as a read-only count
    "JOIN question_sets s ON s.id = q.set_id",
    "q.gatekeeper_done_at IS NULL AND s.state <> 'queued'",
    "gatekeeper_done_at IS NULL AND via = 'review_desk' AND note_encrypted IS NOT NULL",
    "gatekeeper_done_at IS NULL AND by_side = 'reviewer' AND note_encrypted IS NOT NULL",
)
DESK_TABLES = {"questions", "idea_decisions", "decision_reversals", "merges", "idea_worth"}


def _words_reads() -> tuple[str, list[str]]:
    section = _section(UAT_DOC.read_text("utf-8"), "Switching to full mode (mode A)")
    step7 = section.split("\n7. **", 1)[1].split("\n8. **", 1)[0]
    return step7, re.findall(r'psql -U ideas -d ideas -c "([^"]+)"', step7.split("Words:", 1)[1])


def test_bld_a248_full_mode_step_7_waits_for_the_words_and_step_8_waits_for_step_7() -> None:
    """BLD-C231 and BLD-B278: the words and the desk's texts typed while the assistant was off are re-checked
    before similar ideas come on."""
    section = _section(UAT_DOC.read_text("utf-8"), "Switching to full mode (mode A)")
    [step1] = [line for line in section.splitlines() if line.startswith("1. **")]
    assert "(BLD-C231, with BLD-C234)" in step1 and "(BLD-B278)" in step1
    assert "the tag that has all five" in step1
    step7, reads = _words_reads()
    order = [
        "FROM jobs WHERE type = 'file.check' GROUP BY 1, 2",
        "Words:",
        "SELECT count(*) FROM idea_words_sealed WHERE gatekeeper_done_at IS NULL",
        "SELECT count(*) FROM (SELECT 1 FROM questions q",
        "SELECT type, state, last_error, run_at <= now() AS due, count(*) FROM jobs "
        "WHERE type IN ('hide.recheck', 'desk.text_recheck') GROUP BY 1, 2, 3, 4",
        "action = 'kill_switch.set' AND entity IN ('kill_switch:ai.all', 'kill_switch:agent.gatekeeper')",
        "a.after->>'source' AS source, a.after->>'code' AS code",
        "LEFT JOIN audit_log a ON a.action = 'hide.recheck_gave_up' AND a.at >= s.since",
        "stay at 5 or fewer",
        "`desk.text_recheck` has at most one row `queued` or `running`",
        "`waiting_gatekeeper` that shows on two reads in a row means a switch is off: go back to step 6",
        "if it is empty, stop and tell lane A",
        "`desk` in the source is a review desk text",
        "Step 8 waits until the first two counts are both 0",
    ]
    positions = [step7.index(s) for s in order]
    assert positions == sorted(positions)
    assert len(reads) == 4
    # The reads print counts, states, sources and codes: never an ID, a name or the text itself.
    forbidden = r"\b(id|idea_id|payload|text|words|entity|actor|before|reason|ip|note_encrypted)\b"
    for sql in reads:
        for columns in re.findall(r"SELECT (.+?) FROM ", sql):
            assert not re.search(forbidden, re.sub(r"count\([^)]*\)", "count", columns)), sql
    desk = reads[1]
    assert set(re.findall(r"FROM (\w+)", desk)) - {"question_sets"} == DESK_TABLES
    assert all(f in desk for f in DESK_FILTERS)
    [step8] = [line for line in section.splitlines() if line.startswith("8. **")]
    assert step8.startswith("8. **Turn on similar ideas**, once step 7's first two counts are both 0.")


def test_bld_a248_desk_count_matches_lane_b_filter_once_b278_is_in() -> None:
    """Once lane B's BLD-B278 is in the build, the runbook's desk count reads the same texts its re-check takes."""
    if importlib.util.find_spec("desk.text_recheck") is None:
        pytest.skip("BLD-B278 is not in this build yet")
    from desk import text_recheck

    assert set(text_recheck.COLUMNS) == DESK_TABLES
    assert all(f in text_recheck._UNCHECKED for f in DESK_FILTERS)
    assert text_recheck.JOB == "desk.text_recheck"


# ---- BLD-A246: the web container never gets the model route's credentials ------------------------------------------

MODEL_CREDENTIALS = (
    "ANTHROPIC_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_BEARER_TOKEN_BEDROCK",
)


class _Loader(yaml.SafeLoader):
    """Reads Compose's !reset and !override tags as plain values (as test_compose_speech.py does)."""


_Loader.add_multi_constructor(
    "!",
    lambda loader, suffix, node: (
        loader.construct_sequence(node)
        if isinstance(node, yaml.SequenceNode)
        else loader.construct_scalar(node)
    ),
)


def _compose(name: str) -> dict[str, Any]:
    text = (helpers.ROOT / "infra" / name).read_text(encoding="utf-8")
    return yaml.load(text, Loader=_Loader)  # noqa: S506 - our own file, a safe loader


@pytest.mark.parametrize("name", ["docker-compose.yml", "uat/compose.uat.yml"])
def test_bld_a246_the_web_container_gets_no_model_credential(name: str) -> None:
    services = _compose(name)["services"]
    web = services["web"]["environment"]
    worker = services["worker"].get("environment") or {}
    for key in MODEL_CREDENTIALS:
        assert web.get(key) == "", (name, key)  # blanked over whatever the env file says
        assert key not in worker, (name, key)  # the worker reads them from its env file, untouched
    assert web["SARVAM_API_KEY"] == "" and web["SPEECH_SERVICE_TOKEN"] == ""  # the earlier blanks stay


def test_bld_a246_the_web_app_reads_no_model_credential() -> None:
    # The blank is safe only while the web app never reads these names (S3 uses S3_ACCESS_KEY and S3_SECRET_KEY).
    src = helpers.ROOT / "apps" / "web" / "src"
    hits = [
        str(p.relative_to(helpers.ROOT))
        for p in src.rglob("*")
        if p.suffix in {".ts", ".tsx", ".js", ".mjs"}
        and not re.search(r"\.(test|spec)\.", p.name)
        and re.search(r"\b(ANTHROPIC_[A-Z_]+|AWS_[A-Z_]+)\b", p.read_text(encoding="utf-8"))
    ]
    assert hits == []


def test_a245_runbook_step_3_follows_live_sh_bld_c229() -> None:
    # Step 3 says what live.sh (lane C, BLD-C229) passes, reads and leaves behind, in its own words; the install count
    # leaves out calls refused while ai.all is off, so there is no quiet window; the key is readable by the docker group
    # while the run lasts. Every quoted line is live.sh's own.
    section = _section(UAT_DOC.read_text(encoding="utf-8"), "Switching to full mode (mode A)")
    step3 = section.split("3. **Run the golden sets", 1)[1].split("4. **The product lead says go.**", 1)[0]
    for line in (
        "`kfin-ideas-eval`",
        "`/srv/kfin-ideas-eval` (it must not exist yet)",
        "only the route's credentials and proxy lines, for the golden sets' container alone",
        "the model settings, for that container and the one that prints the paste block",
        "by `docker exec` into the install's own Postgres",
        "people can keep using 1% Club during the run",
        "`docker inspect`",
        "The `docker` group is as good as root",
        "`=== PASTE FROM HERE ===` to `=== PASTE TO HERE ===`",
        "`STOP: <error> at <step>`",
        "`eval-live refused: …`",
        "`details, for your eyes only and never to paste: …`",
        "`another eval-live run holds /srv/kfin-ideas-eval.lock`",
    ):
        assert line in step3, line
    live_sh = helpers.ROOT / "scripts" / "eval" / "live.sh"
    if live_sh.exists():  # on a tree with BLD-C229 (train 15 and on), the quoted lines are the script's own
        script = live_sh.read_text(encoding="utf-8")
        for text in (
            'say "STOP: $1 at $2"',
            "details, for your eyes only and never to paste:",
            'refuse "another eval-live run holds $EL_LOCK.',
            'SERVER_DATA_DIR="/srv/kfin-ideas-eval"',
            "WHERE outcome <> 'switched_off'",
        ):
            assert text in script, text
    step2 = section.split("2. **Put the route's credentials", 1)[1].split("3. **Run the golden sets", 1)[0]
    for text in (
        "`AWS_REGION` alone is enough",
        "`LLM_FAST_MODEL`",
        "`HTTPS_PROXY`",
        "never gets the key (BLD-A246)",
    ):
        assert text in step2, text
