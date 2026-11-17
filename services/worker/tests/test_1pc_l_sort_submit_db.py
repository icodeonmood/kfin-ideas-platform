"""L-SORT and L-SUBMIT against a freshly migrated database (lane C, BLD-C080 to BLD-C086): sorting suggested from the
draft and confirmed or changed, the checks before Submit, Submit itself (reference, status, clock, crew, check,
idempotency), "Checked and matched", the edit window with versions, review routing, and the decide_by timer firing on
lane A's engine. Synthetic people only (non-negotiable 11). Test names carry the module IDs they cover."""

from __future__ import annotations

import datetime as dt
import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from psycopg.types.json import Jsonb

from core.config import get_settings
from submit import check, edit, ready, routing, send, sorting
from submit.config import DECLARATION_VERSION
from submit.errors import NotFound, Refused

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
NOW = dt.datetime(2026, 11, 14, 4, 35, tzinfo=dt.UTC)  # Saturday 14 November, 10:05 am in the office
REF = re.compile(r"^IDEA-2026-[0-9]{6}$")


@pytest.fixture
def world(db: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """A sharer with a ready draft whose parts suggest the sorting, a reviewer, and a colleague."""
    monkeypatch.setenv("COMPANY_REPO_PATH", str(SEED))
    get_settings.cache_clear()
    # Submit queues jobs (submit.check, voice.purge); the conftest does not empty `jobs`, so this test takes its own
    # away again, or a later test's `run_one` would claim them first.
    last_job = int(db.execute("SELECT coalesce(max(id), 0) AS n FROM jobs").fetchone()["n"])
    people: dict[str, str] = {}
    for key, name, code in (
        ("asha", "Asha Verma", "CTR-a1b2c3"),
        ("ravi", "Ravi Desai", "CTR-b2c3d4"),
        ("neha", "Neha Kulkarni", "CTR-c3d4e5"),
    ):
        row = db.execute(
            "INSERT INTO users (emp_id_hash, name, email, location, first_name) VALUES (%s, %s, %s, 'Hyderabad', %s) "
            "RETURNING id",
            (f"test-{key}", name, f"{key}@kfintech.example", name.split()[0]),
        ).fetchone()
        people[key] = str(row["id"])
        db.execute(
            "INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, row["id"])
        )
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'reviewer')", (people["ravi"],))
    draft = _draft(db, "CTR-a1b2c3")
    yield {"conn": db, "p": people, "draft": draft}
    db.execute("DELETE FROM jobs WHERE id > %s", (last_job,))
    get_settings.cache_clear()


def _draft(db: Any, code: str) -> str:
    row = db.execute(
        "INSERT INTO ideas (contributor_code, status, kind, channel, saved_at, created_at) "
        "VALUES (%s, 'draft', 'problem', 'web', %s, %s) RETURNING id",
        (code, NOW - dt.timedelta(minutes=2), NOW - dt.timedelta(minutes=3)),
    ).fetchone()
    uid = str(row["id"])
    parts = {
        "title": (
            {"title": "Rejection SMS codes confuse investors", "summary": "The SMS only gives a code."},
            None,
        ),
        "often": ("About 40 calls a day at one branch", None),
        "who": (["Investors", "KFin teams"], "because you mentioned investors and the branch"),
        "value": (["saves_time", "saves_cost"], "because you said about 40 calls a day"),
        "area": ("Investor service", "because it’s about investors and the SMS they get"),
    }
    for key, (value, why) in parts.items():
        db.execute(
            "INSERT INTO idea_parts (idea_uuid, key, state, value, why) VALUES (%s, %s, 'filled', %s, %s)",
            (uid, key, Jsonb(value), why),
        )
    return uid


def _idea(world: dict[str, Any], key: str | None = None) -> dict[str, Any]:
    row = world["conn"].execute("SELECT * FROM ideas WHERE id = %s", (key or world["draft"],)).fetchone()
    return dict(row)


