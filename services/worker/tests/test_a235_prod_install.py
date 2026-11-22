"""Production mode at install (BLD-A235; the product lead's order, 20 Nov 02:12; L-AUTH.rules/6, L-AUTH.rules/7).

With `APP_ENV=prod`, and only then, the install loads no synthetic people and grants nothing; the fresh smoke check
passes only with no people and no role grants, and the later one only with people. IT loads HR's file through stdin
with `identity.hr_import -` after the first admin (docs/UAT.md). Every other environment is unchanged (lane E's
condition): dev, test, CI, uat, `make seed`, the journeys' env defaults and `.env.example`.

Unit level only: settings, the database and `import_rows` are stubbed. No stack, no docker, no make.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bootstrap import preflight, seed, smoke, synthetic_hr
from identity import hr_import
from identity.hr_import import HEADER, ImportResult, read_stream
from tests import helpers

REHEARSE = helpers.ROOT / "scripts" / "uat" / "rehearse.sh"
DEPLOY = helpers.ROOT / "scripts" / "uat" / "deploy.sh"
# APP_ENV values preflight passes as prod (it strips, case-sensitive): each one is production mode (review nit).
PROD_VALUES = ["prod", " prod ", "prod\n", "\tprod"]
UAT_DOC = helpers.ROOT / "docs" / "UAT.md"


def _people(n: int) -> list[dict[str, str]]:
    """The seed's own synthetic people (eval/golden/generators.py), all @kfintech.example."""
    return synthetic_hr.generate(helpers.SEED)[:n]


def _csv_bytes(people: list[dict[str, str]], *, bom: bool = False, crlf: bool = False) -> bytes:
    end = "\r\n" if crlf else "\n"
    lines = [",".join(HEADER)] + [",".join(p[k] for k in HEADER) for p in people]
    text = end.join(lines) + end
    return (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8")


def _personal(people: list[dict[str, str]]) -> list[str]:
    return [v for p in people for v in (p["name"], p["email"])]


# ---- seed.seed_people: nobody in production, everything else as before --------------------------------------------


class _SeedConn:
    """Answers the persona lookup the seed makes in dev and test."""

    def execute(self, sql: str, params: Any = None) -> Any:
        assert "FROM users WHERE emp_id_hash" in sql
        return SimpleNamespace(fetchone=lambda: {"id": "00000000-0000-0000-0000-000000000001"})


def _stub_seed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, app_env: str) -> dict[str, list[Any]]:
    calls: dict[str, list[Any]] = {"generate": [], "import_rows": [], "grant": [], "connect": []}
    settings = SimpleNamespace(app_env=app_env, company_repo_path=tmp_path / "data" / "kfin-ideas")
    monkeypatch.setattr(seed, "get_settings", lambda: settings)

    def generate(repo: Path) -> list[dict[str, str]]:
        calls["generate"].append(repo)
        return [{"employee_id": "SYN-00001"}]

    @contextmanager
    def connect(autocommit: bool = False) -> Iterator[_SeedConn]:
        calls["connect"].append(autocommit)
        yield _SeedConn()

    def import_rows(conn: Any, rows: Any, tax: Any, **kw: Any) -> ImportResult:
        calls["import_rows"].append(rows)
        return ImportResult(rows=200, created=200)

    monkeypatch.setattr(seed, "generate", generate)
    monkeypatch.setattr(seed, "write_csv", lambda people, path: path)
    monkeypatch.setattr(seed, "read_csv", lambda path: ["row"] * 200)
    monkeypatch.setattr(seed, "load_taxonomy", lambda repo: object())
    monkeypatch.setattr(seed, "connect", connect)
    monkeypatch.setattr(seed, "import_rows", import_rows)

    def grant(*a: Any, **kw: Any) -> bool:
        calls["grant"].append((a, kw))
        return True

    monkeypatch.setattr(seed, "grant", grant)
    monkeypatch.setattr(seed, "emp_id_hash", lambda employee_id: f"hash:{employee_id}")
    return calls


