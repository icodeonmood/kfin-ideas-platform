"""BLD-C229 (V-EVAL, AT-B4-03, AT-B5-04): `make eval-live`, the real-model golden sets in the product lead's terminal
and on the launch server.

No database, no Docker, no key: `--only` runs with the runners stood in for; the paste block renders from fixture
reports; and `scripts/eval/live.sh` runs under bash with a stubbed `docker` (and, for the Mac run, a stubbed Python)
that records every call. The refusals happen before any container; a server run touches the install only with the
read-only `SELECT count(*) FROM llm_calls WHERE outcome <> 'switched_off'`; only the golden sets' step gets the route's
credential, by name, never in argv. CI keeps LLM_MODE=fake with no secret and never runs live.sh beyond these tests.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.config import REPO_ROOT
from evalrunner import __main__ as main_mod
from evalrunner import paste

assert REPO_ROOT is not None
ROOT: Path = REPO_ROOT
SCRIPT = ROOT / "scripts" / "eval" / "live.sh"
BASH = shutil.which("bash") or "/bin/bash"
KEY = "synthetic-model-key-c229-not-a-real-key-0000"  # a stand-in: no key exists in any test or session
PROXY = (
    "http://eval:synthetic-proxy-pass@proxy.example:3128"  # a proxy URL can carry a password: never printed
)
SENTENCE = "The branch team keeps typing every SIP mandate in again by hand"  # synthetic case text
INSTALL = "kfin-ideas-uat"
STEP_ENV = {
    "APP_ENV",
    "DATABASE_URL",
    "COMPANY_REPO_PATH",
    "EVAL_REPORTS_DIR",
    "LLM_MODE",
    "EMBEDDINGS_MODE",
    "SPEECH_MODE",
    "KFIN_EMAIL_DOMAINS",
    "VAULT_ENCRYPTION_KEY",
    "PSEUDONYM_VAULT_KEY",
    "CONTRIBUTOR_HMAC_SECRET",
    "INTERNAL_API_TOKEN",
    "SESSION_SECRET",
    "PYTHONDONTWRITEBYTECODE",
}
GENERATED = (
    "VAULT_ENCRYPTION_KEY",
    "PSEUDONYM_VAULT_KEY",
    "CONTRIBUTOR_HMAC_SECRET",
    "INTERNAL_API_TOKEN",
    "SESSION_SECRET",
)


# ---- --only ------------------------------------------------------------------------------------------------------


def _fake_result(agent: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {"cases": 2}
    if agent == "gatekeeper":
        metrics |= {
            "personal_data_recall": 1.0,
            "false_block_rate": 0.0,
            "kind_accuracy": 1.0,
            "pattern_layer_recall": 1.0,
        }
    elif agent == "judge":
        metrics |= {"labels": 4, "same_precision": 1.0, "same_recall": 1.0, "labelled_share": 1.0}
    elif agent == "canvas-assist":
        metrics |= {"submitter_field_changes": 0, "out_of_slice_ids": 0, "neutral_summary_leaks": 0,
                    "area_tag_accuracy": 1.0, "ungrounded_suggestions": 0, "suggestions_dropped": 0}  # fmt: skip
    return {
        "agent": agent,
        "version": "0.0.0",
        "metrics": metrics,
        "model_gates": {},
        "harness_gates": {"ok": True},
    }


@pytest.fixture
def stood_in_runners(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    """Every golden-set runner records its name instead of running; no database is opened."""
    import core.db
    import evalrunner.common as common
    from evalrunner import (
        attachment_digest,
        canvas_assist,
        cluster_summary,
        committee,
        draft_part,
        gatekeeper,
        handover_draft,
        judge,
        prescore,
        role_themes,
    )

    ran: list[str] = []

    def runner(agent: str) -> Any:
        def run(ctx: Any) -> dict[str, Any]:
            ran.append(agent)
            return _fake_result(agent)

        return run

    @contextlib.contextmanager
    def no_db(*_: Any, **__: Any) -> Iterator[object]:
        yield object()

    class Ctx:
        def cleanup(self) -> None:
            return None

    monkeypatch.setattr(core.db, "connect", no_db)
    monkeypatch.setattr(common, "context", lambda conn, seed: Ctx())
    monkeypatch.setattr(common, "route_name", lambda: "fake")
    monkeypatch.setattr(common, "write_report", lambda agent, version, body: tmp_path / f"{agent}.json")
    for module, agent in (
        (gatekeeper, "gatekeeper"),
        (canvas_assist, "canvas-assist"),
        (draft_part, "draft-part"),
        (judge, "judge"),
        (cluster_summary, "cluster-summary"),
        (attachment_digest, "attachment-digest"),
        (handover_draft, "handover-draft"),
        (role_themes, "role-themes"),
        (prescore, "prescore"),
    ):
        monkeypatch.setattr(module, "run", runner(agent))
    monkeypatch.setattr(committee, "run_pitch_prep", runner("pitch-prep"))
    monkeypatch.setattr(committee, "run_collation", runner("collation"))
    monkeypatch.setattr(committee, "run_reason_writer", runner("reason-writer"))
    return ran


def test_v_eval_c229_only_runs_just_the_named_agents_in_the_usual_order(stood_in_runners: list[str]) -> None:
    assert main_mod.run_agents(42, only=main_mod.select_agents("judge, gatekeeper")) == 0
    assert stood_in_runners == ["gatekeeper", "judge"]


def test_v_eval_c229_without_only_every_agent_runs_as_before(stood_in_runners: list[str]) -> None:
    assert main_mod.select_agents(None) == main_mod.AGENT_ORDER
    assert main_mod.run_agents(42) == 0
    assert stood_in_runners == list(main_mod.AGENT_ORDER)


def test_v_eval_c229_main_runs_the_harness_checks_then_only_the_named_agents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evalrunner import speech

    seen: dict[str, Any] = {}
    monkeypatch.setattr(main_mod, "check_golden", lambda: seen.setdefault("golden", []))
    monkeypatch.setattr(main_mod, "check_agents", lambda: seen.setdefault("agents", []))
    monkeypatch.setattr(
        main_mod, "run_agents", lambda seed, switch_off=False, only=(): seen.update(only=only) or 0
    )
    monkeypatch.setattr(speech, "run", lambda: seen.setdefault("speech", True) and 0)
    assert main_mod.main(["--only", "gatekeeper,judge"]) == 0
    assert seen["golden"] == [] and seen["agents"] == []  # the harness checks still ran
    assert seen["only"] == ("gatekeeper", "judge") and "speech" not in seen
    seen.clear()
    assert main_mod.main([]) == 0
    assert seen["only"] == main_mod.AGENT_ORDER and seen["speech"] is True  # unchanged without --only


def test_v_eval_c229_only_refuses_an_unknown_name_before_anything_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    called: list[str] = []

    def harness() -> list[str]:
        called.append("harness")
        return []

    def agents(*_: Any, **__: Any) -> int:
        called.append("agents")
        return 0

    monkeypatch.setattr(main_mod, "check_golden", harness)
    monkeypatch.setattr(main_mod, "run_agents", agents)
    for bad in ("gatekeeper,nope", "", " , "):
        with pytest.raises(SystemExit) as stopped:
            main_mod.main(["--only", bad])
        assert stopped.value.code == 2
    assert called == []
    err = capsys.readouterr().err
    assert "nope" in err and "gatekeeper" in err and "invalid" not in err.lower()


# ---- the paste block ---------------------------------------------------------------------------------------------

PASS_GATES = {
    "gatekeeper": {"personal_data_recall": 1.0, "false_block_rate_max": 0.05, "kind_accuracy_min": 0.85},
    "judge": {"same_precision_min": 0.85, "same_recall_min": 0.75},
}


def gk_report(**gates: bool) -> dict[str, Any]:
    model_gates = {
        "personal_data_recall": True,
        "false_block_rate": True,
        "kind_accuracy": True,
        "injection_held": True,
    }
    model_gates |= gates
    return {
        "agent": "gatekeeper",
        "version": "0.2.0",
        "route": "anthropic",
        "passed": all(model_gates.values()),
        "metrics": {
            "cases": 41,
            "errors": 0,
            "personal_data_recall": 1.0,
            "false_block_rate": 0.0294,
            "kind_accuracy": 0.8824,
            "injection_held": 1.0,
            "pattern_layer_recall": 1.0,
        },
        "model_gates": model_gates,
        "harness_gates": {
            "no_errors": True,
            "pattern_layer_recall": True,
            "pattern_layer_false_blocks": True,
            "pattern_layer_warns": True,
        },
        "cases": [{"id": "gk-001", "text": SENTENCE, "decision": "ok", "kind": "problem"}],
    }


def judge_report(**gates: bool) -> dict[str, Any]:
    model_gates = {"same_precision": True, "same_recall": True} | gates
    return {
        "agent": "judge",
        "version": "0.3.1",
        "route": "anthropic",
        "metrics": {
            "cases": 12,
            "errors": 0,
            "labels": 30,
            "labelled_share": 1.0,
            "same_precision": 0.9,
            "same_recall": 0.8,
        },
        "model_gates": model_gates,
        "harness_gates": {"no_errors": True, "every_candidate_labelled": True},
        "cases": [{"id": "j-001", "labels": {"c1": "same"}, "reason": SENTENCE}],
    }


def meta(**over: Any) -> paste.Meta:
    base: dict[str, Any] = {
        "mode": "mac",
        "route": "anthropic",
        "fast_model": "claude-haiku-5-5",
        "reasoning_model": "claude-sonnet-5-5",
        "checkout_sha": "a" * 40,
        "at": dt.datetime(2026, 11, 23, 4, 30, tzinfo=dt.UTC),
    }
    return paste.Meta(**(base | over))


CALLS = paste.Calls(rows=53, reached_model=53, cost_inr=12.3456, answered=52)


def row(lines: list[str], name: str) -> tuple[int, str]:
    hits = [(i, line) for i, line in enumerate(lines) if line.startswith(name + " ")]
    assert len(hits) == 1, (name, lines)
    return hits[0]


def test_at_b4_03_at_b5_04_c229_paste_block_rows_lead_first_numbers_only() -> None:
    reports = {"gatekeeper": gk_report(), "judge": judge_report()}
    lines, passed = paste.render(reports, PASS_GATES, CALLS, meta())
    text = "\n".join(lines)
    assert passed and lines[0] == paste.BEGIN and lines[-1] == paste.END and lines[-2] == "EVAL-LIVE: PASS"
    recall, false_block, precision = (
        row(lines, "gatekeeper personal_data_recall"),
        row(lines, "gatekeeper false_block_rate"),
        row(lines, "judge same_precision"),
    )
    others = [
        row(lines, n) for n in ("gatekeeper kind_accuracy", "gatekeeper injection_held", "judge same_recall")
    ]
    assert (
        recall[0] < false_block[0] < precision[0] < min(i for i, _ in others)
    )  # the lead's three come first
    assert "100.0%" in recall[1] and ">=100.0%" in recall[1] and recall[1].endswith("PASS")
    assert "2.9%" in false_block[1] and "<=5.0%" in false_block[1] and false_block[1].endswith("PASS")
    assert "90.0%" in precision[1] and ">=85.0%" in precision[1] and precision[1].endswith("PASS")
    assert all(line.endswith("PASS  also gated") for _, line in others)
    assert ">=75.0%" in row(lines, "judge same_recall")[1]
    assert "checkout: " + "a" * 40 in text and "route: anthropic" in text
    assert "fast model: claude-haiku-5-5" in text and "reasoning model: claude-sonnet-5-5" in text
    assert "time: 23 Nov 2026 10:00 IST" in text
    assert "agent gatekeeper 0.2.0: 41 cases" in text and "agent judge 0.3.1: 12 cases" in text
    assert "harness gates: gatekeeper 4/4 PASS | judge 2/2 PASS" in text
    assert "model calls: 53 (52 answered; llm_calls rows: 53) | cost: INR 12.35" in text
    assert "installed:" not in text and "install database" not in text  # Mac: no install lines
    assert SENTENCE not in text and "SIP mandate" not in text  # no case text, ever
    assert "://" not in text and KEY not in text
    assert text.isascii()


def test_at_b5_04_c229_paste_block_fail_names_the_gates_lead_first() -> None:
    reports = {"gatekeeper": gk_report(kind_accuracy=False), "judge": judge_report(same_precision=False)}
    lines, passed = paste.render(reports, PASS_GATES, CALLS, meta())
    assert not passed
    assert row(lines, "judge same_precision")[1].endswith("FAIL")
    assert row(lines, "gatekeeper kind_accuracy")[1].endswith("FAIL  also gated")
    assert lines[-2] == "EVAL-LIVE: FAIL (judge.same_precision, gatekeeper.kind_accuracy)"


def test_at_b4_03_c229_paste_block_fails_without_a_report_on_another_route_or_a_failed_run() -> None:
    lines, passed = paste.render({"gatekeeper": gk_report()}, PASS_GATES, None, meta())
    assert not passed and row(lines, "judge same_precision")[1].endswith("FAIL (no report)")
    assert "model calls: not counted" in lines
    assert lines[-2] == "EVAL-LIVE: FAIL (judge.no_report, model.no_calls)"
    faked = gk_report() | {"route": "fake"}
    lines, passed = paste.render({"gatekeeper": faked, "judge": judge_report()}, PASS_GATES, CALLS, meta())
    assert not passed and lines[-2] == "EVAL-LIVE: FAIL (gatekeeper.route_not_anthropic)"
    harness = gk_report()
    harness["harness_gates"]["no_errors"] = False
    lines, passed = paste.render({"gatekeeper": harness, "judge": judge_report()}, PASS_GATES, CALLS, meta())
    assert not passed and "gatekeeper 3/4 PASS (no_errors FAIL)" in "\n".join(lines)
    assert lines[-2] == "EVAL-LIVE: FAIL (gatekeeper.harness.no_errors)"
    reports = {"gatekeeper": gk_report(), "judge": judge_report()}
    lines, passed = paste.render(reports, PASS_GATES, CALLS, meta(eval_exit=1))
    assert not passed and lines[-2] == "EVAL-LIVE: FAIL (evalrunner.exit_1)"


def test_v_eval_c229_a_run_the_model_never_answered_cannot_pass() -> None:
    """Every gate's boolean can read PASS while no call reached the model (a fake route, every call refused or a route
    error): `model.no_calls` then fails the run, as it does when the calls were not counted."""
    reports = {"gatekeeper": gk_report(), "judge": judge_report()}
    silent = paste.Calls(rows=53, reached_model=53, cost_inr=0.0, answered=0)  # every call a route_error
    lines, passed = paste.render(reports, PASS_GATES, silent, meta())
    assert not passed and lines[-2] == "EVAL-LIVE: FAIL (model.no_calls)"
    assert "model calls: 53 (0 answered; llm_calls rows: 53) | cost: INR 0.00" in lines
    lines, passed = paste.render(reports, PASS_GATES, None, meta())
    assert not passed and lines[-2] == "EVAL-LIVE: FAIL (model.no_calls)"
    one = paste.Calls(rows=1, reached_model=1, cost_inr=0.01, answered=1)
    assert paste.render(reports, PASS_GATES, one, meta())[1]


def test_at_b4_03_c229_server_block_shows_the_install_and_fails_if_its_llm_calls_moved() -> None:
    reports = {"gatekeeper": gk_report(), "judge": judge_report()}
    same = meta(mode="server", installed_tag="launch-2026-11-23-r5", installed_sha="b" * 40, install_before=7,
                install_after=7)  # fmt: skip
    lines, passed = paste.render(reports, PASS_GATES, CALLS, same)
    text = "\n".join(lines)
    assert passed and "installed: launch-2026-11-23-r5 at " + "b" * 40 in text and "checkout:" not in text
    assert lines[-3] == "install database: llm_calls unchanged (7)" and lines[-2] == "EVAL-LIVE: PASS"
    moved = meta(mode="server", installed_sha="b" * 40, install_before=7, install_after=8)
    lines, passed = paste.render(reports, PASS_GATES, CALLS, moved)
    assert not passed and "install database: llm_calls CHANGED (7 to 8)" in lines
    assert lines[-2] == "EVAL-LIVE: FAIL (install.llm_calls_changed)"


def test_v_eval_c229_paste_main_reads_the_report_json_and_the_gates_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "gatekeeper-0.2.0-20261123-043000.json").write_text(json.dumps(gk_report()))
    (tmp_path / "judge-0.3.1-20261123-043500.json").write_text(json.dumps(judge_report()))
    (tmp_path / "judge-x-20991231-000000.json").write_text(
        json.dumps({"agent": "canvas-assist"})
    )  # not judge's
    monkeypatch.setattr(paste, "count_calls", lambda: CALLS)
    args = ["--reports", str(tmp_path), "--route", "anthropic", "--mode", "mac", "--checkout-sha", "c" * 40]
    assert paste.main(args) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == paste.BEGIN and out[-1] == paste.END and out[-2] == "EVAL-LIVE: PASS"
    assert "<=5.0%" in row(out, "gatekeeper false_block_rate")[1]  # from agents/gatekeeper/config.yaml
    assert paste._gates_of("gatekeeper")["false_block_rate_max"] == 0.05
    assert paste._gates_of("judge")["same_precision_min"] == 0.85
    assert paste.main([*args, "--eval-exit", "1"]) == 1


# ---- scripts/eval/live.sh under bash, with stubbed docker and python ---------------------------------------------

STUB = r"""
import json, os, sys
from pathlib import Path

