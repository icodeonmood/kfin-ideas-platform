"""L-MERGE.effects/3 and L-MERGE.desk/5 against the database: ideas merged into the lead show on its reviewer page
as contributions, through the whole chain, and a Pick that joins a similar idea runs the desk merge with it."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import asking, decide, merging, reads
from desk.store import Refused, own_codes
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

REASON = "Picked. A clear problem, a real number and a simple fix. One team builds one fix."
NOTE = "You both found the same R07 calls in Hyderabad."


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
    kavya, ravi, anil = f.person(db, "Kavya Menon"), f.person(db, "Ravi Nair"), f.person(db, "Anil Kumar")
    return {
        "kavya": kavya, "ravi": ravi, "anil": anil,
        "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "idea": f.idea(db, kavya, shared_at=f.at(14, 10)),
        "ravis": f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(15, 9),
                        affects=["Investors"]),
        "anils": f.idea(db, anil, title="No script for calls about rejections", shared_at=f.at(15, 12)),
    }  # fmt: skip


def _file(db: Conn, idea: dict[str, Any], sharer: dict[str, str], n: int, state: str) -> str:
    fid = f"ATT-2026-{n:06d}"
    db.execute(
        "INSERT INTO attachments (id, idea_uuid, uploaded_by_code, name, mime, bytes, store_key, kind, file_state) "
        "VALUES (%s, %s, %s, %s, 'image/png', 2048, %s, 'file', %s)",
        (fid, idea["id"], sharer["code"], f"sms-{n}.png", f"clean/{fid}", state),
    )
    return fid


def test_L_MERGE_effects_3_merged_ideas_show_on_the_lead_as_contributions_through_the_chain(
    db: Conn, cast: dict[str, Any]
) -> None:
    meera, ravis, anils = cast["meera"]["id"], cast["ravis"], cast["anils"]
    # Ravi was asked and answered before the merge; one answer carries a checked file and a marked one
    sent = asking.send_set(db, ravis["idea_id"], meera,
                           {"questions": [{"part": "often", "text": "Is it every branch, or one?"}]}, f.at(16, 9))  # fmt: skip
    on_answer = {s: _file(db, ravis, cast["ravi"], n, s) for n, s in enumerate(
        ("checked", "personal_data_found", "checking"), start=951)}  # fmt: skip
    attached = {s: _file(db, ravis, cast["ravi"], n, s) for n, s in enumerate(
        ("hidden_checked", "infected"), start=961)}  # fmt: skip
    asking.save_answer(db, sent["questions"][0]["id"], cast["ravi"]["id"], "Every branch in Hyderabad.",
                       list(on_answer.values()), f.at(16, 10))  # fmt: skip
    asking.send_answers(db, sent["id"], cast["ravi"]["id"], f.at(16, 10))
    # Anil's joins Ravi's, then Ravi's joins Kavya's: the chain is Kavya's <- Ravi's <- Anil's
    merging.desk_merge(db, ravis["idea_id"], meera, {"other_idea_id": anils["idea_id"], "lead": "this",
                                                     "note": NOTE}, f.at(16, 11))  # fmt: skip
    merging.desk_merge(db, cast["idea"]["idea_id"], meera, {"other_idea_id": ravis["idea_id"], "lead": "this",
                                                            "note": NOTE}, f.at(16, 12))  # fmt: skip
    page = reads.reviewer_idea(db, cast["idea"]["idea_id"], meera, f.at(16, 13))
    got = page["contributions"]
    assert [(c["idea_id"], c["sharer"]["first_name"], c["into"]) for c in got] == [
        (ravis["idea_id"], "Ravi", cast["idea"]["idea_id"]), (anils["idea_id"], "Anil", ravis["idea_id"])
    ]  # fmt: skip
    ravi = got[0]
    assert ravi["label"] == f"Ravi’s idea, {ravis['idea_id']}" and ravi["title"] == ravis["title"]
    parts = {p["part"]: p for p in ravi["parts"]}
    assert parts["who"]["text"] == "Investors"
    question = parts["often"]["questions"][0]
    assert (question["asked_line"], question["state"]) == ("You asked, today 9 am", "Answered")
    assert question["answer"]["text"] == "Every branch in Hyderabad."
    assert [(x["id"], x["customer_detail"]) for x in question["answer"]["files"]] == [
        (on_answer["checked"], False), (on_answer["personal_data_found"], True)
    ]  # fmt: skip
    assert [(x["id"], x["customer_detail"]) for x in ravi["files"]] == [
        (on_answer["checked"], False), (on_answer["personal_data_found"], True),
        (attached["hidden_checked"], False),
    ]  # fmt: skip
    # the lead's own parts and files are not mixed with the contributions
    assert all(a.get("id") not in on_answer.values() for a in page["artefacts"])


def test_L_MERGE_desk_5_a_pick_with_joined_with_merges_the_similar_idea_into_the_picked_one(
    db: Conn, cast: dict[str, Any]
) -> None:
    ref, ravis, meera = cast["idea"]["idea_id"], cast["ravis"], cast["meera"]["id"]
    got = decide.send(db, ref, meera, {"choice": "pick", "reason": REASON, "joined_with": ravis["idea_id"]},
                      f.at(16, 16, 58))  # fmt: skip
    assert got["joined_with"] == ravis["idea_id"] and got["label"] == "Picked"
    m = got["merge"]
    assert (m["lead_idea_id"], m["merged_idea_id"], m["team_up"], m["note"]) == (
        ref, ravis["idea_id"], True, REASON
    )  # fmt: skip
    row = db.execute("SELECT status, merged_into FROM ideas WHERE id = %s", (ravis["id"],)).fetchone()
    assert row == {"status": "merged", "merged_into": cast["idea"]["id"]}
    lead = db.execute("SELECT * FROM ideas WHERE id = %s", (cast["idea"]["id"],)).fetchone()
    assert lead is not None and lead["status"] == "picked"
    assert cast["ravi"]["code"] in own_codes(db, dict(lead))  # credited (L-MERGE.effects/2)
    crew = db.execute(
        "SELECT contributor_code, via FROM crew_members WHERE idea_uuid = %s AND left_at IS NULL ORDER BY id",
        (cast["idea"]["id"],),
    ).fetchall()
    assert (cast["ravi"]["code"], "desk_merge") in [(c["contributor_code"], c["via"]) for c in crew]
    decision = db.execute("SELECT joined_with FROM idea_decisions WHERE id = %s", (got["id"],)).fetchone()
    assert decision == {"joined_with": ravis["id"]}
    windows = db.execute(
        "SELECT count(*) FILTER (WHERE decision_id = %s) AS d, count(*) FILTER (WHERE merge_id = %s) AS m "
        "FROM decision_windows",
        (got["id"], m["id"]),
    ).fetchone()
    assert windows == {"d": 1, "m": 1}  # the committee can reverse the Pick and the merge, each in its window
    assert f.audit_actions(db, f"idea:{ravis['idea_id']}")[-1] == "desk.merge"
    assert f.audit_actions(db, f"idea:{ref}")[-1] == "desk.decide"
    page = reads.reviewer_idea(db, ref, meera, f.at(16, 17))
    assert [c["idea_id"] for c in page["contributions"]] == [ravis["idea_id"]]


def test_L_MERGE_desk_5_a_join_that_cannot_run_refuses_the_whole_decision(
    db: Conn, cast: dict[str, Any]
) -> None:
    ref, meera = cast["idea"]["idea_id"], cast["meera"]
    mine = f.idea(db, meera, title="Branch queue times are not tracked anywhere", shared_at=f.at(13, 9))
    decided = f.idea(db, cast["anil"], status="not_picked", shared_at=f.at(12, 9))
    for joined, status, code in (
        (mine["idea_id"], 403, "own_idea"),
        (decided["idea_id"], 409, "other_not_open"),
        ("IDEA-2026-999999", 409, "other_not_open"),
        (ref, 409, "same_idea"),
    ):
        with pytest.raises(Refused) as refused:
            decide.send(db, ref, meera["id"], {"choice": "pick", "reason": REASON, "joined_with": joined},
                        f.at(16, 16))  # fmt: skip
        assert (refused.value.status, refused.value.code) == (status, code), joined
        if status == 409:
            assert refused.value.field == "joined_with"
    assert db.execute(
        "SELECT count(*) AS n FROM idea_decisions WHERE idea_uuid = %s", (cast["idea"]["id"],)
    ).fetchone() == {"n": 0}
    assert db.execute(
        "SELECT count(*) AS n FROM merges WHERE lead_idea_uuid = %s", (cast["idea"]["id"],)
    ).fetchone() == {"n": 0}
    assert "desk.own_idea_refused" in f.audit_actions(db, f"idea:{mine['idea_id']}")
    # joined_with goes with a Pick only: Not now ignores it
    got = decide.send(db, ref, meera["id"], {"choice": "not_now", "reason": REASON, "return_in": "1m",
                                             "joined_with": cast["ravis"]["idea_id"]}, f.at(16, 17))  # fmt: skip
    assert got["merge"] is None and got["joined_with"] is None
