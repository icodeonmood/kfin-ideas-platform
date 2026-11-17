"""C-SIDEBAR.anatomy/4 and A-API.me: the sidebar's Your ideas (`ideapage.mine.shell_lists`, `GET
/internal/me/{id}/shell-lists`; the sidebar's drafts are lane C's L-DRAFT read) against a freshly migrated database
loaded with the synthetic 1% Club seed (bootstrap/club_seed.py; nobody from the pack's cast). One fixed "now" for the
seed and S-07's reads. Test names carry the module IDs they cover."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bootstrap import club_seed
from core import killswitch
from core.config import get_settings
from ideapage.mine import my_ideas, shell_lists
from tests import helpers

NOW = dt.datetime(2026, 11, 16, 6, 0, tzinfo=dt.UTC)  # Monday 16 November, 11:30 am in the office
TOKEN = "lane-e-test-token-0123456789abcdef"
# C-SIDEBAR.anatomy/4: warn for needs you, blue for active, grey (F-COLOR.status `neutral`) otherwise; by S-07's group.
DOT = {
    "needs_you": "warn",
    "with_review_desk": "blue",
    "picked_and_building": "blue",
    "shipped": "neutral",
    "closed": "neutral",
}


@pytest.fixture
def club(db: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    monkeypatch.setenv("COMPANY_REPO_PATH", str(helpers.SEED))
    get_settings.cache_clear()
    killswitch.clear_cache()
    made = club_seed.load(db, NOW)
    people = {
        str(r["name"]).split()[0].lower(): str(r["id"]) for r in db.execute("SELECT id, name FROM users")
    }
    yield {"conn": db, "m": made, "p": people}
    club_seed.remove(db)  # the seed's people and all that is theirs, so no rows outlive the test
    get_settings.cache_clear()
    killswitch.clear_cache()


@pytest.fixture
def client(club: dict[str, Any], test_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", helpers.db_url(test_database))
    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    from api.app import app

    yield TestClient(app, headers={"X-Internal-Token": TOKEN})
    get_settings.cache_clear()


def lists(club: dict[str, Any], who: str) -> dict[str, Any]:
    return shell_lists(club["conn"], club["p"][who])


def first_in_my_ideas(club: dict[str, Any], who: str) -> list[dict[str, Any]]:
    """What S-07 lists first in its default view (Yours, All, Latest activity): its first three shared ideas."""
    items = my_ideas(club["conn"], club["p"][who], {}, now=NOW)["items"]
    return [i for i in items if i["group"] != "drafts"][:3]


def ref(club: dict[str, Any], key: str) -> str:
    return str(club["m"][key].ref)


def owner_of(club: dict[str, Any], key: str) -> str:
    """The users.id of whoever shared an idea, by its row id or reference."""
    row = (
        club["conn"]
        .execute(
            "SELECT m.user_id FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code "
            "WHERE i.idea_id = %s OR i.id::text = %s",
            (key, key),
        )
        .fetchone()
    )
    return str(row["user_id"])


def test_c_sidebar_anatomy_4_a_api_me_tanvi_gets_her_three_ideas_in_order(club: dict[str, Any]) -> None:
    out = lists(club, "tanvi")
    assert set(out) == {"ideas"}  # ideas only: the sidebar's drafts are lane C's L-DRAFT read
    # Latest activity first: T4 shared minutes ago, T5 shared a day ago, then T10 withdrawn a day ago (T6's
    # questions went the same minute; S-07 breaks the tie on the later share, T10's).
    assert out["ideas"] == [
        {
            "id": ref(club, "T4"),
            "title": "Change of address forms come back for one missing tick",
            "status_dot": "blue",
            "status_label": "Checking",
        },
        {
            "id": ref(club, "T5"),
            "title": "Redemption status is not visible to the branch",
            "status_dot": "blue",
            "status_label": "With the review desk",
        },
        {
            "id": ref(club, "T10"),
            "title": "Token slips at the branch run out by noon",
            "status_dot": "neutral",
            "status_label": "Withdrawn",
        },
    ]


def test_c_sidebar_anatomy_4_a_api_me_lists_match_what_my_ideas_lists_first(club: dict[str, Any]) -> None:
    """The sidebar and My ideas never disagree: the same rows, order, titles and links, the dot by S-07's group and
    the dot's words from S-07's pill (F-A11Y.rules/4: never colour alone), for every seeded person."""
    checked = 0
    for who in club["p"]:
        out = lists(club, who)
        ideas = first_in_my_ideas(club, who)
        assert [(i["id"], i["title"]) for i in out["ideas"]] == [(i["id"], i["title"]) for i in ideas], who
        for got, row in zip(out["ideas"], ideas, strict=True):
            assert row["href"].split("?")[0] == f"/ideas/{got['id']}"
            assert got["status_dot"] == DOT[row["group"]], (who, got["id"])
            assert got["status_label"], (who, got["id"])
            assert got["status_label"] == row["pill"]["label"], (who, got["id"])
        checked += bool(out["ideas"])
    assert checked >= 15  # the seed's sharers, not an empty pass


def test_c_sidebar_anatomy_4_a_api_me_needs_you_gets_the_warn_dot(club: dict[str, Any]) -> None:
    """S-07's needs-you reading: an open question set on an idea the desk has, or `needs_you` as lane B stores it."""
    conn, t6 = club["conn"], ref(club, "T6")
    # The review desk sends T6's questions again a few minutes ago, so it is the latest activity.
    conn.execute(
        "UPDATE question_sets SET sent_at = %s WHERE idea_uuid = %s AND state <> 'queued'",
        (NOW - dt.timedelta(minutes=5), club["m"]["T6"].uuid),
    )
    first = lists(club, "tanvi")["ideas"][0]
    assert first == {
        "id": t6,
        "title": "PAN mismatch holds new folios for days",
        "status_dot": "warn",
        "status_label": "Needs you",
    }
    ideas = first_in_my_ideas(club, "tanvi")
    assert ideas[0]["id"] == t6 and ideas[0]["group"] == "needs_you"
    assert ideas[0]["pill"]["label"] == "Needs you"
    conn.execute("UPDATE ideas SET status = 'needs_you' WHERE idea_id = %s", (t6,))
    assert lists(club, "tanvi")["ideas"][0] == first
    # Answered: back with the review desk, a blue dot.
    conn.execute("UPDATE ideas SET status = 'with_review_desk' WHERE idea_id = %s", (t6,))
    conn.execute(
        "UPDATE question_sets SET state = 'answered', answered_at = %s WHERE idea_uuid = %s AND state <> 'queued'",
        (NOW - dt.timedelta(minutes=5), club["m"]["T6"].uuid),
    )
    assert lists(club, "tanvi")["ideas"][0] == {
        **first,
        "status_dot": "blue",
        "status_label": "With the review desk",
    }


