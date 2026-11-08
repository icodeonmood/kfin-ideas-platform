"""Find your crew choices and the save (B5): AT-B5-06 (team up, +1, adoption, mine is different, withdraw),
AT-B5-07 (editing the one line or details by more than 20% of the words re-runs the match) and AT-B5-08 (the
save is one transaction: a failure after the ideas update rolls back links, review item, timer and outbox)."""

from __future__ import annotations

from typing import Any

import pytest

from scan import pipeline, save
from scan.confirm import ConfirmRefused, confirm, edit_share
from scan.view import view
from tests.conftest import MATCH_TEXT as TEXT
from tests.test_b4_scan import canvas, submitted

pytestmark = pytest.mark.stack
CODE = "CTR-0a1b2c"
CONTEXT = "Our branch sees the same thing with every lumpsum form too"


def ready(db: Any, suffix: str = "", code: str = CODE) -> tuple[str, str, dict[str, str]]:
    idea = submitted(db, canvas(TEXT + suffix + "."))
    db.execute("UPDATE ideas SET contributor_code = %s WHERE id = %s", (code, idea))
    assert pipeline.run(db, idea) == "done"
    idea_id = db.execute("SELECT idea_id FROM ideas WHERE id = %s", (idea,)).fetchone()["idea_id"]
    shown = view(db, idea, "real")
    assert shown is not None
    refs = {c["kind"]: c["ref"] for c in shown["ready"]["matches"] if c["ref"]}
    return idea, idea_id, refs


def counts(db: Any, idea_id: str) -> dict[str, int]:
    def n(sql: str, *args: str) -> int:
        return int(db.execute(sql, args).fetchone()["n"])

    return {
        "links": n(
            "SELECT count(*) AS n FROM idea_links WHERE idea_id = %s OR from_idea_id = %s", idea_id, idea_id
        ),
        "items": n("SELECT count(*) AS n FROM review_items WHERE ref_id = %s", idea_id),
        "timers": n(
            "SELECT count(*) AS n FROM sla_timers t JOIN review_items r ON t.entity_id = r.id::text WHERE r.ref_id = %s",
            idea_id,
        ),
        "outbox": n("SELECT count(*) AS n FROM outbox WHERE aggregate_id = %s", idea_id),
    }


def test_confirm_first_then_team_up_with_context(world: Any) -> None:
    db = world
    idea, idea_id, refs = ready(db)
    with pytest.raises(save.SaveRefused) as first:
        save.save(db, idea, CODE, {"choice": "team_up", "ref": refs["idea"], "text": CONTEXT})
    assert first.value.code == "confirm_first"
    confirm(db, idea, idea_id, {"keep": {}})
    with pytest.raises(save.SaveRefused) as short:
        save.save(db, idea, CODE, {"choice": "team_up", "ref": refs["idea"], "text": "me too"})
    assert short.value.code == "context_too_short"
    out = save.save(db, idea, CODE, {"choice": "team_up", "ref": refs["idea"], "text": CONTEXT})
    assert out["stage"] == "merged"
    link = db.execute(
        "SELECT idea_id, link_type, context_text FROM idea_links WHERE from_idea_id = %s", (idea_id,)
    ).fetchone()
    assert (
        link["link_type"] == "joiner"
        and link["idea_id"] == "IDEA-2026-000011"
        and "lumpsum" in link["context_text"]
    )
    assert counts(db, idea_id) == {"links": 2, "items": 1, "timers": 1, "outbox": 1}
    row = db.execute("SELECT stage, raw_encrypted, canvas FROM ideas WHERE id = %s", (idea,)).fetchone()
    assert row["raw_encrypted"] is None and row["canvas"]["neutral_summary"]


def test_plus_one_adoption_different_and_withdraw(world: Any) -> None:
    db = world
    idea, idea_id, refs = ready(db, " (a)")
    confirm(db, idea, idea_id, {})
    assert save.save(db, idea, CODE, {"choice": "plus_one", "ref": refs["idea"]})["stage"] == "merged"
    assert (
        db.execute("SELECT link_type FROM idea_links WHERE from_idea_id = %s", (idea_id,)).fetchone()[
            "link_type"
        ]
        == "plus_one"
    )

    idea, idea_id, refs = ready(db, " (b)", "CTR-0b0b0b")
    confirm(db, idea, idea_id, {})
    assert (
        save.save(db, idea, "CTR-0b0b0b", {"choice": "team_up", "ref": refs["solution"]})["stage"]
        == "adoption_requested"
    )
    assert (
        db.execute("SELECT solution_id FROM idea_links WHERE from_idea_id = %s", (idea_id,)).fetchone()[
            "solution_id"
        ]
        == "SOL-0004"
    )
    assert db.execute(
        "SELECT 1 FROM comms_log WHERE event = 'adoption.requested' AND message_ref LIKE %s", (f"{idea_id}%",)
    ).fetchone()

    idea, idea_id, refs = ready(db, " (c)", "CTR-0c0c0c")
    confirm(db, idea, idea_id, {})
    with pytest.raises(save.SaveRefused) as needs_line:
        save.save(db, idea, "CTR-0c0c0c", {"choice": "different", "ref": refs["idea"]})
    assert needs_line.value.code == "one_line_required"
    out = save.save(
        db,
        idea,
        "CTR-0c0c0c",
        {"choice": "different", "ref": refs["idea"], "text": "Mine is about lumpsum forms only"},
    )
    assert out["stage"] == "scanned"

    idea, idea_id, _ = ready(db, " (d)")
    assert save.save(db, idea, CODE, {"choice": "withdraw"})["stage"] == "withdrawn"
    assert counts(db, idea_id)["outbox"] == 0


def test_the_save_is_one_transaction(world: Any, monkeypatch: Any) -> None:
    db = world
    idea, idea_id, refs = ready(db, " (e)")
    confirm(db, idea, idea_id, {})

    def boom(conn: Any, idea_uuid: str) -> None:
        raise RuntimeError("injected")

    monkeypatch.setattr(save, "_hook_after_idea_update", boom)
    with pytest.raises(RuntimeError):
        save.save(db, idea, CODE, {"choice": "team_up", "ref": refs["idea"], "text": CONTEXT})
    row = db.execute("SELECT stage, raw_encrypted, canvas FROM ideas WHERE id = %s", (idea,)).fetchone()
    assert row["stage"] == "scanning" and row["raw_encrypted"] is not None and row["canvas"] is None
    assert counts(db, idea_id) == {"links": 0, "items": 0, "timers": 0, "outbox": 0}


def test_a_big_edit_reruns_the_match(world: Any) -> None:
    db = world
    idea, idea_id, _ = ready(db, " (f)")

    def judge_calls() -> int:
        return int(db.execute("SELECT count(*) AS n FROM llm_calls WHERE agent = 'judge'").fetchone()["n"])

    before = judge_calls()
    small = confirm(db, idea, idea_id, {"details": TEXT + " (f). Seen daily."})
    assert small["rerun_match"] is False and judge_calls() == before + 0
    big = confirm(
        db,
        idea,
        idea_id,
        {"details": "Canteen seating on the fourth floor is cramped at lunch and people queue for long."},
    )
    assert big["rerun_match"] is True and judge_calls() == before + 1
    assert edit_share("a b c d e", "a b c d e") == 0.0 and edit_share("a b c d e", "a b c d x") <= 0.2
    with pytest.raises(ConfirmRefused) as too_short:
        confirm(db, idea, idea_id, {"details": "short"})
    assert too_short.value.code == "details_too_short"
