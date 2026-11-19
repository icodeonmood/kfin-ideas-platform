"""BLD-A232: privacy notice 0.2 (P-PRODUCT.privacy, L-AUTH's first sign-in, L-HIDE, DEC-108). No database, no docker:
the notice's text and its version pins are read from the files.

- The version in `apps/web/src/content/privacy-notice.ts` equals PRIVACY_NOTICE_VERSION in `.env.example` (which CI
  copies to `.env`) and in `scripts/uat/rehearse.sh`, or the notice page refuses to render. `scripts/uat/deploy.sh`
  stops at preflight when a server's app env file differs, and never prints a value that is not a version.
- A draft version keeps `draft: true` (the go/no-go reads any version ending in "draft" as not live). A draft
  carries the DPO's three "to be confirmed" lines word for word; a final notice carries none.
- The corrected sentences are pinned. Every sentence in `docs/privacy-notice-0.2.md`, the table Legal and the DPO
  sign, appears in the notice word for word.
- The words follow F-COPY.vocabulary, name no speech vendor or model (DEC-096, DEC-108) and promise no perfect
  detection (review B7)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from tests import helpers

NOTICE = helpers.ROOT / "apps" / "web" / "src" / "content" / "privacy-notice.ts"
DOC = helpers.ROOT / "docs" / "privacy-notice-0.2.md"
DEPLOY = helpers.ROOT / "scripts" / "uat" / "deploy.sh"
PINS = (helpers.ROOT / ".env.example", helpers.ROOT / "scripts" / "uat" / "rehearse.sh")
# The DPO's three lines (HR appraisal, retention, the DPO contact) stay word for word until the DPO's text arrives.
WAITING = (
    "Your contribution history is not used in performance appraisal unless HR policy says so. "
    "(To be confirmed by HR.)",
    "As long as KFintech's record-retention policy requires. If you leave KFintech, the link between your name and "
    "your contributor code is deleted, so your ideas stay but no longer point to you. (Retention period to be "
    "confirmed by Legal.)",
    "For questions or complaints under KFintech's data protection policy, contact the Data Protection Officer. "
    "(Contact details to be confirmed by Legal.)",
)


def _source() -> str:
    return NOTICE.read_text("utf-8")


def _one(pattern: str) -> str:
    found = re.findall(pattern, _source(), re.M)
    assert len(found) == 1, f"privacy-notice.ts: {pattern} matched {len(found)} times"
    return str(found[0])


def _version() -> str:
    return _one(r'^\s*version: "([^"]+)",$')


def _draft() -> bool:
    return _one(r"^\s*draft: (true|false),$") == "true"


def _paragraphs() -> list[str]:
    """Every paragraph: a string on a line of its own (headings sit after `heading:` and are not matched)."""
    body = _source().split("sections:", 1)[1]
    return re.findall(r'^\s*"((?:[^"\\]|\\.)*)",$', body, re.M)


def _headings() -> list[str]:
    return re.findall(r'^\s*(?:title|heading): "([^"]+)",$', _source(), re.M)


def _text() -> str:
    return " ".join(_paragraphs())


def test_a232_l_auth_notice_version_matches_every_pin() -> None:
    version = _version()
    for pin in PINS:
        found = re.findall(r"^PRIVACY_NOTICE_VERSION=(\S+)", pin.read_text("utf-8"), re.M)
        assert found == [version], f"{pin.name}: {found} is not the notice's {version}"


def test_a232_l_auth_a_draft_version_is_marked_draft_and_a_final_one_is_not() -> None:
    assert _version().endswith("draft") == _draft()


def test_a232_p_product_privacy_the_dpos_three_lines_wait_while_draft() -> None:
    pending = [p for p in _paragraphs() if "to be confirmed" in p.lower()]
    if _draft():
        assert pending == list(WAITING)
    else:
        assert pending == [], "a final notice carries no 'to be confirmed' line"


@pytest.mark.parametrize(
    "sentence",
    [
        # DEC-104, P-PRODUCT.privacy: names and who reads what
        "The review desk and the Ones Committee see your name.",
        "Only you, the review desk and the Ones Committee read your words. Everyone else sees the short summary.",
        "Your crew also sees the idea's checked files, its conversation, the review desk's questions and your "
        "answers, and the decision with its reason. A file that holds a customer detail is the exception (see Never "
        "share). Once a build team is chosen, it sees the conversation too, and a colleague you mention in a message "
        "sees that message.",
        "Your points are private to you.",
        # DEC-103, L-HIDE.rules/3, /4, /6, /7: hidden as far as the checks find, Show it, the desk's own hiding
        "Don't type or say them.",
        "our checks look for it and hide it before any other person or service sees your text. The review desk can "
        "hide one the checks missed.",
        "The full detail is stored encrypted, and only you can see it. If it isn't a customer's detail, such as a "
        "scheme code, you can choose Show it and give a reason. It is then no longer hidden, and the review desk sees "
        "that you showed it and why.",
        # DEC-107: a file with a detail
        "A file that holds a customer detail is not hidden. It opens only for you, the review desk and the Ones "
        "Committee, and they see it as it is.",
        # DEC-108: voice notes, the pronoun, listening
        "it goes to an Indian speech service to turn it into text.",
        "The recording goes as you spoke it, because a recording can't be hidden. So don't say a customer's details "
        "in a voice note.",
        "How you'd like us to refer to you, if you choose to tell us in Profile.",
        "If you chose 'she' or 'he' in Profile, that goes to the service with your voice note, so its English copy "
        "refers to you correctly.",
        "The text that comes back is checked, and customers' details the checks find are hidden before anyone else, "
        "or any other service, sees it.",
        "When you send an idea, its draft, with customers' details hidden, also goes to that service so it can be "
        "read aloud to the review desk. This happens whether or not you recorded a voice note.",
        # Non-negotiable 2, review B7: labels before the assistant, as far as the checks find
        "Our checks look for names and personal details in your text and replace them with labels before the AI "
        "assistant reads it.",
    ],
)
def test_a232_p_product_privacy_l_hide_dec108_corrected_sentences(sentence: str) -> None:
    assert sentence in _text()


def test_a232_f_copy_vocabulary_no_banned_words_no_vendor_no_absolute_promise() -> None:
    text = " ".join([*_headings(), *_paragraphs()]).lower()
    # F-COPY.vocabulary's never-say words; DEC-096: no vendor or model named; review B7 and DEC-104: no promise the
    # system cannot keep.
    banned = (
        *("block", "duplicate", "rejected", "appeal", "invalid", "already solved", "please", "transcript"),
        *("sarvam", "saaras", "mayura", "bulbul"),
        *("never sees", "public wall", "slips in"),
    )
    for word in banned:
        assert word not in text, word
    assert "Voice notes and listening" in _headings()  # review B2: read-aloud reaches every idea sent


def _doc_cells(section: str, column: int) -> list[str]:
    """One column of the first table under a `## ` heading of the change doc."""
    part = DOC.read_text("utf-8").split(f"## {section}\n", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in part.splitlines() if line.startswith("| ") and not line.startswith("|---")]
    return [r.strip("|").split(" | ")[column].strip() for r in rows[1:]]


def test_a232_p_product_privacy_the_table_legal_signs_is_the_text_that_ships() -> None:
    text = _text()
    new = [c for c in _doc_cells("Changed and new sentences", 2) if not c.startswith("Removed")]
    waiting = [
        c for c in _doc_cells("Waiting for the product lead", 1) if not c.startswith("The whole section")
    ]
    dpo = _doc_cells("Still waiting for the DPO", 1)
    assert len(new) >= 30 and len(waiting) == 3 and dpo == list(WAITING)
    for sentence in [*new, *waiting]:
        assert sentence in text, sentence


# ---- scripts/uat/deploy.sh: a server's version must be this build's -----------------------------------------------


def _deploy(tmp_path: Path, version_line: str) -> subprocess.CompletedProcess[str]:
    """deploy.sh up to its first stop. `docker` on PATH is a stub that refuses, so nothing real can start; the
    database env file is empty, so a run that passes the notice check stops at the next one (POSTGRES_PASSWORD)."""
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "docker").write_text("#!/bin/sh\necho 'docker stub' >&2\nexit 97\n")
    (stub / "docker").chmod(0o755)
    app, db = tmp_path / "app.env", tmp_path / "db.env"
    app.write_text(f"APP_ENV=uat\n{version_line}\n")
    db.write_text("")
    env = {
        **os.environ,
        "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
        "UAT_DATA_DIR": str(tmp_path / "d"),
    }
    return subprocess.run(
        ["bash", str(DEPLOY), str(app), str(db)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )


def test_a232_l_auth_deploy_stops_on_another_version_and_names_both(tmp_path: Path) -> None:
    run = _deploy(tmp_path, "PRIVACY_NOTICE_VERSION=0.1-draft")
    assert run.returncode == 1 and "docker stub" not in run.stderr
    assert f"is 0.1-draft, but this build's privacy notice is {_version()}" in run.stderr


@pytest.mark.parametrize(
    "line",
    ["PRIVACY_NOTICE_VERSION=pasted-by-mistake-value", "PRIVACY_NOTICE_VERSION=", "# no version at all"],
)
def test_a232_l_auth_deploy_stops_without_printing_a_value_that_is_not_a_version(
    tmp_path: Path, line: str
) -> None:
    run = _deploy(tmp_path, line)
    assert run.returncode == 1 and "docker stub" not in run.stderr
    assert "must equal the version in apps/web/src/content/privacy-notice.ts" in run.stderr
    assert "pasted-by-mistake" not in run.stdout + run.stderr and _version() not in run.stdout + run.stderr


def test_a232_l_auth_deploy_passes_the_notice_check_on_this_builds_version(tmp_path: Path) -> None:
    run = _deploy(tmp_path, f"PRIVACY_NOTICE_VERSION={_version()}")
    assert run.returncode == 1 and "PRIVACY_NOTICE_VERSION" not in run.stderr
    assert "POSTGRES_PASSWORD must be" in run.stderr  # the next preflight check, before anything starts
