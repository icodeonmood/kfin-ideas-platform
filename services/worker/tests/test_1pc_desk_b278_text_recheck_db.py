"""BLD-B278 (L-HIDE.detect, DEC-131 (3), non-negotiable 4; on lane C's BLD-C231): the review desk's own texts written
while the assistant was off get the gatekeeper's check once it is back (`desk.text_recheck`).

The five texts are a sent question, a decision reason, the committee's reversal note, a desk merge's note and the
reviewer's worth note. Each is written here with `ai.all` off, so it has had the patterns and names only and keeps
`gatekeeper_done_at` NULL. With both switches on, the re-check asks the gatekeeper about each masked copy, hides what
it finds in every copy of the idea (the reasons and notes through lane B's `sweep_value`, lane C's `_sweep` step 10),
and marks each text done only after a complete check:

- the writers mark a text done when the gatekeeper's check is complete as it is written;
- while either switch is off the job waits, and nothing is asked;
- a gateway failure is never marked done, and the run fails so the runner tries again;
- a queued question is not re-checked (Send hides it again);
- a reviewer's "Hide this" (lane C's `_sweep`) now reaches the desk's reasons and notes too.

A customer's name only the gatekeeper finds is made up for each test and found by a stand-in for
`hide.detect.gatekeeper_finds`, as lane C's and lane F's tests do. Synthetic people only (non-negotiable 11); lane B's
fixtures remove every idea and person made (the texts go with their idea)."""

from __future__ import annotations

import secrets
import string
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core import killswitch
from core.db import Conn
from desk import asking, committee, decide, merging, revise
from desk import text_recheck as tr
from desk.store import unseal
from hide import desk as hide_desk
from hide import detect
from hide.core import lock
from jobs.runner import HANDLERS, JobWaits
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

T = f.at(16, 12)  # Monday 16 November 2026, noon IST
TEXTS = ("questions", "idea_decisions", "decision_reversals", "merges", "idea_worth")
UNCHECKED = tr.unchecked  # the real queue read, kept before any test narrows it to its own idea


def made_up_name() -> str:
    return "Kiran Ra" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(4))