def _submit(world: dict[str, Any], key: str | None = None, **kw: Any) -> tuple[int, dict[str, Any]]:
    return send.submit(
        world["conn"],
        key or world["draft"],
        world["p"]["asha"],
        {"declaration_version": DECLARATION_VERSION},
        now=kw.pop("now", NOW),
        **kw,
    )


def _confirm(world: dict[str, Any]) -> dict[str, Any]:
    return sorting.update_draft(world["conn"], world["draft"], world["p"]["asha"], {"confirm": True}, now=NOW)


# --- L-SORT -------------------------------------------------------------------------------------------------------


def test_l_sort_rules_1_each_field_arrives_prefilled_with_its_reason(world: dict[str, Any]) -> None:
    v = sorting.read_draft(world["conn"], world["draft"], world["p"]["asha"])
    assert v["affects"] == {
        "value": ["Investors", "KFin teams"],
        "source": "suggested",
        "why": "because you mentioned investors and the branch",
        "why_line": "Suggested because you mentioned investors and the branch.",
    }
    assert v["kind"]["value"] == "problem"
    assert v["kind"]["why_line"] == "Suggested because you described something that goes wrong today."
    assert v["area"]["value"] == "Investor service"
    assert v["brings"]["value"] == ["saves_time", "saves_cost"]
    assert v["confirmed"] is False and v["complete"] is True
    assert v["rail"] == "Suggested, not confirmed yet"
    assert v["note"] == "These are suggestions from your words. Not confirmed yet."


def test_l_sort_rules_2_one_action_confirms_every_untouched_suggestion(world: dict[str, Any]) -> None:
    v = _confirm(world)
    assert v["confirmed"] is True
    assert {f: v[f]["source"] for f in sorting.FIELDS} == dict.fromkeys(sorting.FIELDS, "confirmed")
    assert v["rail"] == "Investor service, saves time, saves cost"
    assert v["summary"] == "Investor service, affecting investors and KFin teams, saves time, saves cost"
    assert v["note"] is None
    idea = _idea(world)
    assert idea["area"] == "Investor service" and idea["sorting_confirmed_at"] == NOW
    assert idea["stage"] == "draft"  # new code never writes ideas.stage


def test_l_sort_rules_3_a_change_is_recorded_and_never_overwritten(world: dict[str, Any]) -> None:
    conn, asha = world["conn"], world["p"]["asha"]
    v = sorting.update_draft(conn, world["draft"], asha, {"area": "operations"}, now=NOW)
    assert v["area"] == {"value": "Operations", "source": "changed", "why": None, "why_line": None}
    assert v["confirmed"] is False  # the other three are still suggestions
    conn.execute(
        "UPDATE idea_parts SET value = %s WHERE idea_uuid = %s AND key = 'area'",
        (Jsonb("Technology"), world["draft"]),
    )
    v = _confirm(world)
    assert v["area"]["value"] == "Operations" and v["area"]["source"] == "changed"
    assert v["kind"]["source"] == "confirmed"
    # Choosing the suggestion itself counts as confirming it, not as a change.
    v = sorting.update_draft(conn, world["draft"], asha, {"brings": ["saves_cost", "saves_time"]}, now=NOW)
    assert v["brings"]["source"] == "confirmed"


def test_v_fields_sorting_an_empty_required_field_is_refused(world: dict[str, Any]) -> None:
    with pytest.raises(Refused) as err:
        sorting.update_draft(world["conn"], world["draft"], world["p"]["asha"], {"affects": []}, now=NOW)
    assert err.value.code == "sorting_incomplete" and err.value.field == "sorting"
    world["conn"].execute("DELETE FROM idea_parts WHERE idea_uuid = %s AND key = 'area'", (world["draft"],))
    with pytest.raises(Refused) as err:
        _confirm(world)  # no suggested area: the person picks one first
    assert err.value.message == "Confirm these, or change any of them, before you send."


def test_l_sort_someone_elses_draft_looks_missing(world: dict[str, Any]) -> None:
    with pytest.raises(NotFound):
        sorting.read_draft(world["conn"], world["draft"], world["p"]["neha"])
    with pytest.raises(NotFound):
        sorting.update_draft(world["conn"], world["draft"], world["p"]["neha"], {"confirm": True}, now=NOW)