@pytest.mark.parametrize("app_env", PROD_VALUES)
def test_a235_l_auth_rules_6_seed_in_prod_loads_no_person_and_grants_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], app_env: str
) -> None:
    calls = _stub_seed(monkeypatch, tmp_path, app_env)
    assert seed.seed_people(tmp_path / "repo") == 0
    assert calls == {"generate": [], "import_rows": [], "grant": [], "connect": []}  # not even a connection
    assert not (tmp_path / "data" / "hr").exists()  # no synthetic CSV written
    out = capsys.readouterr().out
    assert out == (
        "people: none loaded in production; IT loads HR's file with identity.hr_import (docs/UAT.md)\n"
    )


NOT_PROD_VALUES = ["uat", "production", "PROD", "Prod", "", "staging", "pro d"]


def test_a235_production_mode_reads_app_env_as_preflight_validates_it() -> None:
    """Every value preflight passes as prod is production mode; every value it refuses, or reads as uat, is not."""
    for value in PROD_VALUES + NOT_PROD_VALUES:
        accepted_as_prod = preflight.check({"APP_ENV": value})[0].count(
            "APP_ENV must be uat or prod"
        ) == 0 and (value.strip() != "uat")
        assert preflight.is_production(value) == accepted_as_prod, repr(value)


@pytest.mark.parametrize("app_env", NOT_PROD_VALUES)
def test_a235_l_auth_rules_6_only_app_env_prod_skips_the_people_uat_loads_them_as_before(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], app_env: str
) -> None:
    calls = _stub_seed(monkeypatch, tmp_path, app_env)
    assert seed.seed_people(tmp_path / "repo") == 0
    assert len(calls["generate"]) == 1 and len(calls["import_rows"]) == 1
    assert calls["grant"] == []  # persona roles only in dev and test, as before
    out = capsys.readouterr().out
    assert "hr import: 200 people (200 new, 0 updated, 0 deactivated)" in out
    assert "persona roles: skipped outside dev and test" in out
    assert "none loaded in production" not in out


@pytest.mark.parametrize("app_env", ["dev", "test"])
def test_a235_l_auth_rules_7_dev_and_test_still_load_people_and_grant_the_personas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], app_env: str
) -> None:
    calls = _stub_seed(monkeypatch, tmp_path, app_env)
    assert seed.seed_people(tmp_path / "repo") == 0
    assert len(calls["import_rows"]) == 1
    assert len(calls["grant"]) == sum(len(p.roles) for p in synthetic_hr.PERSONAS)
    assert "dev personas (sign in with the employee ID as the username):" in capsys.readouterr().out


# ---- smoke.people(): prod fresh / prod later / every other env as before --------------------------------------------


class _SmokeConn:
    def __init__(self, n: int, other: int, grants: int) -> None:
        self.n, self.other, self.grants = n, other, grants

    def execute(self, sql: str, params: Any = None) -> Any:
        if "FROM users" in sql:
            row = {"n": self.n, "other": self.other}
        elif "FROM role_grants" in sql:
            row = {"n": self.grants}
        else:  # pragma: no cover - people() reads nothing else
            raise AssertionError(sql)
        return SimpleNamespace(fetchone=lambda: row)


def _people_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    app_env: str,
    fresh: bool,
    n: int,
    other: int,
    grants: int,
) -> tuple[str, bool, str, int]:
    settings = SimpleNamespace(
        app_env=app_env,
        company_repo_path=tmp_path,
        is_production_like=app_env not in {"dev", "test"},
    )
    monkeypatch.setattr(smoke, "get_settings", lambda: settings)

    @contextmanager
    def connect(autocommit: bool = False) -> Iterator[_SmokeConn]:
        yield _SmokeConn(n, other, grants)

    monkeypatch.setattr(smoke, "connect", connect)
    checks = smoke.checks("http://web:3000", "http://localhost:8000", fresh)
    [(name, run)] = [(name, run) for name, run in checks if run.__name__ == "people"]
    ok, detail = run()
    return name, ok, detail, len(checks)


