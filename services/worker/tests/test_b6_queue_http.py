"""The review queue over HTTP (B6, AT-B6-01): sorted by due date, then lowest confidence first; filters by item
type, kind, LOB, category, strength, confidence band and age; only review roles may read it."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from core.db import connect
from tests.web import people

pytestmark = pytest.mark.stack
NOW = dt.datetime.now(dt.UTC)


@pytest.fixture
def queue() -> Iterator[Any]:
    with connect(autocommit=True) as conn, people(conn) as make:
        made: list[tuple[str, int]] = []
        specs = [  # (n, kind, category, strength, lob, due in days, confidence, age days)
            (991, "problem", "cost_saving", 2, "LOB-mf", 3, 0.9, 1),
            (992, "business_idea", "new_revenue", 4, "LOB-sif", 3, 0.3, 4),
            (993, "problem_with_solution", "cost_saving", 5, "LOB-mf", 1, 0.7, 6),
        ]
        for n, kind, cat, strength, lob, due, conf, age in specs:
            idea_id = f"IDEA-2026-990{n}"
            conn.execute(
                "INSERT INTO ideas (id, idea_id, submission_id, stage, contributor_code, kind, category, strength, "
                "canvas) VALUES (%s, %s, %s, 'scanned', 'CTR-0a1b2c', %s, %s, %s, %s)",
                (str(uuid.uuid4()), idea_id, f"SUB-2026-990{n}", kind, cat, strength,
                 json.dumps({"neutral_summary": f"Synthetic queue item {n}"})),
            )  # fmt: skip
            rid = conn.execute(
                "INSERT INTO review_items (item_type, ref_id, proposal, confidence, created_at) "
                "VALUES ('idea', %s, %s, %s, %s) RETURNING id",
                (idea_id, json.dumps({"system": {"lobs": [lob]}}), json.dumps({"system.areas": conf, "value.category": 0.95}),
                 NOW - dt.timedelta(days=age)),
            ).fetchone()["id"]  # fmt: skip
            conn.execute(
                "INSERT INTO sla_timers (entity_type, entity_id, stage, started_at, due_at) "
                "VALUES ('review_item', %s, 'review', %s, %s)",
                (str(rid), NOW, NOW + dt.timedelta(days=due)),
            )
            made.append((idea_id, rid))
        reviewer = make((("reviewer", None),)).browser()
        contributor = make().browser()
        core = make((("core_committee", None),)).browser()
        yield reviewer, contributor, made, core
        for idea_id, rid in made:
            conn.execute("DELETE FROM sla_timers WHERE entity_id = %s", (str(rid),))
            conn.execute("DELETE FROM review_items WHERE id = %s", (rid,))
            conn.execute("DELETE FROM ideas WHERE idea_id = %s", (idea_id,))


def ids(b: Any, query: str = "") -> list[str]:
    r = b.get(f"/api/review/items{query}")
    assert r.status_code == 200, r.text
    return [i["idea_id"] for i in r.json()["items"] if i["idea_id"].startswith("IDEA-2026-990")]


def test_sort_and_filters(queue: Any) -> None:
    reviewer, contributor, made, core = queue
    # Due soonest first; on the same due date the lower confidence first (0.3 before 0.9).
    assert ids(reviewer) == ["IDEA-2026-990993", "IDEA-2026-990992", "IDEA-2026-990991"]
    assert ids(reviewer, "?kind=business_idea") == ["IDEA-2026-990992"]
    assert ids(reviewer, "?category=cost_saving") == ["IDEA-2026-990993", "IDEA-2026-990991"]
    assert ids(reviewer, "?lob=LOB-sif") == ["IDEA-2026-990992"]
    assert ids(reviewer, "?strength=4") == ["IDEA-2026-990993", "IDEA-2026-990992"]
    assert ids(reviewer, "?band=low") == ["IDEA-2026-990992"]
    assert ids(reviewer, "?age=5") == ["IDEA-2026-990993"]
    assert ids(reviewer, "?type=disagreement") == []
    assert contributor.get("/api/review/items").status_code == 403

    # A core committee member sees the queue but may act only on an item they vetoed (BLD-092).
    assert core.get("/api/review/items").status_code == 200
    item = made[0][1]
    r = core.post(f"/api/review/items/{item}/action", json={"action": "decide"})
    assert r.status_code == 403
