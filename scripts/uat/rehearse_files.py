"""BLD-A239, BLD-A250: three synthetic files on FROM for the upgrade rehearsal, through FROM's own code.

`scripts/uat/rehearse-upgrade.sh` (REHEARSE_APP_ENV=prod, phase `files-from`) pipes this file into FROM's running
worker, after the synthetic HR import, with FROM's shape:

    docker exec -i kfin-ideas-uat-rehearsal-worker-1 python - plant <r3|waits> < scripts/uat/rehearse_files.py

The shape (BLD-A250) is what FROM's file check does while the gatekeeper is off. `r3` (launch-2026-11-20-r3 and
earlier) counts each wait as a failed try. `waits` (lane C's file waits, BLD-C225, from launch-2026-11-20-r4 on)
gives the try back: the job goes back to `queued` with `last_error` "waiting_gatekeeper", due in 300 s, and the file
stays `checking` with `checks.waiting_for` "gatekeeper"; that wait comes before the virus scan. The rehearsal picks the
shape from FROM's tree (`class JobWaits` in services/worker/jobs/runner.py); this file checks it against FROM's
running code (`jobs.runner.JobWaits`) and stops, before it plants anything, when the two differ.

It is never imported by the app. Each file goes in as the web app sends one: a draft by `draft.store.create` (behind
`POST /internal/drafts`), then the file by `attachments.files.accept` (behind `POST /internal/files`), as a synthetic
person (SYN-, `@kfintech.example`). FROM's own worker then checks them, with AI off:

- D, dead by waits: a plain synthetic text file, its check job on its last try, due now. `r3`: its check waits on
  the gatekeeper, so r3 ends it `upload_failed` (`check_failed`, no `gatekeeper` key, the quarantine copy kept).
  `waits`: the last try is given back, so D stays `checking`, waiting for the gatekeeper; it never reads "Didn't
  upload".
- W, waiting on its last try: the same, but its last try is 6 hours away, so FROM never runs it before the upgrade.
- V, a real failure: the EICAR antivirus test string (harmless), assembled here at run time, so the repo never
  holds it whole. `r3`'s scanner ends it `infected`. `waits`: the gatekeeper's wait comes first, so with AI off V is
  never scanned and stays `checking`, waiting for the gatekeeper, like D.

The one direct write is to the jobs table, a rehearsal-only shortcut for the 81-minute backoff: D's and W's
`file.check` job is set to its last try (`attempts = max_attempts - 1`), due now (D) or in 6 hours (W). Nothing is
written to `ideas` or `attachments` by hand.

Prints IDs and states only: never the file's text, its name or a person's name (non-negotiable 3). The lines
`files: <D|W|V> <file id> ...` are read back by the rehearsal; anything else it prints is for people. It imports only
what r3, r4 and r5 all have, with the same signatures; `jobs.runner` is imported where the shape is checked.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from attachments import files, store
from core.config import get_settings
from core.db import connect
from desk.store import code_of
from draft.store import Device, Owner, create
from identity.codes import emp_id_hash

PEOPLE = {"D": "SYN-00010", "W": "SYN-00011", "V": "SYN-00012"}  # synthetic people from the HR file of 20
NAMES = {"D": "rehearsal-d.md", "W": "rehearsal-w.md", "V": "rehearsal-v.md"}
TEXT = {
    "D": b"Synthetic rehearsal file D. No personal data.\n",
    "W": b"Synthetic rehearsal file W. No personal data.\n",
}
EICAR_HALVES = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-", "ANTIVIRUS-TEST-FILE!$H+H*")
LAST_TRY = {"D": "0 seconds", "W": "6 hours"}
# FROM's file check while the gatekeeper is off: r3 counts each wait as a try; waits gives the try back (BLD-C225).
SHAPES = ("r3", "waits")
# waits: the file waits for the gatekeeper and its job is put back, not failed (the names BLD-C225 pins).
WAITING = (
    "SELECT EXISTS (SELECT 1 FROM jobs WHERE type = 'file.check' AND payload->>'attachment_id' = %(id)s "
    "AND state = 'queued' AND attempts < max_attempts AND last_error = 'waiting_gatekeeper' AND run_at > now()) "
    "AND NOT EXISTS (SELECT 1 FROM jobs WHERE type = 'file.check' AND payload->>'attachment_id' = %(id)s "
    "AND state = 'dead') AND EXISTS (SELECT 1 FROM attachments WHERE id = %(id)s AND file_state = 'checking' "
    "AND checks->>'waiting_for' = 'gatekeeper') AS ok"
)
DEVICE = Device.of("laptop", "rehearsal-a239")


class Stop(Exception):
    """The phase stops: the message names IDs and states only."""


def _person(conn: Any, employee_id: str) -> Owner:
    row = conn.execute(
        "SELECT id FROM users WHERE emp_id_hash = %s AND active", (emp_id_hash(employee_id),)
    ).fetchone()
    if row is None:
        raise Stop(f"{employee_id} is not an active person: did people-prod import the synthetic HR file?")
    user_id = str(row["id"])
    code = code_of(conn, user_id)
    if code is None:
        raise Stop(f"{employee_id} has no contributor code")
    return Owner(user_id, code)


def _data(which: str) -> bytes:
    return "".join(EICAR_HALVES).encode("ascii") if which == "V" else TEXT[which]


def _add(conn: Any, which: str) -> tuple[str, str]:
    """A draft for the person, then the file on it: (draft id, file id)."""
    owner = _person(conn, PEOPLE[which])
    draft_id, _ = create(conn, owner, DEVICE, channel="web")
    try:
        item = files.accept(
            conn, user_id=owner.user_id, name=NAMES[which], data=_data(which), draft_id=draft_id
        )
    except files.FileRefused as exc:
        raise Stop(f"{which}: FROM refused the file ({exc.status} {exc.code})") from None
    return draft_id, str(item["id"])


def _last_try(conn: Any, which: str, att_id: str) -> None:
    """The rehearsal-only shortcut (see the module's note): only a queued job is moved, so a try already running ends
    first and this one follows it."""
    deadline = time.monotonic() + 120
    while True:
        row = conn.execute(
            "UPDATE jobs SET attempts = max_attempts - 1, run_at = now() + %s::interval "
            "WHERE type = 'file.check' AND payload->>'attachment_id' = %s AND state = 'queued' RETURNING id",
            (LAST_TRY[which], att_id),
        ).fetchone()
        if row is not None:
            return
        if time.monotonic() > deadline:
            raise Stop(f"{which} {att_id}: its file.check job was not queued within 120 s")
        time.sleep(1)


def _row(conn: Any, att_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT file_state, checks, store_key FROM attachments WHERE id = %s", (att_id,)
    ).fetchone()
    if row is None:
        raise Stop(f"{att_id} is gone")
    return dict(row)


def _ended(conn: Any, which: str, att_id: str, seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while True:
        row = _row(conn, att_id)
        if row["file_state"] != "checking":
            return row
        if time.monotonic() > deadline:
            raise Stop(f"{which} {att_id}: still checking after {seconds} s")
        time.sleep(2)


def _check_shape(shape: str) -> None:
    """The rehearsal picked the shape from FROM's tree; FROM's running worker must have the same, or nothing is
    planted (BLD-A250)."""
    import jobs.runner  # on r3 and every later build; JobWaits only from r4 on (BLD-C225)

    running = "waits" if hasattr(jobs.runner, "JobWaits") else "r3"
    if running != shape:
        raise Stop(f"the rehearsal asked for shape {shape}, but FROM's running worker has shape {running}")


def _waiting(conn: Any, which: str, att_id: str, seconds: int) -> None:
    """`waits`: until the file waits for the gatekeeper, its job put back (`WAITING`), never dead."""
    deadline = time.monotonic() + seconds
    while True:
        row = conn.execute(WAITING, {"id": att_id}).fetchone()
        if row is not None and row["ok"]:
            return
        if time.monotonic() > deadline:
            state = _row(conn, att_id)["file_state"]
            raise Stop(f"{which} {att_id}: {state}, not waiting for the gatekeeper after {seconds} s")
        time.sleep(2)


def plant(shape: str) -> None:
    _check_shape(shape)
    quarantine = get_settings().s3_bucket_quarantine
    with connect(autocommit=True) as conn:
        made = {which: _add(conn, which) for which in ("D", "W", "V")}
        for which in ("D", "W"):
            _last_try(conn, which, made[which][1])
        for which, (draft_id, att_id) in made.items():
            print(f"files: {which} {att_id} on draft {draft_id} of {PEOPLE[which]}", flush=True)

        att = made["D"][1]
        if shape == "waits":  # its last try, due now, is claimed and given back (BLD-A250)
            _waiting(conn, "D", att, 180)
            print(f"files: D {att} checking (waiting for the gatekeeper; FROM has the waits)", flush=True)
        else:
            d = _ended(conn, "D", att, 180)
            checks = d["checks"] or {}
            if d["file_state"] != "upload_failed" or checks.get("result") != "check_failed":
                raise Stop(
                    f"D {att}: {d['file_state']} ({checks.get('result')}), not upload_failed (check_failed)"
                )
            if "gatekeeper" in checks:
                raise Stop(f"D {att}: its checks have a gatekeeper key")
            if not d["store_key"] or not store.exists(quarantine, d["store_key"]):
                raise Stop(f"D {att}: no quarantine copy")
            print(
                f"files: D {att} upload_failed (check_failed, no gatekeeper key, quarantine copy kept)",
                flush=True,
            )

        att = made["W"][1]
        w = _row(conn, att)
        if w["file_state"] != "checking":
            raise Stop(f"W {att}: {w['file_state']}, not checking")
        print(f"files: W {att} checking (its last try is in 6 hours)", flush=True)

        att = made["V"][1]
        # waits: the gatekeeper's wait comes before the virus scan, so with AI off V is never scanned.
        if shape == "waits":
            _waiting(conn, "V", att, 180)
            print(
                f"files: V {att} checking (waiting for the gatekeeper, not scanned; FROM has the waits)",
                flush=True,
            )
        else:
            v = _ended(conn, "V", att, 300)
            if v["file_state"] != "infected":
                raise Stop(f"V {att}: {v['file_state']}, not infected")
            print(f"files: V {att} infected", flush=True)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "plant" or argv[1] not in SHAPES:
        print("usage: python - plant <r3|waits> < scripts/uat/rehearse_files.py", file=sys.stderr)
        return 2
    try:
        plant(argv[1])
    except Stop as exc:
        print(f"STOPPED: files-from: {exc}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