here = Path(__file__).parent
cfg = json.loads((here / "scenario.json").read_text())
tool, argv = sys.argv[1], sys.argv[2:]
names = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "-e"]
record = {"tool": tool, "argv": argv, "env_names": sorted(os.environ), "named": {n: os.environ.get(n) for n in names},
          "key": os.environ.get("ANTHROPIC_API_KEY"), "cwd": os.getcwd()}
if tool == "python":
    for n in ("DATABASE_URL", "LLM_MODE", "COMPANY_REPO_PATH", "EVAL_REPORTS_DIR", "VAULT_ENCRYPTION_KEY"):
        record["named"][n] = os.environ.get(n)
with open(here / "calls.jsonl", "a") as f:
    f.write(json.dumps(record) + "\n")
if cfg.get("fail_if_called"):
    sys.exit(99)
joined = " ".join(argv)
block = "\n".join(cfg.get("block", ["=== PASTE FROM HERE ===", "EVAL-LIVE: PASS", "=== PASTE TO HERE ==="]))
if tool == "python":
    if "evalrunner.paste" in joined:
        print(block)
    sys.exit(0)
if tool == "chown":
    sys.exit(0)
if argv[:3] == ["compose", "ls", "-a"]:
    print("\n".join(cfg.get("all_projects", [])))
