"""S-06, S-09, S-07 and L-SUBMIT.withdraw against a freshly migrated database loaded with the synthetic 1% Club seed
(bootstrap/club_seed.py; nobody from the pack's cast). One fixed "now" for the seed and the views, so dates are
stable. Test names carry the module IDs they cover."""

from __future__ import annotations

import datetime as dt
import json
import sys
import types
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from bootstrap import club_seed
from core import killswitch
from core.config import get_settings
from ideapage import read
from ideapage.colleague import Paused
from ideapage.mine import my_ideas, snippet
from ideapage.route import idea_view
from ideapage.withdraw import Refused, restore, withdraw
from ideapage.words import IST, day
from tests import helpers

NOW = dt.datetime(2026, 11, 16, 6, 0, tzinfo=dt.UTC)  # Monday 16 November, 11:30 am in the office


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
    club_seed.remove(db)  # the seed's people and all that is theirs, so no rows outlive the test (rule 14)
    get_settings.cache_clear()
    killswitch.clear_cache()


def view(club: dict[str, Any], key: str, who: str, **kw: Any) -> dict[str, Any]:
    return idea_view(club["conn"], key, club["p"][who], now=NOW, **kw)


def ref(club: dict[str, Any], key: str) -> str:
    return str(club["m"][key].ref)


