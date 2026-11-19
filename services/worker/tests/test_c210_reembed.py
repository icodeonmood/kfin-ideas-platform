"""`python -m similar.reembed` (L-SIMILAR, BLD-080 BGE-M3, BLD-C210): every stored vector is rebuilt with the
configured embedder. A stand-in "model" (a different deterministic function) replaces `embeddings.embed`, so a
rebuilt vector is told apart from the seeded hash vector. Synthetic text only; `audit_log` refuses deletes, so the
tests count its rows from a baseline."""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Iterator
from typing import Any

import numpy as np
import pytest

import embeddings
from cluster.linkage import centroid
from core.db import vector_literal
from pii.log_rules import scan_log_lines
from similar import reembed
from similar.index import text_hash
from tests import helpers

REPO_A = "Ops re-check every SIP mandate by hand because bank fields are often missing at capture"
REPO_C = "Nominee fields on SIP forms are checked twice by two different desks before keying"
IDEA_TEXT = "Manual checks on SIP mandates delay registration\n\nForms wait a day for a second look."
FILE_TEXT = "page 1: SIP forms by branch, with the count of forms sent back for missing fields"
DETAIL = "7700012389"  # a synthetic folio number in the reviewed card: it must reach no model unmasked
CARD_DETAILS = f"Folio {DETAIL} was re-checked twice by hand before keying."
EXPECTED = {
    "chunks_repo": 2,
    "chunks_idea": 1,
    "chunks_file": 1,
    "chunks_skipped": 1,
    "corrections_reembedded": 1,
    "corrections_cleared": 1,
    "centroids_recomputed": 1,
    "centroids_cleared": 1,
}
ACTIONS = ("embeddings.rebuilt", "embeddings.rebuild_stopped")


def model_b(text: str) -> list[float]:
    """The stand-in model: deterministic, unit length, and different from `hash_embed` on the same text."""
    return embeddings.hash_embed("model-b " + text[::-1])


class StandIn:
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.seen: list[str] = []
        self.calls = 0
        self.fail_on_call = fail_on_call

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError("stand-in model stopped")
        self.seen.extend(texts)
        return [model_b(t) for t in texts]


def _vec(text: Any) -> list[float]:
    return [float(x) for x in json.loads(str(text))]


def _close(stored: Any, expected: list[float]) -> bool:
    return stored is not None and bool(np.allclose(_vec(stored), expected, atol=1e-5))


def _chunk(db: Any, source: str, value: str, text: str, **extra: Any) -> int:
    row = db.execute(
        f"INSERT INTO chunks ({source}, file_type, section, ordinal, text, embedding, trust, stage, area_ids, "  # noqa: S608
        "text_hash) VALUES (%s, %s, 'card', 0, %s, %s::vector, 'unverified', %s, %s, %s) RETURNING id",
        (
            value, extra.get("file_type", "idea"), text, vector_literal(embeddings.hash_embed(text)),
            extra.get("stage"), extra.get("areas", []), extra.get("text_hash"),
        ),
    ).fetchone()  # fmt: skip
    return int(row["id"])


def _idea(db: Any, *, repo_path: str | None, cluster_id: str) -> dict[str, Any]:
    idea_id = helpers.insert_idea(db, stage="in_cluster")
    row = db.execute(
        "UPDATE ideas SET repo_path = %s, cluster_id = %s, canvas = canvas || jsonb_build_object('details', %s::text) "
        "WHERE idea_id = %s RETURNING id, idea_id, canvas",
        (repo_path, cluster_id, CARD_DETAILS, idea_id),
    ).fetchone()
    return dict(row)


