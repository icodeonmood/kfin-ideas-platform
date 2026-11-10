"""The demo seed (`make demo`) is dev only and clearly synthetic: refused anywhere else, never a real name."""

from __future__ import annotations

import contextlib
from typing import Any

import pytest

from bootstrap import demo
from core.config import Settings


@pytest.mark.parametrize("argv", [[], ["--reset"], ["--remove"]])
@pytest.mark.parametrize("env", ["test", "uat", "prod", "staging"])
def test_the_demo_is_refused_outside_dev(env: str, argv: list[str], monkeypatch: Any) -> None:
    monkeypatch.setattr(demo, "get_settings", lambda: Settings(app_env=env))
    with pytest.raises(SystemExit, match="local dev stack only"):
        demo.main(argv)


def _stub(monkeypatch: Any, loaded: bool) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(demo, "_dev_only", lambda: None)
    monkeypatch.setattr(demo, "connect", lambda **_: contextlib.nullcontext(object()))
    monkeypatch.setattr(demo, "_demo_user_ids", lambda _conn: ["u1"] if loaded else [])
    monkeypatch.setattr(demo, "remove", lambda _conn: calls.append("remove"))
    monkeypatch.setattr(demo, "_wait_for_repo", lambda _conn: calls.append("wait"))
    monkeypatch.setattr(demo, "load", lambda _conn: calls.append("load"))
    return calls


def test_remove_only_removes_waits_for_the_repo_and_does_not_load_again(monkeypatch: Any) -> None:
    calls = _stub(monkeypatch, loaded=True)
    assert demo.main(["--remove"]) == 0
    assert calls == ["remove", "wait"]


def test_remove_when_the_demo_is_not_loaded_changes_nothing(monkeypatch: Any, capsys: Any) -> None:
    calls = _stub(monkeypatch, loaded=False)
    assert demo.main(["--remove"]) == 0
    assert calls == []
    assert "nothing to remove" in capsys.readouterr().out


def test_after_removal_new_numbers_start_after_the_demo_s_fixed_ones() -> None:
    assert max(o["number"] for o in demo.ONES) == 20  # `load` leaves the counter here too


def test_remove_and_reset_cannot_be_combined() -> None:
    with pytest.raises(SystemExit) as stop:
        demo.main(["--remove", "--reset"])
    assert stop.value.code == 2  # argparse usage error, before anything runs


def test_every_demo_row_is_marked_as_demo() -> None:
    assert all(emp.startswith("DEMO-") for emp, *_ in demo.PEOPLE)
    assert all(demo._email(name).endswith(".demo@kfintech.example") for _, name, *_ in demo.PEOPLE)
    assert {name for _, name, *_ in demo.PEOPLE if "CEO" in name} == {"Demo CEO"}
    assert all(m.get("demo") is None for o in demo.ONES for m in o["measures"].values())  # flagged on load
    assert {o["number"] for o in demo.ONES} >= {1, 2, 3, 4, 5, 6, 17, 18, 19}
