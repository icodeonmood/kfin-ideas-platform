"""Round-3 review follow-up on the review back end, against the database, with lane A's `notify` replaced by a recorder
(`FakeNotify`): a Pick that joins tells each person once (V-ACC.committee/4, L-MERGE.desk/5), the sharer's joined line
on both pages (Status.md, Picked), "Your reason" for the reviewer who decided only (DeskIdea.md, Decided), more time
moves the sharer's Inbox item (V-ACC.track/3), the committee's actions check the role in the worker (L-COMMITTEE,
A-API.committee), the reviewer's own queued questions on their page (S-R2.panel, J-REVIEW/A1), a Pick never joins the
reviewer's own idea (A-API.conventions/2) and the window line at the 3-month limit (L-COMMITTEE.rules/2)."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, clocks, committee, decide, merging, reads
from desk.store import Refused, own_codes, seal
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

DECIDED = f.at(16, 16, 58)  # Monday 16 November, 4:58 pm
REASON = "Picked. A clear problem, a real number and a simple fix. One team builds one fix."
NOTE = "The SMS templates are frozen until the platform upgrade in January, so a team picked now would wait."
QS: list[dict[str, Any]] = [
    {"part": "summary", "text": "Is it mostly R07, or all rejection codes?"},
    {"part": "often", "text": "Is the 40 calls a day at one branch, or across Hyderabad?"},
]


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
    kavya, ravi = f.person(db, "Kavya Menon"), f.person(db, "Ravi Nair", city="Hyderabad")
    return {
        "kavya": kavya, "ravi": ravi,
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "harish": f.person(db, "Harish Rao", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "idea": f.idea(db, kavya, shared_at=f.at(14, 10), city="Vizag"),
        "ravis": f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(15, 9),
                        city="Hyderabad"),
    }  # fmt: skip


@pytest.fixture
def told(monkeypatch: pytest.MonkeyPatch) -> f.FakeNotify:
    return f.install_fake_notify(monkeypatch)


def _pick_and_join(db: Conn, cast: dict[str, Any]) -> dict[str, Any]:
    return decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                       {"choice": "pick", "reason": REASON, "joined_with": cast["ravis"]["idea_id"]}, DECIDED)  # fmt: skip


def _window(db: Conn, decision_id: str) -> str:
    row = db.execute("SELECT id FROM decision_windows WHERE decision_id = %s", (decision_id,)).fetchone()
    assert row is not None
    return str(row["id"])


# ---- item 1: a Pick that joins tells each person once ----------------------------------------------------------
def test_V_ACC_committee_4_a_pick_that_joins_tells_each_person_exactly_once(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    farhan, sana = f.person(db, "Farhan Shaikh"), f.person(db, "Sana Qureshi")
    f.crew(db, cast["idea"], farhan)
    f.crew(db, cast["ravis"], sana)
    d = _pick_and_join(db, cast)
    assert d["merge"] is not None and d["joined_with"] == cast["ravis"]["idea_id"]
    assert told.of("desk_merge") == []  # the decision carries the join (L-MERGE.desk/5)
    everyone = [cast["kavya"]["id"], farhan["id"], cast["ravi"]["id"], sana["id"]]
    told_ids = [u for p in told.posts for u in p.recipients]
    assert sorted(told_ids) == sorted(everyone)  # both sharers and both crews, one item each
    [decided] = told.of("decision")
    assert (decided.needs_you, decided.sender, decided.actions) == (
        False,
        cast["meera"]["id"],
        ["Read the decision"],
    )
    # a desk merge on its own still tells both sharers (V-ACC.review/13)
    other = f.idea(
        db, f.person(db, "Anil Kumar"), title="No script for calls about rejections", shared_at=f.at(15, 12)
    )
    third = f.idea(
        db, f.person(db, "Divya Pillai"), title="Branch staff cannot read R-codes", shared_at=f.at(15, 13)
    )
    merging.desk_merge(db, other["idea_id"], cast["meera"]["id"],
                       {"other_idea_id": third["idea_id"], "note": "You both found the same R07 calls."},
                       f.at(16, 17))  # fmt: skip
    assert len(told.of("desk_merge")) == 1


# ---- item 2: the joined line, on the picked idea and on the one it joined ---------------------------------------
def test_L_MERGE_desk_5_the_sharers_read_the_joined_line_on_both_pages(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    _ = told
    d = _pick_and_join(db, cast)
    at = f.at(17, 9)
    lead = committee.decision_for_viewer(db, cast["idea"]["idea_id"], cast["kavya"]["id"], at)
    assert lead is not None and lead["joined_into"] is None
    assert lead["lines"]["joined_line"] == (
        f"Meera from the review desk picked it on Monday 16 November and joined it with {cast['ravis']['idea_id']} "
        "from Hyderabad, so one team builds one fix."
    )
    # Ravi's idea is merged and has no decision of its own: his page reads the lead's Pick, naming the lead
    joined = committee.decision_for_viewer(db, cast["ravis"]["idea_id"], cast["ravi"]["id"], at)
    assert joined is not None and joined["joined_into"] == cast["idea"]["idea_id"]
    assert joined["decision"]["reason"] == REASON  # the reason was the note to both
    assert joined["lines"]["joined_line"] == (
        f"Meera from the review desk picked it on Monday 16 November and joined it with {cast['idea']['idea_id']} "
        "from Vizag, so one team builds one fix."
    )
    assert joined["lines"]["committee_line"].startswith("The Ones Committee can review this decision until")
    assert joined["window_id"] == _window(db, d["id"])
    # someone outside the two ideas reads the stage only
    stranger = f.person(db, "Nikhil Das")
    assert committee.decision_for_viewer(db, cast["ravis"]["idea_id"], stranger["id"], at) == {
        "stage_only": True, "decision": {"choice": "pick", "label": "Picked"},
    }  # fmt: skip


# ---- item 3: "Your reason" only for the reviewer who decided ----------------------------------------------------
def test_S_R2_panel_decided_your_reason_only_for_the_reviewer_who_decided(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    _ = told
    decide.send(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, DECIDED
    )
    at = f.at(16, 17)
    mine = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], at)["panel"]["lines"]
    assert (mine["sent_line"], mine["reason_heading"]) == (
        "Today, 4:58 pm. Kavya has it now.", "Your reason, as Kavya reads it"
    )  # fmt: skip
    for reader in ("harish", "rohan"):  # another reviewer, the committee
        lines = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast[reader]["id"], at)["panel"]["lines"]
        assert (lines["sent_line"], lines["reason_heading"]) == (
            "Today, 4:58 pm. Meera sent it.", "The review desk’s reason, as Kavya read it"
        ), reader  # fmt: skip


# ---- item 8: more time moves the sharer's Inbox item -----------------------------------------------------------
def test_V_ACC_track_3_more_time_reposts_the_questions_item_with_the_new_deadline(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    sent = asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                           {"questions": QS, "time_to_answer": "3d"}, f.at(16, 11, 20))  # fmt: skip
    got = asking.give_more_time(db, sent["id"], cast["meera"]["id"], f.at(17, 10))
    first, again = told.of("questions")
    key = f"qs:{sent['id']}"
    assert (first.dedupe_key, again.dedupe_key) == (key, key)  # one item, kept under the set's key
    assert (first.due_at, again.due_at) == (f.at(19, 18), f.at(21, 18))
    assert dt.datetime.fromisoformat(got["due_at"]) == again.due_at
    assert (again.recipients, again.needs_you, again.sender, again.actions) == (
        [cast["kavya"]["id"]], True, cast["meera"]["id"], ["Answer the questions"]
    )  # fmt: skip
    # the sharer's page counts down to the same deadline
    opened = asking.open_set_for_sharer(db, cast["idea"]["idea_id"], cast["kavya"]["id"], f.at(17, 11))
    assert opened is not None and dt.datetime.fromisoformat(opened["due_at"]) == again.due_at


# ---- the committee's actions check the role in the worker -------------------------------------------------------
def test_L_COMMITTEE_only_the_committee_lists_reads_extends_or_reverses(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    _ = told
    d = decide.send(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, DECIDED
    )
    window = _window(db, d["id"])
    at = f.at(17, 9)
    calls: tuple[Callable[[str], Any], ...] = (
        lambda who: committee.listing(db, who, at=at),
        lambda who: committee.reversing_words(db, window, who, at),
        lambda who: committee.extend_window(db, window, who, at),
        lambda who: committee.reverse_window(db, window, who, {"to": "not_now", "note": NOTE}, at),
    )
    stranger = f.person(db, "Nikhil Das")
    for who in (cast["meera"]["id"], stranger["id"]):  # a reviewer, an employee
        for call in calls:
            with pytest.raises(Refused) as refused:
                call(who)
            assert (refused.value.status, refused.value.code) == (403, "forbidden")
    assert db.execute("SELECT extended_times FROM decision_windows WHERE id = %s", (window,)).fetchone() == {
        "extended_times": 0
    }
    # the old role still reaches it until it is dropped (contracts.md §2.14)
    old = f.person(db, "Lata Krishnan", roles=("core_committee",))
    assert committee.listing(db, old["id"], at=at)["counts"]["window"] >= 1
    assert committee.reversing_words(db, window, old["id"], at)["send_label"] == "Reverse and tell Kavya"
    assert committee.extend_window(db, window, old["id"], at)["window"]["extended_times"] == 1
    row = committee.reverse_window(db, window, old["id"], {"to": "not_now", "note": NOTE}, at)
    assert row["window"]["state"] == "reversed"


# ---- S-R2.panel Asking: the reviewer's own queued questions ------------------------------------------------------
def _queue(db: Conn, idea: dict[str, Any], by: str, questions: list[tuple[str, str, bool]]) -> str:
    sid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO question_sets (id, idea_uuid, by_user_id, state, created_at) VALUES (%s, %s, %s, 'queued', %s)",
        (sid, idea["id"], by, f.at(16, 10)),
    )
    for seq, (part, text, suggested) in enumerate(questions, start=1):
        qid = str(uuid.uuid4())
        db.execute(
            "INSERT INTO questions (id, set_id, seq, part, text_encrypted, suggested) VALUES (%s, %s, %s, %s, %s, %s)",
            (qid, sid, seq, part, seal(text, "questions", "text_encrypted", qid), suggested),
        )
    return sid


def test_S_R2_panel_the_reviewer_reads_their_own_queued_questions_and_no_one_elses(
    db: Conn, cast: dict[str, Any]
) -> None:
    idea = cast["idea"]
    sid = _queue(db, idea, cast["meera"]["id"], [("who", "Which distributor segments re-send most?", True)])
    panel = reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], f.at(16, 11))["panel"]
    assert panel["state"] == "reviewing"
    assert panel["queued"] == {
        "set_id": sid, "time_to_answer": None, "ready_line": "1 question ready",
        "send_label": "Send 1 question to Kavya",
        "questions": [{"id": panel["queued"]["questions"][0]["id"], "part": "who", "part_name": "Who it affects",
                       "text": "Which distributor segments re-send most?", "suggested": True}],
    }  # fmt: skip
    # one queued set per idea, and it is Meera's alone: another reviewer and the committee never see it
    for other in ("harish", "rohan"):
        assert (
            reads.reviewer_idea(db, idea["idea_id"], cast[other]["id"], f.at(16, 11))["panel"]["queued"]
            is None
        )
    # nothing queued is "asked": the desk's lists and the page's parts leave it out (L-REVIEW.queue)
    page = reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], f.at(16, 11))
    assert all(not p.get("asked") for p in page["parts"])
    # once sent it is no longer queued: the panel waits on the sharer
    asking.send_set(db, idea["idea_id"], cast["meera"]["id"],
                    {"questions": [{"part": "who", "text": "Which distributor segments re-send most?"}]},
                    f.at(16, 12))  # fmt: skip
    after = reads.reviewer_idea(db, idea["idea_id"], cast["meera"]["id"], f.at(16, 12, 5))["panel"]
    assert after["state"] == "sent" and "queued" not in after
    # the send took the queued row: none is left behind for the idea
    left = db.execute(
        "SELECT count(*) AS n FROM question_sets WHERE idea_uuid = %s AND state = 'queued'", (idea["id"],)
    ).fetchone()
    assert left == {"n": 0} and sid not in [q["set_id"] for q in [after] if "set_id" in q]


# ---- item 4: a Pick never joins the reviewer's own idea ----------------------------------------------------------
def test_A_API_conventions_2_joining_your_own_idea_is_refused_under_joined_with(
    db: Conn, cast: dict[str, Any]
) -> None:
    hers = f.idea(db, cast["meera"], title="Couriers come back twice", shared_at=f.at(15, 10))
    with pytest.raises(Refused) as refused:
        decide.send(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                    {"choice": "pick", "reason": REASON, "joined_with": hers["idea_id"]}, DECIDED)  # fmt: skip
    got = refused.value
    assert (got.status, got.code, got.field) == (403, "own_idea", "joined_with")
    assert got.message == decide.OWN_OTHER
    assert db.execute("SELECT count(*) AS n FROM idea_decisions WHERE idea_uuid = %s", (cast["idea"]["id"],)
                      ).fetchone() == {"n": 0}  # fmt: skip


# ---- item 5: the window line at the 3-month limit ---------------------------------------------------------------
def test_L_COMMITTEE_rules_2_the_reviewers_window_line_at_the_limit(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    _ = told
    d = decide.send(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, DECIDED
    )
    window = _window(db, d["id"])
    at = f.at(17, 9)
    while committee.extend_window(db, window, cast["rohan"]["id"], at)["can_extend"]:
        pass
    line = reads.reviewer_idea(db, cast["idea"]["idea_id"], cast["meera"]["id"], at)["panel"]["lines"][
        "window_line"
    ]
    assert "The committee can extend it" not in line
    assert line.startswith("Open until ") and ". At the 3-month limit. If they reverse it, Kavya gets" in line


# ---- item 10: the V-ACC rows completed ---------------------------------------------------------------------------
def test_V_ACC_review_13_the_other_idea_joins_the_lead_with_both_sharers_credited(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    m = merging.desk_merge(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                           {"other_idea_id": cast["ravis"]["idea_id"], "note": "You both found the same R07 calls."},
                           f.at(16, 12))  # fmt: skip
    lead, other = cast["idea"], cast["ravis"]  # Kavya's was shared first, so it leads (L-MERGE.desk/2)
    assert (m["lead_idea_id"], m["merged_idea_id"]) == (lead["idea_id"], other["idea_id"])
    row = db.execute("SELECT status, merged_into FROM ideas WHERE id = %s", (other["id"],)).fetchone()
    assert row == {"status": "merged", "merged_into": lead["id"]}
    assert {cast["kavya"]["code"], cast["ravi"]["code"]} <= own_codes(db, lead)  # both credited
    crew = db.execute(
        "SELECT contributor_code, role, via FROM crew_members WHERE idea_uuid = %s AND left_at IS NULL",
        (lead["id"],),
    ).fetchall()
    assert {"contributor_code": cast["ravi"]["code"], "role": "crew", "via": "desk_merge"} in crew
    assert m["banner"]  # C-SHEET-MERGE.after
    [item] = told.of("desk_merge")
    assert sorted(item.recipients) == sorted([cast["kavya"]["id"], cast["ravi"]["id"]])


def test_V_ACC_track_5_no_reminder_for_a_sharer_with_reminders_off(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    db.execute("INSERT INTO comms_prefs (user_id, reminders) VALUES (%s, false)", (cast["kavya"]["id"],))
    asking.send_set(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                    {"questions": QS, "time_to_answer": "3d"}, f.at(16, 11, 20))  # fmt: skip
    for t in (f.at(18, 18, 5), f.at(19, 16, 5)):  # a day and two hours before the deadline
        assert clocks.run_due(db, t)["reminded"] == 0
    assert told.of("answer_reminder") == []
    assert len(told.of("questions")) == 1  # the questions themselves still arrive


def test_V_ACC_committee_4_a_reversed_row_sits_under_reversed_and_is_final(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    _ = told
    d = decide.send(
        db, cast["idea"]["idea_id"], cast["meera"]["id"], {"choice": "pick", "reason": REASON}, DECIDED
    )
    window = _window(db, d["id"])
    rohan = cast["rohan"]["id"]
    committee.reverse_window(
        db, window, rohan, {"to": "not_now", "note": NOTE, "return_in": "3m"}, f.at(24, 17, 40)
    )
    listed = committee.listing(db, rohan, tab="reversed", at=f.at(24, 18))
    assert window in [r["window_id"] for r in listed["items"]]
    assert window not in [r["window_id"] for r in committee.listing(db, rohan, at=f.at(24, 18))["items"]]
    agains: tuple[Callable[[], Any], ...] = (
        lambda: committee.reverse_window(db, window, rohan, {"to": "not_picked", "note": NOTE}, f.at(25, 9)),
        lambda: committee.extend_window(db, window, rohan, f.at(25, 9)),
    )
    for again in agains:
        with pytest.raises(Refused) as refused:
            again()
        assert (refused.value.status, refused.value.code) == (409, "already_reversed")
