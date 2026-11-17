"""The second independent review of lane B's back end (17 Nov 2026), each finding pinned by a test against the
database: bodies of the wrong type, co-sharers' drafts, the crew told of decisions, the panel and the asked lines,
answer files by check state (DEC-107), more time on an overdue set and a sweep that carries on past a bad item."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import adapters, asking, clocks, committee, decide, merging, reads, revise
from desk.store import Refused
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

SENT = f.at(16, 11, 20)  # Monday 16 November 2026, 11:20 am IST
QS: list[dict[str, Any]] = [
    {"part": "often", "text": "Is the 40 calls a day at one branch, or across Hyderabad?"},
    {"part": "evidence", "text": "Can you add a screenshot of the SMS, with the folio hidden?"},
]
REASON = "A clear problem, a real number and a simple fix that the branch can try."
MERGE_NOTE = "You both found the same R07 calls in Hyderabad."


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, repo: Path) -> dict[str, Any]:
    kavya, ravi = f.person(db, "Kavya Menon"), f.person(db, "Ravi Nair")
    return {
        "kavya": kavya, "ravi": ravi,
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "anil": f.person(db, "Anil Kapoor", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "idea": f.idea(db, kavya),
    }  # fmt: skip


def _send(db: Conn, cast: dict[str, Any], by: str = "meera", **body: Any) -> dict[str, Any]:
    return asking.send_set(
        db, cast["idea"]["idea_id"], cast[by]["id"], {"questions": QS, "time_to_answer": "3d", **body}, SENT
    )


def _refused(fn: Any, *args: Any) -> Refused:
    with pytest.raises(Refused) as refused:
        fn(*args)
    return refused.value


# ---- finding 3: a list, object or number in a body is refused in the pack's shape, never a 500 ----------------
def test_L_WORTH_a_list_object_or_number_where_a_figure_belongs_is_refused(
    db: Conn, cast: dict[str, Any]
) -> None:
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    for body, code, field in (
        ({"outside_tools": []}, "outside_tools_invalid", "outside_tools"),
        ({"outside_tools": {}}, "outside_tools_invalid", "outside_tools"),
        ({"hours_month": 70}, "worth_invalid", "hours_month"),
        ({"hours_month": ["70"]}, "worth_invalid", "hours_month"),
        ({"worth": {"cost_month": {"low": 1}}}, "worth_invalid", "cost_month"),
        ({"hours_month": "99,99,99,99,999"}, "worth_invalid", "hours_month"),  # past numeric(12,2)
        ({"revenue_month": "1 to 5,00,000 crore"}, "worth_invalid", "revenue_month"),  # past numeric(14,2)
    ):
        e = _refused(revise.revise_worth, db, ref, meera, body)
        assert (e.status, e.code, e.field) == (422, code, field), body
    e = _refused(revise.revise_worth, db, ref, meera, {"cost_month": "1,20,00,00,00,00,000"})
    assert e.message == "That figure is too large. Check it and write it again."
    assert db.execute("SELECT count(*) AS n FROM idea_worth").fetchone() == {"n": 0}
    ok = revise.revise_worth(db, ref, meera, {"cost_month": "₹1,200 crore"})
    assert ok["reviewer"]["cost_month"]["low"] == 1.2e10


def test_L_QUESTIONS_answer_a_number_where_the_files_or_the_text_belong_is_refused(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = _send(db, cast)
    q1, kavya = sent["questions"][0]["id"], cast["kavya"]["id"]
    for text, file_ids, code, field in (
        ("Across Hyderabad.", 5, "file_not_found", "file_ids"),
        ("Across Hyderabad.", "ATT-2026-000001", "file_not_found", "file_ids"),
        ("Across Hyderabad.", [{"id": "ATT-2026-000001"}], "file_not_found", "file_ids"),
        ({"text": "Across Hyderabad."}, None, "answer_invalid", "text"),
        (["Across Hyderabad."], None, "answer_invalid", "text"),
    ):
        e = _refused(asking.save_answer, db, q1, kavya, text, file_ids)
        assert (e.status, e.code, e.field) == (422, code, field)
    assert asking.save_answer(db, q1, kavya, None, None)["text"] == ""


# ---- finding 6: WorthResponse is what the worker returns (figures, the person under reviewer.by) ----------------
def test_L_WORTH_the_revision_response_matches_the_shared_sample(db: Conn, cast: dict[str, Any]) -> None:
    """desk/worth_response_sample.json is what apps/web/tests/unit/desk-worth.test.ts checks `WorthResponse` against."""
    import json

    sample = json.loads(
        (Path(__file__).parents[1] / "desk" / "worth_response_sample.json").read_text("utf-8")
    )
    sample.pop("_about")
    db.execute(
        "INSERT INTO idea_worth (idea_uuid, by_side, by_code, hours_low, hours_high, cost_low, outside_tools, at) "
        "VALUES (%s, 'sharer', %s, 70, 150, 25000, 'none', %s)",
        (cast["idea"]["id"], cast["kavya"]["code"], f.at(14, 10)),
    )
    got = revise.revise_worth(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                              {"hours_month": "120 to 200", "outside_tools": "partly",
                               "note": "Every branch in the region takes these calls, not one."}, SENT)  # fmt: skip
    got = json.loads(json.dumps(got))
    for key in ("idea_id", "worth_id"):
        got[key] = sample[key]
    got["reviewer"]["by"]["id"] = sample["reviewer"]["by"]["id"]
    assert dt.datetime.fromisoformat(got["reviewer"]["at"]) == SENT
    got["reviewer"]["at"] = sample["reviewer"]["at"]
    assert got == sample


def _merge_ravi_in(db: Conn, cast: dict[str, Any]) -> dict[str, Any]:
    """Ravi's idea joins Kavya's at the desk: Ravi is credited (own_codes) and joins the crew."""
    theirs = f.idea(db, cast["ravi"], title="Rejection SMS codes confuse investors", shared_at=f.at(2, 15))
    merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                       {"other_idea_id": theirs["idea_id"], "lead": "this", "team_up": True, "note": MERGE_NOTE},
                       f.at(16, 10))  # fmt: skip
    return theirs


# ---- finding 4: a credited co-sharer never sees, sends or overwrites another sharer's draft ---------------------
def test_L_QUESTIONS_answer_4_a_draft_answer_stays_with_the_sharer_who_wrote_it(
    db: Conn, cast: dict[str, Any]
) -> None:
    _merge_ravi_in(db, cast)
    sent = _send(db, cast)
    ref, kavya, ravi = cast["idea"]["idea_id"], cast["kavya"]["id"], cast["ravi"]["id"]
    q1, q2 = (q["id"] for q in sent["questions"])
    asking.save_answer(db, q1, kavya, "One branch, about 40 a day.", at=SENT)
    seen_by_ravi = asking.open_set_for_sharer(db, ref, ravi, SENT)
    assert seen_by_ravi is not None and [q["answer"] for q in seen_by_ravi["questions"]] == [None, None]
    e = _refused(asking.save_answer, db, q1, ravi, "All of Hyderabad.")
    assert (e.status, e.code) == (409, "answer_in_progress")
    assert _refused(asking.send_answers, db, sent["id"], ravi).code == "nothing_answered"
    asking.save_answer(db, q2, ravi, "The SMS says R07 and nothing else.", at=SENT)
    assert asking.send_answers(db, sent["id"], ravi, SENT)["sent"] == 1
    mine = asking.open_set_for_sharer(db, ref, kavya, SENT)
    assert mine is not None
    first, second = (q["answer"] for q in mine["questions"])
    assert (first["text"], first["sent"]) == ("One branch, about 40 a day.", False)  # still Kavya's to send
    assert second["sent"] is True and second["by"]["first_name"] == "Ravi"
    assert asking.send_answers(db, sent["id"], kavya, SENT)["state"] == "answered"


# ---- finding 5: the crew is told of a decision and of a reversal (L-INBOX.kinds) --------------------------------
def _told(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str]]]:
    calls: list[tuple[str, list[str]]] = []

    def tell(conn: Conn, kind: str, recipients: list[str], **_: Any) -> None:
        calls.append((kind, list(recipients)))

    monkeypatch.setattr(adapters, "tell", tell)
    return calls


def test_L_INBOX_kinds_a_decision_goes_to_the_sharer_and_crew_a_reversal_to_the_reviewer_too(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    farhan, sneha = f.person(db, "Farhan Shaikh"), f.person(db, "Sneha Kulkarni")
    f.crew(db, cast["idea"], farhan)
    f.crew(db, cast["idea"], sneha)
    db.execute(
        "UPDATE crew_members SET left_at = %s, left_how = 'left' WHERE contributor_code = %s",
        (f.at(15, 9), sneha["code"]),
    )
    told = _told(monkeypatch)
    kavya, meera = cast["kavya"]["id"], cast["meera"]["id"]
    decide.send(db, cast["idea"]["idea_id"], meera, {"choice": "pick", "reason": REASON}, f.at(16, 10))
    assert told == [
        ("decision", [kavya, farhan["id"]])
    ]  # Kavya leads the crew too: told once; Sneha has left
    window = db.execute("SELECT id FROM decision_windows").fetchone()
    assert window is not None
    committee.reverse_window(db, str(window["id"]), cast["rohan"]["id"],
                             {"to": "not_picked", "note": "The SMS vendor is changing; this goes with the new one."},
                             f.at(17, 10))  # fmt: skip
    assert told[-1] == ("decision_reversed", [kavya, farhan["id"], meera])


# ---- finding 7: a Not now that came back and was then merged shows the merge, not the old decision --------------
def test_L_REVIEW_panel_merged_is_checked_before_an_old_decision(db: Conn, cast: dict[str, Any]) -> None:
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    decide.send(db, ref, meera, {"choice": "not_now", "reason": REASON, "return_in": "1m"}, f.at(16, 10))
    back = f.at(17, 9, m=12)
    assert clocks.return_due(db, back) == 1
    theirs = f.idea(
        db, cast["ravi"], title="Rejection SMS codes confuse investors", shared_at=f.at(14, 9, m=12)
    )
    merging.desk_merge(db, ref, meera, {"other_idea_id": theirs["idea_id"], "lead": "other", "team_up": True,
                                        "note": MERGE_NOTE}, f.at(17, 10, m=12))  # fmt: skip
    assert reads.reviewer_idea(db, ref, meera, f.at(17, 11, m=12))["panel"] == {"state": "merged"}


# ---- finding 9: "You asked" only for the viewer's own questions ---------------------------------------------------
def test_S_R2_left_3_another_reviewers_question_reads_with_their_first_name(
    db: Conn, cast: dict[str, Any]
) -> None:
    _send(db, cast, by="anil")
    ref = cast["idea"]["idea_id"]

    def lines(viewer: str) -> list[str]:
        page = reads.reviewer_idea(db, ref, cast[viewer]["id"], SENT)
        return [q["asked_line"] for p in page["parts"] for q in p["questions"]]

    assert lines("meera") == ["Anil asked, today 11:20 am"] * 2
    assert lines("anil") == ["You asked, today 11:20 am"] * 2


# ---- finding 10 (DEC-107): the desk sees checked files and marked customer-detail ones; nobody sees checking ------
def _file(db: Conn, idea: dict[str, Any], sharer: dict[str, str], n: int, state: str) -> str:
    fid = f"ATT-2026-{n:06d}"
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, mime, bytes, store_key, kind, file_state) "
        "VALUES (%s, %s, %s, %s, 'image/png', 2048, %s, 'file', %s)",
        (fid, idea["id"], sharer["code"], f"sms-{n}.png", f"clean/{fid}", state),
    )
    return fid


def test_S_R2_DEC_107_files_by_check_state_on_the_reviewer_page_and_for_a_co_sharer(
    db: Conn, cast: dict[str, Any]
) -> None:
    _merge_ravi_in(db, cast)
    kavya, idea = cast["kavya"], cast["idea"]
    attached = {s: _file(db, idea, kavya, n, s) for n, s in enumerate(
        ("checked", "personal_data_found", "checking", "infected", "locked"), start=801)}  # fmt: skip
    sent = _send(db, cast)
    q2 = sent["questions"][1]["id"]
    on_answer = {s: _file(db, idea, kavya, n, s) for n, s in enumerate(
        ("hidden_checked", "personal_data_found", "checking", "infected"), start=811)}  # fmt: skip
    asking.save_answer(db, q2, kavya["id"], "Two screenshots of the SMS.", list(on_answer.values()), SENT)
    asking.send_answers(db, sent["id"], kavya["id"], SENT)
    page = reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], SENT)
    files = [(a["id"], a["customer_detail"]) for a in page["artefacts"] if a["kind"] == "file"]
    assert files == [
        (attached["checked"], False), (attached["personal_data_found"], True),
        (on_answer["hidden_checked"], False), (on_answer["personal_data_found"], True),
    ]  # fmt: skip
    answer = next(p for p in page["parts"] if p["part"] == "evidence")["questions"][0]["answer"]
    assert [(x["id"], x["customer_detail"]) for x in answer["files"]] == [
        (on_answer["hidden_checked"], False), (on_answer["personal_data_found"], True)
    ]  # fmt: skip
    # Ravi, credited through the merge, reads Kavya's sent answer: the checked file only, never the marked one
    seen = asking.open_set_for_sharer(db, idea["idea_id"], cast["ravi"]["id"], SENT)
    assert seen is not None
    assert [x["id"] for x in seen["questions"][1]["answer"]["files"]] == [on_answer["hidden_checked"]]
    # the listen script is the same for every viewer: no file with a customer detail is named in it
    script = reads.listen_script(db, idea["idea_id"], cast["meera"]["id"])
    evidence = next(p for p in script["parts"] if p["part"] == "evidence")["text"]
    assert "sms-801.png" in evidence and "sms-802.png" not in evidence


# ---- finding 8: "Give 2 more days" on an overdue set counts from now, and reminds before the new deadline --------
def test_L_QUESTIONS_clock_3_more_time_on_an_overdue_set_is_never_still_overdue(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = _send(db, cast, time_to_answer="1d")  # due Tuesday 17 November, 11:20 am
    late = f.at(18, 10)  # overdue by nearly a day
    got = asking.give_more_time(db, sent["id"], cast["meera"]["id"], late)
    # two days on, at 6 pm office time on that working day (L-QUESTIONS.clock/5)
    assert dt.datetime.fromisoformat(got["due_at"]) == f.at(20, 18)
    assert got["countdown"] == {"label": "2 days to answer", "variant": "normal"}
    assert (
        reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], late)["panel"]["variant"]
        == "normal"
    )
    assert clocks.run_due(db, f.at(19, 17))["reminded"] == 0
    assert clocks.run_due(db, f.at(19, 18, 5))["reminded"] == 1  # a day before the new deadline
    assert clocks.run_due(db, f.at(20, 16, 5))["reminded"] == 1  # and two hours before


# ---- finding 12: one failing item never undoes the rest of the sweep, and the lock is let go --------------------
def test_L_DECIDE_rules_7_a_failing_item_is_logged_and_the_sweep_carries_on(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch, test_database: str
) -> None:
    from core.db import connect
    from tests import helpers

    meera = cast["meera"]["id"]
    second = f.idea(db, cast["ravi"], title="Branch queue times are not tracked anywhere")
    for idea in (cast["idea"], second):
        decide.send(db, idea["idea_id"], meera, {"choice": "not_now", "reason": REASON, "return_in": "1m"},
                    f.at(16, 10))  # fmt: skip
    real = decide.return_from_not_now

    def flaky(conn: Conn, idea_uuid: str, at: Any = None) -> bool:
        if idea_uuid == str(cast["idea"]["id"]):
            raise RuntimeError("synthetic failure")
        return real(conn, idea_uuid, at)

    monkeypatch.setattr(decide, "return_from_not_now", flaky)
    got = clocks.run_due(db, f.at(17, 9, m=12))
    assert got == {"returned": 1, "windows_closed": 2, "reminded": 0}  # both 30-day windows ended too

    def status(idea: dict[str, Any]) -> str:
        row = db.execute("SELECT status FROM ideas WHERE id = %s", (idea["id"],)).fetchone()
        assert row is not None
        return str(row["status"])

    assert (status(cast["idea"]), status(second)) == ("not_now", "with_review_desk")
    assert db.execute("SELECT count(*) AS n FROM decision_windows WHERE state = 'expired'").fetchone() == {
        "n": 2
    }
    other = connect(helpers.db_url(test_database), autocommit=True)
    try:  # the session lock was let go: another connection takes it at once
        held = other.execute("SELECT pg_try_advisory_lock(%s) AS got", (clocks.SWEEP_LOCK,)).fetchone()
        assert held == {"got": True}
        other.execute("SELECT pg_advisory_unlock(%s)", (clocks.SWEEP_LOCK,))
    finally:
        other.close()
    monkeypatch.setattr(decide, "return_from_not_now", real)
    assert clocks.run_due(db, f.at(17, 9, 5, m=12))["returned"] == 1  # the next run picks it up


# ---- finding 11: a Needs you item leaves the list once its action is done (L-INBOX.rules/3) ----------------------
class _Notify:
    """A stand-in for lane A's `notify` with `resolve`: records each key, as `notify.resolve` would clear it."""

    def __init__(self, with_resolve: bool) -> None:
        self.posted: list[tuple[str, str | None]] = []
        self.resolved: list[str] = []
        if with_resolve:
            self.resolve = self._resolve

    def post(self, conn: Conn, kind: str, recipients: list[str], **kw: Any) -> None:
        self.posted.append((kind, kw.get("dedupe_key")))

    def Action(self, **kw: Any) -> dict[str, Any]:  # notify.Action is a class
        return kw

    def _resolve(self, conn: Conn, dedupe_key: str, *, recipients: Any = None) -> int:
        self.resolved.append(dedupe_key)
        return 1


