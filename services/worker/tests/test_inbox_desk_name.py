"""DEC-111 part 2 (BLD-A221, BLD-A222) without a database: a sharer never reads the name of the person at the review
desk. Every desk kind of Inbox item (L-INBOX.kinds, J-TRACK/2–6) comes from "The review desk" with the mark, and
the 1% Club's own kinds name no one, whoever posted them: no reviewer users.id, name, first name or initials in the
item's JSON, its template variables or its email, and the reviewer's row is never read. The Ones Committee still
signs by name (DEC-111 hides only the review desk's people). The desk's emails for the old routes (J-REVIEW's
outgoing messages: question, redirected, reviewed) sign as the desk. Synthetic people only; the same flows against
the real tables run in CI in tests/test_notify.py."""

from __future__ import annotations

import datetime as dt
import json
import types
from pathlib import Path
from typing import Any

import pytest

from comms import render as crender
from comms import templates
from notify import render
from onepc.words import REVIEW_DESK_START

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
NOW = dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.UTC)
SHARER = "6f1c2a9e-3b7d-4e0a-9c55-2f4b8d1e7a01"  # Kavya Menon, who shared the idea (synthetic)
REVIEWER = "0b7e2c41-9d3a-4f58-8e16-5a2c7d9f3b10"  # Meera Iyer, at the review desk (synthetic)
MEMBER = "9a4d6e21-7c3b-4b19-8f02-3e6a5d1c8b47"  # Rohan Mehta, on the Ones Committee (synthetic)
OTHER = "2c8f1b6d-5e4a-4d37-a1c9-7b3e9f2d6a58"  # Ravi Nair, the other sharer in a desk merge (synthetic)
IDEA = "c3d9a1f2-4b6e-4c8a-9f21-7e5d3b2a1c90"
SET = "5b0e7a3c-2d41-4f6e-9a18-0c7d3e2b9f11"
CODES = {SHARER: "CTR-1a2b3c", OTHER: "CTR-4d5e6f"}
PEOPLE = {
    SHARER: ("Kavya Menon", "Kavya"),
    REVIEWER: ("Meera Iyer", "Meera"),
    MEMBER: ("Rohan Mehta", "Rohan"),
    OTHER: ("Ravi Nair", "Ravi"),
}
# Every way the reviewer could show: their users.id, name, first name, surname and initials
REVIEWER_TRACES = (REVIEWER, "Meera", "Iyer", '"MI"')

DESK_KINDS = ("questions", "decision", "worth_revised", "desk_merge", "detail_hidden_by_desk")
SYSTEM_KINDS = ("sent_to_desk", "answer_reminder")


class _Rows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchone(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class _Conn:
    """The reads `notify.render` and `comms.render` make, answered from synthetic rows. `people_read` keeps every
    users.id whose row was read, so a test can show the reviewer was never looked up."""

    def __init__(self) -> None:
        self.people_read: list[str] = []

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _Rows:
        if (
            "FROM ideas WHERE id = %s" in sql
        ):  # notify.render's read; the old routes' read by idea_id finds none
            return _Rows([{"id": IDEA, "idea_id": "IDEA-2026-000900", "title": "Rejection SMS codes confuse investors",
                           "status": "with_review_desk", "decide_by": NOW + dt.timedelta(days=4),
                           "contributor_code": CODES[SHARER]}])  # fmt: skip
        if "FROM question_sets" in sql:  # a reviewer's set; `by_user_id` is there to be ignored
            return _Rows([{"id": SET, "by_user_id": REVIEWER, "n": 3}])
        if "FROM idea_decisions" in sql:
            return _Rows([{"choice": "pick"}])
        if "FROM merges" in sql:
            return _Rows([{"lead_code": CODES[SHARER], "merged_code": CODES[OTHER]}])
        if "JOIN users u ON u.id = m.user_id" in sql:  # a contributor code's person: the other sharer
            user = next((u for u, c in CODES.items() if c == params[0]), None)
            if user is None:
                return _Rows([])
            self.people_read.append(user)
            return _Rows([{"name": PEOPLE[user][0], "first_name": PEOPLE[user][1]}])
        if "FROM contributor_map WHERE user_id" in sql:
            code = CODES.get(str(params[0]))
            return _Rows([{"contributor_code": code}] if code else [])
        if "FROM users WHERE id" in sql:
            self.people_read.append(str(params[0]))
            who = PEOPLE.get(str(params[0]))
            return _Rows([{"id": params[0], "name": who[0], "first_name": who[1]}] if who else [])
        return _Rows([])


@pytest.fixture(autouse=True)
def _seed_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render, "load", lambda name: templates._load(SEED, name))


