"""A person's own lens (BLD-135): their ideas by stage group and the groups they are part of, counts only, never
anyone else's name or text, and only their own. Synthetic people only."""

from __future__ import annotations

import json
from typing import Any

import pytest

import lenses
from tests import helpers
from tests.test_points import person

pytestmark = pytest.mark.stack


@pytest.fixture
def ldb(db: Any, company_repo: Any, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    from views import common

    settings = helpers.settings_for(company_repo, test_database)
    monkeypatch.setattr(common, "get_settings", lambda: settings)
    return db


def test_your_lens_counts_your_ideas_and_groups_and_nothing_else(ldb: Any) -> None:
    db = ldb
    me, mine = person(db)
    _, other = person(db)
    stranger, _ = person(db)
    taken = {r["id"] for r in db.execute("SELECT id FROM clusters").fetchall()}
    cl = next(f"CL-{n}" for n in range(9100, 9999) if f"CL-{n}" not in taken)
    db.execute("INSERT INTO clusters (id, stage, distinct_contributors) VALUES (%s, 'picked', 2)", (cl,))
    a = helpers.insert_idea(db, contributor=mine, stage="in_cluster")
    b = helpers.insert_idea(db, contributor=other, stage="in_cluster")
    helpers.insert_idea(db, contributor=mine, stage="scanned")
    helpers.insert_idea(db, contributor=mine, stage="draft")  # drafts are not counted
    db.execute("UPDATE ideas SET cluster_id = %s WHERE idea_id = ANY(%s)", (cl, [a, b]))

    lens = lenses.mine(db, me)
    assert lens["shared"] == 2
    assert lens["ideas"]["Reviewed or grouped"] == 1 and lens["ideas"]["With the review desk"] == 1
    group = next(g for g in lens["groups"] if g["id"] == cl)
    assert (group["stage"], group["ideas"], group["colleagues"], group["how"]) == (
        "Picked", 2, 1, "Your idea is in it",
    )  # fmt: skip
    text = json.dumps(lens)
    assert other not in text and "Synthetic Person" not in text  # never who else
    assert lenses.mine(db, stranger)["groups"] == []  # only ever your own
