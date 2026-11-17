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


def test_e_entities_seed_fills_every_screen_and_removes_cleanly(db: Any) -> None:
    conn = db
    club_seed.load(conn)

    names = _set(conn, "SELECT name FROM users")
    assert not names & PACK_CAST
    assert not {n.split()[0] for n in names} & {c.split()[0] for c in PACK_CAST}
    assert _set(conn, "SELECT email FROM users") <= {club_seed._email(n) for n in names}

    stored = set(enums.IDEA_STATUS) - {"needs_you"}  # needs_you is the sharer's view, never stored
    assert _set(conn, "SELECT status FROM ideas") == stored
    assert _set(conn, "SELECT kind FROM notifications WHERE kind IS NOT NULL") == set(enums.INBOX_KIND)
    assert _set(conn, "SELECT state FROM decision_windows") == set(enums.values("window_state"))
    assert {"queued", "sent", "seen", "answered", "closed"} <= _set(conn, "SELECT state FROM question_sets")
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