@pytest.mark.parametrize(
    ("n", "other", "grants", "ok"),
    [
        (0, 0, 0, True),  # the install loaded nobody, nobody has a role
        (200, 0, 0, False),  # synthetic people loaded on the launch server
        (0, 0, 1, False),
        (1, 1, 0, False),  # someone signed in before the smoke ran: not a fresh install
    ],
)
@pytest.mark.parametrize("app_env", PROD_VALUES)
def test_a235_l_auth_rules_6_prod_fresh_smoke_passes_only_with_no_people_and_no_grants(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    app_env: str,
    n: int,
    other: int,
    grants: int,
    ok: bool,
) -> None:
    name, passed, detail, count = _people_check(monkeypatch, tmp_path, app_env, True, n, other, grants)
    assert (passed, count) == (ok, 13)
    assert name == "no people or roles yet (production)"
    assert detail == f"{n} people, {grants} role grants"


@pytest.mark.parametrize(
    ("n", "other", "grants", "ok"), [(0, 0, 0, False), (20, 0, 1, True), (5000, 5000, 9, True)]
)
def test_a235_l_auth_rules_7_prod_smoke_after_the_hr_import_and_grants_passes_with_people(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, n: int, other: int, grants: int, ok: bool
) -> None:
    name, passed, detail, count = _people_check(monkeypatch, tmp_path, "prod", False, n, other, grants)
    assert (passed, count) == (ok, 13)
    assert name == "people loaded (production)"
    assert detail == f"{n} people, {grants} role grants"


@pytest.mark.parametrize(
    ("app_env", "fresh", "n", "other", "grants", "ok"),
    [
        ("uat", True, 200, 0, 0, True),
        ("uat", True, 0, 0, 0, False),  # uat still needs the synthetic people
        ("uat", True, 200, 1, 0, False),
        ("uat", True, 200, 0, 1, False),
        ("uat", False, 200, 3, 4, True),
        ("uat", False, 0, 0, 0, False),
        ("production", True, 0, 0, 0, False),  # only prod, as preflight reads it, is production mode
        ("PROD", True, 0, 0, 0, False),  # preflight refuses it, so it is never production mode
        ("dev", True, 200, 0, 0, True),
        ("test", False, 7, 7, 7, True),
    ],
)
def test_a235_l_auth_rules_6_every_other_env_keeps_the_people_check_as_before(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    app_env: str,
    fresh: bool,
    n: int,
    other: int,
    grants: int,
    ok: bool,
) -> None:
    name, passed, detail, count = _people_check(monkeypatch, tmp_path, app_env, fresh, n, other, grants)
    assert (passed, count) == (ok, 13)
    assert name == "people are synthetic, no dev personas"
    assert detail == f"{n} people, {other} outside the synthetic domain, {grants} role grants"


def test_a235_smoke_keeps_thirteen_checks_and_the_pass_line() -> None:
    source = (helpers.ROOT / "services" / "worker" / "bootstrap" / "smoke.py").read_text("utf-8")
    assert 'print("smoke: all checks passed" if not failed' in source
    # No other check reads people or role grants (the other twelve need none at install).
    assert source.count("FROM users") == 1 and source.count("FROM role_grants") == 1


# ---- identity.hr_import: `-` reads HR's file from stdin; counts only, line numbers, never a value -------------------


def _stdin(monkeypatch: pytest.MonkeyPatch, data: bytes) -> None:
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(data), encoding="utf-8"))


def _stub_import(monkeypatch: pytest.MonkeyPatch) -> list[list[hr_import.HrRow]]:
    seen: list[list[hr_import.HrRow]] = []

    @contextmanager
    def connect(autocommit: bool = False) -> Iterator[object]:
        yield object()

    def import_rows(conn: Any, rows: list[hr_import.HrRow], tax: Any, *, force: bool = False) -> ImportResult:
        seen.append(rows)
        return ImportResult(rows=len(rows), created=len(rows))

    monkeypatch.setattr(hr_import, "load", lambda repo: object())
    monkeypatch.setattr(hr_import, "connect", connect)
    monkeypatch.setattr(hr_import, "import_rows", import_rows)
    return seen