def nodes(v: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    return [(n["stage"], n["state"], n.get("detail")) for n in v["idea"]["stages"]]


# --- S-06: the sharer's page --------------------------------------------------------------------------------------


def test_s06_states_just_shared_shows_the_decide_by_date(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T5"), "tanvi")
    idea = club["conn"].execute("SELECT * FROM ideas WHERE idea_id = %s", (ref(club, "T5"),)).fetchone()
    page = v["page"]
    assert v["view"] == "sharer" and page["state"] == "just_shared" and page["state_label"] == "Just shared"
    assert page["pill"] == {"status": "with_review_desk", "label": "With the review desk", "variant": "blue"}
    assert page["card"]["lead"] == f"The review desk will look at it by {day(idea['decide_by'], NOW)}."
    assert page["card"]["rest"] == "We’ll tell you on Teams and by email when anything changes."
    assert page["window"]["open"] and page["window"]["line"].startswith(
        f"Open to changes until {day(idea['edit_closes_at'], NOW)}."
    )
    assert page["window"]["countdown"]["label"] == "2 days left"
    assert {"edit", "withdraw", "conversation"} <= set(page["actions"])
    assert page["actions"]["withdraw"]["confirm"]["confirm_label"] == "Withdraw it"
    assert page["breadcrumb"] == {"label": "My ideas", "to": "/my-ideas", "current": ref(club, "T5")}
    assert nodes(v)[2] == ("reviewed", "now", f"By {day(idea['decide_by'], NOW)}")
    # BLD-E012: no question set is open, so the card is lane E's own and nothing is composed from lane B's.
    assert v["idea"]["has_open_questions"] is False and "card_from" not in page


def test_s06_states_questions_from_the_review_desk_leaves_the_card_to_lane_b(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T6"), "tanvi")
    page = v["page"]
    assert page["state_label"] == "Questions from the review desk"
    assert page["pill"]["label"] == "Needs you" and v["idea"]["status"] == "needs_you"
    assert v["idea"]["has_open_questions"] is True
    # The questions card is lane B's (C-QCARD, GET /ideas/:id/question-set): none of it is built here.
    assert page["card"] is None and page["card_from"] == "question_set" and "questions" not in page
    assert page["lane_b"]["question_set"] == f"/api/ideas/{ref(club, 'T6')}/question-set"
    assert "answer" not in page["actions"]
    assert not page["window"]["open"] and page["window"]["line"].startswith("The review desk opened it on")
    assert "withdraw" not in page["actions"] and "edit" not in page["actions"]
    assert nodes(v)[2][2] == f"3 questions for you since {day(NOW - dt.timedelta(days=1), NOW)}"


def test_s06_states_needs_you_as_lane_b_stores_it(club: dict[str, Any]) -> None:
    """Lane B writes `needs_you` on the idea when it sends questions (E-ENUMS.idea-status)."""
    conn, t6 = club["conn"], ref(club, "T6")
    conn.execute("UPDATE ideas SET status = 'needs_you' WHERE idea_id = %s", (t6,))
    v = view(club, t6, "tanvi")
    assert v["page"]["state"] == "questions" and v["page"]["pill"]["label"] == "Needs you"
    assert v["idea"]["edit_window"]["open"] is False and nodes(v)[2][1] == "now"
    other = view(club, t6, "rekha")
    assert (
        other["idea"]["status"] == "with_review_desk"
        and other["page"]["pill"]["label"] == "With the review desk"
    )
    row = next(i for i in mine(club, "tanvi")["items"] if i["id"] == t6)
    assert row["pill"]["label"] == "Needs you" and row["group"] == "needs_you"
    with pytest.raises(Refused):
        withdraw(conn, t6, club["p"]["tanvi"], None, now=NOW)


def test_s06_states_decisions_leave_the_decision_to_lane_b(club: dict[str, Any]) -> None:
    """Picked, Not now, Not picked and Reversed: the decision, its reason, the committee's window and any reversal
    are lane B's (GET /ideas/:id/decision). This page keeps the state, the pill and the track."""
    expected = {
        "T7": ("Picked", "Picked"),
        "T8": ("Not now", "Not now"),
        "T9": ("Reversed by the Ones Committee", "Picked"),
    }
    for key, (label, pill_label) in expected.items():
        v = view(club, ref(club, key), "tanvi")
        page = v["page"]
        assert page["state_label"] == label and page["pill"]["label"] == pill_label
        assert page["card"] is None and page["card_from"] == "decision"
        assert page["lane_b"]["decision"] == f"/api/ideas/{ref(club, key)}/decision"
        assert "decision" not in v["idea"] and "join_build" not in page["actions"]
        dump = json.dumps(v, ensure_ascii=False, default=str)
        for words in ("compliance sign-off", "exchange calendar", "Failed dividends cost more"):
            assert words not in dump  # reasons and the committee's note are read from lane B only
    picked = nodes(view(club, ref(club, "T7"), "tanvi"))
    assert picked[2][1] == "done" and str(picked[2][2]).startswith("Picked, ")
    assert picked[3][1] == "now" and str(picked[3][2]).startswith("Team chosen by ")
    assert (
        nodes(view(club, ref(club, "T9"), "tanvi"))[2][2]
        == "Not picked, then moved to picked by the Ones Committee"
    )
    assert str(nodes(view(club, ref(club, "T8"), "tanvi"))[3][2]).startswith("Looked at again on ")


def test_l_questions_answer_5_answers_under_their_parts_come_from_lane_b(
    club: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Lane B's desk.asking is on main (82668c1), so the page reads whatever it returns. A stand-in fixes what it
    # returns, so this test checks lane E's mapping (an answer under its part, its line) and not lane B's data.
    t7 = ref(club, "T7")
    asked = NOW - dt.timedelta(days=6)
    fake = types.ModuleType("desk.asking")
    fake.answers_by_part = lambda conn, uuid: {
        "often": [
            {
                "question_id": "q1",
                "question": "Across branches?",
                "asked_by": "Harish",
                "asked_at": asked.isoformat(),
                "answer": "Yes, across the six largest branches.",
                "answered_at": asked.isoformat(),
                "by": "Tanvi",
                "files": [],
            },
            {
                "question_id": "q2",
                "question": "Since when?",
                "asked_by": "Harish",
                "asked_at": asked.isoformat(),
                "answer": None,
                "answered_at": None,
                "by": None,
                "files": [],
            },
        ]
    }
    monkeypatch.setitem(sys.modules, "desk.asking", fake)
    often = next(r for r in view(club, t7, "tanvi")["page"]["shared"]["rows"] if r["part"] == "often")
    assert [a["text"] for a in often["answers"]] == ["Yes, across the six largest branches."]
    assert often["answers"][0]["line"] == f"From your answer to Harish, {day(asked, NOW)}"


def test_s06_states_withdrawn_offers_restore_it(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T10"), "tanvi")
    page = v["page"]
    assert (
        page["state_label"] == "Withdrawn" and page["card"]["lead"] == "Withdrawn. It’s back in your drafts."
    )
    assert "No reason given." in page["card"]["rest"]
    assert page["actions"]["restore"]["label"] == "Restore it" and "withdraw" not in page["actions"]
    assert [n[1] for n in nodes(v)][2:] == ["not_going_ahead"] * 3
    assert nodes(v)[2][2] == "Withdrawn before review"
    assert page["conversation"] is None


def test_s06_rules_4_a_merged_idea_shows_where_it_went(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T11"), "tanvi")
    merged = v["page"]["merged"]
    assert merged["line"] == f"Merged into {ref(club, 'R2')} by the review desk"
    assert merged["note"] == "Both ideas ask for one clear message after a failed debit."
    assert v["idea"]["stages"] == [] and v["idea"]["merged_into"] == ref(club, "R2")


def test_s06_sharer_sees_masked_words_until_lane_c_reader_lands(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T6"), "tanvi")
    words = json.dumps(v["idea"]["own_words"], ensure_ascii=False)
    assert "PAN ••••9Z" in words and "AAAPZ9999Z" not in words
    assert v["page"]["own_words_unmasked"] is False
    assert v["page"]["shared"]["hidden"]["chips"] == ["PAN ••••9Z"]


# --- P-ROUTES.screens: who gets what at /ideas/:id ---------------------------------------------------------------


def test_p_routes_a_non_sharer_never_gets_s06_data(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "T6"), "rekha")
    assert v["view"] == "colleague"
    for private in ("own_words", "hidden", "files", "answers_by_part", "decision", "edit_window", "review"):
        assert private not in v["idea"]
    assert "shared" not in v["page"] and "actions" not in v["page"]


def test_p_routes_a_reviewer_lands_on_the_desk_page(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "R1"), "harish")
    assert v == {"view": "desk", "to": f"/desk/ideas/{ref(club, 'R1')}"}


def test_p_routes_nobody_but_the_owner_sees_a_draft(club: dict[str, Any]) -> None:
    draft = club["m"]["T2"].uuid
    assert view(club, draft, "tanvi") == {"view": "draft", "to": f"/share/{draft}"}
    for who in ("rekha", "harish", "manoj", "kunal"):
        with pytest.raises(read.NotFound):
            view(club, draft, who)


def test_p_routes_a_withdrawn_idea_is_seen_by_its_sharer_alone(club: dict[str, Any]) -> None:
    for who in ("rekha", "harish"):
        with pytest.raises(read.NotFound):
            view(club, ref(club, "T10"), who)


def test_s09_rules_2_bld_e011_a_former_crew_member_gets_one_line_for_a_withdrawn_idea(
    club: dict[str, Any],
) -> None:
    conn, t10 = club["conn"], ref(club, "T10")
    code = conn.execute(
        "SELECT contributor_code FROM contributor_map WHERE user_id = %s", (club["p"]["rekha"],)
    ).fetchone()
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at, left_at, left_how) "
        "VALUES (%s, %s, 'crew', 'teamup', %s, %s, 'idea_withdrawn')",
        (
            club["m"]["T10"].uuid,
            code["contributor_code"],
            NOW - dt.timedelta(days=3),
            NOW - dt.timedelta(days=1),
        ),
    )
    v = view(club, t10, "rekha")
    assert v["view"] == "colleague" and v["page"]["state"] == "withdrawn"
    assert (
        v["page"]["team_up"]["line"] == "The person who shared it withdrew it, so nobody else can see it now."
    )
    assert set(v["idea"]) == {"id", "ref", "status"}  # no title, summary, crew, track or name
    with pytest.raises(read.NotFound):
        view(club, t10, "harish")


def test_p_routes_others_reach_an_idea_by_its_reference_only(club: dict[str, Any]) -> None:
    with pytest.raises(read.NotFound):
        view(club, club["m"]["R1"].uuid, "tanvi")
    with pytest.raises(read.NotFound):
        view(club, "IDEA-2026-999999", "tanvi")


# --- S-09: a colleague's idea ----------------------------------------------------------------------------------------


def test_dec_104_s09_never_returns_raw_words(club: dict[str, Any]) -> None:
    conn = club["conn"]
    for key in ("T5", "T6", "T7", "T9"):
        v = view(club, ref(club, key), "rekha")
        dump = json.dumps(v, default=str)
        uid = club["m"][key].uuid
        for m in conn.execute(
            "SELECT id, text_encrypted FROM idea_messages WHERE idea_uuid = %s", (uid,)
        ).fetchall():
            from onepc.context import open_text

            masked = open_text("idea_messages", "text_encrypted", str(m["id"]), m["text_encrypted"])
            assert masked and masked not in dump
        assert "SR40021187" not in dump and "AAAPZ9999Z" not in dump
        assert "reason" not in v["idea"] and "compliance sign-off" not in dump
        assert v["idea"]["summary"] == club["m"][key].spec.summary


def test_s09_omits_the_name_when_hidden_on_the_wall(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "C1"), "tanvi")
    dump = json.dumps(v, default=str)
    assert "Charulata" not in dump and v["idea"]["sharer"] is None
    assert v["page"]["shared_line"] == f"Shared {day(NOW - dt.timedelta(days=16), NOW)}, Compliance, Kolkata"
    assert "The sharer’s own words stay with them" in v["page"]["summary_note"]


def test_s09_layout_names_the_sharer_and_bld_e008_uses_no_pronoun(club: dict[str, Any]) -> None:
    v = view(club, ref(club, "R1"), "pallavi")
    page = v["page"]
    assert (
        page["shared_line"]
        == f"Shared {day(NOW - dt.timedelta(days=6), NOW)} by Rekha Saxena, Investor service, Hyderabad"
    )
    assert page["summary_note"] == (
        "This is the short summary everyone at KFintech sees. Rekha’s own words stay with them and the review desk."
    )
    assert [a["label"] for a in page["about"]] == [
        "Who it affects",
        "What it’s worth",
        "Area",
        "Linked",
        "Who can see it",
    ]
    assert page["back"] == {"from": "wall", "label": "Back to the Wall", "to": "/wall"}
    for word in (" him", " her ", " his ", " she ", " he "):
        assert word not in json.dumps(page)


def test_s09_states_not_asked_request_sent_and_on_the_crew(club: dict[str, Any]) -> None:
    r1 = ref(club, "R1")
    assert view(club, r1, "pallavi")["page"]["team_up"]["state"] == "not_asked"
    sent = view(club, r1, "bhavesh")["page"]["team_up"]
    assert sent["state"] == "request_sent" and sent["heading"] == "Waiting for Rekha"
    assert sent["line"] == "Rekha reads your note and decides. You’ll hear in your Inbox."
    crew = view(club, r1, "zoya")["page"]["team_up"]
    assert crew["state"] == "on_crew" and crew["line"] == "You’re on the crew. You’ll get its updates."
    assert crew["action"] == {"label": "Say hello", "to": f"/ideas/{r1}/conversation"}
    assert crew["count_line"].startswith("2 colleagues on it. Rekha leads it and decides who joins.")


def test_s09_rules_2_a_closed_idea_offers_no_team_up(club: dict[str, Any]) -> None:
    t = view(club, ref(club, "F1"), "tanvi")["page"]["team_up"]
    assert t["state"] == "closed" and t["can_team_up"] is False
    m = view(club, ref(club, "T11"), "rekha")["page"]["team_up"]
    assert m["state"] == "merged" and m["link"]["to"].startswith(f"/ideas/{ref(club, 'R2')}")


def test_p_routes_state_s09_back_link_names_where_you_came_from(club: dict[str, Any]) -> None:
    r1 = ref(club, "R1")
    b = view(club, r1, "pallavi", came_from="my-ideas", back="/my-ideas?list=teamed&sort=stage")["page"][
        "back"
    ]
    assert b == {"from": "my-ideas", "label": "Back to My ideas", "to": "/my-ideas?list=teamed&sort=stage"}
    b = view(club, r1, "tanvi", came_from=ref(club, "T5"))["page"]["back"]
    assert b["label"] == f"Back to {ref(club, 'T5')}" and b["to"] == f"/ideas/{ref(club, 'T5')}"
    b = view(club, r1, "pallavi", came_from="wall", back="https://example.org/wall")["page"]["back"]
    assert b["to"] == "/wall"


def test_s09_the_wall_switch_hides_colleagues_ideas(club: dict[str, Any]) -> None:
    club["conn"].execute("UPDATE kill_switches SET state = 'off' WHERE name = 'wall.public'")
    killswitch.clear_cache()
    with pytest.raises(Paused):
        view(club, ref(club, "R1"), "pallavi")
    assert view(club, ref(club, "T5"), "tanvi")["view"] == "sharer"  # the sharer's own page stays


def test_l_wall_justin_4_a_colleague_opening_counts_once_a_day(club: dict[str, Any]) -> None:
    conn, uid, who = club["conn"], club["m"]["R1"].uuid, club["p"]["pallavi"]
    today = NOW.astimezone(IST).date()
    # Start from no open today, whatever the seed spread over the week.
    conn.execute("DELETE FROM idea_opens WHERE idea_uuid = %s AND user_id = %s", (uid, who))
    for _ in range(2):
        view(club, ref(club, "R1"), "pallavi")
    rows = conn.execute(
        "SELECT day FROM idea_opens WHERE idea_uuid = %s AND user_id = %s", (uid, who)
    ).fetchall()
    assert [r["day"] for r in rows] == [today]  # the view's own day in India time, once
    idea_view(conn, ref(club, "R1"), who, now=NOW + dt.timedelta(days=1))
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM idea_opens WHERE idea_uuid = %s AND user_id = %s", (uid, who)
        ).fetchone()["n"]
        == 2
    )