elif argv[:2] == ["compose", "ls"]:
    print("\n".join(cfg.get("running", [])))
elif argv[:1] == ["ps"]:
    if "label=com.docker.compose.service=postgres" in argv:
        print("pg0000000001")
elif argv[:2] in (["volume", "ls"], ["network", "ls"]):
    print("\n".join(cfg.get("volumes", [])) if argv[0] == "volume" else "")
elif argv[:2] == ["image", "inspect"]:
    sys.exit(1 if cfg.get("image_missing") else 0)
elif argv[:1] == ["run"]:
    if "import evalrunner.paste" in joined:
        sys.exit(1 if cfg.get("image_old") else 0)
    if "evalrunner.paste" in joined:
        print(block)
elif argv[:1] == ["exec"]:
    counts = cfg["install_counts"]
    seen = here / "counts-used"
    n = len(seen.read_text().splitlines()) if seen.exists() else 0
    seen.write_text("x\n" * (n + 1))
    print(counts[min(n, len(counts) - 1)])
elif argv[:1] == ["compose"]:
    if " port postgres 5432" in joined:
        print("127.0.0.1:55447")
    elif "dbmate status" in joined:
        print("Applied: 90\nPending: 0")
sys.exit(0)
"""


@pytest.fixture
def stubs(tmp_path: Path) -> Path:
    """A folder for PATH with `docker`, `chown` and `python` stand-ins that record each call in calls.jsonl."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "stub.py").write_text(STUB)
    for tool in ("docker", "chown", "python"):
        path = bin_dir / tool
        path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bin_dir / "stub.py"}" {tool} "$@"\n')
        path.chmod(0o755)
    scenario(bin_dir)
    return bin_dir