def test_l_sort_rules_8_the_trust_metric_counts_changes(world: dict[str, Any]) -> None:
    sorting.update_draft(world["conn"], world["draft"], world["p"]["asha"], {"area": "Operations"}, now=NOW)
    _confirm(world)
    _submit(world)
    rows = {
        r["field"]: (r["shared"], r["kept"], r["changed"])
        for r in world["conn"].execute("SELECT * FROM sorting_trust")
    }
    assert rows["area"] == (1, 0, 1) and rows["kind"] == (1, 1, 0)


def test_l_sort_rules_7_any_reviewer_never_the_sharer(world: dict[str, Any]) -> None:
    conn, p = world["conn"], world["p"]
    conn.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'reviewer')", (p["asha"],))
    idea = _idea(world)
    assert routing.reviewers_for(conn, idea) == [p["ravi"]]
    assert routing.may_review(conn, idea, p["ravi"]) and not routing.may_review(conn, idea, p["asha"])


# --- L-SUBMIT.pre -------------------------------------------------------------------------------------------------


def test_l_sort_rules_4_submit_waits_for_the_sorting(world: dict[str, Any]) -> None:
    """V-ACC.share/11: nothing is sent; the Send part says what to do and where."""
    view = ready.send_view(world["conn"], world["draft"], world["p"]["asha"], now=NOW)
    assert view["ready"] is False
    assert view["submit_says"] == {
        "code": "sorting_unconfirmed",
        "message": "Confirm the sorting first, or change any of it.",
        "field": "sorting",
    }
    assert view["go_to"] == {"label": "Go to the sorting", "step": "check:2"}
    assert [r["value"] for r in view["rows"] if r["key"] == "sorting"] == ["Not confirmed yet"]
    with pytest.raises(Refused) as err:
        _submit(world)
    assert err.value.code == "sorting_unconfirmed"
    assert _idea(world)["status"] == "draft" and _idea(world)["idea_id"] is None


def test_l_submit_pre_the_send_part_rows_and_the_declaration(world: dict[str, Any]) -> None:
    _confirm(world)
    view = ready.send_view(world["conn"], world["draft"], world["p"]["asha"], now=NOW)
    assert view["ready"] is True and view["problems"] == []
    assert {r["key"]: r["value"] for r in view["rows"]} == {
        "title": "Rejection SMS codes confuse investors",
        "sorting": "Investor service, affecting investors and KFin teams, saves time, saves cost",
        "similar": "Nobody has raised this yet",
        "proof": "None added",
        "fix": "None added",
        "helpers": "Not said",
    }
    assert view["button"] == "Submit"
    assert view["declaration"]["version"] == DECLARATION_VERSION
    world["conn"].execute(
        "INSERT INTO idea_fix (idea_uuid, how) VALUES (%s, 'Print a plain sentence for each code on the SMS.')",
        (world["draft"],),
    )
    assert (
        ready.send_view(world["conn"], world["draft"], world["p"]["asha"], now=NOW)["button"]
        == "Submit with my fix"
    )


def _file(world: dict[str, Any], n: int, file_state: str) -> str:
    att = f"ATT-2026-{n:06d}"
    world["conn"].execute(
        "INSERT INTO attachments (id, idea_uuid, name, store_key, mime, bytes, sha256, uploaded_by_code, kind, "
        "file_state) VALUES (%s, %s, 'screenshot.png', %s, 'image/png', 1000, %s, 'CTR-a1b2c3', 'file', %s)",
        (att, world["draft"], f"quarantine/{att}", "0" * 64, file_state),
    )
    return att


def test_l_submit_pre_3_a_file_still_being_checked_holds_submit(world: dict[str, Any]) -> None:
    _confirm(world)
    att = _file(world, 1, "checking")
    with pytest.raises(Refused) as err:
        _submit(world)
    assert err.value.code == "file_blocked" and err.value.field == att
    world["conn"].execute("UPDATE attachments SET file_state = 'personal_data_found' WHERE id = %s", (att,))
    status, _ = _submit(world)  # DEC-107: a file with a customer detail found can still be sent
    assert status == 201


