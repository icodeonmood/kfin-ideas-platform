"""L-CONVO rules that need no database: who opens files is read from the RBAC policy (BLD-F062), lane C's recipe for
forgetting a removed message runs in its order behind one function (BLD-F067), and lane C's refusal becomes a
ready one (BLD-F054). A recording stand-in plays the connection; synthetic IDs only."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml

from convo import adapters
from convo.access import FILE_ROLES

POLICY = Path(__file__).resolve().parents[3] / "policy" / "rbac.yaml"
NO_CONN: Any = None  # the stand-in hide never touches a connection


def test_bld_f062_file_roles_are_the_policys_view_review_queue_with_its_aliases() -> None:
    """`accessible()` in apps/web/src/server/attachments.ts opens a file for `view_review_queue`; the conversation's
    list must not drift from it."""
    policy = yaml.safe_load(POLICY.read_text())
    roles = set(policy["capabilities"]["view_review_queue"])
    aliases = {alias for alias, target in (policy.get("role_aliases") or {}).items() if target in roles}
    assert set(FILE_ROLES) == roles | aliases
    assert "committee" not in FILE_ROLES  # a plain committee holder neither opens nor adds files


class _Rows:
    def __init__(self, rows: list[dict[str, Any]], rowcount: int) -> None:
        self._rows, self.rowcount = rows, rowcount

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _Conn:
    """Records each statement; answers the tag SELECT with `tags` and each DELETE with a row count."""

    def __init__(self, tags: list[str]) -> None:
        self.tags, self.sql = tags, []  # type: ignore[var-annotated]
        self.params: list[Any] = []

    def execute(self, sql: str, params: Any = None) -> _Rows:
        self.sql.append(sql)
        self.params.append(params)
        if sql.startswith("SELECT vault_tag"):
            return _Rows([{"vault_tag": t} for t in self.tags], len(self.tags))
        return _Rows([], 2)


def test_bld_f067_l_convo_10_forget_runs_lane_cs_recipe_in_order_lock_first(
    monkeypatch: pytest.MonkeyPatch, captured_logs: Any
) -> None:
    idea, entry = str(uuid.uuid4()), str(uuid.uuid4())
    order: list[str] = []
    monkeypatch.setattr(adapters, "_hide_lock", lambda conn, i: order.append(f"lock {i}"))
    monkeypatch.setattr(adapters, "_hide_scope", lambda i: f"DRAFT-{i}")
    conn = _Conn(["[[KFIN_FOLIO_1]]", "[[KFIN_FOLIO_2]]"])
    real = conn.execute

    def traced(sql: str, params: Any = None) -> _Rows:
        order.append(sql.split(" WHERE ")[0])
        return real(sql, params)

    conn.execute = traced  # type: ignore[method-assign]
    adapters.forget(conn, idea, entry)  # type: ignore[arg-type]
    assert order == [
        f"lock {idea}",
        "SELECT vault_tag FROM hidden_details",
        "DELETE FROM hidden_details",
        "DELETE FROM idea_words_sealed",
        "DELETE FROM pseudonym_vault v",
    ]
    assert conn.params[:3] == [(idea, entry)] * 3  # the entry's uuid as it is, as source_id
    assert conn.params[3] == (f"DRAFT-{idea}", ["[[KFIN_FOLIO_1]]", "[[KFIN_FOLIO_2]]"], idea)
    assert "NOT EXISTS" in conn.sql[3]  # a value another text still uses stays
    logs = captured_logs.getvalue()
    assert "convo.hidden_forgotten" in logs and entry in logs and "FOLIO" not in logs  # IDs and counts only


def test_bld_f067_forget_skips_the_vault_when_nothing_was_tagged_and_does_nothing_without_lane_c(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    idea, entry = str(uuid.uuid4()), str(uuid.uuid4())
    monkeypatch.setattr(adapters, "_hide_lock", lambda conn, i: None)
    monkeypatch.setattr(adapters, "_hide_scope", lambda i: f"DRAFT-{i}")
    conn = _Conn([])
    adapters.forget(conn, idea, entry)  # type: ignore[arg-type]
    assert not any("pseudonym_vault" in q for q in conn.sql)
    monkeypatch.setattr(adapters, "_hide_lock", None)
    none = _Conn(["[[KFIN_FOLIO_1]]"])
    adapters.forget(none, idea, entry)  # type: ignore[arg-type]
    assert none.sql == []


def test_bld_f054_lane_cs_refusal_becomes_hide_refused_with_its_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hide.core import HideError

    def refuses(*a: Any, **k: Any) -> Any:
        raise HideError(503, "gatekeeper_down")

    monkeypatch.setattr(adapters, "_hide_message", refuses)
    with pytest.raises(adapters.HideRefused) as caught:
        adapters.hide(
            NO_CONN, str(uuid.uuid4()), "Folio 1234567890", by=str(uuid.uuid4()), entry_id=str(uuid.uuid4())
        )
    assert caught.value.status == 503

    def breaks(*a: Any, **k: Any) -> Any:
        raise RuntimeError("a bug, not a refusal")

    monkeypatch.setattr(adapters, "_hide_message", breaks)
    with pytest.raises(RuntimeError):
        adapters.hide(NO_CONN, str(uuid.uuid4()), "Hello", by=str(uuid.uuid4()), entry_id=str(uuid.uuid4()))


def test_bld_f054_lane_cs_names_are_found_on_main() -> None:
    """Lane C's L-HIDE is on main: the guarded imports find it, so the pattern mask is only a fallback."""
    assert adapters._hide_message is not None
    assert (
        adapters._hide_lock is not None
        and adapters._hide_scope is not None
        and adapters._HideError is not None
    )
