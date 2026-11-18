"""L-HIDE on the review side (BLD-B246): the desk reads why a detail was shown (L-HIDE.rules/6, S-R2), the desk's own
words are masked through lane C's `hide.hide_text` with who wrote them, and a sharer's answer keeps its details'
ids across autosaves. Synthetic people and values only (non-negotiable 11); every row made is removed at the end
(`clean_up_desk_rows`; hidden_details and the sealed words go with the idea)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import adapters, asking, reads
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 13, 20)


def cast_conn(value: object) -> Conn:
    """A stand-in connection for a call that never reaches the database."""
    return value  # type: ignore[return-value]


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
    kavya = f.person(db, "Kavya Menon")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    asha = f.person(db, "Asha Kulkarni", roles=("committee",))
    arjun = f.person(db, "Arjun Rao")  # no desk or committee role
    return {"kavya": kavya, "meera": meera, "asha": asha, "arjun": arjun, "idea": f.idea(db, kavya)}


def _detail(db: Conn, idea_uuid: str, *, kind: str, masked: str, tag: str, state: str = "hidden",
            reason: str | None = None, by: str | None = None, at: Any = None, source_id: str = "m-1") -> None:  # fmt: skip
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked, vault_tag, state, reason, shown_by, "
        "shown_at, created_at) VALUES (%s, 'message', %s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()))",
        (idea_uuid, source_id, kind, masked, tag, state, reason, by, at, at),
    )


def test_L_HIDE_rules_6_S_R2_the_desk_reads_what_was_shown_and_why_one_line_per_value(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea, kavya = cast["idea"], cast["kavya"]
    # the folio shown in two copies (one value, one vault tag), a PAN shown once, a phone number still hidden
    _detail(db, idea["id"], kind="folio", masked="Folio ••••89", tag="[[FOLIO_NUMBER_1]]", state="shown",
            reason="internal_reference", by=kavya["id"], at=f.at(14, 10, 0))  # fmt: skip
    _detail(db, idea["id"], kind="folio", masked="Folio ••••89", tag="[[FOLIO_NUMBER_1]]", state="shown",
            reason="internal_reference", by=kavya["id"], at=f.at(14, 10, 5), source_id="m-2")  # fmt: skip
    _detail(db, idea["id"], kind="pan", masked="PAN ••••4F", tag="[[PAN_1]]", state="shown",
            reason="made_up_example", by=kavya["id"], at=f.at(14, 11, 0))  # fmt: skip
    _detail(db, idea["id"], kind="phone", masked="Phone ••••10", tag="[[PHONE_1]]")
    _detail(db, idea["id"], kind="phone", masked="Phone ••••10", tag="[[PHONE_1]]", source_id="m-2")

    for reader in ("meera", "asha"):  # the review desk and the Ones Committee
        got = reads.reviewer_idea(db, idea["idea_id"], cast[reader]["id"], NOW)
        assert [s["line"] for s in got["shown"]] == [
            "Folio shown, because it’s an internal reference.",
            "PAN shown, because it’s made up for the example.",
        ]
        first = got["shown"][0]
        assert (first["kind"], first["reason"], first["because"], first["by"]) == (
            "folio", "internal_reference", "it’s an internal reference", "Kavya",
        )  # fmt: skip
        assert first["at"].startswith("2026-11-14T04:35")  # the later of the two showings, 10:05 am IST
        # the hidden line stays hidden-only, one per value: "Phone ••••10 is hidden from everyone."
        evidence = next(p for p in got["parts"] if p["part"] == "evidence")
        assert evidence["text"] == "Phone ••••10 is hidden from everyone."
        assert "Folio" not in evidence["text"] and "PAN" not in evidence["text"]

    # anyone else reads no reasons (the route refuses them first; the read itself gives nothing either)
    assert reads.reviewer_idea(db, idea["idea_id"], cast["arjun"]["id"], NOW)["shown"] == []


def test_L_HIDE_rules_6_S_R2_nothing_shown_reads_an_empty_list(db: Conn, cast: dict[str, Any]) -> None:
    got = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], NOW)
    assert got["shown"] == []


def test_L_HIDE_rules_7_S_R2_messages_and_answers_carry_their_ids_for_hide_this(
    db: Conn, cast: dict[str, Any]
) -> None:
    from desk.store import seal

    msg = db.execute(
        "INSERT INTO idea_messages (idea_uuid, seq, via, text_encrypted, created_at) VALUES (%s, 1, 'typed', %s, %s) "
        "RETURNING id",
        (cast["idea"]["id"], b"x", f.at(14, 9, 50)),
    ).fetchone()
    assert msg is not None
    db.execute(
        "UPDATE idea_messages SET text_encrypted = %s WHERE id = %s",
        (seal("Investors keep calling.", "idea_messages", "text_encrypted", str(msg["id"])), msg["id"]),
    )
    got = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], NOW)
    assert got["own_words"][0]["id"] == str(msg["id"])


def test_L_HIDE_adapters_hide_calls_lane_C_hide_text_with_who_wrote_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, ...]] = []

    def spy(conn: Any, idea_uuid: str, text: str, **kw: Any) -> tuple[str, int]:
        calls.append((conn, idea_uuid, text, kw))
        return "masked", 1

    monkeypatch.setattr(adapters, "hide_text", spy)
    conn = cast_conn("conn")
    assert adapters.hide(conn, "idea-1", "words", by="user-1") == ("masked", 1)
    assert adapters.hide(conn, "idea-1", "words", by="user-2", source="answer", source_id="a-1") == (
        "masked",
        1,
    )
    assert calls == [
        ("conn", "idea-1", "words", {"by": "user-1", "source": "desk", "source_id": None}),
        ("conn", "idea-1", "words", {"by": "user-2", "source": "answer", "source_id": "a-1"}),
    ]


def test_L_HIDE_adapters_hide_the_desks_words_are_masked_and_stored_under_the_idea(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea, meera = cast["idea"], cast["meera"]
    with db.transaction():
        masked, n = adapters.hide(
            db, str(idea["id"]), "Did the investor on 9876543210 call twice?", by=meera["id"]
        )
    assert n == 1 and "9876543210" not in masked and "••••10" in masked
    rows = db.execute(
        "SELECT source, kind, state FROM hidden_details WHERE idea_uuid = %s", (idea["id"],)
    ).fetchall()
    assert [(r["source"], r["kind"], r["state"]) for r in rows] == [("desk", "phone", "hidden")]


def test_L_HIDE_rules_4_L_QUESTIONS_answer_6_an_answer_keeps_its_details_across_autosaves(
    db: Conn, cast: dict[str, Any]
) -> None:
    sent = asking.send_set(
        db, cast["idea"]["idea_id"], cast["meera"]["id"],
        {"questions": [{"part": "summary", "text": "Is it mostly R07?"}], "time_to_answer": "3d"}, f.at(16, 11, 20),
    )  # fmt: skip
    qid, kavya = sent["questions"][0]["id"], cast["kavya"]["id"]
    text = "Mostly R07. Folio 1234567890 got it twice last week."
    first = asking.save_answer(db, qid, kavya, text, at=f.at(16, 12, 10))
    again = asking.save_answer(db, qid, kavya, text + " And once more today.", at=f.at(16, 12, 12))
    assert first["id"] == again["id"] and "1234567890" not in again["text"]
    rows = db.execute(
        "SELECT id, source, source_id FROM hidden_details WHERE idea_uuid = %s", (cast["idea"]["id"],)
    ).fetchall()
    assert len(rows) == 1  # the same detail, not one per autosave
    assert (rows[0]["source"], rows[0]["source_id"]) == ("answer", first["id"])
    # the sharer's own words are kept sealed for them alone, under the answer's id
    from hide import core

    assert core.own_words(db, "answer", first["id"], idea_uuid=str(cast["idea"]["id"])) == text + (
        " And once more today."
    )
    # an emptied box hides nothing any more
    asking.save_answer(db, qid, kavya, "", at=f.at(16, 12, 14))
    left = db.execute(
        "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s", (cast["idea"]["id"],)
    ).fetchone()
    assert left is not None and left["n"] == 0


# ---- BLD-B247: the review round of 18 Nov ----------------------------------------------------------------------


def _message(db: Conn, idea_uuid: str, text: str) -> str:
    """One of the sharer's messages, stored as the masked copy (here, nothing was caught: a detail the checks missed)."""
    from desk.store import seal

    row = db.execute(
        "INSERT INTO idea_messages (idea_uuid, seq, via, text_encrypted, created_at) VALUES (%s, 1, 'typed', %s, %s) "
        "RETURNING id",
        (idea_uuid, b"x", f.at(14, 9, 50)),
    ).fetchone()
    assert row is not None
    mid = str(row["id"])
    db.execute(
        "UPDATE idea_messages SET text_encrypted = %s WHERE id = %s",
        (seal(text, "idea_messages", "text_encrypted", mid), mid),
    )
    return mid


