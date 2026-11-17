"""L-HIDE.files/1 (non-negotiable 4, DEC-103; the 18 Nov rule of BLD-C107): a file never skips the gatekeeper.
Whoever switched `ai.all` or `agent.gatekeeper` off, a person or a process, the file waits (`GatekeeperWaits`),
before its first piece or between two pieces; with both on, every piece is read and each value the gatekeeper names
is placed wherever it appears in the whole text. No database: the switches and the gateway are stubbed. Synthetic
text only."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from hide import detect
from hide import files as hide_files

IDEA = str(uuid.uuid4())
ADDRESS = "Flat 12, Green Park, Pune"
TEXT = ("Calls double on Mondays. " * 400) + f"Forms come back from {ADDRESS}. " + ("Queue grows. " * 50)


class NoConn:
    def transaction(self) -> contextlib.AbstractContextManager[None]:
        return contextlib.nullcontext()


def stub(monkeypatch: pytest.MonkeyPatch, off: Iterator[bool], said: list[detect.Gate]) -> list[str]:
    """`off` answers each check of the switches in turn; `said` is the gateway's answer per piece."""
    asked: list[str] = []

    def gatekeeper_finds(conn: Any, piece: str, scope: str) -> detect.Gate:
        asked.append(scope)
        return said.pop(0)

    monkeypatch.setattr(hide_files, "_switched_off", lambda conn: next(off))
    monkeypatch.setattr(detect, "gatekeeper_finds", gatekeeper_finds)
    return asked


def test_L_HIDE_files_1_the_text_is_long_enough_for_two_pieces() -> None:
    assert len(hide_files.chunks(TEXT)) == 2


def test_L_HIDE_files_1_switched_off_before_the_first_piece_the_file_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = stub(monkeypatch, iter([True]), [])
    with pytest.raises(hide_files.GatekeeperWaits) as waits:
        hide_files.gate_for(NoConn(), IDEA, TEXT)  # type: ignore[arg-type]
    assert str(waits.value) == "switched_off" and asked == []  # no model call


def test_L_HIDE_files_1_switched_off_between_two_pieces_the_file_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second `held()`: switched off while the file was read, by anyone, so nothing is placed."""
    asked = stub(monkeypatch, iter([False, True]), [detect.Gate([]), detect.Gate([])])
    with pytest.raises(hide_files.GatekeeperWaits) as waits:
        hide_files.gate_for(NoConn(), IDEA, TEXT)  # type: ignore[arg-type]
    assert str(waits.value) == "switched_off" and len(asked) == 1


def test_L_HIDE_files_1_a_gateway_failure_waits_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    stub(monkeypatch, iter([False, False]), [detect.Gate([], "connection")])
    with pytest.raises(hide_files.GatekeeperWaits) as waits:
        hide_files.gate_for(NoConn(), IDEA, TEXT)  # type: ignore[arg-type]
    assert str(waits.value) == "connection"


def test_L_HIDE_files_1_with_both_switches_on_every_piece_is_read_and_placed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    named = detect.Found(0, len(ADDRESS), "name", ADDRESS, "gatekeeper")
    asked = stub(monkeypatch, iter([False, False, False]), [detect.Gate([]), detect.Gate([named])])
    gate = hide_files.gate_for(NoConn(), IDEA, TEXT)  # type: ignore[arg-type]
    assert len(asked) == 2 and gate.skipped is None and gate.switched_off is False
    assert [(TEXT[f.start : f.end], f.kind, f.found_by) for f in gate.finds] == [
        (ADDRESS, "name", "gatekeeper")
    ]
