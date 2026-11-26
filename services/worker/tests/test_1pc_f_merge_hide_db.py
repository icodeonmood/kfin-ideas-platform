"""L-MERGE.effects/5, L-HIDE, BLD-B247, BLD-F096: a merge the lead accepts drops the merged idea's queued questions
through lane B's `desk.asking.drop_queued`, so what lane C's hide kept for them goes with them, and it takes lane C's
lock on both ideas first, in uuid order, before their row locks, in the same order as lane B's desk merge.

Each test goes through the other lanes' public entry points and never changes them: lane B's queue
(`desk.asking.save_queue`) and desk merge (`desk.merging.desk_merge`), lane C's "Hide this" (`hide.desk_hide`) and
`hide_message`. Synthetic people only (non-negotiable 11): the pack's fictional cast, and a customer's name made up at
run time. Everything made is removed afterwards except `audit_log`, whose trigger refuses DELETE.
"""

from __future__ import annotations

import secrets
import string
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from teamup import requests
from tests import f_teamup_fixtures as f

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
NOTE = "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07."
MERGE_NOTE = "You both found the same R07 calls."
Q1 = {"part": "often", "text": "Is it 40 calls a day at one branch, or across Hyderabad?"}


@pytest.fixture
def db(db: Conn, monkeypatch: pytest.MonkeyPatch) -> Iterator[Conn]:
    """The shared `db`, with the seed's configuration (promises for the desk's queue and merge) and clean-up: the
    jobs, timers and vault values this test's ideas made, then (through `f.clean`) its ideas and people."""
    from core import killswitch
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(SEED))
    get_settings.cache_clear()
    killswitch.clear_cache()
    last_job = int(db.execute("SELECT coalesce(max(id), 0) AS n FROM jobs").fetchone()["n"])
    yield db
    from hide.core import scope_for

    ideas = list(f._made["ideas"])
    refs = [
        str(r["idea_id"])
        for r in db.execute(
            "SELECT idea_id FROM ideas WHERE id = ANY(%s::uuid[]) AND idea_id IS NOT NULL", (ideas,)
        ).fetchall()
    ]
    scopes = [scope_for(i) for i in ideas]
    db.execute("DELETE FROM jobs WHERE id > %s", (last_job,))
    db.execute("DELETE FROM sla_timers WHERE entity_type = 'idea' AND entity_id = ANY(%s)", (refs,))
    db.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (scopes,))
    db.execute("DELETE FROM vault_counters WHERE scope_id = ANY(%s)", (scopes,))
    f.clean(db)
    killswitch.clear_cache()
    get_settings.cache_clear()


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> f.Inbox:
    return f.record_inbox(monkeypatch)


@pytest.fixture
def cast(db: Conn) -> dict[str, Any]:
    """Ravi leads the idea shared first; Kavya's, shared a day later, is the one that joins it; Meera reviews."""
    ravi = f.person(db, "Ravi Nair")
    kavya = f.person(db, "Kavya Menon")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    lead = f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(13, 9))
    mine = f.idea(
        db, kavya, title="Investors call to ask why a redemption was rejected", shared_at=f.at(14, 10)
    )
    return {"ravi": ravi, "kavya": kavya, "meera": meera, "lead": lead, "mine": mine}


def _sharer_message(db: Conn, c: dict[str, Any], text: str) -> str:
    """One of Kavya's messages on her idea, hidden as lane C hides a sharer's message (her own words sealed for her)
    and stored as the masked copy. The patterns only: the gatekeeper is not asked here."""
    from hide import hide_message
    from onepc.context import seal_text

    mid, idea_uuid = str(uuid.uuid4()), str(c["mine"]["id"])
    with db.transaction():
        out = hide_message(db, idea_uuid, text, by=c["kavya"]["id"], source_id=mid, gatekeeper=False)
        db.execute(
            "INSERT INTO idea_messages (id, idea_uuid, seq, via, text_encrypted, char_count) "
            "VALUES (%s, %s, 1, 'typed', %s, %s)",
            (mid, idea_uuid, seal_text("idea_messages", "text_encrypted", mid, out.masked), len(text)),
        )
    return mid


