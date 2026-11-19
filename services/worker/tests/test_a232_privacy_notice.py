"""BLD-A232: privacy notice 0.2 (P-PRODUCT.privacy, L-AUTH's first sign-in). No database: the notice's text and its
version pins are read from the files. The version in `apps/web/src/content/privacy-notice.ts` equals
PRIVACY_NOTICE_VERSION in `.env.example` (which CI copies to `.env`) and in `scripts/uat/rehearse.sh`, or the
notice page refuses to render; a draft version keeps `draft: true` (the go/no-go reads any version ending in "draft"
as not live); a draft carries the DPO's three "to be confirmed" lines and a final notice none. The words follow
F-COPY.vocabulary and name no speech vendor (DEC-096, DEC-108)."""

from __future__ import annotations

import re

from tests import helpers

NOTICE = helpers.ROOT / "apps" / "web" / "src" / "content" / "privacy-notice.ts"
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


def _version() -> str:
    m = re.search(r'^\s*version: "([^"]+)",$', _source(), re.M)
    assert m, "privacy-notice.ts has no version"
    return m.group(1)


def _draft() -> bool:
    m = re.search(r"^\s*draft: (true|false),$", _source(), re.M)
    assert m, "privacy-notice.ts has no draft flag"
    return m.group(1) == "true"


def _paragraphs() -> list[str]:
    """Every paragraph: a string on a line of its own (headings sit after `heading:` and are not matched)."""
    body = _source().split("sections:", 1)[1]
    return re.findall(r'^\s*"((?:[^"\\]|\\.)*)",$', body, re.M)


def test_a232_l_auth_notice_version_matches_every_pin() -> None:
    version = _version()
    for pin in PINS:
        found = re.findall(r"^PRIVACY_NOTICE_VERSION=(\S+)", pin.read_text("utf-8"), re.M)
        assert found == [version], f"{pin.name}: {found} is not the notice's {version}"


def test_a232_l_auth_a_draft_version_is_marked_draft_and_a_final_one_is_not() -> None:
    assert _version().endswith("draft") == _draft()


def test_a232_p_product_privacy_the_dpos_three_lines_wait_while_draft() -> None:
    paragraphs = _paragraphs()
    pending = [p for p in paragraphs if "to be confirmed" in p.lower()]
    if _draft():
        assert pending == list(WAITING)
    else:
        assert pending == [], "a final notice carries no 'to be confirmed' line"


def test_a232_p_product_privacy_covers_names_words_details_voice_and_suggestions() -> None:
    text = " ".join(_paragraphs())
    for must in (
        "the review desk and the Ones Committee",  # DEC-104: who reads your words
        "Everyone else sees the short summary",  # DEC-104
        "Your points are private to you",  # DEC-104
        "it is hidden",  # DEC-103
        "only you can see it",  # DEC-103
        "opens only for you, the review desk and the Ones Committee",  # DEC-107
        "an Indian speech service",  # DEC-108
        "a recording can't be masked",  # DEC-108: the voice exception, said plainly
        "People decide every change",  # §5, BLD-121
    ):
        assert must in text, must


def test_a232_f_copy_vocabulary_no_banned_words_and_no_vendor() -> None:
    text = " ".join(_paragraphs()).lower()
    for word in ("block", "duplicate", "rejected", "appeal", "invalid", "already solved", "please", "sarvam"):
        assert word not in text, word
    assert "public wall" not in text  # DEC-104: names show on the Wall unless hidden, not only if agreed
