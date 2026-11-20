"""BLD-C200 (DEC-120 fixed; non-negotiable 2; L-DRAFT.voice; DEC-108 (1), (3)): text for the speech service is
tagged like a model call. A voice note's words go to mayura for the English copy only after the gateway's own
tagger (`pii.tagger.tag_payload`) has put tags in place of names, and after its leak check (`gateway.core.leak_hits`)
has passed on the tagged text; every tag must come back intact; the sharer reads their English copy with their own
words; customers' details stay hidden. Against a migrated test database (the `db` fixture, never the demo database)
and the fake Sarvam of `tests/sarvam_fakes.py`, which records what it was sent. Synthetic people and values only.

Listen (L-LISTEN) is not changed here: the pack draws no spoken form for a tagged name, so the lead decides it."""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest

from core import killswitch
from core.config import get_settings
from core.crypto import CryptoError, decrypt_json
from gateway import sarvam
from pii import tagger as tagger_mod
from pii import vault
from pii.detect import clear_cache
from speech import drafts
from tests.sarvam_fakes import FakeSarvamWs, configure, ws_server
from tests.web import people
from voice.service import Limits

COLLEAGUE = "Devika Raghunathan"  # synthetic: a colleague in `users`, named in the sharer's voice note
PAN = "ABCPE1234F"  # synthetic
HEARD = f"{COLLEAGUE} ne bataya ki investor ka {PAN} do baar type hota hai"
MASKED = f"{COLLEAGUE} ne bataya ki investor ka PAN ••••4F do baar type hota hai"  # hide_text's copy of HEARD
SECOND = bytes(drafts.BYTES_PER_SECOND)


def english_of(text: str) -> str:
    """mayura as the fake plays it: the Hinglish sentence in English, tags copied as they are."""
    return text.replace(" ne bataya ki investor ka ", " said the investor's ").replace(
        " do baar type hota hai", " is typed twice"
    )


@pytest.fixture
def world(db: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Sarvam's route with a synthetic key, a sharer with a draft, a colleague in `users`, and the translate calls
    recorded as sent. `reply` turns the text sent into mayura's reply."""
    monkeypatch.setenv("VAULT_ENCRYPTION_KEY", "t" * 40)  # synthetic, tests only
    configure(monkeypatch)
    monkeypatch.setattr(drafts.killswitch, "is_on", lambda name, conn=None: True)
    monkeypatch.setattr("voice.service.limits", lambda: Limits(max_waiting=3, max_per_hour=10))
    monkeypatch.setattr(drafts, "_ensure_reaper", lambda: None)
    killswitch.clear_cache()
    clear_cache()
    sent: list[dict[str, Any]] = []
    reply: dict[str, Callable[[str], str]] = {"make": english_of}

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body)
        return httpx.Response(
            200, json={"translated_text": reply["make"](body["input"]), "source_language_code": "hi-IN"}
        )

    monkeypatch.setattr(sarvam, "_transport", httpx.MockTransport(handle))
    drafts._live.clear()
    with people(db) as make:
        sharer = make()
        colleague = db.execute(
            "INSERT INTO users (emp_id_hash, name, email, source) VALUES ('test:c200', %s, %s, 'hr') RETURNING id",
            (COLLEAGUE, "devika.r@kfintech.example"),
        ).fetchone()
        idea = db.execute(
            "INSERT INTO ideas (contributor_code, status) VALUES (%s, 'draft') RETURNING id",
            (sharer.contributor_code,),
        ).fetchone()
        yield {
            "db": db, "sharer": sharer, "colleague_id": str(colleague["id"]), "idea": str(idea["id"]),
            "sent": sent, "reply": reply,
        }  # fmt: skip
        db.execute("DELETE FROM voice_streams WHERE idea_uuid = %s", (str(idea["id"]),))
        db.execute("DELETE FROM ideas WHERE id = %s", (str(idea["id"]),))
        db.execute("DELETE FROM pseudonym_vault WHERE scope_id = %s", (f"DRAFT-{idea['id']}",))
        db.execute("DELETE FROM users WHERE id = %s", (str(colleague["id"]),))
    drafts._live.clear()
    monkeypatch.setattr(sarvam, "_transport", None)
    get_settings.cache_clear()
    clear_cache()


def english(w: dict[str, Any], masked: str = MASKED) -> tuple[str | None, bool | None, str | None]:
    return drafts._english(w["db"], "stream-c200", masked, "hi-IN", None, idea_uuid=w["idea"])