@pytest.fixture
def seeded(db: Any, test_database: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Chunks of all three kinds (and one with no text), two corrections and two clusters, all with hash vectors.
    DATABASE_URL points at this run's test database, so `main()` never reaches another one."""
    from core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", helpers.db_url(test_database))
    get_settings.cache_clear()
    db.execute("TRUNCATE clusters, corrections RESTART IDENTITY CASCADE")
    a = _idea(db, repo_path="ideas/2026/11/IDEA-2026-009101.md", cluster_id="CL-9101")
    c = _idea(db, repo_path="ideas/2026/11/IDEA-2026-009103.md", cluster_id="CL-9101")
    b = _idea(db, repo_path=None, cluster_id="CL-9102")  # no repo chunk: its cluster has no member vector
    for cid in ("CL-9101", "CL-9102"):
        db.execute(
            "INSERT INTO clusters (id, centroid) VALUES (%s, %s::vector)",
            (cid, vector_literal(embeddings.hash_embed(cid))),
        )
    made: dict[str, Any] = {"a": a, "b": b, "c": c}
    made["repo_a"] = _chunk(
        db, "repo_path", "ideas/2026/11/IDEA-2026-009101.md", REPO_A, stage="stable", areas=["AREA-ops"]
    )
    made["repo_c"] = _chunk(db, "repo_path", "ideas/2026/11/IDEA-2026-009103.md", REPO_C, stage="stable")
    made["empty"] = _chunk(db, "repo_path", "rules/empty.md", "", file_type="rule")
    made["idea"] = _chunk(
        db,
        "idea_uuid",
        str(b["id"]),
        IDEA_TEXT,
        stage="shared",
        areas=["AREA-process"],
        text_hash=text_hash(IDEA_TEXT),
    )
    made["file"] = _chunk(
        db, "attachment_id", "ATT-0001", FILE_TEXT, file_type="attachment", stage="in_cluster"
    )
    # The second correction's idea is not in the database: its card cannot be reached.
    for ref in (a["idea_id"], "IDEA-2026-999999"):
        item = db.execute(
            "INSERT INTO review_items (item_type, ref_id) VALUES ('idea', %s) RETURNING id", (ref,)
        ).fetchone()["id"]
        db.execute(
            "INSERT INTO corrections (review_item_id, field, proposed, final, card_embedding) "
            "VALUES (%s, 'system.areas', '[\"AREA-x\"]', '[\"AREA-ops\"]', %s::vector)",
            (item, vector_literal(embeddings.hash_embed(ref))),
        )
    made["audit_from"] = db.execute("SELECT coalesce(max(id), 0) AS n FROM audit_log").fetchone()["n"]
    yield made
    monkeypatch.undo()
    get_settings.cache_clear()


def _snapshot(db: Any) -> dict[str, list[tuple[Any, ...]]]:
    return {
        "chunks": [
            tuple(r.values())
            for r in db.execute(
                "SELECT id, embedding::text, text, text_hash, stage, area_ids, updated_at FROM chunks ORDER BY id"
            ).fetchall()
        ],
        "corrections": [
            tuple(r.values())
            for r in db.execute("SELECT id, card_embedding::text FROM corrections ORDER BY id").fetchall()
        ],
        "clusters": [
            tuple(r.values())
            for r in db.execute("SELECT id, centroid::text, updated_at FROM clusters ORDER BY id").fetchall()
        ],
    }


def _audits(db: Any, since: int) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT actor, action, entity, before, after, reason FROM audit_log WHERE id > %s AND action = ANY(%s) "
            "ORDER BY id",
            (since, list(ACTIONS)),
        ).fetchall()
    ]


def _use(monkeypatch: pytest.MonkeyPatch, model: Callable[[list[str]], list[list[float]]]) -> None:
    monkeypatch.setattr(embeddings, "embed", model)  # the name `similar.reembed` calls


def test_l_similar_bld_080_c210_every_vector_is_rebuilt_from_its_own_text(
    db: Any,
    seeded: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    captured_logs: io.StringIO,
) -> None:
    logged_from = len(captured_logs.getvalue())
    before = _snapshot(db)
    model = StandIn()
    _use(monkeypatch, model)
    monkeypatch.setattr(reembed, "BATCH", 2)  # several batches, each committed on its own
    assert reembed.main([]) == 0
    out = capsys.readouterr()

    rows = {r["id"]: r for r in db.execute("SELECT *, embedding::text AS vec FROM chunks").fetchall()}
    for key, text in (("repo_a", REPO_A), ("repo_c", REPO_C), ("idea", IDEA_TEXT), ("file", FILE_TEXT)):
        assert _close(rows[seeded[key]]["vec"], model_b(text)), key
    assert _close(rows[seeded["empty"]]["vec"], embeddings.hash_embed(""))  # no text: left as it was
    # Only the vector changes: text, text_hash, stage, area_ids and updated_at stay.
    after = _snapshot(db)
    assert [r[:1] + r[2:] for r in after["chunks"]] == [r[:1] + r[2:] for r in before["chunks"]]
    assert rows[seeded["idea"]]["text_hash"] == text_hash(IDEA_TEXT)

    # The reviewed card is re-embedded masked; the unreachable one is cleared (corrections_for skips NULL).
    corr = db.execute("SELECT card_embedding::text AS vec FROM corrections ORDER BY id").fetchall()
    card = reembed.card_text(seeded["a"]["canvas"])
    assert DETAIL not in card and "••••89" in card
    assert _close(corr[0]["vec"], model_b(card))
    assert corr[1]["vec"] is None
    assert not any(DETAIL in t for t in model.seen)  # no unmasked detail reached the model

    # CL-9101: the normalised mean of its two members' new vectors; CL-9102 has no member vector, so NULL.
    cen = {r["id"]: r["c"] for r in db.execute("SELECT id, centroid::text AS c FROM clusters").fetchall()}
    want = centroid(np.asarray([model_b(REPO_A), model_b(REPO_C)], dtype=np.float64)).tolist()
    assert _close(cen["CL-9101"], want)
    assert cen["CL-9102"] is None

    # One audit row, with the mode and counts only; the output carries counts and the mode, never text.
    audits = _audits(db, seeded["audit_from"])
    assert len(audits) == 1
    row = audits[0]
    assert (row["actor"], row["action"], row["entity"], row["before"], row["reason"]) == (
        "process:reembed", "embeddings.rebuilt", "embeddings", None, None,
    )  # fmt: skip
    assert row["after"] == {"mode": "hash", **EXPECTED}
    dumped = json.dumps(row, default=str) + out.out + out.err
    for word in ("mandate", "Nominee", "registration", "branch", "olio", "keying", DETAIL):  # from each text
        assert word not in dumped, word
    assert "EMBEDDINGS_MODE=hash" in out.out
    assert "repo 2, idea 1, file 1" in out.out and "skipped (no text): 1" in out.out
    # The log line passes the log-scrubber rules (conftest scans every captured line again at the end).
    lines = [ln for ln in captured_logs.getvalue()[logged_from:].splitlines() if "embeddings.rebuilt" in ln]
    assert len(lines) == 1 and scan_log_lines(lines) == []
    assert json.loads(lines[0])["chunks_repo"] == 2