def _queue(db: Conn, c: dict[str, Any], questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Meera's queue on Kavya's idea, kept as lane B's panel keeps it (BLD-B272): one queued set, not sent."""
    from desk import asking

    return asking.save_queue(
        db, c["mine"]["idea_id"], c["meera"]["id"],
        {"questions": questions, "time_to_answer": "1w", "base": 0, "after": None}, f.at(16, 11),
    )  # fmt: skip


def _queued_ids(db: Conn, idea_uuid: Any) -> set[str]:
    return {
        str(r["id"])
        for r in db.execute(
            "SELECT q.id FROM questions q JOIN question_sets s ON s.id = q.set_id WHERE s.idea_uuid = %s "
            "AND s.state = 'queued'",
            (idea_uuid,),
        ).fetchall()
    }


def _details(db: Conn, idea_uuid: Any, source: str | None = None) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT id, source, source_id, vault_tag FROM hidden_details WHERE idea_uuid = %s "
            "AND (%s::text IS NULL OR source = %s::text) ORDER BY id",
            (idea_uuid, source, source),
        ).fetchall()
    ]


def _vault(db: Conn, idea_uuid: Any) -> dict[str, str]:
    """The idea's vault values, tag -> value, read the way only the worker's restore reads them."""
    from pii import vault

    return {tag: value for tag, (_, value) in vault.mapping(db, f"DRAFT-{idea_uuid}").items()}


def test_l_merge_effects_5_l_hide_bld_f096_a_lead_accepted_merge_leaves_no_row_for_a_queued_question(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """L-MERGE.effects/5, L-HIDE.rules/7, BLD-F096: a customer's name the checks missed is in Kavya's message and in a
    question Meera queued on Kavya's idea. Meera's "Hide this" (lane C's `desk_hide`) masks it everywhere and writes a
    `hidden_details` row for each copy, the queued question's included. Ravi then merges Kavya's idea into his through
    the team-up answer: its queued set goes, and no `hidden_details` row is left keyed by a question that is gone (the
    sharer's page lists every row of the idea). The name stays hidden on Kavya's message, its vault value with it."""
    from hide import desk_hide

    name = "Kiran Ra" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(4))  # synthetic, missed
    mine = cast["mine"]
    idea_uuid = mine["id"]
    text = f"The agent {name} keeps asking why the redemption is late."
    mid = _sharer_message(db, cast, text)
    _queue(db, cast, [{"part": "who", "text": f"Did {name} call the branch twice?"}, Q1])
    gone = _queued_ids(db, idea_uuid)
    assert len(gone) == 2
    start = text.index(name)
    desk_hide(db, str(idea_uuid), source_kind="message", source_id=mid, start=start, end=start + len(name),
              by=cast["meera"]["id"])  # fmt: skip
    # "Hide this" wrote a row for the queued copy
    assert {str(r["source_id"]) for r in _details(db, idea_uuid, "desk")} & gone

    sent = requests.send(db, cast["lead"]["idea_id"], cast["kavya"]["id"],
                         {"note": NOTE, "brought_idea_ids": [mine["idea_id"]]})  # fmt: skip
    out = requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "merge"})
    assert out["request"]["state"] == "approved_merged"
    assert f.status_of(db, mine) == {"status": "merged", "merged_into": cast["lead"]["id"]}
    assert _queued_ids(db, idea_uuid) == set()
    assert (
        db.execute(
            "SELECT count(*) AS n FROM question_sets WHERE idea_uuid = %s AND state = 'queued'", (idea_uuid,)
        ).fetchone()["n"]
        == 0
    )
    left = [r for r in _details(db, idea_uuid) if str(r["source_id"]) in gone]
    assert left == []
    on_message = [r for r in _details(db, idea_uuid, "message") if str(r["source_id"]) == mid]
    assert len(on_message) == 1 and _vault(db, idea_uuid)[on_message[0]["vault_tag"]] == name