def leak_alerts(db: Any, scope: str) -> list[Any]:
    """This test's own `alert.leak_check` rows from the speech path (its draft's scope is new), so the order the tests
    run in never changes the count."""
    rows = db.execute(
        "SELECT after FROM audit_log WHERE action = 'alert.leak_check' AND entity = 'speech:sarvam' "
        "AND after->>'ref_id' = %s ORDER BY at",
        (scope,),
    ).fetchall()
    return [r["after"] for r in rows]


def test_BLD_C200_L_DRAFT_voice_a_colleagues_name_never_reaches_the_speech_service_and_the_sharer_reads_it_back(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch, captured_logs: io.StringIO
) -> None:
    db, sharer, idea = world["db"], world["sharer"], world["idea"]
    code = sharer.contributor_code
    with ws_server(monkeypatch, FakeSarvamWs(heard=HEARD)) as fake:
        sid = str(drafts.start(db, idea_uuid=idea, by_code=code, user_id=sharer.user_id)["id"])
        drafts.chunk(db, sid, idea_uuid=idea, by_code=code, seq=0, data=SECOND)
        done = drafts.end(db, sid, idea_uuid=idea, by_code=code)
    # What reached the fake service: the audio, and for the English copy a tag where the name was.
    assert len(world["sent"]) == 1
    went = world["sent"][0]["input"]
    assert COLLEAGUE not in went and "Devika" not in went and "Raghunathan" not in went
    assert went == "[[KFIN_EMPLOYEE_1]] ne bataya ki investor ka PAN ••••4F do baar type hota hai"
    assert PAN not in went  # customers' details are still hidden from the service
    on_the_socket = json.dumps(fake.received, ensure_ascii=False)
    assert "Devika" not in on_the_socket and PAN not in on_the_socket
    # The sharer reads their own words, and the English copy with the colleague's name as they said it.
    assert done["state"] == "done" and done["text"] == HEARD and done["translated"] is True
    assert done["text_en"] == f"{COLLEAGUE} said the investor's PAN ••••4F is typed twice"
    assert PAN not in done["text_en"] and done["translation_failure"] is None
    row = db.execute("SELECT text_en_encrypted FROM voice_streams WHERE id = %s", (sid,)).fetchone()
    assert (
        decrypt_json(bytes(row["text_en_encrypted"]), f"voice_streams.text_en:{sid}")["text"]
        == done["text_en"]
    )
    msg = drafts.voice_to_message(db, sid, idea_uuid=idea, by_code=code)
    assert msg is not None and msg.text_en == done["text_en"] and PAN not in msg.text_masked
    # The tag is the draft's own, as a model call on the same words gets it, held for the colleague's erasure.
    scope = f"DRAFT-{idea}"
    held = db.execute(
        "SELECT tag, type, subject_user_id FROM pseudonym_vault WHERE scope_id = %s", (scope,)
    ).fetchall()
    assert [(r["tag"], r["type"], str(r["subject_user_id"])) for r in held] == [
        ("[[KFIN_EMPLOYEE_1]]", "KFIN_EMPLOYEE", world["colleague_id"])
    ]
    assert tagger_mod.tag_payload(db, scope, COLLEAGUE).payload == "[[KFIN_EMPLOYEE_1]]"
    metered = db.execute(
        "SELECT call, outcome FROM speech_calls WHERE ref_id = %s", (f"stream:{sid}",)
    ).fetchall()
    assert [(r["call"], r["outcome"]) for r in metered] == [("translate", "ok")]
    logged = captured_logs.getvalue()
    assert "Devika" not in logged and PAN not in logged and "bataya" not in logged


def test_BLD_C200_L_DRAFT_voice_each_name_and_client_goes_as_a_tag_and_comes_back_for_the_sharer(
    world: dict[str, Any],
) -> None:
    masked = f"{COLLEAGUE} ne bataya ki investor ka PAN ••••4F do baar type hota hai. {COLLEAGUE} ne phir se bataya."
    text_en, translated, failure = english(world, masked)
    went = world["sent"][0]["input"]
    assert went.count("[[KFIN_EMPLOYEE_1]]") == 2 and "Devika" not in went  # the same name, the same tag
    assert failure is None and translated is True and text_en is not None
    assert text_en.startswith(f"{COLLEAGUE} said the investor's PAN ••••4F is typed twice.")
    assert text_en.count(COLLEAGUE) == 2


