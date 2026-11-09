"""The demo seed (`make demo`) is dev only and clearly synthetic: refused anywhere else, never a real name."""

from __future__ import annotations

from typing import Any

import pytest

from bootstrap import demo
from core.config import Settings


@pytest.mark.parametrize("env", ["test", "uat", "prod", "staging"])
def test_the_demo_is_refused_outside_dev(env: str, monkeypatch: Any) -> None:
    monkeypatch.setattr(demo, "get_settings", lambda: Settings(app_env=env))
    with pytest.raises(SystemExit, match="local dev stack only"):
        demo.main([])


def test_every_demo_row_is_marked_as_demo() -> None:
    assert all(emp.startswith("DEMO-") for emp, *_ in demo.PEOPLE)
    assert all(demo._email(name).endswith(".demo@kfintech.example") for _, name, *_ in demo.PEOPLE)
    assert {name for _, name, *_ in demo.PEOPLE if "CEO" in name} == {"Demo CEO"}
    assert all(m.get("demo") is None for o in demo.ONES for m in o["measures"].values())  # flagged on load
    assert {o["number"] for o in demo.ONES} >= {1, 2, 3, 4, 5, 6, 17, 18, 19}
