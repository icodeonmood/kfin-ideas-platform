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
from submit import check, edit, fix, helpers, ready, routing, send, sorting
from submit.config import DECLARATION_VERSION
from submit.errors import NotFound, Refused

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
NOW = dt.datetime(2026, 11, 14, 4, 35, tzinfo=dt.UTC)  # Saturday 14 November, 10:05 am in the office
REF = re.compile(r"^IDEA-2026-[0-9]{6}$")


@pytest.fixture
def world(db: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """A sharer with a ready draft whose parts suggest the sorting, a reviewer, and a colleague: people, codes and
    ideas of this test's own (crunch rule 14, BLD-C087), so it reads and removes only what it made."""
    monkeypatch.setenv("COMPANY_REPO_PATH", str(SEED))
    get_settings.cache_clear()
    # Submit queues jobs (submit.check, voice.purge); the conftest does not empty `jobs`, so this test takes its own
    # away again, or a later test's `run_one` would claim them first.
    last_job = int(db.execute("SELECT coalesce(max(id), 0) AS n FROM jobs").fetchone()["n"])
    run = uuid.uuid4().hex[:8]
    people: dict[str, str] = {}
    codes: dict[str, str] = {}
    for key, name in (("asha", "Asha Verma"), ("ravi", "Ravi Desai"), ("neha", "Neha Kulkarni")):
        code = f"CTR-{uuid.uuid4().hex[:6]}"
        row = db.execute(
            "INSERT INTO users (emp_id_hash, name, email, location, first_name) VALUES (%s, %s, %s, 'Hyderabad', %s) "
            "RETURNING id",
            (f"test-{key}-{run}", name, f"{key}.{run}@kfintech.example", name.split()[0]),
        ).fetchone()
        people[key] = str(row["id"])
        codes[key] = code
        db.execute(
            "INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, row["id"])
        )
    db.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'reviewer')", (people["ravi"],))
    draft = _draft(db, codes["asha"])
    yield {"conn": db, "p": people, "c": codes, "draft": draft}
    # Clean up everything this test made except audit_log, whose trigger refuses DELETE (crunch rule 14): its jobs
    # and timers, the vault's values and counters under its ideas' hide scopes, its ideas (their parts, files,
    # hidden details, sealed words, versions, crew and history go with them) and its people (their grants, codes
    # and idempotency keys go with them).
    ideas = [
        str(r["id"])
        for r in db.execute("SELECT id FROM ideas WHERE contributor_code = ANY(%s)", (list(codes.values()),))
    ]
    scopes = [f"DRAFT-{u}" for u in ideas]
    db.execute("DELETE FROM jobs WHERE id > %s", (last_job,))
    db.execute(
        "DELETE FROM sla_timers WHERE entity_type = 'idea' AND (entity_id = 'IDEA-2026-999999' OR entity_id IN "
        "(SELECT idea_id FROM ideas WHERE id = ANY(%s::uuid[]) AND idea_id IS NOT NULL))",
        (ideas,),
    )
    db.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (scopes,))
    db.execute("DELETE FROM vault_counters WHERE scope_id = ANY(%s)", (scopes,))
    db.execute("DELETE FROM ideas WHERE id = ANY(%s::uuid[])", (ideas,))
    db.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", (list(people.values()),))
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
        "file_state) VALUES (%s, %s, 'screenshot.png', %s, 'image/png', 1000, %s, %s, 'file', %s)",
        (att, world["draft"], f"quarantine/{att}", "0" * 64, world["c"]["asha"], file_state),
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
    other = _draft(conn, world["c"]["neha"])
    conn.execute(
        "UPDATE ideas SET status = 'with_review_desk', idea_id = next_idea_ref(%s) WHERE id = %s",
        (NOW, other),
    )
    conn.execute(
        "INSERT INTO merge_requests (draft_uuid, other_idea_uuid, from_code, note_encrypted) VALUES (%s, %s, %s, %s)",
        (world["draft"], other, world["c"]["asha"], b"\x00"),
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
    assert dict(lead) == {"contributor_code": world["c"]["asha"], "role": "lead", "via": "shared"}
    jobs = {
        r["type"]
        for r in conn.execute("SELECT type FROM jobs WHERE payload->>'idea_uuid' = %s", (str(idea["id"]),))
    }
    assert {"submit.check", "voice.purge"} <= jobs
    audit = conn.execute(  # this test's own row: audit_log keeps every earlier run's
        "SELECT actor, after FROM audit_log WHERE action = 'idea.submit' AND entity = %s AND actor = %s "
        "ORDER BY id DESC LIMIT 1",
        (f"idea:{h['ref']}", f"user:{world['p']['asha']}"),
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
    shared = conn.execute(
        "SELECT count(*) AS n FROM ideas WHERE idea_id IS NOT NULL AND contributor_code = %s",
        (world["c"]["asha"],),
    )
    assert shared.fetchone()["n"] == 1
    with pytest.raises(Refused) as err:  # the same key for another draft
        _submit(world, _draft(conn, world["c"]["asha"]), idempotency_key="key-0001-abcdef")
    assert err.value.code == "idempotency_key_reused"


def test_l_submit_send_a_repeat_on_a_sent_draft_keeps_its_answer_for_the_key(world: dict[str, Any]) -> None:
    """A-API.conventions/3 on the already-shared path too (BLD-C087): the hand-over is stored for the key."""
    conn, asha = world["conn"], world["p"]["asha"]
    _confirm(world)
    first = _submit(world)
    again = _submit(world, idempotency_key="key-0002-abcdef")
    assert again[0] == 200 and again[1]["ref"] == first[1]["ref"]
    kept = conn.execute(
        "SELECT status, response_json FROM idempotency_keys WHERE user_id = %s AND key = 'key-0002-abcdef'",
        (asha,),
    ).fetchone()
    assert kept["status"] == 200 and kept["response_json"]["ref"] == first[1]["ref"]
    assert kept["response_json"]["_status"] == 200
    assert _submit(world, idempotency_key="key-0002-abcdef") == again


def test_l_submit_send_queues_listen_with_the_send(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """c/sarvam's `speech.listen.enqueue_prefetch(conn, idea_uuid)` once, inside the send (BLD-C087)."""
    import types

    from submit import adapters

    real = adapters._module
    seen: list[str] = []
    fake = types.SimpleNamespace(enqueue_prefetch=lambda conn, idea_uuid: seen.append(idea_uuid))
    monkeypatch.setattr(adapters, "_module", lambda name: fake if name == "speech.listen" else real(name))
    _confirm(world)
    assert _submit(world)[0] == 201 and seen == [world["draft"]]
    assert _submit(world)[0] == 200 and seen == [world["draft"]]  # a repeat sends nothing again


def test_l_submit_send_the_hide_scope_outlives_the_send(world: dict[str, Any]) -> None:
    """BLD-C087: a PAN hidden in the draft keeps its vault scope `DRAFT-<idea uuid>` through Submit, Checked and
    matched and an edit. Submit never purges or re-keys it, so the sent idea's hidden detail still resolves to its
    value for the sharer, and the same PAN typed again gets the same tag."""
    from onepc.context import open_text
    from pii import vault

    conn, asha, uid = world["conn"], world["p"]["asha"], world["draft"]
    pan = "ABCPE1234F"  # a made-up PAN
    scope = f"DRAFT-{uid}"
    tag = vault.assign(conn, scope, "PAN", pan)  # as Tell it hides it in the draft's message (L-HIDE)
    conn.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked, vault_tag) "
        "VALUES (%s, 'message', 'msg-1', 18, 28, 'pan', 'PAN ••••4F', %s)",
        (uid, tag),
    )
    _confirm(world)
    _, h = _submit(world)
    conn.execute("UPDATE ideas SET often = %s WHERE id = %s", (f"Each time PAN {pan} calls", uid))
    check.run(conn, uid)  # the final pass hides it in the shared text, in the same scope
    later = NOW + dt.timedelta(hours=1)
    edit.save(
        conn, h["ref"], asha, {"declaration_version": DECLARATION_VERSION, "summary": f"PAN {pan} gets only R07."},
        now=later,
    )  # fmt: skip
    idea = _idea(world)
    assert idea["idea_id"] == h["ref"] and idea["status"] == "with_review_desk"
    assert pan not in idea["summary"] and pan not in (idea["often"] or "")
    assert vault.mapping(conn, scope) == {tag: ("PAN", pan)}  # still there, under the same tag
    moved = conn.execute("SELECT 1 FROM pseudonym_vault WHERE scope_id = %s", (h["ref"],)).fetchone()
    assert moved is None  # not re-keyed to a scope of the reference
    tags = {
        r["vault_tag"]
        for r in conn.execute(
            "SELECT vault_tag FROM hidden_details WHERE idea_uuid = %s AND kind = 'pan'", (uid,)
        )
    }
    assert tags == {tag}
    page = edit.page(conn, h["ref"], asha, now=later)  # the sharer's view of the sent idea
    assert "PAN ••••4F" in [d["masked"] for d in page["hidden"]]
    sealed = conn.execute(
        "SELECT source_id, owner_user_id, text_encrypted FROM idea_words_sealed WHERE idea_uuid = %s AND "
        "source = 'edit' AND source_id = %s",
        (uid, f"{uid}:1:summary"),
    ).fetchone()
    assert str(sealed["owner_user_id"]) == asha
    words = open_text(
        "idea_words_sealed",
        "text_encrypted",
        f"edit:{sealed['source_id']}",
        sealed["text_encrypted"],
        vault=True,
    )
    assert words == f"PAN {pan} gets only R07."


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
    # Matching is not on main here, so it could not be checked: never "no similar ideas found" (BLD-C087)
    assert idea["similar_check"] == "failed"
    assert again["stages"][1]["detail"] == (
        "1 personal detail hidden. Couldn’t check for similar ideas. The review desk will."
    )
    assert again["stages"][2]["detail"] == "By Friday 20 November"
    check.run(conn, world["draft"])  # a second run changes nothing
    assert _idea(world)["status"] == "with_review_desk"


def test_l_submit_send_4_decide_by_fires_on_lane_as_engine(world: dict[str, Any]) -> None:
    """BLD-A182 skips, quietly, a timer kind with no rule. decide_by has its rule, so the engine runs it: at its date
    it stops (a window, no breach; lane B's desk flags it overdue from ideas.decide_by, and no digest is sent). The unknown kind beside it is the
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
    audit = conn.execute(  # this test's own row, the newest: audit_log keeps every earlier run's
        "SELECT after FROM audit_log WHERE action = 'idea.edit' AND entity = %s AND actor = %s ORDER BY id DESC",
        (f"idea:{ref}", f"user:{asha}"),
    ).fetchone()
    assert audit["after"] == {"version": 2, "fields": ["title", "sorting", "fix"]}


def test_l_submit_edit_4_files_the_edit_page_added_or_removed_are_a_version(world: dict[str, Any]) -> None:
    """S-06B, BLD-C161 (review of c/s06b): files and links act at once; Save records the ones the page added or
    removed, so a save that changed only files makes a version and never reads "Nothing has changed.". IDs that do
    not hold up (not on this idea, or still there) count for nothing, and the version keeps IDs only."""
    from attachments import files as F

    conn, asha = world["conn"], world["p"]["asha"]
    ref = _shared(world)
    later = NOW + dt.timedelta(hours=2)
    kept = F.accept_link(conn, user_id=asha, url="https://intranet.kfintech.example/codes", idea_id=ref)
    gone = F.accept_link(conn, user_id=asha, url="https://intranet.kfintech.example/calls", idea_id=ref)
    F.remove(conn, gone["id"], asha)
    out = edit.save(
        conn,
        ref,
        asha,
        {
            "declaration_version": DECLARATION_VERSION,
            "files": {"added": [kept["id"], "ATT-2026-999999"], "removed": [gone["id"], "ATT-2026-999998"]},
        },
        now=later,
    )
    assert out["message"] == "Saved. The review desk will see the latest version."
    assert out["version"]["n"] == 2 and out["changed_fields"] == ["files"]
    history = edit.versions(conn, ref, world["p"]["ravi"], now=later)
    assert history["items"][1]["label"] == "Changed: files"
    assert history["items"][1]["after"] == {"files": {"added": [kept["id"]]}}
    assert history["items"][1]["before"] == {"files": {"removed": [gone["id"]]}}
    again = edit.save(
        conn,
        ref,
        asha,
        {"declaration_version": DECLARATION_VERSION, "files": {"added": [], "removed": [kept["id"]]}},
        now=later,
    )
    assert again["version"] is None and again["message"] == "Nothing has changed."
    with pytest.raises(Refused) as err:
        edit.save(
            conn,
            ref,
            asha,
            {"declaration_version": DECLARATION_VERSION, "files": {"added": ["x"]}},
            now=later,
        )
    assert err.value.field == "files"


def test_l_submit_edit_4_only_a_live_grant_reads_the_history(world: dict[str, Any]) -> None:
    """BLD-C087: a grant that has ended, or not started, reads nothing; the Ones Committee's does."""
    conn, p = world["conn"], world["p"]
    ref = _shared(world)
    conn.execute(
        "INSERT INTO role_grants (user_id, role, valid_from, valid_to) VALUES "
        "(%s, 'reviewer', now() - interval '2 days', now() - interval '1 day'), "
        "(%s, 'committee', now() + interval '1 day', NULL)",
        (p["neha"], p["neha"]),
    )
    with pytest.raises(NotFound):
        edit.versions(conn, ref, p["neha"], now=NOW)
    conn.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'core_committee')", (p["neha"],))
    assert edit.versions(conn, ref, p["neha"], now=NOW)["count"] == 1