# --- L-SUBMIT.withdraw ----------------------------------------------------------------------------------------------


def test_l_submit_withdraw_inside_the_window_then_restore_with_the_same_reference(
    club: dict[str, Any],
) -> None:
    conn, t5 = club["conn"], ref(club, "T5")
    out = withdraw(conn, t5, club["p"]["tanvi"], "Folio 1234567890 is already being fixed", now=NOW)
    assert out["page"]["state"] == "withdrawn"
    rest = out["page"]["card"]["rest"]
    assert "1234567890" not in rest and "Your reason:" in rest
    assert (
        withdraw(conn, t5, club["p"]["tanvi"], None, now=NOW)["page"]["state"] == "withdrawn"
    )  # repeat: no change
    with pytest.raises(read.NotFound):
        view(club, t5, "rekha")
    back = restore(conn, t5, club["p"]["tanvi"], now=NOW + dt.timedelta(hours=1))
    row = conn.execute("SELECT * FROM ideas WHERE idea_id = %s", (t5,)).fetchone()
    assert back["idea"]["id"] == t5 and row["status"] == "with_review_desk"
    assert row["decide_by"] > NOW + dt.timedelta(days=5) and row["withdraw_reason_encrypted"] is None
    assert back["page"]["state"] == "just_shared" and back["page"]["window"]["open"]
    history = [
        r["to_status"]
        for r in conn.execute(
            "SELECT to_status FROM idea_status_history WHERE idea_uuid = %s ORDER BY id", (row["id"],)
        ).fetchall()
    ]
    assert history[-3:] == ["withdrawn", "checking", "with_review_desk"]
    audit = [
        r["action"]
        for r in conn.execute(
            "SELECT action FROM audit_log WHERE entity = %s ORDER BY id", (f"idea:{t5}",)
        ).fetchall()
    ]
    assert audit == ["idea.withdraw", "idea.restore"]
    assert (
        restore(conn, t5, club["p"]["tanvi"], now=NOW)["page"]["state"] == "just_shared"
    )  # repeat: no change
    assert view(club, t5, "rekha")["view"] == "colleague"


