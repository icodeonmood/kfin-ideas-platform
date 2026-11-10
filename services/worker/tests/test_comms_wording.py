"""Message wording keeps the product's promises (BLD-157). No database: each template is rendered from the seed with
the variables the renderer fills, so a sentence that offers something the product does not do, a reference number,
a build-team step or a broken plural fails here before HR reviews the words."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from comms import render
from comms.templates import render_text
from okf.frontmatter import parse

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "seed" / "company-repo" / "comms" / "templates"


def _template(name: str) -> tuple[str, str]:
    doc = parse((TEMPLATES / f"{name}.md").read_text(encoding="utf-8"))
    return str((doc.meta or {})["kfin"]["subject"]), doc.body


def _render(name: str, data: dict[str, Any]) -> tuple[str, str]:
    subject, body = _template(name)
    return render_text(subject, data).strip(), render_text(body, data)


BASE = {"recipient": {"first_name": "Asha"}, "links": {"idea": "https://club.example/ideas/IDEA-2026-000901"}}
IDEA = {"id": "IDEA-2026-000901", "one_line": "Branch forms wait a day", "strength": 2}


def test_no_template_promises_an_action_the_product_does_not_have() -> None:
    gone = (
        "reply in the app and tell us why",  # no such reply: the idea page has "Disagree with this?"
        "another look within",  # appealing a review desk decision is not built yet
        "credited for the reuse",  # nothing records credit for an adoption
        "working day(s) past",  # sent the moment the limit passes, so always "0"
        "more colleagues raised",  # the number is a running total
    )
    for path in sorted(TEMPLATES.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for words in gone:
            assert words not in text, (path.name, words)


def test_no_reference_number_reaches_a_contributor_message() -> None:
    for name in ("reviewed", "cluster-approved", "delivery-writeup-decided", "delivery-phase-changed"):
        subject, body = _template(name)
        assert "{{cluster.id}}" not in subject + body and "solution_id" not in subject + body, name


def test_joined_reads_right_for_one_and_for_many() -> None:
    one = BASE | {"idea": IDEA, "join": {"count": 1, "one": True, "many": False}}
    subject, body = _render("joined", one)
    assert subject == "A colleague raised the same thing as you"
    assert "Good news: a colleague has raised the same thing as your idea" in body
    many = BASE | {"idea": IDEA, "join": {"count": 3, "one": False, "many": True}}
    subject, body = _render("joined", many)
    assert subject == "3 colleagues have now raised the same thing as you"
    assert "1 colleagues" not in body and "more colleague" not in body


def test_group_messages_name_the_group_and_count_in_plain_plurals() -> None:
    cluster = {"name": "Outward register delays", "description": "", "other_count": 1, "one_other": True}
    subject, body = _render("cluster-approved", BASE | {"cluster": cluster})
    assert subject == "Your idea is now in a group: Outward register delays"
    assert "It holds one other idea." in body and "1 other ideas" not in body
    cluster |= {"other_count": 4, "one_other": False, "many_others": True}
    _, body = _render("cluster-approved", BASE | {"cluster": cluster})
    assert "It holds 4 other ideas." in body
    data = BASE | {"idea": IDEA, "outcome": {"grouped": True}, "cluster": {"name": "Outward register delays"}}
    _, body = _render("reviewed", data)
    assert "It's now part of **Outward register delays**, a group of similar ideas" in body


def test_suggestions_show_only_the_bullets_that_exist() -> None:
    for name in ("submitted", "quick-capture-nudge"):
        two = BASE | {"idea": IDEA | {"next_best": ["Add numbers", "Add evidence"]}}
        assert "What would help most:\n- Add numbers\n- Add evidence\n" in _render(name, two)[1], name
        one = BASE | {"idea": IDEA | {"next_best": ["Add numbers"]}}
        body = _render(name, one)[1]
        assert "- Add numbers\n\n" in body and "\n- \n" not in body, name
        none = BASE | {"idea": IDEA | {"next_best": []}}
        body = _render(name, none)[1]
        assert "What would help most" not in body and "\n- " not in body, name


def test_a_tier_change_down_never_reads_as_a_step_up() -> None:
    down = BASE | {"tier": {"up": False, "down": True, "from_name": "Flame", "to_name": "Glow"}}
    subject, body = _render("one-tier-changed", down)
    assert subject == "Your tier has changed" and "from Flame to Glow" in body
    assert "hotter" not in subject + body and "well done" not in body
    # An event queued before the old tier travelled with it: no blank "from  to".
    _, body = _render("one-tier-changed", BASE | {"tier": down["tier"] | {"from_name": ""}})
    assert "has moved your tier to Glow." in body and "from  to" not in body
    up = BASE | {"tier": {"up": True, "down": False, "from_name": "", "to_name": "Glow"}}
    assert "Your spark has moved to **Glow**." in _render("one-tier-changed", up)[1]


def test_redirect_and_reconsideration_point_to_disagree_on_the_idea_page() -> None:
    redirect: dict[str, Any] = {"team": "IT helpdesk", "message": "Ask IT.", "url": None}
    data = BASE | {"idea": IDEA, "redirect": redirect}
    _, body = _render("redirected", data | {"reviewer": {"name": "The review desk"}})
    assert "use **Disagree with this?**" in body and "[See your idea](https://club.example/ideas/" in body
    assert "Go to" not in body  # only when that team has a link
    _, body = _render("redirected", data | {"redirect": redirect | {"url": "https://it.example"}})
    assert "[Go to IT helpdesk](https://it.example)" in body
    reconsidered = BASE | {"idea": IDEA, "outcome": {"text": "x", "reason": "y"}, "next_step": {"text": "z"}}
    _, body = _render("reconsidered", reconsidered | {"member": {"name": "A member"}})
    assert "use **Disagree with this?**" in body and "[See your idea](" in body


def test_an_adoption_request_links_only_when_the_reader_can_open_the_desk() -> None:
    data = BASE | {"requester": {"lob_name": "MF Operations"}, "solution": {"title": "Mandate checks"}}
    _, body = _render("adoption-requested", data | {"request": {"context": "We would use it in MF ops"}})
    assert "Open the request" not in body and "the 1% Club team can put you in touch" in body
    assert "review desk" not in body
    assert "> We would use it in MF ops" in body
    data["links"] = BASE["links"] | {"request": "https://club.example/review"}
    _, body = _render("adoption-requested", data | {"request": {"context": ""}})
    assert "[Open the request](https://club.example/review)" in body and "In their words" not in body


def test_an_overdue_message_gives_the_limit_and_names_only_a_real_owner() -> None:
    data = BASE | {"breach": {"limit_wd": 5}, "links": {"item": "https://club.example/review"}}
    item = {"label": "The review of IDEA-2026-000901", "owner_name": "", "unassigned": True}
    subject, body = _render("sla-breached", data | {"item": item})
    assert subject == "Overdue: The review of IDEA-2026-000901"
    assert (
        "has passed its time limit of 5 working days. Nobody on the review desk has picked it up yet." in body
    )
    _, body = _render(
        "sla-breached", data | {"item": item | {"owner_name": "Synthetic Reviewer", "unassigned": False}}
    )
    assert "It is with Synthetic Reviewer." in body and "Nobody" not in body


def test_delivery_steps_use_the_plain_words_of_the_spec() -> None:
    """§4.9's words, with every build step from handoff to deploy as one step, "Being built" (BLD-157)."""
    from delivery.phases import PHASE_IDS, plain_step

    words = {p: plain_step(p) for p in PHASE_IDS}
    assert words == {
        "01-discover": "Discovery",
        "02-shape": "Writing the spec",
        "03-gate": "Spec review",
        **{
            p: "Being built" for p in ("04-handoff", "05-build", "06-test", "07-review", "08-qa", "09-deploy")
        },
        "handed-off": "With the development team",
        "shipped": "Shipped",
    }
    for word in [*words.values(), *render.PHASE_MESSAGE_WORDS.values()]:
        assert word and ":" not in word and "QA" not in word and "deploy" not in word.lower(), word
    data = BASE | {
        "delivery": {"label": "Outward register delays", "building": True, "phase_words": "Writing the spec"}
    }
    subject, body = _render("delivery-phase-changed", data)
    assert subject == "Outward register delays: Writing the spec"
    assert "The work on **Outward register delays** has moved to a new step: Writing the spec." in body


def test_the_ember_note_reads_as_an_issue() -> None:
    data = BASE | {
        "ember": {"month_label": "November 2026"},
        "links": {"ember": "https://club.example/ember/1"},
    }
    assert "This month's issue of The Ember is out" in _render("ember", data)[1]


def test_desk_viewers_match_the_access_policy() -> None:
    policy = yaml.safe_load((ROOT / "policy" / "rbac.yaml").read_text(encoding="utf-8"))
    allowed = {role for role, how in policy["capabilities"]["view_review_queue"].items() if how}
    allowed |= {alias for alias, role in (policy.get("role_aliases") or {}).items() if role in allowed}
    assert set(render.DESK_VIEWERS) == allowed