def test_l_submit_withdraw_2_a_withdrawn_ideas_history_is_its_sharers_alone(world: dict[str, Any]) -> None:
    """L-SUBMIT.withdraw/2 and BLD-E011: once withdrawn, the review desk and the Ones Committee no longer find its
    draft history; the sharer still does."""
    conn, p = world["conn"], world["p"]
    ref = _shared(world)
    conn.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, 'committee')", (p["neha"],))
    check.run(conn, world["draft"])
    assert edit.versions(conn, ref, p["ravi"], now=NOW)["count"] == 1
    assert edit.versions(conn, ref, p["neha"], now=NOW)["count"] == 1
    conn.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (world["draft"],))
    for viewer in ("ravi", "neha"):
        with pytest.raises(NotFound):
            edit.versions(conn, ref, p[viewer], now=NOW)
    history = edit.versions(conn, ref, p["asha"], now=NOW)
    assert history["count"] == 1 and history["items"][0]["label"] == "As shared"


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
    # The folio is masked. Since L-HIDE (c/hide) is on main, a name-like word in the same sentence may be hidden too
    # (L-HIDE.detect/4), so only the folio's part of the line is pinned here.
    summary = _idea(world)["summary"]
    assert summary.startswith("Folio Folio ••••90 gets the SMS with only ")
    assert "1234567890" not in summary
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