@pytest.fixture
def switches(monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    """`ai.all` and `agent.gatekeeper` as the test sets them; every other switch as the database has it."""
    sw = {"ai.all": False, "agent.gatekeeper": True}
    real = killswitch.is_on
    monkeypatch.setattr(
        killswitch, "is_on", lambda name, conn=None: sw[name] if name in sw else real(name, conn)
    )
    return sw


@pytest.fixture
def gatekeeper(monkeypatch: pytest.MonkeyPatch, switches: dict[str, bool]) -> dict[str, Any]:
    """A stand-in for the gatekeeper: it finds `name` wherever it is, behaves as the real one does with the switches,
    and fails as the gateway does when `down` is set. `asked` holds every text it was asked about."""
    state: dict[str, Any] = {"name": made_up_name(), "asked": [], "down": False}

    def gatekeeper_finds(conn: Any, text: str, scope: str) -> detect.Gate:
        if not text.strip():
            return detect.Gate([], checked=True)
        if not switches["ai.all"]:
            return detect.Gate([])  # not checked, nothing asked
        state["asked"].append(text)
        if not switches["agent.gatekeeper"]:
            return detect.Gate([], "switched_off", True)
        if state["down"]:
            return detect.Gate([], "connection")
        name = str(state["name"])
        found: list[detect.Found] = []
        at = text.find(name)
        while at != -1:
            found.append(detect.Found(at, at + len(name), "name", name, "gatekeeper"))
            at = text.find(name, at + len(name))
        return detect.Gate(found, checked=True)

    monkeypatch.setattr(detect, "gatekeeper_finds", gatekeeper_finds)
    return state


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, repo: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    _ = repo
    f.install_fake_notify(monkeypatch)
    kavya, ravi = f.person(db, "Kavya Menon"), f.person(db, "Ravi Nair")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    rohan = f.person(db, "Rohan Mehta", roles=("committee",))
    return {
        "kavya": kavya, "ravi": ravi, "meera": meera, "rohan": rohan,
        "idea": f.idea(db, kavya, shared_at=f.at(14, 10)),
        "ravis": f.idea(db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(15, 9)),
    }  # fmt: skip


def write_all(db: Conn, cast: dict[str, Any], name: str) -> dict[str, str]:
    """The five desk texts, each naming the same made-up customer, as the desk writes them. Returns each row's id."""
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    worth = f"Scaled up for the three branches; {name} alone rang four times."
    revise.revise_worth(db, ref, meera, {"hours_month": "200 to 300", "note": worth}, T)
    merging.desk_merge(db, ref, meera, {"other_idea_id": cast["ravis"]["idea_id"], "lead": "this",
                                        "note": f"You both found {name}'s R07 calls."}, T)  # fmt: skip
    asked = {"part": "often", "text": f"How often did {name} ring the Vizag branch about R07?"}
    asking.send_set(db, ref, meera, {"questions": [asked], "time_to_answer": "3d"}, T)
    reason = f"Picked. {name} rang the branch four times about the R07 SMS, so the fix is worth it."
    d = decide.send(db, ref, meera, {"choice": "pick", "reason": reason}, f.at(16, 13))
    window = db.execute("SELECT id FROM decision_windows WHERE decision_id = %s", (d["id"],)).fetchone()
    assert window is not None
    note = f"Not picked after all: {name}'s calls were about another code, and that has its own fix."
    committee.reverse_window(db, str(window["id"]), cast["rohan"]["id"], {"to": "not_picked", "note": note},
                             f.at(17, 10))  # fmt: skip
    return ids_of(db, cast)


def ids_of(db: Conn, cast: dict[str, Any]) -> dict[str, str]:
    idea = cast["idea"]["id"]
    one = {
        "questions": "SELECT q.id FROM questions q JOIN question_sets s ON s.id = q.set_id "
        "WHERE s.idea_uuid = %s AND s.state <> 'queued'",
        "idea_decisions": "SELECT id FROM idea_decisions WHERE idea_uuid = %s",
        "decision_reversals": "SELECT r.id FROM decision_reversals r JOIN decision_windows w ON w.id = r.window_id "
        "JOIN idea_decisions d ON d.id = w.decision_id WHERE d.idea_uuid = %s",
        "merges": "SELECT id FROM merges WHERE lead_idea_uuid = %s AND via = 'review_desk'",
        "idea_worth": "SELECT id FROM idea_worth WHERE idea_uuid = %s AND by_side = 'reviewer'",
    }
    out: dict[str, str] = {}
    for table, sql in one.items():
        rows = db.execute(sql, (idea,)).fetchall()
        assert len(rows) == 1, table
        out[table] = str(rows[0]["id"])
    return out


def text_of(db: Conn, table: str, row_id: str) -> str:
    column = tr.COLUMNS[table]
    row = db.execute(f"SELECT {column} AS blob FROM {table} WHERE id::text = %s", (row_id,)).fetchone()  # noqa: S608
    assert row is not None
    words = unseal(row["blob"], table, column, row_id)
    assert words is not None
    return words


def done_of(db: Conn, ids: dict[str, str]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for table, row_id in ids.items():
        row = db.execute(
            f"SELECT gatekeeper_done_at IS NOT NULL AS done FROM {table} WHERE id::text = %s",  # noqa: S608
            (row_id,),
        ).fetchone()
        assert row is not None
        out[table] = bool(row["done"])
    return out


def mine(db: Conn, cast: dict[str, Any]) -> list[tr.Text]:
    """The re-check's queue, only this test's idea (other rows in the database are not this test's)."""
    idea = str(cast["idea"]["id"])
    return [
        t for t in UNCHECKED(db, limit=10_000, head=10_000) if t.idea_uuid in (idea, str(cast["ravis"]["id"]))
    ]


# ---- the writers ------------------------------------------------------------------------------------------------------
def test_BLD_B278_written_with_the_assistant_off_each_desk_text_waits_with_the_patterns_only(
    db: Conn, cast: dict[str, Any], gatekeeper: dict[str, Any]
) -> None:
    name = gatekeeper["name"]
    ids = write_all(db, cast, name)
    assert done_of(db, ids) == dict.fromkeys(TEXTS, False)
    for table, row_id in ids.items():
        assert name in text_of(db, table, row_id), table  # only the gatekeeper finds it
    assert gatekeeper["asked"] == []
    assert {t.table for t in mine(db, cast)} == set(TEXTS)


def test_BLD_B278_written_with_the_gatekeeper_on_each_desk_text_is_checked_and_marked_at_once(
    db: Conn, cast: dict[str, Any], gatekeeper: dict[str, Any], switches: dict[str, bool]
) -> None:
    switches["ai.all"] = True
    name = gatekeeper["name"]
    ids = write_all(db, cast, name)
    assert done_of(db, ids) == dict.fromkeys(TEXTS, True)
    for table, row_id in ids.items():
        assert name not in text_of(db, table, row_id), table
    assert mine(db, cast) == []


def test_BLD_B278_a_gateway_failure_as_it_is_written_leaves_the_text_waiting(
    db: Conn, cast: dict[str, Any], gatekeeper: dict[str, Any], switches: dict[str, bool]
) -> None:
    switches["ai.all"], gatekeeper["down"] = True, True
    ids = write_all(db, cast, gatekeeper["name"])
    assert done_of(db, ids) == dict.fromkeys(TEXTS, False)


# ---- the re-check -----------------------------------------------------------------------------------------------------
def test_BLD_B278_once_the_assistant_is_back_each_text_is_checked_and_the_name_is_hidden_in_every_copy(
    db: Conn, cast: dict[str, Any], gatekeeper: dict[str, Any], switches: dict[str, bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    name = gatekeeper["name"]
    ids = write_all(db, cast, name)
    monkeypatch.setattr(tr, "unchecked", lambda conn, limit=tr.BATCH, head=tr.HEAD: mine(conn, cast)[:limit])
    with pytest.raises(JobWaits):  # the assistant is still off: the job waits, its try given back
        tr.run(db, {})
    assert gatekeeper["asked"] == [] and done_of(db, ids) == dict.fromkeys(TEXTS, False)

    switches["ai.all"] = True
    tr.run(db, {})
    assert done_of(db, ids) == dict.fromkeys(TEXTS, True)
    masked = detect.mask("name", name)
    for table, row_id in ids.items():
        text = text_of(db, table, row_id)
        assert name not in text and masked in text, table
    assert gatekeeper["asked"]  # the masked copies, one model call per text
    places = {
        (r["source"], r["source_id"])
        for r in db.execute(
            "SELECT source, source_id FROM hidden_details WHERE idea_uuid = %s AND found_by = 'gatekeeper'",
            (cast["idea"]["id"],),
        ).fetchall()
    }
    assert ("desk", ids["questions"]) in places  # lane C's step 5
    for table in ("idea_decisions", "decision_reversals", "merges", "idea_worth"):
        assert ("desk", f"{table}:{ids[table]}") in places, table  # lane B's sweep_value, step 10
    rechecked = db.execute(
        "SELECT count(*) AS n FROM audit_log WHERE action = 'hide.rechecked' AND entity = %s AND after->>'source' = 'desk'",
        (f"idea:{cast['idea']['id']}",),
    ).fetchone()
    assert rechecked is not None and rechecked["n"] >= 1
    # nothing left: a second run asks nothing more about these texts
    before = len(gatekeeper["asked"])
    tr.run(db, {})
    assert len(gatekeeper["asked"]) == before


def test_BLD_B278_the_reversal_note_on_the_joining_idea_is_hidden_too(
    db: Conn, cast: dict[str, Any], gatekeeper: dict[str, Any], switches: dict[str, bool]
) -> None:
    """A reversal note is hidden under the decision's idea; its sweep finds it there (`sweep_value`)."""
    name = gatekeeper["name"]
    ids = write_all(db, cast, name)
    switches["ai.all"] = True
    t = next(x for x in mine(db, cast) if x.table == "decision_reversals")
    assert tr.check_one(db, t) == 1
    assert name not in text_of(db, "decision_reversals", ids["decision_reversals"])
    assert name not in text_of(db, "idea_decisions", ids["idea_decisions"])  # the same value, every copy


def test_BLD_B278_a_gateway_failure_is_never_marked_done_and_the_run_fails_for_the_backoff(
    db: Conn, cast: dict[str, Any], gatekeeper: dict[str, Any], switches: dict[str, bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    name = gatekeeper["name"]
    ids = write_all(db, cast, name)
    monkeypatch.setattr(tr, "unchecked", lambda conn, limit=tr.BATCH, head=tr.HEAD: mine(conn, cast)[:limit])
    switches["ai.all"], gatekeeper["down"] = True, True
    with pytest.raises(tr.RecheckFailed):
        tr.run(db, {})
    assert len(gatekeeper["asked"]) == len(TEXTS)  # each text asked once; a failure goes on to the next
    assert done_of(db, ids) == dict.fromkeys(TEXTS, False)
    assert all(name in text_of(db, table, row_id) for table, row_id in ids.items())
    gatekeeper["down"] = False
    tr.run(db, {})
    assert done_of(db, ids) == dict.fromkeys(TEXTS, True)


def test_BLD_B278_the_gatekeeper_switched_off_makes_the_job_wait_with_nothing_marked(
    db: Conn, cast: dict[str, Any], gatekeeper: dict[str, Any], switches: dict[str, bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    ids = write_all(db, cast, gatekeeper["name"])
    switches["ai.all"], switches["agent.gatekeeper"] = True, False
    with pytest.raises(JobWaits) as wait:
        tr.run(db, {})
    assert (wait.value.code, wait.value.seconds) == (tr.WAITING, tr.WAIT_S)
    t = mine(db, cast)[0]
    switches["agent.gatekeeper"] = True

    def switched_off(
        conn: Any, text: str, scope: str
    ) -> detect.Gate:  # switched off between the check and the call
        return detect.Gate([], "switched_off", True)

    monkeypatch.setattr(detect, "gatekeeper_finds", switched_off)
    with pytest.raises(JobWaits):
        tr.check_one(db, t)
    assert done_of(db, ids) == dict.fromkeys(TEXTS, False)


def test_BLD_B278_a_queued_question_is_not_rechecked(
    db: Conn, cast: dict[str, Any], gatekeeper: dict[str, Any], switches: dict[str, bool]
) -> None:
    """Nobody but its reviewer reads a queued question, and Send hides it again: it is not in the re-check's queue."""
    q = {"part": "often", "text": f"How often did {gatekeeper['name']} ring about R07?"}
    asking.save_queue(db, cast["idea"]["idea_id"], cast["meera"]["id"],
                      {"questions": [q], "time_to_answer": "3d", "base": 0}, T)  # fmt: skip
    queued = db.execute(
        "SELECT q.gatekeeper_done_at FROM questions q JOIN question_sets s ON s.id = q.set_id "
        "WHERE s.idea_uuid = %s AND s.state = 'queued'",
        (cast["idea"]["id"],),
    ).fetchall()
    assert len(queued) == 1 and queued[0]["gatekeeper_done_at"] is None
    assert mine(db, cast) == []


# ---- lane C's step 10: "Hide this" reaches the desk's reasons and notes (non-negotiable 4) ---------------------------
def test_BLD_B278_a_reviewers_hide_now_reaches_the_desks_reasons_and_notes(
    db: Conn, cast: dict[str, Any], gatekeeper: dict[str, Any]
) -> None:
    """Before BLD-B278 a value the desk hid stayed in the decision reason and the notes: `_sweep` now calls
    `sweep_value` for them, under the lock its caller took."""
    name = gatekeeper["name"]
    ids = write_all(db, cast, name)
    idea = str(cast["idea"]["id"])
    with db.transaction():
        lock(db, idea)
        swept = hide_desk._sweep(db, idea, name, "name", found_by="reviewer")
    assert swept.copies >= len(TEXTS)
    for table, row_id in ids.items():
        assert name not in text_of(db, table, row_id), table
    # each reason and note is listed once, by its row, as a copy the sweep masked
    rows = db.execute(
        "SELECT source_id FROM hidden_details WHERE idea_uuid = %s AND source = 'desk' AND found_by = 'reviewer'",
        (idea,),
    ).fetchall()
    assert {f"{t}:{ids[t]}" for t in ("idea_decisions", "decision_reversals", "merges", "idea_worth")} <= {
        str(r["source_id"]) for r in rows
    }
    with db.transaction():  # a second sweep finds nothing more to mask
        lock(db, idea)
        assert tr.sweep_value(db, idea, name, "name", found_by="reviewer") == 0


def test_BLD_B278_the_job_is_registered_under_lane_cs_name() -> None:
    from hide.recheck import DESK_TEXT_RECHECK
    from jobs import handlers  # noqa: F401 (importing it registers the handlers)

    assert DESK_TEXT_RECHECK == tr.JOB and tr.JOB in HANDLERS
    assert hide_desk.DESK_TEXTS == ("desk.text_recheck", "sweep_value")
