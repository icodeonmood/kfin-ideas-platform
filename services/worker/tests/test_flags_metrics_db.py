"""P-DECISIONS.experiments, the deciding metrics (BLD-C174, BLD-C176): `flag_events` keeps codes only and each S1 step
once per draft; `flag_s1_metrics`, `flag_s2_metrics` and `flag_s3_metrics` count per variant from exposures, drafts and events, never a
person, an idea or a word. Synthetic people and drafts only; the test's own rows are counted before and after and
removed at the end (rule 14)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

pytestmark = pytest.mark.stack


def _person(db: Any, n: int) -> tuple[str, str]:
    uid = db.execute(
        "INSERT INTO users (emp_id_hash, name, email) VALUES (%s, 'Synthetic Flagger', %s) RETURNING id",
        (f"h-flags-{n}", f"flagger{n}@kfintech.example"),
    ).fetchone()["id"]
    code = f"CTR-f1a9{n:02x}"
    db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, uid))
    return str(uid), code


def _draft(db: Any, code: str, *, device: str, shared: bool, parts: list[str]) -> str:
    idea = str(uuid.uuid4())
    db.execute(
        "INSERT INTO ideas (id, contributor_code, created_at, shared_at) "
        "VALUES (%s, %s, now() - interval '20 minutes', CASE WHEN %s THEN now() ELSE NULL END)",
        (idea, code, shared),
    )
    db.execute(
        "INSERT INTO idea_messages (idea_uuid, seq, via, device, text_encrypted, char_count) "
        "VALUES (%s, 1, 'typed', %s, %s, 40)",
        (idea, device, b"sealed-synthetic"),
    )
    for key in parts:
        db.execute("INSERT INTO idea_parts (idea_uuid, key, state) VALUES (%s, %s, 'filled')", (idea, key))
    return idea


def _event(db: Any, flag: str, uid: str, variant: str, draft: str | None, event: str, outcome: str) -> None:
    screen = {"s1": "S-04B", "s2": "S-05"}.get(flag, "S-04")
    db.execute(
        "INSERT INTO flag_events (flag_key, user_id, variant, draft_id, screen, event, outcome) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (flag, uid, variant, draft, screen, event, outcome),
    )


@pytest.fixture
def people(db: Any) -> Iterator[tuple[Any, list[tuple[str, str]]]]:
    before = db.execute("SELECT count(*) AS n FROM flag_events").fetchone()["n"]
    made = [_person(db, n) for n in (1, 2)]
    yield db, made
    ids = [uid for uid, _ in made]
    db.execute("DELETE FROM flag_events WHERE user_id = ANY(%s::uuid[])", (ids,))
    db.execute("DELETE FROM flag_exposures WHERE user_id = ANY(%s::uuid[])", (ids,))
    db.execute("DELETE FROM flag_assignments WHERE user_id = ANY(%s::uuid[])", (ids,))
    db.execute("DELETE FROM ideas WHERE contributor_code = ANY(%s)", ([c for _, c in made],))
    db.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", (ids,))
    assert db.execute("SELECT count(*) AS n FROM flag_events").fetchone()["n"] == before


def test_p_decisions_experiments_flag_events_keep_codes_and_each_s1_step_once(people: Any) -> None:
    db, [(uid, code), _] = people
    draft = _draft(db, code, device="laptop", shared=False, parts=["title"])
    _event(db, "s1", uid, "alternative", draft, "s1.often", "answered")
    with pytest.raises(psycopg.errors.UniqueViolation):
        _event(db, "s1", uid, "alternative", draft, "s1.often", "skipped")
    for flag, event, outcome in (
        ("s2", "s1.often", "answered"),  # an event of another flag
        ("s3", "s3.listen", "Said: the SMS only gives a code"),  # words, never
        ("s3", "s3 listen", "started"),
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            _event(db, flag, uid, "default", None, event, outcome)
    # S2's events and S3's notes name a draft, and are kept once per draft and outcome: a flood adds nothing
    for flag, event, outcome in (("s2", "s2.check", "opened"), ("s3", "s3.note", "as_heard")):
        with pytest.raises(psycopg.errors.CheckViolation):
            _event(db, flag, uid, "default", None, event, outcome)
        _event(db, flag, uid, "default", draft, event, outcome)
        with pytest.raises(psycopg.errors.UniqueViolation):
            _event(db, flag, uid, "default", draft, event, outcome)
    _event(
        db, "s3", uid, "default", draft, "s3.note", "corrected"
    )  # another outcome for the same draft is kept
    # S3's listening is not per draft: each page that listened counts once per person in the view
    _event(db, "s3", uid, "default", None, "s3.listen", "started")
    _event(db, "s3", uid, "default", None, "s3.listen", "started")
    assert db.execute("SELECT count(*) AS n FROM flag_events WHERE user_id = %s", (uid,)).fetchone()["n"] == 6


def test_p_decisions_experiments_s1_and_s3_metrics_per_variant(people: Any) -> None:
    db, [(alt, alt_code), (dflt, dflt_code)] = people
    for flag in ("s1", "s3"):
        db.execute(
            "INSERT INTO flag_exposures (flag_key, user_id, variant, screen, at) VALUES "
            "(%s, %s, 'alternative', 'S-04', now() - interval '1 hour'), "
            "(%s, %s, 'default', 'S-04', now() - interval '1 hour')",
            (flag, alt, flag, dflt),
        )
    # alternative: one phone draft, not shared, interview answered once and skipped twice; two notes, one corrected
    a = _draft(db, alt_code, device="phone", shared=False, parts=["title", "often", "area"])
    for event, outcome in (
        ("s1.start", "started"),
        ("s1.often", "answered"),
        ("s1.who", "skipped"),
        ("s1.size", "skipped"),
        ("s1.end", "finished"),
    ):
        _event(db, "s1", alt, "alternative", a, event, outcome)
    _event(db, "s3", alt, "alternative", a, "s3.listen", "started")
    _event(db, "s3", alt, "alternative", None, "s3.listen", "started")  # a second page: the same person
    _event(db, "s3", alt, "alternative", a, "s3.note", "corrected")
    a2 = _draft(db, alt_code, device="phone", shared=True, parts=["title"])
    _event(db, "s3", alt, "alternative", a2, "s3.note", "as_heard")
    # default: two laptop drafts, one shared with every part
    _draft(db, dflt_code, device="laptop", shared=True, parts=["title", "often", "who", "value", "area"])
    _draft(db, dflt_code, device="laptop", shared=False, parts=[])

    s1 = {r["variant"]: r for r in db.execute("SELECT * FROM flag_s1_metrics").fetchall()}
    assert s1["alternative"]["people"] == 1
    assert s1["alternative"]["drafts_started"] == 2  # both phone drafts below
    assert s1["alternative"]["drafts_shared"] == 1
    assert float(s1["alternative"]["drop_off_rate"]) == 0.5
    assert float(s1["alternative"]["completeness_all_drafts"]) == 0.4
    assert (s1["alternative"]["questions_answered"], s1["alternative"]["questions_skipped"]) == (1, 2)
    assert (s1["alternative"]["interviews_started"], s1["alternative"]["interviews_finished"]) == (1, 1)
    assert s1["default"]["drafts_started"] == 2
    assert s1["default"]["drafts_shared"] == 1
    assert float(s1["default"]["drop_off_rate"]) == 0.5
    assert float(s1["default"]["completeness_when_shared"]) == 1.0
    assert 1100 <= float(s1["default"]["median_seconds_to_share"]) <= 1300
    assert s1["default"]["questions_answered"] == 0

    s3 = {r["variant"]: r for r in db.execute("SELECT * FROM flag_s3_metrics").fetchall()}
    assert s3["alternative"]["phone_drafts_started"] == 2
    assert float(s3["alternative"]["phone_completion_rate"]) == 0.5
    assert (s3["alternative"]["drafts_with_notes"], s3["alternative"]["drafts_corrected"]) == (2, 1)
    assert float(s3["alternative"]["correction_rate"]) == 0.5
    assert s3["alternative"]["people_listened_at_once"] == 1
    assert s3["default"]["phone_drafts_started"] == 0  # laptop drafts are not the phone's
    assert s3["default"]["phone_completion_rate"] is None

    # Counts and rates only: no column names a person, an idea or a word
    for view in ("flag_s1_metrics", "flag_s2_metrics", "flag_s3_metrics"):
        cols = {
            r["column_name"]
            for r in db.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (view,)
            ).fetchall()
        }
        assert not cols & {"user_id", "draft_id", "idea_id", "id", "text", "title", "contributor_code"}


def test_p_decisions_experiments_s2_metrics_duplicates_to_the_desk_and_completion(people: Any) -> None:
    db, [(alt, alt_code), (dflt, dflt_code)] = people
    db.execute(
        "INSERT INTO flag_exposures (flag_key, user_id, variant, screen) VALUES "
        "('s2', %s, 'alternative', 'S-05'), ('s2', %s, 'default', 'S-05')",
        (alt, dflt),
    )
    other = _draft(db, dflt_code, device="laptop", shared=True, parts=["title"])  # the idea matched against
    # alternative: shown the comparison first, asked to merge; not shared
    a = _draft(db, alt_code, device="laptop", shared=False, parts=["title"])
    _event(db, "s2", alt, "alternative", a, "s2.check", "opened")
    _event(db, "s2", alt, "alternative", a, "s2.check", "close_match")
    _event(db, "s2", alt, "alternative", a, "s2.compare", "shown")
    _event(db, "s2", alt, "alternative", a, "s2.compare", "merge_asked")
    # default: the same close match, carried on and shared on its own (a duplicate reaching the desk)
    d = _draft(db, dflt_code, device="laptop", shared=True, parts=["title"])
    _event(db, "s2", dflt, "default", d, "s2.check", "opened")
    _event(db, "s2", dflt, "default", d, "s2.check", "close_match")
    plain = _draft(
        db, dflt_code, device="laptop", shared=False, parts=["title"]
    )  # no close match: not exposed
    _event(db, "s2", dflt, "default", plain, "s2.check", "opened")
    db.execute(
        "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason, outcome) VALUES "
        "(%s, %s, 'close', 'Close match: same SMS, same calls', 'merge_asked'), "
        "(%s, %s, 'close', 'Close match: same SMS, same calls', NULL)",
        (a, other, d, other),
    )
    s2 = {r["variant"]: r for r in db.execute("SELECT * FROM flag_s2_metrics").fetchall()}
    assert (s2["alternative"]["drafts_checked"], s2["alternative"]["drafts_with_close_match"]) == (1, 1)
    assert s2["alternative"]["close_match_merged"] == 1
    assert s2["alternative"]["duplicates_to_desk"] == 0
    assert (s2["alternative"]["compare_shown"], s2["alternative"]["compare_merge_asked"]) == (1, 1)
    assert (s2["default"]["drafts_checked"], s2["default"]["drafts_with_close_match"]) == (2, 1)
    assert s2["default"]["drafts_shared"] == 1
    assert float(s2["default"]["completion_rate"]) == 1.0
    assert s2["default"]["duplicates_to_desk"] == 1
    assert float(s2["default"]["duplicate_rate"]) == 1.0
    assert s2["default"]["compare_shown"] == 0