# --- S-05.fix, A-API.drafts `PUT|DELETE /drafts/:id/fix` and `PUT /drafts/:id/helpers` -----------------------------


def test_a_api_drafts_fix_put_reads_amounts_hides_details_and_counts_ready(world: dict[str, Any]) -> None:
    """S-05.fix: "Add my fix" with figures in any Indian form → `Fix` with `ready_count` and `Range.text`, "about"
    kept before a single figure (BLD-C140, Review.md "about ₹25,000 a month saved"); a PAN in the words is hidden
    like any part, and saving again replaces what was hidden from that answer."""
    conn, asha, draft = world["conn"], world["p"]["asha"], world["draft"]
    body = {
        "how": "Send the reason in plain words in the SMS, as for PAN ABCPE1234F.",  # a made-up PAN
        "solved_already": "partly",
        "worth": {"hours_month": "70 to 150", "cost_month": "about 25k"},
    }
    out = fix.put_draft(conn, draft, asha, body, now=NOW)
    assert out["how"] == "Send the reason in plain words in the SMS, as for PAN PAN ••••4F."
    assert out["worth"] == {
        "hours_month": {"low": 70.0, "high": 150.0, "text": "70 to 150 hours a month"},
        "cost_month": {"low": 25000.0, "text": "about ₹25,000 a month"},
    }
    assert out["ready_count"] == 3 and out["included"] is True
    assert out["readiness"] == "3 of 5 ready for the review desk"
    assert out["next"] == {"key": "basis", "line": "Most useful next: what that is based on."}
    assert out["part"] == {
        "rail": "Added",
        "line": "Included, 3 of 5 ready",
        "fix_line": "Send the reason in plain words in the SMS, as for PAN PAN ••••4F.",
        "size_line": "70 to 150 hours a month, about ₹25,000 a month saved, solved elsewhere: partly",
    }
    flags = conn.execute(
        "SELECT hours_about, cost_about, revenue_about FROM idea_worth WHERE idea_uuid = %s AND by_side = 'sharer'",
        (draft,),
    ).fetchone()
    assert (flags["hours_about"], flags["cost_about"], flags["revenue_about"]) == (False, True, None)
    hid = conn.execute(
        "SELECT kind, masked FROM hidden_details WHERE idea_uuid = %s AND source = 'edit'", (draft,)
    ).fetchall()
    assert [(h["kind"], h["masked"]) for h in hid] == [("pan", "PAN ••••4F")]
    view = ready.send_view(conn, draft, asha, now=NOW)
    assert view["button"] == "Submit with my fix"
    assert {r["key"]: r["value"] for r in view["rows"]}["fix"] == out["part"]["fix_line"]
    again = fix.put_draft(
        conn,
        draft,
        asha,
        {**body, "how": "Send the reason in plain words in the SMS.", "basis": "report"},
        now=NOW,
    )
    assert again["ready_count"] == 4
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s AND source = 'edit'", (draft,)
        ).fetchone()["n"]
        == 0
    )  # the PAN left the words, so its hidden detail went too
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM idea_worth WHERE idea_uuid = %s AND by_side = 'sharer'", (draft,)
        ).fetchone()["n"]
        == 1
    )  # a draft's figures are replaced: nobody else has seen them
    audit = conn.execute(
        "SELECT after FROM audit_log WHERE action = 'idea.fix' AND actor = %s ORDER BY id DESC",
        (f"user:{asha}",),
    ).fetchone()
    assert audit["after"] == {"included": True, "ready_count": 4}  # counts only, never the words


