"""The Wall from the database (S-WALL, L-WALL.kindling, L-WALL.justin, V-ACC.browse/3, /4, /6, DEC-104): stages and
counts, the four sorts with ties to the newest, paging by five, "Opened this week" without the sharer or reviewers,
the kind chips, names only where the sharer allows, never their own words, and the one "on the Wall" hook."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from core import killswitch
from core.db import Conn
from tests import wall_fixtures as f
from wall import ember, kindling

pytestmark = pytest.mark.stack


@pytest.fixture
def wall_db(db: Conn) -> Iterator[Conn]:
    killswitch.clear_cache()
    kindling.clear_cache()
    yield db
    f.leave_clean(db)
    kindling.clear_cache()


@pytest.fixture
def desk(wall_db: Conn) -> dict[str, Any]:
    """Seven ideas with the review desk, each with a different shape, and a reviewer."""
    db = wall_db
    p = {k: f.person(db, n) for k, n in (("ishaan", "Ishaan Bhatt"), ("rhea", "Rhea Dutta"), ("kabir", "Kabir Sethi"),
                                          ("nisha", "Nisha Rawat"), ("omkar", "Omkar Joshi"), ("yamini", "Yamini Kapoor"))}  # fmt: skip
    p["reviewer"] = f.person(db, "Lalit Ahuja", roles=("reviewer",))
    ideas = {
        "a": f.idea(db, p["ishaan"], title="Remind investors before a mandate expires", shared_at=f.ago(hours=2)),
        "b": f.idea(db, p["rhea"], title="Let branches book a courier pickup", kind="fix", shared_at=f.ago(hours=5)),
        "c": f.idea(db, p["kabir"], title="Show the cut-off time on every purchase screen", shared_at=f.ago(days=1)),
        "d": f.idea(db, p["nisha"], title="A paid data feed of SIP trends", kind="business_idea",
                    area="New business", shared_at=f.ago(days=1, hours=3)),
        "e": f.idea(db, p["omkar"], title="Pre-fill the nominee form", status="needs_you", shared_at=f.ago(days=2)),
        "f": f.idea(db, p["yamini"], title="Explain rejection codes in plain words", shared_at=f.ago(days=3)),
        "g": f.idea(db, p["ishaan"], title="Track couriered forms", shared_at=f.ago(days=4)),
    }  # fmt: skip
    return {"p": p, "i": ideas}


def _ids(rows: list[dict[str, Any]]) -> list[str]:
    return [r["id"] for r in rows]


def test_S_WALL_justin_1_lists_only_ideas_with_the_review_desk_newest_first(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    i = desk["i"]
    f.idea(wall_db, desk["p"]["rhea"], title="Already picked one", status="picked")
    f.idea(wall_db, desk["p"]["rhea"], title="Still a draft", status="draft")
    out = kindling.just_in(wall_db, limit=50, now=f.NOW)
    assert _ids(out["items"]) == [i[k]["idea_id"] for k in "abcdefg"]
    assert out["total"] == 7 and out["sort"] == "newest"
    assert out["items"][0]["shared_label"] == "2h ago" and out["items"][2]["shared_label"] == "Yesterday"
    assert out["items"][4]["shared_label"] == "2 days ago"


def test_V_ACC_browse_3_just_in_pages_by_five_then_shows_the_rest(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    first = kindling.just_in(wall_db, now=f.NOW)
    assert len(first["items"]) == 5 and first["next"] == "5" and first["total"] == 7
    assert first["sub"] == "7 with the review desk"
    assert first["more"] == 2 and first["more_label"] == "Show 2 more"
    rest = kindling.just_in(wall_db, offset=5, now=f.NOW)
    assert len(rest["items"]) == 2 and rest["next"] is None
    assert rest["more"] == 0 and rest["more_label"] == "Show fewer"


def test_V_ACC_browse_3_twelve_with_the_desk_show_5_more_then_2_more_then_fewer(wall_db: Conn) -> None:
    db = wall_db
    who = f.person(db, "Tanvi Mehra")
    for n in range(12):
        f.idea(db, who, title=f"Idea number {n}", shared_at=f.ago(hours=n + 1))
    labels = [kindling.just_in(db, offset=o, now=f.NOW)["more_label"] for o in (0, 5, 10)]
    assert labels == ["Show 5 more", "Show 2 more", "Show fewer"]
    # The phone asks for three at a time (L-WALL.justin/5): "Show 3 more".
    assert kindling.just_in(db, limit=3, now=f.NOW)["more_label"] == "Show 3 more"
    assert kindling.just_in(db, limit=50, now=f.NOW)["more_label"] is None  # everything fits: no button
    assert kindling.just_in(db, now=f.NOW)["sub"] == "12 with the review desk"


def test_S_WALL_phone_each_row_carries_the_figure_for_the_current_sort(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    """L-WALL.justin/5: "Opened by 233 this week", "Shared 2h ago", "3 on the crew", "1 One on the crew"."""
    db, p, i = wall_db, desk["p"], desk["i"]
    for viewer in ("rhea", "kabir"):
        f.opened(db, i["a"], p[viewer])
    f.crew(db, i["a"], p["nisha"])
    f.one(db, p["nisha"], number=21)

    def line(sort: str, ref: str) -> str:
        rows = kindling.just_in(db, sort=sort, limit=50, now=f.NOW)["items"]
        return str(next(r["figure_label"] for r in rows if r["id"] == ref))

    a, c = i["a"]["idea_id"], i["c"]["idea_id"]
    assert (line("popular", a), line("newest", a), line("crew", a), line("ones", a)) == (
        "Opened by 2 this week", "Shared 2h ago", "2 on the crew", "1 One on the crew",
    )  # fmt: skip
    assert line("newest", c) == "Shared yesterday" and line("ones", c) == "0 Ones on the crew"


def test_J_BROWSE_5_a_Wall_row_opens_the_idea_with_its_way_back_to_the_Wall(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    """S-WALL.rules/4: the title opens the idea page; it says "Back to the Wall" and returns to the same sort and
    kind chip (the idea page reads `from` and `back`)."""
    db, i = wall_db, desk["i"]
    a = i["a"]["idea_id"]
    plain = kindling.just_in(db, limit=50, now=f.NOW)["items"][0]
    assert plain["id"] == a and plain["to"] == f"/ideas/{a}?from=wall"
    assert plain["meta"] == "Problem, Investor service"
    sorted_ = next(
        r for r in kindling.just_in(db, kind="problem", sort="popular", now=f.NOW)["items"] if r["id"] == a
    )
    assert sorted_["to"] == f"/ideas/{a}?from=wall&back=%2Fwall%3Fkind%3Dproblem%26sort%3Dpopular"


def test_S_WALL_justin_2_sorts_Popular_by_distinct_openers_in_7_days(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    """L-WALL.justin/4: distinct colleagues in the last 7 days; not the sharer, not a reviewer, not twice."""
    db, p, i = wall_db, desk["p"], desk["i"]
    for viewer in ("rhea", "kabir", "nisha"):
        f.opened(db, i["g"], p[viewer])
    f.opened(db, i["g"], p["rhea"], days_ago=2)  # the same colleague on another day counts once
    f.opened(db, i["g"], p["ishaan"])  # the sharer
    f.opened(db, i["g"], p["reviewer"])  # a reviewer
    f.opened(db, i["c"], p["rhea"])
    f.opened(db, i["c"], p["omkar"], days_ago=8)  # outside the 7 days
    out = kindling.just_in(db, sort="popular", limit=50, now=f.NOW)
    figures = {r["id"]: r["opened_7d"] for r in out["items"]}
    assert figures[i["g"]["idea_id"]] == 3 and figures[i["c"]["idea_id"]] == 1
    assert _ids(out["items"])[:2] == [i["g"]["idea_id"], i["c"]["idea_id"]]
    # Ties (none opened) go to the newest (L-WALL.justin/3, V-ACC.browse/4).
    assert _ids(out["items"])[2:] == [i[k]["idea_id"] for k in "abdef"]


def test_S_WALL_justin_3_sorts_by_crew_size_and_by_Ones_on_the_crew(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    db, i = wall_db, desk["i"]
    farah, arvind, sunil = (f.person(db, n) for n in ("Farah Qureshi", "Arvind Pillay", "Sunil Bakshi"))
    for member in (farah, arvind, sunil):
        f.crew(db, i["f"], member)
    f.crew(db, i["e"], farah)
    f.one(db, farah, number=17)
    f.one(db, arvind, number=9, tier=5)
    by_crew = kindling.just_in(db, sort="crew", limit=50, now=f.NOW)
    assert _ids(by_crew["items"])[:2] == [i["f"]["idea_id"], i["e"]["idea_id"]]
    assert {r["id"]: r["crew_count"] for r in by_crew["items"]}[i["f"]["idea_id"]] == 4
    by_ones = kindling.just_in(db, sort="ones", limit=50, now=f.NOW)
    rows = {r["id"]: r for r in by_ones["items"]}
    assert rows[i["f"]["idea_id"]]["ones_count"] == 2 and rows[i["e"]["idea_id"]]["ones_count"] == 1
    assert _ids(by_ones["items"])[:3] == [i["f"]["idea_id"], i["e"]["idea_id"], i["a"]["idea_id"]]
    # Every row carries all four figures whatever the sort, so rows can be matched (S-WALL.rules/2).
    assert set(by_ones["items"][0]) >= {"opened_7d", "shared_at", "crew_count", "ones_count"}


def test_V_ACC_browse_6_a_kind_chip_filters_Kindling_and_Just_in_and_the_counts_follow(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    db, p = wall_db, desk["p"]
    f.idea(db, p["kabir"], title="Picked problem", status="picked")
    f.idea(db, p["kabir"], title="Picked business idea", status="picked", kind="business_idea")
    problems = kindling.just_in(db, kind="problem", limit=50, now=f.NOW)
    assert problems["total"] == 5 and {r["kind"] for r in problems["items"]} == {"problem"}
    assert problems["counts"] == {"all": 7, "problem": 5, "fix": 1, "business_idea": 1}
    stages = {s["stage"]: s for s in kindling.kindling(db, "problem")}
    assert stages["picked"]["count"] == 1 and [x["title"] for x in stages["picked"]["items"]] == [
        "Picked problem"
    ]
    assert kindling.kindling(db, None)[0]["count"] == 2


def test_S_WALL_kindling_three_stages_with_counts_and_up_to_three_ideas(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    db, p = wall_db, desk["p"]
    for n in range(4):
        f.idea(
            db, p["rhea"], title=f"Being built number {n}", status="being_built", shared_at=f.ago(days=10 - n)
        )
    shipped = f.idea(db, p["kabir"], title="Shipped fix", status="shipped")
    f.idea(db, p["kabir"], title="Problem with a fix attached", status="shipped")
    db.execute("INSERT INTO idea_fix (idea_uuid, how) VALUES ((SELECT id FROM ideas WHERE title = %s), 'x')",
               ("Problem with a fix attached",))  # fmt: skip
    f.crew(db, shipped, p["nisha"])
    out = kindling.kindling(db)
    assert [s["stage"] for s in out] == ["picked", "being_built", "shipped"]
    built = out[1]
    assert built["count"] == 4 and len(built["items"]) == 3
    assert [x["title"] for x in built["items"]] == [
        "Being built number 3",
        "Being built number 2",
        "Being built number 1",
    ]
    kinds = {x["title"]: x for x in out[2]["items"]}
    # E-ENUMS.kind OPEN default: a problem shared with a fix shows as a Fix on the Wall.
    assert kinds["Problem with a fix attached"]["kind"] == "fix"
    assert kinds["Shipped fix"]["crew_count"] == 2
    # "Problem, Distributor experience, 4 colleagues on it" (S-WALL.kindling)
    assert kinds["Shipped fix"]["meta"] == "Problem, Investor service, 2 colleagues on it"
    assert kinds["Problem with a fix attached"]["meta"] == "Fix, Investor service, 1 colleague on it"
    assert kinds["Shipped fix"]["to"].startswith(f"/ideas/{shipped['idea_id']}?from=wall")


def test_DEC_104_hides_the_name_when_the_sharer_turned_it_off(wall_db: Conn, desk: dict[str, Any]) -> None:
    db = wall_db
    hidden = f.person(db, "Varsha Pandey", show_name=False)
    shown = f.person(db, "Gaurav Saini")  # no row yet: names show by default (DEC-104)
    f.idea(db, hidden, title="Hidden sharer's idea", shared_at=f.ago(hours=1))
    f.idea(db, shown, title="Named sharer's idea", shared_at=f.ago(hours=1.5))
    rows = {r["title"]: r for r in kindling.just_in(db, limit=50, now=f.NOW)["items"]}
    assert rows["Hidden sharer's idea"]["sharer"] is None
    assert rows["Named sharer's idea"]["sharer"]["name"] == "Gaurav Saini"
    assert rows["Named sharer's idea"]["sharer"]["initials"] == "GS"


def test_P_PRODUCT_privacy_the_Wall_carries_the_short_summary_never_own_words_or_points(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    out = kindling.just_in(wall_db, limit=50, now=f.NOW)
    row = out["items"][0]
    assert set(row) == {
        "id", "title", "summary", "kind", "area", "crew_count", "sharer", "shared_at", "shared_label",
        "opened_7d", "ones_count", "meta", "figure_label", "to",
    }  # fmt: skip
    assert "points" not in str(out) and "own_words" not in str(out)


def test_L_WALL_a_title_that_still_holds_a_detail_or_a_tag_is_left_out(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    db = wall_db
    f.idea(db, desk["p"]["rhea"], title="Call the investor on 9876543210 today", shared_at=f.ago(hours=1))
    f.idea(db, desk["p"]["rhea"], title="Folio [[CLIENT_FOLIO_1]] keeps bouncing", shared_at=f.ago(hours=1))
    titles = [r["title"] for r in kindling.just_in(db, limit=50, now=f.NOW)["items"]]
    assert not any("9876543210" in t or "[[" in t for t in titles)


def test_DEC_106_the_on_the_Wall_hook_keeps_restricted_and_merged_ideas_off(
    wall_db: Conn, desk: dict[str, Any]
) -> None:
    db, i = wall_db, desk["i"]
    db.execute("UPDATE ideas SET visibility = 'committee' WHERE id = %s", (i["a"]["id"],))
    db.execute("UPDATE ideas SET merged_into = %s WHERE id = %s", (i["c"]["id"], i["b"]["id"]))
    ids = _ids(kindling.just_in(db, limit=50, now=f.NOW)["items"])
    assert i["a"]["idea_id"] not in ids and i["b"]["idea_id"] not in ids and len(ids) == 5


def test_A_API_wall_refuses_an_unknown_sort_kind_or_page(wall_db: Conn) -> None:
    from wall.common import Refused

    for kwargs in ({"sort": "loudest"}, {"kind": "rumour"}, {"limit": 0}, {"limit": 51}, {"offset": -1}):
        with pytest.raises(Refused):
            kindling.just_in(wall_db, now=f.NOW, **kwargs)


def test_L_WALL_ember_shows_the_latest_issue_and_the_next_as_coming_soon(wall_db: Conn) -> None:
    db = wall_db
    assert ember.ember(db, f.NOW) == [
        {"number": 1, "month": "November 2026", "headline": None, "items": [], "state": "coming_soon"}
    ]
    admin = f.person(db, "Mehul Desai", roles=("admin",))
    content = {"headline": "The 1% Club is open, and the first Ones are named.",
               "items": ["How a stuck SIP registration became an idea.", "620 hours a month saved.",
                         "Kindling to watch."]}  # fmt: skip
    from psycopg.types.json import Jsonb

    issue = db.execute(
        "INSERT INTO ember_issues (month, state, content, created_by, sent_by, sent_at) "
        "VALUES ('2026-11-01', 'sent', %s, %s, %s, %s) RETURNING id",
        (Jsonb(content), admin["id"], admin["id"], f.NOW),
    ).fetchone()
    db.execute("INSERT INTO ember_issues (month, content) VALUES ('2026-12-01', %s)",
               (Jsonb({"headline": "Shipped in the first month, and the next Ones."}),))  # fmt: skip
    latest, soon = ember.ember(db, f.NOW)
    assert latest == {"number": 1, "month": "November 2026", "headline": content["headline"],
                      "items": content["items"], "state": "latest", "to": f"/ember/{issue['id']}"}  # fmt: skip
    assert soon["number"] == 2 and soon["month"] == "December 2026" and soon["state"] == "coming_soon"
    assert soon["headline"] == "Shipped in the first month, and the next Ones."