def test_l_similar_bld_c210_dry_run_changes_nothing(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _snapshot(db)
    model = StandIn()
    _use(monkeypatch, model)
    assert reembed.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert _snapshot(db) == before
    assert _audits(db, seeded["audit_from"]) == []
    assert model.seen == [reembed.PROBE]  # the embedder is still tried before anything else
    assert "dry run: nothing was changed" in out
    assert "repo 2, idea 1, file 1" in out and "re-embedded: 1 · cleared (card not reachable): 1" in out
    assert reembed.run(db, dry_run=True).__dict__ == EXPECTED


@pytest.mark.parametrize("broken", ["no_bge_library", "wrong_dimensions"])
def test_l_similar_bld_080_c210_an_embedder_that_does_not_load_changes_nothing(
    db: Any,
    seeded: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    broken: str,
) -> None:
    from core.config import get_settings

    # This venv has no sentence-transformers, like an image built without WITH_BGE=1.
    if broken == "no_bge_library":
        monkeypatch.setenv("EMBEDDINGS_MODE", "bge-m3")
        monkeypatch.setenv("EMBEDDINGS_MODEL_PATH", "")
        monkeypatch.setattr(embeddings, "_model", None)
        get_settings.cache_clear()
    else:
        _use(monkeypatch, lambda texts: [[0.5] * 384 for _ in texts])
    before = _snapshot(db)
    assert reembed.main([]) == 1
    err = capsys.readouterr().err
    assert "did not load" in err and "Nothing was changed." in err
    assert _snapshot(db) == before
    assert _audits(db, seeded["audit_from"]) == []
    get_settings.cache_clear()


def test_l_similar_bld_c210_a_second_run_gives_the_same_result(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, StandIn())
    first = reembed.run(db)
    once = _snapshot(db)
    second = reembed.run(db)
    twice = _snapshot(db)
    assert first == second and first.__dict__ == EXPECTED
    assert once["chunks"] == twice["chunks"] and once["corrections"] == twice["corrections"]
    assert [r[:2] for r in once["clusters"]] == [r[:2] for r in twice["clusters"]]
    assert [a["action"] for a in _audits(db, seeded["audit_from"])] == ["embeddings.rebuilt"] * 2


def test_l_similar_bld_c210_a_stopped_run_is_audited_and_simply_run_again(
    db: Any, seeded: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _snapshot(db)
    _use(monkeypatch, StandIn(fail_on_call=3))  # call 1 is the check, call 2 the first batch of two chunks
    monkeypatch.setattr(reembed, "BATCH", 2)
    assert reembed.main([]) == 1
    assert "run the command again" in capsys.readouterr().err
    mid = _snapshot(db)
    assert mid["chunks"][:2] != before["chunks"][:2]  # the first batch was committed …
    assert mid["chunks"][2:] == before["chunks"][2:]  # … the failed one rolled back, the rest not reached
    assert mid["corrections"] == before["corrections"] and mid["clusters"] == before["clusters"]
    stopped = _audits(db, seeded["audit_from"])
    assert [a["action"] for a in stopped] == ["embeddings.rebuild_stopped"]
    assert stopped[0]["after"] == {
        "mode": "hash", "error_type": "RuntimeError", **{k: 0 for k in EXPECTED}, "chunks_repo": 2,
    }  # fmt: skip

    _use(monkeypatch, StandIn())
    assert reembed.main([]) == 0
    rows = {r["id"]: r["vec"] for r in db.execute("SELECT id, embedding::text AS vec FROM chunks").fetchall()}
    assert _close(rows[seeded["idea"]], model_b(IDEA_TEXT))
    assert _close(rows[seeded["file"]], model_b(FILE_TEXT))
    assert [a["action"] for a in _audits(db, seeded["audit_from"])] == [
        "embeddings.rebuild_stopped",
        "embeddings.rebuilt",
    ]


def test_l_similar_bld_c210_every_reader_skips_a_cleared_vector(db: Any, seeded: dict[str, Any]) -> None:
    """The NULL paths: corrections_for skips a cleared correction, the batch and the lenses skip a NULL centroid."""
    from cluster.batch import load_clusters
    from router.corrections import corrections_for

    db.execute("UPDATE corrections SET card_embedding = NULL")
    db.execute("UPDATE clusters SET centroid = NULL")
    assert corrections_for(db, model_b(REPO_A)) == []
    assert all(c.centroid is None for c in load_clusters(db))