@pytest.mark.parametrize(("bom", "crlf"), [(False, False), (True, True)])
def test_a235_l_auth_rules_6_hr_import_reads_dash_from_stdin_and_prints_counts_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    captured_logs: io.StringIO,
    bom: bool,
    crlf: bool,
) -> None:
    people = _people(20)
    seen = _stub_import(monkeypatch)
    _stdin(monkeypatch, _csv_bytes(people, bom=bom, crlf=crlf))
    assert hr_import.main(["-", "--repo", str(helpers.SEED)]) == 0
    assert [r.employee_id for r in seen[0]] == [p["employee_id"] for p in people]
    assert seen[0][0].email == people[0]["email"]  # the byte-order mark is not part of the first header
    out = capsys.readouterr().out
    assert out == (
        "hr import: 20 rows, 20 created, 0 updated, 0 deactivated, 0 unmapped departments, 0 unmapped titles, "
        "0 proposals opened\n"
    )
    logs = captured_logs.getvalue()
    assert not [v for v in _personal(people) if v in out or v in logs]


def test_a235_hr_import_still_reads_a_file_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    people = _people(3)
    seen = _stub_import(monkeypatch)
    path = tmp_path / "hr.csv"
    path.write_bytes(_csv_bytes(people))
    assert hr_import.main([str(path), "--repo", str(helpers.SEED)]) == 0
    assert len(seen[0]) == 3 and capsys.readouterr().out.startswith("hr import: 3 rows, 3 created")


def _failed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], data: bytes) -> str:
    seen = _stub_import(monkeypatch)
    _stdin(monkeypatch, data)
    assert hr_import.main(["-", "--repo", str(helpers.SEED)]) == 4
    assert seen == []  # nothing reaches the database
    out = capsys.readouterr()
    return out.out + out.err


def test_a235_hr_import_error_names_the_line_never_a_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    people = _people(4)
    broken = [dict(p) for p in people]
    broken[1]["email"] = ""  # line 3
    out = _failed(monkeypatch, capsys, _csv_bytes(broken))
    assert out == "failed: line 3: employee_id, name and email are required; nothing was changed\n"
    assert not [v for v in _personal(people) if v and v in out]