def _row(kind: str, sender: str | None, channel: str = "in_app") -> dict[str, Any]:
    refs: dict[str, Any] = {
        "questions": {"set_id": SET},
        "answer_reminder": {"set_id": SET},
        "decision": {"choice": "pick"},
        "desk_merge": {"merge_id": "8e2d4c6a-1b3f-4a59-9d70-6c1e8b2f4a35"},
        "decision_reversed": {"window_id": "7d1c3b5a-9e2f-4c68-8b40-5a9e7c3d1f26", "to": "pick"},
        "sent_to_desk": {"ref": "IDEA-2026-000900"},
    }.get(kind, {})
    return {
        "id": 51,
        "user_id": SHARER,
        "channel": channel,
        "kind": kind,
        "payload": refs,
        "actions": [],
        "from_user_id": sender,
        "idea_uuid": IDEA,
        "created_at": NOW,
        "due_at": NOW + dt.timedelta(days=1, hours=1) if kind in ("questions", "answer_reminder") else None,
        "needs_you": kind in ("questions", "answer_reminder"),
        "resolved_at": None,
        "read_at": None,
        "archived_at": None,
        "dedupe_key": None,
    }


def _read(kind: str, sender: str | None) -> tuple[_Conn, dict[str, Any], dict[str, Any], str]:
    """The sharer's item, its template variables and its email, all from one connection."""
    conn = _Conn()
    item = render.item(conn, _row(kind, sender), SHARER, NOW)  # type: ignore[arg-type]
    _, data = render.variables(conn, _row(kind, sender), SHARER, NOW)  # type: ignore[arg-type]
    mail = render.email(conn, _row(kind, sender, "email"), NOW)  # type: ignore[arg-type]
    return conn, item, data, "\n".join((mail.subject, mail.text, mail.html))


@pytest.mark.parametrize("kind", DESK_KINDS)
def test_DEC_111_L_INBOX_kinds_J_TRACK_a_desk_kind_comes_from_the_review_desk_and_never_names_the_reviewer(
    kind: str,
) -> None:
    conn, item, data, mail = _read(kind, REVIEWER)
    assert item["from"] == "system", kind  # drawn with the mark: no id, name, first name or initials
    assert item["body"]["sender"] == REVIEW_DESK_START == "The review desk", kind
    assert data["from"]["display"] == REVIEW_DESK_START and data["from"]["system"] is True, kind
    seen = "\n".join(
        (json.dumps(item, ensure_ascii=False), json.dumps(data, ensure_ascii=False, default=str), mail)
    )
    for trace in REVIEWER_TRACES:
        assert trace not in seen, (kind, trace)
    assert f"{REVIEW_DESK_START} {item['line']}" in mail, kind
    assert REVIEWER not in conn.people_read, kind  # not read at all, so no future template can name them


@pytest.mark.parametrize("kind", DESK_KINDS)
def test_DEC_111_L_INBOX_kinds_a_desk_kind_posted_with_no_sender_still_reads_the_review_desk(
    kind: str,
) -> None:
    """Lane E's reading: a desk kind always reads "the review desk", whoever posted it and whoever reads it."""
    _, item, _, _ = _read(kind, None)
    assert (item["from"], item["body"]["sender"]) == ("system", REVIEW_DESK_START), kind


@pytest.mark.parametrize("kind", SYSTEM_KINDS)
def test_DEC_111_L_INBOX_kinds_the_1pc_clubs_own_kinds_name_no_one_even_when_a_reviewer_set_them_off(
    kind: str,
) -> None:
    """Lane B posts a hand-sent "Send a reminder" with the reviewer as its sender: it still reads "1% Club"."""
    conn, item, data, mail = _read(kind, REVIEWER)
    assert (item["from"], item["body"]["sender"]) == ("system", "1% Club"), kind
    seen = "\n".join(
        (json.dumps(item, ensure_ascii=False), json.dumps(data, ensure_ascii=False, default=str), mail)
    )
    for trace in REVIEWER_TRACES:
        assert trace not in seen, (kind, trace)
    assert REVIEWER not in conn.people_read, kind


def test_DEC_111_J_TRACK_the_answer_reminder_reads_the_review_desks_questions() -> None:
    """answer_reminder 1.1 (BLD-A222): "1 day left to answer the review desk’s questions", in the row, the subject
    and the email; never "Meera’s questions" as the board drew it. The typographic apostrophe, as every line."""
    _, item, data, mail = _read("answer_reminder", REVIEWER)
    line = "1 day left to answer the review desk’s questions"
    assert item["line"] == line and "asker" not in data
    assert mail.startswith(line) and f"{line} about **" not in mail and line in mail


def test_DEC_111_L_INBOX_kinds_the_questions_item_keeps_its_count_and_set_without_the_asker() -> None:
    _, item, _, _ = _read("questions", REVIEWER)
    assert item["line"] == "asked you 3 questions" and item["body"]["set_id"] == SET
    assert item["body"]["heading"] == "Questions from the review desk"


