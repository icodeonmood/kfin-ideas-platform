"""The 1% Club synthetic seed (BLD-E006, bootstrap/club_seed.py) against a freshly migrated database: it fills every
table a screen of the pack reads (E-ENTITIES), with no one from the pack's demo cast (P-PRODUCT.cast), masked
words everywhere but the sharer's sealed copy (DEC-103), and it removes cleanly so `--reset` can load it again."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from bootstrap import club_seed
from identity.codes import emp_id_hash
from onepc import enums
from onepc.context import open_text

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