def scenario(bin_dir: Path, **cfg: Any) -> None:
    (bin_dir / "scenario.json").write_text(json.dumps({"install": INSTALL, "install_counts": [7]} | cfg))


def calls(bin_dir: Path) -> list[dict[str, Any]]:
    path = bin_dir / "calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run_live(
    bin_dir: Path, *args: str, env: dict[str, str] | None = None, trace: bool = False
) -> subprocess.CompletedProcess[str]:
    tmp = bin_dir.parent / "t"
    tmp.mkdir(exist_ok=True)
    base = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(bin_dir.parent),
        "TMPDIR": str(tmp),
        "LANG": "C.UTF-8",
    }
    cmd = [BASH, *(["-x"] if trace else []), str(SCRIPT), *args]
    return subprocess.run(
        cmd, env=base | (env or {}), capture_output=True, text=True, timeout=120, check=False
    )


def leftovers(bin_dir: Path) -> list[str]:
    return sorted(p.name for p in (bin_dir.parent / "t").iterdir())


@pytest.mark.parametrize(
    ("env", "args", "says"),
    [
        ({"CI": "true", "ANTHROPIC_API_KEY": KEY}, [], "never runs in CI"),
        ({}, [], "ANTHROPIC_API_KEY is not set in this terminal"),
        (
            {"ANTHROPIC_API_KEY": KEY, "ANTHROPIC_BASE_URL": "http://127.0.0.1:9"},
            [],
            "ANTHROPIC_BASE_URL is set",
        ),
        ({"ANTHROPIC_API_KEY": KEY, "ANTHROPIC_BEDROCK_MANTLE_BASE_URL": ""}, [], "MANTLE_BASE_URL is set"),
        ({"ANTHROPIC_API_KEY": KEY}, ["--route", "openai"], "the route must be anthropic or bedrock"),
        ({"ANTHROPIC_API_KEY": KEY}, ["--route", "bedrock"], "the Bedrock route needs AWS_REGION"),
        ({"AWS_ACCESS_KEY_ID": "synthetic-id"}, ["--route", "bedrock"], "the Bedrock route needs AWS_REGION"),
        (
            {"AWS_ACCESS_KEY_ID": "synthetic-id", "AWS_REGION": "ap-south-1"},
            ["--route", "bedrock"],
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY go together",
        ),
        ({"ANTHROPIC_API_KEY": KEY}, ["--checkout", "/tmp"], "for --server only"),
    ],
)
def test_v_eval_c229_live_sh_refuses_before_any_container(
    stubs: Path, env: dict[str, str], args: list[str], says: str
) -> None:
    scenario(stubs, fail_if_called=True)
    done = run_live(stubs, *args, env=env)
    assert done.returncode == 2, done.stdout + done.stderr
    assert says in done.stdout and "eval-live refused: " in done.stdout
    assert calls(stubs) == []  # docker (and python) never called
    assert KEY not in done.stdout + done.stderr
    assert leftovers(stubs) == []