def test_l_submit_pre_4_a_waiting_merge_request_holds_submit(world: dict[str, Any]) -> None:
    conn = world["conn"]
    _confirm(world)
    other = _draft(conn, "CTR-c3d4e5")
    conn.execute(
        "UPDATE ideas SET status = 'with_review_desk', idea_id = next_idea_ref(%s) WHERE id = %s",
        (NOW, other),
    )
    conn.execute(
        "INSERT INTO merge_requests (draft_uuid, other_idea_uuid, from_code, note_encrypted) VALUES (%s, %s, "
        "'CTR-a1b2c3', %s)",
        (world["draft"], other, b"\x00"),
    )
    with pytest.raises(Refused) as err:
        _submit(world)
    assert err.value.code == "merge_waiting"
    assert err.value.message == (
        "Waiting for Neha to accept the merge. If Neha declines, you can send yours on its own."
    )


# --- L-SUBMIT.send ------------------------------------------------------------------------------------------------


def test_l_submit_send_1_the_idea_gets_its_reference_and_the_clock_starts(world: dict[str, Any]) -> None:
    """V-ACC.share/12 and L-SUBMIT.send/1, /4: the reference at once, status checking, decide-by Friday 20
    November, the edit window to Tuesday 17 November, the timer on the engine, the sharer as lead."""
    conn = world["conn"]
    _confirm(world)
    status, h = _submit(world)
    idea = _idea(world)
    assert status == 201 and REF.match(h["idea_id"]) and idea["idea_id"] == h["idea_id"]
    assert idea["status"] == "checking" and idea["stage"] == "draft"
    assert (
        idea["title"] == "Rejection SMS codes confuse investors"
        and idea["often"] == "About 40 calls a day at one branch"
    )
    assert idea["shared_at"] == NOW and idea["city"] == "Hyderabad"
    assert idea["declaration_version"] == DECLARATION_VERSION and idea["declared_at"] == NOW
    assert idea["decide_by"] == dt.datetime(2026, 11, 20, 12, 30, tzinfo=dt.UTC)  # 6 pm India time
    assert idea["edit_closes_at"] == dt.datetime(2026, 11, 17, 4, 35, tzinfo=dt.UTC)
    assert idea["affects"] == ["Investors", "KFin teams"] and idea["brings"] == ["saves_time", "saves_cost"]
    assert h["review"]["line"].startswith("The review desk will look at it by Friday 20 November.")
    assert h["edit_window"]["line"].startswith("Open to changes until Tuesday 17 November.")
    timer = conn.execute(
        "SELECT * FROM sla_timers WHERE entity_type = 'idea' AND entity_id = %s", (h["ref"],)
    ).fetchone()
    assert (
        timer["stage"] == "decide_by" and timer["state"] == "running" and timer["due_at"] == idea["decide_by"]
    )
    lead = conn.execute(
        "SELECT contributor_code, role, via FROM crew_members WHERE idea_uuid = %s", (idea["id"],)
    ).fetchone()
    assert dict(lead) == {"contributor_code": "CTR-a1b2c3", "role": "lead", "via": "shared"}
    jobs = {
        r["type"]
        for r in conn.execute("SELECT type FROM jobs WHERE payload->>'idea_uuid' = %s", (str(idea["id"]),))
    }
    assert {"submit.check", "voice.purge"} <= jobs
    audit = conn.execute(
        "SELECT actor, after FROM audit_log WHERE action = 'idea.submit' AND entity = %s",
        (f"idea:{h['ref']}",),
    ).fetchone()
    assert audit["actor"] == f"user:{world['p']['asha']}" and audit["after"]["sorting"]["area"] == "confirmed"
    history = [r["to_status"] for r in conn.execute(
        "SELECT to_status FROM idea_status_history WHERE idea_uuid = %s ORDER BY id", (idea["id"],))]  # fmt: skip
    assert history[-1] == "checking"