def test_L_HIDE_rules_7_BLD_B247_a_desk_hide_and_a_decision_on_one_idea_queue_and_never_deadlock(
    db: Conn, cast: dict[str, Any], test_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two connections, no load: the decision holds the idea's rows when the reviewer's "Hide this" starts. Before
    BLD-B247 the hide took lane C's lock, then waited on the idea's row (its new hidden_details row points at it),
    while the decision, holding that row, waited on the lock: 40P01. Now the decision takes the lock first, so the
    hide waits on the lock itself, holding nothing, and goes through once the decision is in."""
    import threading

    import psycopg

    from core.db import connect
    from desk import decide
    from hide import desk_hide
    from tests import helpers

    idea, meera = cast["idea"], cast["meera"]
    text = "Call the investor back on 9876501234 before Friday."
    mid = _message(db, str(idea["id"]), text)
    start = text.index("9876501234")
    other = connect(helpers.db_url(test_database), autocommit=True)
    other.execute("SET lock_timeout = '20s'")  # a regression fails on the lock, not on the join's timeout
    hid: dict[str, Any] = {}
    errors: list[BaseException] = []
    waited_on: list[str] = []

    def hide_now() -> None:
        try:
            hid.update(desk_hide(other, str(idea["id"]), source_kind="message", source_id=mid, start=start,
                                 end=start + 10, by=meera["id"]))  # fmt: skip
        except BaseException as exc:  # reported below
            errors.append(exc)

    hider = threading.Thread(target=hide_now, daemon=True)  # never holds the test run open
    real_refuse_own = decide.refuse_own

    def refuse_own_then_let_the_hide_start(conn: Conn, *a: Any, **kw: Any) -> None:
        real_refuse_own(conn, *a, **kw)
        if hider.ident is not None:
            return
        hider.start()  # the decision holds the idea's row (and, now, lane C's lock)
        for _ in range(200):  # until the hide is waiting on a lock
            row = conn.execute(
                "SELECT wait_event_type, wait_event FROM pg_stat_activity WHERE pid = %s",
                (other.info.backend_pid,),
            ).fetchone()
            if row is not None and row["wait_event_type"] == "Lock":
                waited_on.append(str(row["wait_event"]))
                return
            conn.execute("SELECT pg_sleep(0.05)")
        raise AssertionError("the hide never waited")

    monkeypatch.setattr(decide, "refuse_own", refuse_own_then_let_the_hide_start)
    try:
        reason = "Not picked for now. The branch can fix this with a clearer SMS template."
        try:
            got = decide.send(
                db, idea["idea_id"], meera["id"], {"choice": "not_picked", "reason": reason}, NOW
            )
        except psycopg.errors.DeadlockDetected:  # pragma: no cover (the failure this test exists for)
            pytest.fail("the decision deadlocked with the desk's hide")
    finally:
        if hider.ident is not None:
            hider.join(timeout=30)
        # `other` is closed only once the thread is done with it; a thread still waiting is cancelled first
        if hider.is_alive():
            other.cancel_safe()
            hider.join(timeout=5)
        if not hider.is_alive():
            other.close()
    assert not hider.is_alive()
    assert not errors, [type(e).__name__ for e in errors]
    assert waited_on == ["advisory"]  # the hide queued on lane C's lock, holding no row
    assert got["choice"] == "not_picked" and hid["kind"] == "phone"


def _detail_from(db: Conn, idea_uuid: str, source: str, source_id: str, *, kind: str, masked: str, tag: str,
                 state: str = "hidden", reason: str | None = None, by: str | None = None) -> None:  # fmt: skip
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked, vault_tag, state, reason, shown_by, "
        "shown_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s = 'shown' THEN now() END)",
        (idea_uuid, source, source_id, kind, masked, tag, state, reason, by, state),
    )


def test_non_negotiable_7_L_HIDE_rules_6_BLD_B247_the_desk_reads_no_detail_from_a_draft_answer_or_its_own_words(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    sent = asking.send_set(
        db, idea["idea_id"], meera["id"],
        {"questions": [{"part": "summary", "text": "Did the investor on 9876543210 call twice?"},
                       {"part": "often", "text": "How many a day?"}], "time_to_answer": "3d"}, f.at(16, 11, 20),
    )  # fmt: skip
    q1, q2 = (q["id"] for q in sent["questions"])
    # a desk question holding a phone number: the desk's own words, hidden, never read back as the sharer's detail
    assert db.execute(
        "SELECT 1 FROM hidden_details WHERE idea_uuid = %s AND source = 'desk'", (idea["id"],)
    ).fetchone()
    # a draft answer holding another phone number, one detail of it shown: both stay Kavya's until she sends
    draft = asking.save_answer(db, q1, kavya["id"], "Yes, from 9123456780, twice.", at=f.at(16, 12, 10))
    _detail_from(db, idea["id"], "answer", draft["id"], kind="account", masked="Account ••••77", tag="[[ACCOUNT_NUMBER_9]]",
                 state="shown", reason="made_up_example", by=kavya["id"])  # fmt: skip
    got = reads.reviewer_idea(db, idea["idea_id"], meera["id"], NOW)
    evidence = next(p for p in got["parts"] if p["part"] == "evidence")
    assert "Phone" not in evidence["text"] and "••••" not in evidence["text"]
    assert got["shown"] == []
    # once sent, the answer's details are the desk's to read: "Phone ••••80 is hidden from everyone."
    asking.save_answer(db, q2, kavya["id"], "About 40.", at=f.at(16, 12, 11))
    asking.send_answers(db, sent["id"], kavya["id"], f.at(16, 12, 12))
    got = reads.reviewer_idea(db, idea["idea_id"], meera["id"], NOW)
    evidence = next(p for p in got["parts"] if p["part"] == "evidence")
    assert evidence["text"] == "Phone ••••80 is hidden from everyone."
    # L-HIDE.detect's label for each kind: "Phone shown, because …", not "Phone number"
    _detail_from(db, idea["id"], "message", "m-1", kind="phone", masked="Phone ••••21", tag="[[PHONE_9]]",
                 state="shown", reason="made_up_example", by=kavya["id"])  # fmt: skip
    got = reads.reviewer_idea(db, idea["idea_id"], meera["id"], NOW)
    assert [s["line"] for s in got["shown"]] == ["Phone shown, because it’s made up for the example."]


def test_L_HIDE_rules_1_BLD_B247_autosave_runs_the_patterns_and_sending_runs_the_gatekeeper_once(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from hide import core

    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    sent = asking.send_set(db, idea["idea_id"], meera["id"],
                           {"questions": [{"part": "summary", "text": "Is it mostly R07?"}], "time_to_answer": "3d"},
                           f.at(16, 11, 20))  # fmt: skip
    qid = sent["questions"][0]["id"]
    calls: list[tuple[str, bool]] = []
    real = adapters.hide_message

    def spy(conn: Conn, idea_uuid: str, text: str, **kw: Any) -> Any:
        calls.append((text, kw["gatekeeper"]))
        assert (kw["source"], kw["by"]) == ("answer", kavya["id"])
        return real(conn, idea_uuid, text, **kw)

    monkeypatch.setattr(adapters, "hide_message", spy)
    words = "Mostly R07. Folio 1234567890 got it twice."
    for n in range(3):  # three autosaves as she types: no model call
        asking.save_answer(db, qid, kavya["id"], words[: 20 + n * 11], at=f.at(16, 12, 10 + n))
    asking.save_answer(db, qid, kavya["id"], words, at=f.at(16, 12, 14))
    assert [g for _, g in calls] == [False, False, False, False]
    calls.clear()
    asking.send_answers(db, sent["id"], kavya["id"], f.at(16, 12, 20))
    # once, on her own words (not the masked copy), with the gatekeeper on
    assert calls == [(words, True)]
    aid = db.execute("SELECT id FROM answers WHERE question_id = %s", (qid,)).fetchone()
    assert aid is not None
    assert core.own_words(db, "answer", str(aid["id"]), idea_uuid=str(idea["id"])) == words


def test_L_HIDE_BLD_B247_a_refusal_from_hiding_reads_as_S_R3s_failure_line_never_raw(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from desk.store import Refused
    from hide import HideError

    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    sent = asking.send_set(db, idea["idea_id"], meera["id"],
                           {"questions": [{"part": "summary", "text": "Is it mostly R07?"}], "time_to_answer": "3d"},
                           f.at(16, 11, 20))  # fmt: skip
    qid = sent["questions"][0]["id"]
    asking.save_answer(db, qid, kavya["id"], "Mostly R07.", at=f.at(16, 12, 10))

    def refuse(*_: Any, **__: Any) -> Any:
        raise HideError(409, "conflict")

    monkeypatch.setattr(adapters, "hide_message", refuse)
    with pytest.raises(Refused) as saving:
        asking.save_answer(db, qid, kavya["id"], "Mostly R07, twice.", at=f.at(16, 12, 11))
    assert (saving.value.status, saving.value.code, saving.value.message) == (
        409, "answer_not_saved", "Couldn’t save that. Try again.",
    )  # fmt: skip
    with pytest.raises(Refused) as sending:
        asking.send_answers(db, sent["id"], kavya["id"], f.at(16, 12, 12))
    assert (sending.value.status, sending.value.code, sending.value.message) == (
        409, "answers_not_sent", "Your answers didn’t send. Try again.",
    )  # fmt: skip
    row = db.execute("SELECT sent_at FROM answers WHERE question_id = %s", (qid,)).fetchone()
    assert row is not None and row["sent_at"] is None  # nothing went


def test_L_HIDE_rules_4_L_QUESTIONS_answer_4_BLD_B247_an_emptied_answer_keeps_no_words_so_a_co_sharer_takes_it_over(
    db: Conn, cast: dict[str, Any]
) -> None:
    from desk import merging
    from hide import core

    idea, kavya, meera = cast["idea"], cast["kavya"], cast["meera"]
    ravi = f.person(db, "Ravi Nair")
    theirs = f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(2, 15))
    merging.desk_merge(db, idea["idea_id"], meera["id"],
                       {"other_idea_id": theirs["idea_id"], "lead": "this", "team_up": True,
                        "note": "The same SMS problem, raised twice. One team builds one fix."}, f.at(16, 10))  # fmt: skip
    sent = asking.send_set(db, idea["idea_id"], meera["id"],
                           {"questions": [{"part": "summary", "text": "Is it mostly R07?"}], "time_to_answer": "3d"},
                           f.at(16, 11, 20))  # fmt: skip
    qid = sent["questions"][0]["id"]
    first = asking.save_answer(db, qid, kavya["id"], "Folio 1234567890, mostly.", at=f.at(16, 12, 10))
    asking.save_answer(db, qid, kavya["id"], "", at=f.at(16, 12, 11))  # she empties the box
    key = core.sealed_key(str(idea["id"]), first["id"])
    assert (
        db.execute(
            "SELECT 1 FROM idea_words_sealed WHERE source = 'answer' AND source_id = %s", (key,)
        ).fetchone()
        is None
    )
    # Ravi takes the empty draft over and his words are sealed for him, under the same answer
    his = asking.save_answer(
        db, qid, ravi["id"], "All of Hyderabad, folio 7654321098 too.", at=f.at(16, 12, 12)
    )
    assert his["id"] == first["id"] and "7654321098" not in his["text"]
    owner = db.execute(
        "SELECT owner_user_id FROM idea_words_sealed WHERE source = 'answer' AND source_id = %s", (key,)
    ).fetchone()
    assert owner is not None and str(owner["owner_user_id"]) == ravi["id"]


def _one_question(db: Conn, cast: dict[str, Any]) -> tuple[str, str]:
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                           {"questions": [{"part": "summary", "text": "Is it mostly R07?"}], "time_to_answer": "3d"},
                           f.at(16, 11, 20))  # fmt: skip
    return str(sent["id"]), str(sent["questions"][0]["id"])


def test_L_HIDE_S_R3_BLD_B247_any_other_failure_inside_hiding_reads_as_S_R3s_line_never_raw(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not a HideError (a bug, a lost connection inside lane C's hide): the same S-R3 lines, as 500 so the Answer
    screen tries again, and nothing of the error reaches the reply."""
    from desk.store import Refused

    kavya = cast["kavya"]
    set_id, qid = _one_question(db, cast)
    asking.save_answer(db, qid, kavya["id"], "Mostly R07.", at=f.at(16, 12, 10))

    def broken(*_: Any, **__: Any) -> Any:
        raise RuntimeError("Kavya's folio 1234567890 broke it")  # synthetic; must never reach the reply

    monkeypatch.setattr(adapters, "hide_message", broken)
    with pytest.raises(Refused) as saving:
        asking.save_answer(db, qid, kavya["id"], "Mostly R07, twice.", at=f.at(16, 12, 11))
    assert (saving.value.status, saving.value.body()) == (
        500, {"error": {"code": "answer_not_saved", "message": "Couldn’t save that. Try again."}},
    )  # fmt: skip
    with pytest.raises(Refused) as sending:
        asking.send_answers(db, set_id, kavya["id"], f.at(16, 12, 12))
    assert (sending.value.status, sending.value.body()) == (
        500, {"error": {"code": "answers_not_sent", "message": "Your answers didn’t send. Try again."}},
    )  # fmt: skip
    row = db.execute("SELECT sent_at FROM answers WHERE question_id = %s", (qid,)).fetchone()
    assert row is not None and row["sent_at"] is None  # nothing went


def test_L_HIDE_rules_1_BLD_B247_BLD_C067_gateway_down_at_send_the_answers_go_patterns_masked_and_are_rechecked(
    db: Conn, cast: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """R6, as lane C's messages do (BLD-C067): the gateway fails, the answer is still sent, masked by the patterns,
    `hide.gatekeeper_skipped` is audited and a `hide.recheck` job (IDs only) is queued for its sealed words."""
    import gateway
    from core import killswitch
    from desk.store import unseal
    from gateway import AgentFailed

    idea, kavya = cast["idea"], cast["kavya"]
    set_id, qid = _one_question(db, cast)
    words = "Mostly R07. Folio 1234567890 got it twice."
    saved = asking.save_answer(db, qid, kavya["id"], words, at=f.at(16, 12, 10))
    aid = saved["id"]
    calls: list[str] = []

    def down(agent: str, *_: Any, **__: Any) -> Any:
        calls.append(agent)
        raise AgentFailed("connection")

    killswitch.clear_cache()
    monkeypatch.setattr(gateway, "run_agent", down)
    try:
        got = asking.send_answers(db, set_id, kavya["id"], f.at(16, 12, 20))
        assert calls == ["gatekeeper"] and got["sent"] == 1 and got["state"] == "answered"
        row = db.execute("SELECT sent_at, text_encrypted FROM answers WHERE id = %s", (aid,)).fetchone()
        assert row is not None and row["sent_at"] is not None
        stored = unseal(row["text_encrypted"], "answers", "text_encrypted", aid)
        # the patterns masked it
        assert stored is not None and "1234567890" not in stored and "••••90" in stored
        skipped = db.execute(
            "SELECT after FROM audit_log WHERE action = 'hide.gatekeeper_skipped' AND entity = %s",
            (f"idea:{idea['id']}",),
        ).fetchone()
        assert skipped is not None
        assert skipped["after"]["code"] == "connection" and skipped["after"]["source"] == "answer"
        assert "1234567890" not in str(skipped["after"])
        job = db.execute(
            "SELECT id, payload FROM jobs WHERE type = 'hide.recheck' AND payload->>'idea_uuid' = %s",
            (str(idea["id"]),),
        ).fetchone()
        assert job is not None and skipped["after"]["recheck_job"] == job["id"]
        assert job["payload"] == {"idea_uuid": str(idea["id"]), "source": "answer", "source_id": aid,
                                  "by": kavya["id"]}  # fmt: skip
    finally:
        db.execute(
            "DELETE FROM jobs WHERE type = 'hide.recheck' AND payload->>'idea_uuid' = %s", (str(idea["id"]),)
        )