def test_v_eval_c229_bedrock_takes_aws_region_alone_as_the_install_preflight_does(stubs: Path) -> None:
    """Lane A's decision: an instance role gives the credentials, so AWS_REGION alone gets past the refusals (the run
    goes on to ask Docker, which this stub refuses, so it stops there)."""
    scenario(stubs, fail_if_called=True)
    done = run_live(stubs, "--route", "bedrock", env={"AWS_REGION": "ap-south-1"})
    assert "eval-live refused" not in done.stdout, done.stdout
    assert done.returncode == 1 and "STOP: docker did not answer at checks" in done.stdout
    assert calls(stubs) and calls(stubs)[0]["argv"][:2] == ["compose", "ls"]


def test_v_eval_c229_live_sh_never_traces_the_key_even_under_bash_x(stubs: Path) -> None:
    scenario(stubs, fail_if_called=True)
    done = run_live(
        stubs, env={"ANTHROPIC_API_KEY": KEY, "ANTHROPIC_BASE_URL": "http://127.0.0.1:9"}, trace=True
    )
    assert done.returncode == 2 and KEY not in done.stdout + done.stderr
    assert calls(stubs) == []


def test_v_eval_c229_mac_run_throwaway_database_and_the_key_for_the_golden_sets_only(stubs: Path) -> None:
    reports_before = (
        sorted(p.name for p in (ROOT / "eval" / "reports").glob("*"))
        if (ROOT / "eval" / "reports").exists()
        else []
    )
    env = {
        "ANTHROPIC_API_KEY": KEY,
        "SARVAM_API_KEY": "synthetic-sarvam-key-never-passed",
        "PYTHONPATH": "/nowhere",
        "EVAL_LIVE_PYTHON": str(stubs / "python"),
        "LLM_REASONING_MODEL": "claude-sonnet-5-5",  # the terminal's model setting is kept (fix 3)
        "HTTPS_PROXY": PROXY,  # the golden sets only (lane A's decision)
    }
    done = run_live(stubs, env=env)
    assert done.returncode == 0, done.stdout + done.stderr
    out = done.stdout.splitlines()
    assert out[out.index("=== PASTE TO HERE ===") - 1] == "EVAL-LIVE: PASS"
    assert out[-1].startswith("cleaned up: project kfin-eval-live")  # after the block, outside the paste
    recorded = calls(stubs)
    py = [c for c in recorded if c["tool"] == "python"]
    assert [c["argv"][:2] for c in py] == [["-m", "bootstrap.seed"]] + [["-m", "core.killswitch"]] * 3 + [
        ["-m", "evalrunner"],
        ["-m", "evalrunner.paste"],
    ]
    switches = [c["argv"][3] for c in py if c["argv"][1] == "core.killswitch"]
    assert switches == ["ai.all", "agent.gatekeeper", "agent.judge"]
    assert all(c["argv"][4:5] == ["on"] and c["argv"][-2:] == ["--actor", "process:eval"] for c in py[1:4])
    golden = py[4]
    assert golden["argv"] == ["-m", "evalrunner", "--only", "gatekeeper,judge"]  # no --switch-off-failing
    allowed = {
        "PATH",
        "HOME",
        "TMPDIR",
        "LANG",
        "_",
        "PWD",
        "OLDPWD",
        "SHLVL",
        "LC_CTYPE",
        "__CF_USER_TEXT_ENCODING",
    } | STEP_ENV
    allowed |= {"LLM_FAST_MODEL", "LLM_REASONING_MODEL", "LLM_REFUSAL_FALLBACK"}
    assert "LLM_REASONING_MODEL" in golden["env_names"]
    for c in py:
        extra = set(c["env_names"]) - allowed - ({"ANTHROPIC_API_KEY"} if c is golden else set())
        assert not extra, (c["argv"], extra)
        assert c["named"]["DATABASE_URL"].startswith("postgres://ideas:")
        assert c["named"]["DATABASE_URL"].endswith("@127.0.0.1:55447/ideas?sslmode=disable")
        assert c["named"]["LLM_MODE"] == ("anthropic" if c is golden else "fake")
        for n in ("COMPANY_REPO_PATH", "EVAL_REPORTS_DIR"):
            assert c["named"][n].startswith(str(stubs.parent / "t")), n  # a temp folder, never the repo
        assert c["key"] == (KEY if c is golden else None)
    docker = [c for c in recorded if c["tool"] == "docker"]
    assert docker and all(c["key"] is None for c in docker)  # docker never holds the key
    assert all("HTTPS_PROXY" not in c["env_names"] for c in docker)  # nor the proxy
    assert [c["argv"][:2] for c in py if "HTTPS_PROXY" in c["env_names"]] == [["-m", "evalrunner"]]
    assert PROXY not in done.stdout + done.stderr
    compose = [c for c in docker if c["argv"][:1] == ["compose"] and "-p" in c["argv"]]
    assert {c["argv"][c["argv"].index("-p") + 1] for c in compose} == {"kfin-eval-live"}
    assert any(c["argv"][-3:] == ["down", "-v", "--remove-orphans"] for c in compose)
    assert any(c["argv"][-6:] == ["up", "-d", "--wait", "--wait-timeout", "120", "postgres"] for c in compose)
    assert all(KEY not in json.dumps(c["argv"]) for c in recorded)
    assert all("synthetic-sarvam" not in json.dumps(c) for c in recorded)
    assert leftovers(stubs) == []  # temp folders and the error file are gone after a PASS
    after = (
        sorted(p.name for p in (ROOT / "eval" / "reports").glob("*"))
        if (ROOT / "eval" / "reports").exists()
        else []
    )
    assert after == reports_before