def test_v_fields_checkit_8_9_the_fix_sheets_messages(world: dict[str, Any]) -> None:
    conn, asha, draft = world["conn"], world["p"]["asha"], world["draft"]
    with pytest.raises(Refused) as err:
        fix.put_draft(conn, draft, asha, {"needs": "A template change"}, now=NOW)
    assert err.value.body()["error"] == {
        "code": "fix_how_needed",
        "message": "Say how you’d solve it, or close this to send without a fix.",
        "field": "how",
    }
    with pytest.raises(Refused) as err:
        fix.put_draft(
            conn,
            draft,
            asha,
            {"how": "Send the reason in plain words.", "worth": {"cost_month": "a lot"}},
            now=NOW,
        )
    assert (err.value.code, err.value.field) == ("worth_unclear", "worth.cost_month")
    assert conn.execute("SELECT 1 FROM idea_fix WHERE idea_uuid = %s", (draft,)).fetchone() is None


def test_s05_fix_close_and_keep_then_remove(world: dict[str, Any]) -> None:
    """ "Close, and keep what you wrote" keeps a started fix that is not included and holds nothing; "Remove" takes the
    fix, its figures and what was hidden from its words away."""
    conn, asha, draft = world["conn"], world["p"]["asha"], world["draft"]
    started = fix.put_draft(
        conn, draft, asha, {"included": False, "needs": "Folio 1234567890 shows it", "worth": {"hours_month": "70"}},
        now=NOW,
    )  # fmt: skip
    assert started["included"] is False and started["ready_count"] == 2
    assert started["part"] == {
        "rail": "Optional",
        "line": "You started a fix. It isn’t included yet.",
        "action": "Carry on with your fix",
    }
    _confirm(world)
    view = ready.send_view(conn, draft, asha, now=NOW)
    assert view["button"] == "Submit" and view["ready"] is True  # a fix never holds Submit (L-SUBMIT.pre/6)
    assert fix.delete_draft(conn, draft, asha, now=NOW) == {"fix": None, "part": {"rail": "Optional"}}
    gone = conn.execute(
        "SELECT (SELECT count(*) FROM idea_fix WHERE idea_uuid = %s) + (SELECT count(*) FROM idea_worth WHERE "
        "idea_uuid = %s) AS n",
        (draft, draft),
    ).fetchone()
    assert gone["n"] == 0
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s AND source = 'edit'", (draft,)
        ).fetchone()["n"]
        == 0
    )
    assert fix.delete_draft(conn, draft, asha, now=NOW)["fix"] is None  # removing twice is fine


