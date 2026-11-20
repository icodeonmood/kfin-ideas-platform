"""BLD-B272 (amends BLD-B244): a reviewer's queued questions are kept between visits (S-R2.panel Asking, J-REVIEW/A1;
L-QUESTIONS.ask/4, L-QUESTIONS.states "queued (reviewer only)").

`asking.save_queue` stores the panel's whole queue as the reviewer's queued set, masked as Send masks it (L-HIDE), and
the next read of S-R2 opens with it. One queued set per reviewer per idea; a save is kept only from the revision stored
for its reviewer (`base`, compare-and-swap), so a stale tab keeps nothing. A save that comes too late (after Send, a
decision or a merge) keeps nothing either, and nobody but the reviewer who queued the questions reads them. Synthetic
people only; the customer details are generated at run time (eval/golden/generators.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import generators
import pytest

from core.db import Conn
from desk import adapters, asking, decide, merging, reads
from desk.store import Refused, unseal
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

T = f.at(16, 11, 20)  # Monday 16 November 2026, 11:20 am IST
REASON = "A clear problem, a real number and a simple fix that the branch can try."
Q1 = {"part": "often", "text": "Is it 40 calls a day at one branch, or across Hyderabad?"}
# the suggestion for an idea with nothing attached (desk.questions._GAP), added from the panel's list
Q2 = {
    "part": "evidence",
    "text": "Can you add a screenshot or a file that shows it, with customer details hidden?",
    "suggested": True,
}


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
        "harish": f.person(db, "Harish Rao", roles=("reviewer",)),
        "rohan": f.person(db, "Rohan Mehta", roles=("committee",)),
        "idea": f.idea(db, kavya, shared_at=f.at(14, 10)),
        "ravis": f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(13, 9)),
    }  # fmt: skip


@pytest.fixture
def told(monkeypatch: pytest.MonkeyPatch) -> f.FakeNotify:
    return f.install_fake_notify(monkeypatch)


def _save(db: Conn, cast: dict[str, Any], questions: list[dict[str, Any]], *, base: int = 0, who: str = "meera",
          after: str | None = None, time: str = "1w", idea: str = "idea") -> dict[str, Any]:  # fmt: skip
    return asking.save_queue(
        db, cast[idea]["idea_id"], cast[who]["id"],
        {"questions": questions, "time_to_answer": time, "base": base, "after": after}, T,
    )  # fmt: skip


def _queued(db: Conn, cast: dict[str, Any], who: str = "meera", idea: str = "idea") -> dict[str, Any] | None:
    panel = reads.reviewer_idea(db, cast[idea]["idea_id"], cast[who]["id"], f.at(16, 12))["panel"]
    queued: dict[str, Any] | None = panel.get("queued")
    return queued


def _stored(db: Conn, idea_uuid: Any) -> list[dict[str, Any]]:
    """Every queued set of the idea as stored, with its questions opened (the masked copy)."""
    return [
        {"by": str(s["by_user_id"]), "rev": s["queue_rev"], "time": s["time_to_answer"],
         "texts": [unseal(q["text_encrypted"], "questions", "text_encrypted", str(q["id"]))
                   for q in db.execute("SELECT id, text_encrypted FROM questions WHERE set_id = %s ORDER BY seq",
                                       (s["id"],)).fetchall()]}
        for s in db.execute(
            "SELECT id, by_user_id, queue_rev, time_to_answer FROM question_sets WHERE idea_uuid = %s "
            "AND state = 'queued'", (idea_uuid,),
        ).fetchall()
    ]  # fmt: skip


def test_bld_b272_s_r2_panel_a_stored_queue_comes_back_on_the_next_read(
    db: Conn, cast: dict[str, Any]
) -> None:
    """BLD-B272, S-R2.panel, J-REVIEW/A1: the queue saved as it changed is the panel's queue on the next visit, with
    its time to answer and the revision the next save carries as `base`. Each save replaces the reviewer's last: one
    queued set, stored one revision on from the `base` it carried."""
    saved = _save(db, cast, [Q1])
    assert (saved["rev"], saved["count"]) == (1, 1)
    again = _save(db, cast, [Q1, Q2], base=1)
    assert again["set_id"] != saved["set_id"] and again["rev"] == 2
    queued = _queued(db, cast)
    assert queued is not None
    assert [(q["part"], q["text"], q["suggested"]) for q in queued["questions"]] == [
        ("often", Q1["text"], False), ("evidence", Q2["text"], True),
    ]  # fmt: skip
    assert (queued["set_id"], queued["time_to_answer"], queued["rev"]) == (again["set_id"], "1w", 2)
    assert (queued["ready_line"], queued["send_label"]) == ("2 questions ready", "Send 2 questions to Kavya")
    assert len(_stored(db, cast["idea"]["id"])) == 1
    # a question removed in the browser stays removed; an emptied queue keeps its revision, with nothing ready
    _save(db, cast, [Q2], base=2)
    assert [q["text"] for q in (_queued(db, cast) or {})["questions"]] == [Q2["text"]]
    _save(db, cast, [], base=3)
    emptied = _queued(db, cast)
    assert emptied is not None and (emptied["questions"], emptied["rev"]) == ([], 4)
    # audited with IDs, counts and parts only, never the words
    rows = db.execute(
        "SELECT after FROM audit_log WHERE action = 'desk.queue_questions' AND entity = %s ORDER BY id",
        (f"idea:{cast['idea']['idea_id']}",),
    ).fetchall()
    assert [r["after"]["count"] for r in rows] == [1, 2, 1, 0]
    assert all("calls a day" not in str(r["after"]) and "screenshot" not in str(r["after"]) for r in rows)


def test_bld_b272_l_hide_a_customer_detail_in_a_queued_question_is_stored_masked(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BLD-B272, L-HIDE.rules/1, /3, DEC-103: a PAN and a mobile number typed into a question go through the same
    `hide` as Send before anything is stored; only the masked copy is kept, and nothing hide found is left for
    another page to count or show (the sharer's page lists every hidden detail of the idea)."""
    rng = generators.default_rng(272)
    pan, mobile = generators.pan(rng), generators.mobile(rng)
    raw = f"Is this the investor with PAN {pan} who called from {mobile}?"
    _save(db, cast, [{"part": "who", "text": raw}])
    [stored] = _stored(db, cast["idea"]["id"])
    [text] = stored["texts"]
    assert pan not in text and mobile not in text and mobile.replace(" ", "") not in text.replace(" ", "")
    assert "••••" in text and text.startswith("Is this the investor with PAN ")
    queued = _queued(db, cast)
    # the reviewer reads the masked copy too
    assert queued is not None and queued["questions"][0]["text"] == text
    idea_uuid = cast["idea"]["id"]
    assert db.execute(
        "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchone() == {"n": 0}
    from ideapage import read as sharer_page

    assert sharer_page.hidden(db, str(idea_uuid)) == []
    assert told.posts == []  # no Inbox item, no email
    audited = db.execute(
        "SELECT after FROM audit_log WHERE entity = %s OR entity = %s",
        (f"idea:{cast['idea']['idea_id']}", str(idea_uuid)),
    ).fetchall()
    assert all(pan not in str(r["after"]) and mobile not in str(r["after"]) for r in audited)
    # the masked copy sent back unchanged (the page holds it after a reload) is kept as it is, with no second pass
    calls: list[str] = []
    real = adapters.hide_queued

    def counted(*args: Any, **kwargs: Any) -> str:
        calls.append(str(kwargs.get("question_id")))
        return real(*args, **kwargs)

    monkeypatch.setattr(adapters, "hide_queued", counted)
    _save(db, cast, [{"part": "who", "text": text}, Q1], base=1)
    assert len(calls) == 1  # Q1 only
    assert _stored(db, idea_uuid)[0]["texts"] == [text, Q1["text"]]


@pytest.mark.parametrize("ending", ["send", "decide", "merge"])
def test_bld_b272_l_questions_a_save_after_send_decide_or_merge_is_refused_and_brings_nothing_back(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify, ending: str
) -> None:
    """BLD-B272, L-QUESTIONS.states, L-REVIEW.panel: Send, a decision and a merge each take the queued set (as they
    did). A save the panel made before them and that arrives after them is refused and keeps nothing."""
    _save(db, cast, [Q1])
    meera, ref = cast["meera"]["id"], cast["idea"]["idea_id"]
    code = "queue_stale"
    if ending == "send":
        asking.send_set(db, ref, meera, {"questions": [Q1], "time_to_answer": "3d"}, f.at(16, 11, 30))
    elif ending == "decide":
        decide.send(db, ref, meera, {"choice": "pick", "reason": REASON}, f.at(16, 11, 30))
        code = "already_decided"
    else:  # Kavya's idea was shared second, so it joins Ravi's (L-MERGE.desk/2)
        merging.desk_merge(db, ref, meera, {"other_idea_id": cast["ravis"]["idea_id"],
                                            "note": "You both found the same R07 calls."}, f.at(16, 11, 30))  # fmt: skip
        code = "already_decided"
        assert db.execute("SELECT status FROM ideas WHERE id = %s", (cast["idea"]["id"],)).fetchone() == {
            "status": "merged"
        }
    assert _stored(db, cast["idea"]["id"]) == []
    with pytest.raises(Refused) as late:
        _save(db, cast, [Q1, Q2], base=1)
    assert (late.value.status, late.value.code) == (409, code)
    assert _stored(db, cast["idea"]["id"]) == []
    if ending == "send":
        # nor with the sent set named as the one the panel knew: it is still waiting on Kavya's answers
        sent = db.execute(
            "SELECT id FROM question_sets WHERE idea_uuid = %s AND state = 'sent'", (cast["idea"]["id"],)
        ).fetchone()
        assert sent is not None
        with pytest.raises(Refused) as waiting:
            _save(db, cast, [Q2], after=str(sent["id"]))
        assert (waiting.value.status, waiting.value.code) == (409, "queue_stale")
        assert _stored(db, cast["idea"]["id"]) == []


def test_bld_b272_s_r2_panel_two_tabs_from_one_base_the_second_is_refused_and_the_first_is_kept(
    db: Conn, cast: dict[str, Any]
) -> None:
    """BLD-B272 (fix round), S-R2.panel: a save is kept only from the revision stored for its reviewer. Two tabs read
    the same stored queue (revision 1); the first tab's save is kept as revision 2, and the second tab's, from the same
    `base`, is refused (409 `queue_stale`) and stores nothing: the first tab's queue is what's stored. A save from one
    below the stored revision (an older save overtaken) is refused the same way; the clock plays no part."""
    _save(db, cast, [Q1])  # revision 1, read by both tabs
    first = _save(db, cast, [Q1, Q2], base=1)  # tab A
    assert first["rev"] == 2
    with pytest.raises(Refused) as second:  # tab B, from the same read
        _save(db, cast, [Q2], base=1, time="1d")
    assert (second.value.status, second.value.code) == (409, "queue_stale")
    [kept] = _stored(db, cast["idea"]["id"])
    assert (kept["rev"], kept["time"], kept["texts"]) == (2, "1w", [Q1["text"], Q2["text"]])
    # one below the stored revision, and one above it (a revision the worker never returned): both refused
    for wrong in (1, 3):
        with pytest.raises(Refused) as stale:
            _save(db, cast, [Q1], base=wrong)
        assert (stale.value.status, stale.value.code) == (409, "queue_stale")
    assert _stored(db, cast["idea"]["id"])[0]["rev"] == 2
    # with nothing stored for a reviewer, only `base` 0 is kept
    with pytest.raises(Refused) as none_stored:
        _save(db, cast, [Q1], who="harish", base=2)
    assert none_stored.value.code == "queue_stale"
    assert _save(db, cast, [Q1], who="harish", base=0)["rev"] == 1


def test_bld_b272_l_questions_a_late_or_malformed_save_keeps_nothing(db: Conn, cast: dict[str, Any]) -> None:
    """BLD-B272: a set sent and answered since the panel's read (its `after` no longer names the latest set) is
    refused; a `base` that is not a whole number with 0 <= base < 2**53 - 1, or a bad question, is refused before
    anything is stored."""
    _save(db, cast, [Q1, Q2])
    with pytest.raises(Refused) as moved:
        _save(db, cast, [Q1], base=1, after="00000000-0000-4000-8000-000000000000")
    assert moved.value.code == "queue_stale"
    for bad in (-1, True, "5", 1.0, None, asking.REV_MAX, 2**53):
        with pytest.raises(Refused) as invalid:
            _save(db, cast, [Q1], base=bad)  # type: ignore[arg-type]
        refused = (invalid.value.status, invalid.value.code, invalid.value.field)
        assert refused == (422, "base_invalid", "base")
    with pytest.raises(Refused) as empty:
        _save(db, cast, [{"part": "often", "text": "  "}], base=1)
    assert (empty.value.code, empty.value.field) == ("question_empty", "questions.0.text")
    with pytest.raises(Refused) as no_list:
        asking.save_queue(db, cast["idea"]["idea_id"], cast["meera"]["id"], {"base": 1}, T)
    assert (no_list.value.status, no_list.value.code) == (422, "questions_required")
    assert _stored(db, cast["idea"]["id"])[0]["rev"] == 1


def test_bld_b272_p_product_privacy_only_the_reviewer_who_queued_reads_it_back(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    """BLD-B272, P-PRODUCT.privacy, L-QUESTIONS.states "queued (reviewer only)": another reviewer, a committee member
    and the sharer never read a queued set: not on S-R2, not in the suggestions, not on the sharer's question set,
    page or conversation, and nothing reaches the Inbox or comms."""
    _save(db, cast, [Q1, Q2])
    for who in ("harish", "rohan"):
        assert _queued(db, cast, who) is None, who
    # another reviewer's suggestions still offer what only Meera queued (Q2 is a suggestion's wording)
    offered = [s["text"] for s in asking.suggested(db, cast["idea"]["idea_id"], cast["harish"]["id"])]
    assert Q2["text"] in offered
    assert Q2["text"] not in [
        s["text"] for s in asking.suggested(db, cast["idea"]["idea_id"], cast["meera"]["id"])
    ]
    # the sharer: no question set to answer, nothing asked on their page, no line in the conversation
    kavya = cast["kavya"]["id"]
    assert asking.open_set_for_sharer(db, cast["idea"]["idea_id"], kavya, f.at(16, 12)) is None
    assert all(not qs for qs in asking.answers_by_part(db, cast["idea"]["id"]).values())
    assert f.events(db, cast["idea"]["id"]) == []
    assert told.posts == []
    # a reviewer never queues on their own idea (the route lets only the review desk in: test_1pc_desk_routes.py)
    mine = f.idea(db, cast["meera"], title="Meera's own idea about cheque returns")
    with pytest.raises(Refused) as refused:
        asking.save_queue(db, mine["idea_id"], cast["meera"]["id"], {"questions": [Q1], "base": 0}, T)
    assert (refused.value.status, refused.value.code) == (403, "own_idea")


def test_bld_b272_s_r2_panel_each_reviewer_keeps_their_own_queue_and_send_drops_both(
    db: Conn, cast: dict[str, Any], told: f.FakeNotify
) -> None:
    """BLD-B272 (fix round), S-R2.panel, L-QUESTIONS.states "queued (reviewer only)": one queued set per reviewer per
    idea. A second reviewer's save keeps the first reviewer's queue, and each reads back only their own; their
    revisions are their own. Send, by either, drops every queued set on the idea."""
    _save(db, cast, [Q1])  # Meera, revision 1
    harish = _save(db, cast, [Q2], who="harish")  # from base 0: his own, untouched by Meera's
    assert harish["rev"] == 1
    _save(db, cast, [Q1, Q2], base=1)  # Meera again: Harish's queue stays
    assert [q["text"] for q in (_queued(db, cast) or {})["questions"]] == [Q1["text"], Q2["text"]]
    assert [q["text"] for q in (_queued(db, cast, "harish") or {})["questions"]] == [Q2["text"]]
    assert (_queued(db, cast) or {})["rev"] == 2 and (_queued(db, cast, "harish") or {})["rev"] == 1
    by = {s["by"]: s["texts"] for s in _stored(db, cast["idea"]["id"])}
    assert by == {cast["meera"]["id"]: [Q1["text"], Q2["text"]], cast["harish"]["id"]: [Q2["text"]]}
    asking.send_set(db, cast["idea"]["idea_id"], cast["harish"]["id"], {"questions": [Q2], "time_to_answer": "3d"},
                    f.at(16, 11, 30))  # fmt: skip
    assert _stored(db, cast["idea"]["id"]) == []
    assert _queued(db, cast) is None and _queued(db, cast, "harish") is None