def test_l_submit_send_a_retry_never_creates_two_ideas(world: dict[str, Any]) -> None:
    conn = world["conn"]
    _confirm(world)
    first = _submit(world, idempotency_key="key-0001-abcdef")
    again = _submit(world, idempotency_key="key-0001-abcdef")
    assert first == again  # A-API.conventions/3: the first result
    no_key = _submit(world)
    assert no_key[0] == 200 and no_key[1]["ref"] == first[1]["ref"]
    assert conn.execute("SELECT count(*) AS n FROM ideas WHERE idea_id IS NOT NULL").fetchone()["n"] == 1
    with pytest.raises(Refused) as err:  # the same key for another draft
        _submit(world, _draft(conn, "CTR-a1b2c3"), idempotency_key="key-0001-abcdef")
    assert err.value.code == "idempotency_key_reused"


def test_l_submit_pre_5_the_declaration_must_be_the_current_one(world: dict[str, Any]) -> None:
    _confirm(world)
    with pytest.raises(Refused) as err:
        send.submit(
            world["conn"], world["draft"], world["p"]["asha"], {"declaration_version": "old"}, now=NOW
        )
    assert err.value.code == "declaration_changed" and err.value.field == "declaration"


def test_l_submit_send_3_checked_and_matched_then_with_the_review_desk(world: dict[str, Any]) -> None:
    conn = world["conn"]
    _confirm(world)
    _submit(world)
    conn.execute(
        "UPDATE ideas SET summary = 'Investor 9876543210 calls the branch' WHERE id = %s", (world["draft"],)
    )
    check.run(conn, world["draft"])
    idea = _idea(world)
    assert idea["status"] == "with_review_desk"
    assert idea["summary"] == "Investor Phone ••••10 calls the branch"  # the final hidden-detail pass
    assert conn.execute(
        "SELECT kind, masked FROM hidden_details WHERE idea_uuid = %s", (world["draft"],)
    ).fetchone() == {"kind": "phone", "masked": "Phone ••••10"}
    again = send.handover(conn, idea, NOW + dt.timedelta(minutes=5))
    assert [(s["stage"], s["state"]) for s in again["stages"]][:3] == [
        ("shared", "done"), ("checked_matched", "done"), ("reviewed", "now"),
    ]  # fmt: skip
    assert again["stages"][1]["detail"] == "1 personal detail hidden, no similar ideas found"
    assert again["stages"][2]["detail"] == "By Friday 20 November"
    check.run(conn, world["draft"])  # a second run changes nothing
    assert _idea(world)["status"] == "with_review_desk"


def test_l_submit_send_4_decide_by_fires_on_lane_as_engine(world: dict[str, Any]) -> None:
    """BLD-A182 skips, quietly, a timer kind with no rule. decide_by has its rule, so the engine runs it: at its date
    it stops (a window, no breach; the desk lead's digest covers overdue ideas). The unknown kind beside it is the
    control: the engine skips that one."""
    from sla import engine

    conn = world["conn"]
    _confirm(world)
    _, h = _submit(world)
    conn.execute(
        "INSERT INTO sla_timers (entity_type, entity_id, stage, started_at, due_at) VALUES "
        "('idea', 'IDEA-2026-999999', 'no_such_kind', %s, %s)",
        (NOW, NOW + dt.timedelta(days=1)),
    )
    early = engine.tick(
        conn, NOW + dt.timedelta(hours=1)
    )  # before its date: handled, still running, not skipped
    assert early["skipped"] == 1 and early["expired"] == 0 and early["reminders"] == 0

    def state() -> str:
        row = conn.execute(
            "SELECT state FROM sla_timers WHERE entity_id = %s AND stage = 'decide_by'", (h["ref"],)
        )
        return str(row.fetchone()["state"])

    assert state() == "running"
    counts = engine.tick(
        conn, dt.datetime(2026, 11, 21, 0, 0, tzinfo=dt.UTC)
    )  # past Friday 20 November, 6 pm
    assert counts["expired"] == 1 and counts["skipped"] == 1 and counts["breaches"] == 0
    assert state() == "stopped"


