"""L-CONVO rules that need no database: who opens files is read from the RBAC policy (BLD-F062), forgetting a removed
message is lane C's `hide.forget` behind one function (BLD-F067, BLD-F076), and lane C's refusal becomes a
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


def test_bld_f076_l_convo_10_forget_is_lane_cs_hide_forget_for_the_conversation_entry(
    monkeypatch: pytest.MonkeyPatch, captured_logs: Any
) -> None:
    """Lane C's `hide.forget` does the whole recipe (lock first, hidden details, sealed words, unshared vault values);
    lane F's forget hands it the conversation entry and logs IDs and counts only."""
    idea, entry = str(uuid.uuid4()), str(uuid.uuid4())
    calls: list[tuple[Any, ...]] = []

    def hide_forget(conn: Any, idea_uuid: str, *, source: str, source_id: str) -> int:
        calls.append((conn, idea_uuid, source, source_id))
        return 2

    monkeypatch.setattr(adapters, "_hide_forget", hide_forget)
    conn = object()
    adapters.forget(conn, idea, entry)  # type: ignore[arg-type]
    assert calls == [(conn, idea, "conversation", entry)]
    logs = captured_logs.getvalue()
    assert "convo.hidden_forgotten" in logs and entry in logs and "FOLIO" not in logs  # IDs and counts only


def test_bld_f076_forget_does_nothing_without_lane_c(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no lane C at all, messages were masked by the patterns alone: nothing was kept, nothing to drop. With
    lane C's `hide_message` but no `forget`, values were kept: it raises (no IDs in the message) so the removal
    rolls back, rather than leave them behind silently."""
    idea, entry = str(uuid.uuid4()), str(uuid.uuid4())
    monkeypatch.setattr(adapters, "_hide_forget", None)
    monkeypatch.setattr(adapters, "_hide_message", None)
    adapters.forget(NO_CONN, idea, entry)

    monkeypatch.setattr(adapters, "_hide_message", lambda *a, **k: None)
    with pytest.raises(RuntimeError) as half:
        adapters.forget(NO_CONN, idea, entry)
    assert idea not in str(half.value) and entry not in str(half.value)


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
    import hide

    assert adapters._hide_forget is hide.forget and adapters._HideError is not None
