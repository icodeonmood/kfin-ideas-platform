"""V-ACC gap tests for lane F's two tables, V-ACC.teamup and V-ACC.similar, on the database (the coverage map of
18 Nov 10:00 found these rows with no automated check). Each test names its row.

Where a row crosses another lane's code, the test goes through that lane's public entry points and never changes
them: lane A's Inbox (`notify.inbox`, `notify.render`), lane B's reviewer page (`desk.reads.reviewer_idea`), lane C's
Submit (`submit.sorting`, `submit.send`, `submit.check`) and similar ideas (`similar.views`, on c/similar). The
worker's routes are called over HTTP through its own FastAPI app with the internal token, as the web calls them.
Synthetic people only (non-negotiable 11): the pack's fictional cast. Everything made is removed afterwards except
`audit_log`, whose trigger refuses DELETE.
"""

from __future__ import annotations

import datetime as dt
import importlib
import importlib.util
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from core.db import Conn
from teamup import drafts, requests
from tests import f_teamup_fixtures as f
from tests import helpers

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
TOKEN = "lane-f-vacc-token-0123456789abcdef"
NOTE = "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07."
REASON = "Mine is about the SMS wording, yours is about the calls it causes. Better as two."
NOW = dt.datetime(2026, 11, 18, 5, 0, tzinfo=dt.UTC)  # Wednesday 18 November, 10:30 am in the office
REF = re.compile(r"^IDEA-2026-[0-9]{6}$")
NOT_LEAD = {"error": {"code": "not_lead", "message": "Only the lead of this idea can answer."}}


@pytest.fixture
def db(db: Conn, monkeypatch: pytest.MonkeyPatch) -> Iterator[Conn]:
    """The shared `db`, with the seed's configuration (lists, promises, templates) and clean-up: the jobs, timers
    and vault values this test's ideas made, then (through `f.clean`) its ideas and people."""
    from core import killswitch
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(SEED))
    get_settings.cache_clear()
    killswitch.clear_cache()
    last_job = int(db.execute("SELECT coalesce(max(id), 0) AS n FROM jobs").fetchone()["n"])
    yield db
    from hide.core import scope_for

    ideas = list(f._made["ideas"])
    refs = [
        str(r["idea_id"])
        for r in db.execute(
            "SELECT idea_id FROM ideas WHERE id = ANY(%s::uuid[]) AND idea_id IS NOT NULL", (ideas,)
        ).fetchall()
    ]
    scopes = [scope_for(i) for i in ideas]
    db.execute("DELETE FROM jobs WHERE id > %s", (last_job,))
    db.execute("DELETE FROM sla_timers WHERE entity_type = 'idea' AND entity_id = ANY(%s)", (refs,))
    db.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (scopes,))
    db.execute("DELETE FROM vault_counters WHERE scope_id = ANY(%s)", (scopes,))
    f.clean(db)
    killswitch.clear_cache()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn) -> dict[str, Any]:
    ravi = f.person(db, "Ravi Nair")
    kavya = f.person(db, "Kavya Menon")
    asha = f.person(db, "Asha Sen", city="Pune", area="Operations")
    meera = f.person(db, "Meera Iyer", roles=("reviewer",))
    lead_idea = f.idea(db, ravi, title="Rejection SMS codes confuse investors")
    f.crew(db, lead_idea, asha)
    return {"ravi": ravi, "kavya": kavya, "asha": asha, "meera": meera, "lead": lead_idea}


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> f.Inbox:
    """Lane A's `notify.post` and `notify.resolve`, recorded rather than sent, where the row is not about the Inbox."""
    return f.record_inbox(monkeypatch)


def ready_draft(db: Conn, owner: dict[str, str]) -> dict[str, Any]:
    """An unsent draft with the parts Submit needs (lane C's shape, BLD-C080): title and summary, how often, who it
    affects, what it is worth and its area, each with the reason the sorting is suggested from."""
    draft = f.draft(db, owner)
    parts = {
        "title": (
            {
                "title": "Investors call to ask why a redemption was rejected",
                "summary": "The rejection SMS only gives a code, such as R07.",
            },
            None,
        ),
        "often": ("About 40 calls a day at one branch", None),
        "who": (["Investors", "KFin teams"], "because you mentioned investors and the branch"),
        "value": (["saves_time"], "because you said about 40 calls a day"),
        "area": ("Investor service", "because it’s about investors and the SMS they get"),
    }
    for key, (value, why) in parts.items():
        db.execute(
            "INSERT INTO idea_parts (idea_uuid, key, state, value, why) VALUES (%s, %s, 'filled', %s, %s)",
            (draft["id"], key, Jsonb(value), why),
        )
    return draft


