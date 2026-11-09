"""Branded HTML email (DEC-061, BLD-125): every template, in the sent form (light inline, dark through the style
block) and the dark preview, matches its snapshot; values never become markup; the message is multipart.

Update the snapshots after an intended change with `UPDATE_SNAPSHOTS=1 pytest tests/test_email_html.py`."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest

from comms import email_html
from comms.templates import _load

REPO = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
SNAPS = Path(__file__).parent / "snapshots" / "email"
BASE = "https://ideas.example"
NAMES = sorted(p.stem for p in (REPO / "comms" / "templates").glob("*.md") if p.stem != "index")


def _links() -> dict[str, str]:
    keys = ("idea", "my_ideas", "wall", "item", "request", "write", "delivery")
    return {k: f"{BASE}/{k.replace('_', '-')}" for k in keys}


SAMPLE: dict[str, Any] = {
    "recipient": {"first_name": "Kavya"},
    "idea": {
        "id": "IDEA-2026-000123",
        "one_line": "Fill the bank name from the IFSC on change-of-bank forms",
        "strength": 4,
        "next_best": ["Say who feels this most", "Add how often it happens"],
    },
    "links": _links(),
    "cluster": {
        "id": "CL-2026-0007",
        "name": "Change of bank, fewer steps",
        "description": "Ideas about shortening the change-of-bank journey",
        "other_count": 4,
    },
    "reviewer": {"name": "Nikhil Rao", "note": "A clear problem and a fair estimate."},
    "outcome": {"grouped": True, "standalone": False, "text": "Grouped", "reason": "It fits better with IT."},
    "next_step": {"text": "The committee assesses grouped ideas in the next round."},
    "question": {"text": "How many forms a week does this affect?", "due_date": "18 Nov 2026"},
    "review": {"due_date": "16 Nov 2026"},
    "redirect": {
        "team": "IT helpdesk",
        "url": "https://helpdesk.example/new",
        "message": "This is a laptop fault.",
    },
    "breach": {"days_late": 2, "limit_wd": 5},
    "item": {"label": "Review of IDEA-2026-000123", "due_date": "16 Nov 2026", "owner_name": "Nikhil Rao"},
    "join": {"count": 3, "count_word": "three", "names": "Farhan and Lakshmi", "names_visible": True},
    "member": {"name": "Farhan Qureshi"},
    "reminder": {"share_percent": 60},
    "request": {"context": "We run a similar check at the service centres."},
    "requester": {"lob_name": "Investor servicing"},
    "solution": {"id": "SOL-2026-0003", "title": "IFSC look-up on bank forms"},
    "writeup": {"approved": True, "sent_back": False, "solution_id": "SOL-0007"},
    "one": {
        "number": 17,
        "display": "No. 17, Ananya Rao",
        "swap_until": "13 Jan 2027",
        "tier": 1,
        "tier_name": "Spark",
    },
    "tier": {
        "to": 2,
        "to_name": "Glow",
        "from_name": "Spark",
        "up": True,
        "down": False,
        "committee_message": "You saw a form everyone tolerated and refused to tolerate it.",
    },
    "ones": {
        "count": 3,
        "count_word": "three",
        "list": "No. 17, Ananya Rao; No. 18, Farhan Qureshi; One No. 19",
    },
    "removal": {
        "reason": "Membership lapsed after 12 months without a delivery, mentoring or a new accepted idea."
    },
    "delivery": {
        "label": "IFSC look-up on bank forms",
        "phase_words": "Being built",
        "mark_words": "30 days",
        "outcome_words": "Shipped",
        "milestone": "First AMC live",
        "started": True,
        "building": True,
        "shipped": False,
        "blocked": False,
        "plan_late": False,
        "measured": False,
        "resolved": False,
        "closed": False,
    },
}


def _check_snapshot(name: str, html: str) -> None:
    path = SNAPS / name
    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        if os.environ.get("UPDATE_SNAPSHOTS") != "1":
            pytest.fail(f"new snapshot written: {name}; check it and run again")
    assert html == path.read_text(encoding="utf-8"), f"{name} changed; UPDATE_SNAPSHOTS=1 if intended"


# The renderer sets `show_number` only for the One's own induction and tier change (Ember review).
NUMBER_TEMPLATES = ("one-inducted", "one-tier-changed")


def _sample(name: str) -> dict[str, Any]:
    return {**SAMPLE, "one": {**SAMPLE["one"], "show_number": name in NUMBER_TEMPLATES}}


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("theme", ["auto", "dark"])
def test_every_template_matches_its_snapshot(name: str, theme: Any) -> None:
    email = email_html.compose(_load(REPO, name), _sample(name), BASE, theme)
    _check_snapshot(f"{name}.html" if theme == "auto" else f"{name}.dark.html", email.html)


@pytest.mark.parametrize("name", NAMES)
def test_every_template_is_safe_and_complete(name: str) -> None:
    email = email_html.compose(_load(REPO, name), _sample(name), BASE)
    html = email.html
    assert "{{" not in html and "" not in html and "<svg" not in html
    assert html.count(email_html.TAGLINE) == 1 and html.count(email_html.ENDORSEMENT) == 1
    assert f'src="{BASE}/{email_html.MARK_FILE}"' in html
    hrefs = re.findall(r'href="([^"]+)"', html)
    assert all(h.startswith(("https://", "http://")) for h in hrefs), hrefs
    assert 'width="600"' in html and "prefers-color-scheme: dark" in html and "[data-ogsc]" in html
    assert email.text.strip() and "**" not in email.text and "{{" not in email.text


def test_values_never_become_markup() -> None:
    tpl = _load(REPO, "reviewed")
    data = {
        **SAMPLE,
        "idea": {**SAMPLE["idea"], "one_line": '[win](javascript:alert(1)) **bold** <script>x</script> "q"'},
        "reviewer": {"name": "<b>Nikhil</b>", "note": "[click](https://evil.example)"},
    }
    html = email_html.compose(tpl, data, BASE).html
    assert "<script>" not in html and 'href="javascript' not in html
    assert "&lt;script&gt;" in html and "&lt;b&gt;Nikhil&lt;/b&gt;" in html  # shown as typed, as text
    assert 'href="https://evil.example"' not in html  # a value can't make a link
    assert "**bold**" in html  # nor bold


def test_unsafe_link_addresses_are_dropped() -> None:
    tpl = _load(REPO, "one-inducted")
    data = {**SAMPLE, "links": {**SAMPLE["links"], "my_ideas": "javascript:alert(1)"}}
    html = email_html.compose(tpl, data, BASE).html
    assert "javascript:" not in html and "Open your dashboard" in html  # the words stay, the link goes


def test_the_first_link_paragraph_is_the_button_and_the_one_block_shows_the_tier() -> None:
    data = {
        k: v for k, v in _sample("one-inducted").items() if k != "tier"
    }  # an induction has no tier change
    email = email_html.compose(_load(REPO, "one-inducted"), data, BASE)
    assert email.html.count('bgcolor="#2B5BFF"') == 1
    assert "No. 17" in email.html and "Tier 1, Spark" in email.html and "#FF5B14" in email.html
    assert email.text.startswith("Your number: No. 17 (Tier 1, Spark)\n")  # the text part has it too


@pytest.mark.parametrize("name", ["one-message-invited", "one-removed", "ones-announced", "submitted"])
def test_the_number_block_is_only_for_the_ones_own_news(name: str) -> None:
    """A peer's invitation, a removal or any other message never shows a number (Ember review)."""
    email = email_html.compose(_load(REPO, name), _sample(name), BASE)
    assert "Your number" not in email.html and "Your number" not in email.text


