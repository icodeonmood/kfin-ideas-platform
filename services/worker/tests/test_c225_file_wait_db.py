"""BLD-C225 to BLD-C227, L-HIDE.files, BLD-C107 (amended): files wait properly while the assistant is off.

- BLD-C225: while `ai.all` or `agent.gatekeeper` is off, the file check waits before the virus scan without using a
  try (`jobs.runner.JobWaits`: the job queued again, `attempts` as before the claim, `last_error`
  "waiting_gatekeeper", run 300 s on), the file stays checking with `checks.waiting_for` "gatekeeper", and its row
  reads "Waiting for the personal details check. It runs when the assistant is back." It never reaches "Didn't
  upload" while it only waits. A late switch-off or a spent budget waits the same way; the gateway failing, the
  scanner, the store and OCR are still tries, and back off and give up as before.
- BLD-C226: the ticker's watch makes waiting checks due within one tick of both switches being on, batched, the
  switches read again before each batch.
- BLD-C227: at worker start, rows r3 let die of its waits (THE EXACT RULE, a to e) go back to waiting, with the
  pinned log line, audit rows and names lane A's upgrade reads; rows outside the rule, real failures and every row
  from this build, never do.

The non-stack tests stand in the file store (a dict), the virus scanner, the sandbox's text layer and the file
gatekeeper, as BLD-C228's do; the one `stack` test uses the dev stack's store, scanner and sandbox. Synthetic people,
files and values only (non-negotiable 11). Everything made is removed afterwards except `audit_log`, whose trigger
refuses DELETE, so audit reads are scoped to this test's own ideas or to rows newer than the test's start."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError

from attachments import clamav
from attachments import files as F
from attachments.extract import Extracted
from core import killswitch
from core import logging as klog
from core.config import get_settings
from core.db import Conn
from hide import detect
from hide import files as hide_files
from jobs import handlers  # noqa: F401 (registers the job types)
from jobs.runner import JobWaits, run_one
from tests import f_teamup_fixtures as f
from tests import files as make

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
WORDS = "Investors call the branch about 40 times a day because the SMS only says R07."
WAITING = "Waiting for the personal details check. It runs when the assistant is back."
WORKER = "test-c225"


def _switch(db: Conn, state: str, *names: str) -> None:
    """Flip switches straight in the table, as the Admin page does: the worker's own set path never sees it."""
    db.execute(
        "UPDATE kill_switches SET state = %s WHERE name = ANY(%s)",
        (state, list(names or ("ai.all", "agent.gatekeeper"))),
    )
    killswitch.clear_cache()


@pytest.fixture
def db(db: Conn, monkeypatch: pytest.MonkeyPatch) -> Iterator[Conn]:
    """The shared `db` with the seeded company repo and the assistant off (no model call while files are added);
    afterwards this test's jobs, ideas and people go, and the switches are on again."""
    monkeypatch.setenv("COMPANY_REPO_PATH", str(SEED))
    get_settings.cache_clear()
    last_job = int(db.execute("SELECT coalesce(max(id), 0) AS n FROM jobs").fetchone()["n"])
    _switch(db, "off", "ai.all")
    yield db
    db.execute("DELETE FROM jobs WHERE id > %s", (last_job,))
    f.clean(db)
    _switch(db, "on")
    get_settings.cache_clear()


class _S3:
    """`store.client()` for the start sweep: `head_object` on the stood-in store."""

    def __init__(self, kept: dict[tuple[str, str], bytes], fail_after: int | None = None) -> None:
        self.kept, self.fail_after, self.calls = kept, fail_after, 0

    def head_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise ClientError({"Error": {"Code": "500"}}, "HeadObject")
        if (Bucket, Key) not in self.kept:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}