# ---- BLD-B247: one lock order on both paths that can lock the same two ideas -----------------------------------


class _Undo(Exception):
    """Raised at the end of a path, so its transaction rolls back and the next path starts from the same two ideas."""


def _undone(db: Conn, run: Callable[[], object]) -> None:
    with pytest.raises(_Undo), db.transaction():
        run()
        raise _Undo


def _lock_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Every lock asked for, in order: ("hide", uuid) for each call of lane C's `hide.core.lock` (lane B reaches it as
    `desk.adapters.hide_lock`, through `lock_idea` and `lock_refs`; lane F through `teamup.adapters.lock_hide`; lane
    C's own hide and `forget` call it too), and ("row", uuid) for each idea row that lane F's `lock_ideas` or lane B's
    `lock_pair` locks, in the order it locks them (both by uuid)."""
    import hide.core
    from desk import adapters as desk_adapters
    from desk import merging as desk_merging
    from teamup import merging, store

    calls: list[tuple[str, str]] = []
    real_lock, real_ideas, real_pair = hide.core.lock, store.lock_ideas, desk_merging.lock_pair

    def hide_lock(conn: Conn, idea_uuid: str) -> None:
        calls.append(("hide", str(idea_uuid)))
        real_lock(conn, idea_uuid)

    def lock_ideas(conn: Conn, *uuids: Any) -> dict[str, dict[str, Any]]:
        calls.extend(("row", u) for u in sorted({str(u) for u in uuids}))
        return real_ideas(conn, *uuids)

    def lock_pair(
        conn: Conn, ref: str, other_ref: str, field: str | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        this, other = real_pair(conn, ref, other_ref, field)
        calls.extend(("row", u) for u in sorted((str(this["id"]), str(other["id"]))))  # it locks nothing else
        return this, other

    monkeypatch.setattr(hide.core, "lock", hide_lock)
    monkeypatch.setattr(desk_adapters, "hide_lock", hide_lock)
    monkeypatch.setattr(requests, "lock_ideas", lock_ideas)
    monkeypatch.setattr(merging, "lock_ideas", lock_ideas)
    monkeypatch.setattr(desk_merging, "lock_pair", lock_pair)
    return calls


def _first_taken(calls: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Each lock the first time it is asked for. A later call on a lock the transaction already holds is re-entrant
    and waits for nothing, so this is the order in which the transaction can wait."""
    return list(dict.fromkeys(calls))