def test_DEC_111_L_INBOX_kinds_a_desk_merge_still_names_the_other_sharer_not_the_reviewer() -> None:
    """`other.possessive` is the other sharer's first name (L-INBOX.kinds "merged your idea with Ravi’s")."""
    _, item, _, _ = _read("desk_merge", REVIEWER)
    assert item["line"] == "merged your idea with Ravi’s"


def test_DEC_111_L_INBOX_kinds_the_ones_committee_still_signs_by_name() -> None:
    """COMMITTEE_KINDS keep the member's full name, role and initials: DEC-111 hides only the review desk's people."""
    _, item, _, mail = _read("decision_reversed", MEMBER)
    assert item["body"]["sender"] == "Rohan Mehta from the Ones Committee"
    assert item["from"] == {
        "id": MEMBER,
        "name": "Rohan Mehta",
        "first_name": "Rohan",
        "initials": "RM",
        "role_label": "from the Ones Committee",
    }
    assert "Rohan Mehta from the Ones Committee reversed a decision on your idea" in mail


def test_DEC_111_a_teamup_answer_still_names_its_lead() -> None:
    """Kinds outside the desk keep their sender as before (a crew lead is not at the review desk)."""
    conn = _Conn()
    row = {**_row("teamup_answer", OTHER), "payload": {"answer": "approve"}}
    item = render.item(conn, row, SHARER, NOW)  # type: ignore[arg-type]
    assert item["body"]["sender"] == "Ravi Nair" and item["from"]["initials"] == "RN"


# ---------------------------------------------------------------------------------------------------------------
# J-REVIEW's outgoing messages on the old routes: question, redirected, reviewed (BLD-A222)
# ---------------------------------------------------------------------------------------------------------------

DESK_EMAILS: dict[str, tuple[str, dict[str, Any]]] = {
    "idea.question": ("question", {"idea_id": "IDEA-2026-000900", "question_id": 7}),
    "idea.redirected": ("redirected", {"idea_id": "IDEA-2026-000900", "redirect_kind": "it_helpdesk"}),
    "idea.reviewed": (
        "reviewed",
        {"idea_id": "IDEA-2026-000900", "outcome": "standalone", "next_step": "review"},
    ),
}


@pytest.mark.parametrize("event", sorted(DESK_EMAILS))
def test_DEC_111_J_REVIEW_the_desks_emails_sign_as_the_review_desk_and_never_read_the_reviewer(
    event: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = {
        "it_helpdesk": {"team": "IT Helpdesk", "message": "IT Helpdesk can fix this one.", "url": None}
    }
    monkeypatch.setattr(crender, "load_rule", lambda *_: types.SimpleNamespace(data={"targets": targets}))
    name, refs = DESK_EMAILS[event]
    conn = _Conn()
    data = crender.variables(conn, SHARER, event, {**refs, "reviewer_user_id": REVIEWER})  # type: ignore[arg-type]
    tpl = templates._load(SEED, name)
    subject, body = templates.render_text(tpl.subject, data), templates.render_text(tpl.body, data)
    assert body.rstrip().endswith(f"{REVIEW_DESK_START}, 1% Club\n\nA KFintech programme"), event
    assert "name" not in data.get("reviewer", {}), event
    for trace in REVIEWER_TRACES:
        assert trace not in subject + body + json.dumps(data, default=str), (event, trace)
    assert REVIEWER not in conn.people_read, event
    assert "{{" not in subject + body and "review desk, 1% Club" not in body.replace(REVIEW_DESK_START, ""), (
        event
    )


def test_DEC_111_J_REVIEW_the_question_email_speaks_as_the_desk() -> None:
    """question 1.2: the desk signs as a whole, so the opening is "We’re reviewing", not "I’m reviewing"."""
    body = templates._load(SEED, "question").body
    assert body.startswith("Hi {{recipient.first_name}},\n\nWe're reviewing your idea") and "I'm" not in body


def test_DEC_111_no_comms_template_names_a_reviewer_or_an_asker() -> None:
    """Nothing in the company repo's comms reads a reviewer's or an asker's name, so none can come back by a
    template edit alone; every template this branch changed waits for HR."""
    folder = SEED / "comms"
    for path in sorted(folder.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for var in ("reviewer.name", "reviewer.first_name", "reviewer.initials", "asker."):
            assert var not in text, (path.name, var)
    for name, version in (("inbox/answer_reminder", "1.1"), ("question", "1.2"), ("redirected", "1.3"),
                          ("reviewed", "1.4")):  # fmt: skip
        path = folder / "templates" / f"{name}.md"
        text = path.read_text(encoding="utf-8")
        assert f"version: '{version}'" in text and "hr_signed_off: false" in text, name
        assert templates._load(SEED, name).version == version