@pytest.fixture
def stood_in(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The file store (a dict by bucket and key), a clean scan that counts its calls, the sandbox's text layer and
    the file gatekeeper with nothing found: the check's own steps, without the stack's services."""
    kept: dict[tuple[str, str], bytes] = {}
    scans: list[int] = []
    out: dict[str, Any] = {"kept": kept, "scans": scans, "s3": _S3(kept)}

    def get(bucket: str, key: str) -> bytes:
        if (bucket, key) not in kept:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return kept[(bucket, key)]

    def scan(data: bytes, timeout: float = 60.0) -> clamav.ScanResult:
        scans.append(len(data))
        return clamav.ScanResult(True, None)

    monkeypatch.setattr(F.store, "put", lambda bucket, key, data: kept.__setitem__((bucket, key), data))
    monkeypatch.setattr(F.store, "get", get)
    monkeypatch.setattr(F.store, "delete", lambda bucket, key: kept.pop((bucket, key), None))
    monkeypatch.setattr(F.store, "exists", lambda bucket, key: (bucket, key) in kept)
    monkeypatch.setattr(F.store, "client", lambda: out["s3"])
    monkeypatch.setattr(F.clamav, "scan_bytes", scan)
    monkeypatch.setattr(
        F, "_extract", lambda kind, data, types: Extracted(pieces=[("page 1", WORDS)], pages=1, kind="pdf")
    )
    monkeypatch.setattr(F.hide_files, "gate_for", lambda conn, idea_uuid, text: detect.Gate([]))
    return out


@pytest.fixture
def cast(db: Conn) -> dict[str, Any]:
    """Kavya, with a draft to add files to; Arjun, who has nothing to do with it."""
    kavya = f.person(db, "Kavya Menon")
    return {"kavya": kavya, "arjun": f.person(db, "Arjun Nair"), "draft": f.draft(db, kavya)}


def _add(
    db: Conn, cast: dict[str, Any], draft: dict[str, Any] | None = None, name: str = "branch-notes.pdf"
) -> str:
    out = F.accept(
        db,
        user_id=cast["kavya"]["id"],
        name=name,
        data=make.pdf([WORDS]),
        draft_id=str((draft or cast["draft"])["id"]),
    )
    return str(out["id"])


def _row(db: Conn, att: str) -> dict[str, Any]:
    row = db.execute("SELECT * FROM attachments WHERE id = %s", (att,)).fetchone()
    assert row is not None
    return dict(row)


def _job(db: Conn, att: str, state: str | None = None) -> dict[str, Any]:
    """The file's newest check job (of a state, if given), with whether it is due and how far off it runs."""
    row = db.execute(
        "SELECT id, state, attempts, max_attempts, last_error, run_at <= now() AS due, "
        "extract(epoch FROM run_at - now()) AS wait_s FROM jobs "
        "WHERE type = %s AND payload->>'attachment_id' = %s AND (%s::text IS NULL OR state = %s) "
        "ORDER BY id DESC LIMIT 1",
        (F.JOB, att, state, state),
    ).fetchone()
    assert row is not None
    return dict(row)


def _first_due(db: Conn, att: str, *, last_try: bool = False) -> None:
    """Put this file's queued check job first in the queue (and on its last try), so `run_one` runs it."""
    db.execute(
        "UPDATE jobs SET run_at = '2000-01-01', "
        "attempts = CASE WHEN %s THEN max_attempts - 1 ELSE attempts END "
        "WHERE type = %s AND state = 'queued' AND payload->>'attachment_id' = %s",
        (last_try, F.JOB, att),
    )


def _run(db: Conn, att: str, *, last_try: bool = False) -> None:
    _first_due(db, att, last_try=last_try)
    assert run_one(db, WORKER)


def _r3_dead(db: Conn, att: str) -> None:
    """The row EXACTLY as r3's `_finish` leaves a file whose check ran out of tries on its waits: `upload_failed`,
    `checks` = {"type", "result": "check_failed", "ended_at"} and no `gatekeeper` key, the store key set and the
    quarantine copy kept; its job dead with `CheckWaits`."""
    db.execute(
        "UPDATE attachments SET file_state = 'upload_failed', state = 'rejected', "
        "checks = jsonb_build_object('type', checks->>'type', 'result', 'check_failed', 'ended_at', now()) "
        "WHERE id = %s",
        (att,),
    )
    db.execute(
        "UPDATE jobs SET state = 'dead', attempts = max_attempts, last_error = 'CheckWaits', locked_by = NULL "
        "WHERE type = %s AND payload->>'attachment_id' = %s",
        (F.JOB, att),
    )


class _Lines:
    """The worker's JSON log lines while the block runs."""

    def __init__(self) -> None:
        self.stream = io.StringIO()

    def __enter__(self) -> _Lines:
        klog.configure("INFO", self.stream)
        return self

    def __exit__(self, *exc: object) -> None:
        klog.configure("INFO")

    def events(self, event: str) -> list[dict[str, Any]]:
        out = []
        for line in self.stream.getvalue().splitlines():
            got = json.loads(line)
            if got.get("event") == event:
                got.pop("ts", None)
                out.append(got)
        return out


def _since(db: Conn) -> Any:
    return db.execute("SELECT clock_timestamp() AS t").fetchone()["t"]


def _audits(db: Conn, action: str, since: Any) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT actor, action, entity, before, after, reason FROM audit_log WHERE action = %s AND at >= %s "
            "ORDER BY id",
            (action, since),
        ).fetchall()
    ]