def test_l_submit_withdraw_is_refused_once_the_desk_opened_it(club: dict[str, Any]) -> None:
    with pytest.raises(Refused) as exc:
        withdraw(club["conn"], ref(club, "T6"), club["p"]["tanvi"], None, now=NOW)
    assert exc.value.status == 409 and exc.value.code == "edit_window_closed"
    assert "opened_by_desk_at" in exc.value.body()["error"]


def test_l_submit_withdraw_only_the_sharer_may_withdraw_or_restore(club: dict[str, Any]) -> None:
    for fn, key in ((withdraw, "T5"), (restore, "T10")):
        with pytest.raises(read.NotFound):
            fn(club["conn"], ref(club, key), club["p"]["rekha"], now=NOW)
    with pytest.raises(Refused) as exc:
        restore(club["conn"], ref(club, "T7"), club["p"]["tanvi"], now=NOW)
    assert exc.value.code == "not_withdrawn"


# --- S-07: My ideas ------------------------------------------------------------------------------------------------


def mine(club: dict[str, Any], who: str, **params: Any) -> dict[str, Any]:
    return my_ideas(club["conn"], club["p"][who], params, now=NOW)


def test_p_routes_state_j_browse_3_my_ideas_restores_tab_filter_sort_and_q_from_the_url(
    club: dict[str, Any],
) -> None:
    r2 = ref(club, "R2")
    out = mine(club, "tanvi", list="teamed", filter="with_review_desk", sort="stage", q="debit", row=r2)
    assert out["state"] == {
        "list": "teamed",
        "filter": "with_review_desk",
        "sort": "stage",
        "q": "debit",
        "row": r2,
    }
    assert out["query"] == f"list=teamed&filter=with_review_desk&sort=stage&q=debit&row={r2}"
    assert out["url"] == f"/my-ideas?{out['query']}"
    assert [i["id"] for i in out["items"]] == [r2]
    assert out["arrival"] == {"line": "Back where you were: Teamed up.", "row": r2}
    # The row's link carries this exact view back (J-BROWSE/2 and /3), the opened row included.
    href = out["items"][0]["href"]
    assert href.startswith(f"/ideas/{r2}?from=my-ideas&back=")
    back = parse_qs(urlsplit(href).query)["back"][0]
    assert back == out["url"]
    assert [t["selected"] for t in out["tabs"]] == [False, True]
    assert [f["filter"] for f in out["filters"] if f["selected"]] == ["with_review_desk"]
    assert [s["sort"] for s in out["sorts"] if s["selected"]] == ["stage"]
    # A filter the opened row is not in shows nothing to come back to, and says nothing about arriving.
    elsewhere = mine(club, "tanvi", list="teamed", filter="shipped", q="debit", row=r2)
    assert elsewhere["items"] == [] and "arrival" not in elsewhere
    # Unknown values fall back to the defaults; defaults are left out of the canonical URL.
    plain = mine(club, "tanvi", list="nope", filter="nope", sort="nope")
    assert plain["query"] == "" and plain["url"] == "/my-ideas"


