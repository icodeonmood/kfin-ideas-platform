"""Public pages (B7): AT-B7-01 (the wall lists org-visible ideas by `neutral_summary`, names only with
`public_name_consent`, committee-only items never), AT-B7-02 (My ideas: stage in plain words and the next step
with a date), AT-B7-03 (the idea page timeline is the repo file's history; tags restored only in the mode the web
app chose), AT-B7-04 (the Garage showcase lists solutions; `wall.public` off hides the wall)."""

from __future__ import annotations

import datetime as dt
import json
import re
import secrets
from typing import Any

import pytest

from core import killswitch
from pii import vault
from repo_writer.render import existing_state
from repo_writer.writer import RepoWriter
from review import service
from tests import helpers
from tests.conftest import MATCH_TEXT as TEXT
from tests.test_b6_review import _user, desk  # noqa: F401  (the fixture is reused)
from views import idea_page, mine, wall

pytestmark = pytest.mark.stack


@pytest.fixture
def repo_settings(desk: Any, monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: F811
    """Point the views at this test's company repo."""
    settings = helpers.settings_for(desk["repo"], desk["database"])
    monkeypatch.setattr(idea_page, "get_settings", lambda: settings)
    return settings


def _write_repo(desk: Any) -> None:  # noqa: F811
    writer = RepoWriter(helpers.settings_for(desk["repo"], desk["database"]))
    assert writer.acquire()
    try:
        writer.run_once()
    finally:
        writer.release()


def _ids(cards: list[dict[str, Any]]) -> list[str | None]:
    return [c.get("idea_id") for c in cards]


def test_the_wall_shows_reviewed_org_ideas_and_names_only_with_consent(desk: Any) -> None:  # noqa: F811
    db = desk["db"]
    killswitch.clear_cache()
    assert desk["idea_id"] not in _ids(wall.wall(db)["recent"])  # not yet looked at by the desk

    service.act(db, desk["item"], desk["r1"], {"action": "decide"})
    w = wall.wall(db)
    card = next(c for c in w["recent"] if c["idea_id"] == desk["idea_id"])
    assert card["summary"] == "An idea to improve a KFintech process."  # the neutral summary, nothing else
    assert card["stage"] == "Reviewed" and card["colleagues"] == 1 and card["names"] == []
    assert TEXT not in json.dumps(w) and desk["code"] not in json.dumps(w)  # never their words or code

    mine.set_name_on_wall(db, desk["owner"], True)
    name = db.execute("SELECT name FROM users WHERE id = %s", (desk["owner"],)).fetchone()["name"]
    card = next(c for c in wall.wall(db)["recent"] if c["idea_id"] == desk["idea_id"])
    assert card["names"] == [name]
    assert db.execute("SELECT 1 FROM audit_log WHERE action = 'prefs.name_on_wall'").fetchone()

    db.execute("UPDATE ideas SET visibility = 'committee' WHERE idea_id = %s", (desk["idea_id"],))
    assert desk["idea_id"] not in _ids(wall.wall(db)["recent"])  # committee-only: never on the wall
    assert idea_page.page(db, desk["idea_id"], "public", "neutral", []) is None

    db.execute(
        "UPDATE ideas SET visibility = 'org', stage = 'declined' WHERE idea_id = %s", (desk["idea_id"],)
    )
    assert desk["idea_id"] not in _ids(wall.wall(db)["recent"])  # declined (or held as spam): never shown


def test_my_ideas_show_stage_next_step_and_date(desk: Any) -> None:  # noqa: F811
    db = desk["db"]
    review_due = db.execute(
        "SELECT due_at FROM sla_timers WHERE entity_id = %s AND stage = 'review'", (str(desk["item"]),)
    ).fetchone()["due_at"]
    expires = dt.datetime.now(dt.UTC) + dt.timedelta(days=20)
    draft = db.execute(
        "INSERT INTO ideas (contributor_code, stage, draft_expires_at) VALUES (%s, 'draft', %s) RETURNING id",
        (desk["code"], expires),
    ).fetchone()["id"]

    out = mine.my_ideas(db, desk["owner"])
    by_id = {i["idea_id"]: i for i in out["ideas"] if i["idea_id"]}
    shared = by_id[desk["idea_id"]]
    assert shared["stage"] == "With the review desk" and shared["next_step"] == "The review desk decides by"
    assert dt.datetime.fromisoformat(shared["due"]) == review_due
    assert shared["one_line"]  # their own words, restored for them
    d = next(i for i in out["ideas"] if i["id"] == str(draft))
    assert d["draft"] and dt.datetime.fromisoformat(d["due"]) == expires
    assert out["name_on_wall"] is False

    service.act(
        db, desk["item"], desk["r1"], {"action": "ask", "question": "Which branches see this the most?"}
    )
    asked = next(i for i in mine.my_ideas(db, desk["owner"])["ideas"] if i["idea_id"] == desk["idea_id"])
    info_due = db.execute(
        "SELECT due_at FROM sla_timers WHERE entity_id = %s AND stage = 'needs_info'", (desk["idea_id"],)
    ).fetchone()["due_at"]
    assert asked["stage"] == "The review desk has a question" and asked["next_step"] == "Please answer by"
    assert dt.datetime.fromisoformat(asked["due"]) == info_due

    # A colleague who teamed up sees the idea as everyone does: summary, stage, how they joined.
    joiner = _user(db, None)
    code = f"CTR-{secrets.token_hex(3)}"
    db.execute("INSERT INTO contributor_map (contributor_code, user_id) VALUES (%s, %s)", (code, joiner))
    db.execute(
        "INSERT INTO idea_links (idea_id, contributor_code, link_type, context_text) VALUES (%s, %s, 'joiner', %s)",
        (desk["idea_id"], code, "Same at the Jaipur branch"),
    )
    theirs = mine.my_ideas(db, joiner)
    assert theirs["ideas"] == [] and theirs["joined"][0]["how"] == "You joined"
    assert theirs["joined"][0]["summary"] == "An idea to improve a KFintech process."
    assert TEXT not in json.dumps(theirs)

    words = " ".join(" ".join(v) for v in mine.OWNER_WORDS.values()).lower()
    assert not re.search(r"duplicate|rejected|already solved", words)  # never shown to a submitter


def test_the_idea_page_timeline_is_the_repo_history(desk: Any, repo_settings: Any) -> None:  # noqa: F811
    db = desk["db"]
    service.act(db, desk["item"], desk["r1"], {"action": "decide"})
    _write_repo(desk)
    rel = db.execute("SELECT repo_path FROM ideas WHERE idea_id = %s", (desk["idea_id"],)).fetchone()[
        "repo_path"
    ]
    rows, _ = existing_state((desk["repo"] / rel).read_text(encoding="utf-8"))
    assert [r.event for r in rows][:1] == ["submitted"] and "reviewed" in [r.event for r in rows]

    full = idea_page.page(db, desk["idea_id"], "full", "real", [desk["code"]])
    assert full is not None and full["owner"] and full["uuid"] == desk["idea"]
    assert [(t["when"], t["event"]) for t in full["timeline"]] == [(r.when, r.event) for r in rows]
    assert full["timeline"][0]["by"] == "You" and full["timeline"][-1]["by"] == "The review desk"
    assert full["can_disagree"] is True

    public = idea_page.page(db, desk["idea_id"], "public", "neutral", [])
    assert public is not None and set(public) == {"view", "card", "timeline"}
    assert [t["event"] for t in public["timeline"]] == [
        r.event for r in rows if r.event in idea_page.PUBLIC_EVENTS
    ]
    assert all(set(t) == {"when", "event", "what"} for t in public["timeline"])  # no notes, no who
    assert TEXT not in json.dumps(public)


def test_tags_are_restored_only_in_the_mode_given(desk: Any, repo_settings: Any) -> None:  # noqa: F811
    db = desk["db"]
    tag = vault.assign(db, desk["idea_id"], "KFIN_EMPLOYEE", "Meera Iyer")  # synthetic
    db.execute(
        "UPDATE ideas SET canvas = jsonb_set(canvas, '{details}', to_jsonb(%s::text)) WHERE idea_id = %s",
        (f"Checked with {tag} at the branch desk.", desk["idea_id"]),
    )
    real = idea_page.page(db, desk["idea_id"], "full", "real", [desk["code"]])
    neutral = idea_page.page(db, desk["idea_id"], "full", "neutral", [])
    assert real is not None and neutral is not None
    assert real["card"]["details"] == "Checked with Meera Iyer at the branch desk."
    assert neutral["card"]["details"] == "Checked with a colleague at the branch desk."
    assert "uuid" not in neutral and "question" not in neutral  # owner-only parts


def test_the_showcase_lists_solutions_and_the_switch_hides_the_wall(desk: Any) -> None:  # noqa: F811
    db = desk["db"]
    items = wall.showcase(desk["repo"])
    sol = next(s for s in items if s["solution_id"] == "SOL-0004")
    assert sol["description"] == "Automated mandate checks" and sol["title"]
    killswitch.set_switch(db, "wall.public", "off", reason="Testing the wall switch", actor="REV-0001")
    killswitch.clear_cache()
    try:
        assert wall.wall(db) == {"paused": True}
    finally:
        killswitch.set_switch(db, "wall.public", "on", reason="Testing the wall switch", actor="REV-0001")
        killswitch.clear_cache()