def server_args(tmp_path: Path, **over: str) -> list[str]:
    values = {
        "--checkout": str(ROOT),
        "--project": INSTALL,
        "--app-env": str(tmp_path / "app.env"),
        "--route": "anthropic",
        "--data-dir": str(tmp_path / "srv" / "kfin-ideas-eval"),
    } | over
    return ["--server", *[x for k, v in values.items() for x in (k, v)]]


INSTALL_VALUES = {
    "VAULT_ENCRYPTION_KEY": "install-vault-key-synthetic-0000000000000000",
    "SARVAM_API_KEY": "install-sarvam-key-synthetic",
    "INTERNAL_API_TOKEN": "install-internal-token-synthetic-0000000000",
}


@pytest.fixture
def app_env(tmp_path: Path) -> Path:
    (tmp_path / "srv").mkdir()
    path = tmp_path / "app.env"
    lines = [
        "APP_ENV=prod",
        "LLM_MODE=fake",
        f'ANTHROPIC_API_KEY="{KEY}"   # from the vault',
        'LLM_FAST_MODEL="claude-haiku-5-5"   # the install\'s own model setting',
        "LLM_REFUSAL_FALLBACK=false",
        f"HTTPS_PROXY={PROXY}",
        "no_proxy=localhost,127.0.0.1",
    ]
    path.write_text("\n".join(lines + [f"{k}={v}" for k, v in INSTALL_VALUES.items()]) + "\n")
    return path