def test_s07_filters_counts_per_filter_and_per_list(club: dict[str, Any]) -> None:
    out = mine(club, "tanvi")
    assert out["counts"] == {
        "all": 10,
        "needs_you": 1,
        "drafts": 3,
        "with_review_desk": 2,
        "picked_and_building": 2,
        "shipped": 0,
        "closed": 3,
    }
    assert out["lists"] == {"yours": 10, "teamed": 2}
    needs = mine(club, "tanvi", filter="needs_you")
    assert needs["lists"] == {"yours": 1, "teamed": 0} and [i["ref"] for i in needs["items"]] == [
        ref(club, "T6")
    ]


def test_s07_rows_next_step_and_action_per_status(club: dict[str, Any]) -> None:
    rows = {i["id"]: i for i in mine(club, "tanvi")["items"]}
    t6 = rows[ref(club, "T6")]
    assert t6["pill"]["label"] == "Needs you"
    assert t6["next_step"]["sentence"] == "The review desk asked you 3 questions yesterday."
    assert t6["next_step"]["action"]["label"] == "Answer the questions"
    assert t6["next_step"]["action"]["to"] == f"/ideas/{ref(club, 'T6')}/answer"
    assert (
        t6["next_step"]["action"]["accessible_name"]
        == "Answer the questions: PAN mismatch holds new folios for days"
    )
    assert t6["track"]["label"] == "2 of 5 stages done. Now: reviewed"
    t10 = rows[ref(club, "T10")]
    assert t10["next_step"]["action"]["label"] == "Restore it" and t10["next_step"]["sentence"].startswith(
        "Withdrawn on "
    )
    t9 = rows[ref(club, "T9")]
    assert t9["meta"].startswith(f"{ref(club, 'T9')}, Picked by the Ones Committee, ")
    assert t9["next_step"]["sentence"].startswith(
        "The committee reversed the review desk’s not picked: We can ask"
    )
    assert t9["next_step"]["action"]["label"] == "Read the decision"
    draft = rows[club["m"]["T2"].uuid]
    assert draft["pill"]["label"] == "Draft" and draft["track"] is None
    assert draft["next_step"]["action"] == {
        "label": "Carry on",
        "to": f"/share/{club['m']['T2'].uuid}",
        "style": "line",
        "accessible_name": "Carry on: SIP failure SMS gives no reason",
    }
    assert draft["next_step"]["sentence"].startswith("Waiting for Rekha")  # its merge request waits on Rekha
    assert club["m"]["T3"].uuid not in rows  # archived: only under Drafts