def confirm_and_submit(db: Conn, draft: dict[str, Any], owner: dict[str, str]) -> tuple[int, dict[str, Any]]:
    """Lane C's Send it, as S-05 calls it: confirm the sorting, then Submit with the declaration's version."""
    from submit import send, sorting
    from submit.config import DECLARATION_VERSION

    sorting.update_draft(db, str(draft["id"]), owner["id"], {"confirm": True}, now=NOW)
    return send.submit(
        db, str(draft["id"]), owner["id"], {"declaration_version": DECLARATION_VERSION}, now=NOW
    )


# ---------------------------------------------------------------------------------------------------------------
# V-ACC.similar/8: refused by any route, over HTTP
# ---------------------------------------------------------------------------------------------------------------
@pytest.fixture
def client(db: Conn, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The worker's own app, on this test's database, behind the internal token the web sends."""
    from core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", helpers.db_url(test_database))
    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    from api.app import app

    yield TestClient(app, headers={"X-Internal-Token": TOKEN})
    get_settings.cache_clear()


def test_V_ACC_similar_8_over_http_no_route_merges_without_the_lead(
    db: Conn, client: TestClient, cast: dict[str, Any]
) -> None:
    """A sharer (Kavya) and a crew member (Asha) try every route a merge could go through: the lead's answer route,
    the draft's merge-request route with an answer of its own, someone else's draft, the lead's Inbox item, a
    team-up that brings a shared idea, and lane B's desk merge. Each is refused with the route's own code; nothing
    is merged or joined."""
    kavya, asha, ravi, lead_ref = cast["kavya"], cast["asha"], cast["ravi"], cast["lead"]["idea_id"]
    draft = f.draft(db, kavya)
    f.similar(db, draft, cast["lead"])
    drafts_url = f"/internal/drafts/{draft['id']}/merge-request"

    asked = client.post(
        drafts_url, params={"user_id": kavya["id"]}, json={"other_idea_id": lead_ref, "note": NOTE}
    )
    assert asked.status_code == 201, asked.text
    rid = asked.json()["id"]
    assert asked.json()["state"] == "waiting" and asked.json()["after"]["can_submit"] is False

    # 1. The lead's answer route, by the sharer and by someone on the crew
    for who in (kavya, asha):
        r = client.post(
            f"/internal/team-up/{rid}/answer", params={"user_id": who["id"]}, json={"answer": "merge"}
        )
        assert (r.status_code, r.json()) == (403, NOT_LEAD), who["name"]
    # 2. The merge-request route again, carrying an answer and a state of its own: still only a request
    again = client.post(
        drafts_url,
        params={"user_id": kavya["id"]},
        json={"other_idea_id": lead_ref, "note": NOTE, "answer": "merge", "state": "accepted"},
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_requested"
    # ... and on a draft that is not theirs
    theirs = client.post(
        drafts_url, params={"user_id": asha["id"]}, json={"other_idea_id": lead_ref, "note": NOTE}
    )
    assert theirs.status_code == 404 and theirs.json()["error"]["code"] == "not_found"
    # 3. The lead's Inbox item and its Merge it button, from anyone but the lead
    item = db.execute(
        "SELECT id FROM notifications WHERE user_id = %s AND channel = 'in_app' AND kind = 'teamup_request'",
        (ravi["id"],),
    ).fetchone()
    assert item is not None
    for who in (kavya, asha):
        r = client.post(f"/internal/inbox/{who['id']}/{item['id']}/actions/merge")
        assert (r.status_code, r.json()) == (404, {"error": "not_found"}), who["name"]
    # 4. A team-up that brings a shared idea: only the lead may answer Merge it there too
    pradeep = f.person(db, "Pradeep Kumar")
    brought = f.idea(db, pradeep, title="No script for calls about rejections")
    sent = client.post(
        f"/internal/ideas/{lead_ref}/team-up",
        params={"user_id": pradeep["id"]},
        json={"note": NOTE, "brought_idea_ids": [brought["idea_id"]]},
    )
    assert sent.status_code == 201, sent.text
    for who in (pradeep, asha):
        r = client.post(
            f"/internal/team-up/{sent.json()['id']}/answer",
            params={"user_id": who["id"]},
            json={"answer": "merge"},
        )
        assert (r.status_code, r.json()) == (403, NOT_LEAD), who["name"]

    # 5. Lane B's desk merge (L-MERGE.desk), which needs no consent: only the review desk may call it, so a sharer
    # who is not a reviewer is refused, whichever idea they put first
    forbidden = {"error": {"code": "forbidden", "message": "Only the review desk can do this."}}
    for who, ref, other in ((pradeep, brought["idea_id"], lead_ref), (kavya, lead_ref, brought["idea_id"]),
                            (kavya, str(draft["id"]), lead_ref)):  # fmt: skip
        r = client.post(
            f"/internal/desk/ideas/{ref}/merge",
            params={"user_id": who["id"]},
            json={"other_idea_id": other, "lead": lead_ref, "team_up": True, "note": NOTE},
        )
        assert (r.status_code, r.json()) == (403, forbidden), (who["name"], ref)

    # Nothing moved: the draft is still Kavya's and held, the idea brought is still with the desk, no merge exists,
    # neither asker is on Ravi's crew, and each refused answer is in the audit log
    state = client.get(drafts_url, params={"user_id": kavya["id"]}).json()
    assert state["state"] == "waiting" and state["after"]["label"] == "Waiting on Ravi to merge"
    assert f.status_of(db, draft) == {"status": "draft", "merged_into": None}
    assert f.status_of(db, brought)["status"] == "with_review_desk"
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone()["n"] == 0
    assert (
        db.execute("SELECT state FROM merge_requests WHERE id = %s", (rid,)).fetchone()["state"] == "waiting"
    )
    assert kavya["code"] not in f.live_crew(db, cast["lead"]) and pradeep["code"] not in f.live_crew(
        db, cast["lead"]
    )
    assert len(f.audit_rows(db, "teamup.answer_refused", rid)) == 2
    assert len(f.audit_rows(db, "teamup.answer_refused", sent.json()["id"])) == 2


# ---------------------------------------------------------------------------------------------------------------
# V-ACC.teamup/6: Kavya's Inbox gets the matching item, rendered by lane A
# ---------------------------------------------------------------------------------------------------------------
@pytest.fixture
def seed_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lane A's renderer reads the seed's comms templates (as `test_inbox_teamup_words.py` does)."""
    from comms import templates
    from notify import render

    monkeypatch.setattr(render, "load", lambda name: templates._load(SEED, name))


def _answer_item(db: Conn, person: dict[str, str]) -> dict[str, Any]:
    from notify import inbox

    got = [i for i in inbox.items(db, person["id"], "all")["items"] if i["kind"] == "teamup_answer"]
    assert len(got) == 1, [i["kind"] for i in inbox.items(db, person["id"], "all")["items"]]
    return got[0]


@pytest.mark.usefixtures("seed_templates")
def test_V_ACC_teamup_6_the_askers_inbox_item_for_each_answer_reads_the_matching_line(
    db: Conn, cast: dict[str, Any]
) -> None:
    """Ravi answers Merge it on Kavya's request, Team up only on Meghna's and Decline, with a reason, on Pradeep's.
    Each asker's Inbox item, as lane A renders it from `comms/templates/inbox/teamup_answer.md`, says which; none
    offers an Undo."""
    ravi, kavya, lead_ref = cast["ravi"], cast["kavya"], cast["lead"]["idea_id"]
    mine = f.idea(db, kavya, title="Investors call to ask why a redemption was rejected")
    merge = requests.send(db, lead_ref, kavya["id"], {"note": NOTE, "brought_idea_ids": [mine["idea_id"]]})
    out = requests.answer(db, merge["id"], ravi["id"], {"answer": "merge"})
    assert out["result"]["state"] == "merged"

    meghna = f.person(db, "Meghna Das")
    hers = f.idea(db, meghna, title="No script for calls about rejections")
    team = requests.send(db, lead_ref, meghna["id"], {"note": NOTE, "brought_idea_ids": [hers["idea_id"]]})
    out = requests.answer(db, team["id"], ravi["id"], {"answer": "team_only"})
    assert out["result"]["state"] == "teamed_up"

    pradeep = f.person(db, "Pradeep Kumar")
    decline = requests.send(db, lead_ref, pradeep["id"], {"note": NOTE, "brought_idea_ids": []})
    out = requests.answer(db, decline["id"], ravi["id"], {"answer": "decline", "reason": REASON})
    assert out["result"]["state"] == "declined"

    merged = _answer_item(db, kavya)
    assert (merged["body"]["sender"], merged["line"]) == ("Ravi Nair", "approved your team-up request")
    assert merged["body"]["heading"] == "Request answered"
    assert merged["body"]["note"] == "You’re on Ravi’s crew now."
    assert merged["idea"]["id"] == lead_ref and merged["needs_you"] is False

    teamed = _answer_item(db, meghna)
    assert (teamed["body"]["sender"], teamed["line"]) == ("Ravi Nair", "approved your team-up request")
    assert teamed["body"]["note"] == "You’re on Ravi’s crew now."

    declined = _answer_item(db, pradeep)
    assert (declined["body"]["sender"], declined["line"]) == (
        "Ravi Nair",
        "declined your team-up request, with a reason",
    )
    assert declined["body"]["note"] == "The reason is in the app, with your request."
    assert REASON not in str(declined)  # the reason is read in the app, never in the Inbox line (L-NOTIFY/3)

    # Each item only opens things: no Undo, and no server operation that could take the answer back
    for item in (merged, teamed, declined):
        labels = [a["label"] for a in item["actions"]]
        assert labels and all(a.get("to") and not a.get("op") for a in item["actions"]), item["actions"]
        assert not any("undo" in label.lower() for label in labels), labels


# ---------------------------------------------------------------------------------------------------------------
# V-ACC.similar/5: declined, then "Send mine on its own" submits normally (lane C's Submit)
# ---------------------------------------------------------------------------------------------------------------
def test_V_ACC_similar_5_a_draft_whose_merge_request_was_declined_is_submitted_normally(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    from submit.errors import Refused as SubmitRefused

    kavya, ravi = cast["kavya"], cast["ravi"]
    draft = ready_draft(db, kavya)
    f.similar(db, draft, cast["lead"])
    asked = drafts.ask(
        db, str(draft["id"]), kavya["id"], {"other_idea_id": cast["lead"]["idea_id"], "note": NOTE}
    )

    # While Ravi has not answered, Submit is held (L-MERGE.request/4)
    with pytest.raises(SubmitRefused) as held:
        confirm_and_submit(db, draft, kavya)
    assert held.value.code == "merge_waiting"

    requests.answer(db, asked["id"], ravi["id"], {"answer": "decline", "reason": REASON})
    after = drafts.state(db, str(draft["id"]), kavya["id"])
    assert after["lead_reason"] == REASON
    assert after["after"]["action"] == {"label": "Send mine on its own", "op": "submit"}
    assert after["after"]["can_submit"] is True

    status, handover = confirm_and_submit(db, draft, kavya)
    assert status == 201 and REF.match(handover["idea_id"])
    row = db.execute(
        "SELECT status, idea_id, merged_into, shared_at FROM ideas WHERE id = %s", (draft["id"],)
    ).fetchone()
    assert (row["status"], row["idea_id"], row["merged_into"], row["shared_at"]) == (
        "checking",
        handover["idea_id"],
        None,
        NOW,
    )
    # Her own idea, with her as its lead; nothing joined Ravi's
    assert f.live_crew(db, draft) == {kavya["code"]: "lead"}
    assert kavya["code"] not in f.live_crew(db, cast["lead"])
    assert db.execute("SELECT count(*) AS n FROM merges").fetchone()["n"] == 0


# ---------------------------------------------------------------------------------------------------------------
# V-ACC.similar/7: "Keep mine separate", then Submit, then the reviewer's page (lane B)
# ---------------------------------------------------------------------------------------------------------------
def test_V_ACC_similar_7_keep_mine_separate_then_submit_and_the_reviewers_page_says_so(
    db: Conn, cast: dict[str, Any], inbox: f.Inbox
) -> None:
    """The real flow: the sheet's "Keep mine separate" on Check it (a team-up request with the draft, BLD-F020,
    BLD-F071), lane C's Submit and its check, then lane B's reviewer page. A draft that only carried on (Next, which
    records nothing, BLD-C131) reads no such line."""
    from desk import reads
    from submit import check

    kavya, meera = cast["kavya"], cast["meera"]
    draft = ready_draft(db, kavya)
    f.similar(db, draft, cast["lead"])
    kept = requests.send(db, cast["lead"]["idea_id"], kavya["id"],
                         {"note": NOTE, "brought_idea_ids": [], "draft_id": str(draft["id"])})  # fmt: skip
    assert kept["state"] == "sent"

    status, handover = confirm_and_submit(db, draft, kavya)
    assert status == 201
    check.run(db, str(draft["id"]))
    assert f.status_of(db, draft)["status"] == "with_review_desk"

    page = reads.reviewer_idea(db, handover["idea_id"], meera["id"], NOW)
    found = {a["kind"]: a for a in page["artefacts"]}["similar_found"]
    assert found["line"] == "1 found while Kavya wrote. Kavya kept it separate."

    # Asha's draft matched the same idea and she only carried on: no "kept it separate" for her
    asha = cast["asha"]
    carried = ready_draft(db, asha)
    other = f.idea(db, cast["ravi"], title="No script for calls about rejections")
    f.similar(db, carried, other)
    _, h2 = confirm_and_submit(db, carried, asha)
    check.run(db, str(carried["id"]))
    page2 = reads.reviewer_idea(db, h2["idea_id"], meera["id"], NOW)
    assert {a["kind"]: a for a in page2["artefacts"]}["similar_found"]["line"] == "1 found while Asha wrote."


# ---------------------------------------------------------------------------------------------------------------
# V-ACC.similar/1: the matches come back closest first (lane C's similar.views, on c/similar)
# ---------------------------------------------------------------------------------------------------------------
_MATCHES_ON_MAIN = importlib.util.find_spec("similar.views") is not None


@pytest.mark.xfail(
    not _MATCHES_ON_MAIN,
    strict=True,
    raises=ModuleNotFoundError,
    reason="V-ACC.similar/1: lane C — `similar.views.matches_for` (c/similar) is not on main, so no worker code "
    "orders a draft's matches yet; the test runs as a plain test once it lands",
)
def test_V_ACC_similar_1_a_drafts_matches_come_back_closest_first(db: Conn, cast: dict[str, Any]) -> None:
    """S-05 draws the matches in the order the API sends (C-SIMGRID.grid): the worker must send the closest first,
    whatever order the links were found in."""
    from similar.preview import Viewer

    matches_for = importlib.import_module(
        "similar.views"
    ).matches_for  # on c/similar; not importable until it lands
    kavya, asha = cast["kavya"], cast["asha"]
    pradeep = f.person(db, "Pradeep Kumar")
    draft = f.draft(db, kavya)
    related = f.idea(db, asha, title="No script for calls about rejections")
    also = f.idea(db, pradeep, title="Branch staff cannot read the SMS codes")
    close = cast["lead"]
    for other, strength, rank, minutes in (
        (related, "related", 1, 30),
        (also, "related", 2, 20),
        (close, "close", 3, 10),
    ):
        db.execute(
            "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason, rank, created_at) "
            "VALUES (%s, %s, %s, 'Same R07 SMS', %s, now() - make_interval(mins => %s))",
            (draft["id"], other["id"], strength, rank, minutes),
        )
    out = matches_for(db, str(draft["id"]), Viewer.of(db, kavya["id"]))
    assert out is not None
    assert [(m["idea"]["id"], m["strength"]) for m in out] == [
        (close["idea_id"], "close"),
        (related["idea_id"], "related"),
        (also["idea_id"], "related"),
    ]