def test_the_render_sets_show_number_only_for_the_recipient() -> None:
    from comms import render

    assert render.YOUR_NUMBER_EVENTS == ("ones.inducted", "ones.tier_changed")


def test_the_idea_card_shows_only_when_the_message_does_not_quote_the_idea() -> None:
    quoted = email_html.compose(_load(REPO, "reviewed"), SAMPLE, BASE)
    assert ">Idea</p>" not in quoted.html  # reviewed.md quotes the idea in its first line
    assert not quoted.text.startswith("Idea: ")
    card = email_html.compose(_load(REPO, "one-inducted"), _sample("one-inducted"), BASE)
    if ">Idea</p>" in card.html:  # and the text part carries the card whenever the HTML does
        assert f"Idea: {SAMPLE['idea']['one_line']}" in card.text


def test_plain_text_part() -> None:
    text = email_html.to_text(
        "Hi **Kavya**,\n\n[See your idea](https://ideas.example/idea)\n\n## Next\nSoon."
    )
    assert text == "Hi Kavya,\n\nSee your idea: https://ideas.example/idea\n\nNext\nSoon.\n"


def test_the_message_is_multipart_with_text_first() -> None:
    from comms.send import build_message

    email = email_html.compose(_load(REPO, "submitted"), SAMPLE, BASE)
    msg = build_message("kavya@kfintech.example", email)
    assert msg.get_content_type() == "multipart/alternative"
    assert [p.get_content_type() for p in msg.iter_parts()] == ["text/plain", "text/html"]


def test_digest_keeps_each_subject_as_a_heading() -> None:
    sections = [(_load(REPO, "submitted"), SAMPLE), (_load(REPO, "reviewed"), SAMPLE)]
    email = email_html.digest(sections, BASE)
    assert email.subject == "Your 1% Club update: 2 new"
    assert email.html.count("<h2") >= 2 and email.html.count(email_html.TAGLINE) == 1


def _luminance(hex_colour: str) -> float:
    rgb = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_colours_meet_aa(theme: str) -> None:
    p = email_html.PALETTES[theme]
    for fg in ("text", "muted", "link"):
        assert _contrast(p[fg], p["card"]) >= 4.5, (theme, fg)
    assert _contrast(p["text"], p["panel"]) >= 4.5
    assert _contrast(email_html.WHITE, email_html.ELECTRIC) >= 4.5
    assert _contrast(email_html.ASH, email_html.ZED) >= 4.5


def test_the_dark_style_block_covers_every_class_used() -> None:
    html = email_html.compose(_load(REPO, "reviewed"), SAMPLE, BASE).html
    used = set(re.findall(r'class="([^"]+)"', html))
    classes = {c for group in used for c in group.split()}
    for c in classes:
        assert f".{c} " in email_html._DARK_CSS, c