def test_l_hide_bld_b247_l_merge_effects_5_bld_f096_a_team_up_merge_and_a_desk_merge_take_the_locks_in_one_order(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-HIDE (BLD-C067's lock order), BLD-B247, L-MERGE.effects/5, BLD-F096: the two paths that can lock the same two
    ideas, (1) Ravi's "Merge it" on Kavya's team-up request (`requests.answer`, then `apply_lead_merge`) and (2) lane
    B's desk merge of the same pair (`desk.merging.desk_merge`), each take lane C's lock on both ideas first, in uuid
    order, before any row lock, and then the rows in that same order. Every later lane C lock on the way (the merged
    idea's queued question forgotten by `drop_queued`, the desk's note hidden on the lead) is one the transaction
    already holds. So the two cannot deadlock each other, nor a reviewer's "Hide this", which takes lane C's lock
    first too. Each path runs in a transaction that is rolled back, so both start from the same two ideas."""
    from desk import merging as desk_merging

    lead, mine = cast["lead"], cast["mine"]
    _queue(db, cast, [Q1])  # so each merge has a queued question to forget under lane C's lock
    sent = requests.send(db, lead["idea_id"], cast["kavya"]["id"],
                         {"note": NOTE, "brought_idea_ids": [mine["idea_id"]]})  # fmt: skip
    lo, hi = sorted((str(lead["id"]), str(mine["id"])))
    in_order = [("hide", lo), ("hide", hi), ("row", lo), ("row", hi)]
    calls = _lock_calls(monkeypatch)

    def team_up_merge() -> None:
        out = requests.answer(db, sent["id"], cast["ravi"]["id"], {"answer": "merge"})
        assert out["request"]["state"] == "approved_merged"
        assert _queued_ids(db, mine["id"]) == set()  # dropped inside the path, under the locks above

    def desk_merge() -> None:
        merged = desk_merging.desk_merge(
            db, mine["idea_id"], cast["meera"]["id"],
            {"other_idea_id": lead["idea_id"], "lead": "other", "note": MERGE_NOTE}, f.at(16, 12),
        )  # fmt: skip
        assert (merged["lead_idea_id"], merged["merged_idea_id"]) == (lead["idea_id"], mine["idea_id"])
        assert _queued_ids(db, mine["id"]) == set()

    by_path: dict[str, list[tuple[str, str]]] = {}
    for path, run in (("team_up", team_up_merge), ("desk", desk_merge)):
        calls.clear()
        _undone(db, run)
        by_path[path] = list(calls)
        # the merged idea's lane C lock is asked for again on the way (its queued question forgotten): held already
        assert ("hide", str(mine["id"])) in by_path[path][len(in_order) :], path
    assert _first_taken(by_path["team_up"]) == in_order
    assert _first_taken(by_path["desk"]) == in_order
    # both rolled back: the two ideas and the queued question are as they were
    assert f.status_of(db, mine) == {"status": "with_review_desk", "merged_into": None}
    assert len(_queued_ids(db, mine["id"])) == 1


# ---- BLD-F108: a lead-accepted merge takes the merged idea's questions off Needs you (L-INBOX.rules/3) ----------


def _needs_you(db: Conn, user_id: str, key: str) -> list[bool]:
    """Whether each of the person's in-app items under `key` (the item and its reminders) still needs them."""
    return [
        bool(r["needs_you"]) and r["resolved_at"] is None
        for r in db.execute(
            "SELECT needs_you, resolved_at FROM notifications WHERE user_id = %s AND channel = 'in_app' "
            "AND (dedupe_key = %s OR starts_with(dedupe_key, %s)) ORDER BY created_at",
            (user_id, key, key + ":"),
        ).fetchall()
    ]


def test_l_inbox_rules_3_l_merge_effects_1_bld_f108_a_lead_accepted_merge_resolves_the_merged_ideas_questions(
    db: Conn, cast: dict[str, Any]
) -> None:
    """L-INBOX.rules/3, L-MERGE.effects/1, BLD-F108: Meera sends Kavya a set of questions on Kavya's idea, so Kavya has
    "Questions from the review desk" in Needs you. Ravi then merges Kavya's idea into his through the team-up answer
    (`requests.answer`, then `apply_lead_merge`): the set closes, and Kavya's item leaves Needs you with its
    reminders, as it does when the review desk merges (`desk.merging`, lane B's `adapters.resolve`). Lane A's own
    `notify`, so the item itself is read, not a stand-in."""
    from desk import asking

    mine, kavya = cast["mine"], cast["kavya"]
    sent = asking.send_set(db, mine["idea_id"], cast["meera"]["id"],
                           {"questions": [Q1], "time_to_answer": "3d"}, f.at(16, 11))  # fmt: skip
    key = f"qs:{sent['id']}"
    assert _needs_you(db, kavya["id"], key) == [True]

    asked = requests.send(db, cast["lead"]["idea_id"], kavya["id"],
                          {"note": NOTE, "brought_idea_ids": [mine["idea_id"]]})  # fmt: skip
    out = requests.answer(db, asked["id"], cast["ravi"]["id"], {"answer": "merge"})
    assert out["request"]["state"] == "approved_merged"
    assert f.status_of(db, mine) == {"status": "merged", "merged_into": cast["lead"]["id"]}
    closed = db.execute("SELECT state FROM question_sets WHERE id = %s", (sent["id"],)).fetchone()
    assert closed is not None and closed["state"] == "closed"
    assert _needs_you(db, kavya["id"], key) == [False]