def test_a_api_drafts_fix_and_helpers_are_the_owners_and_only_on_a_draft(world: dict[str, Any]) -> None:
    conn, draft = world["conn"], world["draft"]
    with pytest.raises(NotFound):
        fix.put_draft(conn, draft, world["p"]["neha"], {"how": "Send the reason in plain words."}, now=NOW)
    with pytest.raises(NotFound):
        helpers.put_draft(conn, draft, world["p"]["neha"], {"picks": []}, now=NOW)
    ref = _shared(world)
    asha = world["p"]["asha"]
    with pytest.raises(Refused) as err:
        fix.put_draft(conn, ref, asha, {"how": "Send the reason in plain words."}, now=NOW)
    assert err.value.code == "not_a_draft"  # a shared idea changes from its edit page
    with pytest.raises(Refused) as err:
        fix.delete_draft(conn, ref, asha, now=NOW)
    assert err.value.code == "not_a_draft"
    with pytest.raises(Refused) as err:
        helpers.put_draft(conn, ref, asha, {"picks": []}, now=NOW)
    assert err.value.code == "not_a_draft"


def test_a_api_drafts_helpers_put_picks_and_hidden_own_words(world: dict[str, Any]) -> None:
    """S-05 part 6: picks from the list and the person's own words, masked like any part; the Send part's row."""
    conn, asha, draft = world["conn"], world["p"]["asha"], world["draft"]
    out = helpers.put_draft(
        conn, draft, asha, {"picks": ["someone at a branch", "Data or reports"], "text": "whoever has 9876543210"},
        now=NOW,
    )  # fmt: skip
    assert out["picks"] == ["Someone at a branch", "Data or reports"]
    assert out["text"] == "whoever has Phone ••••10"
    assert out["line"] == "Someone at a branch, Data or reports and whoever has Phone ••••10"
    assert out["part"] == {"rail": "Added"}
    idea = _idea(world)
    assert idea["helper_picks"] == ["Someone at a branch", "Data or reports"]
    assert idea["helper_text"] == "whoever has Phone ••••10"
    rows = {r["key"]: r["value"] for r in ready.send_view(conn, draft, asha, now=NOW)["rows"]}
    assert rows["helpers"] == out["line"]
    cleared = helpers.put_draft(conn, draft, asha, {"picks": []}, now=NOW)
    assert cleared["line"] == "Not said" and cleared["part"] == {"rail": "Optional"}
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s AND source = 'edit'", (draft,)
        ).fetchone()["n"]
        == 0
    )