def test_l_draft_autosave_8_archived_drafts_are_listed_under_drafts(club: dict[str, Any]) -> None:
    rows = {i["id"]: i for i in mine(club, "tanvi", filter="drafts")["items"]}
    t3 = rows[club["m"]["T3"].uuid]
    assert t3["archived"] is True and t3["meta"].startswith("Archived ")
    assert (
        t3["next_step"]["action"]["label"] == "Restore it"
        and t3["next_step"]["action"]["op"] == "draft.restore"
    )


def test_s07_teamed_up_rows_read_as_everyone_sees_them(club: dict[str, Any]) -> None:
    rows = {i["id"]: i for i in mine(club, "tanvi", list="teamed")["items"]}
    v1 = rows[ref(club, "V1")]
    assert v1["meta"].startswith("Varun Chopra’s idea, you teamed up ") and v1["meta"].endswith(
        ref(club, "V1")
    )
    assert v1["next_step"]["action"]["label"] == "See the result"
    r2 = rows[ref(club, "R2")]
    assert r2["next_step"]["sentence"].endswith("You’ll get a note either way.")


def test_s07_search_matches_title_summary_and_reference(club: dict[str, Any]) -> None:
    out = mine(club, "tanvi", q="SIP")
    assert out["search"]["sentence"].startswith("Found ") and "Closest: “" in out["search"]["sentence"]
    assert out["search"]["matched_on"] == ["title", "summary", "reference"]
    assert {i["id"] for i in out["items"]} >= {club["m"]["T2"].uuid, ref(club, "T11")}
    by_ref = mine(club, "tanvi", q=ref(club, "T7"))
    assert [i["id"] for i in by_ref["items"]] == [ref(club, "T7")]
    none = mine(club, "tanvi", q="nothing like this")
    assert none["empty"]["kind"] == "no_results" and none["total"] == 0