@pytest.mark.parametrize(
    "broken",
    [
        lambda t: t.replace("[[KFIN_EMPLOYEE_1]]", "Devika"),  # the tag dropped for a guess
        lambda t: t.replace("[[KFIN_EMPLOYEE_1]]", "[[KFIN_कर्मचारी_1]]"),  # the tag translated
        lambda t: t.replace("[[KFIN_EMPLOYEE_1]]", "[[KFIN_EMPLOYEE_ 1]]"),  # the tag split
        lambda t: t.replace("[[KFIN_EMPLOYEE_1]]", "[KFIN_EMPLOYEE_1]"),  # a bracket lost
        lambda t: t.replace("[[KFIN_EMPLOYEE_1]]", "[[KFIN_EMPLOYEE_2]]"),  # a tag that was never sent
        lambda t: t + " [[PERSON_1]]",  # one sent tag back, and another nobody sent
    ],
    ids=["dropped", "translated", "split", "bracket", "unknown", "extra"],
)
def test_BLD_C200_L_DRAFT_voice_a_broken_tag_fails_the_english_copy_cleanly_never_as_a_leak(
    world: dict[str, Any], broken: Callable[[str], str]
) -> None:
    world["reply"]["make"] = lambda text: broken(english_of(text))
    scope = f"DRAFT-{world['idea']}"
    before = len(leak_alerts(world["db"], scope))
    text_en, translated, failure = english(world)
    assert (text_en, translated, failure) == (None, None, "translation_hosted_tags_broken")
    assert len(leak_alerts(world["db"], scope)) == before  # a failed reply, never a leak: no value was sent