def test_l_submit_edit_fix_and_helpers_save_as_a_version_with_range_text(world: dict[str, Any]) -> None:
    """J-RECOVER/15, A-API `PATCH /ideas/:id`: the fix and who would help are saved from the edit page; figures read
    back normalised; the same answers again make no new version."""
    conn, asha = world["conn"], world["p"]["asha"]
    ref = _shared(world)
    later = NOW + dt.timedelta(hours=1)
    body = {
        "declaration_version": DECLARATION_VERSION,
        "fix": {"how": "Send the reason in plain words in the SMS.", "worth": {"cost_month": "2L"}},
        "helpers": {"picks": ["Someone from tech"]},
    }
    out = edit.save(conn, ref, asha, body, now=later)
    assert out["changed_fields"] == ["fix", "helpers"] and out["version"]["n"] == 2
    page = edit.page(conn, ref, asha, now=later)
    assert page["fix"]["worth"] == {"cost_month": {"low": 200000.0, "text": "₹2,00,000 a month"}}
    assert page["fix"]["part"]["size_line"] == "₹2,00,000 a month saved"
    assert page["helpers"]["line"] == "Someone from tech"
    assert edit.save(conn, ref, asha, body, now=later)["version"] is None  # nothing changed, no version
    with pytest.raises(Refused) as err:
        edit.save(
            conn, ref, asha, {**body, "fix": {"how": "Send it.", "worth": {"cost_month": "lots"}}}, now=later
        )
    assert err.value.field == "fix.how"


def _hide_rows(conn: Any, uid: str) -> dict[str, Any]:
    """What hide holds for an idea: its hidden details and the sealed words, each row as it is stored."""
    hidden = conn.execute(
        "SELECT id, source, source_id, kind, masked FROM hidden_details WHERE idea_uuid = %s ORDER BY id",
        (uid,),
    ).fetchall()
    sealed = conn.execute(
        "SELECT id, source_id, text_encrypted FROM idea_words_sealed WHERE idea_uuid = %s ORDER BY id", (uid,)
    ).fetchall()
    return {"hidden": [dict(r) for r in hidden], "sealed": [dict(r) for r in sealed]}


