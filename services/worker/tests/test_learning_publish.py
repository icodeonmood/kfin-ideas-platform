"""Approved glossary terms and area tags written into the company repo (BLD-136): an admin writes the words, they
are checked like public text, queued with IDs only, and only the repo writer writes the file. Synthetic only."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from learning import proposals
from ones.text import seal
from tests import helpers, test_delivery
from tests.test_ones import refused

ones_db = test_delivery.ones_db
cast = test_delivery.cast
crew = test_delivery.crew
NOW = dt.datetime(2026, 12, 18, 9, 0, tzinfo=dt.UTC)


def test_slugs() -> None:
    assert proposals.slug("IFSC code") == "ifsc-code"
    assert proposals.slug("  Payout / bank files ") == "payout-bank-files"


def _proposal(db: Any, kind: str, term: str | None = None) -> int:
    row = db.execute(
        "INSERT INTO learning_proposals (kind, period, payload) VALUES (%s, '2026-W51', '{}') RETURNING id",
        (kind,),
    ).fetchone()
    if term:
        db.execute(
            "UPDATE learning_proposals SET text_encrypted = %s WHERE id = %s",
            (seal(term, f"learning:{row['id']}"), row["id"]),
        )
    return int(row["id"])


@pytest.mark.stack
def test_an_approved_term_reaches_the_repo_only_through_the_writer(
    ones_db: Any, crew: Any, company_repo: Any, test_database: str
) -> None:
    from repo_writer.writer import RepoWriter

    db = ones_db
    pid = _proposal(db, "glossary_term", "PAYCHK")
    body = {
        "definition": "A daily check of payout files against bank masters before release.",
        "aliases": "pay check",
    }
    refused("not_approved", proposals.publish, db, crew["admin"], pid, body)
    proposals.decide(db, crew["admin"], pid, {"verdict": "approve"}, now=NOW)
    refused("forbidden", proposals.publish, db, crew["member"], pid, body)
    refused("text_too_short", proposals.publish, db, crew["admin"], pid, {"definition": "short"})
    out = proposals.publish(db, crew["admin"], pid, body, now=NOW)
    assert out["doc_id"] == "GL-paychk"
    refused("already_published", proposals.publish, db, crew["admin"], pid, body)
    event = db.execute(
        "SELECT payload FROM outbox WHERE event_type = 'taxonomy.glossary_added' AND aggregate_id = 'GL-paychk'"
    ).fetchone()
    assert dict(event["payload"]) == {"proposal_id": pid}  # IDs only
    assert not (company_repo / "taxonomy" / "glossary" / "GL-paychk.md").exists()  # nothing written here

    writer = RepoWriter(helpers.settings_for(company_repo, test_database))
    assert writer.acquire()
    try:
        writer.run_once()
    finally:
        writer.release()
    text = (company_repo / "taxonomy" / "glossary" / "GL-paychk.md").read_text(encoding="utf-8")
    assert "A daily check of payout files" in text and "pay check" in text
    assert "[GL-paychk.md](GL-paychk.md)" in (company_repo / "taxonomy" / "glossary" / "index.md").read_text()
    listed = next(p for p in proposals.listing(db) if p["id"] == pid)
    assert listed["doc_id"] == "GL-paychk" and listed["in_repo"] and not listed["can_publish"]


@pytest.mark.stack
def test_a_tag_never_overwrites_one_the_product_team_wrote(ones_db: Any, crew: Any) -> None:
    db = ones_db
    pid = _proposal(db, "area_tag")
    proposals.decide(db, crew["admin"], pid, {"verdict": "approve"}, now=NOW)
    refused(
        "doc_exists", proposals.publish, db, crew["admin"], pid,
        {"title": "Process", "description": "How work gets done: steps, handoffs, checks and rework."},
    )  # fmt: skip
    out = proposals.publish(
        db, crew["admin"], pid,
        {"title": "Payout files", "description": "Files that move money to investors and how they are checked."},
        now=NOW,
    )  # fmt: skip
    assert out["doc_id"] == "AREA-payout-files"
