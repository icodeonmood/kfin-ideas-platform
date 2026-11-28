"""BLD-E078 (R1, dead code only): every agent the worker's own code runs has its folder. The test reads the source and
collects each `run_agent(<name>, ...)` name in services/worker outside tests/, then asserts agents/<name>/config.yaml
exists for each. So an agents/<name>/ folder can only go in the same change that removes its last caller.

A name is read from a string literal, from a module-level string constant (draft/runs.py's `AGENT`), or, when it is
a parameter of the function that calls `run_agent`, from the string literals passed for that parameter in the same
module (evalrunner/committee.py's `_run`). A call whose name cannot be read that way fails the test, so a new
indirect caller cannot slip past it. Pure: no database, no stack."""

from __future__ import annotations

import ast
from pathlib import Path

from tests import helpers

WORKER = Path(__file__).resolve().parents[1]
AGENTS = helpers.ROOT / "agents"


def _sources() -> list[Path]:
    return sorted(
        p for p in WORKER.rglob("*.py") if not {"tests", ".venv"} & set(p.relative_to(WORKER).parts)
    )


def _constants(tree: ast.Module) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node.value.value
    return out


def _param_values(tree: ast.Module, func: ast.FunctionDef, param: str) -> set[str] | None:
    """The string literals passed for `param` in calls to `func` within the module, or None if any call passes
    something else (or the function is never called)."""
    names = [a.arg for a in func.args.posonlyargs + func.args.args]
    index = names.index(param) if param in names else None
    found: set[str] = set()
    calls = 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == func.name):
            continue
        calls += 1
        arg: ast.expr | None = next((k.value for k in node.keywords if k.arg == param), None)
        if arg is None and index is not None and index < len(node.args):
            arg = node.args[index]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            return None
        found.add(arg.value)
    return found if calls else None


def _callers() -> tuple[dict[str, list[str]], list[str]]:
    """{agent name: ["path:line", ...]} and the calls whose name could not be read."""
    names: dict[str, list[str]] = {}
    unread: list[str] = []
    for path in _sources():
        rel = path.relative_to(WORKER).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = _constants(tree)
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            called = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else None
            if called != "run_agent":
                continue
            where = f"{rel}:{node.lineno}"
            arg = (
                node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "name"), None)
            )
            values: set[str] | None = None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                values = {arg.value}
            elif isinstance(arg, ast.Name) and arg.id in constants:
                values = {constants[arg.id]}
            elif isinstance(arg, ast.Name):
                enclosing = [f for f in funcs if f.lineno <= node.lineno <= (f.end_lineno or f.lineno)]
                if enclosing:
                    func = max(enclosing, key=lambda f: f.lineno)  # the innermost
                    values = _param_values(tree, func, arg.id)
            if not values:
                unread.append(where)
                continue
            for value in values:
                names.setdefault(value, []).append(where)
    return names, unread


def test_BLD_E078_every_run_agent_name_has_an_agent_config() -> None:
    names, unread = _callers()
    assert not unread, f"run_agent calls whose agent name the test cannot read: {unread}"
    missing = {n: where for n, where in names.items() if not (AGENTS / n / "config.yaml").is_file()}
    assert not missing, f"run_agent names with no agents/<name>/config.yaml: {missing}"


def test_BLD_E078_the_collector_reads_direct_constant_and_parameter_names() -> None:
    """The collector is not vacuous: it finds the live agents by each of the three ways a name is given."""
    names, _ = _callers()
    assert "gatekeeper" in names  # literal, many callers
    assert any(w.startswith("draft/runs.py:") for w in names.get("draft-part", []))  # module constant AGENT
    assert any(
        w.startswith("evalrunner/committee.py:") for w in names.get("pitch-prep", [])
    )  # `_run`'s parameter