def test_l_submit_edit_3_an_unchanged_save_hides_nothing_again(world: dict[str, Any]) -> None:
    """BLD-C141, J-RECOVER edit step: words sent back exactly as their stored masked copies (the summary, the fix and
    who would help, as the edit page gave them) are not masked again, so a repeat Save adds no hidden-detail or
    sealed rows, no figures and no version."""
    conn, asha, uid = world["conn"], world["p"]["asha"], world["draft"]
    ref = _shared(world)
    later = NOW + dt.timedelta(hours=1)
    first = edit.save(
        conn,
        ref,
        asha,
        {
            "declaration_version": DECLARATION_VERSION,
            "summary": "Folio 1234567890 gets the SMS with only R07.",  # a made-up folio
            "fix": {
                "how": "Send the reason in plain words in the SMS, as for PAN ABCPE1234F.",  # a made-up PAN
                "worth": {"cost_month": "about 25k"},
            },
            "helpers": {"picks": ["Someone from tech"], "text": "whoever has 9876543210"},  # a made-up phone
        },
        now=later,
    )
    assert first["changed_fields"] == ["summary", "fix", "helpers"]
    before = _hide_rows(conn, uid)
    kinds = {r["kind"] for r in before["hidden"]}
    assert {"folio", "pan", "phone"} <= kinds and len(before["sealed"]) >= 3
    worth_rows = conn.execute("SELECT count(*) AS n FROM idea_worth WHERE idea_uuid = %s", (uid,)).fetchone()[
        "n"
    ]
    idea = _idea(world)
    page = edit.page(conn, ref, asha, now=later)
    assert "1234567890" not in idea["summary"] and "9876543210" not in idea["helper_text"]
    assert "ABCPE1234F" not in page["fix"]["how"]
    again = edit.save(
        conn,
        ref,
        asha,
        {
            "declaration_version": DECLARATION_VERSION,
            "summary": idea["summary"],
            "fix": {"how": page["fix"]["how"], "worth": page["fix"]["worth"]},
            "helpers": {"picks": list(idea["helper_picks"]), "text": idea["helper_text"]},
        },
        now=later + dt.timedelta(minutes=5),
    )
    assert again["version"] is None and again["changed_fields"] == []
    assert _hide_rows(conn, uid) == before
    assert (
        conn.execute("SELECT count(*) AS n FROM idea_worth WHERE idea_uuid = %s", (uid,)).fetchone()["n"]
        == worth_rows
    )  # "about ₹25,000 a month" reads back the same, so no new figures row (BLD-C140)


def test_s05_fix_and_helpers_sent_back_masked_keep_what_was_hidden(world: dict[str, Any]) -> None:
    """BLD-C141 on a draft (one source id per answer): the fix sheet or who would help sent again with the masked copy
    it got back keeps the hidden detail and the sealed words as they were, instead of hiding nothing from the masked
    copy and dropping them."""
    conn, asha, draft = world["conn"], world["p"]["asha"], world["draft"]
    out = fix.put_draft(
        conn,
        draft,
        asha,
        {"how": "Send the reason in plain words in the SMS, as for PAN ABCPE1234F."},
        now=NOW,
    )
    said = helpers.put_draft(
        conn, draft, asha, {"picks": ["Data or reports"], "text": "whoever has 9876543210"}, now=NOW
    )
    before = _hide_rows(conn, draft)
    assert {r["kind"] for r in before["hidden"]} >= {"pan", "phone"}
    fix.put_draft(conn, draft, asha, {"how": out["how"], "basis": "report"}, now=NOW)
    again = helpers.put_draft(
        conn, draft, asha, {"picks": ["Data or reports", "Someone from tech"], "text": said["text"]}, now=NOW
    )
    assert again["text"] == "whoever has Phone ••••10"
    assert _hide_rows(conn, draft) == before


