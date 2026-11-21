"""S-08's "+" (DEC-124, walk item WF-01; lane F, BLD-F095), the worker's half: a message takes only files added for
the conversation (`attachments.purpose` "conversation", lane C's BLD-C216), uploaded by the sender, checked, and not on
another message (L-CONVO/7); a file with a customer detail is refused with words that say only what S-08 can do
(DEC-107); a sent file opens through `/api/files/:id/view`; nobody on the crew ever opens a conversation file with a
customer detail; and what a co-sharer from a merge reads. Lane F's fixtures; synthetic people only.

Held, not pinned here (the coordinator, 21 Nov): whether the crew's conversation read carries checked files
(P-PRODUCT.privacy), which is the product lead's call. BLD-F062's rule stands unchanged meanwhile.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from attachments import files as F
from convo.messages import FILE_HAS_DETAIL, FILE_NOT_CHECKED, FILE_UNAVAILABLE, send
from convo.reads import conversation
from convo.store import Refused
from tests import convo_fixtures as fx

NOW = fx.at(21, 10, 30)  # Saturday 21 November 2026, IST


@pytest.fixture
def db(db: Any) -> Iterator[Any]:
    """The shared `db` fixture, plus clean-up: the people and ideas made here are deleted when the test ends."""
    yield db
    fx.clean(db)


@pytest.fixture
def told(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every inbox post, as lane A's `notify.post` receives it."""
    calls: list[dict[str, Any]] = []

    def fake(conn: Any, kind: str, recipients: list[str], **kw: Any) -> None:
        calls.append({"kind": kind, "to": list(recipients), **kw})

    monkeypatch.setattr("convo.adapters.notify_post", fake)
    return calls


def refused(fn: Any, *args: Any, **kwargs: Any) -> Any:
    with pytest.raises((Refused, F.FileRefused)) as caught:
        fn(*args, **kwargs)
    return caught.value


def on_entry(db: Any, att: str) -> Any:
    return db.execute("SELECT conversation_entry_id FROM attachments WHERE id = %s", (att,)).fetchone()[
        "conversation_entry_id"
    ]


def test_l_convo_7_dec_107_bld_f095_a_message_takes_only_the_senders_checked_conversation_files(
    db: Any, told: list[dict[str, Any]]
) -> None:
    """L-CONVO/7, DEC-107, BLD-F095: `_check_files` keeps every condition it had and adds the file's purpose."""
    kavya = fx.person(db, "Kavya Menon")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    tara = fx.person(db, "Tara Joshi")
    idea = fx.idea(db, kavya)
    other = fx.idea(db, tara, title="Branch staff retype the same KYC form twice")

    own = fx.attachment(
        db, idea, kavya, purpose="idea", name="proof-screenshot.png"
    )  # the idea's own, checked
    detail = fx.attachment(db, idea, kavya, file_state="personal_data_found", name="calls-with-a-name.xlsx")
    checking = fx.attachment(db, idea, kavya, file_state="checking", name="still-checking.pdf")
    deskfile = fx.attachment(db, idea, meera, name="desk-notes.xlsx")  # this idea's, but not the sender's
    elsewhere = fx.attachment(db, other, tara, name="kyc-form.pdf")  # another idea's
    link = fx.attachment(db, idea, kavya, name="intranet.kfintech.com/ops/R07")
    # a link row as `accept_link` leaves it: its address sealed (a stand-in here, never read)
    db.execute(
        "UPDATE attachments SET kind = 'link', url_encrypted = decode('00', 'hex') WHERE id = %s", (link,)
    )
    for fid, code, words in (
        (own, "file_unavailable", FILE_UNAVAILABLE),
        (detail, "file_has_detail", FILE_HAS_DETAIL),
        (checking, "file_not_checked", FILE_NOT_CHECKED),
        (deskfile, "file_unavailable", FILE_UNAVAILABLE),
        (elsewhere, "file_unavailable", FILE_UNAVAILABLE),
        (link, "file_unavailable", FILE_UNAVAILABLE),
    ):
        err = refused(send, db, idea["idea_id"], kavya["id"], {"text": "Here it is.", "file_ids": [fid]})
        assert (err.status, err.code, err.field, err.message) == (422, code, "file_ids", words), fid
        assert on_entry(db, fid) is None, fid  # nothing was sent
    assert fx.entries(db, idea["id"]) == []

    # The found line says only what S-08 can do: it offers no way to hide a file's detail (DEC-107).
    assert "Hide" not in FILE_HAS_DETAIL and "Remove" in FILE_HAS_DETAIL

    # The same file added for the conversation goes, alone or with words; once sent it is on that message only.
    ok = fx.attachment(db, idea, kavya, name="proof-screenshot.png")
    out = send(db, idea["idea_id"], kavya["id"], {"file_ids": [ok]}, at=fx.at(21, 10))
    [f] = out["entry"]["files"]
    assert (f["id"], f["name"], f["state"]) == (ok, "proof-screenshot.png", "checked")
    assert str(on_entry(db, ok)) == out["entry"]["id"]
    again = refused(send, db, idea["idea_id"], kavya["id"], {"text": "Again.", "file_ids": [ok]})
    assert again.code == "file_unavailable"  # on a message already
    assert on_entry(db, own) is None  # the idea's own file never moved