def install_calls(recorded: list[dict[str, Any]]) -> list[list[str]]:
    """Every docker call that acts on the install: an exec into a container, or compose with the install's name."""
    return [
        c["argv"]
        for c in recorded
        if c["tool"] == "docker"
        and (
            c["argv"][:1] == ["exec"]
            or ("-p" in c["argv"] and c["argv"][c["argv"].index("-p") + 1] == INSTALL)
        )
    ]


# `docker exec` into the install's Postgres container, found by its compose labels (no compose model): the only command.
COUNT = ["exec", "pg0000000001", "psql", "-U", "ideas", "-d", "ideas", "-At", "-c",
         "SELECT count(*) FROM llm_calls WHERE outcome <> 'switched_off'"]  # fmt: skip


def test_at_b4_03_c229_server_run_reads_the_install_only_and_passes_only_the_key(
    stubs: Path, app_env: Path, tmp_path: Path
) -> None:
    scenario(stubs, running=[INSTALL, "other-project"], install_counts=[7, 7])
    done = run_live(stubs, *server_args(tmp_path))
    assert done.returncode == 0, done.stdout + done.stderr
    recorded = calls(stubs)
    assert install_calls(recorded) == [
        COUNT,
        COUNT,
    ]  # before and after: the only commands sent to the install
    pgs = [
        c["argv"]
        for c in recorded
        if c["argv"][:1] == ["ps"] and "label=com.docker.compose.service=postgres" in c["argv"]
    ]
    assert len(pgs) == 2 and all(
        f"label=com.docker.compose.project={INSTALL}" in a for a in pgs
    )  # resolved twice
    runs = [c for c in recorded if c["tool"] == "docker" and c["argv"][:1] == ["run"]]
    probe, steps = runs[0], runs[1:]
    assert probe["argv"][-4:] == [f"{INSTALL}-worker", "python", "-c", "import evalrunner.paste"]
    assert "--network" in probe["argv"] and probe["argv"][probe["argv"].index("--network") + 1] == "none"
    assert [s["argv"][s["argv"].index(f"{INSTALL}-worker") + 1 :][:3] for s in steps] == [
        ["python", "-m", "bootstrap.seed"],
        ["python", "-m", "core.killswitch"],
        ["python", "-m", "core.killswitch"],
        ["python", "-m", "core.killswitch"],
        ["python", "-m", "evalrunner"],
        ["python", "-m", "evalrunner.paste"],
    ]
    for s in steps:
        argv = s["argv"]
        assert (
            argv[argv.index("--network") + 1] == "kfin-ideas-eval_default"
        )  # the eval project's network only
        golden = "evalrunner" in argv and "--only" in argv
        measured = golden or "evalrunner.paste" in argv  # the golden sets and the paste block's model line
        names = set(s["named"])
        models = {"LLM_FAST_MODEL", "LLM_REFUSAL_FALLBACK"} if measured else set()  # the file's, when set
        proxies = {"HTTPS_PROXY", "no_proxy"} if golden else set()  # the file's proxies, golden sets only
        assert names == STEP_ENV | ({"ANTHROPIC_API_KEY"} if golden else set()) | models | proxies
        if golden:
            assert s["named"]["HTTPS_PROXY"] == PROXY and s["named"]["no_proxy"] == "localhost,127.0.0.1"
        if measured:
            assert s["named"]["LLM_FAST_MODEL"] == "claude-haiku-5-5"
            assert s["named"]["LLM_REFUSAL_FALLBACK"] == "false"
        assert s["named"].get("ANTHROPIC_API_KEY") == (KEY if golden else None)
        assert s["named"]["DATABASE_URL"].startswith("postgres://ideas:")
        assert s["named"]["DATABASE_URL"].endswith("@postgres:5432/ideas?sslmode=disable")
        assert s["named"]["LLM_MODE"] == ("anthropic" if golden else "fake")
        for n in GENERATED:
            assert len(s["named"][n] or "") == 48 and s["named"][n] not in INSTALL_VALUES.values()
        assert "SARVAM_API_KEY" not in names
    for c in recorded:
        dumped = json.dumps(c["argv"])
        assert KEY not in dumped and PROXY not in dumped
        assert not any(v in json.dumps(c["named"]) for v in INSTALL_VALUES.values())
    assert not [c for c in recorded if c["tool"] == "docker" and c["key"] and c not in steps]
    assert [c for c in recorded if "HTTPS_PROXY" in c["env_names"]] == [
        s for s in steps if "--only" in s["argv"]
    ]
    assert PROXY not in done.stdout + done.stderr
    paste_argv = steps[-1]["argv"]
    assert paste_argv[paste_argv.index("--install-before") + 1] == "7"
    assert paste_argv[paste_argv.index("--install-after") + 1] == "7"
    assert paste_argv[paste_argv.index("--mode") : paste_argv.index("--mode") + 2] == ["--mode", "server"]
    eval_compose = [
        c["argv"] for c in recorded if c["tool"] == "docker" and "kfin-ideas-eval" in c["argv"][:3]
    ]
    assert any(a[-3:] == ["down", "-v", "--remove-orphans"] for a in eval_compose)
    assert [c["argv"] for c in recorded if c["tool"] == "chown"] == [
        ["10001:10001", str(tmp_path / "srv" / "kfin-ideas-eval")]
    ]
    assert not (tmp_path / "srv" / "kfin-ideas-eval").exists() and leftovers(stubs) == []