def test_a235_hr_import_line_numbers_are_the_files_own_lines_when_a_field_holds_a_newline(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Review S3: lines 2-3 are one row (a quoted job title over two lines), so the row with no email is line 4."""
    people = _people(3)
    rows = [",".join(HEADER)]
    first = dict(people[0], job_title='"Team Lead\nOperations"')
    rows.append(",".join(first[k] for k in HEADER))
    rows.append(",".join(dict(people[1], email="")[k] for k in HEADER))
    out = _failed(monkeypatch, capsys, ("\n".join(rows) + "\n").encode("utf-8"))
    assert out == "failed: line 4: employee_id, name and email are required; nothing was changed\n"
    assert people[1]["name"] not in out


def test_a235_hr_import_a_row_over_two_lines_is_named_by_the_line_it_ends_on(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    people = _people(3)
    broken = dict(people[1], email="", job_title='"Team Lead\r\nOperations"')  # lines 3-4
    rows = [",".join(HEADER), ",".join(people[0][k] for k in HEADER), ",".join(broken[k] for k in HEADER)]
    out = _failed(monkeypatch, capsys, ("\r\n".join(rows) + "\r\n").encode("utf-8"))
    assert out == "failed: line 4: employee_id, name and email are required; nothing was changed\n"


def test_a235_hr_import_a_bare_carriage_return_in_a_quoted_field_counts_as_a_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Delta review 2: a bare \\r inside quotes is a line break to the reader, so the row after it is line 4."""
    people = _people(3)
    first = dict(people[0], job_title='"Team Lead\rOperations"')  # lines 2-3
    rows = [
        ",".join(HEADER),
        ",".join(first[k] for k in HEADER),
        ",".join(dict(people[1], email="")[k] for k in HEADER),
    ]
    out = _failed(monkeypatch, capsys, ("\n".join(rows) + "\n").encode("utf-8"))
    assert out == "failed: line 4: employee_id, name and email are required; nothing was changed\n"


def test_a235_hr_import_a_row_with_an_extra_column_keeps_the_line_count(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Delta review 2: an extra column (DictReader's list under None), holding a line break. Since BLD-A238 the
    extra field is itself refused, named by the line the row ends on (3), and the row after it is never read."""
    people = _people(3)
    rows = [
        ",".join(HEADER),
        ",".join(people[0][k] for k in HEADER) + ',"extra\ncolumn"',  # lines 2-3
        ",".join(dict(people[1], name="")[k] for k in HEADER),
    ]
    out = _failed(monkeypatch, capsys, ("\n".join(rows) + "\n").encode("utf-8"))
    assert out == "failed: line 3: expected 7 fields, found 8; nothing was changed\n"
    assert not [v for v in _personal(people) if v in out]


def test_a235_hr_import_wrong_header_names_the_expected_header_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    people = _people(2)
    data = _csv_bytes(people).replace(b"employee_id,name,", b"emp_no,full_name,", 1)
    out = _failed(monkeypatch, capsys, data)
    assert out == f"failed: HR CSV header must be exactly: {','.join(HEADER)}; nothing was changed\n"


def test_a235_hr_import_a_row_that_is_not_csv_names_its_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    people = _people(3)
    data = (
        _csv_bytes(people) + b"SYN-09999," + b"x" * 200_000 + b",a@kfintech.example,,,,\n"
    )  # over the field limit
    out = _failed(monkeypatch, capsys, data)
    assert out == "failed: line 5: not a valid CSV row; nothing was changed\n"
    assert "x" * 20 not in out and "a@kfintech.example" not in out


def test_a235_hr_import_a_bad_row_after_a_two_line_row_names_the_files_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    people = _people(2)
    first = dict(people[0], job_title='"Team Lead\nOperations"')  # lines 2-3
    head = ",".join(HEADER) + "\n" + ",".join(first[k] for k in HEADER) + "\n"
    data = (
        (head + ",".join(people[1][k] for k in HEADER) + "\n").encode()
        + b"SYN-09999,"
        + b"x" * 200_000
        + b"\n"
    )
    assert _failed(monkeypatch, capsys, data) == "failed: line 5: not a valid CSV row; nothing was changed\n"


def test_a235_hr_import_stdin_is_left_open_for_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_import(monkeypatch)
    _stdin(monkeypatch, _csv_bytes(_people(2)))
    assert hr_import.main(["-", "--repo", str(helpers.SEED)]) == 0
    assert not sys.stdin.buffer.closed  # the wrapper is detached, never closes the stream it was given


def test_a235_hr_import_a_file_that_is_not_utf8_prints_the_type_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _csv_bytes(_people(2)) + "SYN-09998,Rám,ram@kfintech.example,,,,\n".encode("latin-1", "replace")
    data = data.replace(b"Ra?m", b"Ra\xe9m")
    out = _failed(monkeypatch, capsys, data)
    assert out == "failed: UnicodeDecodeError; nothing was changed\n"


def test_a235_synthetic_hr_cli_writes_the_rehearsal_file_on_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert synthetic_hr.main(["--count", "20", "--repo", str(helpers.SEED)]) == 0
    out = capsys.readouterr()
    rows = read_stream(io.StringIO(out.out, newline=""))
    assert len(rows) == 20 and rows[0].employee_id == "SYN-00001"
    assert all(r.email.endswith("@kfintech.example") for r in rows)
    assert out.err == "synthetic hr: 20 people written\n"  # counts only on the terminal


# ---- scripts/uat/rehearse.sh: APP_ENV=prod only when asked; never runs docker or make here --------------------------


def _rehearse_env_files(tmp_path: Path, rehearse_app_env: str | None) -> subprocess.CompletedProcess[str]:
    """Run only the part of rehearse.sh that writes the throwaway env files, from a copy under tmp_path: it stops
    before the trap, `make down` and deploy.sh. `docker` and `make` on PATH are stubs that refuse, in case."""
    script = REHEARSE.read_text("utf-8")
    head = script.split("\ncleanup() {\n", 1)[0]
    code = "\n".join(line for line in head.splitlines() if not line.lstrip().startswith("#"))
    assert "docker" not in code and "make " not in code and "deploy.sh" not in code
    copy = tmp_path / "scripts" / "uat" / "rehearse.sh"
    copy.parent.mkdir(parents=True)
    copy.write_text(head + "\n")
    stub = tmp_path / "bin"
    stub.mkdir()
    for tool in ("docker", "make"):
        (stub / tool).write_text(f"#!/bin/sh\necho '{tool} stub' >&2\nexit 97\n")
        (stub / tool).chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "REHEARSE_APP_ENV"}
    env["PATH"] = f"{stub}{os.pathsep}{os.environ['PATH']}"
    if rehearse_app_env is not None:
        env["REHEARSE_APP_ENV"] = rehearse_app_env
    return subprocess.run(
        ["bash", str(copy)], capture_output=True, text=True, env=env, check=False, timeout=60
    )


@pytest.mark.parametrize(("value", "expected"), [(None, "uat"), ("uat", "uat"), ("prod", "prod")])
def test_a235_rehearsal_writes_app_env_prod_only_when_rehearse_app_env_is_prod(
    tmp_path: Path, value: str | None, expected: str
) -> None:
    run = _rehearse_env_files(tmp_path, value)
    assert run.returncode == 0, run.stderr
    assert "stub" not in run.stdout + run.stderr
    app = (tmp_path / ".data-uat-rehearsal" / "app.env").read_text("utf-8").splitlines()
    assert [line for line in app if line.startswith("APP_ENV=")] == [f"APP_ENV={expected}"]
    assert "LLM_MODE=fake" in app and "OIDC_MODE=entra" in app  # the rest of the file is as before
    assert oct((tmp_path / ".data-uat-rehearsal" / "app.env").stat().st_mode & 0o777) == "0o600"


@pytest.mark.parametrize("value", ["production", "PROD", "dev", "test"])
def test_a235_rehearsal_refuses_any_other_app_env(tmp_path: Path, value: str) -> None:
    run = _rehearse_env_files(tmp_path, value)
    assert run.returncode == 1 and "REHEARSE_APP_ENV must be uat (the default) or prod" in run.stdout
    assert not (tmp_path / ".data-uat-rehearsal").exists()


def test_a235_rehearsal_production_steps_run_only_in_prod_and_follow_the_runbook() -> None:
    script = REHEARSE.read_text("utf-8")
    deploy_line = 'scripts/uat/deploy.sh "$WORK/app.env" "$WORK/db.env"\n'
    before, after = script.split(deploy_line, 1)
    assert after.startswith('[[ "$REHEARSE_APP_ENV" == "prod" ]] || exit 0\n')  # uat ends where it always did
    assert "synthetic_hr" not in before and "hr_import" not in before
    steps = [
        "bootstrap.smoke --web-url http://web:3000 --fresh)",  # (a)
        'no people or roles yet (production)" <<<"$fresh"',
        'python -m bootstrap.synthetic_hr --count 20 >"$WORK/hr-synthetic.csv")',  # (b), mode 600 by umask
        'docker exec -i "$WORKER" python -m identity.hr_import - <"$WORK/hr-synthetic.csv"',  # UAT.md 1b
        'docker exec "$WORKER" python -m identity.grants grant --employee-id SYN-00001 --role admin',  # (c), 1c
        "--actor ops:rehearsal",
        'docker exec "$WORKER" python -m bootstrap.smoke --web-url http://web:3000\n',  # (d), 2b: no --fresh
    ]
    positions = [after.index(s) for s in steps]
    assert positions == sorted(positions)
    assert "(umask 077 && compose run" in after
    assert 'WORKER="$PROJECT-worker-1"' in after
    assert "--force" not in after


# ---- lane E's condition: the dev, test and CI defaults the journeys depend on are untouched ------------------------


def test_a235_env_example_keeps_the_dev_defaults_the_journeys_depend_on() -> None:
    env = (helpers.ROOT / ".env.example").read_text("utf-8")

    def value(name: str) -> str:
        found = re.findall(rf"^{name}=(\S*)", env, re.M)
        assert len(found) == 1, name
        return found[0]

    assert value("APP_ENV") == "dev"
    assert value("LLM_MODE") == "fake"
    assert value("OIDC_MODE") == "mock"
    assert value("EMBEDDINGS_MODE") == "hash"
    assert value("SPEECH_MODE") == "fake"


# ---- docs/UAT.md: the HR import step IT follows -------------------------------------------------------------------


def test_a235_uat_runbook_hr_import_step_in_lane_as_order_with_one_command_form() -> None:
    doc = UAT_DOC.read_text("utf-8")
    # Only "After the deploy": the sections after it have their own tests (full mode's restart needs the compose
    # wrapper, BLD-A245, test_a245_mode_a.py).
    after = doc.split("## After the deploy", 1)[1].split("\n## ", 1)[0]
    assert f"`{','.join(HEADER)}`" in after
    hr = "docker exec -i kfin-ideas-uat-worker-1 python -m identity.hr_import - < /secure/hr/<file>.csv"
    grant = (
        "docker exec kfin-ideas-uat-worker-1 python -m identity.grants grant --employee-id <ID> --role admin"
    )
    smoke_later = "docker exec kfin-ideas-uat-worker-1 python -m bootstrap.smoke --web-url http://web:3000\n"
    order = ["**1a. The first admin signs in once**", hr, grant, "2. Ones Committee members", smoke_later]
    positions = [after.index(s) for s in order]
    assert positions == sorted(positions)
    assert "docker compose" not in after  # one form for the import, the grants and the smoke check
    assert "**The first admin must be in HR's file with the same email they sign in with.**" in after
    assert (
        "refused" not in after.split("**1b.", 1)[1].split("Pass:", 1)[0]
    )  # the guard counts HR's rows only (S1)
    assert '--reason "First admin at launch, <ticket>"' in after
    assert "chmod 600" in after and "--force" in after and "never a name or an email" in after
    assert "0 people, 0 role grants" in doc


# ---- scripts/uat/deploy.sh: the last line points production at the steps after the deploy (review S2) -------------


@pytest.mark.parametrize(
    ("line", "production"),
    [
        ("APP_ENV=prod", True),
        ('APP_ENV="prod "', True),
        ("APP_ENV=prod   # launch", True),
        ("APP_ENV=uat", False),
    ],
)
def test_a235_deploy_next_line_in_production_points_at_the_runbook(
    tmp_path: Path, line: str, production: bool
) -> None:
    """Runs only deploy.sh's own `value` helper and its last lines, never docker."""
    script = DEPLOY.read_text("utf-8")
    [value_fn] = [x for x in script.splitlines() if x.startswith("value() {")]
    tail = "printf '\\nUAT stack is up" + script.split("printf '\\nUAT stack is up", 1)[1]
    app = tmp_path / "app.env"
    app.write_text(f"{line}\n")
    snippet = f'set -euo pipefail\nAPP_ENV_FILE="{app}"\nPROJECT=kfin-ideas-uat\n{value_fn}\n{tail}'
    run = subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, check=False, timeout=30)
    assert run.returncode == 0, run.stderr
    if production:
        assert "Next (APP_ENV=prod, no people yet): docs/UAT.md After the deploy, 1a to 2b" in run.stdout
        assert "identity.grants" not in run.stdout
    else:
        assert (
            "Next: grant the first admin with\n  docker compose -p kfin-ideas-uat ... exec worker"
            in run.stdout
        )
        assert "APP_ENV=prod" not in run.stdout