def test_l_submit_withdraw_3_restore_restarts_the_clock_and_the_check(world: dict[str, Any]) -> None:
    """Lane C's part of lane E's restore (ON_RESTORED_HOOK): a new decide-by from now, one running timer, a check."""
    from submit import adapters

    conn = world["conn"]
    _confirm(world)
    _, h = _submit(world)
    check.run(conn, world["draft"])
    conn.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (world["draft"],))
    conn.execute("UPDATE ideas SET status = 'checking', restored_at = now() WHERE id = %s", (world["draft"],))
    adapters.on_restored(conn, world["draft"])
    running = conn.execute(
        "SELECT due_at FROM sla_timers WHERE entity_id = %s AND stage = 'decide_by' AND state = 'running'",
        (h["ref"],),
    ).fetchall()
    assert len(running) == 1 and running[0]["due_at"] == _idea(world)["decide_by"]
    assert _idea(world)["decide_by"] > dt.datetime(2026, 11, 20, 12, 30, tzinfo=dt.UTC)
    check.run(conn, world["draft"])
    assert _idea(world)["status"] == "with_review_desk"


# --- L-SUBMIT.edit ------------------------------------------------------------------------------------------------


def _shared(world: dict[str, Any]) -> str:
    _confirm(world)
    _, h = _submit(world)
    return str(h["ref"])


def test_s06b_the_edit_page_has_its_dates_and_the_sorting_note(world: dict[str, Any]) -> None:
    ref = _shared(world)
    page = edit.page(world["conn"], ref, world["p"]["asha"], now=NOW + dt.timedelta(hours=1))
    assert page["bar"]["title"] == f"Edit {ref}"
    assert page["bar"]["line"] == (
        "Shared Saturday 14 November. You can edit until the review desk opens it, at the latest Tuesday 17 November."
    )
    assert page["window"]["open"] is True and page["window"]["countdown"]["label"] == "3 days left"
    assert page["sorting"]["note"] == "Confirmed when you shared it. You can still change any of these."
    assert page["prompts"] == {
        "fix": "No fix added. Add one until Tuesday 17 November",
        "files": "Nothing attached. Add one until Tuesday 17 November",
    }
    assert [s["when"] for s in page["side"]] == [
        "Straight away", "At the latest Tuesday 17 November", "By Friday 20 November",
    ]  # fmt: skip
    assert page["declaration"]["text"].startswith("By saving, you confirm")
    assert page["versions"] == {"count": 1, "summary": "1 version. Sorting confirmed."}
    with pytest.raises(NotFound):
        edit.page(world["conn"], ref, world["p"]["neha"], now=NOW)


def test_l_submit_edit_4_each_save_is_a_version(world: dict[str, Any]) -> None:
    conn, asha = world["conn"], world["p"]["asha"]
    ref = _shared(world)
    later = NOW + dt.timedelta(hours=3)
    out = edit.save(
        conn,
        ref,
        asha,
        {
            "declaration_version": DECLARATION_VERSION,
            "title": "SMS rejection codes confuse investors",
            "sorting": {"area": "Operations"},
            "fix": {
                "how": "Print one plain sentence for each code on the SMS.",
                "worth": {"hours_month": "70 to 150"},
            },
        },
        now=later,
    )
    assert out["message"] == "Saved. The review desk will see the latest version."
    assert out["version"]["n"] == 2 and out["changed_fields"] == ["title", "sorting", "fix"]
    assert out["saved_label"] == "Saved at 1:05 pm"
    idea = _idea(world)
    assert idea["title"] == "SMS rejection codes confuse investors" and idea["area"] == "Operations"
    assert idea["kind"] == "fix"  # a problem shared with a fix shows as a Fix (E-ENUMS.kind)
    assert idea["sorting_sources"]["area"]["source"] == "changed"
    worth = conn.execute(
        "SELECT hours_low, hours_high FROM idea_worth WHERE idea_uuid = %s", (idea["id"],)
    ).fetchone()
    assert (float(worth["hours_low"]), float(worth["hours_high"])) == (70.0, 150.0)
    history = edit.versions(conn, ref, world["p"]["ravi"], now=later)  # the review desk sees what changed
    assert (
        history["count"] == 2 and history["summary"] == "2 versions. Title changed once, sorting confirmed."
    )
    assert history["items"][1]["before"]["title"] == "Rejection SMS codes confuse investors"
    assert history["items"][1]["after"]["sorting"]["area"] == "Operations"
    with pytest.raises(NotFound):
        edit.versions(conn, ref, world["p"]["neha"], now=later)  # a colleague does not
    audit = conn.execute(
        "SELECT after FROM audit_log WHERE action = 'idea.edit' AND entity = %s", (f"idea:{ref}",)
    ).fetchone()
    assert audit["after"] == {"version": 2, "fields": ["title", "sorting", "fix"]}


