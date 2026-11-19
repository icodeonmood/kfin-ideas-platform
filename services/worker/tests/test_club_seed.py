"""The 1% Club synthetic seed (BLD-E006, bootstrap/club_seed.py) against a freshly migrated database: it fills every
table a screen of the pack reads (E-ENTITIES), with no one from the pack's demo cast (P-PRODUCT.cast), masked
words everywhere but the sharer's sealed copy (DEC-103), and it removes cleanly so `--reset` can load it again."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterator
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from bootstrap import club_seed
from core import killswitch
from identity.codes import emp_id_hash
from onepc import enums
from onepc.context import open_text

IST = ZoneInfo("Asia/Kolkata")

PACK_CAST = {
    "Kavya Menon", "Meera Iyer", "Ravi Nair", "Sanjay Pillai", "Rohan Mehta", "Arjun Rao", "Rohit Menon",
    "Ananya Rao", "Sneha Kulkarni", "Arjun Nair", "Priya Iyer", "Farhan Nair", "Deepa",
}  # fmt: skip


def _one(conn: Any, sql: str, *args: Any) -> Any:
    row = conn.execute(sql, args).fetchone()
    return None if row is None else next(iter(row.values()))


def _set(conn: Any, sql: str) -> set[Any]:
    return {next(iter(r.values())) for r in conn.execute(sql).fetchall()}


@pytest.fixture
def made(db: Any) -> Iterator[dict[str, club_seed.Made]]:
    """The seed with each idea's row by key, loaded for one test and removed after it, so no rows outlive the test
    (rule 14). The base's `seeded` fixture yields the connection, so this one has its own name."""
    m = club_seed.load(db)
    yield m
    club_seed.remove(db)


@pytest.fixture
def unloaded(db: Any) -> Iterator[Any]:
    """A test that loads and removes the seed itself: whatever it left loaded (a failed assert, the --reset load
    at its end) is removed after it, so no rows outlive the test (rule 14)."""
    yield db
    club_seed.remove(db)


def test_e_entities_seed_fills_every_screen_and_removes_cleanly(unloaded: Any) -> None:
    conn = unloaded
    club_seed.load(conn)

    names = _set(conn, "SELECT name FROM users")
    assert not names & PACK_CAST
    assert not {n.split()[0] for n in names} & {c.split()[0] for c in PACK_CAST}
    assert _set(conn, "SELECT email FROM users") <= {club_seed._email(n) for n in names}

    stored = set(enums.IDEA_STATUS) - {"needs_you"}  # needs_you is the sharer's view, never stored
    assert _set(conn, "SELECT status FROM ideas") == stored
    assert _set(conn, "SELECT kind FROM notifications WHERE kind IS NOT NULL") == set(enums.INBOX_KIND)
    assert _set(conn, "SELECT state FROM decision_windows") == set(enums.values("window_state"))
    # No set is queued: the ideas the desk has not opened have none (J-REVIEW/1, A1-A3 walk their first open).
    assert _set(conn, "SELECT state FROM question_sets") == {"sent", "seen", "answered", "closed"}
    assert _one(conn, "SELECT count(*) FROM decision_reversals") == 1
    assert _set(conn, "SELECT state FROM teamup_requests") >= {"sent", "approved_team_only", "declined"}
    assert _set(conn, "SELECT state FROM merge_requests") == {"waiting", "accepted"}
    assert _set(conn, "SELECT via FROM merges") == {"lead_accepted", "review_desk"}
    assert _one(conn, "SELECT count(*) FROM teamup_brought") == 1
    assert _one(conn, "SELECT count(DISTINCT tier) FROM ones") == 7
    assert _set(conn, "SELECT way_in FROM ones") == {"founding", "accepted_idea"}
    assert _one(conn, "SELECT count(*) FROM one_posts") >= 3
    assert _one(conn, "SELECT count(*) FROM idea_parts WHERE state = 'failed'") == 1
    assert _one(conn, "SELECT count(*) FROM ideas WHERE status = 'draft' AND archived_at IS NOT NULL") == 1
    assert _one(conn, "SELECT count(*) FROM ideas WHERE idea_id IS NOT NULL AND submission_id IS NULL") >= 20
    assert (
        _one(conn, "SELECT count(*) FROM delivery_measurements WHERE finance_confirmed_at IS NOT NULL") == 1
    )

    # DEC-103: the masked copy never holds a hidden value; the sharer's sealed copy does.
    for r in conn.execute(
        "SELECT h.kind, h.state, m.id, m.text_encrypted, s.text_encrypted AS sealed FROM hidden_details h "
        "JOIN idea_messages m ON m.id::text = h.source_id "
        "JOIN idea_words_sealed s ON s.source = 'message' AND s.source_id = h.source_id"
    ).fetchall():
        masked = open_text("idea_messages", "text_encrypted", r["id"], r["text_encrypted"])
        own = open_text("idea_words_sealed", "text_encrypted", f"message:{r['id']}", r["sealed"], vault=True)
        assert masked and own
        if r["state"] == "hidden":
            assert masked != own and "••••" in masked

    club_seed.remove(conn)
    assert not club_seed.seed_user_ids(conn)
    for table in ("ideas", "ones", "notifications", "crew_members", "teamup_requests", "pseudonym_vault",
                  "one_proposals", "one_messages", "one_glow_ups"):  # fmt: skip
        assert _one(conn, f"SELECT count(*) FROM {table}") == 0, table  # noqa: S608 - fixed names
    club_seed.load(conn)  # --reset loads again on the same counters and contributor codes
    assert len(club_seed.seed_user_ids(conn)) == len(club_seed.PEOPLE)


@pytest.fixture
def seeded(db: Any) -> Iterator[Any]:
    """The seed for one test, removed after it, so no rows outlive the test (rule 14)."""
    club_seed.load(db)
    yield db
    club_seed.remove(db)


def test_l_ones_3_s_one_glow_up_one_tier_rise_waits_to_play_once(seeded: Any) -> None:
    """J-ONE step 6 (L-ONES.rules/3, S-ONE showGlowUp, S-ONE.rules/3): exactly one One has a tier rise not yet shown.
    my_one hands S-ONE the tiers, the story so far and the committee's note; once seen it does not play again. No
    other One has one waiting, so the dashboards J-ONE/4 and /6 walk are not covered by it."""
    from ones.service import glow_up_seen
    from ones.views import my_one

    conn = seeded
    waiting = conn.execute(
        "SELECT g.id, g.tier_from, g.tier_to, o.tier, o.user_id FROM one_glow_ups g JOIN ones o ON o.id = g.one_id "
        "WHERE g.seen_at IS NULL"
    ).fetchall()
    assert len(waiting) == 1
    g = waiting[0]
    who = str(g["user_id"])
    assert who == str(
        _one(conn, "SELECT id FROM users WHERE emp_id_hash = %s", emp_id_hash(club_seed.EMP["dinesh"]))
    )
    assert (g["tier_from"], g["tier_to"], g["tier"]) == (4, 5, 5)

    one = my_one(conn, who)
    assert one is not None and one["glow_up"] is not None
    glow = one["glow_up"]
    assert glow["up"] and glow["from"]["tier_name"] == "Blaze" and glow["to"]["tier_name"] == "White heat"
    # The rise came from his shipped idea's 90-day figures (J-ONE/6). The story's counts are the S-ONE view's (it
    # still reads the old ideas.stage); the seed's part is the milestones.
    shipped = _one(
        conn, "SELECT i.status FROM ideas i JOIN ones o ON o.idea_id = i.idea_id WHERE o.user_id = %s", who
    )
    assert shipped == "shipped"
    measured = (
        "SELECT count(*) FROM delivery_measurements d JOIN ideas i ON i.id = d.idea_uuid "
        "JOIN ones o ON o.idea_id = i.idea_id WHERE o.user_id = %s AND d.mark = 'day_90' AND d.filled_at IS NOT NULL"
    )
    assert _one(conn, measured, who) == 1
    assert {"Became a One", "Reached White heat"} <= {m["what"] for m in glow["story"]["milestones"]}
    assert [(m["from"], m["text"]) for m in glow["messages"]] == [("committee", club_seed.GLOW_UP[4])]

    siddharth = _one(
        conn, "SELECT id FROM users WHERE emp_id_hash = %s", emp_id_hash(club_seed.EMP["siddharth"])
    )
    clear = my_one(conn, str(siddharth))
    assert clear is not None and clear["glow_up"] is None and clear["tier"] == 1

    assert glow_up_seen(conn, who, int(g["id"]))
    again = my_one(conn, who)
    assert again is not None and again["glow_up"] is None


