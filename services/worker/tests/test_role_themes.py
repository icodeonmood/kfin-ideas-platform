"""Recurring friction themes for each role (BLD-139): the role-themes agent works from checked summaries only,
its themes are card-safe and grouped by real refs, only counts are kept, and only approved themes show on the
lenses page. Synthetic text only."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from gateway import checks, fakes
from gateway.spec import load
from learning import role_themes
from tests import helpers, test_delivery
from tests.test_ones import refused

ones_db = test_delivery.ones_db
cast = test_delivery.cast
crew = test_delivery.crew
ROOT = Path(__file__).resolve().parents[3]
NOW = dt.datetime(2026, 12, 14, 4, 0, tzinfo=dt.UTC)


def test_examples_and_fake_outputs_pass_the_schema_and_the_checks() -> None:
    spec = load("role-themes")
    schema = json.loads((ROOT / "agents" / "role-themes" / "schema.json").read_text())
    for ex in spec.examples:
        jsonschema.validate(ex.output, schema)
        assert checks.run("role-themes", ex.input, ex.output, None) == []
    for line in (ROOT / "eval" / "golden" / "role_themes.jsonl").read_text().splitlines():
        case = json.loads(line)
        out = fakes.output_for(spec, case["input"])
        jsonschema.validate(out, schema)
        assert checks.run("role-themes", case["input"], out, None) == [], case["id"]


def test_the_checks_refuse_unknown_refs_repeats_and_tags() -> None:
    sent = {"role": "Operations executive", "ideas": [{"ref": f"I{n}", "summary": "x"} for n in (1, 2, 3)]}
    out = {"themes": [
        {"name": "Re-checking by hand", "description": "Forms are checked again by hand.", "refs": ["I1", "I9"]},
        {"name": "Same idea twice", "description": "The first idea appears again here.", "refs": ["I1", "I2"]},
        {"name": "[[CLIENT_AMC_1]] delays", "description": "Files from one client arrive late.", "refs": ["I3", "I2"]},
    ]}  # fmt: skip
    problems = " ".join(checks.run("role-themes", sent, out, None))
    assert "refs that are not in the input" in problems
    assert "repeats an idea already in a theme" in problems
    assert "must not contain tags" in problems


@pytest.mark.stack
def test_themes_wait_for_the_product_team_and_keep_counts_only(
    ones_db: Any, crew: Any, monkeypatch: Any
) -> None:
    db = ones_db
    monkeypatch.setattr(role_themes, "_role_names", lambda: {"ROLE-ops-executive": "Operations executive"})
    summaries = [
        "SIP mandate bank fields are re-checked by hand after capture.",
        "Payout files are checked twice by hand before release.",
        "Change-of-bank requests arrive without a cancelled cheque.",
        "Nominee forms come back because a witness signature is missing.",
    ]
    for n, text in enumerate(summaries):
        idea = helpers.insert_idea(db, stage="reviewed")
        db.execute(
            "UPDATE ideas SET canvas = jsonb_set(canvas, '{neutral_summary}', to_jsonb(%s::text)), "
            "roles_affected = '{ROLE-ops-executive}', area_ids = %s, submitted_at = %s WHERE idea_id = %s",
            (
                text,
                ["AREA-process"] if n < 2 else ["AREA-customer-experience"],
                NOW - dt.timedelta(days=3),
                idea,
            ),
        )
    assert role_themes.propose(db, NOW, "2026-W51") == 1
    assert role_themes.propose(db, NOW, "2026-W51") == 0  # once per role per week
    row = db.execute("SELECT id, themes FROM role_themes WHERE role_id = 'ROLE-ops-executive'").fetchone()
    stored = json.dumps(row["themes"])
    assert "IDEA-" not in stored and "re-checked by hand" not in stored  # counts and theme words only
    assert role_themes.approved(db) == []  # nothing shows before a person approves
    refused("forbidden", role_themes.decide, db, crew["member"], row["id"], {"verdict": "approve"})
    role_themes.decide(db, crew["admin"], row["id"], {"verdict": "approve"}, now=NOW)
    shown = role_themes.approved(db)
    assert (
        shown
        and shown[0]["role"] == "Operations executive"
        and all(t["ideas"] >= 2 for t in shown[0]["themes"])
    )