def test_l_submit_edit_3_a_customer_detail_in_an_edit_is_hidden(world: dict[str, Any]) -> None:
    conn = world["conn"]
    ref = _shared(world)
    edit.save(
        conn,
        ref,
        world["p"]["asha"],
        {
            "declaration_version": DECLARATION_VERSION,
            "summary": "Folio 1234567890 gets the SMS with only R07.",
        },
        now=NOW + dt.timedelta(hours=1),
    )
    assert _idea(world)["summary"] == "Folio Folio ••••90 gets the SMS with only R07."
    sealed = conn.execute(
        "SELECT owner_user_id FROM idea_words_sealed WHERE idea_uuid = %s AND source = 'edit'",
        (world["draft"],),
    ).fetchone()
    assert str(sealed["owner_user_id"]) == world["p"]["asha"]


def test_l_submit_edit_5_once_the_desk_opens_it_save_is_refused(world: dict[str, Any]) -> None:
    conn = world["conn"]
    ref = _shared(world)
    opened = NOW + dt.timedelta(days=1)
    conn.execute("UPDATE ideas SET opened_at = %s WHERE id = %s", (opened, world["draft"]))
    with pytest.raises(Refused) as err:
        edit.save(
            conn, ref, world["p"]["asha"], {"declaration_version": DECLARATION_VERSION, "title": "New"},
            now=opened + dt.timedelta(minutes=1),
        )  # fmt: skip
    assert err.value.code == "edit_window_closed"
    assert err.value.message.startswith("The review desk has just opened it, so it can’t be changed now.")
    assert dt.datetime.fromisoformat(err.value.extra["opened_by_desk_at"]) == opened
    page = edit.page(conn, ref, world["p"]["asha"], now=opened)
    assert page["window"]["open"] is False
    assert page["window"]["line"].startswith("The review desk opened it on Sunday 15 November")


def test_l_submit_edit_1_after_three_days_save_is_refused(world: dict[str, Any]) -> None:
    ref = _shared(world)
    with pytest.raises(Refused) as err:
        edit.save(
            world["conn"], ref, world["p"]["asha"], {"declaration_version": DECLARATION_VERSION, "title": "New"},
            now=NOW + dt.timedelta(days=3, minutes=1),
        )  # fmt: skip
    assert err.value.code == "edit_window_closed"


def test_l_sort_rules_5_sorting_changes_in_the_edit_window_need_every_field(world: dict[str, Any]) -> None:
    ref = _shared(world)
    with pytest.raises(Refused) as err:
        edit.save(
            world["conn"], ref, world["p"]["asha"],
            {"declaration_version": DECLARATION_VERSION, "sorting": {"brings": []}}, now=NOW + dt.timedelta(hours=1),
        )  # fmt: skip
    assert err.value.code == "sorting_incomplete"


def test_l_submit_keys_never_reach_sql_unless_well_formed() -> None:
    """A key that is neither a row id nor a reference never reaches SQL."""
    from submit.own import find

    assert find(None, "x' OR 1=1 --") is None  # type: ignore[arg-type]
    assert find(None, str(uuid.uuid4()).upper()) is None  # type: ignore[arg-type]