def test_s07_search_rows_carry_a_snippet_of_the_summary(club: dict[str, Any]) -> None:
    out = mine(club, "tanvi", q=ref(club, "T7"))
    row = out["items"][0]
    summary = club["m"]["T7"].spec.summary
    assert row["snippet"] == snippet(summary) and len(row["snippet"]) <= 97
    assert "snippet" not in mine(club, "tanvi")["items"][0]
    assert out["search"]["clear"]["to"] == "/my-ideas"


def test_s07_phone_sort_cycler_copy_link_and_short_filter_label(club: dict[str, Any]) -> None:
    out = mine(club, "tanvi", sort="stage", filter="with_review_desk", row="x")
    assert out["sort_cycle"] == {
        "label": "Sorted by stage",
        "next": "latest",
        "to": "/my-ideas?filter=with_review_desk",
    }
    assert out["copy_link"]["url"] == "/my-ideas?filter=with_review_desk&sort=stage"
    chip = next(f for f in out["filters"] if f["filter"] == "with_review_desk")
    assert (
        chip["label"] == "With the review desk"
        and chip["short_label"] == "With the desk"
        and chip["selected"]
    )


def test_s07_states_empty_first_time_and_filtered(club: dict[str, Any]) -> None:
    first = mine(club, "kunal")
    assert first["empty"]["kind"] == "first_time" and first["empty"]["title"] == "Nothing shared yet"
    assert first["empty"]["actions"][0] == {
        "label": "Share your first problem",
        "to": "/share",
        "style": "primary",
    }
    shipped = mine(club, "tanvi", filter="shipped")
    assert shipped["empty"]["title"] == "Nothing shipped yet."
    assert [a["label"] for a in shipped["empty"]["actions"]] == ["See 1 in Teamed up", "Show all ideas"]
    desk = mine(club, "tanvi", list="teamed", filter="with_review_desk")
    assert desk["total"] == 1  # R2


def test_j_browse_6_a_shared_link_shows_only_what_that_person_may_see(club: dict[str, Any]) -> None:
    tanvis = {i["id"] for i in mine(club, "tanvi", filter="closed")["items"]}
    rekhas = {i["id"] for i in mine(club, "rekha", filter="closed")["items"]}
    assert tanvis and not tanvis & rekhas