# ---- BLD-C225: a wait is not a try --------------------------------------------------------------------------------


def test_l_hide_files_bld_c225_a_wait_never_uses_a_try_never_scans_and_never_reaches_didnt_upload(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """With the assistant off, run after run past `max_attempts`: the job stays queued at 0 tries with
    `waiting_gatekeeper`, 300 s on; no scan runs; the file stays checking, waiting for the gatekeeper, and its row
    reads the waiting line, never "Didn't upload"; it opens for nobody, and the dead handler never runs."""
    att = _add(db, cast)
    since = _since(db)
    with _Lines() as lines:
        for _ in range(int(_job(db, att)["max_attempts"]) + 2):
            _run(db, att)
            job = _job(db, att)
            assert (job["state"], job["attempts"], job["last_error"]) == ("queued", 0, "waiting_gatekeeper")
            assert 290 < float(job["wait_s"]) <= 300
    assert stood_in["scans"] == []  # no scan is repeated while it is off
    row = _row(db, att)
    assert (row["file_state"], row["checks"]["waiting_for"]) == ("checking", "gatekeeper")
    assert "result" not in row["checks"]
    item = F.get_item(db, att, cast["kavya"]["id"])
    assert (item["state"], item["problem"]) == ("checking", WAITING)
    assert [i["problem"] for i in F.items_for(db, str(cast["draft"]["id"]), cast["kavya"]["id"])] == [WAITING]
    assert "view_url" not in item
    with pytest.raises(F.FileRefused):
        F.get_item(db, att, cast["arjun"]["id"])
    assert not db.execute("SELECT 1 FROM jobs WHERE type = %s AND state = 'dead' AND payload->>'attachment_id' = %s",
                          (F.JOB, att)).fetchone()  # fmt: skip
    assert _audits(db, "file.checked", since) == []
    waits = lines.events("jobs.waiting")
    assert waits and set(waits[0]) == {"level", "logger", "event", "job_id", "job_type", "code"}
    assert (waits[0]["logger"], waits[0]["job_type"], waits[0]["code"]) == (
        "jobs",
        "file.check",
        "waiting_gatekeeper",
    )


def test_l_hide_files_bld_c225_a_check_on_its_last_try_survives_a_wait(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """A file still checking ON ITS LAST TRY, under r3 or after real failures: a wait gives the claim's try back,
    so it is queued under its last try again, never dead, the file still checking."""
    att = _add(db, cast)
    _run(db, att, last_try=True)
    job = _job(db, att)
    assert (job["state"], job["attempts"], job["last_error"]) == (
        "queued",
        job["max_attempts"] - 1,
        "waiting_gatekeeper",
    )
    assert _row(db, att)["file_state"] == "checking"
    _switch(db, "off", "agent.gatekeeper")  # the gatekeeper's own switch waits the same way
    _switch(db, "on", "ai.all")
    _run(db, att)
    assert _job(db, att)["state"] == "queued" and _job(db, att)["attempts"] == job["max_attempts"] - 1
    assert F.get_item(db, att, cast["kavya"]["id"])["problem"] == WAITING


def test_l_hide_files_bld_c225_a_late_switch_off_or_spent_budget_waits_a_gateway_failure_is_a_try(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gatekeeper switched off while the file is read, or the day's budget spent: a wait. The gateway failing
    (a refusal, an answer off its schema, a timeout): a counted try with today's backoff, its reason kept."""
    files = {code: _add(db, cast, name=f"{code}.pdf") for code in ("switched_off", "daily_budget", "refusal")}
    _switch(db, "on")

    def waits(code: str) -> Any:
        def gate_for(conn: Conn, idea_uuid: str, text: str) -> detect.Gate:
            raise hide_files.GatekeeperWaits(code)

        return gate_for

    # The day's budget waits as `waiting_budget`, 30 minutes on, which the watch leaves alone (BLD-C236).
    for code, step, job_code in (
        ("switched_off", 300, "waiting_gatekeeper"),
        ("daily_budget", 1800, "waiting_budget"),
    ):
        monkeypatch.setattr(F.hide_files, "gate_for", waits(code))
        with pytest.raises(JobWaits) as wait:
            F.check(db, files[code])
        assert (wait.value.seconds, wait.value.code) == (step, job_code)
        assert _row(db, files[code])["checks"]["waiting_for"] == "gatekeeper"
        assert F.get_item(db, files[code], cast["kavya"]["id"])["problem"] == WAITING

    att = files["refusal"]
    monkeypatch.setattr(F.hide_files, "gate_for", waits("refusal"))
    _run(db, att)
    job = _job(db, att)
    assert (job["state"], job["attempts"], job["last_error"]) == ("queued", 1, "CheckRetry")
    assert 50 < float(job["wait_s"]) <= 60  # today's first step: 1 minute
    # A counted try with the assistant on: kept as "gateway", and the row never says "when the assistant is back".
    assert _row(db, att)["checks"]["waiting_for"] == "gateway"
    assert "problem" not in F.get_item(db, att, cast["kavya"]["id"])


def test_l_hide_files_bld_c225_real_failures_still_back_off_and_give_up_as_today(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the assistant on, the scanner down is a try: 1 minute on, then dead after the last try, the file
    "Didn't upload" with the wait it died of kept ("scanner"). An infected file ends at once."""
    att, infected = _add(db, cast), _add(db, cast, name="infected.pdf")
    _switch(db, "on")

    def down(data: bytes, timeout: float = 60.0) -> clamav.ScanResult:
        raise clamav.ScannerUnavailable("down")

    monkeypatch.setattr(F.clamav, "scan_bytes", down)
    _run(db, att)
    job = _job(db, att)
    assert (job["state"], job["attempts"], job["last_error"]) == ("queued", 1, "CheckRetry")
    assert 50 < float(job["wait_s"]) <= 60
    assert _row(db, att)["checks"]["waiting_for"] == "scanner"
    assert "problem" not in F.get_item(
        db, att, cast["kavya"]["id"]
    )  # only the gatekeeper's wait has the line
    _run(db, att, last_try=True)
    assert _job(db, att)["state"] == "dead"
    row = _row(db, att)
    assert (row["file_state"], row["checks"]["result"], row["checks"]["waiting_for"]) == (
        "upload_failed", "check_failed", "scanner")  # fmt: skip
    assert F.get_item(db, att, cast["kavya"]["id"])["problem"] == F.UPLOAD_FAILED

    monkeypatch.setattr(
        F.clamav, "scan_bytes", lambda data, timeout=60.0: clamav.ScanResult(False, "Eicar-Test")
    )
    _run(db, infected)
    assert _job(db, infected)["state"] == "done" and _row(db, infected)["file_state"] == "infected"
    assert "waiting_for" not in _row(db, infected)["checks"]
    assert F.start_sweep(db) == 0  # neither comes back: real failures, and rows from this build


# ---- BLD-C226: switched on, waiting checks run within a tick ------------------------------------------------------


def test_l_hide_files_bld_c226_bld_c225_switch_on_runs_a_waiting_check_within_one_tick(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """Switched on from the Admin page (straight in the table): the ticker's watch makes the waiting check due at
    its next tick, the runner checks it, the waiting line goes. While off, the watch moves nothing."""
    from core.watch import Watch

    att = _add(db, cast)
    _run(db, att)
    watch = Watch(ping=lambda: True)
    watch.run(db)
    assert not _job(db, att)["due"]  # still off: nothing moves
    _switch(db, "on")
    watch.run(db)
    job = _job(db, att)
    assert job["due"] and (job["state"], job["attempts"]) == ("queued", 0)
    _run(db, att)
    row = _row(db, att)
    assert (row["file_state"], row["checks"]["gatekeeper"]) == ("checked", "ran")
    assert "waiting_for" not in row["checks"] and stood_in["scans"]
    assert "problem" not in F.get_item(db, att, cast["kavya"]["id"])


def test_l_hide_files_bld_c226_bld_c225_the_requeue_is_batched_and_stops_when_switched_off_again(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """One batch per commit, the switches read again before each: switched off after the first batch, the second
    file keeps waiting."""
    first, second = _add(db, cast, name="first.pdf"), _add(db, cast, name="second.pdf")
    _run(db, first)
    _run(db, second)
    reads = iter([True, False])
    monkeypatch.setattr(F, "gatekeeper_on", lambda conn: next(reads))
    assert F.requeue_waiting(db, batch=1) == 1
    assert [_job(db, a)["due"] for a in (first, second)] == [True, False]


def test_l_hide_files_bld_c236_the_requeue_leaves_a_spent_budgets_wait_alone(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """BLD-C236 (review nit 2): a check waiting for tomorrow's budget is not made due on every tick, so its scan and
    OCR are not run again each minute; a check waiting for the switches still is."""
    budget, off = _add(db, cast, name="budget.pdf"), _add(db, cast, name="off.pdf")
    _run(db, budget)
    _run(db, off)
    db.execute(
        "UPDATE jobs SET last_error = 'waiting_budget' WHERE type = %s AND payload->>'attachment_id' = %s",
        (F.JOB, budget),
    )
    _switch(db, "on")
    assert F.requeue_waiting(db) >= 1
    assert [_job(db, a)["due"] for a in (budget, off)] == [False, True]


# ---- BLD-C227: the worker-start sweep (THE EXACT RULE) ------------------------------------------------------------


def test_l_hide_files_bld_c227_bld_c225_start_sweep_brings_an_r3_row_back_to_waiting_with_the_pinned_names(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """A row EXACTLY as r3's `_finish` leaves it: back to checking, waiting for the gatekeeper, its result cleared,
    a fresh job at 0 tries with `waiting_gatekeeper` due later, nothing opened. The pinned names: logger `files`,
    event `files.start_sweep` with `count` only; audit `file.start_sweep` (actor `system:files`, entity
    `files:start_sweep`, after {"count", "complete"}, before and reason empty) and one `file.check_requeued` per
    file (entity `idea:<uuid>`, after {"file_id", "from", "to"}). Run again, it moves nothing and says 0."""
    att = _add(db, cast)
    _r3_dead(db, att)
    since = _since(db)
    with _Lines() as lines:
        assert F.start_sweep(db) == 1
    row = _row(db, att)
    assert (row["file_state"], row["state"]) == ("checking", "quarantine")
    assert row["checks"] == {"type": "pdf", "waiting_for": "gatekeeper"}
    job = _job(db, att, "queued")
    assert (job["attempts"], job["last_error"], job["due"]) == (0, "waiting_gatekeeper", False)
    assert stood_in["scans"] == []  # nothing checked
    assert lines.events("files.start_sweep") == [
        {"level": "info", "logger": "files", "event": "files.start_sweep", "count": 1}
    ]
    assert [a["after"] for a in _audits(db, "file.start_sweep", since)] == [{"count": 1, "complete": True}]
    sweep = _audits(db, "file.start_sweep", since)[0]
    assert (sweep["actor"], sweep["entity"], sweep["before"], sweep["reason"]) == (
        "system:files", "files:start_sweep", None, None)  # fmt: skip
    moved = _audits(db, "file.check_requeued", since)
    assert [(m["actor"], m["entity"], m["after"]) for m in moved] == [
        (
            "system:files",
            f"idea:{cast['draft']['id']}",
            {"file_id": att, "from": "upload_failed", "to": "checking"},
        )
    ]
    assert _audits(db, "file.opened", since) == []
    assert F.get_item(db, att, cast["kavya"]["id"])["problem"] == WAITING
    with pytest.raises(F.FileRefused):
        F.content(db, att, cast["kavya"]["id"])  # not checked: it opens for nobody, its uploader included
    with pytest.raises(F.FileRefused):
        F.get_item(db, att, cast["arjun"]["id"])

    with _Lines() as lines:
        assert F.start_sweep(db) == 0  # idempotent: the row is checking now
    assert lines.events("files.start_sweep")[0]["count"] == 0
    assert _audits(db, "file.start_sweep", since)[-1]["after"] == {"count": 0, "complete": True}


def test_l_hide_files_bld_c227_bld_c225_start_sweep_moves_only_rows_inside_the_exact_rule(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """One row per condition that fails (a to e), one per real-failure code, and rows from this build (a
    `waiting_for` key): none comes back. The one r3 row beside them does."""
    s = get_settings()
    kept = stood_in["kept"]
    kavya = cast["kavya"]
    withdrawn, merged, into = f.draft(db, kavya), f.draft(db, kavya), f.draft(db, kavya)
    good = _add(db, cast, name="good.pdf")
    _r3_dead(db, good)
    stay: dict[str, str] = {}

    def r3(name: str, draft: dict[str, Any] | None = None) -> str:
        att = _add(db, cast, draft, name=f"{name}.pdf")
        _r3_dead(db, att)
        stay[name] = att
        return att

    r3("withdrawn", withdrawn)  # a: added first, then the idea withdrawn or merged
    r3("merged", merged)  # a
    db.execute("UPDATE ideas SET status = 'withdrawn' WHERE id = %s", (withdrawn["id"],))
    db.execute("UPDATE ideas SET merged_into = %s WHERE id = %s", (into["id"], merged["id"]))
    for state, code in (("infected", "virus"), ("locked", "locked"), ("too_big", "too_big"),
                        ("upload_failed", "no_copy"), ("upload_failed", "unreadable"),
                        ("upload_failed", "timeout"), ("upload_failed", "crashed"),
                        ("upload_failed", "not_checkable")):  # fmt: skip
        att = r3(f"{state}-{code}")  # b, c: a real failure
        db.execute(
            "UPDATE attachments SET file_state = %s, checks = checks || jsonb_build_object('result', %s::text) "
            "WHERE id = %s",
            (state, code, att),
        )
    att = r3("gatekeeper-ran")  # c
    db.execute('UPDATE attachments SET checks = checks || \'{"gatekeeper": "ran"}\' WHERE id = %s', (att,))
    for reason in ("scanner", "store", "ocr", "gatekeeper", "none"):  # c: rows from this build
        att = r3(f"this-build-{reason}")
        db.execute(
            "UPDATE attachments SET checks = checks || jsonb_build_object('waiting_for', %s::text) WHERE id = %s",
            (reason, att),
        )
    att = r3("masked-copy")  # d
    db.execute("UPDATE attachments SET masked_store_key = %s WHERE id = %s", (f"files/{att}-masked", att))
    att = r3("in-clean")  # d
    kept[(s.s3_bucket_clean, _row(db, att)["store_key"])] = b"%PDF-1.4"
    att = r3("hidden-detail")  # d
    db.execute(
        "INSERT INTO hidden_details (idea_uuid, source, source_id, kind, masked) VALUES (%s, 'file', %s, 'pan', %s)",
        (cast["draft"]["id"], att, "PAN ••••4F"),
    )
    att = r3("copy-missing")  # e
    kept.pop((s.s3_bucket_quarantine, _row(db, att)["store_key"]))
    att = r3("copy-gone")  # e: the failed copies' sweep marked it gone
    db.execute('UPDATE attachments SET checks = checks || \'{"copy": "gone"}\' WHERE id = %s', (att,))
    # e's "store_key is set": a file row without one cannot exist (attachments_file_has_object), so no row here.
    before = {name: (_row(db, a)["file_state"], _row(db, a)["checks"]) for name, a in stay.items()}

    assert F.start_sweep(db) == 1
    assert _row(db, good)["file_state"] == "checking"
    after = {name: (_row(db, a)["file_state"], _row(db, a)["checks"]) for name, a in stay.items()}
    assert after == before
    for att in stay.values():
        assert not db.execute(
            "SELECT 1 FROM jobs WHERE type = %s AND state = 'queued' AND payload->>'attachment_id' = %s",
            (F.JOB, att),
        ).fetchone()


def test_l_hide_files_bld_c227_bld_c225_a_stuck_file_and_a_really_failed_one_switch_on_runs_only_the_stuck_one(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """Lane E's (e): after the start sweep, switching the assistant on checks the file that only died of waits;
    the infected one and this build's scanner failure stay as they were."""
    from core.watch import Watch

    stuck = _add(db, cast, name="stuck.pdf")
    _r3_dead(db, stuck)
    infected = _add(db, cast, name="infected.pdf")
    _r3_dead(db, infected)
    db.execute("UPDATE attachments SET file_state = 'infected', checks = checks || '{\"result\": \"virus\"}' "
               "WHERE id = %s", (infected,))  # fmt: skip
    scanner = _add(db, cast, name="scanner.pdf")
    _r3_dead(db, scanner)
    db.execute(
        'UPDATE attachments SET checks = checks || \'{"waiting_for": "scanner"}\' WHERE id = %s', (scanner,)
    )
    assert F.start_sweep(db) == 1
    _switch(db, "on")
    Watch(ping=lambda: True).run(db)
    assert _job(db, stuck, "queued")["due"]
    _run(db, stuck)
    assert _row(db, stuck)["file_state"] == "checked"
    assert (_row(db, infected)["file_state"], _row(db, scanner)["file_state"]) == (
        "infected",
        "upload_failed",
    )


def test_l_hide_files_bld_c227_bld_c225_start_sweep_resets_r3s_live_waiters_outside_its_count(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """r3 counted waits as tries: a file check still queued with `CheckWaits` gets 0 tries and `waiting_gatekeeper`,
    logged as `jobs.waits_reset` with `job_count` only, and the count line does not include it."""
    att = _add(db, cast)
    db.execute(
        "UPDATE jobs SET attempts = 4, last_error = 'CheckWaits', run_at = now() + interval '6 hours' "
        "WHERE type = %s AND payload->>'attachment_id' = %s",
        (F.JOB, att),
    )
    with _Lines() as lines:
        assert F.start_sweep(db) == 0
    job = _job(db, att)
    assert (job["state"], job["attempts"], job["last_error"]) == ("queued", 0, "waiting_gatekeeper")
    reset = lines.events("jobs.waits_reset")
    assert len(reset) == 1 and set(reset[0]) == {"level", "logger", "event", "job_count"}
    assert reset[0]["logger"] == "jobs" and reset[0]["job_count"] >= 1
    assert _row(db, att)["file_state"] == "checking"


def test_l_hide_files_bld_c236_start_sweep_leaves_this_builds_retries_in_their_backoff(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """BLD-C236 (review nit 4): this build's counted retries record `CheckRetry`, so a worker restart's r3 reset
    (which reads r3's `CheckWaits` only) neither gives their tries back nor makes them wait for the gatekeeper."""
    att = _add(db, cast)
    db.execute(
        "UPDATE jobs SET attempts = 2, last_error = 'CheckRetry', run_at = now() + interval '15 minutes' "
        "WHERE type = %s AND payload->>'attachment_id' = %s",
        (F.JOB, att),
    )
    F.start_sweep(db)
    job = _job(db, att)
    assert (job["state"], job["attempts"], job["last_error"]) == ("queued", 2, "CheckRetry")


def test_l_hide_files_bld_c227_bld_c225_a_sweep_that_fails_part_way_says_so_and_audits_complete_false(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The store stops answering after the first batch: the first file moved stays moved, `files.start_sweep_failed`
    carries `count` and `error_type` only, and the run's audit row says `complete` false."""
    first, second = _add(db, cast, name="first.pdf"), _add(db, cast, name="second.pdf")
    _r3_dead(db, first)
    _r3_dead(db, second)
    monkeypatch.setattr(F, "BATCH", 1)
    stood_in["s3"] = _S3(stood_in["kept"], fail_after=2)  # first's two reads answer, then the store fails
    since = _since(db)
    with _Lines() as lines:
        assert F.start_sweep(db) == 1
    failed = lines.events("files.start_sweep_failed")
    assert failed == [{"level": "error", "logger": "files", "event": "files.start_sweep_failed", "count": 1,
                       "error_type": "ClientError"}]  # fmt: skip
    assert lines.events("files.start_sweep") == []
    assert _audits(db, "file.start_sweep", since)[-1]["after"] == {"count": 1, "complete": False}
    assert (_row(db, first)["file_state"], _row(db, second)["file_state"]) == ("checking", "upload_failed")


def test_l_hide_files_bld_c227_bld_c225_the_failed_copies_sweep_keeps_an_r3_copy_for_its_retention_only(
    db: Conn, cast: dict[str, Any], stood_in: dict[str, Any]
) -> None:
    """Condition e and `sweep_failed_copies`: an r3 row's quarantine copy is kept until `ended_at` is older than
    the failed uploads' retention (24 hours in the seeded rules), then deleted and marked gone, and the start
    sweep no longer brings it back."""
    s = get_settings()
    att = _add(db, cast)
    _r3_dead(db, att)
    key = _row(db, att)["store_key"]
    db.execute(  # the sweep deletes only while the latest start sweep finished (BLD-C242)
        "INSERT INTO audit_log (actor, action, entity, after) VALUES "
        "('system:files', 'file.start_sweep', 'files:start_sweep', '{\"count\": 0, \"complete\": true}'::jsonb)"
    )
    F.sweep_failed_copies(db)
    assert (s.s3_bucket_quarantine, key) in stood_in["kept"]
    db.execute(
        "UPDATE attachments SET checks = checks || jsonb_build_object('ended_at', now() - interval '25 hours') "
        "WHERE id = %s",
        (att,),
    )
    F.sweep_failed_copies(db)
    assert (s.s3_bucket_quarantine, key) not in stood_in["kept"]
    assert _row(db, att)["checks"]["copy"] == "gone"
    assert F.start_sweep(db) == 0


# ---- the stack: an r3-shaped dead row on the dev stack's store, scanner and sandbox --------------------------------


@pytest.mark.stack
def test_l_hide_files_bld_c227_bld_c225_stack_an_r3_dead_row_comes_back_and_is_checked_on_switch_on(
    db: Conn, cast: dict[str, Any]
) -> None:
    """Lane E's stack test: a file added through the real store, left as r3 leaves a file that died of its waits;
    the worker-start sweep brings it back to waiting with the count line, and switching `ai.all` on checks it
    through the real scanner and sandbox and the gatekeeper (the gateway's fake route)."""
    from attachments import store
    from core.watch import Watch
    from gateway import limits
    from gateway.routes import FAKE_SCRIPT

    limits.reset()
    FAKE_SCRIPT.clear()
    s = get_settings()
    att = _add(db, cast)
    key = _row(db, att)["store_key"]
    try:
        _r3_dead(db, att)
        assert store.exists(s.s3_bucket_quarantine, key)
        since = _since(db)
        with _Lines() as lines:
            assert F.start_sweep(db) == 1
        assert lines.events("files.start_sweep") == [
            {"level": "info", "logger": "files", "event": "files.start_sweep", "count": 1}
        ]
        assert _audits(db, "file.start_sweep", since)[-1]["after"] == {"count": 1, "complete": True}
        assert F.get_item(db, att, cast["kavya"]["id"])["problem"] == WAITING
        _switch(db, "on")
        Watch(ping=lambda: True).run(db)
        assert _job(db, att, "queued")["due"]
        _run(db, att)
        row = _row(db, att)
        assert (row["file_state"], row["checks"]["gatekeeper"]) == ("checked", "ran")
        assert "waiting_for" not in row["checks"]
    finally:
        FAKE_SCRIPT.clear()
        store.delete(s.s3_bucket_quarantine, key)
        store.delete(s.s3_bucket_clean, key)


def test_l_hide_files_bld_c225_the_waiting_line_is_the_one_lane_g_pins() -> None:
    """J-SHARE/v8 pins these words (To confirm later, HR): the line, and the names the upgrade reads."""
    assert F.WAITING_LINE == WAITING
    assert (F.GATEKEEPER, F.WAITING_GATEKEEPER, F.WAIT_STEP_S, F.SYSTEM) == (
        "gatekeeper", "waiting_gatekeeper", 300, "system:files")  # fmt: skip
    assert F.log._logger.name == "files"
