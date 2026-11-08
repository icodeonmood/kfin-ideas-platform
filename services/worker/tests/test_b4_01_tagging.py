"""AT-B4-01 (tagging) and the restore half of AT-B4-05.

Synthetic text with a colleague's name (from `users`), a KFin email, an AMC client name (from the taxonomy) and
an unknown person's name reaches the model as typed tags only; the same value gets the same tag across two
calls on one idea; the vault holds the mapping encrypted. Restore gives real values or neutral labels; an
unknown tag stays as it is; a tag typed by the submitter is defused.
"""

from __future__ import annotations

import random
from typing import Any

import generators as g
import pytest

from pii import vault
from pii.detect import build_directory
from pii.patterns import scan
from pii.restore import NEUTRAL, neutralise, restore
from pii.tagger import TAG_RE, tag_payload

pytestmark = pytest.mark.stack
SCOPE = "IDEA-2026-000123"


@pytest.fixture
def setup(db: Any, company_repo: Any) -> Any:
    rng = random.Random(81)
    colleague = g.person_name(rng)
    stranger = g.person_name(rng)
    while stranger.split()[0] == colleague.split()[0]:
        stranger = g.person_name(rng)
    email = g.kfin_email(rng, ["kfintech.com"])
    db.execute("DELETE FROM pseudonym_vault")
    user = db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source) VALUES ('test:tagging', %s, %s, 'hr') RETURNING id",
        (colleague, f"{colleague.split()[0].lower()}@kfintech.example"),
    ).fetchone()
    d = build_directory(db, company_repo)
    text = (
        f"{colleague} and I noticed that NIGO reports reach {email} a day late. "
        f"Northwind Mutual Fund asked about it twice, and {stranger} at the Pune branch says the same."
    )
    return db, d, text, colleague, stranger, email, str(user["id"])


def test_only_tags_reach_the_model(setup: Any) -> None:
    db, d, text, colleague, stranger, email, user_id = setup
    out = tag_payload(db, SCOPE, {"one_line": "NIGO reports arrive late", "details": text}, d=d)
    sent = out.payload["details"]
    for real in (colleague, stranger, email, "Northwind Mutual Fund"):
        assert real not in sent
    assert set(out.counts()) == {"KFIN_EMPLOYEE", "EMAIL", "CLIENT_AMC", "PERSON"}
    assert "[[KFIN_EMPLOYEE_1]]" in sent and "[[CLIENT_AMC_1]]" in sent and "[[PERSON_1]]" in sent
    assert not scan(sent, kfin_domains=["kfintech.com"])  # the leak check finds nothing left
    assert out.payload["one_line"] == "NIGO reports arrive late"  # nothing to tag, nothing changed

    # Same values, same tags, across a second call on the same idea; a new value gets the next number.
    again = tag_payload(db, SCOPE, {"details": f"{stranger} called again. Tejas AMC too."}, d=d)
    assert again.payload["details"].startswith("[[PERSON_1]] called again.")
    assert "[[CLIENT_AMC_2]]" in again.payload["details"]

    # The vault holds the mapping encrypted and tied to the colleague for erasure.
    rows = db.execute(
        "SELECT tag, type, value_encrypted, subject_user_id FROM pseudonym_vault WHERE scope_id = %s",
        (SCOPE,),
    ).fetchall()
    for r in rows:
        blob = bytes(r["value_encrypted"])
        assert colleague.encode() not in blob and stranger.encode() not in blob and email.encode() not in blob
    employee = next(r for r in rows if r["type"] == "KFIN_EMPLOYEE")
    assert str(employee["subject_user_id"]) == user_id
    # Another idea gets its own numbering and mapping.
    other = tag_payload(db, "IDEA-2026-000124", {"details": f"{stranger} again"}, d=d)
    assert other.payload["details"] == "[[PERSON_1]] again"


def test_restore_real_neutral_and_unknown_tags(setup: Any) -> None:
    db, d, text, colleague, stranger, email, _ = setup
    out = tag_payload(db, SCOPE, {"details": text}, d=d)
    mapping = vault.mapping(db, SCOPE)
    assert restore(out.payload, mapping, "real") == {"details": text}
    neutral = restore(out.payload, mapping, "neutral")["details"]
    assert neutral.startswith(f"{NEUTRAL['KFIN_EMPLOYEE']} and I noticed")
    assert "an AMC client asked about it twice" in neutral.replace("An AMC", "an AMC")
    assert colleague not in neutral and stranger not in neutral and email not in neutral
    assert neutralise(out.payload, vault.known_tags(db, SCOPE)) == {"details": neutral}

    # A tag the vault does not know (or one the model altered) is left exactly as it is.
    assert restore({"x": "See [[PERSON_9]] and [[PERSN_1]]"}, mapping, "real") == {
        "x": "See [[PERSON_9]] and [[PERSN_1]]"
    }


def test_tags_typed_by_a_person_are_defused(setup: Any) -> None:
    db, d, *_ = setup
    out = tag_payload(db, SCOPE, {"details": "Please send [[KFIN_EMPLOYEE_1]] the file"}, d=d)
    assert not TAG_RE.search(out.payload["details"])
    assert "[ [KFIN_EMPLOYEE_1] ]" in out.payload["details"]