def test_bld_f095_a_sent_conversation_file_opens_through_the_files_route_for_its_readers(
    db: Any, told: list[dict[str, Any]]
) -> None:
    """BLD-F095: the old `/api/attachments/:id` finds no 1% Club file, so a sent file's View goes to lane C's
    `/api/files/:id/view`, which lets the sharer and the desk open it (DEC-107)."""
    kavya = fx.person(db, "Kavya Menon")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    idea = fx.idea(db, kavya)
    att = fx.attachment(db, idea, kavya, name="branch-call-log.pdf")
    send(db, idea["idea_id"], kavya["id"], {"text": "The call log.", "file_ids": [att]}, at=fx.at(21, 10))
    for who in (kavya, meera):
        [m] = [
            e
            for e in conversation(db, idea["idea_id"], who["id"], at=NOW)["entries"]
            if e["type"] == "message"
        ]
        assert [f["view_url"] for f in m["files"]] == [f"/api/files/{att}/view"], who["name"]
        assert F.get_item(db, att, who["id"])["view_url"] == f"/api/files/{att}/view", who["name"]


def test_dec_107_bld_f062_bld_f095_the_crew_never_opens_a_conversation_file_with_a_customer_detail(
    db: Any, told: list[dict[str, Any]]
) -> None:
    """DEC-107, BLD-F062, BLD-F095: lane C's `rights()` lets the crew open a checked file by its address
    (non-negotiable 7); a conversation file with a customer detail found never opens for them, whoever added it,
    while the sharer and the desk open it."""
    kavya = fx.person(db, "Kavya Menon")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    meghna = fx.person(db, "Meghna Das")
    idea = fx.idea(db, kavya, status="picked")
    fx.join_crew(db, idea, meghna)
    for by in (kavya, meera):
        found = fx.attachment(
            db, idea, by, file_state="personal_data_found", name=f"calls-{by['first_name']}.xlsx"
        )
        db.execute(
            "UPDATE attachments SET state = 'quarantine' WHERE id = %s", (found,)
        )  # never marked clean
        for see in (kavya, meera):  # the sharer (the idea's own) and the desk
            item = F.get_item(db, found, see["id"])
            assert item["customer_detail"] is True and item["view_url"] == f"/api/files/{found}/view"
        for fn in (F.get_item, F.content):  # the row, and the stored copy (`GET /api/files/:id/view`)
            err = refused(fn, db, found, meghna["id"])
            assert (err.status, err.code) == (404, "not_found"), (fn.__name__, by["name"])
    assert conversation(db, idea["idea_id"], meghna["id"], at=NOW)["composer"]["can_attach"] is False


def test_l_merge_bld_f095_a_co_sharer_from_a_merge_has_no_plus_and_never_opens_a_found_conversation_file(
    db: Any, told: list[dict[str, Any]]
) -> None:
    """BLD-F095: a co-sharer from a merge is credited on the idea (`own_codes`) but is not its own sharer. On the
    lead's crew they read the conversation as the crew do, with no "+" (BLD-F063); without a crew place they do
    not read it at all (L-CONVO/2). Either way a conversation file with a customer detail never opens for them."""
    ravi = fx.person(db, "Ravi Nair")
    kavya = fx.person(db, "Kavya Menon")
    sunil = fx.person(db, "Sunil Varma")
    meera = fx.person(db, "Meera Iyer", roles=(("reviewer", None),))
    lead = fx.idea(db, ravi, title="Rejection SMS codes confuse investors")
    joined = fx.idea(db, kavya, status="merged", title="Investors call to ask why a redemption was rejected")
    alone = fx.idea(db, sunil, status="merged", title="The R07 SMS gives a code, not a reason")
    merge = db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_code) VALUES (%s, %s, 'lead_accepted', %s) "
        "RETURNING id",
        (lead["id"], joined["id"], ravi["code"]),
    ).fetchone()["id"]
    db.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, merge_id) VALUES (%s, %s, 'crew', 'merge', %s)",
        (lead["id"], kavya["code"], merge),
    )
    db.execute(
        "INSERT INTO merges (lead_idea_uuid, merged_idea_uuid, via, by_user_id, team_up) "
        "VALUES (%s, %s, 'review_desk', %s, false)",
        (lead["id"], alone["id"], meera["id"]),
    )

    # On the crew: the conversation, with no "+".
    view = conversation(db, lead["idea_id"], kavya["id"], at=NOW)
    assert view["composer"]["can_attach"] is False
    # Not on the crew: no conversation (404, never 403).
    err = refused(conversation, db, lead["idea_id"], sunil["id"], at=NOW)
    assert err.status == 404

    found = fx.attachment(db, lead, ravi, file_state="personal_data_found", name="calls-with-a-name.xlsx")
    db.execute("UPDATE attachments SET state = 'quarantine' WHERE id = %s", (found,))
    for co in (kavya, sunil):
        for fn in (F.get_item, F.content):
            err = refused(fn, db, found, co["id"])
            assert (err.status, err.code) == (404, "not_found"), (fn.__name__, co["name"])
    assert F.get_item(db, found, ravi["id"])["customer_detail"] is True  # the lead's own sharer opens it