def test_l_merge_desk_l_review_open_j_review_m3_two_opened_desk_ideas_list_each_other(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """J-REVIEW/M3 (L-MERGE.desk/1, 2, 5; L-REVIEW.open/1; L-SIMILAR.rules/6): two ideas from different sharers,
    both with the review desk, opened by the same reviewer (so both edit windows are closed), nothing decided or
    asked, and each lists the other under similar ideas. The one shared first leads by default."""
    conn, m = db, made
    first, later, _reason = club_seed.DESK_PAIR
    rows = {
        str(r["id"]): r
        for r in conn.execute(
            "SELECT id, status, reviewer_id, opened_at, opened_by, edit_closes_at, shared_at, contributor_code, "
            "merged_into, now() AS now FROM ideas WHERE id = ANY(%s::uuid[])",
            ([m[first].uuid, m[later].uuid],),
        ).fetchall()
    }
    a, b = rows[m[first].uuid], rows[m[later].uuid]
    lavanya = _one(conn, "SELECT id FROM users WHERE emp_id_hash = %s", emp_id_hash(club_seed.EMP["lavanya"]))
    for r in (a, b):
        assert r["status"] == "with_review_desk" and r["merged_into"] is None
        assert r["reviewer_id"] == lavanya and r["opened_by"] == lavanya and r["opened_at"] is not None
        assert r["edit_closes_at"] <= r["opened_at"] < r["now"]  # opening closed the sharer's edit window
    assert a["contributor_code"] != b["contributor_code"]
    assert a["shared_at"] < b["shared_at"]  # the default lead (L-MERGE.desk/2)
    assert m[first].ref and m[later].ref

    links = conn.execute(
        "SELECT idea_uuid, other_idea_uuid, strength FROM similar_links WHERE idea_uuid = ANY(%s::uuid[]) "
        "AND other_idea_uuid = ANY(%s::uuid[])",
        ([m[first].uuid, m[later].uuid], [m[first].uuid, m[later].uuid]),
    ).fetchall()
    assert {(str(r["idea_uuid"]), str(r["other_idea_uuid"]), r["strength"]) for r in links} == {
        (m[first].uuid, m[later].uuid, "close"),
        (m[later].uuid, m[first].uuid, "close"),
    }
    pair = [m[first].uuid, m[later].uuid]
    for table, column in (("idea_decisions", "idea_uuid"), ("question_sets", "idea_uuid"),
                          ("merges", "lead_idea_uuid"), ("merges", "merged_idea_uuid")):  # fmt: skip
        sql = f"SELECT count(*) FROM {table} WHERE {column} = ANY(%s::uuid[])"  # noqa: S608 - fixed names
        assert _one(conn, sql, pair) == 0, table
    matched = "SELECT payload->>'similar' FROM conversation_entries WHERE idea_uuid = %s AND event = 'checked_matched'"
    assert _one(conn, matched, m[later].uuid) == "1"


def test_l_merge_request_4_6_7_j_similar_6b_6c_drafts_wait_on_rekha_with_inbox_items(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """J-SIMILAR/5, /6b and /6c (L-MERGE.request/1-4, L-TEAMUP.rules/5): besides T2, two more unsent drafts from
    other sharers each have a merge request waiting on Rekha's R1, so Team up only and Decline each have a request
    of their own to answer. Each waiting request is in Rekha's Inbox under Needs you with the three answers; refs
    carry IDs and small values only."""
    conn, m = db, made
    rekha = p_id(conn, "rekha")
    lead_code = _one(
        conn, "SELECT contributor_code FROM crew_members WHERE idea_uuid = %s AND role = 'lead'", m["R1"].uuid
    )
    assert _one(conn, "SELECT user_id FROM contributor_map WHERE contributor_code = %s", lead_code) == rekha
    assert _one(conn, "SELECT status FROM ideas WHERE id = %s", m["R1"].uuid) == "with_review_desk"

    owners = set()
    for key in ("T2", "N2", "G2"):
        draft = conn.execute(
            "SELECT status, archived_at, shared_at, contributor_code FROM ideas WHERE id = %s", (m[key].uuid,)
        ).fetchone()
        assert draft["status"] == "draft" and draft["archived_at"] is None and draft["shared_at"] is None, key
        assert draft["contributor_code"] != lead_code
        owners.add(draft["contributor_code"])
        reqs = conn.execute(
            "SELECT id, other_idea_uuid, from_code, state, note_encrypted FROM merge_requests WHERE draft_uuid = %s",
            (m[key].uuid,),
        ).fetchall()
        assert len(reqs) == 1, key
        req = reqs[0]
        assert (str(req["other_idea_uuid"]), req["from_code"], req["state"]) == (
            m["R1"].uuid, draft["contributor_code"], "waiting"
        )  # fmt: skip
        note = open_text("merge_requests", "note_encrypted", str(req["id"]), req["note_encrypted"])
        assert note and len(note) >= 30
        outcome = "SELECT outcome FROM similar_links WHERE idea_uuid = %s AND other_idea_uuid = %s"
        assert _one(conn, outcome, m[key].uuid, m["R1"].uuid) == "merge_asked"
        on_crew = "SELECT count(*) FROM crew_members WHERE idea_uuid = %s AND contributor_code = %s"
        assert _one(conn, on_crew, m["R1"].uuid, draft["contributor_code"]) == 0

        items = conn.execute(
            "SELECT n.from_user_id, n.idea_uuid, n.needs_you, n.payload, n.actions FROM notifications n "
            "WHERE n.user_id = %s AND n.kind = 'teamup_request' AND n.payload->>'request_id' = %s",
            (rekha, str(req["id"])),
        ).fetchall()
        assert len(items) == 1, key
        item = items[0]
        sender = _one(
            conn, "SELECT user_id FROM contributor_map WHERE contributor_code = %s", draft["contributor_code"]
        )
        assert item["from_user_id"] == sender and str(item["idea_uuid"]) == m["R1"].uuid and item["needs_you"]
        # Exactly what lane F's tell_lead posts (teamup/requests.py): refs, and answers_for(brings=True) as bare ops.
        assert item["payload"] == {"request_id": str(req["id"]), "request": "merge", "brought": 1}
        assert item["actions"] == BRINGS
    assert len(owners) == 3  # one sharer per request (L-TEAMUP.rules/4)


# The lead's answers as lane F's tell_lead posts them (teamup/rules.py answers_for), each a bare op lane A's Inbox
# hands to teamup/inbox_ops.py: with something brought, and with nothing brought.
BRINGS = [
    {"label": "Decline", "style": "text", "op": "decline"},
    {"label": "Team up only", "style": "line", "op": "team_only"},
    {"label": "Merge it", "style": "primary", "op": "merge"},
]
BRINGS_NOTHING = [
    {"label": "Decline", "style": "text", "op": "decline"},
    {"label": "Approve", "style": "primary", "op": "team_only"},
]


def test_l_inbox_kinds_l_teamup_l_merge_request_each_teamup_request_item_is_a_waiting_request_row(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """L-INBOX.kinds, L-TEAMUP.rules/5-6, L-MERGE.request/4 (J-SIMILAR/5-6c): every seeded `teamup_request` item is
    one waiting request, exactly as lane F's tell_lead posts it: to the idea's lead, from the requester, refs
    {request_id, request, brought} where request_id is the real teamup_requests or merge_requests row, and the
    answers as bare ops (decline, team_only, merge), so lane F's inbox_ops handler finds the row it answers."""
    conn, m = db, made
    waiting = {
        str(r["id"]): ("teamup", r)
        for r in conn.execute(
            "SELECT r.id, r.idea_uuid, r.from_code, (SELECT count(*) FROM teamup_brought b WHERE b.request_id = r.id) "
            "AS brought FROM teamup_requests r WHERE r.state = 'sent'"
        ).fetchall()
    } | {
        str(r["id"]): ("merge", r)
        for r in conn.execute(
            "SELECT id, other_idea_uuid AS idea_uuid, from_code, 1 AS brought FROM merge_requests "
            "WHERE state = 'waiting'"
        ).fetchall()
    }
    items = conn.execute(
        "SELECT user_id, from_user_id, idea_uuid, needs_you, payload, actions FROM notifications "
        "WHERE kind = 'teamup_request'"
    ).fetchall()
    assert len(waiting) == 5 and sorted(i["payload"]["request_id"] for i in items) == sorted(waiting)

    user_of = "SELECT user_id FROM contributor_map WHERE contributor_code = %s"
    lead_of = "SELECT contributor_code FROM crew_members WHERE idea_uuid = %s AND role = 'lead'"
    for item in items:
        request, row = waiting[item["payload"]["request_id"]]
        assert item["payload"] == {
            "request_id": str(row["id"]),
            "request": request,
            "brought": row["brought"],
        }
        assert item["actions"] == (BRINGS if row["brought"] else BRINGS_NOTHING)
        assert item["needs_you"] and item["idea_uuid"] == row["idea_uuid"]
        assert item["user_id"] == _one(conn, user_of, _one(conn, lead_of, row["idea_uuid"]))
        assert item["from_user_id"] == _one(conn, user_of, row["from_code"])

    def item_for(lead: str, key: str, requester: str) -> Any:
        found = [
            i
            for i in items
            if str(i["idea_uuid"]) == m[key].uuid and i["from_user_id"] == p_id(conn, requester)
        ]
        assert len(found) == 1 and found[0]["user_id"] == p_id(conn, lead), (key, requester)
        return found[0]

    esha = item_for("tanvi", "T5", "esha")  # E1 brought along
    brought = "SELECT idea_uuid FROM teamup_brought WHERE request_id = %s"
    assert str(_one(conn, brought, esha["payload"]["request_id"])) == m["E1"].uuid
    assert (esha["payload"]["request"], esha["payload"]["brought"], esha["actions"]) == ("teamup", 1, BRINGS)
    bhavesh = item_for("rekha", "R1", "bhavesh")  # nothing brought: Decline and Approve
    assert (bhavesh["payload"]["request"], bhavesh["payload"]["brought"]) == ("teamup", 0)
    assert bhavesh["actions"] == BRINGS_NOTHING


def test_gap_seed_l_inbox_needs_you_and_draft_kept_items_carry_notify_dedupe_keys(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """GAP-SEED, L-INBOX (J-TEAMUP's lead Inbox, J-RESUME/5): every seeded lead "Needs you" item carries lane F's
    `request_key(<request id>)` and every `draft_kept` item `draft_kept:<ideas.id>`, the keys lane A's notify.post
    stores, so a later post or `notify.resolve` on the same key finds the seeded item instead of adding a second. Each
    key passes notify's `_KEY` rule, and no other seeded item carries one."""
    from notify import _KEY
    from teamup.adapters import request_key

    conn, m = db, made
    asks = conn.execute(
        "SELECT payload, dedupe_key FROM notifications WHERE kind = 'teamup_request'"
    ).fetchall()
    assert len(asks) == 5
    assert all(a["dedupe_key"] == request_key(a["payload"]["request_id"]) for a in asks)
    assert {a["payload"]["request"] for a in asks} == {"teamup", "merge"}

    kept = conn.execute(
        "SELECT idea_uuid, dedupe_key FROM notifications WHERE kind = 'draft_kept'"
    ).fetchall()
    assert sorted(str(k["idea_uuid"]) for k in kept) == sorted([m["T1"].uuid, m["I2"].uuid])
    assert all(k["dedupe_key"] == f"draft_kept:{k['idea_uuid']}" for k in kept)

    keys = [r["dedupe_key"] for r in [*asks, *kept]]
    assert all(_KEY.match(k) for k in keys) and len(set(keys)) == len(keys)
    assert _one(conn, "SELECT count(*) FROM notifications WHERE dedupe_key IS NOT NULL") == len(keys)

    # The hand-off to the lead's answer (J-TEAMUP): lane F's resolve, by request id, clears that seeded item only.
    from teamup import adapters

    rid = asks[0]["payload"]["request_id"]
    adapters.resolve(conn, rid)
    still = "SELECT count(*) FROM notifications WHERE kind = 'teamup_request' AND needs_you"
    assert _one(conn, still) == len(asks) - 1
    assert not _one(conn, "SELECT needs_you FROM notifications WHERE dedupe_key = %s", request_key(rid))


def p_id(conn: Any, first: str) -> Any:
    return _one(conn, "SELECT id FROM users WHERE emp_id_hash = %s", emp_id_hash(club_seed.EMP[first]))


def test_l_draft_channels_l_hide_j_resume_5_6_email_draft_with_detail_hidden(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """J-RESUME/5 and /6 (L-DRAFT.channels, L-HIDE.rules/4): a forwarded email landed as an unsent draft on the email
    channel, with its origin (subject, when it came) sealed on the draft, no device, its words in via email with the
    customer detail hidden from everyone but the owner, and a "kept your draft" Inbox item for its owner that opens
    the draft. The channel is off at launch (DEC-105); the record only has to exist."""
    import json

    conn, m = db, made
    i2 = m["I2"]
    idea = conn.execute(
        "SELECT status, channel, step, saved_device, saved_device_id, archived_at, shared_at, origin_encrypted "
        "FROM ideas WHERE id = %s",
        (i2.uuid,),
    ).fetchone()
    assert (idea["status"], idea["channel"], idea["step"]) == ("draft", "email", "tell")
    assert idea["saved_device"] is None and idea["saved_device_id"] is None
    assert idea["archived_at"] is None and idea["shared_at"] is None
    origin = json.loads(open_text("ideas", "origin_encrypted", i2.uuid, idea["origin_encrypted"]) or "{}")
    assert origin["subject"] and origin["note"] and origin["received_at"]

    msgs = conn.execute(
        "SELECT id, via, device, text_encrypted FROM idea_messages WHERE idea_uuid = %s", (i2.uuid,)
    ).fetchall()
    assert [(r["via"], r["device"]) for r in msgs] == [("email", None)]
    hidden = conn.execute(
        "SELECT kind, state, source_id FROM hidden_details WHERE idea_uuid = %s", (i2.uuid,)
    ).fetchall()
    assert [(h["kind"], h["state"], h["source_id"]) for h in hidden] == [
        ("folio", "hidden", str(msgs[0]["id"]))
    ]
    value = i2.spec.hidden["{folio}"][1]
    masked = open_text("idea_messages", "text_encrypted", str(msgs[0]["id"]), msgs[0]["text_encrypted"])
    assert masked and value not in masked and "••••" in masked
    sealed = _one(
        conn, "SELECT text_encrypted FROM idea_words_sealed WHERE source = 'message' AND source_id = %s",
        str(msgs[0]["id"]),
    )  # fmt: skip
    own = open_text("idea_words_sealed", "text_encrypted", f"message:{msgs[0]['id']}", sealed, vault=True)
    assert own and value in own

    kept = conn.execute(
        "SELECT user_id, from_user_id, needs_you, payload, actions FROM notifications "
        "WHERE kind = 'draft_kept' AND idea_uuid = %s",
        (i2.uuid,),
    ).fetchall()
    assert len(kept) == 1
    # To the sharer's users.id, from the system.
    assert kept[0]["user_id"] == p_id(conn, "indira") and kept[0]["from_user_id"] is None
    # Exactly what lane C's intake posts (L-DRAFT.channels): refs `via` only, one "Check and send" to the draft by
    # its ideas.id uuid, never an IDEA- reference (a draft has none).
    assert kept[0]["payload"] == {"via": "email"} and not kept[0]["needs_you"]
    assert kept[0]["actions"] == [{"label": "Check and send", "style": "primary", "to": f"/share/{i2.uuid}"}]
    assert i2.ref is None and "IDEA-" not in kept[0]["actions"][0]["to"]


@pytest.mark.parametrize(("key", "sharer"), [("P1", "pallavi"), ("K1", "kiran")])
def test_l_review_open_1_j_review_1_a1_a3_unopened_unassigned_with_no_question_set(
    db: Any, made: dict[str, club_seed.Made], key: str, sharer: str
) -> None:
    """J-REVIEW/1 walks P1's first open and J-REVIEW/A1 K1's (L-REVIEW.open/1, L-QUESTIONS.ask): each is with the
    review desk at To review, never opened, no reviewer, and no question set at all, so the walk's first open and
    (A2, A3) its first question are its own. Nothing in the conversation says it was opened or asked, and the
    sharer has no questions item about it."""
    conn, m = db, made
    idea = conn.execute(
        "SELECT status, idea_id, reviewer_id, opened_at, opened_by, contributor_code FROM ideas WHERE id = %s",
        (m[key].uuid,),
    ).fetchone()
    assert idea["status"] == "with_review_desk" and idea["idea_id"]
    assert (idea["reviewer_id"], idea["opened_at"], idea["opened_by"]) == (None, None, None)
    owner = "SELECT user_id FROM contributor_map WHERE contributor_code = %s"
    assert _one(conn, owner, idea["contributor_code"]) == p_id(conn, sharer)

    assert _one(conn, "SELECT count(*) FROM question_sets WHERE idea_uuid = %s", m[key].uuid) == 0
    said = (
        "SELECT count(*) FROM conversation_entries WHERE idea_uuid = %s "
        "AND (question_set_id IS NOT NULL OR event = 'opened_by_desk')"
    )
    assert _one(conn, said, m[key].uuid) == 0
    asked = (
        "SELECT count(*) FROM notifications WHERE idea_uuid = %s AND kind IN ('questions', 'answer_reminder')"
    )
    assert _one(conn, asked, m[key].uuid) == 0


def test_l_questions_ask_j_review_a1_a3_k1_how_often_left_empty_waits(seeded: Any) -> None:
    """J-REVIEW/A1 to A3 (L-QUESTIONS.ask, L-DRAFT.parts): Kiran's K1 is his only idea, and its "How often" was left
    empty: no value on the idea, and its part is waiting with no value, reason or quote, not filled with nothing.
    That gap is what the walk asks about. Kiran has nothing in his Inbox."""
    conn = seeded
    kiran = p_id(conn, "kiran")
    spec = club_seed.IDEAS["K1"]
    ideas = conn.execute(
        "SELECT i.id, i.title, i.often FROM ideas i "
        "JOIN contributor_map m ON m.contributor_code = i.contributor_code WHERE m.user_id = %s",
        (kiran,),
    ).fetchall()
    assert len(ideas) == 1  # Kiran's only idea: nothing another step changes is his
    assert spec.often is None and ideas[0]["title"] == spec.title and ideas[0]["often"] is None
    part = conn.execute(
        "SELECT state, value, why, source_quote FROM idea_parts WHERE idea_uuid = %s AND key = 'often'",
        (ideas[0]["id"],),
    ).fetchone()
    assert dict(part) == {"state": "waiting", "value": None, "why": None, "source_quote": None}
    assert _one(conn, "SELECT count(*) FROM notifications WHERE user_id = %s", kiran) == 0


def test_s_03_hero_1_bld_c148_every_persona_has_seen_home_but_sana_the_first_visit(unloaded: Any) -> None:
    """S-03's first visit (BLD-C148, J-TRACK/2): every seeded persona has seen Home, so their first /home after a reset
    is the returning one with Needs you and Your ideas; Sana (SYN-10026) alone has not, and has nothing of her own: no
    ideas or drafts, no crew place, no team-up or merge request, no Inbox item. `remove` takes her out (rule 14)."""
    conn = unloaded
    club_seed.load(conn)
    assert club_seed.FIRST_VISIT == "sana" and club_seed.EMP["sana"] == "SYN-10026"
    rows = conn.execute(
        "SELECT u.id, u.emp_id_hash, s.home_seen_at FROM users u JOIN person_settings s ON s.user_id = u.id "
        "WHERE u.emp_id_hash = ANY(%s)",
        ([emp_id_hash(e) for e, *_ in club_seed.PEOPLE],),
    ).fetchall()
    assert len(rows) == len(club_seed.PEOPLE)
    sana_hash = emp_id_hash("SYN-10026")
    unseen = [r for r in rows if r["home_seen_at"] is None]
    assert [r["emp_id_hash"] for r in unseen] == [sana_hash]
    sana = str(unseen[0]["id"])
    code = _one(conn, "SELECT contributor_code FROM contributor_map WHERE user_id = %s", sana)
    assert code
    assert _one(conn, "SELECT count(*) FROM ideas WHERE contributor_code = %s", code) == 0
    for table, column in (("crew_members", "contributor_code"), ("teamup_requests", "from_code"),
                          ("merge_requests", "from_code"), ("answers", "by_code")):  # fmt: skip
        assert _one(conn, f"SELECT count(*) FROM {table} WHERE {column} = %s", code) == 0, table  # noqa: S608
    assert _one(conn, "SELECT count(*) FROM notifications WHERE user_id = %s", sana) == 0
    assert _one(conn, "SELECT count(*) FROM idea_opens WHERE user_id = %s", sana) == 0

    club_seed.remove(conn)
    assert _one(conn, "SELECT count(*) FROM users WHERE emp_id_hash = %s", sana_hash) == 0
    assert _one(conn, "SELECT count(*) FROM person_settings WHERE user_id = %s", sana) == 0
    assert _one(conn, "SELECT count(*) FROM contributor_map WHERE user_id = %s", sana) == 0


def test_bld_f069_j_teamup_faisals_seeded_team_up_answer_says_hello_into_the_box(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """BLD-F069, J-TEAMUP: Faisal's seeded team-up answer (team only, from Tanvi on T7) is posted the way lane F's
    live `tell_requester` posts it: one "Say hello" that opens T7's conversation with the box focused."""
    t7 = made["T7"]
    rows = db.execute(
        "SELECT actions FROM notifications WHERE kind = 'teamup_answer' AND user_id = %s AND idea_uuid = %s",
        (p_id(db, "faisal"), t7.uuid),
    ).fetchall()
    assert len(rows) == 1 and t7.ref
    assert rows[0]["actions"] == [
        {"label": "Say hello", "style": "primary", "to": f"/ideas/{t7.ref}/conversation#say-hello"}
    ]


def test_gap_seed_j_similar_1_l_similar_rules_4_each_draft_carries_the_matches_check_it_shows(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """GAP-SEED, J-SIMILAR/1 (L-SIMILAR.rules/4, C-SIMGRID.other S-04B): each unsent draft's similar part holds the
    SimilarMatch[] lane C's draft run would write, the same matches S-05's part 3 reads for its sharer, so S-04B's
    panel says "1 similar idea, Colleagues raised something close". T2 finds R1, close; a draft with no links keeps
    none. "Checked and matched" counts what was found by the check (L-SIMILAR.rules/5); F2's later link is not."""
    from draft.store import Device, Owner, view
    from similar.preview import Viewer
    from similar.views import matches_for

    tanvi = p_id(db, "tanvi")
    code = _one(db, "SELECT contributor_code FROM contributor_map WHERE user_id = %s", tanvi)
    part = view(db, Owner(str(tanvi), str(code)), made["T2"].uuid, Device("laptop", None))["parts"]["similar"]
    assert part["state"] == "filled"
    assert [(x["idea"]["id"], x["strength"]) for x in part["value"]] == [(made["R1"].ref, "close")]
    assert part["value"][0]["idea"]["title"] == club_seed.IDEAS["R1"].title
    assert part["value"][0]["reason"] == "Close match: the same failed SIP debit"

    part_of = "SELECT value FROM idea_parts WHERE idea_uuid = %s AND key = 'similar'"
    for key in ("T1", "T2", "N2", "G2"):  # the drafts that found R1: their parts are what S-05 shows now
        owner = p_id(db, club_seed.IDEAS[key].owner)
        stored = _one(db, part_of, made[key].uuid)
        assert stored and stored == matches_for(db, made[key].uuid, Viewer.of(db, str(owner))), key
        assert [x["idea"]["id"] for x in stored] == [made["R1"].ref], key
    assert _one(db, part_of, made["I2"].uuid) == []

    matched = "SELECT payload->>'similar' FROM conversation_entries WHERE idea_uuid = %s AND event = 'checked_matched'"
    for key, found in (("T5", "1"), ("T6", "1"), ("T11", "1"), ("J2", "1"), ("F2", "0"), ("V1", "0")):
        assert _one(db, matched, made[key].uuid) == found, key


def test_gap_seed_l_similar_rules_4_with_matching_show_off_the_seed_refuses_and_a_reset_keeps_the_seed(
    unloaded: Any, test_database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """GAP-SEED (L-SIMILAR.rules/4, /5): with `matching.show` off, `matches_for` gives a sharer no matches and has no
    way past the switch, so a seed loaded then would leave each draft's similar part empty while "Checked and
    matched" still counts 1. The seed raises instead, naming the switch, and writes nothing, so the parts and the
    counts never disagree. `--reset` removes and loads in one transaction: refused, it keeps the seed it found."""
    from core.db import connect
    from tests import helpers

    conn = unloaded

    def switch(state: str) -> None:
        conn.execute("UPDATE kill_switches SET state = %s WHERE name = 'matching.show'", (state,))
        killswitch.clear_cache()  # past the 10-second cache, as the `club` fixture does

    try:
        switch("off")
        with pytest.raises(club_seed.MatchingHidden, match=r"kill switch matching\.show is off"):
            club_seed.load(conn)
        assert club_seed.seed_user_ids(conn) == []
        assert _one(conn, "SELECT count(*) FROM idea_parts") == 0
        assert _one(conn, "SELECT count(*) FROM conversation_entries WHERE event = 'checked_matched'") == 0

        switch("on")
        m = club_seed.load(conn)
        switch("off")
        monkeypatch.setattr(club_seed, "_dev_only", lambda: None)
        monkeypatch.setattr(club_seed, "connect", lambda **kw: connect(helpers.db_url(test_database), **kw))
        assert club_seed.main(["--reset"]) == 1
        assert "matching.show" in capsys.readouterr().err
        part_of = "SELECT value FROM idea_parts WHERE idea_uuid = %s AND key = 'similar'"
        assert [x["idea"]["id"] for x in _one(conn, part_of, m["T2"].uuid)] == [m["R1"].ref]  # the same rows
        matched = "SELECT payload->>'similar' FROM conversation_entries WHERE idea_uuid = %s AND event = 'checked_matched'"
        assert _one(conn, matched, m["T5"].uuid) == "1"
    finally:
        switch("on")


def test_gap_seed_j_teamup_1_l_crew_4_the_top_crew_card_says_who_would_help(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """GAP-SEED, J-TEAMUP/1 (L-CREW/4, BLD-F031): with AI drafting off, "They're looking for" on the top crew card
    ("Distributors re-send the same empanelment papers") is its sharer's Who would help picks, each one from the
    configured list (`rules/sorting.md` `helpers`)."""
    from pathlib import Path

    from crew.deck import looking_for
    from rules.loader import load_rule

    seeded_repo = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
    configured = load_rule(seeded_repo, "sorting").data["helpers"]
    picks = _one(db, "SELECT helper_picks FROM ideas WHERE id = %s", made["P1"].uuid)
    assert len(picks) == 3
    assert set(picks) <= set(configured)
    assert looking_for(picks, None) == "Someone in operations, someone who knows the rules, data or reports"


def test_gap_seed_l_decide_6_j_one_1_j1_carries_one_ask_to_join_the_build_team(
    made: dict[str, club_seed.Made], db: Any
) -> None:
    """BLD-E059: the seed's only join ask is J1's, from its sharer, on a Pick that stands with no build team yet."""
    rows = db.execute(
        "SELECT a.idea_uuid, u.first_name FROM join_build_asks a JOIN users u ON u.id = a.user_id "
        "WHERE a.idea_uuid = ANY(%s)",
        ([mm.uuid for mm in made.values()],),
    ).fetchall()
    assert [(str(r["idea_uuid"]), r["first_name"]) for r in rows] == [(made["J1"].uuid, "Jatin")]
    assert not db.execute("SELECT 1 FROM build_teams WHERE idea_uuid = %s", (made["J1"].uuid,)).fetchone()


# --- Lane G's 23:00 walk: T1, the draft J-RECOVER/3 and /6 open (BLD-E064) ----------------------------------------


def _t1_view(db: Any, made: dict[str, club_seed.Made]) -> dict[str, Any]:
    """T1 as Tell it reads it for Tanvi: lane C's `GET /drafts/:id` (S-04B), the API J-RECOVER/3 and /6 open."""
    from draft.store import Device, Owner, view

    tanvi = p_id(db, "tanvi")
    code = _one(db, "SELECT contributor_code FROM contributor_map WHERE user_id = %s", tanvi)
    return view(db, Owner(str(tanvi), str(code)), made["T1"].uuid, Device("phone", None))


def test_gap_seed_j_recover_3_j_recover_6_l_hide_t1_hides_a_folio_the_shared_rules_call_a_folio(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """GAP-SEED, L-HIDE (J-RECOVER/3, /6): T1's hidden value is a folio by the one-source pattern rules
    (`pii/patterns.yaml`) in the words Tanvi typed, and nothing else: not a phone, as `7700012389` was. It is stored
    and shown as a folio ("Folio ••••17"), and her sealed words hold it while the message holds only the mask."""
    from hide.detect import config as hide_config
    from pii.patterns import scan

    spec = club_seed.IDEAS["T1"]
    kind, value = spec.hidden["{folio}"]
    own = spec.words[0].replace("{folio}", value)
    start = own.index(value)
    over = [m for m in scan(own) if m.start < start + len(value) and m.end > start]
    assert [(m.pattern_id, own[m.start : m.end], m.action) for m in over] == [("folio", value, "block")]
    assert hide_config().from_patterns["folio"] == kind == "folio"

    rows = db.execute(
        "SELECT kind, masked, state FROM hidden_details WHERE idea_uuid = %s", (made["T1"].uuid,)
    ).fetchall()
    assert [(r["kind"], r["masked"], r["state"]) for r in rows] == [("folio", "Folio ••••17", "hidden")]
    msg = db.execute(
        "SELECT id, text_encrypted FROM idea_messages WHERE idea_uuid = %s", (made["T1"].uuid,)
    ).fetchone()
    masked = open_text("idea_messages", "text_encrypted", str(msg["id"]), msg["text_encrypted"])
    assert masked and value not in masked and "folio Folio ••••17 left" in masked


def test_gap_seed_j_recover_6_l_draft_parts_8_c_hidden_where_t1_receipt_lists_what_was_hidden(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """GAP-SEED, L-DRAFT.parts/8, C-HIDDEN.where (J-RECOVER/6): T1's receipt is what lane C's `draft.runs.finish`
    writes after a first run, so its hidden line lists the details by their masks, "Hid 1 personal detail from
    everyone but you: Folio ••••17.", beside the hidden list the panel reads. The drafted, sorted and found lines
    come in the engine's order; How often failed, so there is no "Noted how often" line. Its next prompts are
    the engine's for those parts."""
    from draft import parts as dp

    spec, out = club_seed.IDEAS["T1"], _t1_view(db, made)
    assert [(h["kind"], h["masked"], h["state"]) for h in out["hidden"]] == [
        ("folio", "Folio ••••17", "hidden")
    ]
    assert out["receipt"] == [
        f"Drafted a title: “{spec.title}”.",
        "Sorted it under Investor service, affecting investors.",
        "Marked it as saves time.",
        "Hid 1 personal detail from everyone but you: Folio ••••17.",
        "Found 1 similar idea from colleagues. You can team up on the next step.",
        "Your draft is ready. Add a detail, or check it.",
    ]
    assert out["suggestions"] == ["Say how often it happens", "Add what you already tried"]
    after = {"title": {"title": spec.title, "summary": spec.summary}, "often": None, "who": spec.affects,
             "value": spec.brings, "area": spec.area}  # fmt: skip
    assert out["suggestions"] == dp.suggestions(after)
    # Every seeded draft's receipt is the engine's: no line it would not write
    known = (
        "Turned your email", "Drafted a title", "Sorted it under", "Noted ", "Marked it as", "Hid ", "Found ",
        "Your draft is ready",
    )  # fmt: skip
    for key, mm in made.items():
        lines = _one(db, "SELECT receipt FROM draft_runs WHERE idea_uuid = %s", mm.uuid)
        assert lines and all(line.startswith(known) for line in lines), key
        hid = [line for line in lines if line.startswith("Hid ")]
        assert all(": " in line and "••••" in line for line in hid), key


def test_gap_seed_j_recover_3_j_recover_6_l_draft_parts_2_each_part_reads_the_engines_reason(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """GAP-SEED, L-DRAFT.parts/2 (J-RECOVER/3, /6): T1's parts carry the reason lines lane C's engine writes
    (`draft.parts.why_for`), in Compose.md's words: the title "From your first sentence.", who it affects "Suggested
    because you mentioned investors.", the area "Suggested because it’s about investor service." (ComposeResume.md's
    form), what it's worth quoting her words; How often failed, so it has none. No part anywhere in the seed reads
    the old "Because you mentioned it"."""
    parts = _t1_view(db, made)["parts"]
    assert parts["title"]["why"] == "From your first sentence."
    assert parts["title"]["source_quote"].startswith("Walk-in investors who come to update KYC")
    assert parts["often"]["state"] == "failed" and "why" not in parts["often"]
    assert parts["who"]["why"] == "Suggested because you mentioned investors."
    assert parts["area"]["why"] == "Suggested because it’s about investor service."
    assert parts["value"]["why"] == (
        "From your words: “Yesterday one investor with folio Folio ••••17 left after forty minutes”"
    )
    ours = [mm.uuid for mm in made.values()]
    assert not _one(
        db,
        "SELECT count(*) FROM idea_parts WHERE idea_uuid = ANY(%s) AND why = 'Because you mentioned it'",
        ours,
    )
    # A confirmed sorting keeps the suggestion's line (submit.sorting), never "From your words" on its own
    rows = db.execute("SELECT sorting_sources FROM ideas WHERE id = ANY(%s)", (ours,)).fetchall()
    whys = {
        str(rec.get("why")) for r in rows for rec in (r["sorting_sources"] or {}).values() if rec.get("why")
    }
    assert "From your words" not in whys


def test_gap_seed_bld_e066_p_decisions_19_every_seeded_person_is_on_the_launch_default(
    db: Any, made: dict[str, club_seed.Made]
) -> None:
    """GAP-SEED, P-DECISIONS #19 (BLD-E066): at launch S1-S3 give everyone the default, so the seed puts nobody on an
    alternative and the demo and the journeys walk what employees get. The assignments and exposures are still there
    for the admin experiments page."""
    variants = _set(db, "SELECT DISTINCT variant FROM flag_assignments")
    assert variants == {"default"}
    assert _set(db, "SELECT DISTINCT flag_key FROM flag_assignments") == {"s1", "s2", "s3"}
    assert _set(db, "SELECT DISTINCT variant FROM flag_exposures") == {"default"}


# --- The seed's clocks are the live ones (BLD-E067; lane G's walk of 19 Nov, rows 2 and 5) ---------------------------

# Fixed load times, never the real clock (office time, 2026): a Monday morning; Thursday 19 November in the morning
# (the walk's), in the two hours before 6 pm, and just before midnight, read after it; launch night, Friday 20
# November at 10 pm; a Saturday at noon; and a Monday in the two hours before 6 pm.
WALK_LOAD = dt.datetime(2026, 11, 19, 10, 0, tzinfo=IST)
LOADS = (
    dt.datetime(2026, 11, 16, 11, 30, tzinfo=IST),
    WALK_LOAD,
    dt.datetime(2026, 11, 19, 17, 0, tzinfo=IST),
    dt.datetime(2026, 11, 19, 23, 50, tzinfo=IST),
    dt.datetime(2026, 11, 20, 22, 0, tzinfo=IST),
    dt.datetime(2026, 11, 21, 12, 0, tzinfo=IST),
    dt.datetime(2026, 11, 23, 17, 0, tzinfo=IST),
)


@pytest.fixture
def office(unloaded: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """The seed's company repo for its calendar and promises, as the pages' tests load it."""
    from core.config import get_settings
    from tests import helpers

    monkeypatch.setenv("COMPANY_REPO_PATH", str(helpers.SEED))
    get_settings.cache_clear()
    yield unloaded
    get_settings.cache_clear()


def _sets(conn: Any) -> dict[str, Any]:
    return {
        str(r["idea_id"]): r
        for r in conn.execute(
            "SELECT i.idea_id, s.* FROM question_sets s JOIN ideas i ON i.id = s.idea_uuid WHERE s.sent_at IS NOT NULL"
        ).fetchall()
    }


def test_gap_seed_l_questions_clock_5_every_seeded_set_is_due_at_6_pm_ist_as_the_desk_sends_it(
    office: Any,
) -> None:
    """GAP-SEED, L-QUESTIONS.clock/5 (J-TRACK/3, /5, /6; J-BROWSE/4): "Deadlines are at 6 pm local office time on the
    due day". Every seeded set is due when lane B's send would make it due (`desk.clock.answer_due`), never at the
    load's hour. Z1 stays overdue, B1 answered, and T6 is due at 6 pm within the day, at least 2 hours after the
    load, so a walk straight after never finds it overdue."""
    from desk import clock, promises

    conn = office
    for now in LOADS:
        m = club_seed.load(conn, now)
        sets = _sets(conn)
        assert set(sets) == {m[k].ref for k in ("T6", "Z1", "B1", "T7")}
        for ref, s in sets.items():
            due = s["due_at"].astimezone(IST)
            assert (due.hour, due.minute, due.second) == (18, 0, 0), (now, ref, due)
            assert s["due_at"] == clock.answer_due(
                s["sent_at"], s["time_to_answer"], promises.get(), clock.office_calendar()
            ), (now, ref)
        t6, z1, b1 = sets[m["T6"].ref], sets[m["Z1"].ref], sets[m["B1"].ref]
        assert now + club_seed.WALK_ROOM <= t6["due_at"] <= now + dt.timedelta(hours=26), now
        assert t6["state"] == "seen" and t6["seen_at"] < now
        # Overdue, as J-REVIEW/A4 walks it (Remind Zoya, Give 2 more days)
        assert z1["state"] == "sent" and z1["due_at"] < now, now
        assert b1["state"] == "answered" and b1["sent_at"] < b1["answered_at"] < now, now
        # Shared, then opened by the desk, then asked (L-REVIEW.open/1), all before the load
        idea = conn.execute(
            "SELECT shared_at, opened_at FROM ideas WHERE id = %s", (m["T6"].uuid,)
        ).fetchone()
        assert idea["shared_at"] < idea["opened_at"] < t6["sent_at"] < now, now
        club_seed.remove(conn)


def test_gap_seed_l_notify_5_t6_reminder_went_a_day_before_its_deadline_and_says_so(office: Any) -> None:
    """GAP-SEED, L-NOTIFY/5, L-QUESTIONS.clock/2 (J-TRACK/2, /6): an open set is reminded 24 hours and 2 hours before
    its deadline. T6's "Answer reminder" went 24 hours before (or at the load, when that is still ahead), its set
    records it, and both of T6's Inbox items and Z1's are due when their set is. So the reminder reads "1 day" or
    hours and minutes left, never "2 days", before midnight and after it."""
    from notify import render

    conn = office
    for now in LOADS:
        m = club_seed.load(conn, now)
        sets = _sets(conn)
        t6 = sets[m["T6"].ref]
        items = {
            (str(r["idea_uuid"]), r["kind"]): r
            for r in conn.execute(
                "SELECT idea_uuid, kind, created_at, due_at FROM notifications "
                "WHERE kind IN ('questions', 'answer_reminder')"
            ).fetchall()
        }
        assert set(items) == {
            (m["T6"].uuid, "questions"),
            (m["T6"].uuid, "answer_reminder"),
            (m["Z1"].uuid, "questions"),
        }
        reminder = items[(m["T6"].uuid, "answer_reminder")]
        assert reminder["created_at"] == min(t6["due_at"] - dt.timedelta(hours=24), now) == t6["reminded_at"]
        assert reminder["created_at"] <= now
        for (idea, kind), item in items.items():
            s = t6 if idea == m["T6"].uuid else sets[m["Z1"].ref]
            assert item["due_at"] == s["due_at"], kind
            if kind == "questions":
                assert item["created_at"] == s["sent_at"]
        for read_at in (now, now + dt.timedelta(minutes=30)):  # a load before midnight, read after it
            left = render._left(dict(reminder), read_at)
            assert left == "1 day" or re.fullmatch(r"\d{2}:\d{2}", left), (now, read_at, left)
        club_seed.remove(conn)


def test_gap_seed_bld_b231_decide_by_and_team_by_are_the_live_clocks(office: Any) -> None:
    """GAP-SEED, BLD-B231, L-REVIEW.clock/1, L-DECIDE.rules/6 (J-TEAMUP/2, /3, /5): a seeded idea's decide-by is the
    date a share at the same moment would get (`submit.clock.decide_by`, which counts the share day as day 1), and a
    seeded Pick's or reversal's team-by the date the desk would write (`desk.clock.team_by`), each at 6 pm office
    time. An idea still with the desk keeps its decide-by ahead of the load: the live date, or the first working
    day's 6 pm at least 2 hours after the load when that is later (a Friday-night or weekend load; launch night is
    a Friday evening). R1, shared on Friday 13 November at 10 am and loaded on Thursday 19 November at 10 am, is
    decided by Thursday 19 November, not Friday 20 (the walk's row 5)."""
    from desk import clock as desk_clock
    from desk import promises
    from submit import clock, config

    conn = office
    cal = desk_clock.office_calendar()
    for now in LOADS:
        m = club_seed.load(conn, now)
        floor_day = now.astimezone(IST).date()
        while not cal.working(floor_day) or cal.at(floor_day, 18) - now < dt.timedelta(hours=2):
            floor_day += dt.timedelta(days=1)
        floor = cal.at(floor_day, 18)
        shared = conn.execute(
            "SELECT idea_id, status, shared_at, decide_by FROM ideas WHERE shared_at IS NOT NULL"
        ).fetchall()
        assert len(shared) >= 20
        with_desk = [r for r in shared if r["status"] in ("checking", "with_review_desk")]
        assert len(with_desk) >= 10
        for r in shared:
            live = clock.decide_by(r["shared_at"], config.promises())
            expected = max(live, floor) if r in with_desk else live
            assert r["decide_by"] == expected, (now, r["idea_id"])
            assert r["decide_by"].astimezone(IST).hour == 18
        for r in with_desk:
            assert r["decide_by"] > now, (now, r["idea_id"])
        teams = conn.execute(
            "SELECT at, team_by FROM idea_decisions WHERE choice = 'pick' "
            "UNION ALL SELECT at, team_by FROM decision_reversals WHERE to_choice = 'pick'"
        ).fetchall()
        assert len(teams) >= 5
        for t in teams:
            assert t["team_by"] == desk_clock.team_by(t["at"], promises.get(), desk_clock.office_calendar())
            assert t["team_by"].astimezone(IST).hour == 18
        if now == WALK_LOAD:
            r1 = _one(conn, "SELECT decide_by FROM ideas WHERE id = %s", m["R1"].uuid)
            assert r1 == dt.datetime(2026, 11, 19, 18, 0, tzinfo=IST)
        club_seed.remove(conn)


def test_dec111_gap_seed_l_inbox_a_reviewers_comment_comes_from_the_review_desk(office: Any) -> None:
    """DEC-111, GAP-SEED (BLD-E072): Harish is on the review desk, so his comment on Tanvi's T7 is sent as the desk
    as a whole, as lane F posts a comment or a mention a reviewer writes as the desk: its refs say `as_desk: true`
    and, as `notify.post` stores it, the item keeps no reviewer. Tanvi's Inbox reads "The review desk" with no
    "Harish" anywhere in the item. The desk's own kinds keep no reviewer either; a reversal keeps its committee
    member, whom lane A names by the reader's live roles (DEC-113)."""
    import json

    from notify import inbox

    conn = office
    m = club_seed.load(conn)
    tanvi, harish = p_id(conn, "tanvi"), p_id(conn, "harish")
    rows = conn.execute(
        "SELECT id, kind, from_user_id, payload FROM notifications WHERE user_id = %s AND channel = 'in_app'",
        (tanvi,),
    ).fetchall()
    by_kind = {r["kind"]: r for r in rows}
    comment = by_kind["comment"]
    assert comment["payload"] == {"idea_id": m["T7"].ref, "as_desk": True}
    assert comment["from_user_id"] is None
    for kind in ("questions", "decision", "worth_revised", "detail_hidden_by_desk", "desk_merge"):
        assert by_kind[kind]["from_user_id"] is None, kind
        assert "as_desk" not in by_kind[kind]["payload"], kind  # already the desk's own kind
    assert by_kind["decision_reversed"]["from_user_id"] == p_id(conn, "manoj")
    assert by_kind["mention"]["from_user_id"] == p_id(conn, "naveen")  # a colleague, named as before
    assert "as_desk" not in by_kind["mention"]["payload"]

    items = inbox.items(conn, str(tanvi))["items"]
    seen = next(it for it in items if it["kind"] == "comment")
    assert seen["body"]["sender"] == "The review desk"
    dump = json.dumps(seen, ensure_ascii=False, default=str)
    assert "Harish" not in dump and "Venkatesan" not in dump and str(harish) not in dump, dump
    assert '"initials": "HV"' not in dump


# --- Founding Ones since the founding day (BLD-E073; lane G's walk of the release candidate, row 2) -----------------

# The Wall's order (`one_cards`: by induction time, then number) and the order of becoming a One (induction_no), by
# number, as the seed has always laid them out: Gopal, Aparna, Rekha, Dinesh, then Indira, Siddharth, Varun.
WALL_ORDER = [15, 2, 4, 8, 30, 21, 11]
INDUCTION_ORDER = [2, 4, 8, 11, 15, 21, 30]


def test_s_one_gap_seed_founding_ones_inducted_on_the_founding_day(office: Any) -> None:
    """S-ONE.layout/2 and /3, GAP-SEED, BLD-E073 (J-ONE/3b to /6b; the Wall's Ones in J-BROWSE): every founding One
    is inducted on the programme's founding day as the board draws it ("Founding One since 1 Nov 2026",
    reference/copy/OneDashboard.md:36), never a year before the programme existed and never after the load. Its
    number window keeps the live rule (30 days from becoming a One), so it is open "until 1 Dec 2026" (:40).
    Dinesh's dashboard reads his since line and still holds his glow-up. Accepted-idea Ones keep their days back,
    and every One keeps its number, tier, way in, Wall order and order of becoming a One."""
    from wall import ones as wall_ones

    conn = office
    founding_day = dt.datetime(2026, 11, 1, tzinfo=IST)
    assert club_seed.FOUNDING_DAY.astimezone(IST).date() == founding_day.date()
    accepted = {who: days for who, *_r, way_in, _k, _b, days in club_seed.ONES if way_in == "accepted_idea"}
    assert accepted == {"varun": 8, "siddharth": 10, "indira": 12}
    who_by_hash = {emp_id_hash(emp): who for who, emp in club_seed.EMP.items()}
    for now in LOADS:
        assert now >= dt.datetime(2026, 11, 2, tzinfo=IST)  # every load is on or after 2 Nov 2026
        club_seed.load(conn, now)
        rows = conn.execute(
            "SELECT o.number, o.tier, o.way_in, o.inducted_at, o.swap_until, o.induction_no, u.emp_id_hash "
            "FROM ones o JOIN users u ON u.id = o.user_id"
        ).fetchall()
        by_who = {who_by_hash[r["emp_id_hash"]]: r for r in rows}
        assert len(by_who) == len(rows) == 7
        for who, wanted, tier, way_in, *_rest in club_seed.ONES:
            r = by_who[who]
            assert (r["number"], r["tier"], r["way_in"]) == (wanted, tier, way_in), (now, who)
            assert r["swap_until"] == r["inducted_at"] + dt.timedelta(days=30), (now, who)
            if way_in == "founding":
                assert founding_day <= r["inducted_at"] < founding_day + dt.timedelta(days=1), (now, who)
                assert r["inducted_at"] <= now, (now, who)
            else:
                assert r["inducted_at"] == now - dt.timedelta(days=accepted[who]), (now, who)
        assert [c["number"] for c in wall_ones.one_cards(conn)] == WALL_ORDER, now
        assert [r["number"] for r in sorted(rows, key=lambda r: r["induction_no"])] == INDUCTION_ORDER, now

        dash = wall_ones.dashboard(conn, str(p_id(conn, "dinesh")), now)
        assert dash["headline"] == "You're No. 8"
        assert dash["since_line"] == "Tier 5, White heat. Founding One since 1 Nov 2026.", now
        window = dash["number_window"]
        assert window["open"] is True and window["until_label"] == "1 Dec 2026", now
        assert window["keep_label"] == (
            "Keep No. 8, or choose any free number from 1 to 999 until 1 Dec 2026. First come, first served. "
            "After that, it's yours."
        )
        moment = dash["tier_moment"]  # J-ONE/6b: his glow-up still waits to play once
        assert moment is not None and moment["line"] == "From Tier 4, Blaze to Tier 5, White heat", now
        assert moment["title"] == "No. 8, your spark is hotter"
        club_seed.remove(conn)


def test_s_one_gap_seed_founding_ones_never_after_a_load_before_the_founding_day() -> None:
    """S-ONE.layout/2, GAP-SEED, BLD-E073: a load before the founding day (or within the hour after it) inducts the
    founding Ones just before the load, in the same order, never after it; from an hour after it, on the founding
    day itself. Accepted-idea Ones count their days back from the load as before."""
    founding = [(who, when) for who, *_r, way_in, _k, _b, when in club_seed.ONES if way_in == "founding"]
    order = [who for who, _w in sorted(founding, key=lambda f: f[1])]
    assert order == ["gopal", "aparna", "rekha", "dinesh"]
    for now in (
        dt.datetime(2026, 10, 20, 9, 0, tzinfo=IST),
        club_seed.FOUNDING_DAY - dt.timedelta(minutes=1),
        club_seed.FOUNDING_DAY,
        club_seed.FOUNDING_DAY + dt.timedelta(minutes=30),
        club_seed.FOUNDING_DAY + dt.timedelta(hours=1),
        dt.datetime(2026, 11, 20, 22, 0, tzinfo=IST),
    ):
        at = {who: club_seed._inducted("founding", when, now) for who, when in founding}
        assert all(t < now for t in at.values()), now
        assert sorted(at, key=lambda who: at[who]) == order, now
        if now >= club_seed.FOUNDING_DAY + dt.timedelta(hours=1):
            assert min(at.values()) == club_seed.FOUNDING_DAY, now
        else:
            assert max(at.values()) > now - dt.timedelta(hours=1), now
        assert club_seed._inducted("accepted_idea", 8, now) == now - dt.timedelta(days=8)