def test_L_INBOX_rules_3_answers_sent_and_a_decision_resolve_the_questions_item(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    notify = _Notify(with_resolve=True)
    monkeypatch.setitem(sys.modules, "notify", notify)
    sent = _send(db, cast)
    sid, kavya = sent["id"], cast["kavya"]["id"]
    assert ("questions", f"qs:{sid}") in notify.posted
    q1, q2 = (q["id"] for q in sent["questions"])
    asking.save_answer(db, q1, kavya, "One branch, about 40 a day.", at=SENT)
    asking.send_answers(db, sid, kavya, SENT)
    assert notify.resolved == []  # one of two answered: the questions still need Kavya
    asking.save_answer(db, q2, kavya, "The SMS says R07 and nothing else.", at=SENT)
    asking.send_answers(db, sid, kavya, SENT)
    assert notify.resolved == [f"qs:{sid}"]  # every reminder key sits under it
    # a decision closes an open set: its item goes too
    second = f.idea(db, cast["ravi"], title="Branch queue times are not tracked anywhere")
    other = asking.send_set(db, second["idea_id"], cast["meera"]["id"], {"questions": QS[:1]}, SENT)
    decide.send(
        db, second["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, f.at(16, 12)
    )
    assert notify.resolved[-1] == f"qs:{other['id']}"
    # and so does a desk merge that closes the joining idea's set
    third = f.idea(db, cast["anil"], title="SMS codes, one more time", shared_at=f.at(15, 9))
    joined = asking.send_set(db, third["idea_id"], cast["meera"]["id"], {"questions": QS[:1]}, SENT)
    merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                       {"other_idea_id": third["idea_id"], "lead": "this", "team_up": False, "note": MERGE_NOTE},
                       f.at(16, 13))  # fmt: skip
    assert notify.resolved[-1] == f"qs:{joined['id']}"


def test_L_INBOX_rules_3_without_notify_resolve_nothing_happens(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    notify = _Notify(with_resolve=False)
    monkeypatch.setitem(sys.modules, "notify", notify)
    assert adapters.resolve(db, "qs:00000000-0000-4000-8000-000000000001") == 0
    sent = _send(db, cast)
    q1, q2 = (q["id"] for q in sent["questions"])
    for q in (q1, q2):
        asking.save_answer(db, q, cast["kavya"]["id"], "Answered for the test.", at=SENT)
    assert asking.send_answers(db, sent["id"], cast["kavya"]["id"], SENT)["state"] == "answered"
    assert notify.resolved == [] and not hasattr(notify, "resolve")