def test_at_b4_03_c229_server_run_fails_when_the_install_llm_calls_moved(
    stubs: Path, app_env: Path, tmp_path: Path
) -> None:
    scenario(stubs, running=[INSTALL], install_counts=[7, 8])  # the stand-in paste block still says PASS
    done = run_live(stubs, *server_args(tmp_path))
    assert done.returncode == 1
    paste_argv = [c["argv"] for c in calls(stubs) if "evalrunner.paste" in c["argv"]][-1]
    assert paste_argv[paste_argv.index("--install-after") + 1] == "8"
    assert install_calls(calls(stubs)) == [COUNT, COUNT]


@pytest.mark.parametrize(
    ("over", "cfg", "says"),
    [
        ({"--checkout": "relative/checkout"}, {}, "must be absolute paths"),
        ({"--app-env": "app.env"}, {}, "must be absolute paths"),
        ({"--project": "kfin-ideas"}, {}, "dev stack"),
        ({"--project": "Bad Name"}, {}, "compose project name"),
        ({}, {"all_projects": ["kfin-ideas-eval"]}, "kfin-ideas-eval project"),
        ({}, {"volumes": ["kfin-ideas-eval_pgdata"]}, "kfin-ideas-eval project"),
        ({}, {"image_missing": True}, "worker image kfin-ideas-uat-worker is missing"),
        ({}, {"running": ["other-project"]}, "is not running"),
        ({}, {"running": [INSTALL], "image_old": True}, "has no make eval-live"),
    ],
)
def test_v_eval_c229_server_refusals_never_start_or_touch_anything(
    stubs: Path, app_env: Path, tmp_path: Path, over: dict[str, str], cfg: dict[str, Any], says: str
) -> None:
    scenario(stubs, **({"running": [INSTALL]} | cfg))
    done = run_live(stubs, *server_args(tmp_path, **over))
    assert done.returncode == 2, done.stdout + done.stderr
    assert says in done.stdout
    recorded = calls(stubs)
    assert install_calls(recorded) == []
    for c in recorded:
        argv = c["argv"]
        assert not ({"up", "down", "restart", "exec", "stop", "rm"} & set(argv)), argv
        assert (
            argv[:1] != ["run"] or "import evalrunner.paste" in argv
        )  # only the image probe, with no network
    assert not (tmp_path / "srv" / "kfin-ideas-eval").exists()


def test_v_eval_c229_server_refuses_an_existing_data_folder_a_missing_key_and_a_base_url(
    stubs: Path, app_env: Path, tmp_path: Path
) -> None:
    scenario(stubs, fail_if_called=True)
    data = tmp_path / "srv" / "kfin-ideas-eval"
    data.mkdir()
    done = run_live(stubs, *server_args(tmp_path))
    assert done.returncode == 2 and "already exists" in done.stdout and data.exists()
    data.rmdir()
    app_env.write_text("APP_ENV=prod\nLLM_MODE=fake\nANTHROPIC_API_KEY=\n")
    done = run_live(
        stubs, *server_args(tmp_path), env={"ANTHROPIC_API_KEY": KEY}
    )  # the shell's key never counts
    assert done.returncode == 2 and "ANTHROPIC_API_KEY is not set in the app env file" in done.stdout
    app_env.write_text(f"ANTHROPIC_API_KEY={KEY}\nANTHROPIC_BASE_URL=http://proxy.example:8080\n")
    done = run_live(stubs, *server_args(tmp_path))
    assert done.returncode == 2 and "ANTHROPIC_BASE_URL is set in the app env file" in done.stdout
    assert calls(stubs) == [] and KEY not in done.stdout + done.stderr


def test_v_eval_c229_ci_keeps_the_fake_route_and_never_runs_eval_live() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert any(line.split("#")[0].strip() == "LLM_MODE=fake" for line in env_example)
    assert any(line.strip() == "ANTHROPIC_API_KEY=" for line in env_example)
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        assert "eval-live" not in text and "live.sh" not in text and "${{ secrets." not in text, workflow.name
        assert "ANTHROPIC_API_KEY" not in text and "AWS_SECRET_ACCESS_KEY" not in text, workflow.name
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "eval-live:" in makefile and "eval-live" in makefile.split(".PHONY:")[1].splitlines()[0]
    recipe = makefile.split("\neval-live:")[1].split("\n\n")[0]
    assert "ANTHROPIC_API_KEY" not in recipe and "AWS_" not in recipe  # the key is never on a command line
