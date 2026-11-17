"""S-H2B.reader/1 and L-INBOX.kinds without a database: the lead's team-up item reads "Merge request" and "asks to
team up and merge their idea into yours" whenever the request brings an idea, as lane F's `tell_lead` posts it
(`request` "teamup" from the sheet, "merge" for a draft, with `brought`), and "Team-up request" / "asks to team up"
when nothing comes along. The reader's note is empty: the idea brought shows in the reader (BLD-A195). Words come
from the seed template; the item is built by `render.item` with a connection that finds no rows, so the sender is
the system and the idea is absent, which leaves the kind's own words to check."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from comms import templates
from notify import render

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
RID = "5b0e7a3c-2d41-4f6e-9a18-0c7d3e2b9f11"
NOW = dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.UTC)

# The lead's answers as lane F's `tell_lead` posts them (teamup/rules.py `answers_for`, bare ops).
BRINGS = [
    {"label": "Decline", "style": "text", "op": "decline"},
    {"label": "Team up only", "style": "line", "op": "team_only"},
    {"label": "Merge it", "style": "primary", "op": "merge"},
]
NOTHING = [
    {"label": "Decline", "style": "text", "op": "decline"},
    {"label": "Approve", "style": "primary", "op": "team_only"},
]


class _NoRows:
    """A connection that finds nothing: no idea, no sender, no reader."""

    def execute(self, *_: Any, **__: Any) -> Any:
        return self

    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[Any]:
        return []


@pytest.fixture(autouse=True)
def _seed_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render, "load", lambda name: templates._load(SEED, name))


def _item(refs: dict[str, Any], actions: list[dict[str, str]]) -> dict[str, Any]:
    row = {
        "id": 41,
        "kind": "teamup_request",
        "payload": refs,
        "actions": actions,
        "created_at": NOW,
        "needs_you": True,
        "resolved_at": None,
        "read_at": None,
        "archived_at": None,
    }
    return render.item(_NoRows(), row, "u-lead", NOW)  # type: ignore[arg-type]


MERGE = ("Merge request", "asks to team up and merge their idea into yours")
TEAM_ONLY = ("Team-up request", "asks to team up")


@pytest.mark.parametrize(
    ("case", "refs", "actions", "words"),
    [
        ("a bare team-up request", {"request_id": RID, "request": "teamup", "brought": 0}, NOTHING, TEAM_ONLY),
        ("a sheet request with one idea brought", {"request_id": RID, "request": "teamup", "brought": 1}, BRINGS, MERGE),
        ("a draft merge request", {"request_id": RID, "request": "merge", "brought": 1}, BRINGS, MERGE),
        (
            "a sheet request with two ideas brought",
            {"request_id": RID, "request": "teamup", "brought": 2},
            BRINGS,
            ("Merge request", "asks to team up and merge their ideas into yours"),
        ),
        ("a draft merge request that names no count", {"request_id": RID, "request": "merge"}, BRINGS, MERGE),
        ("a seeded item with no refs that offers Merge it", {}, BRINGS, MERGE),
        ("a seeded item with no refs and nothing to merge", {}, NOTHING, TEAM_ONLY),
    ],
)  # fmt: skip
def test_S_H2B_reader_1_L_INBOX_kinds_a_request_that_brings_an_idea_reads_as_a_merge_request(
    case: str, refs: dict[str, Any], actions: list[dict[str, str]], words: tuple[str, str]
) -> None:
    item = _item(refs, actions)
    assert (item["body"]["heading"], item["line"]) == words, case
    # The note is gone: the idea brought already shows in the reader, and "other ideas" was wrong for one.
    assert item["body"]["note"] == "", case
    assert item["body"]["request_id"] == RID if refs else "request_id" not in item["body"]


def test_S_H2B_reader_1_the_choice_is_made_once_from_request_and_brought() -> None:
    """`teamup_request_vars` is the one place the words are chosen; the web shows the heading and line as given."""
    pick = render.teamup_request_vars
    assert pick({"request": "teamup", "brought": 0}, [])["request"] == {"merge": False, "team_only": True}
    assert pick({"request": "teamup", "brought": 1}, [])["request"] == {"merge": True, "team_only": False}
    assert pick({"request": "merge", "brought": 0}, [])["request"]["merge"] is True
    # Lane F's `request` wins over the item's buttons once it is there: a team-up with nothing brought stays one.
    assert pick({"request": "teamup", "brought": 0}, ["merge"])["request"]["merge"] is False
    assert pick({"request": "teamup", "brought": True}, [])["brought"] == {
        "any": True,
        "count": 1,
        "many": False,
        "single": True,
    }


def test_L_INBOX_kinds_the_request_template_carries_no_note() -> None:
    tpl = templates._load(SEED, "inbox/teamup_request")
    assert tpl.inbox["note"] == ""
    assert not any("bringing" in words for words in (tpl.subject, tpl.body, *tpl.inbox.values()))