def test_c_sidebar_anatomy_4_a_api_me_someone_with_no_ideas_gets_an_empty_list(club: dict[str, Any]) -> None:
    empty: dict[str, list[Any]] = {"ideas": []}
    assert lists(club, "harish") == empty  # the review desk, with nothing of his own
    assert my_ideas(club["conn"], club["p"]["harish"], {}, now=NOW)["items"] == []
    conn = club["conn"]
    assert shell_lists(conn, str(uuid.uuid4())) == empty  # unknown
    assert shell_lists(conn, "not-a-person") == empty  # not an id at all
    conn.execute("UPDATE users SET active = false WHERE id = %s", (club["p"]["tanvi"],))
    assert lists(club, "tanvi") == empty  # inactive


def test_c_sidebar_anatomy_4_a_api_me_never_lists_another_persons_ideas(club: dict[str, Any]) -> None:
    """Only the person's own ideas: never a colleague's, and not the ideas they teamed up on."""
    teamed = {
        i["id"] for i in my_ideas(club["conn"], club["p"]["tanvi"], {"list": "teamed"}, now=NOW)["items"]
    }
    assert teamed  # Tanvi is on two crews
    for who, user_id in club["p"].items():
        out = lists(club, who)
        for row in out["ideas"]:
            assert owner_of(club, row["id"]) == user_id, (who, row["id"])
    tanvi = lists(club, "tanvi")
    assert not teamed & {i["id"] for i in tanvi["ideas"]}
    rekha = lists(club, "rekha")
    assert rekha["ideas"] and not {i["id"] for i in rekha["ideas"]} & {
        ref(club, k) for k in club["m"] if k.startswith("T") and club["m"][k].ref
    }


def test_a_api_me_shell_lists_route_reads_the_lists_without_caching(
    club: dict[str, Any], client: TestClient
) -> None:
    tanvi = club["p"]["tanvi"]
    got = client.get(f"/internal/me/{tanvi}/shell-lists")
    assert got.status_code == 200 and got.headers["cache-control"] == "no-store"
    body = got.json()
    assert set(body) == {"ideas"}  # no drafts: lane C's L-DRAFT read fills those
    assert len(body["ideas"]) == 3 and all(
        set(i) == {"id", "title", "status_dot", "status_label"} and i["status_label"] for i in body["ideas"]
    )
    for who in (str(uuid.uuid4()), "not-a-person", club["p"]["harish"]):
        empty = client.get(f"/internal/me/{who}/shell-lists")
        assert empty.status_code == 200 and empty.json() == {"ideas": []}
    assert TestClient(client.app).get(f"/internal/me/{tanvi}/shell-lists").status_code == 401