def test_BLD_C200_L_DRAFT_voice_a_broken_tag_keeps_the_sharers_own_words_through_the_stream(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    world["reply"]["make"] = lambda text: english_of(text).replace("[[KFIN_EMPLOYEE_1]]", "[[KFIN_ 1]]")
    db, sharer, idea = world["db"], world["sharer"], world["idea"]
    with ws_server(monkeypatch, FakeSarvamWs(heard=HEARD)):
        sid = str(drafts.start(db, idea_uuid=idea, by_code=sharer.contributor_code)["id"])
        drafts.chunk(db, sid, idea_uuid=idea, by_code=sharer.contributor_code, seq=0, data=SECOND)
        done = drafts.end(db, sid, idea_uuid=idea, by_code=sharer.contributor_code)
    assert done["state"] == "done" and done["text"] == HEARD and done["text_en"] is None
    assert done["translation_failure"] == "translation_hosted_tags_broken"


def test_BLD_C200_the_leak_check_stops_a_payload_with_a_pattern_hit_before_anything_is_sent(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tagger_mod, "detect", lambda *a, **k: [])  # detection misses everything
    monkeypatch.setattr(drafts, "mask_for_service", lambda text: text)  # and so did the masking before it
    db = world["db"]
    scope = f"DRAFT-{world['idea']}"
    metered = db.execute("SELECT count(*) AS n FROM speech_calls").fetchone()["n"]
    before = leak_alerts(db, scope)
    with pytest.raises(sarvam.SarvamFailed) as refused:
        sarvam.tag_for_service(f"Investor PAN {PAN} again", conn=db, scope_id=f"DRAFT-{world['idea']}")
    assert refused.value.code == "unmasked_text"
    text_en, translated, failure = english(world, f"{COLLEAGUE} ne investor ka {PAN} bheja")
    assert (text_en, translated, failure) == (None, None, "translation_unmasked_text")
    assert world["sent"] == []  # nothing reached the service
    new = leak_alerts(db, scope)[len(before) :]
    assert new == [{"patterns": ["pan"], "ref_id": scope}] * 2  # one alert per refusal, pattern ids only
    assert PAN not in json.dumps(new)
    assert db.execute("SELECT count(*) AS n FROM speech_calls").fetchone()["n"] == metered  # no call made


def test_BLD_C200_the_tag_check_lets_only_a_reply_with_every_tag_intact_through() -> None:
    two = sarvam.Outgoing(text="[[KFIN_EMPLOYEE_1]] and [[CLIENT_AMC_1]]", tags={
        "[[KFIN_EMPLOYEE_1]]": "KFIN_EMPLOYEE", "[[CLIENT_AMC_1]]": "CLIENT_AMC",
    })  # fmt: skip
    none = sarvam.Outgoing(text="No names.", tags={})
    twice = sarvam.Outgoing(
        text="[[KFIN_EMPLOYEE_1]] said it. [[KFIN_EMPLOYEE_1]] said it again.",
        tags={"[[KFIN_EMPLOYEE_1]]": "KFIN_EMPLOYEE"},
    )
    assert sarvam.tags_back(twice, "[[KFIN_EMPLOYEE_1]] said so. [[KFIN_EMPLOYEE_1]] said so again.")
    assert sarvam.tags_back(two, "[[CLIENT_AMC_1]] told [[KFIN_EMPLOYEE_1]].") == (
        "[[CLIENT_AMC_1]] told [[KFIN_EMPLOYEE_1]]."
    )
    assert sarvam.tags_back(none, "No names here.") == "No names here."
    for sent, reply in (
        (two, "[[CLIENT_AMC_1]] told someone."),  # one tag missing
        (
            two,
            "[[CLIENT_AMC_1]] told [[KFIN_EMPLOYEE_1]] and KFIN_EMPLOYEE_1.",
        ),  # all back, plus a piece of one
        (none, "No names [["),  # a bracket pair with no tag sent
        (none, "No names [[PERSON_1]]"),  # a tag nobody sent
        (twice, "[[KFIN_EMPLOYEE_1]] said it again."),  # a tag sent twice, back once
    ):
        with pytest.raises(sarvam.SarvamFailed) as broken:
            sarvam.tags_back(sent, reply)
        assert broken.value.code == "hosted_tags_broken"


def test_BLD_C200_english_needs_no_service_and_sends_nothing(world: dict[str, Any]) -> None:
    text_en, translated, failure = drafts._english(
        world["db"], "stream-c200", MASKED, "en-IN", None, idea_uuid=world["idea"]
    )
    assert (text_en, translated, failure) == (MASKED, False, None) and world["sent"] == []
    assert vault.known_tags(world["db"], f"DRAFT-{world['idea']}") == {}


# ---- review fixes (BLD-C200): an error in the tagging or the swapping back never costs the person their words -------


def ended_in_a_transaction(w: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> tuple[str, dict[str, Any]]:
    """A note heard and ended inside the caller's own transaction, so `store.done` must still commit on the same
    connection after the failure."""
    db, code, idea = w["db"], w["sharer"].contributor_code, w["idea"]
    with ws_server(monkeypatch, FakeSarvamWs(heard=HEARD)):
        sid = str(drafts.start(db, idea_uuid=idea, by_code=code)["id"])
        drafts.chunk(db, sid, idea_uuid=idea, by_code=code, seq=0, data=SECOND)
        with db.transaction():
            done = drafts.end(db, sid, idea_uuid=idea, by_code=code)
    return sid, done


def kept_without_english(db: Any, sid: str, done: dict[str, Any]) -> None:
    assert done["state"] == "done" and done["text"] == HEARD and done["text_en"] is None
    assert done["translation_failure"] == drafts.TAGGING_FAILED == "translation_tagging_failed"
    row = db.execute(
        "SELECT state, failure, text_en_encrypted, own_words_sealed FROM voice_streams WHERE id = %s", (sid,)
    ).fetchone()
    assert (row["state"], row["failure"], row["text_en_encrypted"]) == ("done", drafts.TAGGING_FAILED, None)
    assert row["own_words_sealed"] is not None  # the person's words are kept, sealed for them


def test_BLD_C200_L_DRAFT_voice_a_tagger_that_fails_in_the_database_keeps_the_words_and_sends_nothing(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch, captured_logs: io.StringIO
) -> None:
    def failing(conn: Any, scope_id: str, payload: Any, *, d: Any = None) -> Any:
        conn.execute("SELECT no_such_column FROM users")  # a database error, mid-tagging
        raise AssertionError("unreachable")

    monkeypatch.setattr(sarvam, "tag_payload", failing)
    sid, done = ended_in_a_transaction(world, monkeypatch)
    kept_without_english(world["db"], sid, done)
    assert world["sent"] == []  # nothing reached the service
    logged = captured_logs.getvalue()
    assert "voice_stream.translation_tagging_failed" in logged and "UndefinedColumn" in logged
    assert "Devika" not in logged and PAN not in logged


def test_BLD_C200_L_DRAFT_voice_a_vault_that_cannot_be_opened_keeps_the_words_and_no_name_was_sent(
    world: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def cannot_open(*a: Any, **k: Any) -> bytes:
        raise CryptoError("open_failed")

    monkeypatch.setattr(vault, "decrypt_bytes", cannot_open)  # the swapping back cannot read the vault
    sid, done = ended_in_a_transaction(world, monkeypatch)
    kept_without_english(world["db"], sid, done)
    # The failure is after the service's reply: what reached it was the tagged copy only, never the name.
    assert [b["input"] for b in world["sent"]] == [
        "[[KFIN_EMPLOYEE_1]] ne bataya ki investor ka PAN ••••4F do baar type hota hai"
    ]