def test_l_submit_edit_fix_figures_cleared_then_added_again(world: dict[str, Any]) -> None:
    """J-RECOVER edit step, L-WORTH/7 (`replace_worth=False`): clearing every figure adds an all-empty sharer row, so
    the fix counts no size and its size line drops the figures; adding figures again counts and reads them. Each
    earlier row stays."""
    conn, asha, uid = world["conn"], world["p"]["asha"], world["draft"]
    ref = _shared(world)
    later = NOW + dt.timedelta(hours=1)
    how = "Send the reason in plain words in the SMS."

    def save(worth: dict[str, Any], minutes: int) -> dict[str, Any]:
        body = {
            "declaration_version": DECLARATION_VERSION,
            "fix": {"how": how, "solved_already": "partly", "worth": worth},
        }
        return edit.save(conn, ref, asha, body, now=later + dt.timedelta(minutes=minutes))

    def shown() -> dict[str, Any]:
        part = edit.page(conn, ref, asha, now=later)["fix"]
        assert part is not None
        return dict(part)

    def sharer_rows() -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT hours_low, cost_low, cost_about, revenue_low, outside_tools FROM idea_worth "
                "WHERE idea_uuid = %s AND by_side = 'sharer' ORDER BY id",
                (uid,),
            ).fetchall()
        ]

    assert save({"hours_month": "70 to 150", "cost_month": "about 25k"}, 0)["changed_fields"] == ["fix"]
    part = shown()
    assert part["ready_count"] == 3 and part["readiness"] == "3 of 5 ready for the review desk"
    assert part["part"]["size_line"] == (
        "70 to 150 hours a month, about ₹25,000 a month saved, solved elsewhere: partly"
    )

    cleared = save({"hours_month": "", "cost_month": ""}, 1)
    assert cleared["changed_fields"] == ["fix"] and cleared["version"]["n"] == 3
    part = shown()
    assert "worth" not in part
    assert part["ready_count"] == 2 and part["part"]["line"] == "Included, 2 of 5 ready"
    assert part["next"] == {"key": "worth", "line": "Most useful next: a rough size. A range is fine."}
    assert part["part"]["size_line"] == "solved elsewhere: partly"
    rows = sharer_rows()
    assert len(rows) == 2 and all(
        v is None for v in rows[-1].values()
    )  # the earlier figures stay (L-WORTH/7)

    added = save({"cost_month": "2L"}, 2)
    assert added["changed_fields"] == ["fix"] and added["version"]["n"] == 4
    part = shown()
    assert part["worth"] == {"cost_month": {"low": 200000.0, "text": "₹2,00,000 a month"}}
    assert part["ready_count"] == 3 and part["next"] == {
        "key": "basis",
        "line": "Most useful next: what that is based on.",
    }
    assert part["part"]["size_line"] == "₹2,00,000 a month saved, solved elsewhere: partly"
    assert len(sharer_rows()) == 3
    assert save({"cost_month": "2L"}, 3)["version"] is None  # the same figures again: no row, no version
    assert len(sharer_rows()) == 3


# --- BLD-C087 verification fixes ------------------------------------------------------------------------------------


def test_l_similar_failure_the_send_part_says_couldnt_check(world: dict[str, Any]) -> None:
    """A draft whose similar part failed reads "Couldn't check …", not "Nobody has raised this yet"."""
    conn, draft = world["conn"], world["draft"]
    conn.execute(
        "INSERT INTO idea_parts (idea_uuid, key, state, value) VALUES (%s, 'similar', 'failed', NULL)",
        (draft,),
    )
    rows = {r["key"]: r for r in ready.send_view(conn, draft, world["p"]["asha"], now=NOW)["rows"]}
    assert rows["similar"]["value"] == "Couldn’t check for similar ideas. The review desk will."
    assert rows["similar"]["ok"] is True  # it never holds the send (L-SIMILAR.failure)


def test_l_similar_failure_a_check_that_matched_reads_its_count(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from submit import adapters

    monkeypatch.setattr(adapters, "find_similar", lambda conn, idea_uuid, *, found_while: 0)
    _confirm(world)
    _submit(world)
    check.run(world["conn"], world["draft"])
    idea = _idea(world)
    assert idea["similar_check"] == "done"
    detail = send.handover(world["conn"], idea, NOW + dt.timedelta(minutes=5))["stages"][1]["detail"]
    assert detail == "No personal details found, no similar ideas found"


def test_l_submit_send_a_listen_prefetch_failure_never_fails_a_send(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import types

    from submit import adapters

    real = adapters._module

    def boom(conn: Any, idea_uuid: str) -> None:
        conn.execute("INSERT INTO jobs (type, payload) VALUES ('listen.prefetch', '{\"probe\": true}')")
        raise RuntimeError("speech service down")

    fake = types.SimpleNamespace(enqueue_prefetch=boom)
    monkeypatch.setattr(adapters, "_module", lambda name: fake if name == "speech.listen" else real(name))
    _confirm(world)
    status, out = _submit(world)
    assert status == 201 and REF.match(out["ref"])
    assert _idea(world)["status"] == "checking"
    assert (
        world["conn"]
        .execute("SELECT count(*) AS n FROM jobs WHERE type = 'listen.prefetch' AND payload ? 'probe'")
        .fetchone()["n"]
        == 0
    )  # the savepoint undid what the failed prefetch wrote
